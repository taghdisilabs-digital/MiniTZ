"""Evidence-based learned ranking layered strictly after P1 routing eligibility."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType

from .capability import CapabilityRef
from .project import ProjectAccess, ProjectRef
from .resource import ResourceRef
from .routing import (
    CapabilityImplementationRef,
    RoutingDecision,
    RoutingPolicy,
    RoutingRequest,
    RoutingService,
)
from .scheduler import SchedulingRequest


_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[a-z][a-z0-9+.-]{1,63}://[^\s\x00-\x1f]{1,1024}")


class RoutingLearningError(ValueError):
    """Learned ranking evidence is malformed, stale, or would weaken P1 routing."""


class RoutingEvidenceState(str, Enum):
    UNKNOWN_EVIDENCE = "UNKNOWN_EVIDENCE"
    INSUFFICIENT = "INSUFFICIENT"
    OBSERVED = "OBSERVED"
    SUPPORTED = "SUPPORTED"
    STRONG = "STRONG"
    STALE = "STALE"
    CONTRADICTED = "CONTRADICTED"
    DISABLED = "DISABLED"
    FALLBACK_BASELINE = "FALLBACK_BASELINE"


class RoutingObjective(str, Enum):
    QUALITY = "QUALITY"
    LATENCY = "LATENCY"
    COST = "COST"
    RELIABILITY = "RELIABILITY"
    WEIGHTED = "WEIGHTED"


class ExplorationMode(str, Enum):
    NO_EXPLORATION = "NO_EXPLORATION"
    EVALUATION_ONLY = "EVALUATION_ONLY"
    BOUNDED_EXPLORATION = "BOUNDED_EXPLORATION"
    SHADOW_EVALUATION = "SHADOW_EVALUATION"
    DISABLED = "NO_EXPLORATION"
    OFF = "NO_EXPLORATION"
    BOUNDED = "BOUNDED_EXPLORATION"
    SHADOW = "SHADOW_EVALUATION"
    SAFE_SHADOW = "SHADOW_EVALUATION"


_METRICS = frozenset({"quality", "latency_ms", "cost", "reliability", "resource"})
_CURRENT_EVIDENCE = frozenset(
    {RoutingEvidenceState.OBSERVED, RoutingEvidenceState.SUPPORTED, RoutingEvidenceState.STRONG}
)


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise RoutingLearningError("routing-learning evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _key(value: object, label: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise RoutingLearningError(f"{label} is malformed")
    return value


def _ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise RoutingLearningError(f"{label} must be an exact reference")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise RoutingLearningError(f"{label} must be a SHA-256 digest")
    return value


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise RoutingLearningError(f"{label} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RoutingLearningError(f"{label} must be a timezone-aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RoutingLearningError(f"{label} must be a timezone-aware timestamp")
    return parsed


def _metrics(values: Mapping[str, float | None], label: str) -> Mapping[str, float | None]:
    if not isinstance(values, Mapping) or len(values) > 64:
        raise RoutingLearningError(f"{label} is malformed or unbounded")
    copied = dict(values)
    for key, value in copied.items():
        _key(key, f"{label} key")
        if key not in _METRICS:
            raise RoutingLearningError(f"{label} contains unsupported metric {key}")
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
        ):
            raise RoutingLearningError(f"{label} values must be finite or unknown")
        copied[key] = None if value is None else float(value)
    return MappingProxyType(dict(sorted(copied.items())))


@dataclass(frozen=True)
class RoutingEstimate:
    """One immutable, versioned estimate for a concrete route and workload."""

    project_ref: ProjectRef
    estimate_id: str
    version: int
    workload_ref: str
    workload_digest: str
    capability_ref: CapabilityRef
    implementation_ref: CapabilityImplementationRef
    implementation_record_sha256: str
    strategy_ref: str
    strategy_digest: str
    resource_ref: ResourceRef
    resource_identity_digest: str
    evidence_state: RoutingEvidenceState
    metrics: Mapping[str, float | None]
    evidence_refs: tuple[str, ...]
    observed_at: str
    fresh_until: str
    calibration_ref: str | None
    supersedes: str | None
    estimate_ref: str = field(init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.capability_ref, CapabilityRef):
            raise RoutingLearningError("estimate Project or Capability is malformed")
        _key(self.estimate_id, "estimate identity")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise RoutingLearningError("estimate version must be positive")
        for value, label in ((self.workload_ref, "workload"), (self.strategy_ref, "strategy")):
            _ref(value, label)
        for value, label in ((self.workload_digest, "workload digest"), (self.implementation_record_sha256, "implementation digest"), (self.strategy_digest, "strategy digest"), (self.resource_identity_digest, "resource identity digest")):
            _sha(value, label)
        if not isinstance(self.implementation_ref, CapabilityImplementationRef) or self.implementation_ref.project_ref != self.project_ref:
            raise RoutingLearningError("estimate implementation crossed Project scope")
        if not isinstance(self.resource_ref, ResourceRef) or self.resource_ref.project_ref != self.project_ref:
            raise RoutingLearningError("estimate Resource crossed Project scope")
        if not isinstance(self.evidence_state, RoutingEvidenceState):
            raise RoutingLearningError("estimate evidence state is malformed")
        metrics = _metrics(self.metrics, "estimate metrics")
        if not metrics:
            raise RoutingLearningError("estimate metrics are required")
        object.__setattr__(self, "metrics", metrics)
        refs = tuple(self.evidence_refs)
        if not refs or len(refs) > 128 or len(set(refs)) != len(refs):
            raise RoutingLearningError("estimate evidence refs are missing or duplicated")
        for item in refs:
            _ref(item, "estimate evidence")
        object.__setattr__(self, "evidence_refs", tuple(sorted(refs)))
        observed = _timestamp(self.observed_at, "estimate observed_at")
        fresh = _timestamp(self.fresh_until, "estimate fresh_until")
        if fresh <= observed or fresh <= datetime.now(timezone.utc):
            raise RoutingLearningError("estimate freshness must be future and follow observation")
        if self.calibration_ref is not None:
            _ref(self.calibration_ref, "calibration")
        if self.supersedes is not None:
            _ref(self.supersedes, "superseded estimate")
        identity = _digest(
            {
                "capability": self.capability_ref.value,
                "implementation": self.implementation_ref.value,
                "project": self.project_ref.value,
                "resource": self.resource_ref.value,
                "strategy": self.strategy_ref,
                "workload": self.workload_ref,
            }
        )[:32]
        ref = f"routing-estimate://{self.project_ref.value}/{self.estimate_id}/{self.version}/{identity}"
        object.__setattr__(self, "estimate_ref", ref)
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"calibration": self.calibration_ref, "capability": self.capability_ref.value, "evidence": list(self.evidence_refs), "evidence_state": self.evidence_state.value, "estimate": self.estimate_ref, "implementation": self.implementation_ref.value, "implementation_digest": self.implementation_record_sha256, "metrics": dict(self.metrics), "observed_at": self.observed_at, "project": self.project_ref.value, "resource": self.resource_ref.value, "resource_digest": self.resource_identity_digest, "strategy": self.strategy_ref, "strategy_digest": self.strategy_digest, "supersedes": self.supersedes, "workload": self.workload_ref, "workload_digest": self.workload_digest}


@dataclass(frozen=True)
class RoutingLearningPolicy:
    project_ref: ProjectRef
    policy_ref: str
    objective: RoutingObjective
    weights: Mapping[str, float]
    exploration_mode: ExplorationMode
    thresholds: Mapping[str, float] = field(default_factory=dict)
    version: int = 1
    formula_ref: str | None = None
    enabled: bool = True
    allow_side_effect_exploration: bool = False
    exploration_fraction: float = 0.0
    maximum_exploration_risk: str = "LOW"
    policy_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.objective, RoutingObjective) or not isinstance(self.exploration_mode, ExplorationMode):
            raise RoutingLearningError("learning policy identity is malformed")
        _ref(self.policy_ref, "learning policy")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise RoutingLearningError("learning policy version must be positive")
        if not isinstance(self.enabled, bool) or not isinstance(self.allow_side_effect_exploration, bool):
            raise RoutingLearningError("learning policy flags are malformed")
        if (
            isinstance(self.exploration_fraction, bool)
            or not isinstance(self.exploration_fraction, (int, float))
            or not math.isfinite(float(self.exploration_fraction))
            or not 0.0 <= float(self.exploration_fraction) <= 1.0
        ):
            raise RoutingLearningError("exploration fraction must be between zero and one")
        if self.maximum_exploration_risk not in {"LOW", "MEDIUM"}:
            raise RoutingLearningError("maximum exploration risk is malformed")
        weights = _metrics(self.weights, "learning weights")
        if any(value is None or value < 0 for value in weights.values()) or not any(value and value > 0 for value in weights.values()):
            raise RoutingLearningError("learning weights must be non-negative and contain a positive value")
        object.__setattr__(self, "weights", MappingProxyType({key: float(value) for key, value in weights.items() if value is not None}))
        thresholds = _metrics(self.thresholds, "learning thresholds")
        if any(value is None for value in thresholds.values()):
            raise RoutingLearningError("learning thresholds must be known finite values")
        object.__setattr__(self, "thresholds", MappingProxyType({key: float(value) for key, value in thresholds.items() if value is not None}))
        if self.formula_ref is None:
            object.__setattr__(self, "formula_ref", "routing-formula://p4-03/weighted-v1")
        _ref(self.formula_ref, "learning formula")
        object.__setattr__(self, "policy_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"allow_side_effect_exploration": self.allow_side_effect_exploration, "enabled": self.enabled, "exploration": self.exploration_mode.value, "exploration_fraction": float(self.exploration_fraction), "formula": self.formula_ref, "maximum_exploration_risk": self.maximum_exploration_risk, "objective": self.objective.value, "policy": self.policy_ref, "project": self.project_ref.value, "thresholds": dict(self.thresholds), "version": self.version, "weights": dict(self.weights)}


@dataclass(frozen=True)
class RoutingExplanation:
    estimate_ref: str | None
    components: Mapping[str, float | None]
    rejected_thresholds: tuple[str, ...]
    baseline_reason: str | None
    hard_eligible_candidates: tuple[str, ...] = ()
    ranked_estimates: tuple[str, ...] = ()
    objective: str | None = None
    formula_ref: str | None = None

    def __post_init__(self) -> None:
        if self.estimate_ref is not None:
            _ref(self.estimate_ref, "explanation estimate")
        object.__setattr__(self, "components", _metrics(self.components, "explanation components"))
        values = tuple(self.rejected_thresholds)
        if len(values) > 64 or len(set(values)) != len(values):
            raise RoutingLearningError("explanation threshold list is malformed")
        for value in values:
            _key(value, "explanation threshold")
        object.__setattr__(self, "rejected_thresholds", tuple(sorted(values)))
        for value in self.hard_eligible_candidates:
            _ref(value, "hard-eligible candidate")
        for value in self.ranked_estimates:
            _ref(value, "ranked estimate")
        if self.formula_ref is not None:
            _ref(self.formula_ref, "explanation formula")


@dataclass(frozen=True)
class RoutingLearningDecision:
    routing_decision: RoutingDecision
    request: RoutingRequest
    learning_policy: RoutingLearningPolicy
    selected_implementation_ref: CapabilityImplementationRef | None
    selected_resource_ref: ResourceRef | None
    selected_estimate: RoutingEstimate | None
    evidence_state: RoutingEvidenceState
    explanation: RoutingExplanation
    used_baseline: bool
    exploration_executed: bool
    calibration_ref: str | None
    rollback_baseline_ref: str | None
    source_request_sha256: str | None = None
    shadow_selected_implementation_ref: CapabilityImplementationRef | None = None
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.routing_decision.decision_ref.project_ref != self.request.project_ref or self.learning_policy.project_ref != self.request.project_ref:
            raise RoutingLearningError("learning decision crossed Project scope")
        if self.selected_implementation_ref is not None and self.selected_implementation_ref.project_ref != self.request.project_ref:
            raise RoutingLearningError("learning selection crossed Project scope")
        if self.selected_resource_ref is not None and self.selected_resource_ref.project_ref != self.request.project_ref:
            raise RoutingLearningError("learning Resource selection crossed Project scope")
        if self.selected_estimate is not None and self.selected_estimate.project_ref != self.request.project_ref:
            raise RoutingLearningError("learning estimate crossed Project scope")
        if not isinstance(self.evidence_state, RoutingEvidenceState) or not isinstance(self.used_baseline, bool) or not isinstance(self.exploration_executed, bool):
            raise RoutingLearningError("learning decision state is malformed")
        if not isinstance(self.exploration_executed, bool):
            raise RoutingLearningError("exploration execution state is malformed")
        if self.calibration_ref is not None:
            _ref(self.calibration_ref, "decision calibration")
        if self.rollback_baseline_ref is not None:
            _ref(self.rollback_baseline_ref, "rollback baseline")
        if self.source_request_sha256 is not None:
            _sha(self.source_request_sha256, "source request digest")
        if self.shadow_selected_implementation_ref is not None and self.shadow_selected_implementation_ref.project_ref != self.request.project_ref:
            raise RoutingLearningError("shadow selection crossed Project scope")
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    @property
    def ineligible_implementations(self) -> tuple[CapabilityImplementationRef, ...]:
        return tuple(item.implementation_ref for item in self.routing_decision.candidates if not item.eligible)

    def payload(self) -> dict[str, object]:
        return {"baseline": self.used_baseline, "calibration": self.calibration_ref, "estimate": None if self.selected_estimate is None else self.selected_estimate.canonical_digest, "evidence_state": self.evidence_state.value, "explanation": {"baseline_reason": self.explanation.baseline_reason, "components": dict(self.explanation.components), "estimate": self.explanation.estimate_ref, "formula": self.explanation.formula_ref, "hard_eligible": list(self.explanation.hard_eligible_candidates), "objective": self.explanation.objective, "ranked_estimates": list(self.explanation.ranked_estimates), "rejected_thresholds": list(self.explanation.rejected_thresholds)}, "learning_policy": self.learning_policy.policy_sha256, "request": self.request.request_sha256, "rollback_baseline": self.rollback_baseline_ref, "routing_decision": self.routing_decision.record_sha256, "selected_implementation": None if self.selected_implementation_ref is None else self.selected_implementation_ref.value, "selected_resource": None if self.selected_resource_ref is None else self.selected_resource_ref.value, "shadow_selected_implementation": None if self.shadow_selected_implementation_ref is None else self.shadow_selected_implementation_ref.value, "source_request": self.source_request_sha256}


@dataclass(frozen=True)
class RoutingCalibration:
    project_ref: ProjectRef
    calibration_ref: str
    estimate_ref: str
    routing_decision_ref: str
    predicted_metrics: Mapping[str, float | None]
    observed_metrics: Mapping[str, float | None]
    evidence_refs: tuple[str, ...]
    measured_at: str
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise RoutingLearningError("calibration Project is malformed")
        for value, label in ((self.calibration_ref, "calibration"), (self.estimate_ref, "calibration estimate"), (self.routing_decision_ref, "calibration route")):
            _ref(value, label)
        object.__setattr__(self, "predicted_metrics", _metrics(self.predicted_metrics, "predicted metrics"))
        object.__setattr__(self, "observed_metrics", _metrics(self.observed_metrics, "observed metrics"))
        if set(self.predicted_metrics) != set(self.observed_metrics):
            raise RoutingLearningError("calibration metric identities differ")
        if not self.evidence_refs or len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise RoutingLearningError("calibration evidence is missing or duplicated")
        for value in self.evidence_refs:
            _ref(value, "calibration evidence")
        _timestamp(self.measured_at, "calibration measured_at")
        object.__setattr__(self, "canonical_digest", _digest({"calibration": self.calibration_ref, "estimate": self.estimate_ref, "evidence": sorted(self.evidence_refs), "measured_at": self.measured_at, "observed": dict(self.observed_metrics), "predicted": dict(self.predicted_metrics), "project": self.project_ref.value, "route": self.routing_decision_ref}))


class RoutingLearningService:
    """Ranks P1-eligible candidates; it never admits, schedules, or executes a route."""

    def __init__(self, database_path: str | Path, *, routing_service: RoutingService | None = None) -> None:
        self.database_path = Path(database_path).resolve()
        if routing_service is not None and routing_service.database_path != self.database_path:
            raise RoutingLearningError("RoutingLearningService and RoutingService must share one database scope")
        self.routing = routing_service or RoutingService(self.database_path)
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS routing_learning_receipts (
                    project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
                    routing_record_sha256 TEXT NOT NULL, receipt_json TEXT NOT NULL,
                    receipt_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, decision_id),
                    FOREIGN KEY (project_id, decision_id, routing_record_sha256)
                      REFERENCES routing_decisions(project_id, decision_id, record_sha256)
                      ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS routing_learning_receipts_no_update
                  BEFORE UPDATE ON routing_learning_receipts
                  BEGIN SELECT RAISE(ABORT, 'RoutingLearning receipt is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS routing_learning_receipts_no_delete
                  BEFORE DELETE ON routing_learning_receipts
                  BEGIN SELECT RAISE(ABORT, 'RoutingLearning receipt cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def _estimate_score(estimate: RoutingEstimate, policy: RoutingLearningPolicy) -> tuple[float | None, Mapping[str, float | None], tuple[str, ...]]:
        components: dict[str, float | None] = {}
        rejected: list[str] = []
        total = 0.0
        known = False
        for metric, weight in policy.weights.items():
            value = estimate.metrics.get(metric)
            components[metric] = value
            threshold = policy.thresholds.get(metric)
            lower_is_better = metric in {"latency_ms", "cost"}
            if threshold is not None and (value is None or (value > threshold if lower_is_better else value < threshold)):
                rejected.append(metric)
                continue
            if value is None:
                continue
            known = True
            direction = -1.0 if lower_is_better else 1.0
            total += direction * weight * value
        return (total if known else None), MappingProxyType(dict(sorted(components.items()))), tuple(sorted(rejected))

    @staticmethod
    def _estimate_key(estimate: RoutingEstimate) -> tuple[str, ...]:
        return (
            estimate.workload_ref,
            estimate.workload_digest,
            estimate.capability_ref.value,
            estimate.implementation_ref.value,
            estimate.implementation_record_sha256,
            estimate.strategy_ref,
            estimate.strategy_digest,
            estimate.resource_ref.value,
            estimate.resource_identity_digest,
        )

    def _active_estimates(self, estimates: Sequence[RoutingEstimate]) -> tuple[RoutingEstimate, ...]:
        if isinstance(estimates, (str, bytes)) or not isinstance(estimates, Sequence) or len(estimates) > 4096:
            raise RoutingLearningError("estimate set is malformed or unbounded")
        values = tuple(estimates)
        if not all(isinstance(item, RoutingEstimate) for item in values):
            raise RoutingLearningError("estimate set contains malformed evidence")
        by_ref = {item.estimate_ref: item for item in values}
        if len(by_ref) != len(values):
            raise RoutingLearningError("estimate identity is duplicated")
        for item in values:
            if item.supersedes is None or item.supersedes not in by_ref:
                continue
            prior = by_ref[item.supersedes]
            if self._estimate_key(prior) != self._estimate_key(item) or prior.version >= item.version:
                raise RoutingLearningError("estimate supersession identity is invalid")
        active: dict[tuple[str, ...], RoutingEstimate] = {}
        for item in values:
            key = self._estimate_key(item)
            active_prior = active.get(key)
            if active_prior is None or item.version > active_prior.version:
                active[key] = item
            elif item.version == active_prior.version:
                raise RoutingLearningError("estimate revision is ambiguous")
        return tuple(sorted(active.values(), key=lambda item: item.estimate_ref))

    def _validate_estimate(self, access: ProjectAccess, request: RoutingRequest, estimate: RoutingEstimate) -> None:
        if estimate.project_ref != request.project_ref or estimate.capability_ref != request.capability_ref:
            raise RoutingLearningError("estimate crossed Project scope or Capability")
        _timestamp(estimate.fresh_until, "estimate fresh_until")
        if _timestamp(estimate.fresh_until, "estimate fresh_until") <= datetime.now(timezone.utc):
            raise RoutingLearningError("estimate is stale")
        implementation = self.routing.registry.get(access, estimate.implementation_ref)
        if implementation.record_sha256 != estimate.implementation_record_sha256:
            raise RoutingLearningError("estimate implementation revision is stale")

    def _persist(self, decision: RoutingLearningDecision) -> RoutingLearningDecision:
        receipt = _canonical(decision.payload())
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT receipt_json,receipt_sha256 FROM routing_learning_receipts WHERE project_id=? AND decision_id=?",
                (decision.request.project_ref.value, decision.routing_decision.decision_ref.decision_id),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO routing_learning_receipts VALUES (?,?,?,?,?,?)",
                    (decision.request.project_ref.value, decision.routing_decision.decision_ref.decision_id, decision.routing_decision.record_sha256, receipt, decision.canonical_digest, decision.routing_decision.created_at),
                )
            elif not hmac.compare_digest(row["receipt_json"], receipt) or not hmac.compare_digest(row["receipt_sha256"], decision.canonical_digest):
                raise RoutingLearningError("immutable RoutingLearning receipt conflicts")
            connection.commit()
            return decision
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def route(self, access: ProjectAccess, request: RoutingRequest, *, learning_policy: RoutingLearningPolicy, estimates: Sequence[RoutingEstimate] | None, learned_state_available: bool = True, task_risk: str = "HIGH", side_effect_authority: str = "READ_ONLY") -> RoutingLearningDecision:
        if learning_policy.project_ref != request.project_ref:
            raise RoutingLearningError("learning policy crossed Project scope")
        if task_risk not in {"LOW", "MEDIUM", "HIGH", "DESTRUCTIVE"} or side_effect_authority not in {"READ_ONLY", "PROJECT_WRITE", "EXTERNAL_WRITE"}:
            raise RoutingLearningError("task risk or side-effect authority is malformed")
        rollback_ref = f"routing-baseline://{request.project_ref.value}/p1.deterministic.v1"
        if not learning_policy.enabled or not learned_state_available or estimates is None:
            base = self.routing.route(access, request)
            state = RoutingEvidenceState.DISABLED if not learning_policy.enabled else RoutingEvidenceState.FALLBACK_BASELINE
            result = RoutingLearningDecision(base, request, learning_policy, base.selected_implementation_ref, base.selected_resource_ref, None, state, RoutingExplanation(None, {}, (), "learning_disabled" if not learning_policy.enabled else "learned_state_unavailable"), True, False, None, rollback_ref, request.request_sha256)
            return self._persist(result)
        validated = self._active_estimates(estimates)
        for estimate in validated:
            self._validate_estimate(access, request, estimate)
        options: list[tuple[float, str, RoutingEstimate, Mapping[str, float | None], tuple[str, ...]]] = []
        for estimate in validated:
            if estimate.evidence_state not in _CURRENT_EVIDENCE:
                continue
            score, components, rejected = self._estimate_score(estimate, learning_policy)
            if score is not None and not rejected:
                options.append((score, estimate.estimate_ref, estimate, components, rejected))
        options.sort(key=lambda item: (item[0], item[1]), reverse=True)
        safe_bounded = (
            learning_policy.exploration_mode is ExplorationMode.BOUNDED_EXPLORATION
            and learning_policy.exploration_fraction > 0.0
            and task_risk in ({"LOW"} if learning_policy.maximum_exploration_risk == "LOW" else {"LOW", "MEDIUM"})
            and (side_effect_authority == "READ_ONLY" or learning_policy.allow_side_effect_exploration)
        )
        exploration_target: str | None = None
        if safe_bounded and len(options) > 1:
            bucket = int(_digest({"policy": learning_policy.policy_sha256, "request": request.request_sha256})[:8], 16) / 0xFFFFFFFF
            if bucket < learning_policy.exploration_fraction:
                options[0], options[1] = options[1], options[0]
                exploration_target = options[0][1]
        ranked_implementations: list[CapabilityImplementationRef] = []
        for _, _, estimate, _, _ in options:
            if estimate.implementation_ref not in ranked_implementations:
                ranked_implementations.append(estimate.implementation_ref)
        owner_preferences = request.policy.preferred_implementation_refs
        combined_preferences = owner_preferences + tuple(item for item in ranked_implementations if item not in owner_preferences)
        evaluation_only = learning_policy.exploration_mode in {ExplorationMode.EVALUATION_ONLY, ExplorationMode.SHADOW_EVALUATION}
        effective_request = request
        if options and not evaluation_only:
            effective_request = replace(request, policy=replace(request.policy, preferred_implementation_refs=combined_preferences))
        base = self.routing.route(access, effective_request)
        eligible = tuple(item for item in base.candidates if item.eligible)
        hard_eligible_refs = tuple(sorted(item.implementation_ref.value for item in eligible))
        if not eligible:
            result = RoutingLearningDecision(base, effective_request, learning_policy, None, None, None, RoutingEvidenceState.UNKNOWN_EVIDENCE, RoutingExplanation(None, {}, (), "no_hard_eligible_candidate", hard_eligible_refs, tuple(item[1] for item in options), learning_policy.objective.value, learning_policy.formula_ref), True, False, None, rollback_ref, request.request_sha256)
            return self._persist(result)
        if not options:
            result = RoutingLearningDecision(base, effective_request, learning_policy, base.selected_implementation_ref, base.selected_resource_ref, None, RoutingEvidenceState.UNKNOWN_EVIDENCE, RoutingExplanation(None, {}, (), "unknown_or_ineligible_evidence", hard_eligible_refs, (), learning_policy.objective.value, learning_policy.formula_ref), True, False, None, rollback_ref, request.request_sha256)
            return self._persist(result)
        selected_option = next((item for item in options if item[2].implementation_ref == base.selected_implementation_ref and item[2].resource_ref == base.selected_resource_ref), None)
        shadow = options[0][2].implementation_ref if evaluation_only else None
        if selected_option is None or evaluation_only or base.selected_implementation_ref in owner_preferences:
            reason = "evaluation_only" if evaluation_only else "owner_instruction_or_current_resource_rank"
            result = RoutingLearningDecision(base, effective_request, learning_policy, base.selected_implementation_ref, base.selected_resource_ref, None, RoutingEvidenceState.OBSERVED, RoutingExplanation(options[0][2].estimate_ref, options[0][3], options[0][4], reason, hard_eligible_refs, tuple(item[1] for item in options), learning_policy.objective.value, learning_policy.formula_ref), True, False, None, rollback_ref, request.request_sha256, shadow)
            return self._persist(result)
        _, _, estimate, components, rejected = selected_option
        exploration_executed = exploration_target == estimate.estimate_ref
        result = RoutingLearningDecision(base, effective_request, learning_policy, base.selected_implementation_ref, base.selected_resource_ref, estimate, estimate.evidence_state, RoutingExplanation(estimate.estimate_ref, components, rejected, None, hard_eligible_refs, tuple(item[1] for item in options), learning_policy.objective.value, learning_policy.formula_ref), False, exploration_executed, estimate.calibration_ref, rollback_ref, request.request_sha256)
        return self._persist(result)

    def scheduling_request(self, access: ProjectAccess, decision: RoutingLearningDecision, *, priority: int = 0) -> SchedulingRequest:
        """Require the P1 decision and scheduler to revalidate selected live resources."""
        if decision.selected_estimate is not None:
            self._validate_estimate(access, decision.request, decision.selected_estimate)
            selected_candidate = next((item for item in decision.routing_decision.candidates if item.eligible and item.implementation_ref == decision.selected_implementation_ref and item.resource_ref == decision.selected_resource_ref), None)
            if selected_candidate is None or selected_candidate.snapshot_record_sha256 != decision.selected_estimate.resource_identity_digest:
                raise RoutingLearningError("selected Resource identity changed before scheduler allocation")
        if decision.selected_implementation_ref != decision.routing_decision.selected_implementation_ref or decision.selected_resource_ref != decision.routing_decision.selected_resource_ref:
            raise RoutingLearningError("learned rank differs from P1 routing receipt; a fresh P1 route is required before scheduling")
        return self.routing.scheduling_request(access, decision.routing_decision, priority=priority)


__all__ = [
    "ExplorationMode",
    "RoutingEstimate",
    "RoutingEvidenceState",
    "RoutingExplanation",
    "RoutingLearningDecision",
    "RoutingLearningError",
    "RoutingLearningPolicy",
    "RoutingLearningService",
    "RoutingObjective",
    "RoutingCalibration",
]
