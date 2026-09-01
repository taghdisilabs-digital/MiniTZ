"""Project-scoped REAL Blender rendering on the generic process substrate."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
from types import MappingProxyType
import zlib
from typing import cast

from .artifact import ArtifactRef, ArtifactService
from .execution import NodeExecutionAttempt, NodeExecutionService
from .filesystem import FilesystemAdapter, FilesystemError, FilesystemRootRef
from .object_store import ObjectStorageBackend
from .process import ManagedProcessAdapter, ProcessExecutionRequest, ProcessStatus
from .project import ProjectAccess, ProjectRef
from .render_pack import (
    RenderConfig,
    RenderContractError,
    RenderFrameRef,
    RenderRequest,
    RenderSequenceManifest,
)
from .scheduler import ResourceAllocationRef, ScheduledDispatch, Scheduler
from .three_d_tool import ThreeDToolIdentity, _ThreeDService


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _request_identity(request: RenderRequest) -> dict[str, object]:
    return request.identity_payload()


def _png_dimensions(payload: bytes) -> tuple[int, int, int]:
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RenderContractError("rendered frame is not PNG")
    offset = 8
    width = height = channels = 0
    compressed = bytearray()
    seen_header = False
    seen_data = False
    seen_end = False
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise RenderContractError("PNG is truncated")
        size = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(payload):
            raise RenderContractError("PNG is truncated")
        data = payload[offset + 8:offset + 8 + size]
        expected_crc = struct.unpack(">I", payload[offset + 8 + size:end])[0]
        if zlib.crc32(kind + data) & 0xffffffff != expected_crc:
            raise RenderContractError("PNG chunk integrity failed")
        if kind == b"IHDR":
            if seen_header or offset != 8 or size != 13:
                raise RenderContractError("PNG IHDR is malformed")
            width, height, depth, colour, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(colour, 0)
            if (
                not width or not height or depth != 8 or not channels
                or compression != 0 or filtering != 0 or interlace != 0
            ):
                raise RenderContractError("PNG dimensions, channels, or encoding are unsupported")
            seen_header = True
        elif kind == b"IDAT":
            if not seen_header or seen_end:
                raise RenderContractError("PNG image data ordering is malformed")
            compressed.extend(data)
            seen_data = True
        elif kind == b"IEND":
            if not seen_header or not seen_data or seen_end or size != 0:
                raise RenderContractError("PNG IEND is malformed")
            seen_end = True
            offset = end
            if offset != len(payload):
                raise RenderContractError("PNG has trailing data after IEND")
            break
        offset = end
    if not seen_end:
        raise RenderContractError("PNG lacks IEND")
    decoder = zlib.decompressobj()
    try:
        decoded = decoder.decompress(bytes(compressed)) + decoder.flush()
    except zlib.error as exc:
        raise RenderContractError("PNG pixels are corrupt") from exc
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise RenderContractError("PNG compressed stream is malformed")
    stride = width * channels
    if len(decoded) != height * (1 + stride):
        raise RenderContractError("PNG decoded size is inconsistent")
    for row in range(height):
        if decoded[row * (stride + 1)] not in range(5):
            raise RenderContractError("PNG scanline filter is invalid")
    return width, height, channels


def _frame_record(frame: RenderFrameRef) -> tuple[str, str]:
    payload = frame.payload()
    return _json(payload).decode(), _digest(payload)


def _driver_receipt(stdout_preview: str) -> Mapping[str, object]:
    marker = "BIELLA_RENDER="
    for line in reversed(stdout_preview.splitlines()):
        position = line.find(marker)
        if position >= 0:
            try:
                value = json.loads(line[position + len(marker):])
            except (TypeError, ValueError) as exc:
                raise RenderContractError("Blender render receipt is malformed") from exc
            if not isinstance(value, dict):
                raise RenderContractError("Blender render receipt is malformed")
            return value
    raise RenderContractError("Blender render receipt is missing")


class RendererAdapter:
    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        identity: ThreeDToolIdentity,
    ) -> None:
        if not isinstance(identity, ThreeDToolIdentity):
            raise TypeError("identity must be ThreeDToolIdentity")
        self.database = Path(database_path)
        self.objects = object_store
        self.identity = identity
        self.project_ref = identity.project_ref
        self.renderer_ref = "renderer://blender"
        self.runtime_ref = identity.runtime_ref
        self.executor_ref = "executor://local"
        self.artifacts = ArtifactService(self.database)
        self.filesystem = FilesystemAdapter(self.database, object_store)
        self.process = ManagedProcessAdapter(self.database, object_store)
        self.executions = NodeExecutionService(self.database)
        self.scheduler = Scheduler(self.database)
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS render_sequence_frames ("
                "project_id TEXT NOT NULL, sequence_digest TEXT NOT NULL, frame INTEGER NOT NULL, "
                "pass_id TEXT NOT NULL, artifact_id TEXT NOT NULL, artifact_revision INTEGER NOT NULL, "
                "content_sha256 TEXT NOT NULL, frame_json TEXT, frame_sha256 TEXT, "
                "PRIMARY KEY (project_id, sequence_digest, frame, pass_id))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS render_frame_results ("
                "project_id TEXT NOT NULL, result_digest TEXT NOT NULL, artifact_id TEXT NOT NULL, "
                "artifact_revision INTEGER NOT NULL, content_sha256 TEXT NOT NULL, "
                "frame_json TEXT, frame_sha256 TEXT, "
                "PRIMARY KEY (project_id, result_digest))"
            )
            for table in ("render_sequence_frames", "render_frame_results"):
                columns = {
                    str(row[1])
                    for row in connection.execute(f"PRAGMA table_info({table})")
                }
                if "frame_json" not in columns:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN frame_json TEXT")
                if "frame_sha256" not in columns:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN frame_sha256 TEXT")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS render_sequence_claims ("
                "project_id TEXT NOT NULL, sequence_key TEXT NOT NULL, identity_digest TEXT NOT NULL, "
                "request_json TEXT NOT NULL, PRIMARY KEY (project_id, sequence_key))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS render_cancellations ("
                "project_id TEXT NOT NULL, request_digest TEXT NOT NULL, attempt_id TEXT NOT NULL, "
                "attempt_fence INTEGER NOT NULL, idempotency_key TEXT NOT NULL, "
                "PRIMARY KEY (project_id, request_digest, attempt_id, attempt_fence))"
            )
            connection.commit()
        finally:
            connection.close()

    def describeRuntime(self) -> Mapping[str, object]:
        return MappingProxyType({
            "adapter_ref": "adapter://renderer/blender/v1",
            "device_backends": ("CPU", "CUDA", "OPTIX"),
            "executor_ref": self.executor_ref,
            "executable_sha256": self.identity.executable_sha256,
            "identity_sha256": self.identity.semantic_digest,
            "media_types": ("image/png",),
            "project_ref": self.project_ref.value,
            "real": True,
            "renderer_ref": self.renderer_ref,
            "runtime_ref": self.runtime_ref,
            "supported_passes": ("beauty", "normal", "z"),
            "tool_name": self.identity.tool_name,
            "tool_version": self.identity.tool_version,
        })

    def describe_runtime(self) -> Mapping[str, object]:
        return self.describeRuntime()

    @staticmethod
    def _matches_requirement(value: str, actual: str, generic: str) -> bool:
        if value in {actual, generic}:
            return True
        # This legacy URI is a requirement alias, never a producer identity.
        return value == "runtime://blender" and generic == "runtime://generic/v1"

    def inspect(self, request: RenderRequest) -> Mapping[str, object]:
        if not isinstance(request, RenderRequest):
            raise RenderContractError("RenderRequest is required")
        if request.project_ref != self.project_ref:
            raise RenderContractError("renderer adapter crossed Project scope")
        if not self._matches_requirement(request.renderer_ref, self.renderer_ref, "renderer://generic/v1"):
            raise RenderContractError("request renderer identity differs from adapter")
        if not self._matches_requirement(request.runtime_ref, self.runtime_ref, "runtime://generic/v1"):
            raise RenderContractError("request runtime identity differs from adapter")
        return MappingProxyType({
            "config_digest": request.config.digest,
            "request_digest": _digest(_request_identity(request)),
            "runtime": dict(self.describeRuntime()),
        })

    def _assert_live_attempt(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: RenderRequest,
    ) -> None:
        if (
            access.project_ref != self.project_ref
            or request.project_ref != access.project_ref
            or attempt.node_ref.project_ref != access.project_ref
            or attempt.run_ref.project_ref != access.project_ref
            or attempt.task_ref.project_ref != access.project_ref
        ):
            raise RenderContractError("render execution crossed Project scope")
        current = self.executions.get_node_execution(access, attempt.node_ref)
        if (
            current.status != "RUNNING"
            or current.current_attempt_id != attempt.attempt_id
            or current.current_fence != attempt.fence
            or current.current_owner_ref != attempt.owner_ref
            or current.current_run_attempt_id != attempt.run_attempt_id
            or current.current_run_fence != attempt.run_fence
        ):
            raise RenderContractError("render execution attempt/fence is stale")
        if request.executor_ref not in {
            self.executor_ref,
            attempt.owner_ref,
            "executor://generic/v1",
            "executor://local",
        }:
            raise RenderContractError("request executor identity differs from live attempt")

    def _attempt_is_current(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: RenderRequest,
    ) -> bool:
        try:
            self._assert_live_attempt(access, attempt, request)
        except Exception:
            return False
        return True

    def _admit_scene(
        self,
        access: ProjectAccess,
        request: RenderRequest,
        scene_artifact_ref: ArtifactRef,
    ) -> object:
        if (
            scene_artifact_ref.project_ref != access.project_ref
            or scene_artifact_ref.value != request.scene_ref
        ):
            raise RenderContractError("render scene ArtifactRef identity differs from request")
        scene = self.artifacts.get_artifact(access, scene_artifact_ref)
        if scene.content_ref is None or scene.content_ref.digest != request.scene_content_sha256:
            raise RenderContractError("render scene artifact/content identity changed")
        return scene

    def _execution_identity(self, request: RenderRequest) -> dict[str, object]:
        return {
            "request": _request_identity(request),
            "runtime": dict(self.describeRuntime()),
        }

    def _sequence_digest(self, request: RenderRequest, frames: tuple[int, ...]) -> str:
        return _digest({"execution": self._execution_identity(request), "frames": list(frames)})

    def _result_digest(self, request: RenderRequest, pass_id: str) -> str:
        return _digest({
            "execution": self._execution_identity(request),
            "frame": request.frame_start,
            "pass": pass_id,
        })

    @staticmethod
    def _artifact_identity(value: str) -> tuple[str, int]:
        parts = value.rsplit("/", 2)
        if len(parts) != 3 or not parts[0].startswith("artifact://"):
            raise RenderContractError("frame artifact identity is malformed")
        try:
            return parts[1], int(parts[2])
        except ValueError as exc:
            raise RenderContractError("frame artifact identity is malformed") from exc

    def _resource_evidence(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: RenderRequest,
        resource_allocation_ref: ResourceAllocationRef | None,
    ) -> dict[str, object]:
        backend = request.config.device_backend
        if resource_allocation_ref is None:
            if backend != "CPU":
                raise RenderContractError("CUDA/OptiX render requires exact ResourceAllocation")
            payload = {
                "allocation_ref": None,
                "backend": "CPU",
                "device_ids": ["CPU"],
                "executor_ref": attempt.owner_ref,
                "project_ref": access.project_ref.value,
                "runtime_identity_sha256": self.identity.semantic_digest,
            }
            return {
                "allocation_ref": None,
                "backend": "CPU",
                "device_ids": ("CPU",),
                "identity_sha256": _digest(payload),
                "resource_ref": f"resource://{access.project_ref.value}/local-renderer",
            }
        if resource_allocation_ref.project_ref != access.project_ref:
            raise RenderContractError("render ResourceAllocation crossed Project scope")
        allocation = self.scheduler.get_allocation(access, resource_allocation_ref)
        if (
            allocation.status != "DISPATCHED"
            or allocation.node_ref != attempt.node_ref
            or allocation.node_attempt_id != attempt.attempt_id
            or allocation.node_attempt_fence != attempt.fence
            or allocation.owner_ref != attempt.owner_ref
        ):
            raise RenderContractError("render ResourceAllocation/attempt evidence is stale")
        observed_ids = tuple(sorted({
            device_id
            for reservation in allocation.reservations
            for device_id in reservation.device_ids
        }))
        requested_ids = tuple(
            item for item in request.config.resource.get("device_ids", "").split(",") if item
        )
        if backend in {"CUDA", "OPTIX"}:
            if not observed_ids:
                raise RenderContractError("GPU ResourceAllocation has no exact device identity")
            if requested_ids and not set(requested_ids) <= set(observed_ids):
                raise RenderContractError("requested GPU device identity is not allocated")
            device_ids = requested_ids or observed_ids
        else:
            device_ids = ("CPU",)
        allocation_payload: dict[str, object] = {
            "allocation_identity_sha256": allocation.identity_sha256,
            "allocation_ref": allocation.allocation_ref.value,
            "backend": backend,
            "device_ids": list(device_ids),
            "fence": allocation.fence,
            "reservations": [item.payload() for item in allocation.reservations],
            "runtime_identity_sha256": self.identity.semantic_digest,
        }
        return {
            "allocation_ref": allocation.allocation_ref,
            "backend": backend,
            "device_ids": device_ids,
            "identity_sha256": _digest(allocation_payload),
            "resource_ref": allocation.allocation_ref.value,
        }

    def _cancel_digest(self, request: RenderRequest) -> str:
        return _digest(self._execution_identity(request))

    def _is_cancelled(self, request: RenderRequest, attempt: NodeExecutionAttempt) -> bool:
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            return connection.execute(
                "SELECT 1 FROM render_cancellations WHERE project_id=? AND request_digest=? "
                "AND attempt_id=? AND attempt_fence=?",
                (
                    request.project_ref.value, self._cancel_digest(request),
                    attempt.attempt_id, attempt.fence,
                ),
            ).fetchone() is not None
        finally:
            connection.close()

    def cancel(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: RenderRequest,
        *,
        idempotency_key: str,
    ) -> None:
        self.inspect(request)
        self._assert_live_attempt(access, attempt, request)
        if not request.config.cancel_allowed:
            raise RenderContractError("render config forbids cancellation")
        if not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 256:
            raise RenderContractError("cancellation idempotency_key")
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            connection.execute(
                "INSERT OR IGNORE INTO render_cancellations VALUES (?, ?, ?, ?, ?)",
                (
                    access.project_ref.value, self._cancel_digest(request),
                    attempt.attempt_id, attempt.fence, idempotency_key,
                ),
            )
            row = connection.execute(
                "SELECT idempotency_key FROM render_cancellations WHERE project_id=? "
                "AND request_digest=? AND attempt_id=? AND attempt_fence=?",
                (
                    access.project_ref.value, self._cancel_digest(request),
                    attempt.attempt_id, attempt.fence,
                ),
            ).fetchone()
            if row is None or str(row[0]) != idempotency_key:
                raise RenderContractError("cancellation identity conflicts")
            connection.commit()
        finally:
            connection.close()

    def validateOutput(
        self,
        payload: bytes,
        request: RenderRequest,
        pass_id: str = "beauty",
    ) -> tuple[int, int, tuple[str, ...]]:
        if request.config.media_type != "image/png":
            raise RenderContractError("render output media type differs from config")
        if pass_id not in request.config.passes:
            raise RenderContractError("render pass is not declared by config")
        width, height, channel_count = _png_dimensions(payload)
        if (width, height) != request.config.dimensions:
            raise RenderContractError("rendered PNG dimensions differ from config")
        if channel_count != len(request.config.channels):
            raise RenderContractError("rendered PNG channels differ from config")
        return width, height, request.config.channels

    def validate_output(
        self,
        payload: bytes,
        request: RenderRequest,
        pass_id: str = "beauty",
    ) -> tuple[int, int, tuple[str, ...]]:
        return self.validateOutput(payload, request, pass_id)

    def _frame_from_row(
        self,
        access: ProjectAccess,
        request: RenderRequest,
        row: tuple[object, ...],
    ) -> RenderFrameRef:
        artifact_id, revision, content_sha256, frame_json, frame_sha256 = row
        if not isinstance(frame_json, str) or not isinstance(frame_sha256, str):
            raise RenderContractError("legacy render journal lacks exact frame evidence")
        try:
            payload = json.loads(frame_json)
        except ValueError as exc:
            raise RenderContractError("persisted frame evidence is malformed") from exc
        if not isinstance(payload, dict) or _digest(payload) != frame_sha256:
            raise RenderContractError("persisted frame evidence digest changed")
        frame = RenderFrameRef.from_payload(payload)
        artifact_ref = ArtifactRef(
            access.project_ref, str(artifact_id), int(cast(int, revision))
        )
        if (
            frame.artifact_ref != artifact_ref.value
            or frame.content_sha256 != str(content_sha256)
            or frame.renderer_ref != self.renderer_ref
            or frame.runtime_ref != self.runtime_ref
        ):
            raise RenderContractError("durable frame identity is forged or stale")
        one = replace(request, frame_start=frame.frame, frame_end=frame.frame)
        RenderSequenceManifest(access.project_ref, one, (frame.frame,), (frame,), (), "0" * 64)
        artifact = self.artifacts.get_artifact(access, artifact_ref)
        if (
            artifact.content_ref is None
            or artifact.content_ref.digest != frame.content_sha256
            or artifact.content_ref.media_type != request.config.media_type
        ):
            raise RenderContractError("durable frame artifact is forged or stale")
        self.validateOutput(self.objects.read(artifact.content_ref), one, frame.pass_id)
        return frame

    def _replay_result(
        self,
        access: ProjectAccess,
        request: RenderRequest,
        pass_id: str,
    ) -> RenderFrameRef | None:
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            row = connection.execute(
                "SELECT artifact_id, artifact_revision, content_sha256, frame_json, frame_sha256 "
                "FROM render_frame_results WHERE project_id=? AND result_digest=?",
                (access.project_ref.value, self._result_digest(request, pass_id)),
            ).fetchone()
        finally:
            connection.close()
        return None if row is None else self._frame_from_row(access, request, row)

    def _persist_result(
        self,
        access: ProjectAccess,
        request: RenderRequest,
        frame: RenderFrameRef,
    ) -> None:
        artifact_id, revision = self._artifact_identity(frame.artifact_ref)
        frame_json, frame_sha = _frame_record(frame)
        values = (
            access.project_ref.value, self._result_digest(request, frame.pass_id),
            artifact_id, revision, frame.content_sha256, frame_json, frame_sha,
        )
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            connection.execute(
                "INSERT OR IGNORE INTO render_frame_results "
                "(project_id,result_digest,artifact_id,artifact_revision,content_sha256,frame_json,frame_sha256) "
                "VALUES (?,?,?,?,?,?,?)",
                values,
            )
            row = connection.execute(
                "SELECT project_id,result_digest,artifact_id,artifact_revision,content_sha256,frame_json,frame_sha256 "
                "FROM render_frame_results WHERE project_id=? AND result_digest=?",
                values[:2],
            ).fetchone()
            if row != values:
                raise RenderContractError("durable render result identity conflicts")
            connection.commit()
        finally:
            connection.close()

    def _replay_frame(
        self,
        access: ProjectAccess,
        request: RenderRequest,
        sequence_digest: str,
        frame: int,
        pass_id: str,
    ) -> RenderFrameRef | None:
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            row = connection.execute(
                "SELECT artifact_id,artifact_revision,content_sha256,frame_json,frame_sha256 "
                "FROM render_sequence_frames WHERE project_id=? AND sequence_digest=? "
                "AND frame=? AND pass_id=?",
                (access.project_ref.value, sequence_digest, frame, pass_id),
            ).fetchone()
        finally:
            connection.close()
        return None if row is None else self._frame_from_row(access, request, row)

    def _persist_frame(
        self,
        access: ProjectAccess,
        sequence_digest: str,
        frame: RenderFrameRef,
    ) -> None:
        artifact_id, revision = self._artifact_identity(frame.artifact_ref)
        frame_json, frame_sha = _frame_record(frame)
        values = (
            access.project_ref.value, sequence_digest, frame.frame, frame.pass_id,
            artifact_id, revision, frame.content_sha256, frame_json, frame_sha,
        )
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            connection.execute(
                "INSERT OR IGNORE INTO render_sequence_frames "
                "(project_id,sequence_digest,frame,pass_id,artifact_id,artifact_revision,"
                "content_sha256,frame_json,frame_sha256) VALUES (?,?,?,?,?,?,?,?,?)",
                values,
            )
            row = connection.execute(
                "SELECT project_id,sequence_digest,frame,pass_id,artifact_id,artifact_revision,"
                "content_sha256,frame_json,frame_sha256 FROM render_sequence_frames "
                "WHERE project_id=? AND sequence_digest=? AND frame=? AND pass_id=?",
                values[:4],
            ).fetchone()
            if row != values:
                raise RenderContractError("durable sequence frame identity conflicts")
            connection.commit()
        finally:
            connection.close()

    def _claim_sequence(
        self,
        access: ProjectAccess,
        request: RenderRequest,
        frames: tuple[int, ...],
        idempotency_key: str,
    ) -> str:
        if not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 256:
            raise RenderContractError("sequence idempotency_key")
        identity = self._sequence_digest(request, frames)
        request_json = _json(self._execution_identity(request)).decode()
        values = (access.project_ref.value, idempotency_key, identity, request_json)
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            connection.execute(
                "INSERT OR IGNORE INTO render_sequence_claims VALUES (?,?,?,?)",
                values,
            )
            row = connection.execute(
                "SELECT project_id,sequence_key,identity_digest,request_json "
                "FROM render_sequence_claims WHERE project_id=? AND sequence_key=?",
                values[:2],
            ).fetchone()
            if row != values:
                raise RenderContractError("same render sequence mixed source/config/camera/runtime identity")
            connection.commit()
        finally:
            connection.close()
        return identity

    def _render_reference_frame(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: RenderRequest,
        scene_artifact_ref: ArtifactRef,
        scene: object,
        resource: Mapping[str, object],
        pass_id: str,
        resource_allocation_ref: ResourceAllocationRef | None,
    ) -> RenderFrameRef:
        if resource["backend"] != "CPU":
            raise RenderContractError("REFERENCE renderer supports CPU Resources only")
        seed = hashlib.sha256(_json({
            "pass_id": pass_id,
            "renderer_ref": self.renderer_ref,
            "request": _request_identity(request),
            "runtime_ref": self.runtime_ref,
        })).digest()
        payload = _reference_png(
            request.config.dimensions[0],
            request.config.dimensions[1],
            "".join(request.config.channels),
            seed,
        )
        self.validateOutput(payload, request, pass_id)
        output = self.objects.put(payload, media_type=request.config.media_type)
        self._assert_live_attempt(access, attempt, request)
        if self._is_cancelled(request, attempt):
            raise RenderContractError("cancelled render result was fenced before publication")
        current_resource = self._resource_evidence(
            access, attempt, request, resource_allocation_ref
        )
        if current_resource["identity_sha256"] != resource["identity_sha256"]:
            raise RenderContractError("render Resource identity changed before publication")
        device_identity = f"device://reference/cpu/{resource['identity_sha256']}"
        role = (
            "render.preview"
            if request.config.kind == "preview" and pass_id == "beauty"
            else "render.frame"
            if request.config.kind == "final" and pass_id == "beauty"
            else "render.pass"
        )
        artifact = self.artifacts.create_artifact(
            access,
            project_ref=access.project_ref,
            role=role,
            content_ref=output,
            source_refs=(),
            source_artifact_refs=(scene_artifact_ref,),
            source_content_refs=(getattr(scene, "content_ref"),),
            derivation_type="render.reference",
            metadata={
                "media_type": request.config.media_type,
                "media_profile": json.dumps({
                    "camera_settings_sha256": request.camera_settings_sha256,
                    "channels": request.config.channels,
                    "config_sha256": request.config.digest,
                    "device_identity": device_identity,
                    "dimensions": request.config.dimensions,
                    "pass_id": pass_id,
                    "producer_attempt_id": attempt.attempt_id,
                    "producer_fence": attempt.fence,
                    "renderer_ref": self.renderer_ref,
                    "resource_identity_sha256": resource["identity_sha256"],
                    "runtime_ref": self.runtime_ref,
                }, sort_keys=True, separators=(",", ":")),
                "semantic_label": pass_id,
                "semantic_version": request.config.config_version,
            },
        )
        frame = RenderFrameRef.from_request(
            request,
            artifact.artifact_ref.value,
            output.digest,
            True,
            pass_id,
            attempt=attempt,
            renderer_ref=self.renderer_ref,
            runtime_ref=self.runtime_ref,
            executor_ref=attempt.owner_ref,
            resource_ref=str(resource["resource_ref"]),
            resource_identity_sha256=str(resource["identity_sha256"]),
            device_identity=device_identity,
        )
        self._persist_result(access, request, frame)
        return frame

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
        self.inspect(request)
        self._assert_live_attempt(access, attempt, request)
        if request.frame_start != request.frame_end:
            raise RenderContractError("renderFrame requires one exact frame")
        if pass_id not in request.config.passes:
            raise RenderContractError("render pass is not declared by config")
        scene = self._admit_scene(access, request, scene_artifact_ref)
        resource = self._resource_evidence(
            access, attempt, request, resource_allocation_ref
        )
        if self._is_cancelled(request, attempt):
            raise RenderContractError("render was cancelled before launch")
        recovered = self._replay_result(access, request, pass_id)
        if recovered is not None:
            return recovered
        if getattr(self, "_reference_backend", False):
            return self._render_reference_frame(
                access,
                attempt,
                request,
                scene_artifact_ref,
                scene,
                resource,
                pass_id,
                resource_allocation_ref,
            )
        token = self._result_digest(request, pass_id)[:24]
        stage_name = f".biella-render-{token}"
        scene_name = f"{stage_name}-scene.blend"
        config_name = f"{stage_name}-config.json"
        driver_name = f"{stage_name}-driver.py"
        output_directory = f"{stage_name}-out"
        output_name = f"{stage_name}-{request.frame_start:06d}.png"
        driver = self.objects.put(
            Path(__file__).with_name("_blender_render_driver.py").read_bytes(),
            media_type="text/x-python",
        )
        config = self.objects.put(_json({
            "camera": {
                "materialization": request.camera_materialization,
                "object": request.camera_object,
                "ref": request.camera_ref,
                "settings": dict(request.camera_settings),
                "settings_sha256": request.camera_settings_sha256,
                "transform": list(request.camera_transform),
            },
            "channels": list(request.config.channels),
            "device": {
                "backend": resource["backend"],
                "device_ids": list(cast(Iterable[str], resource["device_ids"])),
            },
            "dimensions": list(request.config.dimensions),
            "frame": request.frame_start,
            "kind": request.config.kind,
            "output_path": f"{output_directory}/{output_name}",
            "pass_id": pass_id,
            "quality": dict(request.config.quality),
        }), media_type="application/json")
        self.filesystem.mkdir(
            access, attempt, root_ref=root_ref,
            path=f"{working_directory}/{output_directory}",
            idempotency_key=f"render-{token}-output-directory",
        )
        workspace = Path(
            self.filesystem.get_root(access, root_ref).canonical_path,
            working_directory,
        ).resolve()
        sandbox_argv = _ThreeDService._sandbox_argv(
            self.identity, workspace,
            ("-b", scene_name, "--python", driver_name, "--", config_name),
            {
                "config": workspace / config_name,
                "driver": workspace / driver_name,
                "scene": workspace / scene_name,
            },
            {"output": workspace / output_directory},
            (),
        )
        process = self.process.execute(
            access,
            attempt,
            ProcessExecutionRequest(
                project_ref=access.project_ref,
                working_root_ref=root_ref,
                working_directory=working_directory,
                executable=self.identity.process_executable_path,
                expected_executable_sha256=self.identity.process_executable_sha256,
                argv=sandbox_argv,
                timeout_seconds=request.config.timeout_seconds,
                resource_allocation_ref=resource_allocation_ref,
                descriptor_content_refs={
                    "config": config,
                    "driver": driver,
                    "scene": getattr(scene, "content_ref"),
                },
                descriptor_directory_paths={"output": output_directory},
            ),
            idempotency_key=f"render-process-{token}",
            cancelled=lambda: self._is_cancelled(request, attempt)
            or not self._attempt_is_current(access, attempt, request),
        )
        if process.status is not ProcessStatus.SUCCEEDED:
            raise RenderContractError(
                f"REAL Blender render process failed: {process.stderr_preview[:512]}"
            )
        self._assert_live_attempt(access, attempt, request)
        if self._is_cancelled(request, attempt):
            raise RenderContractError("cancelled render result was fenced before publication")
        current_resource = self._resource_evidence(
            access, attempt, request, resource_allocation_ref
        )
        if current_resource["identity_sha256"] != resource["identity_sha256"]:
            raise RenderContractError("render Resource identity changed before publication")
        receipt = _driver_receipt(process.stdout_preview)
        if (
            receipt.get("frame") != request.frame_start
            or receipt.get("pass_id") != pass_id
            or receipt.get("camera_object") != request.camera_object
            or receipt.get("output_path") != f"{output_directory}/{output_name}"
        ):
            raise RenderContractError("Blender render receipt identity differs")
        device = receipt.get("device")
        if not isinstance(device, dict) or device.get("backend") != resource["backend"]:
            raise RenderContractError("Blender device receipt differs from allocation policy")
        device_digest = _digest(device)
        if receipt.get("device_digest") != device_digest:
            raise RenderContractError("Blender device receipt digest differs")
        if resource["backend"] != "CPU":
            selected = tuple(
                str(item)
                for item in cast(Iterable[object], device.get("devices", ()))
            )
            if any(
                not any(token in actual for actual in selected)
                for token in cast(Iterable[str], resource["device_ids"])
            ):
                raise RenderContractError("Blender did not use the allocated GPU identity")
        device_identity = (
            f"device://cycles/{str(resource['backend']).lower()}/{device_digest}"
        )
        try:
            output = self.filesystem.read(
                access, attempt, root_ref=root_ref,
                path=f"{working_directory}/{output_directory}/{output_name}",
                media_type=request.config.media_type,
                idempotency_key=f"render-{token}-read",
            ).output_ref
        except FilesystemError as exc:
            raise RenderContractError("required render pass output is missing") from exc
        if output.media_type != request.config.media_type:
            raise RenderContractError("render output container/media type differs from config")
        self.validateOutput(self.objects.read(output), request, pass_id)
        role = (
            "render.preview"
            if request.config.kind == "preview" and pass_id == "beauty"
            else "render.frame"
            if request.config.kind == "final" and pass_id == "beauty"
            else "render.pass"
        )
        artifact = self.artifacts.create_artifact(
            access,
            project_ref=access.project_ref,
            role=role,
            content_ref=output,
            source_refs=(),
            source_artifact_refs=(scene_artifact_ref, process.artifact_ref),
            source_content_refs=(
                getattr(scene, "content_ref"), process.result_ref, config, driver
            ),
            derivation_type="render.blender",
            metadata={
                "media_type": request.config.media_type,
                "media_profile": json.dumps({
                    "camera_settings_sha256": request.camera_settings_sha256,
                    "channels": request.config.channels,
                    "config_sha256": request.config.digest,
                    "device_identity": device_identity,
                    "dimensions": request.config.dimensions,
                    "pass_id": pass_id,
                    "producer_attempt_id": attempt.attempt_id,
                    "producer_fence": attempt.fence,
                    "renderer_ref": self.renderer_ref,
                    "resource_identity_sha256": resource["identity_sha256"],
                    "runtime_ref": self.runtime_ref,
                }, sort_keys=True, separators=(",", ":")),
                "semantic_label": pass_id,
                "semantic_version": request.config.config_version,
            },
        )
        frame = RenderFrameRef.from_request(
            request,
            artifact.artifact_ref.value,
            output.digest,
            True,
            pass_id,
            attempt=attempt,
            renderer_ref=self.renderer_ref,
            runtime_ref=self.runtime_ref,
            executor_ref=attempt.owner_ref,
            resource_ref=str(resource["resource_ref"]),
            resource_identity_sha256=str(resource["identity_sha256"]),
            device_identity=device_identity,
        )
        self._persist_result(access, request, frame)
        return frame

    def render(
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
        return self.renderFrame(
            access, attempt, request, scene_artifact_ref=scene_artifact_ref,
            root_ref=root_ref, working_directory=working_directory,
            idempotency_key=idempotency_key, pass_id=pass_id,
            resource_allocation_ref=resource_allocation_ref,
        )

    def renderPasses(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: RenderRequest,
        *,
        scene_artifact_ref: ArtifactRef,
        root_ref: FilesystemRootRef,
        working_directory: str,
        idempotency_key: str,
        resource_allocation_ref: ResourceAllocationRef | None = None,
    ) -> tuple[RenderFrameRef, ...]:
        if request.frame_start != request.frame_end:
            raise RenderContractError("renderPasses requires one exact frame")
        return tuple(
            self.render(
                access, attempt, request, scene_artifact_ref=scene_artifact_ref,
                root_ref=root_ref, working_directory=working_directory,
                idempotency_key=f"{idempotency_key}-{pass_id}",
                pass_id=pass_id,
                resource_allocation_ref=resource_allocation_ref,
            )
            for pass_id in request.config.passes
        )

    def render_passes(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: RenderRequest,
        **kwargs: object,
    ) -> tuple[RenderFrameRef, ...]:
        return self.renderPasses(access, attempt, request, **kwargs)  # type: ignore[arg-type]

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
        self.inspect(request)
        self._assert_live_attempt(access, coordinator_attempt, request)
        self._admit_scene(access, request, scene_artifact_ref)
        frames = tuple(range(request.frame_start, request.frame_end + 1))
        sequence_digest = self._claim_sequence(
            access, request, frames, idempotency_key
        )
        completed: list[RenderFrameRef] = []
        failed: list[int] = []
        missing: list[tuple[int, str, RenderRequest]] = []
        for frame in frames:
            frame_request = replace(request, frame_start=frame, frame_end=frame)
            for pass_id in request.config.passes:
                replayed = self._replay_frame(
                    access, frame_request, sequence_digest, frame, pass_id
                )
                if replayed is not None:
                    completed.append(replayed)
                else:
                    missing.append((frame, pass_id, frame_request))
        if child_dispatches is not None:
            if set(child_dispatches) != {
                (frame, pass_id) for frame, pass_id, _ in missing
            }:
                raise RenderContractError(
                    "child dispatch keys must equal exact missing frame/pass work"
                )
            dispatches = tuple(child_dispatches.values())
            if any(
                not isinstance(dispatch, ScheduledDispatch)
                or dispatch.allocation.project_ref != access.project_ref
                or dispatch.allocation.status != "DISPATCHED"
                or dispatch.allocation.node_ref != dispatch.node_attempt.node_ref
                or dispatch.allocation.node_attempt_id != dispatch.node_attempt.attempt_id
                or dispatch.allocation.node_attempt_fence != dispatch.node_attempt.fence
                for dispatch in dispatches
            ):
                raise RenderContractError(
                    "child dispatch allocation/attempt evidence is invalid"
                )
            if (
                len({item.allocation.allocation_ref for item in dispatches}) != len(dispatches)
                or len({item.node_attempt.attempt_id for item in dispatches}) != len(dispatches)
                or len({item.node_attempt.node_ref for item in dispatches}) != len(dispatches)
            ):
                raise RenderContractError(
                    "child dispatch allocation, attempt, and node identities must be unique"
                )

        def render_missing(item: tuple[int, str, RenderRequest]) -> RenderFrameRef:
            frame, pass_id, frame_request = item
            dispatch = None if child_dispatches is None else child_dispatches[(frame, pass_id)]
            child_request = frame_request if dispatch is None else replace(
                frame_request,
                task_ref=(
                    f"task://{dispatch.node_attempt.task_ref.project_ref.value}/"
                    f"{dispatch.node_attempt.task_ref.task_id}/"
                    f"{dispatch.node_attempt.task_ref.revision}"
                ),
                run_ref=(
                    f"run://{dispatch.node_attempt.run_ref.project_ref.value}/"
                    f"{dispatch.node_attempt.run_ref.run_id}"
                ),
                node_ref=dispatch.node_attempt.node_ref.value,
                executor_ref=dispatch.node_attempt.owner_ref,
            )
            rendered = self.render(
                access,
                coordinator_attempt if dispatch is None else dispatch.node_attempt,
                child_request,
                scene_artifact_ref=scene_artifact_ref,
                root_ref=root_ref,
                working_directory=working_directory,
                idempotency_key=f"{idempotency_key}-{frame}-{pass_id}",
                pass_id=pass_id,
                resource_allocation_ref=(
                    None if dispatch is None else dispatch.allocation.allocation_ref
                ),
            )
            self._persist_frame(access, sequence_digest, rendered)
            return rendered

        max_parallel = (
            1
            if child_dispatches is None
            else min(request.config.max_parallel, max(1, len(missing)))
        )
        if max_parallel > 1 and len(missing) > 1:
            with ThreadPoolExecutor(
                max_workers=max_parallel, thread_name_prefix="biella-render"
            ) as executor:
                futures = tuple(
                    (item[0], executor.submit(render_missing, item))
                    for item in missing
                )
                for frame, future in futures:
                    try:
                        completed.append(future.result())
                    except RenderContractError:
                        failed.append(frame)
        else:
            for item in missing:
                try:
                    completed.append(render_missing(item))
                except RenderContractError:
                    failed.append(item[0])
        failed_set = set(failed)
        completed = sorted(
            (item for item in completed if item.frame not in failed_set),
            key=lambda item: (item.frame, item.pass_id),
        )
        return RenderSequenceManifest(
            access.project_ref, request, frames, tuple(completed),
            tuple(sorted(failed_set)), "0" * 64,
        )

    def render_sequence(
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
        return self.renderSequence(
            access, coordinator_attempt, request,
            scene_artifact_ref=scene_artifact_ref, root_ref=root_ref,
            working_directory=working_directory, idempotency_key=idempotency_key,
            child_dispatches=child_dispatches,
        )



def _reference_png(width: int, height: int, channels: str, seed: bytes) -> bytes:
    """Produce a deterministic, fully decodable PNG for the reference backend."""
    import binascii

    channel_count = 4 if channels == "RGBA" else 3
    color_type = 6 if channel_count == 4 else 2
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)
        for x in range(width):
            block = hashlib.sha256(seed + x.to_bytes(4, "big") + y.to_bytes(4, "big")).digest()
            pixels.extend(block[:channel_count])

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(pixels))) + chunk(b"IEND", b"")



class ReferenceRendererAdapter(RendererAdapter):
    """Deterministic backend using the exact canonical renderer lifecycle."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        identity: ThreeDToolIdentity,
    ) -> None:
        super().__init__(database_path, object_store, identity=identity)
        runtime_digest = hashlib.sha256(
            f"{self.project_ref.value}:reference-renderer:1".encode("utf-8")
        ).hexdigest()
        self._reference_backend = True
        self.renderer_ref = "renderer://reference/v1"
        self.runtime_ref = f"runtime://reference/{runtime_digest}"
        self.executor_ref = "executor://reference/local/v1"

    def describeRuntime(self) -> Mapping[str, object]:
        return MappingProxyType({
            "adapter_ref": "adapter://renderer/reference/v1",
            "device_backends": ("CPU",),
            "executor_ref": self.executor_ref,
            "executable_sha256": None,
            "identity_sha256": hashlib.sha256(
                f"{self.renderer_ref}:{self.runtime_ref}".encode("utf-8")
            ).hexdigest(),
            "media_types": ("image/png",),
            "project_ref": self.project_ref.value,
            "real": False,
            "renderer_ref": self.renderer_ref,
            "runtime_ref": self.runtime_ref,
            "supported_passes": ("beauty", "normal", "z"),
            "tool_name": "biella-reference-renderer",
            "tool_version": "1.0.0",
        })
