"""REAL Blender-backed deterministic VFX simulation on existing authorities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Callable, Mapping

from .artifact import ArtifactRef, ArtifactService, ContentRef
from .execution import NodeExecutionAttempt
from .filesystem import FilesystemAdapter, FilesystemConflictError, FilesystemError, FilesystemRootRef
from .game_engine import GameAssetInput, GameRuntimeInputBinding
from .object_store import ObjectStorageBackend
from .process import ManagedProcessAdapter, ProcessExecutionRequest, ProcessResourcePolicy, ProcessStatus
from .project import ProjectAccess, ProjectRef
from .render_pack import RenderFrameRef, RenderRequest
from .render_tool import RendererAdapter
from .scheduler import ResourceAllocation, ScheduledDispatch, Scheduler
from .three_d_tool import ThreeDToolIdentity, _ThreeDService
from .vfx_pack import SimulationBakeRef, SimulationCheckpointRef, SimulationContractError, SimulationSpecification
from .vfx_recovery import SimulationResourceRecoveryPlan, plan_verified_resource_exhaustion_recovery


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


class BlenderSimulationAdapter:
    """Bound REAL adapter; scheduling is supplied by upstream authorities."""

    def __init__(self, database_path: str | Path, object_store: ObjectStorageBackend, *, identity: ThreeDToolIdentity, access: ProjectAccess, scene_artifact_ref: ArtifactRef, root_ref: FilesystemRootRef, working_directory: str, segment_dispatches: Mapping[int, ScheduledDispatch], before_segment_process: Callable[[int], None] | None = None, cancelled: Callable[[], bool] | None = None) -> None:
        if access.project_ref != identity.project_ref or scene_artifact_ref.project_ref != access.project_ref or root_ref.project_ref != access.project_ref:
            raise SimulationContractError("bound simulation authority crossed Project scope")
        self.database, self.objects, self.identity, self.access = Path(database_path), object_store, identity, access
        self.scene_artifact_ref, self.root_ref, self.working_directory = scene_artifact_ref, root_ref, working_directory
        self.working_cache_path = f"{working_directory}/.minitz-simulation-cache"
        self._cache_initialized = False
        self.segment_dispatches = dict(segment_dispatches)
        self.before_segment_process, self.cancelled = before_segment_process, cancelled
        self.project_ref, self.tool_ref, self.runtime_ref = access.project_ref, "tool://blender", identity.runtime_ref
        self.artifacts, self.filesystem, self.process = ArtifactService(self.database), FilesystemAdapter(self.database, object_store), ManagedProcessAdapter(self.database, object_store)
        self.checkpoints: tuple[SimulationCheckpointRef, ...] = ()
        self.bake_artifact_ref: ArtifactRef | None = None
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS simulation_checkpoint_index (project_id TEXT NOT NULL, specification_digest TEXT NOT NULL, frame INTEGER NOT NULL, artifact_id TEXT NOT NULL, artifact_revision INTEGER NOT NULL, content_sha256 TEXT NOT NULL, predecessor_artifact_id TEXT NOT NULL, predecessor_artifact_revision INTEGER NOT NULL, predecessor_content_sha256 TEXT NOT NULL, producer_attempt_id TEXT NOT NULL, producer_fence INTEGER NOT NULL, PRIMARY KEY (project_id, specification_digest, frame))")
            connection.commit()
        finally:
            connection.close()

    def _artifact_ref(self, value: str) -> ArtifactRef:
        parts = value.rsplit("/", 2)
        if len(parts) != 3 or parts[0] != f"artifact://{self.project_ref.value}":
            raise SimulationContractError("simulation ArtifactRef is invalid or foreign")
        try:
            return ArtifactRef(self.project_ref, parts[1], int(parts[2]))
        except ValueError as exc:
            raise SimulationContractError("simulation ArtifactRef is invalid") from exc

    def _resolve(self, value: str, digest: str, label: str) -> tuple[ArtifactRef, ContentRef]:
        artifact_ref = self._artifact_ref(value)
        artifact = self.artifacts.get_artifact(self.access, artifact_ref)
        if artifact.content_ref is None or artifact.content_ref.digest != digest or not self.objects.read(artifact.content_ref):
            raise SimulationContractError(f"{label} Artifact/Content identity is stale, missing, or forged")
        return artifact_ref, artifact.content_ref

    def _allocation(self, dispatch: ScheduledDispatch) -> ResourceAllocation:
        allocation = Scheduler(self.database).get_allocation(self.access, dispatch.allocation.allocation_ref)
        attempt = dispatch.node_attempt
        if allocation.status != "DISPATCHED" or allocation.project_ref != self.project_ref or allocation.node_ref != attempt.node_ref or allocation.run_ref != attempt.run_ref or allocation.node_attempt_id != attempt.attempt_id or allocation.node_attempt_fence != attempt.fence:
            raise SimulationContractError("segment dispatch is stale or forged")
        return allocation

    def _publish(self, attempt: NodeExecutionAttempt, *, role: str, content: ContentRef, sources: tuple[ArtifactRef, ...], source_contents: tuple[ContentRef, ...], derivation: str, metadata: Mapping[str, str]) -> ArtifactRef:
        matches = [item for item in self.artifacts.runs.list_attempts(self.access, attempt.run_ref) if item.attempt_id == attempt.run_attempt_id and item.fence == attempt.run_fence]
        if len(matches) != 1:
            raise SimulationContractError("simulation producer Run authority is stale")
        artifact = self.artifacts.publish_from_run(self.access, producer_attempt=matches[0], expected_task_ref=attempt.task_ref, expected_task_digest=attempt.task_digest, role=role, content_ref=content, source_refs=(), source_artifact_refs=sources, source_content_refs=source_contents, derivation_type=derivation, metadata=dict(metadata))
        return artifact.artifact_ref

    @staticmethod
    def _policy(resources: Mapping[str, str]) -> ProcessResourcePolicy:
        values: dict[str, int] = {}
        for name in ("cpu_seconds", "memory_bytes", "file_size_bytes", "process_count"):
            raw = resources.get(name)
            if raw is not None:
                try:
                    values[name] = int(raw)
                except ValueError as exc:
                    raise SimulationContractError(f"resource {name} is invalid") from exc
        return ProcessResourcePolicy(**values)

    @staticmethod
    def _vector(config: Mapping[str, str], name: str, default: tuple[float, float, float]) -> list[float]:
        raw = config.get(name)
        if raw is None:
            return list(default)
        try:
            value = json.loads(raw)
            vector = [float(item) for item in value]
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SimulationContractError(f"{name} is invalid") from exc
        if len(vector) != 3:
            raise SimulationContractError(f"{name} is invalid")
        return vector

    def _persist_checkpoint(self, specification: SimulationSpecification, checkpoint: SimulationCheckpointRef) -> None:
        artifact = self._artifact_ref(checkpoint.artifact_ref)
        predecessor = self._artifact_ref(checkpoint.predecessor_artifact_ref)
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("INSERT OR IGNORE INTO simulation_checkpoint_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (self.project_ref.value, specification.canonical_digest, checkpoint.frame, artifact.artifact_id, artifact.revision, checkpoint.content_sha256, predecessor.artifact_id, predecessor.revision, checkpoint.predecessor_content_sha256, checkpoint.producer_attempt_id, checkpoint.producer_fence))
            connection.commit()
        finally:
            connection.close()

    def _existing_checkpoint(self, specification: SimulationSpecification, frame: int) -> SimulationCheckpointRef | None:
        connection = sqlite3.connect(self.database)
        try:
            row = connection.execute("SELECT artifact_id, artifact_revision, content_sha256, predecessor_artifact_id, predecessor_artifact_revision, predecessor_content_sha256, producer_attempt_id, producer_fence FROM simulation_checkpoint_index WHERE project_id=? AND specification_digest=? AND frame=?", (self.project_ref.value, specification.canonical_digest, frame)).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        ref = ArtifactRef(self.project_ref, str(row[0]), int(row[1]))
        predecessor = ArtifactRef(self.project_ref, str(row[3]), int(row[4]))
        artifact = self.artifacts.get_artifact(self.access, ref)
        if artifact.content_ref is None or artifact.content_ref.digest != str(row[2]) or not self.objects.read(artifact.content_ref):
            raise SimulationContractError("persisted checkpoint Artifact is corrupt or unavailable")
        self.artifacts.get_artifact(self.access, predecessor)
        return SimulationCheckpointRef.create(self.project_ref, specification, frame, specification.time_start + (frame - specification.frame_start) * specification.timestep, ref.value, artifact.content_ref.digest, predecessor.value, str(row[5]), str(row[6]), int(row[7]), "reopened")

    def _driver_config(self, specification: SimulationSpecification, frame: int, output_path: str, predecessor_state: list[dict[str, object]] | None) -> dict[str, object]:
        particle_count = int(specification.config.get("particle_count", "8"))
        if specification.simulation_type not in {"particles", "procedural"} or not 1 <= particle_count <= 256:
            raise SimulationContractError("REAL Blender simulation type or particle_count is unsupported")
        return {"simulation_type": specification.simulation_type, "segment": frame, "frame_start": frame, "frame_end": frame, "timestep": specification.timestep, "substeps": specification.substeps, "seed": specification.seed, "generator_ref": specification.generator_ref, "solver_ref": specification.solver_ref, "runtime_ref": specification.runtime_ref, "particle_count": particle_count, "gravity": self._vector(specification.config, "gravity", (0.0, 0.0, -9.81)), "initial_velocity": self._vector(specification.config, "initial_velocity", (0.0, 0.0, 1.0)), "floor_height": float(specification.config.get("floor_height", "0")), "restitution": float(specification.config.get("restitution", "0.5")), "predecessor_state": predecessor_state, "requires_predecessor_state": frame > specification.frame_start, "material_parameters": dict(specification.material_parameters), "output_path": output_path}

    def simulate(self, specification: SimulationSpecification, checkpoint: SimulationCheckpointRef | None = None) -> SimulationBakeRef:
        if specification.project_ref != self.project_ref or specification.tool_ref != self.tool_ref or specification.tool_version != self.identity.tool_version or specification.runtime_ref != self.runtime_ref:
            raise SimulationContractError("simulation specification is incompatible with bound REAL adapter")
        scene_ref, scene_content = self._resolve(specification.scene_ref, specification.scene_sha256, "scene")
        if scene_ref != self.scene_artifact_ref:
            raise SimulationContractError("simulation scene differs from bound scene Artifact")
        self._resolve(specification.geometry_ref, specification.geometry_sha256, "geometry")
        self._resolve(specification.animation_ref, specification.animation_sha256, "animation")
        start, current_ref, current_content = specification.frame_start, scene_ref, scene_content
        all_checkpoints: dict[int, SimulationCheckpointRef] = {}
        if checkpoint is not None:
            if checkpoint.specification != specification:
                raise SimulationContractError("checkpoint is incompatible with simulation")
            for prior in range(specification.frame_start, checkpoint.frame + 1):
                restored = self._existing_checkpoint(specification, prior)
                if restored is None:
                    raise SimulationContractError("checkpoint chain is incomplete")
                all_checkpoints[prior] = restored
            current = all_checkpoints[checkpoint.frame]
            current_ref, current_content = self._resolve(current.artifact_ref, current.content_sha256, "checkpoint")
            start = checkpoint.frame + 1
        segments = tuple(range(start, specification.frame_end + 1))
        if set(segments) != set(self.segment_dispatches):
            raise SimulationContractError("exact dispatched segment authorities are required")
        completed: list[SimulationCheckpointRef] = []
        previous_state: list[dict[str, object]] | None = None
        for frame in segments:
            existing = self._existing_checkpoint(specification, frame)
            if existing is not None:
                current_ref, current_content = self._resolve(existing.artifact_ref, existing.content_sha256, "checkpoint")
                all_checkpoints[frame] = existing
                completed.append(existing)
                continue
            dispatch, allocation = self.segment_dispatches[frame], self._allocation(self.segment_dispatches[frame])
            attempt = dispatch.node_attempt
            token = _digest({"specification": specification.canonical_digest, "frame": frame})[:24]
            stage, output_dir, output_name = f".minitz-simulation-{token}", f".minitz-simulation-{token}-out", f".minitz-simulation-{token}.blend"
            config_payload = self._driver_config(specification, frame, f"{output_dir}/{output_name}", previous_state)
            driver = self.objects.put(Path(__file__).with_name("_blender_simulation_driver.py").read_bytes(), media_type="text/x-python")
            config = self.objects.put(_bytes(config_payload), media_type="application/json")
            if not self._cache_initialized:
                try:
                    self.filesystem.mkdir(self.access, attempt, root_ref=self.root_ref, path=self.working_cache_path, idempotency_key=f"simulation-{token}-cache")
                except FilesystemConflictError:
                    pass
                self._cache_initialized = True
            self.filesystem.mkdir(self.access, attempt, root_ref=self.root_ref, path=f"{self.working_directory}/{output_dir}", idempotency_key=f"simulation-{token}-directory")
            workspace = Path(self.filesystem.get_root(self.access, self.root_ref).canonical_path, self.working_directory).resolve()
            argv = _ThreeDService._sandbox_argv(self.identity, workspace, ("-b", f"{stage}-scene.blend", "--python", f"{stage}-driver.py", "--", f"{stage}-config.json"), {"scene": workspace / f"{stage}-scene.blend", "driver": workspace / f"{stage}-driver.py", "config": workspace / f"{stage}-config.json"}, {"output": workspace / output_dir}, ())
            if self.before_segment_process is not None:
                self.before_segment_process(frame)
            process = self.process.execute(self.access, attempt, ProcessExecutionRequest(project_ref=self.project_ref, working_root_ref=self.root_ref, working_directory=self.working_directory, executable=self.identity.process_executable_path, expected_executable_sha256=self.identity.process_executable_sha256, argv=argv, timeout_seconds=float(specification.resources.get("timeout_seconds", "90")), resource_policy=self._policy(specification.resources), resource_allocation_ref=allocation.allocation_ref, descriptor_content_refs={"scene": current_content, "driver": driver, "config": config}, descriptor_directory_paths={"output": output_dir}), idempotency_key=f"simulation-{token}-resume-{start}", cancelled=self.cancelled)
            if process.status is not ProcessStatus.SUCCEEDED:
                raise SimulationContractError("REAL Blender simulation segment failed")
            self._allocation(dispatch)
            try:
                output = self.filesystem.read(self.access, attempt, root_ref=self.root_ref, path=f"{self.working_directory}/{output_dir}/{output_name}", media_type="application/x-blender", idempotency_key=f"simulation-{token}-read").output_ref
                metadata = self.filesystem.read(self.access, attempt, root_ref=self.root_ref, path=f"{self.working_directory}/{output_dir}/{output_name}.json", media_type="application/json", idempotency_key=f"simulation-{token}-metadata").output_ref
                applied = json.loads(self.objects.read(metadata))
            except (FilesystemError, json.JSONDecodeError) as exc:
                raise SimulationContractError("simulation segment output or metadata is missing") from exc
            if not isinstance(applied, dict) or applied.get("segment") != frame or applied.get("solver_ref") != specification.solver_ref or applied.get("runtime_ref") != specification.runtime_ref:
                raise SimulationContractError("simulation segment metadata is corrupt or incompatible")
            cache_ref = self._publish(attempt, role="vfx.cache", content=config, sources=(current_ref, process.artifact_ref), source_contents=(current_content, process.result_ref), derivation="vfx.blender.cache", metadata={"media_type": "application/json"})
            artifact_ref = self._publish(attempt, role="vfx.checkpoint", content=output, sources=(current_ref, process.artifact_ref, cache_ref), source_contents=(current_content, process.result_ref, metadata), derivation="vfx.blender.segment", metadata={"media_type": "application/x-blender"})
            checkpoint_ref = SimulationCheckpointRef.create(self.project_ref, specification, frame, specification.time_start + (frame - specification.frame_start) * specification.timestep, artifact_ref.value, output.digest, current_ref.value, current_content.digest, attempt.attempt_id, attempt.fence, "verified")
            self._persist_checkpoint(specification, checkpoint_ref)
            all_checkpoints[frame] = checkpoint_ref
            completed.append(checkpoint_ref)
            self.checkpoints = tuple((*self.checkpoints, checkpoint_ref))
            current_ref, current_content = artifact_ref, output
            previous_state = applied.get("state") if isinstance(applied.get("state"), list) else None
        chain = tuple(all_checkpoints[frame] for frame in range(specification.frame_start, specification.frame_end + 1))
        if not chain or not completed:
            raise SimulationContractError("simulation has no completed segments")
        final_attempt = self.segment_dispatches[chain[-1].frame].node_attempt
        final_allocation = self._allocation(self.segment_dispatches[chain[-1].frame])
        _ = final_allocation
        bake_ref = self._publish(final_attempt, role="vfx.bake", content=current_content, sources=(current_ref,), source_contents=(current_content,), derivation="vfx.blender.bake", metadata={"media_type": "application/x-blender"})
        manifest_payload = {"specification_digest": specification.canonical_digest, "bake_artifact_ref": bake_ref.value, "bake_content_sha256": current_content.digest, "checkpoints": [{"frame": item.frame, "artifact_ref": item.artifact_ref, "content_sha256": item.content_sha256, "checkpoint_digest": item.checkpoint_digest} for item in chain]}
        manifest_content = self.objects.put(_bytes(manifest_payload), media_type="application/json")
        manifest_ref = self._publish(final_attempt, role="vfx.validation", content=manifest_content, sources=(bake_ref, current_ref), source_contents=(current_content,), derivation="vfx.blender.bake-manifest", metadata={"media_type": "application/json"})
        reopened = json.loads(self.objects.read(manifest_content))
        if not isinstance(reopened, dict) or reopened.get("bake_content_sha256") != current_content.digest or len(reopened.get("checkpoints", ())) != len(chain):
            raise SimulationContractError("bake manifest is incomplete or corrupt")
        self.bake_artifact_ref = bake_ref
        return SimulationBakeRef.create(self.project_ref, specification, "application/x-blender", (current_ref.value, bake_ref.value, manifest_ref.value), (current_content.digest, current_content.digest, manifest_content.digest), chain, final_attempt.attempt_id, final_attempt.fence)

    def plan_resource_exhaustion_recovery(
        self,
        specification: SimulationSpecification,
        *,
        failed_frame: int,
        failure_reason: str,
    ) -> SimulationResourceRecoveryPlan:
        checkpoints: list[SimulationCheckpointRef] = []
        for frame in range(specification.frame_start, failed_frame):
            checkpoint = self._existing_checkpoint(specification, frame)
            if checkpoint is None:
                raise SimulationContractError(
                    "resource recovery requires an exact durable checkpoint prefix"
                )
            checkpoints.append(checkpoint)
        dispatchable_frames = tuple(
            frame
            for frame in sorted(self.segment_dispatches)
            if frame >= failed_frame
        )
        return plan_verified_resource_exhaustion_recovery(
            artifacts=self.artifacts,
            access=self.access,
            specification=specification,
            verified_checkpoints=checkpoints,
            failed_frame=failed_frame,
            failure_reason=failure_reason,
            dispatchable_frames=dispatchable_frames,
        )

    def game_runtime_input(
        self,
        attempt: NodeExecutionAttempt,
        *,
        kind: str,
        runtime_path: str,
    ) -> tuple[GameAssetInput, GameRuntimeInputBinding]:
        if self.bake_artifact_ref is None:
            raise SimulationContractError(
                "completed bake Artifact is required for game handoff"
            )
        bake = self.artifacts.get_artifact(self.access, self.bake_artifact_ref)
        if bake.content_ref is None:
            raise SimulationContractError("completed bake ContentRef is missing")
        final_attempt = self.segment_dispatches[
            max(self.segment_dispatches)
        ].node_attempt
        if (
            final_attempt.attempt_id != attempt.attempt_id
            or final_attempt.fence != attempt.fence
        ):
            raise SimulationContractError(
                "game handoff requires exact bake producer authority"
            )
        GameAssetInput(kind, self.bake_artifact_ref)
        role = f"game.asset.{kind}.input"
        artifact_ref = self._publish(
            attempt,
            role=role,
            content=bake.content_ref,
            sources=(self.bake_artifact_ref,),
            source_contents=(bake.content_ref,),
            derivation="vfx.blender.game-input",
            metadata={"media_type": bake.content_ref.media_type},
        )
        asset = GameAssetInput(kind, artifact_ref)
        binding = GameRuntimeInputBinding(
            artifact_ref,
            role,
            bake.content_ref,
            runtime_path,
        )
        return asset, binding

    def render_preview(self, renderer: RendererAdapter, attempt: NodeExecutionAttempt, request: RenderRequest, *, idempotency_key: str) -> RenderFrameRef:
        if self.bake_artifact_ref is None:
            raise SimulationContractError("completed bake Artifact is required for preview")
        bake = self.artifacts.get_artifact(self.access, self.bake_artifact_ref)
        if bake.content_ref is None or request.scene_ref != self.bake_artifact_ref.value or request.scene_content_sha256 != bake.content_ref.digest:
            raise SimulationContractError("preview must bind exact completed bake Artifact and ContentRef")
        return renderer.render(self.access, attempt, request, scene_artifact_ref=self.bake_artifact_ref, root_ref=self.root_ref, working_directory=self.working_directory, idempotency_key=idempotency_key)


class ReferenceSimulationAdapter:
    """Honest reference adapter: it never claims REAL simulation evidence."""

    def __init__(self, project_ref: ProjectRef, tool_ref: str = "tool://reference", runtime_ref: str = "runtime://reference") -> None:
        self.project_ref, self.tool_ref, self.runtime_ref = project_ref, tool_ref, runtime_ref

    def simulate(self, specification: SimulationSpecification, checkpoint: SimulationCheckpointRef | None = None) -> SimulationBakeRef:
        raise SimulationContractError("REFERENCE simulation cannot claim REAL bake evidence")
