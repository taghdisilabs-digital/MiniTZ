"""One scoped MiniTZ routing family over core, learning, evaluation, and live routes.

The family is an attachment and receipt boundary, not another route selector.  The
existing :class:`RoutingService` remains the only authority that admits an
implementation/resource pair; :class:`RoutingLearningService` may only rank that
already-eligible set.  Evaluation and provider metadata are recorded as evidence
and never become a liveness gate or a second semantic capability identity.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import Any, cast

from .capability import CapabilityRef
from .model_evaluation import ModelEvaluationKnowledgeCandidate, ModelEvaluationResult
from .project import ProjectAccess, ProjectRef
from .resource import ResourceRef
from .routing import CapabilityImplementationRef, RoutingDecision, RoutingRequest, RoutingService
from .routing_learning import (
    RoutingEstimate,
    RoutingLearningDecision,
    RoutingLearningPolicy,
    RoutingLearningService,
    RoutingObjective,
    ExplorationMode,
)


_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,1024}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_FAMILY_REVISION = "routing-family.v1"
_LIVE_STATES = frozenset({"SELECTED", "FALLBACK", "CANDIDATE", "UNAVAILABLE", "OBSERVED"})


class RoutingFamilyError(ValueError):
    """Base failure for the MiniTZ routing-family attachment."""


class RoutingFamilyScopeError(RoutingFamilyError):
    """The family attempted to combine evidence from different scopes."""


class RoutingFamilyAuthorityError(RoutingFamilyError):
    """More than one routing decision authority was introduced."""


class RoutingFamilyConflictError(RoutingFamilyError):
    """An immutable family receipt conflicts with existing evidence."""


class RoutingFamilyIntegrityError(RoutingFamilyError):
    """A persisted family receipt failed exact readback verification."""


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise RoutingFamilyError("routing-family evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise RoutingFamilyError(f"{label} must be an exact absolute reference")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise RoutingFamilyError(f"{label} must be a SHA-256 digest")
    return value


def _text(value: object, label: str, *, allow_empty: bool = False, limit: int = 2048) -> str:
    if (
        not isinstance(value, str)
        or (not allow_empty and not value)
        or len(value.encode("utf-8")) > limit
        or any(ord(character) < 32 for character in value)
    ):
        raise RoutingFamilyError(f"{label} is malformed or unbounded")
    return value


def _refs(values: Sequence[str], label: str, *, required: bool = False, limit: int = 256) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise RoutingFamilyError(f"{label} must be a sequence")
    copied = tuple(values)
    if len(copied) > limit or len(copied) != len(set(copied)) or (required and not copied):
        raise RoutingFamilyError(f"{label} is missing, duplicated, or unbounded")
    for value in copied:
        _ref(value, label)
    return tuple(sorted(copied))


def _metadata(values: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(values, Mapping) or len(values) > 128:
        raise RoutingFamilyError("live route metadata is malformed or unbounded")
    copied: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or _KEY.fullmatch(key) is None:
            raise RoutingFamilyError("live route metadata key is malformed")
        copied[key] = _text(value, "live route metadata value")
    return MappingProxyType(dict(sorted(copied.items())))


def _optional_identity(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label, limit=512)


@dataclass(frozen=True)
class RoutingFamilyScope:
    """The exact workload/resource/environment scope of one routing family."""

    project_ref: ProjectRef
    capability_ref: CapabilityRef
    workload_ref: str
    workload_digest: str
    resource_scope: tuple[ResourceRef, ...] = ()
    environment_ref: str = "environment://default"
    scope_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.capability_ref, CapabilityRef):
            raise RoutingFamilyScopeError("family Project or Capability identity is malformed")
        _ref(self.workload_ref, "family workload")
        _sha(self.workload_digest, "family workload digest")
        _ref(self.environment_ref, "family environment")
        resources = tuple(self.resource_scope)
        if len(resources) > 256 or len(resources) != len(set(resources)):
            raise RoutingFamilyScopeError("family Resource scope is duplicated or unbounded")
        if any(not isinstance(item, ResourceRef) or item.project_ref != self.project_ref for item in resources):
            raise RoutingFamilyScopeError("family Resource scope crossed Project boundary")
        object.__setattr__(self, "resource_scope", tuple(sorted(resources, key=lambda item: item.value)))
        object.__setattr__(self, "scope_digest", _digest(self.payload()))

    @classmethod
    def from_request(
        cls,
        request: RoutingRequest,
        *,
        workload_ref: str,
        workload_digest: str,
        environment_ref: str = "environment://default",
    ) -> "RoutingFamilyScope":
        if not isinstance(request, RoutingRequest):
            raise RoutingFamilyScopeError("family scope requires an exact RoutingRequest")
        return cls(
            request.project_ref,
            request.capability_ref,
            workload_ref,
            workload_digest,
            request.resource_refs,
            environment_ref,
        )

    @property
    def resource_refs(self) -> tuple[ResourceRef, ...]:
        """Compatibility spelling matching :class:`RoutingRequest`."""
        return self.resource_scope

    def payload(self) -> dict[str, object]:
        return {
            "capability_ref": self.capability_ref.value,
            "environment_ref": self.environment_ref,
            "project_ref": self.project_ref.value,
            "resource_scope": [item.value for item in self.resource_scope],
            "workload_digest": self.workload_digest,
            "workload_ref": self.workload_ref,
        }


@dataclass(frozen=True)
class RoutingValueReceipt:
    """Evidence that retired behavior was transferred to an explicit destination."""

    retired_ref: str
    destination_ref: str
    evidence_refs: tuple[str, ...]
    reason: str
    receipt_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _ref(self.retired_ref, "retired behavior")
        _ref(self.destination_ref, "retired behavior destination")
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs, "retired behavior evidence", required=True))
        _text(self.reason, "retired behavior reason", limit=2048)
        object.__setattr__(self, "receipt_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "destination_ref": self.destination_ref,
            "evidence_refs": list(self.evidence_refs),
            "reason": self.reason,
            "retired_ref": self.retired_ref,
        }


@dataclass(frozen=True)
class LiveProviderRoute:
    """Provider/model/tool selection metadata attached without semantic authority."""

    capability_ref: CapabilityRef
    route_ref: str
    provider_ref: str | None = None
    model_ref: str | None = None
    tool_ref: str | None = None
    implementation_ref: CapabilityImplementationRef | None = None
    resource_ref: ResourceRef | None = None
    reasoning: str | None = None
    route_state: str = "SELECTED"
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    route_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.capability_ref, CapabilityRef):
            raise RoutingFamilyError("live route Capability identity is malformed")
        _ref(self.route_ref, "live route")
        _optional_identity(self.provider_ref, "live provider identity")
        _optional_identity(self.model_ref, "live model identity")
        _optional_identity(self.tool_ref, "live tool identity")
        if self.implementation_ref is not None and not isinstance(self.implementation_ref, CapabilityImplementationRef):
            raise RoutingFamilyError("live implementation metadata is malformed")
        if self.resource_ref is not None and not isinstance(self.resource_ref, ResourceRef):
            raise RoutingFamilyError("live Resource metadata is malformed")
        if self.reasoning is not None:
            _text(self.reasoning, "live route reasoning", limit=128)
        if self.route_state not in _LIVE_STATES:
            raise RoutingFamilyError("live route state is unsupported")
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs, "live route evidence"))
        object.__setattr__(self, "metadata", _metadata(self.metadata))
        object.__setattr__(self, "route_digest", _digest(self.payload()))

    @classmethod
    def from_route(cls, scope: RoutingFamilyScope, route: object) -> "LiveProviderRoute":
        """Adapt a replaceable live router ``Route`` without importing that router."""
        if isinstance(route, cls):
            return route
        if isinstance(route, Mapping):
            return cls.from_mapping(scope, route)
        provider = getattr(route, "provider", None)
        model = getattr(route, "model", None)
        reasoning = getattr(route, "reasoning", None)
        if provider is None and model is None and reasoning is None:
            raise RoutingFamilyError("live route lacks provider/model metadata")
        identity_payload = {"model": model, "provider": provider, "reasoning": reasoning}
        return cls(
            scope.capability_ref,
            f"live-route://{scope.project_ref.value}/{_digest(identity_payload)}",
            provider_ref=None if provider is None else str(provider),
            model_ref=None if model is None else str(model),
            reasoning=None if reasoning is None else str(reasoning),
            metadata={"identity_role": "IMPLEMENTATION_METADATA"},
        )

    @classmethod
    def from_mapping(cls, scope: RoutingFamilyScope, value: Mapping[str, object]) -> "LiveProviderRoute":
        if not isinstance(value, Mapping):
            raise RoutingFamilyError("live route mapping is malformed")
        provider = value.get("provider_ref", value.get("provider"))
        model = value.get("model_ref", value.get("model"))
        tool = value.get("tool_ref", value.get("tool"))
        route_ref = value.get("route_ref")
        if route_ref is None:
            route_identity = {"model": model, "provider": provider, "tool": tool}
            route_ref = f"live-route://{scope.project_ref.value}/{_digest(route_identity)}"
        raw_evidence = value.get("evidence_refs", ())
        raw_metadata = value.get("metadata", {})
        if not isinstance(raw_evidence, Sequence) or isinstance(raw_evidence, (str, bytes)):
            raise RoutingFamilyError("live route evidence is malformed")
        if not isinstance(raw_metadata, Mapping):
            raise RoutingFamilyError("live route metadata is malformed")
        metadata = dict(cast(Mapping[str, str], raw_metadata))
        metadata.setdefault("identity_role", "IMPLEMENTATION_METADATA")
        return cls(
            scope.capability_ref,
            cast(str, route_ref),
            provider_ref=None if provider is None else str(provider),
            model_ref=None if model is None else str(model),
            tool_ref=None if tool is None else str(tool),
            reasoning=None if value.get("reasoning") is None else str(value["reasoning"]),
            route_state=str(value.get("route_state", "SELECTED")),
            evidence_refs=tuple(cast(Sequence[str], raw_evidence)),
            metadata=metadata,
        )

    def payload(self) -> dict[str, object]:
        return {
            "capability_ref": self.capability_ref.value,
            "evidence_refs": list(self.evidence_refs),
            "implementation_ref": None if self.implementation_ref is None else self.implementation_ref.value,
            "metadata": dict(self.metadata),
            "model_ref": self.model_ref,
            "provider_ref": self.provider_ref,
            "reasoning": self.reasoning,
            "resource_ref": None if self.resource_ref is None else self.resource_ref.value,
            "route_ref": self.route_ref,
            "route_state": self.route_state,
            "tool_ref": self.tool_ref,
            "provider_model_tool_identity": "IMPLEMENTATION_METADATA",
        }


# The longer name is useful to callers that want to distinguish this metadata
# from the selected core CapabilityImplementation.
LiveRouteMetadata = LiveProviderRoute


@dataclass(frozen=True)
class RoutingFamilyDecision:
    """The immutable cross-plane attachment around one core route decision."""

    scope: RoutingFamilyScope
    learning_decision: RoutingLearningDecision
    evaluation_digests: tuple[str, ...]
    learning_evidence_digests: tuple[str, ...]
    live_route: LiveProviderRoute | None
    value_receipts: tuple[RoutingValueReceipt, ...]
    family_revision: str = _FAMILY_REVISION
    evaluation_evidence_refs: tuple[str, ...] = ()
    decision_authority_ref: str = field(init=False)
    family_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.scope, RoutingFamilyScope) or not isinstance(self.learning_decision, RoutingLearningDecision):
            raise RoutingFamilyError("family decision identity is malformed")
        request = self.learning_decision.request
        base = self.learning_decision.routing_decision
        if request.project_ref != self.scope.project_ref or request.capability_ref != self.scope.capability_ref:
            raise RoutingFamilyScopeError("family decision crossed Project or Capability scope")
        if tuple(request.resource_refs) != tuple(self.scope.resource_scope):
            raise RoutingFamilyScopeError("family decision Resource scope differs from request")
        if base.capability_ref != self.scope.capability_ref or base.decision_ref.project_ref != self.scope.project_ref:
            raise RoutingFamilyScopeError("core routing receipt crossed family scope")
        if not _KEY.fullmatch(self.family_revision):
            raise RoutingFamilyError("family revision is malformed")
        object.__setattr__(self, "evaluation_digests", self._digests(self.evaluation_digests, "evaluation digests"))
        object.__setattr__(self, "learning_evidence_digests", self._digests(self.learning_evidence_digests, "learning evidence digests"))
        object.__setattr__(self, "evaluation_evidence_refs", _refs(self.evaluation_evidence_refs, "evaluation evidence"))
        receipts = tuple(self.value_receipts)
        if len(receipts) > 256 or not all(isinstance(item, RoutingValueReceipt) for item in receipts):
            raise RoutingFamilyError("family value receipts are malformed or duplicated")
        if len(receipts) != len({item.retired_ref for item in receipts}):
            raise RoutingFamilyError("family value receipts are malformed or duplicated")
        object.__setattr__(self, "value_receipts", tuple(sorted(receipts, key=lambda item: item.retired_ref)))
        if self.live_route is not None and not isinstance(self.live_route, LiveProviderRoute):
            raise RoutingFamilyError("family live route metadata is malformed")
        if self.live_route is not None:
            if self.live_route.capability_ref != self.scope.capability_ref:
                raise RoutingFamilyScopeError("live route Capability differs from family scope")
            for item in (self.live_route.implementation_ref, self.live_route.resource_ref):
                if item is not None and item.project_ref != self.scope.project_ref:
                    raise RoutingFamilyScopeError("live route metadata crossed Project scope")
        authority = f"routing-family://{self.scope.project_ref.value}/{self.scope.scope_digest}"
        object.__setattr__(self, "decision_authority_ref", authority)
        object.__setattr__(self, "family_digest", _digest(self.payload()))

    @staticmethod
    def _digests(values: Sequence[str], label: str) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise RoutingFamilyError(f"{label} must be a sequence")
        copied = tuple(values)
        if len(copied) > 4096 or len(copied) != len(set(copied)):
            raise RoutingFamilyError(f"{label} is duplicated or unbounded")
        for value in copied:
            _sha(value, label)
        return tuple(sorted(copied))

    @property
    def routing_decision(self) -> RoutingDecision:
        """Expose the one authoritative core decision without copying it."""
        return self.learning_decision.routing_decision

    @property
    def selected_implementation_ref(self) -> CapabilityImplementationRef | None:
        return self.learning_decision.selected_implementation_ref

    @property
    def selected_resource_ref(self) -> ResourceRef | None:
        return self.learning_decision.selected_resource_ref

    @property
    def authority_collision_free(self) -> bool:
        return True

    def payload(self) -> dict[str, object]:
        return {
            "authority": "MINITZ_ROUTING_FAMILY",
            "decision_authority_ref": getattr(self, "decision_authority_ref", f"routing-family://{self.scope.project_ref.value}/{self.scope.scope_digest}"),
            "evaluation": {
                "digests": list(self.evaluation_digests),
                "evidence_refs": list(self.evaluation_evidence_refs),
                "liveness_gate": False,
            },
            "family_revision": self.family_revision,
            "learning": {
                "decision_digest": self.learning_decision.canonical_digest,
                "evidence_digests": list(self.learning_evidence_digests),
                "evidence_state": self.learning_decision.evidence_state.value,
                "policy_sha256": self.learning_decision.learning_policy.policy_sha256,
            },
            "live_route": None if self.live_route is None else self.live_route.payload(),
            "provider_model_tool_identity": "IMPLEMENTATION_METADATA",
            "routing_decision": self.learning_decision.routing_decision.record_sha256,
            "scope": self.scope.payload(),
            "value_receipts": [item.payload() | {"receipt_digest": item.receipt_digest} for item in self.value_receipts],
        }


class RoutingFamilyService:
    """Attach all MiniTZ route implementations to one scoped authority."""

    family_revision = _FAMILY_REVISION

    def __init__(
        self,
        database_path: str | Path,
        *,
        routing_service: RoutingService | None = None,
        learning_service: RoutingLearningService | None = None,
    ) -> None:
        self.database_path = Path(database_path).resolve()
        if routing_service is not None and routing_service.database_path != self.database_path:
            raise RoutingFamilyScopeError("family and core RoutingService must share one database")
        self.routing = routing_service or RoutingService(self.database_path)
        if learning_service is not None:
            if learning_service.database_path != self.database_path:
                raise RoutingFamilyScopeError("family and learning service must share one database")
            if learning_service.routing is not self.routing:
                raise RoutingFamilyAuthorityError("family cannot attach two RoutingService authorities")
            self.learning = learning_service
        else:
            self.learning = RoutingLearningService(self.database_path, routing_service=self.routing)
        self.projects = self.routing.projects
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS routing_family_receipts (
                    project_id TEXT NOT NULL,
                    scope_sha256 TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    routing_record_sha256 TEXT NOT NULL,
                    authority_ref TEXT NOT NULL,
                    family_json TEXT NOT NULL,
                    family_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, scope_sha256, decision_id),
                    UNIQUE (project_id, authority_ref, request_sha256),
                    FOREIGN KEY (project_id, decision_id, routing_record_sha256)
                      REFERENCES routing_decisions(project_id, decision_id, record_sha256)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS routing_family_receipts_no_update
                  BEFORE UPDATE ON routing_family_receipts
                  BEGIN SELECT RAISE(ABORT, 'RoutingFamily receipt is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS routing_family_receipts_no_delete
                  BEFORE DELETE ON routing_family_receipts
                  BEGIN SELECT RAISE(ABORT, 'RoutingFamily receipt cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def _default_policy(project_ref: ProjectRef) -> RoutingLearningPolicy:
        return RoutingLearningPolicy(
            project_ref,
            "routing-policy://minitz-family/disabled",
            RoutingObjective.QUALITY,
            {"quality": 1.0},
            ExplorationMode.DISABLED,
            enabled=False,
        )

    @staticmethod
    def _validate_scope(request: RoutingRequest, scope: RoutingFamilyScope) -> None:
        if not isinstance(request, RoutingRequest) or not isinstance(scope, RoutingFamilyScope):
            raise RoutingFamilyScopeError("family route requires exact request and scope contracts")
        if request.project_ref != scope.project_ref or request.capability_ref != scope.capability_ref:
            raise RoutingFamilyScopeError("family request crossed Project or Capability scope")
        if tuple(request.resource_refs) != tuple(scope.resource_scope):
            raise RoutingFamilyScopeError("family request Resource scope is not exact")

    @staticmethod
    def _evaluation_binding(
        scope: RoutingFamilyScope,
        evaluation_result: ModelEvaluationResult | None,
        knowledge_candidate: ModelEvaluationKnowledgeCandidate | None,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if evaluation_result is not None and not isinstance(evaluation_result, ModelEvaluationResult):
            raise RoutingFamilyError("evaluation evidence is not a ModelEvaluationResult")
        if knowledge_candidate is not None and not isinstance(knowledge_candidate, ModelEvaluationKnowledgeCandidate):
            raise RoutingFamilyError("knowledge evidence is not a ModelEvaluationKnowledgeCandidate")
        digests: list[str] = []
        evidence_refs: list[str] = []
        if evaluation_result is not None:
            suite = evaluation_result.suite
            if suite.project_ref != scope.project_ref or suite.capability_ref != scope.capability_ref:
                raise RoutingFamilyScopeError("evaluation evidence crossed family Project or Capability scope")
            digests.extend((evaluation_result.suite_digest, evaluation_result.canonical_digest))
            evidence_refs.append(f"evaluation-suite://{scope.project_ref.value}/{suite.suite_id}/{suite.version}")
        if knowledge_candidate is not None:
            if knowledge_candidate.project_ref != scope.project_ref:
                raise RoutingFamilyScopeError("knowledge evidence crossed family Project scope")
            if knowledge_candidate.routing_allowed or knowledge_candidate.promotion_allowed:
                raise RoutingFamilyAuthorityError("descriptive knowledge evidence cannot grant routing authority")
            if evaluation_result is not None and knowledge_candidate.suite_digest != evaluation_result.suite_digest:
                raise RoutingFamilyConflictError("knowledge evidence does not bind the exact evaluation suite")
            digests.extend((knowledge_candidate.suite_digest, knowledge_candidate.canonical_digest))
            evidence_refs.extend(knowledge_candidate.evidence_refs)
        return tuple(sorted(set(digests))), tuple(sorted(set(evidence_refs)))

    @staticmethod
    def _learning_binding(scope: RoutingFamilyScope, estimates: Sequence[RoutingEstimate] | None) -> tuple[str, ...]:
        if estimates is None:
            return ()
        if isinstance(estimates, (str, bytes)) or not isinstance(estimates, Sequence):
            raise RoutingFamilyError("learning evidence is not a bounded sequence")
        digests: list[str] = []
        for estimate in estimates:
            if not isinstance(estimate, RoutingEstimate):
                raise RoutingFamilyError("learning evidence contains a malformed estimate")
            if (
                estimate.project_ref != scope.project_ref
                or estimate.capability_ref != scope.capability_ref
                or estimate.workload_ref != scope.workload_ref
                or estimate.workload_digest != scope.workload_digest
                or estimate.resource_ref not in scope.resource_scope
            ):
                raise RoutingFamilyScopeError("learning evidence crossed family workload/resource scope")
            digests.append(estimate.canonical_digest)
        return tuple(sorted(set(digests)))

    @staticmethod
    def _live_binding(scope: RoutingFamilyScope, live_route: object | None) -> LiveProviderRoute | None:
        if live_route is None:
            return None
        result = LiveProviderRoute.from_route(scope, live_route)
        if result.capability_ref != scope.capability_ref:
            raise RoutingFamilyScopeError("live provider route crossed Capability scope")
        if result.resource_ref is not None and result.resource_ref not in scope.resource_scope:
            raise RoutingFamilyScopeError("live provider route crossed Resource scope")
        if result.implementation_ref is not None and result.implementation_ref.project_ref != scope.project_ref:
            raise RoutingFamilyScopeError("live implementation metadata crossed Project scope")
        return result

    def authority_collision_check(self) -> bool:
        """Return whether learning and core share the one decision authority."""
        return self.learning.routing is self.routing and self.learning.database_path == self.database_path

    def route(
        self,
        access: ProjectAccess,
        request: RoutingRequest,
        *,
        scope: RoutingFamilyScope,
        learning_policy: RoutingLearningPolicy | None = None,
        estimates: Sequence[RoutingEstimate] | None = None,
        evaluation_result: ModelEvaluationResult | None = None,
        knowledge_candidate: ModelEvaluationKnowledgeCandidate | None = None,
        live_route: object | None = None,
        value_receipts: Sequence[RoutingValueReceipt] = (),
        learned_state_available: bool = True,
        task_risk: str = "HIGH",
        side_effect_authority: str = "READ_ONLY",
    ) -> RoutingFamilyDecision:
        """Route through the existing authority and persist one family receipt.

        ``evaluation_result`` is validated and attached as descriptive evidence;
        it is deliberately never invoked as a completion or liveness condition.
        ``live_route`` is metadata from a replaceable provider/model/tool router;
        it cannot override the core decision.
        """
        self._validate_scope(request, scope)
        if not self.authority_collision_check():
            raise RoutingFamilyAuthorityError("family core and learning services do not share one authority")
        policy = self._default_policy(scope.project_ref) if learning_policy is None else learning_policy
        if not isinstance(policy, RoutingLearningPolicy) or policy.project_ref != scope.project_ref:
            raise RoutingFamilyScopeError("family learning policy crossed Project scope")
        evaluation_digests, evaluation_refs = self._evaluation_binding(scope, evaluation_result, knowledge_candidate)
        learning_digests = self._learning_binding(scope, estimates)
        route_metadata = self._live_binding(scope, live_route)
        receipts = tuple(value_receipts)
        if len(receipts) > 256 or not all(isinstance(item, RoutingValueReceipt) for item in receipts):
            raise RoutingFamilyError("family value receipts are malformed or unbounded")
        learning = self.learning.route(
            access,
            request,
            learning_policy=policy,
            estimates=estimates,
            learned_state_available=learned_state_available,
            task_risk=task_risk,
            side_effect_authority=side_effect_authority,
        )
        decision = RoutingFamilyDecision(
            scope,
            learning,
            evaluation_digests,
            learning_digests,
            route_metadata,
            receipts,
            evaluation_evidence_refs=evaluation_refs,
        )
        return self._persist(decision)

    def _persist(self, decision: RoutingFamilyDecision) -> RoutingFamilyDecision:
        receipt_json = _canonical(decision.payload())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT family_json,family_sha256 FROM routing_family_receipts WHERE project_id=? AND scope_sha256=? AND decision_id=?",
                (
                    decision.scope.project_ref.value,
                    decision.scope.scope_digest,
                    decision.routing_decision.decision_ref.decision_id,
                ),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO routing_family_receipts VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        decision.scope.project_ref.value,
                        decision.scope.scope_digest,
                        decision.routing_decision.decision_ref.decision_id,
                        decision.routing_decision.request_sha256,
                        decision.routing_decision.record_sha256,
                        decision.decision_authority_ref,
                        receipt_json,
                        decision.family_digest,
                        decision.routing_decision.created_at,
                    ),
                )
            elif not hmac.compare_digest(cast(str, row["family_json"]), receipt_json) or not hmac.compare_digest(cast(str, row["family_sha256"]), decision.family_digest):
                raise RoutingFamilyConflictError("immutable RoutingFamily receipt conflicts")
            connection.commit()
            return decision
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_receipt(self, access: ProjectAccess, scope: RoutingFamilyScope, decision_ref: object) -> Mapping[str, object]:
        if not isinstance(scope, RoutingFamilyScope):
            raise RoutingFamilyScopeError("family receipt requires an exact scope")
        self.projects.get_project(access, scope.project_ref)
        decision_id = getattr(decision_ref, "decision_id", None)
        if not isinstance(decision_id, str):
            raise RoutingFamilyError("family receipt requires an exact RoutingDecisionRef")
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT family_json,family_sha256 FROM routing_family_receipts WHERE project_id=? AND scope_sha256=? AND decision_id=?",
                (scope.project_ref.value, scope.scope_digest, decision_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise RoutingFamilyError("RoutingFamily receipt was not found")
        serialized = cast(str, row["family_json"])
        try:
            payload = json.loads(serialized)
        except json.JSONDecodeError as exc:
            raise RoutingFamilyIntegrityError("RoutingFamily receipt JSON is malformed") from exc
        if not isinstance(payload, dict) or _canonical(payload) != serialized or not hmac.compare_digest(cast(str, row["family_sha256"]), _digest(payload)):
            raise RoutingFamilyIntegrityError("RoutingFamily receipt readback differs")
        return MappingProxyType(cast(dict[str, object], payload))

    get_receipt_payload = get_receipt


# Explicit aliases keep the family name stable for MiniTZ callers while the
# implementation remains a normal reusable Biella service.
MiniTZRoutingFamily = RoutingFamilyService
RoutingFamily = RoutingFamilyService


__all__ = [
    "LiveProviderRoute",
    "LiveRouteMetadata",
    "MiniTZRoutingFamily",
    "RoutingFamily",
    "RoutingFamilyAuthorityError",
    "RoutingFamilyConflictError",
    "RoutingFamilyDecision",
    "RoutingFamilyError",
    "RoutingFamilyIntegrityError",
    "RoutingFamilyScope",
    "RoutingFamilyScopeError",
    "RoutingFamilyService",
    "RoutingValueReceipt",
]
