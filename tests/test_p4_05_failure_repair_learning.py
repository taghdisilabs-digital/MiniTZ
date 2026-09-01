from __future__ import annotations
from pathlib import Path
import pytest
from biella.project import ProjectRef

def test_failure_learning_public_states_and_project_scope(tmp_path: Path) -> None:
    from biella.failure_repair_learning import FailureLearningService, FailurePatternScope, FailurePatternStatus, RootCauseState, RepairOutcome, FailureMatchState
    service = FailureLearningService(tmp_path / "learning.db")
    project = ProjectRef.new()
    observation = service.record_observation(project, "run_volatile", "attempt_volatile", "worker failed at /secret/path token=redacted", source_ref="tests/test_p3_10_vfx_real.py")
    pattern = service.create_pattern(project, FailurePatternScope.PROJECT, observation, signature="worker-loss")
    assert pattern.status is FailurePatternStatus.CANDIDATE
    assert service.match_observation(project, observation).state in {FailureMatchState.MATCHED, FailureMatchState.POSSIBLE_MATCH}
    with pytest.raises(Exception): service.create_pattern(ProjectRef.new(), FailurePatternScope.ENGINE, observation, signature="foreign")
    cause = service.advance_root_cause(pattern, RootCauseState.HYPOTHESIS, evidence=(observation,))
    cause = service.advance_root_cause(cause, RootCauseState.CONFIRMED, evidence=(observation,), controlled=True)
    assert cause.state is RootCauseState.CONFIRMED
    assert service.project_knowledge_candidate(project, pattern).routing_allowed is False

def test_repair_learning_retains_failures_redacts_and_rebuilds_index(tmp_path: Path) -> None:
    from biella.failure_repair_learning import FailureLearningService, RepairOutcome
    service = FailureLearningService(tmp_path / "learning.db")
    project = ProjectRef.new()
    observation = service.record_observation(project, "run_a", "attempt_a", "Authorization: Bearer secret /tmp/private", source_ref="tests/test_p3_13_video_real.py:453")
    pattern = service.create_pattern(project, "PROJECT", observation, signature="encode")
    strategy = service.record_strategy(pattern, "retry-with-clean-workspace")
    failed = service.record_repair_attempt(strategy, RepairOutcome.FAILED, validation_refs=())
    assert service.recurrence_metrics(pattern).failed_repairs >= 1
    assert "secret" not in repr(failed).lower() and "/tmp/private" not in repr(failed)
    service.rebuild_similarity_index()
    assert service.kpi_results(project)

def test_observation_normalizes_volatile_ids_and_redacts_sensitive_evidence(tmp_path: Path) -> None:
    from biella.failure_repair_learning import FailureLearningService
    service = FailureLearningService(tmp_path / "learning.db")
    observation = service.record_observation(ProjectRef.new(), "run_123", "attempt_456", "token=secret /home/alice/private", capability_ref="capability://x/v1", implementation_ref="implementation://x/v1", runtime_ref="runtime://x/v1", failure_category="PROCESS", error_code="E1", raw_evidence_refs=(), artifact_refs=(), resource_snapshot_refs=(), environment={})
    assert observation.normalized_signature and "secret" not in observation.sanitized_summary.lower()

def test_match_states_and_similar_text_different_cause_do_not_merge(tmp_path: Path) -> None:
    from biella.failure_repair_learning import FailureLearningService, FailureMatchState
    service = FailureLearningService(tmp_path / "learning.db"); project = ProjectRef.new()
    observation = service.record_observation(project, "r", "a", "disk full")
    pattern = service.create_pattern(project, "PROJECT", observation, signature="disk-full")
    assert service.match_observation(project, observation, embedding_similarity=1.0).state is FailureMatchState.MATCHED
    assert service.match_observation(project, service.record_observation(project, "r2", "a2", "unrelated"), embedding_similarity=.8).state in {FailureMatchState.POSSIBLE_MATCH, FailureMatchState.NO_MATCH}

def test_root_cause_contradiction_preserves_versions_and_repair_validation_is_required(tmp_path: Path) -> None:
    from biella.failure_repair_learning import FailureLearningService, RootCauseState, RepairOutcome
    service = FailureLearningService(tmp_path / "learning.db"); project = ProjectRef.new(); observation = service.record_observation(project, "r", "a", "failure"); pattern = service.create_pattern(project, "PROJECT", observation, signature="f")
    cause = service.advance_root_cause(pattern, RootCauseState.HYPOTHESIS, evidence=(observation,)); cause = service.advance_root_cause(cause, RootCauseState.CONFIRMED, evidence=(observation,), controlled=True); service.advance_root_cause(cause, RootCauseState.CONTRADICTED, evidence=(observation,))
    assert len(service.list_root_causes(pattern)) >= 2
    strategy = service.record_strategy(pattern, "repair", version=1, applicability={}, prerequisites=(), actions=(), side_effect_authority="READ_ONLY", required_validation=True, supersedes=None)
    with pytest.raises(Exception): service.record_repair_attempt(strategy, RepairOutcome.SUCCEEDED, validation_refs=())

def test_repair_count_restart_rebuild_stale_strategy_and_engine_projection_guards(tmp_path: Path) -> None:
    from biella.failure_repair_learning import FailureLearningService, RepairOutcome
    project = ProjectRef.new(); service = FailureLearningService(tmp_path / "learning.db"); observation = service.record_observation(project, "r", "a", "failure"); pattern = service.create_pattern(project, "PROJECT", observation, signature="f"); strategy = service.record_strategy(pattern, "repair", version=1, applicability={}, prerequisites=(), actions=(), side_effect_authority="READ_ONLY", required_validation=False, supersedes=None)
    for _ in range(10): service.record_repair_attempt(strategy, RepairOutcome.FAILED, validation_refs=())
    service.rebuild_similarity_index(); restarted = FailureLearningService(tmp_path / "learning.db"); restarted.rebuild_similarity_index()
    assert restarted.recurrence_metrics(pattern).failed_repairs >= 10
    with pytest.raises(Exception): restarted.engine_knowledge_candidate(project, pattern)
