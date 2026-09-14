"""Focused P4-03 contracts layered on the accepted P1 router fixtures."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from minitz_os.engine.capability import CapabilityRef
from minitz_os.engine.routing import CapabilityImplementation, RoutingOutcome
from minitz_os.engine.routing_learning import (
    ExplorationMode,
    RoutingEstimate,
    RoutingEvidenceState,
    RoutingLearningError,
    RoutingLearningPolicy,
    RoutingLearningService,
    RoutingObjective,
)
from test_p1_09_routing import _Environment, _environment, _implementation, _policy, _request


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _registered(env: _Environment, identity: str, **changes: Any) -> CapabilityImplementation:
    implementation = _implementation(env, identity=identity, **changes)
    return env.routing.registry.register(
        env.access,
        implementation,
        idempotency_key=f"register-{identity}",
    )


def _estimate(env: _Environment, implementation: CapabilityImplementation, *, version: int = 1, fresh_until: str | None = None) -> RoutingEstimate:
    project_ref = env.project_ref
    capability = env.capability.capability_ref
    resource = env.resources[0].resource_ref
    implementation_ref = implementation.implementation_ref
    implementation_digest = implementation.record_sha256
    return RoutingEstimate(
        project_ref=project_ref,
        estimate_id="strategy-a",
        version=version,
        workload_ref="workload://routing/p4-03/core",
        workload_digest="a" * 64,
        capability_ref=capability,
        implementation_ref=implementation_ref,
        implementation_record_sha256=implementation_digest,
        strategy_ref="strategy://p4-03/a/1",
        strategy_digest="b" * 64,
        resource_ref=resource,
        resource_identity_digest="c" * 64,
        evidence_state=RoutingEvidenceState.OBSERVED,
        metrics={"quality": 0.9, "latency_ms": 100.0, "cost": None},
        evidence_refs=("artifact://routing-evidence/one",),
        observed_at=_now(),
        fresh_until=fresh_until or (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec="seconds"),
        calibration_ref="calibration://p4-03/1",
        supersedes=None,
    )


def test_versioned_estimate_keeps_metric_evidence_freshness_and_supersession_separate(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    implementation = _registered(env, "learned-a")
    first = _estimate(env, implementation)
    second = replace(first, version=2, supersedes=first.estimate_ref)

    assert first.canonical_digest != second.canonical_digest
    assert first.metrics["cost"] is None
    assert second.supersedes == first.estimate_ref
    with pytest.raises(RoutingLearningError):
        replace(first, fresh_until=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds"))


def test_hard_eligibility_egress_and_project_scope_precede_learned_rank(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    remote = _registered(env, "remote", remote=True)
    local = _registered(env, "local")
    service = RoutingLearningService(env.database)
    policy = RoutingLearningPolicy(env.project_ref, "policy://routing-learning/p4-03/1", RoutingObjective.QUALITY, {"quality": 1.0}, ExplorationMode.DISABLED)

    decision = service.route(
        env.access,
        _request(env, policy=_policy(env, allow_remote_egress=False), idempotency_key="hard-first"),
        learning_policy=policy,
        estimates=(_estimate(env, remote), _estimate(env, local)),
    )

    assert decision.routing_decision.outcome is RoutingOutcome.ROUTED
    assert decision.selected_implementation_ref == local.implementation_ref
    assert remote.implementation_ref in decision.ineligible_implementations


def test_objective_changes_only_the_rank_of_already_eligible_candidates(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    quality = _registered(env, "quality")
    latency = _registered(env, "latency")
    service = RoutingLearningService(env.database)
    base = _request(env, policy=_policy(env), idempotency_key="objective-rank")
    estimates = (
        replace(_estimate(env, quality), metrics={"quality": 0.95, "latency_ms": 200.0, "cost": None}),
        replace(_estimate(env, latency), implementation_ref=latency.implementation_ref, implementation_record_sha256=latency.record_sha256, metrics={"quality": 0.70, "latency_ms": 10.0, "cost": None}),
    )

    quality_decision = service.route(env.access, base, learning_policy=RoutingLearningPolicy(env.project_ref, "policy://routing-learning/quality", RoutingObjective.QUALITY, {"quality": 1.0}, ExplorationMode.DISABLED), estimates=estimates)
    latency_decision = service.route(env.access, replace(base, idempotency_key="latency-rank"), learning_policy=RoutingLearningPolicy(env.project_ref, "policy://routing-learning/latency", RoutingObjective.LATENCY, {"latency_ms": 1.0}, ExplorationMode.DISABLED), estimates=estimates)

    assert quality_decision.selected_implementation_ref == quality.implementation_ref
    assert latency_decision.selected_implementation_ref == latency.implementation_ref


def test_unknown_cold_start_cost_and_gpu_recovery_use_safe_baseline(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    implementation = _registered(env, "cold-start")
    service = RoutingLearningService(env.database)
    policy = RoutingLearningPolicy(env.project_ref, "policy://routing-learning/cold", RoutingObjective.QUALITY, {"quality": 1.0}, ExplorationMode.SHADOW)

    cold = service.route(env.access, _request(env, policy=_policy(env), idempotency_key="cold"), learning_policy=policy, estimates=())
    assert cold.evidence_state is RoutingEvidenceState.UNKNOWN_EVIDENCE
    assert cold.routing_decision.outcome is RoutingOutcome.ROUTED
    assert cold.used_baseline is True
    assert cold.exploration_executed is False

    unavailable = service.route(env.access, _request(env, policy=_policy(env), resources=(), idempotency_key="gpu-unavailable"), learning_policy=policy, estimates=(_estimate(env, implementation),))
    assert unavailable.routing_decision.outcome is RoutingOutcome.RESOURCE_TEMPORARILY_UNAVAILABLE
    recovered = service.route(env.access, _request(env, policy=_policy(env), idempotency_key="gpu-recovered"), learning_policy=policy, estimates=())
    assert recovered.routing_decision.outcome is RoutingOutcome.ROUTED

    cost_unknown = service.route(
        env.access,
        _request(env, policy=_policy(env), idempotency_key="cost-unknown"),
        learning_policy=RoutingLearningPolicy(env.project_ref, "policy://routing-learning/cost", RoutingObjective.COST, {"cost": 1.0}, ExplorationMode.DISABLED),
        estimates=(_estimate(env, implementation),),
    )
    assert cost_unknown.evidence_state is RoutingEvidenceState.UNKNOWN_EVIDENCE
    assert cost_unknown.used_baseline is True


def test_stale_or_revision_mismatched_evidence_is_rejected_and_policy_failure_falls_back(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    implementation = _registered(env, "stale")
    estimate = _estimate(env, implementation)
    service = RoutingLearningService(env.database)
    request = _request(env, policy=_policy(env), idempotency_key="stale")
    valid_policy = RoutingLearningPolicy(env.project_ref, "policy://routing-learning/fallback", RoutingObjective.QUALITY, {"quality": 1.0}, ExplorationMode.BOUNDED)

    with pytest.raises(RoutingLearningError):
        service.route(env.access, request, learning_policy=valid_policy, estimates=(replace(estimate, implementation_record_sha256="d" * 64),))
    fallback = service.route(env.access, replace(request, idempotency_key="fallback"), learning_policy=replace(valid_policy, enabled=False), estimates=(estimate,))
    assert fallback.used_baseline is True
    assert fallback.exploration_executed is False
    unavailable = service.route(env.access, replace(request, idempotency_key="state-unavailable"), learning_policy=valid_policy, estimates=None, learned_state_available=False)
    assert unavailable.evidence_state is RoutingEvidenceState.FALLBACK_BASELINE
    assert unavailable.used_baseline is True


def test_bounded_exploration_is_deterministic_and_task_risk_constrained(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    best = _registered(env, "explore-best")
    challenger = _registered(env, "explore-challenger")
    service = RoutingLearningService(env.database)
    estimates = (
        replace(_estimate(env, best), metrics={"quality": 0.95, "latency_ms": 100.0, "cost": None}),
        replace(_estimate(env, challenger), metrics={"quality": 0.70, "latency_ms": 50.0, "cost": None}),
    )
    policy = RoutingLearningPolicy(
        env.project_ref,
        "policy://routing-learning/explore",
        RoutingObjective.QUALITY,
        {"quality": 1.0},
        ExplorationMode.BOUNDED,
        exploration_fraction=1.0,
    )

    safe = service.route(env.access, _request(env, policy=_policy(env), idempotency_key="safe-explore"), learning_policy=policy, estimates=estimates, task_risk="LOW")
    high_risk = service.route(env.access, _request(env, policy=_policy(env), idempotency_key="high-risk"), learning_policy=policy, estimates=estimates, task_risk="HIGH")

    assert safe.selected_implementation_ref == challenger.implementation_ref
    assert safe.exploration_executed is True
    assert high_risk.selected_implementation_ref == best.implementation_ref
    assert high_risk.exploration_executed is False


def test_calibration_rollback_and_scheduler_revalidation_are_explicit(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    implementation = _registered(env, "revalidate")
    service = RoutingLearningService(env.database)
    policy = RoutingLearningPolicy(env.project_ref, "policy://routing-learning/calibrated", RoutingObjective.QUALITY, {"quality": 1.0}, ExplorationMode.BOUNDED)
    learned = service.route(env.access, _request(env, policy=_policy(env), idempotency_key="calibrated"), learning_policy=policy, estimates=(_estimate(env, implementation),))

    assert learned.calibration_ref == "calibration://p4-03/1"
    assert learned.rollback_baseline_ref is not None
    connection = sqlite3.connect(env.database)
    try:
        receipt = connection.execute("SELECT receipt_sha256 FROM routing_learning_receipts WHERE decision_id=?", (learned.routing_decision.decision_ref.decision_id,)).fetchone()
        assert receipt == (learned.canonical_digest,)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE routing_learning_receipts SET receipt_sha256=? WHERE decision_id=?", ("0" * 64, learned.routing_decision.decision_ref.decision_id))
    finally:
        connection.close()
    with pytest.raises(RoutingLearningError):
        service.scheduling_request(env.access, learned, priority=0)
