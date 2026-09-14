"""Focused REAL deterministic audio runtime evidence."""
from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
from threading import Barrier, Lock
from typing import Any, cast
import wave

import pytest

from minitz_os.engine.artifact import Artifact, ArtifactRef, ArtifactService
from minitz_os.engine.audio_pack import (
    AudioArtifactContentRef,
    AudioContractError,
    AudioSpecification,
    GameAudioHandoffBinding,
    MixSpecification,
    ProcessingChain,
    StemSpecification,
    VideoAudioHandoffBinding,
)
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.scheduler import ScheduledDispatch, Scheduler


def _runtime() -> Any:
    return importlib.import_module("minitz.audio_tool")


def _support() -> Any:
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location("p3_12_support", path)
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


def _wav(*, rate: int = 48_000, seconds: float = 0.24, channels: int = 2) -> bytes:
    frames = round(rate * seconds)
    samples: list[int] = []
    for frame in range(frames):
        left = round(10_000 * math.sin(2.0 * math.pi * 440.0 * frame / rate))
        right = round(6_000 * math.sin(2.0 * math.pi * 660.0 * frame / rate))
        samples.extend((left, right) if channels == 2 else (left,))
    output = BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return output.getvalue()


def _mp3(wav_payload: bytes) -> bytes:
    completed = subprocess.run(
        (
            "/usr/bin/ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "wav",
            "-i",
            "pipe:0",
            "-map_metadata",
            "-1",
            "-threads",
            "1",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "96k",
            "-write_xing",
            "0",
            "-id3v2_version",
            "0",
            "-f",
            "mp3",
            "pipe:1",
        ),
        input=wav_payload,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def _source(
    environment: Any,
    payload: bytes,
    *,
    media_type: str = "audio/wav",
    role: str = "audio.source",
) -> AudioArtifactContentRef:
    content = environment.objects.put(payload, media_type=media_type)
    artifact = ArtifactService(environment.database).create_artifact(
        environment.access,
        project_ref=environment.access.project_ref,
        role=role,
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="audio.fixture",
        metadata={"media_type": media_type},
    )
    return AudioArtifactContentRef(
        environment.access.project_ref,
        artifact.artifact_ref.value,
        content.value,
        content.digest,
    )


def _specification(
    environment: Any,
    runtime_ref: str,
    *,
    audio_id: str,
    sources: tuple[AudioArtifactContentRef, ...],
    operation: str,
    duration: float = 0.24,
    start: float = 0.0,
    source_rate: int = 48_000,
    target_rate: int = 48_000,
    source_layout: tuple[str, ...] = ("FL", "FR"),
    target_layout: tuple[str, ...] = ("FL", "FR"),
    media_type: str = "audio/wav",
    container: str = "wav",
    codec: str | None = None,
    sample_format: str = "s16",
    bit_depth: int = 16,
    config: Mapping[str, str] | None = None,
    loudness: Mapping[str, str] | None = None,
    role: str = "audio.clip",
) -> AudioSpecification:
    config_value = {} if config is None else dict(config)
    recipe_payload = json.dumps(
        {"config": config_value, "operation": operation},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    chain = ProcessingChain(
        f"chain://audio/{operation}/{audio_id}",
        hashlib.sha256(recipe_payload + b"chain").hexdigest(),
        "1.0.0",
        (f"effect://audio/{operation}/v1",),
        config_value or {"mode": "identity"},
    )
    codec_value = codec or ("mp3" if container == "mp3" else "pcm_s16le")
    return AudioSpecification.create(
        project_ref=environment.access.project_ref,
        audio_id=audio_id,
        sources=sources,
        operation=operation,
        recipe_ref=f"recipe://audio/{operation}/v1",
        recipe_sha256=hashlib.sha256(recipe_payload).hexdigest(),
        time_start=start,
        time_end=start + duration,
        duration=duration,
        source_sample_rate=source_rate,
        target_sample_rate=target_rate,
        source_channel_layout=source_layout,
        target_channel_layout=target_layout,
        media_type=media_type,
        container=container,
        codec=codec_value,
        sample_format=sample_format,
        bit_depth=bit_depth,
        processing_chain=chain,
        tool_config=config_value,
        loudness_policy={} if loudness is None else dict(loudness),
        measurement_algorithm_ref="algorithm://audio/pcm-f32le/v1",
        spatial_metadata={},
        model_ref="model://audio/deterministic",
        model_version="1.0.0",
        runtime_ref=runtime_ref,
        seed=0,
        voice_ref=None,
        language=None,
        prompt=None,
        validator_ref="validator://audio/real/v1",
        output_contract={"role": role},
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
    runtime = _runtime()
    return runtime.DeterministicAudioTool(
        environment.database,
        environment.objects,
        access=environment.access,
        dispatch=dispatch,
        root_ref=environment.root_ref,
        working_directory="candidate",
    )


def test_real_wav_mp3_probe_and_full_decode_metrics_reject_corruption(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path)[0]
    dispatch = _dispatch(environment)
    tool = _tool(environment, dispatch)
    wav_payload = _wav()
    wav_source = _source(environment, wav_payload)

    inspection = tool.inspect(wav_source, "validator://audio/decode/v1")

    assert inspection.container == "wav"
    assert inspection.codec == "pcm_s16le"
    assert inspection.sample_rate == 48_000
    assert inspection.sample_format == "s16"
    assert inspection.bit_depth == 16
    assert inspection.channels == 2
    assert inspection.channel_layout == ("FL", "FR")
    assert inspection.duration == pytest.approx(0.24, abs=1 / 48_000)
    assert inspection.sample_count == 11_520
    assert inspection.bit_rate == 1_536_000
    assert inspection.content_sha256 == hashlib.sha256(wav_payload).hexdigest()
    assert inspection.pcm_sha256 != inspection.content_sha256
    assert inspection.decoder.startswith("ffmpeg://8.0.1/")
    assert 0.25 < inspection.peak < 0.32
    assert 0.1 < inspection.rms < inspection.peak
    assert math.isfinite(inspection.loudness_lufs)
    assert inspection.clipping_samples == 0
    assert 0 <= inspection.silence_samples < inspection.sample_count * inspection.channels
    analysis = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(inspection.analysis_ref, environment.access.project_ref),
    )
    assert analysis.role == "audio.analysis"
    assert analysis.content_ref is not None
    assert analysis.content_ref.digest == inspection.analysis_sha256

    mp3_payload = _mp3(wav_payload)
    mp3 = tool.validate(mp3_payload, expected_media_type="audio/mpeg")
    assert mp3.container == "mp3" and mp3.codec == "mp3"
    assert mp3.sample_rate == 48_000 and mp3.channels == 2
    assert mp3.sample_format in {"fltp", "s16p"}
    assert mp3.bit_depth in {16, 32}
    assert mp3.sample_count > 11_000 and mp3.bit_rate is not None
    assert all(math.isfinite(value) for value in (mp3.peak, mp3.rms, mp3.loudness_lufs))

    with pytest.raises(AudioContractError, match="decode|corrupt|probe|process"):
        tool.validate(b"ID3-not-really-mp3", expected_media_type="audio/mpeg")
    with pytest.raises(AudioContractError, match="media|container|codec"):
        tool.validate(wav_payload, expected_media_type="audio/mpeg")


def test_all_explicit_edits_publish_real_immutable_artifact_derivations(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path)[0]
    dispatch = _dispatch(environment)
    tool = _tool(environment, dispatch)
    source_payload = _wav()
    source = _source(environment, source_payload)
    cases: tuple[
        tuple[
            str,
            float,
            float,
            int,
            tuple[str, ...],
            str,
            str,
            str,
            int,
            dict[str, str],
            dict[str, str],
            str,
        ],
        ...,
    ] = (
        ("trim", 0.12, 0.04, 48_000, ("FL", "FR"), "audio/wav", "wav", "s16", 16, {}, {}, "audio.clip"),
        ("segment", 0.08, 0.08, 48_000, ("FL", "FR"), "audio/wav", "wav", "s16", 16, {}, {}, "audio.clip"),
        ("resample", 0.24, 0.0, 24_000, ("FL", "FR"), "audio/wav", "wav", "s16", 16, {}, {}, "audio.clip"),
        ("convert", 0.24, 0.0, 48_000, ("FC",), "audio/wav", "wav", "s16", 16, {"conversion": "channel"}, {}, "audio.clip"),
        ("convert", 0.24, 0.0, 48_000, ("FL", "FR"), "audio/mpeg", "mp3", "fltp", 32, {"bit_rate": "96k", "conversion": "format"}, {}, "audio.clip"),
        ("filter", 0.24, 0.0, 48_000, ("FL", "FR"), "audio/wav", "wav", "s16", 16, {"highpass_hz": "120"}, {}, "audio.clip"),
        ("clean", 0.24, 0.0, 48_000, ("FL", "FR"), "audio/wav", "wav", "s16", 16, {"highpass_hz": "80", "lowpass_hz": "12000"}, {}, "audio.cleaned"),
        ("normalize", 0.24, 0.0, 48_000, ("FL", "FR"), "audio/wav", "wav", "s16", 16, {}, {"target_lufs": "-18", "true_peak_dbfs": "-1"}, "audio.master"),
        ("master", 0.24, 0.0, 48_000, ("FL", "FR"), "audio/wav", "wav", "s16", 16, {}, {"target_lufs": "-16", "true_peak_dbfs": "-1"}, "audio.master"),
        ("preview", 0.10, 0.0, 48_000, ("FL", "FR"), "audio/wav", "wav", "s16", 16, {}, {}, "audio.preview"),
        ("export", 0.24, 0.0, 48_000, ("FL", "FR"), "audio/wav", "wav", "s16", 16, {}, {}, "audio.export"),
    )
    outputs: list[Any] = []
    for index, case in enumerate(cases):
        (
            operation,
            duration,
            start,
            target_rate,
            target_layout,
            media_type,
            container,
            sample_format,
            bit_depth,
            config,
            loudness,
            role,
        ) = case
        specification = _specification(
            environment,
            tool.runtime_ref,
            audio_id=f"{operation}-{index}",
            sources=(source,),
            operation=operation,
            duration=duration,
            start=start,
            target_rate=target_rate,
            target_layout=target_layout,
            media_type=media_type,
            container=container,
            sample_format=sample_format,
            bit_depth=bit_depth,
            config=config,
            loudness=loudness,
            role=role,
        )
        output = tool.execute(environment.access, environment.attempt, specification)
        artifact, payload = _read_output(environment, output)
        decoded = tool.validate(payload, expected_media_type=media_type)
        assert artifact.role == role
        assert output.producer_attempt_id == environment.attempt.attempt_id
        assert output.producer_fence == environment.attempt.fence
        assert decoded.sample_rate == target_rate
        assert decoded.channel_layout == target_layout
        assert decoded.container == container
        assert decoded.duration == pytest.approx(duration, abs=0.05 if container == "mp3" else 1 / target_rate)
        derivation = ArtifactService(environment.database).list_derivations(
            environment.access, artifact.artifact_ref
        )[0]
        assert source.artifact_ref in tuple(item.value for item in derivation.source_artifact_refs)
        assert source.content_sha256 in tuple(item.digest for item in derivation.source_content_refs)
        outputs.append(output)
    assert len({item.output.artifact_ref for item in outputs}) == len(cases)
    original = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(source.artifact_ref, environment.access.project_ref),
    )
    assert original.content_ref is not None
    assert environment.objects.read(original.content_ref) == source_payload

    implicit_rate = _specification(
        environment,
        tool.runtime_ref,
        audio_id="implicit-rate",
        sources=(source,),
        operation="filter",
        target_rate=24_000,
        config={"highpass_hz": "80"},
    )
    with pytest.raises(AudioContractError, match="resample|sample rate"):
        tool.execute(environment.access, environment.attempt, implicit_rate)
    implicit_channel = _specification(
        environment,
        tool.runtime_ref,
        audio_id="implicit-channel",
        sources=(source,),
        operation="filter",
        target_layout=("FC",),
        config={"highpass_hz": "80"},
    )
    with pytest.raises(AudioContractError, match="channel"):
        tool.execute(environment.access, environment.attempt, implicit_channel)
    implicit_loudness = _specification(
        environment,
        tool.runtime_ref,
        audio_id="implicit-loudness",
        sources=(source,),
        operation="filter",
        config={"gain_db": "3"},
    )
    with pytest.raises(AudioContractError, match="loudness|gain"):
        tool.execute(environment.access, environment.attempt, implicit_loudness)


def test_dispatched_stems_overlap_mix_to_session_preserve_failure_and_handoffs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator, first_child, second_child = _environments(tmp_path, count=3)
    coordinator_dispatch = _dispatch(coordinator)
    first_dispatch, second_dispatch = _dispatch(first_child), _dispatch(second_child)
    tool = _tool(coordinator, coordinator_dispatch)
    first_source = _source(coordinator, _wav())
    second_source = _source(coordinator, _wav(channels=2))
    first = _specification(
        coordinator,
        tool.runtime_ref,
        audio_id="stem-first",
        sources=(first_source,),
        operation="filter",
        config={"highpass_hz": "80"},
        role="audio.stem",
    )
    second = _specification(
        coordinator,
        tool.runtime_ref,
        audio_id="stem-second",
        sources=(second_source,),
        operation="filter",
        config={"lowpass_hz": "12000"},
        role="audio.stem",
    )
    barrier = Barrier(2)
    lock = Lock()
    active = 0
    maximum_active = 0
    real_execute = tool._execute_authorized

    def observe_overlap(*args: object, **kwargs: object) -> object:
        nonlocal active, maximum_active
        barrier.wait(timeout=5.0)
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            return real_execute(*args, **kwargs)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(tool, "_execute_authorized", observe_overlap)
    batch = tool.execute_stems(
        {"first": first, "second": second},
        {"first": first_dispatch, "second": second_dispatch},
    )
    assert set(batch.outputs) == {"first", "second"}
    assert not batch.failures and maximum_active == 2
    monkeypatch.setattr(tool, "_execute_authorized", real_execute)

    stem_first = StemSpecification(
        coordinator.access.project_ref, first, "first", batch.outputs["first"].output
    )
    stem_second = StemSpecification(
        coordinator.access.project_ref, second, "second", batch.outputs["second"].output
    )
    levels = {
        "first": json.dumps(
            {"effects": ["highpass:80"], "gain_db": -3.0, "offset_seconds": 0.0, "pan": -0.5},
            sort_keys=True,
            separators=(",", ":"),
        ),
        "second": json.dumps(
            {"effects": ["lowpass:12000"], "gain_db": -6.0, "offset_seconds": 0.02, "pan": 0.5},
            sort_keys=True,
            separators=(",", ":"),
        ),
    }
    mix_contract = MixSpecification(
        coordinator.access.project_ref,
        "mix://audio/project-main/v1",
        "1.0.0",
        (stem_first, stem_second),
        levels,
    )
    mix_specification = _specification(
        coordinator,
        tool.runtime_ref,
        audio_id="project-main",
        sources=(batch.outputs["first"].output, batch.outputs["second"].output),
        operation="mix",
        duration=0.26,
        loudness={"target_lufs": "-18", "true_peak_dbfs": "-1"},
        role="audio.mix",
    )

    mixed = tool.mix(
        coordinator.access,
        coordinator.attempt,
        mix_specification,
        mix_contract,
    )

    mix_artifact, mix_payload = _read_output(coordinator, mixed.output)
    measured = tool.validate(mix_payload, expected_media_type="audio/wav")
    assert mix_artifact.role == "audio.mix"
    assert measured.duration == pytest.approx(0.26, abs=1 / 48_000)
    assert measured.channels == 2 and measured.sample_rate == 48_000
    assert mixed.measurements.project_ref == coordinator.access.project_ref
    assert math.isfinite(mixed.measurements.actual_lufs)
    assert mixed.measurements.target_lufs == -18.0
    session_ref = mixed.session.session
    session_artifact = ArtifactService(coordinator.database).get_artifact(
        coordinator.access,
        _artifact_ref(session_ref.artifact_ref, coordinator.access.project_ref),
    )
    assert session_artifact.role == "audio.session" and session_artifact.content_ref is not None
    session = json.loads(coordinator.objects.read(session_artifact.content_ref))
    assert session["levels"] == levels
    assert session["mix_output"]["artifact_ref"] == mixed.output.output.artifact_ref

    broken = _source(coordinator, b"not-a-wave", media_type="audio/wav")
    failed_specification = _specification(
        coordinator,
        tool.runtime_ref,
        audio_id="stem-broken",
        sources=(broken,),
        operation="filter",
        config={"highpass_hz": "80"},
        role="audio.stem",
    )
    retry_specification = _specification(
        coordinator,
        tool.runtime_ref,
        audio_id="stem-good-retry",
        sources=(first_source,),
        operation="filter",
        config={"highpass_hz": "80"},
        role="audio.stem",
    )
    failed_batch = tool.execute_stems(
        {"good": retry_specification, "bad": failed_specification},
        {"good": first_dispatch, "bad": second_dispatch},
    )
    assert set(failed_batch.outputs) == {"good"}
    assert set(failed_batch.failures) == {"bad"}
    good_artifact, _ = _read_output(coordinator, failed_batch.outputs["good"])
    assert good_artifact.role == "audio.stem"

    target = _source(coordinator, b"target-audio-binding", role="audio.validation-evidence")
    game = tool.bind_game_handoff(
        mixed.output, target, "integration://game/project-main/audio/v1"
    )
    video = tool.bind_video_handoff(
        mixed.output, target, "integration://video/project-main/audio/v1"
    )
    assert isinstance(game, GameAudioHandoffBinding)
    assert isinstance(video, VideoAudioHandoffBinding)
    assert game.target == target and video.output == mixed.output

    foreign = replace(first_source, project_ref=ProjectRef.new())
    with pytest.raises(AudioContractError, match="Project"):
        tool.inspect(foreign, "validator://audio/decode/v1")
    reserved = ScheduledDispatch(
        replace(
            coordinator_dispatch.allocation,
            status="RESERVED",
            dispatch_idempotency_key=None,
            node_attempt_id=None,
            node_attempt_fence=None,
        ),
        coordinator_dispatch.node_attempt,
    )
    with pytest.raises(AudioContractError, match="dispatch|allocation"):
        tool.execute_dispatched(mix_specification, reserved)


def test_concurrent_maps_reject_reused_dispatch_before_launch(tmp_path: Path) -> None:
    coordinator, first_child, _ = _environments(tmp_path, count=3)
    tool = _tool(coordinator, _dispatch(coordinator))
    source = _source(coordinator, _wav())
    first = _specification(
        coordinator,
        tool.runtime_ref,
        audio_id="unique-first",
        sources=(source,),
        operation="filter",
        config={"highpass_hz": "80"},
        role="audio.stem",
    )
    second = _specification(
        coordinator,
        tool.runtime_ref,
        audio_id="unique-second",
        sources=(source,),
        operation="filter",
        config={"highpass_hz": "80"},
        role="audio.stem",
    )
    reused = _dispatch(first_child)
    with pytest.raises(AudioContractError, match="distinct|unique"):
        tool.execute_stems(
            {"first": first, "second": second},
            {"first": reused, "second": reused},
        )


def test_real_fixture_encoder_is_independent_and_bounded() -> None:
    wav_payload = _wav(seconds=0.05)
    mp3_payload = _mp3(wav_payload)
    assert wav_payload.startswith(b"RIFF") and b"WAVE" in wav_payload[:16]
    assert mp3_payload and len(mp3_payload) < 64_000
    with ThreadPoolExecutor(max_workers=2) as executor:
        encoded = tuple(executor.map(_mp3, (wav_payload, wav_payload)))
    assert encoded[0] == encoded[1]
