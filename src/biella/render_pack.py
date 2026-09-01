from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from .capability import Capability, CapabilityRef
from .production_pack import (
    GraphRecipeRegistration,
    GraphRecipeStepRegistration,
    ProductionPack,
    ProductionPackRef,
    ValidatorRegistration,
)
from .project import ProjectRef

if TYPE_CHECKING:
    from .artifact import ArtifactRef
    from .execution import NodeExecutionAttempt
    from .filesystem import FilesystemRootRef
    from .project import ProjectAccess
    from .scheduler import ResourceAllocationRef, ScheduledDispatch


_NAMES = (
    "inspect", "preview", "frame", "sequence", "batch", "raster",
    "raytrace", "pathtrace", "pass", "composite_input", "validate",
    "performance",
)
_ROLES = (
    "render.config", "render.frame", "render.sequence", "render.pass",
    "render.preview", "render.validation",
)
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA = re.compile(r"[0-9a-f]{64}")
_SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
_ATTEMPT = re.compile(r"natt_[0-9a-f]{32}")
_SUPPORTED_PASSES = frozenset({"beauty", "z", "normal"})
_DEFAULT_CAMERA_SETTINGS = MappingProxyType({
    "clip_end": "1000.0",
    "clip_start": "0.1",
    "lens_mm": "50.0",
    "projection": "PERSP",
    "sensor_width_mm": "36.0",
})


class RenderContractError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _ref(value: object, name: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise RenderContractError(name)
    return value


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise RenderContractError(name)
    return value


def _text(value: object, name: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value.encode()) > maximum or any(ord(item) < 32 for item in value):
        raise RenderContractError(name)
    return value


def _floats(value: object, name: str, length: int) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != length:
        raise RenderContractError(name)
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        raise RenderContractError(name) from None
    if not all(math.isfinite(item) for item in result):
        raise RenderContractError(name)
    return result


def _mapping(value: object, name: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or len(value) > 128:
        raise RenderContractError(name)
    copied: dict[str, str] = {}
    for key, item in value.items():
        copied[_text(key, f"{name} key", 128)] = _text(item, f"{name} value", 1024)
    return MappingProxyType(dict(sorted(copied.items())))


def _channels(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RenderContractError("channels")
    result = tuple(str(item) for item in value)
    if tuple(item.lower() for item in result) == ("rgba",):
        result = ("R", "G", "B", "A")
    elif tuple(item.lower() for item in result) == ("rgb",):
        result = ("R", "G", "B")
    else:
        result = tuple(item.upper() for item in result)
    if result not in {("R", "G", "B"), ("R", "G", "B", "A")}:
        raise RenderContractError("PNG channels must be exact RGB or RGBA")
    return result


@dataclass(frozen=True)
class RenderConfig:
    # digest remains an accepted compatibility argument, but is never trusted.
    project_ref: ProjectRef
    config_id: str
    config_ref: str
    digest: str
    kind: str
    dimensions: tuple[int, int]
    media_type: str
    channels: tuple[str, ...]
    passes: tuple[str, ...]
    quality: Mapping[str, str]
    resource: Mapping[str, str]
    egress: Mapping[str, str]
    timeout_seconds: float
    cancel_allowed: bool
    config_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise RenderContractError("config Project")
        object.__setattr__(self, "config_id", _text(self.config_id, "config_id", 256))
        object.__setattr__(self, "config_ref", _ref(self.config_ref, "config_ref"))
        _sha(self.digest, "supplied config digest")
        if not isinstance(self.config_version, str) or _SEMVER.fullmatch(self.config_version) is None:
            raise RenderContractError("config_version")
        if self.kind not in {"preview", "final"}:
            raise RenderContractError("config kind")
        if (
            not isinstance(self.dimensions, tuple)
            or len(self.dimensions) != 2
            or any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in self.dimensions)
        ):
            raise RenderContractError("dimensions")
        if self.media_type != "image/png":
            raise RenderContractError("renderer supports exact image/png output only")
        object.__setattr__(self, "channels", _channels(self.channels))
        if isinstance(self.passes, (str, bytes)) or not isinstance(self.passes, Sequence):
            raise RenderContractError("passes")
        passes = tuple(str(item).lower() for item in self.passes)
        if not passes or len(set(passes)) != len(passes) or set(passes) - _SUPPORTED_PASSES:
            raise RenderContractError("passes")
        object.__setattr__(self, "passes", passes)
        object.__setattr__(self, "quality", _mapping(self.quality, "quality"))
        object.__setattr__(self, "resource", _mapping(self.resource, "resource"))
        object.__setattr__(self, "egress", _mapping(self.egress, "egress"))
        if not isinstance(self.cancel_allowed, bool):
            raise RenderContractError("cancel_allowed")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or not math.isfinite(float(self.timeout_seconds)) or self.timeout_seconds <= 0:
            raise RenderContractError("timeout_seconds")
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))
        max_parallel = self.resource.get("max_parallel", "1")
        if not max_parallel.isdigit() or int(max_parallel) < 1 or int(max_parallel) > 256:
            raise RenderContractError("resource max_parallel")
        backend = self.resource.get("device", "CPU").upper()
        if backend not in {"CPU", "CUDA", "OPTIX"}:
            raise RenderContractError("resource device")
        object.__setattr__(self, "digest", _digest(self.canonical_payload()))

    @property
    def content_sha256(self) -> str:
        return self.digest

    @property
    def max_parallel(self) -> int:
        return int(self.resource.get("max_parallel", "1"))

    @property
    def device_backend(self) -> str:
        return self.resource.get("device", "CPU").upper()

    def canonical_payload(self) -> dict[str, object]:
        return {
            "cancel_allowed": self.cancel_allowed,
            "channels": list(self.channels),
            "config_id": self.config_id,
            "config_ref": self.config_ref,
            "config_version": self.config_version,
            "dimensions": list(self.dimensions),
            "egress": dict(self.egress),
            "kind": self.kind,
            "media_type": self.media_type,
            "passes": list(self.passes),
            "project_ref": self.project_ref.value,
            "quality": dict(self.quality),
            "resource": dict(self.resource),
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True)
class RenderRequest:
    project_ref: ProjectRef
    task_ref: str
    run_ref: str
    node_ref: str
    scene_ref: str
    scene_content_sha256: str
    camera_ref: str
    camera_transform: tuple[float, ...]
    lens_ref: str
    camera_settings_sha256: str
    frame_start: int
    frame_end: int
    time_seconds: float
    capability_id: str
    config: RenderConfig
    renderer_ref: str
    runtime_ref: str
    executor_ref: str
    dependencies: tuple[str, ...]
    camera_object: str = "BiellaCamera"
    camera_settings: Mapping[str, str] = field(default_factory=lambda: dict(_DEFAULT_CAMERA_SETTINGS))
    camera_materialization: str = "CREATE_EXACT"

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.config, RenderConfig) or self.config.project_ref != self.project_ref:
            raise RenderContractError("request Project/config")
        if self.capability_id not in {f"render.{name}" for name in _NAMES}:
            raise RenderContractError("request capability")
        for name in ("task_ref", "run_ref", "node_ref", "scene_ref", "camera_ref", "lens_ref", "renderer_ref", "runtime_ref", "executor_ref"):
            object.__setattr__(self, name, _ref(getattr(self, name), name))
        object.__setattr__(self, "scene_content_sha256", _sha(self.scene_content_sha256, "scene_content_sha256"))
        _sha(self.camera_settings_sha256, "supplied camera settings digest")
        object.__setattr__(self, "camera_transform", _floats(self.camera_transform, "camera_transform", 16))
        object.__setattr__(self, "camera_object", _text(self.camera_object, "camera_object", 256))
        settings = _mapping(self.camera_settings, "camera_settings")
        projection = settings.get("projection")
        if projection not in {"PERSP", "ORTHO"}:
            raise RenderContractError("camera projection")
        names = ["clip_start", "clip_end", "sensor_width_mm"]
        names.append("lens_mm" if projection == "PERSP" else "ortho_scale")
        for name in names:
            try:
                value = float(settings[name])
            except (KeyError, TypeError, ValueError):
                raise RenderContractError(f"camera setting {name}") from None
            if not math.isfinite(value) or value <= 0:
                raise RenderContractError(f"camera setting {name}")
        if float(settings["clip_end"]) <= float(settings["clip_start"]):
            raise RenderContractError("camera clipping")
        object.__setattr__(self, "camera_settings", settings)
        if self.camera_materialization not in {"CREATE_EXACT", "REQUIRE_EXISTING"}:
            raise RenderContractError("camera_materialization")
        object.__setattr__(self, "camera_settings_sha256", _digest({
            "camera_materialization": self.camera_materialization,
            "camera_object": self.camera_object,
            "camera_ref": self.camera_ref,
            "camera_transform": list(self.camera_transform),
            "lens_ref": self.lens_ref,
            "settings": dict(settings),
        }))
        if (
            not isinstance(self.frame_start, int) or isinstance(self.frame_start, bool)
            or not isinstance(self.frame_end, int) or isinstance(self.frame_end, bool)
            or self.frame_end < self.frame_start
        ):
            raise RenderContractError("frame range")
        if isinstance(self.time_seconds, bool) or not isinstance(self.time_seconds, (int, float)) or not math.isfinite(float(self.time_seconds)):
            raise RenderContractError("time_seconds")
        object.__setattr__(self, "time_seconds", float(self.time_seconds))
        if not isinstance(self.dependencies, tuple) or len(set(self.dependencies)) != len(self.dependencies):
            raise RenderContractError("dependencies")
        object.__setattr__(self, "dependencies", tuple(_ref(item, "dependency") for item in self.dependencies))

    def identity_payload(self) -> dict[str, object]:
        return {
            "camera_materialization": self.camera_materialization,
            "camera_object": self.camera_object,
            "camera_ref": self.camera_ref,
            "camera_settings": dict(self.camera_settings),
            "camera_settings_sha256": self.camera_settings_sha256,
            "camera_transform": list(self.camera_transform),
            "capability_id": self.capability_id,
            "config": self.config.canonical_payload(),
            "config_digest": self.config.digest,
            "dependencies": list(self.dependencies),
            "executor_ref": self.executor_ref,
            "frame_end": self.frame_end,
            "frame_start": self.frame_start,
            "lens_ref": self.lens_ref,
            "node_ref": self.node_ref,
            "project_ref": self.project_ref.value,
            "renderer_ref": self.renderer_ref,
            "run_ref": self.run_ref,
            "runtime_ref": self.runtime_ref,
            "scene_content_sha256": self.scene_content_sha256,
            "scene_ref": self.scene_ref,
            "task_ref": self.task_ref,
            "time_seconds": self.time_seconds,
        }


@dataclass(frozen=True)
class RenderFrameRef:
    project_ref: ProjectRef
    task_ref: str
    run_ref: str
    node_ref: str
    executor_ref: str
    dependencies: tuple[str, ...]
    scene_ref: str
    scene_content_sha256: str
    camera_ref: str
    camera_transform: tuple[float, ...]
    lens_ref: str
    camera_settings_sha256: str
    frame: int
    config_ref: str
    config_digest: str
    renderer_ref: str
    runtime_ref: str
    pass_id: str
    artifact_ref: str
    content_sha256: str
    verified: bool
    camera_object: str
    camera_settings: Mapping[str, str]
    config_id: str
    config_version: str
    media_type: str
    channels: tuple[str, ...]
    required_passes: tuple[str, ...]
    producer_attempt_id: str
    producer_fence: int
    producer_attempt_record_sha256: str
    resource_ref: str
    resource_identity_sha256: str
    device_identity: str

    @classmethod
    def from_request(
        cls,
        request: RenderRequest,
        artifact_ref: str,
        content_sha256: str,
        verified: bool,
        pass_id: str = "beauty",
        *,
        attempt: NodeExecutionAttempt | None = None,
        producer_attempt_id: str | None = None,
        producer_fence: int | None = None,
        producer_attempt_record_sha256: str | None = None,
        renderer_ref: str | None = None,
        runtime_ref: str | None = None,
        executor_ref: str | None = None,
        resource_ref: str,
        resource_identity_sha256: str,
        device_identity: str,
    ) -> RenderFrameRef:
        if attempt is not None:
            producer_attempt_id = attempt.attempt_id
            producer_fence = attempt.fence
            producer_attempt_record_sha256 = attempt.record_sha256
            executor_ref = attempt.owner_ref if executor_ref is None else executor_ref
        if producer_attempt_id is None or producer_fence is None or producer_attempt_record_sha256 is None:
            raise RenderContractError("producer attempt evidence is required")
        return cls(
            request.project_ref, request.task_ref, request.run_ref, request.node_ref,
            request.executor_ref if executor_ref is None else executor_ref,
            request.dependencies, request.scene_ref, request.scene_content_sha256,
            request.camera_ref, request.camera_transform, request.lens_ref,
            request.camera_settings_sha256, request.frame_start,
            request.config.config_ref, request.config.digest,
            request.renderer_ref if renderer_ref is None else renderer_ref,
            request.runtime_ref if runtime_ref is None else runtime_ref,
            pass_id, artifact_ref, content_sha256, verified,
            request.camera_object, request.camera_settings, request.config.config_id,
            request.config.config_version, request.config.media_type,
            request.config.channels, request.config.passes, producer_attempt_id,
            producer_fence, producer_attempt_record_sha256, resource_ref,
            resource_identity_sha256, device_identity,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.frame, int) or isinstance(self.frame, bool) or not self.verified:
            raise RenderContractError("frame")
        for name in ("task_ref", "run_ref", "node_ref", "executor_ref", "scene_ref", "camera_ref", "lens_ref", "config_ref", "renderer_ref", "runtime_ref", "artifact_ref", "resource_ref", "device_identity"):
            object.__setattr__(self, name, _ref(getattr(self, name), name))
        for name in ("scene_content_sha256", "camera_settings_sha256", "config_digest", "content_sha256", "producer_attempt_record_sha256", "resource_identity_sha256"):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        if _ATTEMPT.fullmatch(self.producer_attempt_id) is None or not isinstance(self.producer_fence, int) or isinstance(self.producer_fence, bool) or self.producer_fence < 1:
            raise RenderContractError("producer attempt/fence")
        object.__setattr__(self, "camera_transform", _floats(self.camera_transform, "camera_transform", 16))
        object.__setattr__(self, "camera_object", _text(self.camera_object, "camera_object", 256))
        object.__setattr__(self, "camera_settings", _mapping(self.camera_settings, "camera_settings"))
        object.__setattr__(self, "config_id", _text(self.config_id, "config_id", 256))
        if _SEMVER.fullmatch(self.config_version) is None or self.media_type != "image/png":
            raise RenderContractError("frame config/media identity")
        object.__setattr__(self, "channels", _channels(self.channels))
        passes = tuple(self.required_passes)
        if not passes or self.pass_id not in passes or set(passes) - _SUPPORTED_PASSES:
            raise RenderContractError("frame pass identity")
        object.__setattr__(self, "required_passes", passes)
        if not isinstance(self.dependencies, tuple):
            raise RenderContractError("frame dependencies")

    def payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref,
            "camera_object": self.camera_object,
            "camera_ref": self.camera_ref,
            "camera_settings": dict(self.camera_settings),
            "camera_settings_sha256": self.camera_settings_sha256,
            "camera_transform": list(self.camera_transform),
            "channels": list(self.channels),
            "config_digest": self.config_digest,
            "config_id": self.config_id,
            "config_ref": self.config_ref,
            "config_version": self.config_version,
            "content_sha256": self.content_sha256,
            "dependencies": list(self.dependencies),
            "device_identity": self.device_identity,
            "executor_ref": self.executor_ref,
            "frame": self.frame,
            "lens_ref": self.lens_ref,
            "media_type": self.media_type,
            "node_ref": self.node_ref,
            "pass_id": self.pass_id,
            "producer_attempt_id": self.producer_attempt_id,
            "producer_attempt_record_sha256": self.producer_attempt_record_sha256,
            "producer_fence": self.producer_fence,
            "project_ref": self.project_ref.value,
            "renderer_ref": self.renderer_ref,
            "required_passes": list(self.required_passes),
            "resource_identity_sha256": self.resource_identity_sha256,
            "resource_ref": self.resource_ref,
            "run_ref": self.run_ref,
            "runtime_ref": self.runtime_ref,
            "scene_content_sha256": self.scene_content_sha256,
            "scene_ref": self.scene_ref,
            "task_ref": self.task_ref,
            "verified": self.verified,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> RenderFrameRef:
        try:
            return cls(
                ProjectRef(str(payload["project_ref"])), str(payload["task_ref"]),
                str(payload["run_ref"]), str(payload["node_ref"]),
                str(payload["executor_ref"]),
                tuple(cast(Sequence[str], payload["dependencies"])),
                str(payload["scene_ref"]), str(payload["scene_content_sha256"]),
                str(payload["camera_ref"]),
                tuple(cast(Sequence[float], payload["camera_transform"])),
                str(payload["lens_ref"]), str(payload["camera_settings_sha256"]),
                int(cast(int, payload["frame"])), str(payload["config_ref"]),
                str(payload["config_digest"]), str(payload["renderer_ref"]),
                str(payload["runtime_ref"]), str(payload["pass_id"]),
                str(payload["artifact_ref"]), str(payload["content_sha256"]),
                bool(payload["verified"]), str(payload["camera_object"]),
                dict(cast(Mapping[str, str], payload["camera_settings"])),
                str(payload["config_id"]),
                str(payload["config_version"]), str(payload["media_type"]),
                tuple(cast(Sequence[str], payload["channels"])),
                tuple(cast(Sequence[str], payload["required_passes"])),
                str(payload["producer_attempt_id"]),
                int(cast(int, payload["producer_fence"])),
                str(payload["producer_attempt_record_sha256"]),
                str(payload["resource_ref"]), str(payload["resource_identity_sha256"]),
                str(payload["device_identity"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RenderContractError("persisted frame evidence is malformed") from exc


@dataclass(frozen=True)
class RenderSequenceManifest:
    project_ref: ProjectRef
    request: RenderRequest
    expected_frames: tuple[int, ...]
    completed_frames: tuple[RenderFrameRef, ...]
    failed_frames: tuple[int, ...]
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.request, RenderRequest) or self.request.project_ref != self.project_ref:
            raise RenderContractError("manifest")
        _sha(self.digest, "supplied manifest digest")
        expected = tuple(self.expected_frames)
        if expected != tuple(range(self.request.frame_start, self.request.frame_end + 1)):
            raise RenderContractError("manifest expected frames")
        failed = tuple(sorted(set(self.failed_frames)))
        if len(failed) != len(self.failed_frames) or set(failed) - set(expected):
            raise RenderContractError("manifest failed frames")
        completed = tuple(self.completed_frames)
        if len({(item.frame, item.pass_id) for item in completed}) != len(completed):
            raise RenderContractError("manifest duplicate frames")
        if any(item.frame not in expected for item in completed) or set(failed) & {item.frame for item in completed}:
            raise RenderContractError("manifest frames")
        for frame in completed:
            self.require_frame(frame)
        object.__setattr__(self, "expected_frames", expected)
        object.__setattr__(self, "failed_frames", failed)
        object.__setattr__(self, "completed_frames", completed)
        object.__setattr__(self, "digest", _digest({
            "completed": [item.payload() for item in completed],
            "expected": list(expected),
            "failed": list(failed),
            "request": self.request.identity_payload(),
        }))

    def require_frame(self, frame: RenderFrameRef) -> RenderFrameRef:
        request = self.request
        if not isinstance(frame, RenderFrameRef) or frame.project_ref != self.project_ref:
            raise RenderContractError("frame stale")
        exact = (
            frame.task_ref, frame.run_ref, frame.scene_ref,
            frame.scene_content_sha256, frame.camera_ref, frame.camera_object,
            frame.camera_transform, frame.lens_ref, frame.camera_settings_sha256,
            dict(frame.camera_settings), frame.config_id, frame.config_version,
            frame.config_ref, frame.config_digest, frame.media_type,
            frame.channels, frame.required_passes,
        )
        wanted = (
            request.task_ref, request.run_ref, request.scene_ref,
            request.scene_content_sha256, request.camera_ref,
            request.camera_object, request.camera_transform, request.lens_ref,
            request.camera_settings_sha256, dict(request.camera_settings),
            request.config.config_id, request.config.config_version,
            request.config.config_ref, request.config.digest,
            request.config.media_type, request.config.channels,
            request.config.passes,
        )
        if exact != wanted or frame.pass_id not in request.config.passes:
            raise RenderContractError("frame stale")
        return frame


@runtime_checkable
class RendererAdapter(Protocol):
    project_ref: ProjectRef
    renderer_ref: str
    runtime_ref: str
    executor_ref: str

    def inspect(self, request: RenderRequest) -> Mapping[str, object]: ...
    def describeRuntime(self) -> Mapping[str, object]: ...
    def validateOutput(self, payload: bytes, request: RenderRequest, pass_id: str = "beauty") -> tuple[int, int, tuple[str, ...]]: ...
    def renderFrame(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: RenderRequest, *, scene_artifact_ref: ArtifactRef, root_ref: FilesystemRootRef, working_directory: str, idempotency_key: str, pass_id: str = "beauty", resource_allocation_ref: ResourceAllocationRef | None = None) -> RenderFrameRef: ...
    def renderSequence(self, access: ProjectAccess, coordinator_attempt: NodeExecutionAttempt, request: RenderRequest, *, scene_artifact_ref: ArtifactRef, root_ref: FilesystemRootRef, working_directory: str, idempotency_key: str, child_dispatches: Mapping[tuple[int, str], ScheduledDispatch] | None = None) -> RenderSequenceManifest: ...
    def renderPasses(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: RenderRequest, *, scene_artifact_ref: ArtifactRef, root_ref: FilesystemRootRef, working_directory: str, idempotency_key: str, resource_allocation_ref: ResourceAllocationRef | None = None) -> tuple[RenderFrameRef, ...]: ...
    def cancel(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: RenderRequest, *, idempotency_key: str) -> None: ...
    def render(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: RenderRequest, *, scene_artifact_ref: ArtifactRef, root_ref: FilesystemRootRef, working_directory: str, idempotency_key: str, pass_id: str = "beauty", resource_allocation_ref: ResourceAllocationRef | None = None) -> RenderFrameRef: ...
    def render_sequence(self, access: ProjectAccess, coordinator_attempt: NodeExecutionAttempt, request: RenderRequest, *, scene_artifact_ref: ArtifactRef, root_ref: FilesystemRootRef, working_directory: str, idempotency_key: str, child_dispatches: Mapping[tuple[int, str], ScheduledDispatch] | None = None) -> RenderSequenceManifest: ...


def render_production_pack() -> ProductionPack:
    capabilities = tuple(
        Capability(
            CapabilityRef(f"render.{name}", "1.0.0"),
            f"Bounded render {name}",
            {
                "project": "biella://contracts/project-ref/v1",
                "request": "biella://contracts/render-request/v2",
            },
            {"result": f"biella://contracts/render-{name}/v2"},
            (),
            "2026-08-31T00:00:00+00:00",
        )
        for name in _NAMES
    )
    refs = {item.name: item.capability_ref for item in capabilities}
    steps = tuple(
        GraphRecipeStepRegistration(name, refs[name], () if index == 0 else (_NAMES[index - 1],))
        for index, name in enumerate(_NAMES)
    )
    return ProductionPack(
        ProductionPackRef("render", "1.0.0"), capabilities,
        (GraphRecipeRegistration("pack-recipe://render/production@1.0.0", steps),),
        tuple(
            ValidatorRegistration(
                f"pack-validator://render/{name}@1.0.0", refs[name],
                f"validation-check://artifact-role/{_ROLES[index % len(_ROLES)]}/v1",
            )
            for index, name in enumerate(_NAMES)
        ),
        _ROLES,
        {item.capability_ref.value: ("adapter://renderer/v1",) for item in capabilities},
        {item.capability_ref.value: "resource-profile://render/project-configured/v1" for item in capabilities},
        "2026-08-31T00:00:00+00:00",
    )
