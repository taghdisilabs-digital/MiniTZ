"""Focused REAL Blender render evidence."""
from __future__ import annotations

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
from pathlib import Path
import sqlite3
import sys
from typing import Any

import pytest

from biella.artifact import ArtifactService
from biella.render_pack import RenderConfig, RenderContractError, RenderRequest, RendererAdapter as RendererProtocol
from biella.render_tool import ReferenceRendererAdapter, RendererAdapter, _digest, _request_identity
from biella.scheduler import ScheduledDispatch, Scheduler


def _support() -> Any:
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location("p3_09_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_real_preview_and_final_png_frame_are_independently_verified(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-scene.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderScene", "unit_system": "METRIC"}), idempotency_key="render-scene")
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    config = RenderConfig(env.access.project_ref, "preview", "config://render/preview", hashlib.sha256(b"preview").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/test", "run://render/test", "node://render/test", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/default", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/default", hashlib.sha256(b"camera").hexdigest(), 1, 1, 0.0, "render.preview", config, "renderer://blender", "runtime://blender", "executor://local", ())
    adapter = RendererAdapter(env.database, env.objects, identity=env.identity)
    protocol: RendererProtocol = adapter
    assert protocol.project_ref == env.access.project_ref
    assert protocol.renderer_ref == "renderer://blender"
    assert protocol.runtime_ref == env.identity.runtime_ref
    assert protocol.executor_ref == "executor://local"
    preview = adapter.render(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="preview")
    assert preview.verified and preview.frame == 1 and preview.content_sha256
    final = adapter.render(env.access, env.attempt, replace(request, capability_id="render.frame", config=replace(config, kind="final", config_id="final", config_ref="config://render/final", digest=hashlib.sha256(b"final").hexdigest())), scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="final")
    assert final.verified and final.config_ref != preview.config_ref and final.content_sha256 != preview.content_sha256
    with pytest.raises(RenderContractError):
        ReferenceRendererAdapter().render(request)


def test_verified_sequence_frame_replays_after_fresh_adapter_without_rerender(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    support = _support()
    env = support._environment(tmp_path)
    scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-replay-scene.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderReplay", "unit_system": "METRIC"}), idempotency_key="render-replay-scene")
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    config = RenderConfig(env.access.project_ref, "preview", "config://render/replay", hashlib.sha256(b"replay").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/replay", "run://render/replay", "node://render/replay", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/replay", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/replay", hashlib.sha256(b"replay-camera").hexdigest(), 1, 1, 0.0, "render.sequence", config, "renderer://blender", "runtime://blender", "executor://local", ())
    first = RendererAdapter(env.database, env.objects, identity=env.identity).render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="replay")
    recovered = RendererAdapter(env.database, env.objects, identity=env.identity)

    def should_not_render(*args: object, **kwargs: object) -> object:
        raise AssertionError("durable verified frame must be replayed")

    monkeypatch.setattr(recovered, "render", should_not_render)
    replay = recovered.render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="replay")
    assert replay == first


def test_worker_loss_after_durable_result_before_journal_reuses_one_publication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    support = _support()
    env = support._environment(tmp_path)
    scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-loss-scene.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderLoss", "unit_system": "METRIC"}), idempotency_key="render-loss-scene")
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    config = RenderConfig(env.access.project_ref, "preview", "config://render/loss", hashlib.sha256(b"loss").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/loss", "run://render/loss", "node://render/loss", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/loss", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/loss", hashlib.sha256(b"loss-camera").hexdigest(), 1, 1, 0.0, "render.sequence", config, "renderer://blender", "runtime://blender", "executor://local", ())
    lost = RendererAdapter(env.database, env.objects, identity=env.identity)

    def lose_after_result(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected worker loss")

    monkeypatch.setattr(lost, "_persist_frame", lose_after_result)
    with pytest.raises(RuntimeError, match="injected worker loss"):
        lost.render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="loss")
    recovered = RendererAdapter(env.database, env.objects, identity=env.identity)

    def should_not_execute(*args: object, **kwargs: object) -> object:
        raise AssertionError("durable render result must not launch Blender again")

    monkeypatch.setattr(recovered.process, "execute", should_not_execute)
    replay = recovered.render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="loss")
    assert len(replay.completed_frames) == 1
    with sqlite3.connect(env.database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM render_frame_results").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM render_sequence_frames").fetchone() == (1,)


def test_corrupt_persisted_pass_fails_closed_without_rerender(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-corrupt-scene.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderCorrupt", "unit_system": "METRIC"}), idempotency_key="render-corrupt-scene")
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    config = RenderConfig(env.access.project_ref, "preview", "config://render/corrupt", hashlib.sha256(b"corrupt").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/corrupt", "run://render/corrupt", "node://render/corrupt", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/corrupt", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/corrupt", hashlib.sha256(b"corrupt-camera").hexdigest(), 1, 1, 0.0, "render.sequence", config, "renderer://blender", "runtime://blender", "executor://local", ())
    RendererAdapter(env.database, env.objects, identity=env.identity).render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="corrupt")
    corrupt = env.objects.put(b"corrupt-pass", media_type="image/png")
    corrupt_artifact = ArtifactService(env.database).create_artifact(env.access, project_ref=env.access.project_ref, role="render.pass", content_ref=corrupt, source_refs=(), source_artifact_refs=(), source_content_refs=(), derivation_type="render.blender", metadata={"media_type": "image/png"})
    with sqlite3.connect(env.database) as connection:
        connection.execute("UPDATE render_sequence_frames SET artifact_id=?, artifact_revision=?, content_sha256=?", (corrupt_artifact.artifact_ref.artifact_id, corrupt_artifact.artifact_ref.revision, corrupt.digest))
        connection.commit()
    with pytest.raises(RenderContractError, match="not PNG"):
        RendererAdapter(env.database, env.objects, identity=env.identity).render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="corrupt")


def test_injected_sibling_failure_preserves_completed_real_frame(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    support = _support()
    env = support._environment(tmp_path)
    scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-sibling-scene.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderSibling", "unit_system": "METRIC"}), idempotency_key="render-sibling-scene")
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    config = RenderConfig(env.access.project_ref, "preview", "config://render/sibling", hashlib.sha256(b"sibling").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/sibling", "run://render/sibling", "node://render/sibling", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/sibling", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/sibling", hashlib.sha256(b"sibling-camera").hexdigest(), 1, 2, 0.0, "render.sequence", config, "renderer://blender", "runtime://blender", "executor://local", ())
    adapter = RendererAdapter(env.database, env.objects, identity=env.identity)
    real_render = adapter.render

    def fail_second(access: object, attempt: object, frame_request: RenderRequest, **kwargs: object) -> object:
        if frame_request.frame_start == 2:
            raise RenderContractError("injected sibling failure")
        return real_render(access, attempt, frame_request, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(adapter, "render", fail_second)
    manifest = adapter.render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="sibling")
    assert tuple(frame.frame for frame in manifest.completed_frames) == (1,)
    assert manifest.failed_frames == (2,)


def test_parallel_frame_staging_paths_are_tokenized_before_config_write(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    config = RenderConfig(env.access.project_ref, "preview", "config://render/staging", hashlib.sha256(b"staging").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/staging", "run://render/staging", "node://render/staging", "artifact://staging/scene/1", hashlib.sha256(b"scene").hexdigest(), "camera://render/staging", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/staging", hashlib.sha256(b"staging-camera").hexdigest(), 1, 2, 0.0, "render.sequence", config, "renderer://blender", "runtime://blender", "executor://local", ())
    from threading import Barrier

    barrier = Barrier(2)

    def write(frame: int) -> Path:
        token = _digest({"request": _request_identity(request), "frame": frame, "pass": "beauty"})[:24]
        config_path = tmp_path / f".biella-render-{token}-config.json"
        barrier.wait()
        config_path.write_text(str(frame), encoding="ascii")
        return config_path

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = tuple(executor.map(write, (1, 2)))
    assert first != second and first.read_text(encoding="ascii") == "1" and second.read_text(encoding="ascii") == "2"


def test_distinct_scheduled_children_parallelize_after_staging_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    support = _support()
    coordinator, first_child, second_child = support._environments(tmp_path, count=3)
    scene = coordinator.adapter.createAsset(coordinator.access, coordinator.attempt, support._request(coordinator, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-fanout-scene.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderFanout", "unit_system": "METRIC"}), idempotency_key="render-fanout-scene")
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    config = RenderConfig(coordinator.access.project_ref, "preview", "config://render/fanout", hashlib.sha256(b"fanout").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 25.0, True)
    task_ref = f"task://{coordinator.attempt.task_ref.project_ref.value}/{coordinator.attempt.task_ref.task_id}/{coordinator.attempt.task_ref.revision}"
    run_ref = f"run://{coordinator.attempt.run_ref.project_ref.value}/{coordinator.attempt.run_ref.run_id}"
    request = RenderRequest(coordinator.access.project_ref, task_ref, run_ref, coordinator.attempt.node_ref.value, scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/fanout", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/fanout", hashlib.sha256(b"fanout-camera").hexdigest(), 1, 2, 0.0, "render.sequence", config, "renderer://blender", "runtime://blender", coordinator.attempt.owner_ref, ())
    scheduler = Scheduler(coordinator.database)
    first_dispatch = ScheduledDispatch(scheduler.get_allocation(coordinator.access, first_child.allocation_ref), first_child.attempt)
    second_dispatch = ScheduledDispatch(scheduler.get_allocation(coordinator.access, second_child.allocation_ref), second_child.attempt)
    adapter = RendererAdapter(coordinator.database, coordinator.objects, identity=coordinator.identity)
    from threading import Lock

    real_render = adapter.render
    lock = Lock()
    active = 0
    maximum_active = 0

    def observe_overlap(access: object, attempt: object, frame_request: RenderRequest, **kwargs: object) -> object:
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            return real_render(access, attempt, frame_request, **kwargs)  # type: ignore[arg-type]
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(adapter, "render", observe_overlap)
    manifest = adapter.render_sequence(coordinator.access, coordinator.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=coordinator.root_ref, working_directory="candidate", idempotency_key="fanout", child_dispatches={(1, "beauty"): first_dispatch, (2, "beauty"): second_dispatch})
    assert tuple(frame.frame for frame in manifest.completed_frames) == (1, 2)
    assert not manifest.failed_frames and maximum_active == 2


def test_child_dispatches_reject_forged_keys_state_and_reuse_before_launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    support = _support()
    coordinator, first_child, second_child = support._environments(tmp_path, count=3)
    config = RenderConfig(coordinator.access.project_ref, "preview", "config://render/child-validation", hashlib.sha256(b"child-validation").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 25.0, True)
    task_ref = f"task://{coordinator.attempt.task_ref.project_ref.value}/{coordinator.attempt.task_ref.task_id}/{coordinator.attempt.task_ref.revision}"
    run_ref = f"run://{coordinator.attempt.run_ref.project_ref.value}/{coordinator.attempt.run_ref.run_id}"
    request = RenderRequest(coordinator.access.project_ref, task_ref, run_ref, coordinator.attempt.node_ref.value, coordinator.snapshot_artifact_ref.value, hashlib.sha256(b"child-validation-scene").hexdigest(), "camera://render/child-validation", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/child-validation", hashlib.sha256(b"child-validation-camera").hexdigest(), 1, 2, 0.0, "render.sequence", config, "renderer://blender", "runtime://blender", coordinator.attempt.owner_ref, ())
    scheduler = Scheduler(coordinator.database)
    first_dispatch = ScheduledDispatch(scheduler.get_allocation(coordinator.access, first_child.allocation_ref), first_child.attempt)
    second_dispatch = ScheduledDispatch(scheduler.get_allocation(coordinator.access, second_child.allocation_ref), second_child.attempt)
    adapter = RendererAdapter(coordinator.database, coordinator.objects, identity=coordinator.identity)

    def must_not_launch(*args: object, **kwargs: object) -> object:
        raise AssertionError("invalid child dispatches must reject before launch")

    monkeypatch.setattr(adapter, "render", must_not_launch)
    with pytest.raises(RenderContractError, match="keys"):
        adapter.render_sequence(coordinator.access, coordinator.attempt, request, scene_artifact_ref=coordinator.snapshot_artifact_ref, root_ref=coordinator.root_ref, working_directory="candidate", idempotency_key="child-validation", child_dispatches={(1, "beauty"): first_dispatch})
    with pytest.raises(RenderContractError, match="unique"):
        adapter.render_sequence(coordinator.access, coordinator.attempt, request, scene_artifact_ref=coordinator.snapshot_artifact_ref, root_ref=coordinator.root_ref, working_directory="candidate", idempotency_key="child-validation", child_dispatches={(1, "beauty"): first_dispatch, (2, "beauty"): first_dispatch})
    reserved = ScheduledDispatch(replace(second_dispatch.allocation, status="RESERVED", dispatch_idempotency_key=None, node_attempt_id=None, node_attempt_fence=None), second_dispatch.node_attempt)
    with pytest.raises(RenderContractError, match="allocation"):
        adapter.render_sequence(coordinator.access, coordinator.attempt, request, scene_artifact_ref=coordinator.snapshot_artifact_ref, root_ref=coordinator.root_ref, working_directory="candidate", idempotency_key="child-validation", child_dispatches={(1, "beauty"): first_dispatch, (2, "beauty"): reserved})


def test_scene_or_config_version_change_never_reuses_render_result(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    first_scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-version-first.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderVersionFirst", "unit_system": "METRIC"}), idempotency_key="render-version-first")
    second_scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-version-second.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderVersionSecond", "unit_system": "METRIC"}), idempotency_key="render-version-second")
    assert first_scene.output_artifact_ref is not None and first_scene.output_content_ref is not None
    assert second_scene.output_artifact_ref is not None and second_scene.output_content_ref is not None
    config = RenderConfig(env.access.project_ref, "preview", "config://render/version/one", hashlib.sha256(b"version-one").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/version", "run://render/version", "node://render/version", first_scene.output_artifact_ref.value, first_scene.output_content_ref.digest, "camera://render/version", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/version", hashlib.sha256(b"version-camera").hexdigest(), 1, 1, 0.0, "render.preview", config, "renderer://blender", "runtime://blender", "executor://local", ())
    adapter = RendererAdapter(env.database, env.objects, identity=env.identity)
    first = adapter.render(env.access, env.attempt, request, scene_artifact_ref=first_scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="version-first")
    changed_scene = replace(request, scene_ref=second_scene.output_artifact_ref.value, scene_content_sha256=second_scene.output_content_ref.digest)
    scene_result = adapter.render(env.access, env.attempt, changed_scene, scene_artifact_ref=second_scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="version-second-scene")
    changed_config = replace(request, config=replace(config, config_id="two", config_ref="config://render/version/two", digest=hashlib.sha256(b"version-two").hexdigest()))
    config_result = adapter.render(env.access, env.attempt, changed_config, scene_artifact_ref=first_scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="version-second-config")
    assert len({first.artifact_ref, scene_result.artifact_ref, config_result.artifact_ref}) == 3


def test_missing_required_pass_is_failed_without_substitution(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-missing-pass.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderMissingPass", "unit_system": "METRIC"}), idempotency_key="render-missing-pass")
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    config = RenderConfig(env.access.project_ref, "preview", "config://render/missing-pass", hashlib.sha256(b"missing-pass").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty", "missing"), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/missing-pass", "run://render/missing-pass", "node://render/missing-pass", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/missing-pass", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/missing-pass", hashlib.sha256(b"missing-pass-camera").hexdigest(), 1, 1, 0.0, "render.sequence", config, "renderer://blender", "runtime://blender", "executor://local", ())
    manifest = RendererAdapter(env.database, env.objects, identity=env.identity).render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="missing-pass")
    assert not manifest.completed_frames and manifest.failed_frames == (1,)
