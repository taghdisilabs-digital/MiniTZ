"""P3-07 provider-neutral animation pack contract."""

from __future__ import annotations

from dataclasses import replace
import math

import pytest

from biella.animation_pack import AnimationClip, AnimationContractError, AnimationSet, BoneMapping, RetargetMapping, RetargetRequest, animation_production_pack
from biella.character_pack import CharacterRigRef
from biella.production_pack import ProductionPackRef
from biella.project import ProjectRef


CORE = {"inspect", "import", "generate", "edit", "keyframe", "retarget", "blend", "root_motion", "loop", "clean", "bake", "preview", "export", "validate"}
OPTIONAL = {"mocap", "facial", "compress"}
POLICIES = {"mapping", "coordinate", "scale", "root_motion", "export"}


def _rig(project_ref: ProjectRef, name: str, skeleton_digest: str, rig_digest: str) -> CharacterRigRef:
    return CharacterRigRef(project_ref, f"{name}-character", f"artifact://character/{name}/source/v1", "a" * 64, f"artifact://character/{name}/mesh/v1", "b" * 64, f"artifact://character/{name}/skeleton/v1", skeleton_digest, f"{name}-rig", f"artifact://character/{name}/rig/v1", rig_digest, (1.0, 1.0, 1.0), {"up": "Z", "forward": "Y"}, "contract://coordinate/z-up/v1", f"artifact://character/{name}/rest-pose/v1", f"provenance://character/{name}/rig/v1", "provenance://tool/character/v1", "provenance://script/character/v1", {})


def _clip(project_ref: ProjectRef, rig: CharacterRigRef) -> AnimationClip:
    return AnimationClip(project_ref, "walk-cycle", "artifact://animation/walk/source/v1", "1" * 64, rig, 0.0, 1.0, 1.0, 30.0, "seconds", {"translation": 3, "rotation": 4}, {}, {"mode": "seamless"}, {"up": "Z", "forward": "Y"}, "contract://coordinate/z-up/v1", "provenance://tool/animation/v1", "runtime://animation/reference/v1", "content://animation/walk/v1")


def _mapping(project_ref: ProjectRef, source: CharacterRigRef, target: CharacterRigRef) -> RetargetMapping:
    return RetargetMapping(project_ref, "walk-source-to-target", "1.0.0", source, target, (BoneMapping("hip", "pelvis"), BoneMapping("spine", "spine-main")), "artifact://animation/walk/retarget-mapping/v1", "2" * 64)


def _request(project_ref: ProjectRef, clip: AnimationClip, source: CharacterRigRef, target: CharacterRigRef, mapping: RetargetMapping) -> RetargetRequest:
    return RetargetRequest(project_ref, "walk-retarget", clip, source, target, mapping, (1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (1.0,) * 16, {}, ("contract://output/animation/v1",), {name: f"policy://animation/{name}/v1" for name in POLICIES}, {name: "1.0.0" for name in POLICIES})


def test_animation_pack_registers_core_optional_paths_roles_validators_and_recipe() -> None:
    pack = animation_production_pack()
    assert pack.pack_ref == ProductionPackRef("animation", "1.0.0")
    assert {item.capability_id for item in pack.capability_definitions} == {*(f"animation.{name}" for name in CORE), *(f"animation.{name}" for name in OPTIONAL)}
    assert pack.artifact_roles and pack.validators and pack.graph_recipes


def test_animation_contracts_bind_exact_character_rigs_mapping_and_policies() -> None:
    project_ref = ProjectRef.new()
    source = _rig(project_ref, "source", "c" * 64, "d" * 64)
    target = _rig(project_ref, "target", "e" * 64, "f" * 64)
    clip = _clip(project_ref, source)
    mapping = _mapping(project_ref, source, target)
    request = _request(project_ref, clip, source, target, mapping)
    animation_set = AnimationSet(project_ref, "locomotion", (clip.source_artifact_ref,), (clip.content_sha256,), source, {"kind": "locomotion"}, "1.0.0")
    assert clip.require_character_rig(source) is source
    assert animation_set.require_clip(clip) is clip
    assert request.require_clip(clip) is clip
    assert request.require_mapping(mapping) is mapping
    with pytest.raises(AnimationContractError): clip.require_character_rig(replace(source, rig_content_sha256="0" * 64))
    with pytest.raises(AnimationContractError): animation_set.require_clip(replace(clip, project_ref=ProjectRef.new()))
    with pytest.raises(AnimationContractError): request.require_mapping(replace(mapping, content_sha256="0" * 64))
    with pytest.raises(AnimationContractError): replace(request, policy_versions={})
    with pytest.raises(AnimationContractError): replace(request, transform=(math.inf,) * 16)
