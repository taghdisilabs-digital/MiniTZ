"""Provider-neutral character production-pack and project-scoped contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import re
from types import MappingProxyType

from .capability import Capability, CapabilityRef
from .production_pack import (
    GraphRecipeRegistration,
    GraphRecipeStepRegistration,
    ProductionPack,
    ProductionPackRef,
    ValidatorRegistration,
)
from .project import ProjectRef


_VERSION = "1.0.0"
_CREATED_AT = "2026-08-31T00:00:00+00:00"
_IDENTITY_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,127}")
_REFERENCE_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

CHARACTER_SOURCE = "character.source"
CHARACTER_MESH = "character.mesh"
HIGH_POLY = "character.high-poly"
LOW_POLY = "character.low-poly"
CHARACTER_RIG = "character.rig"
SKELETON = "character.skeleton"
SKIN_WEIGHTS = "character.skin-weights"
CONTROL_RIG = "character.control-rig"
MATERIAL_BINDINGS = "character.material-bindings"
EXPORT = "character.export"
PREVIEW = "character.preview"
DEFORMATION_EVIDENCE = "character.deformation-evidence"

_CAPABILITY_NAMES = (
    "inspect",
    "model",
    "sculpt",
    "retopology",
    "uv",
    "material",
    "texture_bind",
    "skeleton",
    "rig",
    "skin",
    "weight",
    "deform_test",
    "optimize",
    "export",
    "preview",
    "validate",
)

_VALIDATOR_ROLES = {
    "inspect": CHARACTER_SOURCE,
    "model": CHARACTER_SOURCE,
    "sculpt": HIGH_POLY,
    "retopology": LOW_POLY,
    "uv": CHARACTER_MESH,
    "material": MATERIAL_BINDINGS,
    "texture_bind": MATERIAL_BINDINGS,
    "skeleton": SKELETON,
    "rig": CHARACTER_RIG,
    "skin": SKIN_WEIGHTS,
    "weight": SKIN_WEIGHTS,
    "deform_test": DEFORMATION_EVIDENCE,
    "optimize": LOW_POLY,
    "export": EXPORT,
    "preview": PREVIEW,
    "validate": DEFORMATION_EVIDENCE,
}


class CharacterContractError(ValueError):
    """Character production data does not meet its fail-closed contract."""


def _identity(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _IDENTITY_PATTERN.fullmatch(value) is None:
        raise CharacterContractError(f"{field_name} is malformed")
    return value


def _reference(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _REFERENCE_PATTERN.fullmatch(value) is None:
        raise CharacterContractError(f"{field_name} must be an absolute reference")
    return value


def _sha256(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise CharacterContractError(f"{field_name} must be a SHA-256 digest")
    return value


def _metadata(value: object, field_name: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or len(value) > 64:
        raise CharacterContractError(f"{field_name} must be a bounded mapping")
    copied: dict[str, str] = {}
    for key, item in value.items():
        if (
            not isinstance(key, str)
            or not key
            or len(key) > 128
            or not isinstance(item, str)
            or len(item) > 1024
        ):
            raise CharacterContractError(f"{field_name} contains malformed text")
        copied[key] = item
    return MappingProxyType(dict(sorted(copied.items())))


def _coordinate_system(value: object) -> Mapping[str, str]:
    coordinates = _metadata(value, "coordinate_system")
    if not coordinates:
        raise CharacterContractError("coordinate_system must not be empty")
    return coordinates


def _reference_collection(value: object, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CharacterContractError(f"{field_name} must be a sequence")
    references = tuple(_reference(item, field_name) for item in value)
    if not references or len(references) > 64 or len(set(references)) != len(references):
        raise CharacterContractError(f"{field_name} is empty, duplicated, or unbounded")
    return tuple(sorted(references))


def _scale(value: object) -> tuple[float, float, float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 3:
        raise CharacterContractError("scale must be a three-axis sequence")
    scale = tuple(value)
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in scale):
        raise CharacterContractError("scale must contain numbers")
    normalized = (float(scale[0]), float(scale[1]), float(scale[2]))
    if not all(math.isfinite(item) for item in normalized):
        raise CharacterContractError("scale must be finite")
    return normalized


@dataclass(frozen=True)
class CharacterSpecification:
    """Open, Project-scoped character target data without anatomy assumptions."""

    project_ref: ProjectRef
    character_id: str
    character_artifact_ref: str
    character_content_sha256: str
    mesh_ref: str
    mesh_content_sha256: str
    skeleton_ref: str
    skeleton_content_sha256: str
    scale: tuple[float, float, float]
    coordinate_system: Mapping[str, str]
    coordinate_convention_ref: str
    rest_pose_ref: str
    provenance_ref: str
    visual_reference_refs: tuple[str, ...]
    geometry_topology_refs: tuple[str, ...]
    skeleton_rig_refs: tuple[str, ...]
    material_binding_refs: tuple[str, ...]
    target_constraint_refs: tuple[str, ...]
    validation_contract_refs: tuple[str, ...]
    output_contract_refs: tuple[str, ...]
    target_metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise CharacterContractError("project_ref must be ProjectRef")
        object.__setattr__(self, "character_id", _identity(self.character_id, "character_id"))
        object.__setattr__(self, "character_artifact_ref", _reference(self.character_artifact_ref, "character_artifact_ref"))
        object.__setattr__(self, "character_content_sha256", _sha256(self.character_content_sha256, "character_content_sha256"))
        object.__setattr__(self, "mesh_ref", _reference(self.mesh_ref, "mesh_ref"))
        object.__setattr__(self, "mesh_content_sha256", _sha256(self.mesh_content_sha256, "mesh_content_sha256"))
        object.__setattr__(self, "skeleton_ref", _reference(self.skeleton_ref, "skeleton_ref"))
        object.__setattr__(self, "skeleton_content_sha256", _sha256(self.skeleton_content_sha256, "skeleton_content_sha256"))
        object.__setattr__(self, "scale", _scale(self.scale))
        object.__setattr__(self, "coordinate_system", _coordinate_system(self.coordinate_system))
        object.__setattr__(self, "coordinate_convention_ref", _reference(self.coordinate_convention_ref, "coordinate_convention_ref"))
        object.__setattr__(self, "rest_pose_ref", _reference(self.rest_pose_ref, "rest_pose_ref"))
        object.__setattr__(self, "provenance_ref", _reference(self.provenance_ref, "provenance_ref"))
        object.__setattr__(self, "visual_reference_refs", _reference_collection(self.visual_reference_refs, "visual_reference_refs"))
        object.__setattr__(self, "geometry_topology_refs", _reference_collection(self.geometry_topology_refs, "geometry_topology_refs"))
        object.__setattr__(self, "skeleton_rig_refs", _reference_collection(self.skeleton_rig_refs, "skeleton_rig_refs"))
        object.__setattr__(self, "material_binding_refs", _reference_collection(self.material_binding_refs, "material_binding_refs"))
        object.__setattr__(self, "target_constraint_refs", _reference_collection(self.target_constraint_refs, "target_constraint_refs"))
        object.__setattr__(self, "validation_contract_refs", _reference_collection(self.validation_contract_refs, "validation_contract_refs"))
        object.__setattr__(self, "output_contract_refs", _reference_collection(self.output_contract_refs, "output_contract_refs"))
        object.__setattr__(self, "target_metadata", _metadata(self.target_metadata, "target_metadata"))


@dataclass(frozen=True)
class CharacterRigRef:
    """Exact Project-scoped rig identity and evidence reference for P3-07."""

    project_ref: ProjectRef
    character_id: str
    character_artifact_ref: str
    character_content_sha256: str
    mesh_ref: str
    mesh_content_sha256: str
    skeleton_ref: str
    skeleton_content_sha256: str
    rig_id: str
    rig_artifact_ref: str
    rig_content_sha256: str
    scale: tuple[float, float, float]
    coordinate_system: Mapping[str, str]
    coordinate_convention_ref: str
    rest_pose_ref: str
    provenance_ref: str
    tool_provenance_ref: str
    script_provenance_ref: str
    target_metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise CharacterContractError("project_ref must be ProjectRef")
        object.__setattr__(self, "character_id", _identity(self.character_id, "character_id"))
        object.__setattr__(self, "character_artifact_ref", _reference(self.character_artifact_ref, "character_artifact_ref"))
        object.__setattr__(self, "character_content_sha256", _sha256(self.character_content_sha256, "character_content_sha256"))
        object.__setattr__(self, "mesh_ref", _reference(self.mesh_ref, "mesh_ref"))
        object.__setattr__(self, "mesh_content_sha256", _sha256(self.mesh_content_sha256, "mesh_content_sha256"))
        object.__setattr__(self, "skeleton_ref", _reference(self.skeleton_ref, "skeleton_ref"))
        object.__setattr__(self, "skeleton_content_sha256", _sha256(self.skeleton_content_sha256, "skeleton_content_sha256"))
        object.__setattr__(self, "rig_id", _identity(self.rig_id, "rig_id"))
        object.__setattr__(self, "rig_artifact_ref", _reference(self.rig_artifact_ref, "rig_artifact_ref"))
        object.__setattr__(self, "rig_content_sha256", _sha256(self.rig_content_sha256, "rig_content_sha256"))
        object.__setattr__(self, "scale", _scale(self.scale))
        object.__setattr__(self, "coordinate_system", _coordinate_system(self.coordinate_system))
        object.__setattr__(self, "coordinate_convention_ref", _reference(self.coordinate_convention_ref, "coordinate_convention_ref"))
        object.__setattr__(self, "rest_pose_ref", _reference(self.rest_pose_ref, "rest_pose_ref"))
        object.__setattr__(self, "provenance_ref", _reference(self.provenance_ref, "provenance_ref"))
        object.__setattr__(self, "tool_provenance_ref", _reference(self.tool_provenance_ref, "tool_provenance_ref"))
        object.__setattr__(self, "script_provenance_ref", _reference(self.script_provenance_ref, "script_provenance_ref"))
        object.__setattr__(self, "target_metadata", _metadata(self.target_metadata, "target_metadata"))

    def require_specification(self, specification: CharacterSpecification) -> CharacterSpecification:
        if not isinstance(specification, CharacterSpecification):
            raise CharacterContractError("specification must be CharacterSpecification")
        if (
            specification.project_ref != self.project_ref
            or specification.character_id != self.character_id
            or specification.character_artifact_ref != self.character_artifact_ref
            or specification.character_content_sha256 != self.character_content_sha256
            or specification.mesh_ref != self.mesh_ref
            or specification.mesh_content_sha256 != self.mesh_content_sha256
            or specification.skeleton_ref != self.skeleton_ref
            or specification.skeleton_content_sha256 != self.skeleton_content_sha256
            or specification.scale != self.scale
            or specification.coordinate_system != self.coordinate_system
            or specification.coordinate_convention_ref != self.coordinate_convention_ref
            or specification.rest_pose_ref != self.rest_pose_ref
        ):
            raise CharacterContractError("rig has stale project, character, dependency, coordinate, scale, or rest-pose identity")
        return specification


def _capability(name: str) -> Capability:
    return Capability(
        capability_ref=CapabilityRef(f"character.{name}", _VERSION),
        description=f"Perform bounded character {name.replace('_', ' ')} work through replaceable adapters.",
        input_contract={
            "asset": "biella://contracts/artifact-ref/v1",
            "character": "biella://contracts/character-specification/v1",
            "project": "biella://contracts/project-ref/v1",
            "task": "biella://contracts/task-ref/v1",
        },
        output_contract={
            "result": f"biella://contracts/character-{name.replace('_', '-')}/v1",
        },
        side_effects=(
            "workspace.process.execute",
            "workspace.filesystem.write",
            "workspace.artifact.create",
        ),
        created_at=_CREATED_AT,
    )


def character_production_pack() -> ProductionPack:
    """Return the immutable, provider-neutral character pack descriptor."""

    capabilities = tuple(_capability(name) for name in _CAPABILITY_NAMES)
    by_name = {item.name: item.capability_ref for item in capabilities}
    recipe_steps = tuple(
        GraphRecipeStepRegistration(
            name,
            by_name[name],
            (() if index == 0 else (_CAPABILITY_NAMES[index - 1],)),
        )
        for index, name in enumerate(_CAPABILITY_NAMES)
    )
    validators = tuple(
        ValidatorRegistration(
            registration_ref=f"pack-validator://character/{name}@1.0.0",
            capability_ref=by_name[name],
            validator_ref=f"validation-check://artifact-role/{_VALIDATOR_ROLES[name]}/v1",
        )
        for name in _CAPABILITY_NAMES
    )
    common_adapters = (
        "adapter://artifact/v1",
        "adapter://filesystem/v1",
        "adapter://process/v1",
        "adapter://three-d-tool/v1",
        "adapter://workspace/v1",
    )
    return ProductionPack(
        pack_ref=ProductionPackRef("character", _VERSION),
        capability_definitions=capabilities,
        graph_recipes=(
            GraphRecipeRegistration(
                recipe_ref="pack-recipe://character/asset-production@1.0.0",
                steps=recipe_steps,
            ),
        ),
        validators=validators,
        artifact_roles=(
            CHARACTER_SOURCE,
            CHARACTER_MESH,
            HIGH_POLY,
            LOW_POLY,
            CHARACTER_RIG,
            SKELETON,
            SKIN_WEIGHTS,
            CONTROL_RIG,
            MATERIAL_BINDINGS,
            EXPORT,
            PREVIEW,
            DEFORMATION_EVIDENCE,
        ),
        adapter_bindings={
            capability.capability_ref.value: common_adapters for capability in capabilities
        },
        resource_profiles={
            capability.capability_ref.value: "resource-profile://character/project-configured/v1"
            for capability in capabilities
        },
        created_at=_CREATED_AT,
    )
