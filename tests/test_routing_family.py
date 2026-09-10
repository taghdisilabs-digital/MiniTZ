"""Focused UNIFY-02 contracts for the single MiniTZ routing family."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from biella.artifact import ContentRef
from biella.capability import CapabilityRef
from biella.model_evaluation import (
    DescriptiveStatistics,
    EvidenceClass,
    EvaluationTask,
    EvaluationTaskSet,
    ModelCandidate,
    ModelEvaluationKnowledgeCandidate,
    ModelEvaluationResult,
    ModelEvaluationSuite,
    WorkloadProfile,
)
from biella.routing_family import (
    LiveProviderRoute,
    RoutingFamilyAuthorityError,
    RoutingFamilyScope,
    RoutingFamilyScopeError,
    RoutingFamilyService,
    RoutingValueReceipt,
)
from biella.routing_learning import (
    ExplorationMode,
    RoutingLearningPolicy,
    RoutingObjective,
    RoutingLearningService,
)
from test_p1_09_routing import _environment
from test_p4_03_routing_learning import _estimate, _registered


def _content(label: str) -> ContentRef:
    return ContentRef.from_bytes(label.encode(), media_type="application/json")


def _evaluation(env):
    capability = env.capability.capability_ref
    profile = WorkloadProfile(env.project_ref, "family-workload", 1, _content("profile"), {"input": "short"})
    task = EvaluationTask(
        env.project_ref,
        "family-task",
        1,
        _content("task"),
        capability,
        "template://evaluation/family-task/v1",
        "routing",
        "medium",
    )
    task_set = EvaluationTaskSet(
        env.project_ref,
        "family-set",
        1,
        _content("task-set"),
        (task,),
        "policy://selection/fixed/v1",
    )
    candidates = (
        ModelCandidate(
            env.project_ref,
            "family-a",
            "model-deployment://family/a",
            "a" * 64,
            "adapter://family/a",
            "runtime://family/a/rev-1",
            "revision-a",
            False,
            capability,
        ),
        ModelCandidate(
            env.project_ref,
            "family-b",
            "model-deployment://family/b",
            "b" * 64,
            "adapter://family/b",
            "runtime://family/b/rev-1",
            "revision-b",
            False,
            capability,
        ),
    )
    suite = ModelEvaluationSuite(
        env.project_ref,
        "unify-02-family",
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
    result = ModelEvaluationResult(
        suite,
        (),
        (DescriptiveStatistics("accuracy", 2, 0.5, 0.1, 0.4, 0.6, "ratio"),),
        (),
    )
    knowledge = ModelEvaluationKnowledgeCandidate(
        env.project_ref,
        suite.canonical_digest,
        _content("knowledge"),
        ("artifact://minitz/unify-02/evaluation",),
    )
    return result, knowledge


def test_family_attaches_learning_evaluation_live_route_and_value_receipt_to_one_authority(tmp_path: Path):
    env = _environment(tmp_path, namespace="unify-02")
    first = _registered(env, "family-a", priority=10)
    second = _registered(env, "family-b", priority=20)
    request = __import__("test_p1_09_routing")._request(env, idempotency_key="family-route")
    scope = RoutingFamilyScope.from_request(
        request,
        workload_ref="workload://routing/p4-03/core",
        workload_digest="a" * 64,
        environment_ref="environment://unify-02",
    )
    policy = RoutingLearningPolicy(
        env.project_ref,
        "policy://routing-learning/unify-02",
        RoutingObjective.QUALITY,
        {"quality": 1.0},
        ExplorationMode.DISABLED,
    )
    estimates = (
        replace(_estimate(env, first), metrics={"quality": 0.95, "latency_ms": 100.0, "cost": None}),
        replace(_estimate(env, second), metrics={"quality": 0.70, "latency_ms": 10.0, "cost": None}),
    )
    evaluation, knowledge = _evaluation(env)
    live = LiveProviderRoute.from_mapping(
        scope,
        {
            "route_ref": "live-route://minitz/unify-02/provider",
            "provider": "provider://groq",
            "model": "model://qwen",
            "tool": "tool://route-adapter",
            "reasoning": "high",
            "evidence_refs": ("artifact://minitz/unify-02/live",),
        },
    )
    value = RoutingValueReceipt(
        "behavior://legacy-routing",
        first.implementation_ref.value,
        ("artifact://minitz/unify-02/value-transfer",),
        "legacy route value transferred to the shared MiniTZ family",
    )
    family = RoutingFamilyService(env.database, routing_service=env.routing)

    decision = family.route(
        env.access,
        request,
        scope=scope,
        learning_policy=policy,
        estimates=estimates,
        evaluation_result=evaluation,
        knowledge_candidate=knowledge,
        live_route=live,
        value_receipts=(value,),
    )

    assert family.authority_collision_check() is True
    assert decision.authority_collision_free is True
    assert decision.routing_decision is decision.learning_decision.routing_decision
    assert decision.selected_implementation_ref == first.implementation_ref
    assert decision.payload()["evaluation"]["liveness_gate"] is False
    assert decision.payload()["provider_model_tool_identity"] == "IMPLEMENTATION_METADATA"
    assert decision.payload()["live_route"]["provider_ref"] == "provider://groq"
    assert decision.payload()["value_receipts"][0]["destination_ref"] == first.implementation_ref.value
    assert set(decision.evaluation_digests) == {evaluation.suite_digest, evaluation.canonical_digest, knowledge.canonical_digest}
    assert len(decision.learning_evidence_digests) == 2
    receipt = family.get_receipt(env.access, scope, decision.routing_decision.decision_ref)
    assert receipt["decision_authority_ref"] == decision.decision_authority_ref
    assert receipt["routing_decision"] == decision.routing_decision.record_sha256
    assert receipt["scope"]["project_ref"] == env.project_ref.value


def test_family_rejects_a_second_core_authority_and_cross_scope_evidence(tmp_path: Path):
    env = _environment(tmp_path, namespace="unify-02-collision")
    family = RoutingFamilyService(env.database, routing_service=env.routing)
    competing_learning = RoutingLearningService(env.database)

    with pytest.raises(RoutingFamilyAuthorityError):
        RoutingFamilyService(
            env.database,
            routing_service=env.routing,
            learning_service=competing_learning,
        )

    from test_p1_09_routing import _request
    request = _request(env, idempotency_key="scope-rejection")
    scope = RoutingFamilyScope.from_request(
        request,
        workload_ref="workload://routing/p4-03/core",
        workload_digest="a" * 64,
    )
    crossed = replace(scope, capability_ref=CapabilityRef("other.capability", "1.0.0"))
    with pytest.raises(RoutingFamilyScopeError):
        family.route(env.access, request, scope=crossed)
