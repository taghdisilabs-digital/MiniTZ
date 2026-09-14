from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sqlite3

import pytest

from minitz_os.engine.artifact import Artifact, ArtifactService, ContentRef
from minitz_os.engine.project import ProjectAccess, ProjectRef, ProjectStore
from minitz_os.engine.run import RunService
from minitz_os.engine.task import TaskRevisionService
from minitz_os.engine.vfx_pack import SimulationCheckpointRef, SimulationSpecification
from minitz_os.engine.vfx_recovery import (
    SimulationRecoveryContractError,
    SimulationResourceRecoveryPlan,
    VerifiedSimulationSegment,
    plan_resource_exhaustion_recovery,
    plan_verified_resource_exhaustion_recovery,
)

SPEC = "a" * 64


def test_enospc_recovery_for_1_300_preserves_1_200_and_dispatches_only_201_300() -> None:
    plan = plan_resource_exhaustion_recovery(
        specification_digest=SPEC,
        frame_start=1,
        frame_end=300,
        failed_frame=237,
        failure_reason="ENOSPC: no space left on device while writing frame 237 cache",
        verified_segments=(
            VerifiedSimulationSegment(SPEC, 1, 100, "artifact://p/checkpoint-100/1", "b" * 64, "natt_" + "1" * 32, 1),
            VerifiedSimulationSegment(SPEC, 101, 200, "artifact://p/checkpoint-200/1", "c" * 64, "natt_" + "2" * 32, 1),
        ),
        dispatchable_frames=range(201, 301),
    )

    assert plan.failure_classification == "RESOURCE_EXHAUSTED"
    assert plan.failure_reason == "ENOSPC: no space left on device while writing frame 237 cache"
    assert plan.preserved_segments == ((1, 100), (101, 200))
    assert plan.latest_verified_frame == 200
    assert plan.resume_frame_start == 201
    assert plan.resume_frame_end == 300
    assert plan.frames_to_dispatch == tuple(range(201, 301))
    assert plan.frames_to_recompute == ()
    assert plan.cache_authority == "REBUILDABLE_ONLY"
    assert plan.requires_spec_checkpoint_content_verification


def test_enospc_recovery_fails_closed_on_gaps_in_verified_prefix() -> None:
    with pytest.raises(SimulationRecoveryContractError, match="continuous verified prefix"):
        plan_resource_exhaustion_recovery(
            specification_digest=SPEC,
            frame_start=1,
            frame_end=300,
            failed_frame=237,
            failure_reason="disk full",
            verified_segments=(
                VerifiedSimulationSegment(SPEC, 1, 100, "artifact://p/checkpoint-100/1", "b" * 64, "natt_" + "1" * 32, 1),
                VerifiedSimulationSegment(SPEC, 150, 200, "artifact://p/checkpoint-200/1", "c" * 64, "natt_" + "2" * 32, 1),
            ),
            dispatchable_frames=range(201, 301),
        )


def test_enospc_recovery_rejects_redispatch_of_verified_frames() -> None:
    with pytest.raises(SimulationRecoveryContractError, match="must not include already verified frames"):
        plan_resource_exhaustion_recovery(
            specification_digest=SPEC,
            frame_start=1,
            frame_end=300,
            failed_frame=237,
            failure_reason="No space left on device",
            verified_segments=(
                VerifiedSimulationSegment(SPEC, 1, 100, "artifact://p/checkpoint-100/1", "b" * 64, "natt_" + "1" * 32, 1),
                VerifiedSimulationSegment(SPEC, 101, 200, "artifact://p/checkpoint-200/1", "c" * 64, "natt_" + "2" * 32, 1),
            ),
            dispatchable_frames=range(1, 301),
        )


def test_enospc_recovery_rejects_non_resource_failure_reason() -> None:
    with pytest.raises(SimulationRecoveryContractError, match="resource exhaustion"):
        plan_resource_exhaustion_recovery(
            specification_digest=SPEC,
            frame_start=1,
            frame_end=300,
            failed_frame=237,
            failure_reason="operator cancelled",
            verified_segments=(
                VerifiedSimulationSegment(SPEC, 1, 100, "artifact://p/checkpoint-100/1", "b" * 64, "natt_" + "1" * 32, 1),
            ),
            dispatchable_frames=range(101, 301),
        )


def test_enospc_recovery_rejects_one_producer_attempt_under_multiple_fences() -> None:
    attempt = "natt_" + "1" * 32
    with pytest.raises(SimulationRecoveryContractError, match="attempt/fence is stale"):
        plan_resource_exhaustion_recovery(
            specification_digest=SPEC,
            frame_start=1,
            frame_end=300,
            failed_frame=237,
            failure_reason="ENOSPC: no space left on device",
            verified_segments=(
                VerifiedSimulationSegment(SPEC, 1, 100, "artifact://p/checkpoint-100/1", "b" * 64, attempt, 1),
                VerifiedSimulationSegment(SPEC, 101, 200, "artifact://p/checkpoint-200/1", "c" * 64, attempt, 2),
            ),
            dispatchable_frames=range(201, 301),
        )


def _source(artifacts: ArtifactService, access: ProjectAccess, role: str, payload: bytes) -> Artifact:
    content = ContentRef.from_bytes(payload, media_type="application/octet-stream")
    return artifacts.create_artifact(
        access,
        project_ref=access.project_ref,
        role=role,
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="test.source",
        metadata={"media_type": content.media_type},
    )


def _specification(
    project_ref: ProjectRef,
    sources: tuple[Artifact, Artifact, Artifact],
    *,
    tool_ref: str = "tool://vfx/authoritative/v1",
) -> SimulationSpecification:
    scene, geometry, animation = sources
    assert scene.content_ref is not None and geometry.content_ref is not None and animation.content_ref is not None
    return SimulationSpecification.create(
        project_ref,
        "sim-enospc-authoritative",
        scene.artifact_ref.value,
        scene.content_ref.digest,
        geometry.artifact_ref.value,
        geometry.content_ref.digest,
        animation.artifact_ref.value,
        animation.content_ref.digest,
        "fluid",
        "1.0.0",
        {"solver": "generic"},
        {"density": "1"},
        1,
        300,
        0.0,
        299.0,
        1.0,
        1,
        {"collision": "on"},
        {"force": "gravity"},
        ("artifact://output/v1",),
        ("d" * 64,),
        {"cache": "checkpointed"},
        {"renderer": "generic"},
        {"validation": "required"},
        {"resource": "project"},
        7,
        "generator://vfx/authoritative/v1",
        tool_ref,
        "runtime://vfx/authoritative/v1",
        "solver://vfx/authoritative/v1",
        "1.0.0",
        "deterministic",
    )


def _authority(
    tmp_path: Path,
    *,
    second_has_predecessor: bool = True,
) -> tuple[
    Path,
    ArtifactService,
    ProjectAccess,
    SimulationSpecification,
    tuple[SimulationCheckpointRef, SimulationCheckpointRef],
    tuple[Artifact, Artifact, Artifact],
]:
    database = tmp_path / "p3-10-authority.sqlite3"
    registration = ProjectStore(database).create_project(namespace="p3-10-authority", display_name="P3-10 Authority")
    access = registration.access
    artifacts = ArtifactService(database)
    sources = (
        _source(artifacts, access, "vfx.scene-source", b"scene"),
        _source(artifacts, access, "vfx.geometry-source", b"geometry"),
        _source(artifacts, access, "vfx.animation-source", b"animation"),
    )
    specification = _specification(access.project_ref, sources)
    task = TaskRevisionService(database).create_task(
        access,
        project_ref=access.project_ref,
        idempotency_key="p3-10-authority-task",
        task_type="vfx.recovery",
        objective="Verify exact VFX checkpoint recovery authority",
        required_capabilities=(),
        input_refs=(),
        output_contract={"checkpoint": "schema://minitz/vfx-checkpoint/1"},
        constraints={},
        side_effect_authority="PROJECT_WRITE",
        data_policy_ref=None,
        egress_policy_ref=None,
        evidence_requirements=("checkpoint-authority",),
        acceptance_criteria=("only verified suffix resumes",),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    attempt = runs.acquire_run_lease(access, run.run_ref, owner_ref="controller://p3-10-authority", lease_seconds=300)
    scene_content = sources[0].content_ref
    assert scene_content is not None
    first_content = ContentRef.from_bytes(b"checkpoint-100", media_type="application/x-blender")
    first_artifact = artifacts.publish_from_run(
        access,
        producer_attempt=attempt,
        expected_task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        role="vfx.checkpoint",
        content_ref=first_content,
        source_refs=(),
        source_artifact_refs=(sources[0].artifact_ref,),
        source_content_refs=(scene_content,),
        derivation_type="vfx.blender.segment",
        metadata={"media_type": first_content.media_type},
    )
    node_attempt = "natt_" + "1" * 32
    first = SimulationCheckpointRef.create(
        access.project_ref,
        specification,
        100,
        99.0,
        first_artifact.artifact_ref.value,
        first_content.digest,
        sources[0].artifact_ref.value,
        scene_content.digest,
        node_attempt,
        1,
        "2026-09-01T00:00:00+00:00",
    )
    second_content = ContentRef.from_bytes(b"checkpoint-200", media_type="application/x-blender")
    second_artifact = artifacts.publish_from_run(
        access,
        producer_attempt=attempt,
        expected_task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        role="vfx.checkpoint",
        content_ref=second_content,
        source_refs=(),
        source_artifact_refs=(first_artifact.artifact_ref,) if second_has_predecessor else (),
        source_content_refs=(first_content,) if second_has_predecessor else (),
        derivation_type="vfx.blender.segment",
        metadata={"media_type": second_content.media_type},
    )
    second = SimulationCheckpointRef.create(
        access.project_ref,
        specification,
        200,
        199.0,
        second_artifact.artifact_ref.value,
        second_content.digest,
        first_artifact.artifact_ref.value,
        first_content.digest,
        node_attempt,
        1,
        "2026-09-01T00:00:00+00:00",
    )
    return database, artifacts, access, specification, (first, second), sources


def _verified_plan(
    artifacts: ArtifactService,
    access: ProjectAccess,
    specification: SimulationSpecification,
    checkpoints: tuple[SimulationCheckpointRef, SimulationCheckpointRef],
) -> SimulationResourceRecoveryPlan:
    return plan_verified_resource_exhaustion_recovery(
        artifacts=artifacts,
        access=access,
        specification=specification,
        verified_checkpoints=checkpoints,
        failed_frame=237,
        failure_reason="ENOSPC: no space left on device while writing frame 237 cache",
        dispatchable_frames=range(201, 301),
    )


def test_authoritative_recovery_backs_preserved_ranges_with_exact_artifacts(tmp_path: Path) -> None:
    _, artifacts, access, specification, checkpoints, _ = _authority(tmp_path)
    plan = _verified_plan(artifacts, access, specification, checkpoints)

    assert plan.authority_verified
    assert plan.preserved_segments == ((1, 100), (101, 200))
    assert plan.failed_frame == 237
    assert plan.resume_frame_start == 201 and plan.resume_frame_end == 300
    assert plan.frames_to_dispatch == tuple(range(201, 301))
    assert plan.frames_to_recompute == ()
    assert plan.authoritative_checkpoint_artifact_refs == tuple(item.artifact_ref for item in checkpoints)
    assert len(plan.authoritative_checkpoint_content_refs) == 2
    assert len(plan.authoritative_checkpoint_record_sha256s) == 2
    assert plan.authoritative_checkpoint_node_producers == tuple((item.producer_attempt_id, item.producer_fence) for item in checkpoints)
    assert len(plan.authoritative_checkpoint_artifact_producers) == 2


def test_authoritative_recovery_rejects_forged_hash_role_and_cross_project(tmp_path: Path) -> None:
    database, artifacts, access, specification, checkpoints, sources = _authority(tmp_path)
    first, second = checkpoints
    forged_hash = SimulationCheckpointRef.create(
        access.project_ref,
        specification,
        first.frame,
        first.time,
        first.artifact_ref,
        "f" * 64,
        first.predecessor_artifact_ref,
        first.predecessor_content_sha256,
        first.producer_attempt_id,
        first.producer_fence,
        first.verified_at,
    )
    with pytest.raises(SimulationRecoveryContractError, match="ContentRef"):
        _verified_plan(artifacts, access, specification, (forged_hash, second))

    scene_content = sources[0].content_ref
    assert scene_content is not None
    forged_role = SimulationCheckpointRef.create(
        access.project_ref,
        specification,
        first.frame,
        first.time,
        sources[0].artifact_ref.value,
        scene_content.digest,
        first.predecessor_artifact_ref,
        first.predecessor_content_sha256,
        first.producer_attempt_id,
        first.producer_fence,
        first.verified_at,
    )
    with pytest.raises(SimulationRecoveryContractError, match="role"):
        _verified_plan(artifacts, access, specification, (forged_role, second))

    foreign = ProjectStore(database).create_project(namespace="p3-10-foreign", display_name="P3-10 Foreign")
    with pytest.raises(SimulationRecoveryContractError, match="Project"):
        _verified_plan(artifacts, foreign.access, specification, checkpoints)


def test_authoritative_recovery_rejects_corrupt_persisted_checkpoint(tmp_path: Path) -> None:
    database, artifacts, access, specification, checkpoints, _ = _authority(tmp_path)
    corrupted = checkpoints[0]
    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP TRIGGER artifact_revisions_no_update")
        connection.execute(
            "UPDATE artifact_revisions SET record_sha256=? WHERE project_id=? AND artifact_id=? AND revision=?",
            ("0" * 64, access.project_ref.value, corrupted.artifact_ref.split("/")[-2], 1),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(SimulationRecoveryContractError, match="missing or corrupt"):
        _verified_plan(artifacts, access, specification, checkpoints)


def test_authoritative_recovery_rejects_conflicting_fence_tool_and_source(tmp_path: Path) -> None:
    _, artifacts, access, specification, checkpoints, sources = _authority(tmp_path / "conflict")
    first, second = checkpoints
    conflicting = SimulationCheckpointRef.create(
        access.project_ref,
        specification,
        second.frame,
        second.time,
        second.artifact_ref,
        second.content_sha256,
        second.predecessor_artifact_ref,
        second.predecessor_content_sha256,
        first.producer_attempt_id,
        first.producer_fence + 1,
        second.verified_at,
    )
    with pytest.raises(SimulationRecoveryContractError, match="attempt/fence is stale"):
        _verified_plan(artifacts, access, specification, (first, conflicting))

    incompatible_tool = _specification(access.project_ref, sources, tool_ref="tool://vfx/incompatible/v1")
    with pytest.raises(SimulationRecoveryContractError, match="specification or tool"):
        _verified_plan(artifacts, access, incompatible_tool, checkpoints)

    _, orphan_artifacts, orphan_access, orphan_specification, orphan_checkpoints, _ = _authority(
        tmp_path / "orphan", second_has_predecessor=False
    )
    with pytest.raises(SimulationRecoveryContractError, match="source provenance"):
        _verified_plan(orphan_artifacts, orphan_access, orphan_specification, orphan_checkpoints)
