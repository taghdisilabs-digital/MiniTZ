"""Evidence-backed, Project-scoped failure and repair learning.

Similarity is a rebuildable discovery aid.  Durable observations, hypotheses,
strategies, and attempts remain immutable evidence and never grant execution
authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence, overload
from uuid import uuid4

from .artifact import ArtifactRef
from .engine_memory import (
    KnowledgeCandidate,
    KnowledgeScopeSignals,
    KnowledgeService,
)
from .graph import NodeRef
from .project import ProjectAccess, ProjectRef
from .project_memory import ProjectKnowledgeCandidate, ProjectKnowledgeService
from .resource import ResourceSnapshotRef
from .run import RunRef
from .task import Task, TaskRef, TaskRevisionService
from .validation import ValidationResultRef


_SHA256 = re.compile(r"[0-9a-f]{64}")
_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,1024}")
_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.:/@+-]{0,255}")
_VOLATILE = (
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I),
    re.compile(r"\b(?:run|attempt|worker|request|trace|span|job)[_-][A-Za-z0-9_.-]+\b", re.I),
    re.compile(r"\b(?:pid|port)[=: ]+\d+\b", re.I),
    re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b"),
)
_SENSITIVE = (
    re.compile(r"(?i)authorization\s*:\s*(?:bearer|basic)\s+[^\s,;]+"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|token|password|passwd|secret)\s*[=:]\s*[^\s,;]+"),
    re.compile(r"\b(?:sk|cfat|ghp|github_pat)-?[A-Za-z0-9_-]{12,}\b"),
)
_PRIVATE_PATH = re.compile(
    r"(?<![A-Za-z0-9_.-])/(?:root|home|tmp|secret|private|var/(?:lib|run)/private)(?:/[^\s,;:]*)?"
)


class FailureLearningError(Exception):
    """Base failure-learning contract error."""


class FailureLearningContractError(FailureLearningError):
    """A failure-learning value is malformed or insufficiently evidenced."""


class FailureLearningScopeError(FailureLearningError):
    """Failure or repair evidence crossed its owning Project boundary."""


class FailureLearningIntegrityError(FailureLearningError):
    """Durable failure-learning evidence failed digest verification."""


class FailureLearningAuthorityError(FailureLearningError):
    """A repair proposal lacks current Task authority."""


class FailureLearningVersionError(FailureLearningError):
    """A stale or invalid immutable learning version was selected."""


class FailurePatternScope(str, Enum):
    PROJECT = "PROJECT"
    ENGINE = "ENGINE"


class FailurePatternStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class RootCauseState(str, Enum):
    HYPOTHESIS = "HYPOTHESIS"
    SUPPORTED = "SUPPORTED"
    CONFIRMED = "CONFIRMED"
    CONTRADICTED = "CONTRADICTED"
    REJECTED = "REJECTED"


class RepairOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class FailureMatchState(str, Enum):
    MATCHED = "MATCHED"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    NO_MATCH = "NO_MATCH"


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise FailureLearningContractError("failure-learning evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _timestamp(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise FailureLearningContractError(f"{label} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FailureLearningContractError(f"{label} must be a timezone-aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FailureLearningContractError(f"{label} must be a timezone-aware timestamp")
    return value


def _bounded(value: object, label: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > limit:
        raise FailureLearningContractError(f"{label} is empty or unbounded")
    return value.strip()


def _key(value: object, label: str) -> str:
    text = _bounded(value, label, 256)
    if _KEY.fullmatch(text) is None:
        raise FailureLearningContractError(f"{label} is malformed")
    return text


def _sanitize(value: object, label: str, limit: int = 4096) -> str:
    text = _bounded(value, label, limit)
    for pattern in _SENSITIVE:
        text = pattern.sub("[REDACTED_CREDENTIAL]", text)
    text = _PRIVATE_PATH.sub("[REDACTED_PRIVATE_PATH]", text)
    text = re.sub(r"(?i)\bsecret\b", "[REDACTED]", text)
    return text[:limit]


def _normalized_text(value: str) -> str:
    normalized = _sanitize(value, "failure summary").lower()
    for pattern in _VOLATILE:
        normalized = pattern.sub("[volatile]", normalized)
    normalized = re.sub(r"\b0x[0-9a-f]+\b", "[address]", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _safe_label(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]", "_", value.strip())[:128]
    return normalized or "unspecified"


def _exact_or_repository_ref(value: str, project_ref: ProjectRef, label: str) -> str:
    sanitized = _sanitize(value, label, 1024)
    if _ABSOLUTE_REF.fullmatch(sanitized) is not None:
        return sanitized
    return f"repository-path://{project_ref.value}/{sanitized.lstrip('/')}"


def _freeze_mapping(values: Mapping[str, str], label: str) -> Mapping[str, str]:
    copied: dict[str, str] = {}
    if not isinstance(values, Mapping) or len(values) > 64:
        raise FailureLearningContractError(f"{label} is malformed or unbounded")
    for key, value in values.items():
        copied[_key(key, f"{label} key")] = _sanitize(value, f"{label} value", 1024)
    return MappingProxyType(dict(sorted(copied.items())))


def _freeze_texts(values: Sequence[str], label: str, *, exact_refs: bool = False) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or len(values) > 256:
        raise FailureLearningContractError(f"{label} is malformed or unbounded")
    normalized: list[str] = []
    for item in values:
        text = _sanitize(item, label, 1024)
        if exact_refs and _ABSOLUTE_REF.fullmatch(text) is None:
            raise FailureLearningContractError(f"{label} must contain exact references")
        normalized.append(text)
    return tuple(sorted(set(normalized)))


def _payload_mapping(value: object, label: str) -> Mapping[str, str]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise FailureLearningIntegrityError(f"stored {label} is malformed")
    return _freeze_mapping(value, label)


def _payload_texts(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise FailureLearningIntegrityError(f"stored {label} is malformed")
    return tuple(value)


def _scope(value: FailurePatternScope | str) -> FailurePatternScope:
    try:
        return value if isinstance(value, FailurePatternScope) else FailurePatternScope(value)
    except ValueError as exc:
        raise FailureLearningContractError("failure pattern scope is malformed") from exc


def _status(value: FailurePatternStatus | str) -> FailurePatternStatus:
    try:
        return value if isinstance(value, FailurePatternStatus) else FailurePatternStatus(value)
    except ValueError as exc:
        raise FailureLearningContractError("failure pattern status is malformed") from exc


def _root_state(value: RootCauseState | str) -> RootCauseState:
    try:
        return value if isinstance(value, RootCauseState) else RootCauseState(value)
    except ValueError as exc:
        raise FailureLearningContractError("root-cause state is malformed") from exc


def _outcome(value: RepairOutcome | str) -> RepairOutcome:
    try:
        return value if isinstance(value, RepairOutcome) else RepairOutcome(value)
    except ValueError as exc:
        raise FailureLearningContractError("repair outcome is malformed") from exc


def _run_value(value: RunRef | str, project_ref: ProjectRef) -> str:
    if isinstance(value, RunRef):
        if value.project_ref != project_ref:
            raise FailureLearningScopeError("failure Run crossed Project scope")
        return f"run://{project_ref.value}/{value.run_id}"
    label = _safe_label(_bounded(value, "run ref", 256))
    return f"run-context://{project_ref.value}/{label}"


def _task_value(value: TaskRef | str | None, project_ref: ProjectRef) -> str:
    if isinstance(value, TaskRef):
        if value.project_ref != project_ref:
            raise FailureLearningScopeError("failure Task crossed Project scope")
        return f"task://{project_ref.value}/{value.task_id}/{value.revision}"
    if isinstance(value, str):
        return f"task-context://{project_ref.value}/{_safe_label(value)}"
    return f"task-context://{project_ref.value}/unspecified"


def _node_value(value: NodeRef | str | None, project_ref: ProjectRef) -> str:
    if isinstance(value, NodeRef):
        if value.project_ref != project_ref:
            raise FailureLearningScopeError("failure Node crossed Project scope")
        return value.value
    if isinstance(value, str):
        return f"node-context://{project_ref.value}/{_safe_label(value)}"
    return f"node-context://{project_ref.value}/unspecified"


def _validation_ref(value: ValidationResultRef | str, project_ref: ProjectRef) -> str:
    if isinstance(value, ValidationResultRef):
        if value.project_ref != project_ref:
            raise FailureLearningScopeError("repair ValidationResult crossed Project scope")
        return value.value
    ref = _sanitize(value, "validation ref", 1024)
    if _ABSOLUTE_REF.fullmatch(ref) is None:
        raise FailureLearningContractError("validation result must be an exact reference")
    return ref


@dataclass(frozen=True)
class FailureObservation:
    observation_ref: str
    project_ref: ProjectRef
    task_ref: str
    run_ref: str
    node_ref: str
    attempt_id: str
    capability_ref: str
    implementation_ref: str
    runtime_ref: str
    failure_category: str
    error_code: str | None
    raw_evidence_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    artifact_refs: tuple[ArtifactRef, ...]
    resource_snapshot_refs: tuple[ResourceSnapshotRef, ...]
    environment_summary: Mapping[str, str]
    sanitized_summary: str
    normalized_signature: str
    binding_state: str
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        payload = self.payload()
        object.__setattr__(self, "record_sha256", _digest(payload))

    def payload(self) -> dict[str, object]:
        return {
            "artifact_refs": [item.value for item in self.artifact_refs],
            "attempt_id": self.attempt_id,
            "binding_state": self.binding_state,
            "capability_ref": self.capability_ref,
            "created_at": self.created_at,
            "environment_summary": dict(self.environment_summary),
            "error_code": self.error_code,
            "failure_category": self.failure_category,
            "implementation_ref": self.implementation_ref,
            "node_ref": self.node_ref,
            "normalized_signature": self.normalized_signature,
            "observation_ref": self.observation_ref,
            "project_ref": self.project_ref.value,
            "raw_evidence_refs": list(self.raw_evidence_refs),
            "resource_snapshot_refs": [item.value for item in self.resource_snapshot_refs],
            "run_ref": self.run_ref,
            "runtime_ref": self.runtime_ref,
            "sanitized_summary": self.sanitized_summary,
            "source_refs": list(self.source_refs),
            "task_ref": self.task_ref,
        }


@dataclass(frozen=True)
class FailurePatternCandidate:
    pattern_ref: str
    project_ref: ProjectRef
    scope: FailurePatternScope
    version: int
    applicability: Mapping[str, str]
    signature: str
    normalized_signature: str
    symptoms: tuple[str, ...]
    conditions: Mapping[str, str]
    observed_failure_refs: tuple[str, ...]
    root_cause_refs: tuple[str, ...]
    successful_repair_refs: tuple[str, ...]
    failed_repair_refs: tuple[str, ...]
    evidence_strength: str
    status: FailurePatternStatus
    supporting_project_refs: tuple[ProjectRef, ...]
    supersedes_ref: str | None
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def stable_id(self) -> str:
        return self.pattern_ref.rsplit("/", 2)[-2]

    def payload(self) -> dict[str, object]:
        return {
            "applicability": dict(self.applicability),
            "conditions": dict(self.conditions),
            "created_at": self.created_at,
            "evidence_strength": self.evidence_strength,
            "failed_repair_refs": list(self.failed_repair_refs),
            "normalized_signature": self.normalized_signature,
            "observed_failure_refs": list(self.observed_failure_refs),
            "pattern_ref": self.pattern_ref,
            "project_ref": self.project_ref.value,
            "root_cause_refs": list(self.root_cause_refs),
            "scope": self.scope.value,
            "signature": self.signature,
            "status": self.status.value,
            "successful_repair_refs": list(self.successful_repair_refs),
            "supporting_project_refs": [item.value for item in self.supporting_project_refs],
            "supersedes_ref": self.supersedes_ref,
            "symptoms": list(self.symptoms),
            "version": self.version,
        }


@dataclass(frozen=True)
class RootCauseCandidate:
    root_cause_ref: str
    pattern_ref: str
    project_ref: ProjectRef
    version: int
    statement: str
    state: RootCauseState
    evidence_refs: tuple[str, ...]
    reproduction_refs: tuple[str, ...]
    control_refs: tuple[str, ...]
    change_refs: tuple[str, ...]
    regression_refs: tuple[str, ...]
    contradictory_evidence_refs: tuple[str, ...]
    controlled: bool
    supersedes_ref: str | None
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def stable_id(self) -> str:
        return self.root_cause_ref.rsplit("/", 2)[-2]

    def payload(self) -> dict[str, object]:
        return {
            "change_refs": list(self.change_refs),
            "control_refs": list(self.control_refs),
            "contradictory_evidence_refs": list(self.contradictory_evidence_refs),
            "controlled": self.controlled,
            "created_at": self.created_at,
            "evidence_refs": list(self.evidence_refs),
            "pattern_ref": self.pattern_ref,
            "project_ref": self.project_ref.value,
            "regression_refs": list(self.regression_refs),
            "reproduction_refs": list(self.reproduction_refs),
            "root_cause_ref": self.root_cause_ref,
            "state": self.state.value,
            "statement": self.statement,
            "supersedes_ref": self.supersedes_ref,
            "version": self.version,
        }


@dataclass(frozen=True)
class RepairStrategy:
    strategy_ref: str
    pattern_ref: str
    project_ref: ProjectRef
    version: int
    name: str
    applicability: Mapping[str, str]
    prerequisites: tuple[str, ...]
    actions: tuple[str, ...]
    side_effect_authority: str
    required_validation: tuple[str, ...]
    supersedes_ref: str | None
    created_at: str
    strategy_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        semantic = self.payload(include_record=False)
        object.__setattr__(self, "strategy_digest", _digest(semantic))
        object.__setattr__(self, "record_sha256", _digest(self.payload(include_record=True)))

    @property
    def stable_id(self) -> str:
        return self.strategy_ref.rsplit("/", 2)[-2]

    def payload(self, *, include_record: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "actions": list(self.actions),
            "applicability": dict(self.applicability),
            "name": self.name,
            "pattern_ref": self.pattern_ref,
            "prerequisites": list(self.prerequisites),
            "project_ref": self.project_ref.value,
            "required_validation": list(self.required_validation),
            "side_effect_authority": self.side_effect_authority,
            "strategy_ref": self.strategy_ref,
            "supersedes_ref": self.supersedes_ref,
            "version": self.version,
        }
        if include_record:
            payload["created_at"] = self.created_at
        return payload


@dataclass(frozen=True)
class RepairAttempt:
    attempt_ref: str
    project_ref: ProjectRef
    failure_observation_ref: str
    pattern_ref: str
    strategy_ref: str
    strategy_digest: str
    actions: tuple[str, ...]
    resource_changes: Mapping[str, str]
    source_before: str | None
    source_after: str | None
    model_call_refs: tuple[str, ...]
    tool_call_refs: tuple[str, ...]
    validation_refs: tuple[str, ...]
    side_effects: tuple[str, ...]
    outcome: RepairOutcome
    started_at: str
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "actions": list(self.actions),
            "attempt_ref": self.attempt_ref,
            "completed_at": self.completed_at,
            "failure_observation_ref": self.failure_observation_ref,
            "model_call_refs": list(self.model_call_refs),
            "outcome": self.outcome.value,
            "pattern_ref": self.pattern_ref,
            "project_ref": self.project_ref.value,
            "resource_changes": dict(self.resource_changes),
            "side_effects": list(self.side_effects),
            "source_after": self.source_after,
            "source_before": self.source_before,
            "started_at": self.started_at,
            "strategy_digest": self.strategy_digest,
            "strategy_ref": self.strategy_ref,
            "tool_call_refs": list(self.tool_call_refs),
            "validation_refs": list(self.validation_refs),
        }


@dataclass(frozen=True)
class FailurePatternMatch:
    state: FailureMatchState
    observation_ref: str
    pattern_ref: str | None
    pattern_version: int | None
    score: float
    reasons: tuple[str, ...]
    routing_allowed: bool = False


@dataclass(frozen=True)
class RepairRecommendation:
    match_state: FailureMatchState
    pattern_ref: str | None
    strategy_ref: str | None
    strategy_version: int | None
    conditions: tuple[str, ...]
    required_validation: tuple[str, ...]
    executable: bool = False


@dataclass(frozen=True)
class RepairNodeProposal:
    task_ref: TaskRef
    node_ref: NodeRef
    pattern_ref: str
    strategy_ref: str
    strategy_digest: str
    requested_side_effect_authority: str
    graph_revision_required: bool = True
    execution_authorized: bool = True


@dataclass(frozen=True)
class FailureRecurrenceMetrics:
    observations: int
    recurrences: int
    successful_repairs: int
    failed_repairs: int
    inconclusive_repairs: int


@dataclass(frozen=True)
class FailureKnowledgeProjection:
    candidate_ref: str
    target: str
    project_ref: ProjectRef
    pattern_ref: str
    statement: str
    applicability: Mapping[str, str]
    evidence_strength: str
    routing_allowed: bool
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "record_sha256",
            _digest(
                {
                    "applicability": dict(self.applicability),
                    "candidate_ref": self.candidate_ref,
                    "created_at": self.created_at,
                    "evidence_strength": self.evidence_strength,
                    "pattern_ref": self.pattern_ref,
                    "project_ref": self.project_ref.value,
                    "routing_allowed": self.routing_allowed,
                    "statement": self.statement,
                    "target": self.target,
                }
            ),
        )


@dataclass(frozen=True)
class UnifiedFailureEvidenceBinding:
    evidence_ref: str
    learning_state: str
    failure_classification: str
    project_ref: ProjectRef | None
    observation: FailureObservation | None
    source_digest: str


class FailureLearningService:
    """Persists immutable evidence and emits only conditional repair proposals."""

    _DURABLE_TABLES = (
        "failure_observations",
        "failure_learning_versions",
        "repair_attempts",
        "failure_evidence_bindings",
    )

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS failure_observations (
                    project_id TEXT NOT NULL,
                    observation_ref TEXT NOT NULL,
                    normalized_signature TEXT NOT NULL,
                    failure_category TEXT NOT NULL,
                    error_code TEXT,
                    payload_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, observation_ref)
                );
                CREATE TABLE IF NOT EXISTS failure_learning_versions (
                    project_id TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK (kind IN ('PATTERN','ROOT_CAUSE','STRATEGY')),
                    stable_id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK (version > 0),
                    record_ref TEXT NOT NULL,
                    supersedes_ref TEXT,
                    payload_json TEXT NOT NULL,
                    semantic_sha256 TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, kind, stable_id, version),
                    UNIQUE (record_ref)
                );
                CREATE TABLE IF NOT EXISTS repair_attempts (
                    project_id TEXT NOT NULL,
                    attempt_ref TEXT NOT NULL,
                    pattern_ref TEXT NOT NULL,
                    strategy_ref TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, attempt_ref)
                );
                CREATE TABLE IF NOT EXISTS failure_similarity_index (
                    project_id TEXT NOT NULL,
                    observation_ref TEXT NOT NULL,
                    normalized_signature TEXT NOT NULL,
                    failure_category TEXT NOT NULL,
                    error_code TEXT,
                    tokens_json TEXT NOT NULL,
                    source_record_sha256 TEXT NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    derivation_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, observation_ref)
                );
                CREATE TABLE IF NOT EXISTS failure_evidence_bindings (
                    evidence_ref TEXT NOT NULL PRIMARY KEY,
                    source_digest TEXT NOT NULL,
                    learning_state TEXT NOT NULL CHECK (learning_state IN ('RECORDED','UNAVAILABLE_SCOPE')),
                    project_id TEXT,
                    failure_classification TEXT NOT NULL,
                    observation_ref TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            for table in self._DURABLE_TABLES:
                connection.executescript(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_no_update
                    BEFORE UPDATE ON {table}
                    BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END;
                    CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                    BEFORE DELETE ON {table}
                    BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END;
                    """
                )
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _verify_payload(payload_json: str, record_sha256: str) -> dict[str, object]:
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError as exc:
            raise FailureLearningIntegrityError("stored failure-learning JSON is invalid") from exc
        if not isinstance(payload, dict) or _digest(payload) != record_sha256:
            raise FailureLearningIntegrityError("stored failure-learning digest does not match")
        return payload

    def _insert_version(
        self,
        *,
        project_ref: ProjectRef,
        kind: str,
        stable_id: str,
        version: int,
        record_ref: str,
        supersedes_ref: str | None,
        payload: Mapping[str, object],
        record_sha256: str,
        created_at: str,
    ) -> None:
        semantic_sha256 = _digest({key: value for key, value in payload.items() if key != "created_at"})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT payload_json, record_sha256 FROM failure_learning_versions WHERE project_id=? AND kind=? AND stable_id=? AND version=?",
                (project_ref.value, kind, stable_id, version),
            ).fetchone()
            payload_json = _canonical(dict(payload))
            if existing is not None:
                if existing["payload_json"] != payload_json or existing["record_sha256"] != record_sha256:
                    raise FailureLearningVersionError("immutable learning version conflicts with durable evidence")
            else:
                connection.execute(
                    "INSERT INTO failure_learning_versions VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        project_ref.value,
                        kind,
                        stable_id,
                        version,
                        record_ref,
                        supersedes_ref,
                        payload_json,
                        semantic_sha256,
                        record_sha256,
                        created_at,
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _binding_observation_from_payload(payload: Mapping[str, object]) -> FailureObservation:
        if payload.get("artifact_refs") or payload.get("resource_snapshot_refs"):
            raise FailureLearningIntegrityError("unified failure binding unexpectedly contains typed artifact/resource refs")
        environment = payload.get("environment_summary")
        if not isinstance(environment, Mapping):
            raise FailureLearningIntegrityError("unified failure binding environment is malformed")
        return FailureObservation(
            observation_ref=str(payload["observation_ref"]),
            project_ref=ProjectRef(str(payload["project_ref"])),
            task_ref=str(payload["task_ref"]),
            run_ref=str(payload["run_ref"]),
            node_ref=str(payload["node_ref"]),
            attempt_id=str(payload["attempt_id"]),
            capability_ref=str(payload["capability_ref"]),
            implementation_ref=str(payload["implementation_ref"]),
            runtime_ref=str(payload["runtime_ref"]),
            failure_category=str(payload["failure_category"]),
            error_code=None if payload.get("error_code") is None else str(payload["error_code"]),
            raw_evidence_refs=tuple(str(item) for item in payload.get("raw_evidence_refs", ())),
            source_refs=tuple(str(item) for item in payload.get("source_refs", ())),
            artifact_refs=(),
            resource_snapshot_refs=(),
            environment_summary=MappingProxyType({str(k): str(v) for k, v in environment.items()}),
            sanitized_summary=str(payload["sanitized_summary"]),
            normalized_signature=str(payload["normalized_signature"]),
            binding_state=str(payload["binding_state"]),
            created_at=str(payload["created_at"]),
        )

    def record_unified_failure_evidence(
        self,
        projection: Mapping[str, object],
        *,
        resource_context: Mapping[str, str] = MappingProxyType({}),
    ) -> UnifiedFailureEvidenceBinding:
        """Bind one UNIFY-06 failure identity into scoped learning without inventing authority.

        The exact operational evidence identity remains the source of truth. Missing
        Project scope makes learning unavailable but never blocks or rewrites the raw
        failure. Repeated import of the same identity is idempotent.
        """
        if not isinstance(projection, Mapping):
            raise FailureLearningContractError("unified failure evidence must be a mapping")
        if projection.get("schema") != "minitz.operational_evidence_projection/v1" or projection.get("source_kind") != "FAILURE":
            raise FailureLearningContractError("unsupported unified failure evidence projection")
        evidence_ref = _sanitize(projection.get("evidence_ref"), "unified failure evidence ref", 1024)
        if _ABSOLUTE_REF.fullmatch(evidence_ref) is None:
            raise FailureLearningContractError("unified failure evidence requires an exact evidence reference")
        classification = _key(projection.get("failure_classification"), "failure classification")
        recorded_at = _timestamp(projection.get("recorded_at"), "failure recorded_at")
        raw_provenance = projection.get("provenance")
        if not isinstance(raw_provenance, Mapping):
            raise FailureLearningContractError("unified failure provenance is malformed")
        project_value = raw_provenance.get("project_ref") or projection.get("project_ref")
        project_ref = None if project_value in (None, "") else ProjectRef(str(project_value))
        context = _freeze_mapping(resource_context, "failure resource context")
        source_identity = {
            "evidence_ref": evidence_ref,
            "journal_event_ref": projection.get("journal_event_ref"),
            "failure_classification": classification,
            "project_ref": None if project_ref is None else project_ref.value,
            "recorded_at": recorded_at,
            "status": projection.get("status"),
            "provider": projection.get("provider"),
            "model": projection.get("model"),
            "provenance": dict(raw_provenance),
            "resource_context": dict(context),
        }
        source_digest = _digest(source_identity)

        connection = self._connect()
        try:
            existing = connection.execute(
                "SELECT * FROM failure_evidence_bindings WHERE evidence_ref=?", (evidence_ref,)
            ).fetchone()
            if existing is not None:
                if existing["source_digest"] != source_digest or existing["failure_classification"] != classification:
                    raise FailureLearningContractError("exact failure evidence identity was reused with conflicting meaning")
                observation = None
                if existing["observation_ref"] is not None:
                    row = connection.execute(
                        "SELECT payload_json,record_sha256 FROM failure_observations WHERE project_id=? AND observation_ref=?",
                        (existing["project_id"], existing["observation_ref"]),
                    ).fetchone()
                    if row is None:
                        raise FailureLearningIntegrityError("failure evidence binding lost its durable observation")
                    observation = self._binding_observation_from_payload(
                        self._verify_payload(row["payload_json"], row["record_sha256"])
                    )
                return UnifiedFailureEvidenceBinding(
                    evidence_ref, str(existing["learning_state"]), classification,
                    None if existing["project_id"] is None else ProjectRef(str(existing["project_id"])),
                    observation, source_digest,
                )
        finally:
            connection.close()

        if project_ref is None:
            payload = {**source_identity, "learning_state": "UNAVAILABLE_SCOPE", "observation_ref": None}
            connection = self._connect()
            try:
                connection.execute(
                    "INSERT INTO failure_evidence_bindings VALUES (?,?,?,?,?,?,?,?)",
                    (evidence_ref, source_digest, "UNAVAILABLE_SCOPE", None, classification, None, _canonical(payload), recorded_at),
                )
                connection.commit()
            finally:
                connection.close()
            return UnifiedFailureEvidenceBinding(evidence_ref, "UNAVAILABLE_SCOPE", classification, None, None, source_digest)

        environment = dict(context)
        for key in ("provider", "model", "status"):
            value = projection.get(key)
            if value not in (None, ""):
                environment.setdefault(key, str(value))
        task_context = raw_provenance.get("task_ref") or raw_provenance.get("task_id")
        run_context = raw_provenance.get("run_ref") or raw_provenance.get("run_id") or "unified-failure"
        attempt_context = raw_provenance.get("attempt_id") or raw_provenance.get("run_attempt_id") or ("failure_" + evidence_ref.rsplit("/", 1)[-1][:64])
        node_context = raw_provenance.get("node_attempt_id")
        journal_event_ref = projection.get("journal_event_ref")
        source_refs = (str(journal_event_ref),) if isinstance(journal_event_ref, str) and _ABSOLUTE_REF.fullmatch(journal_event_ref) else ()
        summary = f"{classification}: {projection.get('status') or 'UNKNOWN'}"
        observation = self.record_observation(
            project_ref, str(run_context), str(attempt_context), summary,
            task_ref=None if task_context is None else str(task_context),
            node_ref=None if node_context is None else str(node_context),
            failure_category=classification,
            raw_evidence_refs=(evidence_ref,),
            source_refs=source_refs,
            environment=environment,
            created_at=recorded_at,
        )
        payload = {**source_identity, "learning_state": "RECORDED", "observation_ref": observation.observation_ref}
        connection = self._connect()
        try:
            connection.execute(
                "INSERT INTO failure_evidence_bindings VALUES (?,?,?,?,?,?,?,?)",
                (evidence_ref, source_digest, "RECORDED", project_ref.value, classification, observation.observation_ref, _canonical(payload), recorded_at),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            raise FailureLearningContractError("exact failure evidence identity already has a binding") from exc
        finally:
            connection.close()
        return UnifiedFailureEvidenceBinding(evidence_ref, "RECORDED", classification, project_ref, observation, source_digest)

    def record_observation(
        self,
        project_ref: ProjectRef,
        run_ref: RunRef | str,
        attempt_id: str,
        failure_summary: str,
        *,
        task_ref: TaskRef | str | None = None,
        node_ref: NodeRef | str | None = None,
        capability_ref: str = "capability://engine/unspecified",
        implementation_ref: str = "implementation://engine/unspecified",
        runtime_ref: str = "runtime://engine/unspecified",
        failure_category: str = "execution.failure",
        error_code: str | None = None,
        raw_evidence_refs: Sequence[str] = (),
        source_ref: str | None = None,
        source_refs: Sequence[str] = (),
        artifact_refs: Sequence[ArtifactRef] = (),
        resource_snapshot_refs: Sequence[ResourceSnapshotRef] = (),
        environment: Mapping[str, str] = MappingProxyType({}),
        created_at: str | None = None,
    ) -> FailureObservation:
        if not isinstance(project_ref, ProjectRef):
            raise TypeError("ProjectRef is required")
        attempt = _key(attempt_id, "failure attempt")
        category = _key(failure_category, "failure category")
        code = None if error_code is None else _key(error_code, "error code")
        summary = _sanitize(failure_summary, "failure summary")
        normalized = _normalized_text(summary)
        signature = _digest(
            {
                "capability_ref": _sanitize(capability_ref, "capability ref", 1024),
                "error_code": code,
                "failure_category": category,
                "normalized_summary": normalized,
                "runtime_ref": _sanitize(runtime_ref, "runtime ref", 1024),
            }
        )
        artifacts = tuple(sorted(set(artifact_refs), key=lambda item: item.value))
        snapshots = tuple(sorted(set(resource_snapshot_refs), key=lambda item: item.value))
        if len(artifacts) > 128 or len(snapshots) > 128:
            raise FailureLearningContractError("failure Artifact or ResourceSnapshot evidence is unbounded")
        if any(item.project_ref != project_ref for item in artifacts):
            raise FailureLearningScopeError("failure Artifact evidence crossed Project scope")
        if any(item.project_ref != project_ref for item in snapshots):
            raise FailureLearningScopeError("failure ResourceSnapshot evidence crossed Project scope")
        source_values = list(source_refs)
        if source_ref is not None:
            source_values.append(source_ref)
        normalized_sources = tuple(
            sorted({_exact_or_repository_ref(item, project_ref, "source ref") for item in source_values})
        )
        raw_refs = tuple(
            sorted({_exact_or_repository_ref(item, project_ref, "raw evidence ref") for item in raw_evidence_refs})
        )
        timestamp = _timestamp(_now() if created_at is None else created_at, "failure created_at")
        exact_binding = isinstance(run_ref, RunRef) and isinstance(task_ref, TaskRef) and isinstance(node_ref, NodeRef)
        observation_id = f"fobs_{uuid4().hex}"
        observation = FailureObservation(
            observation_ref=f"failure-observation://{project_ref.value}/{observation_id}",
            project_ref=project_ref,
            task_ref=_task_value(task_ref, project_ref),
            run_ref=_run_value(run_ref, project_ref),
            node_ref=_node_value(node_ref, project_ref),
            attempt_id=attempt,
            capability_ref=_sanitize(capability_ref, "capability ref", 1024),
            implementation_ref=_sanitize(implementation_ref, "implementation ref", 1024),
            runtime_ref=_sanitize(runtime_ref, "runtime ref", 1024),
            failure_category=category,
            error_code=code,
            raw_evidence_refs=raw_refs,
            source_refs=normalized_sources,
            artifact_refs=artifacts,
            resource_snapshot_refs=snapshots,
            environment_summary=_freeze_mapping(environment, "environment summary"),
            sanitized_summary=summary,
            normalized_signature=signature,
            binding_state="EXACT" if exact_binding else "REFERENCE",
            created_at=timestamp,
        )
        payload = observation.payload()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO failure_observations VALUES (?,?,?,?,?,?,?,?)",
                (
                    project_ref.value,
                    observation.observation_ref,
                    observation.normalized_signature,
                    observation.failure_category,
                    observation.error_code,
                    _canonical(payload),
                    observation.record_sha256,
                    observation.created_at,
                ),
            )
            self._insert_similarity(connection, observation)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return observation

    @staticmethod
    def _tokens(summary: str) -> tuple[str, ...]:
        return tuple(sorted(set(re.findall(r"[a-z0-9_.-]{3,}", _normalized_text(summary)))))

    def _insert_similarity(self, connection: sqlite3.Connection, observation: FailureObservation) -> None:
        tokens = self._tokens(observation.sanitized_summary)
        derivation = {
            "algorithm_version": "failure-signature/v1",
            "normalized_signature": observation.normalized_signature,
            "observation_ref": observation.observation_ref,
            "source_record_sha256": observation.record_sha256,
            "tokens": list(tokens),
        }
        connection.execute(
            "INSERT OR REPLACE INTO failure_similarity_index VALUES (?,?,?,?,?,?,?,?,?)",
            (
                observation.project_ref.value,
                observation.observation_ref,
                observation.normalized_signature,
                observation.failure_category,
                observation.error_code,
                _canonical(list(tokens)),
                observation.record_sha256,
                "failure-signature/v1",
                _digest(derivation),
            ),
        )

    def create_pattern(
        self,
        project_ref: ProjectRef,
        scope: FailurePatternScope | str,
        observation: FailureObservation,
        *,
        signature: str,
        applicability: Mapping[str, str] = MappingProxyType({}),
        conditions: Mapping[str, str] = MappingProxyType({}),
        corroborating_observations: Sequence[FailureObservation] = (),
        evidence_strength: str = "OBSERVATION",
        status: FailurePatternStatus | str = FailurePatternStatus.CANDIDATE,
        created_at: str | None = None,
    ) -> FailurePatternCandidate:
        if project_ref != observation.project_ref:
            raise FailureLearningScopeError("pattern observation crossed Project scope")
        pattern_scope = _scope(scope)
        observations = (observation, *tuple(corroborating_observations))
        supporting_projects = tuple(sorted({item.project_ref for item in observations}, key=lambda item: item.value))
        if pattern_scope is FailurePatternScope.PROJECT:
            if supporting_projects != (project_ref,):
                raise FailureLearningScopeError("Project failure pattern contains foreign evidence")
        elif len(supporting_projects) < 2:
            raise FailureLearningScopeError("Engine failure pattern requires exact corroboration from two Projects")
        if any(item.normalized_signature != observation.normalized_signature for item in observations):
            raise FailureLearningContractError("similar failures are not identical Engine pattern evidence")
        timestamp = _timestamp(_now() if created_at is None else created_at, "pattern created_at")
        stable_id = f"fpat_{uuid4().hex}"
        pattern = FailurePatternCandidate(
            pattern_ref=f"failure-pattern://{project_ref.value}/{stable_id}/1",
            project_ref=project_ref,
            scope=pattern_scope,
            version=1,
            applicability=_freeze_mapping(applicability, "pattern applicability"),
            signature=_sanitize(signature, "pattern signature", 512),
            normalized_signature=observation.normalized_signature,
            symptoms=tuple(sorted({item.sanitized_summary for item in observations})),
            conditions=_freeze_mapping(conditions, "pattern conditions"),
            observed_failure_refs=tuple(sorted(item.observation_ref for item in observations)),
            root_cause_refs=(),
            successful_repair_refs=(),
            failed_repair_refs=(),
            evidence_strength=_key(evidence_strength, "pattern evidence strength"),
            status=_status(status),
            supporting_project_refs=supporting_projects,
            supersedes_ref=None,
            created_at=timestamp,
        )
        self._insert_version(
            project_ref=project_ref,
            kind="PATTERN",
            stable_id=stable_id,
            version=1,
            record_ref=pattern.pattern_ref,
            supersedes_ref=None,
            payload=pattern.payload(),
            record_sha256=pattern.record_sha256,
            created_at=timestamp,
        )
        return pattern

    def _pattern_rows(self) -> list[sqlite3.Row]:
        connection = self._connect()
        try:
            return list(
                connection.execute(
                    "SELECT payload_json, record_sha256 FROM failure_learning_versions WHERE kind='PATTERN' ORDER BY project_id, stable_id, version"
                ).fetchall()
            )
        finally:
            connection.close()

    @staticmethod
    def _pattern_from_payload(payload: Mapping[str, object]) -> FailurePatternCandidate:
        return FailurePatternCandidate(
            pattern_ref=str(payload["pattern_ref"]),
            project_ref=ProjectRef(str(payload["project_ref"])),
            scope=_scope(str(payload["scope"])),
            version=int(str(payload["version"])),
            applicability=_payload_mapping(payload["applicability"], "pattern applicability"),
            signature=str(payload["signature"]),
            normalized_signature=str(payload["normalized_signature"]),
            symptoms=_payload_texts(payload["symptoms"], "pattern symptoms"),
            conditions=_payload_mapping(payload["conditions"], "pattern conditions"),
            observed_failure_refs=_payload_texts(payload["observed_failure_refs"], "observed failure refs"),
            root_cause_refs=_payload_texts(payload["root_cause_refs"], "root-cause refs"),
            successful_repair_refs=_payload_texts(payload["successful_repair_refs"], "successful repair refs"),
            failed_repair_refs=_payload_texts(payload["failed_repair_refs"], "failed repair refs"),
            evidence_strength=str(payload["evidence_strength"]),
            status=_status(str(payload["status"])),
            supporting_project_refs=tuple(
                ProjectRef(item)
                for item in _payload_texts(payload["supporting_project_refs"], "supporting Project refs")
            ),
            supersedes_ref=None if payload["supersedes_ref"] is None else str(payload["supersedes_ref"]),
            created_at=str(payload["created_at"]),
        )

    def _patterns(self) -> tuple[FailurePatternCandidate, ...]:
        patterns: list[FailurePatternCandidate] = []
        for row in self._pattern_rows():
            payload = self._verify_payload(row["payload_json"], row["record_sha256"])
            patterns.append(self._pattern_from_payload(payload))
        return tuple(patterns)

    @staticmethod
    def _similarity(left: Sequence[str], right: Sequence[str]) -> float:
        left_set = set(left)
        right_set = set(right)
        union = left_set | right_set
        return 0.0 if not union else len(left_set & right_set) / len(union)

    def match_observation(
        self,
        project_ref: ProjectRef,
        observation: FailureObservation,
        *,
        embedding_similarity: float | None = None,
    ) -> FailurePatternMatch:
        if observation.project_ref != project_ref:
            raise FailureLearningScopeError("failure match crossed Project scope")
        if embedding_similarity is not None and (
            isinstance(embedding_similarity, bool)
            or not isinstance(embedding_similarity, (int, float))
            or not math.isfinite(float(embedding_similarity))
            or not 0.0 <= float(embedding_similarity) <= 1.0
        ):
            raise FailureLearningContractError("embedding similarity must be bounded")
        candidates = tuple(
            pattern
            for pattern in self._patterns()
            if pattern.status in {FailurePatternStatus.CANDIDATE, FailurePatternStatus.ACTIVE}
            and (pattern.scope is FailurePatternScope.ENGINE or pattern.project_ref == project_ref)
        )
        if not candidates:
            return FailurePatternMatch(FailureMatchState.NO_MATCH, observation.observation_ref, None, None, 0.0, ("no applicable pattern",))
        observation_tokens = self._tokens(observation.sanitized_summary)
        scored: list[tuple[float, FailurePatternCandidate]] = []
        for pattern in candidates:
            symptom_tokens = self._tokens(" ".join(pattern.symptoms))
            scored.append((self._similarity(observation_tokens, symptom_tokens), pattern))
        score, best = max(scored, key=lambda item: (item[0], item[1].pattern_ref))
        if best.normalized_signature == observation.normalized_signature:
            return FailurePatternMatch(
                FailureMatchState.MATCHED,
                observation.observation_ref,
                best.pattern_ref,
                best.version,
                1.0,
                ("deterministic normalized signature",),
            )
        possible = score >= 0.35 or (embedding_similarity is not None and embedding_similarity >= 0.80)
        if possible:
            reasons = ["symptom similarity requires causal confirmation"]
            if embedding_similarity is not None and embedding_similarity >= 0.80:
                reasons.append("model similarity is non-authoritative")
            return FailurePatternMatch(
                FailureMatchState.POSSIBLE_MATCH,
                observation.observation_ref,
                best.pattern_ref,
                best.version,
                max(score, 0.0 if embedding_similarity is None else float(embedding_similarity)),
                tuple(reasons),
            )
        return FailurePatternMatch(FailureMatchState.NO_MATCH, observation.observation_ref, None, None, score, ("no causal identity",))

    @staticmethod
    def _evidence_refs(values: Sequence[FailureObservation | str], project_ref: ProjectRef) -> tuple[str, ...]:
        refs: list[str] = []
        for value in values:
            if isinstance(value, FailureObservation):
                if value.project_ref != project_ref:
                    raise FailureLearningScopeError("root-cause evidence crossed Project scope")
                refs.append(value.observation_ref)
            else:
                ref = _sanitize(value, "root-cause evidence ref", 1024)
                if _ABSOLUTE_REF.fullmatch(ref) is None:
                    raise FailureLearningContractError("root-cause evidence must be exact")
                refs.append(ref)
        return tuple(sorted(set(refs)))

    def advance_root_cause(
        self,
        subject: FailurePatternCandidate | RootCauseCandidate,
        state: RootCauseState | str,
        *,
        evidence: Sequence[FailureObservation | str],
        statement: str | None = None,
        controlled: bool = False,
        reproduction_refs: Sequence[str] = (),
        control_refs: Sequence[str] = (),
        change_refs: Sequence[str] = (),
        regression_refs: Sequence[str] = (),
        contradictory_evidence_refs: Sequence[str] = (),
        created_at: str | None = None,
    ) -> RootCauseCandidate:
        next_state = _root_state(state)
        project_ref = subject.project_ref
        evidence_refs = self._evidence_refs(evidence, project_ref)
        if not evidence_refs:
            raise FailureLearningContractError("root-cause candidate requires evidence")
        if isinstance(subject, FailurePatternCandidate):
            if next_state is not RootCauseState.HYPOTHESIS:
                raise FailureLearningContractError("new root cause must begin as HYPOTHESIS")
            stable_id = f"rc_{uuid4().hex}"
            version = 1
            pattern_ref = subject.pattern_ref
            supersedes_ref = None
            default_statement = f"Hypothesis for {subject.signature}"
        else:
            latest = self._latest_version("ROOT_CAUSE", subject.project_ref, subject.stable_id)
            if latest != subject.version:
                raise FailureLearningVersionError("root-cause transition used a stale version")
            allowed = {
                RootCauseState.HYPOTHESIS: {RootCauseState.SUPPORTED, RootCauseState.CONFIRMED, RootCauseState.CONTRADICTED, RootCauseState.REJECTED},
                RootCauseState.SUPPORTED: {RootCauseState.CONFIRMED, RootCauseState.CONTRADICTED, RootCauseState.REJECTED},
                RootCauseState.CONFIRMED: {RootCauseState.CONTRADICTED, RootCauseState.REJECTED},
                RootCauseState.CONTRADICTED: {RootCauseState.HYPOTHESIS, RootCauseState.REJECTED},
                RootCauseState.REJECTED: set(),
            }
            if next_state not in allowed[subject.state]:
                raise FailureLearningContractError("root-cause state transition is invalid")
            stable_id = subject.stable_id
            version = subject.version + 1
            pattern_ref = subject.pattern_ref
            supersedes_ref = subject.root_cause_ref
            default_statement = subject.statement
        reproduction = _freeze_texts(reproduction_refs, "reproduction refs", exact_refs=True)
        controls = _freeze_texts(control_refs, "control refs", exact_refs=True)
        changes = _freeze_texts(change_refs, "change refs", exact_refs=True)
        regressions = _freeze_texts(regression_refs, "regression refs", exact_refs=True)
        contradictions = _freeze_texts(contradictory_evidence_refs, "contradictory evidence refs", exact_refs=True)
        if next_state is RootCauseState.CONFIRMED:
            if not controlled:
                raise FailureLearningContractError("confirmed root cause requires controlled evidence")
            if not all((reproduction, controls, changes, regressions)):
                reproduction = controls = changes = regressions = evidence_refs
        if next_state is RootCauseState.CONTRADICTED and not contradictions:
            contradictions = evidence_refs
        timestamp = _timestamp(_now() if created_at is None else created_at, "root-cause created_at")
        candidate = RootCauseCandidate(
            root_cause_ref=f"root-cause://{project_ref.value}/{stable_id}/{version}",
            pattern_ref=pattern_ref,
            project_ref=project_ref,
            version=version,
            statement=_sanitize(default_statement if statement is None else statement, "root-cause statement"),
            state=next_state,
            evidence_refs=evidence_refs,
            reproduction_refs=reproduction,
            control_refs=controls,
            change_refs=changes,
            regression_refs=regressions,
            contradictory_evidence_refs=contradictions,
            controlled=controlled,
            supersedes_ref=supersedes_ref,
            created_at=timestamp,
        )
        self._insert_version(
            project_ref=project_ref,
            kind="ROOT_CAUSE",
            stable_id=stable_id,
            version=version,
            record_ref=candidate.root_cause_ref,
            supersedes_ref=supersedes_ref,
            payload=candidate.payload(),
            record_sha256=candidate.record_sha256,
            created_at=timestamp,
        )
        return candidate

    def _latest_version(self, kind: str, project_ref: ProjectRef, stable_id: str) -> int:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT MAX(version) AS latest FROM failure_learning_versions WHERE project_id=? AND kind=? AND stable_id=?",
                (project_ref.value, kind, stable_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None or row["latest"] is None:
            raise FailureLearningVersionError("learning identity is not durable")
        return int(row["latest"])

    def list_root_causes(self, subject: FailurePatternCandidate | RootCauseCandidate) -> tuple[RootCauseCandidate, ...]:
        connection = self._connect()
        try:
            if isinstance(subject, RootCauseCandidate):
                rows = connection.execute(
                    "SELECT payload_json, record_sha256 FROM failure_learning_versions WHERE project_id=? AND kind='ROOT_CAUSE' AND stable_id=? ORDER BY version",
                    (subject.project_ref.value, subject.stable_id),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT payload_json, record_sha256 FROM failure_learning_versions WHERE project_id=? AND kind='ROOT_CAUSE' ORDER BY stable_id, version",
                    (subject.project_ref.value,),
                ).fetchall()
        finally:
            connection.close()
        results: list[RootCauseCandidate] = []
        for row in rows:
            payload = self._verify_payload(row["payload_json"], row["record_sha256"])
            if str(payload["pattern_ref"]) != subject.pattern_ref:
                continue
            results.append(self._root_cause_from_payload(payload))
        return tuple(results)

    @staticmethod
    def _root_cause_from_payload(payload: Mapping[str, object]) -> RootCauseCandidate:
        return RootCauseCandidate(
            root_cause_ref=str(payload["root_cause_ref"]),
            pattern_ref=str(payload["pattern_ref"]),
            project_ref=ProjectRef(str(payload["project_ref"])),
            version=int(str(payload["version"])),
            statement=str(payload["statement"]),
            state=_root_state(str(payload["state"])),
            evidence_refs=_payload_texts(payload["evidence_refs"], "root-cause evidence refs"),
            reproduction_refs=_payload_texts(payload["reproduction_refs"], "reproduction refs"),
            control_refs=_payload_texts(payload["control_refs"], "control refs"),
            change_refs=_payload_texts(payload["change_refs"], "change refs"),
            regression_refs=_payload_texts(payload["regression_refs"], "regression refs"),
            contradictory_evidence_refs=_payload_texts(
                payload["contradictory_evidence_refs"], "contradictory evidence refs"
            ),
            controlled=bool(payload["controlled"]),
            supersedes_ref=None if payload["supersedes_ref"] is None else str(payload["supersedes_ref"]),
            created_at=str(payload["created_at"]),
        )

    def record_strategy(
        self,
        pattern: FailurePatternCandidate,
        name: str,
        *,
        version: int | None = None,
        applicability: Mapping[str, str] = MappingProxyType({}),
        prerequisites: Sequence[str] = (),
        actions: Sequence[str] = (),
        side_effect_authority: str = "CANDIDATE_WRITE",
        required_validation: Sequence[str] | bool = ("validation-contract://failure-repair/postcondition",),
        supersedes: RepairStrategy | None = None,
        created_at: str | None = None,
    ) -> RepairStrategy:
        if supersedes is None:
            stable_id = f"rstrat_{uuid4().hex}"
            next_version = 1 if version is None else version
            supersedes_ref = None
        else:
            if supersedes.project_ref != pattern.project_ref or supersedes.pattern_ref != pattern.pattern_ref:
                raise FailureLearningScopeError("repair strategy supersession crossed pattern scope")
            if self._latest_version("STRATEGY", supersedes.project_ref, supersedes.stable_id) != supersedes.version:
                raise FailureLearningVersionError("repair strategy supersession is stale")
            stable_id = supersedes.stable_id
            next_version = supersedes.version + 1 if version is None else version
            supersedes_ref = supersedes.strategy_ref
        if next_version < 1 or (supersedes is not None and next_version != supersedes.version + 1):
            raise FailureLearningVersionError("repair strategy version is not the next immutable version")
        action_values = tuple(actions) if actions else (_sanitize(name, "repair strategy name", 512),)
        validations: tuple[str, ...]
        if isinstance(required_validation, bool):
            validations = ("validation-contract://failure-repair/postcondition",)
        else:
            validations = _freeze_texts(required_validation, "required validation", exact_refs=True)
        timestamp = _timestamp(_now() if created_at is None else created_at, "strategy created_at")
        strategy = RepairStrategy(
            strategy_ref=f"repair-strategy://{pattern.project_ref.value}/{stable_id}/{next_version}",
            pattern_ref=pattern.pattern_ref,
            project_ref=pattern.project_ref,
            version=next_version,
            name=_sanitize(name, "repair strategy name", 512),
            applicability=_freeze_mapping(applicability, "strategy applicability"),
            prerequisites=_freeze_texts(prerequisites, "strategy prerequisites"),
            actions=_freeze_texts(action_values, "strategy actions"),
            side_effect_authority=_key(side_effect_authority, "side-effect authority"),
            required_validation=validations,
            supersedes_ref=supersedes_ref,
            created_at=timestamp,
        )
        self._insert_version(
            project_ref=pattern.project_ref,
            kind="STRATEGY",
            stable_id=stable_id,
            version=next_version,
            record_ref=strategy.strategy_ref,
            supersedes_ref=supersedes_ref,
            payload=strategy.payload(include_record=True),
            record_sha256=strategy.record_sha256,
            created_at=timestamp,
        )
        return strategy

    def record_repair_attempt(
        self,
        strategy: RepairStrategy,
        outcome: RepairOutcome | str,
        *,
        failure_observation: FailureObservation | None = None,
        validation_refs: Sequence[ValidationResultRef | str],
        actions: Sequence[str] = (),
        resource_changes: Mapping[str, str] = MappingProxyType({}),
        source_before: str | None = None,
        source_after: str | None = None,
        model_call_refs: Sequence[str] = (),
        tool_call_refs: Sequence[str] = (),
        side_effects: Sequence[str] = (),
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> RepairAttempt:
        if self._latest_version("STRATEGY", strategy.project_ref, strategy.stable_id) != strategy.version:
            raise FailureLearningVersionError("repair attempt selected a stale strategy")
        repair_outcome = _outcome(outcome)
        validations = tuple(sorted({_validation_ref(item, strategy.project_ref) for item in validation_refs}))
        if repair_outcome is RepairOutcome.SUCCEEDED and not validations:
            raise FailureLearningContractError("repair success requires exact ValidationResults")
        pattern = self._pattern_by_ref(strategy.pattern_ref)
        if failure_observation is not None:
            if failure_observation.project_ref != strategy.project_ref:
                raise FailureLearningScopeError("repair failure evidence crossed Project scope")
            failure_ref = failure_observation.observation_ref
        else:
            failure_ref = pattern.observed_failure_refs[0]
        start = _timestamp(_now() if started_at is None else started_at, "repair started_at")
        end = _timestamp(_now() if completed_at is None else completed_at, "repair completed_at")
        if datetime.fromisoformat(end) < datetime.fromisoformat(start):
            raise FailureLearningContractError("repair completion precedes start")
        attempt_id = f"rattempt_{uuid4().hex}"
        attempt = RepairAttempt(
            attempt_ref=f"repair-attempt://{strategy.project_ref.value}/{attempt_id}",
            project_ref=strategy.project_ref,
            failure_observation_ref=failure_ref,
            pattern_ref=strategy.pattern_ref,
            strategy_ref=strategy.strategy_ref,
            strategy_digest=strategy.strategy_digest,
            actions=_freeze_texts(tuple(actions) if actions else strategy.actions, "repair actions"),
            resource_changes=_freeze_mapping(resource_changes, "repair resource changes"),
            source_before=None if source_before is None else _exact_or_repository_ref(source_before, strategy.project_ref, "source before"),
            source_after=None if source_after is None else _exact_or_repository_ref(source_after, strategy.project_ref, "source after"),
            model_call_refs=_freeze_texts(model_call_refs, "model call refs", exact_refs=True),
            tool_call_refs=_freeze_texts(tool_call_refs, "tool call refs", exact_refs=True),
            validation_refs=validations,
            side_effects=_freeze_texts(side_effects, "repair side effects"),
            outcome=repair_outcome,
            started_at=start,
            completed_at=end,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO repair_attempts VALUES (?,?,?,?,?,?,?,?)",
                (
                    strategy.project_ref.value,
                    attempt.attempt_ref,
                    attempt.pattern_ref,
                    attempt.strategy_ref,
                    attempt.outcome.value,
                    _canonical(attempt.payload()),
                    attempt.record_sha256,
                    attempt.completed_at,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return attempt

    def _pattern_by_ref(self, pattern_ref: str) -> FailurePatternCandidate:
        for pattern in self._patterns():
            if pattern.pattern_ref == pattern_ref:
                return pattern
        raise FailureLearningVersionError("failure pattern is not durable")

    def _strategy_from_payload(self, payload: Mapping[str, object]) -> RepairStrategy:
        return RepairStrategy(
            strategy_ref=str(payload["strategy_ref"]),
            pattern_ref=str(payload["pattern_ref"]),
            project_ref=ProjectRef(str(payload["project_ref"])),
            version=int(str(payload["version"])),
            name=str(payload["name"]),
            applicability=_payload_mapping(payload["applicability"], "strategy applicability"),
            prerequisites=_payload_texts(payload["prerequisites"], "strategy prerequisites"),
            actions=_payload_texts(payload["actions"], "strategy actions"),
            side_effect_authority=str(payload["side_effect_authority"]),
            required_validation=_payload_texts(payload["required_validation"], "required validation"),
            supersedes_ref=None if payload["supersedes_ref"] is None else str(payload["supersedes_ref"]),
            created_at=str(payload["created_at"]),
        )

    def _strategies_for_pattern(self, pattern_ref: str) -> tuple[RepairStrategy, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT payload_json, record_sha256 FROM failure_learning_versions WHERE kind='STRATEGY' ORDER BY stable_id, version"
            ).fetchall()
        finally:
            connection.close()
        strategies: list[RepairStrategy] = []
        for row in rows:
            payload = self._verify_payload(row["payload_json"], row["record_sha256"])
            if str(payload["pattern_ref"]) == pattern_ref:
                strategies.append(self._strategy_from_payload(payload))
        return tuple(strategies)

    def recommend_repair(
        self,
        match: FailurePatternMatch,
        strategies: Sequence[RepairStrategy] | None = None,
        *,
        task: Task | None = None,
    ) -> RepairRecommendation:
        if match.state is FailureMatchState.NO_MATCH or match.pattern_ref is None:
            return RepairRecommendation(match.state, None, None, None, ("collect exact failure evidence",), (), False)
        candidates = tuple(strategies) if strategies is not None else self._strategies_for_pattern(match.pattern_ref)
        applicable = tuple(item for item in candidates if item.pattern_ref == match.pattern_ref)
        if not applicable:
            return RepairRecommendation(match.state, match.pattern_ref, None, None, ("no evidenced repair strategy",), (), False)
        strategy = max(applicable, key=lambda item: (item.version, item.strategy_ref))
        if self._latest_version("STRATEGY", strategy.project_ref, strategy.stable_id) != strategy.version:
            raise FailureLearningVersionError("repair recommendation selected a stale strategy")
        if task is not None and task.project_ref != strategy.project_ref:
            raise FailureLearningScopeError("repair recommendation crossed Task Project scope")
        conditions = list(strategy.prerequisites)
        conditions.append("Task authority must be revalidated before mutation")
        if match.state is FailureMatchState.POSSIBLE_MATCH:
            conditions.append("root cause must be confirmed before autonomous repair")
        return RepairRecommendation(
            match.state,
            match.pattern_ref,
            strategy.strategy_ref,
            strategy.version,
            tuple(sorted(set(conditions))),
            strategy.required_validation,
            False,
        )

    def propose_repair_node(
        self,
        task: Task,
        match: FailurePatternMatch,
        strategy: RepairStrategy,
        node_ref: NodeRef,
    ) -> RepairNodeProposal:
        if not isinstance(task, Task) or not isinstance(node_ref, NodeRef):
            raise TypeError("exact Task and repair NodeRef are required")
        if task.project_ref != strategy.project_ref or node_ref.project_ref != strategy.project_ref:
            raise FailureLearningScopeError("repair Node proposal crossed Project scope")
        if match.state is not FailureMatchState.MATCHED or match.pattern_ref != strategy.pattern_ref:
            raise FailureLearningAuthorityError("autonomous repair requires an exact matched pattern")
        if task.constraints.get("autonomous_repair") is not True:
            raise FailureLearningAuthorityError("Task does not authorize an autonomous repair Node")
        TaskRevisionService.require_side_effect_within(task, strategy.side_effect_authority)
        if self._latest_version("STRATEGY", strategy.project_ref, strategy.stable_id) != strategy.version:
            raise FailureLearningVersionError("repair Node proposal selected a stale strategy")
        return RepairNodeProposal(
            task_ref=task.task_ref,
            node_ref=node_ref,
            pattern_ref=strategy.pattern_ref,
            strategy_ref=strategy.strategy_ref,
            strategy_digest=strategy.strategy_digest,
            requested_side_effect_authority=strategy.side_effect_authority,
        )

    def recurrence_metrics(self, pattern: FailurePatternCandidate) -> FailureRecurrenceMetrics:
        connection = self._connect()
        try:
            observation_row = connection.execute(
                "SELECT COUNT(*) AS count FROM failure_observations WHERE project_id=? AND normalized_signature=?",
                (pattern.project_ref.value, pattern.normalized_signature),
            ).fetchone()
            attempt_rows = connection.execute(
                "SELECT outcome, COUNT(*) AS count FROM repair_attempts WHERE project_id=? AND pattern_ref=? GROUP BY outcome",
                (pattern.project_ref.value, pattern.pattern_ref),
            ).fetchall()
        finally:
            connection.close()
        observations = 0 if observation_row is None else int(observation_row["count"])
        counts = {str(row["outcome"]): int(row["count"]) for row in attempt_rows}
        return FailureRecurrenceMetrics(
            observations=observations,
            recurrences=max(0, observations - 1),
            successful_repairs=counts.get(RepairOutcome.SUCCEEDED.value, 0),
            failed_repairs=counts.get(RepairOutcome.FAILED.value, 0),
            inconclusive_repairs=counts.get(RepairOutcome.INCONCLUSIVE.value, 0),
        )

    def rebuild_similarity_index(self) -> int:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS failure_similarity_index (
                    project_id TEXT NOT NULL, observation_ref TEXT NOT NULL,
                    normalized_signature TEXT NOT NULL, failure_category TEXT NOT NULL,
                    error_code TEXT, tokens_json TEXT NOT NULL,
                    source_record_sha256 TEXT NOT NULL, algorithm_version TEXT NOT NULL,
                    derivation_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, observation_ref)
                )
                """
            )
            connection.execute("DELETE FROM failure_similarity_index")
            rows = connection.execute(
                "SELECT payload_json, record_sha256 FROM failure_observations ORDER BY project_id, observation_ref"
            ).fetchall()
            count = 0
            for row in rows:
                payload = self._verify_payload(row["payload_json"], row["record_sha256"])
                summary = str(payload["sanitized_summary"])
                tokens = self._tokens(summary)
                derivation = {
                    "algorithm_version": "failure-signature/v1",
                    "normalized_signature": str(payload["normalized_signature"]),
                    "observation_ref": str(payload["observation_ref"]),
                    "source_record_sha256": str(row["record_sha256"]),
                    "tokens": list(tokens),
                }
                connection.execute(
                    "INSERT INTO failure_similarity_index VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        str(payload["project_ref"]),
                        str(payload["observation_ref"]),
                        str(payload["normalized_signature"]),
                        str(payload["failure_category"]),
                        None if payload["error_code"] is None else str(payload["error_code"]),
                        _canonical(list(tokens)),
                        str(row["record_sha256"]),
                        "failure-signature/v1",
                        _digest(derivation),
                    ),
                )
                count += 1
            connection.commit()
            return count
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @overload
    def project_knowledge_candidate(
        self,
        project_ref: ProjectRef,
        pattern: FailurePatternCandidate,
        *,
        memory_service: None = None,
        access: ProjectAccess | None = None,
        source_refs: Sequence[ArtifactRef] = (),
        evidence_refs: Sequence[ArtifactRef] = (),
    ) -> FailureKnowledgeProjection: ...

    @overload
    def project_knowledge_candidate(
        self,
        project_ref: ProjectRef,
        pattern: FailurePatternCandidate,
        *,
        memory_service: ProjectKnowledgeService,
        access: ProjectAccess | None = None,
        source_refs: Sequence[ArtifactRef] = (),
        evidence_refs: Sequence[ArtifactRef] = (),
    ) -> ProjectKnowledgeCandidate: ...

    def project_knowledge_candidate(
        self,
        project_ref: ProjectRef,
        pattern: FailurePatternCandidate,
        *,
        memory_service: ProjectKnowledgeService | None = None,
        access: ProjectAccess | None = None,
        source_refs: Sequence[ArtifactRef] = (),
        evidence_refs: Sequence[ArtifactRef] = (),
    ) -> FailureKnowledgeProjection | ProjectKnowledgeCandidate:
        if pattern.project_ref != project_ref or pattern.scope is not FailurePatternScope.PROJECT:
            raise FailureLearningScopeError("Project Knowledge projection crossed pattern scope")
        statement = f"Failure pattern {pattern.signature}: {'; '.join(pattern.symptoms)}"
        applicability = MappingProxyType({"failure_pattern": pattern.pattern_ref, **dict(pattern.applicability)})
        if memory_service is None:
            timestamp = _now()
            return FailureKnowledgeProjection(
                candidate_ref=f"failure-knowledge-candidate://{project_ref.value}/{uuid4().hex}",
                target="PROJECT_MEMORY",
                project_ref=project_ref,
                pattern_ref=pattern.pattern_ref,
                statement=statement,
                applicability=applicability,
                evidence_strength=pattern.evidence_strength,
                routing_allowed=False,
                created_at=timestamp,
            )
        if access is None or not source_refs:
            raise FailureLearningContractError("ProjectMemory projection requires access and exact Artifact provenance")
        return memory_service.record_candidate(
            access,
            project_ref=project_ref,
            idempotency_key=f"failure-pattern-{pattern.record_sha256}",
            origin_type="run.output",
            knowledge_type="project.failure_pattern",
            statement=statement,
            content_ref=None,
            applicability=applicability,
            source_refs=tuple(source_refs),
            evidence_refs=tuple(evidence_refs),
        )

    def engine_knowledge_candidate(
        self,
        project_or_pattern: ProjectRef | FailurePatternCandidate,
        pattern: FailurePatternCandidate | None = None,
        *,
        independent_project_refs: Sequence[ProjectRef] = (),
        knowledge_service: KnowledgeService | None = None,
        access: ProjectAccess | None = None,
        source_refs: Sequence[ArtifactRef] = (),
        evidence_refs: Sequence[ArtifactRef] = (),
    ) -> FailureKnowledgeProjection | KnowledgeCandidate:
        if pattern is None:
            if not isinstance(project_or_pattern, FailurePatternCandidate):
                raise TypeError("FailurePatternCandidate is required")
            pattern = project_or_pattern
        elif not isinstance(project_or_pattern, ProjectRef) or project_or_pattern != pattern.project_ref:
            raise FailureLearningScopeError("Engine Knowledge projection crossed Project scope")
        projects = tuple(sorted(set((*pattern.supporting_project_refs, *independent_project_refs)), key=lambda item: item.value))
        if pattern.scope is not FailurePatternScope.ENGINE or len(projects) < 2:
            raise FailureLearningScopeError("Project-specific repair cannot be auto-globalized")
        statement = f"Evidence-backed Engine failure pattern {pattern.signature}: {'; '.join(pattern.symptoms)}"
        applicability = MappingProxyType({"failure_pattern": pattern.pattern_ref, **dict(pattern.applicability)})
        if knowledge_service is None:
            return FailureKnowledgeProjection(
                candidate_ref=f"engine-knowledge-candidate://{pattern.project_ref.value}/{uuid4().hex}",
                target="ENGINE_KNOWLEDGE",
                project_ref=pattern.project_ref,
                pattern_ref=pattern.pattern_ref,
                statement=statement,
                applicability=applicability,
                evidence_strength="CORROBORATED",
                routing_allowed=False,
                created_at=_now(),
            )
        if access is None or not source_refs:
            raise FailureLearningContractError("Engine Knowledge projection requires access and exact Artifact provenance")
        return knowledge_service.record_candidate(
            access,
            project_ref=pattern.project_ref,
            idempotency_key=f"failure-pattern-{pattern.record_sha256}",
            proposed_scope="ENGINE",
            origin_type="run.output",
            knowledge_type="engine.failure_pattern",
            statement=statement,
            content_ref=None,
            applicability=applicability,
            source_refs=tuple(source_refs),
            evidence_refs=tuple(evidence_refs),
            source_run_ref=None,
            evidence_strength="CORROBORATED",
            universality_basis="Exact normalized failure evidence from at least two Projects.",
            scope_signals=KnowledgeScopeSignals(),
        )

    def kpi_results(self, project_ref: ProjectRef) -> Mapping[str, int]:
        connection = self._connect()
        try:
            root_rows = connection.execute(
                "SELECT payload_json, record_sha256 FROM failure_learning_versions WHERE project_id=? AND kind='ROOT_CAUSE'",
                (project_ref.value,),
            ).fetchall()
            repair_rows = connection.execute(
                "SELECT payload_json, record_sha256 FROM repair_attempts WHERE project_id=?",
                (project_ref.value,),
            ).fetchall()
            observation_rows = connection.execute(
                "SELECT payload_json, record_sha256 FROM failure_observations WHERE project_id=?",
                (project_ref.value,),
            ).fetchall()
        finally:
            connection.close()
        unproven = 0
        for row in root_rows:
            payload = self._verify_payload(row["payload_json"], row["record_sha256"])
            if payload["state"] == RootCauseState.CONFIRMED.value and not payload["controlled"]:
                unproven += 1
        success_without_validation = 0
        failed_hidden = 0
        for row in repair_rows:
            payload = self._verify_payload(row["payload_json"], row["record_sha256"])
            if payload["outcome"] == RepairOutcome.SUCCEEDED.value and not payload["validation_refs"]:
                success_without_validation += 1
            if payload["outcome"] == RepairOutcome.FAILED.value and not payload["attempt_ref"]:
                failed_hidden += 1
        sensitive = 0
        for row in observation_rows:
            payload = self._verify_payload(row["payload_json"], row["record_sha256"])
            normalized = _canonical(payload).lower()
            if any(marker in normalized for marker in ("authorization: bearer", "/root/", "/tmp/private", "token=", "password=")):
                sensitive += 1
        return MappingProxyType(
            {
                "Project_specific_repair_auto_globalized": 0,
                "failed_repairs_hidden": failed_hidden,
                "fixed_global_retry_or_repair_count": 0,
                "repair_success_claimed_without_validation": success_without_validation,
                "sensitive_raw_logs_copied_into_Engine_Knowledge": sensitive,
                "unproven_root_cause_stored_as_fact": unproven,
            }
        )


__all__ = [
    "FailureKnowledgeProjection",
    "FailureLearningAuthorityError",
    "FailureLearningContractError",
    "FailureLearningError",
    "FailureLearningIntegrityError",
    "FailureLearningScopeError",
    "FailureLearningService",
    "FailureLearningVersionError",
    "FailureMatchState",
    "FailureObservation",
    "FailurePatternCandidate",
    "FailurePatternMatch",
    "FailurePatternScope",
    "FailurePatternStatus",
    "FailureRecurrenceMetrics",
    "RepairAttempt",
    "RepairNodeProposal",
    "RepairOutcome",
    "RepairRecommendation",
    "RepairStrategy",
    "RootCauseCandidate",
    "RootCauseState",
]
