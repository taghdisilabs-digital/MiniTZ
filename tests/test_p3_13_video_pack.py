from __future__ import annotations

from dataclasses import replace

import pytest

from minitz_os.engine.production_pack import ProductionPackRef
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.video_pack import (
    AudioTrackBinding,
    VideoArtifactContentRef,
    VideoClip,
    VideoContractError,
    VideoEdit,
    VideoEffect,
    VideoFrameRef,
    VideoFrameSequenceManifest,
    VideoOutputRef,
    VideoSpecification,
    VideoTimeline,
    VideoTransition,
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


def test_timeline_digest_binds_complete_edit_transition_and_effect_semantics() -> None:
    project_ref = ProjectRef.new()
    source = _artifact(project_ref, "source", "a" * 64)
    clip = VideoClip(project_ref, source, 0.0, 2.0, 0.0, 2.0, "1/1000")
    edit = VideoEdit(
        "edit://video/main/1", clip, "trim", {"mode": "exact"}
    )
    transition = VideoTransition(
        "transition://video/crossfade/1", 0.75, 0.25, {"curve": "linear"}
    )
    effect = VideoEffect(
        "effect://video/color/1", "1.2.3", {"strength": "0.5"}
    )
    timeline = VideoTimeline(
        project_ref,
        "timeline://video/semantic/v1",
        "1.0.0",
        (edit,),
        (transition,),
        (effect,),
        {"cut": "exact"},
        (clip,),
        (),
        (),
        (),
        (),
        (),
        "1/1000",
        {"role": "video.composite"},
    )

    assert timeline.payload()["edits"] == [
        {
            "edit_ref": "edit://video/main/1",
            "clip": clip.payload(),
            "operation": "trim",
            "parameters": {"mode": "exact"},
        }
    ]
    assert timeline.payload()["transitions"] == [
        {
            "transition_ref": "transition://video/crossfade/1",
            "at": 0.75,
            "duration": 0.25,
            "parameters": {"curve": "linear"},
        }
    ]
    assert timeline.payload()["effects"] == [
        {
            "effect_ref": "effect://video/color/1",
            "version": "1.2.3",
            "parameters": {"strength": "0.5"},
        }
    ]
    mutations = (
        replace(timeline, edits=(replace(edit, operation="cut"),)),
        replace(timeline, edits=(replace(edit, parameters={"mode": "nearest"}),)),
        replace(timeline, transitions=(replace(transition, at=1.0),)),
        replace(timeline, transitions=(replace(transition, duration=0.5),)),
        replace(
            timeline,
            transitions=(replace(transition, parameters={"curve": "ease-in"}),),
        ),
        replace(timeline, effects=(replace(effect, version="1.2.4"),)),
        replace(timeline, effects=(replace(effect, parameters={"strength": "1"}),)),
    )
    assert all(item.timeline_digest != timeline.timeline_digest for item in mutations)


def test_timeline_rejects_unbound_reordered_and_duplicate_edit_references() -> None:
    project_ref = ProjectRef.new()
    first = VideoClip(
        project_ref,
        _artifact(project_ref, "source-a", "a" * 64),
        0.0,
        1.0,
        0.0,
        1.0,
        "1/1000",
    )
    second = VideoClip(
        project_ref,
        _artifact(project_ref, "source-b", "b" * 64),
        0.0,
        1.0,
        1.0,
        2.0,
        "1/1000",
    )
    first_edit = VideoEdit("edit://video/first/1", first, "trim", {})
    second_edit = VideoEdit("edit://video/second/1", second, "trim", {})
    arguments = (
        project_ref,
        "timeline://video/bindings/v1",
        "1.0.0",
    )

    with pytest.raises(VideoContractError, match="edit.*clip|clip.*edit"):
        VideoTimeline(
            *arguments,
            (replace(first_edit, clip=second),),
            (),
            (),
            {},
            (first,),
            timebase="1/1000",
        )
    with pytest.raises(VideoContractError, match="edit.*clip|clip.*edit|order"):
        VideoTimeline(
            *arguments,
            (second_edit, first_edit),
            (),
            (),
            {},
            (first, second),
            timebase="1/1000",
        )
    with pytest.raises(VideoContractError, match="duplicate.*edit|edit.*duplicate"):
        VideoTimeline(
            *arguments,
            (first_edit, replace(second_edit, edit_ref=first_edit.edit_ref)),
            (),
            (),
            {},
            (first, second),
            timebase="1/1000",
        )


def test_frame_manifest_enforces_relative_cadence_and_unique_exact_identity() -> None:
    project_ref = ProjectRef.new()
    source = _artifact(project_ref, "source", "a" * 64)
    clip = VideoClip(project_ref, source, 2.0, 4.0, 2.0, 4.0, "1/1000")
    first_artifact = _artifact(project_ref, "frame-a", "b" * 64)
    second_artifact = _artifact(project_ref, "frame-b", "c" * 64)
    first = VideoFrameRef(project_ref, clip, 10, 2.0, first_artifact)
    second = VideoFrameRef(project_ref, clip, 11, 2.5, second_artifact)
    manifest = VideoFrameSequenceManifest.create(
        project_ref,
        "sequence://video/nonzero-source-start/v1",
        "1.0.0",
        "2/1",
        (first, second),
    )

    assert tuple(item.frame_index for item in manifest.frames) == (10, 11)
    with pytest.raises(VideoContractError, match="missing|contiguous|order"):
        VideoFrameSequenceManifest.create(
            project_ref,
            "sequence://video/missing/v1",
            "1.0.0",
            "2/1",
            (first, replace(second, frame_index=12)),
        )
    with pytest.raises(VideoContractError, match="timestamp|cadence|duplicate"):
        VideoFrameSequenceManifest.create(
            project_ref,
            "sequence://video/duplicate-time/v1",
            "1.0.0",
            "2/1",
            (first, replace(second, timestamp=2.0)),
        )
    with pytest.raises(VideoContractError, match="cadence|timestamp"):
        VideoFrameSequenceManifest.create(
            project_ref,
            "sequence://video/bad-cadence/v1",
            "1.0.0",
            "2/1",
            (first, replace(second, timestamp=2.25)),
        )
    with pytest.raises(VideoContractError, match="Artifact|artifact|identity|duplicate"):
        VideoFrameSequenceManifest.create(
            project_ref,
            "sequence://video/duplicate-artifact/v1",
            "1.0.0",
            "2/1",
            (first, replace(second, frame=first_artifact)),
        )
    duplicated_content = replace(
        second_artifact,
        content_ref=first_artifact.content_ref,
        content_sha256=first_artifact.content_sha256,
    )
    with pytest.raises(VideoContractError, match="Content|content|identity|duplicate"):
        VideoFrameSequenceManifest.create(
            project_ref,
            "sequence://video/duplicate-content/v1",
            "1.0.0",
            "2/1",
            (first, replace(second, frame=duplicated_content)),
        )
    other_clip = replace(clip, source=_artifact(project_ref, "other", "d" * 64))
    with pytest.raises(VideoContractError, match="clip|source|order"):
        VideoFrameSequenceManifest.create(
            project_ref,
            "sequence://video/mixed-source/v1",
            "1.0.0",
            "2/1",
            (first, replace(second, clip=other_clip)),
        )
    with pytest.raises(VideoContractError, match="manifest_digest"):
        replace(manifest, sequence_ref="sequence://video/nonzero-source-start/v2")
