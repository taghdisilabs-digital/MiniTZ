from __future__ import annotations

from dataclasses import replace

import pytest

from biella.production_pack import ProductionPackRef
from biella.project import ProjectRef
from biella.video_pack import (
    AudioTrackBinding,
    VideoArtifactContentRef,
    VideoClip,
    VideoContractError,
    VideoFrameRef,
    VideoFrameSequenceManifest,
    VideoOutputRef,
    VideoSpecification,
    VideoTimeline,
    video_production_pack,
)


CAPABILITIES = {
    "inspect", "import", "generate", "edit", "trim", "sequence", "compose",
    "frame_extract", "frame_process", "audio_sync", "subtitle", "transcode", "encode",
    "mux", "thumbnail", "preview", "export", "validate",
}
ATTEMPT = "natt_" + "c" * 32


def _artifact(project_ref: ProjectRef, name: str, digest: str) -> VideoArtifactContentRef:
    return VideoArtifactContentRef(project_ref, f"artifact://{project_ref.value}/{name}/1", f"content://video/{name}", digest)


def _specification(project_ref: ProjectRef) -> VideoSpecification:
    source = _artifact(project_ref, "source", "a" * 64)
    audio = AudioTrackBinding(project_ref, _artifact(project_ref, "audio", "b" * 64), 0.0, 2.0, "preserve", "preserve", "sync://video/audio/v1")
    clip = VideoClip(project_ref, source, 0.0, 2.0, 0.0, 2.0, "1/1000")
    timeline = VideoTimeline(project_ref, "timeline://video/main/v1", "1.0.0", (), (), (), {"cut": "exact"}, (clip,), (), (), (audio,), (), ("audio:0",), "1/1000", {"role": "video.generated"})
    return VideoSpecification.create(
        project_ref, "scene", "generate", (source,), (), (), (audio,), (), timeline,
        0.0, 2.0, 2.0, "1/1000", "preserve", None, 1920, 1080, "yuv420p",
        "color://rec709/v1", None, "video/mp4", "mp4", "h264", "high", "4500000",
        "quality://project/v1", "fail", {"audio_sync": "required"}, {"subtitle": "stream"},
        {"role": "video.generated"}, "tool://video/generic/v1", "runtime://video/generic/v1",
        None, 7, {"preset": "medium"}, "validator://video/generic/v1",
    )


def test_video_pack_registers_exact_contract_surface() -> None:
    pack = video_production_pack()
    assert pack.pack_ref == ProductionPackRef("video", "1.0.0")
    assert {item.capability_id for item in pack.capability_definitions} == {f"video.{name}" for name in CAPABILITIES}
    assert {"video.source", "video.clip", "video.timeline", "video.composite", "video.generated", "video.proxy", "video.frame-sequence", "video.preview", "video.export", "video.thumbnail", "video.subtitle-track", "video.validation-evidence", "video.session"} <= set(pack.artifact_roles)


def test_video_specification_and_actual_output_fail_closed() -> None:
    project_ref = ProjectRef.new()
    specification = _specification(project_ref)
    output = VideoOutputRef.create(project_ref, specification, _artifact(project_ref, "output", "d" * 64), 2.0, "30000/1001", 1920, 1080, "h264", "mp4", ATTEMPT, 1, "video.encode")
    assert output.specification_digest == specification.canonical_digest
    with pytest.raises(VideoContractError, match="canonical_digest"):
        replace(specification, codec="h265")
    with pytest.raises(VideoContractError, match="fps"):
        VideoSpecification.create(project_ref, "x", "edit", specification.sources, (), (), specification.audio_tracks, (), specification.timeline, 0.0, 1.0, 1.0, "1/1000", "conform", None, 1920, 1080, "yuv420p", "color://rec709/v1", None, "video/mp4", "mp4", "h264", "high", "4500000", "quality://project/v1", "fail", {}, {}, {"role": "video.generated"}, "tool://video/generic/v1", "runtime://video/generic/v1", None, 1, {}, "validator://video/generic/v1")
    with pytest.raises(VideoContractError, match="Project"):
        VideoSpecification.create(project_ref, "x", "edit", specification.sources, (), (), specification.audio_tracks, (), specification.timeline, 0.0, 1.0, 1.0, "1/1000", "preserve", None, 1920, 1080, "yuv420p", "color://rec709/v1", None, "video/mp4", "mp4", "h264", "high", "4500000", "quality://project/v1", "fail", {}, {}, {"role": "video.generated"}, "tool://video/generic/v1", "runtime://video/generic/v1", None, 1, {}, "validator://video/generic/v1", prompt=_artifact(ProjectRef.new(), "prompt", "e" * 64))


def test_ordered_frame_manifest_and_timeline_reject_duplicates_or_foreign_media() -> None:
    project_ref = ProjectRef.new()
    source = _artifact(project_ref, "source", "a" * 64)
    clip = VideoClip(project_ref, source, 0.0, 1.0, 0.0, 1.0, "1/1000")
    first = VideoFrameRef(project_ref, clip, 0, 0.0, _artifact(project_ref, "frame0", "b" * 64))
    second = VideoFrameRef(project_ref, clip, 1, 1 / 24, _artifact(project_ref, "frame1", "c" * 64))
    manifest = VideoFrameSequenceManifest.create(project_ref, "sequence://video/main/v1", "1.0.0", "24/1", (first, second))
    assert manifest.frames == (first, second)
    render_timeline = VideoTimeline(project_ref, "timeline://video/render/v1", "1.0.0", (), (), (), {}, (), (), (manifest,), (), (), (), "1/1000", {"role": "video.composite"})
    render_only = VideoSpecification.create(project_ref, "render", "sequence", (), (), (manifest,), (), (), render_timeline, 0.0, 1.0, 1.0, "1/1000", "preserve", None, 1920, 1080, "yuv420p", "color://rec709/v1", None, "video/mp4", "mp4", "h264", "high", "4500000", "quality://project/v1", "fail", {}, {}, {"role": "video.composite"}, "tool://video/generic/v1", "runtime://video/generic/v1", None, 1, {}, "validator://video/generic/v1")
    assert render_only.render_sequences == (manifest,)
    with pytest.raises(VideoContractError, match="ordered"):
        VideoFrameSequenceManifest.create(project_ref, "sequence://video/main/v1", "1.0.0", "24/1", (second, first))
    with pytest.raises(VideoContractError, match="Project"):
        VideoClip(ProjectRef.new(), source, 0.0, 1.0, 0.0, 1.0, "1/1000")
