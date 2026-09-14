"""Provider-neutral, fail-closed video production contracts."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol

from .capability import Capability, CapabilityRef
from .production_pack import GraphRecipeRegistration, GraphRecipeStepRegistration, ProductionPack, ProductionPackRef, ValidatorRegistration
from .project import ProjectRef

if TYPE_CHECKING:
    from .execution import NodeExecutionAttempt
    from .project import ProjectAccess


VIDEO_CAPABILITIES = ("inspect", "import", "generate", "edit", "trim", "sequence", "compose", "frame_extract", "frame_process", "audio_sync", "subtitle", "transcode", "encode", "mux", "thumbnail", "preview", "export", "validate")
VIDEO_ARTIFACT_ROLES = ("video.source", "video.clip", "video.timeline", "video.composite", "video.generated", "video.proxy", "video.frame-sequence", "video.preview", "video.export", "video.thumbnail", "video.subtitle-track", "video.validation-evidence", "video.session")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA = re.compile(r"[0-9a-f]{64}")
_ATTEMPT = re.compile(r"natt_[0-9a-f]{32}")
_GENERATIVE = {"generate"}


class VideoContractError(ValueError):
    pass


def _ref(value: object, field: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise VideoContractError(f"{field} is invalid")
    return value


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise VideoContractError(f"{field} is invalid")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise VideoContractError(f"{field} is invalid")
    return value


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise VideoContractError(f"{field} is not finite")
    return float(value)


def _map(value: object, field: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise VideoContractError(f"{field} is invalid")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, str) or not item:
            raise VideoContractError(f"{field} is invalid")
        if item.lower() in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
            raise VideoContractError(f"{field} is not finite")
        result[key] = item
    return MappingProxyType(dict(sorted(result.items())))


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _attempt(value: object, fence: object) -> tuple[str, int]:
    if not isinstance(value, str) or _ATTEMPT.fullmatch(value) is None or not isinstance(fence, int) or isinstance(fence, bool) or fence < 1:
        raise VideoContractError("producer attempt/fence is invalid")
    return value, fence


def _positive(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise VideoContractError(f"{field} is invalid")
    return value


@dataclass(frozen=True)
class VideoArtifactContentRef:
    project_ref: ProjectRef
    artifact_ref: str
    content_ref: str
    content_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise VideoContractError("Artifact Project is invalid")
        _ref(self.artifact_ref, "artifact_ref")
        _ref(self.content_ref, "content_ref")
        _sha(self.content_sha256, "content_sha256")

    def payload(self) -> dict[str, str]:
        return {"artifact_ref": self.artifact_ref, "content_ref": self.content_ref, "content_sha256": self.content_sha256}


@dataclass(frozen=True)
class VideoClip:
    project_ref: ProjectRef
    source: VideoArtifactContentRef
    source_start: float
    source_end: float
    timeline_start: float
    timeline_end: float
    timebase: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.source, VideoArtifactContentRef) or self.source.project_ref != self.project_ref:
            raise VideoContractError("clip Project/source is incompatible")
        start, end, timeline_start, timeline_end = (_finite(self.source_start, "source_start"), _finite(self.source_end, "source_end"), _finite(self.timeline_start, "timeline_start"), _finite(self.timeline_end, "timeline_end"))
        if start < 0 or timeline_start < 0 or end <= start or timeline_end <= timeline_start or not math.isclose(end - start, timeline_end - timeline_start, rel_tol=0.0, abs_tol=1e-9):
            raise VideoContractError("clip ranges are invalid")
        _text(self.timebase, "timebase")

    def payload(self) -> dict[str, object]:
        return {"source": self.source.payload(), "source_start": self.source_start, "source_end": self.source_end, "timeline_start": self.timeline_start, "timeline_end": self.timeline_end, "timebase": self.timebase}


@dataclass(frozen=True)
class VideoFrameRef:
    project_ref: ProjectRef
    clip: VideoClip
    frame_index: int
    timestamp: float
    frame: VideoArtifactContentRef

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.clip, VideoClip) or not isinstance(self.frame, VideoArtifactContentRef) or self.clip.project_ref != self.project_ref or self.frame.project_ref != self.project_ref:
            raise VideoContractError("frame Project/clip is incompatible")
        if not isinstance(self.frame_index, int) or isinstance(self.frame_index, bool) or self.frame_index < 0:
            raise VideoContractError("frame index is invalid")
        _finite(self.timestamp, "frame timestamp")

    def payload(self) -> dict[str, object]:
        return {"clip": self.clip.payload(), "frame_index": self.frame_index, "timestamp": self.timestamp, "frame": self.frame.payload()}


@dataclass(frozen=True)
class VideoFrameSequenceManifest:
    project_ref: ProjectRef
    sequence_ref: str
    version: str
    fps: str
    frames: tuple[VideoFrameRef, ...]
    manifest_digest: str

    @classmethod
    def create(cls, project_ref: ProjectRef, sequence_ref: str, version: str, fps: str, frames: Sequence[VideoFrameRef]) -> "VideoFrameSequenceManifest":
        payload = cls._payload(project_ref, sequence_ref, version, fps, frames)
        return cls(project_ref, sequence_ref, version, fps, tuple(frames), _digest(payload))

    @staticmethod
    def _payload(project_ref: ProjectRef, sequence_ref: str, version: str, fps: str, frames: Sequence[VideoFrameRef]) -> dict[str, object]:
        values = tuple(frames)
        if not isinstance(project_ref, ProjectRef) or not values or not all(isinstance(frame, VideoFrameRef) and frame.project_ref == project_ref for frame in values):
            raise VideoContractError("frame manifest Project/frames are incompatible")
        checked_fps = _text(fps, "fps")
        try:
            rate = Fraction(checked_fps)
        except (ValueError, ZeroDivisionError) as exc:
            raise VideoContractError("frame manifest fps is not rational") from exc
        if rate <= 0:
            raise VideoContractError("frame manifest fps must be positive")
        first_index = values[0].frame_index
        if tuple(frame.frame_index for frame in values) != tuple(range(first_index, first_index + len(values))):
            raise VideoContractError("frame manifest is not ordered or has missing frames")
        first_clip = values[0].clip
        if any(frame.clip != first_clip for frame in values):
            raise VideoContractError("frame manifest clip/source order is inconsistent")
        timestamps = tuple(frame.timestamp for frame in values)
        if len(set(timestamps)) != len(timestamps):
            raise VideoContractError("frame manifest contains duplicate timestamps")
        first_timestamp = timestamps[0]
        for offset, timestamp in enumerate(timestamps):
            expected = first_timestamp + float(Fraction(offset, 1) / rate)
            if not math.isclose(timestamp, expected, rel_tol=0.0, abs_tol=1e-9):
                raise VideoContractError("frame manifest timestamp cadence differs from fps")
        artifact_refs = tuple(frame.frame.artifact_ref for frame in values)
        if len(set(artifact_refs)) != len(artifact_refs):
            raise VideoContractError("frame manifest contains duplicate Artifact identity")
        content_refs = tuple(frame.frame.content_ref for frame in values)
        content_sha256 = tuple(frame.frame.content_sha256 for frame in values)
        if len(set(content_refs)) != len(content_refs) or len(set(content_sha256)) != len(content_sha256):
            raise VideoContractError("frame manifest contains duplicate Content identity")
        return {"project_ref": project_ref.value, "sequence_ref": _ref(sequence_ref, "sequence_ref"), "version": _text(version, "sequence version"), "fps": checked_fps, "frames": [frame.payload() for frame in values]}

    def __post_init__(self) -> None:
        if _sha(self.manifest_digest, "manifest_digest") != _digest(self._payload(self.project_ref, self.sequence_ref, self.version, self.fps, self.frames)):
            raise VideoContractError("manifest_digest does not match exact ordered frame sequence")


@dataclass(frozen=True)
class AudioTrackBinding:
    project_ref: ProjectRef
    audio: VideoArtifactContentRef
    timeline_start: float
    timeline_end: float
    stretch_policy: str
    resample_policy: str
    sync_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.audio, VideoArtifactContentRef) or self.audio.project_ref != self.project_ref:
            raise VideoContractError("audio track Project is incompatible")
        start, end = _finite(self.timeline_start, "audio timeline_start"), _finite(self.timeline_end, "audio timeline_end")
        if start < 0 or end <= start:
            raise VideoContractError("audio track range is invalid")
        _text(self.stretch_policy, "stretch_policy")
        _text(self.resample_policy, "resample_policy")
        _ref(self.sync_ref, "sync_ref")

    def payload(self) -> dict[str, object]:
        return {"audio": self.audio.payload(), "timeline_start": self.timeline_start, "timeline_end": self.timeline_end, "stretch_policy": self.stretch_policy, "resample_policy": self.resample_policy, "sync_ref": self.sync_ref}


@dataclass(frozen=True)
class SubtitleTrackBinding:
    project_ref: ProjectRef
    subtitle: VideoArtifactContentRef
    language: str
    burn_policy: str
    stream_policy: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.subtitle, VideoArtifactContentRef) or self.subtitle.project_ref != self.project_ref:
            raise VideoContractError("subtitle Project is incompatible")
        _text(self.language, "subtitle language")
        _text(self.burn_policy, "subtitle burn_policy")
        _text(self.stream_policy, "subtitle stream_policy")

    def payload(self) -> dict[str, object]:
        return {"subtitle": self.subtitle.payload(), "language": self.language, "burn_policy": self.burn_policy, "stream_policy": self.stream_policy}


@dataclass(frozen=True)
class VideoEdit:
    edit_ref: str
    clip: VideoClip
    operation: str
    parameters: Mapping[str, str]

    def __post_init__(self) -> None:
        _ref(self.edit_ref, "edit_ref")
        if not isinstance(self.clip, VideoClip):
            raise VideoContractError("edit clip is invalid")
        _text(self.operation, "edit operation")
        object.__setattr__(self, "parameters", _map(self.parameters, "edit parameters"))

    def payload(self) -> dict[str, object]:
        return {"edit_ref": self.edit_ref, "clip": self.clip.payload(), "operation": self.operation, "parameters": dict(self.parameters)}


@dataclass(frozen=True)
class VideoTransition:
    transition_ref: str
    at: float
    duration: float
    parameters: Mapping[str, str]

    def __post_init__(self) -> None:
        _ref(self.transition_ref, "transition_ref")
        if _finite(self.at, "transition at") < 0 or _finite(self.duration, "transition duration") <= 0:
            raise VideoContractError("transition range is invalid")
        object.__setattr__(self, "parameters", _map(self.parameters, "transition parameters"))

    def payload(self) -> dict[str, object]:
        return {"transition_ref": self.transition_ref, "at": self.at, "duration": self.duration, "parameters": dict(self.parameters)}


@dataclass(frozen=True)
class VideoEffect:
    effect_ref: str
    version: str
    parameters: Mapping[str, str]

    def __post_init__(self) -> None:
        _ref(self.effect_ref, "effect_ref")
        _text(self.version, "effect version")
        object.__setattr__(self, "parameters", _map(self.parameters, "effect parameters"))

    def payload(self) -> dict[str, object]:
        return {"effect_ref": self.effect_ref, "version": self.version, "parameters": dict(self.parameters)}


@dataclass(frozen=True)
class VideoTimeline:
    project_ref: ProjectRef
    timeline_ref: str
    version: str
    edits: tuple[VideoEdit, ...]
    transitions: tuple[VideoTransition, ...]
    effects: tuple[VideoEffect, ...]
    policy: Mapping[str, str]
    clips: tuple[VideoClip, ...] = ()
    image_sources: tuple[VideoArtifactContentRef, ...] = ()
    render_sequences: tuple[VideoFrameSequenceManifest, ...] = ()
    audio_tracks: tuple[AudioTrackBinding, ...] = ()
    subtitle_tracks: tuple[SubtitleTrackBinding, ...] = ()
    track_order: tuple[str, ...] = ()
    timebase: str = ""
    output_contract: Mapping[str, str] = field(default_factory=dict)
    timeline_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise VideoContractError("timeline Project is invalid")
        _ref(self.timeline_ref, "timeline_ref")
        _text(self.version, "timeline version")
        edits, transitions, effects = tuple(self.edits), tuple(self.transitions), tuple(self.effects)
        clips = tuple(self.clips)
        images = tuple(self.image_sources)
        sequences = tuple(self.render_sequences)
        audio = tuple(self.audio_tracks)
        subtitles = tuple(self.subtitle_tracks)
        if not all(isinstance(item, VideoEdit) and item.clip.project_ref == self.project_ref for item in edits) or not all(isinstance(item, VideoTransition) for item in transitions) or not all(isinstance(item, VideoEffect) for item in effects):
            raise VideoContractError("timeline entries are incompatible")
        if not all(isinstance(item, VideoClip) and item.project_ref == self.project_ref for item in clips) or not all(isinstance(item, VideoArtifactContentRef) and item.project_ref == self.project_ref for item in images) or not all(isinstance(item, VideoFrameSequenceManifest) and item.project_ref == self.project_ref for item in sequences) or not all(isinstance(item, AudioTrackBinding) and item.project_ref == self.project_ref for item in audio) or not all(isinstance(item, SubtitleTrackBinding) and item.project_ref == self.project_ref for item in subtitles):
            raise VideoContractError("timeline media dependency crossed Project scope")
        if tuple(clip.timeline_start for clip in clips) != tuple(sorted(clip.timeline_start for clip in clips)) or len({clip.source.artifact_ref for clip in clips}) != len(clips):
            raise VideoContractError("timeline clips are duplicated or unordered")
        for refs, label in (
            (tuple(item.edit_ref for item in edits), "edit"),
            (tuple(item.transition_ref for item in transitions), "transition"),
            (tuple(item.effect_ref for item in effects), "effect"),
        ):
            if len(refs) != len(set(refs)):
                raise VideoContractError(f"timeline contains duplicate {label} references")
        if edits and tuple(item.clip for item in edits) != clips:
            raise VideoContractError("timeline edit clips do not exactly bind declared clips in order")
        expected_track_order = tuple(f"audio:{index}" for index in range(len(audio))) + tuple(f"subtitle:{index}" for index in range(len(subtitles)))
        if tuple(self.track_order) != expected_track_order:
            raise VideoContractError("timeline track order is missing or inconsistent")
        if clips:
            checked_timebase = _text(self.timebase, "timeline timebase")
            if any(clip.timebase != checked_timebase for clip in clips):
                raise VideoContractError("timeline clip timebases are inconsistent")
        elif self.timebase:
            _text(self.timebase, "timeline timebase")
        object.__setattr__(self, "edits", edits)
        object.__setattr__(self, "transitions", transitions)
        object.__setattr__(self, "effects", effects)
        object.__setattr__(self, "clips", clips)
        object.__setattr__(self, "image_sources", images)
        object.__setattr__(self, "render_sequences", sequences)
        object.__setattr__(self, "audio_tracks", audio)
        object.__setattr__(self, "subtitle_tracks", subtitles)
        object.__setattr__(self, "track_order", expected_track_order)
        object.__setattr__(self, "policy", _map(self.policy, "timeline policy"))
        object.__setattr__(self, "output_contract", _map(self.output_contract, "timeline output_contract"))
        object.__setattr__(self, "timeline_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"project_ref": self.project_ref.value, "timeline_ref": self.timeline_ref, "version": self.version, "edits": [item.payload() for item in self.edits], "transitions": [item.payload() for item in self.transitions], "effects": [item.payload() for item in self.effects], "clips": [item.payload() for item in self.clips], "image_sources": [item.payload() for item in self.image_sources], "render_sequences": [item.manifest_digest for item in self.render_sequences], "audio_tracks": [item.payload() for item in self.audio_tracks], "subtitle_tracks": [item.payload() for item in self.subtitle_tracks], "track_order": list(self.track_order), "timebase": self.timebase, "policy": dict(self.policy), "output_contract": dict(self.output_contract)}


@dataclass(frozen=True)
class VideoSpecification:
    project_ref: ProjectRef
    video_id: str
    operation: str
    sources: tuple[VideoArtifactContentRef, ...]
    image_sources: tuple[VideoArtifactContentRef, ...]
    render_sequences: tuple[VideoFrameSequenceManifest, ...]
    audio_tracks: tuple[AudioTrackBinding, ...]
    subtitle_tracks: tuple[SubtitleTrackBinding, ...]
    timeline: VideoTimeline
    time_start: float | None
    time_end: float | None
    duration: float | None
    timebase: str | None
    fps_policy: str
    target_fps: str | None
    width: int | None
    height: int | None
    pixel_format: str | None
    color_ref: str | None
    hdr_ref: str | None
    media_type: str | None
    container: str | None
    codec: str | None
    profile: str | None
    bitrate: str | None
    quality_ref: str | None
    missing_frame_policy: str
    audio_policy: Mapping[str, str]
    subtitle_policy: Mapping[str, str]
    output_contract: Mapping[str, str]
    tool_ref: str
    runtime_ref: str
    model_ref: str | None
    seed: int
    config: Mapping[str, str]
    validator_ref: str
    prompt: VideoArtifactContentRef | None
    canonical_digest: str

    @classmethod
    def create(cls, project_ref: ProjectRef, video_id: str, operation: str, sources: Sequence[VideoArtifactContentRef], image_sources: Sequence[VideoArtifactContentRef], render_sequences: Sequence[VideoFrameSequenceManifest], audio_tracks: Sequence[AudioTrackBinding], subtitle_tracks: Sequence[SubtitleTrackBinding], timeline: VideoTimeline, time_start: float | None, time_end: float | None, duration: float | None, timebase: str | None, fps_policy: str, target_fps: str | None, width: int | None, height: int | None, pixel_format: str | None, color_ref: str | None, hdr_ref: str | None, media_type: str | None, container: str | None, codec: str | None, profile: str | None, bitrate: str | None, quality_ref: str | None, missing_frame_policy: str, audio_policy: Mapping[str, str], subtitle_policy: Mapping[str, str], output_contract: Mapping[str, str], tool_ref: str, runtime_ref: str, model_ref: str | None, seed: int, config: Mapping[str, str], validator_ref: str, *, prompt: VideoArtifactContentRef | None = None) -> "VideoSpecification":
        payload = cls._payload(project_ref, video_id, operation, sources, image_sources, render_sequences, audio_tracks, subtitle_tracks, timeline, time_start, time_end, duration, timebase, fps_policy, target_fps, width, height, pixel_format, color_ref, hdr_ref, media_type, container, codec, profile, bitrate, quality_ref, missing_frame_policy, audio_policy, subtitle_policy, output_contract, tool_ref, runtime_ref, model_ref, seed, config, validator_ref, prompt)
        return cls(project_ref, video_id, operation, tuple(sources), tuple(image_sources), tuple(render_sequences), tuple(audio_tracks), tuple(subtitle_tracks), timeline, time_start, time_end, duration, timebase, fps_policy, target_fps, width, height, pixel_format, color_ref, hdr_ref, media_type, container, codec, profile, bitrate, quality_ref, missing_frame_policy, audio_policy, subtitle_policy, output_contract, tool_ref, runtime_ref, model_ref, seed, config, validator_ref, prompt, _digest(payload))

    @staticmethod
    def _payload(project_ref: ProjectRef, video_id: str, operation: str, sources: Sequence[VideoArtifactContentRef], image_sources: Sequence[VideoArtifactContentRef], render_sequences: Sequence[VideoFrameSequenceManifest], audio_tracks: Sequence[AudioTrackBinding], subtitle_tracks: Sequence[SubtitleTrackBinding], timeline: VideoTimeline, time_start: float | None, time_end: float | None, duration: float | None, timebase: str | None, fps_policy: str, target_fps: str | None, width: int | None, height: int | None, pixel_format: str | None, color_ref: str | None, hdr_ref: str | None, media_type: str | None, container: str | None, codec: str | None, profile: str | None, bitrate: str | None, quality_ref: str | None, missing_frame_policy: str, audio_policy: Mapping[str, str], subtitle_policy: Mapping[str, str], output_contract: Mapping[str, str], tool_ref: str, runtime_ref: str, model_ref: str | None, seed: int, config: Mapping[str, str], validator_ref: str, prompt: VideoArtifactContentRef | None) -> dict[str, object]:
        if not isinstance(project_ref, ProjectRef) or not isinstance(video_id, str) or not video_id or operation not in VIDEO_CAPABILITIES:
            raise VideoContractError("video Project/operation identity is invalid")
        all_artifacts = (*tuple(sources), *tuple(image_sources))
        if not all(isinstance(item, VideoArtifactContentRef) and item.project_ref == project_ref for item in all_artifacts):
            raise VideoContractError("video source/image Artifact crossed Project scope")
        sequences, audio, subtitles = tuple(render_sequences), tuple(audio_tracks), tuple(subtitle_tracks)
        if not all_artifacts and not sequences:
            raise VideoContractError("video requires exact source/image or render sequence input")
        if not all(isinstance(item, VideoFrameSequenceManifest) and item.project_ref == project_ref for item in sequences) or not all(isinstance(item, AudioTrackBinding) and item.project_ref == project_ref for item in audio) or not all(isinstance(item, SubtitleTrackBinding) and item.project_ref == project_ref for item in subtitles) or not isinstance(timeline, VideoTimeline) or timeline.project_ref != project_ref:
            raise VideoContractError("video dependency crossed Project scope")
        if tuple(clip.source for clip in timeline.clips) != tuple(sources) or timeline.image_sources != tuple(image_sources) or timeline.render_sequences != sequences or timeline.audio_tracks != audio or timeline.subtitle_tracks != subtitles or timeline.output_contract != _map(output_contract, "output_contract"):
            raise VideoContractError("timeline does not bind exact video dependencies/output contract")
        generative = operation in _GENERATIVE
        if time_start is None and time_end is None and duration is None and generative:
            start = end = measured_duration = None
        elif time_start is None or time_end is None or duration is None:
            raise VideoContractError("time range must be explicit or entirely unknown for generation")
        else:
            start, end, measured_duration = _finite(time_start, "time_start"), _finite(time_end, "time_end"), _finite(duration, "duration")
            if start < 0 or end <= start or measured_duration <= 0 or not math.isclose(end - start, measured_duration, rel_tol=0.0, abs_tol=1e-9):
                raise VideoContractError("time range/duration is invalid")
        if fps_policy not in {"preserve", "conform"} or (fps_policy == "conform" and target_fps is None) or (fps_policy == "preserve" and target_fps is not None):
            raise VideoContractError("fps preserve/conform policy is invalid")
        if not generative and (None in (timebase, width, height, pixel_format, color_ref, media_type, container, codec, profile, bitrate, quality_ref)):
            raise VideoContractError("deterministic video fields must be explicit")
        if width is not None:
            _positive(width, "width")
        if height is not None:
            _positive(height, "height")
        for value, field in ((timebase, "timebase"), (target_fps, "target_fps"), (pixel_format, "pixel_format"), (color_ref, "color_ref"), (hdr_ref, "hdr_ref"), (media_type, "media_type"), (container, "container"), (codec, "codec"), (profile, "profile"), (bitrate, "bitrate"), (quality_ref, "quality_ref"), (model_ref, "model_ref")):
            if value is not None:
                (_ref(value, field) if field.endswith("ref") else _text(value, field))
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise VideoContractError("seed is invalid")
        if prompt is not None and (not isinstance(prompt, VideoArtifactContentRef) or prompt.project_ref != project_ref):
            raise VideoContractError("video prompt crossed Project scope")
        return {"project_ref": project_ref.value, "video_id": video_id, "operation": operation, "sources": [item.payload() for item in sources], "image_sources": [item.payload() for item in image_sources], "render_sequences": [item.manifest_digest for item in sequences], "audio_tracks": [item.payload() for item in audio], "subtitle_tracks": [item.payload() for item in subtitles], "timeline": timeline.payload(), "time_start": start, "time_end": end, "duration": measured_duration, "timebase": timebase, "fps_policy": fps_policy, "target_fps": target_fps, "width": width, "height": height, "pixel_format": pixel_format, "color_ref": color_ref, "hdr_ref": hdr_ref, "media_type": media_type, "container": container, "codec": codec, "profile": profile, "bitrate": bitrate, "quality_ref": quality_ref, "missing_frame_policy": _text(missing_frame_policy, "missing_frame_policy"), "audio_policy": dict(_map(audio_policy, "audio_policy")), "subtitle_policy": dict(_map(subtitle_policy, "subtitle_policy")), "output_contract": dict(_map(output_contract, "output_contract")), "tool_ref": _ref(tool_ref, "tool_ref"), "runtime_ref": _ref(runtime_ref, "runtime_ref"), "model_ref": model_ref, "seed": seed, "config": dict(_map(config, "config")), "validator_ref": _ref(validator_ref, "validator_ref"), "prompt": None if prompt is None else prompt.payload()}

    def __post_init__(self) -> None:
        payload = self._payload(self.project_ref, self.video_id, self.operation, self.sources, self.image_sources, self.render_sequences, self.audio_tracks, self.subtitle_tracks, self.timeline, self.time_start, self.time_end, self.duration, self.timebase, self.fps_policy, self.target_fps, self.width, self.height, self.pixel_format, self.color_ref, self.hdr_ref, self.media_type, self.container, self.codec, self.profile, self.bitrate, self.quality_ref, self.missing_frame_policy, self.audio_policy, self.subtitle_policy, self.output_contract, self.tool_ref, self.runtime_ref, self.model_ref, self.seed, self.config, self.validator_ref, self.prompt)
        if _sha(self.canonical_digest, "canonical_digest") != _digest(payload):
            raise VideoContractError("canonical_digest does not match exact video specification")
        for field in ("audio_policy", "subtitle_policy", "output_contract", "config"):
            object.__setattr__(self, field, _map(getattr(self, field), field))


@dataclass(frozen=True)
class VideoInspectionRef:
    project_ref: ProjectRef
    source: VideoArtifactContentRef
    duration: float
    fps: str
    width: int
    height: int
    codec: str
    inspection_ref: str
    inspection_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.source, VideoArtifactContentRef) or self.source.project_ref != self.project_ref:
            raise VideoContractError("inspection Project/source is incompatible")
        if _finite(self.duration, "inspection duration") <= 0:
            raise VideoContractError("inspection duration is invalid")
        _text(self.fps, "inspection fps"); _positive(self.width, "inspection width"); _positive(self.height, "inspection height"); _text(self.codec, "inspection codec"); _ref(self.inspection_ref, "inspection_ref"); _sha(self.inspection_sha256, "inspection_sha256")


@dataclass(frozen=True)
class VideoOutputRef:
    project_ref: ProjectRef
    specification_digest: str
    output: VideoArtifactContentRef
    duration: float
    fps: str
    width: int
    height: int
    codec: str
    container: str
    producer_attempt_id: str
    producer_fence: int
    derivation: str
    output_digest: str

    @classmethod
    def create(cls, project_ref: ProjectRef, specification: VideoSpecification, output: VideoArtifactContentRef, duration: float, fps: str, width: int, height: int, codec: str, container: str, producer_attempt_id: str, producer_fence: int, derivation: str) -> "VideoOutputRef":
        if not isinstance(project_ref, ProjectRef) or not isinstance(specification, VideoSpecification) or specification.project_ref != project_ref or not isinstance(output, VideoArtifactContentRef) or output.project_ref != project_ref:
            raise VideoContractError("output Project/specification is incompatible")
        actual_duration = _finite(duration, "output duration")
        if actual_duration <= 0:
            raise VideoContractError("output duration is invalid")
        actual_fps, actual_codec, actual_container = _text(fps, "output fps"), _text(codec, "output codec"), _text(container, "output container")
        if (specification.codec is not None and specification.codec != actual_codec) or (specification.container is not None and specification.container != actual_container):
            raise VideoContractError("output codec/container contradicts specification")
        attempt, fence = _attempt(producer_attempt_id, producer_fence)
        checked_derivation = _text(derivation, "derivation")
        payload = {"project_ref": project_ref.value, "specification_digest": specification.canonical_digest, "output": output.payload(), "duration": actual_duration, "fps": actual_fps, "width": _positive(width, "output width"), "height": _positive(height, "output height"), "codec": actual_codec, "container": actual_container, "producer_attempt_id": attempt, "producer_fence": fence, "derivation": checked_derivation}
        return cls(project_ref, specification.canonical_digest, output, actual_duration, actual_fps, width, height, actual_codec, actual_container, attempt, fence, checked_derivation, _digest(payload))

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.output, VideoArtifactContentRef) or self.output.project_ref != self.project_ref:
            raise VideoContractError("output Project is incompatible")
        attempt, fence = _attempt(self.producer_attempt_id, self.producer_fence)
        payload = {"project_ref": self.project_ref.value, "specification_digest": _sha(self.specification_digest, "specification_digest"), "output": self.output.payload(), "duration": _finite(self.duration, "output duration"), "fps": _text(self.fps, "output fps"), "width": _positive(self.width, "output width"), "height": _positive(self.height, "output height"), "codec": _text(self.codec, "output codec"), "container": _text(self.container, "output container"), "producer_attempt_id": attempt, "producer_fence": fence, "derivation": _text(self.derivation, "derivation")}
        if _sha(self.output_digest, "output_digest") != _digest(payload):
            raise VideoContractError("output_digest does not match exact output")


@dataclass(frozen=True)
class EditableVideoSessionBinding:
    project_ref: ProjectRef
    timeline: VideoTimeline
    session: VideoArtifactContentRef
    tool_ref: str
    tool_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.timeline, VideoTimeline) or not isinstance(self.session, VideoArtifactContentRef) or self.timeline.project_ref != self.project_ref or self.session.project_ref != self.project_ref:
            raise VideoContractError("session Project/timeline is incompatible")
        _ref(self.tool_ref, "tool_ref"); _text(self.tool_version, "tool_version")


@dataclass(frozen=True)
class GameVideoHandoffBinding:
    project_ref: ProjectRef
    output: VideoOutputRef
    target: VideoArtifactContentRef
    integration_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.output, VideoOutputRef) or not isinstance(self.target, VideoArtifactContentRef) or self.output.project_ref != self.project_ref or self.target.project_ref != self.project_ref:
            raise VideoContractError("game handoff Project is incompatible")
        _ref(self.integration_ref, "integration_ref")


class VideoToolAdapter(Protocol):
    project_ref: ProjectRef
    tool_ref: str
    runtime_ref: str
    determinism: str

    def inspect(self, source: VideoArtifactContentRef, validator_ref: str) -> VideoInspectionRef: ...
    def execute(self, access: "ProjectAccess", attempt: "NodeExecutionAttempt", specification: VideoSpecification) -> VideoOutputRef: ...


class VideoModelAdapter(Protocol):
    project_ref: ProjectRef
    model_ref: str
    runtime_ref: str
    determinism: str

    def generate(self, access: "ProjectAccess", attempt: "NodeExecutionAttempt", specification: VideoSpecification) -> VideoOutputRef: ...


def video_production_pack() -> ProductionPack:
    capabilities = tuple(Capability(CapabilityRef(f"video.{name}", "1.0.0"), f"Bounded video {name}", {}, {"result": f"minitz://contracts/video-{name}/v1"}, (), "2026-09-01T00:00:00+00:00") for name in VIDEO_CAPABILITIES)
    refs = {item.name: item.capability_ref for item in capabilities}
    steps = tuple(GraphRecipeStepRegistration(name, refs[name], () if index == 0 else (VIDEO_CAPABILITIES[index - 1],)) for index, name in enumerate(VIDEO_CAPABILITIES))
    return ProductionPack(ProductionPackRef("video", "1.0.0"), capabilities, (GraphRecipeRegistration("pack-recipe://video/production@1.0.0", steps),), tuple(ValidatorRegistration(f"pack-validator://video/{name}@1.0.0", refs[name], f"validation-check://artifact-role/{VIDEO_ARTIFACT_ROLES[index % len(VIDEO_ARTIFACT_ROLES)]}/v1") for index, name in enumerate(VIDEO_CAPABILITIES)), VIDEO_ARTIFACT_ROLES, {item.capability_ref.value: ("adapter://video/provider-neutral/v1",) for item in capabilities}, {item.capability_ref.value: "resource-profile://video/project-configured/v1" for item in capabilities}, "2026-09-01T00:00:00+00:00")
