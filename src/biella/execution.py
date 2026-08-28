"""Durable fenced Node execution state and atomic finalization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import TypeAlias, cast
from uuid import uuid4

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .event import Event, EventConflictError, EventLedger, EventValue
from .graph import Graph, GraphError, GraphRef, GraphService, Node, NodeRef
from .project import ProjectAccess, ProjectRef, ProjectScopeError, ProjectStore
from .run import (
    ExecutionAttempt,
    Run,
    RunAuthorityError,
    RunError,
    RunRef,
    RunService,
)
from .task import Task, TaskRef, TaskRevisionService


ExecutionObjectRef: TypeAlias = ArtifactRef | ContentRef

_ATTEMPT_ID_PATTERN = re.compile(r"natt_[0-9a-f]{32}")
_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")
_CATEGORY_PATTERN = re.compile(r"[A-Z][A-Z0-9_.-]{0,63}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_ARTIFACT_PATTERN = re.compile(
    r"artifact://(prj_[0-9a-f]{32})/(art_[0-9a-f]{32})/([1-9][0-9]*)"
)
_CONTENT_PATTERN = re.compile(
    r"content://sha256/([0-9a-f]{64})\?size=(0|[1-9][0-9]*)"
)
_ACTIVE_STATUSES = {"LEASED", "RUNNING", "WAITING_EXTERNAL"}
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}
_ALL_STATUSES = {
    "CREATED",
    "QUEUED",
    "READY",
    "LEASED",
    "RUNNING",
    "WAITING_EXTERNAL",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "STALE",
}
_FINALIZATION_LOCK_ORDER = (
    "SQLiteWriteTransaction",
    "IdempotencyReplay",
    "Project",
    "Run",
    "Task",
    "Graph",
    "NodeExecution",
    "NodeExecutionAttempt",
    "Artifact",
    "Event",
)


class NodeExecutionError(Exception):
    """Base class for durable Node execution failures."""


class NodeExecutionContractError(NodeExecutionError, ValueError):
    """A Node execution request or record is malformed."""


class NodeExecutionScopeError(NodeExecutionError):
    """A Node execution operation crossed authenticated Project scope."""


class NodeExecutionAuthorityError(NodeExecutionError):
    """A Node execution operation lacks current fenced authority."""


class NodeExecutionConflictError(NodeExecutionError):
    """A Node execution state, lease, or idempotency identity conflicts."""


class NodeExecutionNotFoundError(NodeExecutionError):
    """An exact Node execution does not exist."""


class NodeExecutionIntegrityError(NodeExecutionError):
    """Persisted Node execution evidence failed verification."""


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _validate_timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise NodeExecutionContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise NodeExecutionContractError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NodeExecutionContractError(f"{name} must be timezone-aware")
    return value


def _validate_key(value: object, name: str) -> str:
    if not isinstance(value, str) or _KEY_PATTERN.fullmatch(value) is None:
        raise NodeExecutionContractError(f"{name} is malformed")
    return value


def _validate_owner(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value.encode()) > 1024
        or re.fullmatch(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}", value) is None
    ):
        raise NodeExecutionContractError("Node execution owner is malformed")
    return value


def _freeze_bindings(value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise NodeExecutionContractError("Node execution bindings must be a mapping")
    copied = dict(value)
    if len(copied) > 64:
        raise NodeExecutionContractError("Node execution bindings are unbounded")
    for key, reference in copied.items():
        _validate_key(key, "Node execution binding key")
        if (
            not isinstance(reference, str)
            or (
                _ARTIFACT_PATTERN.fullmatch(reference) is None
                and _CONTENT_PATTERN.fullmatch(reference) is None
            )
        ):
            raise NodeExecutionContractError("Node execution binding is not exact")
    return MappingProxyType(dict(sorted(copied.items())))


@dataclass(frozen=True)
class NodeExecutionAttempt:
    """Immutable fenced authority token for one Node execution attempt."""

    attempt_id: str
    node_ref: NodeRef
    run_ref: RunRef
    task_ref: TaskRef
    task_digest: str
    attempt_number: int
    fence: int
    owner_ref: str
    run_attempt_id: str
    run_fence: int
    lease_acquired_at: str
    lease_expires_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.node_ref, NodeRef):
            raise TypeError("node_ref must be NodeRef")
        if not isinstance(self.run_ref, RunRef) or not isinstance(self.task_ref, TaskRef):
            raise NodeExecutionContractError("Node attempt exact Run and Task are required")
        if (
            self.node_ref.project_ref != self.run_ref.project_ref
            or self.task_ref.project_ref != self.run_ref.project_ref
        ):
            raise NodeExecutionScopeError("Node attempt Project scope mismatch")
        if not isinstance(self.attempt_id, str) or _ATTEMPT_ID_PATTERN.fullmatch(self.attempt_id) is None:
            raise NodeExecutionContractError("Node attempt identity is malformed")
        if not isinstance(self.task_digest, str) or _SHA256_PATTERN.fullmatch(self.task_digest) is None:
            raise NodeExecutionContractError("Node attempt Task digest is malformed")
        for value, name in (
            (self.attempt_number, "attempt_number"),
            (self.fence, "fence"),
            (self.run_fence, "run_fence"),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise NodeExecutionContractError(f"Node attempt {name} must be positive")
        _validate_owner(self.owner_ref)
        if not isinstance(self.run_attempt_id, str) or re.fullmatch(r"att_[0-9a-f]{32}", self.run_attempt_id) is None:
            raise NodeExecutionContractError("Node attempt Run authority is malformed")
        _validate_timestamp(self.lease_acquired_at, "lease_acquired_at")
        _validate_timestamp(self.lease_expires_at, "lease_expires_at")
        object.__setattr__(self, "record_sha256", _sha256(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "fence": self.fence,
            "lease_acquired_at": self.lease_acquired_at,
            "lease_expires_at": self.lease_expires_at,
            "node_ref": self.node_ref.value,
            "owner_ref": self.owner_ref,
            "run_attempt_id": self.run_attempt_id,
            "run_fence": self.run_fence,
            "run_id": self.run_ref.run_id,
            "task_digest": self.task_digest,
            "task_id": self.task_ref.task_id,
            "task_revision": self.task_ref.revision,
        }


@dataclass(frozen=True)
class NodeExecutionFailure:
    """Immutable bounded failure evidence for one Node attempt."""

    node_ref: NodeRef
    attempt_id: str
    category: str
    reason: str
    evidence_refs: tuple[str, ...]
    retry_possible: bool
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.node_ref, NodeRef):
            raise TypeError("node_ref must be NodeRef")
        if not isinstance(self.attempt_id, str) or _ATTEMPT_ID_PATTERN.fullmatch(self.attempt_id) is None:
            raise NodeExecutionContractError("Failure attempt identity is malformed")
        if not isinstance(self.category, str) or _CATEGORY_PATTERN.fullmatch(self.category) is None:
            raise NodeExecutionContractError("Failure category is malformed")
        if not isinstance(self.reason, str) or not self.reason or len(self.reason.encode()) > 2048:
            raise NodeExecutionContractError("Failure reason is empty or unbounded")
        if not isinstance(self.evidence_refs, tuple) or len(self.evidence_refs) > 32:
            raise NodeExecutionContractError("Failure evidence is unbounded")
        if not isinstance(self.retry_possible, bool):
            raise NodeExecutionContractError("Failure retry_possible must be boolean")
        _validate_timestamp(self.created_at, "created_at")
        object.__setattr__(
            self,
            "record_sha256",
            _sha256(
                {
                    "attempt_id": self.attempt_id,
                    "category": self.category,
                    "created_at": self.created_at,
                    "evidence_refs": list(self.evidence_refs),
                    "node_ref": self.node_ref.value,
                    "reason": self.reason,
                    "retry_possible": self.retry_possible,
                }
            ),
        )


@dataclass(frozen=True)
class NodeExecution:
    """Latest verified state of one exact Node in one immutable Graph revision."""

    node_ref: NodeRef
    run_ref: RunRef
    task_ref: TaskRef
    task_digest: str
    status: str
    state_version: int
    current_attempt_id: str | None
    current_attempt_number: int | None
    current_fence: int
    current_owner_ref: str | None
    current_run_attempt_id: str | None
    current_run_fence: int | None
    lease_expires_at: str | None
    waiting_reason: str | None
    outputs: Mapping[str, str]
    evidence: Mapping[str, str]
    created_at: str
    updated_at: str
    identity_sha256: str = field(init=False)
    state_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.node_ref, NodeRef):
            raise TypeError("node_ref must be NodeRef")
        if not isinstance(self.run_ref, RunRef) or not isinstance(self.task_ref, TaskRef):
            raise NodeExecutionContractError("Node execution exact Run and Task are required")
        if (
            self.node_ref.project_ref != self.run_ref.project_ref
            or self.task_ref.project_ref != self.run_ref.project_ref
        ):
            raise NodeExecutionScopeError("Node execution Project scope mismatch")
        if not isinstance(self.task_digest, str) or _SHA256_PATTERN.fullmatch(self.task_digest) is None:
            raise NodeExecutionContractError("Node execution Task digest is malformed")
        if self.status not in _ALL_STATUSES:
            raise NodeExecutionContractError("Node execution status is malformed")
        if not isinstance(self.state_version, int) or isinstance(self.state_version, bool) or self.state_version < 1:
            raise NodeExecutionContractError("Node state version must be positive")
        if not isinstance(self.current_fence, int) or isinstance(self.current_fence, bool) or self.current_fence < 0:
            raise NodeExecutionContractError("Node fence must be non-negative")
        attempt_values = (
            self.current_attempt_id,
            self.current_attempt_number,
            self.current_run_attempt_id,
            self.current_run_fence,
        )
        if any(value is not None for value in attempt_values) and not all(
            value is not None for value in attempt_values
        ):
            raise NodeExecutionContractError("Node execution attempt evidence is incomplete")
        if self.current_attempt_id is None:
            if self.current_fence != 0:
                raise NodeExecutionContractError("Node without attempt cannot have fence")
        else:
            if _ATTEMPT_ID_PATTERN.fullmatch(self.current_attempt_id) is None:
                raise NodeExecutionContractError("Current Node attempt identity is malformed")
            if (
                not isinstance(self.current_attempt_number, int)
                or isinstance(self.current_attempt_number, bool)
                or self.current_attempt_number < 1
                or self.current_fence < 1
                or not isinstance(self.current_run_attempt_id, str)
                or re.fullmatch(r"att_[0-9a-f]{32}", self.current_run_attempt_id) is None
                or not isinstance(self.current_run_fence, int)
                or isinstance(self.current_run_fence, bool)
                or self.current_run_fence < 1
            ):
                raise NodeExecutionContractError("Current Node attempt or Run fence is malformed")
        owner_values = (self.current_owner_ref, self.lease_expires_at)
        if (owner_values[0] is None) != (owner_values[1] is None):
            raise NodeExecutionContractError("Node owner and lease must be present together")
        if self.current_owner_ref is not None:
            _validate_owner(self.current_owner_ref)
            _validate_timestamp(self.lease_expires_at, "lease_expires_at")
            if self.status not in _ACTIVE_STATUSES:
                raise NodeExecutionContractError("Only active Node state may hold authority")
        elif self.status in _ACTIVE_STATUSES:
            raise NodeExecutionContractError("Active Node state requires lease authority")
        if self.waiting_reason is not None and (
            self.status != "WAITING_EXTERNAL"
            or not self.waiting_reason
            or len(self.waiting_reason.encode()) > 2048
        ):
            raise NodeExecutionContractError("Node waiting reason is malformed")
        if self.status == "WAITING_EXTERNAL" and self.waiting_reason is None:
            raise NodeExecutionContractError("Waiting Node requires bounded reason")
        object.__setattr__(self, "outputs", _freeze_bindings(self.outputs))
        object.__setattr__(self, "evidence", _freeze_bindings(self.evidence))
        if self.status != "SUCCEEDED" and (self.outputs or self.evidence):
            raise NodeExecutionContractError("Only successful Node may expose final bindings")
        _validate_timestamp(self.created_at, "created_at")
        _validate_timestamp(self.updated_at, "updated_at")
        object.__setattr__(self, "identity_sha256", _sha256(self._identity_payload()))
        object.__setattr__(self, "state_sha256", _sha256(self._state_payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.node_ref.project_ref

    @property
    def graph_ref(self) -> GraphRef:
        return self.node_ref.graph_ref

    def _identity_payload(self) -> dict[str, object]:
        return {
            "created_at": self.created_at,
            "node_ref": self.node_ref.value,
            "run_id": self.run_ref.run_id,
            "task_digest": self.task_digest,
            "task_id": self.task_ref.task_id,
            "task_revision": self.task_ref.revision,
        }

    def _state_payload(self) -> dict[str, object]:
        return {
            "current_attempt_id": self.current_attempt_id,
            "current_attempt_number": self.current_attempt_number,
            "current_fence": self.current_fence,
            "current_owner_ref": self.current_owner_ref,
            "current_run_attempt_id": self.current_run_attempt_id,
            "current_run_fence": self.current_run_fence,
            "evidence": dict(self.evidence),
            "lease_expires_at": self.lease_expires_at,
            "node_ref": self.node_ref.value,
            "outputs": dict(self.outputs),
            "state_version": self.state_version,
            "status": self.status,
            "updated_at": self.updated_at,
            "waiting_reason": self.waiting_reason,
        }


class NodeExecutionService:
    """Durable Node lifecycle, fencing, recovery, and atomic finalization service.

    SQLite write transactions use ``BEGIN IMMEDIATE``. Atomic finalization
    resolves durable authority in ``_FINALIZATION_LOCK_ORDER`` and revalidates
    preflight Artifact reads inside that transaction. This gives
    Run/Node/Artifact/Event mutation one database serialization boundary while
    allowing independent live Node leases to coexist durably.
    """

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.runs = RunService(self.database_path)
        self.graphs = GraphService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.events = EventLedger(self.database_path)
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
                CREATE UNIQUE INDEX IF NOT EXISTS graph_nodes_exact_execution_ref
                    ON graph_nodes(project_id, graph_id, graph_revision, node_id, record_sha256);
                CREATE UNIQUE INDEX IF NOT EXISTS execution_attempts_exact_node_run_authority
                    ON execution_attempts(project_id, run_id, attempt_id, fence);

                CREATE TABLE IF NOT EXISTS node_executions (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_revision INTEGER NOT NULL,
                    task_digest TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    node_record_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id),
                    UNIQUE (project_id, graph_id, graph_revision, node_id, record_sha256),
                    FOREIGN KEY (project_id, run_id) REFERENCES runs(project_id, run_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, task_id, task_revision, task_digest)
                        REFERENCES task_revisions(project_id, task_id, revision, canonical_digest)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id, node_record_sha256)
                        REFERENCES graph_nodes(project_id, graph_id, graph_revision, node_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS node_execution_attempts (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_revision INTEGER NOT NULL,
                    task_digest TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    fence INTEGER NOT NULL,
                    owner_ref TEXT NOT NULL,
                    run_attempt_id TEXT NOT NULL,
                    run_fence INTEGER NOT NULL,
                    lease_acquired_at TEXT NOT NULL,
                    lease_expires_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id, attempt_id),
                    UNIQUE (project_id, graph_id, graph_revision, node_id, attempt_number),
                    UNIQUE (project_id, graph_id, graph_revision, node_id, fence),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id)
                        REFERENCES node_executions(project_id, graph_id, graph_revision, node_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, run_id, run_attempt_id, run_fence)
                        REFERENCES execution_attempts(project_id, run_id, attempt_id, fence)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS node_execution_attempt_completions (
                    project_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id, attempt_id),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id, attempt_id)
                        REFERENCES node_execution_attempts(project_id, graph_id, graph_revision, node_id, attempt_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS node_execution_state_versions (
                    project_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    state_version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    current_attempt_id TEXT,
                    current_attempt_number INTEGER,
                    current_fence INTEGER NOT NULL,
                    current_owner_ref TEXT,
                    current_run_attempt_id TEXT,
                    current_run_fence INTEGER,
                    lease_expires_at TEXT,
                    waiting_reason TEXT,
                    updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id, state_version),
                    UNIQUE (project_id, graph_id, graph_revision, node_id, state_version, record_sha256),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id)
                        REFERENCES node_executions(project_id, graph_id, graph_revision, node_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id, current_attempt_id)
                        REFERENCES node_execution_attempts(project_id, graph_id, graph_revision, node_id, attempt_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS node_execution_heads (
                    project_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    current_state_version INTEGER NOT NULL,
                    current_state_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id),
                    FOREIGN KEY (
                        project_id, graph_id, graph_revision, node_id,
                        current_state_version, current_state_sha256
                    ) REFERENCES node_execution_state_versions(
                        project_id, graph_id, graph_revision, node_id,
                        state_version, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS node_execution_bindings (
                    project_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    binding_kind TEXT NOT NULL,
                    binding_key TEXT NOT NULL,
                    object_ref TEXT NOT NULL,
                    artifact_id TEXT,
                    artifact_revision INTEGER,
                    artifact_record_sha256 TEXT,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id, binding_kind, binding_key),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id)
                        REFERENCES node_executions(project_id, graph_id, graph_revision, node_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, artifact_id, artifact_revision, artifact_record_sha256)
                        REFERENCES artifact_revisions(project_id, artifact_id, revision, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS node_execution_failures (
                    project_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    retry_possible INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id, attempt_id),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id, attempt_id)
                        REFERENCES node_execution_attempts(project_id, graph_id, graph_revision, node_id, attempt_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS node_condition_results (
                    project_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    condition_ref TEXT NOT NULL,
                    result INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, condition_ref),
                    FOREIGN KEY (project_id, graph_id, graph_revision)
                        REFERENCES graph_revisions(project_id, graph_id, revision)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS node_transition_idempotency (
                    project_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    semantic_sha256 TEXT NOT NULL,
                    result_state_version INTEGER NOT NULL,
                    result_attempt_id TEXT,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id, operation, idempotency_key),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id, result_state_version)
                        REFERENCES node_execution_state_versions(project_id, graph_id, graph_revision, node_id, state_version)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS run_completion_manifests (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    run_state_version INTEGER NOT NULL,
                    task_id TEXT NOT NULL,
                    task_revision INTEGER NOT NULL,
                    task_digest TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    acceptance_events_json TEXT NOT NULL,
                    completion_event_id TEXT NOT NULL,
                    completion_event_record_sha256 TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id),
                    FOREIGN KEY (project_id, run_id) REFERENCES runs(project_id, run_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, task_id, task_revision, task_digest
                    ) REFERENCES task_revisions(
                        project_id, task_id, revision, canonical_digest
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, graph_id, graph_revision
                    ) REFERENCES graph_revisions(
                        project_id, graph_id, revision
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, completion_event_id,
                        completion_event_record_sha256
                    ) REFERENCES events(
                        project_id, event_id, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS node_executions_no_update BEFORE UPDATE ON node_executions
                BEGIN SELECT RAISE(ABORT, 'Node execution identity is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS node_executions_no_delete BEFORE DELETE ON node_executions
                BEGIN SELECT RAISE(ABORT, 'Node execution identity cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_attempts_no_update BEFORE UPDATE ON node_execution_attempts
                BEGIN SELECT RAISE(ABORT, 'Node attempt is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_attempts_no_delete BEFORE DELETE ON node_execution_attempts
                BEGIN SELECT RAISE(ABORT, 'Node attempt cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_attempt_completions_no_update BEFORE UPDATE ON node_execution_attempt_completions
                BEGIN SELECT RAISE(ABORT, 'Node attempt completion is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_attempt_completions_no_delete BEFORE DELETE ON node_execution_attempt_completions
                BEGIN SELECT RAISE(ABORT, 'Node attempt completion cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_state_versions_no_update BEFORE UPDATE ON node_execution_state_versions
                BEGIN SELECT RAISE(ABORT, 'Node state history is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_state_versions_no_delete BEFORE DELETE ON node_execution_state_versions
                BEGIN SELECT RAISE(ABORT, 'Node state history cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_heads_no_delete BEFORE DELETE ON node_execution_heads
                BEGIN SELECT RAISE(ABORT, 'Node state head cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_heads_monotonic BEFORE UPDATE ON node_execution_heads
                WHEN NEW.current_state_version != OLD.current_state_version + 1
                  OR NEW.project_id != OLD.project_id OR NEW.graph_id != OLD.graph_id
                  OR NEW.graph_revision != OLD.graph_revision OR NEW.node_id != OLD.node_id
                BEGIN SELECT RAISE(ABORT, 'Node state head must advance monotonically'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_bindings_no_update BEFORE UPDATE ON node_execution_bindings
                BEGIN SELECT RAISE(ABORT, 'Node binding is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_bindings_no_delete BEFORE DELETE ON node_execution_bindings
                BEGIN SELECT RAISE(ABORT, 'Node binding cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_failures_no_update BEFORE UPDATE ON node_execution_failures
                BEGIN SELECT RAISE(ABORT, 'Node failure is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS node_execution_failures_no_delete BEFORE DELETE ON node_execution_failures
                BEGIN SELECT RAISE(ABORT, 'Node failure cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS node_condition_results_no_update BEFORE UPDATE ON node_condition_results
                BEGIN SELECT RAISE(ABORT, 'Node condition result is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS node_condition_results_no_delete BEFORE DELETE ON node_condition_results
                BEGIN SELECT RAISE(ABORT, 'Node condition result cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS node_transition_idempotency_no_update BEFORE UPDATE ON node_transition_idempotency
                BEGIN SELECT RAISE(ABORT, 'Node transition idempotency is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS node_transition_idempotency_no_delete BEFORE DELETE ON node_transition_idempotency
                BEGIN SELECT RAISE(ABORT, 'Node transition idempotency cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS run_completion_manifests_no_update BEFORE UPDATE ON run_completion_manifests
                BEGIN SELECT RAISE(ABORT, 'Run completion manifest is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS run_completion_manifests_no_delete BEFORE DELETE ON run_completion_manifests
                BEGIN SELECT RAISE(ABORT, 'Run completion manifest cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def prepare_run(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
        *,
        condition_results: Mapping[str, bool] | None = None,
    ) -> tuple[NodeExecution, ...]:
        self.runs.get_run(requesting_access, run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run, task, graph = self._context(connection, requesting_access, run_ref)
            self._sync_graph(
                connection,
                run,
                task,
                graph,
                {} if condition_results is None else condition_results,
            )
            self._complete_run_if_ready(
                connection,
                requesting_access,
                run,
                task,
                graph,
            )
            executions = self._ordered_current(connection, graph)
            connection.commit()
            return executions
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record_run_acceptance(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
        *,
        criterion: str,
        evidence_ref: ArtifactRef,
        authority_attempt: ExecutionAttempt,
        actor_ref: str,
        idempotency_key: str,
    ) -> Event:
        """Append Graph-scoped controller acceptance to the durable Event chain."""

        _validate_key(idempotency_key, "idempotency_key")
        _validate_owner(actor_ref)
        if not isinstance(criterion, str) or not criterion or len(criterion.encode()) > 512:
            raise NodeExecutionContractError("Acceptance criterion is malformed or unbounded")
        if not isinstance(evidence_ref, ArtifactRef):
            raise NodeExecutionContractError("Acceptance requires exact Artifact evidence")
        if not isinstance(authority_attempt, ExecutionAttempt):
            raise NodeExecutionAuthorityError("Run acceptance requires controller authority")
        if actor_ref != authority_attempt.owner_ref:
            raise NodeExecutionAuthorityError(
                "Acceptance actor must be the current Run controller"
            )
        self._authorize(requesting_access, run_ref.project_ref)
        try:
            expected_artifact = self.artifacts.get_artifact(
                requesting_access,
                evidence_ref,
            )
        except ArtifactError as exc:
            raise NodeExecutionContractError("Acceptance ArtifactRef is invalid") from exc
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run, task, graph = self._context(connection, requesting_access, run_ref)
            acceptance_events = self._verified_acceptance_events(
                connection,
                run,
                task,
                graph,
            )
            prior_criterion = acceptance_events.get(criterion)
            prior_key = next(
                (
                    event
                    for event in acceptance_events.values()
                    if event.metadata["request_idempotency_key"] == idempotency_key
                ),
                None,
            )
            if prior_criterion is not None or prior_key is not None:
                if (
                    prior_criterion is None
                    or prior_key is None
                    or prior_criterion != prior_key
                    or prior_criterion.actor_ref != actor_ref
                    or prior_criterion.object_refs != (evidence_ref.value,)
                    or prior_criterion.metadata["authority_attempt_id"]
                    != authority_attempt.attempt_id
                    or prior_criterion.metadata["authority_fence"]
                    != authority_attempt.fence
                ):
                    raise NodeExecutionConflictError(
                        "Run acceptance idempotency semantics conflict"
                    )
                if run.status == "RUNNING":
                    self._complete_run_if_ready(
                        connection,
                        requesting_access,
                        run,
                        task,
                        graph,
                    )
                connection.commit()
                return prior_criterion
            if criterion not in task.acceptance_criteria:
                raise NodeExecutionContractError("Unknown Task acceptance criterion")
            try:
                current_run = self.runs.assert_current_run_authority_in_transaction(
                    connection,
                    requesting_access,
                    authority_attempt,
                )
            except (RunAuthorityError, RunError) as exc:
                raise NodeExecutionAuthorityError(
                    "Run acceptance requires current controller authority"
                ) from exc
            if current_run.run_ref != run_ref or current_run.status != "RUNNING":
                raise NodeExecutionAuthorityError(
                    "Run acceptance authority is not bound to the live Run"
                )
            artifact = self.artifacts._fetch_artifact(connection, evidence_ref)
            if not hmac.compare_digest(
                artifact.record_sha256,
                expected_artifact.record_sha256,
            ):
                raise NodeExecutionIntegrityError(
                    "Acceptance Artifact changed before durable recording"
                )
            event = self.events._append_in_transaction(
                connection,
                requesting_access,
                project_ref=run.project_ref,
                task_ref=task.task_ref,
                run_ref=run.run_ref,
                graph_ref=graph.graph_ref,
                node_ref=None,
                event_type="RUN_ACCEPTANCE_RECORDED",
                idempotency_key=self._acceptance_event_key(graph, idempotency_key),
                actor_ref=actor_ref,
                object_refs=(evidence_ref,),
                metadata={
                    "authority_attempt_id": authority_attempt.attempt_id,
                    "authority_fence": authority_attempt.fence,
                    "criterion": criterion,
                    "request_idempotency_key": idempotency_key,
                },
                payload_ref=None,
                authority_attempt=authority_attempt,
                require_run_authority=True,
            )
            self._complete_run_if_ready(
                connection,
                requesting_access,
                run,
                task,
                graph,
            )
            connection.commit()
            return event
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise NodeExecutionConflictError("Run acceptance conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def lease_node(
        self,
        requesting_access: ProjectAccess,
        node_ref: NodeRef,
        *,
        authority_attempt: ExecutionAttempt,
        owner_ref: str,
        lease_seconds: int | float,
        idempotency_key: str,
    ) -> NodeExecutionAttempt:
        _validate_owner(owner_ref)
        _validate_key(idempotency_key, "idempotency_key")
        duration = self._validate_lease_seconds(lease_seconds)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run, task, graph = self._context(
                connection,
                requesting_access,
                authority_attempt.run_ref,
            )
            if node_ref.graph_ref != graph.graph_ref:
                raise NodeExecutionAuthorityError("Node is not in the current Graph revision")
            self._sync_graph(connection, run, task, graph, {})
            semantic = _sha256(
                {
                    "authority_attempt": authority_attempt.attempt_id,
                    "lease_seconds": duration,
                    "owner_ref": owner_ref,
                }
            )
            prior = self._idempotent_attempt(
                connection,
                node_ref,
                "LEASE",
                idempotency_key,
                semantic,
            )
            if prior is not None:
                connection.commit()
                return prior
            try:
                current_run = self.runs.assert_current_run_authority_in_transaction(
                    connection,
                    requesting_access,
                    authority_attempt,
                )
            except (RunAuthorityError, RunError) as exc:
                raise NodeExecutionAuthorityError("Node lease requires current Run authority") from exc
            if current_run.status != "RUNNING":
                raise NodeExecutionAuthorityError("Terminal Run cannot lease Node")
            current = self._fetch_execution(connection, node_ref)
            if current.status != "READY":
                raise NodeExecutionConflictError("Node is not READY")
            now, expires_at = self.runs._database_lease_times(connection, duration)
            number = self._next_attempt_number(connection, node_ref)
            attempt = NodeExecutionAttempt(
                f"natt_{uuid4().hex}",
                node_ref,
                run.run_ref,
                task.task_ref,
                task.canonical_digest,
                number,
                current.current_fence + 1,
                owner_ref,
                authority_attempt.attempt_id,
                authority_attempt.fence,
                now,
                expires_at,
            )
            self._insert_attempt(connection, attempt)
            leased = self._next_state(
                current,
                "LEASED",
                now,
                attempt=attempt,
                lease_expires_at=expires_at,
            )
            self._append_state(connection, current, leased)
            self._record_transition(
                connection,
                leased,
                "LEASE",
                idempotency_key,
                semantic,
                attempt.attempt_id,
            )
            connection.commit()
            return attempt
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise NodeExecutionConflictError("Node lease conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def start_node(
        self,
        requesting_access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        idempotency_key: str,
    ) -> NodeExecution:
        return self._active_transition(
            requesting_access,
            attempt,
            operation="START",
            target_status="RUNNING",
            idempotency_key=idempotency_key,
        )

    def heartbeat_node(
        self,
        requesting_access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        lease_seconds: int | float,
        idempotency_key: str,
    ) -> NodeExecution:
        duration = self._validate_lease_seconds(lease_seconds)
        _validate_key(idempotency_key, "idempotency_key")
        self._authorize(requesting_access, attempt.node_ref.project_ref)
        semantic = _sha256({"attempt": attempt.record_sha256, "lease_seconds": duration})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = self._idempotent_state(
                connection,
                attempt.node_ref,
                "HEARTBEAT",
                idempotency_key,
                semantic,
            )
            if prior is not None:
                connection.commit()
                return prior
            current, _, _, _ = self._require_live_attempt(
                connection,
                requesting_access,
                attempt,
                allowed_statuses=_ACTIVE_STATUSES,
            )
            now = self._database_now(connection)
            expires_at = self.runs._database_renewed_expiry(
                connection,
                cast(str, current.lease_expires_at),
                duration,
            )
            renewed = self._next_state(
                current,
                current.status,
                now,
                attempt=attempt,
                lease_expires_at=expires_at,
                waiting_reason=current.waiting_reason,
            )
            self._append_state(connection, current, renewed)
            self._record_transition(connection, renewed, "HEARTBEAT", idempotency_key, semantic, attempt.attempt_id)
            connection.commit()
            return renewed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def wait_node(
        self,
        requesting_access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        reason: str,
        evidence_refs: Sequence[ExecutionObjectRef],
        retry_possible: bool,
        idempotency_key: str,
    ) -> NodeExecution:
        if not isinstance(reason, str) or not reason or len(reason.encode()) > 2048:
            raise NodeExecutionContractError("Waiting reason is empty or unbounded")
        if not isinstance(retry_possible, bool):
            raise NodeExecutionContractError("retry_possible must be boolean")
        self._authorize(requesting_access, attempt.node_ref.project_ref)
        normalized, _ = self._normalize_objects(requesting_access, attempt.node_ref.project_ref, evidence_refs)
        semantic = _sha256(
            {
                "attempt": attempt.record_sha256,
                "evidence": list(normalized),
                "reason": reason,
                "retry_possible": retry_possible,
            }
        )
        _validate_key(idempotency_key, "idempotency_key")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = self._idempotent_state(connection, attempt.node_ref, "WAIT", idempotency_key, semantic)
            if prior is not None:
                connection.commit()
                return prior
            current, _, _, _ = self._require_live_attempt(
                connection,
                requesting_access,
                attempt,
                allowed_statuses={"RUNNING", "WAITING_EXTERNAL"},
            )
            now = self._database_now(connection)
            waiting = self._next_state(
                current,
                "WAITING_EXTERNAL",
                now,
                attempt=attempt,
                lease_expires_at=current.lease_expires_at,
                waiting_reason=reason,
            )
            self._append_state(connection, current, waiting)
            self._record_transition(connection, waiting, "WAIT", idempotency_key, semantic, attempt.attempt_id)
            connection.commit()
            return waiting
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def fail_node(
        self,
        requesting_access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        category: str,
        reason: str,
        evidence_refs: Sequence[ExecutionObjectRef],
        retry_possible: bool,
        idempotency_key: str,
    ) -> NodeExecution:
        _validate_key(idempotency_key, "idempotency_key")
        if not isinstance(category, str) or _CATEGORY_PATTERN.fullmatch(category) is None:
            raise NodeExecutionContractError("Failure category is malformed")
        if not isinstance(reason, str) or not reason or len(reason.encode()) > 2048:
            raise NodeExecutionContractError("Failure reason is empty or unbounded")
        if not isinstance(retry_possible, bool):
            raise NodeExecutionContractError("retry_possible must be boolean")
        self._authorize(requesting_access, attempt.node_ref.project_ref)
        normalized, _ = self._normalize_objects(
            requesting_access,
            attempt.node_ref.project_ref,
            evidence_refs,
        )
        objects = tuple(evidence_refs)
        semantic = _sha256(
            {
                "attempt": attempt.record_sha256,
                "category": category,
                "evidence": list(normalized),
                "reason": reason,
                "retry_possible": retry_possible,
            }
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = self._idempotent_state(connection, attempt.node_ref, "FAIL", idempotency_key, semantic)
            if prior is not None:
                connection.commit()
                return prior
            current, run, task, graph = self._require_live_attempt(
                connection,
                requesting_access,
                attempt,
                allowed_statuses=_ACTIVE_STATUSES,
            )
            now = self._database_now(connection)
            failure = NodeExecutionFailure(
                attempt.node_ref,
                attempt.attempt_id,
                category,
                reason,
                normalized,
                retry_possible,
                now,
            )
            self._insert_failure(connection, failure)
            self._complete_attempt(connection, attempt, now, "FAILED")
            failed = self._next_state(current, "FAILED", now)
            self._append_state(connection, current, failed)
            run_attempt = self.runs._fetch_attempt(connection, run, attempt.run_attempt_id)
            self.events._append_in_transaction(
                connection,
                requesting_access,
                project_ref=run.project_ref,
                task_ref=task.task_ref,
                run_ref=run.run_ref,
                graph_ref=graph.graph_ref,
                node_ref=attempt.node_ref,
                event_type="FAILURE_RECORDED",
                idempotency_key=f"p009-fail-{idempotency_key}",
                actor_ref=attempt.owner_ref,
                object_refs=objects,
                metadata={"category": category, "retry_possible": retry_possible},
                payload_ref=None,
                authority_attempt=run_attempt,
                require_run_authority=True,
            )
            if not retry_possible:
                failed_run = self.runs._fail_run_in_transaction(
                    connection,
                    requesting_access,
                    run.run_ref,
                )
                self.events._append_in_transaction(
                    connection,
                    requesting_access,
                    project_ref=run.project_ref,
                    task_ref=task.task_ref,
                    run_ref=run.run_ref,
                    graph_ref=current.node_ref.graph_ref,
                    node_ref=None,
                    event_type="RUN_FAILED",
                    idempotency_key=f"p009-rf-{idempotency_key}",
                    actor_ref="controller://execution-service",
                    object_refs=objects,
                    metadata={"state_version": failed_run.state_version},
                    payload_ref=None,
                    authority_attempt=None,
                    require_run_authority=False,
                )
            self._record_transition(connection, failed, "FAIL", idempotency_key, semantic, attempt.attempt_id)
            connection.commit()
            return failed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def finalize_node(
        self,
        requesting_access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        outputs: Mapping[str, ExecutionObjectRef],
        evidence: Mapping[str, ExecutionObjectRef],
        acceptance_criteria: Sequence[str],
        idempotency_key: str,
    ) -> NodeExecution:
        _validate_key(idempotency_key, "idempotency_key")
        self._authorize(requesting_access, attempt.node_ref.project_ref)
        normalized_outputs, output_objects, output_artifacts = self._normalize_named_objects(
            requesting_access,
            attempt.node_ref.project_ref,
            outputs,
        )
        normalized_evidence, evidence_objects, evidence_artifacts = self._normalize_named_objects(
            requesting_access,
            attempt.node_ref.project_ref,
            evidence,
        )
        criteria = self._freeze_text(acceptance_criteria, "acceptance_criteria", 128)
        if criteria:
            raise NodeExecutionContractError(
                "Node workers cannot self-assert Task acceptance; use "
                "record_run_acceptance with controller authority and Artifact evidence"
            )
        semantic = _sha256(
            {
                "acceptance_criteria": list(criteria),
                "attempt": attempt.record_sha256,
                "evidence": dict(normalized_evidence),
                "outputs": dict(normalized_outputs),
            }
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = self._idempotent_state(
                connection,
                attempt.node_ref,
                "FINALIZE",
                idempotency_key,
                semantic,
            )
            if existing is not None:
                connection.commit()
                return existing
            current, run, task, graph = self._require_live_attempt(
                connection,
                requesting_access,
                attempt,
                allowed_statuses={"RUNNING", "WAITING_EXTERNAL"},
            )
            node = self._node(graph, attempt.node_ref)
            self._require_dependencies_satisfied(connection, task, graph, node)
            if set(normalized_outputs) != set(node.output_contract):
                raise NodeExecutionContractError("Final outputs do not match exact Node output contract")
            if set(normalized_evidence) != set(node.evidence_requirements):
                raise NodeExecutionContractError("Final evidence does not match exact Node requirements")
            output_artifacts = self._revalidate_artifacts_in_transaction(
                connection,
                run.project_ref,
                output_objects,
                output_artifacts,
            )
            evidence_artifacts = self._revalidate_artifacts_in_transaction(
                connection,
                run.project_ref,
                evidence_objects,
                evidence_artifacts,
            )
            for artifact in output_artifacts.values():
                if (
                    artifact.producer_run_ref != run.run_ref
                    or artifact.producer_attempt_id != attempt.run_attempt_id
                    or artifact.producer_fence != attempt.run_fence
                ):
                    raise NodeExecutionAuthorityError("Output Artifact lacks exact current Run provenance")
            now = self._database_now(connection)
            self._insert_bindings(connection, attempt.node_ref, "output", normalized_outputs, output_artifacts)
            self._insert_bindings(
                connection,
                attempt.node_ref,
                "evidence",
                normalized_evidence,
                evidence_artifacts,
            )
            self._complete_attempt(connection, attempt, now, "SUCCEEDED")
            succeeded = self._next_state(
                current,
                "SUCCEEDED",
                now,
                outputs=normalized_outputs,
                evidence=normalized_evidence,
            )
            self._append_state(connection, current, succeeded)
            run_attempt = self.runs._fetch_attempt(connection, run, attempt.run_attempt_id)
            all_objects = tuple(dict.fromkeys(output_objects + evidence_objects))
            self.events._append_in_transaction(
                connection,
                requesting_access,
                project_ref=run.project_ref,
                task_ref=task.task_ref,
                run_ref=run.run_ref,
                graph_ref=graph.graph_ref,
                node_ref=attempt.node_ref,
                event_type="NODE_FINISHED",
                idempotency_key=f"p009-nf-{idempotency_key}",
                actor_ref=attempt.owner_ref,
                object_refs=all_objects,
                metadata={"fence": attempt.fence, "state_version": succeeded.state_version},
                payload_ref=None,
                authority_attempt=run_attempt,
                require_run_authority=True,
            )
            self._refresh_ready(connection, run, task, graph)
            self._complete_run_if_ready(
                connection,
                requesting_access,
                run,
                task,
                graph,
            )
            self._record_transition(connection, succeeded, "FINALIZE", idempotency_key, semantic, attempt.attempt_id)
            connection.commit()
            return succeeded
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            if "injected" in str(exc):
                raise
            raise NodeExecutionConflictError("Node finalization conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def recover_expired_execution(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> tuple[NodeExecution, ...]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run, task, graph = self._context(connection, requesting_access, run_ref)
            if run.status != "RUNNING":
                raise NodeExecutionAuthorityError("Terminal Run cannot recover execution")
            self._sync_graph(connection, run, task, graph, {})
            now = self._database_now(connection)
            for current in self._ordered_current(connection, graph):
                if (
                    current.status in _ACTIVE_STATUSES
                    and current.lease_expires_at is not None
                    and current.lease_expires_at <= now
                    and current.current_attempt_id is not None
                ):
                    attempt = self._fetch_attempt(connection, current.node_ref, current.current_attempt_id)
                    self._complete_attempt(connection, attempt, current.lease_expires_at, "STALE")
                    stale = self._next_state(current, "STALE", now)
                    self._append_state(connection, current, stale)
            self._refresh_ready(connection, run, task, graph, include_stale=True)
            result = self._ordered_current(connection, graph)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def recoverExpiredExecution(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> tuple[NodeExecution, ...]:
        return self.recover_expired_execution(requesting_access, run_ref)

    def cancel_run(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
        *,
        idempotency_key: str,
        actor_ref: str,
        _run_event_metadata: Mapping[str, EventValue] | None = None,
    ) -> Run:
        _validate_key(idempotency_key, "idempotency_key")
        _validate_owner(actor_ref)
        run_event_metadata: Mapping[str, EventValue] = (
            {"source": "execution-service"}
            if _run_event_metadata is None
            else _run_event_metadata
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run, task, graph = self._context_allowing_no_graph(
                connection,
                requesting_access,
                run_ref,
            )
            events = self.events._fetch_verified_run_events(connection, run_ref)
            cancellation = tuple(event for event in events if event.event_type == "RUN_CANCELLED")
            if run.status == "CANCELLED":
                if (
                    len(cancellation) != 1
                    or cancellation[0].idempotency_key != idempotency_key
                    or cancellation[0].actor_ref != actor_ref
                    or dict(cancellation[0].metadata) != dict(run_event_metadata)
                ):
                    raise NodeExecutionConflictError("Run cancellation idempotency conflicts")
                connection.commit()
                return run
            if run.status in {"SUCCEEDED", "FAILED"}:
                raise NodeExecutionConflictError("Completed Run cannot be cancelled")
            now = self._database_now(connection)
            if graph is not None:
                self._sync_graph(connection, run, task, graph, {})
            current_nodes = () if graph is None else self._ordered_current(connection, graph)
            for current in current_nodes:
                if current.status in _TERMINAL_STATUSES:
                    continue
                if current.current_attempt_id is not None and current.status in _ACTIVE_STATUSES:
                    attempt = self._fetch_attempt(connection, current.node_ref, current.current_attempt_id)
                    self._complete_attempt(connection, attempt, now, "CANCELLED")
                cancelled_node = self._next_state(current, "CANCELLED", now)
                self._append_state(connection, current, cancelled_node)
                self.events._append_in_transaction(
                    connection,
                    requesting_access,
                    project_ref=run.project_ref,
                    task_ref=task.task_ref,
                    run_ref=run.run_ref,
                    graph_ref=current.node_ref.graph_ref,
                    node_ref=current.node_ref,
                    event_type="NODE_CANCELLED",
                    idempotency_key=f"p009-nc-{idempotency_key}-{current.node_ref.node_id}",
                    actor_ref=actor_ref,
                    object_refs=(),
                    metadata={"state_version": cancelled_node.state_version},
                    payload_ref=None,
                    authority_attempt=None,
                    require_run_authority=False,
                )
            cancelled_run = self.runs._request_run_cancellation_in_transaction(
                connection,
                requesting_access,
                run_ref,
            )
            self.events._append_in_transaction(
                connection,
                requesting_access,
                project_ref=run.project_ref,
                task_ref=task.task_ref,
                run_ref=run.run_ref,
                graph_ref=None,
                node_ref=None,
                event_type="RUN_CANCELLED",
                idempotency_key=idempotency_key,
                actor_ref=actor_ref,
                object_refs=(),
                metadata=run_event_metadata,
                payload_ref=None,
                authority_attempt=None,
                require_run_authority=False,
            )
            connection.commit()
            return cancelled_run
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def cancelRun(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
        *,
        idempotency_key: str,
        actor_ref: str,
    ) -> Run:
        return self.cancel_run(
            requesting_access,
            run_ref,
            idempotency_key=idempotency_key,
            actor_ref=actor_ref,
        )

    def get_node_execution(
        self,
        requesting_access: ProjectAccess,
        node_ref: NodeRef,
    ) -> NodeExecution:
        self._authorize(requesting_access, node_ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            result = self._fetch_execution(connection, node_ref)
            self._verify_node_run_completion(connection, result)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_node_executions(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> tuple[NodeExecution, ...]:
        self._authorize(requesting_access, run_ref.project_ref)
        graph = self.graphs.get_active_graph(requesting_access, run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            result = self._ordered_current(connection, graph)
            for execution in result:
                self._verify_node_run_completion(connection, execution)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_node_history(
        self,
        requesting_access: ProjectAccess,
        node_ref: NodeRef,
    ) -> tuple[NodeExecution, ...]:
        self._authorize(requesting_access, node_ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            history = self._fetch_history(connection, node_ref)
            self._verify_node_run_completion(connection, history[-1])
            connection.commit()
            return history
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_failures(
        self,
        requesting_access: ProjectAccess,
        node_ref: NodeRef,
    ) -> tuple[NodeExecutionFailure, ...]:
        self._authorize(requesting_access, node_ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            current = self._fetch_execution(connection, node_ref)
            self._verify_node_run_completion(connection, current)
            rows = connection.execute(
                """
                SELECT * FROM node_execution_failures
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
                ORDER BY created_at, attempt_id
                """,
                self._node_key(node_ref),
            ).fetchall()
            failures = tuple(self._failure_from_row(node_ref, row) for row in rows)
            connection.commit()
            return failures
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _verify_node_run_completion(
        self,
        connection: sqlite3.Connection,
        execution: NodeExecution,
    ) -> None:
        try:
            self.runs._fetch_run(connection, execution.run_ref)
        except RunError as exc:
            raise NodeExecutionIntegrityError(
                "Node Run completion evidence failed verification"
            ) from exc

    def _active_transition(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        operation: str,
        target_status: str,
        idempotency_key: str,
    ) -> NodeExecution:
        _validate_key(idempotency_key, "idempotency_key")
        self._authorize(access, attempt.node_ref.project_ref)
        semantic = _sha256({"attempt": attempt.record_sha256, "target_status": target_status})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = self._idempotent_state(connection, attempt.node_ref, operation, idempotency_key, semantic)
            if prior is not None:
                connection.commit()
                return prior
            current, _, _, _ = self._require_live_attempt(
                connection,
                access,
                attempt,
                allowed_statuses={"LEASED"},
            )
            now = self._database_now(connection)
            changed = self._next_state(
                current,
                target_status,
                now,
                attempt=attempt,
                lease_expires_at=current.lease_expires_at,
            )
            self._append_state(connection, current, changed)
            self._record_transition(connection, changed, operation, idempotency_key, semantic, attempt.attempt_id)
            connection.commit()
            return changed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _context(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        run_ref: RunRef,
    ) -> tuple[Run, Task, Graph]:
        run, task, graph = self._context_allowing_no_graph(
            connection,
            access,
            run_ref,
        )
        if graph is None:
            raise NodeExecutionIntegrityError("Run has no active Graph")
        return run, task, graph

    def _context_allowing_no_graph(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        run_ref: RunRef,
    ) -> tuple[Run, Task, Graph | None]:
        try:
            authorized_ref = self.projects._authorize(connection, access)
            if authorized_ref != run_ref.project_ref:
                raise ProjectScopeError("Project scope mismatch")
            self.projects._fetch_project(connection, authorized_ref)
        except ProjectScopeError as exc:
            raise NodeExecutionScopeError("Node execution Project scope mismatch") from exc
        run = self.runs._fetch_run(connection, run_ref)
        task = self.tasks._fetch_task(connection, run.task_ref)
        if not hmac.compare_digest(task.canonical_digest, run.task_digest):
            raise NodeExecutionIntegrityError("Run Task binding changed")
        head = connection.execute(
            "SELECT * FROM run_graph_heads WHERE project_id = ? AND run_id = ?",
            (run_ref.project_ref.value, run_ref.run_id),
        ).fetchone()
        if head is None:
            binding = connection.execute(
                """
                SELECT 1 FROM run_graph_bindings
                WHERE project_id = ? AND run_id = ? LIMIT 1
                """,
                (run_ref.project_ref.value, run_ref.run_id),
            ).fetchone()
            execution = connection.execute(
                """
                SELECT 1 FROM node_executions
                WHERE project_id = ? AND run_id = ? LIMIT 1
                """,
                (run_ref.project_ref.value, run_ref.run_id),
            ).fetchone()
            if binding is not None or execution is not None:
                raise NodeExecutionIntegrityError(
                    "Run Graph or Node state exists without an active Graph head"
                )
            return run, task, None
        graph_ref = GraphRef(
            run_ref.project_ref,
            cast(str, head["graph_id"]),
            cast(int, head["current_graph_revision"]),
        )
        try:
            graph = self.graphs._fetch_graph(connection, graph_ref)
            verified_head = self.graphs._verify_active_run_head(connection, graph)
            self.graphs._verify_run_binding_history(
                connection,
                run_ref,
                verified_head,
            )
        except GraphError as exc:
            raise NodeExecutionIntegrityError("Active Graph failed verification") from exc
        if graph.graph_ref != graph_ref or graph.run_ref != run_ref or graph.task_ref != task.task_ref:
            raise NodeExecutionIntegrityError("Execution context exact identities differ")
        return run, task, graph

    def _complete_run_if_ready(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        run: Run,
        task: Task,
        graph: Graph,
    ) -> Run:
        if run.status != "RUNNING" or not self._run_is_complete(connection, task, graph):
            return run
        acceptance_events = self._verified_acceptance_events(
            connection,
            run,
            task,
            graph,
        )
        acceptance_manifest = [
            self._acceptance_manifest_entry(acceptance_events[criterion])
            for criterion in sorted(acceptance_events)
        ]
        completion_event = self.events._append_in_transaction(
            connection,
            access,
            project_ref=run.project_ref,
            task_ref=task.task_ref,
            run_ref=run.run_ref,
            graph_ref=graph.graph_ref,
            node_ref=None,
            event_type="RUN_COMPLETED",
            idempotency_key=self._run_completion_event_key(graph),
            actor_ref="controller://execution-service",
            object_refs=(),
            metadata={
                "acceptance_evidence_sha256": _sha256(acceptance_manifest),
                "state_version": run.state_version + 1,
            },
            payload_ref=None,
            authority_attempt=None,
            require_run_authority=False,
        )
        recorded_at = self._database_now(connection)
        manifest_sha256 = self.runs._completion_manifest_sha256(
            run,
            graph_id=graph.graph_id,
            graph_revision=graph.revision,
            run_state_version=run.state_version + 1,
            acceptance_events=acceptance_manifest,
            completion_event_id=completion_event.event_ref.event_id,
            completion_event_record_sha256=completion_event.record_sha256,
            recorded_at=recorded_at,
        )
        if connection.execute(
            "SELECT 1 FROM run_completion_manifests WHERE project_id = ? AND run_id = ?",
            (run.project_ref.value, run.run_id),
        ).fetchone() is not None:
            raise NodeExecutionIntegrityError(
                "Live Run already has an immutable completion manifest"
            )
        connection.execute(
            """
            INSERT INTO run_completion_manifests (
                project_id, run_id, run_state_version,
                task_id, task_revision, task_digest,
                graph_id, graph_revision, acceptance_events_json,
                completion_event_id, completion_event_record_sha256,
                recorded_at, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.project_ref.value,
                run.run_id,
                run.state_version + 1,
                task.task_id,
                task.revision,
                task.canonical_digest,
                graph.graph_id,
                graph.revision,
                _json(acceptance_manifest),
                completion_event.event_ref.event_id,
                completion_event.record_sha256,
                recorded_at,
                manifest_sha256,
            ),
        )
        completed = self.runs._complete_run_in_transaction(
            connection,
            access,
            run.run_ref,
            completion_evidence_sha256=manifest_sha256,
        )
        if completed.state_version != run.state_version + 1:
            raise NodeExecutionIntegrityError(
                "Run completion state differs from terminal Event"
            )
        return completed

    def _sync_graph(
        self,
        connection: sqlite3.Connection,
        run: Run,
        task: Task,
        graph: Graph,
        condition_results: Mapping[str, bool],
    ) -> None:
        if not isinstance(condition_results, Mapping):
            raise NodeExecutionContractError("condition_results must be a mapping")
        self._record_conditions(connection, graph, condition_results)
        now = self._database_now(connection)
        old_rows = connection.execute(
            """
            SELECT graph_id, graph_revision, node_id FROM node_executions
            WHERE project_id = ? AND run_id = ? AND (graph_id != ? OR graph_revision != ?)
            """,
            (run.project_ref.value, run.run_id, graph.graph_id, graph.revision),
        ).fetchall()
        for row in old_rows:
            old_ref = NodeRef(
                GraphRef(run.project_ref, cast(str, row["graph_id"]), cast(int, row["graph_revision"])),
                cast(str, row["node_id"]),
            )
            old = self._fetch_execution(connection, old_ref)
            if old.status not in _TERMINAL_STATUSES and old.status != "STALE":
                if old.current_attempt_id is not None and old.status in _ACTIVE_STATUSES:
                    attempt = self._fetch_attempt(connection, old_ref, old.current_attempt_id)
                    self._complete_attempt(connection, attempt, now, "STALE")
                self._append_state(connection, old, self._next_state(old, "STALE", now))
        for node in graph.nodes:
            exists = connection.execute(
                """
                SELECT 1 FROM node_executions
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
                """,
                self._node_key(node.node_ref),
            ).fetchone()
            if exists is not None:
                continue
            created = NodeExecution(
                node.node_ref,
                run.run_ref,
                task.task_ref,
                task.canonical_digest,
                "CREATED",
                1,
                None,
                None,
                0,
                None,
                None,
                None,
                None,
                None,
                {},
                {},
                now,
                now,
            )
            self._insert_identity(connection, created, node.record_sha256)
            self._insert_initial_state(connection, created)
            queued = self._next_state(created, "QUEUED", now)
            self._append_state(connection, created, queued)
        if run.status == "CANCELLED":
            for current in self._ordered_current(connection, graph):
                if current.status not in _TERMINAL_STATUSES:
                    self._append_state(connection, current, self._next_state(current, "CANCELLED", now))
            return
        self._refresh_ready(connection, run, task, graph)

    def _refresh_ready(
        self,
        connection: sqlite3.Connection,
        run: Run,
        task: Task,
        graph: Graph,
        *,
        include_stale: bool = False,
    ) -> None:
        terminal = {
            item.node_ref: item.status
            for item in self._ordered_current(connection, graph)
            if item.status in _TERMINAL_STATUSES
        }
        conditions = self._condition_results(connection, graph)
        ready = set(graph.ready_set(terminal, conditions, task))
        now = self._database_now(connection)
        for current in self._ordered_current(connection, graph):
            if current.node_ref in ready and (
                current.status == "QUEUED" or (include_stale and current.status == "STALE")
            ):
                self._append_state(connection, current, self._next_state(current, "READY", now))

    def _require_live_attempt(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        allowed_statuses: set[str],
    ) -> tuple[NodeExecution, Run, Task, Graph]:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise NodeExecutionAuthorityError("NodeExecutionAttempt is required")
        run, task, graph = self._context(connection, access, attempt.run_ref)
        if graph.graph_ref != attempt.node_ref.graph_ref:
            raise NodeExecutionAuthorityError("Node attempt Graph revision is stale")
        current = self._fetch_execution(connection, attempt.node_ref)
        if (
            current.status not in allowed_statuses
            or current.current_attempt_id != attempt.attempt_id
            or current.current_fence != attempt.fence
            or current.current_owner_ref != attempt.owner_ref
            or current.current_run_attempt_id != attempt.run_attempt_id
            or current.current_run_fence != attempt.run_fence
        ):
            raise NodeExecutionAuthorityError("Node attempt is not current")
        persisted = self._fetch_attempt(connection, attempt.node_ref, attempt.attempt_id)
        if persisted != attempt:
            raise NodeExecutionAuthorityError("Node attempt evidence differs")
        now = self._database_now(connection)
        if current.lease_expires_at is None or current.lease_expires_at <= now:
            raise NodeExecutionAuthorityError("Node lease expired")
        run_attempt = self.runs._fetch_attempt(connection, run, attempt.run_attempt_id)
        try:
            self.runs.assert_current_run_authority_in_transaction(connection, access, run_attempt)
        except (RunAuthorityError, RunError) as exc:
            raise NodeExecutionAuthorityError("Node attempt Run authority is stale") from exc
        if run.status != "RUNNING":
            raise NodeExecutionAuthorityError("Terminal Run rejects Node authority")
        return current, run, task, graph

    def _run_is_complete(self, connection: sqlite3.Connection, task: Task, graph: Graph) -> bool:
        conditions = self._condition_results(connection, graph)
        executions = {item.node_ref: item for item in self._ordered_current(connection, graph)}
        for node in graph.nodes:
            if node.condition_ref is not None and conditions.get(node.condition_ref) is False:
                continue
            if executions[node.node_ref].status != "SUCCEEDED":
                return False
        criteria = self._verified_acceptance_criteria(
            connection,
            self.runs._fetch_run(connection, graph.run_ref),
            task,
            graph,
        )
        if not set(task.acceptance_criteria).issubset(criteria):
            return False
        output_keys = {
            cast(str, row["binding_key"])
            for row in connection.execute(
                """
                SELECT binding_key FROM node_execution_bindings
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND binding_kind = 'output'
                """,
                (graph.project_ref.value, graph.graph_id, graph.revision),
            ).fetchall()
        }
        return set(task.output_contract).issubset(output_keys)

    def _require_dependencies_satisfied(
        self,
        connection: sqlite3.Connection,
        task: Task,
        graph: Graph,
        node: Node,
    ) -> None:
        conditions = self._condition_results(connection, graph)
        if node.condition_ref is not None and conditions.get(node.condition_ref) is not True:
            raise NodeExecutionAuthorityError("Node condition is not currently satisfied")
        for dependency_ref in node.dependencies:
            dependency = self._node(graph, dependency_ref)
            if (
                dependency.condition_ref is not None
                and conditions.get(dependency.condition_ref) is False
            ):
                continue
            if self._fetch_execution(connection, dependency_ref).status != "SUCCEEDED":
                raise NodeExecutionAuthorityError(
                    "Node dependencies are not authoritatively satisfied"
                )
        terminal_states: dict[NodeRef, str] = {}
        for candidate in graph.nodes:
            status = self._fetch_execution(connection, candidate.node_ref).status
            if status in _TERMINAL_STATUSES:
                terminal_states[candidate.node_ref] = status
        try:
            ready = graph.ready_set(
                terminal_states,
                conditions,
                task,
            )
        except GraphError as exc:
            raise NodeExecutionAuthorityError(
                "Node readiness authority failed revalidation"
            ) from exc
        if node.node_ref not in ready:
            raise NodeExecutionAuthorityError(
                "Node is no longer ready under current Graph authority"
            )

    def _insert_identity(self, connection: sqlite3.Connection, execution: NodeExecution, node_sha: str) -> None:
        connection.execute(
            "INSERT INTO node_executions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                execution.project_ref.value,
                execution.run_ref.run_id,
                execution.task_ref.task_id,
                execution.task_ref.revision,
                execution.task_digest,
                execution.graph_ref.graph_id,
                execution.graph_ref.revision,
                execution.node_ref.node_id,
                node_sha,
                execution.created_at,
                execution.identity_sha256,
            ),
        )

    def _insert_initial_state(self, connection: sqlite3.Connection, execution: NodeExecution) -> None:
        self._insert_state(connection, execution)
        connection.execute(
            "INSERT INTO node_execution_heads VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (*self._node_key(execution.node_ref), execution.state_version, execution.state_sha256, execution.updated_at, self._head_sha(execution)),
        )

    def _append_state(
        self,
        connection: sqlite3.Connection,
        prior: NodeExecution,
        current: NodeExecution,
    ) -> None:
        self._insert_state(connection, current)
        updated = connection.execute(
            """
            UPDATE node_execution_heads SET current_state_version = ?, current_state_sha256 = ?,
                updated_at = ?, record_sha256 = ?
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
                AND current_state_version = ? AND current_state_sha256 = ?
                AND updated_at = ? AND record_sha256 = ?
            """,
            (
                current.state_version,
                current.state_sha256,
                current.updated_at,
                self._head_sha(current),
                *self._node_key(prior.node_ref),
                prior.state_version,
                prior.state_sha256,
                prior.updated_at,
                self._head_sha(prior),
            ),
        )
        if updated.rowcount != 1:
            raise NodeExecutionConflictError("Node state changed concurrently")

    def _insert_state(self, connection: sqlite3.Connection, execution: NodeExecution) -> None:
        connection.execute(
            """
            INSERT INTO node_execution_state_versions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                *self._node_key(execution.node_ref),
                execution.state_version,
                execution.status,
                execution.current_attempt_id,
                execution.current_attempt_number,
                execution.current_fence,
                execution.current_owner_ref,
                execution.current_run_attempt_id,
                execution.current_run_fence,
                execution.lease_expires_at,
                execution.waiting_reason,
                execution.updated_at,
                execution.state_sha256,
            ),
        )

    def _next_state(
        self,
        prior: NodeExecution,
        status: str,
        now: str,
        *,
        attempt: NodeExecutionAttempt | None = None,
        lease_expires_at: str | None = None,
        waiting_reason: str | None = None,
        outputs: Mapping[str, str] | None = None,
        evidence: Mapping[str, str] | None = None,
    ) -> NodeExecution:
        retain_attempt = attempt is not None or prior.current_attempt_id is not None
        source_attempt_id = attempt.attempt_id if attempt is not None else prior.current_attempt_id
        source_attempt_number = attempt.attempt_number if attempt is not None else prior.current_attempt_number
        source_fence = attempt.fence if attempt is not None else prior.current_fence
        source_run_attempt_id = attempt.run_attempt_id if attempt is not None else prior.current_run_attempt_id
        source_run_fence = attempt.run_fence if attempt is not None else prior.current_run_fence
        active = status in _ACTIVE_STATUSES
        return NodeExecution(
            prior.node_ref,
            prior.run_ref,
            prior.task_ref,
            prior.task_digest,
            status,
            prior.state_version + 1,
            source_attempt_id if retain_attempt else None,
            source_attempt_number if retain_attempt else None,
            source_fence if retain_attempt else 0,
            (attempt.owner_ref if attempt is not None else prior.current_owner_ref) if active else None,
            source_run_attempt_id if retain_attempt else None,
            source_run_fence if retain_attempt else None,
            lease_expires_at if active else None,
            waiting_reason if status == "WAITING_EXTERNAL" else None,
            {} if outputs is None else outputs,
            {} if evidence is None else evidence,
            prior.created_at,
            now,
        )

    def _fetch_execution(self, connection: sqlite3.Connection, node_ref: NodeRef) -> NodeExecution:
        history = self._fetch_history(connection, node_ref)
        return history[-1]

    def _fetch_history(self, connection: sqlite3.Connection, node_ref: NodeRef) -> tuple[NodeExecution, ...]:
        identity = connection.execute(
            """
            SELECT * FROM node_executions
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
            """,
            self._node_key(node_ref),
        ).fetchone()
        if identity is None:
            raise NodeExecutionNotFoundError("Node execution not found")
        state_rows = connection.execute(
            """
            SELECT * FROM node_execution_state_versions
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
            ORDER BY state_version
            """,
            self._node_key(node_ref),
        ).fetchall()
        if tuple(row["state_version"] for row in state_rows) != tuple(range(1, len(state_rows) + 1)):
            raise NodeExecutionIntegrityError("Node state history is not gap-free")
        outputs, evidence = self._fetch_bindings(connection, node_ref)
        history = tuple(
            self._state_from_row(identity, row, outputs if row["status"] == "SUCCEEDED" else {}, evidence if row["status"] == "SUCCEEDED" else {})
            for row in state_rows
        )
        if not history:
            raise NodeExecutionIntegrityError("Node execution has no state")
        self._verify_state_lineage(history)
        self._verify_attempt_history(connection, node_ref, history)
        head = connection.execute(
            """
            SELECT * FROM node_execution_heads
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
            """,
            self._node_key(node_ref),
        ).fetchone()
        latest = history[-1]
        if (
            head is None
            or head["current_state_version"] != latest.state_version
            or head["current_state_sha256"] != latest.state_sha256
            or head["updated_at"] != latest.updated_at
        ):
            raise NodeExecutionIntegrityError("Node state head differs from history")
        self._verify_digest(self._head_sha(latest), head["record_sha256"], "Node state head")
        self._verify_identity(connection, identity, latest)
        return history

    @staticmethod
    def _verify_state_lineage(history: tuple[NodeExecution, ...]) -> None:
        allowed = {
            "CREATED": {"QUEUED"},
            "QUEUED": {"READY", "CANCELLED", "STALE"},
            "READY": {"LEASED", "CANCELLED", "STALE"},
            "LEASED": {"LEASED", "RUNNING", "FAILED", "CANCELLED", "STALE"},
            "RUNNING": {"RUNNING", "WAITING_EXTERNAL", "SUCCEEDED", "FAILED", "CANCELLED", "STALE"},
            "WAITING_EXTERNAL": {"WAITING_EXTERNAL", "SUCCEEDED", "FAILED", "CANCELLED", "STALE"},
            "STALE": {"READY", "CANCELLED"},
            "SUCCEEDED": set(),
            "FAILED": set(),
            "CANCELLED": set(),
        }
        first = history[0]
        if (
            first.status != "CREATED"
            or first.state_version != 1
            or first.current_attempt_id is not None
            or first.current_fence != 0
        ):
            raise NodeExecutionIntegrityError("Node initial state is invalid")
        for previous, current in zip(history, history[1:]):
            if (
                current.node_ref != previous.node_ref
                or current.run_ref != previous.run_ref
                or current.task_ref != previous.task_ref
                or current.task_digest != previous.task_digest
                or current.created_at != previous.created_at
                or current.state_version != previous.state_version + 1
                or current.updated_at < previous.updated_at
                or current.status not in allowed[previous.status]
            ):
                raise NodeExecutionIntegrityError("Node state transition lineage is invalid")
            fence_delta = current.current_fence - previous.current_fence
            if fence_delta == 1:
                if (
                    previous.status != "READY"
                    or current.status != "LEASED"
                    or current.current_attempt_id == previous.current_attempt_id
                    or current.current_attempt_number
                    != (previous.current_attempt_number or 0) + 1
                ):
                    raise NodeExecutionIntegrityError("Node lease fence lineage is invalid")
            elif fence_delta == 0:
                if (
                    current.current_attempt_id != previous.current_attempt_id
                    or current.current_attempt_number != previous.current_attempt_number
                    or current.current_run_attempt_id != previous.current_run_attempt_id
                    or current.current_run_fence != previous.current_run_fence
                ):
                    raise NodeExecutionIntegrityError(
                        "Node attempt changed without a new fence"
                    )
            else:
                raise NodeExecutionIntegrityError("Node fence regressed or skipped")

    def _verify_attempt_history(
        self,
        connection: sqlite3.Connection,
        node_ref: NodeRef,
        history: tuple[NodeExecution, ...],
    ) -> None:
        rows = connection.execute(
            """
            SELECT * FROM node_execution_attempts
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
            ORDER BY attempt_number
            """,
            self._node_key(node_ref),
        ).fetchall()
        if tuple(row["attempt_number"] for row in rows) != tuple(range(1, len(rows) + 1)):
            raise NodeExecutionIntegrityError("Node attempt numbers are not gap-free")
        if tuple(row["fence"] for row in rows) != tuple(range(1, len(rows) + 1)):
            raise NodeExecutionIntegrityError("Node attempt fences are not gap-free")
        attempts = {
            attempt.attempt_id: attempt
            for attempt in (
                self._fetch_attempt(connection, node_ref, cast(str, row["attempt_id"]))
                for row in rows
            )
        }
        if history[-1].current_fence != len(attempts):
            raise NodeExecutionIntegrityError("Node fence differs from attempt history")
        for state in history:
            if state.current_attempt_id is None:
                continue
            attempt = attempts.get(state.current_attempt_id)
            if (
                attempt is None
                or state.current_attempt_number != attempt.attempt_number
                or state.current_fence != attempt.fence
                or state.current_run_attempt_id != attempt.run_attempt_id
                or state.current_run_fence != attempt.run_fence
            ):
                raise NodeExecutionIntegrityError("Node state attempt evidence differs")
        completion_rows = connection.execute(
            """
            SELECT * FROM node_execution_attempt_completions
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
            """,
            self._node_key(node_ref),
        ).fetchall()
        completions: set[str] = set()
        for row in completion_rows:
            attempt_id = cast(str, row["attempt_id"])
            if attempt_id not in attempts:
                raise NodeExecutionIntegrityError("Node completion attempt is missing")
            expected = _sha256(
                {
                    "attempt_id": attempt_id,
                    "completed_at": row["completed_at"],
                    "node_ref": node_ref.value,
                    "outcome": row["outcome"],
                }
            )
            self._verify_digest(expected, row["record_sha256"], "Node attempt completion")
            completions.add(attempt_id)
        latest = history[-1]
        live_id = latest.current_attempt_id if latest.status in _ACTIVE_STATUSES else None
        if live_id in completions:
            raise NodeExecutionIntegrityError("Live Node attempt is already completed")
        if set(attempts) - ({live_id} if live_id is not None else set()) != completions:
            raise NodeExecutionIntegrityError("Closed Node attempt lacks completion evidence")

    def _state_from_row(
        self,
        identity: sqlite3.Row,
        row: sqlite3.Row,
        outputs: Mapping[str, str],
        evidence: Mapping[str, str],
    ) -> NodeExecution:
        try:
            project_ref = ProjectRef(cast(str, identity["project_id"]))
            graph_ref = GraphRef(project_ref, cast(str, identity["graph_id"]), cast(int, identity["graph_revision"]))
            execution = NodeExecution(
                NodeRef(graph_ref, cast(str, identity["node_id"])),
                RunRef(project_ref, cast(str, identity["run_id"])),
                TaskRef(project_ref, cast(str, identity["task_id"]), cast(int, identity["task_revision"])),
                cast(str, identity["task_digest"]),
                cast(str, row["status"]),
                cast(int, row["state_version"]),
                cast(str | None, row["current_attempt_id"]),
                cast(int | None, row["current_attempt_number"]),
                cast(int, row["current_fence"]),
                cast(str | None, row["current_owner_ref"]),
                cast(str | None, row["current_run_attempt_id"]),
                cast(int | None, row["current_run_fence"]),
                cast(str | None, row["lease_expires_at"]),
                cast(str | None, row["waiting_reason"]),
                outputs,
                evidence,
                cast(str, identity["created_at"]),
                cast(str, row["updated_at"]),
            )
        except (TypeError, ValueError, KeyError, NodeExecutionError) as exc:
            raise NodeExecutionIntegrityError("Persisted Node execution is malformed") from exc
        self._verify_digest(execution.state_sha256, row["record_sha256"], "Node state")
        return execution

    def _verify_identity(self, connection: sqlite3.Connection, row: sqlite3.Row, execution: NodeExecution) -> None:
        self._verify_digest(execution.identity_sha256, row["record_sha256"], "Node execution identity")
        graph = self.graphs._fetch_graph(connection, execution.graph_ref)
        node = self._node(graph, execution.node_ref)
        self._verify_digest(node.record_sha256, row["node_record_sha256"], "Node execution Node binding")
        try:
            run = self.runs._fetch_run(connection, execution.run_ref)
        except RunError as exc:
            raise NodeExecutionIntegrityError(
                "Node execution Run evidence failed verification"
            ) from exc
        if run.task_ref != execution.task_ref or not hmac.compare_digest(run.task_digest, execution.task_digest):
            raise NodeExecutionIntegrityError("Node execution Run Task binding differs")

    def _insert_attempt(self, connection: sqlite3.Connection, attempt: NodeExecutionAttempt) -> None:
        connection.execute(
            "INSERT INTO node_execution_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                attempt.node_ref.project_ref.value,
                attempt.run_ref.run_id,
                attempt.node_ref.graph_ref.graph_id,
                attempt.node_ref.graph_ref.revision,
                attempt.node_ref.node_id,
                attempt.attempt_id,
                attempt.task_ref.task_id,
                attempt.task_ref.revision,
                attempt.task_digest,
                attempt.attempt_number,
                attempt.fence,
                attempt.owner_ref,
                attempt.run_attempt_id,
                attempt.run_fence,
                attempt.lease_acquired_at,
                attempt.lease_expires_at,
                attempt.record_sha256,
            ),
        )

    def _fetch_attempt(self, connection: sqlite3.Connection, node_ref: NodeRef, attempt_id: str) -> NodeExecutionAttempt:
        row = connection.execute(
            """
            SELECT * FROM node_execution_attempts
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ? AND attempt_id = ?
            """,
            (*self._node_key(node_ref), attempt_id),
        ).fetchone()
        if row is None:
            raise NodeExecutionAuthorityError("Node attempt not found")
        try:
            attempt = NodeExecutionAttempt(
                cast(str, row["attempt_id"]),
                node_ref,
                RunRef(node_ref.project_ref, cast(str, row["run_id"])),
                TaskRef(node_ref.project_ref, cast(str, row["task_id"]), cast(int, row["task_revision"])),
                cast(str, row["task_digest"]),
                cast(int, row["attempt_number"]),
                cast(int, row["fence"]),
                cast(str, row["owner_ref"]),
                cast(str, row["run_attempt_id"]),
                cast(int, row["run_fence"]),
                cast(str, row["lease_acquired_at"]),
                cast(str, row["lease_expires_at"]),
            )
        except (TypeError, ValueError, NodeExecutionError) as exc:
            raise NodeExecutionIntegrityError("Persisted Node attempt is malformed") from exc
        self._verify_digest(attempt.record_sha256, row["record_sha256"], "Node attempt")
        return attempt

    def _complete_attempt(
        self,
        connection: sqlite3.Connection,
        attempt: NodeExecutionAttempt,
        completed_at: str,
        outcome: str,
    ) -> None:
        record = _sha256(
            {
                "attempt_id": attempt.attempt_id,
                "completed_at": completed_at,
                "node_ref": attempt.node_ref.value,
                "outcome": outcome,
            }
        )
        connection.execute(
            "INSERT INTO node_execution_attempt_completions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (*self._node_key(attempt.node_ref), attempt.attempt_id, completed_at, outcome, record),
        )

    def _insert_failure(self, connection: sqlite3.Connection, failure: NodeExecutionFailure) -> None:
        connection.execute(
            "INSERT INTO node_execution_failures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                *self._node_key(failure.node_ref),
                failure.attempt_id,
                failure.category,
                failure.reason,
                _json(list(failure.evidence_refs)),
                int(failure.retry_possible),
                failure.created_at,
                failure.record_sha256,
            ),
        )

    def _failure_from_row(self, node_ref: NodeRef, row: sqlite3.Row) -> NodeExecutionFailure:
        try:
            failure = NodeExecutionFailure(
                node_ref,
                cast(str, row["attempt_id"]),
                cast(str, row["category"]),
                cast(str, row["reason"]),
                tuple(cast(list[str], json.loads(cast(str, row["evidence_refs_json"])))),
                bool(row["retry_possible"]),
                cast(str, row["created_at"]),
            )
        except (TypeError, ValueError, json.JSONDecodeError, NodeExecutionError) as exc:
            raise NodeExecutionIntegrityError("Persisted Node failure is malformed") from exc
        self._verify_digest(failure.record_sha256, row["record_sha256"], "Node failure")
        return failure

    def _normalize_named_objects(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        values: Mapping[str, ExecutionObjectRef],
    ) -> tuple[Mapping[str, str], tuple[ExecutionObjectRef, ...], dict[str, Artifact]]:
        if not isinstance(values, Mapping) or len(values) > 64:
            raise NodeExecutionContractError("Named execution objects must be a bounded mapping")
        normalized: dict[str, str] = {}
        objects: list[ExecutionObjectRef] = []
        artifacts: dict[str, Artifact] = {}
        for key, value in values.items():
            _validate_key(key, "execution object key")
            refs, found = self._normalize_objects(access, project_ref, (value,))
            normalized[key] = refs[0]
            objects.append(value)
            artifacts.update(found)
        return MappingProxyType(dict(sorted(normalized.items()))), tuple(objects), artifacts

    def _normalize_objects(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        values: Sequence[ExecutionObjectRef],
    ) -> tuple[tuple[str, ...], dict[str, Artifact]]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or len(values) > 64:
            raise NodeExecutionContractError("Execution object refs must be a bounded sequence")
        refs: list[str] = []
        artifacts: dict[str, Artifact] = {}
        for value in values:
            if isinstance(value, ArtifactRef):
                if value.project_ref != project_ref:
                    raise NodeExecutionScopeError("Execution Artifact Project scope mismatch")
                try:
                    artifact = self.artifacts.get_artifact(access, value)
                except ArtifactError as exc:
                    raise NodeExecutionContractError("Execution ArtifactRef is invalid") from exc
                refs.append(value.value)
                artifacts[value.value] = artifact
            elif isinstance(value, ContentRef):
                refs.append(value.value)
            else:
                raise NodeExecutionContractError("Execution object must be ArtifactRef or ContentRef")
        return tuple(refs), artifacts

    def _revalidate_artifacts_in_transaction(
        self,
        connection: sqlite3.Connection,
        project_ref: ProjectRef,
        values: Sequence[ExecutionObjectRef],
        expected: Mapping[str, Artifact],
    ) -> dict[str, Artifact]:
        verified: dict[str, Artifact] = {}
        for value in values:
            if isinstance(value, ContentRef):
                continue
            if not isinstance(value, ArtifactRef) or value.project_ref != project_ref:
                raise NodeExecutionScopeError("Execution Artifact Project scope mismatch")
            try:
                artifact = self.artifacts._fetch_artifact(connection, value)
            except ArtifactError as exc:
                raise NodeExecutionIntegrityError(
                    "Execution Artifact failed transactional revalidation"
                ) from exc
            prior = expected.get(value.value)
            if prior is None or not hmac.compare_digest(
                artifact.record_sha256,
                prior.record_sha256,
            ):
                raise NodeExecutionIntegrityError(
                    "Execution Artifact changed before finalization"
                )
            verified[value.value] = artifact
        return verified

    def _insert_bindings(
        self,
        connection: sqlite3.Connection,
        node_ref: NodeRef,
        kind: str,
        bindings: Mapping[str, str],
        artifacts: Mapping[str, Artifact],
    ) -> None:
        for key, reference in bindings.items():
            artifact = artifacts.get(reference)
            record = _sha256(
                {
                    "artifact_record_sha256": None if artifact is None else artifact.record_sha256,
                    "binding_key": key,
                    "binding_kind": kind,
                    "node_ref": node_ref.value,
                    "object_ref": reference,
                }
            )
            connection.execute(
                "INSERT INTO node_execution_bindings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    *self._node_key(node_ref),
                    kind,
                    key,
                    reference,
                    None if artifact is None else artifact.artifact_id,
                    None if artifact is None else artifact.revision,
                    None if artifact is None else artifact.record_sha256,
                    record,
                ),
            )

    def _fetch_bindings(
        self,
        connection: sqlite3.Connection,
        node_ref: NodeRef,
    ) -> tuple[Mapping[str, str], Mapping[str, str]]:
        rows = connection.execute(
            """
            SELECT * FROM node_execution_bindings
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
            ORDER BY binding_kind, binding_key
            """,
            self._node_key(node_ref),
        ).fetchall()
        outputs: dict[str, str] = {}
        evidence: dict[str, str] = {}
        for row in rows:
            reference = cast(str, row["object_ref"])
            artifact_sha = cast(str | None, row["artifact_record_sha256"])
            expected = _sha256(
                {
                    "artifact_record_sha256": artifact_sha,
                    "binding_key": row["binding_key"],
                    "binding_kind": row["binding_kind"],
                    "node_ref": node_ref.value,
                    "object_ref": reference,
                }
            )
            self._verify_digest(expected, row["record_sha256"], "Node binding")
            if artifact_sha is not None:
                matched = _ARTIFACT_PATTERN.fullmatch(reference)
                if matched is None:
                    raise NodeExecutionIntegrityError("Artifact binding identity is malformed")
                artifact = self.artifacts._fetch_artifact(
                    connection,
                    ArtifactRef(node_ref.project_ref, matched.group(2), int(matched.group(3))),
                )
                self._verify_digest(artifact.record_sha256, artifact_sha, "Node Artifact binding")
            elif _CONTENT_PATTERN.fullmatch(reference) is None:
                raise NodeExecutionIntegrityError("Content binding identity is malformed")
            target = outputs if row["binding_kind"] == "output" else evidence
            if row["binding_kind"] not in {"output", "evidence"}:
                raise NodeExecutionIntegrityError("Node binding kind is malformed")
            target[cast(str, row["binding_key"])] = reference
        return MappingProxyType(outputs), MappingProxyType(evidence)

    def _record_conditions(
        self,
        connection: sqlite3.Connection,
        graph: Graph,
        values: Mapping[str, bool],
    ) -> None:
        known = {node.condition_ref for node in graph.nodes if node.condition_ref is not None}
        now = self._database_now(connection)
        for reference, result in values.items():
            if reference not in known or not isinstance(result, bool):
                raise NodeExecutionContractError("Condition result is unknown or malformed")
            record = _sha256(
                {
                    "condition_ref": reference,
                    "graph_ref": graph.graph_ref.value,
                    "recorded_at": now,
                    "result": result,
                }
            )
            prior = connection.execute(
                """
                SELECT * FROM node_condition_results
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND condition_ref = ?
                """,
                (graph.project_ref.value, graph.graph_id, graph.revision, reference),
            ).fetchone()
            if prior is None:
                connection.execute(
                    "INSERT INTO node_condition_results VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (graph.project_ref.value, graph.graph_id, graph.revision, reference, int(result), now, record),
                )
            elif bool(prior["result"]) != result:
                raise NodeExecutionConflictError("Condition result is immutable")

    def _condition_results(self, connection: sqlite3.Connection, graph: Graph) -> dict[str, bool]:
        rows = connection.execute(
            """
            SELECT * FROM node_condition_results
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ?
            """,
            (graph.project_ref.value, graph.graph_id, graph.revision),
        ).fetchall()
        result: dict[str, bool] = {}
        for row in rows:
            expected = _sha256(
                {
                    "condition_ref": row["condition_ref"],
                    "graph_ref": graph.graph_ref.value,
                    "recorded_at": row["recorded_at"],
                    "result": bool(row["result"]),
                }
            )
            self._verify_digest(expected, row["record_sha256"], "Node condition result")
            result[cast(str, row["condition_ref"])] = bool(row["result"])
        return result

    def _verified_acceptance_criteria(
        self,
        connection: sqlite3.Connection,
        run: Run,
        task: Task,
        graph: Graph,
    ) -> set[str]:
        return set(
            self._verified_acceptance_events(connection, run, task, graph)
        )

    def _verified_acceptance_events(
        self,
        connection: sqlite3.Connection,
        run: Run,
        task: Task,
        graph: Graph,
    ) -> dict[str, Event]:
        events = self.events._fetch_verified_run_events(connection, run.run_ref)
        current: dict[str, Event] = {}
        current_keys: set[str] = set()
        for event in events:
            if event.event_type != "RUN_ACCEPTANCE_RECORDED":
                continue
            metadata = dict(event.metadata)
            if (
                event.task_ref != task.task_ref
                or event.run_ref != run.run_ref
                or event.graph_ref is None
                or event.node_ref is not None
                or set(metadata) != {
                    "authority_attempt_id",
                    "authority_fence",
                    "criterion",
                    "request_idempotency_key",
                }
                or not isinstance(metadata["authority_attempt_id"], str)
                or not isinstance(metadata["authority_fence"], int)
                or isinstance(metadata["authority_fence"], bool)
                or not isinstance(metadata["criterion"], str)
                or not isinstance(metadata["request_idempotency_key"], str)
                or len(event.object_refs) != 1
                or _ARTIFACT_PATTERN.fullmatch(event.object_refs[0]) is None
            ):
                raise NodeExecutionIntegrityError(
                    "Run acceptance Event evidence is malformed"
                )
            criterion = metadata["criterion"]
            request_key = metadata["request_idempotency_key"]
            try:
                _validate_key(request_key, "Run acceptance request idempotency key")
                authority = self.runs._fetch_attempt(
                    connection,
                    run,
                    metadata["authority_attempt_id"],
                )
            except (NodeExecutionError, RunError) as exc:
                raise NodeExecutionIntegrityError(
                    "Run acceptance authority evidence is malformed"
                ) from exc
            if (
                criterion not in task.acceptance_criteria
                or event.actor_ref != authority.owner_ref
                or metadata["authority_fence"] != authority.fence
                or event.idempotency_key
                != self._acceptance_event_key(event.graph_ref, request_key)
            ):
                raise NodeExecutionIntegrityError(
                    "Run acceptance Event evidence differs"
                )
            if event.graph_ref != graph.graph_ref:
                continue
            if criterion in current or request_key in current_keys:
                raise NodeExecutionIntegrityError(
                    "Current Graph has conflicting Run acceptance evidence"
                )
            current[criterion] = event
            current_keys.add(request_key)
        return current

    @staticmethod
    def _acceptance_manifest_entry(event: Event) -> dict[str, object]:
        return {
            "actor_ref": event.actor_ref,
            "authority_attempt_id": event.metadata["authority_attempt_id"],
            "authority_fence": event.metadata["authority_fence"],
            "criterion": event.metadata["criterion"],
            "event_id": event.event_ref.event_id,
            "event_record_sha256": event.record_sha256,
            "evidence_ref": event.object_refs[0],
            "idempotency_key": event.metadata["request_idempotency_key"],
        }

    @staticmethod
    def _acceptance_event_key(graph: Graph | GraphRef, idempotency_key: str) -> str:
        graph_ref = graph.graph_ref if isinstance(graph, Graph) else graph
        return RunService._acceptance_event_key(
            graph_ref.graph_id,
            graph_ref.revision,
            idempotency_key,
        )

    @staticmethod
    def _run_completion_event_key(graph: Graph) -> str:
        return f"p009-rc-{_sha256(graph.graph_ref.value)[:32]}"

    def _record_transition(
        self,
        connection: sqlite3.Connection,
        state: NodeExecution,
        operation: str,
        key: str,
        semantic: str,
        attempt_id: str | None,
    ) -> None:
        record = _sha256(
            {
                "idempotency_key": key,
                "node_ref": state.node_ref.value,
                "operation": operation,
                "result_attempt_id": attempt_id,
                "result_state_version": state.state_version,
                "semantic_sha256": semantic,
            }
        )
        connection.execute(
            "INSERT INTO node_transition_idempotency VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*self._node_key(state.node_ref), operation, key, semantic, state.state_version, attempt_id, record),
        )

    def _idempotent_state(
        self,
        connection: sqlite3.Connection,
        node_ref: NodeRef,
        operation: str,
        key: str,
        semantic: str,
    ) -> NodeExecution | None:
        row = self._idempotency_row(connection, node_ref, operation, key)
        if row is None:
            return None
        self._verify_idempotency(node_ref, row, semantic)
        history = self._fetch_history(connection, node_ref)
        version = cast(int, row["result_state_version"])
        if version < 1 or version > len(history):
            raise NodeExecutionIntegrityError("Node idempotency result state is missing")
        return history[version - 1]

    def _idempotent_attempt(
        self,
        connection: sqlite3.Connection,
        node_ref: NodeRef,
        operation: str,
        key: str,
        semantic: str,
    ) -> NodeExecutionAttempt | None:
        row = self._idempotency_row(connection, node_ref, operation, key)
        if row is None:
            return None
        self._verify_idempotency(node_ref, row, semantic)
        attempt_id = cast(str | None, row["result_attempt_id"])
        if attempt_id is None:
            raise NodeExecutionIntegrityError("Node lease idempotency lacks attempt")
        return self._fetch_attempt(connection, node_ref, attempt_id)

    def _idempotency_row(
        self,
        connection: sqlite3.Connection,
        node_ref: NodeRef,
        operation: str,
        key: str,
    ) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            connection.execute(
                """
                SELECT * FROM node_transition_idempotency
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
                    AND operation = ? AND idempotency_key = ?
                """,
                (*self._node_key(node_ref), operation, key),
            ).fetchone(),
        )

    def _verify_idempotency(self, node_ref: NodeRef, row: sqlite3.Row, semantic: str) -> None:
        if not hmac.compare_digest(cast(str, row["semantic_sha256"]), semantic):
            raise NodeExecutionConflictError("Node transition idempotency semantics conflict")
        expected = _sha256(
            {
                "idempotency_key": row["idempotency_key"],
                "node_ref": node_ref.value,
                "operation": row["operation"],
                "result_attempt_id": row["result_attempt_id"],
                "result_state_version": row["result_state_version"],
                "semantic_sha256": row["semantic_sha256"],
            }
        )
        self._verify_digest(expected, row["record_sha256"], "Node transition idempotency")

    def _ordered_current(self, connection: sqlite3.Connection, graph: Graph) -> tuple[NodeExecution, ...]:
        by_ref = {node.node_ref: self._fetch_execution(connection, node.node_ref) for node in graph.nodes}
        return tuple(by_ref[node_ref] for node_ref in graph.topological_order())

    def _next_attempt_number(self, connection: sqlite3.Connection, node_ref: NodeRef) -> int:
        value = connection.execute(
            """
            SELECT COALESCE(MAX(attempt_number), 0) + 1 FROM node_execution_attempts
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
            """,
            self._node_key(node_ref),
        ).fetchone()[0]
        return cast(int, value)

    @staticmethod
    def _node(graph: Graph, node_ref: NodeRef) -> Node:
        node = next((candidate for candidate in graph.nodes if candidate.node_ref == node_ref), None)
        if node is None:
            raise NodeExecutionAuthorityError("Node is not in exact Graph")
        return node

    @staticmethod
    def _node_key(node_ref: NodeRef) -> tuple[str, str, int, str]:
        return (
            node_ref.project_ref.value,
            node_ref.graph_ref.graph_id,
            node_ref.graph_ref.revision,
            node_ref.node_id,
        )

    @staticmethod
    def _head_sha(execution: NodeExecution) -> str:
        return _sha256(
            {
                "current_state_sha256": execution.state_sha256,
                "current_state_version": execution.state_version,
                "node_ref": execution.node_ref.value,
                "updated_at": execution.updated_at,
            }
        )

    @staticmethod
    def _freeze_text(values: Sequence[str], name: str, limit: int) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise NodeExecutionContractError(f"{name} must be a sequence")
        copied = tuple(values)
        if len(copied) > limit or not all(
            isinstance(value, str) and value and len(value.encode()) <= 512 for value in copied
        ):
            raise NodeExecutionContractError(f"{name} is malformed or unbounded")
        return tuple(sorted(set(copied)))

    @staticmethod
    def _validate_lease_seconds(value: int | float) -> float:
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0.01
            or value > 86400
        ):
            raise NodeExecutionContractError("Node lease duration is out of bounds")
        return float(value)

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectScopeError as exc:
            raise NodeExecutionScopeError("Node execution Project scope mismatch") from exc

    @staticmethod
    def _database_now(connection: sqlite3.Connection) -> str:
        value = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')").fetchone()[0]
        return _validate_timestamp(value, "database_now")

    @staticmethod
    def _verify_digest(expected: str, persisted: object, label: str) -> None:
        if (
            not isinstance(persisted, str)
            or _SHA256_PATTERN.fullmatch(persisted) is None
            or not hmac.compare_digest(expected, persisted)
        ):
            raise NodeExecutionIntegrityError(f"{label} failed integrity verification")
