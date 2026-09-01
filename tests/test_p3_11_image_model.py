from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, replace
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from biella.artifact import ArtifactRef, ArtifactService
from biella.cloudflare_image_model import (
    CloudflareHttpResponse,
    CloudflareImageModel,
    CloudflareImageModelError,
)
from biella.execution import NodeExecutionAttempt, NodeExecutionService
from biella.graph import GraphRef, GraphService, Node, NodeRef
from biella.image_pack import ImageArtifactContentRef, ImageOperation, ImageSpecification
from biella.object_store import MemoryObjectStorageBackend
from biella.project import ProjectAccess, ProjectRef, ProjectStore
from biella.run import RunService
from biella.task import TaskRevisionService


_ENVIRONMENT = {
    "CLOUDFLARE_ACCOUNT_ID": "fixture-account",
    "CLOUDFLARE_API_TOKEN": "fixture-secret-token",
}


@dataclass(frozen=True)
class _Fixture:
    database: Path
    objects: MemoryObjectStorageBackend
    access: ProjectAccess
    attempt: NodeExecutionAttempt
    source: ImageArtifactContentRef
    reference: ImageArtifactContentRef
    prompt: ImageArtifactContentRef
    specification: ImageSpecification


def _image(
    width: int = 256,
    height: int = 256,
    *,
    image_format: str = "PNG",
    mode: str = "RGB",
) -> bytes:
    from PIL import Image

    output = BytesIO()
    color: object
    if mode == "RGBA":
        color = (0, 128, 255, 255)
    elif mode == "L":
        color = 255
    else:
        color = (0, 128, 255)
    Image.new(mode, (width, height), color=color).save(output, format=image_format)
    return output.getvalue()


def _cloudflare_response(payload: bytes) -> CloudflareHttpResponse:
    return CloudflareHttpResponse(
        200,
        {"content-type": "application/json"},
        json.dumps({"result": {"image": base64.b64encode(payload).decode("ascii")}}).encode(),
    )


def _input(
    database: Path,
    objects: MemoryObjectStorageBackend,
    access: ProjectAccess,
    *,
    role: str,
    payload: bytes,
    media_type: str,
) -> ImageArtifactContentRef:
    content = objects.put(payload, media_type=media_type)
    artifact = ArtifactService(database).create_artifact(
        access,
        project_ref=access.project_ref,
        role=role,
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="image.fixture",
        metadata={"media_type": media_type},
    )
    return ImageArtifactContentRef(
        access.project_ref,
        artifact.artifact_ref.value,
        content.value,
        content.digest,
    )


def _active_attempt(database: Path, access: ProjectAccess) -> NodeExecutionAttempt:
    task = TaskRevisionService(database).create_task(
        access,
        project_ref=access.project_ref,
        idempotency_key="cloudflare-image-task",
        task_type="image.generate",
        objective="Generate one exact image",
        required_capabilities=(),
        input_refs=(),
        output_contract={"result": "schema://biella/image-result/1"},
        constraints={},
        side_effect_authority="EXTERNAL_SIDE_EFFECT",
        data_policy_ref=None,
        egress_policy_ref=None,
        evidence_requirements=(),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="controller://cloudflare-image-tests",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(access.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "MODEL",
        (),
        (),
        (),
        {"result": "schema://biella/image-result/1"},
        None,
        "EXTERNAL_SIDE_EFFECT",
        {},
        (),
    )
    GraphService(database).create_graph(
        access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(node,),
        compiler_identity=None,
        compiler_version=None,
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    executions.prepare_run(access, run.run_ref)
    attempt = executions.lease_node(
        access,
        node.node_ref,
        authority_attempt=run_attempt,
        owner_ref="executor://cloudflare-image-tests",
        lease_seconds=1800,
        idempotency_key="cloudflare-image-node-lease",
    )
    executions.start_node(access, attempt, idempotency_key="cloudflare-image-node-start")
    return attempt


def _specification(
    project_ref: ProjectRef,
    source: ImageArtifactContentRef,
    reference: ImageArtifactContentRef,
    prompt: ImageArtifactContentRef,
    *,
    output_format: str = "image/png",
) -> ImageSpecification:
    return ImageSpecification.create(
        project_ref,
        "sphere",
        (source,),
        (reference,),
        ImageOperation("generate", "recipe://image/generate/v1", "c" * 64, {}),
        256,
        256,
        output_format,
        ("red", "green", "blue"),
        8,
        "profile://srgb/v1",
        "none",
        {},
        "model://cloudflare/flux-2-klein-4b",
        "1",
        "runtime://cloudflare/workers-ai/v1",
        7,
        {"guidance": "3.5"},
        prompt.artifact_ref,
        prompt.content_ref,
        prompt.content_sha256,
        "validator://image/png/v1",
        {"role": "image.generated"},
    )


def _setup(tmp_path: Path, output_format: str = "image/png") -> _Fixture:
    database = tmp_path / "biella.db"
    access = ProjectStore(database).create_project(
        namespace="images",
        display_name="Images",
    ).access
    objects = MemoryObjectStorageBackend()
    attempt = _active_attempt(database, access)
    source = _input(
        database,
        objects,
        access,
        role="image.source",
        payload=_image(),
        media_type="image/png",
    )
    reference = _input(
        database,
        objects,
        access,
        role="image.source",
        payload=_image(),
        media_type="image/png",
    )
    prompt = _input(
        database,
        objects,
        access,
        role="image.prompt",
        payload=b"a cobalt blue sphere",
        media_type="text/plain",
    )
    specification = _specification(
        access.project_ref,
        source,
        reference,
        prompt,
        output_format=output_format,
    )
    return _Fixture(
        database,
        objects,
        access,
        attempt,
        source,
        reference,
        prompt,
        specification,
    )


def _operation_specification(
    fixture: _Fixture,
    operation: str,
    sources: tuple[ImageArtifactContentRef, ...],
    *,
    size: tuple[int, int] = (256, 256),
    parameters: Mapping[str, str] | None = None,
    config: Mapping[str, str] | None = None,
    role: str = "image.edited",
) -> ImageSpecification:
    bound_parameters = {} if parameters is None else parameters
    bound_config = {"guidance": "3.5", "steps": "4"} if config is None else config
    encoded = json.dumps(
        {"operation": operation, "parameters": dict(bound_parameters)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return ImageSpecification.create(
        fixture.access.project_ref,
        f"sphere-{operation}",
        sources,
        (fixture.reference,),
        ImageOperation(
            operation,
            f"recipe://image/{operation}/v1",
            hashlib.sha256(encoded).hexdigest(),
            bound_parameters,
        ),
        size[0],
        size[1],
        "image/png",
        ("red", "green", "blue"),
        8,
        "profile://srgb/v1",
        "none",
        {},
        fixture.specification.model_ref,
        fixture.specification.model_version,
        fixture.specification.runtime_ref,
        17,
        bound_config,
        fixture.prompt.artifact_ref,
        fixture.prompt.content_ref,
        fixture.prompt.content_sha256,
        "validator://image/png/v1",
        {"role": role},
    )


def _artifact_ref(project_ref: ProjectRef, value: str) -> ArtifactRef:
    prefix = f"artifact://{project_ref.value}/"
    artifact_id, revision = value.removeprefix(prefix).rsplit("/", 1)
    return ArtifactRef(project_ref, artifact_id, int(revision))


def test_provider_contract_import_does_not_require_pillow(
    tmp_path: Path,
) -> None:
    pillow_blocker = tmp_path / "without-pillow" / "PIL"
    pillow_blocker.mkdir(parents=True)
    (pillow_blocker / "__init__.py").write_text(
        'raise ImportError("Pillow intentionally unavailable")\n',
        encoding="utf-8",
    )
    repository = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(pillow_blocker.parent), str(repository / "src"))
    )
    completed = subprocess.run(
        (
            sys.executable,
            "-c",
            "import biella; import biella.cloudflare_image_model",
        ),
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_cloudflare_model_accepts_official_response_and_publishes_with_provenance(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    payload = _image()
    calls: list[tuple[str, str, Mapping[str, str], bytes | None]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        calls.append((method, url, headers, body))
        return _cloudflare_response(payload)

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    result = adapter.generate(fixture.access, fixture.attempt, fixture.specification)
    assert result.project_ref == fixture.access.project_ref
    assert result.specification_digest == fixture.specification.canonical_digest
    assert result.output.content_sha256 == hashlib.sha256(payload).hexdigest()
    assert result.producer_attempt_id == fixture.attempt.attempt_id
    assert result.producer_fence == fixture.attempt.fence
    assert calls[0][0] == "POST"
    assert calls[0][1] == (
        "https://api.cloudflare.com/client/v4/accounts/fixture-account/ai/run/"
        "@cf/black-forest-labs/flux-2-klein-4b"
    )
    request_body = calls[0][3]
    assert request_body is not None
    assert b'name="prompt"' in request_body
    assert b"a cobalt blue sphere" in request_body
    assert b'input_image_0' in request_body

    artifact = ArtifactService(fixture.database).get_artifact(
        fixture.access,
        _artifact_ref(fixture.access.project_ref, result.output.artifact_ref),
    )
    assert artifact.role == "image.generated"
    assert artifact.producer_attempt_id == fixture.attempt.run_attempt_id
    assert artifact.producer_fence == fixture.attempt.run_fence
    assert {item.value for item in artifact.source_artifact_refs} == {
        fixture.prompt.artifact_ref,
        fixture.source.artifact_ref,
        fixture.reference.artifact_ref,
    }
    assert {item.value for item in artifact.source_content_refs} == {
        fixture.prompt.content_ref,
        fixture.source.content_ref,
        fixture.reference.content_ref,
    }
    assert _ENVIRONMENT["CLOUDFLARE_API_TOKEN"] not in repr(artifact.metadata)


@pytest.mark.parametrize("shape", ["binary", "string", "data", "data-uri", "url"])
def test_cloudflare_model_rejects_non_schema_response_shapes(
    tmp_path: Path,
    shape: str,
) -> None:
    fixture = _setup(tmp_path)
    payload = _image()
    encoded = base64.b64encode(payload).decode("ascii")

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        if shape == "binary":
            return CloudflareHttpResponse(200, {"content-type": "image/png"}, payload)
        if shape == "string":
            result: object = encoded
        elif shape == "data":
            result = {"data": encoded}
        elif shape == "data-uri":
            result = {"image": f"data:image/png;base64,{encoded}"}
        else:
            result = {"url": "https://images.example/output.png"}
        return CloudflareHttpResponse(
            200,
            {"content-type": "application/json"},
            json.dumps({"result": result}).encode(),
        )

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    with pytest.raises(CloudflareImageModelError, match="official|result.image"):
        adapter.generate(fixture.access, fixture.attempt, fixture.specification)


@pytest.mark.parametrize(
    ("operation", "size", "parameters", "requires_mask"),
    (
        ("edit", (256, 256), {"instruction": "remove scratches"}, False),
        ("inpaint", (256, 256), {"instruction": "repair center"}, True),
        (
            "outpaint",
            (320, 320),
            {"bottom": "32", "left": "32", "right": "32", "top": "32"},
            False,
        ),
    ),
)
def test_cloudflare_model_executes_operation_specific_edit_inpaint_and_outpaint(
    tmp_path: Path,
    operation: str,
    size: tuple[int, int],
    parameters: Mapping[str, str],
    requires_mask: bool,
) -> None:
    fixture = _setup(tmp_path)
    mask_payload = _image(mode="L")
    mask = _input(
        fixture.database,
        fixture.objects,
        fixture.access,
        role="image.mask",
        payload=mask_payload,
        media_type="image/png",
    )
    sources = (fixture.source, mask) if requires_mask else (fixture.source,)
    specification = _operation_specification(
        fixture,
        operation,
        sources,
        size=size,
        parameters=parameters,
    )
    response_payload = _image(*size)
    captured_body: bytes | None = None

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        nonlocal captured_body
        captured_body = body
        return _cloudflare_response(response_payload)

    result = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment=_ENVIRONMENT,
    ).generate(fixture.access, fixture.attempt, specification)

    assert captured_body is not None
    assert f'name="seed"\r\n\r\n{specification.seed}'.encode() in captured_body
    assert f'"operation":"{operation}"'.encode() in captured_body
    assert json.dumps(dict(parameters), sort_keys=True, separators=(",", ":")).encode() in captured_body
    assert b'name="guidance"' in captured_body
    assert b'name="operation"' not in captured_body
    assert b'name="config"' not in captured_body
    assert b'name="steps"' not in captured_body
    assert b'name="model_ref"' not in captured_body
    assert b'name="runtime_ref"' not in captured_body
    assert b'name="specification_digest"' not in captured_body
    assert b'input_image_0' in captured_body
    assert (b'input_image_2' in captured_body) is requires_mask
    artifact = ArtifactService(fixture.database).get_artifact(
        fixture.access,
        _artifact_ref(fixture.access.project_ref, result.output.artifact_ref),
    )
    assert artifact.role == "image.edited"
    assert result.specification_digest == specification.canonical_digest
    assert artifact.derivation_type == f"image.cloudflare.flux-2-klein-4b.{operation}"
    assert result.derivation == f"image.cloudflare.flux-2-klein-4b.{operation}"


def test_cloudflare_model_rejects_missing_operation_bindings_before_transport(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    called = False

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        nonlocal called
        called = True
        return CloudflareHttpResponse(200, {"content-type": "image/png"}, _image())

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    missing_mask = _operation_specification(fixture, "inpaint", (fixture.source,))
    with pytest.raises(CloudflareImageModelError, match="mask"):
        adapter.generate(fixture.access, fixture.attempt, missing_mask)
    missing_geometry = _operation_specification(fixture, "outpaint", (fixture.source,))
    with pytest.raises(CloudflareImageModelError, match="geometry"):
        adapter.generate(fixture.access, fixture.attempt, missing_geometry)
    wrong_role = _operation_specification(
        fixture,
        "edit",
        (fixture.source,),
        role="image.generated",
    )
    with pytest.raises(CloudflareImageModelError, match="role"):
        adapter.generate(fixture.access, fixture.attempt, wrong_role)
    unsupported_config = _operation_specification(
        fixture,
        "edit",
        (fixture.source,),
        config={"strength": "0.75"},
    )
    with pytest.raises(CloudflareImageModelError, match="unsupported"):
        adapter.generate(fixture.access, fixture.attempt, unsupported_config)
    wrong_steps = _operation_specification(
        fixture,
        "edit",
        (fixture.source,),
        config={"guidance": "3.5", "steps": "5"},
    )
    with pytest.raises(CloudflareImageModelError, match="fixed steps=4"):
        adapter.generate(fixture.access, fixture.attempt, wrong_steps)
    assert not called


@pytest.mark.parametrize("source_size", ((512, 256), (256, 512)))
def test_cloudflare_model_rejects_provider_inputs_at_512_pixels_before_transport(
    tmp_path: Path,
    source_size: tuple[int, int],
) -> None:
    fixture = _setup(tmp_path)
    oversized = _input(
        fixture.database,
        fixture.objects,
        fixture.access,
        role="image.source",
        payload=_image(*source_size),
        media_type="image/png",
    )
    specification = _operation_specification(
        fixture,
        "edit",
        (oversized,),
        size=source_size,
    )
    called = False

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        nonlocal called
        called = True
        return CloudflareHttpResponse(200, {"content-type": "image/png"}, _image())

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    with pytest.raises(CloudflareImageModelError, match="smaller than 512x512"):
        adapter.generate(fixture.access, fixture.attempt, specification)
    assert not called


def test_cloudflare_model_rejects_non_png_provider_input_before_transport(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    jpeg_source = _input(
        fixture.database,
        fixture.objects,
        fixture.access,
        role="image.source",
        payload=_image(image_format="JPEG"),
        media_type="image/jpeg",
    )
    specification = _operation_specification(fixture, "edit", (jpeg_source,))
    called = False

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        nonlocal called
        called = True
        return _cloudflare_response(_image())

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    with pytest.raises(CloudflareImageModelError, match="raw PNG"):
        adapter.generate(fixture.access, fixture.attempt, specification)
    assert not called


@pytest.mark.parametrize(
    ("payload", "output_format"),
    [
        pytest.param(b"not an image", "image/png", id="not-image"),
        pytest.param(_image(128, 128), "image/png", id="wrong-dimensions"),
        pytest.param(_image(mode="RGBA"), "image/png", id="wrong-channels"),
        pytest.param(_image(image_format="JPEG"), "image/png", id="wrong-format"),
        pytest.param(_image()[:-12], "image/png", id="truncated-valid-png"),
        pytest.param(
            _image(image_format="JPEG")[:-2],
            "image/jpeg",
            id="truncated-valid-jpeg",
        ),
    ],
)
def test_cloudflare_model_rejects_incomplete_or_contract_violating_output(
    tmp_path: Path,
    payload: bytes,
    output_format: str,
) -> None:
    fixture = _setup(tmp_path, output_format)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        return _cloudflare_response(payload)

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    with pytest.raises(CloudflareImageModelError, match="provider image"):
        adapter.generate(fixture.access, fixture.attempt, fixture.specification)


def _project_alias(
    project_ref: ProjectRef,
    foreign: ImageArtifactContentRef,
) -> ImageArtifactContentRef:
    prefix = f"artifact://{foreign.project_ref.value}/"
    suffix = foreign.artifact_ref.removeprefix(prefix)
    return ImageArtifactContentRef(
        project_ref,
        f"artifact://{project_ref.value}/{suffix}",
        foreign.content_ref,
        foreign.content_sha256,
    )


@pytest.mark.parametrize("foreign_kind", ["prompt", "reference"])
def test_cloudflare_model_rejects_foreign_project_artifact_aliases(
    tmp_path: Path,
    foreign_kind: str,
) -> None:
    fixture = _setup(tmp_path)
    foreign_access = ProjectStore(fixture.database).create_project(
        namespace="foreign-images",
        display_name="Foreign Images",
    ).access
    foreign_prompt = _input(
        fixture.database,
        fixture.objects,
        foreign_access,
        role="image.prompt",
        payload=b"foreign prompt",
        media_type="text/plain",
    )
    foreign_reference = _input(
        fixture.database,
        fixture.objects,
        foreign_access,
        role="image.source",
        payload=_image(),
        media_type="image/png",
    )
    prompt = (
        _project_alias(fixture.access.project_ref, foreign_prompt)
        if foreign_kind == "prompt"
        else fixture.prompt
    )
    reference = (
        _project_alias(fixture.access.project_ref, foreign_reference)
        if foreign_kind == "reference"
        else fixture.reference
    )
    specification = _specification(
        fixture.access.project_ref,
        fixture.source,
        reference,
        prompt,
    )
    called = False

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        nonlocal called
        called = True
        return _cloudflare_response(_image())

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    with pytest.raises(CloudflareImageModelError, match=foreign_kind):
        adapter.generate(fixture.access, fixture.attempt, specification)
    assert not called


def test_cloudflare_model_rejects_missing_credentials_without_transport(tmp_path: Path) -> None:
    fixture = _setup(tmp_path)
    called = False

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        nonlocal called
        called = True
        return CloudflareHttpResponse(200, {"content-type": "image/png"}, _image())

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment={},
    )
    with pytest.raises(CloudflareImageModelError, match="credentials"):
        adapter.generate(fixture.access, fixture.attempt, fixture.specification)
    assert not called


def test_cloudflare_model_never_surfaces_credentials_or_provider_error_body(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    account = "sensitive-account"
    token = "sensitive-token-value"

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        assert headers["Authorization"] == f"Bearer {token}"
        return CloudflareHttpResponse(
            403,
            {"content-type": "application/json"},
            json.dumps({"error": f"denied {account} {token}"}).encode(),
        )

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment={"CLOUDFLARE_ACCOUNT_ID": account, "CLOUDFLARE_API_TOKEN": token},
    )
    with pytest.raises(CloudflareImageModelError) as raised:
        adapter.generate(fixture.access, fixture.attempt, fixture.specification)
    assert account not in str(raised.value)
    assert token not in str(raised.value)


def test_cloudflare_model_rejects_forged_node_fence_before_transport(tmp_path: Path) -> None:
    fixture = _setup(tmp_path)
    forged = replace(fixture.attempt, fence=fixture.attempt.fence + 1)
    called = False

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        nonlocal called
        called = True
        return CloudflareHttpResponse(200, {"content-type": "image/png"}, _image())

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    with pytest.raises(CloudflareImageModelError, match="stale"):
        adapter.generate(fixture.access, forged, fixture.specification)
    assert not called


def test_cloudflare_model_revalidates_node_authority_after_transport(tmp_path: Path) -> None:
    fixture = _setup(tmp_path)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse:
        NodeExecutionService(fixture.database).fail_node(
            fixture.access,
            fixture.attempt,
            category="STALE_EXECUTION",
            reason="invalidate authority before provider response",
            evidence_refs=(),
            retry_possible=False,
            idempotency_key="invalidate-cloudflare-image-attempt",
        )
        return _cloudflare_response(_image())

    adapter = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    with pytest.raises(CloudflareImageModelError, match="stale"):
        adapter.generate(fixture.access, fixture.attempt, fixture.specification)


@pytest.mark.skipif(
    not (
        os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        and os.environ.get("CLOUDFLARE_API_TOKEN")
    ),
    reason="Cloudflare credentials unavailable",
)
def test_cloudflare_model_live_generation(tmp_path: Path) -> None:
    fixture = _setup(tmp_path, "image/jpeg")
    result = CloudflareImageModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
    ).generate(fixture.access, fixture.attempt, fixture.specification)
    assert result.output.project_ref == fixture.access.project_ref
    assert result.specification_digest == fixture.specification.canonical_digest
