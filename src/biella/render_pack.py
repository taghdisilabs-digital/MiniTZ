from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import re
from typing import TYPE_CHECKING, Protocol

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

_N = (
    "inspect",
    "preview",
    "frame",
    "sequence",
    "batch",
    "raster",
    "raytrace",
    "pathtrace",
    "pass",
    "composite_input",
    "validate",
    "performance",
)
_R = (
    "render.config",
    "render.frame",
    "render.sequence",
    "render.pass",
    "render.preview",
    "render.validation",
)
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA = re.compile(r"[0-9a-f]{64}")


class RenderContractError(ValueError):
    pass


class RendererAdapter(Protocol):
    """Provider-neutral renderer interface.

    Implementations may expose provider-specific internals in their own modules,
    but Tasks and production-pack consumers depend only on these semantic
    operations.
    """

    project_ref: ProjectRef
    renderer_ref: str
    runtime_ref: str
    executor_ref: str

    def inspect(
        self,
        access: "ProjectAccess",
        request: "RenderRequest",
        *,
        scene_artifact_ref: "ArtifactRef",
    ) -> Mapping[str, object]: ...

    def renderFrame(
        self,
        access: "ProjectAccess",
        attempt: "NodeExecutionAttempt",
        request: "RenderRequest",
        *,
        scene_artifact_ref: "ArtifactRef",
        root_ref: "FilesystemRootRef",
        working_directory: str,
        idempotency_key: str,
        pass_id: str = "beauty",
        resource_allocation_ref: "ResourceAllocationRef | None" = None,
    ) -> "RenderFrameRef": ...

    def renderSequence(
        self,
        access: "ProjectAccess",
        coordinator_attempt: "NodeExecutionAttempt",
        request: "RenderRequest",
        *,
        scene_artifact_ref: "ArtifactRef",
        root_ref: "FilesystemRootRef",
        working_directory: str,
        idempotency_key: str,
        child_dispatches: Mapping[tuple[int, str], "ScheduledDispatch"] | None = None,
    ) -> "RenderSequenceManifest": ...

    def renderPasses(
        self,
        access: "ProjectAccess",
        coordinator_attempt: "NodeExecutionAttempt",
        request: "RenderRequest",
        *,
        scene_artifact_ref: "ArtifactRef",
        root_ref: "FilesystemRootRef",
        working_directory: str,
        idempotency_key: str,
        child_dispatches: Mapping[tuple[int, str], "ScheduledDispatch"] | None = None,
    ) -> "RenderSequenceManifest": ...

    def cancel(self, *, idempotency_key: str) -> bool: ...

    def describeRuntime(self) -> Mapping[str, object]: ...

    def validateOutput(
        self,
        access: "ProjectAccess",
        frame: "RenderFrameRef",
        *,
        request: "RenderRequest | None" = None,
    ) -> "RenderFrameRef": ...


def _r(x: object, n: str) -> str:
    if not isinstance(x, str) or not _REF.fullmatch(x):
        raise RenderContractError(n)
    return x


def _s(x: object, n: str) -> str:
    if not isinstance(x, str) or not _SHA.fullmatch(x):
        raise RenderContractError(n)
    return x


def _f(x: object, n: str, l: int) -> tuple[float, ...]:
    if isinstance(x, (str, bytes)) or not isinstance(x, Sequence) or len(x) != l:
        raise RenderContractError(n)
    try:
        v = tuple(float(i) for i in x)
    except (TypeError, ValueError):
        raise RenderContractError(n) from None
    if not all(math.isfinite(i) for i in v):
        raise RenderContractError(n)
    return v


@dataclass(frozen=True)
class RenderConfig:
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

    def __post_init__(self) -> None:
        if (
            not isinstance(self.project_ref, ProjectRef)
            or self.kind not in {"preview", "final"}
            or not isinstance(self.config_id, str)
            or not self.config_id
        ):
            raise RenderContractError("config")
        object.__setattr__(self, "config_ref", _r(self.config_ref, "config_ref"))
        object.__setattr__(self, "digest", _s(self.digest, "digest"))
        if (
            len(self.dimensions) != 2
            or any(not isinstance(x, int) or x <= 0 for x in self.dimensions)
            or not self.channels
            or not self.passes
            or any(not isinstance(x, str) or not x for x in (*self.channels, *self.passes))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise RenderContractError("dimensions channels passes timeout")


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

    def __post_init__(self) -> None:
        if (
            not isinstance(self.project_ref, ProjectRef)
            or not isinstance(self.config, RenderConfig)
            or self.config.project_ref != self.project_ref
            or self.capability_id not in {f"render.{n}" for n in _N}
        ):
            raise RenderContractError("request")
        for n in (
            "task_ref",
            "run_ref",
            "node_ref",
            "scene_ref",
            "camera_ref",
            "lens_ref",
            "renderer_ref",
            "runtime_ref",
            "executor_ref",
        ):
            object.__setattr__(self, n, _r(getattr(self, n), n))
        for n in ("scene_content_sha256", "camera_settings_sha256"):
            object.__setattr__(self, n, _s(getattr(self, n), n))
        object.__setattr__(
            self, "camera_transform", _f(self.camera_transform, "camera_transform", 16)
        )
        if (
            not isinstance(self.frame_start, int)
            or not isinstance(self.frame_end, int)
            or self.frame_end < self.frame_start
            or not math.isfinite(self.time_seconds)
        ):
            raise RenderContractError("frame time")


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

    @classmethod
    def from_request(
        cls,
        r: RenderRequest,
        artifact_ref: str,
        content_sha256: str,
        verified: bool,
        pass_id: str = "beauty",
    ) -> "RenderFrameRef":
        return cls(
            r.project_ref,
            r.task_ref,
            r.run_ref,
            r.node_ref,
            r.executor_ref,
            r.dependencies,
            r.scene_ref,
            r.scene_content_sha256,
            r.camera_ref,
            r.camera_transform,
            r.lens_ref,
            r.camera_settings_sha256,
            r.frame_start,
            r.config.config_ref,
            r.config.digest,
            r.renderer_ref,
            r.runtime_ref,
            pass_id,
            artifact_ref,
            content_sha256,
            verified,
        )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.project_ref, ProjectRef)
            or not isinstance(self.frame, int)
            or not self.verified
        ):
            raise RenderContractError("frame")
        for n in (
            "task_ref",
            "run_ref",
            "node_ref",
            "executor_ref",
            "scene_ref",
            "camera_ref",
            "lens_ref",
            "config_ref",
            "renderer_ref",
            "runtime_ref",
            "artifact_ref",
        ):
            object.__setattr__(self, n, _r(getattr(self, n), n))
        for n in (
            "scene_content_sha256",
            "camera_settings_sha256",
            "config_digest",
            "content_sha256",
        ):
            object.__setattr__(self, n, _s(getattr(self, n), n))
        if not isinstance(self.pass_id, str) or not self.pass_id:
            raise RenderContractError("pass")
        object.__setattr__(
            self, "camera_transform", _f(self.camera_transform, "camera_transform", 16)
        )


@dataclass(frozen=True)
class RenderSequenceManifest:
    project_ref: ProjectRef
    request: RenderRequest
    expected_frames: tuple[int, ...]
    completed_frames: tuple[RenderFrameRef, ...]
    failed_frames: tuple[int, ...]
    digest: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.project_ref, ProjectRef)
            or not isinstance(self.request, RenderRequest)
            or self.request.project_ref != self.project_ref
        ):
            raise RenderContractError("manifest")
        object.__setattr__(self, "digest", _s(self.digest, "digest"))
        fs = tuple(self.completed_frames)
        if (
            len({(f.frame, f.pass_id) for f in fs}) != len(fs)
            or any(f.frame not in self.expected_frames for f in fs)
            or set(self.failed_frames) & {f.frame for f in fs}
        ):
            raise RenderContractError("frames")
        for f in fs:
            self.require_frame(f)
        object.__setattr__(self, "completed_frames", fs)

    def require_frame(self, f: RenderFrameRef) -> RenderFrameRef:
        r = self.request
        if (
            not isinstance(f, RenderFrameRef)
            or f.project_ref != self.project_ref
            or (
                f.task_ref,
                f.run_ref,
                f.scene_ref,
                f.scene_content_sha256,
                f.camera_ref,
                f.camera_transform,
                f.lens_ref,
                f.camera_settings_sha256,
                f.config_ref,
                f.config_digest,
                f.renderer_ref,
                f.runtime_ref,
            )
            != (
                r.task_ref,
                r.run_ref,
                r.scene_ref,
                r.scene_content_sha256,
                r.camera_ref,
                r.camera_transform,
                r.lens_ref,
                r.camera_settings_sha256,
                r.config.config_ref,
                r.config.digest,
                r.renderer_ref,
                r.runtime_ref,
            )
        ):
            raise RenderContractError("frame stale")
        return f


def render_production_pack() -> ProductionPack:
    cs = tuple(
        Capability(
            CapabilityRef(f"render.{n}", "1.0.0"),
            f"Bounded render {n}",
            {"project": "biella://contracts/project-ref/v1"},
            {"result": f"biella://contracts/render-{n}/v1"},
            (),
            "2026-08-31T00:00:00+00:00",
        )
        for n in _N
    )
    d = {c.name: c.capability_ref for c in cs}
    steps = tuple(
        GraphRecipeStepRegistration(n, d[n], (() if i == 0 else (_N[i - 1],)))
        for i, n in enumerate(_N)
    )
    return ProductionPack(
        ProductionPackRef("render", "1.0.0"),
        cs,
        (
            GraphRecipeRegistration(
                "pack-recipe://render/production@1.0.0",
                steps,
            ),
        ),
        tuple(
            ValidatorRegistration(
                f"pack-validator://render/{n}@1.0.0",
                d[n],
                f"validation-check://artifact-role/{_R[i % len(_R)]}/v1",
            )
            for i, n in enumerate(_N)
        ),
        _R,
        {c.capability_ref.value: ("adapter://process/v1",) for c in cs},
        {
            c.capability_ref.value: "resource-profile://render/project-configured/v1"
            for c in cs
        },
        "2026-08-31T00:00:00+00:00",
    )
