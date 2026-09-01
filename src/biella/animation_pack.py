"""Provider-neutral animation production-pack contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from types import MappingProxyType

from .capability import Capability, CapabilityRef
from .character_pack import CharacterRigRef
from .production_pack import GraphRecipeRegistration, GraphRecipeStepRegistration, ProductionPack, ProductionPackRef, ValidatorRegistration
from .project import ProjectRef


_VERSION = "1.0.0"
_CREATED_AT = "2026-08-31T00:00:00+00:00"
_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,127}")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA = re.compile(r"[0-9a-f]{64}")
_CORE = ("inspect", "import", "generate", "edit", "keyframe", "retarget", "blend", "root_motion", "loop", "clean", "bake", "preview", "export", "validate")
_OPTIONAL = ("mocap", "facial", "compress")
_ROLES = ("animation.clip", "animation.set", "animation.skeleton", "animation.rig", "animation.retarget-mapping", "animation.root-motion", "animation.preview", "animation.export", "animation.validation", "animation.mocap", "animation.facial", "animation.compressed")


class AnimationContractError(ValueError):
    """Animation data failed a fail-closed identity or timing contract."""


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise AnimationContractError(f"{field} is malformed")
    return value


def _ref(value: object, field: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise AnimationContractError(f"{field} must be an absolute reference")
    return value


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise AnimationContractError(f"{field} must be a SHA-256 digest")
    return value


def _mapping(value: object, field: str, *, allow_empty: bool) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or len(value) > 64 or (not allow_empty and not value):
        raise AnimationContractError(f"{field} is malformed")
    copied: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or len(key) > 128 or not isinstance(item, str) or len(item) > 1024:
            raise AnimationContractError(f"{field} contains malformed text")
        copied[key] = item
    return MappingProxyType(dict(sorted(copied.items())))


def _counts(value: object) -> Mapping[str, int]:
    if not isinstance(value, Mapping) or not value or len(value) > 64:
        raise AnimationContractError("channel_summary is malformed")
    copied: dict[str, int] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise AnimationContractError("channel_summary is malformed")
        copied[key] = item
    return MappingProxyType(dict(sorted(copied.items())))


def _finite_vector(value: object, field: str, length: int) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != length:
        raise AnimationContractError(f"{field} has the wrong dimension")
    result = tuple(float(item) for item in value if isinstance(item, (int, float)) and not isinstance(item, bool))
    if len(result) != length or not all(math.isfinite(item) for item in result):
        raise AnimationContractError(f"{field} must be finite")
    return result


def _refs(value: object, field: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise AnimationContractError(f"{field} must be a sequence")
    refs = tuple(_ref(item, field) for item in value)
    if not refs or len(refs) > 64 or len(set(refs)) != len(refs):
        raise AnimationContractError(f"{field} is empty, duplicated, or unbounded")
    return tuple(sorted(refs))


@dataclass(frozen=True)
class AnimationClip:
    project_ref: ProjectRef
    clip_id: str
    source_artifact_ref: str
    content_sha256: str
    character_rig_ref: CharacterRigRef
    start_time: float
    end_time: float
    duration_seconds: float
    frame_rate: float
    time_unit: str
    channel_summary: Mapping[str, int]
    root_motion_metadata: Mapping[str, str]
    loop_metadata: Mapping[str, str]
    coordinate_system: Mapping[str, str]
    coordinate_convention_ref: str
    tool_provenance_ref: str
    runtime_ref: str
    content_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef): raise AnimationContractError("project_ref must be ProjectRef")
        for field in ("clip_id", "time_unit"):
            object.__setattr__(self, field, _identity(getattr(self, field), field))
        for field in ("source_artifact_ref", "coordinate_convention_ref", "tool_provenance_ref", "runtime_ref", "content_ref"):
            object.__setattr__(self, field, _ref(getattr(self, field), field))
        if not isinstance(self.character_rig_ref, CharacterRigRef) or self.character_rig_ref.project_ref != self.project_ref:
            raise AnimationContractError("character_rig_ref is out of project scope")
        for field in ("content_sha256",):
            object.__setattr__(self, field, _sha(getattr(self, field), field))
        times = (self.start_time, self.end_time, self.duration_seconds, self.frame_rate)
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in times) or self.end_time <= self.start_time or self.duration_seconds <= 0 or self.frame_rate <= 0 or not math.isclose(self.end_time - self.start_time, self.duration_seconds):
            raise AnimationContractError("clip timing is malformed")
        object.__setattr__(self, "channel_summary", _counts(self.channel_summary))
        object.__setattr__(self, "root_motion_metadata", _mapping(self.root_motion_metadata, "root_motion_metadata", allow_empty=True))
        object.__setattr__(self, "loop_metadata", _mapping(self.loop_metadata, "loop_metadata", allow_empty=True))
        object.__setattr__(self, "coordinate_system", _mapping(self.coordinate_system, "coordinate_system", allow_empty=False))

    def require_character_rig(self, rig: CharacterRigRef) -> CharacterRigRef:
        if not isinstance(rig, CharacterRigRef) or rig != self.character_rig_ref:
            raise AnimationContractError("character rig identity is stale or mismatched")
        return rig


@dataclass(frozen=True)
class AnimationSet:
    project_ref: ProjectRef
    set_id: str
    clip_refs: tuple[str, ...]
    clip_content_sha256s: tuple[str, ...]
    character_rig_ref: CharacterRigRef
    labels: Mapping[str, str]
    version: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef): raise AnimationContractError("project_ref must be ProjectRef")
        object.__setattr__(self, "set_id", _identity(self.set_id, "set_id"))
        refs = tuple(_ref(item, "clip_refs") for item in self.clip_refs)
        if not refs or len(refs) > 64 or len(set(refs)) != len(refs):
            raise AnimationContractError("clip_refs is empty, duplicated, or unbounded")
        digests = tuple(_sha(item, "clip_content_sha256s") for item in self.clip_content_sha256s)
        if len(digests) != len(refs): raise AnimationContractError("clip identities are incomplete")
        identities = tuple(sorted(zip(refs, digests, strict=True)))
        object.__setattr__(self, "clip_refs", tuple(item[0] for item in identities))
        object.__setattr__(self, "clip_content_sha256s", tuple(item[1] for item in identities))
        if not isinstance(self.character_rig_ref, CharacterRigRef) or self.character_rig_ref.project_ref != self.project_ref:
            raise AnimationContractError("character_rig_ref is out of project scope")
        object.__setattr__(self, "labels", _mapping(self.labels, "labels", allow_empty=True))
        if not isinstance(self.version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.version): raise AnimationContractError("version is malformed")

    @property
    def clip_identities(self) -> tuple[tuple[str, str], ...]:
        return tuple(zip(self.clip_refs, self.clip_content_sha256s, strict=True))

    def require_clip(self, clip: AnimationClip) -> AnimationClip:
        if not isinstance(clip, AnimationClip) or clip.project_ref != self.project_ref or clip.character_rig_ref != self.character_rig_ref or (clip.source_artifact_ref, clip.content_sha256) not in self.clip_identities:
            raise AnimationContractError("clip is stale or mismatched for animation set")
        return clip


@dataclass(frozen=True)
class BoneMapping:
    source_bone: str
    target_bone: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_bone", _identity(self.source_bone, "source_bone"))
        object.__setattr__(self, "target_bone", _identity(self.target_bone, "target_bone"))


@dataclass(frozen=True)
class RetargetMapping:
    project_ref: ProjectRef
    mapping_id: str
    mapping_version: str
    source_rig_ref: CharacterRigRef
    target_rig_ref: CharacterRigRef
    bone_mappings: tuple[BoneMapping, ...]
    mapping_ref: str
    content_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef): raise AnimationContractError("project_ref must be ProjectRef")
        object.__setattr__(self, "mapping_id", _identity(self.mapping_id, "mapping_id"))
        if not isinstance(self.mapping_version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.mapping_version): raise AnimationContractError("mapping_version is malformed")
        if not isinstance(self.source_rig_ref, CharacterRigRef) or not isinstance(self.target_rig_ref, CharacterRigRef) or self.source_rig_ref.project_ref != self.project_ref or self.target_rig_ref.project_ref != self.project_ref:
            raise AnimationContractError("retarget rigs are out of project scope")
        object.__setattr__(self, "mapping_ref", _ref(self.mapping_ref, "mapping_ref"))
        object.__setattr__(self, "content_sha256", _sha(self.content_sha256, "content_sha256"))
        mappings = tuple(self.bone_mappings)
        if not mappings or not all(isinstance(item, BoneMapping) for item in mappings) or len({item.source_bone for item in mappings}) != len(mappings) or len({item.target_bone for item in mappings}) != len(mappings): raise AnimationContractError("bone_mappings must be explicit and one-to-one")
        object.__setattr__(self, "bone_mappings", mappings)


def _rig_payload(rig: CharacterRigRef) -> dict[str, object]:
    return {
        "character_artifact_ref": rig.character_artifact_ref,
        "character_content_sha256": rig.character_content_sha256,
        "character_id": rig.character_id,
        "coordinate_convention_ref": rig.coordinate_convention_ref,
        "coordinate_system": dict(rig.coordinate_system),
        "mesh_content_sha256": rig.mesh_content_sha256,
        "mesh_ref": rig.mesh_ref,
        "project_ref": rig.project_ref.value,
        "provenance_ref": rig.provenance_ref,
        "rest_pose_ref": rig.rest_pose_ref,
        "rig_artifact_ref": rig.rig_artifact_ref,
        "rig_content_sha256": rig.rig_content_sha256,
        "rig_id": rig.rig_id,
        "scale": list(rig.scale),
        "script_provenance_ref": rig.script_provenance_ref,
        "skeleton_content_sha256": rig.skeleton_content_sha256,
        "skeleton_ref": rig.skeleton_ref,
        "target_metadata": dict(rig.target_metadata),
        "tool_provenance_ref": rig.tool_provenance_ref,
    }


def _clip_payload(clip: AnimationClip) -> dict[str, object]:
    return {
        "channel_summary": dict(clip.channel_summary),
        "character_rig_ref": _rig_payload(clip.character_rig_ref),
        "clip_id": clip.clip_id,
        "content_ref": clip.content_ref,
        "content_sha256": clip.content_sha256,
        "coordinate_convention_ref": clip.coordinate_convention_ref,
        "coordinate_system": dict(clip.coordinate_system),
        "duration_seconds": clip.duration_seconds,
        "end_time": clip.end_time,
        "frame_rate": clip.frame_rate,
        "loop_metadata": dict(clip.loop_metadata),
        "project_ref": clip.project_ref.value,
        "root_motion_metadata": dict(clip.root_motion_metadata),
        "runtime_ref": clip.runtime_ref,
        "source_artifact_ref": clip.source_artifact_ref,
        "start_time": clip.start_time,
        "time_unit": clip.time_unit,
        "tool_provenance_ref": clip.tool_provenance_ref,
    }


def _retarget_mapping_payload(mapping: RetargetMapping) -> dict[str, object]:
    return {
        "bone_mappings": [
            {"source_bone": item.source_bone, "target_bone": item.target_bone}
            for item in sorted(mapping.bone_mappings, key=lambda item: (item.source_bone, item.target_bone))
        ],
        "content_sha256": mapping.content_sha256,
        "mapping_id": mapping.mapping_id,
        "mapping_ref": mapping.mapping_ref,
        "mapping_version": mapping.mapping_version,
        "project_ref": mapping.project_ref.value,
        "source_rig_ref": _rig_payload(mapping.source_rig_ref),
        "target_rig_ref": _rig_payload(mapping.target_rig_ref),
    }


@dataclass(frozen=True)
class RetargetRequest:
    project_ref: ProjectRef
    request_id: str
    clip: AnimationClip
    source_rig_ref: CharacterRigRef
    target_rig_ref: CharacterRigRef
    mapping: RetargetMapping
    source_scale: tuple[float, float, float]
    target_scale: tuple[float, float, float]
    transform: tuple[float, ...]
    root_motion_metadata: Mapping[str, str]
    output_contract_refs: tuple[str, ...]
    policy_refs: Mapping[str, str]
    policy_versions: Mapping[str, str]
    request_version: str = _VERSION
    request_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef): raise AnimationContractError("project_ref must be ProjectRef")
        object.__setattr__(self, "request_id", _identity(self.request_id, "request_id"))
        if not isinstance(self.request_version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.request_version): raise AnimationContractError("request_version is malformed")
        if not isinstance(self.clip, AnimationClip) or not isinstance(self.source_rig_ref, CharacterRigRef) or not isinstance(self.target_rig_ref, CharacterRigRef) or not isinstance(self.mapping, RetargetMapping):
            raise AnimationContractError("retarget request must bind exact clip, rigs, and mapping")
        if self.clip.project_ref != self.project_ref or self.source_rig_ref.project_ref != self.project_ref or self.target_rig_ref.project_ref != self.project_ref or self.mapping.project_ref != self.project_ref or self.clip.character_rig_ref != self.source_rig_ref or self.mapping.source_rig_ref != self.source_rig_ref or self.mapping.target_rig_ref != self.target_rig_ref:
            raise AnimationContractError("retarget request identity is stale or out of scope")
        object.__setattr__(self, "source_scale", _finite_vector(self.source_scale, "source_scale", 3))
        object.__setattr__(self, "target_scale", _finite_vector(self.target_scale, "target_scale", 3))
        object.__setattr__(self, "transform", _finite_vector(self.transform, "transform", 16))
        object.__setattr__(self, "root_motion_metadata", _mapping(self.root_motion_metadata, "root_motion_metadata", allow_empty=True))
        object.__setattr__(self, "output_contract_refs", _refs(self.output_contract_refs, "output_contract_refs"))
        policy_refs = _mapping(self.policy_refs, "policy_refs", allow_empty=False)
        policy_versions = _mapping(self.policy_versions, "policy_versions", allow_empty=False)
        required_policies = {"mapping", "coordinate", "scale", "root_motion", "export"}
        if set(policy_refs) != required_policies or set(policy_versions) != required_policies:
            raise AnimationContractError("policy bindings are missing")
        for name, ref in policy_refs.items():
            _ref(ref, f"policy_refs.{name}")
        for name, version in policy_versions.items():
            if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
                raise AnimationContractError("policy version is malformed")
        object.__setattr__(self, "policy_refs", policy_refs)
        object.__setattr__(self, "policy_versions", policy_versions)
        object.__setattr__(self, "request_sha256", hashlib.sha256(self.canonical_bytes()).hexdigest())

    def payload(self) -> dict[str, object]:
        return {
            "clip": _clip_payload(self.clip),
            "mapping": _retarget_mapping_payload(self.mapping),
            "output_contract_refs": list(self.output_contract_refs),
            "policy_refs": dict(self.policy_refs),
            "policy_versions": dict(self.policy_versions),
            "project_ref": self.project_ref.value,
            "request_id": self.request_id,
            "request_version": self.request_version,
            "root_motion_metadata": dict(self.root_motion_metadata),
            "source_rig_ref": _rig_payload(self.source_rig_ref),
            "source_scale": list(self.source_scale),
            "target_rig_ref": _rig_payload(self.target_rig_ref),
            "target_scale": list(self.target_scale),
            "transform": list(self.transform),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.payload(),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    def require_clip(self, clip: AnimationClip) -> AnimationClip:
        if not isinstance(clip, AnimationClip) or clip != self.clip or clip.character_rig_ref != self.source_rig_ref: raise AnimationContractError("clip identity is stale or out of scope")
        return clip

    def require_mapping(self, mapping: RetargetMapping) -> RetargetMapping:
        if not isinstance(mapping, RetargetMapping) or mapping != self.mapping or mapping.source_rig_ref != self.source_rig_ref or mapping.target_rig_ref != self.target_rig_ref: raise AnimationContractError("mapping identity is stale or out of scope")
        return mapping


def _capability(name: str) -> Capability:
    return Capability(CapabilityRef(f"animation.{name}", _VERSION), f"Perform bounded animation {name.replace('_', ' ')} work through replaceable adapters.", {"asset": "biella://contracts/artifact-ref/v1", "project": "biella://contracts/project-ref/v1"}, {"result": f"biella://contracts/animation-{name.replace('_', '-')}/v1"}, ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"), _CREATED_AT)


def animation_production_pack() -> ProductionPack:
    capabilities = tuple(_capability(name) for name in (*_CORE, *_OPTIONAL))
    by_name = {item.name: item.capability_ref for item in capabilities}
    steps = tuple(GraphRecipeStepRegistration(name, by_name[name], (() if index == 0 else ((*_CORE, *_OPTIONAL)[index - 1],))) for index, name in enumerate((*_CORE, *_OPTIONAL)))
    return ProductionPack(ProductionPackRef("animation", _VERSION), capabilities, (GraphRecipeRegistration("pack-recipe://animation/production@1.0.0", steps),), tuple(ValidatorRegistration(f"pack-validator://animation/{name}@1.0.0", by_name[name], f"validation-check://artifact-role/{_ROLES[index % len(_ROLES)]}/v1") for index, name in enumerate((*_CORE, *_OPTIONAL))), _ROLES, {item.capability_ref.value: ("adapter://artifact/v1", "adapter://filesystem/v1", "adapter://process/v1", "adapter://three-d-tool/v1", "adapter://workspace/v1") for item in capabilities}, {item.capability_ref.value: "resource-profile://animation/project-configured/v1" for item in capabilities}, _CREATED_AT)
