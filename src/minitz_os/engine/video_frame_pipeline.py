"""REAL, fail-closed video frame extraction and P3-11 image integration."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from datetime import datetime
from fractions import Fraction
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import re
from threading import Event
from types import MappingProxyType

from PIL import Image, UnidentifiedImageError

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .execution import NodeExecutionAttempt, NodeExecutionError, NodeExecutionService
from .filesystem import FilesystemRootRef
from .image_pack import (
    ImageArtifactContentRef,
    ImageContractError,
    ImageOperation,
    ImageOutputRef,
    ImageSpecification,
)
from .image_tool import DeterministicImageTool
from .object_store import ObjectStorageBackend, ObjectStorageError
from .process import (
    ManagedProcessAdapter,
    ProcessError,
    ProcessExecutionRequest,
    ProcessResult,
    ProcessStatus,
)
from .project import ProjectAccess, ProjectRef
from .render_pack import RenderSequenceManifest
from .run import ExecutionAttempt
from .scheduler import ScheduledDispatch
from .video_pack import (
    VideoArtifactContentRef,
    VideoClip,
    VideoFrameRef,
    VideoFrameSequenceManifest,
)


_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA = re.compile(r"[0-9a-f]{64}")
_ATTEMPT = re.compile(r"natt_[0-9a-f]{32}")
_MAX_SEQUENCE_FRAMES = 120
_MAX_PROCESS_FRAMES = 32
_FFMPEG = Path("/usr/bin/ffmpeg")
_FFPROBE = Path("/usr/bin/ffprobe")
_FFMPEG_VERSION = "8.0.1"


class VideoFramePipelineError(ValueError):
    """Exact frame evidence is missing, corrupt, stale, or incompatible."""


def _file_sha256(path: Path) -> str:
    if not path.is_absolute() or not path.is_file():
        raise VideoFramePipelineError(f"required decoder executable is unavailable: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _ref(value: object, field: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise VideoFramePipelineError(f"{field} is invalid")
    return value


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise VideoFramePipelineError(f"{field} is invalid")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise VideoFramePipelineError(f"{field} is invalid")
    return value


def _finite(value: object, field: str, *, minimum: float = 0.0) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < minimum
    ):
        raise VideoFramePipelineError(f"{field} is invalid")
    return float(value)


def _index(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise VideoFramePipelineError(f"{field} is invalid")
    return value


def _channels(value: object, field: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise VideoFramePipelineError(f"{field} is invalid")
    result = tuple(value)
    if (
        not result
        or len(set(result)) != len(result)
        or not all(isinstance(item, str) and item for item in result)
    ):
        raise VideoFramePipelineError(f"{field} is invalid")
    return result


def _string_map(value: object, field: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise VideoFramePipelineError(f"{field} is invalid")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, str) or not item:
            raise VideoFramePipelineError(f"{field} is invalid")
        result[key] = item
    return MappingProxyType(dict(sorted(result.items())))


def _attempt(value: object, fence: object) -> tuple[str, int]:
    if (
        not isinstance(value, str)
        or _ATTEMPT.fullmatch(value) is None
        or not isinstance(fence, int)
        or isinstance(fence, bool)
        or fence < 1
    ):
        raise VideoFramePipelineError("producer attempt/fence is invalid")
    return value, fence


def _artifact_ref(project_ref: ProjectRef, value: str) -> ArtifactRef:
    parts = value.rsplit("/", 2)
    if len(parts) != 3 or parts[0] != f"artifact://{project_ref.value}":
        raise VideoFramePipelineError("ArtifactRef is malformed or crossed Project scope")
    try:
        return ArtifactRef(project_ref, parts[1], int(parts[2]))
    except (TypeError, ValueError) as exc:
        raise VideoFramePipelineError("ArtifactRef is malformed") from exc


def _video_ref(value: ImageArtifactContentRef) -> VideoArtifactContentRef:
    return VideoArtifactContentRef(
        value.project_ref,
        value.artifact_ref,
        value.content_ref,
        value.content_sha256,
    )


def _image_ref(value: VideoArtifactContentRef) -> ImageArtifactContentRef:
    return ImageArtifactContentRef(
        value.project_ref,
        value.artifact_ref,
        value.content_ref,
        value.content_sha256,
    )


@dataclass(frozen=True)
class VideoFrameRequest:
    """One logical sequence position mapped to an exact decoder request."""

    sequence_index: int
    requested_timestamp: float | None = None
    requested_frame_index: int | None = None

    def __post_init__(self) -> None:
        _index(self.sequence_index, "sequence_index")
        if self.requested_timestamp is None and self.requested_frame_index is None:
            raise VideoFramePipelineError(
                "frame request requires a timestamp, frame index, or both"
            )
        if self.requested_timestamp is not None:
            _finite(self.requested_timestamp, "requested_timestamp")
        if self.requested_frame_index is not None:
            _index(self.requested_frame_index, "requested_frame_index")


@dataclass(frozen=True)
class VideoFrameProcessingEvidence:
    project_ref: ProjectRef
    input_frame: ImageArtifactContentRef
    output_frame: ImageArtifactContentRef
    specification_digest: str
    image_output_digest: str
    tool_ref: str
    runtime_ref: str
    producer_attempt_id: str
    producer_fence: int
    evidence_digest: str

    @classmethod
    def create(
        cls,
        project_ref: ProjectRef,
        input_frame: ImageArtifactContentRef,
        output: ImageOutputRef,
        tool_ref: str,
        runtime_ref: str,
    ) -> "VideoFrameProcessingEvidence":
        payload = cls._payload(
            project_ref,
            input_frame,
            output.output,
            output.specification_digest,
            output.output_digest,
            tool_ref,
            runtime_ref,
            output.producer_attempt_id,
            output.producer_fence,
        )
        return cls(
            project_ref,
            input_frame,
            output.output,
            output.specification_digest,
            output.output_digest,
            tool_ref,
            runtime_ref,
            output.producer_attempt_id,
            output.producer_fence,
            _digest(payload),
        )

    @staticmethod
    def _payload(
        project_ref: ProjectRef,
        input_frame: ImageArtifactContentRef,
        output_frame: ImageArtifactContentRef,
        specification_digest: str,
        image_output_digest: str,
        tool_ref: str,
        runtime_ref: str,
        producer_attempt_id: str,
        producer_fence: int,
    ) -> dict[str, object]:
        if (
            not isinstance(project_ref, ProjectRef)
            or not isinstance(input_frame, ImageArtifactContentRef)
            or not isinstance(output_frame, ImageArtifactContentRef)
            or input_frame.project_ref != project_ref
            or output_frame.project_ref != project_ref
        ):
            raise VideoFramePipelineError("processing evidence crossed Project scope")
        attempt, fence = _attempt(producer_attempt_id, producer_fence)
        return {
            "project_ref": project_ref.value,
            "input_frame": input_frame.payload(),
            "output_frame": output_frame.payload(),
            "specification_digest": _sha(
                specification_digest, "specification_digest"
            ),
            "image_output_digest": _sha(image_output_digest, "image_output_digest"),
            "tool_ref": _ref(tool_ref, "image tool_ref"),
            "runtime_ref": _ref(runtime_ref, "image runtime_ref"),
            "producer_attempt_id": attempt,
            "producer_fence": fence,
        }

    def __post_init__(self) -> None:
        payload = self._payload(
            self.project_ref,
            self.input_frame,
            self.output_frame,
            self.specification_digest,
            self.image_output_digest,
            self.tool_ref,
            self.runtime_ref,
            self.producer_attempt_id,
            self.producer_fence,
        )
        if _sha(self.evidence_digest, "processing evidence_digest") != _digest(payload):
            raise VideoFramePipelineError("processing evidence digest is stale")

    def payload(self) -> dict[str, object]:
        payload = self._payload(
            self.project_ref,
            self.input_frame,
            self.output_frame,
            self.specification_digest,
            self.image_output_digest,
            self.tool_ref,
            self.runtime_ref,
            self.producer_attempt_id,
            self.producer_fence,
        )
        payload["evidence_digest"] = self.evidence_digest
        return payload


@dataclass(frozen=True)
class VideoFrameEvidence:
    """Immutable source-to-current-frame mapping independent of worker order."""

    project_ref: ProjectRef
    source: VideoArtifactContentRef
    sequence_index: int
    requested_timestamp: float | None
    requested_frame_index: int | None
    actual_decoder_timestamp: float
    actual_decoder_frame_index: int
    actual_decoder_frame_identity: str
    decoder_tool_ref: str
    decoder_tool_version: str
    decoder_runtime_ref: str
    decoder_metadata: Mapping[str, str]
    extracted_frame: ImageArtifactContentRef
    frame: ImageArtifactContentRef
    decoder_width: int
    decoder_height: int
    decoder_channels: tuple[str, ...]
    decoder_color_ref: str
    frame_width: int
    frame_height: int
    frame_channels: tuple[str, ...]
    frame_color_ref: str
    producer_attempt_id: str
    producer_fence: int
    processing: tuple[VideoFrameProcessingEvidence, ...]
    evidence_digest: str

    @classmethod
    def create(
        cls,
        *,
        project_ref: ProjectRef,
        source: VideoArtifactContentRef,
        request: VideoFrameRequest,
        actual_decoder_timestamp: float,
        actual_decoder_frame_index: int,
        actual_decoder_frame_identity: str,
        decoder_tool_ref: str,
        decoder_tool_version: str,
        decoder_runtime_ref: str,
        decoder_metadata: Mapping[str, str],
        extracted_frame: ImageArtifactContentRef,
        frame: ImageArtifactContentRef,
        decoder_width: int,
        decoder_height: int,
        decoder_channels: Sequence[str],
        decoder_color_ref: str,
        frame_width: int,
        frame_height: int,
        frame_channels: Sequence[str],
        frame_color_ref: str,
        producer_attempt_id: str,
        producer_fence: int,
        processing: Sequence[VideoFrameProcessingEvidence] = (),
    ) -> "VideoFrameEvidence":
        values = tuple(processing)
        payload = cls._payload(
            project_ref,
            source,
            request.sequence_index,
            request.requested_timestamp,
            request.requested_frame_index,
            actual_decoder_timestamp,
            actual_decoder_frame_index,
            actual_decoder_frame_identity,
            decoder_tool_ref,
            decoder_tool_version,
            decoder_runtime_ref,
            decoder_metadata,
            extracted_frame,
            frame,
            decoder_width,
            decoder_height,
            decoder_channels,
            decoder_color_ref,
            frame_width,
            frame_height,
            frame_channels,
            frame_color_ref,
            producer_attempt_id,
            producer_fence,
            values,
        )
        return cls(
            project_ref,
            source,
            request.sequence_index,
            request.requested_timestamp,
            request.requested_frame_index,
            actual_decoder_timestamp,
            actual_decoder_frame_index,
            actual_decoder_frame_identity,
            decoder_tool_ref,
            decoder_tool_version,
            decoder_runtime_ref,
            _string_map(decoder_metadata, "decoder_metadata"),
            extracted_frame,
            frame,
            decoder_width,
            decoder_height,
            _channels(decoder_channels, "decoder_channels"),
            decoder_color_ref,
            frame_width,
            frame_height,
            _channels(frame_channels, "frame_channels"),
            frame_color_ref,
            producer_attempt_id,
            producer_fence,
            values,
            _digest(payload),
        )

    @staticmethod
    def _payload(
        project_ref: ProjectRef,
        source: VideoArtifactContentRef,
        sequence_index: int,
        requested_timestamp: float | None,
        requested_frame_index: int | None,
        actual_decoder_timestamp: float,
        actual_decoder_frame_index: int,
        actual_decoder_frame_identity: str,
        decoder_tool_ref: str,
        decoder_tool_version: str,
        decoder_runtime_ref: str,
        decoder_metadata: Mapping[str, str],
        extracted_frame: ImageArtifactContentRef,
        frame: ImageArtifactContentRef,
        decoder_width: int,
        decoder_height: int,
        decoder_channels: Sequence[str],
        decoder_color_ref: str,
        frame_width: int,
        frame_height: int,
        frame_channels: Sequence[str],
        frame_color_ref: str,
        producer_attempt_id: str,
        producer_fence: int,
        processing: Sequence[VideoFrameProcessingEvidence],
    ) -> dict[str, object]:
        if (
            not isinstance(project_ref, ProjectRef)
            or not isinstance(source, VideoArtifactContentRef)
            or not isinstance(extracted_frame, ImageArtifactContentRef)
            or not isinstance(frame, ImageArtifactContentRef)
            or source.project_ref != project_ref
            or extracted_frame.project_ref != project_ref
            or frame.project_ref != project_ref
        ):
            raise VideoFramePipelineError("frame evidence crossed Project scope")
        request = VideoFrameRequest(
            _index(sequence_index, "sequence_index"),
            requested_timestamp,
            requested_frame_index,
        )
        actual_timestamp = _finite(
            actual_decoder_timestamp, "actual_decoder_timestamp"
        )
        actual_index = _index(
            actual_decoder_frame_index, "actual_decoder_frame_index"
        )
        if decoder_width < 1 or decoder_height < 1 or frame_width < 1 or frame_height < 1:
            raise VideoFramePipelineError("frame evidence dimensions are invalid")
        decoder_channel_values = _channels(decoder_channels, "decoder_channels")
        frame_channel_values = _channels(frame_channels, "frame_channels")
        attempt, fence = _attempt(producer_attempt_id, producer_fence)
        steps = tuple(processing)
        if not all(
            isinstance(step, VideoFrameProcessingEvidence)
            and step.project_ref == project_ref
            for step in steps
        ):
            raise VideoFramePipelineError("frame processing evidence is incompatible")
        current = extracted_frame
        for step in steps:
            if step.input_frame != current:
                raise VideoFramePipelineError("frame processing chain is broken")
            current = step.output_frame
        if current != frame:
            raise VideoFramePipelineError("current frame does not match processing chain")
        return {
            "project_ref": project_ref.value,
            "source": source.payload(),
            "source_sha256": source.content_sha256,
            "sequence_index": request.sequence_index,
            "requested_timestamp": request.requested_timestamp,
            "requested_frame_index": request.requested_frame_index,
            "actual_decoder_timestamp": actual_timestamp,
            "actual_decoder_frame_index": actual_index,
            "actual_decoder_frame_identity": _ref(
                actual_decoder_frame_identity, "actual_decoder_frame_identity"
            ),
            "decoder_tool_ref": _ref(decoder_tool_ref, "decoder_tool_ref"),
            "decoder_tool_version": _text(
                decoder_tool_version, "decoder_tool_version"
            ),
            "decoder_runtime_ref": _ref(decoder_runtime_ref, "decoder_runtime_ref"),
            "decoder_metadata": dict(_string_map(decoder_metadata, "decoder_metadata")),
            "extracted_frame": extracted_frame.payload(),
            "frame": frame.payload(),
            "decoder_width": decoder_width,
            "decoder_height": decoder_height,
            "decoder_channels": list(decoder_channel_values),
            "decoder_color_ref": _ref(decoder_color_ref, "decoder_color_ref"),
            "frame_width": frame_width,
            "frame_height": frame_height,
            "frame_channels": list(frame_channel_values),
            "frame_color_ref": _ref(frame_color_ref, "frame_color_ref"),
            "producer_attempt_id": attempt,
            "producer_fence": fence,
            "processing": [step.payload() for step in steps],
        }

    def __post_init__(self) -> None:
        payload = self._payload(
            self.project_ref,
            self.source,
            self.sequence_index,
            self.requested_timestamp,
            self.requested_frame_index,
            self.actual_decoder_timestamp,
            self.actual_decoder_frame_index,
            self.actual_decoder_frame_identity,
            self.decoder_tool_ref,
            self.decoder_tool_version,
            self.decoder_runtime_ref,
            self.decoder_metadata,
            self.extracted_frame,
            self.frame,
            self.decoder_width,
            self.decoder_height,
            self.decoder_channels,
            self.decoder_color_ref,
            self.frame_width,
            self.frame_height,
            self.frame_channels,
            self.frame_color_ref,
            self.producer_attempt_id,
            self.producer_fence,
            self.processing,
        )
        if _sha(self.evidence_digest, "frame evidence_digest") != _digest(payload):
            raise VideoFramePipelineError("frame evidence digest is stale")
        object.__setattr__(self, "decoder_metadata", _string_map(self.decoder_metadata, "decoder_metadata"))
        object.__setattr__(self, "decoder_channels", _channels(self.decoder_channels, "decoder_channels"))
        object.__setattr__(self, "frame_channels", _channels(self.frame_channels, "frame_channels"))
        object.__setattr__(self, "processing", tuple(self.processing))

    def payload(self) -> dict[str, object]:
        payload = self._payload(
            self.project_ref,
            self.source,
            self.sequence_index,
            self.requested_timestamp,
            self.requested_frame_index,
            self.actual_decoder_timestamp,
            self.actual_decoder_frame_index,
            self.actual_decoder_frame_identity,
            self.decoder_tool_ref,
            self.decoder_tool_version,
            self.decoder_runtime_ref,
            self.decoder_metadata,
            self.extracted_frame,
            self.frame,
            self.decoder_width,
            self.decoder_height,
            self.decoder_channels,
            self.decoder_color_ref,
            self.frame_width,
            self.frame_height,
            self.frame_channels,
            self.frame_color_ref,
            self.producer_attempt_id,
            self.producer_fence,
            self.processing,
        )
        payload["evidence_digest"] = self.evidence_digest
        return payload


@dataclass(frozen=True)
class VideoFrameSequenceResult:
    project_ref: ProjectRef
    clip: VideoClip
    manifest: VideoFrameSequenceManifest
    evidence: tuple[VideoFrameEvidence, ...]
    artifact: VideoArtifactContentRef
    producer_attempt_id: str
    producer_fence: int
    result_digest: str

    @classmethod
    def create(
        cls,
        clip: VideoClip,
        manifest: VideoFrameSequenceManifest,
        evidence: Sequence[VideoFrameEvidence],
        artifact: VideoArtifactContentRef,
        producer_attempt_id: str,
        producer_fence: int,
    ) -> "VideoFrameSequenceResult":
        values = tuple(evidence)
        payload = cls._payload(
            clip.project_ref,
            clip,
            manifest,
            values,
            artifact,
            producer_attempt_id,
            producer_fence,
        )
        return cls(
            clip.project_ref,
            clip,
            manifest,
            values,
            artifact,
            producer_attempt_id,
            producer_fence,
            _digest(payload),
        )

    @staticmethod
    def _payload(
        project_ref: ProjectRef,
        clip: VideoClip,
        manifest: VideoFrameSequenceManifest,
        evidence: Sequence[VideoFrameEvidence],
        artifact: VideoArtifactContentRef,
        producer_attempt_id: str,
        producer_fence: int,
    ) -> dict[str, object]:
        values = tuple(evidence)
        if (
            not isinstance(project_ref, ProjectRef)
            or not isinstance(clip, VideoClip)
            or not isinstance(manifest, VideoFrameSequenceManifest)
            or not isinstance(artifact, VideoArtifactContentRef)
            or clip.project_ref != project_ref
            or manifest.project_ref != project_ref
            or artifact.project_ref != project_ref
            or not values
            or not all(
                isinstance(item, VideoFrameEvidence) and item.project_ref == project_ref
                for item in values
            )
        ):
            raise VideoFramePipelineError("sequence result crossed Project scope")
        attempt, fence = _attempt(producer_attempt_id, producer_fence)
        if tuple(item.sequence_index for item in values) != tuple(range(len(values))):
            raise VideoFramePipelineError("sequence evidence is missing or out of order")
        if len(manifest.frames) != len(values):
            raise VideoFramePipelineError("canonical manifest omitted sequence evidence")
        for frame, item in zip(manifest.frames, values, strict=True):
            if (
                frame.frame_index != item.sequence_index
                or frame.timestamp != item.actual_decoder_timestamp
                or frame.frame != _video_ref(item.frame)
                or frame.clip != clip
            ):
                raise VideoFramePipelineError("canonical frame mapping is stale")
        return {
            "project_ref": project_ref.value,
            "clip": clip.payload(),
            "manifest_digest": manifest.manifest_digest,
            "evidence_digests": [item.evidence_digest for item in values],
            "artifact": artifact.payload(),
            "producer_attempt_id": attempt,
            "producer_fence": fence,
        }

    def __post_init__(self) -> None:
        payload = self._payload(
            self.project_ref,
            self.clip,
            self.manifest,
            self.evidence,
            self.artifact,
            self.producer_attempt_id,
            self.producer_fence,
        )
        if _sha(self.result_digest, "result_digest") != _digest(payload):
            raise VideoFramePipelineError("sequence result digest is stale")
        object.__setattr__(self, "evidence", tuple(self.evidence))


@dataclass(frozen=True)
class VideoDerivedArtifactEvidence:
    project_ref: ProjectRef
    kind: str
    sequence_manifest_digest: str
    source_frame_evidence_digest: str
    image: ImageArtifactContentRef
    artifact: VideoArtifactContentRef
    evidence_artifact: VideoArtifactContentRef
    width: int
    height: int
    channels: tuple[str, ...]
    color_ref: str
    image_specification_digest: str
    image_output_digest: str
    tool_ref: str
    tool_version: str
    runtime_ref: str
    producer_attempt_id: str
    producer_fence: int
    evidence_digest: str

    def __post_init__(self) -> None:
        if self.kind not in {"thumbnail", "preview"}:
            raise VideoFramePipelineError("derived artifact kind is invalid")
        if (
            not isinstance(self.project_ref, ProjectRef)
            or self.image.project_ref != self.project_ref
            or self.artifact.project_ref != self.project_ref
            or self.evidence_artifact.project_ref != self.project_ref
        ):
            raise VideoFramePipelineError("derived artifact crossed Project scope")
        _sha(self.sequence_manifest_digest, "sequence_manifest_digest")
        _sha(self.source_frame_evidence_digest, "source_frame_evidence_digest")
        _sha(self.image_specification_digest, "image_specification_digest")
        _sha(self.image_output_digest, "image_output_digest")
        _sha(self.evidence_digest, "derived evidence_digest")
        if self.width < 1 or self.height < 1:
            raise VideoFramePipelineError("derived artifact dimensions are invalid")
        object.__setattr__(self, "channels", _channels(self.channels, "derived channels"))
        _ref(self.color_ref, "derived color_ref")
        _ref(self.tool_ref, "derived tool_ref")
        _text(self.tool_version, "derived tool_version")
        _ref(self.runtime_ref, "derived runtime_ref")
        _attempt(self.producer_attempt_id, self.producer_fence)


@dataclass(frozen=True)
class _ResolvedArtifact:
    artifact: Artifact
    content_ref: ContentRef
    payload: bytes


@dataclass(frozen=True)
class _DecodedImage:
    width: int
    height: int
    format: str
    channels: tuple[str, ...]
    color_ref: str


@dataclass(frozen=True)
class _DecoderFrame:
    index: int
    timestamp: float
    width: int
    height: int
    metadata: Mapping[str, str]
    color_ref: str
    identity: str


class VideoFramePipeline:
    """Frame execution boundary; scheduling authority is always supplied upstream."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        access: ProjectAccess,
        root_ref: FilesystemRootRef,
        working_directory: str,
        image_tool: DeterministicImageTool | None = None,
        ffmpeg_executable: str | Path = _FFMPEG,
        ffprobe_executable: str | Path = _FFPROBE,
        tool_ref: str = "tool://ffmpeg/decoder",
        runtime_ref: str = "runtime://video/ffmpeg-pillow-cpu",
    ) -> None:
        if not isinstance(access, ProjectAccess):
            raise VideoFramePipelineError("exact ProjectAccess is required")
        if not isinstance(root_ref, FilesystemRootRef) or root_ref.project_ref != access.project_ref:
            raise VideoFramePipelineError("video frame FilesystemRoot crossed Project scope")
        if not isinstance(working_directory, str) or not working_directory:
            raise VideoFramePipelineError("video frame working directory is required")
        self.database = Path(database_path)
        self.objects = object_store
        self.access = access
        self.project_ref = access.project_ref
        self.root_ref = root_ref
        self.working_directory = working_directory
        self.artifacts = ArtifactService(self.database)
        self.executions = NodeExecutionService(self.database)
        self.process = ManagedProcessAdapter(self.database, self.objects)
        self.image_tool = image_tool or DeterministicImageTool(
            self.database, self.objects, access=self.access
        )
        if self.image_tool.project_ref != self.project_ref:
            raise VideoFramePipelineError("P3-11 image tool crossed Project scope")
        self.ffmpeg = Path(ffmpeg_executable)
        self.ffprobe = Path(ffprobe_executable)
        self._ffmpeg_sha256 = _file_sha256(self.ffmpeg)
        self._ffprobe_sha256 = _file_sha256(self.ffprobe)
        self.tool_ref = _ref(tool_ref, "decoder tool_ref")
        self.runtime_ref = _ref(runtime_ref, "decoder runtime_ref")
        self.tool_version = (
            f"ffmpeg version {_FFMPEG_VERSION}; ffprobe version {_FFMPEG_VERSION}"
        )

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
        cancellation: Event | None,
        label: str,
    ) -> ProcessResult:
        attempt = self._require_dispatch(dispatch)
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
            stderr_limit_bytes=8 * 1024 * 1024,
            resource_allocation_ref=dispatch.allocation.allocation_ref,
            descriptor_content_refs=descriptors,
        )

        def cancelled() -> bool:
            return self._dispatch_cancelled(dispatch) or (
                cancellation is not None and cancellation.is_set()
            )

        try:
            result = self.process.execute(
                self.access,
                attempt,
                request,
                idempotency_key=idempotency_key,
                cancelled=cancelled,
            )
        except ProcessError as exc:
            raise VideoFramePipelineError(
                f"managed {label} authority or execution failed"
            ) from exc
        if result.status is ProcessStatus.CANCELLED:
            raise VideoFramePipelineError(f"managed {label} was cancelled")
        if result.status is not ProcessStatus.SUCCEEDED:
            raise VideoFramePipelineError(
                f"managed {label} worker failed: {result.stderr_preview[:1024]}"
            )
        if result.stdout_truncated or result.stderr_truncated:
            raise VideoFramePipelineError(f"managed {label} evidence was truncated")
        return result

    def _resolve(
        self, source: VideoArtifactContentRef | ImageArtifactContentRef
    ) -> _ResolvedArtifact:
        if source.project_ref != self.project_ref:
            raise VideoFramePipelineError("Artifact crossed Project scope")
        reference = _artifact_ref(self.project_ref, source.artifact_ref)
        try:
            artifact = self.artifacts.get_artifact(self.access, reference)
        except ArtifactError as exc:
            raise VideoFramePipelineError("Artifact is missing or stale") from exc
        content = artifact.content_ref
        if (
            content is None
            or content.value != source.content_ref
            or content.digest != source.content_sha256
        ):
            raise VideoFramePipelineError("Artifact/Content identity is stale or forged")
        try:
            if not self.objects.verify(content):
                raise VideoFramePipelineError("Content is missing or corrupt")
            payload = self.objects.read(content)
            content.verify(payload)
        except (ArtifactError, ObjectStorageError) as exc:
            raise VideoFramePipelineError("Content is missing or corrupt") from exc
        return _ResolvedArtifact(artifact, content, payload)

    @staticmethod
    def _decode_image(payload: bytes) -> _DecodedImage:
        try:
            with Image.open(BytesIO(payload)) as probe:
                detected = probe.format
                probe.verify()
            with Image.open(BytesIO(payload)) as reopened:
                reopened.load()
                width, height = reopened.size
                channels = tuple(reopened.getbands())
                profile = reopened.info.get("icc_profile")
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise VideoFramePipelineError("frame image is missing or corrupt") from exc
        if detected is None or width < 1 or height < 1 or not channels:
            raise VideoFramePipelineError("frame image decode identity is incomplete")
        color_ref = (
            f"profile://icc/sha256/{hashlib.sha256(profile).hexdigest()}"
            if isinstance(profile, bytes) and profile
            else "profile://image/unspecified"
        )
        return _DecodedImage(width, height, detected, channels, color_ref)

    def _require_dispatch(self, dispatch: ScheduledDispatch) -> NodeExecutionAttempt:
        if not isinstance(dispatch, ScheduledDispatch):
            raise VideoFramePipelineError("exact ScheduledDispatch is required")
        allocation, attempt = dispatch.allocation, dispatch.node_attempt
        if (
            allocation.project_ref != self.project_ref
            or attempt.node_ref.project_ref != self.project_ref
        ):
            raise VideoFramePipelineError("dispatch crossed Project scope")
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
            raise VideoFramePipelineError("dispatch allocation/attempt evidence is stale")
        current = self.executions.get_node_execution(self.access, attempt.node_ref)
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
            raise VideoFramePipelineError("Node attempt is not current")
        try:
            node_expiry = datetime.fromisoformat(attempt.lease_expires_at)
            allocation_expiry = datetime.fromisoformat(allocation.lease_expires_at)
            now = datetime.now(node_expiry.tzinfo)
        except (TypeError, ValueError) as exc:
            raise VideoFramePipelineError("dispatch lease is malformed") from exc
        if node_expiry <= now or allocation_expiry <= now:
            raise VideoFramePipelineError("dispatch lease is stale")
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
            raise VideoFramePipelineError("producer Run authority is stale")
        matches = tuple(
            candidate
            for candidate in self.artifacts.runs.list_attempts(self.access, attempt.run_ref)
            if candidate.attempt_id == attempt.run_attempt_id
            and candidate.fence == attempt.run_fence
            and candidate.completed_at is None
        )
        if len(matches) != 1:
            raise VideoFramePipelineError("producer Run attempt/fence is stale")
        return matches[0]

    def _publish(
        self,
        dispatch: ScheduledDispatch,
        *,
        role: str,
        payload: bytes,
        media_type: str,
        sources: Sequence[_ResolvedArtifact],
        derivation: str,
        process_results: Sequence[ProcessResult] = (),
    ) -> tuple[Artifact, ContentRef]:
        attempt = self._require_dispatch(dispatch)
        producer = self._producer(attempt)
        try:
            content = self.objects.put(
                payload,
                media_type=media_type,
                expected_digest=hashlib.sha256(payload).hexdigest(),
                expected_size=len(payload),
            )
            if not self.objects.verify(content) or self.objects.read(content) != payload:
                raise VideoFramePipelineError("fresh output Content verification failed")
            artifact = self.artifacts.publish_from_run(
                self.access,
                producer_attempt=producer,
                expected_task_ref=attempt.task_ref,
                expected_task_digest=attempt.task_digest,
                role=role,
                content_ref=content,
                source_refs=(),
                source_artifact_refs=(
                    tuple(item.artifact.artifact_ref for item in sources)
                    + tuple(item.artifact_ref for item in process_results)
                ),
                source_content_refs=(
                    tuple(item.content_ref for item in sources)
                    + tuple(item.result_ref for item in process_results)
                ),
                derivation_type=derivation,
                metadata={"media_type": media_type},
            )
            reopened = self.artifacts.get_artifact(self.access, artifact.artifact_ref)
            if reopened.content_ref != content or self.objects.read(content) != payload:
                raise VideoFramePipelineError("fresh output Artifact verification failed")
        except (ArtifactError, ObjectStorageError) as exc:
            raise VideoFramePipelineError("durable output publication failed") from exc
        return artifact, content

    @staticmethod
    def _mapping(value: object, field: str) -> Mapping[str, object]:
        if not isinstance(value, Mapping) or not all(
            isinstance(key, str) for key in value
        ):
            raise VideoFramePipelineError(f"{field} is malformed")
        return value

    @staticmethod
    def _frame_timestamp(frame: Mapping[str, object]) -> float:
        for key in (
            "best_effort_timestamp_time",
            "pkt_pts_time",
            "pkt_dts_time",
        ):
            raw = frame.get(key)
            if isinstance(raw, (str, int, float)) and not isinstance(raw, bool):
                try:
                    return _finite(float(raw), "decoder frame timestamp")
                except (ValueError, VideoFramePipelineError):
                    continue
        raise VideoFramePipelineError("decoder frame timestamp evidence is missing")

    @staticmethod
    def _integer_field(
        frame: Mapping[str, object], stream: Mapping[str, object], key: str
    ) -> int:
        raw = frame.get(key, stream.get(key))
        if isinstance(raw, bool) or not isinstance(raw, (str, int)):
            raise VideoFramePipelineError(f"decoder {key} is malformed")
        try:
            result = int(raw)
        except (TypeError, ValueError) as exc:
            raise VideoFramePipelineError(f"decoder {key} evidence is missing") from exc
        if result < 1:
            raise VideoFramePipelineError(f"decoder {key} is invalid")
        return result

    def _probe_frames(
        self,
        content: ContentRef,
        dispatch: ScheduledDispatch,
        cancellation: Event | None,
    ) -> tuple[tuple[_DecoderFrame, ...], ProcessResult]:
        entries = (
            "stream=width,height,pix_fmt,color_range,color_space,color_transfer,"
            "color_primaries:frame=media_type,best_effort_timestamp_time,pkt_pts_time,"
            "pkt_dts_time,pkt_dts,coded_picture_number,display_picture_number,key_frame,"
            "pict_type,width,height,pix_fmt,color_range,color_space,color_transfer,"
            "color_primaries"
        )
        token = _digest(
            {
                "content_sha256": content.digest,
                "executable_sha256": self._ffprobe_sha256,
                "entries": entries,
            }
        )[:40]
        process = self._managed_process(
            dispatch,
            executable=self.ffprobe,
            executable_sha256=self._ffprobe_sha256,
            argv=(
                "-hide_banner",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                entries,
                "-of",
                "json",
                "-fd",
                "@minitz-content-fd:input",
                "fd:",
            ),
            descriptors={"input": content},
            idempotency_key=f"video-frame-probe-{token}",
            stdout_limit_bytes=64 * 1024 * 1024,
            cancellation=cancellation,
            label="FFprobe frame inspection",
        )
        try:
            output = self.objects.read(process.stdout_ref)
            loaded: object = json.loads(output)
        except (ObjectStorageError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VideoFramePipelineError("FFprobe evidence is malformed") from exc
        root = self._mapping(loaded, "FFprobe evidence")
        streams_value = root.get("streams")
        frames_value = root.get("frames")
        if (
            not isinstance(streams_value, list)
            or len(streams_value) != 1
            or not isinstance(frames_value, list)
            or not frames_value
        ):
            raise VideoFramePipelineError("video stream or decoder frames are missing")
        stream = self._mapping(streams_value[0], "FFprobe stream")
        result: list[_DecoderFrame] = []
        for decoder_index, raw_frame in enumerate(frames_value):
            frame = self._mapping(raw_frame, "FFprobe frame")
            if frame.get("media_type", "video") != "video":
                continue
            timestamp = self._frame_timestamp(frame)
            width = self._integer_field(frame, stream, "width")
            height = self._integer_field(frame, stream, "height")
            metadata: dict[str, str] = {}
            for key in (
                "pix_fmt",
                "color_range",
                "color_space",
                "color_transfer",
                "color_primaries",
                "pkt_dts",
                "coded_picture_number",
                "display_picture_number",
                "key_frame",
                "pict_type",
            ):
                value = frame.get(key, stream.get(key, "unspecified"))
                metadata[key] = str(value)
            metadata["timestamp"] = format(timestamp, ".17g")
            metadata["decoder_frame_index"] = str(decoder_index)
            metadata["ffprobe_executable_sha256"] = self._ffprobe_sha256
            metadata["ffprobe_process_artifact_ref"] = process.artifact_ref.value
            metadata["ffprobe_result_sha256"] = process.result_ref.digest
            color_payload = {
                key: metadata[key]
                for key in (
                    "pix_fmt",
                    "color_range",
                    "color_space",
                    "color_transfer",
                    "color_primaries",
                )
            }
            color_ref = f"color://ffprobe/sha256/{_digest(color_payload)}"
            identity_payload = {
                "index": decoder_index,
                "timestamp": timestamp,
                "width": width,
                "height": height,
                "metadata": metadata,
            }
            result.append(
                _DecoderFrame(
                    decoder_index,
                    timestamp,
                    width,
                    height,
                    MappingProxyType(metadata),
                    color_ref,
                    f"decoder-frame://sha256/{_digest(identity_payload)}",
                )
            )
        if not result:
            raise VideoFramePipelineError("video has no decodable frames")
        return tuple(result), process

    @staticmethod
    def _select_frame(
        request: VideoFrameRequest, frames: Sequence[_DecoderFrame]
    ) -> _DecoderFrame:
        by_index: _DecoderFrame | None = None
        by_timestamp: _DecoderFrame | None = None
        if request.requested_frame_index is not None:
            if request.requested_frame_index >= len(frames):
                raise VideoFramePipelineError("requested decoder frame is missing")
            by_index = frames[request.requested_frame_index]
        requested_timestamp = request.requested_timestamp
        if requested_timestamp is not None:
            by_timestamp = min(
                frames,
                key=lambda item: (
                    abs(item.timestamp - requested_timestamp),
                    item.timestamp,
                    item.index,
                ),
            )
        if by_index is not None and by_timestamp is not None and by_index != by_timestamp:
            raise VideoFramePipelineError(
                "requested timestamp and frame index identify different decoder frames"
            )
        selected = by_index or by_timestamp
        if selected is None:
            raise VideoFramePipelineError("frame request did not resolve")
        return selected

    def _extract_png(
        self,
        content: ContentRef,
        frame_index: int,
        dispatch: ScheduledDispatch,
        cancellation: Event | None,
    ) -> tuple[bytes, ProcessResult]:
        token = _digest(
            {
                "content_sha256": content.digest,
                "executable_sha256": self._ffmpeg_sha256,
                "frame_index": frame_index,
            }
        )[:40]
        process = self._managed_process(
            dispatch,
            executable=self.ffmpeg,
            executable_sha256=self._ffmpeg_sha256,
            argv=(
                "-nostdin",
                "-v",
                "error",
                "-fd",
                "@minitz-content-fd:input",
                "-i",
                "fd:",
                "-map",
                "0:v:0",
                "-vf",
                f"select=eq(n\\,{frame_index})",
                "-frames:v",
                "1",
                "-c:v",
                "png",
                "-f",
                "image2pipe",
                "pipe:1",
            ),
            descriptors={"input": content},
            idempotency_key=f"video-frame-extract-{token}",
            stdout_limit_bytes=256 * 1024 * 1024,
            cancellation=cancellation,
            label=f"FFmpeg frame {frame_index} extraction",
        )
        try:
            payload = self.objects.read(process.stdout_ref)
        except ObjectStorageError as exc:
            raise VideoFramePipelineError(
                "managed FFmpeg frame stdout evidence is unavailable"
            ) from exc
        if not payload:
            raise VideoFramePipelineError("FFmpeg returned a missing frame")
        return payload, process

    @staticmethod
    def _requests(requests: Sequence[VideoFrameRequest]) -> tuple[VideoFrameRequest, ...]:
        values = tuple(requests)
        if not values or len(values) > _MAX_SEQUENCE_FRAMES:
            raise VideoFramePipelineError("frame sequence is empty or unbounded")
        if not all(isinstance(item, VideoFrameRequest) for item in values):
            raise VideoFramePipelineError("frame sequence request is malformed")
        if tuple(item.sequence_index for item in values) != tuple(range(len(values))):
            raise VideoFramePipelineError(
                "frame sequence requests are missing, duplicate, or out of order"
            )
        return values

    def extract_frame(
        self,
        source: VideoArtifactContentRef,
        request: VideoFrameRequest,
        dispatch: ScheduledDispatch,
        *,
        cancellation: Event | None = None,
    ) -> VideoFrameEvidence:
        if not isinstance(request, VideoFrameRequest):
            raise VideoFramePipelineError("exact VideoFrameRequest is required")
        self._require_dispatch(dispatch)
        resolved = self._resolve(source)
        frames, probe_process = self._probe_frames(
            resolved.content_ref, dispatch, cancellation
        )
        selected = self._select_frame(request, frames)
        return self._extract_evidence(
            source,
            resolved,
            request,
            selected,
            probe_process,
            dispatch,
            cancellation,
        )

    def _extract_evidence(
        self,
        source: VideoArtifactContentRef,
        resolved_source: _ResolvedArtifact,
        request: VideoFrameRequest,
        selected: _DecoderFrame,
        probe_process: ProcessResult,
        dispatch: ScheduledDispatch,
        cancellation: Event | None,
    ) -> VideoFrameEvidence:
        png, extract_process = self._extract_png(
            resolved_source.content_ref,
            selected.index,
            dispatch,
            cancellation,
        )
        decoded = self._decode_image(png)
        if (decoded.width, decoded.height) != (selected.width, selected.height):
            raise VideoFramePipelineError(
                "decoded frame dimensions contradict FFprobe evidence"
            )
        artifact, content = self._publish(
            dispatch,
            role="image.source",
            payload=png,
            media_type="image/png",
            sources=(resolved_source,),
            derivation="video.frame-extract",
            process_results=(probe_process, extract_process),
        )
        image = ImageArtifactContentRef(
            self.project_ref, artifact.artifact_ref.value, content.value, content.digest
        )
        attempt = dispatch.node_attempt
        decoder_metadata = dict(selected.metadata)
        decoder_metadata.update(
            {
                "ffmpeg_executable_sha256": self._ffmpeg_sha256,
                "ffmpeg_process_artifact_ref": extract_process.artifact_ref.value,
                "ffmpeg_result_sha256": extract_process.result_ref.digest,
            }
        )
        return VideoFrameEvidence.create(
            project_ref=self.project_ref,
            source=source,
            request=request,
            actual_decoder_timestamp=selected.timestamp,
            actual_decoder_frame_index=selected.index,
            actual_decoder_frame_identity=selected.identity,
            decoder_tool_ref=self.tool_ref,
            decoder_tool_version=self.tool_version,
            decoder_runtime_ref=self.runtime_ref,
            decoder_metadata=decoder_metadata,
            extracted_frame=image,
            frame=image,
            decoder_width=decoded.width,
            decoder_height=decoded.height,
            decoder_channels=decoded.channels,
            decoder_color_ref=selected.color_ref,
            frame_width=decoded.width,
            frame_height=decoded.height,
            frame_channels=decoded.channels,
            frame_color_ref=selected.color_ref,
            producer_attempt_id=attempt.attempt_id,
            producer_fence=attempt.fence,
        )

    def extract_sequence(
        self,
        clip: VideoClip,
        requests: Sequence[VideoFrameRequest],
        *,
        sequence_ref: str,
        version: str,
        fps: str,
        dispatch: ScheduledDispatch,
        cancellation: Event | None = None,
    ) -> VideoFrameSequenceResult:
        if not isinstance(clip, VideoClip) or clip.project_ref != self.project_ref:
            raise VideoFramePipelineError("video clip crossed Project scope")
        values = self._requests(requests)
        self._require_dispatch(dispatch)
        resolved = self._resolve(clip.source)
        evidence: list[VideoFrameEvidence] = []
        decoder_frames, probe_process = self._probe_frames(
            resolved.content_ref, dispatch, cancellation
        )
        selected = tuple(
            self._select_frame(request, decoder_frames) for request in values
        )
        identities = tuple(item.identity for item in selected)
        indexes = tuple(item.index for item in selected)
        timestamps = tuple(item.timestamp for item in selected)
        if (
            len(set(identities)) != len(identities)
            or indexes != tuple(sorted(indexes))
            or len(set(indexes)) != len(indexes)
            or timestamps != tuple(sorted(timestamps))
            or len(set(timestamps)) != len(timestamps)
        ):
            raise VideoFramePipelineError(
                "decoder frame sequence is duplicate or out of order"
            )
        decoder_signature = {
            (item.width, item.height, item.color_ref) for item in selected
        }
        if len(decoder_signature) != 1:
            raise VideoFramePipelineError(
                "decoder frame dimensions or color identity mismatch"
            )
        for request, decoder_frame in zip(values, selected, strict=True):
            if cancellation is not None and cancellation.is_set():
                raise VideoFramePipelineError("frame sequence extraction was cancelled")
            evidence.append(
                self._extract_evidence(
                    clip.source,
                    resolved,
                    request,
                    decoder_frame,
                    probe_process,
                    dispatch,
                    cancellation,
                )
            )
        return self._publish_sequence(
            clip,
            evidence,
            sequence_ref=sequence_ref,
            version=version,
            fps=fps,
            dispatch=dispatch,
        )

    @staticmethod
    def _fps(value: str) -> float:
        _text(value, "fps")
        try:
            result = float(Fraction(value))
        except (ValueError, ZeroDivisionError) as exc:
            raise VideoFramePipelineError("fps is invalid") from exc
        if not math.isfinite(result) or result <= 0:
            raise VideoFramePipelineError("fps is invalid")
        return result

    def consume_image_sequence(
        self,
        clip: VideoClip,
        frames: Sequence[ImageArtifactContentRef],
        timestamps: Sequence[float],
        *,
        sequence_ref: str,
        version: str,
        fps: str,
        dispatch: ScheduledDispatch,
        source_frame_indices: Sequence[int] | None = None,
        tool_ref: str = "tool://image/artifact-sequence",
        tool_version: str = "image-artifact-v1",
        runtime_ref: str = "runtime://image/artifact-sequence",
    ) -> VideoFrameSequenceResult:
        if not isinstance(clip, VideoClip) or clip.project_ref != self.project_ref:
            raise VideoFramePipelineError("image sequence clip crossed Project scope")
        frame_values, timestamp_values = tuple(frames), tuple(timestamps)
        if (
            not frame_values
            or len(frame_values) != len(timestamp_values)
            or len(frame_values) > _MAX_SEQUENCE_FRAMES
            or not all(isinstance(item, ImageArtifactContentRef) for item in frame_values)
        ):
            raise VideoFramePipelineError("image frame sequence is missing or malformed")
        indexes = (
            tuple(range(len(frame_values)))
            if source_frame_indices is None
            else tuple(source_frame_indices)
        )
        if (
            len(indexes) != len(frame_values)
            or not indexes
            or any(not isinstance(item, int) or isinstance(item, bool) for item in indexes)
            or indexes != tuple(range(indexes[0], indexes[0] + len(indexes)))
        ):
            raise VideoFramePipelineError(
                "image source frame indices are missing, duplicate, or out of order"
            )
        checked_timestamps = tuple(
            _finite(item, "image frame timestamp") for item in timestamp_values
        )
        if checked_timestamps != tuple(sorted(checked_timestamps)) or len(
            set(checked_timestamps)
        ) != len(checked_timestamps):
            raise VideoFramePipelineError("image timestamps are duplicate or out of order")
        self._require_dispatch(dispatch)
        self._resolve(clip.source)
        if len({(item.artifact_ref, item.content_sha256) for item in frame_values}) != len(
            frame_values
        ):
            raise VideoFramePipelineError("image frame sequence contains duplicate frames")
        resolved = tuple(self._resolve(item) for item in frame_values)
        decoded = tuple(self._decode_image(item.payload) for item in resolved)
        signatures = {
            (item.width, item.height, item.channels, item.color_ref) for item in decoded
        }
        if len(signatures) != 1:
            raise VideoFramePipelineError(
                "image frame dimensions, channels, or color identity mismatch"
            )
        attempt = dispatch.node_attempt
        evidence: list[VideoFrameEvidence] = []
        for sequence_index, (image, timestamp, source_index, inspection) in enumerate(
            zip(frame_values, checked_timestamps, indexes, decoded, strict=True)
        ):
            metadata = {
                "source_kind": "image-artifact",
                "source_artifact_ref": image.artifact_ref,
                "source_content_sha256": image.content_sha256,
            }
            identity = f"image-frame://sha256/{_digest({'frame': image.payload(), 'source_index': source_index, 'timestamp': timestamp})}"
            evidence.append(
                VideoFrameEvidence.create(
                    project_ref=self.project_ref,
                    source=clip.source,
                    request=VideoFrameRequest(sequence_index, timestamp, source_index),
                    actual_decoder_timestamp=timestamp,
                    actual_decoder_frame_index=source_index,
                    actual_decoder_frame_identity=identity,
                    decoder_tool_ref=tool_ref,
                    decoder_tool_version=tool_version,
                    decoder_runtime_ref=runtime_ref,
                    decoder_metadata=metadata,
                    extracted_frame=image,
                    frame=image,
                    decoder_width=inspection.width,
                    decoder_height=inspection.height,
                    decoder_channels=inspection.channels,
                    decoder_color_ref=inspection.color_ref,
                    frame_width=inspection.width,
                    frame_height=inspection.height,
                    frame_channels=inspection.channels,
                    frame_color_ref=inspection.color_ref,
                    producer_attempt_id=attempt.attempt_id,
                    producer_fence=attempt.fence,
                )
            )
        return self._publish_sequence(
            clip,
            evidence,
            sequence_ref=sequence_ref,
            version=version,
            fps=fps,
            dispatch=dispatch,
        )

    def consume_render_sequence(
        self,
        clip: VideoClip,
        render: RenderSequenceManifest,
        *,
        sequence_ref: str,
        version: str,
        fps: str,
        dispatch: ScheduledDispatch,
        pass_id: str = "beauty",
    ) -> VideoFrameSequenceResult:
        if (
            not isinstance(render, RenderSequenceManifest)
            or render.project_ref != self.project_ref
            or not isinstance(clip, VideoClip)
            or clip.project_ref != self.project_ref
        ):
            raise VideoFramePipelineError("render sequence crossed Project scope")
        expected = tuple(render.expected_frames)
        if (
            not expected
            or expected != tuple(range(expected[0], expected[0] + len(expected)))
            or render.failed_frames
        ):
            raise VideoFramePipelineError(
                "render sequence has missing, duplicate, failed, or out-of-order frames"
            )
        selected = tuple(item for item in render.completed_frames if item.pass_id == pass_id)
        if tuple(item.frame for item in selected) != expected:
            raise VideoFramePipelineError(
                "render sequence pass is missing, duplicate, or out of order"
            )
        images: list[ImageArtifactContentRef] = []
        for item in selected:
            render.require_frame(item)
            reference = _artifact_ref(self.project_ref, item.artifact_ref)
            artifact = self.artifacts.get_artifact(self.access, reference)
            if artifact.content_ref is None or artifact.content_ref.digest != item.content_sha256:
                raise VideoFramePipelineError("render frame Artifact/Content is stale")
            images.append(
                ImageArtifactContentRef(
                    self.project_ref,
                    reference.value,
                    artifact.content_ref.value,
                    artifact.content_ref.digest,
                )
            )
        rate = self._fps(fps)
        timestamps = tuple(
            render.request.time_seconds + (frame - expected[0]) / rate for frame in expected
        )
        return self.consume_image_sequence(
            clip,
            images,
            timestamps,
            sequence_ref=sequence_ref,
            version=version,
            fps=fps,
            dispatch=dispatch,
            source_frame_indices=expected,
            tool_ref=render.request.renderer_ref,
            tool_version=f"render-config-sha256:{render.request.config.digest}",
            runtime_ref=render.request.runtime_ref,
        )

    @staticmethod
    def _validate_evidence(values: Sequence[VideoFrameEvidence]) -> None:
        evidence = tuple(values)
        if tuple(item.sequence_index for item in evidence) != tuple(range(len(evidence))):
            raise VideoFramePipelineError("frame evidence is missing or out of order")
        if len({item.actual_decoder_frame_identity for item in evidence}) != len(evidence):
            raise VideoFramePipelineError("frame evidence contains duplicate identities")
        timestamps = tuple(item.actual_decoder_timestamp for item in evidence)
        indexes = tuple(item.actual_decoder_frame_index for item in evidence)
        if (
            timestamps != tuple(sorted(timestamps))
            or len(set(timestamps)) != len(timestamps)
            or indexes != tuple(sorted(indexes))
            or len(set(indexes)) != len(indexes)
        ):
            raise VideoFramePipelineError("frame evidence is duplicate or out of order")
        decoder_signatures = {
            (
                item.decoder_width,
                item.decoder_height,
                item.decoder_channels,
                item.decoder_color_ref,
            )
            for item in evidence
        }
        frame_signatures = {
            (item.frame_width, item.frame_height, item.frame_channels, item.frame_color_ref)
            for item in evidence
        }
        if len(decoder_signatures) != 1 or len(frame_signatures) != 1:
            raise VideoFramePipelineError(
                "frame dimensions, channels, or color identity mismatch"
            )

    def _publish_sequence(
        self,
        clip: VideoClip,
        evidence: Sequence[VideoFrameEvidence],
        *,
        sequence_ref: str,
        version: str,
        fps: str,
        dispatch: ScheduledDispatch,
    ) -> VideoFrameSequenceResult:
        values = tuple(evidence)
        if not values or len(values) > _MAX_SEQUENCE_FRAMES:
            raise VideoFramePipelineError("frame evidence sequence is empty or unbounded")
        if any(item.project_ref != self.project_ref or item.source != clip.source for item in values):
            raise VideoFramePipelineError("frame source mapping crossed Project scope")
        self._validate_evidence(values)
        frames = tuple(
            VideoFrameRef(
                self.project_ref,
                clip,
                item.sequence_index,
                item.actual_decoder_timestamp,
                _video_ref(item.frame),
            )
            for item in values
        )
        manifest = VideoFrameSequenceManifest.create(
            self.project_ref, sequence_ref, version, fps, frames
        )
        body = {
            "schema": "minitz.video-frame-sequence-evidence.v1",
            "project_ref": self.project_ref.value,
            "source": clip.source.payload(),
            "sequence_ref": manifest.sequence_ref,
            "version": manifest.version,
            "fps": manifest.fps,
            "manifest_digest": manifest.manifest_digest,
            "ordered_frames": [item.payload() for item in values],
        }
        payload = _json_bytes(body)
        source_artifacts = [self._resolve(clip.source)]
        source_artifacts.extend(self._resolve(item.frame) for item in values)
        artifact, content = self._publish(
            dispatch,
            role="video.frame-sequence",
            payload=payload,
            media_type="application/json",
            sources=source_artifacts,
            derivation="video.frame-sequence",
        )
        durable = VideoArtifactContentRef(
            self.project_ref, artifact.artifact_ref.value, content.value, content.digest
        )
        attempt = dispatch.node_attempt
        return VideoFrameSequenceResult.create(
            clip,
            manifest,
            values,
            durable,
            attempt.attempt_id,
            attempt.fence,
        )

    def process_sequence(
        self,
        sequence: VideoFrameSequenceResult,
        specifications: Mapping[int, ImageSpecification],
        dispatches: Mapping[int, ScheduledDispatch],
        *,
        sequence_ref: str,
        version: str,
        coordinator_dispatch: ScheduledDispatch,
        cancellation: Event | None = None,
    ) -> VideoFrameSequenceResult:
        if not isinstance(sequence, VideoFrameSequenceResult) or sequence.project_ref != self.project_ref:
            raise VideoFramePipelineError("exact Project sequence result is required")
        specification_map, dispatch_map = dict(specifications), dict(dispatches)
        keys = set(range(len(sequence.evidence)))
        if (
            not keys
            or len(keys) > _MAX_PROCESS_FRAMES
            or set(specification_map) != keys
            or set(dispatch_map) != keys
        ):
            raise VideoFramePipelineError(
                "frame processing specifications and dispatches must cover the exact sequence"
            )
        self._require_dispatch(coordinator_dispatch)
        values = tuple(dispatch_map[index] for index in sorted(keys))
        if (
            any(not isinstance(item, ScheduledDispatch) for item in values)
            or len({item.allocation.allocation_ref for item in values}) != len(values)
            or len({item.node_attempt.attempt_id for item in values}) != len(values)
            or len({item.node_attempt.node_ref for item in values}) != len(values)
        ):
            raise VideoFramePipelineError(
                "frame processing requires distinct existing dispatch authorities"
            )
        expected_output: tuple[int, int, tuple[str, ...], str] | None = None
        for index in sorted(keys):
            specification = specification_map[index]
            evidence = sequence.evidence[index]
            if (
                not isinstance(specification, ImageSpecification)
                or specification.project_ref != self.project_ref
                or specification.sources != (evidence.frame,)
            ):
                raise VideoFramePipelineError(
                    "image specification does not consume its exact ordered frame"
                )
            signature = (
                specification.width,
                specification.height,
                specification.channels,
                specification.profile_ref,
            )
            if expected_output is None:
                expected_output = signature
            elif signature != expected_output:
                raise VideoFramePipelineError(
                    "processed frame dimensions, channels, or color identity mismatch"
                )
        if cancellation is not None and cancellation.is_set():
            raise VideoFramePipelineError("frame processing was cancelled")
        outputs: dict[int, ImageOutputRef] = {}
        with ThreadPoolExecutor(
            max_workers=len(keys), thread_name_prefix="minitz-video-frame"
        ) as executor:
            futures: dict[Future[ImageOutputRef], int] = {
                executor.submit(
                    self.image_tool.execute_dispatched,
                    specification_map[index],
                    dispatch_map[index],
                ): index
                for index in sorted(keys)
            }
            pending = set(futures)
            try:
                while pending:
                    if cancellation is not None and cancellation.is_set():
                        for future in pending:
                            future.cancel()
                        raise VideoFramePipelineError("frame processing was cancelled")
                    completed, pending = wait(
                        pending, timeout=0.02, return_when=FIRST_COMPLETED
                    )
                    for future in completed:
                        index = futures[future]
                        try:
                            outputs[index] = future.result()
                        except Exception as exc:
                            for remaining in pending:
                                remaining.cancel()
                            raise VideoFramePipelineError(
                                f"frame processing worker {index} failed"
                            ) from exc
            finally:
                for future in pending:
                    future.cancel()
        processed: list[VideoFrameEvidence] = []
        for index, previous in enumerate(sequence.evidence):
            output = outputs[index]
            resolved = self._resolve(output.output)
            decoded = self._decode_image(resolved.payload)
            specification = specification_map[index]
            if (
                (decoded.width, decoded.height)
                != (specification.width, specification.height)
                or decoded.channels != specification.channels
            ):
                raise VideoFramePipelineError("processed frame decode evidence is incompatible")
            step = VideoFrameProcessingEvidence.create(
                self.project_ref,
                previous.frame,
                output,
                self.image_tool.tool_ref,
                self.image_tool.runtime_ref,
            )
            processed.append(
                VideoFrameEvidence.create(
                    project_ref=self.project_ref,
                    source=previous.source,
                    request=VideoFrameRequest(
                        previous.sequence_index,
                        previous.requested_timestamp,
                        previous.requested_frame_index,
                    ),
                    actual_decoder_timestamp=previous.actual_decoder_timestamp,
                    actual_decoder_frame_index=previous.actual_decoder_frame_index,
                    actual_decoder_frame_identity=previous.actual_decoder_frame_identity,
                    decoder_tool_ref=previous.decoder_tool_ref,
                    decoder_tool_version=previous.decoder_tool_version,
                    decoder_runtime_ref=previous.decoder_runtime_ref,
                    decoder_metadata=previous.decoder_metadata,
                    extracted_frame=previous.extracted_frame,
                    frame=output.output,
                    decoder_width=previous.decoder_width,
                    decoder_height=previous.decoder_height,
                    decoder_channels=previous.decoder_channels,
                    decoder_color_ref=previous.decoder_color_ref,
                    frame_width=decoded.width,
                    frame_height=decoded.height,
                    frame_channels=decoded.channels,
                    frame_color_ref=specification.profile_ref,
                    producer_attempt_id=previous.producer_attempt_id,
                    producer_fence=previous.producer_fence,
                    processing=(*previous.processing, step),
                )
            )
        return self._publish_sequence(
            sequence.clip,
            processed,
            sequence_ref=sequence_ref,
            version=version,
            fps=sequence.manifest.fps,
            dispatch=coordinator_dispatch,
        )

    def create_thumbnail(
        self,
        sequence: VideoFrameSequenceResult,
        sequence_index: int,
        *,
        width: int,
        height: int,
        dispatch: ScheduledDispatch,
        interpolation: str = "lanczos",
    ) -> VideoDerivedArtifactEvidence:
        return self._create_derived(
            "thumbnail",
            sequence,
            sequence_index,
            width,
            height,
            dispatch,
            interpolation,
        )

    def create_preview(
        self,
        sequence: VideoFrameSequenceResult,
        sequence_index: int,
        *,
        width: int,
        height: int,
        dispatch: ScheduledDispatch,
        interpolation: str = "lanczos",
    ) -> VideoDerivedArtifactEvidence:
        return self._create_derived(
            "preview",
            sequence,
            sequence_index,
            width,
            height,
            dispatch,
            interpolation,
        )

    def _create_derived(
        self,
        kind: str,
        sequence: VideoFrameSequenceResult,
        sequence_index: int,
        width: int,
        height: int,
        dispatch: ScheduledDispatch,
        interpolation: str,
    ) -> VideoDerivedArtifactEvidence:
        if not isinstance(sequence, VideoFrameSequenceResult) or sequence.project_ref != self.project_ref:
            raise VideoFramePipelineError("derived output sequence crossed Project scope")
        index = _index(sequence_index, "derived sequence_index")
        if index >= len(sequence.evidence) or width < 1 or height < 1:
            raise VideoFramePipelineError("derived frame or dimensions are missing")
        source = sequence.evidence[index]
        parameters = {"interpolation": _text(interpolation, "interpolation")}
        recipe_digest = _digest(
            {
                "kind": kind,
                "manifest": sequence.manifest.manifest_digest,
                "sequence_index": index,
                "parameters": parameters,
                "width": width,
                "height": height,
            }
        )
        operation = ImageOperation(
            "thumbnail", f"recipe://video/{kind}/v1", recipe_digest, parameters
        )
        specification = ImageSpecification.create(
            self.project_ref,
            f"video-{kind}-{sequence.manifest.manifest_digest[:16]}-{index}",
            (source.frame,),
            (),
            operation,
            width,
            height,
            "PNG",
            source.frame_channels,
            8,
            source.frame_color_ref,
            "straight" if "A" in source.frame_channels else "none",
            {"exif": "strip", "icc_profile": "strip", "text": "strip"},
            "model://image/deterministic",
            "1.0.0",
            self.image_tool.runtime_ref,
            0,
            {"video_derivation": kind},
            None,
            None,
            None,
            f"validator://video/{kind}/v1",
            {"role": "image.preview"},
        )
        try:
            output = self.image_tool.execute_dispatched(specification, dispatch)
        except ImageContractError as exc:
            raise VideoFramePipelineError(f"P3-11 {kind} processing failed") from exc
        resolved_image = self._resolve(output.output)
        decoded = self._decode_image(resolved_image.payload)
        if (decoded.width, decoded.height, decoded.channels) != (
            width,
            height,
            source.frame_channels,
        ):
            raise VideoFramePipelineError(f"{kind} decode evidence is incompatible")
        resolved_source = self._resolve(sequence.clip.source)
        wrapper_artifact, wrapper_content = self._publish(
            dispatch,
            role=f"video.{kind}",
            payload=resolved_image.payload,
            media_type="image/png",
            sources=(resolved_source, resolved_image),
            derivation=f"video.{kind}",
        )
        wrapper = VideoArtifactContentRef(
            self.project_ref,
            wrapper_artifact.artifact_ref.value,
            wrapper_content.value,
            wrapper_content.digest,
        )
        attempt = dispatch.node_attempt
        body = {
            "schema": "minitz.video-derived-frame-evidence.v1",
            "kind": kind,
            "project_ref": self.project_ref.value,
            "sequence_manifest_digest": sequence.manifest.manifest_digest,
            "source": sequence.clip.source.payload(),
            "source_frame_evidence": source.payload(),
            "image": output.output.payload(),
            "artifact": wrapper.payload(),
            "decode": {
                "width": decoded.width,
                "height": decoded.height,
                "format": decoded.format,
                "channels": list(decoded.channels),
                "color_ref": source.frame_color_ref,
            },
            "image_specification_digest": output.specification_digest,
            "image_output_digest": output.output_digest,
            "tool_ref": self.image_tool.tool_ref,
            "tool_version": "pillow-12.1.1",
            "runtime_ref": self.image_tool.runtime_ref,
            "producer_attempt_id": attempt.attempt_id,
            "producer_fence": attempt.fence,
        }
        evidence_payload = _json_bytes(body)
        evidence_artifact, evidence_content = self._publish(
            dispatch,
            role="video.validation-evidence",
            payload=evidence_payload,
            media_type="application/json",
            sources=(resolved_source, self._resolve(source.frame), resolved_image, self._resolve(wrapper)),
            derivation=f"video.{kind}.validate",
        )
        evidence_ref = VideoArtifactContentRef(
            self.project_ref,
            evidence_artifact.artifact_ref.value,
            evidence_content.value,
            evidence_content.digest,
        )
        return VideoDerivedArtifactEvidence(
            self.project_ref,
            kind,
            sequence.manifest.manifest_digest,
            source.evidence_digest,
            output.output,
            wrapper,
            evidence_ref,
            decoded.width,
            decoded.height,
            decoded.channels,
            source.frame_color_ref,
            output.specification_digest,
            output.output_digest,
            self.image_tool.tool_ref,
            "pillow-12.1.1",
            self.image_tool.runtime_ref,
            attempt.attempt_id,
            attempt.fence,
            evidence_content.digest,
        )


__all__ = [
    "VideoDerivedArtifactEvidence",
    "VideoFrameEvidence",
    "VideoFramePipeline",
    "VideoFramePipelineError",
    "VideoFrameProcessingEvidence",
    "VideoFrameRequest",
    "VideoFrameSequenceResult",
]
