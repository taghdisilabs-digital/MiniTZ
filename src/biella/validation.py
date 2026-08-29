"""Task-derived validation and explicit evaluation evidence.

Validation answers whether one exact subject satisfies one immutable Task contract.
Evaluation records explicit measurements and never becomes acceptance implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import Mapping, Sequence, cast
from uuid import uuid4

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .call_ledger import CallLedgerService, ModelCallRef, ToolCallRef
from .capability import CapabilityRef
from .execution import NodeExecutionAttempt, NodeExecutionService
from .graph import GraphRef, GraphService, NodeRef
from .project import ProjectAccess, ProjectNotFoundError, ProjectRef, ProjectScopeError, ProjectStore
from .run import RunRef
from .task import Task, TaskRef, TaskRevisionService
from .workspace import WorkspaceRef, WorkspaceSnapshotRef


class ValidationError(Exception):
    """Base validation/evaluation failure."""


class ValidationContractError(ValidationError, ValueError):
    """A validation contract is malformed."""


class ValidationScopeError(ValidationError):
    """Validation evidence crossed Project scope."""


class ValidationAuthorityError(ValidationError, PermissionError):
    """Current Task/Graph/attempt authority rejected validation."""


class ValidationConflictError(ValidationError):
    """Idempotency or monotonic current-state semantics conflict."""


class ValidationNotFoundError(ValidationError):
    """Exact validation evidence was not found."""


class ValidationIntegrityError(ValidationError):
    """Persisted validation evidence failed verification."""


class ValidationVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"


class ValidationEvidenceState(str, Enum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"


_SHA = re.compile(r"[0-9a-f]{64}")
_ID = re.compile(r"[a-z]+_[0-9a-f]{32}")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]+")
_SUCCESS_RULES = {"ALL_REQUIRED_PASS"}
_SUBJECT_KINDS = {"ARTIFACT", "CONTENT", "WORKSPACE", "TOOL_CALL", "MODEL_CALL", "GIT_TREE", "BUILD", "RUNTIME", "EXTENSIBLE"}
_VALIDATOR_KINDS = {"DETERMINISTIC", "TOOL", "MODEL"}


def _json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValidationContractError("validation evidence must be canonical JSON") from exc


def _sha(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValidationContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationContractError(f"{name} must be timezone-aware")
    return value


def _key(value: object) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise ValidationContractError("idempotency_key is malformed")
    return value


def _name(value: object, label: str) -> str:
    if not isinstance(value, str) or _NAME.fullmatch(value) is None:
        raise ValidationContractError(f"{label} is malformed")
    return value


def _ref(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value.encode()) > 2048 or _REF.fullmatch(value) is None:
        raise ValidationContractError(f"{label} must be an exact bounded reference")
    return value


def _text(value: object, label: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum or "\x00" in value:
        raise ValidationContractError(f"{label} is malformed or unbounded")
    return value


def _freeze_scalar_mapping(value: Mapping[str, object], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or len(value) > 64:
        raise ValidationContractError(f"{label} is malformed or unbounded")
    copied = dict(value)
    for key, item in copied.items():
        _name(key, f"{label} key")
        if not isinstance(item, (str, int, float, bool, type(None))) or (isinstance(item, float) and not math.isfinite(item)):
            raise ValidationContractError(f"{label} values must be finite JSON scalars")
    return MappingProxyType(dict(sorted(copied.items())))


def _capability_text(ref: CapabilityRef) -> str:
    return f"{ref.capability_id}@{ref.version}"


def _capability_uri(ref: CapabilityRef) -> str:
    return f"capability://{ref.capability_id}/{ref.version}"


def _task_ref_text(ref: TaskRef) -> str:
    return f"task://{ref.project_ref.value}/{ref.task_id}/{ref.revision}"


def _run_ref_text(ref: RunRef) -> str:
    return f"run://{ref.project_ref.value}/{ref.run_id}"


@dataclass(frozen=True, order=True)
class ValidationPlanRef:
    project_ref: ProjectRef
    plan_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.plan_id, str) or re.fullmatch(r"vplan_[0-9a-f]{32}", self.plan_id) is None:
            raise ValidationContractError("ValidationPlanRef is malformed")

    @property
    def value(self) -> str:
        return f"validation-plan://{self.project_ref.value}/{self.plan_id}"


@dataclass(frozen=True, order=True)
class ValidationResultRef:
    project_ref: ProjectRef
    result_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.result_id, str) or re.fullmatch(r"vresult_[0-9a-f]{32}", self.result_id) is None:
            raise ValidationContractError("ValidationResultRef is malformed")

    @property
    def value(self) -> str:
        return f"validation-result://{self.project_ref.value}/{self.result_id}"


@dataclass(frozen=True, order=True)
class EvaluationResultRef:
    project_ref: ProjectRef
    evaluation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.evaluation_id, str) or re.fullmatch(r"eval_[0-9a-f]{32}", self.evaluation_id) is None:
            raise ValidationContractError("EvaluationResultRef is malformed")

    @property
    def value(self) -> str:
        return f"evaluation-result://{self.project_ref.value}/{self.evaluation_id}"


@dataclass(frozen=True)
class ValidationSubject:
    project_ref: ProjectRef
    subject_kind: str
    subject_ref: str
    exact_digest: str
    producer_dimensions: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)
    subject_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if self.subject_kind not in _SUBJECT_KINDS:
            raise ValidationContractError("Validation subject kind is unsupported")
        _ref(self.subject_ref, "subject_ref")
        if not isinstance(self.exact_digest, str) or _SHA.fullmatch(self.exact_digest) is None:
            raise ValidationContractError("Validation subject digest is not exact")
        dimensions = dict(self.producer_dimensions)
        if len(dimensions) > 32:
            raise ValidationContractError("producer dimensions are unbounded")
        for key, value in dimensions.items():
            _name(key, "producer dimension")
            _ref(value, "producer dimension ref")
        object.__setattr__(self, "producer_dimensions", MappingProxyType(dict(sorted(dimensions.items()))))
        object.__setattr__(self, "metadata", _freeze_scalar_mapping(self.metadata, "subject metadata"))
        object.__setattr__(self, "subject_sha256", _sha(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "exact_digest": self.exact_digest,
            "metadata": dict(self.metadata),
            "producer_dimensions": dict(self.producer_dimensions),
            "project_ref": self.project_ref.value,
            "subject_kind": self.subject_kind,
            "subject_ref": self.subject_ref,
        }


@dataclass(frozen=True)
class ValidationCheck:
    capability_ref: CapabilityRef
    required: bool
    source: str
    evidence_requirements: tuple[str, ...] = ()
    independence_dimensions: tuple[str, ...] = ()
    parameters: Mapping[str, object] = field(default_factory=dict)
    check_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.capability_ref, CapabilityRef) or not isinstance(self.required, bool):
            raise ValidationContractError("Validation check capability/required classification is malformed")
        _text(self.source, "Validation check source")
        evidence = tuple(sorted(set(_name(item, "evidence requirement") for item in self.evidence_requirements)))
        independence = tuple(sorted(set(_name(item, "independence dimension") for item in self.independence_dimensions)))
        if len(evidence) > 32 or len(independence) > 16:
            raise ValidationContractError("Validation check requirements are unbounded")
        object.__setattr__(self, "evidence_requirements", evidence)
        object.__setattr__(self, "independence_dimensions", independence)
        object.__setattr__(self, "parameters", _freeze_scalar_mapping(self.parameters, "Validation check parameters"))
        artifact_role = self.parameters.get("artifact_role")
        if artifact_role is not None:
            _name(artifact_role, "required Artifact role")
        source_artifact_ref = self.parameters.get("source_artifact_ref")
        if source_artifact_ref is not None:
            _ref(source_artifact_ref, "required source Artifact ref")
        object.__setattr__(self, "check_id", f"vchk_{_sha(self.semantic_payload())[:32]}")

    def semantic_payload(self) -> dict[str, object]:
        return {
            "capability_ref": _capability_text(self.capability_ref),
            "evidence_requirements": list(self.evidence_requirements),
            "independence_dimensions": list(self.independence_dimensions),
            "parameters": dict(self.parameters),
            "required": self.required,
            "source": self.source,
        }

    def payload(self) -> dict[str, object]:
        return {"check_id": self.check_id, **self.semantic_payload()}


@dataclass(frozen=True)
class ProjectValidationCriteria:
    project_ref: ProjectRef
    checks: tuple[ValidationCheck, ...]
    criteria_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.checks, tuple) or not all(isinstance(item, ValidationCheck) for item in self.checks):
            raise ValidationContractError("Project validation checks are malformed")
        checks = tuple(sorted(self.checks, key=lambda item: item.check_id))
        if len(checks) > 128 or len({item.check_id for item in checks}) != len(checks):
            raise ValidationContractError("Project validation checks are duplicated or unbounded")
        object.__setattr__(self, "checks", checks)
        _ref(self.criteria_ref, "Project criteria ref")


@dataclass(frozen=True)
class ValidationPlan:
    plan_ref: ValidationPlanRef
    sequence: int
    task_ref: TaskRef
    task_digest: str
    run_ref: RunRef
    graph_ref: GraphRef
    graph_record_sha256: str
    node_ref: NodeRef
    node_attempt_id: str
    node_attempt_fence: int
    subjects: tuple[ValidationSubject, ...]
    checks: tuple[ValidationCheck, ...]
    success_rule: str
    created_at: str
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.plan_ref, ValidationPlanRef) or not isinstance(self.task_ref, TaskRef) or not isinstance(self.run_ref, RunRef):
            raise ValidationContractError("ValidationPlan identity is malformed")
        if not isinstance(self.graph_ref, GraphRef) or not isinstance(self.node_ref, NodeRef) or self.node_ref.graph_ref != self.graph_ref:
            raise ValidationContractError("ValidationPlan Graph/Node identity is malformed")
        project = self.plan_ref.project_ref
        if any(ref.project_ref != project for ref in (self.task_ref, self.run_ref, self.graph_ref, self.node_ref)):
            raise ValidationScopeError("ValidationPlan identity crossed Project scope")
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise ValidationContractError("ValidationPlan sequence is malformed")
        for digest in (self.task_digest, self.graph_record_sha256):
            if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
                raise ValidationContractError("ValidationPlan exact digest is malformed")
        if not isinstance(self.node_attempt_id, str) or re.fullmatch(r"natt_[0-9a-f]{32}", self.node_attempt_id) is None or not isinstance(self.node_attempt_fence, int) or self.node_attempt_fence < 1:
            raise ValidationContractError("ValidationPlan attempt fence is malformed")
        subjects = tuple(sorted(self.subjects, key=lambda item: item.subject_ref))
        checks = tuple(sorted(self.checks, key=lambda item: item.check_id))
        if not subjects or len(subjects) > 128 or not checks or len(checks) > 128:
            raise ValidationContractError("ValidationPlan subjects/checks are empty or unbounded")
        if any(item.project_ref != project for item in subjects):
            raise ValidationScopeError("ValidationPlan subject crossed Project scope")
        if len({item.subject_ref for item in subjects}) != len(subjects) or len({item.check_id for item in checks}) != len(checks):
            raise ValidationContractError("ValidationPlan subjects/checks are duplicated")
        if self.success_rule not in _SUCCESS_RULES:
            raise ValidationContractError("ValidationPlan success rule is unsupported")
        object.__setattr__(self, "subjects", subjects)
        object.__setattr__(self, "checks", checks)
        _timestamp(self.created_at, "ValidationPlan created_at")
        semantic = _sha(self.semantic_payload())
        object.__setattr__(self, "semantic_digest", semantic)
        object.__setattr__(self, "record_sha256", _sha({"created_at": self.created_at, "plan_ref": self.plan_ref.value, "semantic_digest": semantic, "sequence": self.sequence}))

    @property
    def project_ref(self) -> ProjectRef:
        return self.plan_ref.project_ref

    def semantic_payload(self) -> dict[str, object]:
        return {
            "checks": [item.payload() for item in self.checks],
            "graph_record_sha256": self.graph_record_sha256,
            "graph_ref": self.graph_ref.value,
            "node_attempt_fence": self.node_attempt_fence,
            "node_attempt_id": self.node_attempt_id,
            "node_ref": self.node_ref.value,
            "run_ref": _run_ref_text(self.run_ref),
            "subjects": [item.payload() for item in self.subjects],
            "success_rule": self.success_rule,
            "task_digest": self.task_digest,
            "task_ref": _task_ref_text(self.task_ref),
        }

    def payload(self) -> dict[str, object]:
        return {"created_at": self.created_at, "plan_id": self.plan_ref.plan_id, "project_ref": self.project_ref.value, "sequence": self.sequence, **self.semantic_payload()}


@dataclass(frozen=True, order=True)
class MetricMeasurement:
    name: str
    value: float
    unit: str
    definition: str
    measurement_source_ref: str

    def __post_init__(self) -> None:
        _name(self.name, "metric name")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(float(self.value)):
            raise ValidationContractError("metric value must be finite")
        object.__setattr__(self, "value", float(self.value))
        _text(self.unit, "metric unit", 128)
        _text(self.definition, "metric definition", 2048)
        _ref(self.measurement_source_ref, "metric measurement source")

    def payload(self) -> dict[str, object]:
        return {"definition": self.definition, "measurement_source_ref": self.measurement_source_ref, "name": self.name, "unit": self.unit, "value": self.value}


@dataclass(frozen=True)
class CompositeMetric:
    name: str
    formula: str
    components: tuple[str, ...]
    weights: Mapping[str, float]
    score: float

    def __post_init__(self) -> None:
        _name(self.name, "composite metric name")
        _text(self.formula, "composite metric formula", 2048)
        components = tuple(sorted(set(_name(item, "composite component") for item in self.components)))
        weights = dict(self.weights)
        if not components or set(weights) != set(components):
            raise ValidationContractError("composite metric components and weights differ")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in weights.values()):
            raise ValidationContractError("composite metric weights must be finite")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)) or not math.isfinite(float(self.score)):
            raise ValidationContractError("composite metric score must be finite")
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "weights", MappingProxyType({key: float(weights[key]) for key in sorted(weights)}))
        object.__setattr__(self, "score", float(self.score))

    def payload(self) -> dict[str, object]:
        return {"components": list(self.components), "formula": self.formula, "name": self.name, "score": self.score, "weights": dict(self.weights)}


@dataclass(frozen=True)
class ValidationResult:
    result_ref: ValidationResultRef
    plan_ref: ValidationPlanRef
    plan_digest: str
    check_id: str
    subject_set_digest: str
    capability_ref: CapabilityRef
    validator_kind: str
    implementation_ref: str
    runtime_ref: str
    validator_dimensions: Mapping[str, str]
    verdict: ValidationVerdict
    findings_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    metrics: tuple[MetricMeasurement, ...]
    model_call_ref: ModelCallRef | None
    tool_call_ref: ToolCallRef | None
    evidence_state: ValidationEvidenceState
    error_reason: str | None
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.result_ref.project_ref != self.plan_ref.project_ref:
            raise ValidationScopeError("ValidationResult crossed Project scope")
        for digest in (self.plan_digest, self.subject_set_digest):
            if _SHA.fullmatch(digest) is None:
                raise ValidationContractError("ValidationResult digest is malformed")
        if not isinstance(self.check_id, str) or re.fullmatch(r"vchk_[0-9a-f]{32}", self.check_id) is None:
            raise ValidationContractError("ValidationResult check identity is malformed")
        if not isinstance(self.capability_ref, CapabilityRef) or self.validator_kind not in _VALIDATOR_KINDS:
            raise ValidationContractError("ValidationResult validator identity is malformed")
        _ref(self.implementation_ref, "validator implementation")
        _ref(self.runtime_ref, "validator runtime")
        dimensions = dict(self.validator_dimensions)
        if len(dimensions) > 32:
            raise ValidationContractError("validator dimensions are unbounded")
        for key, value in dimensions.items():
            _name(key, "validator dimension")
            _ref(value, "validator dimension ref")
        if dimensions.get("implementation") != self.implementation_ref or dimensions.get("runtime") != self.runtime_ref:
            raise ValidationContractError("validator dimensions differ from validator identity")
        if not isinstance(self.verdict, ValidationVerdict) or not isinstance(self.evidence_state, ValidationEvidenceState):
            raise ValidationContractError("ValidationResult verdict/state is malformed")
        findings = tuple(sorted(set(_ref(item, "finding ref") for item in self.findings_refs)))
        evidence = tuple(sorted(set(_ref(item, "evidence ref") for item in self.evidence_refs)))
        metrics = tuple(sorted(set(self.metrics), key=lambda item: item.name))
        if len(findings) > 128 or len(evidence) > 256 or len(metrics) > 128 or len({item.name for item in metrics}) != len(metrics):
            raise ValidationContractError("ValidationResult evidence is duplicated or unbounded")
        if self.model_call_ref is not None and self.model_call_ref.project_ref != self.result_ref.project_ref:
            raise ValidationScopeError("ValidationResult ModelCall crossed Project scope")
        if self.tool_call_ref is not None and self.tool_call_ref.project_ref != self.result_ref.project_ref:
            raise ValidationScopeError("ValidationResult ToolCall crossed Project scope")
        if self.validator_kind == "MODEL" and (self.model_call_ref is None or self.tool_call_ref is not None):
            raise ValidationContractError("model validator requires exactly one ModelCall")
        if self.validator_kind == "TOOL" and (self.tool_call_ref is None or self.model_call_ref is not None):
            raise ValidationContractError("tool validator requires exactly one ToolCall")
        if self.validator_kind == "DETERMINISTIC" and (self.model_call_ref is not None or self.tool_call_ref is not None):
            raise ValidationContractError("deterministic validator cannot claim model/tool ledger execution")
        if self.verdict is ValidationVerdict.ERROR:
            _text(self.error_reason, "validator error reason", 2048)
        elif self.error_reason is not None:
            raise ValidationContractError("only ERROR validation carries infrastructure error reason")
        object.__setattr__(self, "findings_refs", findings)
        object.__setattr__(self, "evidence_refs", evidence)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "validator_dimensions", MappingProxyType(dict(sorted(dimensions.items()))))
        _timestamp(self.created_at, "ValidationResult created_at")
        object.__setattr__(self, "record_sha256", _sha(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.result_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "capability_ref": _capability_text(self.capability_ref), "check_id": self.check_id,
            "created_at": self.created_at, "error_reason": self.error_reason,
            "evidence_refs": list(self.evidence_refs), "evidence_state": self.evidence_state.value,
            "findings_refs": list(self.findings_refs), "implementation_ref": self.implementation_ref,
            "metrics": [item.payload() for item in self.metrics],
            "model_call_ref": None if self.model_call_ref is None else self.model_call_ref.value,
            "plan_digest": self.plan_digest, "plan_ref": self.plan_ref.value,
            "result_ref": self.result_ref.value, "runtime_ref": self.runtime_ref,
            "subject_set_digest": self.subject_set_digest,
            "tool_call_ref": None if self.tool_call_ref is None else self.tool_call_ref.value,
            "validator_dimensions": dict(self.validator_dimensions),
            "validator_kind": self.validator_kind, "verdict": self.verdict.value,
        }


@dataclass(frozen=True)
class ValidationAggregate:
    plan_ref: ValidationPlanRef
    plan_digest: str
    verdict: ValidationVerdict
    accepted: bool
    evidence_state: ValidationEvidenceState
    required_result_refs: tuple[ValidationResultRef, ...]
    optional_result_refs: tuple[ValidationResultRef, ...]
    missing_required_check_ids: tuple[str, ...]
    created_at: str
    aggregate_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.plan_ref, ValidationPlanRef)
            or not isinstance(self.plan_digest, str)
            or _SHA.fullmatch(self.plan_digest) is None
            or not isinstance(self.verdict, ValidationVerdict)
            or not isinstance(self.accepted, bool)
            or not isinstance(self.evidence_state, ValidationEvidenceState)
        ):
            raise ValidationContractError("ValidationAggregate is malformed")
        required = tuple(sorted(self.required_result_refs, key=lambda item: item.result_id))
        optional = tuple(sorted(self.optional_result_refs, key=lambda item: item.result_id))
        missing = tuple(sorted(set(self.missing_required_check_ids)))
        if (
            any(item.project_ref != self.plan_ref.project_ref for item in (*required, *optional))
            or len(set(required + optional)) != len(required) + len(optional)
            or any(re.fullmatch(r"vchk_[0-9a-f]{32}", item) is None for item in missing)
        ):
            raise ValidationContractError("ValidationAggregate result evidence is malformed")
        if self.accepted != (self.verdict is ValidationVerdict.PASS and self.evidence_state is ValidationEvidenceState.CURRENT):
            raise ValidationContractError("ValidationAggregate acceptance differs from current PASS")
        object.__setattr__(self, "required_result_refs", required)
        object.__setattr__(self, "optional_result_refs", optional)
        object.__setattr__(self, "missing_required_check_ids", missing)
        _timestamp(self.created_at, "ValidationAggregate created_at")
        object.__setattr__(self, "aggregate_sha256", _sha(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"accepted": self.accepted, "created_at": self.created_at, "evidence_state": self.evidence_state.value, "missing_required_check_ids": list(self.missing_required_check_ids), "optional_result_refs": [item.value for item in self.optional_result_refs], "plan_digest": self.plan_digest, "plan_ref": self.plan_ref.value, "required_result_refs": [item.value for item in self.required_result_refs], "verdict": self.verdict.value}


@dataclass(frozen=True)
class EvaluationResult:
    evaluation_ref: EvaluationResultRef
    task_ref: TaskRef
    task_digest: str
    run_ref: RunRef
    graph_ref: GraphRef
    graph_record_sha256: str
    node_ref: NodeRef
    node_attempt_id: str
    node_attempt_fence: int
    authority_attempt_sha256: str
    subjects: tuple[ValidationSubject, ...]
    metrics: tuple[MetricMeasurement, ...]
    composites: tuple[CompositeMetric, ...]
    evidence_refs: tuple[str, ...]
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.evaluation_ref.project_ref
        if (
            self.task_ref.project_ref != project
            or self.run_ref.project_ref != project
            or self.graph_ref.project_ref != project
            or self.node_ref.project_ref != project
            or self.node_ref.graph_ref != self.graph_ref
            or any(item.project_ref != project for item in self.subjects)
        ):
            raise ValidationScopeError("EvaluationResult crossed Project scope")
        for digest in (self.task_digest, self.graph_record_sha256, self.authority_attempt_sha256):
            if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
                raise ValidationContractError("EvaluationResult authority digest is malformed")
        if (
            not isinstance(self.node_attempt_id, str)
            or re.fullmatch(r"natt_[0-9a-f]{32}", self.node_attempt_id) is None
            or not isinstance(self.node_attempt_fence, int)
            or self.node_attempt_fence < 1
        ):
            raise ValidationContractError("EvaluationResult attempt fence is malformed")
        subjects = tuple(sorted(self.subjects, key=lambda item: item.subject_ref))
        metrics = tuple(sorted(self.metrics, key=lambda item: item.name))
        composites = tuple(sorted(self.composites, key=lambda item: item.name))
        all_metric_names = {item.name for item in metrics} | {item.name for item in composites}
        if (
            not subjects
            or not metrics
            or len({item.subject_ref for item in subjects}) != len(subjects)
            or len(all_metric_names) != len(metrics) + len(composites)
        ):
            raise ValidationContractError("EvaluationResult subjects/metrics are empty or duplicated")
        metric_names = {item.name for item in metrics}
        if any(not set(item.components) <= metric_names for item in composites):
            raise ValidationContractError("Evaluation composite references missing raw dimensions")
        if any(item.name == "quality_score" for item in metrics):
            raise ValidationContractError("opaque quality_score is prohibited; record dimensions and explicit composite")
        object.__setattr__(self, "subjects", subjects)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "composites", composites)
        object.__setattr__(self, "evidence_refs", tuple(sorted(set(_ref(item, "evaluation evidence") for item in self.evidence_refs))))
        _timestamp(self.created_at, "EvaluationResult created_at")
        object.__setattr__(self, "record_sha256", _sha(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "authority_attempt_sha256": self.authority_attempt_sha256,
            "composites": [item.payload() for item in self.composites],
            "created_at": self.created_at,
            "evaluation_ref": self.evaluation_ref.value,
            "evidence_refs": list(self.evidence_refs),
            "graph_record_sha256": self.graph_record_sha256,
            "graph_ref": self.graph_ref.value,
            "metrics": [item.payload() for item in self.metrics],
            "node_attempt_fence": self.node_attempt_fence,
            "node_attempt_id": self.node_attempt_id,
            "node_ref": self.node_ref.value,
            "run_ref": _run_ref_text(self.run_ref),
            "subjects": [item.payload() for item in self.subjects],
            "task_digest": self.task_digest,
            "task_ref": _task_ref_text(self.task_ref),
        }


class ValidationService:
    """Durable compiler, result ledger, deterministic aggregator, and evaluator."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.graphs = GraphService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.calls = CallLedgerService(self.database_path)
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
                CREATE TABLE IF NOT EXISTS validation_plans(project_id TEXT NOT NULL,plan_id TEXT NOT NULL,sequence INTEGER NOT NULL,task_id TEXT NOT NULL,task_revision INTEGER NOT NULL,run_id TEXT NOT NULL,plan_json TEXT NOT NULL,semantic_digest TEXT NOT NULL,record_sha256 TEXT NOT NULL,PRIMARY KEY(project_id,plan_id),UNIQUE(project_id,task_id,task_revision,run_id,sequence),FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS validation_plan_claims(project_id TEXT NOT NULL,node_attempt_id TEXT NOT NULL,idempotency_key TEXT NOT NULL,semantic_digest TEXT NOT NULL,plan_id TEXT NOT NULL,PRIMARY KEY(project_id,node_attempt_id,idempotency_key),UNIQUE(project_id,plan_id),FOREIGN KEY(project_id,plan_id) REFERENCES validation_plans(project_id,plan_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS validation_plan_heads(project_id TEXT NOT NULL,task_id TEXT NOT NULL,task_revision INTEGER NOT NULL,run_id TEXT NOT NULL,sequence INTEGER NOT NULL,plan_id TEXT NOT NULL,record_sha256 TEXT NOT NULL,PRIMARY KEY(project_id,task_id,task_revision,run_id),FOREIGN KEY(project_id,plan_id) REFERENCES validation_plans(project_id,plan_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS validation_results(project_id TEXT NOT NULL,result_id TEXT NOT NULL,plan_id TEXT NOT NULL,check_id TEXT NOT NULL,result_json TEXT NOT NULL,record_sha256 TEXT NOT NULL,PRIMARY KEY(project_id,result_id),UNIQUE(project_id,plan_id,check_id,result_id),FOREIGN KEY(project_id,plan_id) REFERENCES validation_plans(project_id,plan_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS validation_result_claims(project_id TEXT NOT NULL,plan_id TEXT NOT NULL,idempotency_key TEXT NOT NULL,semantic_digest TEXT NOT NULL,result_id TEXT NOT NULL,PRIMARY KEY(project_id,plan_id,idempotency_key),UNIQUE(project_id,result_id),FOREIGN KEY(project_id,result_id) REFERENCES validation_results(project_id,result_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS validation_aggregates(project_id TEXT NOT NULL,plan_id TEXT NOT NULL,idempotency_key TEXT NOT NULL,semantic_digest TEXT NOT NULL,aggregate_json TEXT NOT NULL,aggregate_sha256 TEXT NOT NULL,PRIMARY KEY(project_id,plan_id,idempotency_key),FOREIGN KEY(project_id,plan_id) REFERENCES validation_plans(project_id,plan_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS evaluation_results(project_id TEXT NOT NULL,evaluation_id TEXT NOT NULL,evaluation_json TEXT NOT NULL,record_sha256 TEXT NOT NULL,PRIMARY KEY(project_id,evaluation_id),FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS evaluation_claims(project_id TEXT NOT NULL,idempotency_key TEXT NOT NULL,semantic_digest TEXT NOT NULL,evaluation_id TEXT NOT NULL,PRIMARY KEY(project_id,idempotency_key),UNIQUE(project_id,evaluation_id),FOREIGN KEY(project_id,evaluation_id) REFERENCES evaluation_results(project_id,evaluation_id) ON DELETE RESTRICT);
                CREATE TRIGGER IF NOT EXISTS validation_plans_no_update BEFORE UPDATE ON validation_plans BEGIN SELECT RAISE(ABORT,'Validation plans are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS validation_plans_no_delete BEFORE DELETE ON validation_plans BEGIN SELECT RAISE(ABORT,'Validation plans cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS validation_plan_claims_no_update BEFORE UPDATE ON validation_plan_claims BEGIN SELECT RAISE(ABORT,'Validation plan claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS validation_plan_claims_no_delete BEFORE DELETE ON validation_plan_claims BEGIN SELECT RAISE(ABORT,'Validation plan claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS validation_plan_heads_no_delete BEFORE DELETE ON validation_plan_heads BEGIN SELECT RAISE(ABORT,'Validation plan heads cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS validation_plan_heads_monotonic BEFORE UPDATE ON validation_plan_heads WHEN NEW.sequence!=OLD.sequence+1 OR NEW.project_id!=OLD.project_id OR NEW.task_id!=OLD.task_id OR NEW.task_revision!=OLD.task_revision OR NEW.run_id!=OLD.run_id BEGIN SELECT RAISE(ABORT,'Validation plan head must advance exactly once'); END;
                CREATE TRIGGER IF NOT EXISTS validation_results_no_update BEFORE UPDATE ON validation_results BEGIN SELECT RAISE(ABORT,'Validation results are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS validation_results_no_delete BEFORE DELETE ON validation_results BEGIN SELECT RAISE(ABORT,'Validation results cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS validation_result_claims_no_update BEFORE UPDATE ON validation_result_claims BEGIN SELECT RAISE(ABORT,'Validation result claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS validation_result_claims_no_delete BEFORE DELETE ON validation_result_claims BEGIN SELECT RAISE(ABORT,'Validation result claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS validation_aggregates_no_update BEFORE UPDATE ON validation_aggregates BEGIN SELECT RAISE(ABORT,'Validation aggregates are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS validation_aggregates_no_delete BEFORE DELETE ON validation_aggregates BEGIN SELECT RAISE(ABORT,'Validation aggregates cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS evaluation_results_no_update BEFORE UPDATE ON evaluation_results BEGIN SELECT RAISE(ABORT,'Evaluation results are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS evaluation_results_no_delete BEFORE DELETE ON evaluation_results BEGIN SELECT RAISE(ABORT,'Evaluation results cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS evaluation_claims_no_update BEFORE UPDATE ON evaluation_claims BEGIN SELECT RAISE(ABORT,'Evaluation claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS evaluation_claims_no_delete BEFORE DELETE ON evaluation_claims BEGIN SELECT RAISE(ABORT,'Evaluation claims cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def _now(connection: sqlite3.Connection) -> str:
        return _timestamp(connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now')").fetchone()[0], "database_now")

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise ValidationScopeError("Validation Project scope mismatch") from exc

    def _verify_attempt_record(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> None:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise ValidationAuthorityError("exact NodeExecutionAttempt is required")
        self._authorize(access, attempt.node_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute("SELECT record_sha256 FROM node_execution_attempts WHERE project_id=? AND graph_id=? AND graph_revision=? AND node_id=? AND attempt_id=?", (access.project_ref.value, attempt.node_ref.graph_ref.graph_id, attempt.node_ref.graph_ref.revision, attempt.node_ref.node_id, attempt.attempt_id)).fetchone()
        finally:
            connection.close()
        if row is None or not hmac.compare_digest(cast(str, row["record_sha256"]), attempt.record_sha256):
            raise ValidationAuthorityError("Validation Node attempt evidence is missing or changed")

    def _context_current(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> bool:
        self._verify_attempt_record(access, attempt)
        try:
            task = self.tasks.get_task(access, attempt.task_ref)
            graph = self.graphs.get_graph(access, attempt.node_ref.graph_ref)
            active = self.graphs.get_active_graph(access, attempt.run_ref)
            execution = self.executions.get_node_execution(access, attempt.node_ref)
        except Exception:
            return False
        return (
            task.canonical_digest == attempt.task_digest
            and graph == active
            and execution.status in {"RUNNING", "WAITING_EXTERNAL"}
            and execution.current_attempt_id == attempt.attempt_id
            and execution.current_fence == attempt.fence
            and execution.current_run_attempt_id == attempt.run_attempt_id
            and execution.current_run_fence == attempt.run_fence
        )

    def bind_artifact_subject(self, access: ProjectAccess, artifact_ref: ArtifactRef, *, producer_dimensions: Mapping[str, str] = MappingProxyType({})) -> ValidationSubject:
        artifact = self.artifacts.get_artifact(access, artifact_ref)
        return ValidationSubject(access.project_ref, "ARTIFACT", artifact_ref.value, artifact.record_sha256, producer_dimensions, {"artifact_id": artifact_ref.artifact_id, "artifact_revision": artifact_ref.revision})

    def bind_content_subject(self, access: ProjectAccess, content_ref: ContentRef, *, producer_dimensions: Mapping[str, str] = MappingProxyType({})) -> ValidationSubject:
        self._authorize(access, access.project_ref)
        return ValidationSubject(access.project_ref, "CONTENT", content_ref.value, _sha({"algorithm": content_ref.algorithm, "digest": content_ref.digest, "media_type": content_ref.media_type, "size_bytes": content_ref.size_bytes}), producer_dimensions, {"algorithm": content_ref.algorithm, "digest": content_ref.digest, "media_type": content_ref.media_type, "size_bytes": content_ref.size_bytes})

    def _workspace_receipt_binding(
        self,
        access: ProjectAccess,
        snapshot_ref: WorkspaceSnapshotRef,
        *,
        expected_digest: str | None = None,
    ) -> tuple[str, ArtifactRef]:
        """Verify a Workspace receipt, snapshot identity, and bound Artifact."""

        self._authorize(access, snapshot_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT r.receipt_json, r.receipt_sha256,
                       s.snapshot_json, s.record_sha256 AS snapshot_sha256
                FROM workspace_receipts AS r
                JOIN workspace_snapshots AS s
                  ON s.project_id = r.project_id
                 AND s.workspace_id = r.workspace_id
                 AND s.sequence = r.snapshot_sequence
                WHERE r.project_id=? AND r.workspace_id=?
                  AND r.snapshot_sequence=?
                """,
                (
                    access.project_ref.value,
                    snapshot_ref.workspace_ref.workspace_id,
                    snapshot_ref.sequence,
                ),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ValidationIntegrityError("Workspace subject receipt disappeared")
        try:
            receipt_json = cast(str, row["receipt_json"])
            snapshot_json = cast(str, row["snapshot_json"])
            receipt = cast(dict[str, object], json.loads(receipt_json))
            snapshot = cast(dict[str, object], json.loads(snapshot_json))
            if not isinstance(receipt, dict) or not isinstance(snapshot, dict):
                raise TypeError("Workspace evidence is not an object")
            receipt_digest = _sha(receipt)
            snapshot_digest = _sha(snapshot)
            persisted_receipt_digest = row["receipt_sha256"]
            persisted_snapshot_digest = row["snapshot_sha256"]
            receipt_artifact_text = receipt["snapshot_artifact_ref"]
            snapshot_artifact_text = snapshot["artifact_ref"]
            if (
                not isinstance(persisted_receipt_digest, str)
                or not isinstance(persisted_snapshot_digest, str)
                or not isinstance(receipt_artifact_text, str)
                or not isinstance(snapshot_artifact_text, str)
            ):
                raise TypeError("Workspace evidence identity is not serialized text")
            project_prefix = f"artifact://{access.project_ref.value}/"
            if not receipt_artifact_text.startswith(project_prefix):
                raise ValueError("Workspace Artifact crossed Project scope")
            artifact_prefix, artifact_id, revision_text = receipt_artifact_text.rsplit("/", 2)
            if artifact_prefix != f"artifact://{access.project_ref.value}":
                raise ValueError("Workspace Artifact identity is not canonical")
            artifact_ref = ArtifactRef(
                access.project_ref,
                artifact_id,
                int(revision_text),
            )
        except (
            ArtifactError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ValidationContractError,
        ) as exc:
            raise ValidationIntegrityError(
                "Workspace receipt or snapshot binding is malformed"
            ) from exc
        if (
            receipt_json != _json(receipt)
            or snapshot_json != _json(snapshot)
            or _SHA.fullmatch(persisted_receipt_digest) is None
            or _SHA.fullmatch(persisted_snapshot_digest) is None
            or not hmac.compare_digest(receipt_digest, persisted_receipt_digest)
            or not hmac.compare_digest(snapshot_digest, persisted_snapshot_digest)
            or (
                expected_digest is not None
                and not hmac.compare_digest(receipt_digest, expected_digest)
            )
            or receipt.get("snapshot_ref") != snapshot_ref.value
            or receipt.get("workspace_ref") != snapshot_ref.workspace_ref.value
            or snapshot.get("snapshot_ref") != snapshot_ref.value
            or snapshot_artifact_text != receipt_artifact_text
            or artifact_ref.value != receipt_artifact_text
        ):
            raise ValidationIntegrityError(
                "Workspace receipt, snapshot, or subject identity changed"
            )
        try:
            artifact = self.artifacts.get_artifact(access, artifact_ref)
        except ArtifactError as exc:
            raise ValidationIntegrityError(
                "Workspace snapshot Artifact is unavailable or invalid"
            ) from exc
        if artifact.role != "workspace.snapshot":
            raise ValidationIntegrityError(
                "Workspace receipt does not bind a workspace.snapshot Artifact"
            )
        return receipt_digest, artifact_ref

    def bind_workspace_subject(self, access: ProjectAccess, snapshot_ref: WorkspaceSnapshotRef) -> ValidationSubject:
        receipt_digest, _ = self._workspace_receipt_binding(access, snapshot_ref)
        return ValidationSubject(access.project_ref, "WORKSPACE", snapshot_ref.value, receipt_digest, {}, {"snapshot_sequence": snapshot_ref.sequence, "workspace_id": snapshot_ref.workspace_ref.workspace_id})

    def bind_tool_call_subject(self, access: ProjectAccess, call_ref: ToolCallRef) -> ValidationSubject:
        call = self.calls.get_tool_call(access, call_ref)
        exact_digest = _sha({"call_record_sha256": call.record_sha256, "state_record_sha256": call.state.record_sha256})
        dimensions = self.calls.get_execution_dimensions(access, call_ref)
        return ValidationSubject(access.project_ref, "TOOL_CALL", call_ref.value, exact_digest, dimensions, {"call_id": call_ref.call_id})

    def bind_model_call_subject(self, access: ProjectAccess, call_ref: ModelCallRef) -> ValidationSubject:
        call = self.calls.get_model_call(access, call_ref)
        exact_digest = _sha({"call_record_sha256": call.record_sha256, "state_record_sha256": call.state.record_sha256})
        dimensions = self.calls.get_execution_dimensions(access, call_ref)
        return ValidationSubject(access.project_ref, "MODEL_CALL", call_ref.value, exact_digest, dimensions, {"call_id": call_ref.call_id})

    def _revalidate_subject(self, access: ProjectAccess, subject: ValidationSubject) -> None:
        if subject.project_ref != access.project_ref:
            raise ValidationScopeError("Validation subject crossed Project scope")
        if subject.subject_kind == "ARTIFACT":
            artifact = self.artifacts.get_artifact(access, ArtifactRef(access.project_ref, cast(str, subject.metadata["artifact_id"]), cast(int, subject.metadata["artifact_revision"])))
            observed = artifact.record_sha256
        elif subject.subject_kind == "TOOL_CALL":
            tool_call = self.calls.get_tool_call(access, ToolCallRef(access.project_ref, cast(str, subject.metadata["call_id"])))
            observed = _sha({"call_record_sha256": tool_call.record_sha256, "state_record_sha256": tool_call.state.record_sha256})
        elif subject.subject_kind == "MODEL_CALL":
            model_call = self.calls.get_model_call(access, ModelCallRef(access.project_ref, cast(str, subject.metadata["call_id"])))
            observed = _sha({"call_record_sha256": model_call.record_sha256, "state_record_sha256": model_call.state.record_sha256})
        elif subject.subject_kind == "WORKSPACE":
            snapshot_ref = WorkspaceSnapshotRef(
                WorkspaceRef(
                    access.project_ref,
                    cast(str, subject.metadata["workspace_id"]),
                ),
                cast(int, subject.metadata["snapshot_sequence"]),
            )
            observed, _ = self._workspace_receipt_binding(
                access,
                snapshot_ref,
                expected_digest=subject.exact_digest,
            )
        else:
            observed = subject.exact_digest
        if not hmac.compare_digest(observed, subject.exact_digest):
            raise ValidationIntegrityError("Validation subject exact digest changed")

    @staticmethod
    def _criterion_check(criterion: str) -> ValidationCheck:
        for prefix, required in (("validation.required=", True), ("validation.optional=", False)):
            if criterion.startswith(prefix):
                value = criterion.removeprefix(prefix)
                try:
                    capability_id, version = value.rsplit("@", 1)
                except ValueError as exc:
                    raise ValidationContractError("Task validation criterion capability is malformed") from exc
                return ValidationCheck(CapabilityRef(capability_id, version), required, f"task.acceptance:{criterion}")
        digest = hashlib.sha256(criterion.encode()).hexdigest()[:24]
        return ValidationCheck(CapabilityRef(f"validation.acceptance.{digest}", "1.0.0"), True, f"task.acceptance:{criterion}", parameters={"criterion": criterion})

    @classmethod
    def _compile_checks(cls, task: Task, project_criteria: ProjectValidationCriteria | None) -> tuple[ValidationCheck, ...]:
        checks: list[ValidationCheck] = []
        if task.output_contract:
            checks.extend((
                ValidationCheck(CapabilityRef("validation.schema", "1.0.0"), True, "task.output_contract", ("schema",)),
                ValidationCheck(CapabilityRef("validation.artifact.exists", "1.0.0"), True, "task.output_contract", ("artifact",)),
                ValidationCheck(CapabilityRef("validation.digest", "1.0.0"), True, "task.output_contract", ("content_ref",)),
            ))
        evidence_mapping = {
            "artifact": "validation.artifact.exists", "content-ref": "validation.digest",
            "tool-call": "validation.tool-evidence", "model-call": "validation.model-evidence",
            "provenance": "validation.provenance", "test": "validation.test",
            "build": "validation.build", "runtime": "validation.runtime",
        }
        for requirement in task.evidence_requirements:
            capability_id = evidence_mapping.get(requirement, f"validation.evidence.{hashlib.sha256(requirement.encode()).hexdigest()[:24]}")
            checks.append(ValidationCheck(CapabilityRef(capability_id, "1.0.0"), True, f"task.evidence:{requirement}", (requirement.replace("-", "_"),)))
        for criterion in task.acceptance_criteria:
            if criterion.startswith("validation.success_rule="):
                continue
            checks.append(cls._criterion_check(criterion))
        constraint_mapping = {"validation.build_required": "validation.build", "validation.runtime_required": "validation.runtime", "validation.security_required": "validation.security", "validation.visual_required": "validation.visual", "validation.performance_required": "validation.performance"}
        for key, capability_id in constraint_mapping.items():
            if task.constraints.get(key) is True:
                checks.append(ValidationCheck(CapabilityRef(capability_id, "1.0.0"), True, f"task.constraint:{key}"))
        if project_criteria is not None:
            checks.extend(project_criteria.checks)
        merged: dict[tuple[str, str, tuple[str, ...]], ValidationCheck] = {}
        for check in checks:
            merge_key = (
                check.capability_ref.value,
                _json(dict(check.parameters)),
                check.independence_dimensions,
            )
            prior = merged.get(merge_key)
            if prior is None:
                merged[merge_key] = check
            else:
                merged[merge_key] = ValidationCheck(
                    check.capability_ref,
                    prior.required or check.required,
                    "+".join(sorted(set(prior.source.split("+") + check.source.split("+")))),
                    tuple(sorted(set(prior.evidence_requirements + check.evidence_requirements))),
                    check.independence_dimensions,
                    check.parameters,
                )
        return tuple(sorted(merged.values(), key=lambda item: item.check_id))

    def compile_plan(self, access: ProjectAccess, attempt: NodeExecutionAttempt, *, subjects: Sequence[ValidationSubject], project_criteria: ProjectValidationCriteria | None = None, idempotency_key: str) -> ValidationPlan:
        _key(idempotency_key)
        if not self._context_current(access, attempt):
            raise ValidationAuthorityError("ValidationPlan requires current Graph and attempt authority")
        task = self.tasks.get_task(access, attempt.task_ref)
        graph = self.graphs.get_graph(access, attempt.node_ref.graph_ref)
        subject_tuple = tuple(subjects)
        for subject in subject_tuple:
            self._revalidate_subject(access, subject)
        if project_criteria is not None and project_criteria.project_ref != access.project_ref:
            raise ValidationScopeError("Project validation criteria crossed Project scope")
        checks = self._compile_checks(task, project_criteria)
        if not checks or not any(check.required for check in checks):
            raise ValidationContractError("Task-derived ValidationPlan has no required acceptance check")
        success_values = tuple(item.removeprefix("validation.success_rule=") for item in task.acceptance_criteria if item.startswith("validation.success_rule="))
        success_rule = success_values[0] if success_values else "ALL_REQUIRED_PASS"
        semantic = _sha({"attempt": attempt.record_sha256, "checks": [item.payload() for item in checks], "graph": graph.record_sha256, "subjects": [item.payload() for item in sorted(subject_tuple, key=lambda item: item.subject_ref)], "success_rule": success_rule, "task": task.canonical_digest})
        connection = self._connect()
        try:
            prior = connection.execute("SELECT * FROM validation_plan_claims WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?", (access.project_ref.value, attempt.attempt_id, idempotency_key)).fetchone()
            if prior is not None:
                if not hmac.compare_digest(cast(str, prior["semantic_digest"]), semantic):
                    raise ValidationConflictError("ValidationPlan idempotency semantics changed")
                return self._fetch_plan(connection, ValidationPlanRef(access.project_ref, cast(str, prior["plan_id"])))
            connection.execute("BEGIN IMMEDIATE")
            head = connection.execute("SELECT * FROM validation_plan_heads WHERE project_id=? AND task_id=? AND task_revision=? AND run_id=?", (access.project_ref.value, task.task_id, task.revision, attempt.run_ref.run_id)).fetchone()
            sequence = 1 if head is None else cast(int, head["sequence"]) + 1
            plan = ValidationPlan(ValidationPlanRef(access.project_ref, f"vplan_{uuid4().hex}"), sequence, task.task_ref, task.canonical_digest, attempt.run_ref, graph.graph_ref, graph.record_sha256, attempt.node_ref, attempt.attempt_id, attempt.fence, subject_tuple, checks, success_rule, self._now(connection))
            connection.execute("INSERT INTO validation_plans VALUES (?,?,?,?,?,?,?,?,?)", (access.project_ref.value, plan.plan_ref.plan_id, sequence, task.task_id, task.revision, attempt.run_ref.run_id, _json(plan.payload()), plan.semantic_digest, plan.record_sha256))
            connection.execute("INSERT INTO validation_plan_claims VALUES (?,?,?,?,?)", (access.project_ref.value, attempt.attempt_id, idempotency_key, semantic, plan.plan_ref.plan_id))
            if head is None:
                connection.execute("INSERT INTO validation_plan_heads VALUES (?,?,?,?,?,?,?)", (access.project_ref.value, task.task_id, task.revision, attempt.run_ref.run_id, sequence, plan.plan_ref.plan_id, plan.record_sha256))
            else:
                changed = connection.execute("UPDATE validation_plan_heads SET sequence=?,plan_id=?,record_sha256=? WHERE project_id=? AND task_id=? AND task_revision=? AND run_id=? AND sequence=? AND plan_id=? AND record_sha256=?", (sequence, plan.plan_ref.plan_id, plan.record_sha256, access.project_ref.value, task.task_id, task.revision, attempt.run_ref.run_id, head["sequence"], head["plan_id"], head["record_sha256"]))
                if changed.rowcount != 1:
                    raise ValidationConflictError("ValidationPlan head changed concurrently")
            connection.commit()
            return plan
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ValidationConflictError("ValidationPlan persistence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _subject_from(value: Mapping[str, object], project: ProjectRef) -> ValidationSubject:
        if value.get("project_ref") != project.value:
            raise ValidationScopeError("Persisted validation subject crossed Project scope")
        return ValidationSubject(project, cast(str, value["subject_kind"]), cast(str, value["subject_ref"]), cast(str, value["exact_digest"]), cast(dict[str, str], value["producer_dimensions"]), cast(dict[str, object], value["metadata"]))

    @staticmethod
    def _check_from(value: Mapping[str, object]) -> ValidationCheck:
        capability_id, version = cast(str, value["capability_ref"]).rsplit("@", 1)
        check = ValidationCheck(CapabilityRef(capability_id, version), cast(bool, value["required"]), cast(str, value["source"]), tuple(cast(list[str], value["evidence_requirements"])), tuple(cast(list[str], value["independence_dimensions"])), cast(dict[str, object], value["parameters"]))
        if check.check_id != value["check_id"]:
            raise ValidationIntegrityError("Persisted ValidationCheck identity changed")
        return check

    @classmethod
    def _plan_from(cls, value: Mapping[str, object], project: ProjectRef) -> ValidationPlan:
        graph = GraphRef(project, cast(str, value["graph_ref"]).split("/")[-2], int(cast(str, value["graph_ref"]).split("/")[-1]))
        node = NodeRef(graph, cast(str, value["node_ref"]).rsplit("/", 1)[1])
        task_tail = cast(str, value["task_ref"]).split("/")
        return ValidationPlan(ValidationPlanRef(project, cast(str, value["plan_id"])), cast(int, value["sequence"]), TaskRef(project, task_tail[-2], int(task_tail[-1])), cast(str, value["task_digest"]), RunRef(project, cast(str, value["run_ref"]).rsplit("/", 1)[1]), graph, cast(str, value["graph_record_sha256"]), node, cast(str, value["node_attempt_id"]), cast(int, value["node_attempt_fence"]), tuple(cls._subject_from(item, project) for item in cast(list[dict[str, object]], value["subjects"])), tuple(cls._check_from(item) for item in cast(list[dict[str, object]], value["checks"])), cast(str, value["success_rule"]), cast(str, value["created_at"]))

    def _fetch_plan(self, connection: sqlite3.Connection, ref: ValidationPlanRef) -> ValidationPlan:
        row = connection.execute("SELECT * FROM validation_plans WHERE project_id=? AND plan_id=?", (ref.project_ref.value, ref.plan_id)).fetchone()
        if row is None:
            raise ValidationNotFoundError("ValidationPlan not found")
        try:
            plan = self._plan_from(cast(dict[str, object], json.loads(cast(str, row["plan_json"]))), ref.project_ref)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            raise ValidationIntegrityError("Persisted ValidationPlan is malformed") from exc
        if plan.plan_ref != ref or not hmac.compare_digest(plan.semantic_digest, cast(str, row["semantic_digest"])) or not hmac.compare_digest(plan.record_sha256, cast(str, row["record_sha256"])):
            raise ValidationIntegrityError("ValidationPlan evidence changed")
        return plan

    def get_plan(self, access: ProjectAccess, ref: ValidationPlanRef) -> ValidationPlan:
        self._authorize(access, ref.project_ref)
        connection = self._connect()
        try:
            return self._fetch_plan(connection, ref)
        finally:
            connection.close()

    @staticmethod
    def _subject_set_digest(plan: ValidationPlan) -> str:
        return _sha([item.payload() for item in plan.subjects])

    def _plan_is_current(self, connection: sqlite3.Connection, access: ProjectAccess, attempt: NodeExecutionAttempt, plan: ValidationPlan) -> bool:
        head = connection.execute("SELECT plan_id,record_sha256 FROM validation_plan_heads WHERE project_id=? AND task_id=? AND task_revision=? AND run_id=?", (plan.project_ref.value, plan.task_ref.task_id, plan.task_ref.revision, plan.run_ref.run_id)).fetchone()
        return head is not None and head["plan_id"] == plan.plan_ref.plan_id and head["record_sha256"] == plan.record_sha256 and self._context_current(access, attempt)

    def record_result(self, access: ProjectAccess, attempt: NodeExecutionAttempt, plan_ref: ValidationPlanRef, *, check_id: str, verdict: ValidationVerdict, validator_kind: str, implementation_ref: str, runtime_ref: str, validator_dimensions: Mapping[str, str] = MappingProxyType({}), findings_refs: Sequence[str] = (), evidence_refs: Sequence[str] = (), metrics: Sequence[MetricMeasurement] = (), model_call_ref: ModelCallRef | None = None, tool_call_ref: ToolCallRef | None = None, error_reason: str | None = None, idempotency_key: str) -> ValidationResult:
        _key(idempotency_key)
        self._verify_attempt_record(access, attempt)
        plan = self.get_plan(access, plan_ref)
        if (plan.node_attempt_id, plan.node_attempt_fence) != (attempt.attempt_id, attempt.fence):
            raise ValidationAuthorityError("ValidationResult attempt differs from plan authority")
        check = next((item for item in plan.checks if item.check_id == check_id), None)
        if check is None:
            raise ValidationContractError("ValidationResult check is not in the exact plan")
        for subject in plan.subjects:
            self._revalidate_subject(access, subject)
        artifact_evidence: list[ArtifactRef] = []
        evidence_artifacts: list[Artifact] = []
        for evidence_ref in evidence_refs:
            if evidence_ref.startswith("artifact://"):
                project_prefix = f"artifact://{access.project_ref.value}/"
                if not evidence_ref.startswith(project_prefix):
                    raise ValidationScopeError("Artifact validation evidence crossed Project scope")
                tail = evidence_ref.rsplit("/", 2)
                if len(tail) != 3:
                    raise ValidationContractError("Artifact validation evidence is malformed")
                try:
                    artifact_ref = ArtifactRef(access.project_ref, tail[-2], int(tail[-1]))
                except (TypeError, ValueError) as exc:
                    raise ValidationContractError("Artifact validation evidence is malformed") from exc
                artifact = self.artifacts.get_artifact(access, artifact_ref)
                if artifact_ref.value != evidence_ref:
                    raise ValidationContractError("Artifact validation evidence is not canonical")
                artifact_evidence.append(artifact_ref)
                evidence_artifacts.append(artifact)
        if check.capability_ref.capability_id in {"validation.build", "validation.runtime", "validation.artifact.exists"} and verdict is ValidationVerdict.PASS and not artifact_evidence:
            raise ValidationContractError("successful build/runtime/artifact validation requires exact Artifact evidence")
        required_artifact_role = check.parameters.get("artifact_role")
        role_artifacts = tuple(
            artifact
            for artifact in evidence_artifacts
            if artifact.role == required_artifact_role
        )
        if (
            verdict is ValidationVerdict.PASS
            and isinstance(required_artifact_role, str)
            and not role_artifacts
        ):
            raise ValidationContractError(
                "successful validation lacks the exact required Artifact role"
            )
        artifact_subject_refs = {
            subject.subject_ref
            for subject in plan.subjects
            if subject.subject_kind == "ARTIFACT"
        }
        subject_role_artifacts = tuple(
            artifact
            for artifact in role_artifacts
            if artifact.artifact_ref.value in artifact_subject_refs
        )
        if verdict is ValidationVerdict.PASS and isinstance(required_artifact_role, str):
            if not subject_role_artifacts:
                raise ValidationContractError(
                    "required-role Artifact is not an exact ValidationPlan subject"
                )
        required_source_artifact = check.parameters.get("source_artifact_ref")
        if isinstance(required_source_artifact, str):
            plan_source_artifact_refs = {
                subject.subject_ref
                for subject in plan.subjects
                if subject.subject_kind == "ARTIFACT"
            }
            for subject in plan.subjects:
                if subject.subject_kind != "WORKSPACE":
                    continue
                snapshot_ref = WorkspaceSnapshotRef(
                    WorkspaceRef(
                        access.project_ref,
                        cast(str, subject.metadata["workspace_id"]),
                    ),
                    cast(int, subject.metadata["snapshot_sequence"]),
                )
                _, snapshot_artifact_ref = self._workspace_receipt_binding(
                    access,
                    snapshot_ref,
                    expected_digest=subject.exact_digest,
                )
                plan_source_artifact_refs.add(snapshot_artifact_ref.value)
            if required_source_artifact not in plan_source_artifact_refs:
                raise ValidationContractError(
                    "required source Artifact is not bound to an exact plan subject"
                )
        provenance_artifacts = (
            subject_role_artifacts
            if isinstance(required_artifact_role, str)
            else tuple(evidence_artifacts)
        )
        if (
            verdict is ValidationVerdict.PASS
            and isinstance(required_source_artifact, str)
            and not any(
                required_source_artifact
                in {source.value for source in artifact.source_artifact_refs}
                for artifact in provenance_artifacts
            )
        ):
            raise ValidationContractError(
                "successful validation lacks required Artifact provenance"
            )
        if verdict is ValidationVerdict.PASS and not evidence_refs:
            raise ValidationContractError("PASS requires exact validation evidence")
        dimensions = dict(validator_dimensions)
        supplied_identity = {
            "implementation": implementation_ref,
            "runtime": runtime_ref,
            **dimensions,
        }
        if dimensions.get("implementation", implementation_ref) != implementation_ref or dimensions.get("runtime", runtime_ref) != runtime_ref:
            raise ValidationContractError("validator dimensions conflict with validator identity")
        if validator_kind == "TOOL":
            if tool_call_ref is None:
                raise ValidationContractError("tool validator requires ToolCall")
            tool_call = self.calls.get_tool_call(access, tool_call_ref)
            if tool_call.attempt.record_sha256 != attempt.record_sha256 or tool_call.capability_ref != check.capability_ref or tool_call.implementation_id != implementation_ref or tool_call.runtime_id != runtime_ref:
                raise ValidationAuthorityError("Tool validator ledger identity differs from plan/result")
            if verdict is not ValidationVerdict.ERROR and tool_call.status != "SUCCEEDED":
                raise ValidationContractError("non-ERROR tool validation requires successful ToolCall")
            supplied_identity.update({
                "tool": tool_call.tool_id,
                "strategy": _capability_uri(tool_call.capability_ref),
            })
            output_values = {item.value for item in tool_call.output_refs}
            if verdict is ValidationVerdict.PASS and artifact_evidence and not {item.value for item in artifact_evidence} <= output_values:
                raise ValidationContractError("successful tool validation Artifact evidence must be exact ToolCall output")
        elif validator_kind == "MODEL":
            if model_call_ref is None:
                raise ValidationContractError("model validator requires ModelCall")
            model_call = self.calls.get_model_call(access, model_call_ref)
            if model_call.attempt.record_sha256 != attempt.record_sha256 or model_call.capability_ref != check.capability_ref or model_call.runtime_id != runtime_ref:
                raise ValidationAuthorityError("Model validator ledger identity differs from plan/result")
            model_dimensions = self.calls.get_execution_dimensions(access, model_call_ref)
            expected_impl = model_dimensions["implementation"]
            if implementation_ref != expected_impl:
                raise ValidationAuthorityError("Model validator implementation differs from ModelCall")
            if verdict is not ValidationVerdict.ERROR and model_call.status != "SUCCEEDED":
                raise ValidationContractError("non-ERROR model validation requires successful ModelCall")
            supplied_identity.update(model_dimensions)
            output_values = {item.value for item in model_call.output_refs}
            if verdict is ValidationVerdict.PASS and artifact_evidence and not {item.value for item in artifact_evidence} <= output_values:
                raise ValidationContractError("successful model validation Artifact evidence must be exact ModelCall output")
        elif validator_kind != "DETERMINISTIC":
            raise ValidationContractError("validator kind is unsupported")
        normalized_dimensions = {
            key: value
            for key, value in supplied_identity.items()
            if value is not None
        }
        for dimension in check.independence_dimensions:
            validator_value = normalized_dimensions.get(dimension)
            producer_values = {
                subject.producer_dimensions[dimension]
                for subject in plan.subjects
                if dimension in subject.producer_dimensions
            }
            if validator_value is None or len(producer_values) != len(plan.subjects):
                raise ValidationAuthorityError(f"independence by {dimension} is not provable")
            if validator_value in producer_values:
                raise ValidationAuthorityError(f"validator is not independent by {dimension}")
        semantic = _sha({"check_id": check_id, "error_reason": error_reason, "evidence_refs": sorted(set(evidence_refs)), "findings_refs": sorted(set(findings_refs)), "implementation_ref": implementation_ref, "metrics": [item.payload() for item in sorted(metrics, key=lambda item: item.name)], "model_call_ref": None if model_call_ref is None else model_call_ref.value, "plan_digest": plan.semantic_digest, "runtime_ref": runtime_ref, "tool_call_ref": None if tool_call_ref is None else tool_call_ref.value, "validator_dimensions": dict(sorted(normalized_dimensions.items())), "validator_kind": validator_kind, "verdict": verdict.value})
        connection = self._connect()
        try:
            prior = connection.execute("SELECT * FROM validation_result_claims WHERE project_id=? AND plan_id=? AND idempotency_key=?", (access.project_ref.value, plan_ref.plan_id, idempotency_key)).fetchone()
            if prior is not None:
                if not hmac.compare_digest(cast(str, prior["semantic_digest"]), semantic):
                    raise ValidationConflictError("ValidationResult idempotency semantics changed")
                return self._fetch_result(connection, ValidationResultRef(access.project_ref, cast(str, prior["result_id"])))
            connection.execute("BEGIN IMMEDIATE")
            current = self._plan_is_current(connection, access, attempt, plan)
            result = ValidationResult(ValidationResultRef(access.project_ref, f"vresult_{uuid4().hex}"), plan_ref, plan.semantic_digest, check_id, self._subject_set_digest(plan), check.capability_ref, validator_kind, implementation_ref, runtime_ref, normalized_dimensions, verdict, tuple(findings_refs), tuple(evidence_refs), tuple(metrics), model_call_ref, tool_call_ref, ValidationEvidenceState.CURRENT if current else ValidationEvidenceState.HISTORICAL, error_reason, self._now(connection))
            connection.execute("INSERT INTO validation_results VALUES (?,?,?,?,?,?)", (access.project_ref.value, result.result_ref.result_id, plan_ref.plan_id, check_id, _json(result.payload()), result.record_sha256))
            connection.execute("INSERT INTO validation_result_claims VALUES (?,?,?,?,?)", (access.project_ref.value, plan_ref.plan_id, idempotency_key, semantic, result.result_ref.result_id))
            connection.commit()
            return result
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ValidationConflictError("ValidationResult persistence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _metric_from(value: Mapping[str, object]) -> MetricMeasurement:
        return MetricMeasurement(cast(str, value["name"]), cast(float, value["value"]), cast(str, value["unit"]), cast(str, value["definition"]), cast(str, value["measurement_source_ref"]))

    @classmethod
    def _result_from(cls, value: Mapping[str, object], project: ProjectRef) -> ValidationResult:
        capability_id, version = cast(str, value["capability_ref"]).rsplit("@", 1)
        return ValidationResult(ValidationResultRef(project, cast(str, value["result_ref"]).rsplit("/", 1)[1]), ValidationPlanRef(project, cast(str, value["plan_ref"]).rsplit("/", 1)[1]), cast(str, value["plan_digest"]), cast(str, value["check_id"]), cast(str, value["subject_set_digest"]), CapabilityRef(capability_id, version), cast(str, value["validator_kind"]), cast(str, value["implementation_ref"]), cast(str, value["runtime_ref"]), cast(dict[str, str], value["validator_dimensions"]), ValidationVerdict(cast(str, value["verdict"])), tuple(cast(list[str], value["findings_refs"])), tuple(cast(list[str], value["evidence_refs"])), tuple(cls._metric_from(item) for item in cast(list[dict[str, object]], value["metrics"])), None if value["model_call_ref"] is None else ModelCallRef(project, cast(str, value["model_call_ref"]).rsplit("/", 1)[1]), None if value["tool_call_ref"] is None else ToolCallRef(project, cast(str, value["tool_call_ref"]).rsplit("/", 1)[1]), ValidationEvidenceState(cast(str, value["evidence_state"])), cast(str | None, value["error_reason"]), cast(str, value["created_at"]))

    def _fetch_result(self, connection: sqlite3.Connection, ref: ValidationResultRef) -> ValidationResult:
        row = connection.execute("SELECT * FROM validation_results WHERE project_id=? AND result_id=?", (ref.project_ref.value, ref.result_id)).fetchone()
        if row is None:
            raise ValidationNotFoundError("ValidationResult not found")
        try:
            result = self._result_from(cast(dict[str, object], json.loads(cast(str, row["result_json"]))), ref.project_ref)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            raise ValidationIntegrityError("Persisted ValidationResult is malformed") from exc
        if result.result_ref != ref or not hmac.compare_digest(result.record_sha256, cast(str, row["record_sha256"])):
            raise ValidationIntegrityError("ValidationResult evidence changed")
        return result

    def get_result(self, access: ProjectAccess, ref: ValidationResultRef) -> ValidationResult:
        self._authorize(access, ref.project_ref)
        connection = self._connect()
        try:
            return self._fetch_result(connection, ref)
        finally:
            connection.close()

    def aggregate(self, access: ProjectAccess, attempt: NodeExecutionAttempt, plan_ref: ValidationPlanRef, *, idempotency_key: str) -> ValidationAggregate:
        _key(idempotency_key)
        plan = self.get_plan(access, plan_ref)
        connection = self._connect()
        try:
            rows = connection.execute("SELECT result_id FROM validation_results WHERE project_id=? AND plan_id=? ORDER BY result_id", (access.project_ref.value, plan_ref.plan_id)).fetchall()
            results = tuple(self._fetch_result(connection, ValidationResultRef(access.project_ref, cast(str, row["result_id"]))) for row in rows)
            current_plan = self._plan_is_current(connection, access, attempt, plan)
            current_results = tuple(item for item in results if item.evidence_state is ValidationEvidenceState.CURRENT)
            by_check: dict[str, ValidationResult] = {}
            for result in current_results:
                prior = by_check.get(result.check_id)
                if prior is not None and prior.record_sha256 != result.record_sha256:
                    raise ValidationConflictError("Multiple current ValidationResults claim one check")
                by_check[result.check_id] = result
            required = tuple(item for item in plan.checks if item.required)
            optional = tuple(item for item in plan.checks if not item.required)
            missing = tuple(sorted(item.check_id for item in required if item.check_id not in by_check))
            required_results = tuple(by_check[item.check_id] for item in required if item.check_id in by_check)
            optional_results = tuple(by_check[item.check_id] for item in optional if item.check_id in by_check)
            verdicts = {item.verdict for item in required_results}
            if ValidationVerdict.ERROR in verdicts:
                verdict = ValidationVerdict.ERROR
            elif ValidationVerdict.FAIL in verdicts:
                verdict = ValidationVerdict.FAIL
            elif missing or ValidationVerdict.INCONCLUSIVE in verdicts:
                verdict = ValidationVerdict.INCONCLUSIVE
            else:
                verdict = ValidationVerdict.PASS
            evidence_state = ValidationEvidenceState.CURRENT if current_plan else ValidationEvidenceState.HISTORICAL
            aggregate_basis = {
                "accepted": verdict is ValidationVerdict.PASS and evidence_state is ValidationEvidenceState.CURRENT,
                "evidence_state": evidence_state.value,
                "missing_required_check_ids": list(missing),
                "optional_result_refs": [item.result_ref.value for item in optional_results],
                "plan_digest": plan.semantic_digest,
                "plan_ref": plan_ref.value,
                "required_result_refs": [item.result_ref.value for item in required_results],
                "verdict": verdict.value,
            }
            semantic = _sha({"aggregate": aggregate_basis, "result_records": [item.record_sha256 for item in (*required_results, *optional_results)]})
            prior_row = connection.execute("SELECT * FROM validation_aggregates WHERE project_id=? AND plan_id=? AND idempotency_key=?", (access.project_ref.value, plan_ref.plan_id, idempotency_key)).fetchone()
            if prior_row is not None:
                if not hmac.compare_digest(cast(str, prior_row["semantic_digest"]), semantic):
                    raise ValidationConflictError("ValidationAggregate idempotency semantics changed")
                saved = cast(dict[str, object], json.loads(cast(str, prior_row["aggregate_json"])))
                persisted = ValidationAggregate(plan_ref, cast(str, saved["plan_digest"]), ValidationVerdict(cast(str, saved["verdict"])), cast(bool, saved["accepted"]), ValidationEvidenceState(cast(str, saved["evidence_state"])), tuple(ValidationResultRef(access.project_ref, item.rsplit("/", 1)[1]) for item in cast(list[str], saved["required_result_refs"])), tuple(ValidationResultRef(access.project_ref, item.rsplit("/", 1)[1]) for item in cast(list[str], saved["optional_result_refs"])), tuple(cast(list[str], saved["missing_required_check_ids"])), cast(str, saved["created_at"]))
                if not hmac.compare_digest(persisted.aggregate_sha256, cast(str, prior_row["aggregate_sha256"])):
                    raise ValidationIntegrityError("ValidationAggregate evidence changed")
                return persisted
            aggregate = ValidationAggregate(plan_ref, plan.semantic_digest, verdict, verdict is ValidationVerdict.PASS and evidence_state is ValidationEvidenceState.CURRENT, evidence_state, tuple(item.result_ref for item in required_results), tuple(item.result_ref for item in optional_results), missing, self._now(connection))
            connection.execute("INSERT INTO validation_aggregates VALUES (?,?,?,?,?,?)", (access.project_ref.value, plan_ref.plan_id, idempotency_key, semantic, _json(aggregate.payload()), aggregate.aggregate_sha256))
            connection.commit()
            return aggregate
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record_evaluation(self, access: ProjectAccess, attempt: NodeExecutionAttempt, *, subjects: Sequence[ValidationSubject], metrics: Sequence[MetricMeasurement], composites: Sequence[CompositeMetric] = (), evidence_refs: Sequence[str] = (), idempotency_key: str) -> EvaluationResult:
        _key(idempotency_key)
        if not self._context_current(access, attempt):
            raise ValidationAuthorityError("EvaluationResult requires current Graph and attempt authority")
        graph = self.graphs.get_graph(access, attempt.node_ref.graph_ref)
        subject_tuple = tuple(subjects)
        for subject in subject_tuple:
            self._revalidate_subject(access, subject)
        semantic = _sha({"attempt": attempt.record_sha256, "composites": [item.payload() for item in composites], "evidence_refs": sorted(set(evidence_refs)), "metrics": [item.payload() for item in metrics], "subjects": [item.payload() for item in subject_tuple]})
        connection = self._connect()
        try:
            prior = connection.execute("SELECT * FROM evaluation_claims WHERE project_id=? AND idempotency_key=?", (access.project_ref.value, idempotency_key)).fetchone()
            if prior is not None:
                if not hmac.compare_digest(cast(str, prior["semantic_digest"]), semantic):
                    raise ValidationConflictError("EvaluationResult idempotency semantics changed")
                return self._fetch_evaluation(connection, EvaluationResultRef(access.project_ref, cast(str, prior["evaluation_id"])))
            connection.execute("BEGIN IMMEDIATE")
            result = EvaluationResult(
                EvaluationResultRef(access.project_ref, f"eval_{uuid4().hex}"),
                attempt.task_ref,
                attempt.task_digest,
                attempt.run_ref,
                graph.graph_ref,
                graph.record_sha256,
                attempt.node_ref,
                attempt.attempt_id,
                attempt.fence,
                attempt.record_sha256,
                subject_tuple,
                tuple(metrics),
                tuple(composites),
                tuple(evidence_refs),
                self._now(connection),
            )
            connection.execute("INSERT INTO evaluation_results VALUES (?,?,?,?)", (access.project_ref.value, result.evaluation_ref.evaluation_id, _json(result.payload()), result.record_sha256))
            connection.execute("INSERT INTO evaluation_claims VALUES (?,?,?,?)", (access.project_ref.value, idempotency_key, semantic, result.evaluation_ref.evaluation_id))
            connection.commit()
            return result
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ValidationConflictError("EvaluationResult persistence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _composite_from(value: Mapping[str, object]) -> CompositeMetric:
        return CompositeMetric(cast(str, value["name"]), cast(str, value["formula"]), tuple(cast(list[str], value["components"])), cast(dict[str, float], value["weights"]), cast(float, value["score"]))

    @classmethod
    def _evaluation_from(cls, value: Mapping[str, object], project: ProjectRef) -> EvaluationResult:
        task_tail = cast(str, value["task_ref"]).split("/")
        graph_tail = cast(str, value["graph_ref"]).split("/")
        graph_ref = GraphRef(project, graph_tail[-2], int(graph_tail[-1]))
        return EvaluationResult(
            EvaluationResultRef(project, cast(str, value["evaluation_ref"]).rsplit("/", 1)[1]),
            TaskRef(project, task_tail[-2], int(task_tail[-1])),
            cast(str, value["task_digest"]),
            RunRef(project, cast(str, value["run_ref"]).rsplit("/", 1)[1]),
            graph_ref,
            cast(str, value["graph_record_sha256"]),
            NodeRef(graph_ref, cast(str, value["node_ref"]).rsplit("/", 1)[1]),
            cast(str, value["node_attempt_id"]),
            cast(int, value["node_attempt_fence"]),
            cast(str, value["authority_attempt_sha256"]),
            tuple(cls._subject_from(item, project) for item in cast(list[dict[str, object]], value["subjects"])),
            tuple(cls._metric_from(item) for item in cast(list[dict[str, object]], value["metrics"])),
            tuple(cls._composite_from(item) for item in cast(list[dict[str, object]], value["composites"])),
            tuple(cast(list[str], value["evidence_refs"])),
            cast(str, value["created_at"]),
        )

    def _fetch_evaluation(self, connection: sqlite3.Connection, ref: EvaluationResultRef) -> EvaluationResult:
        row = connection.execute("SELECT * FROM evaluation_results WHERE project_id=? AND evaluation_id=?", (ref.project_ref.value, ref.evaluation_id)).fetchone()
        if row is None:
            raise ValidationNotFoundError("EvaluationResult not found")
        try:
            result = self._evaluation_from(cast(dict[str, object], json.loads(cast(str, row["evaluation_json"]))), ref.project_ref)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            raise ValidationIntegrityError("Persisted EvaluationResult is malformed") from exc
        if result.evaluation_ref != ref or not hmac.compare_digest(result.record_sha256, cast(str, row["record_sha256"])):
            raise ValidationIntegrityError("EvaluationResult evidence changed")
        return result

    def get_evaluation(self, access: ProjectAccess, ref: EvaluationResultRef) -> EvaluationResult:
        self._authorize(access, ref.project_ref)
        connection = self._connect()
        try:
            return self._fetch_evaluation(connection, ref)
        finally:
            connection.close()

    compile = compile_plan
    aggregateResults = aggregate
    recordResult = record_result
    recordEvaluation = record_evaluation


__all__ = [
    "CompositeMetric", "EvaluationResult", "EvaluationResultRef", "MetricMeasurement",
    "ProjectValidationCriteria", "ValidationAggregate", "ValidationAuthorityError",
    "ValidationCheck", "ValidationConflictError", "ValidationContractError",
    "ValidationError", "ValidationEvidenceState", "ValidationIntegrityError",
    "ValidationNotFoundError", "ValidationPlan", "ValidationPlanRef",
    "ValidationResult", "ValidationResultRef", "ValidationScopeError",
    "ValidationService", "ValidationSubject", "ValidationVerdict",
]
