"""P3-06 character production-pack contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import math
from typing import Mapping, TypedDict

import pytest

import minitz_os.engine as minitz_engine
from minitz_os.engine.character_pack import (
    CHARACTER_MESH,
    CHARACTER_RIG,
    CHARACTER_SOURCE,
    CONTROL_RIG,
    DEFORMATION_EVIDENCE,
    EXPORT,
    HIGH_POLY,
    LOW_POLY,
    MATERIAL_BINDINGS,
    PREVIEW,
    SKELETON,
    SKIN_WEIGHTS,
    CharacterContractError,
    CharacterRigRef,
    CharacterSpecification,
    character_production_pack,
)
from minitz_os.engine.production_pack import ProductionPackRef
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.three_d_tool import (
    ThreeDBoneSpec,
    ThreeDSkeletonSpec,
    ThreeDSkinBinding,
    ThreeDSkinWeight,
)


CAPABILITY_SUFFIXES = {
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
}

_CHARACTER_ARTIFACT_REF = "artifact://character/hero-01/source/v1"
_MESH_REF = "artifact://character/hero-01/mesh/v1"
_SKELETON_REF = "artifact://character/hero-01/skeleton/v1"
_REST_POSE_REF = "artifact://character/hero-01/rest-pose/v1"
_COORDINATE_CONVENTION_REF = "contract://coordinate/left-handed-z-up/v1"
_PROVENANCE_REF = "provenance://character/hero-01/source/v1"
_SHA256 = "a" * 64


class _SpecificationKwargs(TypedDict):
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


def _specification_kwargs(project_ref: ProjectRef) -> _SpecificationKwargs:
    return {
        "project_ref": project_ref,
        "character_id": "hero-01",
        "character_artifact_ref": _CHARACTER_ARTIFACT_REF,
        "character_content_sha256": _SHA256,
        "mesh_ref": _MESH_REF,
        "mesh_content_sha256": "b" * 64,
        "skeleton_ref": _SKELETON_REF,
        "skeleton_content_sha256": "c" * 64,
        "scale": (1.0, 1.0, 1.0),
        "coordinate_system": {"up": "Z", "forward": "Y", "unit": "meter"},
        "coordinate_convention_ref": _COORDINATE_CONVENTION_REF,
        "rest_pose_ref": _REST_POSE_REF,
        "provenance_ref": _PROVENANCE_REF,
        "visual_reference_refs": ("artifact://character/hero-01/visual/v1",),
        "geometry_topology_refs": ("contract://character/hero-01/topology/v1",),
        "skeleton_rig_refs": ("contract://character/hero-01/rig/v1",),
        "material_binding_refs": ("contract://character/hero-01/material/v1",),
        "target_constraint_refs": ("contract://target/generic-runtime/v1",),
        "validation_contract_refs": ("contract://validation/character/v1",),
        "output_contract_refs": ("contract://output/character/v1",),
        "target_metadata": {"target": "generic-runtime"},
    }

ROLES = {
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
}


def test_character_pack_has_the_exact_capabilities_roles_and_validators() -> None:
    pack = character_production_pack()

    assert pack.pack_ref == ProductionPackRef("character", "1.0.0")
    assert {item.capability_id for item in pack.capability_definitions} == {
        f"character.{suffix}" for suffix in CAPABILITY_SUFFIXES
    }
    assert set(pack.artifact_roles) == ROLES
    assert {item.capability_ref.capability_id for item in pack.validators} == {
        f"character.{suffix}" for suffix in CAPABILITY_SUFFIXES
    }
    assert all(
        "adapter://three-d-tool/v1" in bindings
        for bindings in pack.adapter_bindings.values()
    )


def test_character_contracts_and_provider_neutral_skeleton_types_are_root_exports() -> None:
    expected = {
        "CharacterContractError": CharacterContractError,
        "CharacterSpecification": CharacterSpecification,
        "CharacterRigRef": CharacterRigRef,
        "character_production_pack": character_production_pack,
        "CHARACTER_SOURCE": CHARACTER_SOURCE,
        "CHARACTER_MESH": CHARACTER_MESH,
        "HIGH_POLY": HIGH_POLY,
        "LOW_POLY": LOW_POLY,
        "CHARACTER_RIG": CHARACTER_RIG,
        "SKELETON": SKELETON,
        "SKIN_WEIGHTS": SKIN_WEIGHTS,
        "CONTROL_RIG": CONTROL_RIG,
        "MATERIAL_BINDINGS": MATERIAL_BINDINGS,
        "EXPORT": EXPORT,
        "PREVIEW": PREVIEW,
        "DEFORMATION_EVIDENCE": DEFORMATION_EVIDENCE,
        "ThreeDBoneSpec": ThreeDBoneSpec,
        "ThreeDSkeletonSpec": ThreeDSkeletonSpec,
        "ThreeDSkinWeight": ThreeDSkinWeight,
        "ThreeDSkinBinding": ThreeDSkinBinding,
    }

    assert set(expected) <= set(minitz_engine.__all__)
    assert all(getattr(minitz, name) is value for name, value in expected.items())


def test_character_specification_and_rig_ref_fail_closed_across_project_boundaries() -> None:
    project_ref = ProjectRef.new()
    specification = CharacterSpecification(**_specification_kwargs(project_ref))
    rig = CharacterRigRef(
        project_ref=project_ref,
        character_id="hero-01",
        character_artifact_ref=_CHARACTER_ARTIFACT_REF,
        character_content_sha256=_SHA256,
        mesh_ref=_MESH_REF,
        mesh_content_sha256="b" * 64,
        skeleton_ref=_SKELETON_REF,
        skeleton_content_sha256="c" * 64,
        rig_id="hero-01-control-rig",
        rig_artifact_ref="artifact://character/hero-01/control-rig/v1",
        rig_content_sha256="d" * 64,
        scale=(1.0, 1.0, 1.0),
        coordinate_system={"up": "Z", "forward": "Y", "unit": "meter"},
        coordinate_convention_ref=_COORDINATE_CONVENTION_REF,
        rest_pose_ref=_REST_POSE_REF,
        provenance_ref="provenance://character/hero-01/rig-source/v1",
        tool_provenance_ref="provenance://tool/character-rig/v1",
        script_provenance_ref="provenance://script/character-rig/v1",
        target_metadata={"target": "generic-runtime"},
    )

    assert rig.require_specification(specification) is specification
    with pytest.raises(FrozenInstanceError):
        specification.character_id = "changed"  # type: ignore[misc]
    with pytest.raises(CharacterContractError):
        invalid_scale = _specification_kwargs(project_ref)
        invalid_scale["scale"] = (math.inf, 1.0, 1.0)
        CharacterSpecification(
            **invalid_scale
        )
    with pytest.raises(CharacterContractError):
        invalid_coordinate = _specification_kwargs(project_ref)
        invalid_coordinate["coordinate_system"] = {}
        invalid_coordinate["rest_pose_ref"] = "not-a-reference"
        CharacterSpecification(
            **invalid_coordinate
        )
    with pytest.raises(CharacterContractError):
        rig.require_specification(
            CharacterSpecification(**_specification_kwargs(ProjectRef.new()))
        )
    with pytest.raises(CharacterContractError):
        replace(rig, mesh_content_sha256="e" * 64).require_specification(specification)
    with pytest.raises(CharacterContractError):
        replace(rig, skeleton_content_sha256="e" * 64).require_specification(specification)
    with pytest.raises(CharacterContractError):
        replace(rig, coordinate_convention_ref="contract://coordinate/right-handed-y-up/v1").require_specification(specification)
    with pytest.raises(CharacterContractError):
        replace(rig, scale=(2.0, 1.0, 1.0)).require_specification(specification)
