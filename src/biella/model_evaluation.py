"""Project-scoped, evidence-based model capability comparison contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
import re
from types import MappingProxyType

from .artifact import ContentRef
from .call_ledger import ModelCall, ToolCall
from .capability import CapabilityRef
from .context_retrieval import ContextReceipt
from .project import ProjectRef
from .resource import ResourceSnapshot
from .run import RunRef
from .validation import EvaluationResult, ValidationResult


_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[a-z][a-z0-9+.-]{1,63}://[^\s\x00-\x1f]{1,1024}")


class EvaluationContractError(ValueError):
    """Model-evaluation contract is malformed, mixed, or overclaims evidence."""


class EvidenceClass(str, Enum):
    CONTROLLED = "CONTROLLED"
    QUASI_CONTROLLED = "QUASI_CONTROLLED"
    OBSERVATIONAL = "OBSERVATIONAL"


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise EvaluationContractError("evaluation evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _key(value: object, label: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise EvaluationContractError(f"{label} is malformed")
    return value


def _ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise EvaluationContractError(f"{label} must be an exact reference")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise EvaluationContractError(f"{label} must be a SHA-256 digest")
    return value


def _positive(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise EvaluationContractError(f"{label} must be positive")
    return value


def _timestamp(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise EvaluationContractError(f"{label} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise EvaluationContractError(f"{label} must be a timezone-aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvaluationContractError(f"{label} must be a timezone-aware timestamp")
    return value


def _text_map(values: Mapping[str, str], label: str, *, nonempty: bool = False) -> Mapping[str, str]:
    if not isinstance(values, Mapping) or (nonempty and not values) or len(values) > 64:
        raise EvaluationContractError(f"{label} is malformed or unbounded")
    copied = dict(values)
    for key, value in copied.items():
        if key != "MODEL_IMPLEMENTATION":
            _key(key, f"{label} key")
        if not isinstance(value, str) or not value or len(value) > 1024 or "\x00" in value:
            raise EvaluationContractError(f"{label} value is malformed")
    return MappingProxyType(dict(sorted(copied.items())))


def _metric_map(values: Mapping[str, float | None], label: str) -> Mapping[str, float | None]:
    if not isinstance(values, Mapping) or len(values) > 64:
        raise EvaluationContractError(f"{label} is malformed or unbounded")
    copied = dict(values)
    for key, value in copied.items():
        _key(key, f"{label} key")
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
        ):
            raise EvaluationContractError(f"{label} values must be finite or unknown")
        copied[key] = None if value is None else float(value)
    return MappingProxyType(dict(sorted(copied.items())))


@dataclass(frozen=True)
class WorkloadProfile:
    project_ref: ProjectRef
    profile_id: str
    version: int
    content_ref: ContentRef
    dimensions: Mapping[str, str]
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.content_ref, ContentRef):
            raise EvaluationContractError("WorkloadProfile Project and content are required")
        _key(self.profile_id, "profile identity")
        _positive(self.version, "profile version")
        object.__setattr__(self, "dimensions", _text_map(self.dimensions, "profile dimensions", nonempty=True))
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"content": self.content_ref.value, "dimensions": dict(self.dimensions), "profile_id": self.profile_id, "project": self.project_ref.value, "version": self.version}


@dataclass(frozen=True)
class EvaluationTask:
    project_ref: ProjectRef
    task_id: str
    version: int
    content_ref: ContentRef
    capability_ref: CapabilityRef
    template_ref: str
    domain: str
    difficulty: str
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.content_ref, ContentRef) or not isinstance(self.capability_ref, CapabilityRef):
            raise EvaluationContractError("EvaluationTask identity is malformed")
        _key(self.task_id, "task identity")
        _positive(self.version, "task version")
        _ref(self.template_ref, "task template")
        _key(self.domain, "task domain")
        _key(self.difficulty, "task difficulty")
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"capability": self.capability_ref.value, "content": self.content_ref.value, "difficulty": self.difficulty, "domain": self.domain, "project": self.project_ref.value, "task_id": self.task_id, "template": self.template_ref, "version": self.version}


@dataclass(frozen=True)
class EvaluationTaskSet:
    project_ref: ProjectRef
    task_set_id: str
    version: int
    content_ref: ContentRef
    tasks: tuple[EvaluationTask, ...]
    selection_policy_ref: str
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.content_ref, ContentRef):
            raise EvaluationContractError("EvaluationTaskSet identity is malformed")
        _key(self.task_set_id, "task-set identity")
        _positive(self.version, "task-set version")
        _ref(self.selection_policy_ref, "task selection policy")
        tasks = tuple(self.tasks)
        if not tasks or len(tasks) > 4096 or not all(isinstance(item, EvaluationTask) for item in tasks):
            raise EvaluationContractError("task set is empty or malformed")
        if any(item.project_ref != self.project_ref for item in tasks) or len({item.canonical_digest for item in tasks}) != len(tasks):
            raise EvaluationContractError("task set crosses Project scope or duplicates a task")
        object.__setattr__(self, "tasks", tuple(sorted(tasks, key=lambda item: item.canonical_digest)))
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"content": self.content_ref.value, "project": self.project_ref.value, "selection_policy": self.selection_policy_ref, "task_set_id": self.task_set_id, "tasks": [item.canonical_digest for item in self.tasks], "version": self.version}


@dataclass(frozen=True)
class ModelCandidate:
    project_ref: ProjectRef
    candidate_id: str
    deployment_ref: str
    deployment_digest: str
    adapter_ref: str
    runtime_ref: str
    model_revision: str | None
    hosted_revision_mutable: bool
    capability_ref: CapabilityRef
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.capability_ref, CapabilityRef):
            raise EvaluationContractError("candidate Project or Capability is malformed")
        _key(self.candidate_id, "candidate identity")
        for value, label in ((self.deployment_ref, "candidate deployment"), (self.adapter_ref, "candidate adapter"), (self.runtime_ref, "candidate runtime")):
            _ref(value, label)
        _sha(self.deployment_digest, "candidate deployment digest")
        if self.model_revision is not None:
            _key(self.model_revision, "candidate model revision")
        if not isinstance(self.hosted_revision_mutable, bool):
            raise EvaluationContractError("hosted revision mutability must be explicit")
        if not self.hosted_revision_mutable and self.model_revision is None:
            raise EvaluationContractError("immutable hosted model requires an exact revision")
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"adapter": self.adapter_ref, "capability": self.capability_ref.value, "candidate_id": self.candidate_id, "deployment": self.deployment_ref, "deployment_digest": self.deployment_digest, "hosted_revision_mutable": self.hosted_revision_mutable, "model_revision": self.model_revision, "project": self.project_ref.value, "runtime": self.runtime_ref}


@dataclass(frozen=True)
class ModelEvaluationSuite:
    project_ref: ProjectRef
    suite_id: str
    version: int
    capability_ref: CapabilityRef
    workload_profile: WorkloadProfile
    task_set: EvaluationTaskSet
    evidence_class: EvidenceClass
    controlled_variables: Mapping[str, str]
    confounders: Mapping[str, str]
    candidates: tuple[ModelCandidate, ...]
    execution_policy_ref: str
    tool_policy_ref: str
    context_policy_ref: str
    validation_policy_ref: str
    resource_policy_ref: str
    generation_policy_ref: str
    order_policy_ref: str
    cache_policy_ref: str
    repetitions: int
    scoring_policy_ref: str | None
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.capability_ref, CapabilityRef):
            raise EvaluationContractError("suite Project or Capability is malformed")
        _key(self.suite_id, "suite identity")
        _positive(self.version, "suite version")
        if not isinstance(self.workload_profile, WorkloadProfile) or not isinstance(self.task_set, EvaluationTaskSet):
            raise EvaluationContractError("suite profile or task set is malformed")
        if self.workload_profile.project_ref != self.project_ref or self.task_set.project_ref != self.project_ref:
            raise EvaluationContractError("suite profile or task set crossed Project scope")
        if not isinstance(self.evidence_class, EvidenceClass):
            raise EvaluationContractError("suite evidence class is malformed")
        controlled = _text_map(self.controlled_variables, "controlled variables", nonempty=True)
        if controlled.get("MODEL_IMPLEMENTATION") != "varied":
            raise EvaluationContractError("MODEL_IMPLEMENTATION must be the explicit primary varied dimension")
        confounders = _text_map(self.confounders, "confounders")
        if any(value.lower() in {"uncontrolled", "unknown", "varied"} for value in confounders.values()):
            raise EvaluationContractError("uncontrolled confounder cannot support the declared evidence class")
        object.__setattr__(self, "controlled_variables", controlled)
        object.__setattr__(self, "confounders", confounders)
        candidates = tuple(self.candidates)
        if len(candidates) < 2 or len(candidates) > 128 or not all(isinstance(item, ModelCandidate) for item in candidates):
            raise EvaluationContractError("suite requires at least two exact candidates")
        if any(item.project_ref != self.project_ref or item.capability_ref != self.capability_ref for item in candidates):
            raise EvaluationContractError("candidate crossed Project scope or changed capability")
        if len({item.candidate_id for item in candidates}) != len(candidates):
            raise EvaluationContractError("candidate identity is duplicated")
        object.__setattr__(self, "candidates", tuple(sorted(candidates, key=lambda item: item.candidate_id)))
        for value, label in (
            (self.execution_policy_ref, "execution policy"), (self.tool_policy_ref, "tool policy"), (self.context_policy_ref, "context policy"),
            (self.validation_policy_ref, "validation policy"), (self.resource_policy_ref, "resource policy"), (self.generation_policy_ref, "generation policy"),
            (self.order_policy_ref, "order policy"), (self.cache_policy_ref, "cache policy"),
        ):
            _ref(value, label)
        _positive(self.repetitions, "suite repetitions")
        if self.scoring_policy_ref is not None:
            _ref(self.scoring_policy_ref, "scoring policy")
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"cache_policy": self.cache_policy_ref, "candidates": [item.canonical_digest for item in self.candidates], "capability": self.capability_ref.value, "confounders": dict(self.confounders), "context_policy": self.context_policy_ref, "controlled_variables": dict(self.controlled_variables), "evidence_class": self.evidence_class.value, "execution_policy": self.execution_policy_ref, "generation_policy": self.generation_policy_ref, "order_policy": self.order_policy_ref, "profile": self.workload_profile.canonical_digest, "project": self.project_ref.value, "repetitions": self.repetitions, "resource_policy": self.resource_policy_ref, "scoring_policy": self.scoring_policy_ref, "suite_id": self.suite_id, "task_set": self.task_set.canonical_digest, "tool_policy": self.tool_policy_ref, "validation_policy": self.validation_policy_ref, "version": self.version}


@dataclass(frozen=True)
class ModelEvaluationRun:
    suite: ModelEvaluationSuite
    candidate_id: str
    task: EvaluationTask
    repetition: int
    run_ref: RunRef
    model_calls: tuple[ModelCall, ...]
    tool_calls: tuple[ToolCall, ...]
    validation_results: tuple[ValidationResult, ...]
    evaluation_results: tuple[EvaluationResult, ...]
    context_receipt: ContextReceipt | None
    resource_snapshots: tuple[ResourceSnapshot, ...]
    transport_outcome: str
    semantic_outcome: str
    infrastructure_outcome: str
    status: str
    started_at: str
    completed_at: str | None
    resource_metrics: Mapping[str, float | None]
    token_count: int | None
    cost: float | None
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.suite, ModelEvaluationSuite) or not isinstance(self.task, EvaluationTask) or not isinstance(self.run_ref, RunRef):
            raise EvaluationContractError("evaluation cell identity is malformed")
        candidate = next((item for item in self.suite.candidates if item.candidate_id == self.candidate_id), None)
        if candidate is None or self.task not in self.suite.task_set.tasks:
            raise EvaluationContractError("evaluation cell candidate or task is absent from suite")
        if self.run_ref.project_ref != self.suite.project_ref or self.task.project_ref != self.suite.project_ref:
            raise EvaluationContractError("evaluation cell crossed Project scope")
        repetition = _positive(self.repetition, "evaluation repetition")
        if repetition > self.suite.repetitions:
            raise EvaluationContractError("evaluation repetition exceeds suite contract")
        for call in self.model_calls:
            if call.project_ref != self.suite.project_ref or call.run_ref != self.run_ref or call.retry_of is not None:
                raise EvaluationContractError("call crossed scope/run or retry was counted as a repetition")
        for tool_call in self.tool_calls:
            if tool_call.project_ref != self.suite.project_ref or tool_call.run_ref != self.run_ref or tool_call.retry_of is not None:
                raise EvaluationContractError("call crossed scope/run or retry was counted as a repetition")
        if any(item.result_ref.project_ref != self.suite.project_ref for item in self.validation_results) or any(item.evaluation_ref.project_ref != self.suite.project_ref for item in self.evaluation_results):
            raise EvaluationContractError("validation/evaluation result crossed Project scope")
        if self.context_receipt is not None and self.context_receipt.project_ref != self.suite.project_ref:
            raise EvaluationContractError("ContextReceipt crossed Project scope")
        if any(item.project_ref != self.suite.project_ref for item in self.resource_snapshots):
            raise EvaluationContractError("ResourceSnapshot crossed Project scope")
        for value, label in ((self.transport_outcome, "transport outcome"), (self.semantic_outcome, "semantic outcome"), (self.infrastructure_outcome, "infrastructure outcome"), (self.status, "status")):
            _key(value, label)
        started = _timestamp(self.started_at, "started_at")
        if self.completed_at is not None:
            completed = _timestamp(self.completed_at, "completed_at")
            if datetime.fromisoformat(completed) < datetime.fromisoformat(started):
                raise EvaluationContractError("evaluation completion precedes start")
        object.__setattr__(self, "resource_metrics", _metric_map(self.resource_metrics, "resource metrics"))
        if self.token_count is not None and (not isinstance(self.token_count, int) or isinstance(self.token_count, bool) or self.token_count < 0):
            raise EvaluationContractError("token count must be non-negative or unknown")
        if self.cost is not None and (isinstance(self.cost, bool) or not isinstance(self.cost, (int, float)) or not math.isfinite(float(self.cost)) or self.cost < 0):
            raise EvaluationContractError("cost must be non-negative finite or unknown")
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"candidate": self.candidate_id, "calls": [item.record_sha256 for item in self.model_calls], "completed_at": self.completed_at, "context": None if self.context_receipt is None else self.context_receipt.record_sha256, "cost": self.cost, "evaluation_results": [item.record_sha256 for item in self.evaluation_results], "infrastructure_outcome": self.infrastructure_outcome, "resource_metrics": dict(self.resource_metrics), "resource_snapshots": [item.record_sha256 for item in self.resource_snapshots], "repetition": self.repetition, "run": f"run://{self.run_ref.project_ref.value}/{self.run_ref.run_id}", "semantic_outcome": self.semantic_outcome, "started_at": self.started_at, "status": self.status, "suite": self.suite.canonical_digest, "task": self.task.canonical_digest, "token_count": self.token_count, "tool_calls": [item.record_sha256 for item in self.tool_calls], "transport_outcome": self.transport_outcome, "validation_results": [item.record_sha256 for item in self.validation_results]}


@dataclass(frozen=True)
class DescriptiveStatistics:
    metric: str
    count: int
    mean: float | None
    standard_deviation: float | None
    minimum: float | None
    maximum: float | None
    unit: str

    def __post_init__(self) -> None:
        _key(self.metric, "statistics metric")
        _positive(self.count, "statistics count")
        _key(self.unit, "statistics unit")
        values = (self.mean, self.standard_deviation, self.minimum, self.maximum)
        if any(value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))) for value in values):
            raise EvaluationContractError("statistics must be finite or explicitly unknown")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise EvaluationContractError("statistics minimum exceeds maximum")


@dataclass(frozen=True)
class PairwiseComparison:
    suite: ModelEvaluationSuite
    left_candidate_id: str
    right_candidate_id: str
    paired_wins: int
    paired_losses: int
    paired_ties: int
    conclusion: str
    resource_confounder_ref: str | None
    winner: None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.suite, ModelEvaluationSuite) or self.left_candidate_id == self.right_candidate_id:
            raise EvaluationContractError("pairwise comparison candidates are malformed")
        candidates = {item.candidate_id for item in self.suite.candidates}
        if self.left_candidate_id not in candidates or self.right_candidate_id not in candidates:
            raise EvaluationContractError("pairwise comparison candidate is absent from suite")
        for value, label in ((self.paired_wins, "paired wins"), (self.paired_losses, "paired losses"), (self.paired_ties, "paired ties")):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise EvaluationContractError(f"{label} is malformed")
        if self.conclusion not in {"INSUFFICIENT_EVIDENCE", "DESCRIPTIVE"}:
            raise EvaluationContractError("pairwise comparison cannot claim a universal winner")
        if self.resource_confounder_ref is not None:
            _ref(self.resource_confounder_ref, "resource confounder")


@dataclass(frozen=True)
class ModelEvaluationResult:
    suite: ModelEvaluationSuite
    runs: tuple[ModelEvaluationRun, ...]
    statistics: tuple[DescriptiveStatistics, ...]
    pairwise_comparisons: tuple[PairwiseComparison, ...]
    suite_digest: str = field(init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.suite, ModelEvaluationSuite):
            raise EvaluationContractError("result suite is required")
        runs = tuple(self.runs)
        if not all(isinstance(item, ModelEvaluationRun) and item.suite.canonical_digest == self.suite.canonical_digest for item in runs):
            raise EvaluationContractError("result run does not bind the exact suite")
        cells = {(item.candidate_id, item.task.canonical_digest, item.repetition) for item in runs}
        if len(cells) != len(runs):
            raise EvaluationContractError("result repeats an evaluation cell")
        statistics = tuple(self.statistics)
        comparisons = tuple(self.pairwise_comparisons)
        if len({item.metric for item in statistics}) != len(statistics) or any(item.suite.canonical_digest != self.suite.canonical_digest for item in comparisons):
            raise EvaluationContractError("result statistics or comparison is inconsistent")
        object.__setattr__(self, "runs", tuple(sorted(runs, key=lambda item: (item.candidate_id, item.task.canonical_digest, item.repetition))))
        object.__setattr__(self, "statistics", tuple(sorted(statistics, key=lambda item: item.metric)))
        object.__setattr__(self, "pairwise_comparisons", tuple(sorted(comparisons, key=lambda item: (item.left_candidate_id, item.right_candidate_id))))
        object.__setattr__(self, "suite_digest", self.suite.canonical_digest)
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"comparisons": [{"conclusion": item.conclusion, "left": item.left_candidate_id, "losses": item.paired_losses, "resource_confounder": item.resource_confounder_ref, "right": item.right_candidate_id, "ties": item.paired_ties, "wins": item.paired_wins} for item in self.pairwise_comparisons], "runs": [item.canonical_digest for item in self.runs], "statistics": [{"count": item.count, "maximum": item.maximum, "mean": item.mean, "metric": item.metric, "minimum": item.minimum, "standard_deviation": item.standard_deviation, "unit": item.unit} for item in self.statistics], "suite": self.suite.canonical_digest}


@dataclass(frozen=True)
class ModelEvaluationKnowledgeCandidate:
    """Scoped observation only; this contract supplies no promotion or routing policy."""

    project_ref: ProjectRef
    suite_digest: str
    content_ref: ContentRef
    evidence_refs: tuple[str, ...]
    promotion_allowed: bool = field(default=False, init=False)
    routing_allowed: bool = field(default=False, init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.content_ref, ContentRef):
            raise EvaluationContractError("knowledge candidate Project/content is malformed")
        _sha(self.suite_digest, "knowledge candidate suite digest")
        refs = tuple(self.evidence_refs)
        if not refs or len(set(refs)) != len(refs):
            raise EvaluationContractError("knowledge candidate evidence is missing or duplicated")
        for ref in refs:
            _ref(ref, "knowledge candidate evidence")
        object.__setattr__(self, "evidence_refs", tuple(sorted(refs)))
        object.__setattr__(self, "canonical_digest", _digest({"content": self.content_ref.value, "evidence": list(self.evidence_refs), "project": self.project_ref.value, "suite": self.suite_digest}))
