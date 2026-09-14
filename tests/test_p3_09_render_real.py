"""Focused REAL Blender render evidence."""
from __future__ import annotations

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
from pathlib import Path
import sqlite3
import struct
import sys
from typing import Any
import zlib

import pytest

from minitz_os.engine.artifact import ArtifactService
from minitz_os.engine.render_pack import RenderConfig, RenderContractError, RenderRequest, RendererAdapter as RendererProtocol
from minitz_os.engine.render_tool import ReferenceRendererAdapter, RendererAdapter, _digest, _png_dimensions, _request_identity
from minitz_os.engine.scheduler import ScheduledDispatch, Scheduler


def _support() -> Any:
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location("p3_09_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _png_with_filter(filter_type: int, *, include_iend: bool) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)

    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(bytes((filter_type, 0, 0, 0, 255))))
    if include_iend:
        payload += chunk(b"IEND", b"")
    return payload


def test_png_validation_rejects_invalid_scanline_filter_and_missing_iend() -> None:
    with pytest.raises(RenderContractError, match="filter"):
        _png_dimensions(_png_with_filter(5, include_iend=True))
    with pytest.raises(RenderContractError, match="IEND"):
        _png_dimensions(_png_with_filter(0, include_iend=False))


def test_real_preview_and_final_png_frame_are_independently_verified(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-scene.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderScene", "unit_system": "METRIC"}), idempotency_key="render-scene")
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    config = RenderConfig(env.access.project_ref, "preview", "config://render/preview", hashlib.sha256(b"preview").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/test", "run://render/test", "node://render/test", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/default", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/default", hashlib.sha256(b"camera").hexdigest(), 1, 1, 0.0, "render.preview", config, "renderer://generic/v1", "runtime://generic/v1", "executor://local", ())
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


    reference_config = RenderConfig(env.access.project_ref, "preview", "config://render/reference", hashlib.sha256(b"reference").hexdigest(), "preview", (3, 3), "image/png", ("R", "G", "B", "A"), ("beauty", "z", "normal"), {"samples": "1"}, {}, {}, 90.0, True)
    reference_request = replace(request, config=reference_config)
    reference = ReferenceRendererAdapter(env.database, env.objects, identity=env.identity)
    reference_frames = reference.renderPasses(env.access, env.attempt, reference_request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="reference-passes")
    assert tuple(frame.pass_id for frame in reference_frames) == ("beauty", "z", "normal")
    assert all(frame.verified for frame in reference_frames)
    assert all(frame.renderer_ref == reference.renderer_ref for frame in reference_frames)
    assert all(frame.runtime_ref == reference.runtime_ref for frame in reference_frames)


def test_verified_sequence_frame_replays_after_fresh_adapter_without_rerender(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    support = _support()
    env = support._environment(tmp_path)
    scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-replay-scene.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderReplay", "unit_system": "METRIC"}), idempotency_key="render-replay-scene")
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    config = RenderConfig(env.access.project_ref, "preview", "config://render/replay", hashlib.sha256(b"replay").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/replay", "run://render/replay", "node://render/replay", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/replay", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/replay", hashlib.sha256(b"replay-camera").hexdigest(), 1, 1, 0.0, "render.sequence", config, "renderer://generic/v1", "runtime://generic/v1", "executor://local", ())
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
    request = RenderRequest(env.access.project_ref, "task://render/loss", "run://render/loss", "node://render/loss", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/loss", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/loss", hashlib.sha256(b"loss-camera").hexdigest(), 1, 1, 0.0, "render.sequence", config, "renderer://generic/v1", "runtime://generic/v1", "executor://local", ())
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
    request = RenderRequest(env.access.project_ref, "task://render/corrupt", "run://render/corrupt", "node://render/corrupt", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/corrupt", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/corrupt", hashlib.sha256(b"corrupt-camera").hexdigest(), 1, 1, 0.0, "render.sequence", config, "renderer://generic/v1", "runtime://generic/v1", "executor://local", ())
    RendererAdapter(env.database, env.objects, identity=env.identity).render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="corrupt")
    corrupt = env.objects.put(b"corrupt-pass", media_type="image/png")
    corrupt_artifact = ArtifactService(env.database).create_artifact(env.access, project_ref=env.access.project_ref, role="render.pass", content_ref=corrupt, source_refs=(), source_artifact_refs=(), source_content_refs=(), derivation_type="render.blender", metadata={"media_type": "image/png"})
    with sqlite3.connect(env.database) as connection:
        connection.execute("UPDATE render_sequence_frames SET artifact_id=?, artifact_revision=?, content_sha256=?", (corrupt_artifact.artifact_ref.artifact_id, corrupt_artifact.artifact_ref.revision, corrupt.digest))
        connection.commit()
    with pytest.raises(RenderContractError, match="forged or stale"):
        RendererAdapter(env.database, env.objects, identity=env.identity).render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="corrupt")


def test_injected_sibling_failure_preserves_completed_real_frame(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    support = _support()
    env = support._environment(tmp_path)
    scene = env.adapter.createAsset(env.access, env.attempt, support._request(env, support.ThreeDOperation.MODEL, source=None, source_path=None, output_path="render-sibling-scene.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "RenderSibling", "unit_system": "METRIC"}), idempotency_key="render-sibling-scene")
    assert scene.output_artifact_ref is not None and scene.output_content_ref is not None
    config = RenderConfig(env.access.project_ref, "preview", "config://render/sibling", hashlib.sha256(b"sibling").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/sibling", "run://render/sibling", "node://render/sibling", scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/sibling", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/sibling", hashlib.sha256(b"sibling-camera").hexdigest(), 1, 2, 0.0, "render.sequence", config, "renderer://generic/v1", "runtime://generic/v1", "executor://local", ())
    adapter = RendererAdapter(env.database, env.objects, identity=env.identity)
    real_render = adapter.render

    def fail_second(access: object, attempt: object, frame_request: RenderRequest, **kwargs: object) -> object:
        if frame_request.frame_start == 2:
            raise RenderContractError("injected sibling failure")
        return real_render(access, attempt, frame_request, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(adapter, "render", fail_second)
    interrupted = adapter.render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="sibling")
    preserved = interrupted.completed_frames[0]
    assert interrupted.require_frame(preserved) == preserved
    assert interrupted.failed_frames == (2,)

    fresh = RendererAdapter(env.database, env.objects, identity=env.identity)
    fresh_render = fresh.render
    launched: list[int] = []

    def observe_resume(access: object, attempt: object, frame_request: RenderRequest, **kwargs: object) -> object:
        launched.append(frame_request.frame_start)
        return fresh_render(access, attempt, frame_request, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(fresh, "render", observe_resume)
    resumed = fresh.render_sequence(env.access, env.attempt, request, scene_artifact_ref=scene.output_artifact_ref, root_ref=env.root_ref, working_directory="candidate", idempotency_key="sibling")
    assert launched == [2]
    assert resumed.failed_frames == ()
    resumed_first = next(frame for frame in resumed.completed_frames if frame.frame == 1)
    resumed_second = next(frame for frame in resumed.completed_frames if frame.frame == 2)
    assert resumed.require_frame(resumed_first) == preserved
    assert resumed.require_frame(resumed_second).verified


def test_parallel_frame_staging_paths_are_tokenized_before_config_write(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    config = RenderConfig(env.access.project_ref, "preview", "config://render/staging", hashlib.sha256(b"staging").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {}, {}, 90.0, True)
    request = RenderRequest(env.access.project_ref, "task://render/staging", "run://render/staging", "node://render/staging", "artifact://staging/scene/1", hashlib.sha256(b"scene").hexdigest(), "camera://render/staging", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/staging", hashlib.sha256(b"staging-camera").hexdigest(), 1, 2, 0.0, "render.sequence", config, "renderer://generic/v1", "runtime://generic/v1", "executor://local", ())
    from threading import Barrier

    barrier = Barrier(2)

    def write(frame: int) -> Path:
        token = _digest({"request": _request_identity(request), "frame": frame, "pass": "beauty"})[:24]
        config_path = tmp_path / f".minitz-render-{token}-config.json"
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
    config = RenderConfig(coordinator.access.project_ref, "preview", "config://render/fanout", hashlib.sha256(b"fanout").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty",), {"samples": "1"}, {"max_parallel": "2"}, {}, 25.0, True)
    task_ref = f"task://{coordinator.attempt.task_ref.project_ref.value}/{coordinator.attempt.task_ref.task_id}/{coordinator.attempt.task_ref.revision}"
    run_ref = f"run://{coordinator.attempt.run_ref.project_ref.value}/{coordinator.attempt.run_ref.run_id}"
    request = RenderRequest(coordinator.access.project_ref, task_ref, run_ref, coordinator.attempt.node_ref.value, scene.output_artifact_ref.value, scene.output_content_ref.digest, "camera://render/fanout", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/fanout", hashlib.sha256(b"fanout-camera").hexdigest(), 1, 2, 0.0, "render.sequence", config, "renderer://generic/v1", "runtime://generic/v1", coordinator.attempt.owner_ref, ())
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
    snapshot = ArtifactService(coordinator.database).get_artifact(coordinator.access, coordinator.snapshot_artifact_ref)
    assert snapshot.content_ref is not None
    request = RenderRequest(coordinator.access.project_ref, task_ref, run_ref, coordinator.attempt.node_ref.value, coordinator.snapshot_artifact_ref.value, snapshot.content_ref.digest, "camera://render/child-validation", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/child-validation", hashlib.sha256(b"child-validation-camera").hexdigest(), 1, 2, 0.0, "render.sequence", config, "renderer://generic/v1", "runtime://generic/v1", coordinator.attempt.owner_ref, ())
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
    request = RenderRequest(env.access.project_ref, "task://render/version", "run://render/version", "node://render/version", first_scene.output_artifact_ref.value, first_scene.output_content_ref.digest, "camera://render/version", (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0), "lens://render/version", hashlib.sha256(b"version-camera").hexdigest(), 1, 1, 0.0, "render.preview", config, "renderer://generic/v1", "runtime://generic/v1", "executor://local", ())
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
    with pytest.raises(RenderContractError, match="passes"):
        RenderConfig(env.access.project_ref, "preview", "config://render/missing-pass", hashlib.sha256(b"missing-pass").hexdigest(), "preview", (64, 64), "image/png", ("R", "G", "B", "A"), ("beauty", "missing"), {"samples": "1"}, {}, {}, 90.0, True)


def test_reference_fences_project_mixing_and_cancelled_late_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = _support()
    env = support._environment(tmp_path)
    scene = ArtifactService(env.database).get_artifact(
        env.access, env.snapshot_artifact_ref
    )
    assert scene.content_ref is not None
    config = RenderConfig(
        env.access.project_ref,
        "reference-sequence",
        "config://render/reference-sequence",
        hashlib.sha256(b"reference-sequence").hexdigest(),
        "preview",
        (3, 3),
        "image/png",
        ("R", "G", "B", "A"),
        ("beauty",),
        {"samples": "1"},
        {},
        {},
        30.0,
        True,
    )
    request = RenderRequest(
        env.access.project_ref,
        "task://render/reference-boundaries",
        "run://render/reference-boundaries",
        "node://render/reference-boundaries",
        env.snapshot_artifact_ref.value,
        scene.content_ref.digest,
        "camera://render/reference-boundaries",
        (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 0.0, 0.0, 1.0),
        "lens://render/reference-boundaries",
        hashlib.sha256(b"reference-boundaries-camera").hexdigest(),
        1,
        1,
        0.0,
        "render.sequence",
        config,
        "renderer://generic/v1",
        "runtime://generic/v1",
        "executor://generic/v1",
        (),
    )
    reference = ReferenceRendererAdapter(
        env.database, env.objects, identity=env.identity
    )

    foreign_project = type(env.access.project_ref).new()
    foreign_config = replace(config, project_ref=foreign_project)
    foreign_request = replace(
        request, project_ref=foreign_project, config=foreign_config
    )
    with pytest.raises(RenderContractError, match="Project"):
        reference.inspect(foreign_request)
    with pytest.raises(RenderContractError, match="Project"):
        reference.renderFrame(
            replace(env.access, project_ref=foreign_project),
            env.attempt,
            request,
            scene_artifact_ref=env.snapshot_artifact_ref,
            root_ref=env.root_ref,
            working_directory="candidate",
            idempotency_key="foreign-access",
        )
    with pytest.raises(RenderContractError, match="ArtifactRef"):
        reference.renderFrame(
            env.access,
            env.attempt,
            request,
            scene_artifact_ref=replace(
                env.snapshot_artifact_ref, project_ref=foreign_project
            ),
            root_ref=env.root_ref,
            working_directory="candidate",
            idempotency_key="foreign-scene",
        )

    manifest = reference.renderSequence(
        env.access,
        env.attempt,
        request,
        scene_artifact_ref=env.snapshot_artifact_ref,
        root_ref=env.root_ref,
        working_directory="candidate",
        idempotency_key="mixing",
    )
    assert len(manifest.completed_frames) == 1
    for mixed in (
        replace(request, config=replace(config, quality={"samples": "2"})),
        replace(request, camera_object="MixedCamera"),
    ):
        with pytest.raises(RenderContractError, match="sequence.*identity"):
            reference.renderSequence(
                env.access,
                env.attempt,
                mixed,
                scene_artifact_ref=env.snapshot_artifact_ref,
                root_ref=env.root_ref,
                working_directory="candidate",
                idempotency_key="mixing",
            )

    mixed_content = env.objects.put(
        b"distinct-reference-scene", media_type="application/x-blender"
    )
    mixed_scene = ArtifactService(env.database).create_artifact(
        env.access,
        project_ref=env.access.project_ref,
        role="3d.mesh",
        content_ref=mixed_content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="3d.model",
        metadata={"media_type": "application/x-blender"},
    )
    mixed_scene_request = replace(
        request,
        scene_ref=mixed_scene.artifact_ref.value,
        scene_content_sha256=mixed_content.digest,
    )
    with pytest.raises(RenderContractError, match="sequence.*identity"):
        reference.renderSequence(
            env.access,
            env.attempt,
            mixed_scene_request,
            scene_artifact_ref=mixed_scene.artifact_ref,
            root_ref=env.root_ref,
            working_directory="candidate",
            idempotency_key="mixing",
        )
    with pytest.raises(RenderContractError, match="mixed.*runtime identity"):
        RendererAdapter(env.database, env.objects, identity=env.identity).renderSequence(
            env.access,
            env.attempt,
            request,
            scene_artifact_ref=env.snapshot_artifact_ref,
            root_ref=env.root_ref,
            working_directory="candidate",
            idempotency_key="mixing",
        )

    cancel_config = replace(
        config,
        config_id="reference-cancel",
        config_ref="config://render/reference-cancel",
        quality={"samples": "3"},
    )
    cancel_request = replace(request, config=cancel_config)
    validate = reference.validateOutput

    def cancel_after_decode(
        payload: bytes, output_request: RenderRequest, pass_id: str = "beauty"
    ) -> tuple[int, int, tuple[str, ...]]:
        result = validate(payload, output_request, pass_id)
        reference.cancel(
            env.access,
            env.attempt,
            cancel_request,
            idempotency_key="late-cancel",
        )
        return result

    monkeypatch.setattr(reference, "validateOutput", cancel_after_decode)
    with pytest.raises(RenderContractError, match="fenced before publication"):
        reference.renderFrame(
            env.access,
            env.attempt,
            cancel_request,
            scene_artifact_ref=env.snapshot_artifact_ref,
            root_ref=env.root_ref,
            working_directory="candidate",
            idempotency_key="late-result",
        )
    with pytest.raises(RenderContractError, match="cancelled before launch"):
        ReferenceRendererAdapter(
            env.database, env.objects, identity=env.identity
        ).renderFrame(
            env.access,
            env.attempt,
            cancel_request,
            scene_artifact_ref=env.snapshot_artifact_ref,
            root_ref=env.root_ref,
            working_directory="candidate",
            idempotency_key="late-result-retry",
        )
@pytest.mark.parametrize("pass_id", ("z", "normal"))
def test_blender_5_exports_data_passes_without_image_layers(
    tmp_path: Path,
    pass_id: str,
) -> None:
    import json
    import subprocess

    output_path = tmp_path / f"{pass_id}.png"
    config_path = tmp_path / f"{pass_id}.json"
    config_path.write_text(json.dumps({
        "camera": {
            "materialization": "CREATE_EXACT",
            "object": "MiniTZCamera",
            "ref": "camera://render/blender-5-pass",
            "settings": {
                "clip_end": "1000.0",
                "clip_start": "0.1",
                "lens_mm": "50.0",
                "ortho_scale": "10.0",
                "projection": "PERSP",
                "sensor_width_mm": "36.0",
            },
            "settings_sha256": hashlib.sha256(b"blender-5-pass").hexdigest(),
            "transform": [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 5.0,
                0.0, 0.0, 0.0, 1.0,
            ],
        },
        "channels": ["R", "G", "B", "A"],
        "device": {"backend": "CPU", "device_ids": ["CPU"]},
        "dimensions": [8, 8],
        "frame": 1,
        "kind": "preview",
        "output_path": str(output_path),
        "pass_id": pass_id,
        "quality": {"samples": "1"},
    }, sort_keys=True), encoding="utf-8")
    driver = Path(__file__).parents[1] / "src/minitz_os/engine/_blender_render_driver.py"
    completed = subprocess.run(
        (
            "/usr/bin/blender",
            "--background",
            "--factory-startup",
            "--python",
            str(driver),
            "--",
            str(config_path),
        ),
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
        timeout=90.0,
    )
    assert "MINITZ_RENDER=" in completed.stdout, (
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert output_path.is_file()
    assert _png_dimensions(output_path.read_bytes()) == (8, 8, 4)
