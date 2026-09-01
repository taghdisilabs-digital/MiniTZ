"""Focused REAL video-frame pipeline evidence."""
from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier, Event, Lock
from typing import Any, cast

from PIL import Image
import pytest

from biella.artifact import Artifact, ArtifactRef, ArtifactService
from biella.image_pack import (
    ImageArtifactContentRef,
    ImageContractError,
    ImageOperation,
    ImageOutputRef,
    ImageSpecification,
)
from biella.render_pack import (
    RenderConfig,
    RenderFrameRef,
    RenderRequest,
    RenderSequenceManifest,
)
from biella.scheduler import ScheduledDispatch, Scheduler
from biella.video_frame_pipeline import (
    VideoFramePipeline,
    VideoFramePipelineError,
    VideoFrameRequest,
)
from biella.video_pack import VideoArtifactContentRef, VideoClip


def _support() -> Any:
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location("p3_13_frame_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _environments(tmp_path: Path, count: int = 1) -> tuple[Any, ...]:
    return cast(tuple[Any, ...], _support()._environments(tmp_path, count=count))


def _dispatch(environment: Any) -> ScheduledDispatch:
    allocation = Scheduler(environment.database).get_allocation(
        environment.access, environment.allocation_ref
    )
    return ScheduledDispatch(allocation, environment.attempt)


def _pipeline(environment: Any) -> VideoFramePipeline:
    return VideoFramePipeline(
        environment.database,
        environment.objects,
        access=environment.access,
        root_ref=environment.root_ref,
        working_directory="candidate",
    )


def _managed_results(environment: Any) -> tuple[dict[str, Any], ...]:
    connection = sqlite3.connect(environment.database)
    try:
        rows = connection.execute(
            "SELECT result_json FROM managed_process_results ORDER BY call_id"
        ).fetchall()
    finally:
        connection.close()
    return tuple(cast(dict[str, Any], json.loads(str(row[0]))) for row in rows)


def _artifact_ref(project_ref: Any, value: str) -> ArtifactRef:
    parts = value.rsplit("/", 2)
    assert len(parts) == 3
    return ArtifactRef(project_ref, parts[1], int(parts[2]))


def _image_bytes(
    color: tuple[int, int, int], size: tuple[int, int] = (4, 3)
) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


def _video_bytes(tmp_path: Path) -> bytes:
    frames = tmp_path / "frames"
    frames.mkdir(parents=True)
    for index, color in enumerate(((255, 0, 0), (0, 255, 0), (0, 0, 255))):
        Image.new("RGB", (4, 3), color).save(frames / f"frame-{index:03d}.png")
    output = tmp_path / "source.mkv"
    subprocess.run(
        (
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-framerate",
            "2",
            "-i",
            str(frames / "frame-%03d.png"),
            "-c:v",
            "ffv1",
            "-pix_fmt",
            "rgb24",
            str(output),
        ),
        check=True,
    )
    return output.read_bytes()


def _source(
    environment: Any,
    payload: bytes,
    *,
    role: str = "video.source",
    media_type: str = "video/x-matroska",
) -> VideoArtifactContentRef:
    content = environment.objects.put(payload, media_type=media_type)
    artifact = ArtifactService(environment.database).create_artifact(
        environment.access,
        project_ref=environment.access.project_ref,
        role=role,
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="video.fixture",
        metadata={"media_type": media_type},
    )
    return VideoArtifactContentRef(
        environment.access.project_ref,
        artifact.artifact_ref.value,
        content.value,
        content.digest,
    )


def _image_source(
    environment: Any,
    payload: bytes,
    *,
    role: str = "image.source",
) -> ImageArtifactContentRef:
    content = environment.objects.put(payload, media_type="image/png")
    artifact = ArtifactService(environment.database).create_artifact(
        environment.access,
        project_ref=environment.access.project_ref,
        role=role,
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="image.fixture",
        metadata={"media_type": "image/png"},
    )
    return ImageArtifactContentRef(
        environment.access.project_ref,
        artifact.artifact_ref.value,
        content.value,
        content.digest,
    )


def _clip(environment: Any, source: VideoArtifactContentRef) -> VideoClip:
    return VideoClip(
        environment.access.project_ref,
        source,
        0.0,
        1.5,
        0.0,
        1.5,
        "1/1000",
    )


def _requests() -> tuple[VideoFrameRequest, ...]:
    return tuple(
        VideoFrameRequest(index, index / 2.0, index) for index in range(3)
    )


def _read_artifact(environment: Any, value: str) -> tuple[Artifact, bytes]:
    artifact = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(environment.access.project_ref, value),
    )
    assert artifact.content_ref is not None
    return artifact, environment.objects.read(artifact.content_ref)


def _specification(
    pipeline: VideoFramePipeline,
    environment: Any,
    source: ImageArtifactContentRef,
    index: int,
) -> ImageSpecification:
    operation = ImageOperation(
        "resize",
        "recipe://video/frame-process/v1",
        hashlib.sha256(f"resize-{index}".encode()).hexdigest(),
        {"interpolation": "nearest"},
    )
    return ImageSpecification.create(
        environment.access.project_ref,
        f"processed-{index}",
        (source,),
        (),
        operation,
        2,
        2,
        "PNG",
        ("R", "G", "B"),
        8,
        "profile://image/unspecified",
        "none",
        {"exif": "strip", "icc_profile": "strip", "text": "strip"},
        "model://image/deterministic",
        "1.0.0",
        pipeline.image_tool.runtime_ref,
        0,
        {},
        None,
        None,
        None,
        "validator://video/frame-process/v1",
        {"role": "image.edited"},
    )


def test_real_extraction_publishes_ordered_image_frames_and_durable_evidence(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path / "runtime")[0]
    source = _source(environment, _video_bytes(tmp_path / "media"))
    pipeline = _pipeline(environment)

    result = pipeline.extract_sequence(
        _clip(environment, source),
        _requests(),
        sequence_ref="sequence://video/extracted/v1",
        version="1.0.0",
        fps="2",
        dispatch=_dispatch(environment),
    )

    assert tuple(item.sequence_index for item in result.evidence) == (0, 1, 2)
    assert tuple(item.actual_decoder_frame_index for item in result.evidence) == (0, 1, 2)
    assert tuple(item.actual_decoder_timestamp for item in result.evidence) == (0.0, 0.5, 1.0)
    assert all(item.source.content_sha256 == source.content_sha256 for item in result.evidence)
    assert all("ffmpeg version" in item.decoder_tool_version.lower() for item in result.evidence)
    assert tuple(frame.frame_index for frame in result.manifest.frames) == (0, 1, 2)
    for item in result.evidence:
        artifact, payload = _read_artifact(environment, item.frame.artifact_ref)
        assert artifact.role == "image.source"
        with Image.open(BytesIO(payload)) as image:
            assert image.size == (4, 3) and image.mode == "RGB"
    durable, payload = _read_artifact(environment, result.artifact.artifact_ref)
    report = json.loads(payload)
    assert durable.role == "video.frame-sequence"
    assert report["manifest_digest"] == result.manifest.manifest_digest
    assert [item["sequence_index"] for item in report["ordered_frames"]] == [0, 1, 2]
    first_artifact, _ = _read_artifact(environment, result.evidence[0].frame.artifact_ref)
    source_ref = _artifact_ref(environment.access.project_ref, source.artifact_ref)
    process_refs = tuple(
        item for item in first_artifact.source_artifact_refs if item != source_ref
    )
    assert len(process_refs) == 2
    managed_results = _managed_results(environment)
    for process_ref in process_refs:
        process_artifact = ArtifactService(environment.database).get_artifact(
            environment.access, process_ref
        )
        assert process_artifact.content_ref in first_artifact.source_content_refs
        assert process_artifact.content_ref is not None
        process_result = next(
            item for item in managed_results if item["artifact_ref"] == process_ref.value
        )
        request_digest = process_result["request_ref"]["digest"]
        request_ref = next(
            item for item in process_artifact.source_content_refs if item.digest == request_digest
        )
        request = json.loads(environment.objects.read(request_ref))
        assert request["resource_allocation_ref"] == _dispatch(environment).allocation.allocation_ref.value
        assert request["descriptor_content_refs"]["input"]["digest"] == source.content_sha256
        assert len(request["expected_executable_sha256"]) == 64
    managed_count = len(_managed_results(environment))
    replayed = _pipeline(environment).extract_frame(
        source,
        VideoFrameRequest(0, requested_timestamp=0.0, requested_frame_index=0),
        _dispatch(environment),
    )
    assert replayed.frame.content_sha256 == result.evidence[0].frame.content_sha256
    assert len(_managed_results(environment)) == managed_count


def test_missing_duplicate_out_of_order_corrupt_and_mismatched_frames_fail_closed(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path / "runtime")[0]
    pipeline = _pipeline(environment)
    source = _source(environment, _video_bytes(tmp_path / "media"))
    clip = _clip(environment, source)
    dispatch = _dispatch(environment)

    with pytest.raises(VideoFramePipelineError, match="missing|out of order"):
        pipeline.extract_sequence(
            clip,
            (VideoFrameRequest(1, requested_frame_index=0),),
            sequence_ref="sequence://video/bad-order/v1",
            version="1",
            fps="2",
            dispatch=dispatch,
        )
    with pytest.raises(VideoFramePipelineError, match="missing"):
        pipeline.extract_sequence(
            clip,
            (VideoFrameRequest(0, requested_frame_index=99),),
            sequence_ref="sequence://video/missing/v1",
            version="1",
            fps="2",
            dispatch=dispatch,
        )
    with pytest.raises(VideoFramePipelineError, match="different|duplicate"):
        pipeline.extract_sequence(
            clip,
            (
                VideoFrameRequest(0, requested_timestamp=0.0),
                VideoFrameRequest(1, requested_timestamp=0.01),
            ),
            sequence_ref="sequence://video/duplicate/v1",
            version="1",
            fps="2",
            dispatch=dispatch,
        )
    corrupt = _source(environment, b"not-video")
    with pytest.raises(VideoFramePipelineError, match="failed|missing"):
        pipeline.extract_sequence(
            _clip(environment, corrupt),
            (VideoFrameRequest(0, requested_frame_index=0),),
            sequence_ref="sequence://video/corrupt/v1",
            version="1",
            fps="2",
            dispatch=dispatch,
        )
    assert any(item["status"] == "FAILED" for item in _managed_results(environment))
    first = _image_source(environment, _image_bytes((10, 20, 30), (4, 3)))
    second = _image_source(environment, _image_bytes((40, 50, 60), (2, 2)))
    with pytest.raises(VideoFramePipelineError, match="dimensions|mismatch"):
        pipeline.consume_image_sequence(
            clip,
            (first, second),
            (0.0, 0.5),
            sequence_ref="sequence://video/mismatch/v1",
            version="1",
            fps="2",
            dispatch=dispatch,
        )
    with pytest.raises(VideoFramePipelineError, match="duplicate"):
        pipeline.consume_image_sequence(
            clip,
            (first, first),
            (0.0, 0.5),
            sequence_ref="sequence://video/duplicate-images/v1",
            version="1",
            fps="2",
            dispatch=dispatch,
        )


def test_existing_image_and_render_sequences_keep_exact_source_order(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path / "runtime")[0]
    pipeline = _pipeline(environment)
    source = _source(environment, _video_bytes(tmp_path / "media"))
    clip = _clip(environment, source)
    images = tuple(
        _image_source(environment, _image_bytes(color), role="render.frame")
        for color in ((1, 2, 3), (4, 5, 6), (7, 8, 9))
    )
    consumed = pipeline.consume_image_sequence(
        clip,
        images,
        (0.0, 0.5, 1.0),
        sequence_ref="sequence://video/images/v1",
        version="1",
        fps="2",
        dispatch=_dispatch(environment),
        source_frame_indices=(10, 11, 12),
    )
    assert tuple(item.actual_decoder_frame_index for item in consumed.evidence) == (10, 11, 12)
    config = RenderConfig(
        environment.access.project_ref,
        "preview",
        "render-config://video/preview/v1",
        hashlib.sha256(b"render-config").hexdigest(),
        "preview",
        (4, 3),
        "image/png",
        ("R", "G", "B"),
        ("beauty",),
        {},
        {},
        {},
        10.0,
        True,
    )
    request = RenderRequest(
        environment.access.project_ref,
        "task://video/render/1",
        "run://video/render",
        "node://video/render",
        source.artifact_ref,
        source.content_sha256,
        "camera://video/main",
        (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0),
        "lens://video/main",
        hashlib.sha256(b"camera").hexdigest(),
        10,
        12,
        0.0,
        "render.sequence",
        config,
        "renderer://video/fixture",
        "runtime://render/fixture",
        "executor://render/fixture",
        (),
    )
    rendered = tuple(
        RenderFrameRef.from_request(
            replace(request, frame_start=frame, frame_end=frame),
            image.artifact_ref,
            image.content_sha256,
            True,
        )
        for frame, image in zip((10, 11, 12), images, strict=True)
    )
    manifest = RenderSequenceManifest(
        environment.access.project_ref,
        request,
        (10, 11, 12),
        rendered,
        (),
        hashlib.sha256(b"render-manifest").hexdigest(),
    )
    result = pipeline.consume_render_sequence(
        clip,
        manifest,
        sequence_ref="sequence://video/render/v1",
        version="1",
        fps="2",
        dispatch=_dispatch(environment),
    )
    assert tuple(item.actual_decoder_frame_index for item in result.evidence) == (10, 11, 12)
    bad = replace(manifest, completed_frames=(rendered[1], rendered[0], rendered[2]))
    with pytest.raises(VideoFramePipelineError, match="out of order"):
        pipeline.consume_render_sequence(
            clip,
            bad,
            sequence_ref="sequence://video/render-bad/v1",
            version="1",
            fps="2",
            dispatch=_dispatch(environment),
        )


def test_distinct_existing_dispatches_process_concurrently_but_publish_media_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator, first, second, third = _environments(tmp_path / "runtime", count=4)
    pipeline = _pipeline(coordinator)
    source = _source(coordinator, _video_bytes(tmp_path / "media"))
    extracted = pipeline.extract_sequence(
        _clip(coordinator, source),
        _requests(),
        sequence_ref="sequence://video/raw/v1",
        version="1",
        fps="2",
        dispatch=_dispatch(coordinator),
    )
    specifications = {
        index: _specification(pipeline, coordinator, item.frame, index)
        for index, item in enumerate(extracted.evidence)
    }
    dispatches = {
        0: _dispatch(first),
        1: _dispatch(second),
        2: _dispatch(third),
    }
    real_execute = pipeline.image_tool.execute_dispatched
    barrier = Barrier(3)
    lock = Lock()
    active = 0
    maximum_active = 0

    def observed(
        specification: ImageSpecification, dispatch: ScheduledDispatch
    ) -> ImageOutputRef:
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            barrier.wait(timeout=5.0)
            return real_execute(specification, dispatch)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(pipeline.image_tool, "execute_dispatched", observed)
    processed = pipeline.process_sequence(
        extracted,
        specifications,
        dispatches,
        sequence_ref="sequence://video/processed/v1",
        version="2",
        coordinator_dispatch=_dispatch(coordinator),
    )

    assert maximum_active == 3
    assert tuple(item.sequence_index for item in processed.evidence) == (0, 1, 2)
    assert tuple(item.actual_decoder_frame_index for item in processed.evidence) == (0, 1, 2)
    assert tuple(item.processing[0].producer_attempt_id for item in processed.evidence) == (
        first.attempt.attempt_id,
        second.attempt.attempt_id,
        third.attempt.attempt_id,
    )
    assert tuple(frame.frame_index for frame in processed.manifest.frames) == (0, 1, 2)


def test_worker_failure_cancellation_and_stale_fence_publish_no_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator, first, second, third = _environments(tmp_path / "runtime", count=4)
    pipeline = _pipeline(coordinator)
    source = _source(coordinator, _video_bytes(tmp_path / "media"))
    clip = _clip(coordinator, source)
    extracted = pipeline.extract_sequence(
        clip,
        _requests(),
        sequence_ref="sequence://video/raw/v1",
        version="1",
        fps="2",
        dispatch=_dispatch(coordinator),
    )
    specifications = {
        index: _specification(pipeline, coordinator, item.frame, index)
        for index, item in enumerate(extracted.evidence)
    }
    dispatches = {0: _dispatch(first), 1: _dispatch(second), 2: _dispatch(third)}
    real_execute = pipeline.image_tool.execute_dispatched

    def fail_one(
        specification: ImageSpecification, dispatch: ScheduledDispatch
    ) -> ImageOutputRef:
        if specification.image_id == "processed-1":
            raise ImageContractError("injected worker failure")
        return real_execute(specification, dispatch)

    monkeypatch.setattr(pipeline.image_tool, "execute_dispatched", fail_one)
    with pytest.raises(VideoFramePipelineError, match="worker 1 failed"):
        pipeline.process_sequence(
            extracted,
            specifications,
            dispatches,
            sequence_ref="sequence://video/failed/v1",
            version="2",
            coordinator_dispatch=_dispatch(coordinator),
        )
    cancelled = Event()
    cancelled.set()
    with pytest.raises(VideoFramePipelineError, match="cancelled"):
        pipeline.extract_sequence(
            clip,
            _requests(),
            sequence_ref="sequence://video/cancelled/v1",
            version="1",
            fps="2",
            dispatch=_dispatch(first),
            cancellation=cancelled,
        )
    assert any(item["status"] == "CANCELLED" for item in _managed_results(coordinator))
    dispatch = _dispatch(coordinator)
    forged = ScheduledDispatch(
        replace(dispatch.allocation, node_attempt_fence=dispatch.node_attempt.fence + 1),
        replace(dispatch.node_attempt, fence=dispatch.node_attempt.fence + 1),
    )
    with pytest.raises(VideoFramePipelineError, match="current|stale"):
        pipeline.extract_frame(
            source,
            VideoFrameRequest(0, requested_frame_index=0),
            forged,
        )


def test_thumbnail_and_preview_publish_full_decode_and_source_evidence(
    tmp_path: Path,
) -> None:
    coordinator, thumbnail_worker, preview_worker = _environments(
        tmp_path / "runtime", count=3
    )
    pipeline = _pipeline(coordinator)
    source = _source(coordinator, _video_bytes(tmp_path / "media"))
    sequence = pipeline.extract_sequence(
        _clip(coordinator, source),
        _requests(),
        sequence_ref="sequence://video/raw/v1",
        version="1",
        fps="2",
        dispatch=_dispatch(coordinator),
    )

    thumbnail = pipeline.create_thumbnail(
        sequence,
        0,
        width=2,
        height=2,
        dispatch=_dispatch(thumbnail_worker),
        interpolation="nearest",
    )
    preview = pipeline.create_preview(
        sequence,
        2,
        width=3,
        height=2,
        dispatch=_dispatch(preview_worker),
        interpolation="nearest",
    )

    for derived, role, size in (
        (thumbnail, "video.thumbnail", (2, 2)),
        (preview, "video.preview", (3, 2)),
    ):
        artifact, payload = _read_artifact(coordinator, derived.artifact.artifact_ref)
        assert artifact.role == role
        with Image.open(BytesIO(payload)) as image:
            assert image.size == size and image.mode == "RGB"
        evidence_artifact, evidence_payload = _read_artifact(
            coordinator, derived.evidence_artifact.artifact_ref
        )
        report = json.loads(evidence_payload)
        assert evidence_artifact.role == "video.validation-evidence"
        assert report["source"]["content_sha256"] == source.content_sha256
        assert report["source_frame_evidence"]["actual_decoder_frame_identity"]
        assert report["decode"]["width"] == size[0]
        assert report["decode"]["height"] == size[1]
        assert report["producer_attempt_id"] == derived.producer_attempt_id
