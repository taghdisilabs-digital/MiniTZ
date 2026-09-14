"""Cloudflare Workers AI image-model adapter with immutable MiniTZ publication."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
import json
import os
from pathlib import Path
from typing import Protocol
import urllib.error
import urllib.request
from uuid import uuid4

from .artifact import ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .execution import NodeExecutionAttempt, NodeExecutionError, NodeExecutionService
from .image_pack import (
    ImageArtifactContentRef,
    ImageContractError,
    ImageModelAdapter,
    ImageOutputRef,
    ImageSpecification,
)
from .object_store import ObjectStorageBackend
from .project import ProjectAccess, ProjectRef
from .run import ExecutionAttempt, RunError, RunService


_MODEL = "model://cloudflare/flux-2-klein-4b"
_MODEL_API_ID = "@cf/black-forest-labs/flux-2-klein-4b"
_DERIVATION = "image.cloudflare.flux-2-klein-4b"
_FORMAT_MEDIA_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg"}
_MODE_CONTRACTS: Mapping[str, tuple[tuple[str, ...], int]] = {
    "L": (("gray",), 8),
    "LA": (("gray", "alpha"), 8),
    "RGB": (("red", "green", "blue"), 8),
    "RGBA": (("red", "green", "blue", "alpha"), 8),
    "CMYK": (("cyan", "magenta", "yellow", "black"), 8),
    "YCbCr": (("luma", "blue-difference", "red-difference"), 8),
    "I;16": (("gray",), 16),
    "I;16B": (("gray",), 16),
    "I;16L": (("gray",), 16),
}


class CloudflareImageModelError(ImageContractError):
    """Cloudflare adapter failure which never includes credential material."""


@dataclass(frozen=True)
class CloudflareHttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class CloudflareTransport(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareHttpResponse: ...


def _http_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
    timeout_seconds: float,
) -> CloudflareHttpResponse:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return CloudflareHttpResponse(
                response.status,
                dict(response.headers.items()),
                response.read(),
            )
    except urllib.error.HTTPError as exc:
        return CloudflareHttpResponse(exc.code, dict(exc.headers.items()), exc.read())
    except urllib.error.URLError:
        raise CloudflareImageModelError("Cloudflare request was unavailable") from None


def _multipart(
    fields: Mapping[str, str],
    files: tuple[tuple[str, bytes, str], ...],
) -> tuple[str, bytes]:
    boundary = f"----minitz-{uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            (
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            )
        )
    for index, payload, media_type in files:
        extension = "png" if media_type == "image/png" else "jpg"
        chunks.extend(
            (
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="input_image_{index}"; '
                    f'filename="reference-{index}.{extension}"\r\n'
                ).encode(),
                f"Content-Type: {media_type}\r\n\r\n".encode(),
                payload,
                b"\r\n",
            )
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(chunks)


def _decoded_image(payload: bytes) -> tuple[int, int, tuple[str, ...], int, str]:
    try:
        from PIL import Image
    except ImportError:
        raise CloudflareImageModelError(
            "provider image validation requires the Pillow image extra"
        ) from None
    try:
        with Image.open(BytesIO(payload)) as probe:
            probe.verify()
        with Image.open(BytesIO(payload)) as decoded:
            decoded.load()
            width, height = decoded.size
            image_format = decoded.format
            mode = decoded.mode
    except (Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise CloudflareImageModelError("provider image is not fully decodable") from None
    if image_format is None or image_format not in _FORMAT_MEDIA_TYPES:
        raise CloudflareImageModelError("provider image format is unsupported")
    mode_contract = _MODE_CONTRACTS.get(mode)
    if mode_contract is None:
        raise CloudflareImageModelError("provider image channels or bit depth are unsupported")
    channels, bit_depth = mode_contract
    return width, height, channels, bit_depth, _FORMAT_MEDIA_TYPES[image_format]


class CloudflareImageModel:
    """REAL Cloudflare model resource adapter; credentials remain process-local."""

    project_ref: ProjectRef
    model_ref: str
    runtime_ref: str
    determinism: str

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        access: ProjectAccess,
        model_ref: str = _MODEL,
        runtime_ref: str = "runtime://cloudflare/workers-ai/v1",
        transport: CloudflareTransport = _http_transport,
        environment: Mapping[str, str] | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not isinstance(access, ProjectAccess):
            raise TypeError("Cloudflare image model requires ProjectAccess")
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("Cloudflare image model requires ObjectStorageBackend")
        if model_ref != _MODEL:
            raise CloudflareImageModelError("Cloudflare model_ref must name the bound FLUX model")
        if not isinstance(runtime_ref, str) or not runtime_ref:
            raise CloudflareImageModelError("Cloudflare runtime_ref is invalid")
        if not isinstance(timeout_seconds, float) or timeout_seconds <= 0.0:
            raise CloudflareImageModelError("Cloudflare timeout must be positive")
        self.access = access
        self.project_ref = access.project_ref
        self.model_ref = model_ref
        self.runtime_ref = runtime_ref
        self.determinism = "provider-seeded"
        self.objects = object_store
        self.artifacts = ArtifactService(database_path)
        self.executions = NodeExecutionService(database_path)
        self.runs = RunService(database_path)
        self.transport = transport
        self.environment = os.environ if environment is None else environment
        self.timeout_seconds = timeout_seconds

    def _artifact(
        self,
        access: ProjectAccess,
        value: ImageArtifactContentRef,
        label: str,
    ) -> tuple[ArtifactRef, ContentRef, bytes, str]:
        if value.project_ref != self.project_ref:
            raise CloudflareImageModelError(f"{label} crossed Project scope")
        prefix = f"artifact://{self.project_ref.value}/"
        if not value.artifact_ref.startswith(prefix):
            raise CloudflareImageModelError(f"{label} ArtifactRef is malformed or foreign")
        try:
            artifact_id, revision = value.artifact_ref.removeprefix(prefix).rsplit("/", 1)
            artifact_ref = ArtifactRef(self.project_ref, artifact_id, int(revision))
            artifact = self.artifacts.get_artifact(access, artifact_ref)
        except (ArtifactError, ImageContractError, ValueError):
            raise CloudflareImageModelError(f"{label} ArtifactRef is invalid") from None
        content = artifact.content_ref
        if (
            content is None
            or content.value != value.content_ref
            or content.digest != value.content_sha256
        ):
            raise CloudflareImageModelError(
                f"{label} Artifact/Content identity is stale or forged"
            )
        try:
            payload = self.objects.read(content)
        except Exception:
            raise CloudflareImageModelError(f"{label} content is missing or corrupt") from None
        return artifact_ref, content, payload, artifact.role

    def _prompt(
        self,
        access: ProjectAccess,
        specification: ImageSpecification,
    ) -> tuple[str, tuple[ArtifactRef, ContentRef, bytes, str]]:
        artifact_value = specification.prompt_artifact_ref
        content_value = specification.prompt_content_ref
        digest = specification.prompt_content_sha256
        if artifact_value is None or content_value is None or digest is None:
            raise CloudflareImageModelError("generative specification has no prompt identity")
        exact = ImageArtifactContentRef(
            self.project_ref,
            artifact_value,
            content_value,
            digest,
        )
        resolved = self._artifact(access, exact, "prompt")
        if resolved[1].media_type != "text/plain":
            raise CloudflareImageModelError("prompt content must be UTF-8 text/plain")
        try:
            prompt = resolved[2].decode("utf-8")
        except UnicodeDecodeError:
            raise CloudflareImageModelError("prompt content is not UTF-8") from None
        if not prompt:
            raise CloudflareImageModelError("prompt content is empty")
        return prompt, resolved

    def _send(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> CloudflareHttpResponse:
        try:
            return self.transport(method, url, headers, body, self.timeout_seconds)
        except Exception:
            raise CloudflareImageModelError("Cloudflare request was unavailable") from None

    @staticmethod
    def _content_type(response: CloudflareHttpResponse) -> str:
        for key, value in response.headers.items():
            if key.lower() == "content-type":
                return value.split(";", 1)[0].strip().lower()
        return ""

    def _response_image(self, response: CloudflareHttpResponse) -> bytes:
        if response.status < 200 or response.status >= 300:
            raise CloudflareImageModelError(
                f"Cloudflare generation failed with HTTP {response.status}"
            )
        content_type = self._content_type(response)
        if content_type != "application/json":
            raise CloudflareImageModelError(
                "Cloudflare response is not the official JSON image schema"
            )
        try:
            decoded = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CloudflareImageModelError(
                "Cloudflare response is not valid official JSON"
            ) from None
        value: object = None
        if isinstance(decoded, dict):
            result = decoded.get("result")
            if isinstance(result, dict):
                value = result.get("image")
        if not isinstance(value, str) or not value:
            raise CloudflareImageModelError(
                "Cloudflare official JSON response has no result.image payload"
            )
        try:
            return base64.b64decode(value, validate=True)
        except ValueError:
            raise CloudflareImageModelError(
                "Cloudflare result.image payload is not base64"
            ) from None

    def _current_authority(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
    ) -> ExecutionAttempt:
        try:
            current = self.executions.get_node_execution(access, attempt.node_ref)
            producer = next(
                (
                    candidate
                    for candidate in self.runs.list_attempts(access, attempt.run_ref)
                    if candidate.attempt_id == attempt.run_attempt_id
                    and candidate.fence == attempt.run_fence
                ),
                None,
            )
            if producer is None or producer.completed_at is not None:
                raise CloudflareImageModelError("Cloudflare Run attempt is stale")
            run = self.runs.assert_current_run_authority(access, producer)
        except (NodeExecutionError, RunError):
            raise CloudflareImageModelError("Cloudflare Node or Run attempt is stale") from None
        if (
            current.status != "RUNNING"
            or current.current_attempt_id != attempt.attempt_id
            or current.current_fence != attempt.fence
            or producer.run_ref != attempt.run_ref
            or producer.task_ref != attempt.task_ref
            or producer.task_digest != attempt.task_digest
            or run.task_ref != attempt.task_ref
            or run.task_digest != attempt.task_digest
        ):
            raise CloudflareImageModelError("Cloudflare Node or Run attempt is stale")
        return producer

    def generate(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        specification: ImageSpecification,
    ) -> ImageOutputRef:
        if (
            access != self.access
            or not isinstance(attempt, NodeExecutionAttempt)
            or attempt.node_ref.project_ref != self.project_ref
            or attempt.run_ref.project_ref != self.project_ref
            or attempt.task_ref.project_ref != self.project_ref
        ):
            raise CloudflareImageModelError("Cloudflare generation crossed Project or authority")
        if not isinstance(specification, ImageSpecification):
            raise CloudflareImageModelError("image specification is invalid")
        self._current_authority(access, attempt)
        if specification.project_ref != self.project_ref:
            raise CloudflareImageModelError("image specification crossed Project scope")
        if specification.model_ref != self.model_ref or specification.runtime_ref != self.runtime_ref:
            raise CloudflareImageModelError("image model or runtime identity does not match adapter")
        operation = specification.operation.operation
        if operation not in {"generate", "edit", "inpaint", "outpaint"}:
            raise CloudflareImageModelError(
                "Cloudflare model accepts only generate, edit, inpaint, and outpaint operations"
            )
        if specification.format not in {"image/png", "image/jpeg"} or specification.bit_depth != 8:
            raise CloudflareImageModelError("Cloudflare adapter requires 8-bit PNG or JPEG output")
        if not 256 <= specification.width <= 1920 or not 256 <= specification.height <= 1920:
            raise CloudflareImageModelError("Cloudflare dimensions must be within 256..1920")
        account = self.environment.get("CLOUDFLARE_ACCOUNT_ID")
        token = self.environment.get("CLOUDFLARE_API_TOKEN")
        if not account or not token:
            raise CloudflareImageModelError("Cloudflare credentials are unavailable")

        prompt, prompt_entry = self._prompt(access, specification)
        source_entries = tuple(
            self._artifact(access, item, "source") for item in specification.sources
        )
        reference_entries = tuple(
            self._artifact(access, item, "reference") for item in specification.references
        )
        if len(reference_entries) > 4:
            raise CloudflareImageModelError("Cloudflare accepts at most four reference images")
        base_entries: list[tuple[ArtifactRef, ContentRef, bytes, str]] = []
        mask_entries: list[tuple[ArtifactRef, ContentRef, bytes, str]] = []
        source_dimensions: dict[ArtifactRef, tuple[int, int, tuple[str, ...]]] = {}
        for artifact_ref, content, payload, role in source_entries:
            if content.media_type not in {"image/png", "image/jpeg"}:
                raise CloudflareImageModelError("source content format is unsupported")
            width, height, channels, _, media_type = _decoded_image(payload)
            if media_type != content.media_type:
                raise CloudflareImageModelError("source content media type is corrupt")
            if width >= 512 or height >= 512:
                raise CloudflareImageModelError(
                    "Cloudflare source inputs must be smaller than 512x512"
                )
            entry = (artifact_ref, content, payload, role)
            if role == "image.mask":
                mask_entries.append(entry)
            else:
                base_entries.append(entry)
            source_dimensions[artifact_ref] = (width, height, channels)

        expected_role = "image.generated" if operation == "generate" else "image.edited"
        if specification.output_contract.get("role") != expected_role:
            raise CloudflareImageModelError(
                f"{operation} output contract requires role {expected_role}"
            )
        if operation == "generate":
            if mask_entries:
                raise CloudflareImageModelError("generate does not accept a mask source")
        else:
            if len(base_entries) != 1:
                raise CloudflareImageModelError(
                    f"{operation} requires exactly one exact source image"
                )
            base_width, base_height, _ = source_dimensions[base_entries[0][0]]
            if operation == "inpaint":
                if len(mask_entries) != 1:
                    raise CloudflareImageModelError("inpaint requires exactly one image.mask")
                mask_width, mask_height, mask_channels = source_dimensions[mask_entries[0][0]]
                if (
                    mask_width != base_width
                    or mask_height != base_height
                    or len(mask_channels) != 1
                    or mask_entries[0][1].media_type != "image/png"
                ):
                    raise CloudflareImageModelError(
                        "inpaint mask must be a same-size single-channel PNG"
                    )
            elif mask_entries:
                raise CloudflareImageModelError(f"{operation} does not accept a mask source")
            if operation in {"edit", "inpaint"} and (
                specification.width != base_width or specification.height != base_height
            ):
                raise CloudflareImageModelError(
                    f"{operation} output dimensions must match the exact source"
                )
            if operation == "outpaint":
                geometry: dict[str, int] = {}
                for edge in ("left", "right", "top", "bottom"):
                    value = specification.operation.parameters.get(edge)
                    if value is None or not value.isdigit():
                        raise CloudflareImageModelError(
                            "outpaint requires non-negative integer geometry"
                        )
                    geometry[edge] = int(value)
                if not any(geometry.values()):
                    raise CloudflareImageModelError("outpaint geometry cannot be empty")
                if (
                    specification.width
                    != base_width + geometry["left"] + geometry["right"]
                    or specification.height
                    != base_height + geometry["top"] + geometry["bottom"]
                ):
                    raise CloudflareImageModelError(
                        "outpaint dimensions do not match the exact geometry"
                    )

        for _, content, payload, _ in reference_entries:
            if content.media_type not in {"image/png", "image/jpeg"}:
                raise CloudflareImageModelError("reference content format is unsupported")
            width, height, _, _, media_type = _decoded_image(payload)
            if media_type != content.media_type:
                raise CloudflareImageModelError("reference content media type is corrupt")
            if width >= 512 or height >= 512:
                raise CloudflareImageModelError(
                    "Cloudflare reference inputs must be smaller than 512x512"
                )
        provider_entries = (
            reference_entries
            if operation == "generate"
            else (*base_entries, *mask_entries, *reference_entries)
        )
        if len(provider_entries) > 4:
            raise CloudflareImageModelError(
                "Cloudflare accepts at most four exact provider image inputs"
            )
        if operation != "generate" and not provider_entries:
            raise CloudflareImageModelError(
                "Cloudflare edit operations require at least one provider image input"
            )
        if any(content.media_type != "image/png" for _, content, _, _ in provider_entries):
            raise CloudflareImageModelError(
                "Cloudflare provider image inputs must be raw PNG"
            )
        provider_files = tuple(
            (str(index), payload, content.media_type)
            for index, (_, content, payload, _) in enumerate(provider_entries)
        )
        unsupported_config = set(specification.config) - {"guidance", "steps"}
        if unsupported_config:
            raise CloudflareImageModelError(
                "Cloudflare configuration contains unsupported fields"
            )
        steps = specification.config.get("steps")
        if steps is not None and steps != "4":
            raise CloudflareImageModelError("Cloudflare model has fixed steps=4")
        provider_prompt = prompt
        if operation != "generate":
            operation_binding: dict[str, object] = {
                "operation": operation,
                "parameters": dict(specification.operation.parameters),
                "source_input": "input_image_0",
                "reference_inputs": [
                    f"input_image_{index}"
                    for index in range(
                        2 if operation == "inpaint" else 1,
                        len(provider_entries),
                    )
                ],
            }
            if operation == "inpaint":
                operation_binding["mask_input"] = "input_image_1"
            provider_prompt = (
                f"{prompt}\nMiniTZ operation binding: "
                + json.dumps(
                    operation_binding,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
            )
        fields = {
            "prompt": provider_prompt,
            "width": str(specification.width),
            "height": str(specification.height),
            "seed": str(specification.seed),
        }
        guidance = specification.config.get("guidance")
        if guidance is not None:
            fields["guidance"] = guidance
        boundary, body = _multipart(fields, provider_files)
        response = self._send(
            "POST",
            f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{_MODEL_API_ID}",
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            body,
        )
        payload = self._response_image(response)
        width, height, channels, bit_depth, media_type = _decoded_image(payload)
        if (
            width != specification.width
            or height != specification.height
            or channels != specification.channels
            or bit_depth != specification.bit_depth
            or media_type != specification.format
        ):
            raise CloudflareImageModelError(
                "provider image dimensions, channels, bit depth, or format violate output contract"
            )

        producer = self._current_authority(access, attempt)
        try:
            output_content = self.objects.put(payload, media_type=media_type)
        except Exception:
            raise CloudflareImageModelError("provider image storage failed") from None
        provenance = (prompt_entry, *source_entries, *reference_entries)
        derivation = f"{_DERIVATION}.{operation}"
        try:
            artifact = self.artifacts.publish_from_run(
                access,
                producer_attempt=producer,
                expected_task_ref=attempt.task_ref,
                expected_task_digest=attempt.task_digest,
                role=expected_role,
                content_ref=output_content,
                source_refs=(),
                source_artifact_refs=tuple(item[0] for item in provenance),
                source_content_refs=tuple(item[1] for item in provenance),
                derivation_type=derivation,
                metadata={"media_type": media_type},
            )
        except ArtifactError:
            raise CloudflareImageModelError("provider image publication was rejected") from None
        output = ImageArtifactContentRef(
            self.project_ref,
            artifact.artifact_ref.value,
            output_content.value,
            output_content.digest,
        )
        return ImageOutputRef.create(
            self.project_ref,
            specification,
            output,
            attempt.attempt_id,
            attempt.fence,
            derivation,
        )


def cloudflare_image_model_adapter(*args: object, **kwargs: object) -> ImageModelAdapter:
    """Return the public replaceable adapter protocol without exposing provider details."""
    return CloudflareImageModel(*args, **kwargs)  # type: ignore[arg-type]
