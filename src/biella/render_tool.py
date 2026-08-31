"""Project-scoped REAL Blender raster rendering on the generic process substrate."""
from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
from threading import Barrier, BrokenBarrierError
import zlib

from .artifact import ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .filesystem import FilesystemAdapter, FilesystemError, FilesystemRootRef
from .object_store import ObjectStorageBackend, ObjectStorageError
from .process import ManagedProcessAdapter, ProcessExecutionRequest, ProcessStatus
from .project import ProjectAccess, ProjectRef
from .execution import NodeExecutionAttempt
from .render_pack import RenderConfig, RenderContractError, RenderFrameRef, RenderRequest, RenderSequenceManifest
from .scheduler import ResourceAllocationRef, ScheduledDispatch
from .three_d_tool import ThreeDToolIdentity, _ThreeDService


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _request_identity(request: RenderRequest) -> dict[str, object]:
    return {
        "task_ref": request.task_ref, "run_ref": request.run_ref, "node_ref": request.node_ref,
        "dependencies": list(request.dependencies),
        "camera_ref": request.camera_ref, "camera_settings_sha256": request.camera_settings_sha256,
        "camera_transform": list(request.camera_transform), "capability_id": request.capability_id,
        "config_digest": request.config.digest, "config_ref": request.config.config_ref,
        "dimensions": list(request.config.dimensions), "kind": request.config.kind, "channels": list(request.config.channels),
        "passes": list(request.config.passes), "quality": dict(request.config.quality), "resource": dict(request.config.resource),
        "egress": dict(request.config.egress), "timeout_seconds": request.config.timeout_seconds,
        "executor_ref": request.executor_ref, "renderer_ref": request.renderer_ref,
        "runtime_ref": request.runtime_ref, "scene_content_sha256": request.scene_content_sha256,
        "scene_ref": request.scene_ref, "time_seconds": request.time_seconds,
    }


def _png_dimensions(payload: bytes) -> tuple[int, int, int]:
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RenderContractError("rendered frame is not PNG")
    offset = 8
    width = height = channels = 0
    compressed = bytearray()
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise RenderContractError("PNG is truncated")
        size = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(payload) or zlib.crc32(kind + payload[offset + 8:offset + 8 + size]) & 0xffffffff != struct.unpack(">I", payload[offset + 8 + size:end])[0]:
            raise RenderContractError("PNG chunk integrity failed")
        data = payload[offset + 8:offset + 8 + size]
        if kind == b"IHDR":
            if size != 13:
                raise RenderContractError("PNG IHDR is malformed")
            width, height, depth, colour, _, _, _ = struct.unpack(">IIBBBBB", data)
            channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(colour, 0)
            if not width or not height or depth != 8 or not channels:
                raise RenderContractError("PNG dimensions or channels are unsupported")
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            break
        offset = end
    if not width or not compressed:
        raise RenderContractError("PNG lacks image data")
    try:
        decoded = zlib.decompress(compressed)
    except zlib.error as exc:
        raise RenderContractError("PNG pixels are corrupt") from exc
    if len(decoded) != height * (1 + width * channels):
        raise RenderContractError("PNG decoded size is inconsistent")
    return width, height, channels


class RendererAdapter:
    def __init__(self, database_path: str | Path, object_store: ObjectStorageBackend, *, identity: ThreeDToolIdentity) -> None:
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
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS render_sequence_frames ("
                "project_id TEXT NOT NULL, sequence_digest TEXT NOT NULL, frame INTEGER NOT NULL, "
                "pass_id TEXT NOT NULL, artifact_id TEXT NOT NULL, artifact_revision INTEGER NOT NULL, "
                "content_sha256 TEXT NOT NULL, PRIMARY KEY (project_id, sequence_digest, frame, pass_id))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS render_frame_results ("
                "project_id TEXT NOT NULL, result_digest TEXT NOT NULL, artifact_id TEXT NOT NULL, "
                "artifact_revision INTEGER NOT NULL, content_sha256 TEXT NOT NULL, "
                "PRIMARY KEY (project_id, result_digest))"
            )
            connection.commit()
        finally:
            connection.close()

    def _sequence_digest(self, request: RenderRequest, frames: tuple[int, ...]) -> str:
        return _digest({"request": _request_identity(request), "frames": frames})

    def _result_digest(self, request: RenderRequest, pass_id: str) -> str:
        return _digest({"request": _request_identity(request), "frame": request.frame_start, "pass": pass_id})

    @staticmethod
    def _artifact_identity(value: str) -> tuple[str, int]:
        parts = value.rsplit("/", 2)
        if len(parts) != 3 or not parts[0].startswith("artifact://"):
            raise RenderContractError("frame artifact identity is malformed")
        try:
            return parts[1], int(parts[2])
        except ValueError as exc:
            raise RenderContractError("frame artifact identity is malformed") from exc

    def _replay_result(self, access: ProjectAccess, request: RenderRequest, pass_id: str) -> RenderFrameRef | None:
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            row = connection.execute(
                "SELECT artifact_id, artifact_revision, content_sha256 FROM render_frame_results "
                "WHERE project_id = ? AND result_digest = ?",
                (access.project_ref.value, self._result_digest(request, pass_id)),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        artifact_ref = ArtifactRef(access.project_ref, str(row[0]), int(row[1]))
        artifact = self.artifacts.get_artifact(access, artifact_ref)
        if artifact.content_ref is None or artifact.content_ref.digest != str(row[2]):
            raise RenderContractError("durable render result artifact is forged or stale")
        width, height, channels = _png_dimensions(self.objects.read(artifact.content_ref))
        if (width, height) != request.config.dimensions or channels < 3:
            raise RenderContractError("durable render result PNG is missing or corrupt")
        return RenderFrameRef.from_request(request, artifact_ref.value, artifact.content_ref.digest, True, pass_id)

    def _persist_result(self, access: ProjectAccess, request: RenderRequest, frame: RenderFrameRef) -> None:
        artifact_id, revision = self._artifact_identity(frame.artifact_ref)
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            connection.execute(
                "INSERT OR IGNORE INTO render_frame_results "
                "(project_id, result_digest, artifact_id, artifact_revision, content_sha256) VALUES (?, ?, ?, ?, ?)",
                (access.project_ref.value, self._result_digest(request, frame.pass_id), artifact_id, revision, frame.content_sha256),
            )
            connection.commit()
        finally:
            connection.close()

    def _replay_frame(self, access: ProjectAccess, request: RenderRequest, sequence_digest: str, frame: int, pass_id: str) -> RenderFrameRef | None:
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            row = connection.execute(
                "SELECT pass_id, artifact_id, artifact_revision, content_sha256 FROM render_sequence_frames "
                "WHERE project_id = ? AND sequence_digest = ? AND frame = ? AND pass_id = ?",
                (access.project_ref.value, sequence_digest, frame, pass_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        artifact_ref = ArtifactRef(access.project_ref, str(row[1]), int(row[2]))
        artifact = self.artifacts.get_artifact(access, artifact_ref)
        if artifact.content_ref is None or artifact.content_ref.digest != str(row[3]):
            raise RenderContractError("durable frame artifact content is forged or stale")
        width, height, channels = _png_dimensions(self.objects.read(artifact.content_ref))
        if (width, height) != request.config.dimensions or channels < 3:
            raise RenderContractError("durable frame PNG is missing or corrupt")
        return RenderFrameRef.from_request(request, artifact_ref.value, artifact.content_ref.digest, True, str(row[0]))

    def _persist_frame(self, access: ProjectAccess, sequence_digest: str, frame: RenderFrameRef) -> None:
        artifact_id, revision = self._artifact_identity(frame.artifact_ref)
        connection = sqlite3.connect(self.database, timeout=30.0)
        try:
            connection.execute(
                "INSERT OR IGNORE INTO render_sequence_frames "
                "(project_id, sequence_digest, frame, pass_id, artifact_id, artifact_revision, content_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (access.project_ref.value, sequence_digest, frame.frame, frame.pass_id, artifact_id, revision, frame.content_sha256),
            )
            connection.commit()
        finally:
            connection.close()

    def render(
        self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: RenderRequest, *, scene_artifact_ref: ArtifactRef,
        root_ref: FilesystemRootRef, working_directory: str, idempotency_key: str, pass_id: str = "beauty",
        resource_allocation_ref: ResourceAllocationRef | None = None,
    ) -> RenderFrameRef:
        if request.project_ref != access.project_ref or scene_artifact_ref.project_ref != access.project_ref:
            raise RenderContractError("render scene crossed Project scope")
        if request.frame_start != request.frame_end:
            raise RenderContractError("render() requires one exact frame")
        scene = self.artifacts.get_artifact(access, scene_artifact_ref)
        if scene.content_ref is None or scene.content_ref.digest != request.scene_content_sha256:
            raise RenderContractError("render scene artifact/content identity changed")
        if request.config.kind not in {"preview", "final"}:
            raise RenderContractError("render kind is malformed")
        if pass_id not in request.config.passes:
            raise RenderContractError("render pass is not declared by config")
        if resource_allocation_ref is not None and resource_allocation_ref.project_ref != access.project_ref:
            raise RenderContractError("render resource allocation crossed Project scope")
        recovered = self._replay_result(access, request, pass_id)
        if recovered is not None:
            return recovered
        token = _digest({"request": _request_identity(request), "frame": request.frame_start, "pass": pass_id})[:24]
        stage_name = f".biella-render-{token}"
        scene_name = f"{stage_name}-scene.blend"
        config_name = f"{stage_name}-config.json"
        driver_name = f"{stage_name}-driver.py"
        output_directory = f"{stage_name}-out"
        output_name = f"{stage_name}-{request.frame_start:06d}.png"
        driver = self.objects.put(Path(__file__).with_name("_blender_render_driver.py").read_bytes(), media_type="text/x-python")
        config = self.objects.put(_json({"camera_transform": list(request.camera_transform), "dimensions": list(request.config.dimensions), "frame": request.frame_start, "output_path": f"{output_directory}/{output_name}", "pass_id": pass_id, "kind": request.config.kind, "quality": dict(request.config.quality)}), media_type="application/json")
        self.filesystem.mkdir(access, attempt, root_ref=root_ref, path=f"{working_directory}/{output_directory}", idempotency_key=f"render-{token}-output-directory")
        workspace = Path(self.filesystem.get_root(access, root_ref).canonical_path, working_directory).resolve()
        sandbox_argv = _ThreeDService._sandbox_argv(
            self.identity, workspace, ("-b", scene_name, "--python", driver_name, "--", config_name),
            {"config": workspace / config_name, "driver": workspace / driver_name, "scene": workspace / scene_name},
            {"output": workspace / output_directory}, (),
        )
        process = self.process.execute(access, attempt, ProcessExecutionRequest(
            project_ref=access.project_ref, working_root_ref=root_ref, working_directory=working_directory,
            executable=self.identity.process_executable_path, expected_executable_sha256=self.identity.process_executable_sha256,
            argv=sandbox_argv, timeout_seconds=request.config.timeout_seconds,
            resource_allocation_ref=resource_allocation_ref,
            descriptor_content_refs={"config": config, "driver": driver, "scene": scene.content_ref},
            descriptor_directory_paths={"output": output_directory},
        ), idempotency_key=f"render-process-{token}")
        if process.status is not ProcessStatus.SUCCEEDED:
            raise RenderContractError(f"REAL Blender render process failed: {process.stderr_preview[:512]}")
        try:
            png = self.filesystem.read(access, attempt, root_ref=root_ref, path=f"{working_directory}/{output_directory}/{output_name}", media_type="image/png", idempotency_key=f"render-{token}-read").output_ref
        except FilesystemError as exc:
            raise RenderContractError("required render pass output is missing") from exc
        raw = self.objects.read(png)
        width, height, channels = _png_dimensions(raw)
        if (width, height) != request.config.dimensions or channels < 3:
            raise RenderContractError("rendered PNG dimensions/channels differ from config")
        artifact = self.artifacts.create_artifact(access, project_ref=access.project_ref, role=("render.preview" if request.config.kind == "preview" and pass_id == "beauty" else "render.pass"), content_ref=png, source_refs=(), source_artifact_refs=(scene_artifact_ref, process.artifact_ref), source_content_refs=(scene.content_ref, process.result_ref), derivation_type="render.blender", metadata={"media_type": "image/png"})
        frame = RenderFrameRef.from_request(request, artifact.artifact_ref.value, png.digest, True, pass_id)
        self._persist_result(access, request, frame)
        return frame

    def render_sequence(self, access: ProjectAccess, coordinator_attempt: NodeExecutionAttempt, request: RenderRequest, *, scene_artifact_ref: ArtifactRef, root_ref: FilesystemRootRef, working_directory: str, idempotency_key: str, child_dispatches: Mapping[tuple[int, str], ScheduledDispatch] | None = None) -> RenderSequenceManifest:
        frames = tuple(range(request.frame_start, request.frame_end + 1))
        sequence_digest = self._sequence_digest(request, frames)
        completed: list[RenderFrameRef] = []
        failed: list[int] = []
        missing: list[tuple[int, str, RenderRequest]] = []
        for frame in frames:
            frame_request = replace(request, frame_start=frame, frame_end=frame)
            for pass_id in request.config.passes:
                replayed = self._replay_frame(access, frame_request, sequence_digest, frame, pass_id)
                if replayed is not None:
                    completed.append(replayed)
                    continue
                missing.append((frame, pass_id, frame_request))
        if child_dispatches is not None:
            if set(child_dispatches) != {(frame, pass_id) for frame, pass_id, _ in missing}:
                raise RenderContractError("child dispatch keys must equal exact missing frame/pass work")
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
                raise RenderContractError("child dispatch allocation/attempt evidence is invalid")
            if len({dispatch.allocation.allocation_ref for dispatch in dispatches}) != len(dispatches) or len({dispatch.node_attempt.attempt_id for dispatch in dispatches}) != len(dispatches) or len({dispatch.node_attempt.node_ref for dispatch in dispatches}) != len(dispatches):
                raise RenderContractError("child dispatch allocation, attempt, and node identities must be unique")
        launch_barrier = Barrier(len(missing)) if child_dispatches is not None and len(missing) > 1 else None
        def render_missing(item: tuple[int, str, RenderRequest]) -> RenderFrameRef:
            frame, pass_id, frame_request = item
            if launch_barrier is not None:
                try:
                    launch_barrier.wait(timeout=5.0)
                except BrokenBarrierError as exc:
                    raise RenderContractError("parallel child launch barrier failed") from exc
            dispatch = None if child_dispatches is None else child_dispatches[(frame, pass_id)]
            child_request = frame_request if dispatch is None else replace(frame_request, task_ref=f"task://{dispatch.node_attempt.task_ref.project_ref.value}/{dispatch.node_attempt.task_ref.task_id}/{dispatch.node_attempt.task_ref.revision}", run_ref=f"run://{dispatch.node_attempt.run_ref.project_ref.value}/{dispatch.node_attempt.run_ref.run_id}", node_ref=dispatch.node_attempt.node_ref.value, executor_ref=dispatch.node_attempt.owner_ref)
            rendered = self.render(access, coordinator_attempt if dispatch is None else dispatch.node_attempt, child_request, scene_artifact_ref=scene_artifact_ref, root_ref=root_ref, working_directory=working_directory, idempotency_key=f"{idempotency_key}-{frame}-{pass_id}", pass_id=pass_id, resource_allocation_ref=(None if dispatch is None else dispatch.allocation.allocation_ref))
            self._persist_frame(access, sequence_digest, rendered)
            return rendered
        if child_dispatches is not None and len(missing) > 1:
            with ThreadPoolExecutor(max_workers=len(missing), thread_name_prefix="biella-render") as executor:
                futures = tuple((item[0], executor.submit(render_missing, item)) for item in missing)
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
        completed = [item for item in completed if item.frame not in failed_set]
        return RenderSequenceManifest(access.project_ref, request, frames, tuple(completed), tuple(failed), _digest({"request": _request_identity(request), "frames": [(item.frame, item.pass_id, item.content_sha256) for item in completed], "failed": failed}))


class ReferenceRendererAdapter:
    """Honest reference implementation: it never claims a verified real frame."""
    def render(self, request: RenderRequest) -> RenderFrameRef:
        raise RenderContractError("REFERENCE renderer cannot claim REAL verified render evidence")
