"""Focused REAL FFmpeg video runtime qualification evidence."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from io import BytesIO
import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
from typing import Any, cast
import wave

import pytest

from biella.artifact import Artifact, ArtifactRef, ArtifactService
from biella.project import ProjectRef
from biella.scheduler import ScheduledDispatch, Scheduler
from biella.video_pack import (
    AudioTrackBinding,
    GameVideoHandoffBinding,
    SubtitleTrackBinding,
    VideoArtifactContentRef,
    VideoClip,
    VideoContractError,
    VideoSpecification,
    VideoTimeline,
)


def _runtime() -> Any:
    return importlib.import_module("biella.video_tool")


def _support() -> Any:
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location("p3_13_video_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _environment(tmp_path: Path) -> Any:
    values = cast(tuple[Any, ...], _support()._environments(tmp_path, count=1))
    return values[0]


def _dispatch(environment: Any) -> ScheduledDispatch:
    allocation = Scheduler(environment.database).get_allocation(
        environment.access, environment.allocation_ref
    )
    return ScheduledDispatch(allocation, environment.attempt)


def _fixture_mp4(*, seconds: float = 0.8, rate: int = 25) -> bytes:
    completed = subprocess.run(
        (
            "/usr/bin/ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=160x90:rate={rate}",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=660:sample_rate=48000",
            "-t",
            f"{seconds:.6f}",
            "-map_metadata",
            "-1",
            "-codec:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-color_range",
            "tv",
            "-codec:a",
            "aac",
            "-ar",
            "48000",
            "-threads",
            "1",
            "-movflags",
            "+frag_keyframe+empty_moov+default_base_moof",
            "-f",
            "mp4",
            "pipe:1",
        ),
        capture_output=True,
        check=True,
    )
    assert completed.stdout
    return completed.stdout


def _wav(*, seconds: float = 0.4, rate: int = 48_000) -> bytes:
    frames = round(seconds * rate)
    samples = [round(8_000 * math.sin(2.0 * math.pi * 440.0 * frame / rate)) for frame in range(frames)]
    output = BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return output.getvalue()


def _source(
    environment: Any,
    payload: bytes,
    *,
    media_type: str,
    role: str,
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


def _artifact_ref(value: str, project_ref: ProjectRef) -> ArtifactRef:
    parts = value.rsplit("/", 2)
    assert len(parts) == 3
    return ArtifactRef(project_ref, parts[1], int(parts[2]))


def _read_output(environment: Any, output: Any) -> tuple[Artifact, bytes]:
    artifact = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(output.output.artifact_ref, environment.access.project_ref),
    )
    assert artifact.content_ref is not None
    return artifact, environment.objects.read(artifact.content_ref)


def _tool(environment: Any, dispatch: ScheduledDispatch) -> Any:
    return _runtime().DeterministicVideoTool(
        environment.database,
        environment.objects,
        access=environment.access,
        dispatch=dispatch,
        root_ref=environment.root_ref,
        working_directory="candidate",
    )


def _specification(
    environment: Any,
    tool: Any,
    source: VideoArtifactContentRef,
    *,
    video_id: str,
    operation: str,
    start: float = 0.0,
    duration: float = 0.8,
    audio_tracks: tuple[AudioTrackBinding, ...] = (),
    subtitle_tracks: tuple[SubtitleTrackBinding, ...] = (),
    audio_policy: Mapping[str, str] | None = None,
    subtitle_policy: Mapping[str, str] | None = None,
    config: Mapping[str, str] | None = None,
    role: str = "video.export",
) -> VideoSpecification:
    project_ref = environment.access.project_ref
    output_contract = {
        "role": role,
        **({"cache_only": "true"} if role == "video.proxy" else {}),
    }
    clip = VideoClip(
        project_ref,
        source,
        start,
        start + duration,
        0.0,
        duration,
        "1/1000",
    )
    timeline = VideoTimeline(
        project_ref,
        f"timeline://video/{video_id}/v1",
        "1.0.0",
        (),
        (),
        (),
        {"cut": "exact", "timebase": "1/1000"},
        clips=(clip,),
        image_sources=(),
        render_sequences=(),
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
        track_order=tuple(f"audio:{index}" for index in range(len(audio_tracks)))
        + tuple(f"subtitle:{index}" for index in range(len(subtitle_tracks))),
        timebase="1/1000",
        output_contract=output_contract,
    )
    return VideoSpecification.create(
        project_ref=project_ref,
        video_id=video_id,
        operation=operation,
        sources=(source,),
        image_sources=(),
        render_sequences=(),
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
        timeline=timeline,
        time_start=start,
        time_end=start + duration,
        duration=duration,
        timebase="1/1000",
        fps_policy="conform",
        target_fps="25/1",
        width=160,
        height=90,
        pixel_format="yuv420p",
        color_ref="color://rec709/v1",
        hdr_ref=None,
        media_type="video/mp4",
        container="mp4",
        codec="h264",
        profile="high",
        bitrate="500000",
        quality_ref="quality://video/reference/v1",
        missing_frame_policy="fail",
        audio_policy={} if audio_policy is None else dict(audio_policy),
        subtitle_policy={} if subtitle_policy is None else dict(subtitle_policy),
        output_contract=output_contract,
        tool_ref=tool.tool_ref,
        runtime_ref=tool.runtime_ref,
        model_ref=None,
        seed=0,
        config={"preset": "medium", "scale_filter": "bicubic"}
        if config is None
        else dict(config),
        validator_ref=tool.validator_ref,
    )


def test_full_mp4_probe_and_decode_rejects_truncated_corruption(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    tool = _tool(environment, _dispatch(environment))
    payload = _fixture_mp4(seconds=0.6)
    source = _source(
        environment, payload, media_type="video/mp4", role="video.source"
    )

    inspection = tool.inspect(source, "validator://video/qualification/v1")

    assert inspection.container == "mp4" and inspection.codec == "h264"
    assert inspection.width == 160 and inspection.height == 90
    assert inspection.fps == "25/1" and inspection.frame_count == 15
    assert inspection.pixel_format == "yuv420p"
    assert inspection.color_space == "bt709"
    assert inspection.content_sha256 == hashlib.sha256(payload).hexdigest()
    assert set(inspection.decoded_sha256) == {
        item.index for item in inspection.streams if item.codec_type in {"audio", "video"}
    }
    assert {"duration", "format_name", "size"} <= set(inspection.format_evidence)
    evidence = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(inspection.inspection_ref, environment.access.project_ref),
    )
    assert evidence.role == "video.validation-evidence"
    assert evidence.content_ref is not None
    assert evidence.content_ref.digest == inspection.inspection_sha256

    corrupted = payload[: max(64, len(payload) // 2)]
    with pytest.raises(VideoContractError, match="probe|decode|corrupt|process|stream"):
        tool.validate(corrupted, expected_media_type="video/mp4")
    with pytest.raises(VideoContractError, match="media|container|probe|process"):
        tool.validate(b"not an mp4", expected_media_type="video/mp4")


def test_exact_trim_and_reference_mux_preserve_audio_subtitle_and_provenance(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path)
    dispatch = _dispatch(environment)
    tool = _tool(environment, dispatch)
    video_payload = _fixture_mp4()
    video = _source(
        environment, video_payload, media_type="video/mp4", role="video.source"
    )
    trim = _specification(
        environment,
        tool,
        video,
        video_id="exact-trim",
        operation="trim",
        start=0.12,
        duration=0.4,
        role="video.clip",
    )

    trimmed_output = tool.execute(environment.access, environment.attempt, trim)
    trimmed_artifact, trimmed_payload = _read_output(environment, trimmed_output)
    trimmed = tool.validate(trimmed_payload, expected_media_type="video/mp4")

    assert trimmed_artifact.role == "video.clip"
    assert trimmed.duration == pytest.approx(0.4, abs=1 / 25)
    assert trimmed.video_stream.time_base == "1/1000"
    assert trimmed.fps == "25/1" and trimmed.video_stream.width == 160
    original = ArtifactService(environment.database).get_artifact(
        environment.access, _artifact_ref(video.artifact_ref, environment.access.project_ref)
    )
    assert original.content_ref is not None
    assert environment.objects.read(original.content_ref) == video_payload

    audio = _source(
        environment, _wav(), media_type="audio/wav", role="audio.source"
    )
    subtitle_payload = (
        b"1\n00:00:00,100 --> 00:00:00,300\nBound subtitle\n\n"
    )
    subtitle = _source(
        environment,
        subtitle_payload,
        media_type="application/x-subrip",
        role="video.subtitle-track",
    )
    audio_binding = AudioTrackBinding(
        environment.access.project_ref,
        audio,
        0.2,
        0.6,
        "preserve",
        "resample:48000",
        "sync://video/reference/audio/v1",
    )
    subtitle_binding = SubtitleTrackBinding(
        environment.access.project_ref, subtitle, "eng", "none", "stream"
    )
    mux = _specification(
        environment,
        tool,
        video,
        video_id="reference-mux",
        operation="mux",
        audio_tracks=(audio_binding,),
        subtitle_tracks=(subtitle_binding,),
        audio_policy={"bitrate": "128000", "codec": "aac", "source_start.0": "0"},
        subtitle_policy={"codec": "mov_text"},
    )

    rendered = tool.render(environment.access, environment.attempt, mux)
    mux_artifact, mux_payload = _read_output(environment, rendered.output)
    qualified = tool.validate(mux_payload, expected_media_type="video/mp4")
    reference = subprocess.run(
        (
            "/usr/bin/ffprobe",
            "-hide_banner",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            "pipe:0",
        ),
        input=mux_payload,
        capture_output=True,
        check=True,
    )
    reference_payload = cast(dict[str, object], json.loads(reference.stdout))
    reference_streams = cast(list[dict[str, object]], reference_payload["streams"])

    assert mux_artifact.role == "video.export"
    assert [item["codec_type"] for item in reference_streams] == [
        "video",
        "audio",
        "subtitle",
    ]
    assert [item["codec_name"] for item in reference_streams] == ["h264", "aac", "mov_text"]
    assert len(tuple(item for item in qualified.streams if item.codec_type == "audio")) == 1
    assert len(tuple(item for item in qualified.streams if item.codec_type == "subtitle")) == 1
    audio_stream = next(item for item in qualified.streams if item.codec_type == "audio")
    assert audio_stream.sample_rate == 48_000
    assert audio_stream.start_time == pytest.approx(0.0, abs=0.03)
    if audio_stream.duration is not None:
        assert audio_stream.duration == pytest.approx(0.6, abs=0.08)
    decoded_audio = subprocess.run(
        (
            "/usr/bin/ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-i",
            "pipe:0",
            "-map",
            "0:a:0",
            "-codec:a",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-f",
            "s16le",
            "pipe:1",
        ),
        input=mux_payload,
        capture_output=True,
        check=True,
    ).stdout
    samples = struct.unpack(f"<{len(decoded_audio) // 2}h", decoded_audio)
    audible = tuple(index for index, sample in enumerate(samples) if abs(sample) > 500)
    assert audible[0] / 48_000 == pytest.approx(0.2, abs=0.03)
    assert audible[-1] / 48_000 == pytest.approx(0.6, abs=0.03)
    subtitle_stream = next(item for item in qualified.streams if item.codec_type == "subtitle")
    assert subtitle_stream.tags["language"] == "eng"
    assert rendered.timeline.project_ref == environment.access.project_ref
    timeline_artifact = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(rendered.timeline.artifact_ref, environment.access.project_ref),
    )
    session_artifact = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(rendered.session.session.artifact_ref, environment.access.project_ref),
    )
    assert timeline_artifact.role == "video.timeline"
    assert session_artifact.role == "video.session"
    derivation = ArtifactService(environment.database).list_derivations(
        environment.access, mux_artifact.artifact_ref
    )[0]
    provenance = {item.value for item in derivation.source_artifact_refs}
    assert {video.artifact_ref, audio.artifact_ref, subtitle.artifact_ref, rendered.timeline.artifact_ref} <= provenance
    target = _source(
        environment,
        b'{"target":"game-video"}',
        media_type="application/json",
        role="video.validation-evidence",
    )
    handoff = tool.bind_game_handoff(
        rendered.output, target, "integration://game/reference/video/v1"
    )
    assert isinstance(handoff, GameVideoHandoffBinding)
    assert handoff.output == rendered.output and handoff.target == target


def test_real_encoder_failure_and_stale_worker_preserve_sources_then_recover(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path)
    dispatch = _dispatch(environment)
    tool = _tool(environment, dispatch)
    source_payload = _fixture_mp4(seconds=0.4)
    source = _source(
        environment, source_payload, media_type="video/mp4", role="video.source"
    )
    failing = _specification(
        environment,
        tool,
        source,
        video_id="encoder-failure",
        operation="encode",
        duration=0.4,
        config={"preset": "not-a-real-x264-preset", "scale_filter": "bicubic"},
    )

    with pytest.raises(VideoContractError, match="process|encoder|failed"):
        tool.execute(environment.access, environment.attempt, failing)

    source_artifact = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(source.artifact_ref, environment.access.project_ref),
    )
    assert source_artifact.content_ref is not None
    assert environment.objects.read(source_artifact.content_ref) == source_payload
    with sqlite3.connect(environment.database) as connection:
        timeline_count = cast(
            int,
            connection.execute(
                "SELECT COUNT(*) FROM artifact_revisions WHERE project_id=? AND role='video.timeline'",
                (environment.access.project_ref.value,),
            ).fetchone()[0],
        )
        process_count = cast(
            int,
            connection.execute(
                "SELECT COUNT(*) FROM artifact_revisions WHERE project_id=? AND role='process.execution.result'",
                (environment.access.project_ref.value,),
            ).fetchone()[0],
        )
    assert timeline_count >= 1 and process_count >= 1

    recovered = _specification(
        environment,
        tool,
        source,
        video_id="encoder-recovery",
        operation="encode",
        duration=0.4,
    )
    output = tool.execute(environment.access, environment.attempt, recovered)
    _, output_payload = _read_output(environment, output)
    assert tool.validate(output_payload, expected_media_type="video/mp4").duration == pytest.approx(
        0.4, abs=1 / 25
    )

    stale = ScheduledDispatch(
        replace(
            dispatch.allocation,
            status="RESERVED",
            dispatch_idempotency_key=None,
            node_attempt_id=None,
            node_attempt_fence=None,
        ),
        dispatch.node_attempt,
    )
    with pytest.raises(VideoContractError, match="dispatch|allocation|stale"):
        tool.execute_dispatched(recovered, stale)
    foreign = replace(source, project_ref=ProjectRef.new())
    with pytest.raises(VideoContractError, match="Project"):
        tool.inspect(foreign, "validator://video/qualification/v1")
