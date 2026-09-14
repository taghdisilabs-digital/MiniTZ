from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from minitz_os.engine.artifact import ArtifactService, ContentRef
from minitz_os.engine.engine_memory import KnowledgeCandidate, KnowledgeService
from minitz_os.engine.failure_repair_learning import (
    FailureKnowledgeProjection,
    FailureLearningContractError,
    FailureLearningIntegrityError,
    FailureLearningScopeError,
    FailureLearningService,
    FailureLearningVersionError,
    FailureMatchState,
    FailureObservation,
    FailurePatternScope,
    RepairOutcome,
    RootCauseState,
)
from minitz_os.engine.graph import GraphRef, NodeRef
from minitz_os.engine.project import ProjectRef, ProjectStore
from minitz_os.engine.project_memory import ProjectKnowledgeCandidate, ProjectKnowledgeService
from minitz_os.engine.task import Task, TaskRef, TaskSideEffectError


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "p4_05_failure_repair_learning"


def _task(project_ref: ProjectRef, suffix: str, authority: str) -> Task:
    return Task(
        task_ref=TaskRef(project_ref, "tsk_" + suffix * 32, 1),
        idempotency_key=f"p4-05-{authority.lower()}-{suffix}",
        task_type="failure.repair",
        objective="Produce an isolated repair candidate from exact evidence.",
        required_capabilities=(),
        input_refs=(),
        output_contract={},
        constraints={"autonomous_repair": True},
        side_effect_authority=authority,
        data_policy_ref=None,
        egress_policy_ref=None,
        evidence_requirements=(),
        acceptance_criteria=(),
        resource_hints={},
    )


def _observation(
    service: FailureLearningService,
    project_ref: ProjectRef,
    run_id: str,
    attempt_id: str,
    summary: str,
    *,
    category: str = "encoder.failure",
    code: str = "ENCODER_EXIT_1",
) -> FailureObservation:
    return service.record_observation(
        project_ref,
        run_id,
        attempt_id,
        summary,
        capability_ref="capability://media/video",
        implementation_ref="implementation://ffmpeg/reference",
        runtime_ref="runtime://linux/cpu",
        failure_category=category,
        error_code=code,
        source_ref="tests/test_p3_13_video_real.py:477",
    )


def test_task_authority_stale_strategy_and_conditional_recommendation(tmp_path: Path) -> None:
    service = FailureLearningService(tmp_path / "learning.sqlite3")
    project_ref = ProjectRef.new()
    observation = _observation(service, project_ref, "run_job-1", "attempt_req-1", "encoder process failed for timeline frames")
    pattern = service.create_pattern(project_ref, "PROJECT", observation, signature="video-encode-process")
    strategy = service.record_strategy(
        pattern,
        "repair isolated encode configuration",
        side_effect_authority="CANDIDATE_WRITE",
        required_validation=False,
    )
    assert strategy.required_validation
    match = service.match_observation(project_ref, observation)
    recommendation = service.recommend_repair(match, (strategy,))
    assert match.state is FailureMatchState.MATCHED
    assert recommendation.executable is False
    assert recommendation.required_validation == strategy.required_validation

    node_ref = NodeRef(GraphRef(project_ref, "gph_" + "3" * 32, 1), "nod_" + "4" * 32)
    with pytest.raises(TaskSideEffectError):
        service.propose_repair_node(_task(project_ref, "1", "READ_ONLY"), match, strategy, node_ref)
    proposal = service.propose_repair_node(
        _task(project_ref, "2", "CANDIDATE_WRITE"), match, strategy, node_ref
    )
    assert proposal.graph_revision_required and proposal.execution_authorized

    replacement = service.record_strategy(
        pattern,
        "repair isolated encode configuration v2",
        supersedes=strategy,
        required_validation=("validation-contract://video/duration",),
    )
    assert replacement.version == strategy.version + 1
    with pytest.raises(FailureLearningVersionError):
        service.recommend_repair(match, (strategy,))
    with pytest.raises(FailureLearningVersionError):
        service.record_repair_attempt(strategy, RepairOutcome.FAILED, validation_refs=())


def test_match_states_engine_scope_and_model_similarity_is_not_identity(tmp_path: Path) -> None:
    service = FailureLearningService(tmp_path / "learning.sqlite3")
    alpha = ProjectRef.new()
    beta = ProjectRef.new()
    original = _observation(service, alpha, "run_job-11", "attempt_req-aa", "encoder process failed for timeline frames")
    volatile = _observation(service, alpha, "run_job-99", "attempt_req-zz", "encoder process failed for timeline frames")
    assert original.normalized_signature == volatile.normalized_signature
    project_pattern = service.create_pattern(alpha, FailurePatternScope.PROJECT, original, signature="encode-process")
    assert service.match_observation(alpha, volatile).state is FailureMatchState.MATCHED

    different_cause = _observation(
        service,
        alpha,
        "run_job-12",
        "attempt_req-bb",
        "encoder process failed for timeline frames because authority expired",
        category="execution.authority",
        code="STALE_EXECUTION",
    )
    possible = service.match_observation(alpha, different_cause, embedding_similarity=0.99)
    assert possible.state is FailureMatchState.POSSIBLE_MATCH

    unrelated = _observation(
        service,
        alpha,
        "run_job-13",
        "attempt_req-cc",
        "database quota exhausted during migration",
        category="database.capacity",
        code="DISK_FULL",
    )
    assert service.match_observation(alpha, unrelated, embedding_similarity=0.0).state is FailureMatchState.NO_MATCH
    with pytest.raises(FailureLearningScopeError):
        service.engine_knowledge_candidate(alpha, project_pattern)

    corroborating = _observation(service, beta, "run_job-14", "attempt_req-dd", "encoder process failed for timeline frames")
    engine_pattern = service.create_pattern(
        alpha,
        FailurePatternScope.ENGINE,
        original,
        signature="cross-project-encode-process",
        corroborating_observations=(corroborating,),
        evidence_strength="CORROBORATED",
    )
    projection = service.engine_knowledge_candidate(alpha, engine_pattern)
    assert isinstance(projection, FailureKnowledgeProjection)
    assert projection.target == "ENGINE_KNOWLEDGE" and projection.routing_allowed is False
    assert service.match_observation(beta, corroborating).state is FailureMatchState.MATCHED


def test_repair_attempts_preserve_negative_and_exact_side_effect_evidence(tmp_path: Path) -> None:
    service = FailureLearningService(tmp_path / "learning.sqlite3")
    project_ref = ProjectRef.new()
    observation = _observation(service, project_ref, "run_job-21", "attempt_req-ee", "encoder process failed")
    pattern = service.create_pattern(project_ref, "PROJECT", observation, signature="encoder")
    strategy = service.record_strategy(
        pattern,
        "correct encode configuration",
        actions=("edit candidate configuration", "run isolated encoder"),
        prerequisites=("source content digest remains unchanged",),
        required_validation=("validation-contract://video/duration",),
    )
    with pytest.raises(FailureLearningContractError):
        service.record_repair_attempt(strategy, RepairOutcome.SUCCEEDED, validation_refs=())
    successful = service.record_repair_attempt(
        strategy,
        RepairOutcome.SUCCEEDED,
        failure_observation=observation,
        validation_refs=("validation-result://project/video-duration-pass",),
        resource_changes={"workspace": "isolated candidate"},
        source_before="tests/fixtures/video-before.json",
        source_after="tests/fixtures/video-after.json",
        model_call_refs=("model-call://provider/model/call-1",),
        tool_call_refs=("tool-call://process/ffmpeg/call-1",),
        side_effects=("candidate artifact written",),
    )
    for _ in range(12):
        service.record_repair_attempt(
            strategy,
            RepairOutcome.FAILED,
            failure_observation=observation,
            validation_refs=(),
            resource_changes={"diagnostic": "Authorization: Bearer fixture-value"},
        )
    metrics = service.recurrence_metrics(pattern)
    assert metrics.successful_repairs == 1 and metrics.failed_repairs == 12
    assert successful.validation_refs and successful.source_before and successful.source_after
    assert successful.model_call_refs and successful.tool_call_refs and successful.side_effects
    assert not hasattr(service, "max_repair_attempts")
    assert set(service.kpi_results(project_ref).values()) == {0}


def test_restart_cache_rebuild_and_immutable_evidence_integrity(tmp_path: Path) -> None:
    database = tmp_path / "learning.sqlite3"
    service = FailureLearningService(database)
    project_ref = ProjectRef.new()
    observation = _observation(service, project_ref, "run_job-31", "attempt_req-ff", "encoder process failed")
    pattern = service.create_pattern(project_ref, "PROJECT", observation, signature="encoder")
    cause = service.advance_root_cause(pattern, RootCauseState.HYPOTHESIS, evidence=(observation,))
    service.advance_root_cause(cause, RootCauseState.CONFIRMED, evidence=(observation,), controlled=True)
    strategy = service.record_strategy(pattern, "repair", required_validation=True)
    service.record_repair_attempt(strategy, RepairOutcome.FAILED, validation_refs=())

    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP TABLE failure_similarity_index")
        connection.commit()
    finally:
        connection.close()
    restarted = FailureLearningService(database)
    assert restarted.rebuild_similarity_index() == 1
    assert restarted.match_observation(project_ref, observation).state is FailureMatchState.MATCHED
    assert restarted.recurrence_metrics(pattern).failed_repairs == 1

    connection = sqlite3.connect(database)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE failure_learning_versions SET payload_json='{}'")
        connection.rollback()
        connection.execute("DROP TRIGGER failure_learning_versions_no_update")
        connection.execute(
            "UPDATE failure_learning_versions SET payload_json='{}' WHERE kind='PATTERN'"
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(FailureLearningIntegrityError):
        restarted.match_observation(project_ref, observation)


def test_real_knowledge_candidate_projection_and_reference_fixture_identity(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.sqlite3"
    project_store = ProjectStore(database)
    alpha_registration = project_store.create_project(
        namespace="p4-05-alpha",
        display_name="P4-05 Alpha",
    )
    beta_registration = project_store.create_project(
        namespace="p4-05-beta",
        display_name="P4-05 Beta",
    )
    alpha = alpha_registration.project.project_ref
    beta = beta_registration.project.project_ref
    source = ArtifactService(database).create_artifact(
        alpha_registration.access,
        project_ref=alpha,
        role="p4-05.source",
        content_ref=ContentRef.from_bytes(b"bounded failure evidence", media_type="text/plain"),
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="p4-05.fixture",
        metadata={},
    )
    service = FailureLearningService(database)
    alpha_observation = _observation(service, alpha, "run_job-41", "attempt_req-gg", "encoder process failed")
    project_pattern = service.create_pattern(alpha, "PROJECT", alpha_observation, signature="alpha-encoder")
    project_candidate = service.project_knowledge_candidate(
        alpha,
        project_pattern,
        memory_service=ProjectKnowledgeService(database),
        access=alpha_registration.access,
        source_refs=(source.artifact_ref,),
    )
    assert isinstance(project_candidate, ProjectKnowledgeCandidate)
    assert project_candidate.project_ref == alpha

    beta_observation = _observation(service, beta, "run_job-42", "attempt_req-hh", "encoder process failed")
    engine_pattern = service.create_pattern(
        alpha,
        "ENGINE",
        alpha_observation,
        signature="engine-encoder",
        corroborating_observations=(beta_observation,),
        evidence_strength="CORROBORATED",
    )
    engine_candidate = service.engine_knowledge_candidate(
        alpha,
        engine_pattern,
        knowledge_service=KnowledgeService(database),
        access=alpha_registration.access,
        source_refs=(source.artifact_ref,),
    )
    assert isinstance(engine_candidate, KnowledgeCandidate)
    assert engine_candidate.proposed_scope == "ENGINE"
    assert engine_candidate.source_project_ref == alpha

    manifest = json.loads((FIXTURE_ROOT / "reference_cases.json").read_text())
    assert manifest["schema"] == "minitz.failure_repair_reference_manifest/v1"
    assert manifest["reality"] == "REFERENCE" and manifest["production_history_claimed"] is False
    for name in manifest["cases"]:
        fixture = json.loads((FIXTURE_ROOT / name).read_text())
        assert fixture["schema"] == "minitz.failure_repair_fixture/v1"
        assert fixture["reality"] == "REFERENCE"
        source_path = fixture["source_ref"].split(":", 1)[0]
        assert (Path(__file__).parents[1] / source_path).is_file()
