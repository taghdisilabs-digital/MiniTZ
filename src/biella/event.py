"""Durable append-only meaningful execution Event ledger."""

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

from .artifact import (
    Artifact,
    ArtifactError,
    ArtifactRef,
    ArtifactService,
    ContentRef,
)
from .graph import Graph, GraphError, GraphRef, GraphService, NodeRef
from .project import ProjectAccess, ProjectRef, ProjectScopeError, ProjectStore
from .run import (
    ExecutionAttempt,
    Run,
    RunAuthorityError,
    RunError,
    RunRef,
    RunService,
)
from .task import TaskError, TaskRef, TaskRevisionService


EventValue: TypeAlias = str | int | float | bool | None
EventObjectRef: TypeAlias = ArtifactRef | ContentRef

_EVENT_ID_PATTERN = re.compile(r"evt_[0-9a-f]{32}")
_EVENT_TYPE_PATTERN = re.compile(r"[A-Z][A-Z0-9_.-]{0,127}")
_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_METADATA_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_ABSOLUTE_REF_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_ARTIFACT_REF_PATTERN = re.compile(
    r"artifact://(prj_[0-9a-f]{32})/(art_[0-9a-f]{32})/([1-9][0-9]*)"
)
_CONTENT_REF_PATTERN = re.compile(
    r"content://sha256/([0-9a-f]{64})\?size=(0|[1-9][0-9]*)"
)
_SECRET_KEY_PARTS = {
    "access_key",
    "accesskey",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}
_PAYLOAD_KEY_PARTS = {
    "full_prompt",
    "model_output",
    "prompt",
    "raw_output",
    "stderr",
    "stdout",
}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{4,}"),
    re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{4,}"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
_MAX_ACTOR_REF_BYTES = 1024


class EventError(Exception):
    """Base class for Event ledger failures."""


class EventContractError(EventError, ValueError):
    """An Event envelope or append request is malformed."""


class EventScopeError(EventError):
    """An Event operation crossed authenticated Project scope."""


class EventAuthorityError(EventError):
    """A Run-scoped Event publisher lacks current fenced authority."""


class EventConflictError(EventError):
    """An Event idempotency or sequence identity conflicts."""


class EventNotFoundError(EventError):
    """An exact Event does not exist in the authorized Project."""


class EventIntegrityError(EventError):
    """Persisted Event evidence failed integrity verification."""


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
        raise EventContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise EventContractError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EventContractError(f"{name} must be timezone-aware")
    return value


def _task_ref_value(task_ref: TaskRef) -> str:
    return (
        f"task://{task_ref.project_ref.value}/{task_ref.task_id}/"
        f"{task_ref.revision}"
    )


def _run_ref_value(run_ref: RunRef) -> str:
    return f"run://{run_ref.project_ref.value}/{run_ref.run_id}"


def _freeze_metadata(value: Mapping[str, EventValue]) -> Mapping[str, EventValue]:
    if not isinstance(value, Mapping):
        raise EventContractError("Event metadata must be a mapping")
    copied = dict(value)
    if len(copied) > 32:
        raise EventContractError("Event metadata exceeds 32 entries")
    for key, item in copied.items():
        if not isinstance(key, str) or _METADATA_KEY_PATTERN.fullmatch(key) is None:
            raise EventContractError("Event metadata key is malformed")
        normalized_key = key.lower()
        if any(part in normalized_key for part in _SECRET_KEY_PARTS | _PAYLOAD_KEY_PARTS):
            raise EventContractError("Event metadata cannot contain secret or payload fields")
        if not isinstance(item, (str, int, float, bool, type(None))):
            raise EventContractError("Event metadata values must be JSON scalars")
        if isinstance(item, float) and not math.isfinite(item):
            raise EventContractError("Event metadata contains non-finite value")
        if isinstance(item, str):
            if len(item) > 512:
                raise EventContractError("Event metadata value is unbounded")
            if any(pattern.search(item) is not None for pattern in _SECRET_VALUE_PATTERNS):
                raise EventContractError("Event metadata contains an obvious secret")
    if len(_json(copied).encode()) > 4096:
        raise EventContractError("Event metadata exceeds 4096 serialized bytes")
    return MappingProxyType(copied)


def _content_payload(content_ref: ContentRef) -> dict[str, object]:
    return {
        "algorithm": content_ref.algorithm,
        "digest": content_ref.digest,
        "media_type": content_ref.media_type,
        "size_bytes": content_ref.size_bytes,
    }


def _validate_actor_ref(actor_ref: str | None) -> None:
    if actor_ref is None:
        return
    if (
        not isinstance(actor_ref, str)
        or len(actor_ref.encode("utf-8")) > _MAX_ACTOR_REF_BYTES
        or _ABSOLUTE_REF_PATTERN.fullmatch(actor_ref) is None
    ):
        raise EventContractError("Event actor reference is malformed or unbounded")


@dataclass(frozen=True, order=True)
class EventRef:
    """Opaque exact identity of one immutable Project-scoped Event."""

    project_ref: ProjectRef
    event_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.event_id, str) or _EVENT_ID_PATTERN.fullmatch(self.event_id) is None:
            raise EventContractError("Event identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "EventRef":
        return cls(project_ref, f"evt_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"event://{self.project_ref.value}/{self.event_id}"


@dataclass(frozen=True)
class Event:
    """One universal immutable meaningful execution occurrence."""

    event_ref: EventRef
    task_ref: TaskRef | None
    run_ref: RunRef | None
    graph_ref: GraphRef | None
    node_ref: NodeRef | None
    sequence: int | None
    event_type: str
    idempotency_key: str
    actor_ref: str | None
    object_refs: tuple[str, ...]
    metadata: Mapping[str, EventValue]
    payload_ref: ContentRef | None
    created_at: str
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.event_ref, EventRef):
            raise TypeError("event_ref must be EventRef")
        for reference in (self.task_ref, self.run_ref, self.graph_ref, self.node_ref):
            project_ref = getattr(reference, "project_ref", self.project_ref)
            if reference is not None and project_ref != self.project_ref:
                raise EventScopeError("Event reference Project scope mismatch")
        if self.graph_ref is None and self.node_ref is not None:
            raise EventContractError("NodeRef requires exact GraphRef")
        if self.node_ref is not None and self.node_ref.graph_ref != self.graph_ref:
            raise EventContractError("NodeRef does not belong to Event GraphRef")
        if self.run_ref is None:
            if self.sequence is not None:
                raise EventContractError("Only Run Events have a sequence")
            if self.graph_ref is not None or self.node_ref is not None:
                raise EventContractError("Graph and Node Events require RunRef")
        elif (
            not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or self.sequence < 1
        ):
            raise EventContractError("Run Event sequence must be positive")
        if not isinstance(self.event_type, str) or _EVENT_TYPE_PATTERN.fullmatch(self.event_type) is None:
            raise EventContractError("Event type is malformed")
        if (
            not isinstance(self.idempotency_key, str)
            or _KEY_PATTERN.fullmatch(self.idempotency_key) is None
        ):
            raise EventContractError("Event idempotency key is malformed")
        _validate_actor_ref(self.actor_ref)
        if not isinstance(self.object_refs, tuple) or len(self.object_refs) > 32:
            raise EventContractError("Event object refs must be a bounded tuple")
        if not all(
            isinstance(reference, str)
            and len(reference) <= 1056
            and _ABSOLUTE_REF_PATTERN.fullmatch(reference) is not None
            for reference in self.object_refs
        ):
            raise EventContractError("Event object reference is malformed")
        object.__setattr__(self, "object_refs", tuple(sorted(set(self.object_refs))))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        if self.payload_ref is not None and not isinstance(self.payload_ref, ContentRef):
            raise EventContractError("Event payload must be an exact ContentRef")
        _validate_timestamp(self.created_at, "created_at")
        object.__setattr__(self, "semantic_digest", _sha256(self._semantic_payload()))
        object.__setattr__(
            self,
            "record_sha256",
            _sha256(
                {
                    "created_at": self.created_at,
                    "event_id": self.event_ref.event_id,
                    "project_id": self.project_ref.value,
                    "semantic_digest": self.semantic_digest,
                    "sequence": self.sequence,
                }
            ),
        )

    @property
    def project_ref(self) -> ProjectRef:
        return self.event_ref.project_ref

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "actor_ref": self.actor_ref,
            "event_type": self.event_type,
            "graph_ref": None if self.graph_ref is None else self.graph_ref.value,
            "idempotency_key": self.idempotency_key,
            "metadata": dict(self.metadata),
            "node_ref": None if self.node_ref is None else self.node_ref.value,
            "object_refs": list(self.object_refs),
            "payload_ref": None if self.payload_ref is None else _content_payload(self.payload_ref),
            "project_id": self.project_ref.value,
            "run_ref": None if self.run_ref is None else _run_ref_value(self.run_ref),
            "task_ref": None if self.task_ref is None else _task_ref_value(self.task_ref),
        }


class EventLedger:
    """Project-scoped append/read service for meaningful immutable Events."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.runs = RunService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.graphs = GraphService(self.database_path)
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
                CREATE UNIQUE INDEX IF NOT EXISTS graph_nodes_exact_event_ref
                    ON graph_nodes(
                        project_id, graph_id, graph_revision, node_id, record_sha256
                    );

                CREATE TABLE IF NOT EXISTS events (
                    project_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_scope TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    task_id TEXT,
                    task_revision INTEGER,
                    task_digest TEXT,
                    run_id TEXT,
                    graph_id TEXT,
                    graph_revision INTEGER,
                    graph_record_sha256 TEXT,
                    node_id TEXT,
                    node_record_sha256 TEXT,
                    sequence INTEGER,
                    event_type TEXT NOT NULL,
                    actor_ref TEXT,
                    object_refs_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    payload_ref_json TEXT,
                    created_at TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, event_id),
                    UNIQUE (project_id, event_id, record_sha256),
                    UNIQUE (project_id, event_scope, idempotency_key),
                    UNIQUE (project_id, run_id, sequence),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, task_id, task_revision, task_digest)
                        REFERENCES task_revisions(
                            project_id, task_id, revision, canonical_digest
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, run_id) REFERENCES runs(project_id, run_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, graph_id, graph_revision, graph_record_sha256
                    ) REFERENCES graph_revisions(
                        project_id, graph_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, graph_id, graph_revision,
                        node_id, node_record_sha256
                    ) REFERENCES graph_nodes(
                        project_id, graph_id, graph_revision,
                        node_id, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    CHECK (
                        (run_id IS NULL AND sequence IS NULL)
                        OR (run_id IS NOT NULL AND sequence >= 1)
                    )
                );

                CREATE TABLE IF NOT EXISTS event_objects (
                    project_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    object_ref TEXT NOT NULL,
                    object_kind TEXT NOT NULL,
                    artifact_id TEXT,
                    artifact_revision INTEGER,
                    artifact_record_sha256 TEXT,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, event_id, object_ref),
                    FOREIGN KEY (project_id, event_id)
                        REFERENCES events(project_id, event_id) ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, artifact_id,
                        artifact_revision, artifact_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    CHECK (
                        (object_kind = 'artifact' AND artifact_id IS NOT NULL
                            AND artifact_revision IS NOT NULL
                            AND artifact_record_sha256 IS NOT NULL)
                        OR
                        (object_kind = 'content' AND artifact_id IS NULL
                            AND artifact_revision IS NULL
                            AND artifact_record_sha256 IS NULL)
                    )
                );

                CREATE TABLE IF NOT EXISTS run_event_heads (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    current_sequence INTEGER NOT NULL,
                    current_event_id TEXT NOT NULL,
                    current_event_record_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id),
                    FOREIGN KEY (
                        project_id, current_event_id, current_event_record_sha256
                    ) REFERENCES events(project_id, event_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, run_id) REFERENCES runs(project_id, run_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
                BEGIN SELECT RAISE(ABORT, 'Events are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
                BEGIN SELECT RAISE(ABORT, 'Events cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS event_objects_no_update BEFORE UPDATE ON event_objects
                BEGIN SELECT RAISE(ABORT, 'Event objects are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS event_objects_no_delete BEFORE DELETE ON event_objects
                BEGIN SELECT RAISE(ABORT, 'Event objects cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS run_event_heads_no_delete BEFORE DELETE ON run_event_heads
                BEGIN SELECT RAISE(ABORT, 'Run Event heads cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS run_event_heads_monotonic
                BEFORE UPDATE ON run_event_heads
                WHEN NEW.current_sequence != OLD.current_sequence + 1
                  OR NEW.project_id != OLD.project_id
                  OR NEW.run_id != OLD.run_id
                BEGIN SELECT RAISE(ABORT, 'Run Event head must advance monotonically'); END;
                """
            )
        finally:
            connection.close()

    def append_event(
        self,
        requesting_access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        task_ref: TaskRef | None,
        run_ref: RunRef | None,
        graph_ref: GraphRef | None,
        node_ref: NodeRef | None,
        event_type: str,
        idempotency_key: str,
        actor_ref: str | None,
        object_refs: Sequence[EventObjectRef],
        metadata: Mapping[str, EventValue],
        payload_ref: ContentRef | None,
        authority_attempt: ExecutionAttempt | None,
    ) -> Event:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            event = self.append_event_in_transaction(
                connection,
                requesting_access,
                project_ref=project_ref,
                task_ref=task_ref,
                run_ref=run_ref,
                graph_ref=graph_ref,
                node_ref=node_ref,
                event_type=event_type,
                idempotency_key=idempotency_key,
                actor_ref=actor_ref,
                object_refs=object_refs,
                metadata=metadata,
                payload_ref=payload_ref,
                authority_attempt=authority_attempt,
            )
            connection.commit()
            return event
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            if "injected" in str(exc):
                raise
            raise EventConflictError("Event identity or sequence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def appendEvent(
        self,
        requesting_access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        task_ref: TaskRef | None,
        run_ref: RunRef | None,
        graph_ref: GraphRef | None,
        node_ref: NodeRef | None,
        event_type: str,
        idempotency_key: str,
        actor_ref: str | None,
        object_refs: Sequence[EventObjectRef],
        metadata: Mapping[str, EventValue],
        payload_ref: ContentRef | None,
        authority_attempt: ExecutionAttempt | None,
    ) -> Event:
        """Required compatibility spelling for appendEvent."""

        return self.append_event(
            requesting_access,
            project_ref=project_ref,
            task_ref=task_ref,
            run_ref=run_ref,
            graph_ref=graph_ref,
            node_ref=node_ref,
            event_type=event_type,
            idempotency_key=idempotency_key,
            actor_ref=actor_ref,
            object_refs=object_refs,
            metadata=metadata,
            payload_ref=payload_ref,
            authority_attempt=authority_attempt,
        )

    def append_event_in_transaction(
        self,
        connection: sqlite3.Connection,
        requesting_access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        task_ref: TaskRef | None,
        run_ref: RunRef | None,
        graph_ref: GraphRef | None,
        node_ref: NodeRef | None,
        event_type: str,
        idempotency_key: str,
        actor_ref: str | None,
        object_refs: Sequence[EventObjectRef],
        metadata: Mapping[str, EventValue],
        payload_ref: ContentRef | None,
        authority_attempt: ExecutionAttempt | None,
    ) -> Event:
        self._require_transaction(connection)
        if event_type == "RUN_CANCELLED":
            raise EventContractError(
                "RUN_CANCELLED must use the atomic Run cancellation Event API"
            )
        return self._append_in_transaction(
            connection,
            requesting_access,
            project_ref=project_ref,
            task_ref=task_ref,
            run_ref=run_ref,
            graph_ref=graph_ref,
            node_ref=node_ref,
            event_type=event_type,
            idempotency_key=idempotency_key,
            actor_ref=actor_ref,
            object_refs=object_refs,
            metadata=metadata,
            payload_ref=payload_ref,
            authority_attempt=authority_attempt,
            require_run_authority=True,
        )

    def request_run_cancellation_with_event(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
        *,
        idempotency_key: str,
        actor_ref: str,
        metadata: Mapping[str, EventValue],
    ) -> tuple[Run, Event]:
        self.runs.get_run(requesting_access, run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self.runs._fetch_run(connection, run_ref)
            prior_events = self._fetch_verified_run_events(connection, run_ref)
            cancellation_events = tuple(
                event for event in prior_events if event.event_type == "RUN_CANCELLED"
            )
            if current.status == "CANCELLED":
                if len(cancellation_events) != 1:
                    raise EventIntegrityError(
                        "Cancelled Run lacks exactly one atomic cancellation Event"
                    )
                if cancellation_events[0].idempotency_key != idempotency_key:
                    raise EventConflictError(
                        "Run cancellation already has a different idempotency identity"
                    )
                cancelled = current
            else:
                if cancellation_events:
                    raise EventIntegrityError(
                        "Live Run already has a terminal cancellation Event"
                    )
                cancelled = self.runs._request_run_cancellation_in_transaction(
                    connection,
                    requesting_access,
                    run_ref,
                )
            event = self._append_in_transaction(
                connection,
                requesting_access,
                project_ref=run_ref.project_ref,
                task_ref=cancelled.task_ref,
                run_ref=run_ref,
                graph_ref=None,
                node_ref=None,
                event_type="RUN_CANCELLED",
                idempotency_key=idempotency_key,
                actor_ref=actor_ref,
                object_refs=(),
                metadata=metadata,
                payload_ref=None,
                authority_attempt=None,
                require_run_authority=False,
            )
            connection.commit()
            return cancelled, event
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            if "injected" in str(exc):
                raise
            raise EventConflictError("Cancellation Event conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_event(
        self,
        requesting_access: ProjectAccess,
        event_ref: EventRef,
    ) -> Event:
        if not isinstance(event_ref, EventRef):
            raise TypeError("EventRef is required")
        self._authorize(requesting_access, event_ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            row = connection.execute(
                "SELECT * FROM events WHERE project_id = ? AND event_id = ?",
                (event_ref.project_ref.value, event_ref.event_id),
            ).fetchone()
            if row is None:
                raise EventNotFoundError("Event not found")
            event = self._event_from_row(connection, cast(sqlite3.Row, row))
            if event.run_ref is not None:
                self._fetch_verified_run_events(connection, event.run_ref)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        self._validate_relationships(requesting_access, event)
        return event

    def list_run_events(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> tuple[Event, ...]:
        self._authorize(requesting_access, run_ref.project_ref)
        self.runs.get_run(requesting_access, run_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            events = self._fetch_verified_run_events(connection, run_ref)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        for event in events:
            self._validate_relationships(requesting_access, event)
        return events

    def _append_in_transaction(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        task_ref: TaskRef | None,
        run_ref: RunRef | None,
        graph_ref: GraphRef | None,
        node_ref: NodeRef | None,
        event_type: str,
        idempotency_key: str,
        actor_ref: str | None,
        object_refs: Sequence[EventObjectRef],
        metadata: Mapping[str, EventValue],
        payload_ref: ContentRef | None,
        authority_attempt: ExecutionAttempt | None,
        require_run_authority: bool,
    ) -> Event:
        self._authorize(access, project_ref)
        self._validate_reference_scopes(
            project_ref,
            task_ref,
            run_ref,
            graph_ref,
            node_ref,
        )
        normalized_refs, artifact_evidence = self._normalize_object_refs(
            access,
            project_ref,
            object_refs,
        )
        run = self._require_run_authority(
            connection,
            access,
            run_ref,
            task_ref,
            authority_attempt,
            require_run_authority,
        )
        task_digest, graph, node_record_sha256 = self._validate_requested_relationships(
            access,
            project_ref,
            task_ref,
            run,
            graph_ref,
            node_ref,
        )
        frozen_metadata = _freeze_metadata(metadata)
        self._validate_static_fields(
            event_type,
            idempotency_key,
            actor_ref,
            payload_ref,
        )
        scope = self._scope_key(project_ref, run_ref)
        run_events = (
            ()
            if run_ref is None
            else self._fetch_verified_run_events(connection, run_ref)
        )
        existing_row = connection.execute(
            """
            SELECT * FROM events
            WHERE project_id = ? AND event_scope = ? AND idempotency_key = ?
            """,
            (project_ref.value, scope, idempotency_key),
        ).fetchone()
        if existing_row is not None:
            existing = self._event_from_row(connection, cast(sqlite3.Row, existing_row))
            candidate = Event(
                existing.event_ref,
                task_ref,
                run_ref,
                graph_ref,
                node_ref,
                existing.sequence,
                event_type,
                idempotency_key,
                actor_ref,
                normalized_refs,
                frozen_metadata,
                payload_ref,
                existing.created_at,
            )
            if not hmac.compare_digest(existing.semantic_digest, candidate.semantic_digest):
                raise EventConflictError("Event idempotency key has conflicting semantics")
            return existing
        sequence = None if run_ref is None else len(run_events) + 1
        event = Event(
            EventRef.new(project_ref),
            task_ref,
            run_ref,
            graph_ref,
            node_ref,
            sequence,
            event_type,
            idempotency_key,
            actor_ref,
            normalized_refs,
            frozen_metadata,
            payload_ref,
            self._database_now(connection),
        )
        self._insert_event(
            connection,
            event,
            task_digest=task_digest,
            graph=graph,
            node_record_sha256=node_record_sha256,
            artifact_evidence=artifact_evidence,
        )
        if run_ref is not None:
            self._advance_run_head(connection, event, run_events)
        return event

    @staticmethod
    def _validate_reference_scopes(
        project_ref: ProjectRef,
        task_ref: TaskRef | None,
        run_ref: RunRef | None,
        graph_ref: GraphRef | None,
        node_ref: NodeRef | None,
    ) -> None:
        for reference in (task_ref, run_ref, graph_ref, node_ref):
            if reference is not None and reference.project_ref != project_ref:
                raise EventScopeError("Event reference Project scope mismatch")
        if graph_ref is None and node_ref is not None:
            raise EventContractError("Event NodeRef requires GraphRef")
        if node_ref is not None and node_ref.graph_ref != graph_ref:
            raise EventContractError("Event NodeRef does not belong to GraphRef")

    def _require_run_authority(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        run_ref: RunRef | None,
        task_ref: TaskRef | None,
        attempt: ExecutionAttempt | None,
        required: bool,
    ) -> Run | None:
        if run_ref is None:
            if attempt is not None:
                raise EventAuthorityError("Project Event cannot carry Run authority")
            return None
        if required:
            if not isinstance(attempt, ExecutionAttempt):
                raise EventAuthorityError("Run Event requires current ExecutionAttempt")
            try:
                run = self.runs.assert_current_run_authority_in_transaction(
                    connection,
                    access,
                    attempt,
                )
            except (RunAuthorityError, RunError) as exc:
                raise EventAuthorityError("Run Event authority is stale or invalid") from exc
            if run.run_ref != run_ref:
                raise EventAuthorityError("ExecutionAttempt belongs to another Run")
        else:
            run = self.runs._fetch_run(connection, run_ref)
        if task_ref is not None and run.task_ref != task_ref:
            raise EventContractError("Event TaskRef does not match exact Run")
        return run

    def _validate_requested_relationships(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        task_ref: TaskRef | None,
        run: Run | None,
        graph_ref: GraphRef | None,
        node_ref: NodeRef | None,
    ) -> tuple[str | None, Graph | None, str | None]:
        if task_ref is not None and task_ref.project_ref != project_ref:
            raise EventScopeError("Event Task Project scope mismatch")
        if run is not None and run.project_ref != project_ref:
            raise EventScopeError("Event Run Project scope mismatch")
        task_digest = None
        if task_ref is not None:
            try:
                task = self.tasks.get_task(access, task_ref)
            except (TaskError, ProjectScopeError) as exc:
                raise EventContractError("Event TaskRef is not exact and authorized") from exc
            task_digest = task.canonical_digest
            if run is not None and (
                run.task_ref != task.task_ref
                or not hmac.compare_digest(run.task_digest, task.canonical_digest)
            ):
                raise EventContractError("Event Run and Task bindings differ")
        graph = None
        node_record_sha256 = None
        if graph_ref is not None:
            if graph_ref.project_ref != project_ref or run is None:
                raise EventScopeError("Event Graph Project or Run scope mismatch")
            try:
                graph = self.graphs.get_graph(access, graph_ref)
            except (GraphError, ProjectScopeError) as exc:
                raise EventContractError("Event GraphRef is not exact and authorized") from exc
            if graph.run_ref != run.run_ref:
                raise EventContractError("Event Graph does not belong to exact Run")
            if task_ref is not None and graph.task_ref != task_ref:
                raise EventContractError("Event Graph does not belong to exact Task")
        elif node_ref is not None:
            raise EventContractError("Event NodeRef requires GraphRef")
        if node_ref is not None:
            if node_ref.graph_ref != graph_ref or graph is None:
                raise EventContractError("Event NodeRef does not belong to GraphRef")
            node = next((candidate for candidate in graph.nodes if candidate.node_ref == node_ref), None)
            if node is None:
                raise EventContractError("Event NodeRef is not present in exact Graph")
            node_record_sha256 = node.record_sha256
        return task_digest, graph, node_record_sha256

    def _validate_relationships(self, access: ProjectAccess, event: Event) -> None:
        run = None if event.run_ref is None else self.runs.get_run(access, event.run_ref)
        self._validate_requested_relationships(
            access,
            event.project_ref,
            event.task_ref,
            run,
            event.graph_ref,
            event.node_ref,
        )
        self._normalize_object_ref_values(access, event.project_ref, event.object_refs)

    def _normalize_object_refs(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        values: Sequence[EventObjectRef],
    ) -> tuple[tuple[str, ...], dict[str, Artifact]]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise EventContractError("Event object_refs must be a sequence")
        if len(values) > 32:
            raise EventContractError("Event object_refs exceeds 32 entries")
        refs: list[str] = []
        artifacts: dict[str, Artifact] = {}
        content_annotations: dict[str, str] = {}
        for value in values:
            if isinstance(value, ArtifactRef):
                if value.project_ref != project_ref:
                    raise EventScopeError("Event ArtifactRef Project scope mismatch")
                try:
                    artifact = self.artifacts.get_artifact(access, value)
                except ArtifactError as exc:
                    raise EventContractError("Event ArtifactRef is not exact and authorized") from exc
                refs.append(value.value)
                artifacts[value.value] = artifact
            elif isinstance(value, ContentRef):
                prior_media = content_annotations.get(value.value)
                if prior_media is not None and prior_media != value.media_type:
                    raise EventContractError("Content identity has conflicting media annotations")
                content_annotations[value.value] = value.media_type
                refs.append(value.value)
            else:
                raise EventContractError("Event object ref must be ArtifactRef or ContentRef")
        return tuple(sorted(set(refs))), artifacts

    def _normalize_object_ref_values(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        values: Sequence[str],
    ) -> None:
        for value in values:
            artifact_match = _ARTIFACT_REF_PATTERN.fullmatch(value)
            if artifact_match is not None:
                artifact_ref = ArtifactRef(
                    ProjectRef(artifact_match.group(1)),
                    artifact_match.group(2),
                    int(artifact_match.group(3)),
                )
                if artifact_ref.project_ref != project_ref:
                    raise EventScopeError("Persisted Event Artifact scope mismatch")
                self.artifacts.get_artifact(access, artifact_ref)
            elif _CONTENT_REF_PATTERN.fullmatch(value) is None:
                raise EventIntegrityError("Persisted Event object identity is malformed")

    @staticmethod
    def _validate_static_fields(
        event_type: str,
        idempotency_key: str,
        actor_ref: str | None,
        payload_ref: ContentRef | None,
    ) -> None:
        if not isinstance(event_type, str) or _EVENT_TYPE_PATTERN.fullmatch(event_type) is None:
            raise EventContractError("Event type is malformed")
        if (
            not isinstance(idempotency_key, str)
            or _KEY_PATTERN.fullmatch(idempotency_key) is None
        ):
            raise EventContractError("Event idempotency key is malformed")
        _validate_actor_ref(actor_ref)
        if payload_ref is not None and not isinstance(payload_ref, ContentRef):
            raise EventContractError("Event payload must be ContentRef")

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        event: Event,
        *,
        task_digest: str | None,
        graph: Graph | None,
        node_record_sha256: str | None,
        artifact_evidence: Mapping[str, Artifact],
    ) -> None:
        connection.execute(
            """
            INSERT INTO events (
                project_id, event_id, event_scope, idempotency_key,
                task_id, task_revision, task_digest, run_id,
                graph_id, graph_revision, graph_record_sha256,
                node_id, node_record_sha256, sequence, event_type, actor_ref,
                object_refs_json, metadata_json, payload_ref_json,
                created_at, semantic_digest, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.project_ref.value,
                event.event_ref.event_id,
                self._scope_key(event.project_ref, event.run_ref),
                event.idempotency_key,
                None if event.task_ref is None else event.task_ref.task_id,
                None if event.task_ref is None else event.task_ref.revision,
                task_digest,
                None if event.run_ref is None else event.run_ref.run_id,
                None if event.graph_ref is None else event.graph_ref.graph_id,
                None if event.graph_ref is None else event.graph_ref.revision,
                None if graph is None else graph.record_sha256,
                None if event.node_ref is None else event.node_ref.node_id,
                node_record_sha256,
                event.sequence,
                event.event_type,
                event.actor_ref,
                _json(list(event.object_refs)),
                _json(dict(event.metadata)),
                None if event.payload_ref is None else _json(_content_payload(event.payload_ref)),
                event.created_at,
                event.semantic_digest,
                event.record_sha256,
            ),
        )
        for object_ref in event.object_refs:
            artifact = artifact_evidence.get(object_ref)
            kind = "artifact" if artifact is not None else "content"
            evidence_sha = None if artifact is None else artifact.record_sha256
            connection.execute(
                """
                INSERT INTO event_objects (
                    project_id, event_id, object_ref, object_kind,
                    artifact_id, artifact_revision, artifact_record_sha256,
                    record_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.project_ref.value,
                    event.event_ref.event_id,
                    object_ref,
                    kind,
                    None if artifact is None else artifact.artifact_id,
                    None if artifact is None else artifact.revision,
                    evidence_sha,
                    self._object_record_sha256(event.event_ref, object_ref, evidence_sha),
                ),
            )

    def _advance_run_head(
        self,
        connection: sqlite3.Connection,
        event: Event,
        prior_events: Sequence[Event],
    ) -> None:
        if event.run_ref is None or event.sequence is None:
            raise EventIntegrityError("Run Event head requires RunRef and sequence")
        head_sha = self._run_head_sha256(event)
        if not prior_events:
            connection.execute(
                "INSERT INTO run_event_heads VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.project_ref.value,
                    event.run_ref.run_id,
                    event.sequence,
                    event.event_ref.event_id,
                    event.record_sha256,
                    event.created_at,
                    head_sha,
                ),
            )
            return
        prior = prior_events[-1]
        updated = connection.execute(
            """
            UPDATE run_event_heads SET
                current_sequence = ?, current_event_id = ?,
                current_event_record_sha256 = ?, updated_at = ?, record_sha256 = ?
            WHERE project_id = ? AND run_id = ? AND current_sequence = ?
                AND current_event_id = ? AND current_event_record_sha256 = ?
                AND updated_at = ? AND record_sha256 = ?
            """,
            (
                event.sequence,
                event.event_ref.event_id,
                event.record_sha256,
                event.created_at,
                head_sha,
                prior.project_ref.value,
                event.run_ref.run_id,
                prior.sequence,
                prior.event_ref.event_id,
                prior.record_sha256,
                prior.created_at,
                self._run_head_sha256(prior),
            ),
        )
        if updated.rowcount != 1:
            raise EventConflictError("Run Event sequence changed concurrently")

    def _fetch_verified_run_events(
        self,
        connection: sqlite3.Connection,
        run_ref: RunRef,
    ) -> tuple[Event, ...]:
        if not connection.in_transaction:
            raise EventIntegrityError("Event reads require one durable snapshot")
        rows = connection.execute(
            """
            SELECT * FROM events
            WHERE project_id = ? AND run_id = ? ORDER BY sequence
            """,
            (run_ref.project_ref.value, run_ref.run_id),
        ).fetchall()
        head = connection.execute(
            "SELECT * FROM run_event_heads WHERE project_id = ? AND run_id = ?",
            (run_ref.project_ref.value, run_ref.run_id),
        ).fetchone()
        if not rows:
            if head is not None:
                raise EventIntegrityError("Run Event head exists without history")
            return ()
        events = tuple(self._event_from_row(connection, row) for row in rows)
        if tuple(event.sequence for event in events) != tuple(range(1, len(events) + 1)):
            raise EventIntegrityError("Run Event sequence history is not gap-free")
        if head is None:
            raise EventIntegrityError("Run Event head is missing")
        latest = events[-1]
        if (
            head["current_sequence"] != latest.sequence
            or head["current_event_id"] != latest.event_ref.event_id
            or head["current_event_record_sha256"] != latest.record_sha256
            or head["updated_at"] != latest.created_at
        ):
            raise EventIntegrityError("Run Event history does not match durable head")
        self._verify_digest(
            self._run_head_sha256(latest),
            head["record_sha256"],
            "Run Event head",
        )
        return events

    def _event_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> Event:
        try:
            project_ref = ProjectRef(cast(str, row["project_id"]))
            task_ref = (
                None
                if row["task_id"] is None
                else TaskRef(
                    project_ref,
                    cast(str, row["task_id"]),
                    cast(int, row["task_revision"]),
                )
            )
            run_ref = (
                None
                if row["run_id"] is None
                else RunRef(project_ref, cast(str, row["run_id"]))
            )
            graph_ref = (
                None
                if row["graph_id"] is None
                else GraphRef(
                    project_ref,
                    cast(str, row["graph_id"]),
                    cast(int, row["graph_revision"]),
                )
            )
            node_ref = (
                None
                if row["node_id"] is None or graph_ref is None
                else NodeRef(graph_ref, cast(str, row["node_id"]))
            )
            event = Event(
                EventRef(project_ref, cast(str, row["event_id"])),
                task_ref,
                run_ref,
                graph_ref,
                node_ref,
                cast(int | None, row["sequence"]),
                cast(str, row["event_type"]),
                cast(str, row["idempotency_key"]),
                cast(str | None, row["actor_ref"]),
                tuple(cast(list[str], json.loads(cast(str, row["object_refs_json"])))),
                cast(dict[str, EventValue], json.loads(cast(str, row["metadata_json"]))),
                self._parse_content(cast(str | None, row["payload_ref_json"])),
                cast(str, row["created_at"]),
            )
        except (TypeError, ValueError, KeyError, json.JSONDecodeError, EventError) as exc:
            raise EventIntegrityError("Persisted Event is malformed") from exc
        if row["event_scope"] != self._scope_key(event.project_ref, event.run_ref):
            raise EventIntegrityError("Persisted Event scope identity is inconsistent")
        self._verify_digest(event.semantic_digest, row["semantic_digest"], "Event semantics")
        self._verify_digest(event.record_sha256, row["record_sha256"], "Event record")
        self._verify_persisted_reference_evidence(connection, row, event)
        self._verify_event_objects(connection, event)
        return event

    def _verify_persisted_reference_evidence(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        event: Event,
    ) -> None:
        if event.task_ref is None:
            if any(
                row[name] is not None
                for name in ("task_id", "task_revision", "task_digest")
            ):
                raise EventIntegrityError("Event has orphan Task digest")
        else:
            task_row = connection.execute(
                """
                SELECT canonical_digest FROM task_revisions
                WHERE project_id = ? AND task_id = ? AND revision = ?
                """,
                (
                    event.project_ref.value,
                    event.task_ref.task_id,
                    event.task_ref.revision,
                ),
            ).fetchone()
            if task_row is None:
                raise EventIntegrityError("Event exact Task record is missing")
            self._verify_digest(
                cast(str, task_row["canonical_digest"]),
                row["task_digest"],
                "Event Task binding",
            )
        if event.run_ref is not None:
            run_row = connection.execute(
                "SELECT 1 FROM runs WHERE project_id = ? AND run_id = ?",
                (event.project_ref.value, event.run_ref.run_id),
            ).fetchone()
            if run_row is None:
                raise EventIntegrityError("Event exact Run record is missing")
        if event.graph_ref is None:
            if any(
                row[name] is not None
                for name in (
                    "graph_id",
                    "graph_revision",
                    "graph_record_sha256",
                    "node_id",
                    "node_record_sha256",
                )
            ):
                raise EventIntegrityError("Event has orphan Graph or Node evidence")
        else:
            graph_row = connection.execute(
                """
                SELECT record_sha256 FROM graph_revisions
                WHERE project_id = ? AND graph_id = ? AND revision = ?
                """,
                (
                    event.project_ref.value,
                    event.graph_ref.graph_id,
                    event.graph_ref.revision,
                ),
            ).fetchone()
            if graph_row is None:
                raise EventIntegrityError("Event exact Graph record is missing")
            self._verify_digest(
                cast(str, graph_row["record_sha256"]),
                row["graph_record_sha256"],
                "Event Graph binding",
            )
            if event.node_ref is None:
                if row["node_id"] is not None or row["node_record_sha256"] is not None:
                    raise EventIntegrityError("Event has orphan Node evidence")
            else:
                node_row = connection.execute(
                    """
                    SELECT record_sha256 FROM graph_nodes
                    WHERE project_id = ? AND graph_id = ?
                        AND graph_revision = ? AND node_id = ?
                    """,
                    (
                        event.project_ref.value,
                        event.graph_ref.graph_id,
                        event.graph_ref.revision,
                        event.node_ref.node_id,
                    ),
                ).fetchone()
                if node_row is None:
                    raise EventIntegrityError("Event exact Node record is missing")
                self._verify_digest(
                    cast(str, node_row["record_sha256"]),
                    row["node_record_sha256"],
                    "Event Node binding",
                )

    def _verify_event_objects(
        self,
        connection: sqlite3.Connection,
        event: Event,
    ) -> None:
        rows = connection.execute(
            """
            SELECT * FROM event_objects
            WHERE project_id = ? AND event_id = ? ORDER BY object_ref
            """,
            (event.project_ref.value, event.event_ref.event_id),
        ).fetchall()
        if tuple(row["object_ref"] for row in rows) != event.object_refs:
            raise EventIntegrityError("Event object bindings are inconsistent")
        for row in rows:
            evidence_sha = cast(str | None, row["artifact_record_sha256"])
            self._verify_digest(
                self._object_record_sha256(
                    event.event_ref,
                    cast(str, row["object_ref"]),
                    evidence_sha,
                ),
                row["record_sha256"],
                "Event object binding",
            )
            if row["object_kind"] == "artifact":
                matched = _ARTIFACT_REF_PATTERN.fullmatch(cast(str, row["object_ref"]))
                if (
                    matched is None
                    or row["artifact_id"] != matched.group(2)
                    or row["artifact_revision"] != int(matched.group(3))
                    or evidence_sha is None
                ):
                    raise EventIntegrityError("Event Artifact evidence is inconsistent")
                try:
                    artifact = self.artifacts._fetch_artifact(
                        connection,
                        ArtifactRef(event.project_ref, matched.group(2), int(matched.group(3))),
                    )
                except ArtifactError as exc:
                    raise EventIntegrityError("Event Artifact no longer verifies") from exc
                self._verify_digest(
                    artifact.record_sha256,
                    evidence_sha,
                    "Event Artifact record",
                )
            elif (
                row["object_kind"] != "content"
                or _CONTENT_REF_PATTERN.fullmatch(cast(str, row["object_ref"])) is None
                or evidence_sha is not None
            ):
                raise EventIntegrityError("Event Content evidence is inconsistent")

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectScopeError as exc:
            raise EventScopeError("Event Project scope mismatch") from exc

    def _require_transaction(self, connection: sqlite3.Connection) -> None:
        if not isinstance(connection, sqlite3.Connection) or not connection.in_transaction:
            raise EventContractError("Event transaction must already be active")
        database_file = connection.execute("PRAGMA database_list").fetchone()[2]
        if (
            not isinstance(database_file, str)
            or Path(database_file).resolve() != self.database_path
        ):
            raise EventContractError("Event transaction uses a different database")

    @staticmethod
    def _database_now(connection: sqlite3.Connection) -> str:
        value = connection.execute(
            "SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
        ).fetchone()[0]
        return _validate_timestamp(value, "database_now")

    @staticmethod
    def _scope_key(project_ref: ProjectRef, run_ref: RunRef | None) -> str:
        return project_ref.value if run_ref is None else run_ref.run_id

    @staticmethod
    def _object_record_sha256(
        event_ref: EventRef,
        object_ref: str,
        artifact_record_sha256: str | None,
    ) -> str:
        return _sha256(
            {
                "artifact_record_sha256": artifact_record_sha256,
                "event_ref": event_ref.value,
                "object_ref": object_ref,
            }
        )

    @staticmethod
    def _run_head_sha256(event: Event) -> str:
        if event.run_ref is None or event.sequence is None:
            raise EventIntegrityError("Run Event head requires Run identity")
        return _sha256(
            {
                "current_event_id": event.event_ref.event_id,
                "current_event_record_sha256": event.record_sha256,
                "current_sequence": event.sequence,
                "project_id": event.project_ref.value,
                "run_id": event.run_ref.run_id,
                "updated_at": event.created_at,
            }
        )

    @staticmethod
    def _parse_content(value: str | None) -> ContentRef | None:
        if value is None:
            return None
        parsed = cast(dict[str, object], json.loads(value))
        return ContentRef(
            cast(str, parsed["algorithm"]),
            cast(str, parsed["digest"]),
            cast(int, parsed["size_bytes"]),
            cast(str, parsed["media_type"]),
        )

    @staticmethod
    def _verify_digest(expected: str, persisted: object, label: str) -> None:
        if (
            not isinstance(persisted, str)
            or _SHA256_PATTERN.fullmatch(persisted) is None
            or not hmac.compare_digest(expected, persisted)
        ):
            raise EventIntegrityError(f"{label} failed integrity verification")
