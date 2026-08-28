"""Durable Run identity, immutable attempts, leases, and fencing for P0-05."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import cast
from uuid import uuid4

from .project import ProjectAccess, ProjectRef, ProjectScopeError, ProjectStore
from .task import TaskRef, TaskRevisionService


_RUN_ID_PATTERN = re.compile(r"run_[0-9a-f]{32}")
_ATTEMPT_ID_PATTERN = re.compile(r"att_[0-9a-f]{32}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_OWNER_REF_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_OUTCOME_PATTERN = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
_RUN_STATUSES = {"PENDING", "RUNNING", "CANCELLED"}


class RunError(Exception):
    """Base class for durable Run failures."""


class RunContractError(RunError):
    """A Run, attempt, owner, or lease contract is malformed."""


class RunScopeError(RunError):
    """A Run operation crossed its authenticated Project boundary."""


class RunNotFoundError(RunError):
    """A requested Run does not exist in the authenticated Project."""


class RunConflictError(RunError):
    """A Run identity or immutable state transition conflicts."""


class RunIntegrityError(RunError):
    """Persisted Run or attempt evidence failed integrity verification."""


class RunAuthorityError(RunError):
    """An executor does not hold current live fenced Run authority."""


class RunLeaseConflictError(RunAuthorityError):
    """A different current live lease already owns the Run."""


class RunCancelledError(RunAuthorityError):
    """A durable cancellation marker prevents execution authority."""


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


def _validate_timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise RunContractError(f"{field_name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RunContractError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RunContractError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        )
    return value


def _validate_optional_timestamp(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _validate_timestamp(value, field_name)


def _validate_owner_ref(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 576
        or _OWNER_REF_PATTERN.fullmatch(value) is None
    ):
        raise RunContractError("Run owner reference is malformed or unbounded")
    return value


def _validate_lease_seconds(value: object) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0.01
        or value > 86_400
    ):
        raise RunContractError("lease_seconds must be finite and between 0.01 and 86400")
    return float(value)


@dataclass(frozen=True, order=True)
class RunRef:
    """Exact identity of one durable Run in one Project."""

    project_ref: ProjectRef
    run_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.run_id, str) or _RUN_ID_PATTERN.fullmatch(self.run_id) is None:
            raise RunContractError("Run identity is malformed")


@dataclass(frozen=True)
class Run:
    """One exact Task-bound Run and its latest append-only authority state."""

    run_ref: RunRef
    task_ref: TaskRef
    task_digest: str
    status: str
    state_version: int
    current_attempt_id: str | None
    current_attempt_number: int | None
    current_fence: int
    current_owner_ref: str | None
    lease_expires_at: str | None
    cancellation_requested_at: str | None
    created_at: str
    updated_at: str
    identity_sha256: str = field(init=False)
    state_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.run_ref, RunRef):
            raise TypeError("run_ref must be RunRef")
        if not isinstance(self.task_ref, TaskRef):
            raise TypeError("task_ref must be TaskRef")
        if self.task_ref.project_ref != self.run_ref.project_ref:
            raise RunContractError("Run and Task Project scope differ")
        if (
            not isinstance(self.task_digest, str)
            or _SHA256_PATTERN.fullmatch(self.task_digest) is None
        ):
            raise RunContractError("Task canonical digest is malformed")
        if self.status not in _RUN_STATUSES:
            raise RunContractError("Run status is malformed")
        if (
            not isinstance(self.state_version, int)
            or isinstance(self.state_version, bool)
            or self.state_version < 1
        ):
            raise RunContractError("Run state version must be a positive integer")
        if (
            not isinstance(self.current_fence, int)
            or isinstance(self.current_fence, bool)
            or self.current_fence < 0
        ):
            raise RunContractError("Run fence must be a non-negative integer")
        if self.current_attempt_id is None:
            if self.current_attempt_number is not None or self.current_fence != 0:
                raise RunContractError("Run attempt identity is incomplete")
        else:
            if _ATTEMPT_ID_PATTERN.fullmatch(self.current_attempt_id) is None:
                raise RunContractError("Current attempt identity is malformed")
            if (
                not isinstance(self.current_attempt_number, int)
                or isinstance(self.current_attempt_number, bool)
                or self.current_attempt_number < 1
                or self.current_fence < 1
            ):
                raise RunContractError("Current attempt number or fence is malformed")
        if (self.current_owner_ref is None) != (self.lease_expires_at is None):
            raise RunContractError("Run owner and lease expiry must be present together")
        if self.current_owner_ref is not None:
            _validate_owner_ref(self.current_owner_ref)
            _validate_timestamp(self.lease_expires_at, "lease_expires_at")
            if self.status != "RUNNING":
                raise RunContractError("Only a running Run may hold a lease")
        if self.status == "RUNNING" and self.current_owner_ref is None:
            raise RunContractError("A running Run must have current lease authority")
        cancellation = _validate_optional_timestamp(
            self.cancellation_requested_at,
            "cancellation_requested_at",
        )
        if (self.status == "CANCELLED") != (cancellation is not None):
            raise RunContractError("Run cancellation status and marker are inconsistent")
        _validate_timestamp(self.created_at, "created_at")
        _validate_timestamp(self.updated_at, "updated_at")
        object.__setattr__(self, "identity_sha256", self._identity_digest())
        object.__setattr__(self, "state_sha256", self._state_digest())

    @property
    def project_ref(self) -> ProjectRef:
        return self.run_ref.project_ref

    @property
    def run_id(self) -> str:
        return self.run_ref.run_id

    def _identity_digest(self) -> str:
        return _sha256(
            {
                "created_at": self.created_at,
                "project_id": self.project_ref.value,
                "run_id": self.run_id,
                "task_digest": self.task_digest,
                "task_id": self.task_ref.task_id,
                "task_revision": self.task_ref.revision,
            }
        )

    def _state_digest(self) -> str:
        return _sha256(
            {
                "cancellation_requested_at": self.cancellation_requested_at,
                "current_attempt_id": self.current_attempt_id,
                "current_attempt_number": self.current_attempt_number,
                "current_fence": self.current_fence,
                "current_owner_ref": self.current_owner_ref,
                "lease_expires_at": self.lease_expires_at,
                "project_id": self.project_ref.value,
                "run_id": self.run_id,
                "state_version": self.state_version,
                "status": self.status,
                "updated_at": self.updated_at,
            }
        )


@dataclass(frozen=True)
class ExecutionAttempt:
    """Immutable acquisition record for one monotonically fenced ownership generation."""

    attempt_id: str
    run_ref: RunRef
    task_ref: TaskRef
    task_digest: str
    attempt_number: int
    fence: int
    owner_ref: str
    lease_acquired_at: str
    lease_expires_at: str
    started_at: str
    completed_at: str | None = None
    terminal_outcome: str | None = None
    record_sha256: str = field(init=False)
    completion_sha256: str | None = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_id, str) or _ATTEMPT_ID_PATTERN.fullmatch(self.attempt_id) is None:
            raise RunContractError("ExecutionAttempt identity is malformed")
        if not isinstance(self.run_ref, RunRef):
            raise TypeError("run_ref must be RunRef")
        if not isinstance(self.task_ref, TaskRef):
            raise TypeError("task_ref must be TaskRef")
        if self.run_ref.project_ref != self.task_ref.project_ref:
            raise RunContractError("ExecutionAttempt Project scope differs from Task")
        if (
            not isinstance(self.task_digest, str)
            or _SHA256_PATTERN.fullmatch(self.task_digest) is None
        ):
            raise RunContractError("ExecutionAttempt Task digest is malformed")
        for value, field_name in (
            (self.attempt_number, "attempt_number"),
            (self.fence, "fence"),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise RunContractError(f"ExecutionAttempt {field_name} must be positive")
        _validate_owner_ref(self.owner_ref)
        _validate_timestamp(self.lease_acquired_at, "lease_acquired_at")
        _validate_timestamp(self.lease_expires_at, "lease_expires_at")
        _validate_timestamp(self.started_at, "started_at")
        if (self.completed_at is None) != (self.terminal_outcome is None):
            raise RunContractError(
                "ExecutionAttempt completion timestamp and outcome must be present together"
            )
        if self.completed_at is not None:
            _validate_timestamp(self.completed_at, "completed_at")
            if (
                not isinstance(self.terminal_outcome, str)
                or _OUTCOME_PATTERN.fullmatch(self.terminal_outcome) is None
            ):
                raise RunContractError("ExecutionAttempt terminal outcome is malformed")
        object.__setattr__(self, "record_sha256", self._record_digest())
        object.__setattr__(self, "completion_sha256", self._completion_digest())

    def _record_digest(self) -> str:
        return _sha256(
            {
                "attempt_id": self.attempt_id,
                "attempt_number": self.attempt_number,
                "fence": self.fence,
                "lease_acquired_at": self.lease_acquired_at,
                "lease_expires_at": self.lease_expires_at,
                "owner_ref": self.owner_ref,
                "project_id": self.run_ref.project_ref.value,
                "run_id": self.run_ref.run_id,
                "started_at": self.started_at,
                "task_digest": self.task_digest,
                "task_id": self.task_ref.task_id,
                "task_revision": self.task_ref.revision,
            }
        )

    def _completion_digest(self) -> str | None:
        if self.completed_at is None or self.terminal_outcome is None:
            return None
        return _sha256(
            {
                "attempt_id": self.attempt_id,
                "completed_at": self.completed_at,
                "project_id": self.run_ref.project_ref.value,
                "run_id": self.run_ref.run_id,
                "terminal_outcome": self.terminal_outcome,
            }
        )


class RunService:
    """Project-scoped durable Run identity and transactional fenced lease service."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
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
                CREATE UNIQUE INDEX IF NOT EXISTS task_revisions_exact_run_binding
                    ON task_revisions(project_id, task_id, revision, canonical_digest);

                CREATE TABLE IF NOT EXISTS runs (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_revision INTEGER NOT NULL,
                    task_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, task_id, task_revision, task_digest)
                        REFERENCES task_revisions(
                            project_id, task_id, revision, canonical_digest
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS execution_attempts (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_revision INTEGER NOT NULL,
                    task_digest TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    fence INTEGER NOT NULL,
                    owner_ref TEXT NOT NULL,
                    lease_acquired_at TEXT NOT NULL,
                    lease_expires_at TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id, attempt_id),
                    UNIQUE (project_id, run_id, attempt_number),
                    UNIQUE (project_id, run_id, fence),
                    FOREIGN KEY (project_id, run_id)
                        REFERENCES runs(project_id, run_id) ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, task_id, task_revision, task_digest)
                        REFERENCES task_revisions(
                            project_id, task_id, revision, canonical_digest
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS execution_attempt_completions (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    terminal_outcome TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id, attempt_id),
                    FOREIGN KEY (project_id, run_id, attempt_id)
                        REFERENCES execution_attempts(project_id, run_id, attempt_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS run_state_versions (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    state_version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    current_attempt_id TEXT,
                    current_attempt_number INTEGER,
                    current_fence INTEGER NOT NULL,
                    current_owner_ref TEXT,
                    lease_expires_at TEXT,
                    cancellation_requested_at TEXT,
                    updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id, state_version),
                    UNIQUE (project_id, run_id, state_version, record_sha256),
                    FOREIGN KEY (project_id, run_id)
                        REFERENCES runs(project_id, run_id) ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, run_id, current_attempt_id)
                        REFERENCES execution_attempts(project_id, run_id, attempt_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS run_state_heads (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    current_state_version INTEGER NOT NULL,
                    current_state_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id),
                    FOREIGN KEY (
                        project_id, run_id,
                        current_state_version, current_state_sha256
                    ) REFERENCES run_state_versions(
                        project_id, run_id, state_version, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS run_cancellations (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    cancellation_requested_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id),
                    FOREIGN KEY (project_id, run_id)
                        REFERENCES runs(project_id, run_id) ON DELETE RESTRICT
                );

                CREATE INDEX IF NOT EXISTS run_state_versions_latest
                    ON run_state_versions(project_id, run_id, state_version DESC);

                CREATE TRIGGER IF NOT EXISTS runs_no_update
                BEFORE UPDATE ON runs
                BEGIN
                    SELECT RAISE(ABORT, 'Run identity is immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS runs_no_delete
                BEFORE DELETE ON runs
                BEGIN
                    SELECT RAISE(ABORT, 'Run identity cannot be deleted');
                END;

                CREATE TRIGGER IF NOT EXISTS execution_attempts_no_update
                BEFORE UPDATE ON execution_attempts
                BEGIN
                    SELECT RAISE(ABORT, 'ExecutionAttempt history is immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS execution_attempts_no_delete
                BEFORE DELETE ON execution_attempts
                BEGIN
                    SELECT RAISE(ABORT, 'ExecutionAttempt history cannot be deleted');
                END;

                CREATE TRIGGER IF NOT EXISTS execution_attempt_completions_no_update
                BEFORE UPDATE ON execution_attempt_completions
                BEGIN
                    SELECT RAISE(ABORT, 'ExecutionAttempt completion is immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS execution_attempt_completions_no_delete
                BEFORE DELETE ON execution_attempt_completions
                BEGIN
                    SELECT RAISE(ABORT, 'ExecutionAttempt completion cannot be deleted');
                END;

                CREATE TRIGGER IF NOT EXISTS run_state_versions_no_update
                BEFORE UPDATE ON run_state_versions
                BEGIN
                    SELECT RAISE(ABORT, 'Run authority history is immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS run_state_versions_no_delete
                BEFORE DELETE ON run_state_versions
                BEGIN
                    SELECT RAISE(ABORT, 'Run authority history cannot be deleted');
                END;

                CREATE TRIGGER IF NOT EXISTS run_state_heads_monotonic_update
                BEFORE UPDATE ON run_state_heads
                WHEN
                    NEW.project_id != OLD.project_id
                    OR NEW.run_id != OLD.run_id
                    OR NEW.current_state_version != OLD.current_state_version + 1
                    OR NEW.updated_at < OLD.updated_at
                BEGIN
                    SELECT RAISE(ABORT, 'Run state head must advance monotonically');
                END;

                CREATE TRIGGER IF NOT EXISTS run_state_heads_no_delete
                BEFORE DELETE ON run_state_heads
                BEGIN
                    SELECT RAISE(ABORT, 'Run state head cannot be deleted');
                END;

                CREATE TRIGGER IF NOT EXISTS run_cancellations_no_update
                BEFORE UPDATE ON run_cancellations
                BEGIN
                    SELECT RAISE(ABORT, 'Run cancellation marker is immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS run_cancellations_no_delete
                BEFORE DELETE ON run_cancellations
                BEGIN
                    SELECT RAISE(ABORT, 'Run cancellation marker cannot be deleted');
                END;
                """
            )
        finally:
            connection.close()

    def create_run(
        self,
        requesting_access: ProjectAccess,
        *,
        task_ref: TaskRef,
    ) -> Run:
        if not isinstance(task_ref, TaskRef):
            raise TypeError("TaskRef is required")
        task = self.tasks.get_task(requesting_access, task_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            now = self._database_now(connection)
            run = Run(
                run_ref=RunRef(task.project_ref, f"run_{uuid4().hex}"),
                task_ref=task.task_ref,
                task_digest=task.canonical_digest,
                status="PENDING",
                state_version=1,
                current_attempt_id=None,
                current_attempt_number=None,
                current_fence=0,
                current_owner_ref=None,
                lease_expires_at=None,
                cancellation_requested_at=None,
                created_at=now,
                updated_at=now,
            )
            connection.execute(
                """
                INSERT INTO runs (
                    project_id, run_id, task_id, task_revision,
                    task_digest, created_at, record_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.project_ref.value,
                    run.run_id,
                    run.task_ref.task_id,
                    run.task_ref.revision,
                    run.task_digest,
                    run.created_at,
                    run.identity_sha256,
                ),
            )
            self._insert_state(connection, run)
            self._insert_initial_head(connection, run)
            connection.commit()
            return run
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_run(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> Run:
        self._authorize(requesting_access, run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            run = self._fetch_run(connection, run_ref)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        self._verify_task_binding(requesting_access, run)
        return run

    def list_attempts(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> tuple[ExecutionAttempt, ...]:
        self._authorize(requesting_access, run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            run = self._fetch_run(connection, run_ref)
            attempts = self._fetch_attempts(connection, run)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        self._verify_task_binding(requesting_access, run)
        return attempts

    def acquire_run_lease(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
        *,
        owner_ref: str,
        lease_seconds: int | float,
    ) -> ExecutionAttempt:
        _validate_owner_ref(owner_ref)
        duration = _validate_lease_seconds(lease_seconds)
        self.get_run(requesting_access, run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run = self._fetch_run(connection, run_ref)
            if run.status == "CANCELLED":
                raise RunCancelledError("Run cancellation prevents lease acquisition")
            now, expires_at = self._database_lease_times(connection, duration)
            if (
                run.current_owner_ref is not None
                and run.lease_expires_at is not None
                and run.lease_expires_at > now
            ):
                raise RunLeaseConflictError("Run already has current live authority")
            if run.current_owner_ref is not None and run.current_attempt_id is not None:
                expired_attempt = self._fetch_attempt(
                    connection,
                    run,
                    run.current_attempt_id,
                )
                self._insert_attempt_completion(
                    connection,
                    expired_attempt,
                    completed_at=cast(str, run.lease_expires_at),
                    terminal_outcome="LEASE_EXPIRED",
                )
            attempt_number = self._next_attempt_number(connection, run_ref)
            attempt = ExecutionAttempt(
                attempt_id=f"att_{uuid4().hex}",
                run_ref=run_ref,
                task_ref=run.task_ref,
                task_digest=run.task_digest,
                attempt_number=attempt_number,
                fence=run.current_fence + 1,
                owner_ref=owner_ref,
                lease_acquired_at=now,
                lease_expires_at=expires_at,
                started_at=now,
            )
            self._insert_attempt(connection, attempt)
            next_state = self._next_state(
                run,
                status="RUNNING",
                current_attempt_id=attempt.attempt_id,
                current_attempt_number=attempt.attempt_number,
                current_fence=attempt.fence,
                current_owner_ref=attempt.owner_ref,
                lease_expires_at=attempt.lease_expires_at,
                cancellation_requested_at=None,
                updated_at=now,
            )
            self._insert_state(connection, next_state)
            self._advance_head(connection, run, next_state)
            connection.commit()
            return attempt
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def renew_run_lease(
        self,
        requesting_access: ProjectAccess,
        attempt: ExecutionAttempt,
        *,
        lease_seconds: int | float,
    ) -> Run:
        duration = _validate_lease_seconds(lease_seconds)
        self.get_run(requesting_access, self._require_attempt(attempt).run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run = self._fetch_run(connection, attempt.run_ref)
            if run.status == "CANCELLED":
                raise RunCancelledError("Run cancellation invalidates execution authority")
            persisted = self._fetch_attempt(connection, run, attempt.attempt_id)
            self._require_same_attempt(persisted, attempt)
            now = self._database_now(connection)
            self._require_current_authority(run, attempt, now)
            renewed_expires_at = self._database_renewed_expiry(
                connection,
                cast(str, run.lease_expires_at),
                duration,
            )
            renewed = self._next_state(
                run,
                status="RUNNING",
                current_attempt_id=run.current_attempt_id,
                current_attempt_number=run.current_attempt_number,
                current_fence=run.current_fence,
                current_owner_ref=run.current_owner_ref,
                lease_expires_at=renewed_expires_at,
                cancellation_requested_at=None,
                updated_at=now,
            )
            self._insert_state(connection, renewed)
            self._advance_head(connection, run, renewed)
            connection.commit()
            return renewed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def release_run_lease(
        self,
        requesting_access: ProjectAccess,
        attempt: ExecutionAttempt,
    ) -> Run:
        self.get_run(requesting_access, self._require_attempt(attempt).run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run = self._fetch_run(connection, attempt.run_ref)
            if run.status == "CANCELLED":
                raise RunCancelledError("Run cancellation invalidates execution authority")
            persisted = self._fetch_attempt(connection, run, attempt.attempt_id)
            self._require_same_attempt(persisted, attempt)
            now = self._database_now(connection)
            self._require_current_authority(run, attempt, now)
            self._insert_attempt_completion(
                connection,
                persisted,
                completed_at=now,
                terminal_outcome="RELEASED",
            )
            released = self._next_state(
                run,
                status="PENDING",
                current_attempt_id=run.current_attempt_id,
                current_attempt_number=run.current_attempt_number,
                current_fence=run.current_fence,
                current_owner_ref=None,
                lease_expires_at=None,
                cancellation_requested_at=None,
                updated_at=now,
            )
            self._insert_state(connection, released)
            self._advance_head(connection, run, released)
            connection.commit()
            return released
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def assert_current_run_authority(
        self,
        requesting_access: ProjectAccess,
        attempt: ExecutionAttempt,
    ) -> Run:
        self.get_run(requesting_access, self._require_attempt(attempt).run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run = self._fetch_run(connection, attempt.run_ref)
            if run.status == "CANCELLED":
                raise RunCancelledError("Run cancellation invalidates execution authority")
            persisted = self._fetch_attempt(connection, run, attempt.attempt_id)
            self._require_same_attempt(persisted, attempt)
            self._require_current_authority(
                run,
                attempt,
                self._database_now(connection),
            )
            connection.commit()
            return run
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def assertCurrentRunAuthority(
        self,
        requesting_access: ProjectAccess,
        attempt: ExecutionAttempt,
    ) -> Run:
        """Compatibility spelling of the required P0-05 authority seam."""

        return self.assert_current_run_authority(requesting_access, attempt)

    def request_run_cancellation(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> Run:
        self.get_run(requesting_access, run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run = self._fetch_run(connection, run_ref)
            if run.status == "CANCELLED":
                connection.commit()
                return run
            now = self._database_now(connection)
            self._insert_cancellation(connection, run_ref, now)
            if run.current_owner_ref is not None and run.current_attempt_id is not None:
                current_attempt = self._fetch_attempt(
                    connection,
                    run,
                    run.current_attempt_id,
                )
                self._insert_attempt_completion(
                    connection,
                    current_attempt,
                    completed_at=now,
                    terminal_outcome="CANCELLED",
                )
            cancelled = self._next_state(
                run,
                status="CANCELLED",
                current_attempt_id=run.current_attempt_id,
                current_attempt_number=run.current_attempt_number,
                current_fence=run.current_fence,
                current_owner_ref=None,
                lease_expires_at=None,
                cancellation_requested_at=now,
                updated_at=now,
            )
            self._insert_state(connection, cancelled)
            self._advance_head(connection, run, cancelled)
            connection.commit()
            return cancelled
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def requestRunCancellation(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> Run:
        """Compatibility spelling of the required P0-05 cancellation seam."""

        return self.request_run_cancellation(requesting_access, run_ref)

    def _authorize(self, access: ProjectAccess, run_ref: RunRef) -> None:
        if not isinstance(run_ref, RunRef):
            raise TypeError("RunRef is required")
        try:
            self.projects.get_project(access, run_ref.project_ref)
        except ProjectScopeError as exc:
            raise RunScopeError("Run Project scope mismatch") from exc

    def _verify_task_binding(self, access: ProjectAccess, run: Run) -> None:
        try:
            task = self.tasks.get_task(access, run.task_ref)
        except ProjectScopeError as exc:
            raise RunScopeError("Run Project scope mismatch") from exc
        except Exception as exc:
            raise RunIntegrityError("Run exact Task binding failed verification") from exc
        if not hmac.compare_digest(task.canonical_digest, run.task_digest):
            raise RunIntegrityError("Run exact Task digest binding is inconsistent")

    @staticmethod
    def _require_attempt(attempt: ExecutionAttempt) -> ExecutionAttempt:
        if not isinstance(attempt, ExecutionAttempt):
            raise TypeError("ExecutionAttempt is required")
        return attempt

    @staticmethod
    def _require_same_attempt(
        persisted: ExecutionAttempt,
        supplied: ExecutionAttempt,
    ) -> None:
        if persisted != supplied:
            raise RunAuthorityError("ExecutionAttempt authority does not match durable evidence")

    @staticmethod
    def _require_current_authority(
        run: Run,
        attempt: ExecutionAttempt,
        database_now: str,
    ) -> None:
        if run.status == "CANCELLED":
            raise RunCancelledError("Run cancellation invalidates execution authority")
        if (
            run.status != "RUNNING"
            or run.current_attempt_id != attempt.attempt_id
            or run.current_attempt_number != attempt.attempt_number
            or run.current_fence != attempt.fence
            or run.current_owner_ref != attempt.owner_ref
            or run.task_ref != attempt.task_ref
            or not hmac.compare_digest(run.task_digest, attempt.task_digest)
            or run.lease_expires_at is None
            or run.lease_expires_at <= database_now
        ):
            raise RunAuthorityError("ExecutionAttempt does not hold current live Run authority")

    @staticmethod
    def _database_now(connection: sqlite3.Connection) -> str:
        value = connection.execute(
            "SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
        ).fetchone()[0]
        if not isinstance(value, str):
            raise RunIntegrityError("Durable database time is unavailable")
        return _validate_timestamp(value, "database_now")

    @staticmethod
    def _database_lease_times(
        connection: sqlite3.Connection,
        duration: float,
    ) -> tuple[str, str]:
        row = connection.execute(
            """
            SELECT
                strftime('%Y-%m-%dT%H:%M:%fZ', 'now') AS database_now,
                strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    julianday('now') + (? / 86400.0)
                ) AS expires_at
            """,
            (duration,),
        ).fetchone()
        now = _validate_timestamp(row["database_now"], "database_now")
        expires_at = _validate_timestamp(row["expires_at"], "lease_expires_at")
        if expires_at <= now:
            raise RunIntegrityError("Database could not produce a future lease expiry")
        return now, expires_at

    @staticmethod
    def _database_renewed_expiry(
        connection: sqlite3.Connection,
        current_expiry: str,
        duration: float,
    ) -> str:
        value = connection.execute(
            """
            SELECT strftime(
                '%Y-%m-%dT%H:%M:%fZ',
                max(julianday('now'), julianday(?)) + (? / 86400.0)
            )
            """,
            (current_expiry, duration),
        ).fetchone()[0]
        expires_at = _validate_timestamp(value, "lease_expires_at")
        if expires_at <= current_expiry:
            raise RunIntegrityError("Database lease renewal did not extend authority")
        return expires_at

    @staticmethod
    def _next_attempt_number(
        connection: sqlite3.Connection,
        run_ref: RunRef,
    ) -> int:
        value = connection.execute(
            """
            SELECT COALESCE(MAX(attempt_number), 0) + 1
            FROM execution_attempts
            WHERE project_id = ? AND run_id = ?
            """,
            (run_ref.project_ref.value, run_ref.run_id),
        ).fetchone()[0]
        if not isinstance(value, int) or value < 1:
            raise RunIntegrityError("ExecutionAttempt lineage is malformed")
        return value

    @staticmethod
    def _next_state(
        run: Run,
        *,
        status: str,
        current_attempt_id: str | None,
        current_attempt_number: int | None,
        current_fence: int,
        current_owner_ref: str | None,
        lease_expires_at: str | None,
        cancellation_requested_at: str | None,
        updated_at: str,
    ) -> Run:
        return Run(
            run_ref=run.run_ref,
            task_ref=run.task_ref,
            task_digest=run.task_digest,
            status=status,
            state_version=run.state_version + 1,
            current_attempt_id=current_attempt_id,
            current_attempt_number=current_attempt_number,
            current_fence=current_fence,
            current_owner_ref=current_owner_ref,
            lease_expires_at=lease_expires_at,
            cancellation_requested_at=cancellation_requested_at,
            created_at=run.created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _insert_attempt(
        connection: sqlite3.Connection,
        attempt: ExecutionAttempt,
    ) -> None:
        connection.execute(
            """
            INSERT INTO execution_attempts (
                project_id, run_id, attempt_id, task_id, task_revision,
                task_digest, attempt_number, fence, owner_ref,
                lease_acquired_at, lease_expires_at, started_at, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt.run_ref.project_ref.value,
                attempt.run_ref.run_id,
                attempt.attempt_id,
                attempt.task_ref.task_id,
                attempt.task_ref.revision,
                attempt.task_digest,
                attempt.attempt_number,
                attempt.fence,
                attempt.owner_ref,
                attempt.lease_acquired_at,
                attempt.lease_expires_at,
                attempt.started_at,
                attempt.record_sha256,
            ),
        )

    @staticmethod
    def _insert_attempt_completion(
        connection: sqlite3.Connection,
        attempt: ExecutionAttempt,
        *,
        completed_at: str,
        terminal_outcome: str,
    ) -> None:
        completed = ExecutionAttempt(
            attempt_id=attempt.attempt_id,
            run_ref=attempt.run_ref,
            task_ref=attempt.task_ref,
            task_digest=attempt.task_digest,
            attempt_number=attempt.attempt_number,
            fence=attempt.fence,
            owner_ref=attempt.owner_ref,
            lease_acquired_at=attempt.lease_acquired_at,
            lease_expires_at=attempt.lease_expires_at,
            started_at=attempt.started_at,
            completed_at=completed_at,
            terminal_outcome=terminal_outcome,
        )
        if completed.completion_sha256 is None:
            raise RunIntegrityError("ExecutionAttempt completion digest is unavailable")
        connection.execute(
            """
            INSERT INTO execution_attempt_completions (
                project_id, run_id, attempt_id,
                completed_at, terminal_outcome, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                completed.run_ref.project_ref.value,
                completed.run_ref.run_id,
                completed.attempt_id,
                completed.completed_at,
                completed.terminal_outcome,
                completed.completion_sha256,
            ),
        )

    @staticmethod
    def _insert_state(connection: sqlite3.Connection, run: Run) -> None:
        connection.execute(
            """
            INSERT INTO run_state_versions (
                project_id, run_id, state_version, status,
                current_attempt_id, current_attempt_number, current_fence,
                current_owner_ref, lease_expires_at, cancellation_requested_at,
                updated_at, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.project_ref.value,
                run.run_id,
                run.state_version,
                run.status,
                run.current_attempt_id,
                run.current_attempt_number,
                run.current_fence,
                run.current_owner_ref,
                run.lease_expires_at,
                run.cancellation_requested_at,
                run.updated_at,
                run.state_sha256,
            ),
        )

    @classmethod
    def _insert_initial_head(cls, connection: sqlite3.Connection, run: Run) -> None:
        connection.execute(
            """
            INSERT INTO run_state_heads (
                project_id, run_id, current_state_version,
                current_state_sha256, updated_at, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run.project_ref.value,
                run.run_id,
                run.state_version,
                run.state_sha256,
                run.updated_at,
                cls._head_sha256(run),
            ),
        )

    @classmethod
    def _advance_head(
        cls,
        connection: sqlite3.Connection,
        prior: Run,
        current: Run,
    ) -> None:
        updated = connection.execute(
            """
            UPDATE run_state_heads
            SET current_state_version = ?, current_state_sha256 = ?,
                updated_at = ?, record_sha256 = ?
            WHERE project_id = ? AND run_id = ?
              AND current_state_version = ? AND current_state_sha256 = ?
            """,
            (
                current.state_version,
                current.state_sha256,
                current.updated_at,
                cls._head_sha256(current),
                prior.project_ref.value,
                prior.run_id,
                prior.state_version,
                prior.state_sha256,
            ),
        )
        if updated.rowcount != 1:
            raise RunConflictError("Run state head changed concurrently")

    @staticmethod
    def _head_sha256(run: Run) -> str:
        return _sha256(
            {
                "current_state_sha256": run.state_sha256,
                "current_state_version": run.state_version,
                "project_id": run.project_ref.value,
                "run_id": run.run_id,
                "updated_at": run.updated_at,
            }
        )

    @staticmethod
    def _insert_cancellation(
        connection: sqlite3.Connection,
        run_ref: RunRef,
        cancellation_requested_at: str,
    ) -> None:
        record_sha256 = RunService._cancellation_sha256(
            run_ref,
            cancellation_requested_at,
        )
        connection.execute(
            """
            INSERT INTO run_cancellations (
                project_id, run_id, cancellation_requested_at, record_sha256
            ) VALUES (?, ?, ?, ?)
            """,
            (
                run_ref.project_ref.value,
                run_ref.run_id,
                cancellation_requested_at,
                record_sha256,
            ),
        )

    @staticmethod
    def _cancellation_sha256(
        run_ref: RunRef,
        cancellation_requested_at: str,
    ) -> str:
        return _sha256(
            {
                "cancellation_requested_at": cancellation_requested_at,
                "project_id": run_ref.project_ref.value,
                "run_id": run_ref.run_id,
            }
        )

    def _fetch_run(
        self,
        connection: sqlite3.Connection,
        run_ref: RunRef,
    ) -> Run:
        if not connection.in_transaction:
            raise RunIntegrityError("Run reads require one explicit durable snapshot")
        identity = connection.execute(
            "SELECT * FROM runs WHERE project_id = ? AND run_id = ?",
            (run_ref.project_ref.value, run_ref.run_id),
        ).fetchone()
        if identity is None:
            raise RunNotFoundError("Run not found in authenticated Project")
        head = connection.execute(
            "SELECT * FROM run_state_heads WHERE project_id = ? AND run_id = ?",
            (run_ref.project_ref.value, run_ref.run_id),
        ).fetchone()
        if head is None:
            raise RunIntegrityError("Run state head is missing")
        state_rows = connection.execute(
            """
            SELECT * FROM run_state_versions
            WHERE project_id = ? AND run_id = ?
            ORDER BY state_version
            """,
            (run_ref.project_ref.value, run_ref.run_id),
        ).fetchall()
        if not state_rows:
            raise RunIntegrityError("Run has no durable authority state")
        runs: list[Run] = []
        try:
            for row in state_rows:
                run = Run(
                    run_ref=run_ref,
                    task_ref=TaskRef(
                        run_ref.project_ref,
                        cast(str, identity["task_id"]),
                        cast(int, identity["task_revision"]),
                    ),
                    task_digest=cast(str, identity["task_digest"]),
                    status=cast(str, row["status"]),
                    state_version=cast(int, row["state_version"]),
                    current_attempt_id=cast(str | None, row["current_attempt_id"]),
                    current_attempt_number=cast(int | None, row["current_attempt_number"]),
                    current_fence=cast(int, row["current_fence"]),
                    current_owner_ref=cast(str | None, row["current_owner_ref"]),
                    lease_expires_at=cast(str | None, row["lease_expires_at"]),
                    cancellation_requested_at=cast(
                        str | None,
                        row["cancellation_requested_at"],
                    ),
                    created_at=cast(str, identity["created_at"]),
                    updated_at=cast(str, row["updated_at"]),
                )
                self._verify_digest(
                    run.identity_sha256,
                    identity["record_sha256"],
                    "Run identity",
                )
                self._verify_digest(
                    run.state_sha256,
                    row["record_sha256"],
                    "Run authority state",
                )
                runs.append(run)
        except (TypeError, ValueError, RunError) as exc:
            if isinstance(exc, RunIntegrityError):
                raise
            raise RunIntegrityError("Persisted Run state is malformed") from exc
        self._verify_state_lineage(runs)
        latest = runs[-1]
        if (
            head["current_state_version"] != latest.state_version
            or head["current_state_sha256"] != latest.state_sha256
            or head["updated_at"] != latest.updated_at
        ):
            raise RunIntegrityError("Run state history does not match its durable head")
        self._verify_digest(
            self._head_sha256(latest),
            head["record_sha256"],
            "Run state head",
        )
        cancellation = connection.execute(
            """
            SELECT cancellation_requested_at, record_sha256
            FROM run_cancellations
            WHERE project_id = ? AND run_id = ?
            """,
            (run_ref.project_ref.value, run_ref.run_id),
        ).fetchone()
        if cancellation is None:
            if latest.status == "CANCELLED":
                raise RunIntegrityError("Run cancellation marker is missing")
        else:
            try:
                cancelled_at = _validate_timestamp(
                    cancellation["cancellation_requested_at"],
                    "cancellation_requested_at",
                )
            except RunContractError as exc:
                raise RunIntegrityError("Persisted Run cancellation is malformed") from exc
            self._verify_digest(
                self._cancellation_sha256(run_ref, cancelled_at),
                cancellation["record_sha256"],
                "Run cancellation",
            )
            if (
                latest.status != "CANCELLED"
                or latest.cancellation_requested_at != cancelled_at
            ):
                raise RunIntegrityError(
                    "Run cancellation marker and current state are inconsistent"
                )
        attempts = self._fetch_attempts(connection, latest)
        if len(attempts) != latest.current_fence:
            raise RunIntegrityError("Run fence does not match durable attempt history")
        if any(attempt.completed_at is None for attempt in attempts[:-1]):
            raise RunIntegrityError(
                "Superseded ExecutionAttempt lacks immutable completion evidence"
            )
        if latest.current_attempt_id is not None:
            attempt = attempts[-1]
            if (
                attempt.attempt_id != latest.current_attempt_id
                or attempt.attempt_number != latest.current_attempt_number
                or attempt.fence != latest.current_fence
            ):
                raise RunIntegrityError("Run current attempt and fence are inconsistent")
            if latest.status == "RUNNING" and attempt.completed_at is not None:
                raise RunIntegrityError("Completed ExecutionAttempt retained live authority")
            if latest.status != "RUNNING" and attempt.completed_at is None:
                raise RunIntegrityError("Released Run attempt lacks immutable completion")
        return latest

    def _fetch_attempts(
        self,
        connection: sqlite3.Connection,
        run: Run,
    ) -> tuple[ExecutionAttempt, ...]:
        rows = connection.execute(
            """
            SELECT
                attempt.*,
                completion.completed_at AS completion_completed_at,
                completion.terminal_outcome AS completion_terminal_outcome,
                completion.record_sha256 AS completion_record_sha256
            FROM execution_attempts AS attempt
            LEFT JOIN execution_attempt_completions AS completion
              ON completion.project_id = attempt.project_id
             AND completion.run_id = attempt.run_id
             AND completion.attempt_id = attempt.attempt_id
            WHERE attempt.project_id = ? AND attempt.run_id = ?
            ORDER BY attempt.attempt_number
            """,
            (run.project_ref.value, run.run_id),
        ).fetchall()
        attempts = tuple(self._attempt_from_row(run, row) for row in rows)
        if tuple(attempt.attempt_number for attempt in attempts) != tuple(
            range(1, len(attempts) + 1)
        ):
            raise RunIntegrityError("ExecutionAttempt numbers are not gap-free")
        if tuple(attempt.fence for attempt in attempts) != tuple(
            range(1, len(attempts) + 1)
        ):
            raise RunIntegrityError("ExecutionAttempt fences are not monotonic and gap-free")
        return attempts

    def _fetch_attempt(
        self,
        connection: sqlite3.Connection,
        run: Run,
        attempt_id: str,
    ) -> ExecutionAttempt:
        row = connection.execute(
            """
            SELECT
                attempt.*,
                completion.completed_at AS completion_completed_at,
                completion.terminal_outcome AS completion_terminal_outcome,
                completion.record_sha256 AS completion_record_sha256
            FROM execution_attempts AS attempt
            LEFT JOIN execution_attempt_completions AS completion
              ON completion.project_id = attempt.project_id
             AND completion.run_id = attempt.run_id
             AND completion.attempt_id = attempt.attempt_id
            WHERE attempt.project_id = ? AND attempt.run_id = ? AND attempt.attempt_id = ?
            """,
            (run.project_ref.value, run.run_id, attempt_id),
        ).fetchone()
        if row is None:
            raise RunIntegrityError("Run current ExecutionAttempt is missing")
        return self._attempt_from_row(run, row)

    def _attempt_from_row(
        self,
        run: Run,
        row: sqlite3.Row,
    ) -> ExecutionAttempt:
        try:
            attempt = ExecutionAttempt(
                attempt_id=cast(str, row["attempt_id"]),
                run_ref=run.run_ref,
                task_ref=TaskRef(
                    run.project_ref,
                    cast(str, row["task_id"]),
                    cast(int, row["task_revision"]),
                ),
                task_digest=cast(str, row["task_digest"]),
                attempt_number=cast(int, row["attempt_number"]),
                fence=cast(int, row["fence"]),
                owner_ref=cast(str, row["owner_ref"]),
                lease_acquired_at=cast(str, row["lease_acquired_at"]),
                lease_expires_at=cast(str, row["lease_expires_at"]),
                started_at=cast(str, row["started_at"]),
                completed_at=cast(str | None, row["completion_completed_at"]),
                terminal_outcome=cast(str | None, row["completion_terminal_outcome"]),
            )
        except (TypeError, ValueError, RunError) as exc:
            raise RunIntegrityError("Persisted ExecutionAttempt is malformed") from exc
        if (
            attempt.task_ref != run.task_ref
            or not hmac.compare_digest(attempt.task_digest, run.task_digest)
        ):
            raise RunIntegrityError("ExecutionAttempt exact Task binding is inconsistent")
        self._verify_digest(
            attempt.record_sha256,
            row["record_sha256"],
            "ExecutionAttempt",
        )
        if attempt.completion_sha256 is None:
            if row["completion_record_sha256"] is not None:
                raise RunIntegrityError("ExecutionAttempt completion is incomplete")
        else:
            self._verify_digest(
                attempt.completion_sha256,
                row["completion_record_sha256"],
                "ExecutionAttempt completion",
            )
        return attempt

    @staticmethod
    def _verify_digest(expected: str, persisted: object, label: str) -> None:
        if (
            not isinstance(persisted, str)
            or _SHA256_PATTERN.fullmatch(persisted) is None
            or not hmac.compare_digest(expected, persisted)
        ):
            raise RunIntegrityError(f"{label} failed integrity verification")

    @staticmethod
    def _verify_state_lineage(runs: list[Run]) -> None:
        first = runs[0]
        if (
            first.state_version != 1
            or first.status != "PENDING"
            or first.current_attempt_id is not None
            or first.current_fence != 0
        ):
            raise RunIntegrityError("Run initial authority state is invalid")
        for expected_version, (previous, current) in enumerate(
            zip(runs, runs[1:]),
            start=2,
        ):
            if current.state_version != expected_version:
                raise RunIntegrityError("Run authority state versions are not gap-free")
            fence_delta = current.current_fence - previous.current_fence
            if fence_delta not in (0, 1):
                raise RunIntegrityError("Run fence lineage regressed or skipped")
            if fence_delta == 1:
                expected_attempt = (previous.current_attempt_number or 0) + 1
                if (
                    current.status != "RUNNING"
                    or current.current_attempt_number != expected_attempt
                    or current.current_attempt_id == previous.current_attempt_id
                ):
                    raise RunIntegrityError("Run acquisition lineage is inconsistent")
            elif (
                current.current_attempt_id != previous.current_attempt_id
                or current.current_attempt_number != previous.current_attempt_number
            ):
                raise RunIntegrityError("Run attempt identity changed without a new fence")
            if previous.status == "CANCELLED" and current != previous:
                raise RunIntegrityError("Cancelled Run authority history was extended")
