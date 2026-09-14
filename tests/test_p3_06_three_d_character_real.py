"""Real Blender character-rig evidence on the P3-05 execution substrate."""

from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path
import sqlite3
import sys
from typing import Any

import pytest

from minitz_os.engine.character_pack import CharacterContractError, CharacterSpecification
from minitz_os.engine.three_d_tool import (
    ThreeDBoneSpec,
    ThreeDConflictError,
    ThreeDContractError,
    ThreeDScopeError,
    ThreeDOperation,
    ThreeDSkeletonSpec,
    ThreeDSkinBinding,
    ThreeDSkinWeight,
    ThreeDValidationRequirements,
)


def _p3_05_support() -> Any:
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location("p3_05_character_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _quadruped_skeleton() -> ThreeDSkeletonSpec:
    return ThreeDSkeletonSpec(
        coordinate_system="BLENDER_Z_UP_RIGHT_HANDED",
        bones=(
            ThreeDBoneSpec("root", None, (0.0, 0.0, 0.0), (0.0, 0.0, 0.8)),
            ThreeDBoneSpec("spine", "root", (0.0, 0.0, 0.8), (0.0, 0.0, 1.6)),
            ThreeDBoneSpec("tail", "root", (0.0, 0.0, 0.5), (0.0, -1.0, 0.8)),
            ThreeDBoneSpec("front_leg", "spine", (0.4, 0.0, 1.1), (0.4, 0.0, 0.0)),
            ThreeDBoneSpec("rear_leg", "root", (-0.4, 0.0, 0.6), (-0.4, 0.0, 0.0)),
        ),
    )


def _character_specification(
    env: Any,
    mesh: Any,
    skeleton: ThreeDSkeletonSpec,
) -> CharacterSpecification:
    return CharacterSpecification(
        project_ref=env.access.project_ref,
        character_id="quadruped-core",
        character_artifact_ref=mesh.output_artifact_ref.value,
        character_content_sha256=mesh.output_content_ref.digest,
        mesh_ref=mesh.output_artifact_ref.value,
        mesh_content_sha256=mesh.output_content_ref.digest,
        skeleton_ref=f"skeleton://character/quadruped/{skeleton.semantic_digest}",
        skeleton_content_sha256=skeleton.semantic_digest,
        scale=(1.0, 1.0, 1.0),
        coordinate_system={"handedness": "RIGHT", "up": "Z"},
        coordinate_convention_ref="coordinate://blender/z-up-right-handed",
        rest_pose_ref=f"rest-pose://character/quadruped/{skeleton.semantic_digest}",
        provenance_ref=f"provenance://character/quadruped/{mesh.output_content_ref.digest}",
        visual_reference_refs=("reference://character/quadruped/visual",),
        geometry_topology_refs=("topology://character/quadruped/mesh",),
        skeleton_rig_refs=("rig-source://character/quadruped/skeleton",),
        material_binding_refs=("material://character/quadruped/default",),
        target_constraint_refs=("constraint://character/quadruped/default",),
        validation_contract_refs=("validation://character/quadruped/default",),
        output_contract_refs=("output://character/quadruped/default",),
        target_metadata={"kind": "quadruped"},
    )


def test_real_non_humanoid_rig_skin_deformation_reopens_and_replays(tmp_path: Path) -> None:
    """Catches a character path that publishes a mesh without rig/skin/deformation proof."""

    support = _p3_05_support()
    env = support._environment(tmp_path)
    skeleton = _quadruped_skeleton()
    mesh = env.adapter.createAsset(
        env.access,
        env.attempt,
        support._request(
            env,
            ThreeDOperation.MODEL,
            source=None,
            source_path=None,
            output_path="creature-mesh.blend",
            output_role="3d.mesh",
            output_media_type="application/x-blender",
            config={"name": "CreatureMesh", "unit_system": "METRIC"},
        ),
        idempotency_key="character-mesh",
    )
    assert mesh.output_artifact_ref is not None
    rig_request = replace(
        support._request(
            env,
            ThreeDOperation.MESH_EDIT,
            source=mesh.output_artifact_ref,
            source_path="creature-mesh.blend",
            output_path="creature-rig.blend",
            output_role="3d.mesh",
            output_media_type="application/x-blender",
        ),
        operation=ThreeDOperation.RIG,
        output_role="3d.rig",
        skeleton_spec=skeleton,
    )
    rig = env.adapter.executeOperation(
        env.access, env.attempt, rig_request, idempotency_key="character-rig"
    )
    assert rig.editable_source and rig.output_artifact_ref is not None
    assert support._report(env, rig)["character_identity"]["skeleton_sha256"] == skeleton.semantic_digest
    beta = support.ProjectStore(env.database).create_project(
        namespace="character-isolation-beta",
        display_name="Character Isolation Beta",
    )
    with pytest.raises(ThreeDScopeError):
        env.adapter.executeOperation(
            beta.access,
            env.attempt,
            rig_request,
            idempotency_key="character-rig-beta",
        )
    skin_request = replace(
        support._request(
            env,
            ThreeDOperation.MESH_EDIT,
            source=rig.output_artifact_ref,
            source_path="creature-rig.blend",
            output_path="creature-skin.blend",
            output_role="3d.mesh",
            output_media_type="application/x-blender",
        ),
        operation=ThreeDOperation.SKIN,
        output_role="3d.skin",
        skeleton_spec=skeleton,
    )
    skin = env.adapter.executeOperation(
        env.access, env.attempt, skin_request, idempotency_key="character-skin"
    )
    assert skin.editable_source and skin.output_artifact_ref is not None
    deform_request = replace(
        support._request(
            env,
            ThreeDOperation.MESH_EDIT,
            source=skin.output_artifact_ref,
            source_path="creature-skin.blend",
            output_path="creature-deformed.blend",
            output_role="3d.mesh",
            output_media_type="application/x-blender",
            config={"pose_degrees": 25.0},
        ),
        operation=ThreeDOperation.DEFORM,
        output_role="3d.deformation",
        skeleton_spec=skeleton,
    )
    deformed = env.adapter.executeOperation(
        env.access, env.attempt, deform_request, idempotency_key="character-deform"
    )
    assert deformed.editable_source and deformed.output_artifact_ref is not None
    specification = _character_specification(env, mesh, skeleton)
    rig_ref = env.adapter.finalizeCharacterRigRef(
        env.access, deformed, specification
    )
    assert rig_ref.rig_artifact_ref == deformed.output_artifact_ref.value
    assert rig_ref.rig_content_sha256 == deformed.output_content_ref.digest
    assert rig_ref.require_specification(specification) is specification
    with pytest.raises(CharacterContractError):
        env.adapter.finalizeCharacterRigRef(
            env.access,
            replace(
                deformed,
                reality=support.ThreeDReality.REFERENCE,
                process_artifact_ref=None,
                process_call_ref=None,
                editable_source=False,
            ),
            specification,
        )
    validated = env.adapter.validate(
        env.access,
        env.attempt,
        replace(
            support._request(
                env,
                ThreeDOperation.VALIDATE,
                source=deformed.output_artifact_ref,
                source_path="creature-deformed.blend",
                output_path="creature-validation.json",
                output_role="3d.validation",
                output_media_type="application/json",
                requirements=ThreeDValidationRequirements(
                    require_skeleton=True,
                    require_rig=True,
                    require_skin=True,
                    require_deformation=True,
                    require_normalized_weights=True,
                    maximum_weight_influences=2,
                ),
            ),
            skeleton_spec=skeleton,
        ),
        idempotency_key="character-validate",
    )
    assert validated.technical_valid is True
    report = support._report(env, validated)
    inspection = report["inspection"]
    assert inspection["skeleton_count"] == 1
    assert inspection["bone_count"] == 5
    assert inspection["deformation"]["posed_bones"] >= 1
    assert inspection["skin"]["nonfinite_weights"] == 0
    assert inspection["skin"]["nonnormalized_vertices"] == 0
    preview = env.adapter.preview(
        env.access,
        env.attempt,
        support._request(
            env,
            ThreeDOperation.PREVIEW,
            source=deformed.output_artifact_ref,
            source_path="creature-deformed.blend",
            output_path="creature-preview.png",
            output_role="3d.preview",
            output_media_type="image/png",
            config={"resolution": 64, "samples": 1},
        ),
        idempotency_key="character-preview",
    )
    assert preview.preview_only and preview.output_content_ref is not None
    exported = env.adapter.export(
        env.access,
        env.attempt,
        support._request(
            env,
            ThreeDOperation.CONVERT,
            source=deformed.output_artifact_ref,
            source_path="creature-deformed.blend",
            output_path="creature.glb",
            output_role="3d.interchange-export",
            output_media_type="model/gltf-binary",
        ),
        idempotency_key="character-export",
    )
    assert exported.output_content_ref is not None
    reopened = env.adapter.inspectAsset(
        env.access,
        env.attempt,
        support._request(
            env,
            ThreeDOperation.INSPECT,
            source=exported.output_artifact_ref,
            source_path="creature.glb",
            output_path="creature-export-inspection.json",
            output_role="3d.inspection",
            output_media_type="application/json",
        ),
        idempotency_key="character-export-reopen",
    )
    assert support._report(env, reopened)["inspection"]["source_format"] == "GLTF"
    replayed = type(env.adapter)(env.database, env.objects).executeOperation(
        env.access, env.attempt, deform_request, idempotency_key="character-deform"
    )
    assert replayed == deformed
    assert replayed.output_artifact_ref == deformed.output_artifact_ref
    assert replayed.output_content_ref == deformed.output_content_ref
    with sqlite3.connect(env.database) as connection:
        publication_count = connection.execute(
            "SELECT COUNT(*) FROM three_d_operation_results "
            "WHERE project_id=? AND adapter_ref=? AND record_sha256=?",
            (
                env.access.project_ref.value,
                deformed.adapter_ref,
                deformed.record_sha256,
            ),
        ).fetchone()
    assert publication_count == (1,)
    limited = env.adapter.validate(
        env.access,
        env.attempt,
        replace(
            support._request(
                env,
                ThreeDOperation.VALIDATE,
                source=deformed.output_artifact_ref,
                source_path="creature-deformed.blend",
                output_path="creature-weight-limit.json",
                output_role="3d.validation",
                output_media_type="application/json",
                requirements=ThreeDValidationRequirements(maximum_weight_influences=1),
            ),
            skeleton_spec=skeleton,
        ),
        idempotency_key="character-weight-limit",
    )
    assert limited.technical_valid is False
    alternate_mesh = env.adapter.createAsset(
        env.access,
        env.attempt,
        support._request(
            env,
            ThreeDOperation.MODEL,
            source=None,
            source_path=None,
            output_path="creature-mesh-v2.blend",
            output_role="3d.mesh",
            output_media_type="application/x-blender",
            config={"name": "CreatureMeshV2", "scale": 1.5, "unit_system": "METRIC"},
        ),
        idempotency_key="character-mesh-v2",
    )
    assert alternate_mesh.output_artifact_ref is not None
    with pytest.raises(ThreeDConflictError):
        env.adapter.executeOperation(
            env.access,
            env.attempt,
            replace(
                rig_request,
                source_artifact_refs=(alternate_mesh.output_artifact_ref,),
                source_path="creature-mesh-v2.blend",
                output_path="creature-rig-v2.blend",
            ),
            idempotency_key="character-rig",
        )
    changed_skeleton = ThreeDSkeletonSpec(
        coordinate_system="BLENDER_Z_UP_RIGHT_HANDED",
        bones=skeleton.bones
        + (ThreeDBoneSpec("ear", "spine", (0.0, 0.0, 1.5), (0.0, 0.2, 1.8)),),
    )
    with pytest.raises(ThreeDConflictError):
        env.adapter.executeOperation(
            env.access,
            env.attempt,
            replace(rig_request, skeleton_spec=changed_skeleton, output_path="creature-rig-v3.blend"),
            idempotency_key="character-rig",
        )


def test_worker_loss_after_character_process_replays_one_real_rig_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches recovery that reruns Blender or loses native rig evidence after its process succeeds."""

    support = _p3_05_support()
    env = support._environment(tmp_path)
    skeleton = _quadruped_skeleton()
    mesh = env.adapter.createAsset(
        env.access,
        env.attempt,
        support._request(
            env,
            ThreeDOperation.MODEL,
            source=None,
            source_path=None,
            output_path="worker-loss-mesh.blend",
            output_role="3d.mesh",
            output_media_type="application/x-blender",
            config={"name": "WorkerLossMesh", "unit_system": "METRIC"},
        ),
        idempotency_key="worker-loss-mesh",
    )
    assert mesh.output_artifact_ref is not None
    rig = env.adapter.executeOperation(
        env.access,
        env.attempt,
        replace(
            support._request(
                env,
                ThreeDOperation.MESH_EDIT,
                source=mesh.output_artifact_ref,
                source_path="worker-loss-mesh.blend",
                output_path="worker-loss-rig.blend",
                output_role="3d.mesh",
                output_media_type="application/x-blender",
            ),
            operation=ThreeDOperation.RIG,
            output_role="3d.rig",
            skeleton_spec=skeleton,
        ),
        idempotency_key="worker-loss-rig",
    )
    assert rig.output_artifact_ref is not None
    skin = env.adapter.executeOperation(
        env.access,
        env.attempt,
        replace(
            support._request(
                env,
                ThreeDOperation.MESH_EDIT,
                source=rig.output_artifact_ref,
                source_path="worker-loss-rig.blend",
                output_path="worker-loss-skin.blend",
                output_role="3d.mesh",
                output_media_type="application/x-blender",
            ),
            operation=ThreeDOperation.SKIN,
            output_role="3d.skin",
            skeleton_spec=skeleton,
        ),
        idempotency_key="worker-loss-skin",
    )
    assert skin.output_artifact_ref is not None
    deform_request = replace(
        support._request(
            env,
            ThreeDOperation.MESH_EDIT,
            source=skin.output_artifact_ref,
            source_path="worker-loss-skin.blend",
            output_path="worker-loss-deformed.blend",
            output_role="3d.mesh",
            output_media_type="application/x-blender",
            config={"pose_degrees": 20.0},
        ),
        operation=ThreeDOperation.DEFORM,
        output_role="3d.deformation",
        skeleton_spec=skeleton,
    )

    def counts() -> tuple[int, int, int, int, int]:
        with sqlite3.connect(env.database) as connection:
            return (
                int(connection.execute("SELECT COUNT(*) FROM managed_process_executions").fetchone()[0]),
                int(connection.execute("SELECT COUNT(*) FROM managed_process_results").fetchone()[0]),
                int(connection.execute("SELECT COUNT(*) FROM three_d_operation_inflight").fetchone()[0]),
                int(connection.execute("SELECT COUNT(*) FROM three_d_operation_results").fetchone()[0]),
                int(connection.execute("SELECT COUNT(*) FROM three_d_output_publications").fetchone()[0]),
            )

    before_fault = counts()
    fault_adapter = type(env.adapter)(env.database, env.objects)

    def fail_after_process(*args: object, **kwargs: object) -> object:
        raise RuntimeError("character worker lost after durable process")

    monkeypatch.setattr(fault_adapter._service, "_persist", fail_after_process)
    with pytest.raises(RuntimeError, match="worker lost after durable process"):
        fault_adapter.executeOperation(
            env.access,
            env.attempt,
            deform_request,
            idempotency_key="worker-loss-deform",
        )
    after_fault = counts()
    assert after_fault[:2] == (before_fault[0] + 1, before_fault[1] + 1)
    assert after_fault[2:] == (before_fault[2] + 1, before_fault[3], before_fault[4])

    recovered_adapter = type(env.adapter)(env.database, env.objects)
    recovered = recovered_adapter.executeOperation(
        env.access,
        env.attempt,
        deform_request,
        idempotency_key="worker-loss-deform",
    )
    assert recovered.editable_source and recovered.output_artifact_ref is not None
    assert recovered.output_content_ref is not None
    recovered_report = support._report(env, recovered)
    assert recovered_report["character_identity"]["skeleton_sha256"] == skeleton.semantic_digest
    assert recovered_report["inspection"]["skeleton_count"] == 1
    assert recovered_report["inspection"]["bone_count"] == len(skeleton.bones)
    after_recovery = counts()
    assert after_recovery[:2] == after_fault[:2]
    assert after_recovery[2:] == (before_fault[2], before_fault[3] + 1, before_fault[4] + 1)
    replayed = type(env.adapter)(env.database, env.objects).executeOperation(
        env.access,
        env.attempt,
        deform_request,
        idempotency_key="worker-loss-deform",
    )
    assert replayed == recovered
    assert counts() == after_recovery
    rig_ref = recovered_adapter.finalizeCharacterRigRef(
        env.access,
        recovered,
        _character_specification(env, mesh, skeleton),
    )
    assert rig_ref.rig_artifact_ref == recovered.output_artifact_ref.value
    assert rig_ref.rig_content_sha256 == recovered.output_content_ref.digest


def test_skeleton_and_skin_specs_reject_invalid_character_evidence() -> None:
    """Catches malformed hierarchy and forged/non-finite/non-normalized skin weights."""

    skeleton = _quadruped_skeleton()
    with pytest.raises(ThreeDContractError):
        ThreeDSkeletonSpec(
            coordinate_system="BLENDER_Z_UP_RIGHT_HANDED",
            bones=(ThreeDBoneSpec("only", "missing", (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),),
        )
    with pytest.raises(ThreeDContractError):
        ThreeDSkinBinding(0, (ThreeDSkinWeight("root", float("nan")),))
    with pytest.raises(ThreeDContractError):
        ThreeDSkinBinding(0, (ThreeDSkinWeight("root", 0.7), ThreeDSkinWeight("tail", 0.2)))
    with pytest.raises(ThreeDContractError):
        skeleton.validate_skin_bindings(
            (ThreeDSkinBinding(0, (ThreeDSkinWeight("unknown", 1.0),)),)
        )
