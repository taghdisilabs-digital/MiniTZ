"""Durable, replaceable physical replicas behind Project-scoped Artifacts."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from typing import BinaryIO, Protocol, cast, runtime_checkable
from uuid import uuid4

from .artifact import Artifact, ArtifactRef, ArtifactService, ContentRef
from .object_store import (
    ContentLocation,
    ContentObject,
    ContentSource,
    ObjectStorageBackend,
    ObjectStorageContractError,
    ObjectStorageError,
    ObjectStorageIntegrityError,
    ObjectStorageNotFoundError,
    ReplicaState,
    _iter_chunks,
    _require_content_ref,
    _validate_expectation_contract,
    _validate_expected,
)
from .project import ProjectAccess, ProjectRef


_BACKEND_ID_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
_IMPLEMENTATION_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.-]{2,127}")
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_SECRET_REF_PATTERN = re.compile(r"secret://[^\s\x00-\x1f]{1,1024}")
_POLICY_REF_PATTERN = re.compile(r"policy://[^\s\x00-\x1f]{1,1024}")
_CHUNK_BYTES = 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class ReplicationError(ObjectStorageError):
    """Base class for replica coordination failures."""


class ReplicationContractError(ReplicationError, ValueError):
    """Replica request or backend registration is malformed."""


class ReplicationUnavailableError(ReplicationError):
    """No verified source or usable target can satisfy the operation."""


class ReplicationCancelledError(ReplicationError):
    """A durable cancellation request stopped replica transfer."""


class ReplicationStaleOwnerError(ReplicationError):
    """A superseded transfer owner attempted to publish replica state."""


class ReplicaBackendClass(str, Enum):
    """Evidence label distinguishing production and faithful reference backends."""

    REAL = "REAL"
    REFERENCE = "REFERENCE"


@dataclass(frozen=True)
class ReplicaBackendRegistration:
    """One replaceable backend binding; credentials remain opaque references."""

    backend_id: str
    backend: ObjectStorageBackend = field(repr=False, compare=False)
    backend_class: ReplicaBackendClass
    implementation: str
    priority: int
    network_egress: bool = False
    credential_secret_ref: str | None = field(default=None, repr=False)
    project_egress_policy_ref: str | None = field(default=None, repr=False)
    project_ref: ProjectRef | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.backend_id, str)
            or len(self.backend_id) > 63
            or _BACKEND_ID_PATTERN.fullmatch(self.backend_id) is None
        ):
            raise ReplicationContractError("backend_id is malformed")
        if not isinstance(self.backend, ObjectStorageBackend):
            raise ReplicationContractError("backend must implement ObjectStorageBackend")
        if not isinstance(self.backend_class, ReplicaBackendClass):
            raise ReplicationContractError("backend_class is malformed")
        if (
            not isinstance(self.implementation, str)
            or _IMPLEMENTATION_PATTERN.fullmatch(self.implementation) is None
        ):
            raise ReplicationContractError("implementation is malformed")
        if (
            not isinstance(self.priority, int)
            or isinstance(self.priority, bool)
            or self.priority < 0
            or self.priority > 1_000_000
        ):
            raise ReplicationContractError("priority is malformed")
        if not isinstance(self.network_egress, bool):
            raise ReplicationContractError("network_egress must be boolean")
        if self.credential_secret_ref is not None and (
            not isinstance(self.credential_secret_ref, str)
            or _SECRET_REF_PATTERN.fullmatch(self.credential_secret_ref) is None
        ):
            raise ReplicationContractError(
                "remote credentials must be represented by an opaque secret reference"
            )
        if self.project_egress_policy_ref is not None and (
            not isinstance(self.project_egress_policy_ref, str)
            or _POLICY_REF_PATTERN.fullmatch(self.project_egress_policy_ref) is None
        ):
            raise ReplicationContractError("Project egress policy reference is malformed")
        if self.network_egress and (
            self.credential_secret_ref is None
            or self.project_egress_policy_ref is None
            or self.project_ref is None
        ):
            raise ReplicationContractError(
                "network backends require Project-bound secret-ref and egress authority"
            )
        if not self.network_egress and (
            self.credential_secret_ref is not None
            or self.project_egress_policy_ref is not None
            or self.project_ref is not None
        ):
            raise ReplicationContractError(
                "local backends cannot claim remote Project, credential, or egress authority"
            )
        if self.project_ref is not None:
            if not isinstance(self.project_ref, ProjectRef):
                raise ReplicationContractError("network backend ProjectRef is malformed")
            required_prefix = f"policy://project/{self.project_ref.value}/"
            if not cast(str, self.project_egress_policy_ref).startswith(required_prefix):
                raise ReplicationContractError(
                    "network backend egress policy is not bound to its exact Project"
                )


@dataclass(frozen=True)
class ReplicationReceipt:
    """Bounded result evidence for one exact physical replication."""

    request_id: str
    content_ref: ContentRef
    source_backend_id: str
    target_backend_id: str
    bytes_transferred: int
    started_at: str
    completed_at: str
    replication_latency_seconds: float
    verification_latency_seconds: float
    throughput_bytes_per_second: float
    target_location: ContentLocation
    idempotent: bool


@dataclass(frozen=True)
class ReplicaMetrics:
    """Bounded aggregate transfer, verification, failure, and health metrics."""

    upload_bytes: int
    download_bytes: int
    replication_latency_seconds: float
    verification_latency_seconds: float
    throughput_bytes_per_second: float
    replication_failures: int
    corruption_detections: int
    backend_health: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _TransferAuthority:
    project_ref: ProjectRef
    content_digest: str
    backend_id: str
    request_id: str
    fence: int


@runtime_checkable
class _ReplicaMutableBackend(Protocol):
    def delete_replica(self, content_ref: ContentRef) -> None:
        """Delete exactly one physical object."""


class SQLiteObjectStorageBackend(ObjectStorageBackend):
    """Independent durable reference backend with atomic streamed BLOB writes."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS object_storage_objects (
                    algorithm TEXT NOT NULL,
                    digest TEXT PRIMARY KEY NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    payload BLOB NOT NULL
                );
                """
            )
        finally:
            connection.close()

    def put(
        self,
        source: ContentSource,
        *,
        media_type: str,
        expected_digest: str | None = None,
        expected_size: int | None = None,
    ) -> ContentRef:
        _validate_expectation_contract(expected_digest, expected_size)
        digest = hashlib.sha256()
        size_bytes = 0
        with tempfile.TemporaryFile(mode="w+b") as spool:
            for chunk in _iter_chunks(source):
                spool.write(chunk)
                digest.update(chunk)
                size_bytes += len(chunk)
            observed_digest = digest.hexdigest()
            _validate_expected(
                digest=observed_digest,
                size_bytes=size_bytes,
                expected_digest=expected_digest,
                expected_size=expected_size,
            )
            content_ref = ContentRef(
                algorithm="sha256",
                digest=observed_digest,
                size_bytes=size_bytes,
                media_type=media_type,
            )
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT rowid FROM object_storage_objects WHERE digest = ?",
                    (content_ref.digest,),
                ).fetchone()
                if existing is None:
                    cursor = connection.execute(
                        """
                        INSERT INTO object_storage_objects (
                            algorithm, digest, size_bytes, created_at, payload
                        ) VALUES (?, ?, ?, ?, zeroblob(?))
                        """,
                        (
                            content_ref.algorithm,
                            content_ref.digest,
                            content_ref.size_bytes,
                            _now(),
                            content_ref.size_bytes,
                        ),
                    )
                    rowid = cursor.lastrowid
                    if rowid is None:
                        raise ObjectStorageIntegrityError("reference backend lost row identity")
                    spool.seek(0)
                    blob = connection.blobopen(
                        "object_storage_objects",
                        "payload",
                        rowid,
                        readonly=False,
                    )
                    try:
                        while True:
                            chunk = spool.read(_CHUNK_BYTES)
                            if not chunk:
                                break
                            blob.write(chunk)
                    finally:
                        blob.close()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        self.verify(content_ref)
        return content_ref

    def _row(self, content_ref: ContentRef) -> sqlite3.Row:
        content_ref = _require_content_ref(content_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT rowid, algorithm, digest, size_bytes, created_at
                FROM object_storage_objects WHERE digest = ?
                """,
                (content_ref.digest,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ObjectStorageNotFoundError("content object is not present")
        if (
            row["algorithm"] != content_ref.algorithm
            or row["digest"] != content_ref.digest
            or row["size_bytes"] != content_ref.size_bytes
        ):
            raise ObjectStorageIntegrityError("reference metadata failed integrity verification")
        return cast(sqlite3.Row, row)

    def open(self, content_ref: ContentRef) -> BinaryIO:
        row = self._row(content_ref)
        connection = self._connect()
        snapshot = cast(
            BinaryIO,
            tempfile.SpooledTemporaryFile(max_size=_CHUNK_BYTES, mode="w+b"),
        )
        try:
            blob = connection.blobopen(
                "object_storage_objects",
                "payload",
                cast(int, row["rowid"]),
                readonly=True,
            )
            digest = hashlib.sha256()
            size_bytes = 0
            try:
                while True:
                    chunk = blob.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    snapshot.write(chunk)
                    digest.update(chunk)
                    size_bytes += len(chunk)
            finally:
                blob.close()
            if digest.hexdigest() != content_ref.digest or size_bytes != content_ref.size_bytes:
                raise ObjectStorageIntegrityError(
                    "stored bytes failed digest or size verification"
                )
            snapshot.seek(0)
            return snapshot
        except Exception:
            snapshot.close()
            raise
        finally:
            connection.close()

    def read(self, content_ref: ContentRef) -> bytes:
        with self.open(content_ref) as reader:
            return reader.read()

    def stat(self, content_ref: ContentRef) -> ContentObject:
        row = self._row(content_ref)
        self.verify(content_ref)
        return ContentObject(
            algorithm=content_ref.algorithm,
            digest=content_ref.digest,
            size_bytes=content_ref.size_bytes,
            media_type=content_ref.media_type,
            created_at=cast(str, row["created_at"]),
        )

    def exists(self, content_ref: ContentRef) -> bool:
        content_ref = _require_content_ref(content_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT 1 FROM object_storage_objects WHERE digest = ?",
                (content_ref.digest,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return False
        self.verify(content_ref)
        return True

    def location(self, content_ref: ContentRef) -> ContentLocation:
        row = self._row(content_ref)
        self.verify(content_ref)
        return ContentLocation(
            backend_id="sqlite-reference",
            locator=(
                f"sqlite-object://{hashlib.sha256(str(self.database_path).encode()).hexdigest()}"
                f"/sha256/{content_ref.digest}"
            ),
            content_digest=content_ref.digest,
            state=ReplicaState.AVAILABLE,
            size_bytes=content_ref.size_bytes,
            verified_at=_now(),
            created_at=cast(str, row["created_at"]),
        )

    def verify(self, content_ref: ContentRef) -> bool:
        with self.open(content_ref):
            pass
        return True

    def delete_replica(self, content_ref: ContentRef) -> None:
        content_ref = _require_content_ref(content_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM object_storage_objects WHERE digest = ?",
                (content_ref.digest,),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class ReplicatedObjectStore:
    """Artifact-authorized coordinator for independently verified physical replicas."""

    def __init__(
        self,
        database_path: str | Path,
        artifacts: ArtifactService,
        backends: Sequence[ReplicaBackendRegistration],
    ) -> None:
        self.database_path = Path(database_path).resolve()
        if not isinstance(artifacts, ArtifactService):
            raise ReplicationContractError("ArtifactService is required")
        if not isinstance(backends, Sequence) or not backends:
            raise ReplicationContractError("at least one replica backend is required")
        registrations: dict[str, ReplicaBackendRegistration] = {}
        for registration in backends:
            if not isinstance(registration, ReplicaBackendRegistration):
                raise ReplicationContractError("backend registration is malformed")
            if registration.backend_id in registrations:
                raise ReplicationContractError("backend_id must be unique")
            registrations[registration.backend_id] = registration
        self.artifacts = artifacts
        self._backends = registrations
        self._initialize_schema()
        self._register_backends()

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
                CREATE TABLE IF NOT EXISTS replica_backends (
                    backend_id TEXT PRIMARY KEY NOT NULL,
                    backend_class TEXT NOT NULL,
                    implementation TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    network_egress INTEGER NOT NULL,
                    credential_secret_ref TEXT,
                    project_egress_policy_ref TEXT,
                    project_id TEXT,
                    registered_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS content_replica_observations (
                    content_digest TEXT NOT NULL,
                    backend_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    locator TEXT NOT NULL,
                    state TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    verified_at TEXT,
                    created_at TEXT NOT NULL,
                    failure_ref TEXT,
                    observed_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (content_digest, backend_id, sequence),
                    FOREIGN KEY (backend_id) REFERENCES replica_backends(backend_id)
                        ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS content_replica_heads (
                    content_digest TEXT NOT NULL,
                    backend_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (content_digest, backend_id),
                    FOREIGN KEY (content_digest, backend_id, sequence)
                        REFERENCES content_replica_observations(
                            content_digest, backend_id, sequence
                        ) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS replica_cancellations (
                    project_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    content_digest TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, request_id)
                );

                CREATE TABLE IF NOT EXISTS replica_transfer_events (
                    project_id TEXT NOT NULL,
                    content_digest TEXT NOT NULL,
                    backend_id TEXT NOT NULL,
                    fence INTEGER NOT NULL,
                    event_sequence INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (
                        project_id, content_digest, backend_id,
                        fence, event_sequence
                    ),
                    FOREIGN KEY (backend_id) REFERENCES replica_backends(backend_id)
                        ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS replica_transfer_heads (
                    project_id TEXT NOT NULL,
                    content_digest TEXT NOT NULL,
                    backend_id TEXT NOT NULL,
                    fence INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, content_digest, backend_id)
                );

                CREATE TABLE IF NOT EXISTS replica_metric_events (
                    event_id TEXT PRIMARY KEY NOT NULL,
                    backend_id TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY (backend_id) REFERENCES replica_backends(backend_id)
                        ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS content_replica_observations_no_update
                BEFORE UPDATE ON content_replica_observations
                BEGIN SELECT RAISE(ABORT, 'replica observations are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS content_replica_observations_no_delete
                BEFORE DELETE ON content_replica_observations
                BEGIN SELECT RAISE(ABORT, 'replica observations are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS content_replica_heads_no_delete
                BEFORE DELETE ON content_replica_heads
                BEGIN SELECT RAISE(ABORT, 'replica heads cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS replica_metric_events_no_update
                BEFORE UPDATE ON replica_metric_events
                BEGIN SELECT RAISE(ABORT, 'replica metrics are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS replica_metric_events_no_delete
                BEFORE DELETE ON replica_metric_events
                BEGIN SELECT RAISE(ABORT, 'replica metrics are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS replica_transfer_events_no_update
                BEFORE UPDATE ON replica_transfer_events
                BEGIN SELECT RAISE(ABORT, 'replica transfer events are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS replica_transfer_events_no_delete
                BEFORE DELETE ON replica_transfer_events
                BEGIN SELECT RAISE(ABORT, 'replica transfer events are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS replica_transfer_heads_no_delete
                BEFORE DELETE ON replica_transfer_heads
                BEGIN SELECT RAISE(ABORT, 'replica transfer heads cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def _register_backends(self) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            for registration in self._backends.values():
                fields: dict[str, object] = {
                    "backend_class": registration.backend_class.value,
                    "backend_id": registration.backend_id,
                    "credential_secret_ref": registration.credential_secret_ref,
                    "implementation": registration.implementation,
                    "network_egress": registration.network_egress,
                    "priority": registration.priority,
                    "project_egress_policy_ref": registration.project_egress_policy_ref,
                    "project_ref": (
                        None
                        if registration.project_ref is None
                        else registration.project_ref.value
                    ),
                }
                record_sha256 = hashlib.sha256(_json(fields).encode()).hexdigest()
                existing = connection.execute(
                    "SELECT record_sha256 FROM replica_backends WHERE backend_id = ?",
                    (registration.backend_id,),
                ).fetchone()
                if existing is not None:
                    if existing["record_sha256"] != record_sha256:
                        raise ReplicationContractError(
                            "durable backend registration conflicts with runtime binding"
                        )
                    continue
                connection.execute(
                    """
                    INSERT INTO replica_backends (
                        backend_id, backend_class, implementation, priority,
                        network_egress, credential_secret_ref,
                        project_egress_policy_ref, project_id,
                        registered_at, record_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        registration.backend_id,
                        registration.backend_class.value,
                        registration.implementation,
                        registration.priority,
                        int(registration.network_egress),
                        registration.credential_secret_ref,
                        registration.project_egress_policy_ref,
                        (
                            None
                            if registration.project_ref is None
                            else registration.project_ref.value
                        ),
                        _now(),
                        record_sha256,
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _failure_ref(stage: str, error: BaseException | None = None) -> str:
        category = "none" if error is None else type(error).__name__
        digest = hashlib.sha256(f"{stage}:{category}".encode()).hexdigest()
        return f"failure://sha256/{digest}"

    def _artifact(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
    ) -> tuple[Artifact, ContentRef]:
        if not isinstance(artifact_ref, ArtifactRef):
            raise TypeError("ArtifactRef is required for physical replica authority")
        artifact = self.artifacts.get_artifact(requesting_access, artifact_ref)
        if artifact.content_ref is None:
            raise ReplicationContractError("Artifact has no physical content")
        return artifact, artifact.content_ref

    def _backend(self, backend_id: str) -> ReplicaBackendRegistration:
        try:
            return self._backends[backend_id]
        except KeyError as exc:
            raise ReplicationContractError("replica backend is not registered") from exc

    @staticmethod
    def _authorize_backend(
        registration: ReplicaBackendRegistration,
        project_ref: ProjectRef,
    ) -> None:
        if registration.network_egress and registration.project_ref != project_ref:
            raise ReplicationUnavailableError(
                "network backend lacks exact Project egress authority"
            )

    def _fallback_locator(self, backend_id: str, content_ref: ContentRef) -> str:
        return f"backend://{backend_id}/sha256/{content_ref.digest}"

    def _record_observation(
        self,
        content_ref: ContentRef,
        backend_id: str,
        state: ReplicaState,
        *,
        locator: str | None = None,
        verified_at: str | None = None,
        created_at: str | None = None,
        failure_ref: str | None = None,
        transfer_authority: _TransferAuthority | None = None,
    ) -> ContentLocation:
        registration = self._backend(backend_id)
        del registration
        observed_at = _now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if transfer_authority is not None:
                self._assert_transfer(connection, transfer_authority)
            prior = connection.execute(
                """
                SELECT o.* FROM content_replica_heads h
                JOIN content_replica_observations o
                  ON o.content_digest = h.content_digest
                 AND o.backend_id = h.backend_id
                 AND o.sequence = h.sequence
                WHERE h.content_digest = ? AND h.backend_id = ?
                """,
                (content_ref.digest, backend_id),
            ).fetchone()
            sequence = 1 if prior is None else cast(int, prior["sequence"]) + 1
            selected_locator = (
                cast(str, prior["locator"])
                if locator is None and prior is not None
                else self._fallback_locator(backend_id, content_ref)
                if locator is None
                else locator
            )
            selected_created_at = (
                cast(str, prior["created_at"])
                if created_at is None and prior is not None
                else observed_at
                if created_at is None
                else created_at
            )
            fields: dict[str, object] = {
                "backend_id": backend_id,
                "content_digest": content_ref.digest,
                "created_at": selected_created_at,
                "failure_ref": failure_ref,
                "locator": selected_locator,
                "sequence": sequence,
                "size_bytes": content_ref.size_bytes,
                "state": state.value,
                "verified_at": verified_at,
            }
            record_sha256 = hashlib.sha256(_json(fields).encode()).hexdigest()
            connection.execute(
                """
                INSERT INTO content_replica_observations (
                    content_digest, backend_id, sequence, locator, state,
                    size_bytes, verified_at, created_at, failure_ref,
                    observed_at, record_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    content_ref.digest,
                    backend_id,
                    sequence,
                    selected_locator,
                    state.value,
                    content_ref.size_bytes,
                    verified_at,
                    selected_created_at,
                    failure_ref,
                    observed_at,
                    record_sha256,
                ),
            )
            connection.execute(
                """
                INSERT INTO content_replica_heads (
                    content_digest, backend_id, sequence, record_sha256
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(content_digest, backend_id) DO UPDATE SET
                    sequence = excluded.sequence,
                    record_sha256 = excluded.record_sha256
                """,
                (content_ref.digest, backend_id, sequence, record_sha256),
            )
            connection.commit()
            return ContentLocation(
                backend_id=backend_id,
                locator=selected_locator,
                content_digest=content_ref.digest,
                state=state,
                size_bytes=content_ref.size_bytes,
                verified_at=verified_at,
                created_at=selected_created_at,
                failure_ref=failure_ref,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _transfer_record_sha256(
        authority: _TransferAuthority,
        event_sequence: int,
        state: str,
    ) -> str:
        return hashlib.sha256(
            _json(
                {
                    "backend_id": authority.backend_id,
                    "content_digest": authority.content_digest,
                    "event_sequence": event_sequence,
                    "fence": authority.fence,
                    "project_id": authority.project_ref.value,
                    "request_id": authority.request_id,
                    "state": state,
                }
            ).encode()
        ).hexdigest()

    @staticmethod
    def _assert_transfer(
        connection: sqlite3.Connection,
        authority: _TransferAuthority,
    ) -> None:
        row = connection.execute(
            """
            SELECT fence, request_id, state FROM replica_transfer_heads
            WHERE project_id = ? AND content_digest = ? AND backend_id = ?
            """,
            (
                authority.project_ref.value,
                authority.content_digest,
                authority.backend_id,
            ),
        ).fetchone()
        if (
            row is None
            or row["fence"] != authority.fence
            or row["request_id"] != authority.request_id
            or row["state"] != "ACTIVE"
        ):
            raise ReplicationStaleOwnerError(
                "replica transfer owner was durably superseded"
            )

    def _acquire_transfer(
        self,
        project_ref: ProjectRef,
        content_ref: ContentRef,
        backend_id: str,
        request_id: str,
    ) -> _TransferAuthority:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                """
                SELECT fence FROM replica_transfer_heads
                WHERE project_id = ? AND content_digest = ? AND backend_id = ?
                """,
                (project_ref.value, content_ref.digest, backend_id),
            ).fetchone()
            fence = 1 if prior is None else cast(int, prior["fence"]) + 1
            authority = _TransferAuthority(
                project_ref=project_ref,
                content_digest=content_ref.digest,
                backend_id=backend_id,
                request_id=request_id,
                fence=fence,
            )
            record_sha256 = self._transfer_record_sha256(authority, 1, "ACTIVE")
            connection.execute(
                """
                INSERT INTO replica_transfer_events (
                    project_id, content_digest, backend_id, fence,
                    event_sequence, request_id, state, observed_at, record_sha256
                ) VALUES (?, ?, ?, ?, 1, ?, 'ACTIVE', ?, ?)
                """,
                (
                    project_ref.value,
                    content_ref.digest,
                    backend_id,
                    fence,
                    request_id,
                    _now(),
                    record_sha256,
                ),
            )
            connection.execute(
                """
                INSERT INTO replica_transfer_heads (
                    project_id, content_digest, backend_id, fence,
                    request_id, state, record_sha256
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?)
                ON CONFLICT(project_id, content_digest, backend_id) DO UPDATE SET
                    fence = excluded.fence,
                    request_id = excluded.request_id,
                    state = excluded.state,
                    record_sha256 = excluded.record_sha256
                """,
                (
                    project_ref.value,
                    content_ref.digest,
                    backend_id,
                    fence,
                    request_id,
                    record_sha256,
                ),
            )
            connection.commit()
            return authority
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _finish_transfer(
        self,
        authority: _TransferAuthority,
        state: str,
    ) -> None:
        if state not in {"COMPLETED", "FAILED", "CANCELLED", "CORRUPT"}:
            raise ReplicationContractError("transfer terminal state is malformed")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_transfer(connection, authority)
            record_sha256 = self._transfer_record_sha256(authority, 2, state)
            connection.execute(
                """
                INSERT INTO replica_transfer_events (
                    project_id, content_digest, backend_id, fence,
                    event_sequence, request_id, state, observed_at, record_sha256
                ) VALUES (?, ?, ?, ?, 2, ?, ?, ?, ?)
                """,
                (
                    authority.project_ref.value,
                    authority.content_digest,
                    authority.backend_id,
                    authority.fence,
                    authority.request_id,
                    state,
                    _now(),
                    record_sha256,
                ),
            )
            connection.execute(
                """
                UPDATE replica_transfer_heads
                SET state = ?, record_sha256 = ?
                WHERE project_id = ? AND content_digest = ? AND backend_id = ?
                  AND fence = ? AND request_id = ? AND state = 'ACTIVE'
                """,
                (
                    state,
                    record_sha256,
                    authority.project_ref.value,
                    authority.content_digest,
                    authority.backend_id,
                    authority.fence,
                    authority.request_id,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _location_from_row(row: sqlite3.Row) -> ContentLocation:
        fields: dict[str, object] = {
            "backend_id": row["backend_id"],
            "content_digest": row["content_digest"],
            "created_at": row["created_at"],
            "failure_ref": row["failure_ref"],
            "locator": row["locator"],
            "sequence": row["sequence"],
            "size_bytes": row["size_bytes"],
            "state": row["state"],
            "verified_at": row["verified_at"],
        }
        expected_record_sha256 = hashlib.sha256(_json(fields).encode()).hexdigest()
        if (
            row["record_sha256"] != expected_record_sha256
            or (
                "head_record_sha256" in row.keys()
                and row["head_record_sha256"] != expected_record_sha256
            )
        ):
            raise ObjectStorageIntegrityError(
                "durable replica observation failed integrity verification"
            )
        return ContentLocation(
            backend_id=cast(str, row["backend_id"]),
            locator=cast(str, row["locator"]),
            content_digest=cast(str, row["content_digest"]),
            state=ReplicaState(cast(str, row["state"])),
            size_bytes=cast(int, row["size_bytes"]),
            verified_at=cast(str | None, row["verified_at"]),
            created_at=cast(str, row["created_at"]),
            failure_ref=cast(str | None, row["failure_ref"]),
        )

    def _head_locations(self, content_ref: ContentRef) -> tuple[ContentLocation, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT o.*, h.record_sha256 AS head_record_sha256
                FROM content_replica_heads h
                JOIN content_replica_observations o
                  ON o.content_digest = h.content_digest
                 AND o.backend_id = h.backend_id
                 AND o.sequence = h.sequence
                WHERE h.content_digest = ?
                """,
                (content_ref.digest,),
            ).fetchall()
        finally:
            connection.close()
        return tuple(
            sorted(
                (self._location_from_row(row) for row in rows),
                key=lambda item: (
                    self._backend(item.backend_id).priority,
                    item.backend_id,
                ),
            )
        )

    def _metric(self, backend_id: str, metric: str, value: float) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """
                INSERT INTO replica_metric_events (
                    event_id, backend_id, metric, value, occurred_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (f"rme_{uuid4().hex}", backend_id, metric, value, _now()),
            )
            connection.commit()
        finally:
            connection.close()

    def registerArtifactReplica(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
        backend_id: str,
    ) -> ContentLocation:
        """Register an already-present replica only after independent verification."""

        artifact, content_ref = self._artifact(requesting_access, artifact_ref)
        registration = self._backend(backend_id)
        self._authorize_backend(registration, artifact.project_ref)
        started = time.monotonic()
        self._independent_verify(registration.backend, content_ref)
        verification_latency = time.monotonic() - started
        self._metric(backend_id, "verification_latency_seconds", verification_latency)
        physical = registration.backend.location(content_ref)
        return self._record_observation(
            content_ref,
            backend_id,
            ReplicaState.AVAILABLE,
            locator=physical.locator,
            verified_at=_now(),
            created_at=physical.created_at,
        )

    def locations(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
    ) -> tuple[ContentLocation, ...]:
        """Return bounded latest replica observations after Artifact authorization."""

        _, content_ref = self._artifact(requesting_access, artifact_ref)
        return self._head_locations(content_ref)

    def observationHistory(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
        backend_id: str,
    ) -> tuple[ContentLocation, ...]:
        """Return append-only state evidence for one authorized replica."""

        _, content_ref = self._artifact(requesting_access, artifact_ref)
        self._backend(backend_id)
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT * FROM content_replica_observations
                WHERE content_digest = ? AND backend_id = ?
                ORDER BY sequence
                """,
                (content_ref.digest, backend_id),
            ).fetchall()
        finally:
            connection.close()
        return tuple(self._location_from_row(row) for row in rows)

    def cancelReplication(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
        request_id: str,
    ) -> None:
        """Durably request cancellation; repeated requests are idempotent."""

        artifact, content_ref = self._artifact(requesting_access, artifact_ref)
        if (
            not isinstance(request_id, str)
            or _REQUEST_ID_PATTERN.fullmatch(request_id) is None
        ):
            raise ReplicationContractError("request_id is malformed")
        connection = self._connect()
        try:
            connection.execute(
                """
                INSERT INTO replica_cancellations (
                    project_id, request_id, content_digest, requested_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id, request_id) DO NOTHING
                """,
                (
                    artifact.project_ref.value,
                    request_id,
                    content_ref.digest,
                    _now(),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def _cancelled(
        self,
        project_ref: ProjectRef,
        content_ref: ContentRef,
        request_id: str,
    ) -> bool:
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT 1 FROM replica_cancellations
                WHERE project_id = ? AND request_id = ? AND content_digest = ?
                """,
                (project_ref.value, request_id, content_ref.digest),
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    @staticmethod
    def _independent_verify(
        backend: ObjectStorageBackend,
        content_ref: ContentRef,
    ) -> None:
        digest = hashlib.sha256()
        size_bytes = 0
        with backend.open(content_ref) as reader:
            while True:
                chunk = reader.read(_CHUNK_BYTES)
                if not isinstance(chunk, bytes):
                    raise ObjectStorageIntegrityError(
                        "backend reader returned mutable or non-byte content"
                    )
                if not chunk:
                    break
                digest.update(chunk)
                size_bytes += len(chunk)
        if digest.hexdigest() != content_ref.digest or size_bytes != content_ref.size_bytes:
            raise ObjectStorageIntegrityError(
                "independent read-back failed digest or size verification"
            )

    def _verified_source(
        self,
        project_ref: ProjectRef,
        content_ref: ContentRef,
        *,
        exclude_backend_id: str | None = None,
    ) -> ReplicaBackendRegistration:
        for location in self._head_locations(content_ref):
            if (
                location.backend_id == exclude_backend_id
                or location.state is not ReplicaState.AVAILABLE
            ):
                continue
            registration = self._backend(location.backend_id)
            self._authorize_backend(registration, project_ref)
            started = time.monotonic()
            try:
                if not registration.backend.exists(content_ref):
                    self._record_observation(
                        content_ref,
                        location.backend_id,
                        ReplicaState.MISSING,
                        failure_ref=self._failure_ref("source-missing"),
                    )
                    self._metric(location.backend_id, "replication_failures", 1)
                    continue
                self._independent_verify(registration.backend, content_ref)
                self._metric(
                    location.backend_id,
                    "verification_latency_seconds",
                    time.monotonic() - started,
                )
                return registration
            except ObjectStorageNotFoundError as exc:
                self._record_observation(
                    content_ref,
                    location.backend_id,
                    ReplicaState.MISSING,
                    failure_ref=self._failure_ref("source-missing", exc),
                )
                self._metric(location.backend_id, "replication_failures", 1)
            except (ObjectStorageIntegrityError, ObjectStorageError) as exc:
                self._record_observation(
                    content_ref,
                    location.backend_id,
                    ReplicaState.CORRUPT,
                    failure_ref=self._failure_ref("source-corrupt", exc),
                )
                self._metric(location.backend_id, "corruption_detections", 1)
        raise ReplicationUnavailableError("no healthy independently verified source replica")

    def replicateContent(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
        target_backend_id: str,
        *,
        request_id: str | None = None,
        chunk_delay_seconds: float = 0.0,
    ) -> ReplicationReceipt:
        """Stream one authorized Artifact's ContentRef to an independently verified target."""

        artifact, content_ref = self._artifact(requesting_access, artifact_ref)
        target = self._backend(target_backend_id)
        self._authorize_backend(target, artifact.project_ref)
        selected_request_id = (
            f"rep_{uuid4().hex}" if request_id is None else request_id
        )
        if _REQUEST_ID_PATTERN.fullmatch(selected_request_id) is None:
            raise ReplicationContractError("request_id is malformed")
        if (
            not isinstance(chunk_delay_seconds, (int, float))
            or isinstance(chunk_delay_seconds, bool)
            or chunk_delay_seconds < 0
            or chunk_delay_seconds > 1
        ):
            raise ReplicationContractError("chunk_delay_seconds is malformed")
        started_at = _now()
        started = time.monotonic()

        current = {
            location.backend_id: location
            for location in self._head_locations(content_ref)
        }.get(target_backend_id)
        if current is not None and current.state is ReplicaState.AVAILABLE:
            verification_started = time.monotonic()
            try:
                self._independent_verify(target.backend, content_ref)
            except (ObjectStorageError, OSError, sqlite3.Error):
                pass
            else:
                verification_latency = time.monotonic() - verification_started
                completed_at = _now()
                elapsed = time.monotonic() - started
                self._metric(
                    target_backend_id,
                    "verification_latency_seconds",
                    verification_latency,
                )
                return ReplicationReceipt(
                    request_id=selected_request_id,
                    content_ref=content_ref,
                    source_backend_id=target_backend_id,
                    target_backend_id=target_backend_id,
                    bytes_transferred=0,
                    started_at=started_at,
                    completed_at=completed_at,
                    replication_latency_seconds=elapsed,
                    verification_latency_seconds=verification_latency,
                    throughput_bytes_per_second=0.0,
                    target_location=current,
                    idempotent=True,
                )

        source = self._verified_source(
            artifact.project_ref,
            content_ref,
            exclude_backend_id=target_backend_id,
        )
        transfer_authority = self._acquire_transfer(
            artifact.project_ref,
            content_ref,
            target_backend_id,
            selected_request_id,
        )
        self._record_observation(
            content_ref,
            target_backend_id,
            ReplicaState.UPLOADING,
            transfer_authority=transfer_authority,
        )
        transferred = 0
        verification_latency = 0.0
        try:
            with source.backend.open(content_ref) as reader:

                def chunks() -> Iterator[bytes]:
                    nonlocal transferred
                    while True:
                        if self._cancelled(
                            artifact.project_ref,
                            content_ref,
                            selected_request_id,
                        ):
                            raise ReplicationCancelledError("replication cancelled")
                        chunk = reader.read(_CHUNK_BYTES)
                        if not isinstance(chunk, bytes):
                            raise ObjectStorageIntegrityError(
                                "source reader returned mutable or non-byte content"
                            )
                        if not chunk:
                            return
                        transferred += len(chunk)
                        yield chunk
                        if chunk_delay_seconds:
                            time.sleep(chunk_delay_seconds)

                stored_ref = target.backend.put(
                    chunks(),
                    media_type=content_ref.media_type,
                    expected_digest=content_ref.digest,
                    expected_size=content_ref.size_bytes,
                )
            if stored_ref != content_ref:
                raise ObjectStorageIntegrityError(
                    "target returned a different immutable content identity"
                )
            try:
                physical = target.backend.location(content_ref)
                locator = physical.locator
                created_at = physical.created_at
            except ObjectStorageError:
                locator = self._fallback_locator(target_backend_id, content_ref)
                created_at = _now()
            self._record_observation(
                content_ref,
                target_backend_id,
                ReplicaState.VERIFYING,
                locator=locator,
                created_at=created_at,
                transfer_authority=transfer_authority,
            )
            verification_started = time.monotonic()
            self._independent_verify(target.backend, content_ref)
            verification_latency = time.monotonic() - verification_started
            available = self._record_observation(
                content_ref,
                target_backend_id,
                ReplicaState.AVAILABLE,
                locator=locator,
                verified_at=_now(),
                created_at=created_at,
                transfer_authority=transfer_authority,
            )
            self._finish_transfer(transfer_authority, "COMPLETED")
        except ReplicationStaleOwnerError:
            raise
        except ReplicationCancelledError as exc:
            self._record_observation(
                content_ref,
                target_backend_id,
                ReplicaState.FAILED,
                failure_ref=self._failure_ref("cancelled", exc),
                transfer_authority=transfer_authority,
            )
            self._finish_transfer(transfer_authority, "CANCELLED")
            self._metric(target_backend_id, "replication_failures", 1)
            raise
        except ObjectStorageIntegrityError as exc:
            self._record_observation(
                content_ref,
                target_backend_id,
                ReplicaState.CORRUPT,
                failure_ref=self._failure_ref("target-corrupt", exc),
                transfer_authority=transfer_authority,
            )
            self._finish_transfer(transfer_authority, "CORRUPT")
            self._metric(target_backend_id, "corruption_detections", 1)
            self._metric(target_backend_id, "replication_failures", 1)
            raise ReplicationUnavailableError(
                "target failed independent digest and size verification"
            ) from exc
        except (ObjectStorageError, OSError, sqlite3.Error) as exc:
            self._record_observation(
                content_ref,
                target_backend_id,
                ReplicaState.FAILED,
                failure_ref=self._failure_ref("target-failed", exc),
                transfer_authority=transfer_authority,
            )
            self._finish_transfer(transfer_authority, "FAILED")
            self._metric(target_backend_id, "replication_failures", 1)
            raise ReplicationUnavailableError("target replica upload failed") from exc

        elapsed = time.monotonic() - started
        completed_at = _now()
        self._metric(target_backend_id, "upload_bytes", transferred)
        self._metric(source.backend_id, "download_bytes", transferred)
        self._metric(target_backend_id, "replication_latency_seconds", elapsed)
        self._metric(
            target_backend_id,
            "verification_latency_seconds",
            verification_latency,
        )
        return ReplicationReceipt(
            request_id=selected_request_id,
            content_ref=content_ref,
            source_backend_id=source.backend_id,
            target_backend_id=target_backend_id,
            bytes_transferred=transferred,
            started_at=started_at,
            completed_at=completed_at,
            replication_latency_seconds=elapsed,
            verification_latency_seconds=verification_latency,
            throughput_bytes_per_second=(
                float(transferred) / elapsed if elapsed > 0 else float(transferred)
            ),
            target_location=available,
            idempotent=False,
        )

    def openArtifact(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
    ) -> BinaryIO:
        """Open deterministic healthy replica bytes after Project authorization."""

        artifact, content_ref = self._artifact(requesting_access, artifact_ref)
        source = self._verified_source(artifact.project_ref, content_ref)
        try:
            reader = source.backend.open(content_ref)
        except ObjectStorageNotFoundError as exc:
            self._record_observation(
                content_ref,
                source.backend_id,
                ReplicaState.MISSING,
                failure_ref=self._failure_ref("read-missing", exc),
            )
            return self.openArtifact(requesting_access, artifact_ref)
        except ObjectStorageError as exc:
            self._record_observation(
                content_ref,
                source.backend_id,
                ReplicaState.CORRUPT,
                failure_ref=self._failure_ref("read-corrupt", exc),
            )
            self._metric(source.backend_id, "corruption_detections", 1)
            return self.openArtifact(requesting_access, artifact_ref)
        self._metric(source.backend_id, "download_bytes", content_ref.size_bytes)
        return reader

    def readArtifact(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
    ) -> bytes:
        """Read exact authorized bytes from the deterministic healthy replica."""

        with self.openArtifact(requesting_access, artifact_ref) as reader:
            return reader.read()

    def repairReplica(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
        backend_id: str,
    ) -> ReplicationReceipt:
        """Replace a recorded failed physical copy from another verified source."""

        artifact, content_ref = self._artifact(requesting_access, artifact_ref)
        target = self._backend(backend_id)
        heads = {item.backend_id: item for item in self._head_locations(content_ref)}
        prior = heads.get(backend_id)
        if prior is None or prior.state is ReplicaState.AVAILABLE:
            raise ReplicationContractError(
                "repair requires a prior CORRUPT, MISSING, or FAILED observation"
            )
        if not isinstance(target.backend, _ReplicaMutableBackend):
            raise ReplicationUnavailableError("target backend cannot remove a failed replica")
        self._authorize_backend(target, artifact.project_ref)
        self._verified_source(
            artifact.project_ref,
            content_ref,
            exclude_backend_id=backend_id,
        )
        target.backend.delete_replica(content_ref)
        return self.replicateContent(
            requesting_access,
            artifact_ref,
            backend_id,
        )

    def deleteReplica(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
        backend_id: str,
    ) -> ContentLocation:
        """Delete one physical replica only while another verified copy survives."""

        artifact, content_ref = self._artifact(requesting_access, artifact_ref)
        target = self._backend(backend_id)
        self._authorize_backend(target, artifact.project_ref)
        self._verified_source(
            artifact.project_ref,
            content_ref,
            exclude_backend_id=backend_id,
        )
        if not isinstance(target.backend, _ReplicaMutableBackend):
            raise ReplicationUnavailableError("target backend cannot delete physical replicas")
        target.backend.delete_replica(content_ref)
        return self._record_observation(
            content_ref,
            backend_id,
            ReplicaState.MISSING,
            failure_ref=self._failure_ref("physical-delete"),
        )

    def metrics(self) -> ReplicaMetrics:
        """Return durable bounded aggregate metrics and current backend health."""

        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT metric, COALESCE(SUM(value), 0) AS total
                FROM replica_metric_events GROUP BY metric
                """
            ).fetchall()
            head_rows = connection.execute(
                """
                SELECT o.backend_id, o.state FROM content_replica_heads h
                JOIN content_replica_observations o
                  ON o.content_digest = h.content_digest
                 AND o.backend_id = h.backend_id
                 AND o.sequence = h.sequence
                """
            ).fetchall()
        finally:
            connection.close()
        totals = {cast(str, row["metric"]): float(row["total"]) for row in rows}
        states: dict[str, set[str]] = {
            backend_id: set() for backend_id in self._backends
        }
        for row in head_rows:
            states[cast(str, row["backend_id"])].add(cast(str, row["state"]))
        health: list[tuple[str, str]] = []
        for backend_id in sorted(states):
            backend_states = states[backend_id]
            if any(state != ReplicaState.AVAILABLE.value for state in backend_states):
                label = "DEGRADED"
            elif backend_states:
                label = "HEALTHY"
            else:
                label = "UNKNOWN"
            health.append((backend_id, label))
        return ReplicaMetrics(
            upload_bytes=int(totals.get("upload_bytes", 0.0)),
            download_bytes=int(totals.get("download_bytes", 0.0)),
            replication_latency_seconds=totals.get(
                "replication_latency_seconds", 0.0
            ),
            verification_latency_seconds=totals.get(
                "verification_latency_seconds", 0.0
            ),
            throughput_bytes_per_second=(
                totals.get("upload_bytes", 0.0)
                / totals.get("replication_latency_seconds", 1.0)
                if totals.get("replication_latency_seconds", 0.0) > 0
                else 0.0
            ),
            replication_failures=int(totals.get("replication_failures", 0.0)),
            corruption_detections=int(totals.get("corruption_detections", 0.0)),
            backend_health=tuple(health),
        )
