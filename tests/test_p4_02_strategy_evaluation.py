from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone

import pytest

from minitz_os.engine.artifact import ContentRef
from minitz_os.engine.capability import CapabilityRef
from minitz_os.engine.model_evaluation import (
    EvidenceClass,
    EvaluationTask,
    EvaluationTaskSet,
    ModelCandidate,
    WorkloadProfile,
)
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.run import RunRef
from minitz_os.engine.strategy_evaluation import (
    ExecutionStrategy,
    MatrixKind,
    PromptArtifact,
    SkillArtifact,
    StrategyContractError,
    StrategyDimension,
    StrategyEffectKind,
    StrategyEvaluationExperiment,
    StrategyEvaluationRun,
    StrategyMetricSet,
    StrategyPattern,
    build_strategy_evaluation_result,
)


def _content(label: str) -> ContentRef:
    return ContentRef.from_bytes(label.encode(), media_type="application/json")


def _strategy(
    project: ProjectRef,
    strategy_id: str,
    *,
    prompt_text: str,
    tool_policy: str = "tool-policy://evaluation/no-tools/v1",
    context_policy: str = "context-policy://evaluation/minimal/v1",
    parallel_policy: str = "parallel-policy://evaluation/serial/v1",
    specialist_policy: str = "specialist-policy://evaluation/generalist/v1",
    validation_refs: tuple[str, ...] = ("validation-policy://evaluation/exact/v1",),
) -> ExecutionStrategy:
    skill = SkillArtifact(
        project_ref=project,
        skill_id=f"{strategy_id}.skill",
        version=1,
        content_ref=_content(f"{strategy_id}-skill"),
        applicability={"workload": "reasoning"},
    )
    prompt = PromptArtifact(
        project_ref=project,
        prompt_id=f"{strategy_id}.prompt",
        version=1,
        content_ref=_content(prompt_text),
        applicability={"workload": "reasoning"},
    )
    return ExecutionStrategy(
        project_ref=project,
        strategy_id=strategy_id,
        version=1,
        patterns=(StrategyPattern.DIRECT,),
        applicability={"workload": "reasoning"},
        skill_artifacts=(skill,),
        prompt_artifacts=(prompt,),
        decomposition_policy_ref="decomposition-policy://evaluation/direct/v1",
        tool_policy_ref=tool_policy,
        context_policy_ref=context_policy,
        model_call_policy_ref="model-call-policy://evaluation/greedy/v1",
        loop_stop_policy_ref="loop-stop-policy://evaluation/output-valid/v1",
        parallelization_policy_ref=parallel_policy,
        specialist_policy_ref=specialist_policy,
        validation_policy_refs=validation_refs,
        failure_policy_ref="failure-policy://evaluation/preserve/v1",
        output_policy_ref="output-policy://evaluation/exact/v1",
    )


def _experiment(
    project: ProjectRef,
    *,
    matrix_kind: MatrixKind = MatrixKind.SAME_MODEL,
    repetitions: int = 3,
    strategies: tuple[ExecutionStrategy, ...] | None = None,
) -> StrategyEvaluationExperiment:
    capability = CapabilityRef("strategy.evaluate", "1.0.0")
    profile = WorkloadProfile(
        project,
        "reasoning",
        1,
        _content("profile"),
        {"domain": "reasoning"},
    )
    task = EvaluationTask(
        project,
        "bounded-reasoning",
        1,
        _content("task"),
        capability,
        "template://strategy-evaluation/bounded-reasoning/v1",
        "reasoning",
        "medium",
    )
    task_set = EvaluationTaskSet(
        project,
        "bounded",
        1,
        _content("task-set"),
        (task,),
        "selection-policy://strategy-evaluation/all/v1",
    )
    models = [
        ModelCandidate(
            project,
            "model-a",
            "model-deployment://evaluation/model-a",
            "a" * 64,
            "adapter://evaluation/local",
            "runtime://evaluation/pytorch",
            "revision-a",
            False,
            capability,
        )
    ]
    if matrix_kind is MatrixKind.FACTORIAL:
        models.append(
            ModelCandidate(
                project,
                "model-b",
                "model-deployment://evaluation/model-b",
                "b" * 64,
                "adapter://evaluation/local",
                "runtime://evaluation/pytorch",
                "revision-b",
                False,
                capability,
            )
        )
    strategy_values = strategies or (
        _strategy(project, "strategy-s1", prompt_text="direct"),
        _strategy(project, "strategy-s2", prompt_text="structured"),
    )
    return StrategyEvaluationExperiment(
        project_ref=project,
        experiment_id="p4-02-controlled",
        version=1,
        capability_ref=capability,
        workload_profile=profile,
        task_set=task_set,
        evidence_class=EvidenceClass.CONTROLLED,
        matrix_kind=matrix_kind,
        controlled_variables={
            "MODEL_IMPLEMENTATION": "varied" if matrix_kind is MatrixKind.FACTORIAL else "fixed",
            "TASK_SET": "fixed",
            "RESOURCE": "fixed",
            "OUTPUT": "fixed",
        },
        varied_dimensions=(StrategyDimension.PROMPT_SKILL,),
        confounders={},
        models=tuple(models),
        strategies=strategy_values,
        required_validation_refs=("validation-policy://evaluation/exact/v1",),
        resource_policy_ref="resource-policy://evaluation/same-l40s/v1",
        order_policy_ref="order-policy://evaluation/counterbalanced/v1",
        cache_policy_ref="cache-policy://evaluation/warm/v1",
        side_effect_authority="READ_ONLY",
        repetitions=repetitions,
    )


def _metrics(*, success: bool, score: float, latency: float = 1.0) -> StrategyMetricSet:
    return StrategyMetricSet(
        task_success=success,
        quality_score=score,
        end_to_end_latency_seconds=latency,
        model_calls=1,
        input_tokens=10,
        output_tokens=2,
        context_tokens=8,
        model_latency_seconds=latency,
        cost=None,
        tool_calls=0,
        invalid_tool_calls=0,
        redundant_tool_calls=0,
        failed_tool_calls=0,
        tool_latency_seconds=0.0,
        tool_side_effects=0,
        tool_data_bytes=0,
        graph_nodes=3,
        graph_depth=2,
        graph_parallel_width=2,
        graph_revisions=1,
        graph_failures=0,
        repairs=0,
        replans=0,
        completed_reuse=0,
        resource_metrics={"gpu.vram_peak_bytes": 1024.0},
    )


def _run(
    experiment: StrategyEvaluationExperiment,
    candidate_id: str,
    strategy_id: str,
    repetition: int,
    score: float,
) -> StrategyEvaluationRun:
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    strategy = next(item for item in experiment.strategies if item.strategy_id == strategy_id)
    return StrategyEvaluationRun(
        experiment=experiment,
        candidate_id=candidate_id,
        strategy_id=strategy_id,
        strategy_digest=strategy.canonical_digest,
        task=experiment.task_set.tasks[0],
        repetition=repetition,
        run_ref=RunRef(experiment.project_ref, "run_" + "1" * 32),
        metrics=_metrics(success=score >= 0.5, score=score),
        transport_outcome="passed",
        semantic_outcome="passed" if score >= 0.5 else "failed",
        infrastructure_outcome="passed",
        status="completed",
        started_at=now,
        completed_at=now,
        evidence_refs=("artifact://strategy-evaluation/raw",),
    )


def test_skill_prompt_and_strategy_versions_are_immutable_exact_identities() -> None:
    project = ProjectRef.new()
    strategy = _strategy(project, "strategy-s1", prompt_text="direct")
    skill_v1 = strategy.skill_artifacts[0]
    prompt_v1 = strategy.prompt_artifacts[0]
    skill_v2 = SkillArtifact.revise(skill_v1, _content("changed-skill"))
    prompt_v2 = PromptArtifact.revise(prompt_v1, _content("changed-prompt"))

    assert skill_v2.version == prompt_v2.version == 2
    assert skill_v2.supersedes_digest == skill_v1.canonical_digest
    assert prompt_v2.supersedes_digest == prompt_v1.canonical_digest
    assert skill_v2.canonical_digest != skill_v1.canonical_digest
    assert prompt_v2.canonical_digest != prompt_v1.canonical_digest
    with pytest.raises(FrozenInstanceError):
        strategy.strategy_id = "changed"  # type: ignore[misc]


def test_same_model_experiment_is_scoped_and_cannot_weaken_task_validation() -> None:
    project = ProjectRef.new()
    experiment = _experiment(project)

    assert experiment.primary_variable == "EXECUTION_STRATEGY"
    assert experiment.controlled_variables["MODEL_IMPLEMENTATION"] == "fixed"
    assert experiment.mandatory_agent_hierarchy_created is False
    assert len(experiment.models) == 1
    assert len({item.canonical_digest for item in experiment.strategies}) == 2

    with pytest.raises(StrategyContractError, match="validation"):
        replace(experiment.strategies[1], validation_policy_refs=())

    foreign = ProjectRef.new()
    with pytest.raises(StrategyContractError, match="Project"):
        replace(
            experiment.strategies[1],
            skill_artifacts=(_strategy(foreign, "foreign", prompt_text="foreign").skill_artifacts[0],),
        )

    hidden_tool_change = replace(
        experiment.strategies[1],
        tool_policy_ref="tool-policy://evaluation/hidden-change/v1",
    )
    with pytest.raises(StrategyContractError, match="unrecorded"):
        _experiment(project, strategies=(experiment.strategies[0], hidden_tool_change))


def test_same_model_pairing_attributes_strategy_effect_and_preserves_worse_runs() -> None:
    experiment = _experiment(ProjectRef.new(), repetitions=3)
    candidate_id = experiment.models[0].candidate_id
    runs = tuple(
        _run(experiment, candidate_id, strategy_id, repetition, score)
        for repetition in range(1, 4)
        for strategy_id, score in (("strategy-s1", 0.0), ("strategy-s2", 1.0))
    )

    result = build_strategy_evaluation_result(experiment, runs)

    assert len(result.runs) == 6
    assert {item.semantic_outcome for item in result.runs} == {"failed", "passed"}
    assert len(result.pairwise_comparisons) == 1
    comparison = result.pairwise_comparisons[0]
    assert (comparison.paired_wins, comparison.paired_losses, comparison.paired_ties) == (0, 3, 0)
    assert comparison.conclusion == "DESCRIPTIVE"
    assert comparison.winner is None
    assert {item.effect_kind for item in result.effects} == {StrategyEffectKind.STRATEGY}
    assert result.universal_winner_claimed is False


def test_factorial_result_separates_model_strategy_and_interaction_effects() -> None:
    experiment = _experiment(ProjectRef.new(), matrix_kind=MatrixKind.FACTORIAL, repetitions=1)
    scores = {
        ("model-a", "strategy-s1"): 0.2,
        ("model-a", "strategy-s2"): 0.8,
        ("model-b", "strategy-s1"): 0.6,
        ("model-b", "strategy-s2"): 0.7,
    }
    runs = tuple(
        _run(experiment, candidate_id, strategy_id, 1, score)
        for (candidate_id, strategy_id), score in scores.items()
    )

    result = build_strategy_evaluation_result(experiment, runs)

    assert {item.effect_kind for item in result.effects} == {
        StrategyEffectKind.MODEL,
        StrategyEffectKind.STRATEGY,
        StrategyEffectKind.INTERACTION,
    }
    assert all(item.conclusion == "INSUFFICIENT_EVIDENCE" for item in result.effects)
    assert result.model_effect_mislabeled_strategy_effect is False
    assert result.strategy_effect_mislabeled_model_effect is False
