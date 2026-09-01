"""Provider-neutral, fail-closed audio production contracts."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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


AUDIO_CAPABILITIES = ("inspect", "import", "generate", "edit", "trim", "segment", "resample", "clean", "filter", "normalize", "mix", "master", "convert", "analyze", "spatial_prepare", "preview", "export", "validate")
AUDIO_OPTIONAL_CAPABILITIES = ("speech", "transcribe", "stem_separation")
AUDIO_ARTIFACT_ROLES = ("audio.source", "audio.clip", "audio.stem", "audio.generated", "audio.cleaned", "audio.mix", "audio.master", "audio.preview", "audio.export", "audio.analysis", "audio.validation-evidence", "audio.prompt", "audio.session", "audio.transcript")
_GENERATIVE_OPERATIONS = {"generate", "speech"}
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA = re.compile(r"[0-9a-f]{64}")
_ATTEMPT = re.compile(r"natt_[0-9a-f]{32}")


class AudioContractError(ValueError):
    pass


def _ref(value: object, field: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise AudioContractError(f"{field} is invalid")
    return value


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise AudioContractError(f"{field} is invalid")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise AudioContractError(f"{field} is invalid")
    return value


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise AudioContractError(f"{field} is not finite")
    return float(value)


def _map(value: object, field: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise AudioContractError(f"{field} is invalid")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, str) or not item:
            raise AudioContractError(f"{field} is invalid")
        if item.lower() in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
            raise AudioContractError(f"{field} is not finite")
        result[key] = item
    return MappingProxyType(dict(sorted(result.items())))


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _attempt(value: object, fence: object) -> tuple[str, int]:
    if not isinstance(value, str) or _ATTEMPT.fullmatch(value) is None or not isinstance(fence, int) or isinstance(fence, bool) or fence < 1:
        raise AudioContractError("producer attempt/fence is invalid")
    return value, fence


@dataclass(frozen=True)
class AudioArtifactContentRef:
    project_ref: ProjectRef
    artifact_ref: str
    content_ref: str
    content_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise AudioContractError("Artifact project is invalid")
        _ref(self.artifact_ref, "artifact_ref")
        _ref(self.content_ref, "content_ref")
        _sha(self.content_sha256, "content_sha256")

    def payload(self) -> dict[str, str]:
        return {"artifact_ref": self.artifact_ref, "content_ref": self.content_ref, "content_sha256": self.content_sha256}


@dataclass(frozen=True)
class ProcessingChain:
    chain_ref: str
    chain_sha256: str
    version: str
    effects: tuple[str, ...]
    config: Mapping[str, str]

    def __post_init__(self) -> None:
        _ref(self.chain_ref, "chain_ref")
        _sha(self.chain_sha256, "chain_sha256")
        _text(self.version, "chain version")
        effects = tuple(self.effects)
        if not effects or len(set(effects)) != len(effects):
            raise AudioContractError("processing effects are invalid")
        object.__setattr__(self, "effects", tuple(_ref(item, "effect_ref") for item in effects))
        object.__setattr__(self, "config", _map(self.config, "processing config"))

    def payload(self) -> dict[str, object]:
        return {"chain_ref": self.chain_ref, "chain_sha256": self.chain_sha256, "version": self.version, "effects": list(self.effects), "config": dict(self.config)}


def _layout_pair(source: Sequence[str] | None, target: Sequence[str] | None, *, allow_unknown: bool) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
    if source is None and target is None:
        if allow_unknown:
            return None, None
        raise AudioContractError("channel layouts must be explicit for source processing")
    if source is None or target is None:
        raise AudioContractError("channel layouts must be explicit as a source/target pair")
    source_value, target_value = tuple(source), tuple(target)
    if not source_value or not target_value or not all(isinstance(item, str) and item for item in (*source_value, *target_value)):
        raise AudioContractError("channel layouts are invalid")
    return source_value, target_value


def _rate_pair(source: int | None, target: int | None, *, allow_unknown: bool) -> tuple[int | None, int | None]:
    if source is None and target is None:
        if allow_unknown:
            return None, None
        raise AudioContractError("sample rates must be explicit for source processing")
    if source is None or target is None:
        raise AudioContractError("sample rates must be explicit as a source/target pair")
    if not isinstance(source, int) or isinstance(source, bool) or source < 1 or not isinstance(target, int) or isinstance(target, bool) or target < 1:
        raise AudioContractError("sample rates are invalid")
    return source, target


@dataclass(frozen=True)
class AudioSpecification:
    project_ref: ProjectRef
    audio_id: str
    sources: tuple[AudioArtifactContentRef, ...]
    operation: str
    recipe_ref: str
    recipe_sha256: str
    time_start: float | None
    time_end: float | None
    duration: float | None
    source_sample_rate: int | None
    target_sample_rate: int | None
    source_channel_layout: tuple[str, ...] | None
    target_channel_layout: tuple[str, ...] | None
    media_type: str
    container: str
    codec: str | None
    sample_format: str | None
    bit_depth: int | None
    processing_chain: ProcessingChain
    tool_config: Mapping[str, str]
    loudness_policy: Mapping[str, str]
    measurement_algorithm_ref: str
    spatial_metadata: Mapping[str, str]
    model_ref: str
    model_version: str
    runtime_ref: str
    seed: int
    voice_ref: str | None
    language: str | None
    prompt: AudioArtifactContentRef | None
    validator_ref: str
    output_contract: Mapping[str, str]
    canonical_digest: str

    @classmethod
    def create(cls, project_ref: ProjectRef, audio_id: str, sources: Sequence[AudioArtifactContentRef], operation: str, recipe_ref: str, recipe_sha256: str, time_start: float | None, time_end: float | None, duration: float | None, source_sample_rate: int | None, target_sample_rate: int | None, source_channel_layout: Sequence[str] | None, target_channel_layout: Sequence[str] | None, media_type: str, container: str, codec: str | None, sample_format: str | None, bit_depth: int | None, processing_chain: ProcessingChain, tool_config: Mapping[str, str], loudness_policy: Mapping[str, str], measurement_algorithm_ref: str, spatial_metadata: Mapping[str, str], model_ref: str, model_version: str, runtime_ref: str, seed: int, voice_ref: str | None, language: str | None, prompt: AudioArtifactContentRef | None, validator_ref: str, output_contract: Mapping[str, str]) -> "AudioSpecification":
        payload = cls._payload(project_ref, audio_id, sources, operation, recipe_ref, recipe_sha256, time_start, time_end, duration, source_sample_rate, target_sample_rate, source_channel_layout, target_channel_layout, media_type, container, codec, sample_format, bit_depth, processing_chain, tool_config, loudness_policy, measurement_algorithm_ref, spatial_metadata, model_ref, model_version, runtime_ref, seed, voice_ref, language, prompt, validator_ref, output_contract)
        rates = _rate_pair(source_sample_rate, target_sample_rate, allow_unknown=operation in _GENERATIVE_OPERATIONS)
        layouts = _layout_pair(source_channel_layout, target_channel_layout, allow_unknown=operation in _GENERATIVE_OPERATIONS)
        return cls(project_ref, audio_id, tuple(sources), operation, recipe_ref, recipe_sha256, time_start, time_end, duration, rates[0], rates[1], layouts[0], layouts[1], media_type, container, codec, sample_format, bit_depth, processing_chain, tool_config, loudness_policy, measurement_algorithm_ref, spatial_metadata, model_ref, model_version, runtime_ref, seed, voice_ref, language, prompt, validator_ref, output_contract, _digest(payload))

    @staticmethod
    def _payload(project_ref: ProjectRef, audio_id: str, sources: Sequence[AudioArtifactContentRef], operation: str, recipe_ref: str, recipe_sha256: str, time_start: float | None, time_end: float | None, duration: float | None, source_sample_rate: int | None, target_sample_rate: int | None, source_channel_layout: Sequence[str] | None, target_channel_layout: Sequence[str] | None, media_type: str, container: str, codec: str | None, sample_format: str | None, bit_depth: int | None, processing_chain: ProcessingChain, tool_config: Mapping[str, str], loudness_policy: Mapping[str, str], measurement_algorithm_ref: str, spatial_metadata: Mapping[str, str], model_ref: str, model_version: str, runtime_ref: str, seed: int, voice_ref: str | None, language: str | None, prompt: AudioArtifactContentRef | None, validator_ref: str, output_contract: Mapping[str, str]) -> dict[str, object]:
        if not isinstance(project_ref, ProjectRef) or not isinstance(audio_id, str) or not audio_id:
            raise AudioContractError("project/audio identity is invalid")
        source_values = tuple(sources)
        if not source_values or not all(isinstance(item, AudioArtifactContentRef) and item.project_ref == project_ref for item in source_values):
            raise AudioContractError("source Artifact crossed Project scope")
        if operation not in AUDIO_CAPABILITIES + AUDIO_OPTIONAL_CAPABILITIES:
            raise AudioContractError("audio operation is invalid")
        if not isinstance(processing_chain, ProcessingChain):
            raise AudioContractError("processing chain is invalid")
        generative = operation in _GENERATIVE_OPERATIONS
        if time_start is None and time_end is None and duration is None and generative:
            start = end = measured_duration = None
        elif time_start is None or time_end is None or duration is None:
            raise AudioContractError("time range/duration must be explicit or entirely unknown for generative audio")
        else:
            start, end, measured_duration = _finite(time_start, "time_start"), _finite(time_end, "time_end"), _finite(duration, "duration")
            if start < 0 or end <= start or measured_duration <= 0 or not math.isclose(end - start, measured_duration, rel_tol=0.0, abs_tol=1e-9):
                raise AudioContractError("time range/duration is invalid")
        rates, layouts = _rate_pair(source_sample_rate, target_sample_rate, allow_unknown=generative), _layout_pair(source_channel_layout, target_channel_layout, allow_unknown=generative)
        if (codec is None or sample_format is None or bit_depth is None) and not generative:
            raise AudioContractError("codec, sample format, and bit depth must be explicit for source processing")
        if codec is not None:
            _text(codec, "codec")
        if sample_format is not None:
            _text(sample_format, "sample_format")
        if bit_depth is not None and (not isinstance(bit_depth, int) or isinstance(bit_depth, bool) or bit_depth < 1):
            raise AudioContractError("bit depth is invalid")
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise AudioContractError("bit depth or seed is invalid")
        if prompt is not None and (not isinstance(prompt, AudioArtifactContentRef) or prompt.project_ref != project_ref):
            raise AudioContractError("prompt Artifact crossed Project scope")
        if operation in _GENERATIVE_OPERATIONS and prompt is None:
            raise AudioContractError("generative audio requires prompt Artifact and Content")
        if (voice_ref is None) != (language is None):
            raise AudioContractError("voice/language must be explicit together")
        contract = _map(output_contract, "output_contract")
        requested_codec = contract.get("codec")
        if requested_codec is not None and codec != requested_codec:
            raise AudioContractError("output_contract codec contradicts first-class codec")
        return {"project_ref": project_ref.value, "audio_id": audio_id, "sources": [item.payload() for item in source_values], "operation": operation, "recipe_ref": _ref(recipe_ref, "recipe_ref"), "recipe_sha256": _sha(recipe_sha256, "recipe_sha256"), "time_start": start, "time_end": end, "duration": measured_duration, "source_sample_rate": rates[0], "target_sample_rate": rates[1], "source_channel_layout": layouts[0], "target_channel_layout": layouts[1], "media_type": _text(media_type, "media_type"), "container": _text(container, "container"), "codec": codec, "sample_format": sample_format, "bit_depth": bit_depth, "processing_chain": processing_chain.payload(), "tool_config": dict(_map(tool_config, "tool_config")), "loudness_policy": dict(_map(loudness_policy, "loudness_policy")), "measurement_algorithm_ref": _ref(measurement_algorithm_ref, "measurement_algorithm_ref"), "spatial_metadata": dict(_map(spatial_metadata, "spatial_metadata")), "model_ref": _ref(model_ref, "model_ref"), "model_version": _text(model_version, "model_version"), "runtime_ref": _ref(runtime_ref, "runtime_ref"), "seed": seed, "voice_ref": None if voice_ref is None else _ref(voice_ref, "voice_ref"), "language": language, "prompt": None if prompt is None else prompt.payload(), "validator_ref": _ref(validator_ref, "validator_ref"), "output_contract": dict(contract)}

    def __post_init__(self) -> None:
        payload = self._payload(self.project_ref, self.audio_id, self.sources, self.operation, self.recipe_ref, self.recipe_sha256, self.time_start, self.time_end, self.duration, self.source_sample_rate, self.target_sample_rate, self.source_channel_layout, self.target_channel_layout, self.media_type, self.container, self.codec, self.sample_format, self.bit_depth, self.processing_chain, self.tool_config, self.loudness_policy, self.measurement_algorithm_ref, self.spatial_metadata, self.model_ref, self.model_version, self.runtime_ref, self.seed, self.voice_ref, self.language, self.prompt, self.validator_ref, self.output_contract)
        if _sha(self.canonical_digest, "canonical_digest") != _digest(payload):
            raise AudioContractError("canonical_digest does not match exact audio specification")
        for field in ("tool_config", "loudness_policy", "spatial_metadata", "output_contract"):
            object.__setattr__(self, field, _map(getattr(self, field), field))


@dataclass(frozen=True)
class AudioInspectionRef:
    project_ref: ProjectRef
    source: AudioArtifactContentRef
    duration: float
    sample_rate: int
    channel_layout: tuple[str, ...]
    codec: str
    analysis_ref: str
    analysis_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.source, AudioArtifactContentRef) or self.source.project_ref != self.project_ref:
            raise AudioContractError("inspection Project/source is incompatible")
        if _finite(self.duration, "inspection duration") <= 0:
            raise AudioContractError("inspection duration is invalid")
        _rate_pair(self.sample_rate, self.sample_rate, allow_unknown=False)
        _layout_pair(self.channel_layout, self.channel_layout, allow_unknown=False)
        _text(self.codec, "inspection codec")
        _ref(self.analysis_ref, "analysis_ref")
        _sha(self.analysis_sha256, "analysis_sha256")


@dataclass(frozen=True)
class AudioOutputRef:
    project_ref: ProjectRef
    specification_digest: str
    output: AudioArtifactContentRef
    duration: float
    sample_rate: int
    channel_layout: tuple[str, ...]
    codec: str
    sample_format: str
    bit_depth: int
    producer_attempt_id: str
    producer_fence: int
    derivation: str
    output_digest: str

    @classmethod
    def create(cls, project_ref: ProjectRef, specification: AudioSpecification, output: AudioArtifactContentRef, duration: float, sample_rate: int, channel_layout: Sequence[str], codec: str, sample_format: str, bit_depth: int, producer_attempt_id: str, producer_fence: int, derivation: str) -> "AudioOutputRef":
        if not isinstance(project_ref, ProjectRef) or not isinstance(specification, AudioSpecification) or specification.project_ref != project_ref or not isinstance(output, AudioArtifactContentRef) or output.project_ref != project_ref:
            raise AudioContractError("output Project/specification is incompatible")
        attempt, fence = _attempt(producer_attempt_id, producer_fence)
        checked = _text(derivation, "derivation")
        actual_duration = _finite(duration, "output duration")
        if actual_duration <= 0:
            raise AudioContractError("output duration is invalid")
        actual_rate, _ = _rate_pair(sample_rate, sample_rate, allow_unknown=False)
        actual_layout, _ = _layout_pair(channel_layout, channel_layout, allow_unknown=False)
        if actual_rate is None or actual_layout is None:
            raise AudioContractError("output decoded values are unknown")
        actual_codec = _text(codec, "output codec")
        if specification.codec is not None and specification.codec != actual_codec:
            raise AudioContractError("output codec contradicts first-class specification")
        actual_format = _text(sample_format, "output sample_format")
        if not isinstance(bit_depth, int) or isinstance(bit_depth, bool) or bit_depth < 1:
            raise AudioContractError("output bit_depth is invalid")
        payload = {"project_ref": project_ref.value, "specification_digest": specification.canonical_digest, "output": output.payload(), "duration": actual_duration, "sample_rate": actual_rate, "channel_layout": actual_layout, "codec": actual_codec, "sample_format": actual_format, "bit_depth": bit_depth, "producer_attempt_id": attempt, "producer_fence": fence, "derivation": checked}
        return cls(project_ref, specification.canonical_digest, output, actual_duration, actual_rate, actual_layout, actual_codec, actual_format, bit_depth, attempt, fence, checked, _digest(payload))

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.output, AudioArtifactContentRef) or self.output.project_ref != self.project_ref:
            raise AudioContractError("output Project is incompatible")
        attempt, fence = _attempt(self.producer_attempt_id, self.producer_fence)
        actual_duration = _finite(self.duration, "output duration")
        actual_rate, _ = _rate_pair(self.sample_rate, self.sample_rate, allow_unknown=False)
        actual_layout, _ = _layout_pair(self.channel_layout, self.channel_layout, allow_unknown=False)
        if actual_duration <= 0 or not isinstance(self.bit_depth, int) or isinstance(self.bit_depth, bool) or self.bit_depth < 1:
            raise AudioContractError("output decoded values are invalid")
        payload = {"project_ref": self.project_ref.value, "specification_digest": _sha(self.specification_digest, "specification_digest"), "output": self.output.payload(), "duration": actual_duration, "sample_rate": actual_rate, "channel_layout": actual_layout, "codec": _text(self.codec, "output codec"), "sample_format": _text(self.sample_format, "output sample_format"), "bit_depth": self.bit_depth, "producer_attempt_id": attempt, "producer_fence": fence, "derivation": _text(self.derivation, "derivation")}
        if _sha(self.output_digest, "output_digest") != _digest(payload):
            raise AudioContractError("output_digest does not match exact output")


@dataclass(frozen=True)
class StemSpecification:
    project_ref: ProjectRef
    specification: AudioSpecification
    stem_id: str
    output: AudioArtifactContentRef

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.specification, AudioSpecification) or not isinstance(self.output, AudioArtifactContentRef) or self.specification.project_ref != self.project_ref or self.output.project_ref != self.project_ref:
            raise AudioContractError("stem Project/specification is incompatible")
        _text(self.stem_id, "stem_id")


@dataclass(frozen=True)
class MixSpecification:
    project_ref: ProjectRef
    mix_ref: str
    version: str
    stems: tuple[StemSpecification, ...]
    levels: Mapping[str, str]

    def __post_init__(self) -> None:
        stems = tuple(self.stems)
        if not isinstance(self.project_ref, ProjectRef) or not stems or not all(isinstance(stem, StemSpecification) and stem.project_ref == self.project_ref for stem in stems):
            raise AudioContractError("mix Project/stems are incompatible")
        _ref(self.mix_ref, "mix_ref")
        _text(self.version, "mix version")
        levels = _map(self.levels, "mix levels")
        if set(levels) != {stem.stem_id for stem in stems}:
            raise AudioContractError("mix levels do not bind exact stems")
        object.__setattr__(self, "stems", stems)
        object.__setattr__(self, "levels", levels)


@dataclass(frozen=True)
class EditableAudioSessionBinding:
    project_ref: ProjectRef
    specification: AudioSpecification
    session: AudioArtifactContentRef
    tool_ref: str
    tool_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.specification, AudioSpecification) or not isinstance(self.session, AudioArtifactContentRef) or self.specification.project_ref != self.project_ref or self.session.project_ref != self.project_ref:
            raise AudioContractError("session Project/specification is incompatible")
        _ref(self.tool_ref, "tool_ref")
        _text(self.tool_version, "tool_version")


@dataclass(frozen=True)
class GameAudioHandoffBinding:
    project_ref: ProjectRef
    output: AudioOutputRef
    target: AudioArtifactContentRef
    integration_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.output, AudioOutputRef) or not isinstance(self.target, AudioArtifactContentRef) or self.output.project_ref != self.project_ref or self.target.project_ref != self.project_ref:
            raise AudioContractError("game handoff Project is incompatible")
        _ref(self.integration_ref, "integration_ref")


@dataclass(frozen=True)
class VideoAudioHandoffBinding(GameAudioHandoffBinding):
    pass


class AudioToolAdapter(Protocol):
    project_ref: ProjectRef
    tool_ref: str
    runtime_ref: str
    determinism: str

    def inspect(self, source: AudioArtifactContentRef, validator_ref: str) -> AudioInspectionRef: ...
    def execute(self, access: "ProjectAccess", attempt: "NodeExecutionAttempt", specification: AudioSpecification) -> AudioOutputRef: ...


class AudioModelAdapter(Protocol):
    project_ref: ProjectRef
    model_ref: str
    runtime_ref: str
    determinism: str

    def generate(self, access: "ProjectAccess", attempt: "NodeExecutionAttempt", specification: AudioSpecification) -> AudioOutputRef: ...


def audio_production_pack() -> ProductionPack:
    names = AUDIO_CAPABILITIES + AUDIO_OPTIONAL_CAPABILITIES
    capabilities = tuple(Capability(CapabilityRef(f"audio.{name}", "1.0.0"), f"Bounded audio {name}", {"optional": "contract://capability/optional/v1"} if name in AUDIO_OPTIONAL_CAPABILITIES else {}, {"result": f"biella://contracts/audio-{name}/v1"}, (), "2026-09-01T00:00:00+00:00") for name in names)
    refs = {capability.name: capability.capability_ref for capability in capabilities}
    steps = tuple(GraphRecipeStepRegistration(name, refs[name], () if index == 0 else (names[index - 1],)) for index, name in enumerate(names))
    return ProductionPack(ProductionPackRef("audio", "1.0.0"), capabilities, (GraphRecipeRegistration("pack-recipe://audio/production@1.0.0", steps),), tuple(ValidatorRegistration(f"pack-validator://audio/{name}@1.0.0", refs[name], f"validation-check://artifact-role/{AUDIO_ARTIFACT_ROLES[index % len(AUDIO_ARTIFACT_ROLES)]}/v1") for index, name in enumerate(names)), AUDIO_ARTIFACT_ROLES, {capability.capability_ref.value: ("adapter://audio/provider-neutral/v1",) for capability in capabilities}, {capability.capability_ref.value: "resource-profile://audio/project-configured/v1" for capability in capabilities}, "2026-09-01T00:00:00+00:00")
