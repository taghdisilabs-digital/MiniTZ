"""Focused Cloudflare Workers AI audio adapter evidence."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any

import pytest

from minitz_os.engine.artifact import ArtifactRef, ArtifactService, ContentRef
from minitz_os.engine.audio_pack import (
    AudioArtifactContentRef,
    AudioContractError,
    AudioSpecification,
    ProcessingChain,
    audio_production_pack,
)
from minitz_os.engine.call_ledger import CallLedgerService, ModelCall, ModelCallRef
from minitz_os.engine.capability import CapabilityRef, CapabilityRegistry
from minitz_os.engine.cloudflare_audio_model import (
    AudioByteValidator,
    CloudflareAudioHttpResponse,
    CloudflareAudioModel,
    CloudflareAudioModelError,
)
from minitz_os.engine.execution import NodeExecutionAttempt, NodeExecutionService
from minitz_os.engine.graph import GraphRef, GraphService, Node, NodeRef
from minitz_os.engine.object_store import MemoryObjectStorageBackend
from minitz_os.engine.project import ProjectAccess, ProjectRef, ProjectStore
from minitz_os.engine.run import RunService
from minitz_os.engine.task import TaskRevisionService


_ACCOUNT = "a" * 32
_TOKEN = "fixture-secret-token-0000"
_ENVIRONMENT = {
    "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT,
    "CLOUDFLARE_API_TOKEN": _TOKEN,
}
_VALIDATOR_REF = "validator://audio/ffmpeg-full-decode/v1"
_VALIDATION_MEDIA_TYPE = "application/vnd.minitz.audio-validation+json"
_AURA_MODEL_REF = "model://cloudflare/deepgram-aura-1"
_AURA_VOICE_REF = "voice://cloudflare/deepgram-aura-1/asteria"


@dataclass(frozen=True)
class _Decoded:
    media_type: str = "audio/mpeg"
    container: str = "mp3"
    codec: str = "mp3"
    sample_rate: int = 24_000
    sample_format: str = "fltp"
    bit_depth: int = 32
    channels: int = 1
    channel_layout: tuple[str, ...] = ("FC",)
    duration: float = 1.25
    sample_count: int = 30_000
    bit_rate: int | None = 64_000
    content_sha256: str = "0" * 64
    pcm_sha256: str = "1" * 64
    decoder: str = "ffmpeg://8.0.1/mp3"
    peak: float = 0.5
    rms: float = 0.2
    loudness_lufs: float = -18.0
    clipping_samples: int = 0
    silence_samples: int = 12


class _Validator:
    project_ref: ProjectRef
    validator_ref: str

    def __init__(self, project_ref: ProjectRef, *, reject: bool = False) -> None:
        self.project_ref = project_ref
        self.validator_ref = _VALIDATOR_REF
        self.reject = reject
        self.calls: list[tuple[bytes, str]] = []

    def validate(self, payload: bytes, *, expected_media_type: str) -> _Decoded:
        self.calls.append((payload, expected_media_type))
        if self.reject:
            raise AudioContractError("full audio decode rejected corrupt or truncated bytes")
        return replace(_Decoded(), content_sha256=hashlib.sha256(payload).hexdigest())


@dataclass(frozen=True)
class _Fixture:
    database: Path
    objects: MemoryObjectStorageBackend
    access: ProjectAccess
    attempt: NodeExecutionAttempt
    source: AudioArtifactContentRef
    prompt: AudioArtifactContentRef
    specification: AudioSpecification
    validator: AudioByteValidator


def _input(
    database: Path,
    objects: MemoryObjectStorageBackend,
    access: ProjectAccess,
    *,
    role: str,
    payload: bytes,
    media_type: str,
) -> AudioArtifactContentRef:
    content = objects.put(payload, media_type=media_type)
    artifact = ArtifactService(database).create_artifact(
        access,
        project_ref=access.project_ref,
        role=role,
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="audio.fixture",
        metadata={"media_type": media_type},
    )
    return AudioArtifactContentRef(
        access.project_ref,
        artifact.artifact_ref.value,
        content.value,
        content.digest,
    )


def _active_attempt(database: Path, access: ProjectAccess) -> NodeExecutionAttempt:
    registry = CapabilityRegistry(database)
    for definition in audio_production_pack().capability_definitions:
        registry.register(definition)
    capability = CapabilityRef("audio.generate", "1.0.0")
    task = TaskRevisionService(database).create_task(
        access,
        project_ref=access.project_ref,
        idempotency_key="cloudflare-audio-task",
        task_type="audio.generate",
        objective="Generate one exact speech Artifact",
        required_capabilities=(capability,),
        input_refs=(),
        output_contract={"result": "schema://minitz/audio-result/1"},
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
        owner_ref="controller://cloudflare-audio-tests",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(access.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "MODEL",
        (capability,),
        (),
        (),
        {"result": "schema://minitz/audio-result/1"},
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
        owner_ref="executor://cloudflare-audio-tests",
        lease_seconds=1800,
        idempotency_key="cloudflare-audio-node-lease",
    )
    executions.start_node(
        access,
        attempt,
        idempotency_key="cloudflare-audio-node-start",
    )
    return attempt


def _specification(
    project_ref: ProjectRef,
    source: AudioArtifactContentRef,
    prompt: AudioArtifactContentRef,
    *,
    model_ref: str = "model://cloudflare/melotts",
    runtime_ref: str = "runtime://cloudflare/workers-ai/v1",
    voice_ref: str = "voice://cloudflare/melotts/default",
    tool_config: Mapping[str, str] | None = None,
    output_contract: Mapping[str, str] | None = None,
    effect_ref: str = "effect://audio/provider-native/v1",
) -> AudioSpecification:
    chain = ProcessingChain(
        "chain://audio/provider-native/v1",
        "c" * 64,
        "1.0.0",
        (effect_ref,),
        {},
    )
    return AudioSpecification.create(
        project_ref,
        "melotts-speech",
        (source,),
        "generate",
        "recipe://audio/generate/v1",
        "d" * 64,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "audio/mpeg",
        "mp3",
        "mp3",
        None,
        None,
        chain,
        {} if tool_config is None else dict(tool_config),
        {},
        "algorithm://audio/ffmpeg-full-decode/v1",
        {},
        model_ref,
        "1",
        runtime_ref,
        0,
        voice_ref,
        "en",
        prompt,
        _VALIDATOR_REF,
        (
            {"role": "audio.generated", "media_type": "audio/mpeg", "container": "mp3", "codec": "mp3"}
            if output_contract is None
            else dict(output_contract)
        ),
    )


def _setup_existing(
    database: Path,
    objects: MemoryObjectStorageBackend,
    access: ProjectAccess,
    *,
    validator: AudioByteValidator | None = None,
) -> _Fixture:
    active_validator: AudioByteValidator = _Validator(access.project_ref) if validator is None else validator
    attempt = _active_attempt(database, access)
    source = _input(
        database,
        objects,
        access,
        role="audio.source",
        payload=b"provenance-only reference audio",
        media_type="audio/wav",
    )
    prompt = _input(
        database,
        objects,
        access,
        role="audio.prompt",
        payload=b"Say hello from the MiniTZ audio provider.",
        media_type="text/plain",
    )
    return _Fixture(
        database,
        objects,
        access,
        attempt,
        source,
        prompt,
        _specification(access.project_ref, source, prompt),
        active_validator,
    )


def _setup(tmp_path: Path, *, reject_audio: bool = False) -> _Fixture:
    database = tmp_path / "minitz.db"
    access = ProjectStore(database).create_project(
        namespace="cloudflare-audio",
        display_name="Cloudflare Audio",
    ).access
    objects = MemoryObjectStorageBackend()
    return _setup_existing(
        database,
        objects,
        access,
        validator=_Validator(access.project_ref, reject=reject_audio),
    )


def _artifact_ref(project_ref: ProjectRef, value: str) -> ArtifactRef:
    prefix = f"artifact://{project_ref.value}/"
    artifact_id, revision = value.removeprefix(prefix).rsplit("/", 1)
    return ArtifactRef(project_ref, artifact_id, int(revision))


def _last_model_call(database: Path, access: ProjectAccess) -> ModelCall:
    connection = sqlite3.connect(database)
    try:
        row = connection.execute(
            "SELECT call_id FROM calls WHERE project_id=? AND call_kind='MODEL' ORDER BY rowid DESC LIMIT 1",
            (access.project_ref.value,),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    return CallLedgerService(database).get_model_call(
        access,
        ModelCallRef(access.project_ref, str(row[0])),
    )


@pytest.mark.parametrize("shape", ("binary", "envelope", "object", "result-string"))
def test_cloudflare_audio_accepts_documented_shapes_and_publishes_exact_evidence(
    tmp_path: Path,
    shape: str,
) -> None:
    fixture = _setup(tmp_path)
    payload = b"complete decoded provider mp3 payload"
    calls: list[tuple[str, str, Mapping[str, str], bytes | None]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareAudioHttpResponse:
        calls.append((method, url, headers, body))
        if shape == "binary":
            return CloudflareAudioHttpResponse(200, {"Content-Type": "audio/mpeg"}, payload)
        encoded = base64.b64encode(payload).decode("ascii")
        if shape == "envelope":
            response: object = {"result": {"audio": encoded}, "success": True, "errors": [], "messages": []}
        elif shape == "object":
            response = {"audio": encoded}
        else:
            response = {"result": encoded, "success": True, "errors": [], "messages": []}
        return CloudflareAudioHttpResponse(
            200,
            {"content-type": "application/json"},
            json.dumps(response).encode(),
        )

    result = CloudflareAudioModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        validator=fixture.validator,
        transport=transport,
        environment=_ENVIRONMENT,
    ).generate(fixture.access, fixture.attempt, fixture.specification)

    assert result.project_ref == fixture.access.project_ref
    assert result.specification_digest == fixture.specification.canonical_digest
    assert result.output.content_sha256 == hashlib.sha256(payload).hexdigest()
    assert (result.duration, result.sample_rate, result.channel_layout) == (1.25, 24_000, ("FC",))
    assert (result.codec, result.sample_format, result.bit_depth) == ("mp3", "fltp", 32)
    assert result.producer_attempt_id == fixture.attempt.attempt_id
    assert result.producer_fence == fixture.attempt.fence

    assert calls[0][0] == "POST"
    assert calls[0][1] == (
        f"https://api.cloudflare.com/client/v4/accounts/{_ACCOUNT}/ai/run/"
        "@cf/myshell-ai/melotts"
    )
    assert calls[0][3] is not None
    assert json.loads(calls[0][3]) == {
        "lang": "en",
        "prompt": "Say hello from the MiniTZ audio provider.",
    }
    assert b"provenance-only reference audio" not in calls[0][3]
    assert calls[0][2]["Authorization"] == f"Bearer {_TOKEN}"
    assert isinstance(fixture.validator, _Validator)
    assert fixture.validator.calls == [(payload, "audio/mpeg")]

    artifact = ArtifactService(fixture.database).get_artifact(
        fixture.access,
        _artifact_ref(fixture.access.project_ref, result.output.artifact_ref),
    )
    assert artifact.role == "audio.generated"
    assert artifact.metadata["media_type"] == "audio/mpeg"
    assert artifact.metadata["semantic_label"] == "audio.generated"
    assert {item.value for item in artifact.source_artifact_refs} == {
        fixture.prompt.artifact_ref,
        fixture.source.artifact_ref,
    }
    assert {item.value for item in artifact.source_content_refs} == {
        fixture.prompt.content_ref,
        fixture.source.content_ref,
    }

    call = _last_model_call(fixture.database, fixture.access)
    assert call.status == "SUCCEEDED"
    assert call.capability_ref == CapabilityRef("audio.generate", "1.0.0")
    assert call.provider_id == "provider://cloudflare/workers-ai"
    assert call.model_id == "model://cloudflare/melotts"
    assert {item.value for item in call.input_refs} == {
        fixture.prompt.artifact_ref,
        fixture.prompt.content_ref,
        fixture.source.artifact_ref,
        fixture.source.content_ref,
    }
    output_artifacts = [item for item in call.output_refs if isinstance(item, ArtifactRef)]
    assert artifact.artifact_ref in output_artifacts
    evidence = next(
        ArtifactService(fixture.database).get_artifact(fixture.access, item)
        for item in output_artifacts
        if item != artifact.artifact_ref
    )
    assert evidence.role == "audio.validation-evidence"
    assert evidence.content_ref is not None
    validation = json.loads(fixture.objects.read(evidence.content_ref))
    assert validation["full_decode"] is True
    assert validation["codec"] == "mp3"
    assert validation["pcm_sha256"] == "1" * 64
    assert not call.failure_evidence_refs
    assert _TOKEN not in repr(artifact.metadata)


@pytest.mark.parametrize("shape", ("binary", "envelope"))
def test_cloudflare_aura_uses_exact_request_and_decodes_documented_responses(
    tmp_path: Path,
    shape: str,
) -> None:
    fixture = _setup(tmp_path)
    specification = _specification(
        fixture.access.project_ref,
        fixture.source,
        fixture.prompt,
        model_ref=_AURA_MODEL_REF,
        voice_ref=_AURA_VOICE_REF,
    )
    payload = b"complete decoded Aura provider mp3 payload"
    calls: list[tuple[str, str, Mapping[str, str], bytes | None]] = []

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareAudioHttpResponse:
        calls.append((method, url, headers, body))
        if shape == "binary":
            return CloudflareAudioHttpResponse(200, {"content-type": "audio/mpeg"}, payload)
        return CloudflareAudioHttpResponse(
            200,
            {"content-type": "application/json"},
            json.dumps(
                {
                    "result": {"audio": base64.b64encode(payload).decode("ascii")},
                    "success": True,
                    "errors": [],
                    "messages": [],
                }
            ).encode(),
        )

    result = CloudflareAudioModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        validator=fixture.validator,
        model_ref=_AURA_MODEL_REF,
        transport=transport,
        environment=_ENVIRONMENT,
    ).generate(fixture.access, fixture.attempt, specification)

    assert result.output.content_sha256 == hashlib.sha256(payload).hexdigest()
    assert calls == [
        (
            "POST",
            (
                f"https://api.cloudflare.com/client/v4/accounts/{_ACCOUNT}/ai/run/"
                "@cf/deepgram/aura-1"
            ),
            calls[0][2],
            calls[0][3],
        )
    ]
    assert calls[0][3] is not None
    assert json.loads(calls[0][3]) == {
        "text": "Say hello from the MiniTZ audio provider.",
        "speaker": "asteria",
        "encoding": "mp3",
    }
    assert calls[0][2]["Authorization"] == f"Bearer {_TOKEN}"
    assert isinstance(fixture.validator, _Validator)
    assert fixture.validator.calls == [(payload, "audio/mpeg")]

    call = _last_model_call(fixture.database, fixture.access)
    assert call.status == "SUCCEEDED"
    assert call.provider_id == "provider://cloudflare/workers-ai"
    assert call.model_id == _AURA_MODEL_REF
    evidence_content = next(
        item
        for item in call.output_refs
        if isinstance(item, ContentRef) and item.media_type == _VALIDATION_MEDIA_TYPE
    )
    validation = json.loads(fixture.objects.read(evidence_content))
    assert validation["full_decode"] is True
    assert validation["container"] == "mp3"
    assert validation["provider_request_config"] == {
        "container": {
            "sent": False,
            "selection": "provider-default",
        },
        "encoding": "mp3",
        "speaker": "asteria",
    }
    assert validation["model_call_ref"] == call.call_ref.value


@pytest.mark.parametrize(
    "payload",
    (b"ID3-not-really-a-complete-mp3", b"ID3-complete-looking-frame"[:-8]),
)
def test_cloudflare_audio_rejects_corrupt_or_truncated_bytes_through_full_validator(
    tmp_path: Path,
    payload: bytes,
) -> None:
    fixture = _setup(tmp_path, reject_audio=True)

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareAudioHttpResponse:
        return CloudflareAudioHttpResponse(200, {"content-type": "audio/mpeg"}, payload)

    adapter = CloudflareAudioModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        validator=fixture.validator,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    with pytest.raises(CloudflareAudioModelError, match="fully decodable"):
        adapter.generate(fixture.access, fixture.attempt, fixture.specification)

    assert isinstance(fixture.validator, _Validator)
    assert fixture.validator.calls == [(payload, "audio/mpeg")]
    call = _last_model_call(fixture.database, fixture.access)
    assert call.status == "FAILED"
    assert not call.output_refs
    assert call.failure_category == "AUDIO_DECODE_FAILED"
    assert call.failure_evidence_refs
    evidence_content = next(item for item in call.failure_evidence_refs if isinstance(item, ContentRef))
    receipt = json.loads(fixture.objects.read(evidence_content))
    assert receipt["response_sha256"] == hashlib.sha256(payload).hexdigest()
    assert "ID3" not in repr(receipt)


def _project_alias(
    project_ref: ProjectRef,
    foreign: AudioArtifactContentRef,
) -> AudioArtifactContentRef:
    prefix = f"artifact://{foreign.project_ref.value}/"
    suffix = foreign.artifact_ref.removeprefix(prefix)
    return AudioArtifactContentRef(
        project_ref,
        f"artifact://{project_ref.value}/{suffix}",
        foreign.content_ref,
        foreign.content_sha256,
    )


@pytest.mark.parametrize("foreign_kind", ("prompt", "reference"))
def test_cloudflare_audio_rejects_foreign_prompt_and_reference_aliases_before_egress(
    tmp_path: Path,
    foreign_kind: str,
) -> None:
    fixture = _setup(tmp_path)
    foreign_access = ProjectStore(fixture.database).create_project(
        namespace="foreign-audio",
        display_name="Foreign Audio",
    ).access
    foreign_prompt = _input(
        fixture.database,
        fixture.objects,
        foreign_access,
        role="audio.prompt",
        payload=b"foreign prompt",
        media_type="text/plain",
    )
    foreign_source = _input(
        fixture.database,
        fixture.objects,
        foreign_access,
        role="audio.source",
        payload=b"foreign reference",
        media_type="audio/wav",
    )
    prompt = _project_alias(fixture.access.project_ref, foreign_prompt) if foreign_kind == "prompt" else fixture.prompt
    source = _project_alias(fixture.access.project_ref, foreign_source) if foreign_kind == "reference" else fixture.source
    specification = _specification(fixture.access.project_ref, source, prompt)
    called = False

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareAudioHttpResponse:
        nonlocal called
        called = True
        return CloudflareAudioHttpResponse(200, {"content-type": "audio/mpeg"}, b"audio")

    adapter = CloudflareAudioModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        validator=fixture.validator,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    with pytest.raises(CloudflareAudioModelError, match=foreign_kind):
        adapter.generate(fixture.access, fixture.attempt, specification)
    assert not called


def test_cloudflare_audio_binds_model_voice_config_and_exact_output_contract(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    invalid = (
        _specification(fixture.access.project_ref, fixture.source, fixture.prompt, model_ref="model://other/provider"),
        _specification(fixture.access.project_ref, fixture.source, fixture.prompt, runtime_ref="runtime://other/v1"),
        _specification(fixture.access.project_ref, fixture.source, fixture.prompt, voice_ref="voice://requested/clone"),
        _specification(fixture.access.project_ref, fixture.source, fixture.prompt, tool_config={"speed": "1.1"}),
        _specification(
            fixture.access.project_ref,
            fixture.source,
            fixture.prompt,
            output_contract={"role": "audio.generated", "unknown": "unprovable"},
        ),
        _specification(
            fixture.access.project_ref,
            fixture.source,
            fixture.prompt,
            effect_ref="effect://audio/normalize/v1",
        ),
    )
    called = False

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareAudioHttpResponse:
        nonlocal called
        called = True
        return CloudflareAudioHttpResponse(200, {"content-type": "audio/mpeg"}, b"audio")

    adapter = CloudflareAudioModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        validator=fixture.validator,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    for specification in invalid:
        with pytest.raises(CloudflareAudioModelError):
            adapter.generate(fixture.access, fixture.attempt, specification)
    assert not called


def test_cloudflare_aura_rejects_model_runtime_voice_and_chain_mismatches_before_egress(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    invalid = (
        fixture.specification,
        _specification(
            fixture.access.project_ref,
            fixture.source,
            fixture.prompt,
            model_ref=_AURA_MODEL_REF,
            runtime_ref="runtime://other/v1",
            voice_ref=_AURA_VOICE_REF,
        ),
        _specification(
            fixture.access.project_ref,
            fixture.source,
            fixture.prompt,
            model_ref=_AURA_MODEL_REF,
            voice_ref="voice://cloudflare/melotts/default",
        ),
        _specification(
            fixture.access.project_ref,
            fixture.source,
            fixture.prompt,
            model_ref=_AURA_MODEL_REF,
            voice_ref=_AURA_VOICE_REF,
            effect_ref="effect://audio/normalize/v1",
        ),
    )
    called = False

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareAudioHttpResponse:
        nonlocal called
        called = True
        return CloudflareAudioHttpResponse(200, {"content-type": "audio/mpeg"}, b"audio")

    adapter = CloudflareAudioModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        validator=fixture.validator,
        model_ref=_AURA_MODEL_REF,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    for specification in invalid:
        with pytest.raises(CloudflareAudioModelError):
            adapter.generate(fixture.access, fixture.attempt, specification)
    assert not called


def test_cloudflare_audio_rejects_forged_and_post_request_stale_attempts(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    calls = 0

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareAudioHttpResponse:
        nonlocal calls
        calls += 1
        NodeExecutionService(fixture.database).fail_node(
            fixture.access,
            fixture.attempt,
            category="STALE_EXECUTION",
            reason="invalidate provider authority after egress",
            evidence_refs=(),
            retry_possible=False,
            idempotency_key="invalidate-cloudflare-audio-attempt",
        )
        return CloudflareAudioHttpResponse(200, {"content-type": "audio/mpeg"}, b"audio")

    adapter = CloudflareAudioModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        validator=fixture.validator,
        transport=transport,
        environment=_ENVIRONMENT,
    )
    with pytest.raises(CloudflareAudioModelError, match="stale"):
        adapter.generate(
            fixture.access,
            replace(fixture.attempt, fence=fixture.attempt.fence + 1),
            fixture.specification,
        )
    assert calls == 0

    with pytest.raises(CloudflareAudioModelError, match="stale"):
        adapter.generate(fixture.access, fixture.attempt, fixture.specification)
    assert calls == 1
    assert isinstance(fixture.validator, _Validator)
    assert not fixture.validator.calls
    assert _last_model_call(fixture.database, fixture.access).status == "RUNNING"


def test_cloudflare_audio_errors_and_failure_evidence_are_secret_safe(
    tmp_path: Path,
) -> None:
    fixture = _setup(tmp_path)
    account = "b" * 32
    token = "sensitive-cloudflare-token-value"

    def transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareAudioHttpResponse:
        assert headers["Authorization"] == f"Bearer {token}"
        return CloudflareAudioHttpResponse(
            403,
            {"content-type": "application/json"},
            json.dumps({"error": f"denied {account} {token}"}).encode(),
        )

    adapter = CloudflareAudioModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        validator=fixture.validator,
        transport=transport,
        environment={"CLOUDFLARE_ACCOUNT_ID": account, "CLOUDFLARE_API_TOKEN": token},
    )
    with pytest.raises(CloudflareAudioModelError) as raised:
        adapter.generate(fixture.access, fixture.attempt, fixture.specification)
    assert account not in str(raised.value)
    assert token not in str(raised.value)

    call = _last_model_call(fixture.database, fixture.access)
    assert call.status == "FAILED" and call.failure_evidence_refs
    for reference in call.failure_evidence_refs:
        if isinstance(reference, ContentRef):
            persisted = fixture.objects.read(reference)
            assert account.encode() not in persisted and token.encode() not in persisted
        else:
            artifact = ArtifactService(fixture.database).get_artifact(fixture.access, reference)
            assert account not in repr(artifact.metadata)
            assert token not in repr(artifact.metadata)


def _real_audio_support() -> Any:
    path = Path(__file__).with_name("test_p3_12_audio_real.py")
    specification = importlib.util.spec_from_file_location("p3_12_audio_provider_support", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


@pytest.mark.skipif(
    not (
        os.environ.get("MINITZ_RUN_LIVE_CLOUDFLARE_AUDIO") == "1"
        and os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        and os.environ.get("CLOUDFLARE_API_TOKEN")
    ),
    reason="explicit Cloudflare audio live gate or credentials unavailable",
)
def test_cloudflare_audio_model_live_generation_uses_real_full_decoder(
    tmp_path: Path,
) -> None:
    support = _real_audio_support()
    environment = support._environments(tmp_path)[0]
    validator = support._tool(environment, support._dispatch(environment))
    fixture = _setup_existing(
        Path(environment.database),
        environment.objects,
        environment.access,
        validator=validator,
    )
    result = CloudflareAudioModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        validator=validator,
        timeout_seconds=120.0,
    ).generate(fixture.access, fixture.attempt, fixture.specification)

    assert result.output.project_ref == fixture.access.project_ref
    assert result.duration > 0.0 and result.sample_rate > 0
    assert result.codec == "mp3" and result.sample_format
    artifact = ArtifactService(fixture.database).get_artifact(
        fixture.access,
        _artifact_ref(fixture.access.project_ref, result.output.artifact_ref),
    )
    assert artifact.metadata["semantic_label"] == "audio.generated"
    call = _last_model_call(fixture.database, fixture.access)
    evidence_content = next(
        item
        for item in call.output_refs
        if isinstance(item, ContentRef) and item.media_type == _VALIDATION_MEDIA_TYPE
    )
    validation = json.loads(fixture.objects.read(evidence_content))
    assert validation["full_decode"] is True
    assert validation["decoder"].startswith("ffmpeg://8.0.1/")


@pytest.mark.skipif(
    not (
        os.environ.get("MINITZ_RUN_LIVE_CLOUDFLARE_AURA") == "1"
        and os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        and os.environ.get("CLOUDFLARE_API_TOKEN")
    ),
    reason="explicit Cloudflare Aura live gate or credentials unavailable",
)
def test_cloudflare_aura_model_live_generation_uses_real_full_decoder(
    tmp_path: Path,
) -> None:
    support = _real_audio_support()
    environment = support._environments(tmp_path)[0]
    validator = support._tool(environment, support._dispatch(environment))
    fixture = _setup_existing(
        Path(environment.database),
        environment.objects,
        environment.access,
        validator=validator,
    )
    specification = _specification(
        fixture.access.project_ref,
        fixture.source,
        fixture.prompt,
        model_ref=_AURA_MODEL_REF,
        voice_ref=_AURA_VOICE_REF,
    )
    result = CloudflareAudioModel(
        fixture.database,
        fixture.objects,
        access=fixture.access,
        validator=validator,
        model_ref=_AURA_MODEL_REF,
        timeout_seconds=120.0,
    ).generate(fixture.access, fixture.attempt, specification)

    assert result.output.project_ref == fixture.access.project_ref
    assert result.duration > 0.0 and result.sample_rate > 0
    assert result.codec == "mp3" and result.sample_format
    artifact = ArtifactService(fixture.database).get_artifact(
        fixture.access,
        _artifact_ref(fixture.access.project_ref, result.output.artifact_ref),
    )
    assert artifact.metadata["semantic_label"] == "audio.generated"
    call = _last_model_call(fixture.database, fixture.access)
    assert call.model_id == _AURA_MODEL_REF
    evidence_content = next(
        item
        for item in call.output_refs
        if isinstance(item, ContentRef) and item.media_type == _VALIDATION_MEDIA_TYPE
    )
    validation = json.loads(fixture.objects.read(evidence_content))
    assert validation["full_decode"] is True
    assert validation["decoder"].startswith("ffmpeg://8.0.1/")
