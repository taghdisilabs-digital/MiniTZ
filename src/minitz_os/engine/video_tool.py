"""REAL provider-neutral video processing on existing MiniTZ authorities."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import cast

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .execution import NodeExecutionAttempt, NodeExecutionError, NodeExecutionService
from .filesystem import FilesystemRootRef
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
from .video_pack import (
    VIDEO_ARTIFACT_ROLES,
    AudioTrackBinding,
    EditableVideoSessionBinding,
    GameVideoHandoffBinding,
    SubtitleTrackBinding,
    VideoArtifactContentRef,
    VideoContractError,
    VideoInspectionRef,
    VideoOutputRef,
    VideoSpecification,
    VideoToolAdapter,
)


_FFMPEG = Path("/usr/bin/ffmpeg")
_FFPROBE = Path("/usr/bin/ffprobe")
_VERSION = "8.0.1"
_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_MEDIA_ALIASES = {
    "application/x-subrip": "application/x-subrip",
    "audio/mpeg": "audio/mpeg",
    "audio/mp4": "audio/mp4",
    "audio/wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/x-wav": "audio/wav",
    "text/plain": "application/x-subrip",
    "video/mp4": "video/mp4",
}
_COLOR_POLICIES = {
    "color://bt709/v1": ("bt709", "bt709", "bt709", "tv"),
    "color://rec709/v1": ("bt709", "bt709", "bt709", "tv"),
}
_FFMPEG_COLOR_COMPONENTS = frozenset({"bt709", "smpte170m"})
_FFMPEG_COLOR_RANGES = frozenset({"pc", "tv"})
_ROLE_BY_OPERATION = {
    "compose": "video.composite",
    "edit": "video.clip",
    "encode": "video.export",
    "export": "video.export",
    "mux": "video.export",
    "preview": "video.proxy",
    "transcode": "video.clip",
    "trim": "video.clip",
}
_SUPPORTED_OPERATIONS = frozenset(_ROLE_BY_OPERATION)


def _file_sha256(path: Path) -> str:
    if not path.is_absolute() or not path.is_file():
        raise VideoContractError(f"required video executable is unavailable: {path}")
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
        raise VideoContractError("video media type is unsupported") from exc


def _artifact_ref(project_ref: ProjectRef, value: str) -> ArtifactRef:
    parts = value.rsplit("/", 2)
    if len(parts) != 3 or parts[0] != f"artifact://{project_ref.value}":
        raise VideoContractError("video ArtifactRef is invalid or crossed Project scope")
    try:
        return ArtifactRef(project_ref, parts[1], int(parts[2]))
    except (TypeError, ValueError) as exc:
        raise VideoContractError("video ArtifactRef is malformed") from exc


def _freeze(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise VideoContractError("ffprobe evidence contains a non-finite number")
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in cast(Sequence[object], value))
    if isinstance(value, Mapping):
        record = cast(Mapping[object, object], value)
        result: dict[str, object] = {}
        for key, item in record.items():
            if not isinstance(key, str):
                raise VideoContractError("ffprobe evidence has a non-text key")
            result[key] = _freeze(item)
        return MappingProxyType(dict(sorted(result.items())))
    raise VideoContractError("ffprobe evidence contains an unsupported value")


def _freeze_record(value: Mapping[str, object]) -> Mapping[str, object]:
    frozen = _freeze(dict(value))
    if not isinstance(frozen, Mapping):
        raise VideoContractError("ffprobe record is malformed")
    return cast(Mapping[str, object], frozen)


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        _thaw(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _record(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise VideoContractError(f"ffprobe {label} is malformed")
    record = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in record):
        raise VideoContractError(f"ffprobe {label} is malformed")
    return cast(dict[str, object], record)


def _optional_text(value: object) -> str | None:
    if value is None or value == "N/A":
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise VideoContractError("ffprobe text field is malformed")
    result = str(value)
    if not result:
        raise VideoContractError("ffprobe text field is empty")
    return result


def _optional_float(value: object, label: str) -> float | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        result = float(text)
    except ValueError as exc:
        raise VideoContractError(f"ffprobe {label} is malformed") from exc
    if not math.isfinite(result):
        raise VideoContractError(f"ffprobe {label} is not finite")
    return result


def _optional_int(value: object, label: str) -> int | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        result = int(text)
    except ValueError as exc:
        raise VideoContractError(f"ffprobe {label} is malformed") from exc
    if result < 0:
        raise VideoContractError(f"ffprobe {label} is negative")
    return result


def _required_int(value: object, label: str) -> int:
    result = _optional_int(value, label)
    if result is None:
        raise VideoContractError(f"ffprobe {label} is missing")
    return result


def _tags(value: object) -> Mapping[str, str]:
    if value is None:
        return MappingProxyType({})
    record = _record(value, "tags")
    result: dict[str, str] = {}
    for key, item in record.items():
        if not isinstance(item, (str, int, float)) or isinstance(item, bool):
            raise VideoContractError("ffprobe tag is malformed")
        result[key.lower()] = str(item)
    return MappingProxyType(dict(sorted(result.items())))


def _fraction(value: str, label: str, *, allow_zero: bool = False) -> Fraction:
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise VideoContractError(f"{label} is not a valid rational") from exc
    if result < 0 or (not allow_zero and result == 0):
        raise VideoContractError(f"{label} must be positive")
    return result


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _seconds(value: float) -> str:
    if not math.isfinite(value) or value < 0.0:
        raise VideoContractError("video timestamp is invalid")
    return f"{value:.12f}".rstrip("0").rstrip(".") or "0"


@dataclass(frozen=True)
class VideoStreamEvidence:
    """One complete ffprobe stream record normalized for validation."""

    index: int
    codec_type: str
    codec_name: str
    profile: str | None
    time_base: str
    start_time: float | None
    duration: float | None
    bit_rate: int | None
    width: int | None
    height: int | None
    pixel_format: str | None
    average_frame_rate: str | None
    real_frame_rate: str | None
    sample_rate: int | None
    channels: int | None
    frame_count: int | None
    packet_count: int | None
    color_range: str | None
    color_space: str | None
    color_transfer: str | None
    color_primaries: str | None
    tags: Mapping[str, str]
    disposition: Mapping[str, int]
    evidence: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.index < 0 or self.codec_type not in {"audio", "subtitle", "video"}:
            raise VideoContractError("ffprobe stream identity is malformed")
        if not self.codec_name or not self.time_base:
            raise VideoContractError("ffprobe stream codec/timebase is missing")
        _fraction(self.time_base, "stream time_base")
        for value in (self.start_time, self.duration):
            if value is not None and (not math.isfinite(value) or value < 0.0):
                raise VideoContractError("ffprobe stream timing is malformed")
        for value in (
            self.bit_rate,
            self.width,
            self.height,
            self.sample_rate,
            self.channels,
            self.frame_count,
            self.packet_count,
        ):
            if value is not None and value < 0:
                raise VideoContractError("ffprobe stream dimension is malformed")
        object.__setattr__(self, "tags", MappingProxyType(dict(sorted(self.tags.items()))))
        object.__setattr__(
            self, "disposition", MappingProxyType(dict(sorted(self.disposition.items())))
        )
        object.__setattr__(self, "evidence", _freeze_record(self.evidence))

    def payload(self) -> dict[str, object]:
        return {
            "average_frame_rate": self.average_frame_rate,
            "bit_rate": self.bit_rate,
            "channels": self.channels,
            "codec_name": self.codec_name,
            "codec_type": self.codec_type,
            "color_primaries": self.color_primaries,
            "color_range": self.color_range,
            "color_space": self.color_space,
            "color_transfer": self.color_transfer,
            "disposition": dict(self.disposition),
            "duration": self.duration,
            "evidence": _thaw(self.evidence),
            "frame_count": self.frame_count,
            "height": self.height,
            "index": self.index,
            "packet_count": self.packet_count,
            "pixel_format": self.pixel_format,
            "profile": self.profile,
            "real_frame_rate": self.real_frame_rate,
            "sample_rate": self.sample_rate,
            "start_time": self.start_time,
            "tags": dict(self.tags),
            "time_base": self.time_base,
            "width": self.width,
        }


@dataclass(frozen=True)
class VideoDecodedMetadata:
    """Container/stream evidence plus hashes from complete decoded streams."""

    media_type: str
    container: str
    format_names: tuple[str, ...]
    format_long_name: str
    start_time: float
    duration: float
    size_bytes: int
    bit_rate: int | None
    tags: Mapping[str, str]
    streams: tuple[VideoStreamEvidence, ...]
    decoded_units: Mapping[int, int]
    decoded_sha256: Mapping[int, str]
    content_sha256: str
    decoder: str
    format_evidence: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.media_type != "video/mp4" or self.container != "mp4":
            raise VideoContractError("decoded video container is unsupported")
        if not self.format_names or not self.format_long_name:
            raise VideoContractError("decoded video format evidence is incomplete")
        if (
            not math.isfinite(self.start_time)
            or not math.isfinite(self.duration)
            or self.start_time < 0.0
            or self.duration <= 0.0
            or self.size_bytes < 1
        ):
            raise VideoContractError("decoded video format timing/size is malformed")
        if self.bit_rate is not None and self.bit_rate < 1:
            raise VideoContractError("decoded video bit rate is malformed")
        video_streams = tuple(item for item in self.streams if item.codec_type == "video")
        if len(video_streams) != 1:
            raise VideoContractError("video requires one exact primary stream")
        decoded_types = {item.index for item in self.streams if item.codec_type in {"audio", "video"}}
        if set(self.decoded_units) != decoded_types or set(self.decoded_sha256) != decoded_types:
            raise VideoContractError("full decoded stream evidence is incomplete")
        if any(value < 1 for value in self.decoded_units.values()):
            raise VideoContractError("full decode produced no frames or samples")
        for value in (self.content_sha256, *self.decoded_sha256.values()):
            if re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise VideoContractError("decoded video digest is malformed")
        object.__setattr__(self, "streams", tuple(self.streams))
        object.__setattr__(self, "tags", MappingProxyType(dict(sorted(self.tags.items()))))
        object.__setattr__(
            self, "decoded_units", MappingProxyType(dict(sorted(self.decoded_units.items())))
        )
        object.__setattr__(
            self,
            "decoded_sha256",
            MappingProxyType(dict(sorted(self.decoded_sha256.items()))),
        )
        object.__setattr__(self, "format_evidence", _freeze_record(self.format_evidence))

    @property
    def video_stream(self) -> VideoStreamEvidence:
        return next(item for item in self.streams if item.codec_type == "video")

    @property
    def fps(self) -> str:
        stream = self.video_stream
        value = stream.real_frame_rate or stream.average_frame_rate
        if value is None:
            raise VideoContractError("decoded video frame rate is missing")
        return _fraction_text(_fraction(value, "decoded frame rate"))

    def payload(self) -> dict[str, object]:
        return {
            "bit_rate": self.bit_rate,
            "container": self.container,
            "content_sha256": self.content_sha256,
            "decoded_sha256": {str(key): value for key, value in self.decoded_sha256.items()},
            "decoded_units": {str(key): value for key, value in self.decoded_units.items()},
            "decoder": self.decoder,
            "duration": self.duration,
            "format_evidence": _thaw(self.format_evidence),
            "format_long_name": self.format_long_name,
            "format_names": list(self.format_names),
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "start_time": self.start_time,
            "streams": [item.payload() for item in self.streams],
            "tags": dict(self.tags),
        }


@dataclass(frozen=True)
class VideoInspection(VideoInspectionRef):
    """VideoInspectionRef extended with the complete qualification evidence."""

    media_type: str
    container: str
    time_base: str
    pixel_format: str
    color_range: str | None
    color_space: str | None
    color_transfer: str | None
    color_primaries: str | None
    frame_count: int
    bit_rate: int | None
    tags: Mapping[str, str]
    streams: tuple[VideoStreamEvidence, ...]
    content_sha256: str
    decoded_sha256: Mapping[int, str]
    decoder: str
    format_evidence: Mapping[str, object]

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.media_type != "video/mp4" or self.container != "mp4":
            raise VideoContractError("inspection container is unsupported")
        if not self.pixel_format or self.frame_count < 1:
            raise VideoContractError("inspection decode evidence is incomplete")
        _fraction(self.time_base, "inspection time_base")
        object.__setattr__(self, "tags", MappingProxyType(dict(sorted(self.tags.items()))))
        object.__setattr__(self, "streams", tuple(self.streams))
        object.__setattr__(
            self,
            "decoded_sha256",
            MappingProxyType(dict(sorted(self.decoded_sha256.items()))),
        )
        object.__setattr__(self, "format_evidence", _freeze_record(self.format_evidence))


@dataclass(frozen=True)
class VideoRenderResult:
    output: VideoOutputRef
    timeline: VideoArtifactContentRef
    session: EditableVideoSessionBinding

    def __post_init__(self) -> None:
        project_ref = self.output.project_ref
        if self.timeline.project_ref != project_ref or self.session.project_ref != project_ref:
            raise VideoContractError("video render provenance crossed Project scope")


@dataclass(frozen=True)
class _ResolvedMedia:
    contract: VideoArtifactContentRef
    artifact: Artifact
    content_ref: ContentRef
    payload: bytes


@dataclass(frozen=True)
class _ProbedMedia:
    media_type: str
    container: str
    format_names: tuple[str, ...]
    format_long_name: str
    start_time: float
    duration: float
    size_bytes: int
    bit_rate: int | None
    tags: Mapping[str, str]
    streams: tuple[VideoStreamEvidence, ...]
    format_evidence: Mapping[str, object]


@dataclass(frozen=True)
class _ValidatedMedia:
    probe: _ProbedMedia
    decoded_units: Mapping[int, int]
    decoded_sha256: Mapping[int, str]
    processes: tuple[ProcessResult, ...]
    content_sha256: str


@dataclass(frozen=True)
class _VideoSegment:
    source: _ResolvedMedia
    metadata: VideoDecodedMetadata
    source_start: float
    source_end: float
    timeline_start: float
    timeline_end: float


class DeterministicVideoTool(VideoToolAdapter):
    """Bound FFmpeg 8.x video node; scheduler authority is supplied upstream."""

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
        runtime_ref: str = "runtime://video/ffmpeg-8.0.1-cpu",
        validator_ref: str = "validator://video/ffmpeg-full-decode/v1",
    ) -> None:
        if not isinstance(access, ProjectAccess):
            raise VideoContractError("exact ProjectAccess is required")
        if not isinstance(dispatch, ScheduledDispatch):
            raise VideoContractError("exact ScheduledDispatch is required")
        if not isinstance(root_ref, FilesystemRootRef) or root_ref.project_ref != access.project_ref:
            raise VideoContractError("video FilesystemRoot crossed Project scope")
        if not isinstance(working_directory, str) or not working_directory:
            raise VideoContractError("video working directory is required")
        for value, label in (
            (tool_ref, "tool_ref"),
            (runtime_ref, "runtime_ref"),
            (validator_ref, "validator_ref"),
        ):
            if _ABSOLUTE_REF.fullmatch(value) is None:
                raise VideoContractError(f"video {label} is malformed")
        if not isinstance(object_store, ObjectStorageBackend):
            raise VideoContractError("ObjectStorageBackend is required")
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
            raise VideoContractError("exact ScheduledDispatch is required")
        allocation, attempt = dispatch.allocation, dispatch.node_attempt
        if (
            allocation.project_ref != self.project_ref
            or attempt.node_ref.project_ref != self.project_ref
            or producer_attempt_id != attempt.attempt_id
            or producer_fence != attempt.fence
        ):
            raise VideoContractError("video producer attempt/fence crossed Project or authority")
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
            raise VideoContractError("video dispatch allocation/attempt evidence is stale or forged")
        try:
            current = self.executions.get_node_execution(self.access, attempt.node_ref)
        except NodeExecutionError as exc:
            raise VideoContractError("video Node attempt evidence is unavailable") from exc
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
            raise VideoContractError("video Node attempt is not current")
        try:
            node_expiry = datetime.fromisoformat(attempt.lease_expires_at)
            allocation_expiry = datetime.fromisoformat(allocation.lease_expires_at)
            now = datetime.now(node_expiry.tzinfo)
        except (TypeError, ValueError) as exc:
            raise VideoContractError("video dispatch lease is malformed") from exc
        if node_expiry <= now or allocation_expiry <= now:
            raise VideoContractError("video dispatch lease is stale")
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
            raise VideoContractError("video producer Run authority is stale")
        matches = tuple(
            candidate
            for candidate in self.artifacts.runs.list_attempts(self.access, attempt.run_ref)
            if candidate.attempt_id == attempt.run_attempt_id
            and candidate.fence == attempt.run_fence
            and candidate.completed_at is None
        )
        if len(matches) != 1:
            raise VideoContractError("video producer Run attempt/fence is stale")
        return matches[0]

    def _dispatch_cancelled(self, dispatch: ScheduledDispatch) -> bool:
        attempt = dispatch.node_attempt
        try:
            current = self.executions.get_node_execution(self.access, attempt.node_ref)
        except NodeExecutionError:
            return True
        return (
            current.status in {"CANCELLED", "FAILED", "SUCCEEDED"}
            or current.current_attempt_id != attempt.attempt_id
            or current.current_fence != attempt.fence
            or current.current_owner_ref != attempt.owner_ref
        )

    def _resolve_artifact(self, source: VideoArtifactContentRef) -> _ResolvedMedia:
        if not isinstance(source, VideoArtifactContentRef) or source.project_ref != self.project_ref:
            raise VideoContractError("video source crossed Project scope")
        reference = _artifact_ref(self.project_ref, source.artifact_ref)
        try:
            artifact = self.artifacts.get_artifact(self.access, reference)
        except ArtifactError as exc:
            raise VideoContractError("video source Artifact is missing or stale") from exc
        content = artifact.content_ref
        if (
            content is None
            or content.value != source.content_ref
            or content.digest != source.content_sha256
        ):
            raise VideoContractError("video source Artifact/Content identity is stale or forged")
        try:
            if not self.objects.verify(content):
                raise VideoContractError("video source Content is unavailable or corrupt")
            payload = self.objects.read(content)
            content.verify(payload)
        except (ArtifactError, ObjectStorageError) as exc:
            raise VideoContractError("video source Content is unavailable or corrupt") from exc
        return _ResolvedMedia(source, artifact, content, payload)

    def _managed_process(
        self,
        dispatch: ScheduledDispatch,
        *,
        executable: Path,
        executable_sha256: str,
        argv: tuple[str, ...],
        descriptors: Mapping[str, ContentRef],
        idempotency_key: str,
        stdout_limit_bytes: int,
        stderr_limit_bytes: int = 8 * 1024 * 1024,
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
            timeout_seconds=300.0,
            termination_grace_seconds=2.0,
            stdout_limit_bytes=stdout_limit_bytes,
            stderr_limit_bytes=stderr_limit_bytes,
            resource_allocation_ref=dispatch.allocation.allocation_ref,
            descriptor_content_refs=descriptors,
        )
        try:
            result = self.process.execute(
                self.access,
                attempt,
                request,
                idempotency_key=idempotency_key,
                cancelled=lambda: self._dispatch_cancelled(dispatch),
            )
        except ProcessError as exc:
            raise VideoContractError("managed video process authority or execution failed") from exc
        if result.status is not ProcessStatus.SUCCEEDED:
            raise VideoContractError(
                f"managed video process failed: {result.stderr_preview[:1024]}"
            )
        if result.stdout_truncated or result.stderr_truncated:
            raise VideoContractError("managed video process evidence was truncated")
        return result

    @staticmethod
    def _parse_stream(value: object) -> VideoStreamEvidence:
        record = _record(value, "stream")
        codec_type = _optional_text(record.get("codec_type"))
        codec_name = _optional_text(record.get("codec_name"))
        time_base = _optional_text(record.get("time_base"))
        if codec_type is None or codec_name is None or time_base is None:
            raise VideoContractError("ffprobe stream codec identity is missing")
        width = _optional_int(record.get("width"), "width")
        height = _optional_int(record.get("height"), "height")
        sample_rate = _optional_int(record.get("sample_rate"), "sample_rate")
        channels = _optional_int(record.get("channels"), "channels")
        if channels is None and record.get("ch_layout") is not None:
            layout = _record(record["ch_layout"], "channel layout")
            channels = _optional_int(layout.get("nb_channels"), "channels")
        disposition_value = record.get("disposition")
        disposition: dict[str, int] = {}
        if disposition_value is not None:
            for key, item in _record(disposition_value, "disposition").items():
                numeric = _optional_int(item, f"disposition {key}")
                if numeric is None:
                    raise VideoContractError("ffprobe disposition is malformed")
                disposition[key] = numeric
        return VideoStreamEvidence(
            index=_required_int(record.get("index"), "stream index"),
            codec_type=codec_type,
            codec_name=codec_name,
            profile=_optional_text(record.get("profile")),
            time_base=time_base,
            start_time=_optional_float(record.get("start_time"), "stream start_time"),
            duration=_optional_float(record.get("duration"), "stream duration"),
            bit_rate=_optional_int(record.get("bit_rate"), "stream bit_rate"),
            width=width,
            height=height,
            pixel_format=_optional_text(record.get("pix_fmt")),
            average_frame_rate=_optional_text(record.get("avg_frame_rate")),
            real_frame_rate=_optional_text(record.get("r_frame_rate")),
            sample_rate=sample_rate,
            channels=channels,
            frame_count=_optional_int(
                record.get("nb_read_frames", record.get("nb_frames")), "frame count"
            ),
            packet_count=_optional_int(record.get("nb_read_packets"), "packet count"),
            color_range=_optional_text(record.get("color_range")),
            color_space=_optional_text(record.get("color_space")),
            color_transfer=_optional_text(record.get("color_transfer")),
            color_primaries=_optional_text(record.get("color_primaries")),
            tags=_tags(record.get("tags")),
            disposition=MappingProxyType(dict(sorted(disposition.items()))),
            evidence=_freeze_record(record),
        )

    def _probe(
        self, content: ContentRef, dispatch: ScheduledDispatch, *, token: str
    ) -> tuple[_ProbedMedia, ProcessResult]:
        result = self._managed_process(
            dispatch,
            executable=_FFPROBE,
            executable_sha256=self._ffprobe_sha256,
            argv=(
                "-hide_banner",
                "-v",
                "error",
                "-show_error",
                "-show_format",
                "-show_streams",
                "-count_frames",
                "-count_packets",
                "-of",
                "json",
                "-fd",
                "@minitz-content-fd:input",
                "fd:",
            ),
            descriptors={"input": content},
            idempotency_key=f"video-probe-{token}",
            stdout_limit_bytes=16 * 1024 * 1024,
        )
        try:
            loaded: object = json.loads(self.objects.read(result.stdout_ref))
        except (ObjectStorageError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VideoContractError("ffprobe video evidence is malformed") from exc
        payload = _record(loaded, "payload")
        streams_value = payload.get("streams")
        if not isinstance(streams_value, list) or not streams_value:
            raise VideoContractError("ffprobe found no media streams")
        streams = tuple(self._parse_stream(item) for item in cast(list[object], streams_value))
        indexes = tuple(item.index for item in streams)
        if len(indexes) != len(set(indexes)):
            raise VideoContractError("ffprobe stream indexes are duplicated")
        format_record = _record(payload.get("format"), "format")
        format_name = _optional_text(format_record.get("format_name"))
        format_long_name = _optional_text(format_record.get("format_long_name"))
        if format_name is None or format_long_name is None:
            raise VideoContractError("ffprobe format identity is missing")
        names = tuple(sorted(set(format_name.split(","))))
        types = {item.codec_type for item in streams}
        if {"mov", "mp4"} & set(names):
            container = "mp4"
            media_type = "video/mp4" if "video" in types else "audio/mp4"
        elif "wav" in names and types == {"audio"}:
            container, media_type = "wav", "audio/wav"
        elif "mp3" in names and types == {"audio"}:
            container, media_type = "mp3", "audio/mpeg"
        elif {"srt", "subrip"} & set(names) and types == {"subtitle"}:
            container, media_type = "srt", "application/x-subrip"
        else:
            raise VideoContractError("ffprobe container/stream combination is unsupported")
        duration = _optional_float(format_record.get("duration"), "format duration")
        if duration is None:
            durations = tuple(item.duration for item in streams if item.duration is not None)
            duration = max(durations, default=0.0)
        start_time = _optional_float(format_record.get("start_time"), "format start_time")
        size_bytes = _optional_int(format_record.get("size"), "format size")
        return (
            _ProbedMedia(
                media_type=media_type,
                container=container,
                format_names=names,
                format_long_name=format_long_name,
                start_time=0.0 if start_time is None else max(0.0, start_time),
                duration=duration,
                size_bytes=content.size_bytes if size_bytes is None else size_bytes,
                bit_rate=_optional_int(format_record.get("bit_rate"), "format bit_rate"),
                tags=_tags(format_record.get("tags")),
                streams=streams,
                format_evidence=_freeze_record(format_record),
            ),
            result,
        )

    def _decode_stream(
        self,
        content: ContentRef,
        stream: VideoStreamEvidence,
        dispatch: ScheduledDispatch,
        *,
        token: str,
    ) -> tuple[int, str, ProcessResult]:
        if stream.codec_type == "video":
            codec_args = ("-an", "-sn", "-dn", "-codec:v", "rawvideo")
        elif stream.codec_type == "audio":
            codec_args = ("-vn", "-sn", "-dn", "-codec:a", "pcm_s16le")
        else:
            raise VideoContractError("only video/audio streams require full decode hashes")
        result = self._managed_process(
            dispatch,
            executable=_FFMPEG,
            executable_sha256=self._ffmpeg_sha256,
            argv=(
                "-hide_banner",
                "-nostdin",
                "-v",
                "error",
                "-fd",
                "@minitz-content-fd:input",
                "-i",
                "fd:",
                "-map",
                f"0:{stream.index}",
                *codec_args,
                "-threads",
                "1",
                "-f",
                "framehash",
                "pipe:1",
            ),
            descriptors={"input": content},
            idempotency_key=f"video-decode-{token}-{stream.index}",
            stdout_limit_bytes=256 * 1024 * 1024,
        )
        try:
            evidence = self.objects.read(result.stdout_ref)
        except ObjectStorageError as exc:
            raise VideoContractError("decoded video stream evidence is unavailable") from exc
        try:
            lines = evidence.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise VideoContractError("decoded video stream evidence is malformed") from exc
        units = sum(1 for line in lines if line and not line.startswith("#"))
        if units < 1:
            raise VideoContractError("full video decode produced no frame evidence")
        return units, hashlib.sha256(evidence).hexdigest(), result

    def _validate_content(
        self,
        content: ContentRef,
        *,
        expected_media_type: str,
        dispatch: ScheduledDispatch,
    ) -> _ValidatedMedia:
        media_type = _canonical_media_type(expected_media_type)
        try:
            if not self.objects.verify(content):
                raise VideoContractError("video Content is unavailable or corrupt")
            payload = self.objects.read(content)
            content.verify(payload)
        except (ArtifactError, ObjectStorageError) as exc:
            raise VideoContractError("video Content is unavailable or corrupt") from exc
        token = hashlib.sha256(f"{media_type}:{content.digest}".encode()).hexdigest()[:40]
        probe, probe_process = self._probe(content, dispatch, token=token)
        if probe.media_type != media_type:
            raise VideoContractError("video media type does not match container/streams")
        decoded_units: dict[int, int] = {}
        decoded_sha256: dict[int, str] = {}
        processes: list[ProcessResult] = [probe_process]
        for stream in probe.streams:
            if stream.codec_type in {"audio", "video"}:
                units, digest, process = self._decode_stream(
                    content, stream, dispatch, token=token
                )
                decoded_units[stream.index] = units
                decoded_sha256[stream.index] = digest
                processes.append(process)
            elif stream.packet_count is None or stream.packet_count < 1:
                raise VideoContractError("subtitle stream has no complete packet evidence")
        if media_type == "video/mp4" and probe.duration <= 0.0:
            raise VideoContractError("decoded video duration is invalid")
        return _ValidatedMedia(
            probe,
            MappingProxyType(dict(sorted(decoded_units.items()))),
            MappingProxyType(dict(sorted(decoded_sha256.items()))),
            tuple(processes),
            hashlib.sha256(payload).hexdigest(),
        )

    @staticmethod
    def _video_metadata(value: _ValidatedMedia) -> VideoDecodedMetadata:
        probe = value.probe
        return VideoDecodedMetadata(
            media_type=probe.media_type,
            container=probe.container,
            format_names=probe.format_names,
            format_long_name=probe.format_long_name,
            start_time=probe.start_time,
            duration=probe.duration,
            size_bytes=probe.size_bytes,
            bit_rate=probe.bit_rate,
            tags=probe.tags,
            streams=probe.streams,
            decoded_units=value.decoded_units,
            decoded_sha256=value.decoded_sha256,
            content_sha256=value.content_sha256,
            decoder=f"ffmpeg://{_VERSION}/full-framehash",
            format_evidence=probe.format_evidence,
        )

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
        sources: Sequence[_ResolvedMedia],
        process_results: Sequence[ProcessResult],
        derivation: str,
        metadata: Mapping[str, str] | None = None,
        extra_artifact_refs: Sequence[ArtifactRef] = (),
        extra_content_refs: Sequence[ContentRef] = (),
    ) -> VideoArtifactContentRef:
        if role not in VIDEO_ARTIFACT_ROLES:
            raise VideoContractError("video output Artifact role is unsupported")
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
                raise VideoContractError("fresh video output Content verification failed")
        except ObjectStorageError as exc:
            raise VideoContractError("fresh video output Content verification failed") from exc
        source_artifacts = self._unique_artifact_refs(
            tuple(item.artifact.artifact_ref for item in sources)
            + tuple(item.artifact_ref for item in process_results)
            + tuple(extra_artifact_refs)
        )
        source_contents = self._unique_content_refs(
            tuple(item.content_ref for item in sources)
            + tuple(item.result_ref for item in process_results)
            + tuple(extra_content_refs)
        )
        try:
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
            reopened_payload = self.objects.read(content)
        except (ArtifactError, ObjectStorageError) as exc:
            raise VideoContractError("fresh video output Artifact verification failed") from exc
        if reopened.content_ref != content or reopened_payload != payload:
            raise VideoContractError("fresh video output Artifact verification failed")
        return VideoArtifactContentRef(
            self.project_ref, artifact.artifact_ref.value, content.value, content.digest
        )

    def validate(self, payload: bytes, *, expected_media_type: str) -> VideoDecodedMetadata:
        """Full-probe and full-decode supplied bytes through the live dispatch."""

        if not isinstance(payload, bytes) or not payload:
            raise VideoContractError("video validation payload is empty")
        media_type = _canonical_media_type(expected_media_type)
        if media_type != "video/mp4":
            raise VideoContractError("public video validation requires video/mp4")
        try:
            content = self.objects.put(
                payload,
                media_type=media_type,
                expected_digest=hashlib.sha256(payload).hexdigest(),
                expected_size=len(payload),
            )
        except ObjectStorageError as exc:
            raise VideoContractError("video validation Content publication failed") from exc
        return self._video_metadata(
            self._validate_content(
                content, expected_media_type=media_type, dispatch=self.dispatch
            )
        )

    def inspect(
        self, source: VideoArtifactContentRef, validator_ref: str
    ) -> VideoInspection:
        if _ABSOLUTE_REF.fullmatch(validator_ref) is None:
            raise VideoContractError("video validator_ref is malformed")
        resolved = self._resolve_artifact(source)
        validated = self._validate_content(
            resolved.content_ref,
            expected_media_type=resolved.content_ref.media_type,
            dispatch=self.dispatch,
        )
        metadata = self._video_metadata(validated)
        report_payload = _json_bytes(
            {
                "metadata": metadata.payload(),
                "source": source.payload(),
                "validator_ref": validator_ref,
                "validator_runtime_ref": self.validator_ref,
            }
        )
        evidence = self._publish(
            self.dispatch,
            role="video.validation-evidence",
            payload=report_payload,
            media_type="application/json",
            sources=(resolved,),
            process_results=validated.processes,
            derivation="video.inspect.full-probe-full-decode",
            metadata={
                "schema_ref": "schema://minitz/video-validation/1",
                "schema_version": "1.0.0",
            },
        )
        stream = metadata.video_stream
        if stream.width is None or stream.height is None or stream.pixel_format is None:
            raise VideoContractError("video stream dimensions are incomplete")
        frame_count = metadata.decoded_units[stream.index]
        return VideoInspection(
            project_ref=self.project_ref,
            source=source,
            duration=metadata.duration,
            fps=metadata.fps,
            width=stream.width,
            height=stream.height,
            codec=stream.codec_name,
            inspection_ref=evidence.artifact_ref,
            inspection_sha256=evidence.content_sha256,
            media_type=metadata.media_type,
            container=metadata.container,
            time_base=stream.time_base,
            pixel_format=stream.pixel_format,
            color_range=stream.color_range,
            color_space=stream.color_space,
            color_transfer=stream.color_transfer,
            color_primaries=stream.color_primaries,
            frame_count=frame_count,
            bit_rate=metadata.bit_rate,
            tags=metadata.tags,
            streams=metadata.streams,
            content_sha256=metadata.content_sha256,
            decoded_sha256=metadata.decoded_sha256,
            decoder=metadata.decoder,
            format_evidence=metadata.format_evidence,
        )

    @staticmethod
    def _audio_source_start(
        specification: VideoSpecification, index: int
    ) -> float:
        key = f"source_start.{index}"
        value = specification.audio_policy.get(key)
        if value is None:
            raise VideoContractError(f"audio policy requires exact {key}")
        try:
            result = float(value)
        except ValueError as exc:
            raise VideoContractError(f"audio {key} is malformed") from exc
        if not math.isfinite(result) or result < 0.0:
            raise VideoContractError(f"audio {key} is malformed")
        return result

    @staticmethod
    def _audio_target_rate(
        binding: AudioTrackBinding, stream: VideoStreamEvidence
    ) -> int:
        if stream.sample_rate is None or stream.sample_rate < 1:
            raise VideoContractError("bound audio sample rate is missing")
        if binding.resample_policy == "preserve":
            return stream.sample_rate
        prefix = "resample:"
        if not binding.resample_policy.startswith(prefix):
            raise VideoContractError("audio resample policy must preserve or resample:<rate>")
        try:
            rate = int(binding.resample_policy.removeprefix(prefix))
        except ValueError as exc:
            raise VideoContractError("audio resample rate is malformed") from exc
        if not 8_000 <= rate <= 384_000:
            raise VideoContractError("audio resample rate is out of range")
        return rate

    def _validate_specification(self, specification: VideoSpecification) -> None:
        if not isinstance(specification, VideoSpecification):
            raise VideoContractError("exact VideoSpecification is required")
        if specification.project_ref != self.project_ref:
            raise VideoContractError("video specification crossed Project scope")
        if specification.operation not in _SUPPORTED_OPERATIONS:
            raise VideoContractError("video operation requires a deterministic FFmpeg path")
        if specification.tool_ref != self.tool_ref or specification.runtime_ref != self.runtime_ref:
            raise VideoContractError("video tool/runtime binding differs from specification")
        if specification.validator_ref != self.validator_ref:
            raise VideoContractError("video validator binding differs from specification")
        if specification.model_ref is not None or specification.prompt is not None:
            raise VideoContractError("deterministic FFmpeg video cannot claim model generation")
        if not specification.sources or specification.image_sources or specification.render_sequences:
            raise VideoContractError("FFmpeg video requires exact video Artifact sources only")
        if specification.media_type != "video/mp4" or specification.container != "mp4":
            raise VideoContractError("video output requires explicit video/mp4 MP4 container")
        if specification.codec != "h264":
            raise VideoContractError("video output requires explicit h264 codec")
        if specification.profile not in {"baseline", "main", "high", "high10"}:
            raise VideoContractError("video H.264 profile is unsupported")
        if specification.bitrate is None or re.fullmatch(r"[1-9][0-9]{4,8}", specification.bitrate) is None:
            raise VideoContractError("video bitrate must be an explicit integer")
        if specification.time_start is None or specification.time_end is None or specification.duration is None:
            raise VideoContractError("video time range must be explicit")
        if specification.timebase is None:
            raise VideoContractError("video timebase must be explicit")
        timebase = _fraction(specification.timebase, "video timebase")
        if timebase.numerator != 1:
            raise VideoContractError("MP4 video timebase must be reciprocal integer")
        if specification.width is None or specification.height is None:
            raise VideoContractError("video output resolution must be explicit")
        if specification.width < 2 or specification.height < 2:
            raise VideoContractError("video output resolution is too small")
        if specification.pixel_format not in {"yuv420p", "yuv422p", "yuv444p"}:
            raise VideoContractError("video pixel format policy is unsupported")
        if specification.pixel_format == "yuv420p" and (
            specification.width % 2 or specification.height % 2
        ):
            raise VideoContractError("yuv420p output requires even resolution")
        if specification.color_ref not in _COLOR_POLICIES or specification.hdr_ref is not None:
            raise VideoContractError("video color/HDR policy is unsupported or implicit")
        if specification.fps_policy == "conform":
            if specification.target_fps is None:
                raise VideoContractError("conform fps policy requires target_fps")
            _fraction(specification.target_fps, "target_fps")
        elif specification.fps_policy != "preserve" or specification.target_fps is not None:
            raise VideoContractError("video fps policy is malformed")
        if specification.missing_frame_policy != "fail":
            raise VideoContractError("video missing-frame policy must fail closed")
        if specification.timeline.transitions or specification.timeline.effects:
            raise VideoContractError("video transitions/effects need a separately qualified implementation")
        if specification.operation == "compose":
            if not specification.timeline.edits:
                raise VideoContractError("compose requires an exact ordered timeline")
        elif len(specification.sources) != 1 or specification.timeline.edits:
            raise VideoContractError("non-compose video requires one source and no implicit edits")
        preset = specification.config.get("preset")
        scale_filter = specification.config.get("scale_filter")
        color_policy = specification.config.get("color_policy")
        if not preset or scale_filter not in {"bilinear", "bicubic", "lanczos", "neighbor"}:
            raise VideoContractError("video encoder preset and scale filter must be explicit")
        if color_policy not in {"convert", "preserve"}:
            raise VideoContractError("video color policy must explicitly preserve or convert")
        if set(specification.config) != {"preset", "scale_filter", "color_policy"}:
            raise VideoContractError("video config contains unknown implicit behavior")
        role = specification.output_contract.get("role", _ROLE_BY_OPERATION[specification.operation])
        if role not in VIDEO_ARTIFACT_ROLES:
            raise VideoContractError("video output role is unsupported")
        if role == "video.proxy":
            if specification.operation != "preview" or specification.output_contract.get("cache_only") != "true":
                raise VideoContractError("video proxy is cache-only and cannot be authoritative output")
        elif specification.output_contract.get("cache_only") == "true":
            raise VideoContractError("cache-only policy is reserved for video.proxy")
        expected_audio_keys = {"bitrate", "codec"} | {
            f"source_start.{index}" for index in range(len(specification.audio_tracks))
        }
        if specification.audio_tracks:
            if set(specification.audio_policy) != expected_audio_keys:
                raise VideoContractError("audio policy omits exact codec/bitrate/source starts")
            if specification.audio_policy.get("codec") != "aac":
                raise VideoContractError("MP4 bound audio requires explicit AAC codec")
            audio_bitrate = specification.audio_policy.get("bitrate")
            if audio_bitrate is None or re.fullmatch(r"[1-9][0-9]{4,6}", audio_bitrate) is None:
                raise VideoContractError("bound audio bitrate is malformed")
        elif specification.audio_policy:
            raise VideoContractError("audio policy exists without bound audio Artifacts")
        for audio_binding in specification.audio_tracks:
            if audio_binding.stretch_policy != "preserve":
                raise VideoContractError("audio time stretching is never implicit")
            if audio_binding.timeline_end > specification.duration + 1e-9:
                raise VideoContractError("bound audio exceeds exact video timeline")
        if specification.subtitle_tracks:
            if dict(specification.subtitle_policy) != {"codec": "mov_text"}:
                raise VideoContractError("MP4 subtitle codec policy must be exact mov_text")
        elif specification.subtitle_policy:
            raise VideoContractError("subtitle policy exists without bound subtitle Artifacts")
        for subtitle_binding in specification.subtitle_tracks:
            if subtitle_binding.burn_policy not in {"none", "preserve"} or subtitle_binding.stream_policy not in {"stream", "preserve"}:
                raise VideoContractError("subtitle binding requires preserved selectable stream")

    @staticmethod
    def _segments(
        specification: VideoSpecification,
        resolved: Mapping[str, tuple[_ResolvedMedia, VideoDecodedMetadata]],
    ) -> tuple[_VideoSegment, ...]:
        if specification.duration is None or specification.time_start is None or specification.time_end is None:
            raise VideoContractError("video range is incomplete")
        if specification.operation != "compose":
            source = specification.sources[0]
            pair = resolved.get(source.artifact_ref)
            if pair is None:
                raise VideoContractError("video source was not resolved")
            media, metadata = pair
            if specification.time_end > metadata.duration + 1e-6:
                raise VideoContractError("video trim exceeds immutable source duration")
            return (
                _VideoSegment(
                    media,
                    metadata,
                    specification.time_start,
                    specification.time_end,
                    0.0,
                    specification.duration,
                ),
            )
        segments: list[_VideoSegment] = []
        cursor = 0.0
        allowed_operations = {"clip", "compose", "cut", "trim"}
        for edit in specification.timeline.edits:
            if edit.operation not in allowed_operations:
                raise VideoContractError("timeline edit operation is unsupported")
            clip = edit.clip
            pair = resolved.get(clip.source.artifact_ref)
            if pair is None or pair[0].contract != clip.source:
                raise VideoContractError("timeline clip source is stale or unbound")
            media, metadata = pair
            if not math.isclose(clip.timeline_start, cursor, rel_tol=0.0, abs_tol=1e-9):
                raise VideoContractError("timeline clips must be contiguous and ordered")
            if clip.source_end > metadata.duration + 1e-6:
                raise VideoContractError("timeline clip exceeds immutable source duration")
            segments.append(
                _VideoSegment(
                    media,
                    metadata,
                    clip.source_start,
                    clip.source_end,
                    clip.timeline_start,
                    clip.timeline_end,
                )
            )
            cursor = clip.timeline_end
        if not math.isclose(cursor, specification.duration, rel_tol=0.0, abs_tol=1e-9):
            raise VideoContractError("timeline duration differs from exact specification")
        return tuple(segments)

    @staticmethod
    def _output_fps(
        specification: VideoSpecification, segments: Sequence[_VideoSegment]
    ) -> Fraction:
        if specification.fps_policy == "conform":
            assert specification.target_fps is not None
            return _fraction(specification.target_fps, "target_fps")
        rates = tuple(_fraction(item.metadata.fps, "source fps") for item in segments)
        if not rates or any(value != rates[0] for value in rates[1:]):
            raise VideoContractError("preserve fps requires one exact source rate")
        return rates[0]

    @staticmethod
    def _color_filter(
        specification: VideoSpecification, segment: _VideoSegment
    ) -> str | None:
        stream = segment.metadata.video_stream
        source = (
            stream.color_primaries,
            stream.color_transfer,
            stream.color_space,
            stream.color_range,
        )
        target = _COLOR_POLICIES[cast(str, specification.color_ref)]
        policy = specification.config["color_policy"]
        if policy == "preserve":
            if source != target:
                raise VideoContractError(
                    "video color policy preserve differs from exact source metadata"
                )
            return None
        if (
            any(value not in _FFMPEG_COLOR_COMPONENTS for value in source[:3])
            or source[3] not in _FFMPEG_COLOR_RANGES
        ):
            raise VideoContractError(
                "video color policy conversion requires supported exact source metadata"
            )
        return (
            "colorspace="
            f"iprimaries={source[0]}:itrc={source[1]}:ispace={source[2]}:irange={source[3]}:"
            f"primaries={target[0]}:trc={target[1]}:space={target[2]}:range={target[3]}"
        )

    def _encode(
        self,
        specification: VideoSpecification,
        segments: Sequence[_VideoSegment],
        audio: Sequence[tuple[AudioTrackBinding, _ResolvedMedia, _ValidatedMedia]],
        subtitles: Sequence[tuple[SubtitleTrackBinding, _ResolvedMedia, _ValidatedMedia]],
        dispatch: ScheduledDispatch,
    ) -> tuple[bytes, ProcessResult, Fraction, tuple[int, ...]]:
        if specification.duration is None or specification.width is None or specification.height is None:
            raise VideoContractError("video output dimensions/timing are incomplete")
        if specification.pixel_format is None or specification.timebase is None:
            raise VideoContractError("video output pixel/timebase policy is incomplete")
        if specification.bitrate is None or specification.profile is None:
            raise VideoContractError("video encoder policy is incomplete")
        fps = self._output_fps(specification, segments)
        timebase = _fraction(specification.timebase, "video timebase")
        descriptors: dict[str, ContentRef] = {}
        input_args: list[str] = []
        filters: list[str] = []
        for index, segment in enumerate(segments):
            key = f"video{index}"
            descriptors[key] = segment.source.content_ref
            input_args.extend(("-fd", f"@minitz-content-fd:{key}", "-i", "fd:"))
            chain = [
                f"trim=start={_seconds(segment.source_start)}:end={_seconds(segment.source_end)}",
                "setpts=PTS-STARTPTS",
            ]
            color_filter = self._color_filter(specification, segment)
            if color_filter is not None:
                chain.append(color_filter)
            chain.append(
                f"scale={specification.width}:{specification.height}:flags={specification.config['scale_filter']}"
            )
            if specification.fps_policy == "conform":
                chain.append(f"fps={_fraction_text(fps)}:round=near")
            chain.extend(
                (
                    f"format={specification.pixel_format}",
                    "setsar=1",
                    f"settb={_fraction_text(timebase)}",
                )
            )
            filters.append(f"[{index}:v:0]{','.join(chain)}[v{index}]")
        if len(segments) == 1:
            filters.append("[v0]null[vout]")
        else:
            inputs = "".join(f"[v{index}]" for index in range(len(segments)))
            filters.append(f"{inputs}concat=n={len(segments)}:v=1:a=0[vout]")
        audio_rates: list[int] = []
        audio_base = len(segments)
        for index, (binding, resolved, validated) in enumerate(audio):
            key = f"audio{index}"
            descriptors[key] = resolved.content_ref
            input_args.extend(("-fd", f"@minitz-content-fd:{key}", "-i", "fd:"))
            audio_streams = tuple(
                item for item in validated.probe.streams if item.codec_type == "audio"
            )
            if len(audio_streams) != 1 or len(validated.probe.streams) != 1:
                raise VideoContractError("bound audio Artifact requires one exact audio stream")
            stream = audio_streams[0]
            source_start = self._audio_source_start(specification, index)
            duration = binding.timeline_end - binding.timeline_start
            if source_start + duration > validated.probe.duration + 1e-6:
                raise VideoContractError("bound audio range exceeds immutable source; stretch refused")
            target_rate = self._audio_target_rate(binding, stream)
            audio_rates.append(target_rate)
            chain = [
                f"atrim=start={_seconds(source_start)}:duration={_seconds(duration)}",
                "asetpts=PTS-STARTPTS",
            ]
            if target_rate != stream.sample_rate:
                chain.append(f"aresample={target_rate}:async=0:first_pts=0")
            offset_samples = round(binding.timeline_start * target_rate)
            if not math.isclose(
                offset_samples / target_rate,
                binding.timeline_start,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise VideoContractError(
                    "bound audio timeline offset is not exact at the resample rate"
                )
            chain.append(f"adelay={offset_samples}S:all=1")
            filters.append(
                f"[{audio_base + index}:a:0]{','.join(chain)}[a{index}]"
            )
        subtitle_base = audio_base + len(audio)
        for index, (_, resolved, validated) in enumerate(subtitles):
            key = f"subtitle{index}"
            descriptors[key] = resolved.content_ref
            input_args.extend(
                ("-f", "srt", "-fd", f"@minitz-content-fd:{key}", "-i", "fd:")
            )
            subtitle_streams = tuple(
                item for item in validated.probe.streams if item.codec_type == "subtitle"
            )
            if len(subtitle_streams) != 1 or len(validated.probe.streams) != 1:
                raise VideoContractError("bound subtitle Artifact requires one exact stream")
        argv: list[str] = ["-hide_banner", "-nostdin", "-v", "error", *input_args]
        argv.extend(("-filter_complex", ";".join(filters), "-map", "[vout]"))
        for index in range(len(audio)):
            argv.extend(("-map", f"[a{index}]"))
        for index in range(len(subtitles)):
            argv.extend(("-map", f"{subtitle_base + index}:s:0"))
        colors = _COLOR_POLICIES[cast(str, specification.color_ref)]
        argv.extend(
            (
                "-codec:v",
                "libx264",
                "-profile:v",
                specification.profile,
                "-preset",
                specification.config["preset"],
                "-b:v",
                specification.bitrate,
                "-pix_fmt",
                specification.pixel_format,
                "-x264-params",
                "colorprim=bt709:transfer=bt709:colormatrix=bt709:range=limited:bframes=0",
                "-color_primaries",
                colors[0],
                "-color_trc",
                colors[1],
                "-colorspace",
                colors[2],
                "-color_range",
                colors[3],
                "-video_track_timescale",
                str(timebase.denominator),
                "-threads",
                "1",
                "-map_metadata",
                "-1",
                "-fflags",
                "+bitexact",
                "-flags:v",
                "+bitexact",
            )
        )
        if audio:
            argv.extend(
                (
                    "-codec:a",
                    "aac",
                    "-b:a",
                    specification.audio_policy["bitrate"],
                    "-flags:a",
                    "+bitexact",
                )
            )
            for index, rate in enumerate(audio_rates):
                argv.extend((f"-ar:a:{index}", str(rate)))
        if subtitles:
            argv.extend(("-codec:s", "mov_text"))
            for index, (subtitle_binding, _, _) in enumerate(subtitles):
                argv.extend(
                    (f"-metadata:s:s:{index}", f"language={subtitle_binding.language}")
                )
        argv.extend(
            (
                "-t",
                _seconds(specification.duration),
                "-use_editlist",
                "0",
                "-movflags",
                "+frag_keyframe+empty_moov+default_base_moof",
                "-max_muxing_queue_size",
                "2048",
                "-f",
                "mp4",
                "pipe:1",
            )
        )
        token = hashlib.sha256(
            f"{dispatch.node_attempt.attempt_id}:{dispatch.node_attempt.fence}:{specification.canonical_digest}".encode()
        ).hexdigest()[:40]
        result = self._managed_process(
            dispatch,
            executable=_FFMPEG,
            executable_sha256=self._ffmpeg_sha256,
            argv=tuple(argv),
            descriptors=descriptors,
            idempotency_key=f"video-encode-{token}",
            stdout_limit_bytes=1024 * 1024 * 1024,
        )
        try:
            payload = self.objects.read(result.stdout_ref)
        except ObjectStorageError as exc:
            raise VideoContractError("video encoder output is unavailable") from exc
        if not payload:
            raise VideoContractError("video encoder produced empty output")
        return payload, result, fps, tuple(audio_rates)

    @staticmethod
    def _verify_output(
        specification: VideoSpecification,
        metadata: VideoDecodedMetadata,
        fps: Fraction,
        audio_rates: Sequence[int],
    ) -> None:
        if specification.duration is None or specification.width is None or specification.height is None:
            raise VideoContractError("video output specification is incomplete")
        if specification.pixel_format is None or specification.timebase is None:
            raise VideoContractError("video output format policy is incomplete")
        stream = metadata.video_stream
        if (
            metadata.media_type != "video/mp4"
            or metadata.container != "mp4"
            or stream.codec_name != "h264"
            or stream.width != specification.width
            or stream.height != specification.height
            or stream.pixel_format != specification.pixel_format
            or _fraction(metadata.fps, "output fps") != fps
            or _fraction(stream.time_base, "output time_base")
            != _fraction(specification.timebase, "specified timebase")
        ):
            raise VideoContractError("fresh video output differs from exact format policy")
        colors = _COLOR_POLICIES[cast(str, specification.color_ref)]
        if (
            stream.color_primaries,
            stream.color_transfer,
            stream.color_space,
            stream.color_range,
        ) != colors:
            raise VideoContractError("fresh video output differs from exact color policy")
        tolerance = max(float(1 / fps), float(_fraction(specification.timebase, "timebase")))
        if not math.isclose(metadata.duration, specification.duration, rel_tol=0.0, abs_tol=tolerance):
            raise VideoContractError("fresh video output duration differs from exact timeline")
        audio_streams = tuple(item for item in metadata.streams if item.codec_type == "audio")
        subtitle_streams = tuple(item for item in metadata.streams if item.codec_type == "subtitle")
        if len(audio_streams) != len(specification.audio_tracks):
            raise VideoContractError("fresh video output lost or invented an audio stream")
        if len(subtitle_streams) != len(specification.subtitle_tracks):
            raise VideoContractError("fresh video output lost or invented a subtitle stream")
        for index, (stream_value, audio_binding, rate) in enumerate(
            zip(audio_streams, specification.audio_tracks, audio_rates, strict=True)
        ):
            if stream_value.codec_name != "aac" or stream_value.sample_rate != rate:
                raise VideoContractError("fresh video output audio codec/resample policy differs")
            if stream_value.start_time is not None and abs(stream_value.start_time) > 0.03:
                raise VideoContractError(f"fresh video output audio origin {index} differs")
            expected_duration = audio_binding.timeline_end
            if stream_value.duration is not None and abs(stream_value.duration - expected_duration) > 0.08:
                raise VideoContractError("fresh video output silently stretched bound audio")
        for stream_value, subtitle_binding in zip(
            subtitle_streams, specification.subtitle_tracks, strict=True
        ):
            if stream_value.codec_name not in {"mov_text", "tx3g"}:
                raise VideoContractError("fresh video output subtitle codec differs")
            if stream_value.tags.get("language") != subtitle_binding.language:
                raise VideoContractError("fresh video output subtitle language differs")

    def _timeline_report(
        self,
        specification: VideoSpecification,
        segments: Sequence[_VideoSegment],
    ) -> bytes:
        return _json_bytes(
            {
                "canonical_digest": specification.canonical_digest,
                "fps_policy": specification.fps_policy,
                "segments": [
                    {
                        "source": item.source.contract.payload(),
                        "source_end": item.source_end,
                        "source_start": item.source_start,
                        "timeline_end": item.timeline_end,
                        "timeline_start": item.timeline_start,
                    }
                    for item in segments
                ],
                "timebase": specification.timebase,
                "timeline": specification.timeline.payload(),
                "tool_ref": self.tool_ref,
                "runtime_ref": self.runtime_ref,
            }
        )

    def _session(
        self,
        specification: VideoSpecification,
        output: VideoOutputRef,
        timeline: VideoArtifactContentRef,
        dispatch: ScheduledDispatch,
    ) -> EditableVideoSessionBinding:
        output_resolved = self._resolve_artifact(output.output)
        timeline_resolved = self._resolve_artifact(timeline)
        payload = _json_bytes(
            {
                "audio_tracks": [item.payload() for item in specification.audio_tracks],
                "output": output.output.payload(),
                "producer_attempt_id": output.producer_attempt_id,
                "producer_fence": output.producer_fence,
                "specification_digest": specification.canonical_digest,
                "subtitle_tracks": [item.payload() for item in specification.subtitle_tracks],
                "timeline": timeline.payload(),
                "tool_ref": self.tool_ref,
                "tool_version": _VERSION,
            }
        )
        session_ref = self._publish(
            dispatch,
            role="video.session",
            payload=payload,
            media_type="application/json",
            sources=(output_resolved, timeline_resolved),
            process_results=(),
            derivation="video.session.editable",
            metadata={
                "schema_ref": "schema://minitz/video-session/1",
                "schema_version": "1.0.0",
            },
        )
        return EditableVideoSessionBinding(
            self.project_ref, specification.timeline, session_ref, self.tool_ref, _VERSION
        )

    def _render_authorized(
        self,
        specification: VideoSpecification,
        dispatch: ScheduledDispatch,
        attempt: NodeExecutionAttempt,
    ) -> VideoRenderResult:
        self._validate_specification(specification)
        video_resolved: list[_ResolvedMedia] = []
        resolved_by_ref: dict[str, tuple[_ResolvedMedia, VideoDecodedMetadata]] = {}
        process_results: list[ProcessResult] = []
        for source in specification.sources:
            resolved = self._resolve_artifact(source)
            if resolved.artifact.role == "video.proxy" and specification.operation != "preview":
                raise VideoContractError("cache-only video proxy cannot become authoritative source")
            validated = self._validate_content(
                resolved.content_ref,
                expected_media_type=resolved.content_ref.media_type,
                dispatch=dispatch,
            )
            metadata = self._video_metadata(validated)
            video_resolved.append(resolved)
            process_results.extend(validated.processes)
            prior = resolved_by_ref.get(source.artifact_ref)
            if prior is not None and prior[0].contract != source:
                raise VideoContractError("duplicate video ArtifactRef has contradictory identity")
            resolved_by_ref[source.artifact_ref] = (resolved, metadata)
        segments = self._segments(specification, resolved_by_ref)
        audio_values: list[tuple[AudioTrackBinding, _ResolvedMedia, _ValidatedMedia]] = []
        audio_resolved: list[_ResolvedMedia] = []
        for audio_binding in specification.audio_tracks:
            resolved = self._resolve_artifact(audio_binding.audio)
            validated = self._validate_content(
                resolved.content_ref,
                expected_media_type=resolved.content_ref.media_type,
                dispatch=dispatch,
            )
            audio_values.append((audio_binding, resolved, validated))
            audio_resolved.append(resolved)
            process_results.extend(validated.processes)
        subtitle_values: list[
            tuple[SubtitleTrackBinding, _ResolvedMedia, _ValidatedMedia]
        ] = []
        subtitle_resolved: list[_ResolvedMedia] = []
        for subtitle_binding in specification.subtitle_tracks:
            resolved = self._resolve_artifact(subtitle_binding.subtitle)
            validated = self._validate_content(
                resolved.content_ref,
                expected_media_type=resolved.content_ref.media_type,
                dispatch=dispatch,
            )
            subtitle_values.append((subtitle_binding, resolved, validated))
            subtitle_resolved.append(resolved)
            process_results.extend(validated.processes)
        all_sources = (*video_resolved, *audio_resolved, *subtitle_resolved)
        timeline = self._publish(
            dispatch,
            role="video.timeline",
            payload=self._timeline_report(specification, segments),
            media_type="application/json",
            sources=all_sources,
            process_results=tuple(process_results),
            derivation="video.timeline.verified-inputs",
            metadata={
                "schema_ref": "schema://minitz/video-timeline/1",
                "schema_version": "1.0.0",
            },
        )
        timeline_resolved = self._resolve_artifact(timeline)
        transformed, encode_process, fps, audio_rates = self._encode(
            specification, segments, audio_values, subtitle_values, dispatch
        )
        try:
            intermediate = self.objects.put(
                transformed,
                media_type="video/mp4",
                expected_digest=hashlib.sha256(transformed).hexdigest(),
                expected_size=len(transformed),
            )
        except ObjectStorageError as exc:
            raise VideoContractError("video encoded intermediate could not be preserved") from exc
        final_validated = self._validate_content(
            intermediate, expected_media_type="video/mp4", dispatch=dispatch
        )
        final_metadata = self._video_metadata(final_validated)
        self._verify_output(specification, final_metadata, fps, audio_rates)
        role = specification.output_contract.get(
            "role", _ROLE_BY_OPERATION[specification.operation]
        )
        output_ref = self._publish(
            dispatch,
            role=role,
            payload=transformed,
            media_type="video/mp4",
            sources=all_sources,
            process_results=(
                *tuple(process_results),
                encode_process,
                *final_validated.processes,
            ),
            derivation=f"video.{specification.operation}",
            metadata={
                "schema_ref": "schema://minitz/video-output/1",
                "schema_version": "1.0.0",
            },
            extra_artifact_refs=(timeline_resolved.artifact.artifact_ref,),
            extra_content_refs=(timeline_resolved.content_ref,),
        )
        output = VideoOutputRef.create(
            project_ref=self.project_ref,
            specification=specification,
            output=output_ref,
            duration=final_metadata.duration,
            fps=final_metadata.fps,
            width=cast(int, final_metadata.video_stream.width),
            height=cast(int, final_metadata.video_stream.height),
            codec=final_metadata.video_stream.codec_name,
            container=final_metadata.container,
            producer_attempt_id=attempt.attempt_id,
            producer_fence=attempt.fence,
            derivation=f"video.{specification.operation}",
        )
        session = self._session(specification, output, timeline, dispatch)
        return VideoRenderResult(output, timeline, session)

    def execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        specification: VideoSpecification,
    ) -> VideoOutputRef:
        if access != self.access:
            raise VideoContractError("video execute ProjectAccess differs from bound authority")
        if attempt != self.dispatch.node_attempt:
            raise VideoContractError("video execute attempt differs from bound dispatch")
        self._require_dispatch(self.dispatch, attempt.attempt_id, attempt.fence)
        return self._render_authorized(specification, self.dispatch, attempt).output

    def render(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        specification: VideoSpecification,
    ) -> VideoRenderResult:
        if access != self.access:
            raise VideoContractError("video render ProjectAccess differs from bound authority")
        if attempt != self.dispatch.node_attempt:
            raise VideoContractError("video render attempt differs from bound dispatch")
        self._require_dispatch(self.dispatch, attempt.attempt_id, attempt.fence)
        return self._render_authorized(specification, self.dispatch, attempt)

    def execute_dispatched(
        self, specification: VideoSpecification, dispatch: ScheduledDispatch
    ) -> VideoOutputRef:
        attempt = self._require_dispatch(
            dispatch, dispatch.node_attempt.attempt_id, dispatch.node_attempt.fence
        )
        return self._render_authorized(specification, dispatch, attempt).output

    def render_dispatched(
        self, specification: VideoSpecification, dispatch: ScheduledDispatch
    ) -> VideoRenderResult:
        attempt = self._require_dispatch(
            dispatch, dispatch.node_attempt.attempt_id, dispatch.node_attempt.fence
        )
        return self._render_authorized(specification, dispatch, attempt)

    def bind_game_handoff(
        self,
        output: VideoOutputRef,
        target: VideoArtifactContentRef,
        integration_ref: str,
    ) -> GameVideoHandoffBinding:
        if (
            not isinstance(output, VideoOutputRef)
            or output.project_ref != self.project_ref
            or not isinstance(target, VideoArtifactContentRef)
            or target.project_ref != self.project_ref
            or _ABSOLUTE_REF.fullmatch(integration_ref) is None
        ):
            raise VideoContractError("video game handoff crossed Project or is malformed")
        self._resolve_artifact(output.output)
        self._resolve_artifact(target)
        return GameVideoHandoffBinding(self.project_ref, output, target, integration_ref)


__all__ = [
    "DeterministicVideoTool",
    "VideoDecodedMetadata",
    "VideoInspection",
    "VideoRenderResult",
    "VideoStreamEvidence",
]
