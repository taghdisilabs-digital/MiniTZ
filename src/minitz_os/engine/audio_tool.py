"""REAL deterministic audio processing on existing MiniTZ authorities."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
from types import MappingProxyType
from typing import Any, cast

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .audio_pack import (
    AUDIO_ARTIFACT_ROLES,
    AudioArtifactContentRef,
    AudioContractError,
    AudioInspectionRef,
    AudioOutputRef,
    AudioSpecification,
    AudioToolAdapter,
    EditableAudioSessionBinding,
    GameAudioHandoffBinding,
    MixSpecification,
    StemSpecification,
    VideoAudioHandoffBinding,
)
from .execution import NodeExecutionAttempt, NodeExecutionError, NodeExecutionService
from .filesystem import FilesystemAdapter, FilesystemError, FilesystemRootRef
from .object_store import ObjectStorageBackend, ObjectStorageError
from .process import (
    ManagedProcessAdapter,
    ProcessError,
    ProcessExecutionRequest,
    ProcessResult,
    ProcessStatus,
)
from .project import ProjectAccess, ProjectRef
from .run import ExecutionAttempt
from .scheduler import ScheduledDispatch


_FFMPEG = Path("/usr/bin/ffmpeg")
_FFPROBE = Path("/usr/bin/ffprobe")
_VERSION = "8.0.1"
_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_MEDIA_ALIASES = {
    "audio/mp3": "audio/mpeg",
    "audio/mpeg": "audio/mpeg",
    "audio/wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/x-wav": "audio/wav",
}
_CONTAINER_MEDIA = {"mp3": "audio/mpeg", "wav": "audio/wav"}
_LAYOUT_CHANNELS = {
    "mono": ("FC",),
    "stereo": ("FL", "FR"),
    "2.1": ("FL", "FR", "LFE"),
    "3.0": ("FL", "FR", "FC"),
    "4.0": ("FL", "FR", "FC", "BC"),
    "5.0": ("FL", "FR", "FC", "BL", "BR"),
    "5.1": ("FL", "FR", "FC", "LFE", "BL", "BR"),
    "7.1": ("FL", "FR", "FC", "LFE", "BL", "BR", "SL", "SR"),
}
_CHANNELS_LAYOUT = {value: key for key, value in _LAYOUT_CHANNELS.items()}
_ROLE_BY_OPERATION = {
    "clean": "audio.cleaned",
    "convert": "audio.clip",
    "edit": "audio.clip",
    "export": "audio.export",
    "filter": "audio.clip",
    "master": "audio.master",
    "normalize": "audio.master",
    "preview": "audio.preview",
    "resample": "audio.clip",
    "segment": "audio.clip",
    "trim": "audio.clip",
}
_SILENCE_THRESHOLD = 10.0 ** (-60.0 / 20.0)


@dataclass(frozen=True)
class AudioDecodedMetadata:
    """Verified container metadata plus metrics from the complete decoded stream."""

    media_type: str
    container: str
    codec: str
    sample_rate: int
    sample_format: str
    bit_depth: int
    channels: int
    channel_layout: tuple[str, ...]
    duration: float
    sample_count: int
    bit_rate: int | None
    tags: Mapping[str, str]
    content_sha256: str
    pcm_sha256: str
    decoder: str
    peak: float
    rms: float
    loudness_lufs: float
    clipping_samples: int
    silence_samples: int

    def __post_init__(self) -> None:
        if self.media_type not in _CONTAINER_MEDIA.values():
            raise AudioContractError("decoded audio media type is unsupported")
        if self.container not in _CONTAINER_MEDIA or not self.codec:
            raise AudioContractError("decoded audio container or codec is malformed")
        if (
            self.sample_rate < 1
            or self.bit_depth < 1
            or self.channels < 1
            or len(self.channel_layout) != self.channels
            or self.sample_count < 0
            or self.duration < 0.0
        ):
            raise AudioContractError("decoded audio dimensions are malformed")
        if self.bit_rate is not None and self.bit_rate < 1:
            raise AudioContractError("decoded audio bit rate is malformed")
        if any(
            not math.isfinite(value)
            for value in (self.duration, self.peak, self.rms, self.loudness_lufs)
        ):
            raise AudioContractError("decoded audio metrics are not finite")
        if (
            self.peak < 0.0
            or self.rms < 0.0
            or self.clipping_samples < 0
            or self.silence_samples < 0
        ):
            raise AudioContractError("decoded audio metrics are malformed")
        for digest in (self.content_sha256, self.pcm_sha256):
            if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise AudioContractError("decoded audio digest is malformed")
        normalized_tags: dict[str, str] = {}
        for key, value in self.tags.items():
            if not isinstance(key, str) or not key or not isinstance(value, str):
                raise AudioContractError("decoded audio tags are malformed")
            normalized_tags[key] = value
        object.__setattr__(self, "tags", MappingProxyType(dict(sorted(normalized_tags.items()))))

    def payload(self) -> dict[str, object]:
        return {
            "bit_depth": self.bit_depth,
            "bit_rate": self.bit_rate,
            "channel_layout": list(self.channel_layout),
            "channels": self.channels,
            "clipping_samples": self.clipping_samples,
            "codec": self.codec,
            "container": self.container,
            "content_sha256": self.content_sha256,
            "decoder": self.decoder,
            "duration": self.duration,
            "loudness_lufs": self.loudness_lufs,
            "media_type": self.media_type,
            "pcm_sha256": self.pcm_sha256,
            "peak": self.peak,
            "rms": self.rms,
            "sample_count": self.sample_count,
            "sample_format": self.sample_format,
            "sample_rate": self.sample_rate,
            "silence_samples": self.silence_samples,
            "tags": dict(self.tags),
        }


@dataclass(frozen=True)
class AudioInspection(AudioInspectionRef):
    """The contract inspection ref extended with complete deterministic evidence."""

    media_type: str
    container: str
    sample_format: str
    bit_depth: int
    channels: int
    sample_count: int
    bit_rate: int | None
    tags: Mapping[str, str]
    content_sha256: str
    pcm_sha256: str
    decoder: str
    peak: float
    rms: float
    loudness_lufs: float
    clipping_samples: int
    silence_samples: int

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.sample_rate is None or self.channel_layout is None:
            raise AudioContractError("full audio inspection requires decoded rate and layout")
        AudioDecodedMetadata(
            self.media_type,
            self.container,
            self.codec,
            self.sample_rate,
            self.sample_format,
            self.bit_depth,
            self.channels,
            self.channel_layout,
            self.duration,
            self.sample_count,
            self.bit_rate,
            self.tags,
            self.content_sha256,
            self.pcm_sha256,
            self.decoder,
            self.peak,
            self.rms,
            self.loudness_lufs,
            self.clipping_samples,
            self.silence_samples,
        )
        object.__setattr__(self, "tags", MappingProxyType(dict(sorted(self.tags.items()))))


@dataclass(frozen=True)
class AudioStemBatch:
    outputs: Mapping[str, AudioOutputRef]
    failures: Mapping[str, str]

    def __post_init__(self) -> None:
        if set(self.outputs) & set(self.failures):
            raise AudioContractError("one stem cannot both succeed and fail")
        object.__setattr__(self, "outputs", MappingProxyType(dict(sorted(self.outputs.items()))))
        object.__setattr__(self, "failures", MappingProxyType(dict(sorted(self.failures.items()))))


@dataclass(frozen=True)
class AudioTargetMeasurements:
    project_ref: ProjectRef
    actual_lufs: float
    target_lufs: float | None
    true_peak_dbfs: float
    target_true_peak_dbfs: float | None
    duration: float
    sample_rate: int
    channel_layout: tuple[str, ...]
    met: bool

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise AudioContractError("audio target measurements crossed Project scope")
        values = (self.actual_lufs, self.true_peak_dbfs, self.duration)
        optional = (self.target_lufs, self.target_true_peak_dbfs)
        if any(not math.isfinite(value) for value in values) or any(
            value is not None and not math.isfinite(value) for value in optional
        ):
            raise AudioContractError("audio target measurements are not finite")
        if self.duration < 0.0 or self.sample_rate < 1 or not self.channel_layout:
            raise AudioContractError("audio target measurements are malformed")

    def payload(self) -> dict[str, object]:
        return {
            "actual_lufs": self.actual_lufs,
            "channel_layout": list(self.channel_layout),
            "duration": self.duration,
            "met": self.met,
            "sample_rate": self.sample_rate,
            "target_lufs": self.target_lufs,
            "target_true_peak_dbfs": self.target_true_peak_dbfs,
            "true_peak_dbfs": self.true_peak_dbfs,
        }


@dataclass(frozen=True)
class AudioMixResult:
    output: AudioOutputRef
    session: EditableAudioSessionBinding
    measurements: AudioTargetMeasurements

    def __post_init__(self) -> None:
        project_ref = self.output.project_ref
        if (
            self.session.project_ref != project_ref
            or self.measurements.project_ref != project_ref
        ):
            raise AudioContractError("audio mix result crossed Project scope")


@dataclass(frozen=True)
class _ResolvedAudio:
    contract: AudioArtifactContentRef
    artifact: Artifact
    content_ref: ContentRef
    payload: bytes


@dataclass(frozen=True)
class _Probe:
    container: str
    codec: str
    sample_rate: int
    sample_format: str
    bit_depth: int
    channels: int
    channel_layout: tuple[str, ...]
    bit_rate: int | None
    tags: Mapping[str, str]


@dataclass(frozen=True)
class _MixLevel:
    offset_seconds: float
    gain_db: float
    pan: float
    effects: tuple[str, ...]


def _file_sha256(path: Path) -> str:
    if not path.is_absolute() or not path.is_file():
        raise AudioContractError(f"required audio executable is unavailable: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def _canonical_media_type(value: str) -> str:
    try:
        return _MEDIA_ALIASES[value.lower()]
    except (AttributeError, KeyError) as exc:
        raise AudioContractError("audio media type is unsupported") from exc


def _artifact_ref(project_ref: ProjectRef, value: str) -> ArtifactRef:
    parts = value.rsplit("/", 2)
    if len(parts) != 3 or parts[0] != f"artifact://{project_ref.value}":
        raise AudioContractError("audio ArtifactRef is invalid or crossed Project scope")
    try:
        return ArtifactRef(project_ref, parts[1], int(parts[2]))
    except (TypeError, ValueError) as exc:
        raise AudioContractError("audio ArtifactRef is malformed") from exc


def _number(
    values: Mapping[str, str],
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    raw = values.get(name)
    if raw is None:
        raise AudioContractError(f"audio parameter {name} is required")
    try:
        result = float(raw)
    except (TypeError, ValueError) as exc:
        raise AudioContractError(f"audio parameter {name} is invalid") from exc
    if (
        not math.isfinite(result)
        or (minimum is not None and result < minimum)
        or (maximum is not None and result > maximum)
    ):
        raise AudioContractError(f"audio parameter {name} is invalid")
    return result


def _optional_number(
    values: Mapping[str, str],
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    if name not in values:
        return None
    return _number(values, name, minimum=minimum, maximum=maximum)


def _integer_text(value: object, field: str, *, allow_missing: bool = False) -> int | None:
    if value in (None, "", "N/A", 0, "0") and allow_missing:
        return None
    try:
        result = int(cast(str | int, value))
    except (TypeError, ValueError) as exc:
        raise AudioContractError(f"ffprobe {field} is malformed") from exc
    if result < 1:
        raise AudioContractError(f"ffprobe {field} is malformed")
    return result


def _bit_depth(stream: Mapping[str, object], sample_format: str) -> int:
    for field in ("bits_per_raw_sample", "bits_per_sample"):
        value = _integer_text(stream.get(field), field, allow_missing=True)
        if value is not None:
            return value
    base = sample_format.rstrip("p")
    match = re.search(r"(8|16|24|32|64)", base)
    if match is not None:
        return int(match.group(1))
    if base == "flt":
        return 32
    if base == "dbl":
        return 64
    raise AudioContractError("ffprobe sample bit depth is unavailable")


def _channel_layout(value: object, channels: int) -> tuple[str, ...]:
    if isinstance(value, str) and value in _LAYOUT_CHANNELS:
        layout = _LAYOUT_CHANNELS[value]
        if len(layout) == channels:
            return layout
    if channels == 1:
        return _LAYOUT_CHANNELS["mono"]
    if channels == 2:
        return _LAYOUT_CHANNELS["stereo"]
    raise AudioContractError("ffprobe channel layout is absent or unsupported")


def _layout_name(layout: tuple[str, ...]) -> str:
    try:
        return _CHANNELS_LAYOUT[layout]
    except KeyError as exc:
        raise AudioContractError("audio channel layout is unsupported by this runtime") from exc


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _true_peak_dbfs(peak: float) -> float:
    return -120.0 if peak <= 0.0 else 20.0 * math.log10(peak)


class DeterministicAudioTool(AudioToolAdapter):
    """Bound ffmpeg audio node; scheduling authority is always supplied upstream."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        access: ProjectAccess,
        dispatch: ScheduledDispatch,
        root_ref: FilesystemRootRef,
        working_directory: str,
        tool_ref: str = "tool://ffmpeg/8.0.1",
        runtime_ref: str = "runtime://audio/ffmpeg-8.0.1-cpu",
        validator_ref: str = "validator://audio/ffmpeg-full-decode/v1",
    ) -> None:
        if not isinstance(access, ProjectAccess):
            raise AudioContractError("exact ProjectAccess is required")
        if not isinstance(dispatch, ScheduledDispatch):
            raise AudioContractError("exact ScheduledDispatch is required")
        if not isinstance(root_ref, FilesystemRootRef) or root_ref.project_ref != access.project_ref:
            raise AudioContractError("audio FilesystemRoot crossed Project scope")
        if not isinstance(working_directory, str) or not working_directory:
            raise AudioContractError("audio working directory is required")
        for value, label in (
            (tool_ref, "tool_ref"),
            (runtime_ref, "runtime_ref"),
            (validator_ref, "validator_ref"),
        ):
            if _ABSOLUTE_REF.fullmatch(value) is None:
                raise AudioContractError(f"audio {label} is malformed")
        if not isinstance(object_store, ObjectStorageBackend):
            raise AudioContractError("ObjectStorageBackend is required")
        self.database = Path(database_path)
        self.objects = object_store
        self.access = access
        self.project_ref = access.project_ref
        self.dispatch = dispatch
        self.root_ref = root_ref
        self.working_directory = working_directory
        self.tool_ref = tool_ref
        self.runtime_ref = runtime_ref
        self.validator_ref = validator_ref
        self.determinism = "deterministic-cpu-bitexact"
        self.artifacts = ArtifactService(self.database)
        self.executions = NodeExecutionService(self.database)
        self.filesystem = FilesystemAdapter(self.database, object_store)
        self.process = ManagedProcessAdapter(self.database, object_store)
        self._ffmpeg_sha256 = _file_sha256(_FFMPEG)
        self._ffprobe_sha256 = _file_sha256(_FFPROBE)

    def _require_dispatch(
        self,
        dispatch: ScheduledDispatch,
        producer_attempt_id: str,
        producer_fence: int,
    ) -> NodeExecutionAttempt:
        if not isinstance(dispatch, ScheduledDispatch):
            raise AudioContractError("exact ScheduledDispatch is required")
        allocation, attempt = dispatch.allocation, dispatch.node_attempt
        if (
            allocation.project_ref != self.project_ref
            or attempt.node_ref.project_ref != self.project_ref
            or producer_attempt_id != attempt.attempt_id
            or producer_fence != attempt.fence
        ):
            raise AudioContractError("audio producer attempt/fence crossed Project or authority")
        if (
            allocation.status != "DISPATCHED"
            or allocation.node_ref != attempt.node_ref
            or allocation.run_ref != attempt.run_ref
            or allocation.run_attempt_id != attempt.run_attempt_id
            or allocation.run_attempt_fence != attempt.run_fence
            or allocation.node_attempt_id != attempt.attempt_id
            or allocation.node_attempt_fence != attempt.fence
            or allocation.owner_ref != attempt.owner_ref
            or allocation.lease_expires_at is None
        ):
            raise AudioContractError("audio dispatch allocation/attempt evidence is stale or forged")
        try:
            current = self.executions.get_node_execution(self.access, attempt.node_ref)
        except NodeExecutionError as exc:
            raise AudioContractError("audio Node attempt evidence is unavailable") from exc
        if (
            current.status in {"CANCELLED", "FAILED", "SUCCEEDED"}
            or current.current_attempt_id != attempt.attempt_id
            or current.current_fence != attempt.fence
            or current.current_owner_ref != attempt.owner_ref
            or current.current_run_attempt_id != attempt.run_attempt_id
            or current.current_run_fence != attempt.run_fence
            or current.run_ref != attempt.run_ref
            or current.task_ref != attempt.task_ref
            or current.task_digest != attempt.task_digest
        ):
            raise AudioContractError("audio Node attempt is not current")
        try:
            node_expiry = datetime.fromisoformat(attempt.lease_expires_at)
            allocation_expiry = datetime.fromisoformat(allocation.lease_expires_at)
            now = datetime.now(node_expiry.tzinfo)
        except (TypeError, ValueError) as exc:
            raise AudioContractError("audio dispatch lease is malformed") from exc
        if node_expiry <= now or allocation_expiry <= now:
            raise AudioContractError("audio dispatch lease is stale")
        return attempt

    def _producer(self, attempt: NodeExecutionAttempt) -> ExecutionAttempt:
        run = self.artifacts.runs.get_run(self.access, attempt.run_ref)
        if (
            run.status != "RUNNING"
            or run.current_attempt_id != attempt.run_attempt_id
            or run.current_fence != attempt.run_fence
            or run.task_ref != attempt.task_ref
            or run.task_digest != attempt.task_digest
        ):
            raise AudioContractError("audio producer Run authority is stale")
        matches = tuple(
            candidate
            for candidate in self.artifacts.runs.list_attempts(self.access, attempt.run_ref)
            if candidate.attempt_id == attempt.run_attempt_id
            and candidate.fence == attempt.run_fence
            and candidate.completed_at is None
        )
        if len(matches) != 1:
            raise AudioContractError("audio producer Run attempt/fence is stale")
        return matches[0]

    def _resolve_artifact(self, source: AudioArtifactContentRef) -> _ResolvedAudio:
        if not isinstance(source, AudioArtifactContentRef) or source.project_ref != self.project_ref:
            raise AudioContractError("audio source crossed Project scope")
        reference = _artifact_ref(self.project_ref, source.artifact_ref)
        try:
            artifact = self.artifacts.get_artifact(self.access, reference)
        except ArtifactError as exc:
            raise AudioContractError("audio source Artifact is missing or stale") from exc
        content = artifact.content_ref
        if (
            content is None
            or content.value != source.content_ref
            or content.digest != source.content_sha256
        ):
            raise AudioContractError("audio source Artifact/Content identity is stale or forged")
        try:
            if not self.objects.verify(content):
                raise AudioContractError("audio source Content is unavailable or corrupt")
            payload = self.objects.read(content)
            content.verify(payload)
        except (ArtifactError, ObjectStorageError) as exc:
            raise AudioContractError("audio source Content is unavailable or corrupt") from exc
        return _ResolvedAudio(source, artifact, content, payload)

    def _managed_process(
        self,
        dispatch: ScheduledDispatch,
        *,
        executable: Path,
        executable_sha256: str,
        argv: tuple[str, ...],
        stdin_ref: ContentRef | None,
        idempotency_key: str,
        stdout_limit_bytes: int,
        stderr_limit_bytes: int = 4 * 1024 * 1024,
    ) -> ProcessResult:
        attempt = self._require_dispatch(
            dispatch, dispatch.node_attempt.attempt_id, dispatch.node_attempt.fence
        )
        request = ProcessExecutionRequest(
            project_ref=self.project_ref,
            working_root_ref=self.root_ref,
            working_directory=self.working_directory,
            executable=str(executable),
            expected_executable_sha256=executable_sha256,
            argv=argv,
            timeout_seconds=120.0,
            termination_grace_seconds=2.0,
            stdout_limit_bytes=stdout_limit_bytes,
            stderr_limit_bytes=stderr_limit_bytes,
            resource_allocation_ref=dispatch.allocation.allocation_ref,
            stdin_ref=stdin_ref,
        )
        try:
            result = self.process.execute(
                self.access, attempt, request, idempotency_key=idempotency_key
            )
        except ProcessError as exc:
            raise AudioContractError("managed audio process authority or execution failed") from exc
        if result.status is not ProcessStatus.SUCCEEDED:
            raise AudioContractError(
                f"managed audio process failed: {result.stderr_preview[:512]}"
            )
        if result.stdout_truncated or result.stderr_truncated:
            raise AudioContractError("managed audio process evidence was truncated")
        return result

    def _probe(
        self, content: ContentRef, dispatch: ScheduledDispatch, *, token: str
    ) -> tuple[_Probe, ProcessResult]:
        result = self._managed_process(
            dispatch,
            executable=_FFPROBE,
            executable_sha256=self._ffprobe_sha256,
            argv=(
                "-hide_banner",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "format=format_name,duration,bit_rate,tags:stream=codec_type,codec_name,sample_fmt,sample_rate,channels,channel_layout,duration,bit_rate,bits_per_raw_sample,bits_per_sample,tags",
                "-of",
                "json",
                "pipe:0",
            ),
            stdin_ref=content,
            idempotency_key=f"audio-probe-{token}",
            stdout_limit_bytes=4 * 1024 * 1024,
        )
        try:
            loaded: object = json.loads(self.objects.read(result.stdout_ref))
        except (ObjectStorageError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AudioContractError("ffprobe audio evidence is malformed") from exc
        if not isinstance(loaded, dict):
            raise AudioContractError("ffprobe audio evidence is malformed")
        payload = cast(dict[str, object], loaded)
        streams_value = payload.get("streams")
        format_value = payload.get("format")
        if (
            not isinstance(streams_value, list)
            or len(streams_value) != 1
            or not isinstance(streams_value[0], dict)
            or not isinstance(format_value, dict)
        ):
            raise AudioContractError("ffprobe found no exact audio stream")
        stream = cast(dict[str, object], streams_value[0])
        format_record = cast(dict[str, object], format_value)
        codec = stream.get("codec_name")
        sample_format = stream.get("sample_fmt")
        format_names = format_record.get("format_name")
        if not isinstance(codec, str) or not codec or not isinstance(sample_format, str):
            raise AudioContractError("ffprobe codec or sample format is missing")
        if not isinstance(format_names, str):
            raise AudioContractError("ffprobe container identity is missing")
        names = set(format_names.split(","))
        if "wav" in names and codec.startswith("pcm_"):
            container = "wav"
        elif "mp3" in names and codec == "mp3":
            container = "mp3"
        else:
            raise AudioContractError("ffprobe container/codec combination is unsupported")
        sample_rate_value = _integer_text(stream.get("sample_rate"), "sample_rate")
        channels_value = _integer_text(stream.get("channels"), "channels")
        assert sample_rate_value is not None and channels_value is not None
        rate_value = _integer_text(stream.get("bit_rate"), "stream bit_rate", allow_missing=True)
        if rate_value is None:
            rate_value = _integer_text(format_record.get("bit_rate"), "format bit_rate", allow_missing=True)
        tags: dict[str, str] = {}
        for prefix, record in (("format", format_record), ("stream", stream)):
            raw_tags = record.get("tags")
            if raw_tags is None:
                continue
            if not isinstance(raw_tags, dict):
                raise AudioContractError("ffprobe tags are malformed")
            for key, value in cast(dict[object, object], raw_tags).items():
                if not isinstance(key, str) or not isinstance(value, (str, int, float)):
                    raise AudioContractError("ffprobe tags are malformed")
                tags[f"{prefix}.{key.lower()}"] = str(value)
        return (
            _Probe(
                container,
                codec,
                sample_rate_value,
                sample_format,
                _bit_depth(stream, sample_format),
                channels_value,
                _channel_layout(stream.get("channel_layout"), channels_value),
                rate_value,
                MappingProxyType(dict(sorted(tags.items()))),
            ),
            result,
        )

    def _decode(
        self,
        content: ContentRef,
        probe: _Probe,
        dispatch: ScheduledDispatch,
        *,
        token: str,
    ) -> tuple[bytes, ProcessResult]:
        result = self._managed_process(
            dispatch,
            executable=_FFMPEG,
            executable_sha256=self._ffmpeg_sha256,
            argv=(
                "-hide_banner",
                "-nostdin",
                "-v",
                "error",
                "-i",
                "pipe:0",
                "-map",
                "0:a:0",
                "-vn",
                "-sn",
                "-dn",
                "-threads",
                "1",
                "-codec:a",
                "pcm_f32le",
                "-f",
                "f32le",
                "pipe:1",
            ),
            stdin_ref=content,
            idempotency_key=f"audio-decode-{token}",
            stdout_limit_bytes=256 * 1024 * 1024,
        )
        try:
            pcm = self.objects.read(result.stdout_ref)
        except ObjectStorageError as exc:
            raise AudioContractError("decoded PCM evidence is unavailable") from exc
        frame_width = 4 * probe.channels
        if not pcm or len(pcm) % frame_width != 0:
            raise AudioContractError("full decoded PCM is empty or truncated")
        return pcm, result

    @staticmethod
    def _pcm_metrics(pcm: bytes, probe: _Probe) -> tuple[float, float, float, int, int, int, float]:
        count = len(pcm) // 4
        values = struct.unpack(f"<{count}f", pcm)
        if any(not math.isfinite(value) for value in values):
            raise AudioContractError("decoded PCM contains NaN or infinity")
        squares = math.fsum(float(value) * float(value) for value in values)
        peak = max(abs(float(value)) for value in values)
        rms = math.sqrt(squares / count)
        loudness = -120.0 if rms <= 0.0 else max(-120.0, 20.0 * math.log10(rms))
        clipping = sum(1 for value in values if abs(float(value)) >= 1.0)
        silence = sum(1 for value in values if abs(float(value)) <= _SILENCE_THRESHOLD)
        frames = count // probe.channels
        duration = frames / probe.sample_rate
        return peak, rms, loudness, clipping, silence, frames, duration

    def _validate_payload(
        self,
        payload: bytes,
        *,
        expected_media_type: str,
        dispatch: ScheduledDispatch,
    ) -> tuple[AudioDecodedMetadata, tuple[ProcessResult, ProcessResult]]:
        if not isinstance(payload, bytes) or not payload:
            raise AudioContractError("audio bytes are empty or corrupt")
        media_type = _canonical_media_type(expected_media_type)
        content_sha256 = hashlib.sha256(payload).hexdigest()
        try:
            content = self.objects.put(
                payload,
                media_type=media_type,
                expected_digest=content_sha256,
                expected_size=len(payload),
            )
        except ObjectStorageError as exc:
            raise AudioContractError("audio validation staging failed") from exc
        token = hashlib.sha256(f"{media_type}:{content_sha256}".encode()).hexdigest()[:40]
        probe, probe_process = self._probe(content, dispatch, token=token)
        if _CONTAINER_MEDIA[probe.container] != media_type:
            raise AudioContractError("audio media type does not match decoded container/codec")
        pcm, decode_process = self._decode(content, probe, dispatch, token=token)
        peak, rms, loudness, clipping, silence, frames, duration = self._pcm_metrics(pcm, probe)
        metadata = AudioDecodedMetadata(
            media_type,
            probe.container,
            probe.codec,
            probe.sample_rate,
            probe.sample_format,
            probe.bit_depth,
            probe.channels,
            probe.channel_layout,
            duration,
            frames,
            probe.bit_rate,
            probe.tags,
            content_sha256,
            hashlib.sha256(pcm).hexdigest(),
            f"ffmpeg://{_VERSION}/{probe.codec}",
            peak,
            rms,
            loudness,
            clipping,
            silence,
        )
        return metadata, (probe_process, decode_process)

    def validate(self, payload: bytes, *, expected_media_type: str) -> AudioDecodedMetadata:
        """Full-decode bytes through the bound live dispatch; suitable for injection."""

        metadata, _ = self._validate_payload(
            payload,
            expected_media_type=expected_media_type,
            dispatch=self.dispatch,
        )
        return metadata

    @staticmethod
    def _unique_artifact_refs(values: Sequence[ArtifactRef]) -> tuple[ArtifactRef, ...]:
        return tuple(sorted(set(values), key=lambda value: value.value))

    @staticmethod
    def _unique_content_refs(values: Sequence[ContentRef]) -> tuple[ContentRef, ...]:
        unique: dict[tuple[str, str, int], ContentRef] = {}
        for value in values:
            unique[(value.algorithm, value.digest, value.size_bytes)] = value
        return tuple(unique[key] for key in sorted(unique))

    def _publish(
        self,
        dispatch: ScheduledDispatch,
        *,
        role: str,
        payload: bytes,
        media_type: str,
        sources: Sequence[_ResolvedAudio],
        process_results: Sequence[ProcessResult],
        derivation: str,
        metadata: Mapping[str, str] | None = None,
    ) -> AudioArtifactContentRef:
        attempt = self._require_dispatch(
            dispatch, dispatch.node_attempt.attempt_id, dispatch.node_attempt.fence
        )
        producer = self._producer(attempt)
        try:
            content = self.objects.put(
                payload,
                media_type=media_type,
                expected_digest=hashlib.sha256(payload).hexdigest(),
                expected_size=len(payload),
            )
            if not self.objects.verify(content) or self.objects.read(content) != payload:
                raise AudioContractError("fresh audio output Content verification failed")
        except ObjectStorageError as exc:
            raise AudioContractError("fresh audio output Content verification failed") from exc
        source_artifacts = self._unique_artifact_refs(
            tuple(item.artifact.artifact_ref for item in sources)
            + tuple(item.artifact_ref for item in process_results)
        )
        source_contents = self._unique_content_refs(
            tuple(item.content_ref for item in sources)
            + tuple(item.result_ref for item in process_results)
        )
        artifact = self.artifacts.publish_from_run(
            self.access,
            producer_attempt=producer,
            expected_task_ref=attempt.task_ref,
            expected_task_digest=attempt.task_digest,
            role=role,
            content_ref=content,
            source_refs=(),
            source_artifact_refs=source_artifacts,
            source_content_refs=source_contents,
            derivation_type=derivation,
            metadata={
                "media_type": media_type,
                **({} if metadata is None else dict(metadata)),
            },
        )
        reopened = self.artifacts.get_artifact(self.access, artifact.artifact_ref)
        try:
            reopened_payload = self.objects.read(content)
        except ObjectStorageError as exc:
            raise AudioContractError("fresh audio output Artifact verification failed") from exc
        if reopened.content_ref != content or reopened_payload != payload:
            raise AudioContractError("fresh audio output Artifact verification failed")
        return AudioArtifactContentRef(
            self.project_ref, artifact.artifact_ref.value, content.value, content.digest
        )

    def inspect(
        self, source: AudioArtifactContentRef, validator_ref: str
    ) -> AudioInspection:
        if _ABSOLUTE_REF.fullmatch(validator_ref) is None:
            raise AudioContractError("audio validator_ref is malformed")
        resolved = self._resolve_artifact(source)
        metadata, processes = self._validate_payload(
            resolved.payload,
            expected_media_type=resolved.content_ref.media_type,
            dispatch=self.dispatch,
        )
        report = {
            "metadata": metadata.payload(),
            "source": source.payload(),
            "validator_ref": validator_ref,
            "validator_runtime_ref": self.validator_ref,
        }
        report_payload = _json_bytes(report)
        analysis = self._publish(
            self.dispatch,
            role="audio.analysis",
            payload=report_payload,
            media_type="application/json",
            sources=(resolved,),
            process_results=processes,
            derivation="audio.inspect.full-decode",
            metadata={
                "schema_ref": "schema://minitz/audio-analysis/1",
                "schema_version": "1.0.0",
            },
        )
        return AudioInspection(
            project_ref=self.project_ref,
            source=source,
            duration=metadata.duration,
            sample_rate=metadata.sample_rate,
            channel_layout=metadata.channel_layout,
            codec=metadata.codec,
            analysis_ref=analysis.artifact_ref,
            analysis_sha256=analysis.content_sha256,
            media_type=metadata.media_type,
            container=metadata.container,
            sample_format=metadata.sample_format,
            bit_depth=metadata.bit_depth,
            channels=metadata.channels,
            sample_count=metadata.sample_count,
            bit_rate=metadata.bit_rate,
            tags=metadata.tags,
            content_sha256=metadata.content_sha256,
            pcm_sha256=metadata.pcm_sha256,
            decoder=metadata.decoder,
            peak=metadata.peak,
            rms=metadata.rms,
            loudness_lufs=metadata.loudness_lufs,
            clipping_samples=metadata.clipping_samples,
            silence_samples=metadata.silence_samples,
        )

    def _validate_specification(self, specification: AudioSpecification) -> None:
        if not isinstance(specification, AudioSpecification):
            raise AudioContractError("exact AudioSpecification is required")
        if specification.project_ref != self.project_ref:
            raise AudioContractError("audio specification crossed Project scope")
        if specification.runtime_ref != self.runtime_ref:
            raise AudioContractError("audio specification runtime identity changed")
        if specification.operation not in {*_ROLE_BY_OPERATION, "mix"}:
            raise AudioContractError("deterministic audio runtime cannot claim this operation")
        if (
            specification.time_start is None
            or specification.time_end is None
            or specification.duration is None
            or specification.codec is None
            or specification.sample_format is None
            or specification.bit_depth is None
        ):
            raise AudioContractError("deterministic source processing requires exact decoded fields")
        if specification.media_type != _canonical_media_type(specification.media_type):
            raise AudioContractError("audio specification media type must be canonical")
        if specification.container not in _CONTAINER_MEDIA:
            raise AudioContractError("audio output container is unsupported")
        if _CONTAINER_MEDIA[specification.container] != specification.media_type:
            raise AudioContractError("audio output container and media type differ")
        role = specification.output_contract.get("role")
        if role is not None and role not in AUDIO_ARTIFACT_ROLES:
            raise AudioContractError("audio output role is outside the production pack")

    @staticmethod
    def _source_targets(
        specification: AudioSpecification,
        metadata: AudioDecodedMetadata,
    ) -> tuple[int, tuple[str, ...]]:
        source_rate = specification.source_sample_rate
        target_rate = specification.target_sample_rate
        if source_rate is not None and source_rate != metadata.sample_rate:
            raise AudioContractError("declared source sample rate differs from decoded source")
        output_rate = metadata.sample_rate if target_rate is None else target_rate
        if output_rate != metadata.sample_rate and specification.operation != "resample":
            raise AudioContractError("sample rate change requires exact resample operation")
        source_layout = specification.source_channel_layout
        target_layout = specification.target_channel_layout
        if source_layout is not None and tuple(source_layout) != metadata.channel_layout:
            raise AudioContractError("declared source channel layout differs from decoded source")
        output_layout = metadata.channel_layout if target_layout is None else tuple(target_layout)
        if output_layout != metadata.channel_layout and (
            specification.operation != "convert"
            or specification.tool_config.get("conversion") != "channel"
        ):
            raise AudioContractError("channel change requires explicit channel conversion")
        _layout_name(output_layout)
        return output_rate, output_layout

    @staticmethod
    def _time_filters(
        specification: AudioSpecification, metadata: AudioDecodedMetadata
    ) -> list[str]:
        if (
            specification.time_start is None
            or specification.time_end is None
            or specification.duration is None
        ):
            raise AudioContractError("audio time range must be explicit")
        tolerance = 1.0 / metadata.sample_rate
        end = specification.time_end
        if end > metadata.duration + tolerance:
            raise AudioContractError("audio time range exceeds immutable source duration")
        bounded = specification.operation in {"trim", "segment", "preview"}
        if bounded:
            return [
                f"atrim=start={specification.time_start:.12g}:end={end:.12g}",
                "asetpts=PTS-STARTPTS",
            ]
        if specification.time_start > tolerance or not math.isclose(
            specification.duration, metadata.duration, rel_tol=0.0, abs_tol=tolerance
        ):
            raise AudioContractError("audio duration change requires trim, segment, or preview")
        return []

    @staticmethod
    def _channel_filter(
        source: tuple[str, ...], target: tuple[str, ...]
    ) -> str:
        if source == ("FL", "FR") and target == ("FC",):
            return "pan=mono|c0=0.5*c0+0.5*c1"
        if source == ("FC",) and target == ("FL", "FR"):
            return "pan=stereo|c0=c0|c1=c0"
        raise AudioContractError("explicit channel conversion is unsupported")

    @staticmethod
    def _loudness_filters(
        specification: AudioSpecification, metadata: AudioDecodedMetadata
    ) -> list[str]:
        policy = specification.loudness_policy
        if specification.operation not in {"normalize", "master"}:
            if any(key in policy for key in ("target_lufs", "true_peak_dbfs")):
                raise AudioContractError("loudness target requires normalize or master")
            return []
        target = _number(policy, "target_lufs", minimum=-70.0, maximum=0.0)
        true_peak = _number(policy, "true_peak_dbfs", minimum=-20.0, maximum=0.0)
        gain = target - metadata.loudness_lufs
        filters = [f"volume={gain:.12g}dB"]
        predicted_peak = _true_peak_dbfs(metadata.peak) + gain
        if specification.operation == "master" or predicted_peak > true_peak:
            limit = 10.0 ** (true_peak / 20.0)
            filters.append(f"alimiter=limit={limit:.12g}:attack=5:release=50")
        return filters

    def _operation_filters(
        self,
        specification: AudioSpecification,
        metadata: AudioDecodedMetadata,
        target_rate: int,
        target_layout: tuple[str, ...],
    ) -> list[str]:
        filters = self._time_filters(specification, metadata)
        config = specification.tool_config
        if specification.operation == "resample":
            if target_rate == metadata.sample_rate:
                raise AudioContractError("resample requires distinct explicit sample rates")
            filters.append(f"aresample={target_rate}")
        if target_layout != metadata.channel_layout:
            filters.append(self._channel_filter(metadata.channel_layout, target_layout))
        highpass = _optional_number(config, "highpass_hz", minimum=1.0, maximum=100_000.0)
        lowpass = _optional_number(config, "lowpass_hz", minimum=1.0, maximum=100_000.0)
        if highpass is not None:
            filters.append(f"highpass=f={highpass:.12g}")
        if lowpass is not None:
            filters.append(f"lowpass=f={lowpass:.12g}")
        if highpass is not None and lowpass is not None and highpass >= lowpass:
            raise AudioContractError("audio clean/filter band is inverted")
        gain = _optional_number(config, "gain_db", minimum=-120.0, maximum=120.0)
        if gain is not None:
            if specification.loudness_policy.get("mode") != "relative":
                raise AudioContractError("explicit gain requires relative loudness policy")
            filters.append(f"volume={gain:.12g}dB")
        if specification.operation in {"filter", "clean", "edit"} and not any(
            value is not None for value in (highpass, lowpass, gain)
        ):
            raise AudioContractError("audio filter/edit operation requires exact parameters")
        filters.extend(self._loudness_filters(specification, metadata))
        return filters

    @staticmethod
    def _encoding_args(specification: AudioSpecification) -> tuple[str, ...]:
        sample_format = specification.sample_format
        bit_depth = specification.bit_depth
        if sample_format is None or bit_depth is None:
            raise AudioContractError("audio output sample format and bit depth are required")
        if specification.container == "wav":
            codecs = {
                ("u8", 8): "pcm_u8",
                ("s16", 16): "pcm_s16le",
                ("s32", 24): "pcm_s24le",
                ("s32", 32): "pcm_s32le",
                ("flt", 32): "pcm_f32le",
            }
            try:
                codec = codecs[(sample_format, bit_depth)]
            except KeyError as exc:
                raise AudioContractError("WAV sample format/bit depth is unsupported") from exc
            return (
                "-codec:a",
                codec,
                "-sample_fmt",
                sample_format,
                "-fflags",
                "+bitexact",
                "-flags:a",
                "+bitexact",
                "-f",
                "wav",
                "pipe:1",
            )
        if sample_format not in {"fltp", "s16p"} or bit_depth not in {16, 32}:
            raise AudioContractError("MP3 sample format/bit depth is unsupported")
        bit_rate = specification.tool_config.get("bit_rate")
        if bit_rate is None or re.fullmatch(r"[1-9][0-9]{1,5}k", bit_rate) is None:
            raise AudioContractError("MP3 conversion requires explicit bounded bit_rate")
        return (
            "-codec:a",
            "libmp3lame",
            "-sample_fmt",
            sample_format,
            "-b:a",
            bit_rate,
            "-write_xing",
            "0",
            "-id3v2_version",
            "0",
            "-fflags",
            "+bitexact",
            "-flags:a",
            "+bitexact",
            "-f",
            "mp3",
            "pipe:1",
        )

    def _encode_one(
        self,
        content: ContentRef,
        specification: AudioSpecification,
        dispatch: ScheduledDispatch,
        *,
        filters: Sequence[str],
        target_rate: int,
        target_layout: tuple[str, ...],
        token: str,
    ) -> tuple[bytes, ProcessResult]:
        argv = (
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-i",
            "pipe:0",
            "-map",
            "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-af",
            ",".join(filters) if filters else "anull",
            "-map_metadata",
            "-1",
            "-ar",
            str(target_rate),
            "-ac",
            str(len(target_layout)),
            "-channel_layout",
            _layout_name(target_layout),
            "-threads",
            "1",
            *self._encoding_args(specification),
        )
        result = self._managed_process(
            dispatch,
            executable=_FFMPEG,
            executable_sha256=self._ffmpeg_sha256,
            argv=argv,
            stdin_ref=content,
            idempotency_key=f"audio-transform-{token}",
            stdout_limit_bytes=256 * 1024 * 1024,
        )
        try:
            payload = self.objects.read(result.stdout_ref)
        except ObjectStorageError as exc:
            raise AudioContractError("audio transform output is unavailable") from exc
        if not payload:
            raise AudioContractError("audio transform produced empty output")
        return payload, result

    @staticmethod
    def _verify_output(
        specification: AudioSpecification,
        metadata: AudioDecodedMetadata,
        target_rate: int,
        target_layout: tuple[str, ...],
    ) -> None:
        if specification.duration is None:
            raise AudioContractError("audio output duration must be explicit")
        if (
            metadata.media_type != specification.media_type
            or metadata.container != specification.container
            or metadata.codec != specification.codec
            or metadata.sample_rate != target_rate
            or metadata.channel_layout != target_layout
            or metadata.sample_format != specification.sample_format
            or metadata.bit_depth != specification.bit_depth
        ):
            raise AudioContractError("fresh audio output differs from exact format specification")
        tolerance = 0.05 if metadata.container == "mp3" else 1.0 / target_rate
        if not math.isclose(
            metadata.duration,
            specification.duration,
            rel_tol=0.0,
            abs_tol=tolerance,
        ):
            raise AudioContractError("fresh audio output duration differs from specification")
        if specification.operation in {"normalize", "master"}:
            target = _number(
                specification.loudness_policy,
                "target_lufs",
                minimum=-70.0,
                maximum=0.0,
            )
            if abs(metadata.loudness_lufs - target) > 1.0:
                raise AudioContractError("fresh audio output missed exact loudness target")

    @staticmethod
    def _derivation(specification: AudioSpecification, source: AudioDecodedMetadata) -> str:
        if specification.operation == "convert" and specification.target_channel_layout is not None and tuple(specification.target_channel_layout) != source.channel_layout:
            return "audio.channel-convert"
        if specification.operation == "convert":
            return "audio.format-convert"
        return f"audio.{specification.operation}"

    def execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        specification: AudioSpecification,
    ) -> AudioOutputRef:
        if access != self.access:
            raise AudioContractError("audio execute ProjectAccess differs from bound authority")
        if attempt != self.dispatch.node_attempt:
            raise AudioContractError("audio execute attempt differs from bound dispatch")
        self._require_dispatch(self.dispatch, attempt.attempt_id, attempt.fence)
        return self._execute_authorized(specification, self.dispatch, attempt)

    def execute_dispatched(
        self, specification: AudioSpecification, dispatch: ScheduledDispatch
    ) -> AudioOutputRef:
        attempt = self._require_dispatch(
            dispatch, dispatch.node_attempt.attempt_id, dispatch.node_attempt.fence
        )
        return self._execute_authorized(specification, dispatch, attempt)

    def _execute_authorized(
        self,
        specification: AudioSpecification,
        dispatch: ScheduledDispatch,
        attempt: NodeExecutionAttempt,
    ) -> AudioOutputRef:
        self._validate_specification(specification)
        if specification.operation == "mix":
            raise AudioContractError("mix requires exact MixSpecification and mix()")
        if len(specification.sources) != 1:
            raise AudioContractError("deterministic audio edit requires one exact source")
        resolved = self._resolve_artifact(specification.sources[0])
        source_metadata, source_processes = self._validate_payload(
            resolved.payload,
            expected_media_type=resolved.content_ref.media_type,
            dispatch=dispatch,
        )
        target_rate, target_layout = self._source_targets(specification, source_metadata)
        filters = self._operation_filters(
            specification, source_metadata, target_rate, target_layout
        )
        token = hashlib.sha256(
            f"{attempt.attempt_id}:{attempt.fence}:{specification.canonical_digest}".encode()
        ).hexdigest()[:40]
        transformed, transform_process = self._encode_one(
            resolved.content_ref,
            specification,
            dispatch,
            filters=filters,
            target_rate=target_rate,
            target_layout=target_layout,
            token=token,
        )
        output_metadata, output_processes = self._validate_payload(
            transformed,
            expected_media_type=specification.media_type,
            dispatch=dispatch,
        )
        self._verify_output(specification, output_metadata, target_rate, target_layout)
        derivation = self._derivation(specification, source_metadata)
        requested_role = specification.output_contract.get("role")
        role = requested_role or _ROLE_BY_OPERATION[specification.operation]
        output = self._publish(
            dispatch,
            role=role,
            payload=transformed,
            media_type=specification.media_type,
            sources=(resolved,),
            process_results=(*source_processes, transform_process, *output_processes),
            derivation=derivation,
            metadata={
                "schema_ref": "schema://minitz/audio-output/1",
                "schema_version": "1.0.0",
            },
        )
        return AudioOutputRef.create(
            project_ref=self.project_ref,
            specification=specification,
            output=output,
            duration=output_metadata.duration,
            sample_rate=output_metadata.sample_rate,
            channel_layout=output_metadata.channel_layout,
            codec=output_metadata.codec,
            sample_format=output_metadata.sample_format,
            bit_depth=output_metadata.bit_depth,
            producer_attempt_id=attempt.attempt_id,
            producer_fence=attempt.fence,
            derivation=f"{derivation}:{specification.recipe_sha256}",
        )

    def execute_stems(
        self,
        specifications: Mapping[str, AudioSpecification],
        dispatches: Mapping[str, ScheduledDispatch],
    ) -> AudioStemBatch:
        if not isinstance(specifications, Mapping) or not isinstance(dispatches, Mapping):
            raise AudioContractError("independent stems require exact mappings")
        specification_map, dispatch_map = dict(specifications), dict(dispatches)
        if not specification_map or set(specification_map) != set(dispatch_map):
            raise AudioContractError("stem specification and dispatch keys must match")
        if len(specification_map) > 32:
            raise AudioContractError("stem fanout is unbounded")
        values = tuple(dispatch_map.values())
        if any(not isinstance(item, ScheduledDispatch) for item in values):
            raise AudioContractError("stem dispatch is malformed")
        if (
            len({item.allocation.allocation_ref for item in values}) != len(values)
            or len({item.node_attempt.attempt_id for item in values}) != len(values)
            or len({item.node_attempt.node_ref for item in values}) != len(values)
        ):
            raise AudioContractError("independent stems require distinct dispatch identities")
        for key in sorted(specification_map):
            self._validate_specification(specification_map[key])
            self._require_dispatch(
                dispatch_map[key],
                dispatch_map[key].node_attempt.attempt_id,
                dispatch_map[key].node_attempt.fence,
            )
        outputs: dict[str, AudioOutputRef] = {}
        failures: dict[str, str] = {}
        with ThreadPoolExecutor(
            max_workers=len(specification_map), thread_name_prefix="minitz-audio"
        ) as executor:
            futures = {
                key: executor.submit(
                    self.execute_dispatched, specification_map[key], dispatch_map[key]
                )
                for key in sorted(specification_map)
            }
            for key in sorted(futures):
                try:
                    outputs[key] = futures[key].result()
                except Exception as exc:
                    detail = str(exc) or type(exc).__name__
                    failures[key] = detail[:2048]
        return AudioStemBatch(outputs, failures)

    @staticmethod
    def _parse_mix_level(value: str) -> _MixLevel:
        try:
            loaded: object = json.loads(value)
        except json.JSONDecodeError as exc:
            try:
                gain = float(value)
            except ValueError:
                raise AudioContractError("mix level is malformed") from exc
            if not math.isfinite(gain) or not -120.0 <= gain <= 120.0:
                raise AudioContractError("mix gain is invalid")
            return _MixLevel(0.0, gain, 0.0, ())
        if not isinstance(loaded, dict):
            raise AudioContractError("mix level must be JSON object or gain number")
        record = cast(dict[str, object], loaded)
        if set(record) != {"effects", "gain_db", "offset_seconds", "pan"}:
            raise AudioContractError("mix level fields are incomplete or unknown")
        numeric: dict[str, float] = {}
        for name in ("gain_db", "offset_seconds", "pan"):
            raw = record[name]
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise AudioContractError(f"mix {name} is invalid")
            numeric[name] = float(raw)
            if not math.isfinite(numeric[name]):
                raise AudioContractError(f"mix {name} is invalid")
        if numeric["offset_seconds"] < 0.0 or not -120.0 <= numeric["gain_db"] <= 120.0 or not -1.0 <= numeric["pan"] <= 1.0:
            raise AudioContractError("mix offset, gain, or pan is out of range")
        effects_value = record["effects"]
        if not isinstance(effects_value, list) or not all(
            isinstance(item, str) and item for item in effects_value
        ):
            raise AudioContractError("mix effects are malformed")
        effects = tuple(cast(list[str], effects_value))
        if len(effects) != len(set(effects)) or len(effects) > 16:
            raise AudioContractError("mix effects are duplicated or unbounded")
        return _MixLevel(
            numeric["offset_seconds"], numeric["gain_db"], numeric["pan"], effects
        )

    @staticmethod
    def _mix_effect(value: str) -> str:
        parts = value.split(":", 1)
        if len(parts) != 2 or parts[0] not in {"highpass", "lowpass"}:
            raise AudioContractError("mix effect is unsupported")
        try:
            frequency = float(parts[1])
        except ValueError as exc:
            raise AudioContractError("mix effect frequency is invalid") from exc
        if not math.isfinite(frequency) or not 1.0 <= frequency <= 100_000.0:
            raise AudioContractError("mix effect frequency is invalid")
        return f"{parts[0]}=f={frequency:.12g}"

    @staticmethod
    def _pan_filter(pan: float, layout: tuple[str, ...]) -> str | None:
        if layout == ("FC",):
            if pan != 0.0:
                raise AudioContractError("mono stem cannot claim non-zero pan")
            return None
        if layout != ("FL", "FR"):
            raise AudioContractError("mix pan requires mono or stereo stems")
        if pan == 0.0:
            return None
        left = math.cos((pan + 1.0) * math.pi / 4.0)
        right = math.sin((pan + 1.0) * math.pi / 4.0)
        return f"pan=stereo|c0={left:.12g}*c0|c1={right:.12g}*c1"

    def _mix_once(
        self,
        resolved: Sequence[_ResolvedAudio],
        metadata: Sequence[AudioDecodedMetadata],
        levels: Sequence[_MixLevel],
        specification: AudioSpecification,
        dispatch: ScheduledDispatch,
        *,
        target_rate: int,
        target_layout: tuple[str, ...],
        token: str,
    ) -> tuple[bytes, ProcessResult]:
        argv: list[str] = ["-hide_banner", "-nostdin", "-v", "error"]
        filters: list[str] = []
        outputs: list[str] = []
        for index, (source, source_metadata, level) in enumerate(
            zip(resolved, metadata, levels, strict=True)
        ):
            suffix = ".wav" if source_metadata.container == "wav" else ".mp3"
            stage_name = f".minitz-audio-{token}-stem-{index}{suffix}"
            stage_path = f"{self.working_directory}/{stage_name}"
            try:
                self.filesystem.write(
                    self.access,
                    dispatch.node_attempt,
                    root_ref=self.root_ref,
                    path=stage_path,
                    content_ref=source.content_ref,
                    idempotency_key=f"audio-stage-{token}-{index}",
                )
                staged = self.filesystem.read(
                    self.access,
                    dispatch.node_attempt,
                    root_ref=self.root_ref,
                    path=stage_path,
                    media_type=source.content_ref.media_type,
                    idempotency_key=f"audio-stage-read-{token}-{index}",
                ).output_ref
            except FilesystemError as exc:
                raise AudioContractError("mix stem staging failed") from exc
            if staged.digest != source.content_ref.digest or staged.size_bytes != source.content_ref.size_bytes:
                raise AudioContractError("mix staged stem identity changed")
            argv.extend(("-i", stage_name))
            chain = [
                f"adelay={round(level.offset_seconds * source_metadata.sample_rate)}S:all=1",
                f"volume={level.gain_db:.12g}dB",
            ]
            pan = self._pan_filter(level.pan, source_metadata.channel_layout)
            if pan is not None:
                chain.append(pan)
            chain.extend(self._mix_effect(effect) for effect in level.effects)
            output = f"stemout{index}"
            filters.append(f"[{index}:a]{','.join(chain)}[{output}]")
            outputs.append(f"[{output}]")
        filters.append(
            f"{''.join(outputs)}amix=inputs={len(outputs)}:duration=longest:dropout_transition=0:normalize=0[mixout]"
        )
        argv.extend(
            (
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[mixout]",
                "-map_metadata",
                "-1",
                "-ar",
                str(target_rate),
                "-ac",
                str(len(target_layout)),
                "-channel_layout",
                _layout_name(target_layout),
                "-threads",
                "1",
                *self._encoding_args(specification),
            )
        )
        result = self._managed_process(
            dispatch,
            executable=_FFMPEG,
            executable_sha256=self._ffmpeg_sha256,
            argv=tuple(argv),
            stdin_ref=None,
            idempotency_key=f"audio-mix-{token}",
            stdout_limit_bytes=256 * 1024 * 1024,
        )
        try:
            payload = self.objects.read(result.stdout_ref)
        except ObjectStorageError as exc:
            raise AudioContractError("audio mix output is unavailable") from exc
        if not payload:
            raise AudioContractError("audio mix produced empty output")
        return payload, result

    def mix(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        specification: AudioSpecification,
        mix_specification: MixSpecification,
    ) -> AudioMixResult:
        if access != self.access or attempt != self.dispatch.node_attempt:
            raise AudioContractError("audio mix authority differs from bound dispatch")
        self._require_dispatch(self.dispatch, attempt.attempt_id, attempt.fence)
        self._validate_specification(specification)
        if specification.operation != "mix":
            raise AudioContractError("audio mix requires operation=mix")
        if not isinstance(mix_specification, MixSpecification) or mix_specification.project_ref != self.project_ref:
            raise AudioContractError("MixSpecification crossed Project scope")
        stems = tuple(mix_specification.stems)
        if len(stems) < 2 or len(stems) > 32 or len({stem.stem_id for stem in stems}) != len(stems):
            raise AudioContractError("mix requires bounded unique stems")
        if tuple(specification.sources) != tuple(stem.output for stem in stems):
            raise AudioContractError("mix AudioSpecification does not bind exact stem outputs")
        resolved = tuple(self._resolve_artifact(stem.output) for stem in stems)
        metadata_and_processes = tuple(
            self._validate_payload(
                item.payload,
                expected_media_type=item.content_ref.media_type,
                dispatch=self.dispatch,
            )
            for item in resolved
        )
        metadata = tuple(item[0] for item in metadata_and_processes)
        validation_processes = tuple(
            process for item in metadata_and_processes for process in item[1]
        )
        target_rate, target_layout = self._source_targets(specification, metadata[0])
        for item in metadata[1:]:
            if item.sample_rate != target_rate or item.channel_layout != target_layout:
                raise AudioContractError("mix stems require exact preprocessed rate and layout")
        levels = tuple(
            self._parse_mix_level(mix_specification.levels[stem.stem_id]) for stem in stems
        )
        expected_duration = max(
            level.offset_seconds + item.duration
            for level, item in zip(levels, metadata, strict=True)
        )
        if specification.duration is None:
            raise AudioContractError("mix duration must be explicit")
        if not math.isclose(
            expected_duration,
            specification.duration,
            rel_tol=0.0,
            abs_tol=1.0 / target_rate,
        ):
            raise AudioContractError("mix offsets and duration do not match exact specification")
        token = hashlib.sha256(
            f"{attempt.attempt_id}:{mix_specification.mix_ref}:{specification.canonical_digest}".encode()
        ).hexdigest()[:40]
        raw_mix, mix_process = self._mix_once(
            resolved,
            metadata,
            levels,
            specification,
            self.dispatch,
            target_rate=target_rate,
            target_layout=target_layout,
            token=token,
        )
        raw_metadata, raw_processes = self._validate_payload(
            raw_mix,
            expected_media_type=specification.media_type,
            dispatch=self.dispatch,
        )
        final_payload = raw_mix
        final_metadata = raw_metadata
        extra_processes: tuple[ProcessResult, ...] = ()
        if specification.loudness_policy:
            filters = self._loudness_filters(
                AudioSpecification.create(
                    project_ref=specification.project_ref,
                    audio_id=specification.audio_id,
                    sources=specification.sources,
                    operation="master",
                    recipe_ref=specification.recipe_ref,
                    recipe_sha256=specification.recipe_sha256,
                    time_start=0.0,
                    time_end=raw_metadata.duration,
                    duration=raw_metadata.duration,
                    source_sample_rate=raw_metadata.sample_rate,
                    target_sample_rate=raw_metadata.sample_rate,
                    source_channel_layout=raw_metadata.channel_layout,
                    target_channel_layout=raw_metadata.channel_layout,
                    media_type=specification.media_type,
                    container=specification.container,
                    codec=specification.codec,
                    sample_format=specification.sample_format,
                    bit_depth=specification.bit_depth,
                    processing_chain=specification.processing_chain,
                    tool_config=specification.tool_config,
                    loudness_policy=specification.loudness_policy,
                    measurement_algorithm_ref=specification.measurement_algorithm_ref,
                    spatial_metadata=specification.spatial_metadata,
                    model_ref=specification.model_ref,
                    model_version=specification.model_version,
                    runtime_ref=specification.runtime_ref,
                    seed=specification.seed,
                    voice_ref=specification.voice_ref,
                    language=specification.language,
                    prompt=specification.prompt,
                    validator_ref=specification.validator_ref,
                    output_contract=specification.output_contract,
                ),
                raw_metadata,
            )
            raw_content = self.objects.put(raw_mix, media_type=specification.media_type)
            final_payload, normalization_process = self._encode_one(
                raw_content,
                specification,
                self.dispatch,
                filters=filters,
                target_rate=target_rate,
                target_layout=target_layout,
                token=f"mix-normalize-{token}"[:40],
            )
            final_metadata, final_process_pair = self._validate_payload(
                final_payload,
                expected_media_type=specification.media_type,
                dispatch=self.dispatch,
            )
            extra_processes = (normalization_process, *final_process_pair)
        self._verify_output(specification, final_metadata, target_rate, target_layout)
        output_ref = self._publish(
            self.dispatch,
            role=specification.output_contract.get("role", "audio.mix"),
            payload=final_payload,
            media_type=specification.media_type,
            sources=resolved,
            process_results=(
                *validation_processes,
                mix_process,
                *raw_processes,
                *extra_processes,
            ),
            derivation="audio.mix",
            metadata={
                "schema_ref": "schema://minitz/audio-mix/1",
                "schema_version": "1.0.0",
            },
        )
        output = AudioOutputRef.create(
            project_ref=self.project_ref,
            specification=specification,
            output=output_ref,
            duration=final_metadata.duration,
            sample_rate=final_metadata.sample_rate,
            channel_layout=final_metadata.channel_layout,
            codec=final_metadata.codec,
            sample_format=final_metadata.sample_format,
            bit_depth=final_metadata.bit_depth,
            producer_attempt_id=attempt.attempt_id,
            producer_fence=attempt.fence,
            derivation=f"audio.mix:{specification.recipe_sha256}",
        )
        target_lufs = (
            None
            if "target_lufs" not in specification.loudness_policy
            else _number(specification.loudness_policy, "target_lufs", minimum=-70.0, maximum=0.0)
        )
        target_peak = (
            None
            if "true_peak_dbfs" not in specification.loudness_policy
            else _number(specification.loudness_policy, "true_peak_dbfs", minimum=-20.0, maximum=0.0)
        )
        actual_peak = _true_peak_dbfs(final_metadata.peak)
        measurements = AudioTargetMeasurements(
            self.project_ref,
            final_metadata.loudness_lufs,
            target_lufs,
            actual_peak,
            target_peak,
            final_metadata.duration,
            final_metadata.sample_rate,
            final_metadata.channel_layout,
            (target_lufs is None or abs(final_metadata.loudness_lufs - target_lufs) <= 1.0)
            and (target_peak is None or actual_peak <= target_peak + 0.1),
        )
        session_report = {
            "levels": dict(mix_specification.levels),
            "measurements": measurements.payload(),
            "mix_output": output.output.payload(),
            "mix_ref": mix_specification.mix_ref,
            "specification_digest": specification.canonical_digest,
            "stems": [
                {
                    "output": stem.output.payload(),
                    "specification_digest": stem.specification.canonical_digest,
                    "stem_id": stem.stem_id,
                }
                for stem in stems
            ],
            "tool_ref": self.tool_ref,
            "tool_version": _VERSION,
        }
        output_resolved = self._resolve_artifact(output.output)
        session_ref = self._publish(
            self.dispatch,
            role="audio.session",
            payload=_json_bytes(session_report),
            media_type="application/json",
            sources=(output_resolved, *resolved),
            process_results=(),
            derivation="audio.mix.session",
            metadata={
                "schema_ref": "schema://minitz/audio-session/1",
                "schema_version": "1.0.0",
            },
        )
        session = EditableAudioSessionBinding(
            self.project_ref, specification, session_ref, self.tool_ref, _VERSION
        )
        return AudioMixResult(output, session, measurements)

    def bind_game_handoff(
        self,
        output: AudioOutputRef,
        target: AudioArtifactContentRef,
        integration_ref: str,
    ) -> GameAudioHandoffBinding:
        self._resolve_handoff(output, target, integration_ref)
        return GameAudioHandoffBinding(self.project_ref, output, target, integration_ref)

    def bind_video_handoff(
        self,
        output: AudioOutputRef,
        target: AudioArtifactContentRef,
        integration_ref: str,
    ) -> VideoAudioHandoffBinding:
        self._resolve_handoff(output, target, integration_ref)
        return VideoAudioHandoffBinding(self.project_ref, output, target, integration_ref)

    def _resolve_handoff(
        self,
        output: AudioOutputRef,
        target: AudioArtifactContentRef,
        integration_ref: str,
    ) -> None:
        if (
            not isinstance(output, AudioOutputRef)
            or output.project_ref != self.project_ref
            or not isinstance(target, AudioArtifactContentRef)
            or target.project_ref != self.project_ref
            or _ABSOLUTE_REF.fullmatch(integration_ref) is None
        ):
            raise AudioContractError("audio handoff identity crossed Project or is malformed")
        self._resolve_artifact(output.output)
        self._resolve_artifact(target)


__all__ = [
    "AudioDecodedMetadata",
    "AudioInspection",
    "AudioMixResult",
    "AudioStemBatch",
    "AudioTargetMeasurements",
    "DeterministicAudioTool",
]
