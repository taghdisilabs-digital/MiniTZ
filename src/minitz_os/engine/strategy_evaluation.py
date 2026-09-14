"""Project-scoped execution-strategy evaluation contracts.

Strategy is immutable experiment data.  These contracts deliberately produce
descriptive evidence only: they do not install routing policy, weaken Task
validation, or create permanent agent authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import itertools
import json
import math
import re
import statistics
from types import MappingProxyType

from .artifact import ContentRef
from .capability import CapabilityRef
from .model_evaluation import (
    EvidenceClass,
    EvaluationTask,
    EvaluationTaskSet,
    ModelCandidate,
    WorkloadProfile,
)
from .project import ProjectRef
from .run import RunRef


_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_DIMENSION = re.compile(r"[A-Z][A-Z0-9_]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[a-z][a-z0-9+.-]{1,63}://[^\s\x00-\x1f]{1,1024}")
_OUTCOMES = frozenset({"passed", "failed", "cancelled", "timed-out", "unknown"})


class StrategyContractError(ValueError):
    """A strategy identity, experiment, metric, or result is malformed."""


class StrategyPattern(str, Enum):
    DIRECT = "DIRECT"
    TOOL_LOOP = "TOOL_LOOP"
    PLAN_FIRST = "PLAN_FIRST"
    RETRIEVAL_FIRST = "RETRIEVAL_FIRST"
    SPECIALIST_AS_TOOL = "SPECIALIST_AS_TOOL"
    PARALLEL_RESEARCH = "PARALLEL_RESEARCH"
    PARALLEL_IMPLEMENTATION = "PARALLEL_IMPLEMENTATION"
    VALIDATOR_ON_DEMAND = "VALIDATOR_ON_DEMAND"
    NO_REVIEW = "NO_REVIEW"
    INDEPENDENT_VALIDATION = "INDEPENDENT_VALIDATION"


class StrategyDimension(str, Enum):
    PROMPT_SKILL = "PROMPT_SKILL"
    TOOL_POLICY = "TOOL_POLICY"
    CONTEXT_POLICY = "CONTEXT_POLICY"
    DECOMPOSITION = "DECOMPOSITION"
    PARALLELIZATION = "PARALLELIZATION"
    SPECIALIST = "SPECIALIST"
    VALIDATION = "VALIDATION"
    FULL_STRATEGY = "FULL_STRATEGY"


class MatrixKind(str, Enum):
    SAME_MODEL = "SAME_MODEL"
    FACTORIAL = "FACTORIAL"
    OBSERVATIONAL = "OBSERVATIONAL"


class StrategyEffectKind(str, Enum):
    MODEL = "MODEL"
    STRATEGY = "STRATEGY"
    INTERACTION = "INTERACTION"


def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise StrategyContractError("strategy evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _key(value: object, label: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise StrategyContractError(f"{label} is malformed")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise StrategyContractError(f"{label} must be a SHA-256 digest")
    return value


def _ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise StrategyContractError(f"{label} must be an exact reference")
    return value


def _positive(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise StrategyContractError(f"{label} must be positive")
    return value


def _nonnegative(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise StrategyContractError(f"{label} must be non-negative")
    return value


def _finite_optional(value: object, label: str, *, nonnegative: bool = False) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise StrategyContractError(f"{label} must be finite or unknown")
    number = float(value)
    if nonnegative and number < 0:
        raise StrategyContractError(f"{label} must be non-negative or unknown")
    return number


def _timestamp(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise StrategyContractError(f"{label} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise StrategyContractError(f"{label} must be a timezone-aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StrategyContractError(f"{label} must be a timezone-aware timestamp")
    return value


def _text_map(values: Mapping[str, str], label: str, *, dimension_keys: bool = False) -> Mapping[str, str]:
    if not isinstance(values, Mapping) or len(values) > 64:
        raise StrategyContractError(f"{label} is malformed or unbounded")
    copied = dict(values)
    for key, value in copied.items():
        if not isinstance(key, str) or (
            (_DIMENSION.fullmatch(key) is None) if dimension_keys else (_KEY.fullmatch(key) is None)
        ):
            raise StrategyContractError(f"{label} key is malformed")
        if not isinstance(value, str) or not value or len(value) > 1024 or "\x00" in value:
            raise StrategyContractError(f"{label} value is malformed")
    return MappingProxyType(dict(sorted(copied.items())))


def _metric_map(values: Mapping[str, float | None]) -> Mapping[str, float | None]:
    if not isinstance(values, Mapping) or len(values) > 64:
        raise StrategyContractError("resource metrics are malformed or unbounded")
    copied: dict[str, float | None] = {}
    for key, value in values.items():
        _key(key, "resource metric")
        copied[key] = _finite_optional(value, f"resource metric {key}")
    return MappingProxyType(dict(sorted(copied.items())))


@dataclass(frozen=True)
class SkillArtifact:
    project_ref: ProjectRef
    skill_id: str
    version: int
    content_ref: ContentRef
    applicability: Mapping[str, str]
    supersedes_digest: str | None = None
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.content_ref, ContentRef):
            raise StrategyContractError("SkillArtifact Project/content identity is malformed")
        _key(self.skill_id, "skill identity")
        _positive(self.version, "skill version")
        applicability = _text_map(self.applicability, "skill applicability")
        if not applicability:
            raise StrategyContractError("skill applicability is required")
        if self.supersedes_digest is not None:
            _sha(self.supersedes_digest, "superseded skill")
            if self.version == 1:
                raise StrategyContractError("first skill version cannot supersede another version")
        object.__setattr__(self, "applicability", applicability)
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "applicability": dict(self.applicability),
            "content": self.content_ref.value,
            "project": self.project_ref.value,
            "skill_id": self.skill_id,
            "supersedes": self.supersedes_digest,
            "version": self.version,
        }

    @classmethod
    def revise(
        cls,
        previous: SkillArtifact,
        content_ref: ContentRef,
        *,
        applicability: Mapping[str, str] | None = None,
    ) -> SkillArtifact:
        return cls(
            previous.project_ref,
            previous.skill_id,
            previous.version + 1,
            content_ref,
            previous.applicability if applicability is None else applicability,
            previous.canonical_digest,
        )


@dataclass(frozen=True)
class PromptArtifact:
    project_ref: ProjectRef
    prompt_id: str
    version: int
    content_ref: ContentRef
    applicability: Mapping[str, str]
    supersedes_digest: str | None = None
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.content_ref, ContentRef):
            raise StrategyContractError("PromptArtifact Project/content identity is malformed")
        _key(self.prompt_id, "prompt identity")
        _positive(self.version, "prompt version")
        applicability = _text_map(self.applicability, "prompt applicability")
        if not applicability:
            raise StrategyContractError("prompt applicability is required")
        if self.supersedes_digest is not None:
            _sha(self.supersedes_digest, "superseded prompt")
            if self.version == 1:
                raise StrategyContractError("first prompt version cannot supersede another version")
        object.__setattr__(self, "applicability", applicability)
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "applicability": dict(self.applicability),
            "content": self.content_ref.value,
            "project": self.project_ref.value,
            "prompt_id": self.prompt_id,
            "supersedes": self.supersedes_digest,
            "version": self.version,
        }

    @classmethod
    def revise(
        cls,
        previous: PromptArtifact,
        content_ref: ContentRef,
        *,
        applicability: Mapping[str, str] | None = None,
    ) -> PromptArtifact:
        return cls(
            previous.project_ref,
            previous.prompt_id,
            previous.version + 1,
            content_ref,
            previous.applicability if applicability is None else applicability,
            previous.canonical_digest,
        )


@dataclass(frozen=True)
class ExecutionStrategy:
    project_ref: ProjectRef
    strategy_id: str
    version: int
    patterns: tuple[StrategyPattern, ...]
    applicability: Mapping[str, str]
    skill_artifacts: tuple[SkillArtifact, ...]
    prompt_artifacts: tuple[PromptArtifact, ...]
    decomposition_policy_ref: str
    tool_policy_ref: str
    context_policy_ref: str
    model_call_policy_ref: str
    loop_stop_policy_ref: str
    parallelization_policy_ref: str
    specialist_policy_ref: str
    validation_policy_refs: tuple[str, ...]
    failure_policy_ref: str
    output_policy_ref: str
    mandatory_hierarchy: bool = field(default=False, init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise StrategyContractError("ExecutionStrategy Project identity is malformed")
        _key(self.strategy_id, "strategy identity")
        _positive(self.version, "strategy version")
        patterns = tuple(self.patterns)
        if not patterns or len(set(patterns)) != len(patterns) or not all(isinstance(item, StrategyPattern) for item in patterns):
            raise StrategyContractError("strategy patterns are empty, duplicated, or malformed")
        applicability = _text_map(self.applicability, "strategy applicability")
        if not applicability:
            raise StrategyContractError("strategy applicability is required")
        skills = tuple(self.skill_artifacts)
        prompts = tuple(self.prompt_artifacts)
        if not skills or not prompts or not all(isinstance(item, SkillArtifact) for item in skills) or not all(isinstance(item, PromptArtifact) for item in prompts):
            raise StrategyContractError("strategy requires exact SkillArtifact and PromptArtifact identities")
        if any(item.project_ref != self.project_ref for item in skills) or any(
            item.project_ref != self.project_ref for item in prompts
        ):
            raise StrategyContractError("strategy Skill/Prompt crossed Project scope")
        if len({item.canonical_digest for item in skills}) != len(skills) or len({item.canonical_digest for item in prompts}) != len(prompts):
            raise StrategyContractError("strategy repeats a Skill/Prompt version")
        refs = (
            (self.decomposition_policy_ref, "decomposition policy"),
            (self.tool_policy_ref, "tool policy"),
            (self.context_policy_ref, "context policy"),
            (self.model_call_policy_ref, "model-call policy"),
            (self.loop_stop_policy_ref, "loop/stop policy"),
            (self.parallelization_policy_ref, "parallelization policy"),
            (self.specialist_policy_ref, "specialist policy"),
            (self.failure_policy_ref, "failure policy"),
            (self.output_policy_ref, "output policy"),
        )
        for value, label in refs:
            _ref(value, label)
        validation = tuple(self.validation_policy_refs)
        if not validation or len(set(validation)) != len(validation):
            raise StrategyContractError("strategy validation policy refs are missing or duplicated")
        for value in validation:
            _ref(value, "validation policy")
        object.__setattr__(self, "patterns", tuple(sorted(patterns, key=lambda item: item.value)))
        object.__setattr__(self, "applicability", applicability)
        object.__setattr__(self, "skill_artifacts", tuple(sorted(skills, key=lambda item: item.canonical_digest)))
        object.__setattr__(self, "prompt_artifacts", tuple(sorted(prompts, key=lambda item: item.canonical_digest)))
        object.__setattr__(self, "validation_policy_refs", tuple(sorted(validation)))
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "applicability": dict(self.applicability),
            "context_policy": self.context_policy_ref,
            "decomposition_policy": self.decomposition_policy_ref,
            "failure_policy": self.failure_policy_ref,
            "loop_stop_policy": self.loop_stop_policy_ref,
            "model_call_policy": self.model_call_policy_ref,
            "output_policy": self.output_policy_ref,
            "parallelization_policy": self.parallelization_policy_ref,
            "patterns": [item.value for item in self.patterns],
            "project": self.project_ref.value,
            "prompts": [item.canonical_digest for item in self.prompt_artifacts],
            "skills": [item.canonical_digest for item in self.skill_artifacts],
            "specialist_policy": self.specialist_policy_ref,
            "strategy_id": self.strategy_id,
            "tool_policy": self.tool_policy_ref,
            "validation_policies": list(self.validation_policy_refs),
            "version": self.version,
        }


_POLICY_FIELDS: Mapping[StrategyDimension, frozenset[str]] = MappingProxyType(
    {
        StrategyDimension.PROMPT_SKILL: frozenset({"skills", "prompts"}),
        StrategyDimension.TOOL_POLICY: frozenset({"tool_policy"}),
        StrategyDimension.CONTEXT_POLICY: frozenset({"context_policy"}),
        StrategyDimension.DECOMPOSITION: frozenset({"decomposition_policy"}),
        StrategyDimension.PARALLELIZATION: frozenset({"parallelization_policy"}),
        StrategyDimension.SPECIALIST: frozenset({"specialist_policy"}),
        StrategyDimension.VALIDATION: frozenset({"validation_policies"}),
        StrategyDimension.FULL_STRATEGY: frozenset(
            {
                "skills",
                "prompts",
                "tool_policy",
                "context_policy",
                "decomposition_policy",
                "parallelization_policy",
                "specialist_policy",
                "validation_policies",
                "model_call_policy",
                "loop_stop_policy",
                "failure_policy",
                "output_policy",
                "patterns",
            }
        ),
    }
)


def _strategy_controls(strategy: ExecutionStrategy) -> dict[str, object]:
    payload = strategy.payload()
    return {
        key: payload[key]
        for key in (
            "context_policy",
            "decomposition_policy",
            "failure_policy",
            "loop_stop_policy",
            "model_call_policy",
            "output_policy",
            "parallelization_policy",
            "patterns",
            "prompts",
            "skills",
            "specialist_policy",
            "tool_policy",
            "validation_policies",
        )
    }


@dataclass(frozen=True)
class StrategyEvaluationExperiment:
    project_ref: ProjectRef
    experiment_id: str
    version: int
    capability_ref: CapabilityRef
    workload_profile: WorkloadProfile
    task_set: EvaluationTaskSet
    evidence_class: EvidenceClass
    matrix_kind: MatrixKind
    controlled_variables: Mapping[str, str]
    varied_dimensions: tuple[StrategyDimension, ...]
    confounders: Mapping[str, str]
    models: tuple[ModelCandidate, ...]
    strategies: tuple[ExecutionStrategy, ...]
    required_validation_refs: tuple[str, ...]
    resource_policy_ref: str
    order_policy_ref: str
    cache_policy_ref: str
    side_effect_authority: str
    repetitions: int
    primary_variable: str = field(default="EXECUTION_STRATEGY", init=False)
    mandatory_agent_hierarchy_created: bool = field(default=False, init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.capability_ref, CapabilityRef):
            raise StrategyContractError("experiment Project/Capability identity is malformed")
        _key(self.experiment_id, "experiment identity")
        _positive(self.version, "experiment version")
        if not isinstance(self.workload_profile, WorkloadProfile) or not isinstance(self.task_set, EvaluationTaskSet):
            raise StrategyContractError("experiment workload/task set is malformed")
        if self.workload_profile.project_ref != self.project_ref or self.task_set.project_ref != self.project_ref:
            raise StrategyContractError("experiment workload/task set crossed Project scope")
        if any(item.capability_ref != self.capability_ref for item in self.task_set.tasks):
            raise StrategyContractError("experiment task Capability differs")
        if not isinstance(self.evidence_class, EvidenceClass) or not isinstance(self.matrix_kind, MatrixKind):
            raise StrategyContractError("experiment evidence or matrix class is malformed")
        controlled = _text_map(self.controlled_variables, "controlled variables", dimension_keys=True)
        if controlled.get("EXECUTION_STRATEGY", "varied") != "varied":
            raise StrategyContractError("EXECUTION_STRATEGY must be the primary varied dimension")
        dimensions = tuple(self.varied_dimensions)
        if not dimensions or len(set(dimensions)) != len(dimensions) or not all(isinstance(item, StrategyDimension) for item in dimensions):
            raise StrategyContractError("varied strategy dimensions are missing or malformed")
        confounders = _text_map(self.confounders, "confounders")
        if self.evidence_class is EvidenceClass.CONTROLLED and any(
            value.casefold() in {"unknown", "uncontrolled", "varied"} for value in confounders.values()
        ):
            raise StrategyContractError("controlled experiment contains an uncontrolled confounder")
        models = tuple(self.models)
        strategies = tuple(self.strategies)
        if not models or len(models) > 64 or not all(isinstance(item, ModelCandidate) for item in models):
            raise StrategyContractError("experiment requires exact model identities")
        if len(strategies) < 2 or len(strategies) > 64 or not all(isinstance(item, ExecutionStrategy) for item in strategies):
            raise StrategyContractError("experiment requires at least two exact strategies")
        if any(item.project_ref != self.project_ref or item.capability_ref != self.capability_ref for item in models):
            raise StrategyContractError("experiment model crossed Project/Capability scope")
        if any(item.project_ref != self.project_ref for item in strategies):
            raise StrategyContractError("experiment strategy crossed Project scope")
        if len({item.candidate_id for item in models}) != len(models) or len({item.canonical_digest for item in strategies}) != len(strategies):
            raise StrategyContractError("experiment repeats a model or strategy identity")
        if len({(item.strategy_id, item.version) for item in strategies}) != len(strategies):
            raise StrategyContractError("experiment repeats a strategy label/version")
        model_control = controlled.get("MODEL_IMPLEMENTATION")
        if self.matrix_kind is MatrixKind.SAME_MODEL and (len(models) != 1 or model_control != "fixed"):
            raise StrategyContractError("same-model matrix must hold model implementation fixed")
        if self.matrix_kind is MatrixKind.FACTORIAL and (len(models) < 2 or model_control != "varied"):
            raise StrategyContractError("factorial matrix must vary at least two model implementations")
        if self.matrix_kind is MatrixKind.OBSERVATIONAL and self.evidence_class is not EvidenceClass.OBSERVATIONAL:
            raise StrategyContractError("observational matrix must be labeled OBSERVATIONAL")
        validation = tuple(self.required_validation_refs)
        if not validation or len(set(validation)) != len(validation):
            raise StrategyContractError("Task-required validation refs are missing or duplicated")
        for value in validation:
            _ref(value, "Task-required validation")
        if any(not set(validation) <= set(item.validation_policy_refs) for item in strategies):
            raise StrategyContractError("strategy validation would weaken Task-required validation")
        for value, label in (
            (self.resource_policy_ref, "resource policy"),
            (self.order_policy_ref, "order policy"),
            (self.cache_policy_ref, "cache policy"),
        ):
            _ref(value, label)
        if self.side_effect_authority not in {"READ_ONLY", "REVERSIBLE"}:
            raise StrategyContractError("strategy evaluation side effects must be read-only or reversible")
        _positive(self.repetitions, "experiment repetitions")
        if self.evidence_class is not EvidenceClass.OBSERVATIONAL:
            allowed = set().union(*(_POLICY_FIELDS[item] for item in dimensions))
            baseline = _strategy_controls(strategies[0])
            for strategy in strategies[1:]:
                candidate = _strategy_controls(strategy)
                hidden = {key for key in baseline if baseline[key] != candidate[key] and key not in allowed}
                if hidden:
                    raise StrategyContractError(f"strategy changed an unrecorded policy dimension: {sorted(hidden)[0]}")
        object.__setattr__(self, "controlled_variables", controlled)
        object.__setattr__(self, "varied_dimensions", tuple(sorted(dimensions, key=lambda item: item.value)))
        object.__setattr__(self, "confounders", confounders)
        object.__setattr__(self, "models", tuple(sorted(models, key=lambda item: item.candidate_id)))
        object.__setattr__(self, "strategies", tuple(sorted(strategies, key=lambda item: (item.strategy_id, item.version, item.canonical_digest))))
        object.__setattr__(self, "required_validation_refs", tuple(sorted(validation)))
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "cache_policy": self.cache_policy_ref,
            "capability": self.capability_ref.value,
            "confounders": dict(self.confounders),
            "controlled_variables": dict(self.controlled_variables),
            "evidence_class": self.evidence_class.value,
            "experiment_id": self.experiment_id,
            "matrix_kind": self.matrix_kind.value,
            "models": [item.canonical_digest for item in self.models],
            "order_policy": self.order_policy_ref,
            "primary_variable": self.primary_variable,
            "profile": self.workload_profile.canonical_digest,
            "project": self.project_ref.value,
            "repetitions": self.repetitions,
            "required_validation": list(self.required_validation_refs),
            "resource_policy": self.resource_policy_ref,
            "side_effect_authority": self.side_effect_authority,
            "strategies": [item.canonical_digest for item in self.strategies],
            "task_set": self.task_set.canonical_digest,
            "varied_dimensions": [item.value for item in self.varied_dimensions],
            "version": self.version,
        }


@dataclass(frozen=True)
class StrategyMetricSet:
    task_success: bool
    quality_score: float | None
    end_to_end_latency_seconds: float
    model_calls: int
    input_tokens: int | None
    output_tokens: int | None
    context_tokens: int | None
    model_latency_seconds: float | None
    cost: float | None
    tool_calls: int
    invalid_tool_calls: int
    redundant_tool_calls: int
    failed_tool_calls: int
    tool_latency_seconds: float | None
    tool_side_effects: int
    tool_data_bytes: int | None
    graph_nodes: int
    graph_depth: int
    graph_parallel_width: int
    graph_revisions: int
    graph_failures: int
    repairs: int
    replans: int
    completed_reuse: int
    resource_metrics: Mapping[str, float | None]
    duplicate_work_items: int = 0
    merge_conflicts: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.task_success, bool):
            raise StrategyContractError("Task success must be explicit")
        object.__setattr__(self, "quality_score", _finite_optional(self.quality_score, "quality score"))
        latency = _finite_optional(self.end_to_end_latency_seconds, "end-to-end latency", nonnegative=True)
        assert latency is not None
        object.__setattr__(self, "end_to_end_latency_seconds", latency)
        object.__setattr__(self, "model_latency_seconds", _finite_optional(self.model_latency_seconds, "model latency", nonnegative=True))
        object.__setattr__(self, "cost", _finite_optional(self.cost, "cost", nonnegative=True))
        object.__setattr__(self, "tool_latency_seconds", _finite_optional(self.tool_latency_seconds, "tool latency", nonnegative=True))
        for name in (
            "model_calls",
            "tool_calls",
            "invalid_tool_calls",
            "redundant_tool_calls",
            "failed_tool_calls",
            "tool_side_effects",
            "graph_failures",
            "repairs",
            "replans",
            "completed_reuse",
            "duplicate_work_items",
            "merge_conflicts",
        ):
            _nonnegative(getattr(self, name), name)
        for name in ("graph_nodes", "graph_depth", "graph_parallel_width"):
            _positive(getattr(self, name), name)
        _nonnegative(self.graph_revisions, "graph_revisions")
        for name in ("input_tokens", "output_tokens", "context_tokens", "tool_data_bytes"):
            value = getattr(self, name)
            if value is not None:
                _nonnegative(value, name)
        if any(
            value > self.tool_calls
            for value in (self.invalid_tool_calls, self.redundant_tool_calls, self.failed_tool_calls)
        ):
            raise StrategyContractError("tool failure metrics are inconsistent with ToolCalls")
        object.__setattr__(self, "resource_metrics", _metric_map(self.resource_metrics))

    def payload(self) -> dict[str, object]:
        return {
            "completed_reuse": self.completed_reuse,
            "context_tokens": self.context_tokens,
            "cost": self.cost,
            "duplicate_work_items": self.duplicate_work_items,
            "end_to_end_latency_seconds": self.end_to_end_latency_seconds,
            "failed_tool_calls": self.failed_tool_calls,
            "graph_depth": self.graph_depth,
            "graph_failures": self.graph_failures,
            "graph_nodes": self.graph_nodes,
            "graph_parallel_width": self.graph_parallel_width,
            "graph_revisions": self.graph_revisions,
            "input_tokens": self.input_tokens,
            "invalid_tool_calls": self.invalid_tool_calls,
            "model_calls": self.model_calls,
            "model_latency_seconds": self.model_latency_seconds,
            "merge_conflicts": self.merge_conflicts,
            "output_tokens": self.output_tokens,
            "quality_score": self.quality_score,
            "redundant_tool_calls": self.redundant_tool_calls,
            "repairs": self.repairs,
            "replans": self.replans,
            "resource_metrics": dict(self.resource_metrics),
            "task_success": self.task_success,
            "tool_calls": self.tool_calls,
            "tool_data_bytes": self.tool_data_bytes,
            "tool_latency_seconds": self.tool_latency_seconds,
            "tool_side_effects": self.tool_side_effects,
        }


@dataclass(frozen=True)
class StrategyEvaluationRun:
    experiment: StrategyEvaluationExperiment
    candidate_id: str
    strategy_id: str
    strategy_digest: str
    task: EvaluationTask
    repetition: int
    run_ref: RunRef
    metrics: StrategyMetricSet
    transport_outcome: str
    semantic_outcome: str
    infrastructure_outcome: str
    status: str
    started_at: str
    completed_at: str | None
    evidence_refs: tuple[str, ...]
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.experiment, StrategyEvaluationExperiment) or not isinstance(self.run_ref, RunRef):
            raise StrategyContractError("strategy evaluation run identity is malformed")
        if not isinstance(self.task, EvaluationTask) or not isinstance(self.metrics, StrategyMetricSet):
            raise StrategyContractError("strategy evaluation run task/metrics are malformed")
        model = next((item for item in self.experiment.models if item.candidate_id == self.candidate_id), None)
        strategy = next(
            (
                item
                for item in self.experiment.strategies
                if item.strategy_id == self.strategy_id and item.canonical_digest == self.strategy_digest
            ),
            None,
        )
        if model is None or strategy is None:
            raise StrategyContractError("strategy evaluation run model/strategy is absent from experiment")
        if self.task not in self.experiment.task_set.tasks or self.run_ref.project_ref != self.experiment.project_ref:
            raise StrategyContractError("strategy evaluation run crossed Task/Project scope")
        if _positive(self.repetition, "strategy evaluation repetition") > self.experiment.repetitions:
            raise StrategyContractError("strategy evaluation repetition exceeds experiment")
        for value, label in (
            (self.transport_outcome, "transport outcome"),
            (self.semantic_outcome, "semantic outcome"),
            (self.infrastructure_outcome, "infrastructure outcome"),
        ):
            if value not in _OUTCOMES:
                raise StrategyContractError(f"{label} is malformed")
        if self.status not in {"completed", "succeeded", "failed", "cancelled"}:
            raise StrategyContractError("strategy evaluation status is malformed")
        started = _timestamp(self.started_at, "started_at")
        if self.completed_at is not None:
            completed = _timestamp(self.completed_at, "completed_at")
            if datetime.fromisoformat(completed) < datetime.fromisoformat(started):
                raise StrategyContractError("strategy evaluation completion precedes start")
        refs = tuple(self.evidence_refs)
        if len(set(refs)) != len(refs):
            raise StrategyContractError("strategy evaluation evidence refs are duplicated")
        for value in refs:
            _ref(value, "strategy evaluation evidence")
        object.__setattr__(self, "evidence_refs", tuple(sorted(refs)))
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "completed_at": self.completed_at,
            "evidence_refs": list(self.evidence_refs),
            "experiment": self.experiment.canonical_digest,
            "infrastructure_outcome": self.infrastructure_outcome,
            "metrics": self.metrics.payload(),
            "model_id": self.candidate_id,
            "repetition": self.repetition,
            "run": f"run://{self.run_ref.project_ref.value}/{self.run_ref.run_id}",
            "semantic_outcome": self.semantic_outcome,
            "started_at": self.started_at,
            "status": self.status,
            "strategy_digest": self.strategy_digest,
            "strategy_id": self.strategy_id,
            "task": self.task.canonical_digest,
            "transport_outcome": self.transport_outcome,
        }


@dataclass(frozen=True)
class StrategyPairwiseComparison:
    experiment_digest: str
    model_digest: str
    left_strategy_digest: str
    right_strategy_digest: str
    paired_wins: int
    paired_losses: int
    paired_ties: int
    conclusion: str
    confounders: tuple[str, ...]
    winner: None = field(default=None, init=False)

    def __post_init__(self) -> None:
        for value, label in (
            (self.experiment_digest, "comparison experiment"),
            (self.model_digest, "comparison model"),
            (self.left_strategy_digest, "left strategy"),
            (self.right_strategy_digest, "right strategy"),
        ):
            _sha(value, label)
        if self.left_strategy_digest == self.right_strategy_digest:
            raise StrategyContractError("strategy comparison requires two versions")
        for count, label in (
            (self.paired_wins, "paired wins"),
            (self.paired_losses, "paired losses"),
            (self.paired_ties, "paired ties"),
        ):
            _nonnegative(count, label)
        if self.conclusion not in {"INSUFFICIENT_EVIDENCE", "DESCRIPTIVE"}:
            raise StrategyContractError("strategy comparison cannot claim a universal winner")
        confounders = tuple(self.confounders)
        if len(set(confounders)) != len(confounders):
            raise StrategyContractError("strategy comparison confounders are duplicated")
        for value in confounders:
            _key(value, "comparison confounder")
        object.__setattr__(self, "confounders", tuple(sorted(confounders)))


@dataclass(frozen=True)
class StrategyEffectEstimate:
    experiment_digest: str
    effect_kind: StrategyEffectKind
    metric: str
    identity_digests: tuple[str, ...]
    sample_count: int
    mean_delta: float | None
    conclusion: str
    applicability: Mapping[str, str]

    def __post_init__(self) -> None:
        _sha(self.experiment_digest, "effect experiment")
        if not isinstance(self.effect_kind, StrategyEffectKind):
            raise StrategyContractError("effect kind is malformed")
        _key(self.metric, "effect metric")
        identities = tuple(self.identity_digests)
        expected = 4 if self.effect_kind is StrategyEffectKind.INTERACTION else 3
        if len(identities) != expected or len(set(identities)) != len(identities):
            raise StrategyContractError("effect exact identities are missing or duplicated")
        for value in identities:
            _sha(value, "effect identity")
        _positive(self.sample_count, "effect sample count")
        object.__setattr__(self, "mean_delta", _finite_optional(self.mean_delta, "effect mean delta"))
        if self.conclusion not in {"INSUFFICIENT_EVIDENCE", "DESCRIPTIVE"}:
            raise StrategyContractError("effect conclusion overclaims evidence")
        applicability = _text_map(self.applicability, "effect applicability")
        if not applicability:
            raise StrategyContractError("effect applicability is required")
        object.__setattr__(self, "identity_digests", identities)
        object.__setattr__(self, "applicability", applicability)


@dataclass(frozen=True)
class StrategyEvaluationResult:
    experiment: StrategyEvaluationExperiment
    runs: tuple[StrategyEvaluationRun, ...]
    pairwise_comparisons: tuple[StrategyPairwiseComparison, ...]
    effects: tuple[StrategyEffectEstimate, ...]
    universal_winner_claimed: bool = field(default=False, init=False)
    mandatory_agent_hierarchy_created: bool = field(default=False, init=False)
    model_effect_mislabeled_strategy_effect: bool = field(default=False, init=False)
    strategy_effect_mislabeled_model_effect: bool = field(default=False, init=False)
    experiment_digest: str = field(init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.experiment, StrategyEvaluationExperiment):
            raise StrategyContractError("strategy result experiment is required")
        runs = tuple(self.runs)
        if not runs or any(item.experiment.canonical_digest != self.experiment.canonical_digest for item in runs):
            raise StrategyContractError("strategy result run differs from exact experiment")
        cells = {
            (item.candidate_id, item.strategy_digest, item.task.canonical_digest, item.repetition)
            for item in runs
        }
        if len(cells) != len(runs):
            raise StrategyContractError("strategy result repeats a cell")
        comparisons = tuple(self.pairwise_comparisons)
        effects = tuple(self.effects)
        if any(item.experiment_digest != self.experiment.canonical_digest for item in comparisons + effects):
            raise StrategyContractError("strategy result comparison/effect differs from experiment")
        object.__setattr__(self, "runs", tuple(sorted(runs, key=lambda item: (item.candidate_id, item.strategy_id, item.strategy_digest, item.task.canonical_digest, item.repetition))))
        object.__setattr__(self, "pairwise_comparisons", tuple(sorted(comparisons, key=lambda item: (item.model_digest, item.left_strategy_digest, item.right_strategy_digest))))
        object.__setattr__(self, "effects", tuple(sorted(effects, key=lambda item: (item.effect_kind.value, item.identity_digests))))
        object.__setattr__(self, "experiment_digest", self.experiment.canonical_digest)
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "comparisons": [
                {
                    "conclusion": item.conclusion,
                    "confounders": list(item.confounders),
                    "left_strategy": item.left_strategy_digest,
                    "losses": item.paired_losses,
                    "model": item.model_digest,
                    "right_strategy": item.right_strategy_digest,
                    "ties": item.paired_ties,
                    "wins": item.paired_wins,
                }
                for item in self.pairwise_comparisons
            ],
            "effects": [
                {
                    "applicability": dict(item.applicability),
                    "conclusion": item.conclusion,
                    "effect_kind": item.effect_kind.value,
                    "identities": list(item.identity_digests),
                    "mean_delta": item.mean_delta,
                    "metric": item.metric,
                    "sample_count": item.sample_count,
                }
                for item in self.effects
            ],
            "experiment": self.experiment.canonical_digest,
            "runs": [item.canonical_digest for item in self.runs],
        }


@dataclass(frozen=True)
class StrategyEvaluationKnowledgeCandidate:
    project_ref: ProjectRef
    experiment_digest: str
    content_ref: ContentRef
    evidence_refs: tuple[str, ...]
    promotion_allowed: bool = field(default=False, init=False)
    routing_allowed: bool = field(default=False, init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.content_ref, ContentRef):
            raise StrategyContractError("strategy knowledge candidate Project/content is malformed")
        _sha(self.experiment_digest, "strategy knowledge experiment")
        refs = tuple(self.evidence_refs)
        if not refs or len(set(refs)) != len(refs):
            raise StrategyContractError("strategy knowledge evidence is missing or duplicated")
        for value in refs:
            _ref(value, "strategy knowledge evidence")
        object.__setattr__(self, "evidence_refs", tuple(sorted(refs)))
        object.__setattr__(self, "canonical_digest", _digest({
            "content": self.content_ref.value,
            "evidence": list(self.evidence_refs),
            "experiment": self.experiment_digest,
            "project": self.project_ref.value,
        }))


def _score(run: StrategyEvaluationRun) -> float:
    return float(run.metrics.task_success) if run.metrics.quality_score is None else run.metrics.quality_score


def _conclusion(samples: int) -> str:
    return "DESCRIPTIVE" if samples >= 3 else "INSUFFICIENT_EVIDENCE"


def _mean(values: Sequence[float]) -> float:
    return statistics.fmean(values)


def build_strategy_evaluation_result(
    experiment: StrategyEvaluationExperiment,
    runs: Sequence[StrategyEvaluationRun],
) -> StrategyEvaluationResult:
    """Build descriptive paired effects without installing a global winner."""

    exact = tuple(runs)
    if not exact:
        raise StrategyContractError("strategy experiment has no runs")
    if any(item.experiment.canonical_digest != experiment.canonical_digest for item in exact):
        raise StrategyContractError("strategy run differs from exact experiment")
    by_cell = {
        (item.candidate_id, item.strategy_digest, item.task.canonical_digest, item.repetition): item
        for item in exact
    }
    if len(by_cell) != len(exact):
        raise StrategyContractError("strategy runs repeat a cell")
    models = {item.candidate_id: item for item in experiment.models}
    strategies = tuple(experiment.strategies)
    comparisons: list[StrategyPairwiseComparison] = []
    effects: list[StrategyEffectEstimate] = []
    confounder_keys = tuple(experiment.confounders)
    for candidate_id, model in sorted(models.items()):
        for left, right in itertools.combinations(strategies, 2):
            pairs: list[tuple[StrategyEvaluationRun, StrategyEvaluationRun]] = []
            for task in experiment.task_set.tasks:
                for repetition in range(1, experiment.repetitions + 1):
                    left_run = by_cell.get((candidate_id, left.canonical_digest, task.canonical_digest, repetition))
                    right_run = by_cell.get((candidate_id, right.canonical_digest, task.canonical_digest, repetition))
                    if left_run is not None and right_run is not None:
                        pairs.append((left_run, right_run))
            if not pairs:
                continue
            wins = losses = ties = 0
            deltas: list[float] = []
            for left_run, right_run in pairs:
                delta = _score(left_run) - _score(right_run)
                deltas.append(delta)
                if math.isclose(delta, 0.0, rel_tol=1e-12, abs_tol=1e-12):
                    ties += 1
                elif delta > 0:
                    wins += 1
                else:
                    losses += 1
            comparisons.append(
                StrategyPairwiseComparison(
                    experiment.canonical_digest,
                    model.canonical_digest,
                    left.canonical_digest,
                    right.canonical_digest,
                    wins,
                    losses,
                    ties,
                    _conclusion(len(pairs)),
                    confounder_keys,
                )
            )
            effects.append(
                StrategyEffectEstimate(
                    experiment.canonical_digest,
                    StrategyEffectKind.STRATEGY,
                    "quality.score",
                    (model.canonical_digest, left.canonical_digest, right.canonical_digest),
                    len(pairs),
                    _mean(deltas),
                    _conclusion(len(pairs)),
                    {"model": candidate_id, "workload": experiment.workload_profile.profile_id},
                )
            )
    if experiment.matrix_kind is MatrixKind.FACTORIAL:
        for strategy in strategies:
            for left_model, right_model in itertools.combinations(experiment.models, 2):
                deltas = []
                for task in experiment.task_set.tasks:
                    for repetition in range(1, experiment.repetitions + 1):
                        left_run = by_cell.get((left_model.candidate_id, strategy.canonical_digest, task.canonical_digest, repetition))
                        right_run = by_cell.get((right_model.candidate_id, strategy.canonical_digest, task.canonical_digest, repetition))
                        if left_run is not None and right_run is not None:
                            deltas.append(_score(left_run) - _score(right_run))
                if deltas:
                    effects.append(
                        StrategyEffectEstimate(
                            experiment.canonical_digest,
                            StrategyEffectKind.MODEL,
                            "quality.score",
                            (strategy.canonical_digest, left_model.canonical_digest, right_model.canonical_digest),
                            len(deltas),
                            _mean(deltas),
                            _conclusion(len(deltas)),
                            {"strategy": strategy.strategy_id, "workload": experiment.workload_profile.profile_id},
                        )
                    )
        for left_model, right_model in itertools.combinations(experiment.models, 2):
            for left_strategy, right_strategy in itertools.combinations(strategies, 2):
                interactions = []
                for task in experiment.task_set.tasks:
                    for repetition in range(1, experiment.repetitions + 1):
                        cells = (
                            by_cell.get((left_model.candidate_id, left_strategy.canonical_digest, task.canonical_digest, repetition)),
                            by_cell.get((left_model.candidate_id, right_strategy.canonical_digest, task.canonical_digest, repetition)),
                            by_cell.get((right_model.candidate_id, left_strategy.canonical_digest, task.canonical_digest, repetition)),
                            by_cell.get((right_model.candidate_id, right_strategy.canonical_digest, task.canonical_digest, repetition)),
                        )
                        if all(item is not None for item in cells):
                            left_left, left_right, right_left, right_right = cells
                            assert left_left is not None and left_right is not None and right_left is not None and right_right is not None
                            interactions.append(
                                (_score(right_right) - _score(right_left))
                                - (_score(left_right) - _score(left_left))
                            )
                if interactions:
                    effects.append(
                        StrategyEffectEstimate(
                            experiment.canonical_digest,
                            StrategyEffectKind.INTERACTION,
                            "quality.score",
                            (
                                left_model.canonical_digest,
                                right_model.canonical_digest,
                                left_strategy.canonical_digest,
                                right_strategy.canonical_digest,
                            ),
                            len(interactions),
                            _mean(interactions),
                            _conclusion(len(interactions)),
                            {"workload": experiment.workload_profile.profile_id},
                        )
                    )
    return StrategyEvaluationResult(experiment, exact, tuple(comparisons), tuple(effects))


__all__ = [
    "ExecutionStrategy",
    "MatrixKind",
    "PromptArtifact",
    "SkillArtifact",
    "StrategyContractError",
    "StrategyDimension",
    "StrategyEffectEstimate",
    "StrategyEffectKind",
    "StrategyEvaluationExperiment",
    "StrategyEvaluationKnowledgeCandidate",
    "StrategyEvaluationResult",
    "StrategyEvaluationRun",
    "StrategyMetricSet",
    "StrategyPairwiseComparison",
    "StrategyPattern",
    "build_strategy_evaluation_result",
]
