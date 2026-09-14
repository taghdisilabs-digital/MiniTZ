"""Project-scoped PostgreSQL capability adapter with durable, bounded evidence.

The public contracts in this module contain only exact identities and digests.
Authentication material is supplied at the last possible moment and is never
serialized into MiniTZ's durable state or object storage.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import ctypes
import ctypes.util
import hashlib
import hmac
import ipaddress
import json
from pathlib import Path
import re
import select
import sqlite3
import tempfile
import threading
import time
from types import MappingProxyType
from typing import IO, Protocol, cast, runtime_checkable
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from .artifact import ArtifactRef, ArtifactService, ContentRef
from .call_ledger import (
    CallAuthorityError,
    CallConflictError,
    CallLedgerService,
    ToolCall,
    ToolCallRef,
)
from .capability import Capability, CapabilityRef, CapabilityRegistry
from .execution import NodeExecutionAttempt
from .graph import GraphService, NodeRef
from .object_store import ObjectStorageBackend, ObjectStorageError
from .project import (
    ProjectAccess,
    ProjectIntegrityError,
    ProjectNotFoundError,
    ProjectRef,
    ProjectScopeError,
    ProjectStore,
)
from .routing import (
    CapabilityImplementation,
    CapabilityImplementationRef,
    CapabilityImplementationRegistry,
    ImplementationKind,
    RoutingNotFoundError,
)
from .run import ExecutionAttempt, RunRef, RunService
from .task import Task, TaskRef, TaskRevisionService


_IDENTITY = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,1024}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_CONNECTION_ID = re.compile(r"dbc_[0-9a-f]{32}")
_OPERATION_ID = re.compile(r"dbop_[0-9a-f]{32}")
_TRANSACTION_ID = re.compile(r"dbtx_[0-9a-f]{32}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SECRET_PATTERNS = (
    re.compile(r"(?i)(?:password|passwd|secret|token|api[_-]?key)\s*[:=]"),
    re.compile(r"(?i)postgres(?:ql)?://[^/\s:@]+:[^/\s@]+@"),
)
_OPERATIONS = ("connect", "inspect_schema", "query", "transaction", "execute", "migrate")
_REQUEST_MEDIA_TYPE = "application/vnd.minitz.postgresql-request+json"
_RECEIPT_MEDIA_TYPE = "application/vnd.minitz.postgresql-receipt+json"
_RESULT_MEDIA_TYPE = "application/vnd.minitz.postgresql-rows+jsonl"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise DatabaseContractError(f"{name} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise DatabaseContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DatabaseContractError(f"{name} must be timezone-aware")
    return value


def _identity(value: object, name: str) -> str:
    if not isinstance(value, str) or _IDENTITY.fullmatch(value) is None:
        raise DatabaseContractError(f"{name} must be an exact bounded reference")
    if value.startswith("secret://"):
        return value
    if any(pattern.search(value) is not None for pattern in _SECRET_PATTERNS):
        raise DatabaseContractError(f"{name} contains credential-like material")
    return value


def _key(value: object, name: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise DatabaseContractError(f"{name} is malformed")
    return value


def _text(value: object, name: str, maximum: int = 2048) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode()) > maximum
        or any(ord(character) < 32 and character not in "\n\t" for character in value)
    ):
        raise DatabaseContractError(f"{name} is malformed or unbounded")
    return value


def _content_payload(value: ContentRef | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "algorithm": value.algorithm,
        "digest": value.digest,
        "media_type": value.media_type,
        "size_bytes": value.size_bytes,
    }


def _content_from_payload(value: object) -> ContentRef | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise DatabaseIntegrityError("persisted ContentRef is malformed")
    try:
        return ContentRef(
            cast(str, value["algorithm"]),
            cast(str, value["digest"]),
            cast(int, value["size_bytes"]),
            cast(str, value["media_type"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DatabaseIntegrityError("persisted ContentRef is malformed") from exc


class DatabaseAdapterError(Exception):
    """Base class for PostgreSQL adapter failures."""


class DatabaseContractError(DatabaseAdapterError, ValueError):
    """A database contract is malformed or unbounded."""


class DatabaseScopeError(DatabaseAdapterError):
    """A database operation crossed Project or infrastructure scope."""


class DatabaseAuthorityError(DatabaseAdapterError, PermissionError):
    """A database operation lacks exact live Task/Node authority."""


class DatabaseConflictError(DatabaseAdapterError):
    """An immutable database claim has conflicting semantics."""


class DatabaseNotFoundError(DatabaseAdapterError):
    """An exact database connection, transaction, or result is unavailable."""


class DatabaseIntegrityError(DatabaseAdapterError):
    """Durable database evidence failed integrity verification."""


class DatabaseScope(str, Enum):
    PROJECT = "PROJECT"
    GLOBAL_INFRASTRUCTURE = "GLOBAL_INFRASTRUCTURE"


class DatabaseQueryMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    MUTATING = "MUTATING"
    DDL_MIGRATION = "DDL_MIGRATION"


class DatabaseTlsMode(str, Enum):
    VERIFY_FULL = "VERIFY_FULL"
    VERIFY_CA = "VERIFY_CA"
    REQUIRE = "REQUIRE"
    ALLOW_LOCAL_PLAINTEXT = "ALLOW_LOCAL_PLAINTEXT"


class DatabaseFailureCategory(str, Enum):
    CONNECTION_FAILED = "CONNECTION_FAILED"
    AUTH_FAILED = "AUTH_FAILED"
    TLS_FAILED = "TLS_FAILED"
    QUERY_FAILED = "QUERY_FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    RESULT_LIMIT = "RESULT_LIMIT"
    TRANSACTION_ABORTED = "TRANSACTION_ABORTED"
    TRANSACTION_OUTCOME_UNKNOWN = "TRANSACTION_OUTCOME_UNKNOWN"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    MIGRATION_FAILED = "MIGRATION_FAILED"
    POLICY_DENIED = "POLICY_DENIED"


class DatabaseTransactionAction(str, Enum):
    BEGIN = "BEGIN"
    COMMIT = "COMMIT"
    ROLLBACK = "ROLLBACK"
    CANCEL = "CANCEL"


class DatabaseTransactionState(str, Enum):
    OPEN = "OPEN"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"
    ABORTED = "ABORTED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


@dataclass(frozen=True, order=True)
class DatabaseConnectionRef:
    scope: DatabaseScope
    connection_id: str
    project_ref: ProjectRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, DatabaseScope):
            raise DatabaseContractError("DatabaseConnectionRef scope is malformed")
        if not isinstance(self.connection_id, str) or _CONNECTION_ID.fullmatch(self.connection_id) is None:
            raise DatabaseContractError("database connection identity is malformed")
        if self.scope is DatabaseScope.PROJECT and not isinstance(self.project_ref, ProjectRef):
            raise DatabaseContractError("Project database connection requires ProjectRef")
        if self.scope is DatabaseScope.GLOBAL_INFRASTRUCTURE and self.project_ref is not None:
            raise DatabaseContractError("infrastructure database connection cannot carry ProjectRef")

    @classmethod
    def new_project(cls, project_ref: ProjectRef) -> DatabaseConnectionRef:
        return cls(DatabaseScope.PROJECT, f"dbc_{uuid4().hex}", project_ref)

    @classmethod
    def new_infrastructure(cls) -> DatabaseConnectionRef:
        return cls(DatabaseScope.GLOBAL_INFRASTRUCTURE, f"dbc_{uuid4().hex}")

    @property
    def value(self) -> str:
        scope = "global-infrastructure" if self.project_ref is None else self.project_ref.value
        return f"database-connection://{scope}/{self.connection_id}"


@dataclass(frozen=True, order=True)
class DatabaseOperationRef:
    project_ref: ProjectRef
    operation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise DatabaseContractError("DatabaseOperationRef requires ProjectRef")
        if not isinstance(self.operation_id, str) or _OPERATION_ID.fullmatch(self.operation_id) is None:
            raise DatabaseContractError("database operation identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> DatabaseOperationRef:
        return cls(project_ref, f"dbop_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"database-operation://{self.project_ref.value}/{self.operation_id}"


@dataclass(frozen=True, order=True)
class DatabaseTransactionRef:
    project_ref: ProjectRef
    transaction_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise DatabaseContractError("DatabaseTransactionRef requires ProjectRef")
        if not isinstance(self.transaction_id, str) or _TRANSACTION_ID.fullmatch(self.transaction_id) is None:
            raise DatabaseContractError("database transaction identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> DatabaseTransactionRef:
        return cls(project_ref, f"dbtx_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"database-transaction://{self.project_ref.value}/{self.transaction_id}"


@dataclass(frozen=True)
class DatabaseTlsConfig:
    mode: DatabaseTlsMode
    root_certificate_ref: str | None = None
    minimum_protocol: str = "TLSv1.2"

    def __post_init__(self) -> None:
        if not isinstance(self.mode, DatabaseTlsMode):
            raise DatabaseContractError("database TLS mode is malformed")
        if self.root_certificate_ref is not None:
            _identity(self.root_certificate_ref, "root certificate ref")
        if self.mode is DatabaseTlsMode.VERIFY_CA and self.root_certificate_ref is None:
            raise DatabaseContractError("VERIFY_CA requires a root certificate ref")
        _text(self.minimum_protocol, "minimum TLS protocol", 32)

    def payload(self) -> dict[str, object]:
        return {
            "minimum_protocol": self.minimum_protocol,
            "mode": self.mode.value,
            "root_certificate_ref": self.root_certificate_ref,
        }


@dataclass(frozen=True)
class DatabaseRestrictions:
    allowed_modes: tuple[DatabaseQueryMode, ...]
    allow_transactions: bool
    allow_migrations: bool
    production: bool
    max_timeout_seconds: float = 60.0
    max_rows: int = 100_000
    max_result_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        if not isinstance(self.allowed_modes, tuple) or not self.allowed_modes:
            raise DatabaseContractError("database allowed modes are required")
        if not all(isinstance(item, DatabaseQueryMode) for item in self.allowed_modes):
            raise DatabaseContractError("database allowed modes are malformed")
        object.__setattr__(self, "allowed_modes", tuple(sorted(set(self.allowed_modes), key=lambda item: item.value)))
        if not all(isinstance(item, bool) for item in (self.allow_transactions, self.allow_migrations, self.production)):
            raise DatabaseContractError("database restriction flags are malformed")
        if not isinstance(self.max_timeout_seconds, (int, float)) or isinstance(self.max_timeout_seconds, bool) or not 0 < self.max_timeout_seconds <= 3600:
            raise DatabaseContractError("database maximum timeout is malformed")
        for value, name, maximum in (
            (self.max_rows, "maximum rows", 10_000_000),
            (self.max_result_bytes, "maximum result bytes", 1024 * 1024 * 1024),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= maximum:
                raise DatabaseContractError(f"database {name} is malformed")

    def payload(self) -> dict[str, object]:
        return {
            "allow_migrations": self.allow_migrations,
            "allow_transactions": self.allow_transactions,
            "allowed_modes": [item.value for item in self.allowed_modes],
            "max_result_bytes": self.max_result_bytes,
            "max_rows": self.max_rows,
            "max_timeout_seconds": float(self.max_timeout_seconds),
            "production": self.production,
        }


@dataclass(frozen=True)
class DatabaseConnection:
    connection_ref: DatabaseConnectionRef
    adapter_ref: str
    endpoint_identity: str
    database_identity: str
    auth_profile_ref: str
    tls: DatabaseTlsConfig
    restrictions: DatabaseRestrictions
    created_at: str = field(default_factory=_now)
    canonical_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.connection_ref, DatabaseConnectionRef):
            raise DatabaseContractError("DatabaseConnection requires exact ref")
        for value, name in (
            (self.adapter_ref, "database adapter ref"),
            (self.endpoint_identity, "database endpoint identity"),
            (self.database_identity, "database identity"),
            (self.auth_profile_ref, "database auth profile ref"),
        ):
            _identity(value, name)
        if not isinstance(self.tls, DatabaseTlsConfig) or not isinstance(self.restrictions, DatabaseRestrictions):
            raise DatabaseContractError("database TLS or restrictions are malformed")
        _timestamp(self.created_at, "database connection created_at")
        payload = self.payload()
        object.__setattr__(self, "canonical_digest", _digest(payload))
        object.__setattr__(self, "record_sha256", _digest({"kind": "DatabaseConnection", "payload": payload}))

    @classmethod
    def create_project(
        cls,
        project_ref: ProjectRef,
        *,
        endpoint_identity: str,
        database_identity: str,
        auth_profile_ref: str,
        tls: DatabaseTlsConfig,
        restrictions: DatabaseRestrictions,
    ) -> DatabaseConnection:
        return cls(
            DatabaseConnectionRef.new_project(project_ref),
            "adapter://minitz/database/postgresql/libpq",
            endpoint_identity,
            database_identity,
            auth_profile_ref,
            tls,
            restrictions,
        )

    @property
    def project_ref(self) -> ProjectRef | None:
        return self.connection_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "auth_profile_ref": self.auth_profile_ref,
            "connection_ref": self.connection_ref.value,
            "created_at": self.created_at,
            "database_identity": self.database_identity,
            "endpoint_identity": self.endpoint_identity,
            "restrictions": self.restrictions.payload(),
            "scope": self.connection_ref.scope.value,
            "tls": self.tls.payload(),
        }


@dataclass(frozen=True)
class DatabaseExecutionBinding:
    task_ref: TaskRef
    task_digest: str
    run_ref: RunRef
    node_ref: NodeRef
    node_attempt_id: str
    node_fence: int

    def __post_init__(self) -> None:
        if not isinstance(self.task_ref, TaskRef) or not isinstance(self.run_ref, RunRef) or not isinstance(self.node_ref, NodeRef):
            raise DatabaseContractError("database execution binding requires Task/Run/Node refs")
        if self.task_ref.project_ref != self.run_ref.project_ref or self.task_ref.project_ref != self.node_ref.project_ref:
            raise DatabaseScopeError("database execution binding crossed Project scope")
        if not isinstance(self.task_digest, str) or _SHA256.fullmatch(self.task_digest) is None:
            raise DatabaseContractError("database Task digest is malformed")
        _text(self.node_attempt_id, "database Node attempt identity", 128)
        if not isinstance(self.node_fence, int) or isinstance(self.node_fence, bool) or self.node_fence < 1:
            raise DatabaseContractError("database Node fence is malformed")

    @classmethod
    def from_attempt(cls, attempt: NodeExecutionAttempt) -> DatabaseExecutionBinding:
        return cls(
            attempt.task_ref,
            attempt.task_digest,
            attempt.run_ref,
            attempt.node_ref,
            attempt.attempt_id,
            attempt.fence,
        )

    @property
    def project_ref(self) -> ProjectRef:
        return self.task_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "node_attempt_id": self.node_attempt_id,
            "node_fence": self.node_fence,
            "node_ref": self.node_ref.value,
            "run_ref": f"run://{self.run_ref.project_ref.value}/{self.run_ref.run_id}",
            "task_digest": self.task_digest,
            "task_ref": (
                f"task://{self.task_ref.project_ref.value}/{self.task_ref.task_id}"
                f"/{self.task_ref.revision}"
            ),
        }


def _validate_limits(timeout_seconds: float, max_rows: int, max_result_bytes: int) -> None:
    if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 0 < timeout_seconds <= 3600:
        raise DatabaseContractError("database timeout is malformed")
    if not isinstance(max_rows, int) or isinstance(max_rows, bool) or not 0 < max_rows <= 10_000_000:
        raise DatabaseContractError("database row bound is malformed")
    if not isinstance(max_result_bytes, int) or isinstance(max_result_bytes, bool) or not 0 < max_result_bytes <= 1024 * 1024 * 1024:
        raise DatabaseContractError("database byte bound is malformed")


@dataclass(frozen=True)
class DatabaseConnectRequest:
    operation_ref: DatabaseOperationRef
    connection_ref: DatabaseConnectionRef
    binding: DatabaseExecutionBinding
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        _request_scope(self.operation_ref, self.connection_ref, self.binding)
        _validate_limits(self.timeout_seconds, 1, 1)

    def payload(self) -> dict[str, object]:
        return {
            "binding": self.binding.payload(),
            "connection_ref": self.connection_ref.value,
            "operation": "connect",
            "operation_ref": self.operation_ref.value,
            "timeout_seconds": float(self.timeout_seconds),
        }


@dataclass(frozen=True)
class DatabaseQueryRequest:
    operation_ref: DatabaseOperationRef
    connection_ref: DatabaseConnectionRef
    binding: DatabaseExecutionBinding
    statement_ref: ContentRef
    parameter_refs: tuple[ContentRef, ...]
    mode: DatabaseQueryMode
    timeout_seconds: float
    max_rows: int
    max_result_bytes: int
    transaction_ref: DatabaseTransactionRef | None = None
    persist_result: bool = False

    def __post_init__(self) -> None:
        _request_scope(self.operation_ref, self.connection_ref, self.binding)
        if not isinstance(self.statement_ref, ContentRef) or self.statement_ref.media_type not in {"application/sql", "text/plain"}:
            raise DatabaseContractError("database statement must be an exact SQL ContentRef")
        if not isinstance(self.parameter_refs, tuple) or len(self.parameter_refs) > 1024 or not all(isinstance(item, ContentRef) for item in self.parameter_refs):
            raise DatabaseContractError("database parameter refs are malformed or unbounded")
        if not all(item.media_type == "application/json" for item in self.parameter_refs):
            raise DatabaseContractError("database parameters must be exact JSON scalar ContentRefs")
        if not isinstance(self.mode, DatabaseQueryMode):
            raise DatabaseContractError("database query mode is malformed")
        _validate_limits(self.timeout_seconds, self.max_rows, self.max_result_bytes)
        if self.transaction_ref is not None and self.transaction_ref.project_ref != self.binding.project_ref:
            raise DatabaseScopeError("database transaction crossed Project scope")
        if not isinstance(self.persist_result, bool):
            raise DatabaseContractError("database persistence flag is malformed")

    def payload(self) -> dict[str, object]:
        return {
            "binding": self.binding.payload(),
            "connection_ref": self.connection_ref.value,
            "max_result_bytes": self.max_result_bytes,
            "max_rows": self.max_rows,
            "mode": self.mode.value,
            "operation": "query" if self.mode is DatabaseQueryMode.READ_ONLY else "execute",
            "operation_ref": self.operation_ref.value,
            "parameter_refs": [item.value for item in self.parameter_refs],
            "persist_result": self.persist_result,
            "statement_ref": self.statement_ref.value,
            "timeout_seconds": float(self.timeout_seconds),
            "transaction_ref": None if self.transaction_ref is None else self.transaction_ref.value,
        }


@dataclass(frozen=True)
class DatabaseTransactionRequest:
    operation_ref: DatabaseOperationRef
    transaction_ref: DatabaseTransactionRef
    connection_ref: DatabaseConnectionRef
    binding: DatabaseExecutionBinding
    action: DatabaseTransactionAction
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        _request_scope(self.operation_ref, self.connection_ref, self.binding)
        if not isinstance(self.transaction_ref, DatabaseTransactionRef) or self.transaction_ref.project_ref != self.binding.project_ref:
            raise DatabaseScopeError("database transaction request crossed Project scope")
        if not isinstance(self.action, DatabaseTransactionAction):
            raise DatabaseContractError("database transaction action is malformed")
        _validate_limits(self.timeout_seconds, 1, 1)

    def payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "binding": self.binding.payload(),
            "connection_ref": self.connection_ref.value,
            "operation": "transaction",
            "operation_ref": self.operation_ref.value,
            "timeout_seconds": float(self.timeout_seconds),
            "transaction_ref": self.transaction_ref.value,
        }


@dataclass(frozen=True)
class DatabaseSchemaRequest:
    operation_ref: DatabaseOperationRef
    connection_ref: DatabaseConnectionRef
    binding: DatabaseExecutionBinding
    timeout_seconds: float = 20.0
    max_objects: int = 10_000
    max_result_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        _request_scope(self.operation_ref, self.connection_ref, self.binding)
        _validate_limits(self.timeout_seconds, self.max_objects, self.max_result_bytes)

    def payload(self) -> dict[str, object]:
        return {
            "binding": self.binding.payload(),
            "connection_ref": self.connection_ref.value,
            "max_objects": self.max_objects,
            "max_result_bytes": self.max_result_bytes,
            "operation": "inspect_schema",
            "operation_ref": self.operation_ref.value,
            "timeout_seconds": float(self.timeout_seconds),
        }


@dataclass(frozen=True)
class DatabaseMigrationRequest:
    operation_ref: DatabaseOperationRef
    connection_ref: DatabaseConnectionRef
    binding: DatabaseExecutionBinding
    migration_artifact_ref: ArtifactRef
    expected_before_schema_sha256: str
    expected_after_schema_sha256: str | None
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        _request_scope(self.operation_ref, self.connection_ref, self.binding)
        if not isinstance(self.migration_artifact_ref, ArtifactRef) or self.migration_artifact_ref.project_ref != self.binding.project_ref:
            raise DatabaseScopeError("database migration Artifact crossed Project scope")
        if _SHA256.fullmatch(self.expected_before_schema_sha256) is None:
            raise DatabaseContractError("migration expected-before schema digest is malformed")
        if self.expected_after_schema_sha256 is not None and _SHA256.fullmatch(self.expected_after_schema_sha256) is None:
            raise DatabaseContractError("migration expected-after schema digest is malformed")
        _validate_limits(self.timeout_seconds, 1, 1)

    def payload(self) -> dict[str, object]:
        return {
            "binding": self.binding.payload(),
            "connection_ref": self.connection_ref.value,
            "expected_after_schema_sha256": self.expected_after_schema_sha256,
            "expected_before_schema_sha256": self.expected_before_schema_sha256,
            "migration_artifact_ref": self.migration_artifact_ref.value,
            "operation": "migrate",
            "operation_ref": self.operation_ref.value,
            "timeout_seconds": float(self.timeout_seconds),
        }


def _request_scope(
    operation_ref: DatabaseOperationRef,
    connection_ref: DatabaseConnectionRef,
    binding: DatabaseExecutionBinding,
) -> None:
    if not isinstance(operation_ref, DatabaseOperationRef) or not isinstance(connection_ref, DatabaseConnectionRef) or not isinstance(binding, DatabaseExecutionBinding):
        raise DatabaseContractError("database request identities are malformed")
    if operation_ref.project_ref != binding.project_ref:
        raise DatabaseScopeError("database operation crossed Project scope")
    if connection_ref.scope is not DatabaseScope.PROJECT or connection_ref.project_ref != binding.project_ref:
        raise DatabaseScopeError("generic Project database request cannot use infrastructure or another Project connection")


@dataclass(frozen=True)
class DatabaseConnectResult:
    operation_ref: DatabaseOperationRef
    connection_ref: DatabaseConnectionRef
    success: bool
    server_version: str | None
    tls_active: bool | None
    failure: DatabaseFailureCategory | None
    sqlstate: str | None
    message: str | None
    tool_call_ref: ToolCallRef
    receipt_ref: ContentRef
    pool_identity: str
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _result_common(self.operation_ref, self.connection_ref, self.success, self.failure, self.tool_call_ref, self.receipt_ref, self.completed_at)
        if not isinstance(self.pool_identity, str) or not self.pool_identity.startswith("database-pool://"):
            raise DatabaseContractError("database pool identity is malformed")
        object.__setattr__(self, "record_sha256", _digest({"kind": "DatabaseConnectResult", "payload": self.payload()}))

    def payload(self) -> dict[str, object]:
        return {
            "completed_at": self.completed_at,
            "connection_ref": self.connection_ref.value,
            "failure": None if self.failure is None else self.failure.value,
            "message": self.message,
            "operation_ref": self.operation_ref.value,
            "pool_identity": self.pool_identity,
            "receipt_ref": self.receipt_ref.value,
            "server_version": self.server_version,
            "sqlstate": self.sqlstate,
            "success": self.success,
            "tls_active": self.tls_active,
            "tool_call_ref": self.tool_call_ref.value,
        }


@dataclass(frozen=True)
class DatabaseQueryResult:
    operation_ref: DatabaseOperationRef
    connection_ref: DatabaseConnectionRef
    mode: DatabaseQueryMode
    success: bool
    row_count: int
    affected_rows: int | None
    result_ref: ContentRef | None
    result_artifact_ref: ArtifactRef | None
    statement_sha256: str
    parameter_sha256: str
    failure: DatabaseFailureCategory | None
    sqlstate: str | None
    message: str | None
    tool_call_ref: ToolCallRef
    receipt_ref: ContentRef
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _result_common(self.operation_ref, self.connection_ref, self.success, self.failure, self.tool_call_ref, self.receipt_ref, self.completed_at)
        if not isinstance(self.mode, DatabaseQueryMode):
            raise DatabaseContractError("database result mode is malformed")
        for value, name in ((self.row_count, "row count"),):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise DatabaseContractError(f"database result {name} is malformed")
        if self.affected_rows is not None and (not isinstance(self.affected_rows, int) or isinstance(self.affected_rows, bool) or self.affected_rows < 0):
            raise DatabaseContractError("database affected-row count is malformed")
        if _SHA256.fullmatch(self.statement_sha256) is None or _SHA256.fullmatch(self.parameter_sha256) is None:
            raise DatabaseContractError("database query digests are malformed")
        object.__setattr__(self, "record_sha256", _digest({"kind": "DatabaseQueryResult", "payload": self.payload()}))

    def payload(self) -> dict[str, object]:
        return {
            "affected_rows": self.affected_rows,
            "completed_at": self.completed_at,
            "connection_ref": self.connection_ref.value,
            "failure": None if self.failure is None else self.failure.value,
            "message": self.message,
            "mode": self.mode.value,
            "operation_ref": self.operation_ref.value,
            "parameter_sha256": self.parameter_sha256,
            "receipt_ref": self.receipt_ref.value,
            "result_artifact_ref": None if self.result_artifact_ref is None else self.result_artifact_ref.value,
            "result_ref": _content_payload(self.result_ref),
            "row_count": self.row_count,
            "sqlstate": self.sqlstate,
            "statement_sha256": self.statement_sha256,
            "success": self.success,
            "tool_call_ref": self.tool_call_ref.value,
        }


@dataclass(frozen=True)
class DatabaseTransactionResult:
    operation_ref: DatabaseOperationRef
    transaction_ref: DatabaseTransactionRef
    connection_ref: DatabaseConnectionRef
    action: DatabaseTransactionAction
    state: DatabaseTransactionState
    success: bool
    failure: DatabaseFailureCategory | None
    sqlstate: str | None
    message: str | None
    tool_call_ref: ToolCallRef
    receipt_ref: ContentRef
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _result_common(self.operation_ref, self.connection_ref, self.success, self.failure, self.tool_call_ref, self.receipt_ref, self.completed_at)
        if self.transaction_ref.project_ref != self.operation_ref.project_ref:
            raise DatabaseScopeError("database transaction result crossed Project scope")
        if not isinstance(self.action, DatabaseTransactionAction) or not isinstance(self.state, DatabaseTransactionState):
            raise DatabaseContractError("database transaction result is malformed")
        object.__setattr__(self, "record_sha256", _digest({"kind": "DatabaseTransactionResult", "payload": self.payload()}))

    def payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "completed_at": self.completed_at,
            "connection_ref": self.connection_ref.value,
            "failure": None if self.failure is None else self.failure.value,
            "message": self.message,
            "operation_ref": self.operation_ref.value,
            "receipt_ref": self.receipt_ref.value,
            "sqlstate": self.sqlstate,
            "state": self.state.value,
            "success": self.success,
            "tool_call_ref": self.tool_call_ref.value,
            "transaction_ref": self.transaction_ref.value,
        }


@dataclass(frozen=True)
class DatabaseSchemaResult:
    operation_ref: DatabaseOperationRef
    connection_ref: DatabaseConnectionRef
    success: bool
    server_version: str | None
    tables: tuple[Mapping[str, object], ...]
    columns: tuple[Mapping[str, object], ...]
    indexes: tuple[Mapping[str, object], ...]
    constraints: tuple[Mapping[str, object], ...]
    extensions: tuple[Mapping[str, object], ...]
    schema_sha256: str | None
    failure: DatabaseFailureCategory | None
    sqlstate: str | None
    message: str | None
    tool_call_ref: ToolCallRef
    receipt_ref: ContentRef
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _result_common(self.operation_ref, self.connection_ref, self.success, self.failure, self.tool_call_ref, self.receipt_ref, self.completed_at)
        if self.schema_sha256 is not None and _SHA256.fullmatch(self.schema_sha256) is None:
            raise DatabaseContractError("database schema digest is malformed")
        for name in ("tables", "columns", "indexes", "constraints", "extensions"):
            values = cast(tuple[Mapping[str, object], ...], getattr(self, name))
            if not isinstance(values, tuple) or len(values) > 10_000 or not all(isinstance(item, Mapping) for item in values):
                raise DatabaseContractError("database schema metadata is malformed or unbounded")
            object.__setattr__(self, name, tuple(MappingProxyType(dict(item)) for item in values))
        object.__setattr__(self, "record_sha256", _digest({"kind": "DatabaseSchemaResult", "payload": self.payload()}))

    def payload(self) -> dict[str, object]:
        return {
            "columns": [dict(item) for item in self.columns],
            "completed_at": self.completed_at,
            "connection_ref": self.connection_ref.value,
            "constraints": [dict(item) for item in self.constraints],
            "extensions": [dict(item) for item in self.extensions],
            "failure": None if self.failure is None else self.failure.value,
            "indexes": [dict(item) for item in self.indexes],
            "message": self.message,
            "operation_ref": self.operation_ref.value,
            "receipt_ref": self.receipt_ref.value,
            "schema_sha256": self.schema_sha256,
            "server_version": self.server_version,
            "sqlstate": self.sqlstate,
            "success": self.success,
            "tables": [dict(item) for item in self.tables],
            "tool_call_ref": self.tool_call_ref.value,
        }


@dataclass(frozen=True)
class DatabaseMigrationResult:
    operation_ref: DatabaseOperationRef
    connection_ref: DatabaseConnectionRef
    migration_artifact_ref: ArtifactRef
    migration_content_sha256: str
    success: bool
    before_schema_sha256: str | None
    after_schema_sha256: str | None
    failure: DatabaseFailureCategory | None
    sqlstate: str | None
    message: str | None
    tool_call_ref: ToolCallRef
    receipt_ref: ContentRef
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _result_common(self.operation_ref, self.connection_ref, self.success, self.failure, self.tool_call_ref, self.receipt_ref, self.completed_at)
        if self.migration_artifact_ref.project_ref != self.operation_ref.project_ref or _SHA256.fullmatch(self.migration_content_sha256) is None:
            raise DatabaseScopeError("database migration result identity is malformed")
        object.__setattr__(self, "record_sha256", _digest({"kind": "DatabaseMigrationResult", "payload": self.payload()}))

    def payload(self) -> dict[str, object]:
        return {
            "after_schema_sha256": self.after_schema_sha256,
            "before_schema_sha256": self.before_schema_sha256,
            "completed_at": self.completed_at,
            "connection_ref": self.connection_ref.value,
            "failure": None if self.failure is None else self.failure.value,
            "message": self.message,
            "migration_artifact_ref": self.migration_artifact_ref.value,
            "migration_content_sha256": self.migration_content_sha256,
            "operation_ref": self.operation_ref.value,
            "receipt_ref": self.receipt_ref.value,
            "sqlstate": self.sqlstate,
            "success": self.success,
            "tool_call_ref": self.tool_call_ref.value,
        }


def _result_common(
    operation_ref: DatabaseOperationRef,
    connection_ref: DatabaseConnectionRef,
    success: bool,
    failure: DatabaseFailureCategory | None,
    tool_call_ref: ToolCallRef,
    receipt_ref: ContentRef,
    completed_at: str,
) -> None:
    if not isinstance(operation_ref, DatabaseOperationRef) or not isinstance(connection_ref, DatabaseConnectionRef):
        raise DatabaseContractError("database result refs are malformed")
    if connection_ref.project_ref != operation_ref.project_ref:
        raise DatabaseScopeError("database result crossed Project scope")
    if not isinstance(success, bool) or success == (failure is not None):
        raise DatabaseContractError("database result success and failure differ")
    if not isinstance(tool_call_ref, ToolCallRef) or tool_call_ref.project_ref != operation_ref.project_ref:
        raise DatabaseScopeError("database ToolCall crossed Project scope")
    if not isinstance(receipt_ref, ContentRef):
        raise DatabaseContractError("database result requires exact receipt ContentRef")
    _timestamp(completed_at, "database result completed_at")


@runtime_checkable
class PostgreSQLAdapter(Protocol):
    def register_connection(self, access: ProjectAccess, connection: DatabaseConnection, *, idempotency_key: str) -> DatabaseConnection: ...
    def get_connection(self, access: ProjectAccess, connection_ref: DatabaseConnectionRef) -> DatabaseConnection: ...
    def connect(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: DatabaseConnectRequest, *, auth_values: Mapping[str, Mapping[str, str]], idempotency_key: str) -> DatabaseConnectResult: ...
    def query(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: DatabaseQueryRequest, *, auth_values: Mapping[str, Mapping[str, str]], idempotency_key: str) -> DatabaseQueryResult: ...
    def execute(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: DatabaseQueryRequest, *, auth_values: Mapping[str, Mapping[str, str]], idempotency_key: str) -> DatabaseQueryResult: ...
    def transaction(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: DatabaseTransactionRequest, *, auth_values: Mapping[str, Mapping[str, str]], idempotency_key: str) -> DatabaseTransactionResult: ...
    def inspect_schema(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: DatabaseSchemaRequest, *, auth_values: Mapping[str, Mapping[str, str]], idempotency_key: str) -> DatabaseSchemaResult: ...
    def migrate(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: DatabaseMigrationRequest, *, auth_values: Mapping[str, Mapping[str, str]], idempotency_key: str) -> DatabaseMigrationResult: ...


class _BackendFailure(Exception):
    def __init__(
        self,
        category: DatabaseFailureCategory,
        *,
        sqlstate: str | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__(category.value)
        self.category = category
        self.sqlstate = sqlstate
        self.message = message


class _Libpq:
    CONNECTION_OK = 0
    PQTRANS_IDLE = 0
    PQTRANS_INTRANS = 2
    PQTRANS_INERROR = 3
    PGRES_COMMAND_OK = 1
    PGRES_TUPLES_OK = 2
    PGRES_FATAL_ERROR = 7
    PGRES_SINGLE_TUPLE = 9
    PG_DIAG_SQLSTATE = ord("C")
    PG_DIAG_MESSAGE_PRIMARY = ord("M")

    def __init__(self) -> None:
        library_name = ctypes.util.find_library("pq")
        if library_name is None:
            raise DatabaseContractError("installed libpq runtime is unavailable")
        self.library = ctypes.CDLL(library_name)
        pointer = ctypes.c_void_p
        self.library.PQconnectdbParams.argtypes = [
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.c_int,
        ]
        self.library.PQconnectdbParams.restype = pointer
        self.library.PQstatus.argtypes = [pointer]
        self.library.PQstatus.restype = ctypes.c_int
        self.library.PQtransactionStatus.argtypes = [pointer]
        self.library.PQtransactionStatus.restype = ctypes.c_int
        self.library.PQserverVersion.argtypes = [pointer]
        self.library.PQserverVersion.restype = ctypes.c_int
        self.library.PQsslInUse.argtypes = [pointer]
        self.library.PQsslInUse.restype = ctypes.c_int
        self.library.PQerrorMessage.argtypes = [pointer]
        self.library.PQerrorMessage.restype = ctypes.c_char_p
        self.library.PQsocket.argtypes = [pointer]
        self.library.PQsocket.restype = ctypes.c_int
        self.library.PQfinish.argtypes = [pointer]
        self.library.PQfinish.restype = None
        self.library.PQsendQueryParams.argtypes = [
            pointer,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
        ]
        self.library.PQsendQueryParams.restype = ctypes.c_int
        self.library.PQsetSingleRowMode.argtypes = [pointer]
        self.library.PQsetSingleRowMode.restype = ctypes.c_int
        self.library.PQconsumeInput.argtypes = [pointer]
        self.library.PQconsumeInput.restype = ctypes.c_int
        self.library.PQisBusy.argtypes = [pointer]
        self.library.PQisBusy.restype = ctypes.c_int
        self.library.PQgetResult.argtypes = [pointer]
        self.library.PQgetResult.restype = pointer
        self.library.PQresultStatus.argtypes = [pointer]
        self.library.PQresultStatus.restype = ctypes.c_int
        self.library.PQresultErrorField.argtypes = [pointer, ctypes.c_int]
        self.library.PQresultErrorField.restype = ctypes.c_char_p
        self.library.PQntuples.argtypes = [pointer]
        self.library.PQntuples.restype = ctypes.c_int
        self.library.PQnfields.argtypes = [pointer]
        self.library.PQnfields.restype = ctypes.c_int
        self.library.PQfname.argtypes = [pointer, ctypes.c_int]
        self.library.PQfname.restype = ctypes.c_char_p
        self.library.PQgetisnull.argtypes = [pointer, ctypes.c_int, ctypes.c_int]
        self.library.PQgetisnull.restype = ctypes.c_int
        self.library.PQgetlength.argtypes = [pointer, ctypes.c_int, ctypes.c_int]
        self.library.PQgetlength.restype = ctypes.c_int
        self.library.PQgetvalue.argtypes = [pointer, ctypes.c_int, ctypes.c_int]
        self.library.PQgetvalue.restype = pointer
        self.library.PQcmdTuples.argtypes = [pointer]
        self.library.PQcmdTuples.restype = ctypes.c_char_p
        self.library.PQclear.argtypes = [pointer]
        self.library.PQclear.restype = None
        self.library.PQgetCancel.argtypes = [pointer]
        self.library.PQgetCancel.restype = pointer
        self.library.PQcancel.argtypes = [pointer, ctypes.c_char_p, ctypes.c_int]
        self.library.PQcancel.restype = ctypes.c_int
        self.library.PQfreeCancel.argtypes = [pointer]
        self.library.PQfreeCancel.restype = None


class _LibpqConnection:
    def __init__(self, api: _Libpq, handle: int) -> None:
        self.api = api
        self.handle: int | None = handle

    def close(self) -> None:
        if self.handle is not None:
            self.api.library.PQfinish(ctypes.c_void_p(self.handle))
            self.handle = None

    def pointer(self) -> ctypes.c_void_p:
        if self.handle is None:
            raise _BackendFailure(DatabaseFailureCategory.CONNECTION_FAILED, message="database connection is closed")
        return ctypes.c_void_p(self.handle)

    def status(self) -> int:
        return int(self.api.library.PQstatus(self.pointer()))

    def transaction_status(self) -> int:
        return int(self.api.library.PQtransactionStatus(self.pointer()))

    def cancel(self) -> None:
        cancel_handle = self.api.library.PQgetCancel(self.pointer())
        if not cancel_handle:
            return
        try:
            error_buffer = ctypes.create_string_buffer(256)
            self.api.library.PQcancel(cancel_handle, error_buffer, len(error_buffer))
        finally:
            self.api.library.PQfreeCancel(cancel_handle)


@dataclass
class _ActiveQuery:
    cancellation: threading.Event
    connection: _LibpqConnection


@dataclass
class _LiveTransaction:
    connection_ref: DatabaseConnectionRef
    connection: _LibpqConnection
    auth_digest: str
    attempt_id: str
    fence: int
    read_only_forced: bool = False


@dataclass
class _QueryObservation:
    row_count: int = 0
    affected_rows: int | None = None
    columns: tuple[str, ...] = ()
    output_bytes: int = 0


@dataclass(frozen=True)
class _StartedOperation:
    call: ToolCall
    request_ref: ContentRef
    first_claim: bool


class LibpqPostgreSQLAdapter:
    """Real PostgreSQL adapter backed by the installed provider C client ABI."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        internal_database_identities: Sequence[str] = (),
    ) -> None:
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("object_store must implement ObjectStorageBackend")
        if isinstance(internal_database_identities, (str, bytes)) or len(internal_database_identities) > 64:
            raise DatabaseContractError("internal database identities are malformed or unbounded")
        for value in internal_database_identities:
            _identity(value, "internal database identity")
        self.database_path = Path(database_path)
        self.object_store = object_store
        self.internal_database_identities = frozenset(internal_database_identities)
        self.projects = ProjectStore(database_path)
        self.graphs = GraphService(database_path)
        self.tasks = TaskRevisionService(database_path)
        self.runs = RunService(database_path)
        self.calls = CallLedgerService(database_path)
        self.artifacts = ArtifactService(database_path)
        self.capabilities = CapabilityRegistry(database_path)
        self.implementations = CapabilityImplementationRegistry(database_path)
        self._libpq = _Libpq()
        self.pool_identity = f"database-pool://libpq/{uuid4().hex}"
        self._condition = threading.Condition()
        self._pool: dict[tuple[str, str], list[_LibpqConnection]] = {}
        self._transactions: dict[str, _LiveTransaction] = {}
        self._active: dict[str, _ActiveQuery] = {}
        self._initialize_schema()

    def _connect_state(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect_state()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS postgresql_connections (
                    project_id TEXT NOT NULL,
                    connection_id TEXT NOT NULL,
                    connection_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,connection_id)
                );
                CREATE TABLE IF NOT EXISTS postgresql_connection_claims (
                    project_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    connection_id TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS postgresql_operation_claims (
                    project_id TEXT NOT NULL,
                    node_attempt_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    operation_kind TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    request_size INTEGER NOT NULL,
                    request_media_type TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    claim_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,node_attempt_id,idempotency_key),
                    UNIQUE(project_id,operation_id),
                    UNIQUE(project_id,call_id),
                    FOREIGN KEY(project_id,call_id) REFERENCES calls(project_id,call_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS postgresql_operation_results (
                    project_id TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    result_kind TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,operation_id)
                );
                CREATE TABLE IF NOT EXISTS postgresql_transaction_states (
                    project_id TEXT NOT NULL,
                    transaction_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    connection_id TEXT NOT NULL,
                    node_attempt_id TEXT NOT NULL,
                    node_fence INTEGER NOT NULL,
                    operation_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,transaction_id,version)
                );
                CREATE TABLE IF NOT EXISTS postgresql_transaction_heads (
                    project_id TEXT NOT NULL,
                    transaction_id TEXT NOT NULL,
                    current_version INTEGER NOT NULL,
                    current_record_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,transaction_id)
                );
                CREATE TRIGGER IF NOT EXISTS postgresql_connections_no_update BEFORE UPDATE ON postgresql_connections
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL connections are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS postgresql_connections_no_delete BEFORE DELETE ON postgresql_connections
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL connections cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS postgresql_connection_claims_no_update BEFORE UPDATE ON postgresql_connection_claims
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL connection claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS postgresql_connection_claims_no_delete BEFORE DELETE ON postgresql_connection_claims
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL connection claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS postgresql_operation_claims_no_update BEFORE UPDATE ON postgresql_operation_claims
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL operation claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS postgresql_operation_claims_no_delete BEFORE DELETE ON postgresql_operation_claims
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL operation claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS postgresql_operation_results_no_update BEFORE UPDATE ON postgresql_operation_results
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL operation results are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS postgresql_operation_results_no_delete BEFORE DELETE ON postgresql_operation_results
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL operation results cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS postgresql_transaction_states_no_update BEFORE UPDATE ON postgresql_transaction_states
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL transaction states are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS postgresql_transaction_states_no_delete BEFORE DELETE ON postgresql_transaction_states
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL transaction states cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS postgresql_transaction_heads_no_delete BEFORE DELETE ON postgresql_transaction_heads
                  BEGIN SELECT RAISE(ABORT,'PostgreSQL transaction heads cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def capability_ref(operation: str) -> CapabilityRef:
        if operation not in _OPERATIONS:
            raise DatabaseContractError("PostgreSQL operation is unsupported")
        capability_operation = operation.replace("_", "-")
        return CapabilityRef(f"database.postgresql.{capability_operation}", "1.0.0")

    @staticmethod
    def _implementation_ref(project_ref: ProjectRef, operation: str) -> CapabilityImplementationRef:
        capability_operation = operation.replace("_", "-")
        identity = hashlib.sha256(f"{project_ref.value}\x00database.postgresql.{capability_operation}\x001.0.0".encode()).hexdigest()[:32]
        return CapabilityImplementationRef(project_ref, f"cimpl_{identity}")

    def register_capabilities(self, access: ProjectAccess) -> Mapping[CapabilityRef, CapabilityImplementation]:
        self._authorize(access, access.project_ref)
        registered: dict[CapabilityRef, CapabilityImplementation] = {}
        for operation in _OPERATIONS:
            capability_ref = self.capability_ref(operation)
            mutating = operation in {"transaction", "execute", "migrate"}
            capability = self.capabilities.register(
                Capability(
                    capability_ref,
                    f"Scoped bounded PostgreSQL {operation}",
                    input_contract={"request": f"schema://minitz/postgresql-{operation}-request/1"},
                    output_contract={"result": f"schema://minitz/postgresql-{operation}-result/1"},
                    side_effects=(f"database.postgresql.{operation}",) if mutating else (),
                )
            )
            implementation_ref = self._implementation_ref(access.project_ref, operation)
            try:
                implementation = self.implementations.get(access, implementation_ref)
            except RoutingNotFoundError:
                implementation = self.implementations.register(
                    access,
                    CapabilityImplementation(
                        implementation_ref,
                        capability.capability_ref,
                        "1.0.0",
                        ImplementationKind.TOOL,
                        "adapter://minitz/database/postgresql/libpq",
                        "runtime://system/libpq",
                        tool_ref=f"tool://minitz/database/postgresql/{operation}",
                        features=("parameterized", "bounded", "single-row-streaming", "cancellation", "transaction-truth"),
                        input_features=("connection-ref", "statement-content-ref", "parameter-content-refs", "auth-profile-ref"),
                        output_features=("content-ref", "artifact", "tool-call", "sqlstate"),
                        side_effect_authority="EXTERNAL_WRITE" if mutating else "READ_ONLY",
                        resource_kinds=("network.database",),
                        remote_egress=True,
                        metadata={"adapter_contract": "postgresql-v1"},
                    ),
                    idempotency_key=f"postgresql-{operation}-implementation",
                )
            registered[capability_ref] = implementation
        return MappingProxyType(registered)

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectIntegrityError as exc:
            raise DatabaseIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise DatabaseScopeError("database Project scope mismatch") from exc

    def register_connection(
        self,
        access: ProjectAccess,
        connection_record: DatabaseConnection,
        *,
        idempotency_key: str,
    ) -> DatabaseConnection:
        _key(idempotency_key, "database idempotency key")
        if not isinstance(connection_record, DatabaseConnection):
            raise DatabaseContractError("exact DatabaseConnection is required")
        if connection_record.connection_ref.scope is not DatabaseScope.PROJECT or connection_record.project_ref is None:
            raise DatabaseScopeError("generic Project adapter cannot register infrastructure database authority")
        self._authorize(access, connection_record.project_ref)
        if connection_record.project_ref != access.project_ref:
            raise DatabaseScopeError("database connection crossed Project scope")
        if connection_record.database_identity in self.internal_database_identities:
            raise DatabaseAuthorityError("MiniTZ internal database identity is not Project database authority")
        request_sha = _digest(connection_record.payload())
        state = self._connect_state()
        try:
            state.execute("BEGIN IMMEDIATE")
            prior = state.execute(
                "SELECT * FROM postgresql_connection_claims WHERE project_id=? AND idempotency_key=?",
                (access.project_ref.value, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior["connection_id"] != connection_record.connection_ref.connection_id or prior["request_sha256"] != request_sha:
                    raise DatabaseConflictError("database connection idempotency semantics changed")
                state.commit()
                return self.get_connection(access, connection_record.connection_ref)
            state.execute(
                "INSERT INTO postgresql_connections VALUES (?,?,?,?)",
                (
                    access.project_ref.value,
                    connection_record.connection_ref.connection_id,
                    _json(connection_record.payload()),
                    connection_record.record_sha256,
                ),
            )
            state.execute(
                "INSERT INTO postgresql_connection_claims VALUES (?,?,?,?)",
                (access.project_ref.value, idempotency_key, connection_record.connection_ref.connection_id, request_sha),
            )
            state.commit()
            return connection_record
        except sqlite3.IntegrityError as exc:
            state.rollback()
            raise DatabaseConflictError("database connection persistence conflicts") from exc
        except Exception:
            state.rollback()
            raise
        finally:
            state.close()

    def get_connection(self, access: ProjectAccess, connection_ref: DatabaseConnectionRef) -> DatabaseConnection:
        if not isinstance(connection_ref, DatabaseConnectionRef):
            raise DatabaseContractError("exact DatabaseConnectionRef is required")
        if connection_ref.scope is not DatabaseScope.PROJECT or connection_ref.project_ref is None:
            raise DatabaseScopeError("generic Project adapter cannot resolve infrastructure database authority")
        self._authorize(access, connection_ref.project_ref)
        state = self._connect_state()
        try:
            row = state.execute(
                "SELECT * FROM postgresql_connections WHERE project_id=? AND connection_id=?",
                (access.project_ref.value, connection_ref.connection_id),
            ).fetchone()
            if row is None:
                raise DatabaseNotFoundError("database connection is unavailable")
            record = self._connection_from_payload(json.loads(cast(str, row["connection_json"])), access.project_ref)
            if record.connection_ref != connection_ref or not hmac.compare_digest(cast(str, row["record_sha256"]), record.record_sha256):
                raise DatabaseIntegrityError("database connection evidence changed")
            return record
        finally:
            state.close()

    @staticmethod
    def _connection_from_payload(payload: object, project_ref: ProjectRef) -> DatabaseConnection:
        if not isinstance(payload, dict):
            raise DatabaseIntegrityError("persisted database connection is malformed")
        try:
            value = cast(str, payload["connection_ref"])
            prefix = f"database-connection://{project_ref.value}/"
            if not value.startswith(prefix):
                raise DatabaseScopeError("persisted database connection crossed Project scope")
            tls_payload = cast(dict[str, object], payload["tls"])
            restriction_payload = cast(dict[str, object], payload["restrictions"])
            return DatabaseConnection(
                DatabaseConnectionRef(DatabaseScope.PROJECT, value.removeprefix(prefix), project_ref),
                cast(str, payload["adapter_ref"]),
                cast(str, payload["endpoint_identity"]),
                cast(str, payload["database_identity"]),
                cast(str, payload["auth_profile_ref"]),
                DatabaseTlsConfig(
                    DatabaseTlsMode(cast(str, tls_payload["mode"])),
                    cast(str | None, tls_payload["root_certificate_ref"]),
                    cast(str, tls_payload["minimum_protocol"]),
                ),
                DatabaseRestrictions(
                    tuple(DatabaseQueryMode(cast(str, item)) for item in cast(list[object], restriction_payload["allowed_modes"])),
                    cast(bool, restriction_payload["allow_transactions"]),
                    cast(bool, restriction_payload["allow_migrations"]),
                    cast(bool, restriction_payload["production"]),
                    cast(float, restriction_payload["max_timeout_seconds"]),
                    cast(int, restriction_payload["max_rows"]),
                    cast(int, restriction_payload["max_result_bytes"]),
                ),
                cast(str, payload["created_at"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DatabaseIntegrityError("persisted database connection is malformed") from exc

    def _require_operation_authority(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        binding: DatabaseExecutionBinding,
        operation: str,
    ) -> Task:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise DatabaseAuthorityError("NodeExecutionAttempt is required")
        if binding != DatabaseExecutionBinding.from_attempt(attempt):
            raise DatabaseAuthorityError("database Task/Run/NodeAttempt binding is not exact")
        if binding.project_ref != access.project_ref:
            raise DatabaseScopeError("database Node attempt crossed Project scope")
        graph = self.graphs.get_graph(access, attempt.node_ref.graph_ref)
        node = next((item for item in graph.nodes if item.node_ref == attempt.node_ref), None)
        if node is None or self.capability_ref(operation) not in node.required_capabilities:
            raise DatabaseAuthorityError("database capability is not authorized by exact Node")
        task = self.tasks.get_task(access, attempt.task_ref)
        if task.canonical_digest != attempt.task_digest:
            raise DatabaseIntegrityError("database Node attempt Task digest changed")
        levels = {"READ_ONLY": 0, "CANDIDATE_WRITE": 1, "PROJECT_WRITE": 2, "EXTERNAL_SIDE_EFFECT": 3}
        required = 3 if operation in {"execute", "transaction", "migrate"} else 0
        if levels[task.side_effect_authority] < required or levels[node.side_effect_requirement] < required:
            raise DatabaseAuthorityError("database operation exceeds Task or Node side-effect authority")
        return task

    def _validate_request_policy(
        self,
        connection_record: DatabaseConnection,
        task: Task,
        *,
        mode: DatabaseQueryMode | None,
        timeout_seconds: float,
        max_rows: int = 1,
        max_result_bytes: int = 1,
        persistence_requested: bool = False,
        migration: bool = False,
        transaction: bool = False,
    ) -> None:
        restrictions = connection_record.restrictions
        if connection_record.database_identity in self.internal_database_identities:
            raise DatabaseAuthorityError("MiniTZ internal database identity is not Project database authority")
        if timeout_seconds > restrictions.max_timeout_seconds or max_rows > restrictions.max_rows or max_result_bytes > restrictions.max_result_bytes:
            raise DatabaseAuthorityError("database request exceeds connection restrictions")
        if mode is not None and mode not in restrictions.allowed_modes:
            raise DatabaseAuthorityError("database mode is denied by connection restrictions")
        if transaction and not restrictions.allow_transactions:
            raise DatabaseAuthorityError("database transactions are denied by connection restrictions")
        if migration and (not restrictions.allow_migrations or restrictions.production):
            raise DatabaseAuthorityError("automatic production or restricted database migration is denied")
        if persistence_requested and task.constraints.get("database.persist_result") is not True:
            raise DatabaseAuthorityError("database result persistence is not required by exact Task")

    @staticmethod
    def _auth_material(
        connection_record: DatabaseConnection,
        auth_values: Mapping[str, Mapping[str, str]],
    ) -> tuple[str, str]:
        if not isinstance(auth_values, Mapping) or set(auth_values) != {connection_record.auth_profile_ref}:
            raise _BackendFailure(DatabaseFailureCategory.AUTH_FAILED, message="exact database auth profile material is unavailable")
        material = auth_values[connection_record.auth_profile_ref]
        if not isinstance(material, Mapping) or set(material) != {"username", "password"}:
            raise _BackendFailure(DatabaseFailureCategory.AUTH_FAILED, message="database auth profile material is malformed")
        username = material["username"]
        password = material["password"]
        if (
            not isinstance(username, str)
            or not username
            or len(username.encode()) > 256
            or "\x00" in username
            or not isinstance(password, str)
            or not password
            or len(password.encode()) > 64 * 1024
            or "\x00" in password
        ):
            raise _BackendFailure(DatabaseFailureCategory.AUTH_FAILED, message="database auth profile material is malformed")
        return username, password

    @classmethod
    def _auth_digest(
        cls,
        connection_record: DatabaseConnection,
        auth_values: Mapping[str, Mapping[str, str]],
    ) -> str:
        username, password = cls._auth_material(connection_record, auth_values)
        return hashlib.sha256(f"{username}\x00{password}".encode()).hexdigest()

    @staticmethod
    def _endpoint(connection_record: DatabaseConnection) -> tuple[str, int, str]:
        endpoint = urlsplit(connection_record.endpoint_identity)
        if endpoint.scheme != "postgresql-endpoint" or endpoint.username is not None or endpoint.password is not None:
            raise DatabaseContractError("database endpoint identity is unsupported")
        if endpoint.hostname is None or endpoint.port is None or endpoint.path not in {"", "/"} or endpoint.query or endpoint.fragment:
            raise DatabaseContractError("database endpoint identity is malformed")
        database = urlsplit(connection_record.database_identity)
        if database.scheme != "postgresql-database" or database.username is not None or database.password is not None or database.query or database.fragment:
            raise DatabaseContractError("database identity is unsupported")
        database_name = unquote(database.path.removeprefix("/"))
        if not database_name or "/" in database_name or len(database_name.encode()) > 63 or "\x00" in database_name:
            raise DatabaseContractError("database identity name is malformed")
        return endpoint.hostname, endpoint.port, database_name

    def _new_backend_connection(
        self,
        connection_record: DatabaseConnection,
        auth_values: Mapping[str, Mapping[str, str]],
        timeout_seconds: float,
    ) -> _LibpqConnection:
        username, password = self._auth_material(connection_record, auth_values)
        host, port, database_name = self._endpoint(connection_record)
        if connection_record.tls.root_certificate_ref is not None:
            raise _BackendFailure(
                DatabaseFailureCategory.POLICY_DENIED,
                message="exact TLS root certificate resolution is unavailable",
            )
        if connection_record.tls.mode is DatabaseTlsMode.ALLOW_LOCAL_PLAINTEXT:
            try:
                address = ipaddress.ip_address(host)
            except ValueError as exc:
                raise _BackendFailure(DatabaseFailureCategory.POLICY_DENIED, message="plaintext database mode requires a literal loopback address") from exc
            if not address.is_loopback:
                raise _BackendFailure(DatabaseFailureCategory.POLICY_DENIED, message="plaintext database mode is restricted to loopback")
            sslmode = "disable"
        else:
            sslmode = {
                DatabaseTlsMode.VERIFY_FULL: "verify-full",
                DatabaseTlsMode.VERIFY_CA: "verify-ca",
                DatabaseTlsMode.REQUIRE: "require",
            }[connection_record.tls.mode]
        keyword_values = (
            ("host", host),
            ("port", str(port)),
            ("dbname", database_name),
            ("user", username),
            ("password", password),
            ("connect_timeout", str(max(1, min(3600, int(timeout_seconds))))),
            ("sslmode", sslmode),
            ("ssl_min_protocol_version", connection_record.tls.minimum_protocol),
            ("application_name", "minitz-project-adapter"),
        )
        keywords = (ctypes.c_char_p * (len(keyword_values) + 1))()
        values = (ctypes.c_char_p * (len(keyword_values) + 1))()
        encoded: list[bytes] = []
        for index, (keyword, value) in enumerate(keyword_values):
            keyword_bytes = keyword.encode()
            value_bytes = value.encode()
            encoded.extend((keyword_bytes, value_bytes))
            keywords[index] = keyword_bytes
            values[index] = value_bytes
        keywords[len(keyword_values)] = None
        values[len(keyword_values)] = None
        handle = self._libpq.library.PQconnectdbParams(keywords, values, 0)
        if not handle:
            raise _BackendFailure(DatabaseFailureCategory.CONNECTION_FAILED, message="database client could not allocate a connection")
        backend = _LibpqConnection(self._libpq, cast(int, handle))
        if backend.status() != _Libpq.CONNECTION_OK:
            raw_message = self._decode_c(self._libpq.library.PQerrorMessage(backend.pointer()))
            backend.close()
            normalized = raw_message.lower()
            if "password authentication failed" in normalized or "no password supplied" in normalized:
                category = DatabaseFailureCategory.AUTH_FAILED
            elif "ssl" in normalized or "certificate" in normalized:
                category = DatabaseFailureCategory.TLS_FAILED
            else:
                category = DatabaseFailureCategory.CONNECTION_FAILED
            raise _BackendFailure(category, message=self._sanitize(raw_message, (username, password)))
        return backend

    def _acquire_backend(
        self,
        connection_record: DatabaseConnection,
        auth_values: Mapping[str, Mapping[str, str]],
        timeout_seconds: float,
    ) -> _LibpqConnection:
        auth_digest = self._auth_digest(connection_record, auth_values)
        pool_key = (connection_record.connection_ref.value, auth_digest)
        with self._condition:
            available = self._pool.get(pool_key, [])
            while available:
                backend = available.pop()
                if backend.status() == _Libpq.CONNECTION_OK and backend.transaction_status() == _Libpq.PQTRANS_IDLE:
                    return backend
                backend.close()
        return self._new_backend_connection(connection_record, auth_values, timeout_seconds)

    def _release_backend(
        self,
        connection_record: DatabaseConnection,
        backend: _LibpqConnection,
        auth_values: Mapping[str, Mapping[str, str]],
    ) -> None:
        if backend.handle is None or backend.status() != _Libpq.CONNECTION_OK or backend.transaction_status() != _Libpq.PQTRANS_IDLE:
            backend.close()
            return
        try:
            auth_digest = self._auth_digest(connection_record, auth_values)
        except _BackendFailure:
            backend.close()
            return
        pool_key = (connection_record.connection_ref.value, auth_digest)
        with self._condition:
            available = self._pool.setdefault(pool_key, [])
            if len(available) >= 2:
                backend.close()
            else:
                available.append(backend)

    @staticmethod
    def _decode_c(value: bytes | None) -> str:
        if value is None:
            return ""
        return value.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _sanitize(value: str, sensitive_values: Sequence[str]) -> str:
        sanitized = value[:2048]
        for sensitive in sensitive_values:
            if sensitive:
                sanitized = sanitized.replace(sensitive, "[redacted]")
        if any(pattern.search(sanitized) is not None for pattern in _SECRET_PATTERNS):
            return "database operation failed; sensitive detail suppressed"
        return sanitized or "database operation failed"

    def _read_statement(self, content_ref: ContentRef) -> str:
        if content_ref.size_bytes > 1024 * 1024:
            raise DatabaseContractError("database statement exceeds one MiB")
        try:
            payload = self.object_store.read(content_ref)
        except ObjectStorageError as exc:
            raise DatabaseIntegrityError("database statement ContentRef is unavailable or changed") from exc
        try:
            statement = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DatabaseContractError("database statement is not UTF-8") from exc
        if not statement.strip() or "\x00" in statement:
            raise DatabaseContractError("database statement is empty or contains NUL")
        return statement

    def _read_parameters(self, refs: tuple[ContentRef, ...]) -> tuple[bytes | None, ...]:
        encoded: list[bytes | None] = []
        for content_ref in refs:
            if content_ref.size_bytes > 1024 * 1024:
                raise DatabaseContractError("database parameter exceeds one MiB")
            try:
                payload = self.object_store.read(content_ref)
                value = json.loads(payload)
            except (ObjectStorageError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise DatabaseIntegrityError("database parameter ContentRef is unavailable or malformed") from exc
            if not isinstance(value, (str, int, float, bool, type(None))):
                raise DatabaseContractError("database parameter must be a JSON scalar")
            if value is None:
                encoded.append(None)
            elif isinstance(value, bool):
                encoded.append(b"true" if value else b"false")
            elif isinstance(value, str):
                if "\x00" in value:
                    raise DatabaseContractError("database text parameter contains NUL")
                encoded.append(value.encode())
            else:
                encoded.append(_json(value).encode())
        return tuple(encoded)

    def _cancel_backend(self, active: _ActiveQuery) -> bool:
        active.cancellation.set()
        try:
            active.connection.cancel()
        except _BackendFailure:
            return False
        return True

    def _execute_backend(
        self,
        backend: _LibpqConnection,
        statement: str,
        parameters: tuple[bytes | None, ...],
        *,
        timeout_seconds: float,
        max_rows: int,
        max_result_bytes: int,
        output: IO[bytes] | None,
        active_key: str,
        timeout_category: DatabaseFailureCategory = DatabaseFailureCategory.TIMEOUT,
    ) -> _QueryObservation:
        values_array = (ctypes.c_char_p * len(parameters))()
        keepalive: list[bytes] = []
        sensitive_parameters = tuple(
            value.decode("utf-8", errors="replace") for value in parameters if value is not None
        )
        for index, value in enumerate(parameters):
            if value is None:
                values_array[index] = None
            else:
                keepalive.append(value)
                values_array[index] = value
        backend_pointer = backend.pointer()
        sent = self._libpq.library.PQsendQueryParams(
            backend_pointer,
            statement.encode(),
            len(parameters),
            None,
            values_array if parameters else None,
            None,
            None,
            0,
        )
        if sent != 1:
            message = self._decode_c(self._libpq.library.PQerrorMessage(backend_pointer))
            raise _BackendFailure(DatabaseFailureCategory.CONNECTION_FAILED, message=self._sanitize(message, ()))
        if self._libpq.library.PQsetSingleRowMode(backend_pointer) != 1:
            backend.cancel()
            raise _BackendFailure(DatabaseFailureCategory.QUERY_FAILED, message="database client could not enable single-row streaming")
        active = _ActiveQuery(threading.Event(), backend)
        with self._condition:
            if active_key in self._active:
                backend.cancel()
                raise DatabaseConflictError("database operation identity is already active")
            self._active[active_key] = active
        deadline = time.monotonic() + timeout_seconds
        observation = _QueryObservation()
        header_written = False
        try:
            while True:
                while self._libpq.library.PQisBusy(backend_pointer) == 1:
                    if active.cancellation.is_set():
                        backend.cancel()
                        raise _BackendFailure(DatabaseFailureCategory.CANCELLED, message="database operation was cancelled")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        backend.cancel()
                        raise _BackendFailure(timeout_category, message="database statement timeout elapsed")
                    socket_fd = self._libpq.library.PQsocket(backend_pointer)
                    if socket_fd < 0:
                        raise _BackendFailure(DatabaseFailureCategory.CONNECTION_FAILED, message="database connection socket is unavailable")
                    readable, _, _ = select.select((socket_fd,), (), (), min(remaining, 0.1))
                    if readable and self._libpq.library.PQconsumeInput(backend_pointer) != 1:
                        message = self._decode_c(self._libpq.library.PQerrorMessage(backend_pointer))
                        raise _BackendFailure(DatabaseFailureCategory.CONNECTION_FAILED, message=self._sanitize(message, ()))
                result_handle = self._libpq.library.PQgetResult(backend_pointer)
                if not result_handle:
                    break
                result_pointer = ctypes.c_void_p(cast(int, result_handle))
                try:
                    status = int(self._libpq.library.PQresultStatus(result_pointer))
                    if status in {_Libpq.PGRES_SINGLE_TUPLE, _Libpq.PGRES_TUPLES_OK}:
                        field_count = int(self._libpq.library.PQnfields(result_pointer))
                        if not header_written:
                            columns = tuple(
                                self._decode_c(self._libpq.library.PQfname(result_pointer, index))
                                for index in range(field_count)
                            )
                            observation.columns = columns
                            header = (_json({"columns": list(columns)}) + "\n").encode()
                            observation.output_bytes += len(header)
                            if observation.output_bytes > max_result_bytes:
                                backend.cancel()
                                raise _BackendFailure(DatabaseFailureCategory.RESULT_LIMIT, message="database result byte limit exceeded")
                            if output is not None:
                                output.write(header)
                            header_written = True
                        row_count = int(self._libpq.library.PQntuples(result_pointer))
                        for row_index in range(row_count):
                            observation.row_count += 1
                            if observation.row_count > max_rows:
                                backend.cancel()
                                raise _BackendFailure(DatabaseFailureCategory.RESULT_LIMIT, message="database result row limit exceeded")
                            row: list[str | None] = []
                            for field_index in range(field_count):
                                if self._libpq.library.PQgetisnull(result_pointer, row_index, field_index) == 1:
                                    row.append(None)
                                else:
                                    length = int(self._libpq.library.PQgetlength(result_pointer, row_index, field_index))
                                    pointer = self._libpq.library.PQgetvalue(result_pointer, row_index, field_index)
                                    row.append(ctypes.string_at(pointer, length).decode("utf-8", errors="replace"))
                            serialized = (_json({"row": row}) + "\n").encode()
                            observation.output_bytes += len(serialized)
                            if observation.output_bytes > max_result_bytes:
                                backend.cancel()
                                raise _BackendFailure(DatabaseFailureCategory.RESULT_LIMIT, message="database result byte limit exceeded")
                            if output is not None:
                                output.write(serialized)
                    elif status == _Libpq.PGRES_COMMAND_OK:
                        command_rows = self._decode_c(self._libpq.library.PQcmdTuples(result_pointer))
                        observation.affected_rows = int(command_rows) if command_rows.isdigit() else None
                    else:
                        sqlstate = self._decode_c(self._libpq.library.PQresultErrorField(result_pointer, _Libpq.PG_DIAG_SQLSTATE)) or None
                        message = self._decode_c(self._libpq.library.PQresultErrorField(result_pointer, _Libpq.PG_DIAG_MESSAGE_PRIMARY))
                        category = DatabaseFailureCategory.CANCELLED if active.cancellation.is_set() or sqlstate == "57014" else DatabaseFailureCategory.QUERY_FAILED
                        raise _BackendFailure(
                            category,
                            sqlstate=sqlstate,
                            message=self._sanitize(message, sensitive_parameters),
                        )
                finally:
                    self._libpq.library.PQclear(result_pointer)
            return observation
        finally:
            with self._condition:
                self._active.pop(active_key, None)
                self._condition.notify_all()

    def _simple_command(
        self,
        backend: _LibpqConnection,
        statement: str,
        *,
        timeout_seconds: float,
        active_key: str,
    ) -> _QueryObservation:
        return self._execute_backend(
            backend,
            statement,
            (),
            timeout_seconds=timeout_seconds,
            max_rows=10_000_000,
            max_result_bytes=64 * 1024 * 1024,
            output=None,
            active_key=active_key,
        )

    def _run_attempt(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> ExecutionAttempt:
        result = next(
            (
                item
                for item in self.runs.list_attempts(access, attempt.run_ref)
                if item.attempt_id == attempt.run_attempt_id and item.fence == attempt.run_fence
            ),
            None,
        )
        if result is None:
            raise DatabaseAuthorityError("exact Run execution authority is unavailable")
        return result

    def _start_operation(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        operation_ref: DatabaseOperationRef,
        operation: str,
        request_payload: Mapping[str, object],
        input_refs: Sequence[ContentRef | ArtifactRef],
        *,
        idempotency_key: str,
    ) -> _StartedOperation:
        _key(idempotency_key, "database operation idempotency key")
        request_ref = self.object_store.put(_json(dict(request_payload)).encode(), media_type=_REQUEST_MEDIA_TYPE)
        try:
            implementation = self.implementations.get(access, self._implementation_ref(access.project_ref, operation))
        except RoutingNotFoundError as exc:
            raise DatabaseAuthorityError("PostgreSQL implementation is not registered") from exc
        call_key = _digest({"attempt": attempt.record_sha256, "idempotency_key": idempotency_key})
        try:
            call = self.calls.start_tool_call(
                access,
                attempt,
                idempotency_key=f"postgresql-start-{call_key[:40]}",
                capability_ref=self.capability_ref(operation),
                purpose="INITIAL",
                retry_of=None,
                parent_model_call_ref=None,
                tool_id=cast(str, implementation.tool_ref),
                implementation_id=implementation.implementation_ref.value,
                runtime_id=implementation.runtime_ref,
                input_refs=(request_ref, *input_refs),
                provider_trace_id=None,
            )
        except CallAuthorityError as exc:
            raise DatabaseAuthorityError("PostgreSQL ToolCall authority was rejected") from exc
        except CallConflictError as exc:
            raise DatabaseConflictError("PostgreSQL ToolCall idempotency conflicts") from exc
        claim = {
            "call_ref": call.call_ref.value,
            "idempotency_key": idempotency_key,
            "node_attempt_id": attempt.attempt_id,
            "operation": operation,
            "operation_ref": operation_ref.value,
            "project_ref": access.project_ref.value,
            "request_ref": request_ref.value,
        }
        claim_sha = _digest(claim)
        state = self._connect_state()
        try:
            state.execute("BEGIN IMMEDIATE")
            prior = state.execute(
                "SELECT * FROM postgresql_operation_claims WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?",
                (access.project_ref.value, attempt.attempt_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if (
                    prior["operation_id"] != operation_ref.operation_id
                    or prior["operation_kind"] != operation
                    or prior["request_digest"] != request_ref.digest
                    or prior["request_size"] != request_ref.size_bytes
                    or prior["request_media_type"] != request_ref.media_type
                    or prior["call_id"] != call.call_ref.call_id
                    or not hmac.compare_digest(cast(str, prior["claim_sha256"]), claim_sha)
                ):
                    raise DatabaseConflictError("database operation idempotency identity changed")
                state.commit()
                return _StartedOperation(call, request_ref, False)
            if call.status != "RUNNING":
                raise DatabaseIntegrityError("terminal database ToolCall lost its immutable claim")
            state.execute(
                "INSERT INTO postgresql_operation_claims VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    access.project_ref.value,
                    attempt.attempt_id,
                    idempotency_key,
                    operation_ref.operation_id,
                    operation,
                    request_ref.digest,
                    request_ref.size_bytes,
                    request_ref.media_type,
                    call.call_ref.call_id,
                    claim_sha,
                ),
            )
            state.commit()
            return _StartedOperation(call, request_ref, True)
        except sqlite3.IntegrityError as exc:
            state.rollback()
            raise DatabaseConflictError("database operation claim conflicts") from exc
        except Exception:
            state.rollback()
            raise
        finally:
            state.close()

    def _finish_call(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        started: _StartedOperation,
        *,
        success: bool,
        failure: DatabaseFailureCategory | None,
        receipt_payload: Mapping[str, object],
        output_refs: Sequence[ContentRef | ArtifactRef] = (),
    ) -> ContentRef:
        receipt_ref = self.object_store.put(_json(dict(receipt_payload)).encode(), media_type=_RECEIPT_MEDIA_TYPE)
        outputs = tuple(output_refs) + (receipt_ref,) if success else ()
        failure_evidence = () if success else (receipt_ref,)
        finish_key = _digest({"call": started.call.call_ref.value, "receipt": receipt_ref.value})
        try:
            self.calls.finish_tool_call(
                access,
                attempt,
                started.call.call_ref,
                idempotency_key=f"postgresql-finish-{finish_key[:39]}",
                status="SUCCEEDED" if success else "FAILED",
                output_refs=outputs,
                usage=None,
                cost=None,
                failure_category=None if failure is None else failure.value,
                failure_reason=None if failure is None else f"PostgreSQL operation failed: {failure.value}",
                failure_evidence_refs=failure_evidence,
            )
        except CallAuthorityError as exc:
            raise DatabaseAuthorityError("PostgreSQL completion authority was rejected") from exc
        except CallConflictError as exc:
            raise DatabaseConflictError("PostgreSQL completion conflicts") from exc
        return receipt_ref

    def _store_result(self, result: object, operation_ref: DatabaseOperationRef, result_kind: str) -> None:
        payload_method = getattr(result, "payload", None)
        record_sha = getattr(result, "record_sha256", None)
        if not callable(payload_method) or not isinstance(record_sha, str):
            raise DatabaseContractError("database result is not persistable")
        state = self._connect_state()
        try:
            state.execute(
                "INSERT INTO postgresql_operation_results VALUES (?,?,?,?,?)",
                (operation_ref.project_ref.value, operation_ref.operation_id, result_kind, _json(payload_method()), record_sha),
            )
            state.commit()
        except sqlite3.IntegrityError as exc:
            state.rollback()
            raise DatabaseConflictError("database result persistence conflicts") from exc
        finally:
            state.close()

    def _prior_payload(self, access: ProjectAccess, operation_ref: DatabaseOperationRef, result_kind: str) -> dict[str, object]:
        self._authorize(access, operation_ref.project_ref)
        state = self._connect_state()
        try:
            row = state.execute(
                "SELECT * FROM postgresql_operation_results WHERE project_id=? AND operation_id=?",
                (access.project_ref.value, operation_ref.operation_id),
            ).fetchone()
            if row is None:
                raise DatabaseNotFoundError("database operation result is unavailable")
            if row["result_kind"] != result_kind:
                raise DatabaseIntegrityError("database operation result kind changed")
            payload = json.loads(cast(str, row["result_json"]))
            if not isinstance(payload, dict):
                raise DatabaseIntegrityError("database operation result is malformed")
            return cast(dict[str, object], payload)
        except json.JSONDecodeError as exc:
            raise DatabaseIntegrityError("database operation result is malformed") from exc
        finally:
            state.close()

    @staticmethod
    def _operation_ref(value: object, project_ref: ProjectRef) -> DatabaseOperationRef:
        if not isinstance(value, str):
            raise DatabaseIntegrityError("persisted database operation ref is malformed")
        prefix = f"database-operation://{project_ref.value}/"
        if not value.startswith(prefix):
            raise DatabaseScopeError("persisted database operation crossed Project scope")
        return DatabaseOperationRef(project_ref, value.removeprefix(prefix))

    @staticmethod
    def _tool_ref(value: object, project_ref: ProjectRef) -> ToolCallRef:
        if not isinstance(value, str):
            raise DatabaseIntegrityError("persisted database ToolCall ref is malformed")
        prefix = f"tool-call://{project_ref.value}/"
        if not value.startswith(prefix):
            raise DatabaseScopeError("persisted database ToolCall crossed Project scope")
        return ToolCallRef(project_ref, value.removeprefix(prefix))

    @staticmethod
    def _artifact_ref(value: object, project_ref: ProjectRef) -> ArtifactRef | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise DatabaseIntegrityError("persisted database Artifact ref is malformed")
        prefix = f"artifact://{project_ref.value}/"
        if not value.startswith(prefix):
            raise DatabaseScopeError("persisted database Artifact crossed Project scope")
        parts = value.removeprefix(prefix).split("/")
        if len(parts) != 2:
            raise DatabaseIntegrityError("persisted database Artifact ref is malformed")
        return ArtifactRef(project_ref, parts[0], int(parts[1]))

    @staticmethod
    def _failure(value: object) -> DatabaseFailureCategory | None:
        return None if value is None else DatabaseFailureCategory(cast(str, value))

    def get_query_result(self, access: ProjectAccess, operation_ref: DatabaseOperationRef) -> DatabaseQueryResult:
        payload = self._prior_payload(access, operation_ref, "QUERY")
        result = DatabaseQueryResult(
            self._operation_ref(payload["operation_ref"], access.project_ref),
            self.get_connection(access, self._connection_ref(payload["connection_ref"], access.project_ref)).connection_ref,
            DatabaseQueryMode(cast(str, payload["mode"])),
            cast(bool, payload["success"]),
            cast(int, payload["row_count"]),
            cast(int | None, payload["affected_rows"]),
            _content_from_payload(payload["result_ref"]),
            self._artifact_ref(payload["result_artifact_ref"], access.project_ref),
            cast(str, payload["statement_sha256"]),
            cast(str, payload["parameter_sha256"]),
            self._failure(payload["failure"]),
            cast(str | None, payload["sqlstate"]),
            cast(str | None, payload["message"]),
            self._tool_ref(payload["tool_call_ref"], access.project_ref),
            self._receipt_from_value(payload["receipt_ref"]),
            cast(str, payload["completed_at"]),
        )
        self._verify_stored_result(operation_ref, result)
        return result

    @staticmethod
    def _connection_ref(value: object, project_ref: ProjectRef) -> DatabaseConnectionRef:
        if not isinstance(value, str):
            raise DatabaseIntegrityError("persisted database connection ref is malformed")
        prefix = f"database-connection://{project_ref.value}/"
        if not value.startswith(prefix):
            raise DatabaseScopeError("persisted database connection crossed Project scope")
        return DatabaseConnectionRef(DatabaseScope.PROJECT, value.removeprefix(prefix), project_ref)

    def _receipt_from_value(self, value: object) -> ContentRef:
        if not isinstance(value, str) or not value.startswith("content://sha256/"):
            raise DatabaseIntegrityError("persisted database receipt ref is malformed")
        digest = value.removeprefix("content://sha256/").split("?", 1)[0]
        try:
            size = int(value.rsplit("size=", 1)[1])
        except (IndexError, ValueError) as exc:
            raise DatabaseIntegrityError("persisted database receipt ref is malformed") from exc
        content_ref = ContentRef("sha256", digest, size, _RECEIPT_MEDIA_TYPE)
        if not self.object_store.verify(content_ref):
            raise DatabaseIntegrityError("database receipt ContentRef is unavailable or changed")
        return content_ref

    def _verify_stored_result(self, operation_ref: DatabaseOperationRef, result: object) -> None:
        if getattr(result, "operation_ref", None) != operation_ref:
            raise DatabaseIntegrityError("database result operation identity changed")
        state = self._connect_state()
        try:
            row = state.execute(
                "SELECT record_sha256 FROM postgresql_operation_results WHERE project_id=? AND operation_id=?",
                (operation_ref.project_ref.value, operation_ref.operation_id),
            ).fetchone()
            if row is None or not hmac.compare_digest(cast(str, row["record_sha256"]), cast(str, getattr(result, "record_sha256", ""))):
                raise DatabaseIntegrityError("database result evidence changed")
        finally:
            state.close()

    @staticmethod
    def _server_version(version: int) -> str:
        major = version // 10_000
        middle = (version // 100) % 100
        patch = version % 100
        return f"{major}.{patch}" if middle == 0 else f"{major}.{middle}.{patch}"

    def connect(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: DatabaseConnectRequest,
        *,
        auth_values: Mapping[str, Mapping[str, str]],
        idempotency_key: str,
    ) -> DatabaseConnectResult:
        if not isinstance(request, DatabaseConnectRequest):
            raise DatabaseContractError("exact DatabaseConnectRequest is required")
        connection_record = self.get_connection(access, request.connection_ref)
        task = self._require_operation_authority(access, attempt, request.binding, "connect")
        self._validate_request_policy(connection_record, task, mode=None, timeout_seconds=request.timeout_seconds)
        started = self._start_operation(access, attempt, request.operation_ref, "connect", request.payload(), (), idempotency_key=idempotency_key)
        if not started.first_claim:
            return self.get_connect_result(access, request.operation_ref)
        backend: _LibpqConnection | None = None
        failure: DatabaseFailureCategory | None = None
        sqlstate: str | None = None
        message: str | None = None
        version: str | None = None
        tls_active: bool | None = None
        try:
            # An explicit connect probe must authenticate the supplied profile
            # material instead of borrowing an already-authenticated session.
            backend = self._new_backend_connection(connection_record, auth_values, request.timeout_seconds)
            version = self._server_version(int(self._libpq.library.PQserverVersion(backend.pointer())))
            tls_active = bool(self._libpq.library.PQsslInUse(backend.pointer()))
        except _BackendFailure as exc:
            failure, sqlstate, message = exc.category, exc.sqlstate, exc.message
        finally:
            if backend is not None:
                self._release_backend(connection_record, backend, auth_values)
        success = failure is None
        receipt_payload = {
            "completed_at": _now(),
            "connection_ref": connection_record.connection_ref.value,
            "database_identity": connection_record.database_identity,
            "failure": None if failure is None else failure.value,
            "operation": "connect",
            "operation_ref": request.operation_ref.value,
            "pool_identity": self.pool_identity,
            "server_version": version,
            "sqlstate": sqlstate,
            "success": success,
            "tls_active": tls_active,
        }
        receipt_ref = self._finish_call(access, attempt, started, success=success, failure=failure, receipt_payload=receipt_payload)
        result = DatabaseConnectResult(
            request.operation_ref,
            connection_record.connection_ref,
            success,
            version,
            tls_active,
            failure,
            sqlstate,
            message,
            started.call.call_ref,
            receipt_ref,
            self.pool_identity,
            cast(str, receipt_payload["completed_at"]),
        )
        self._store_result(result, request.operation_ref, "CONNECT")
        return result

    def get_connect_result(self, access: ProjectAccess, operation_ref: DatabaseOperationRef) -> DatabaseConnectResult:
        payload = self._prior_payload(access, operation_ref, "CONNECT")
        result = DatabaseConnectResult(
            self._operation_ref(payload["operation_ref"], access.project_ref),
            self._connection_ref(payload["connection_ref"], access.project_ref),
            cast(bool, payload["success"]),
            cast(str | None, payload["server_version"]),
            cast(bool | None, payload["tls_active"]),
            self._failure(payload["failure"]),
            cast(str | None, payload["sqlstate"]),
            cast(str | None, payload["message"]),
            self._tool_ref(payload["tool_call_ref"], access.project_ref),
            self._receipt_from_value(payload["receipt_ref"]),
            cast(str, payload["pool_identity"]),
            cast(str, payload["completed_at"]),
        )
        self._verify_stored_result(operation_ref, result)
        return result

    def query(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: DatabaseQueryRequest,
        *,
        auth_values: Mapping[str, Mapping[str, str]],
        idempotency_key: str,
    ) -> DatabaseQueryResult:
        if not isinstance(request, DatabaseQueryRequest):
            raise DatabaseContractError("exact DatabaseQueryRequest is required")
        operation = "query" if request.mode is DatabaseQueryMode.READ_ONLY else "execute"
        connection_record = self.get_connection(access, request.connection_ref)
        task = self._require_operation_authority(access, attempt, request.binding, operation)
        self._validate_request_policy(
            connection_record,
            task,
            mode=request.mode,
            timeout_seconds=request.timeout_seconds,
            max_rows=request.max_rows,
            max_result_bytes=request.max_result_bytes,
            persistence_requested=request.persist_result,
        )
        statement = self._read_statement(request.statement_ref)
        parameters = self._read_parameters(request.parameter_refs)
        parameter_sha = _digest([item.value for item in request.parameter_refs])
        inputs: tuple[ContentRef | ArtifactRef, ...] = (request.statement_ref, *request.parameter_refs)
        started = self._start_operation(access, attempt, request.operation_ref, operation, request.payload(), inputs, idempotency_key=idempotency_key)
        if not started.first_claim:
            return self.get_query_result(access, request.operation_ref)
        backend: _LibpqConnection | None = None
        release_backend = request.transaction_ref is None
        failure: DatabaseFailureCategory | None = None
        sqlstate: str | None = None
        message: str | None = None
        observation = _QueryObservation()
        result_ref: ContentRef | None = None
        result_artifact_ref: ArtifactRef | None = None
        transaction_live: _LiveTransaction | None = None
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as output:
            try:
                if request.transaction_ref is None:
                    backend = self._acquire_backend(connection_record, auth_values, request.timeout_seconds)
                    if request.mode is DatabaseQueryMode.READ_ONLY:
                        self._simple_command(
                            backend,
                            "BEGIN READ ONLY",
                            timeout_seconds=request.timeout_seconds,
                            active_key=f"{request.operation_ref.value}:begin",
                        )
                else:
                    with self._condition:
                        transaction_live = self._transactions.get(request.transaction_ref.value)
                    if transaction_live is None:
                        raise _BackendFailure(DatabaseFailureCategory.TRANSACTION_ABORTED, message="database transaction is not live in this adapter generation")
                    if (
                        transaction_live.connection_ref != request.connection_ref
                        or transaction_live.auth_digest != self._auth_digest(connection_record, auth_values)
                        or transaction_live.attempt_id != attempt.attempt_id
                        or transaction_live.fence != attempt.fence
                    ):
                        raise DatabaseAuthorityError("database transaction ownership binding changed")
                    if transaction_live.read_only_forced and request.mode is not DatabaseQueryMode.READ_ONLY:
                        raise DatabaseAuthorityError("database transaction was made read-only by an earlier operation")
                    backend = transaction_live.connection
                    release_backend = False
                    if request.mode is DatabaseQueryMode.READ_ONLY and not transaction_live.read_only_forced:
                        self._simple_command(
                            backend,
                            "SET LOCAL transaction_read_only = on",
                            timeout_seconds=request.timeout_seconds,
                            active_key=f"{request.operation_ref.value}:readonly",
                        )
                        transaction_live.read_only_forced = True
                observation = self._execute_backend(
                    backend,
                    statement,
                    parameters,
                    timeout_seconds=request.timeout_seconds,
                    max_rows=request.max_rows,
                    max_result_bytes=request.max_result_bytes,
                    output=output if request.persist_result else None,
                    active_key=request.operation_ref.value,
                )
                if request.transaction_ref is None and request.mode is DatabaseQueryMode.READ_ONLY:
                    self._simple_command(
                        backend,
                        "ROLLBACK",
                        timeout_seconds=request.timeout_seconds,
                        active_key=f"{request.operation_ref.value}:rollback",
                    )
                if request.persist_result:
                    output.flush()
                    output.seek(0)
                    result_ref = self.object_store.put(
                        output,
                        media_type=_RESULT_MEDIA_TYPE,
                        expected_size=observation.output_bytes,
                    )
                    artifact = self.artifacts.publish_from_run(
                        access,
                        producer_attempt=self._run_attempt(access, attempt),
                        expected_task_ref=attempt.task_ref,
                        expected_task_digest=attempt.task_digest,
                        role="database.query.result",
                        content_ref=result_ref,
                        source_refs=(),
                        source_artifact_refs=(),
                        source_content_refs=(request.statement_ref, *request.parameter_refs),
                        derivation_type="database.postgresql.query",
                        metadata={
                            "media_type": result_ref.media_type,
                            "schema_ref": "schema://minitz/postgresql-rows/1",
                            "schema_version": "1.0.0",
                        },
                    )
                    result_artifact_ref = artifact.artifact_ref
            except _BackendFailure as exc:
                failure, sqlstate, message = exc.category, exc.sqlstate, self._sanitize(exc.message or exc.category.value, ())
                if backend is not None and backend.handle is not None and backend.transaction_status() in {_Libpq.PQTRANS_INTRANS, _Libpq.PQTRANS_INERROR}:
                    try:
                        self._simple_command(
                            backend,
                            "ROLLBACK",
                            timeout_seconds=min(5.0, request.timeout_seconds),
                            active_key=f"{request.operation_ref.value}:failure-rollback",
                        )
                    except _BackendFailure:
                        backend.close()
                if request.transaction_ref is not None:
                    terminal_state = (
                        DatabaseTransactionState.CANCELLED
                        if failure is DatabaseFailureCategory.CANCELLED
                        else DatabaseTransactionState.ABORTED
                    )
                    with self._condition:
                        self._transactions.pop(request.transaction_ref.value, None)
                        self._condition.notify_all()
                    self._record_transaction_state(
                        request.transaction_ref,
                        connection_record.connection_ref,
                        attempt,
                        request.operation_ref,
                        terminal_state,
                    )
                    release_backend = True
            finally:
                if backend is not None and release_backend:
                    self._release_backend(connection_record, backend, auth_values)
        success = failure is None
        completed_at = _now()
        receipt_payload = {
            "affected_rows": observation.affected_rows,
            "completed_at": completed_at,
            "connection_ref": connection_record.connection_ref.value,
            "database_identity": connection_record.database_identity,
            "failure": None if failure is None else failure.value,
            "mode": request.mode.value,
            "operation": operation,
            "operation_ref": request.operation_ref.value,
            "parameter_sha256": parameter_sha,
            "result_ref": None if result_ref is None else result_ref.value,
            "row_count": observation.row_count,
            "sqlstate": sqlstate,
            "statement_sha256": request.statement_ref.digest,
            "success": success,
            "timeout_enforcement": "libpq-cancel-and-client-deadline",
            "transaction_ref": None if request.transaction_ref is None else request.transaction_ref.value,
        }
        outputs: tuple[ContentRef | ArtifactRef, ...] = tuple(
            item for item in (result_ref, result_artifact_ref) if item is not None
        )
        receipt_ref = self._finish_call(access, attempt, started, success=success, failure=failure, receipt_payload=receipt_payload, output_refs=outputs)
        result = DatabaseQueryResult(
            request.operation_ref,
            connection_record.connection_ref,
            request.mode,
            success,
            observation.row_count,
            observation.affected_rows,
            result_ref,
            result_artifact_ref,
            request.statement_ref.digest,
            parameter_sha,
            failure,
            sqlstate,
            message,
            started.call.call_ref,
            receipt_ref,
            completed_at,
        )
        self._store_result(result, request.operation_ref, "QUERY")
        return result

    def execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: DatabaseQueryRequest,
        *,
        auth_values: Mapping[str, Mapping[str, str]],
        idempotency_key: str,
    ) -> DatabaseQueryResult:
        if not isinstance(request, DatabaseQueryRequest) or request.mode is DatabaseQueryMode.READ_ONLY:
            raise DatabaseContractError("PostgreSQL execute requires MUTATING or DDL_MIGRATION mode")
        return self.query(
            access,
            attempt,
            request,
            auth_values=auth_values,
            idempotency_key=idempotency_key,
        )

    def _record_transaction_state(
        self,
        transaction_ref: DatabaseTransactionRef,
        connection_ref: DatabaseConnectionRef,
        attempt: NodeExecutionAttempt,
        operation_ref: DatabaseOperationRef,
        state_value: DatabaseTransactionState,
    ) -> None:
        state = self._connect_state()
        recorded_at = _now()
        try:
            state.execute("BEGIN IMMEDIATE")
            head = state.execute(
                "SELECT * FROM postgresql_transaction_heads WHERE project_id=? AND transaction_id=?",
                (transaction_ref.project_ref.value, transaction_ref.transaction_id),
            ).fetchone()
            if head is None:
                if state_value is not DatabaseTransactionState.OPEN:
                    raise DatabaseIntegrityError("database transaction has no durable OPEN predecessor")
                version = 1
            else:
                version = cast(int, head["current_version"]) + 1
                if version != 2 or state_value is DatabaseTransactionState.OPEN:
                    raise DatabaseConflictError("database transaction terminal state already exists")
            payload = {
                "connection_ref": connection_ref.value,
                "node_attempt_id": attempt.attempt_id,
                "node_fence": attempt.fence,
                "operation_ref": operation_ref.value,
                "recorded_at": recorded_at,
                "state": state_value.value,
                "transaction_ref": transaction_ref.value,
                "version": version,
            }
            record_sha = _digest({"kind": "DatabaseTransactionState", "payload": payload})
            state.execute(
                "INSERT INTO postgresql_transaction_states VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    transaction_ref.project_ref.value,
                    transaction_ref.transaction_id,
                    version,
                    state_value.value,
                    connection_ref.connection_id,
                    attempt.attempt_id,
                    attempt.fence,
                    operation_ref.operation_id,
                    recorded_at,
                    record_sha,
                ),
            )
            if head is None:
                state.execute(
                    "INSERT INTO postgresql_transaction_heads VALUES (?,?,?,?)",
                    (transaction_ref.project_ref.value, transaction_ref.transaction_id, version, record_sha),
                )
            else:
                updated = state.execute(
                    "UPDATE postgresql_transaction_heads SET current_version=?,current_record_sha256=? WHERE project_id=? AND transaction_id=? AND current_version=? AND current_record_sha256=?",
                    (
                        version,
                        record_sha,
                        transaction_ref.project_ref.value,
                        transaction_ref.transaction_id,
                        cast(int, head["current_version"]),
                        cast(str, head["current_record_sha256"]),
                    ),
                )
                if updated.rowcount != 1:
                    raise DatabaseConflictError("database transaction state changed concurrently")
            state.commit()
        except sqlite3.IntegrityError as exc:
            state.rollback()
            raise DatabaseConflictError("database transaction state conflicts") from exc
        except Exception:
            state.rollback()
            raise
        finally:
            state.close()

    def _current_transaction_state(
        self,
        transaction_ref: DatabaseTransactionRef,
    ) -> DatabaseTransactionState | None:
        state = self._connect_state()
        try:
            row = state.execute(
                """
                SELECT states.state
                FROM postgresql_transaction_heads AS heads
                JOIN postgresql_transaction_states AS states
                  ON states.project_id=heads.project_id
                 AND states.transaction_id=heads.transaction_id
                 AND states.version=heads.current_version
                WHERE heads.project_id=? AND heads.transaction_id=?
                """,
                (transaction_ref.project_ref.value, transaction_ref.transaction_id),
            ).fetchone()
            return None if row is None else DatabaseTransactionState(cast(str, row["state"]))
        finally:
            state.close()

    def _commit_backend(self, backend: _LibpqConnection, request: DatabaseTransactionRequest) -> None:
        """Commit hook kept narrow so a deterministic unknown-outcome fixture can sever transport."""
        self._simple_command(
            backend,
            "COMMIT",
            timeout_seconds=request.timeout_seconds,
            active_key=request.operation_ref.value,
        )

    def transaction(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: DatabaseTransactionRequest,
        *,
        auth_values: Mapping[str, Mapping[str, str]],
        idempotency_key: str,
    ) -> DatabaseTransactionResult:
        if not isinstance(request, DatabaseTransactionRequest):
            raise DatabaseContractError("exact DatabaseTransactionRequest is required")
        connection_record = self.get_connection(access, request.connection_ref)
        task = self._require_operation_authority(access, attempt, request.binding, "transaction")
        self._validate_request_policy(
            connection_record,
            task,
            mode=None,
            timeout_seconds=request.timeout_seconds,
            transaction=True,
        )
        started = self._start_operation(access, attempt, request.operation_ref, "transaction", request.payload(), (), idempotency_key=idempotency_key)
        if not started.first_claim:
            return self.get_transaction_result(access, request.operation_ref)
        backend: _LibpqConnection | None = None
        failure: DatabaseFailureCategory | None = None
        sqlstate: str | None = None
        message: str | None = None
        state_value: DatabaseTransactionState
        settled_by_query = False
        try:
            if request.action is DatabaseTransactionAction.BEGIN:
                with self._condition:
                    if request.transaction_ref.value in self._transactions:
                        raise DatabaseConflictError("database transaction identity is already live")
                backend = self._acquire_backend(connection_record, auth_values, request.timeout_seconds)
                begin_statement = (
                    "BEGIN READ ONLY"
                    if connection_record.restrictions.allowed_modes == (DatabaseQueryMode.READ_ONLY,)
                    else "BEGIN"
                )
                self._simple_command(
                    backend,
                    begin_statement,
                    timeout_seconds=request.timeout_seconds,
                    active_key=request.operation_ref.value,
                )
                live = _LiveTransaction(
                    connection_record.connection_ref,
                    backend,
                    self._auth_digest(connection_record, auth_values),
                    attempt.attempt_id,
                    attempt.fence,
                    begin_statement.endswith("READ ONLY"),
                )
                with self._condition:
                    self._transactions[request.transaction_ref.value] = live
                self._record_transaction_state(
                    request.transaction_ref,
                    connection_record.connection_ref,
                    attempt,
                    request.operation_ref,
                    DatabaseTransactionState.OPEN,
                )
                state_value = DatabaseTransactionState.OPEN
                backend = None
            else:
                with self._condition:
                    persisted_live = self._transactions.get(request.transaction_ref.value)
                if persisted_live is None:
                    raise _BackendFailure(DatabaseFailureCategory.TRANSACTION_ABORTED, message="database transaction is not live in this adapter generation")
                if (
                    persisted_live.connection_ref != request.connection_ref
                    or persisted_live.auth_digest != self._auth_digest(connection_record, auth_values)
                    or persisted_live.attempt_id != attempt.attempt_id
                    or persisted_live.fence != attempt.fence
                ):
                    raise DatabaseAuthorityError("database transaction ownership binding changed")
                backend = persisted_live.connection
                if request.action is DatabaseTransactionAction.COMMIT:
                    try:
                        self._commit_backend(backend, request)
                    except _BackendFailure as exc:
                        if exc.category in {DatabaseFailureCategory.CONNECTION_FAILED, DatabaseFailureCategory.TIMEOUT}:
                            raise _BackendFailure(
                                DatabaseFailureCategory.TRANSACTION_OUTCOME_UNKNOWN,
                                sqlstate=exc.sqlstate,
                                message="database connection was lost before commit outcome was observed",
                            ) from exc
                        raise
                    if backend.transaction_status() != _Libpq.PQTRANS_IDLE:
                        raise _BackendFailure(
                            DatabaseFailureCategory.TRANSACTION_OUTCOME_UNKNOWN,
                            message="database commit completion was not observed as idle",
                        )
                    state_value = DatabaseTransactionState.COMMITTED
                elif request.action is DatabaseTransactionAction.ROLLBACK:
                    self._simple_command(
                        backend,
                        "ROLLBACK",
                        timeout_seconds=request.timeout_seconds,
                        active_key=request.operation_ref.value,
                    )
                    state_value = DatabaseTransactionState.ROLLED_BACK
                else:
                    active_for_transaction: _ActiveQuery | None = None
                    with self._condition:
                        active_for_transaction = next(
                            (item for item in self._active.values() if item.connection is backend),
                            None,
                        )
                    if active_for_transaction is not None:
                        self._cancel_backend(active_for_transaction)
                        deadline = time.monotonic() + request.timeout_seconds
                        with self._condition:
                            while request.transaction_ref.value in self._transactions:
                                remaining = deadline - time.monotonic()
                                if remaining <= 0:
                                    raise _BackendFailure(DatabaseFailureCategory.TIMEOUT, message="database cancellation acknowledgement timed out")
                                self._condition.wait(timeout=min(remaining, 0.1))
                        if self._current_transaction_state(request.transaction_ref) is not DatabaseTransactionState.CANCELLED:
                            raise _BackendFailure(DatabaseFailureCategory.TRANSACTION_ABORTED, message="database cancellation did not reach a cancelled terminal state")
                        state_value = DatabaseTransactionState.CANCELLED
                        backend = None
                        settled_by_query = True
                    else:
                        if backend.handle is not None and backend.transaction_status() in {_Libpq.PQTRANS_INTRANS, _Libpq.PQTRANS_INERROR}:
                            self._simple_command(
                                backend,
                                "ROLLBACK",
                                timeout_seconds=request.timeout_seconds,
                                active_key=request.operation_ref.value,
                            )
                        state_value = DatabaseTransactionState.CANCELLED
                if not settled_by_query:
                    with self._condition:
                        self._transactions.pop(request.transaction_ref.value, None)
                        self._condition.notify_all()
                    self._record_transaction_state(
                        request.transaction_ref,
                        connection_record.connection_ref,
                        attempt,
                        request.operation_ref,
                        state_value,
                    )
                    if backend is None:
                        raise DatabaseIntegrityError("database transaction lost its live connection before release")
                    self._release_backend(connection_record, backend, auth_values)
                    backend = None
        except _BackendFailure as exc:
            failure, sqlstate, message = exc.category, exc.sqlstate, self._sanitize(exc.message or exc.category.value, ())
            if exc.category is DatabaseFailureCategory.TRANSACTION_OUTCOME_UNKNOWN:
                state_value = DatabaseTransactionState.OUTCOME_UNKNOWN
            else:
                state_value = DatabaseTransactionState.ABORTED
            with self._condition:
                self._transactions.pop(request.transaction_ref.value, None)
            if request.action is not DatabaseTransactionAction.BEGIN:
                if self._current_transaction_state(request.transaction_ref) is DatabaseTransactionState.OPEN:
                    self._record_transaction_state(
                        request.transaction_ref,
                        connection_record.connection_ref,
                        attempt,
                        request.operation_ref,
                        state_value,
                    )
            if backend is not None:
                backend.close()
                backend = None
        finally:
            if backend is not None:
                backend.close()
        success = failure is None
        completed_at = _now()
        receipt_payload = {
            "action": request.action.value,
            "completed_at": completed_at,
            "connection_ref": connection_record.connection_ref.value,
            "database_identity": connection_record.database_identity,
            "failure": None if failure is None else failure.value,
            "operation": "transaction",
            "operation_ref": request.operation_ref.value,
            "sqlstate": sqlstate,
            "state": state_value.value,
            "success": success,
            "timeout_enforcement": "libpq-cancel-and-client-deadline",
            "transaction_ref": request.transaction_ref.value,
        }
        receipt_ref = self._finish_call(access, attempt, started, success=success, failure=failure, receipt_payload=receipt_payload)
        result = DatabaseTransactionResult(
            request.operation_ref,
            request.transaction_ref,
            connection_record.connection_ref,
            request.action,
            state_value,
            success,
            failure,
            sqlstate,
            message,
            started.call.call_ref,
            receipt_ref,
            completed_at,
        )
        self._store_result(result, request.operation_ref, "TRANSACTION")
        return result

    def get_transaction_result(self, access: ProjectAccess, operation_ref: DatabaseOperationRef) -> DatabaseTransactionResult:
        payload = self._prior_payload(access, operation_ref, "TRANSACTION")
        transaction_value = cast(str, payload["transaction_ref"])
        prefix = f"database-transaction://{access.project_ref.value}/"
        if not transaction_value.startswith(prefix):
            raise DatabaseScopeError("persisted transaction crossed Project scope")
        result = DatabaseTransactionResult(
            self._operation_ref(payload["operation_ref"], access.project_ref),
            DatabaseTransactionRef(access.project_ref, transaction_value.removeprefix(prefix)),
            self._connection_ref(payload["connection_ref"], access.project_ref),
            DatabaseTransactionAction(cast(str, payload["action"])),
            DatabaseTransactionState(cast(str, payload["state"])),
            cast(bool, payload["success"]),
            self._failure(payload["failure"]),
            cast(str | None, payload["sqlstate"]),
            cast(str | None, payload["message"]),
            self._tool_ref(payload["tool_call_ref"], access.project_ref),
            self._receipt_from_value(payload["receipt_ref"]),
            cast(str, payload["completed_at"]),
        )
        self._verify_stored_result(operation_ref, result)
        return result

    def _schema_rows(
        self,
        backend: _LibpqConnection,
        statement: str,
        *,
        timeout_seconds: float,
        max_rows: int,
        max_result_bytes: int,
        active_key: str,
    ) -> tuple[tuple[Mapping[str, object], ...], int]:
        with tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024) as output:
            observation = self._execute_backend(
                backend,
                statement,
                (),
                timeout_seconds=timeout_seconds,
                max_rows=max_rows,
                max_result_bytes=max_result_bytes,
                output=output,
                active_key=active_key,
            )
            output.seek(0)
            first = output.readline()
            if not first:
                return (), observation.output_bytes
            header = json.loads(first)
            columns = cast(list[str], header["columns"])
            rows: list[Mapping[str, object]] = []
            for line in output:
                body = json.loads(line)
                values = cast(list[object], body["row"])
                rows.append(MappingProxyType(dict(zip(columns, values, strict=True))))
            return tuple(rows), observation.output_bytes

    def _inspect_backend_schema(
        self,
        backend: _LibpqConnection,
        *,
        timeout_seconds: float,
        max_objects: int,
        max_result_bytes: int,
        active_prefix: str,
    ) -> tuple[
        str,
        tuple[Mapping[str, object], ...],
        tuple[Mapping[str, object], ...],
        tuple[Mapping[str, object], ...],
        tuple[Mapping[str, object], ...],
        tuple[Mapping[str, object], ...],
        str,
    ]:
        statements = (
            (
                "tables",
                "SELECT table_schema,table_name,table_type FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY table_schema,table_name",
            ),
            (
                "columns",
                "SELECT table_schema,table_name,column_name,ordinal_position,data_type,is_nullable "
                "FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') "
                "ORDER BY table_schema,table_name,ordinal_position",
            ),
            (
                "indexes",
                "SELECT schemaname AS table_schema,tablename AS table_name,indexname AS index_name,indexdef "
                "FROM pg_indexes WHERE schemaname NOT IN ('pg_catalog','information_schema') "
                "ORDER BY schemaname,tablename,indexname",
            ),
            (
                "constraints",
                "SELECT constraint_schema,table_name,constraint_name,constraint_type "
                "FROM information_schema.table_constraints "
                "WHERE constraint_schema NOT IN ('pg_catalog','information_schema') "
                "ORDER BY constraint_schema,table_name,constraint_name",
            ),
            (
                "extensions",
                "SELECT extname AS extension_name,extversion AS extension_version FROM pg_extension ORDER BY extname",
            ),
        )
        collected: dict[str, tuple[Mapping[str, object], ...]] = {}
        remaining_rows = max_objects
        remaining_bytes = max_result_bytes
        for name, statement in statements:
            if remaining_rows <= 0 or remaining_bytes <= 0:
                raise _BackendFailure(DatabaseFailureCategory.RESULT_LIMIT, message="database schema inspection limit exceeded")
            rows, used_bytes = self._schema_rows(
                backend,
                statement,
                timeout_seconds=timeout_seconds,
                max_rows=remaining_rows,
                max_result_bytes=remaining_bytes,
                active_key=f"{active_prefix}:{name}",
            )
            collected[name] = rows
            remaining_rows -= len(rows)
            remaining_bytes -= used_bytes
        version = self._server_version(int(self._libpq.library.PQserverVersion(backend.pointer())))
        schema_payload = {
            "columns": [dict(item) for item in collected["columns"]],
            "constraints": [dict(item) for item in collected["constraints"]],
            "extensions": [dict(item) for item in collected["extensions"]],
            "indexes": [dict(item) for item in collected["indexes"]],
            "server_version": version,
            "tables": [dict(item) for item in collected["tables"]],
        }
        return (
            version,
            collected["tables"],
            collected["columns"],
            collected["indexes"],
            collected["constraints"],
            collected["extensions"],
            _digest(schema_payload),
        )

    def inspect_schema(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: DatabaseSchemaRequest,
        *,
        auth_values: Mapping[str, Mapping[str, str]],
        idempotency_key: str,
    ) -> DatabaseSchemaResult:
        if not isinstance(request, DatabaseSchemaRequest):
            raise DatabaseContractError("exact DatabaseSchemaRequest is required")
        connection_record = self.get_connection(access, request.connection_ref)
        task = self._require_operation_authority(access, attempt, request.binding, "inspect_schema")
        self._validate_request_policy(
            connection_record,
            task,
            mode=DatabaseQueryMode.READ_ONLY,
            timeout_seconds=request.timeout_seconds,
            max_rows=request.max_objects,
            max_result_bytes=request.max_result_bytes,
        )
        started = self._start_operation(access, attempt, request.operation_ref, "inspect_schema", request.payload(), (), idempotency_key=idempotency_key)
        if not started.first_claim:
            return self.get_schema_result(access, request.operation_ref)
        backend: _LibpqConnection | None = None
        failure: DatabaseFailureCategory | None = None
        sqlstate: str | None = None
        message: str | None = None
        version: str | None = None
        tables: tuple[Mapping[str, object], ...] = ()
        columns: tuple[Mapping[str, object], ...] = ()
        indexes: tuple[Mapping[str, object], ...] = ()
        constraints: tuple[Mapping[str, object], ...] = ()
        extensions: tuple[Mapping[str, object], ...] = ()
        schema_sha: str | None = None
        try:
            backend = self._acquire_backend(connection_record, auth_values, request.timeout_seconds)
            version, tables, columns, indexes, constraints, extensions, schema_sha = self._inspect_backend_schema(
                backend,
                timeout_seconds=request.timeout_seconds,
                max_objects=request.max_objects,
                max_result_bytes=request.max_result_bytes,
                active_prefix=request.operation_ref.value,
            )
        except _BackendFailure as exc:
            failure, sqlstate, message = exc.category, exc.sqlstate, self._sanitize(exc.message or exc.category.value, ())
        finally:
            if backend is not None:
                self._release_backend(connection_record, backend, auth_values)
        success = failure is None
        completed_at = _now()
        receipt_payload = {
            "columns": [dict(item) for item in columns],
            "completed_at": completed_at,
            "connection_ref": connection_record.connection_ref.value,
            "constraints": [dict(item) for item in constraints],
            "database_identity": connection_record.database_identity,
            "extensions": [dict(item) for item in extensions],
            "failure": None if failure is None else failure.value,
            "indexes": [dict(item) for item in indexes],
            "operation": "inspect_schema",
            "operation_ref": request.operation_ref.value,
            "schema_sha256": schema_sha,
            "server_version": version,
            "sqlstate": sqlstate,
            "success": success,
            "tables": [dict(item) for item in tables],
            "timeout_enforcement": "libpq-cancel-and-client-deadline",
        }
        receipt_ref = self._finish_call(access, attempt, started, success=success, failure=failure, receipt_payload=receipt_payload)
        result = DatabaseSchemaResult(
            request.operation_ref,
            connection_record.connection_ref,
            success,
            version,
            tables,
            columns,
            indexes,
            constraints,
            extensions,
            schema_sha,
            failure,
            sqlstate,
            message,
            started.call.call_ref,
            receipt_ref,
            completed_at,
        )
        self._store_result(result, request.operation_ref, "SCHEMA")
        return result

    def get_schema_result(self, access: ProjectAccess, operation_ref: DatabaseOperationRef) -> DatabaseSchemaResult:
        payload = self._prior_payload(access, operation_ref, "SCHEMA")
        result = DatabaseSchemaResult(
            self._operation_ref(payload["operation_ref"], access.project_ref),
            self._connection_ref(payload["connection_ref"], access.project_ref),
            cast(bool, payload["success"]),
            cast(str | None, payload["server_version"]),
            tuple(cast(list[Mapping[str, object]], payload["tables"])),
            tuple(cast(list[Mapping[str, object]], payload["columns"])),
            tuple(cast(list[Mapping[str, object]], payload["indexes"])),
            tuple(cast(list[Mapping[str, object]], payload["constraints"])),
            tuple(cast(list[Mapping[str, object]], payload["extensions"])),
            cast(str | None, payload["schema_sha256"]),
            self._failure(payload["failure"]),
            cast(str | None, payload["sqlstate"]),
            cast(str | None, payload["message"]),
            self._tool_ref(payload["tool_call_ref"], access.project_ref),
            self._receipt_from_value(payload["receipt_ref"]),
            cast(str, payload["completed_at"]),
        )
        self._verify_stored_result(operation_ref, result)
        return result

    def migrate(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: DatabaseMigrationRequest,
        *,
        auth_values: Mapping[str, Mapping[str, str]],
        idempotency_key: str,
    ) -> DatabaseMigrationResult:
        if not isinstance(request, DatabaseMigrationRequest):
            raise DatabaseContractError("exact DatabaseMigrationRequest is required")
        connection_record = self.get_connection(access, request.connection_ref)
        task = self._require_operation_authority(access, attempt, request.binding, "migrate")
        self._validate_request_policy(
            connection_record,
            task,
            mode=DatabaseQueryMode.DDL_MIGRATION,
            timeout_seconds=request.timeout_seconds,
            migration=True,
            transaction=True,
        )
        artifact = self.artifacts.get_artifact(access, request.migration_artifact_ref)
        migration_content = artifact.content_ref
        if migration_content is None or migration_content.media_type not in {"application/sql", "text/plain"}:
            raise DatabaseContractError("database migration Artifact must contain SQL")
        statement = self._read_statement(migration_content)
        started = self._start_operation(
            access,
            attempt,
            request.operation_ref,
            "migrate",
            request.payload(),
            (request.migration_artifact_ref, migration_content),
            idempotency_key=idempotency_key,
        )
        if not started.first_claim:
            return self.get_migration_result(access, request.operation_ref)
        backend: _LibpqConnection | None = None
        failure: DatabaseFailureCategory | None = None
        sqlstate: str | None = None
        message: str | None = None
        before_sha: str | None = None
        after_sha: str | None = None
        try:
            backend = self._acquire_backend(connection_record, auth_values, request.timeout_seconds)
            before = self._inspect_backend_schema(
                backend,
                timeout_seconds=request.timeout_seconds,
                max_objects=connection_record.restrictions.max_rows,
                max_result_bytes=connection_record.restrictions.max_result_bytes,
                active_prefix=f"{request.operation_ref.value}:before",
            )
            before_sha = before[-1]
            if before_sha != request.expected_before_schema_sha256:
                raise _BackendFailure(DatabaseFailureCategory.SCHEMA_MISMATCH, message="database migration expected-before schema digest differs")
            self._simple_command(backend, "BEGIN", timeout_seconds=request.timeout_seconds, active_key=f"{request.operation_ref.value}:begin")
            try:
                self._execute_backend(
                    backend,
                    statement,
                    (),
                    timeout_seconds=request.timeout_seconds,
                    max_rows=1,
                    max_result_bytes=1024 * 1024,
                    output=None,
                    active_key=f"{request.operation_ref.value}:migration",
                )
                after = self._inspect_backend_schema(
                    backend,
                    timeout_seconds=request.timeout_seconds,
                    max_objects=connection_record.restrictions.max_rows,
                    max_result_bytes=connection_record.restrictions.max_result_bytes,
                    active_prefix=f"{request.operation_ref.value}:after",
                )
                after_sha = after[-1]
                if request.expected_after_schema_sha256 is not None and after_sha != request.expected_after_schema_sha256:
                    raise _BackendFailure(DatabaseFailureCategory.SCHEMA_MISMATCH, message="database migration expected-after schema digest differs")
                try:
                    self._simple_command(backend, "COMMIT", timeout_seconds=request.timeout_seconds, active_key=f"{request.operation_ref.value}:commit")
                except _BackendFailure as exc:
                    if exc.category in {DatabaseFailureCategory.CONNECTION_FAILED, DatabaseFailureCategory.TIMEOUT}:
                        raise _BackendFailure(
                            DatabaseFailureCategory.TRANSACTION_OUTCOME_UNKNOWN,
                            sqlstate=exc.sqlstate,
                            message="database connection was lost before migration commit outcome was observed",
                        ) from exc
                    raise
            except _BackendFailure:
                if backend.handle is not None and backend.transaction_status() in {_Libpq.PQTRANS_INTRANS, _Libpq.PQTRANS_INERROR}:
                    try:
                        self._simple_command(backend, "ROLLBACK", timeout_seconds=min(5.0, request.timeout_seconds), active_key=f"{request.operation_ref.value}:rollback")
                    except _BackendFailure:
                        backend.close()
                raise
        except _BackendFailure as exc:
            failure = exc.category
            if failure is DatabaseFailureCategory.QUERY_FAILED:
                failure = DatabaseFailureCategory.MIGRATION_FAILED
            sqlstate, message = exc.sqlstate, self._sanitize(exc.message or failure.value, ())
        finally:
            if backend is not None:
                self._release_backend(connection_record, backend, auth_values)
        success = failure is None
        completed_at = _now()
        receipt_payload = {
            "after_schema_sha256": after_sha,
            "before_schema_sha256": before_sha,
            "completed_at": completed_at,
            "connection_ref": connection_record.connection_ref.value,
            "database_identity": connection_record.database_identity,
            "failure": None if failure is None else failure.value,
            "migration_artifact_ref": request.migration_artifact_ref.value,
            "migration_content_sha256": migration_content.digest,
            "operation": "migrate",
            "operation_ref": request.operation_ref.value,
            "sqlstate": sqlstate,
            "success": success,
            "timeout_enforcement": "libpq-cancel-and-client-deadline",
        }
        receipt_ref = self._finish_call(access, attempt, started, success=success, failure=failure, receipt_payload=receipt_payload)
        result = DatabaseMigrationResult(
            request.operation_ref,
            connection_record.connection_ref,
            request.migration_artifact_ref,
            migration_content.digest,
            success,
            before_sha,
            after_sha,
            failure,
            sqlstate,
            message,
            started.call.call_ref,
            receipt_ref,
            completed_at,
        )
        self._store_result(result, request.operation_ref, "MIGRATION")
        return result

    def get_migration_result(self, access: ProjectAccess, operation_ref: DatabaseOperationRef) -> DatabaseMigrationResult:
        payload = self._prior_payload(access, operation_ref, "MIGRATION")
        artifact_ref = self._artifact_ref(payload["migration_artifact_ref"], access.project_ref)
        if artifact_ref is None:
            raise DatabaseIntegrityError("persisted database migration Artifact is missing")
        result = DatabaseMigrationResult(
            self._operation_ref(payload["operation_ref"], access.project_ref),
            self._connection_ref(payload["connection_ref"], access.project_ref),
            artifact_ref,
            cast(str, payload["migration_content_sha256"]),
            cast(bool, payload["success"]),
            cast(str | None, payload["before_schema_sha256"]),
            cast(str | None, payload["after_schema_sha256"]),
            self._failure(payload["failure"]),
            cast(str | None, payload["sqlstate"]),
            cast(str | None, payload["message"]),
            self._tool_ref(payload["tool_call_ref"], access.project_ref),
            self._receipt_from_value(payload["receipt_ref"]),
            cast(str, payload["completed_at"]),
        )
        self._verify_stored_result(operation_ref, result)
        return result

    def close(self) -> None:
        with self._condition:
            pooled = [backend for values in self._pool.values() for backend in values]
            live = [item.connection for item in self._transactions.values()]
            active = list(self._active.values())
            self._pool.clear()
            self._transactions.clear()
        for item in active:
            self._cancel_backend(item)
        for backend in (*pooled, *live):
            backend.close()
