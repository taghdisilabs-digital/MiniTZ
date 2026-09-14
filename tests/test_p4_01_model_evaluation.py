from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from minitz_os.engine.artifact import ContentRef
from minitz_os.engine.capability import CapabilityRef
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.model_evaluation import (
    DescriptiveStatistics,
    EvaluationContractError,
    EvaluationTask,
    EvaluationTaskSet,
    EvidenceClass,
    ModelCandidate,
    ModelEvaluationKnowledgeCandidate,
    ModelEvaluationResult,
    ModelEvaluationSuite,
    PairwiseComparison,
    WorkloadProfile,
)


def _content(label: str) -> ContentRef:
    return ContentRef.from_bytes(label.encode(), media_type="application/json")


def _suite(project: ProjectRef) -> ModelEvaluationSuite:
    capability = CapabilityRef("model.infer", "1.0.0")
    profile = WorkloadProfile(project, "reasoning", 1, _content("profile"), {"input": "short"})
    task = EvaluationTask(
        project,
        "basic-reasoning",
        1,
        _content("task"),
        capability,
        "template://evaluation/basic-reasoning/v1",
        "reasoning",
        "medium",
    )
    task_set = EvaluationTaskSet(
        project,
        "core",
        1,
        _content("task-set"),
        (task,),
        "policy://selection/fixed/v1",
    )
    candidates = (
        ModelCandidate(
            project,
            "candidate-a",
            "model-deployment://provider/a",
            "a" * 64,
            "adapter://provider/a",
            "runtime://provider/a/rev-1",
            "revision-a",
            False,
            capability,
        ),
        ModelCandidate(
            project,
            "candidate-b",
            "model-deployment://provider/b",
            "b" * 64,
            "adapter://provider/b",
            "runtime://provider/b/rev-1",
            "revision-b",
            False,
            capability,
        ),
    )
    return ModelEvaluationSuite(
        project,
        "p4-01-core",
        1,
        capability,
        profile,
        task_set,
        EvidenceClass.CONTROLLED,
        {"MODEL_IMPLEMENTATION": "varied"},
        {"resource": "fixed"},
        candidates,
        "policy://execution/single/v1",
        "tool://none",
        "context://fixed/v1",
        "validator://exact/v1",
        "resource://fixed/v1",
        "generation://fixed/v1",
        "order://counterbalanced/v1",
        "cache://disabled/v1",
        2,
        None,
    )


def test_suite_is_canonical_project_scoped_and_versioned() -> None:
    project = ProjectRef.new()
    suite = _suite(project)

    assert suite.project_ref == project
    assert len(suite.canonical_digest) == 64
    with pytest.raises(FrozenInstanceError):
        suite.suite_id = "changed"  # type: ignore[misc]
    changed = ModelEvaluationSuite(
        project,
        suite.suite_id,
        2,
        suite.capability_ref,
        suite.workload_profile,
        suite.task_set,
        suite.evidence_class,
        suite.controlled_variables,
        suite.confounders,
        suite.candidates,
        suite.execution_policy_ref,
        suite.tool_policy_ref,
        suite.context_policy_ref,
        suite.validation_policy_ref,
        suite.resource_policy_ref,
        suite.generation_policy_ref,
        suite.order_policy_ref,
        suite.cache_policy_ref,
        suite.repetitions,
        suite.scoring_policy_ref,
    )
    assert changed.canonical_digest != suite.canonical_digest


def test_suite_rejects_hidden_strategy_or_class_upgrade() -> None:
    project = ProjectRef.new()
    suite = _suite(project)
    with pytest.raises(EvaluationContractError):
        ModelEvaluationSuite(
            project, suite.suite_id, 1, suite.capability_ref, suite.workload_profile,
            suite.task_set, EvidenceClass.CONTROLLED, {"other": "varied"}, {},
            suite.candidates, suite.execution_policy_ref, suite.tool_policy_ref,
            suite.context_policy_ref, suite.validation_policy_ref, suite.resource_policy_ref,
            suite.generation_policy_ref, suite.order_policy_ref, suite.cache_policy_ref,
            1, None,
        )
    with pytest.raises(EvaluationContractError):
        ModelEvaluationSuite(
            project, suite.suite_id, 1, suite.capability_ref, suite.workload_profile,
            suite.task_set, EvidenceClass.CONTROLLED, {"MODEL_IMPLEMENTATION": "varied"},
            {"resource": "uncontrolled"}, suite.candidates, suite.execution_policy_ref,
            suite.tool_policy_ref, suite.context_policy_ref, suite.validation_policy_ref,
            suite.resource_policy_ref, suite.generation_policy_ref, suite.order_policy_ref,
            suite.cache_policy_ref, 1, None,
        )


def test_cross_project_task_sets_are_rejected() -> None:
    suite = _suite(ProjectRef.new())
    other = ProjectRef.new()
    task = EvaluationTask(other, "other", 1, _content("other"), suite.capability_ref,
                          "template://evaluation/other/v1", "reasoning", "easy")
    task_set = EvaluationTaskSet(other, "other", 1, _content("other-set"), (task,),
                                 "policy://selection/fixed/v1")
    with pytest.raises(EvaluationContractError):
        ModelEvaluationSuite(
            suite.project_ref, suite.suite_id, suite.version, suite.capability_ref,
            suite.workload_profile, task_set, suite.evidence_class,
            suite.controlled_variables, suite.confounders, suite.candidates,
            suite.execution_policy_ref, suite.tool_policy_ref, suite.context_policy_ref,
            suite.validation_policy_ref, suite.resource_policy_ref,
            suite.generation_policy_ref, suite.order_policy_ref, suite.cache_policy_ref,
            suite.repetitions, suite.scoring_policy_ref,
        )


def test_pairwise_comparison_cannot_claim_a_universal_winner() -> None:
    suite = _suite(ProjectRef.new())
    comparison = PairwiseComparison(
        suite, "candidate-a", "candidate-b", 1, 0, 0, "INSUFFICIENT_EVIDENCE", "resource://unknown"
    )
    assert comparison.winner is None
    with pytest.raises(EvaluationContractError):
        PairwiseComparison(suite, "candidate-a", "candidate-b", 1, 0, 0, "WINNER", None)


def test_statistics_and_knowledge_candidate_remain_descriptive_and_scoped() -> None:
    suite = _suite(ProjectRef.new())
    statistics = DescriptiveStatistics("accuracy", 2, 0.5, 0.1, 0.4, 0.6, "ratio")
    result = ModelEvaluationResult(suite, (), (statistics,), ())
    candidate = ModelEvaluationKnowledgeCandidate(
        suite.project_ref, suite.canonical_digest, _content("observation"), ("artifact://evidence/one",)
    )
    assert result.suite_digest == suite.canonical_digest
    assert candidate.promotion_allowed is False
    assert candidate.routing_allowed is False
