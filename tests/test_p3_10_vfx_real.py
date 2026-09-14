"""Focused REAL Blender deterministic VFX evidence."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from typing import Any, cast

import pytest

from minitz_os.engine.artifact import ArtifactService
from minitz_os.engine.filesystem import FilesystemError
from minitz_os.engine.game_engine import GameAssetInput, GameRuntimeInputBinding
from minitz_os.engine.render_pack import RenderConfig, RenderRequest
from minitz_os.engine.render_tool import RendererAdapter
from minitz_os.engine.scheduler import ScheduledDispatch, Scheduler
from minitz_os.engine.simulation_tool import BlenderSimulationAdapter, ReferenceSimulationAdapter
from minitz_os.engine.vfx_pack import SimulationCheckpointRef, SimulationContractError, SimulationSpecification


def _support() -> Any:
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location("p3_10_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _specification(env: Any, scene: Any, name: str) -> SimulationSpecification:
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    artifacts = ArtifactService(env.database)
    geometry = artifacts.create_artifact(env.access, project_ref=env.access.project_ref, role="vfx.simulation", content_ref=scene.output_content_ref, source_refs=(), source_artifact_refs=(scene.output_artifact_ref,), source_content_refs=(scene.output_content_ref,), derivation_type="vfx.test.geometry", metadata={"media_type": "application/x-blender"})
    animation = artifacts.create_artifact(env.access, project_ref=env.access.project_ref, role="vfx.simulation", content_ref=scene.output_content_ref, source_refs=(), source_artifact_refs=(scene.output_artifact_ref,), source_content_refs=(scene.output_content_ref,), derivation_type="vfx.test.animation", metadata={"media_type": "application/x-blender"})
    assert geometry.content_ref is not None and animation.content_ref is not None
    return SimulationSpecification.create(env.access.project_ref, name, scene.output_artifact_ref.value, scene.output_content_ref.digest, geometry.artifact_ref.value, geometry.content_ref.digest, animation.artifact_ref.value, animation.content_ref.digest, "particles", "v1", {"particle_count": "4", "gravity": "[0,0,-9.81]", "initial_velocity": "[0,0,1]", "floor_height": "0", "restitution": "0.5"}, {"density": "1"}, 1, 2, 0.0, 2.0, 1.0, 1, {"collision": "floor"}, {"force": "gravity"}, (scene.output_artifact_ref.value,), (scene.output_content_ref.digest,), {"cache": "required"}, {"renderer": "blender"}, {"validation": "required"}, {"timeout_seconds": "90", "file_size_bytes": "10485760", "process_count": "1"}, 7, "generator://minitz/procedural/v1", "tool://blender", env.identity.runtime_ref, "solver://blender/procedural/v1", env.identity.tool_version, "deterministic")


def _prepared(tmp_path: Path, name: str, *, count: int = 3) -> tuple[Any, Any, Any, SimulationSpecification, dict[int, ScheduledDispatch]]:
    support = _support()
    environments = support._environments(tmp_path, count=count)
    coordinator, one, two = environments[:3]
    scene = coordinator.adapter.createAsset(coordinator.access, coordinator.attempt, support._request(coordinator, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path=f"{name}.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": name, "unit_system": "METRIC"}), idempotency_key=name)
    scheduler = Scheduler(coordinator.database)
    dispatches = {1: ScheduledDispatch(scheduler.get_allocation(coordinator.access, one.allocation_ref), one.attempt), 2: ScheduledDispatch(scheduler.get_allocation(coordinator.access, two.allocation_ref), two.attempt)}
    if len(environments) > 3:
        fresh = environments[3]
        dispatches[0] = ScheduledDispatch(
            scheduler.get_allocation(coordinator.access, fresh.allocation_ref),
            fresh.attempt,
        )
    adapter = BlenderSimulationAdapter(coordinator.database, coordinator.objects, identity=coordinator.identity, access=coordinator.access, scene_artifact_ref=scene.output_artifact_ref, root_ref=coordinator.root_ref, working_directory="candidate", segment_dispatches={1: dispatches[1], 2: dispatches[2]})
    return coordinator, scene, adapter, _specification(coordinator, scene, name), dispatches


def test_each_segment_advances_only_its_own_timestep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, adapter, specification, _ = _prepared(tmp_path, "vfx-segment-range")
    observed: list[tuple[int, object, object, bool]] = []
    driver_config = adapter._driver_config

    def record_config(
        current: SimulationSpecification,
        frame: int,
        output_path: str,
        predecessor_state: list[dict[str, object]] | None,
    ) -> dict[str, object]:
        payload = cast(
            dict[str, object],
            driver_config(current, frame, output_path, predecessor_state),
        )
        observed.append(
            (
                frame,
                payload["frame_start"],
                payload["frame_end"],
                predecessor_state is not None,
            )
        )
        return payload

    monkeypatch.setattr(adapter, "_driver_config", record_config)
    assert adapter.simulate(specification).complete
    assert observed == [(1, 1, 1, False), (2, 2, 2, True)]


def test_fresh_resume_matches_uninterrupted_blender_content(tmp_path: Path) -> None:
    coordinator, _, adapter, specification, dispatches = _prepared(tmp_path, "vfx-fresh-resume", count=4)
    uninterrupted = adapter.simulate(specification)
    checkpoint = uninterrupted.checkpoints[0]
    uninterrupted_final = uninterrupted.checkpoints[-1]

    def solver_state_sha256(current: BlenderSimulationAdapter, item: SimulationCheckpointRef) -> str:
        artifact = current.artifacts.get_artifact(
            coordinator.access,
            current._artifact_ref(item.artifact_ref),
        )
        assert artifact.role == "vfx.checkpoint"
        assert artifact.content_ref is not None
        assert artifact.content_ref.digest == item.content_sha256
        assert current._artifact_ref(item.predecessor_artifact_ref) in artifact.source_artifact_refs
        states: list[object] = []
        for content_ref in artifact.source_content_refs:
            try:
                payload = json.loads(coordinator.objects.read(content_ref))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("segment") == item.frame and "state" in payload:
                states.append(payload["state"])
        assert len(states) == 1
        canonical = json.dumps(
            states[0],
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    expected_state_sha256 = solver_state_sha256(adapter, uninterrupted_final)
    with sqlite3.connect(coordinator.database) as connection:
        connection.execute(
            "DELETE FROM simulation_checkpoint_index WHERE project_id=? AND specification_digest=? AND frame=?",
            (coordinator.access.project_ref.value, specification.canonical_digest, 2),
        )
        connection.commit()
    workspace = Path(
        coordinator.filesystem.get_root(
            coordinator.access,
            coordinator.root_ref,
        ).canonical_path,
        "candidate",
    )
    for output_directory in workspace.glob(".minitz-simulation-*-out"):
        shutil.rmtree(output_directory)
    resumed = BlenderSimulationAdapter(
        coordinator.database,
        coordinator.objects,
        identity=coordinator.identity,
        access=coordinator.access,
        scene_artifact_ref=adapter.scene_artifact_ref,
        root_ref=coordinator.root_ref,
        working_directory="candidate",
        segment_dispatches={2: dispatches[0]},
    )
    assert resumed.simulate(specification, checkpoint=checkpoint).complete
    assert solver_state_sha256(resumed, resumed.checkpoints[-1]) == expected_state_sha256


def test_real_segments_cache_replay_bake_manifest_render_and_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator, scene, adapter, specification, dispatches = _prepared(tmp_path, "vfx-real")
    bake = adapter.simulate(specification)
    assert bake.complete and len(adapter.checkpoints) == 2 and len(bake.artifact_refs) == 3
    assert adapter.bake_artifact_ref is not None
    manifest_ref = adapter._artifact_ref(bake.artifact_refs[-1])
    manifest = adapter.artifacts.get_artifact(coordinator.access, manifest_ref)
    assert manifest.content_ref is not None and b"specification_digest" in coordinator.objects.read(manifest.content_ref)

    def must_not_repeat(*args: object, **kwargs: object) -> object:
        raise AssertionError("verified checkpoint must not rerun")

    monkeypatch.setattr(adapter.process, "execute", must_not_repeat)
    assert adapter.simulate(specification).complete
    cache_path = Path(coordinator.filesystem.get_root(coordinator.access, coordinator.root_ref).canonical_path, adapter.working_cache_path)
    shutil.rmtree(cache_path)
    fresh = BlenderSimulationAdapter(coordinator.database, coordinator.objects, identity=coordinator.identity, access=coordinator.access, scene_artifact_ref=scene.output_artifact_ref, root_ref=coordinator.root_ref, working_directory="candidate", segment_dispatches=adapter.segment_dispatches)
    monkeypatch.setattr(fresh.process, "execute", must_not_repeat)
    assert fresh.simulate(specification).complete and not cache_path.exists()

    bake_artifact = adapter.artifacts.get_artifact(coordinator.access, adapter.bake_artifact_ref)
    assert bake_artifact.content_ref is not None
    game_asset, game_binding = adapter.game_runtime_input(
        dispatches[2].node_attempt,
        kind="vfx",
        runtime_path="effects/vfx-real.blend",
    )
    assert isinstance(game_asset, GameAssetInput)
    assert isinstance(game_binding, GameRuntimeInputBinding)
    assert game_asset.artifact_ref == game_binding.artifact_ref
    assert game_asset.expected_role == "game.asset.vfx.input"
    assert game_binding.artifact_role == game_asset.expected_role
    assert game_binding.content_ref == bake_artifact.content_ref
    assert game_binding.container_path == "/run/minitz/game-inputs/effects/vfx-real.blend"
    game_artifact = adapter.artifacts.get_artifact(coordinator.access, game_asset.artifact_ref)
    assert game_artifact.source_artifact_refs == (adapter.bake_artifact_ref,)
    assert game_artifact.source_content_refs == (bake_artifact.content_ref,)
    config = RenderConfig(coordinator.access.project_ref, "preview", "config://vfx/preview", hashlib.sha256(b"vfx-preview").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(coordinator.access.project_ref, "task://vfx/preview", "run://vfx/preview", "node://vfx/preview", adapter.bake_artifact_ref.value, bake_artifact.content_ref.digest, "camera://vfx/preview", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://vfx/preview", hashlib.sha256(b"vfx-preview-camera").hexdigest(), 1, 1, 0.0, "render.preview", config, "renderer://blender", "runtime://blender", "executor://local", ())
    assert adapter.render_preview(RendererAdapter(coordinator.database, coordinator.objects, identity=coordinator.identity), coordinator.attempt, request, idempotency_key="vfx-preview").verified
    with pytest.raises(SimulationContractError):
        adapter.render_preview(RendererAdapter(coordinator.database, coordinator.objects, identity=coordinator.identity), coordinator.attempt, replace(request, scene_ref=scene.output_artifact_ref.value), idempotency_key="forged-preview")
    with pytest.raises(SimulationContractError):
        ReferenceSimulationAdapter(coordinator.access.project_ref).simulate(specification)


def test_worker_loss_stale_input_and_checkpoint_corruption_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator, _, adapter, specification, dispatches = _prepared(tmp_path, "vfx-recovery")
    persisted: list[SimulationCheckpointRef] = []
    real_persist = adapter._persist_checkpoint

    def lose_after_checkpoint(*args: object, **kwargs: object) -> None:
        real_persist(*args, **kwargs)
        persisted.append(cast(SimulationCheckpointRef, args[1]))
        raise RuntimeError("worker loss")

    monkeypatch.setattr(adapter, "_persist_checkpoint", lose_after_checkpoint)
    with pytest.raises(RuntimeError, match="worker loss"):
        adapter.simulate(specification)
    checkpoint = persisted[0]
    assert checkpoint.frame == 1
    resumed = BlenderSimulationAdapter(coordinator.database, coordinator.objects, identity=coordinator.identity, access=coordinator.access, scene_artifact_ref=adapter.scene_artifact_ref, root_ref=coordinator.root_ref, working_directory="candidate", segment_dispatches={2: dispatches[2]})
    assert resumed.simulate(specification, checkpoint=checkpoint).complete
    with pytest.raises(SimulationContractError):
        replace(specification, config_version="forged")
    with sqlite3.connect(coordinator.database) as connection:
        connection.execute("UPDATE simulation_checkpoint_index SET content_sha256=? WHERE frame=1", ("0" * 64,))
        connection.commit()
    with pytest.raises(SimulationContractError, match="corrupt|forged"):
        resumed.simulate(specification, checkpoint=checkpoint)


def test_missing_metadata_and_later_cancel_or_enospc_preserve_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator, _, adapter, specification, dispatches = _prepared(tmp_path, "vfx-missing")
    real_read = adapter.filesystem.read

    def missing_metadata(*args: object, **kwargs: object) -> object:
        if str(kwargs.get("path", "")).endswith(".json"):
            raise FilesystemError("missing metadata")
        return real_read(*args, **kwargs)

    monkeypatch.setattr(adapter.filesystem, "read", missing_metadata)
    with pytest.raises(SimulationContractError, match="metadata"):
        adapter.simulate(specification)
    assert not adapter.checkpoints and adapter.bake_artifact_ref is None

    interrupted = BlenderSimulationAdapter(coordinator.database, coordinator.objects, identity=coordinator.identity, access=coordinator.access, scene_artifact_ref=adapter.scene_artifact_ref, root_ref=coordinator.root_ref, working_directory="candidate", segment_dispatches=dispatches, before_segment_process=lambda frame: (_ for _ in ()).throw(OSError(28, "No space left on device")) if frame == 2 else None)
    with pytest.raises(OSError, match="No space left on device"):
        interrupted.simulate(specification)
    assert tuple(item.frame for item in interrupted.checkpoints) == (1,)
    recovery = interrupted.plan_resource_exhaustion_recovery(
        specification,
        failed_frame=2,
        failure_reason="ENOSPC: No space left on device",
    )
    assert recovery.authority_verified
    assert recovery.preserved_segments == ((1, 1),)
    assert recovery.frames_to_dispatch == (2,)
    assert recovery.frames_to_recompute == ()
    assert recovery.authoritative_checkpoint_artifact_refs == (
        interrupted.checkpoints[0].artifact_ref,
    )


def test_independent_dispatched_simulations_overlap_but_each_chain_is_serial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    support = _support()
    coordinator_a, a1, a2, coordinator_b, b1, b2 = support._environments(tmp_path, count=6)
    def build(coordinator: Any, one: Any, two: Any, name: str) -> tuple[BlenderSimulationAdapter, SimulationSpecification]:
        scene = coordinator.adapter.createAsset(coordinator.access, coordinator.attempt, support._request(coordinator, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path=f"{name}.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": name, "unit_system": "METRIC"}), idempotency_key=name)
        scheduler = Scheduler(coordinator.database)
        dispatches = {1: ScheduledDispatch(scheduler.get_allocation(coordinator.access, one.allocation_ref), one.attempt), 2: ScheduledDispatch(scheduler.get_allocation(coordinator.access, two.allocation_ref), two.attempt)}
        return BlenderSimulationAdapter(coordinator.database, coordinator.objects, identity=coordinator.identity, access=coordinator.access, scene_artifact_ref=scene.output_artifact_ref, root_ref=coordinator.root_ref, working_directory="candidate", segment_dispatches=dispatches), _specification(coordinator, scene, name)
    first, first_spec = build(coordinator_a, a1, a2, "vfx-a")
    second, second_spec = build(coordinator_b, b1, b2, "vfx-b")
    barrier, lock = Barrier(2), Lock()
    active = 0
    maximum = 0
    for adapter in (first, second):
        def synchronize(frame: int) -> None:
            if frame == 1:
                barrier.wait(timeout=5.0)

        adapter.before_segment_process = synchronize
        execute = adapter.process.execute
        def observe(*args: object, _execute: object = execute, **kwargs: object) -> object:
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                return _execute(*args, **kwargs)  # type: ignore[operator]
            finally:
                with lock:
                    active -= 1
        monkeypatch.setattr(adapter.process, "execute", observe)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_bake, second_bake = tuple(executor.map(lambda pair: pair[0].simulate(pair[1]), ((first, first_spec), (second, second_spec))))
    assert first_bake.complete and second_bake.complete and maximum == 2
    assert tuple(item.frame for item in first.checkpoints) == (1, 2)
    assert tuple(item.frame for item in second.checkpoints) == (1, 2)
