"""Real Blender animation evidence on the P3-06 character substrate."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import importlib.util
from pathlib import Path
import sqlite3
import sys
from threading import Barrier
from typing import Any

import pytest

from minitz_os.engine.animation_pack import AnimationContractError
from minitz_os.engine.character_pack import CharacterSpecification
from minitz_os.engine.three_d_tool import (
    ThreeDAnimationClipSpec,
    ThreeDAnimationKeyframe,
    ThreeDConflictError,
    ThreeDContractError,
    ThreeDOperation,
    ThreeDRetargetBoneMapping,
    ThreeDRetargetSpec,
    ThreeDRootMotionPolicy,
    ThreeDBoneSpec,
    ThreeDSkeletonSpec,
    ThreeDValidationRequirements,
)


def _support() -> Any:
    global _P3_05_SUPPORT
    if _P3_05_SUPPORT is not None:
        return _P3_05_SUPPORT
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location("p3_07_animation_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _P3_05_SUPPORT = module
    return module


_P3_05_SUPPORT: Any | None = None


def _source_skeleton() -> ThreeDSkeletonSpec:
    return ThreeDSkeletonSpec(
        coordinate_system="BLENDER_Z_UP_RIGHT_HANDED",
        bones=(
            ThreeDBoneSpec("root", None, (0.0, 0.0, 0.0), (0.0, 0.0, 0.8)),
            ThreeDBoneSpec("spine", "root", (0.0, 0.0, 0.8), (0.0, 0.0, 1.6)),
            ThreeDBoneSpec("tail", "root", (0.0, 0.0, 0.5), (0.0, -1.0, 0.8)),
        ),
    )


def _target_skeleton() -> ThreeDSkeletonSpec:
    return ThreeDSkeletonSpec(
        coordinate_system="BLENDER_Z_UP_RIGHT_HANDED",
        bones=(
            ThreeDBoneSpec("target-root", None, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
            ThreeDBoneSpec("target-spine", "target-root", (0.0, 0.0, 1.0), (0.0, 0.0, 1.9)),
            ThreeDBoneSpec("target-tail", "target-root", (0.0, 0.0, 0.6), (0.0, -1.2, 1.0)),
        ),
    )


def _clip(
    clip_id: str,
    skeleton: ThreeDSkeletonSpec,
    *,
    blend_with_clip_id: str | None = None,
    blend_factor: float = 0.0,
) -> ThreeDAnimationClipSpec:
    return ThreeDAnimationClipSpec(
        clip_id=clip_id,
        source_skeleton_sha256=skeleton.semantic_digest,
        keyframes=(
            ThreeDAnimationKeyframe("root", 1.0, (0.0, 0.0, 0.0)),
            ThreeDAnimationKeyframe("spine", 1.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            ThreeDAnimationKeyframe("root", 12.0, (0.0, 0.0, 0.0)),
            ThreeDAnimationKeyframe("spine", 12.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ),
        loop_tolerance=0.0001,
        blend_with_clip_id=blend_with_clip_id,
        blend_factor=blend_factor,
    )


def _rigged_character(env: Any, skeleton: ThreeDSkeletonSpec, prefix: str) -> tuple[Any, Any]:
    mesh = env.adapter.createAsset(
        env.access,
        env.attempt,
        _support()._request(
            env,
            ThreeDOperation.MODEL,
            source=None,
            source_path=None,
            output_path=f"{prefix}-mesh.blend",
            output_role="3d.mesh",
            output_media_type="application/x-blender",
            config={"name": "AnimationMesh", "unit_system": "METRIC"},
        ),
        idempotency_key=f"{prefix}-mesh",
    )
    assert mesh.output_artifact_ref is not None
    rig = env.adapter.executeOperation(
        env.access,
        env.attempt,
        replace(
            _support()._request(
                env,
                ThreeDOperation.MESH_EDIT,
                source=mesh.output_artifact_ref,
                source_path=f"{prefix}-mesh.blend",
                output_path=f"{prefix}-rig.blend",
                output_role="3d.mesh",
                output_media_type="application/x-blender",
            ),
            operation=ThreeDOperation.RIG,
            output_role="3d.rig",
            skeleton_spec=skeleton,
        ),
        idempotency_key=f"{prefix}-rig",
    )
    assert rig.output_artifact_ref is not None
    skin = env.adapter.executeOperation(
        env.access,
        env.attempt,
        replace(
            _support()._request(
                env,
                ThreeDOperation.MESH_EDIT,
                source=rig.output_artifact_ref,
                source_path=f"{prefix}-rig.blend",
                output_path=f"{prefix}-skin.blend",
                output_role="3d.mesh",
                output_media_type="application/x-blender",
            ),
            operation=ThreeDOperation.SKIN,
            output_role="3d.skin",
            skeleton_spec=skeleton,
        ),
        idempotency_key=f"{prefix}-skin",
    )
    assert skin.output_artifact_ref is not None
    return mesh, skin


def _character_specification(env: Any, mesh: Any, skeleton: ThreeDSkeletonSpec, character_id: str) -> CharacterSpecification:
    return CharacterSpecification(
        project_ref=env.access.project_ref,
        character_id=character_id,
        character_artifact_ref=mesh.output_artifact_ref.value,
        character_content_sha256=mesh.output_content_ref.digest,
        mesh_ref=mesh.output_artifact_ref.value,
        mesh_content_sha256=mesh.output_content_ref.digest,
        skeleton_ref=f"skeleton://character/{character_id}/{skeleton.semantic_digest}",
        skeleton_content_sha256=skeleton.semantic_digest,
        scale=(1.0, 1.0, 1.0),
        coordinate_system={"handedness": "RIGHT", "up": "Z"},
        coordinate_convention_ref="coordinate://blender/z-up-right-handed",
        rest_pose_ref=f"rest-pose://character/{character_id}/{skeleton.semantic_digest}",
        provenance_ref=f"provenance://character/{character_id}/{mesh.output_content_ref.digest}",
        visual_reference_refs=(f"reference://character/{character_id}/visual",),
        geometry_topology_refs=(f"topology://character/{character_id}/mesh",),
        skeleton_rig_refs=(f"rig-source://character/{character_id}/skeleton",),
        material_binding_refs=(f"material://character/{character_id}/default",),
        target_constraint_refs=(f"constraint://character/{character_id}/default",),
        validation_contract_refs=(f"validation://character/{character_id}/default",),
        output_contract_refs=(f"output://character/{character_id}/default",),
        target_metadata={"kind": "animation-test"},
    )


def _animation_request(
    env: Any,
    operation: ThreeDOperation,
    source: Any,
    source_path: str,
    output_path: str,
    skeleton: ThreeDSkeletonSpec,
    clip: ThreeDAnimationClipSpec,
    *,
    retarget: ThreeDRetargetSpec | None = None,
    root_motion: ThreeDRootMotionPolicy = ThreeDRootMotionPolicy.PRESERVE,
) -> Any:
    return replace(
        _support()._request(
            env,
            ThreeDOperation.MESH_EDIT,
            source=source,
            source_path=source_path,
            output_path=output_path,
            output_role="3d.mesh",
            output_media_type="application/x-blender",
        ),
        operation=operation,
        output_role="3d.animation",
        skeleton_spec=skeleton,
        animation_clip_spec=clip,
        retarget_spec=retarget,
        root_motion_policy=root_motion,
    )


def _animation_evidence(
    report: dict[str, object],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    inspection = report.get("inspection")
    assert isinstance(inspection, dict)
    animation = inspection.get("animation")
    assert isinstance(animation, dict)
    actions = animation.get("actions")
    assert isinstance(actions, list)
    assert all(isinstance(item, dict) for item in actions)
    return animation, tuple(item for item in actions if isinstance(item, dict))


def _exact_action(
    actions: tuple[dict[str, Any], ...],
    clip_sha256: str,
    *,
    retarget_sha256: str | None = None,
) -> dict[str, Any]:
    matches = tuple(
        item
        for item in actions
        if item.get("clip_sha256") == clip_sha256
        and item.get("retarget_sha256") == retarget_sha256
    )
    assert len(matches) == 1
    return matches[0]


def test_real_animation_actions_retarget_bake_preview_export_and_reopen(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    source_skeleton = _source_skeleton()
    target_skeleton = _target_skeleton()
    source_mesh, skin = _rigged_character(env, source_skeleton, "animation-source")
    target_mesh, target_skin = _rigged_character(env, target_skeleton, "animation-target")
    source_rig = env.adapter.finalizeCharacterRigRef(
        env.access, skin, _character_specification(env, source_mesh, source_skeleton, "animation-source")
    )
    target_rig = env.adapter.finalizeCharacterRigRef(
        env.access, target_skin, _character_specification(env, target_mesh, target_skeleton, "animation-target")
    )
    walk = _clip("walk", source_skeleton)
    walk_request = _animation_request(
        env, ThreeDOperation.ANIMATE, skin.output_artifact_ref, "animation-source-skin.blend",
        "walk.blend", source_skeleton, walk,
    )
    with pytest.raises(ThreeDContractError):
        replace(walk_request, skeleton_spec=target_skeleton)
    animated = env.adapter.executeOperation(
        env.access, env.attempt, walk_request, idempotency_key="animation-walk"
    )
    assert animated.editable_source and animated.output_artifact_ref is not None
    walk_handoff = env.adapter.finalizeAnimationClip(
        env.access, walk_request, animated, source_rig, clip_id="walk"
    )
    assert walk_handoff.source_artifact_ref == animated.output_artifact_ref.value
    blended = _clip("turn", source_skeleton, blend_with_clip_id="walk", blend_factor=0.5)
    blended_request = _animation_request(
        env, ThreeDOperation.ANIMATE, animated.output_artifact_ref, "walk.blend",
        "turn.blend", source_skeleton, blended, root_motion=ThreeDRootMotionPolicy.EXTRACT,
    )
    turned = env.adapter.executeOperation(
        env.access, env.attempt, blended_request, idempotency_key="animation-turn"
    )
    assert turned.editable_source and turned.output_artifact_ref is not None
    baked_clip = _clip("turn-baked", source_skeleton)
    baked = env.adapter.executeOperation(
        env.access,
        env.attempt,
        _animation_request(
            env, ThreeDOperation.BAKE, turned.output_artifact_ref, "turn.blend",
            "turn-baked.blend", source_skeleton, baked_clip,
            root_motion=ThreeDRootMotionPolicy.REMOVE,
        ),
        idempotency_key="animation-bake",
    )
    assert baked.output_artifact_ref is not None
    mapping = ThreeDRetargetSpec(
        source_skeleton_spec=source_skeleton,
        target_skeleton_sha256=target_skeleton.semantic_digest,
        mappings=(
            ThreeDRetargetBoneMapping("root", "target-root"),
            ThreeDRetargetBoneMapping("spine", "target-spine"),
            ThreeDRetargetBoneMapping("tail", "target-tail"),
        ),
    )
    with pytest.raises(ThreeDContractError):
        _animation_request(
            env, ThreeDOperation.RETARGET, turned.output_artifact_ref, "turn.blend",
            "turn-retarget-invalid.blend", target_skeleton, blended,
            retarget=replace(mapping, mappings=(ThreeDRetargetBoneMapping("root", "target-root"),)),
        )
    retargeted = env.adapter.executeOperation(
        env.access,
        env.attempt,
        _animation_request(
            env, ThreeDOperation.RETARGET, turned.output_artifact_ref, "turn.blend",
            "turn-retargeted.blend", target_skeleton, blended, retarget=mapping,
        ),
        idempotency_key="animation-retarget",
    )
    assert retargeted.editable_source and retargeted.output_artifact_ref is not None
    retarget_request = _animation_request(
        env, ThreeDOperation.RETARGET, turned.output_artifact_ref, "turn.blend",
        "turn-retargeted.blend", target_skeleton, blended, retarget=mapping,
    )
    finalized_mapping = env.adapter.finalizeRetargetMapping(
        env.access, retarget_request, retargeted, source_rig, target_rig,
        mapping_id="source-to-target", mapping_version="1.0.0",
    )
    replayed_mapping = type(env.adapter)(env.database, env.objects).finalizeRetargetMapping(
        env.access, retarget_request, retargeted, source_rig, target_rig,
        mapping_id="source-to-target", mapping_version="1.0.0",
    )
    assert replayed_mapping == finalized_mapping
    finalized_retarget = env.adapter.finalizeAnimationClip(
        env.access, retarget_request, retargeted, target_rig,
        clip_id="turn-retargeted", mapping=finalized_mapping,
    )
    assert finalized_mapping.source_rig_ref == source_rig
    assert finalized_retarget.character_rig_ref == target_rig
    with pytest.raises(AnimationContractError):
        env.adapter.finalizeAnimationClip(
            env.access, retarget_request, retargeted, target_rig,
            clip_id="turn-forged-content",
            mapping=replace(finalized_mapping, content_sha256="0" * 64),
        )
    with pytest.raises(AnimationContractError):
        env.adapter.finalizeAnimationClip(
            env.access, retarget_request, retargeted, target_rig,
            clip_id="turn-forged-ref",
            mapping=replace(finalized_mapping, mapping_ref=target_rig.rig_artifact_ref),
        )
    with pytest.raises(AnimationContractError):
        env.adapter.finalizeAnimationClip(
            env.access, walk_request, animated,
            replace(source_rig, skeleton_content_sha256=target_skeleton.semantic_digest),
            clip_id="walk-stale-rig",
        )
    retarget_report = support._report(env, retargeted)
    assert retarget_report["animation_identity"]["retarget_sha256"] == mapping.semantic_digest
    retarget_animation, retarget_actions = _animation_evidence(retarget_report)
    assert retarget_animation["action_count"] == len(retarget_actions)
    walk_action = _exact_action(retarget_actions, walk.semantic_digest)
    turn_action = _exact_action(retarget_actions, blended.semantic_digest)
    retarget_action = _exact_action(
        retarget_actions,
        blended.semantic_digest,
        retarget_sha256=mapping.semantic_digest,
    )
    baked_report = support._report(env, baked)
    baked_animation, baked_actions = _animation_evidence(baked_report)
    baked_action = _exact_action(baked_actions, baked_clip.semantic_digest)
    validated = env.adapter.validate(
        env.access,
        env.attempt,
        replace(
            support._request(
                env,
                ThreeDOperation.VALIDATE,
                source=baked.output_artifact_ref,
                source_path="turn-baked.blend",
                output_path="animation-validation.json",
                output_role="3d.validation",
                output_media_type="application/json",
                requirements=ThreeDValidationRequirements(
                    require_animation=True,
                    require_baked_animation=True,
                    require_loop=True,
                    maximum_loop_error=0.0001,
                ),
            ),
            skeleton_spec=source_skeleton,
        ),
        idempotency_key="animation-validate",
    )
    assert validated.technical_valid is True
    preview = env.adapter.preview(
        env.access,
        env.attempt,
        support._request(
            env, ThreeDOperation.PREVIEW, source=baked.output_artifact_ref,
            source_path="turn-baked.blend", output_path="animation-preview.png",
            output_role="3d.preview", output_media_type="image/png",
            config={"resolution": 64, "samples": 1},
        ),
        idempotency_key="animation-preview",
    )
    assert preview.preview_only
    exported = env.adapter.export(
        env.access,
        env.attempt,
        support._request(
            env, ThreeDOperation.CONVERT, source=baked.output_artifact_ref,
            source_path="turn-baked.blend", output_path="animation.glb",
            output_role="3d.interchange-export", output_media_type="model/gltf-binary",
        ),
        idempotency_key="animation-export",
    )
    reopened = env.adapter.inspectAsset(
        env.access,
        env.attempt,
        support._request(
            env, ThreeDOperation.INSPECT, source=exported.output_artifact_ref,
            source_path="animation.glb", output_path="animation-reopen.json",
            output_role="3d.inspection", output_media_type="application/json",
        ),
        idempotency_key="animation-reopen",
    )
    reopened_report = support._report(env, reopened)
    reopened_inspection = reopened_report["inspection"]
    assert isinstance(reopened_inspection, dict)
    assert reopened_inspection["source_format"] == "GLTF"
    reopened_animation, reopened_actions = _animation_evidence(reopened_report)
    reopened_baked = tuple(
        (
            item.get("clip_id"),
            item.get("start_frame"),
            item.get("end_frame"),
            item.get("source_fcurve_count"),
            item.get("source_keyframe_count"),
        )
        for item in reopened_actions
        if item.get("clip_id") == baked_clip.clip_id
    )
    assert all(
        int(item["fcurve_count"]) >= int(item["source_fcurve_count"])
        and int(item["keyframe_count"]) >= int(item["source_keyframe_count"])
        for item in reopened_actions
    )

    exact_action_evidence = (
        (walk_action, walk.clip_id, walk.semantic_digest),
        (turn_action, blended.clip_id, blended.semantic_digest),
        (retarget_action, blended.clip_id, blended.semantic_digest),
        (baked_action, baked_clip.clip_id, baked_clip.semantic_digest),
    )
    animation_kpis = {
        "exact_clip_action_keyframe_mismatches": sum(
            int(
                (
                    item["clip_id"],
                    item["clip_sha256"],
                    item["start_frame"],
                    item["end_frame"],
                    item["fcurve_count"],
                    item["keyframe_count"],
                )
                != (clip_id, clip_sha256, 1.0, 12.0, 36, 72)
            )
            for item, clip_id, clip_sha256 in exact_action_evidence
        ),
        "retarget_mapping_mismatches": int(
            retarget_report["animation_identity"]["retarget_sha256"]
            != mapping.semantic_digest
        )
        + int(retarget_action["retarget_sha256"] != mapping.semantic_digest),
        "root_motion_loop_bake_failures": sum(
            (
                int(turn_action["root_motion_policy"] != "extract"),
                int(retarget_action["root_motion_policy"] != "preserve"),
                int(baked_action["root_motion_policy"] != "remove"),
                int(baked_action["baked"] is not True),
                int(
                    float(baked_animation["maximum_loop_error"])
                    > baked_clip.loop_tolerance
                ),
                int(validated.technical_valid is not True),
            )
        ),
        "export_reopen_failures": int(
            reopened_inspection["source_format"] != "GLTF"
        )
        + int(reopened_animation["action_count"] < 1)
            + int(
                reopened_baked
                != ((baked_clip.clip_id, 1.0, 12.0, 18, 36),)
            ),
    }
    assert animation_kpis["exact_clip_action_keyframe_mismatches"] == 0
    assert animation_kpis["retarget_mapping_mismatches"] == 0
    assert animation_kpis["root_motion_loop_bake_failures"] == 0
    assert animation_kpis["export_reopen_failures"] == 0
    with pytest.raises(ThreeDConflictError):
        env.adapter.executeOperation(
            env.access,
            env.attempt,
            replace(walk_request, animation_clip_spec=replace(walk, clip_id="walk-stale")),
            idempotency_key="animation-walk",
        )


def test_animation_specs_reject_nonfinite_transforms() -> None:
    source = _source_skeleton()
    with pytest.raises(ThreeDContractError):
        ThreeDAnimationKeyframe("root", float("nan"))
    with pytest.raises(ThreeDContractError):
        ThreeDAnimationKeyframe("root", 1.0, scale=(1.0, float("inf"), 1.0))
    assert _clip("finite", source).semantic_digest


def test_independent_animation_worker_failure_recovers_without_erasing_peer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    support = _support()
    success_env, failed_env = support._environments(tmp_path, count=2)
    assert success_env.database == failed_env.database
    assert success_env.objects is failed_env.objects
    assert success_env.access == failed_env.access
    assert success_env.attempt.node_ref != failed_env.attempt.node_ref
    assert success_env.attempt.attempt_id != failed_env.attempt.attempt_id
    assert success_env.allocation_ref != failed_env.allocation_ref
    skeleton = _source_skeleton()
    _, skin = _rigged_character(success_env, skeleton, "animation-peer")
    _, failed_skin = _rigged_character(
        failed_env,
        skeleton,
        "animation-failed-peer",
    )
    success_clip = _clip("peer-success", skeleton)
    failed_clip = _clip("peer-recover", skeleton)
    success_request = _animation_request(
        success_env, ThreeDOperation.ANIMATE, skin.output_artifact_ref, "animation-peer-skin.blend",
        "peer-success.blend", skeleton, success_clip,
    )
    failed_request = _animation_request(
        failed_env, ThreeDOperation.ANIMATE, failed_skin.output_artifact_ref, "animation-failed-peer-skin.blend",
        "peer-recover.blend", skeleton, failed_clip,
    )
    assert success_request.resource_allocation_ref == success_env.allocation_ref
    assert failed_request.resource_allocation_ref == failed_env.allocation_ref
    fault_adapter = type(failed_env.adapter)(failed_env.database, failed_env.objects)
    success_adapter = type(success_env.adapter)(success_env.database, success_env.objects)
    persistence_barrier = Barrier(2)
    original_success_persist = success_adapter._service._persist

    def persist_success(*args: object, **kwargs: object) -> object:
        persistence_barrier.wait(timeout=60)
        return original_success_persist(*args, **kwargs)

    def fail_after_process(*args: object, **kwargs: object) -> object:
        persistence_barrier.wait(timeout=60)
        raise RuntimeError("animation worker loss after durable process")

    monkeypatch.setattr(success_adapter._service, "_persist", persist_success)
    monkeypatch.setattr(fault_adapter._service, "_persist", fail_after_process)
    with ThreadPoolExecutor(max_workers=2) as executor:
        peer = executor.submit(
            success_adapter.executeOperation,
            success_env.access, success_env.attempt, success_request, idempotency_key="animation-peer-success",
        )
        failed = executor.submit(
            fault_adapter.executeOperation,
            failed_env.access, failed_env.attempt, failed_request, idempotency_key="animation-peer-recover",
        )
        peer_result = peer.result()
        with pytest.raises(RuntimeError, match="worker loss after durable process"):
            failed.result()
    assert peer_result.output_artifact_ref is not None
    peer_artifact_ref = peer_result.output_artifact_ref
    peer_content_ref = peer_result.output_content_ref
    peer_bytes_after_failure = success_env.objects.read(peer_content_ref)
    peer_report_after_failure = support._report(success_env, peer_result)
    _, peer_actions_after_failure = _animation_evidence(peer_report_after_failure)
    peer_action = _exact_action(peer_actions_after_failure, success_clip.semantic_digest)
    assert (
        peer_action["clip_id"],
        peer_action["start_frame"],
        peer_action["end_frame"],
        peer_action["fcurve_count"],
        peer_action["keyframe_count"],
    ) == (success_clip.clip_id, 1.0, 12.0, 36, 72)
    failed_process_key = f"three-d-blender-{failed_request.request_sha256[:36]}"
    with sqlite3.connect(failed_env.database) as connection:
        assert tuple(
            int(connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE call_id=("
                "SELECT call_id FROM managed_process_claims WHERE idempotency_key=?)",
                (failed_process_key,),
            ).fetchone()[0])
            for table in (
                "managed_process_claims",
                "managed_process_prepared_executions",
                "managed_process_executions",
                "managed_process_results",
            )
        ) == (1, 1, 1, 1)
    recovered_adapter = type(failed_env.adapter)(failed_env.database, failed_env.objects)
    recovered = recovered_adapter.executeOperation(
        failed_env.access, failed_env.attempt, failed_request, idempotency_key="animation-peer-recover",
    )
    assert recovered.editable_source and recovered.output_artifact_ref is not None
    replayed = type(failed_env.adapter)(failed_env.database, failed_env.objects).executeOperation(
        failed_env.access, failed_env.attempt, failed_request, idempotency_key="animation-peer-recover",
    )
    assert replayed == recovered
    recovered_report = support._report(failed_env, recovered)
    _, recovered_actions = _animation_evidence(recovered_report)
    recovered_action = _exact_action(recovered_actions, failed_clip.semantic_digest)
    assert (
        recovered_action["clip_id"],
        recovered_action["start_frame"],
        recovered_action["end_frame"],
        recovered_action["fcurve_count"],
        recovered_action["keyframe_count"],
    ) == (failed_clip.clip_id, 1.0, 12.0, 36, 72)
    peer_bytes_after_recovery = failed_env.objects.read(peer_content_ref)
    peer_report_after_recovery = support._report(failed_env, peer_result)
    independent_clip_artifact_losses = int(
        peer_result.output_artifact_ref != peer_artifact_ref
        or peer_result.output_content_ref != peer_content_ref
        or peer_bytes_after_recovery != peer_bytes_after_failure
        or peer_report_after_recovery != peer_report_after_failure
    )
    assert independent_clip_artifact_losses == 0
    with sqlite3.connect(failed_env.database) as connection:
        assert tuple(
            int(connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE call_id=("
                "SELECT call_id FROM managed_process_claims WHERE idempotency_key=?)",
                (failed_process_key,),
            ).fetchone()[0])
            for table in (
                "managed_process_claims",
                "managed_process_prepared_executions",
                "managed_process_executions",
                "managed_process_results",
            )
        ) == (1, 1, 1, 1)
