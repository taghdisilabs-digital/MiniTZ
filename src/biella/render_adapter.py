"""Generic renderer contract implementations over the preserved Blender renderer."""
from __future__ import annotations

from collections.abc import Mapping
from threading import Lock
from types import MappingProxyType

from .artifact import ArtifactRef
from .execution import NodeExecutionAttempt
from .filesystem import FilesystemRootRef
from .object_store import ObjectStorageBackend
from .project import ProjectAccess, ProjectRef
from .render_pack import (
    RenderContractError,
    RenderFrameRef,
    RenderRequest,
    RenderSequenceManifest,
)
from .render_tool import RendererAdapter as _BlenderRenderToolAdapter, _png_dimensions
from .scheduler import ResourceAllocationRef, ScheduledDispatch
from .three_d_tool import ThreeDToolIdentity


class BlenderRendererAdapter(_BlenderRenderToolAdapter):
    """Blender implementation of the provider-neutral RendererAdapter contract.

    The inherited ``render``/``render_sequence`` methods remain adapter-local
    compatibility internals.  Public production-pack callers use the semantic
    operations below.
    """

    def __init__(
        self,
        database_path: str,
        object_store: ObjectStorageBackend,
        *,
        identity: ThreeDToolIdentity,
    ) -> None:
        super().__init__(database_path, object_store, identity=identity)
        self._cancelled_keys: set[str] = set()
        self._cancel_lock = Lock()

    @staticmethod
    def _idempotency_key(value: object) -> str:
        if (
            not isinstance(value, str)
            or not value
            or len(value.encode()) > 256
            or any(ord(character) < 33 for character in value)
        ):
            raise RenderContractError("render idempotency key is malformed")
        return value

    def _require_not_cancelled(
        self,
        request: RenderRequest,
        idempotency_key: str,
    ) -> None:
        key = self._idempotency_key(idempotency_key)
        with self._cancel_lock:
            cancelled = key in self._cancelled_keys
        if not cancelled:
            return
        if not request.config.cancel_allowed:
            raise RenderContractError("render cancellation is forbidden by config")
        raise RenderContractError("render was cancelled before launch or recovery")

    def inspect(
        self,
        access: ProjectAccess,
        request: RenderRequest,
        *,
        scene_artifact_ref: ArtifactRef,
    ) -> Mapping[str, object]:
        if (
            request.project_ref != access.project_ref
            or scene_artifact_ref.project_ref != access.project_ref
        ):
            raise RenderContractError("render inspection crossed Project scope")
        scene = self.artifacts.get_artifact(access, scene_artifact_ref)
        if (
            scene.content_ref is None
            or scene.content_ref.digest != request.scene_content_sha256
            or scene_artifact_ref.value != request.scene_ref
        ):
            raise RenderContractError("render inspection source identity changed")
        return MappingProxyType(
            {
                "project_ref": access.project_ref.value,
                "scene_ref": request.scene_ref,
                "scene_content_sha256": request.scene_content_sha256,
                "camera_ref": request.camera_ref,
                "camera_settings_sha256": request.camera_settings_sha256,
                "config_ref": request.config.config_ref,
                "config_digest": request.config.digest,
                "renderer_ref": self.renderer_ref,
                "runtime_ref": self.runtime_ref,
                "executor_ref": self.executor_ref,
            }
        )

    def renderFrame(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: RenderRequest,
        *,
        scene_artifact_ref: ArtifactRef,
        root_ref: FilesystemRootRef,
        working_directory: str,
        idempotency_key: str,
        pass_id: str = "beauty",
        resource_allocation_ref: ResourceAllocationRef | None = None,
    ) -> RenderFrameRef:
        self._require_not_cancelled(request, idempotency_key)
        self.inspect(access, request, scene_artifact_ref=scene_artifact_ref)
        frame = super().render(
            access,
            attempt,
            request,
            scene_artifact_ref=scene_artifact_ref,
            root_ref=root_ref,
            working_directory=working_directory,
            idempotency_key=idempotency_key,
            pass_id=pass_id,
            resource_allocation_ref=resource_allocation_ref,
        )
        return self.validateOutput(access, frame, request=request)

    def renderSequence(
        self,
        access: ProjectAccess,
        coordinator_attempt: NodeExecutionAttempt,
        request: RenderRequest,
        *,
        scene_artifact_ref: ArtifactRef,
        root_ref: FilesystemRootRef,
        working_directory: str,
        idempotency_key: str,
        child_dispatches: Mapping[tuple[int, str], ScheduledDispatch] | None = None,
    ) -> RenderSequenceManifest:
        self._require_not_cancelled(request, idempotency_key)
        self.inspect(access, request, scene_artifact_ref=scene_artifact_ref)
        manifest = super().render_sequence(
            access,
            coordinator_attempt,
            request,
            scene_artifact_ref=scene_artifact_ref,
            root_ref=root_ref,
            working_directory=working_directory,
            idempotency_key=idempotency_key,
            child_dispatches=child_dispatches,
        )
        for frame in manifest.completed_frames:
            self.validateOutput(access, frame, request=request)
        return manifest

    def renderPasses(
        self,
        access: ProjectAccess,
        coordinator_attempt: NodeExecutionAttempt,
        request: RenderRequest,
        *,
        scene_artifact_ref: ArtifactRef,
        root_ref: FilesystemRootRef,
        working_directory: str,
        idempotency_key: str,
        child_dispatches: Mapping[tuple[int, str], ScheduledDispatch] | None = None,
    ) -> RenderSequenceManifest:
        if not request.config.passes:
            raise RenderContractError("render pass set is empty")
        return self.renderSequence(
            access,
            coordinator_attempt,
            request,
            scene_artifact_ref=scene_artifact_ref,
            root_ref=root_ref,
            working_directory=working_directory,
            idempotency_key=idempotency_key,
            child_dispatches=child_dispatches,
        )

    def cancel(self, *, idempotency_key: str) -> bool:
        key = self._idempotency_key(idempotency_key)
        with self._cancel_lock:
            if key in self._cancelled_keys:
                return False
            self._cancelled_keys.add(key)
            return True

    def describeRuntime(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "adapter_ref": self.identity.adapter_ref,
                "renderer_ref": self.renderer_ref,
                "runtime_ref": self.runtime_ref,
                "executor_ref": self.executor_ref,
                "tool": self.identity.payload(),
                "durable_recovery": "FRAME_AND_RESULT_JOURNAL",
                "cancellation_mode": "PRELAUNCH_FAIL_CLOSED",
            }
        )

    def validateOutput(
        self,
        access: ProjectAccess,
        frame: RenderFrameRef,
        *,
        request: RenderRequest | None = None,
    ) -> RenderFrameRef:
        if frame.project_ref != access.project_ref:
            raise RenderContractError("render validation crossed Project scope")
        artifact_id, revision = self._artifact_identity(frame.artifact_ref)
        artifact = self.artifacts.get_artifact(
            access,
            ArtifactRef(access.project_ref, artifact_id, revision),
        )
        if (
            artifact.content_ref is None
            or artifact.content_ref.digest != frame.content_sha256
        ):
            raise RenderContractError("render output artifact/content identity changed")
        width, height, channels = _png_dimensions(self.objects.read(artifact.content_ref))
        if channels < 3:
            raise RenderContractError("render output lacks required colour channels")
        if request is not None:
            if frame.frame < request.frame_start or frame.frame > request.frame_end:
                raise RenderContractError("render output frame is outside request")
            RenderSequenceManifest(
                access.project_ref,
                request,
                tuple(range(request.frame_start, request.frame_end + 1)),
                (frame,),
                (),
                "0" * 64,
            ).require_frame(frame)
            if (width, height) != request.config.dimensions:
                raise RenderContractError("render output dimensions changed")
        return frame


class ReferenceRendererAdapter:
    """Schema-compatible non-real renderer used only for reference-path proof."""

    def __init__(self, project_ref: ProjectRef) -> None:
        self.project_ref = project_ref
        self.renderer_ref = "renderer://reference"
        self.runtime_ref = "runtime://reference/not-run"
        self.executor_ref = "executor://reference"

    def inspect(
        self,
        access: ProjectAccess,
        request: RenderRequest,
        *,
        scene_artifact_ref: ArtifactRef,
    ) -> Mapping[str, object]:
        if access.project_ref != self.project_ref or request.project_ref != self.project_ref:
            raise RenderContractError("reference renderer crossed Project scope")
        return MappingProxyType(
            {
                "reality": "REFERENCE",
                "scene_ref": scene_artifact_ref.value,
                "renderer_ref": self.renderer_ref,
                "runtime_ref": self.runtime_ref,
            }
        )

    def renderFrame(self, *args: object, **kwargs: object) -> RenderFrameRef:
        raise RenderContractError(
            "REFERENCE renderer cannot claim REAL verified render evidence"
        )

    def renderSequence(self, *args: object, **kwargs: object) -> RenderSequenceManifest:
        raise RenderContractError(
            "REFERENCE renderer cannot claim REAL verified render evidence"
        )

    def renderPasses(self, *args: object, **kwargs: object) -> RenderSequenceManifest:
        raise RenderContractError(
            "REFERENCE renderer cannot claim REAL verified render evidence"
        )

    def cancel(self, *, idempotency_key: str) -> bool:
        BlenderRendererAdapter._idempotency_key(idempotency_key)
        return False

    def describeRuntime(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "reality": "REFERENCE",
                "renderer_ref": self.renderer_ref,
                "runtime_ref": self.runtime_ref,
                "executor_ref": self.executor_ref,
            }
        )

    def validateOutput(
        self,
        access: ProjectAccess,
        frame: RenderFrameRef,
        *,
        request: RenderRequest | None = None,
    ) -> RenderFrameRef:
        raise RenderContractError(
            "REFERENCE renderer cannot validate REAL render evidence"
        )
