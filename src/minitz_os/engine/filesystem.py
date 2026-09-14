"""Authorized, streamed filesystem capabilities with durable execution evidence."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import errno
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat as stat_module
from types import MappingProxyType
from typing import BinaryIO, cast
from uuid import uuid4

from .artifact import Artifact, ArtifactRef, ArtifactService, ContentRef
from .call_ledger import (
    CallAuthorityError,
    CallConflictError,
    CallLedgerService,
    ToolCall,
    ToolCallRef,
)
from .capability import Capability, CapabilityRef, CapabilityRegistry
from .execution import NodeExecutionAttempt
from .graph import GraphService
from .object_store import ObjectStorageBackend, ObjectStorageError
from .project import (
    ProjectAccess,
    ProjectIntegrityError,
    ProjectNotFoundError,
    ProjectRef,
    ProjectScopeError,
    ProjectStore,
)
from .resource import ResourceFitRequest
from .routing import (
    CapabilityImplementation,
    CapabilityImplementationRef,
    CapabilityImplementationRegistry,
    ImplementationKind,
    RoutingNotFoundError,
)
from .run import ExecutionAttempt, RunService
from .task import TaskRevisionService


_ROOT_ID = re.compile(r"fsr_[0-9a-f]{32}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_MUTATING_OPERATIONS = frozenset({"write", "mkdir", "copy", "move", "remove"})
_CAPABILITY_IDS = (
    "filesystem.read",
    "filesystem.write",
    "filesystem.list",
    "filesystem.stat",
    "filesystem.mkdir",
    "filesystem.copy",
    "filesystem.move",
    "filesystem.remove",
)
_REQUEST_MEDIA_TYPE = "application/vnd.minitz.filesystem-request+json"
_RESULT_MEDIA_TYPE = "application/vnd.minitz.filesystem-result+json"
_CHUNK_SIZE = 1024 * 1024


class FilesystemError(Exception):
    """Base class for authorized filesystem failures."""


class FilesystemContractError(FilesystemError, ValueError):
    """A filesystem request is malformed or unsafe."""


class FilesystemScopeError(FilesystemError):
    """A filesystem request crossed its authenticated Project scope."""


class FilesystemAuthorityError(FilesystemError):
    """A filesystem request lacks exact root or execution authority."""


class FilesystemConflictError(FilesystemError):
    """A filesystem identity or idempotency claim conflicts."""


class FilesystemNotFoundError(FilesystemError):
    """An exact root or path does not exist."""


class FilesystemIntegrityError(FilesystemError):
    """Durable or physical filesystem evidence failed verification."""


class FilesystemCancelledError(FilesystemError):
    """A filesystem operation was cancelled before successful publication."""


class FilesystemScope(str, Enum):
    PROJECT = "PROJECT"
    GLOBAL = "GLOBAL"


class FilesystemMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    READ_WRITE = "READ_WRITE"
    TEMPORARY = "TEMPORARY"


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise FilesystemContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FilesystemContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FilesystemContractError(f"{name} must be timezone-aware")
    return value


def _key(value: object, name: str = "idempotency_key") -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise FilesystemContractError(f"{name} is malformed")
    return value


def _freeze_payload(value: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise FilesystemContractError("operation payload must be a mapping")
    try:
        canonical = _json(dict(value))
        copied = cast(dict[str, object], json.loads(canonical))
    except (TypeError, ValueError) as exc:
        raise FilesystemContractError("operation payload must be canonical JSON") from exc
    if len(canonical.encode()) > 64 * 1024:
        raise FilesystemContractError("operation payload is unbounded")
    return MappingProxyType(copied)


@dataclass(frozen=True, order=True)
class FilesystemRootRef:
    """Opaque Project-bound authority for one canonical physical root."""

    project_ref: ProjectRef
    root_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.root_id, str) or _ROOT_ID.fullmatch(self.root_id) is None:
            raise FilesystemContractError("FilesystemRoot identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "FilesystemRootRef":
        return cls(project_ref, f"fsr_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"filesystem-root://{self.project_ref.value}/{self.root_id}"


@dataclass(frozen=True)
class FilesystemRoot:
    """Immutable registration of a canonical directory and its physical identity."""

    root_ref: FilesystemRootRef
    canonical_path: str
    scope: FilesystemScope
    mode: FilesystemMode
    allow_remove: bool
    device: int
    inode: int
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.root_ref, FilesystemRootRef):
            raise TypeError("root_ref must be FilesystemRootRef")
        if (
            not isinstance(self.canonical_path, str)
            or not os.path.isabs(self.canonical_path)
            or "\x00" in self.canonical_path
            or len(self.canonical_path.encode()) > 4096
        ):
            raise FilesystemContractError("canonical_path must be a bounded absolute path")
        if not isinstance(self.scope, FilesystemScope):
            raise FilesystemContractError("FilesystemRoot scope is malformed")
        if not isinstance(self.mode, FilesystemMode):
            raise FilesystemContractError("FilesystemRoot mode is malformed")
        if not isinstance(self.allow_remove, bool):
            raise FilesystemContractError("allow_remove must be boolean")
        if self.mode is FilesystemMode.READ_ONLY and self.allow_remove:
            raise FilesystemContractError("READ_ONLY root cannot authorize removal")
        for value, name in ((self.device, "device"), (self.inode, "inode")):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise FilesystemContractError(f"FilesystemRoot {name} is malformed")
        _timestamp(self.created_at, "created_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.root_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "allow_remove": self.allow_remove,
            "canonical_path": self.canonical_path,
            "created_at": self.created_at,
            "device": self.device,
            "inode": self.inode,
            "mode": self.mode.value,
            "root_ref": self.root_ref.value,
            "scope": self.scope.value,
        }


@dataclass(frozen=True)
class FilesystemOperation:
    """Exact durable result connected to a ToolCall, Event, ContentRef, and Artifact."""

    operation: str
    project_ref: ProjectRef
    request_ref: ContentRef
    output_ref: ContentRef
    artifact_ref: ArtifactRef
    tool_call_ref: ToolCallRef
    payload: Mapping[str, object]
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.operation not in {item.rsplit(".", 1)[1] for item in _CAPABILITY_IDS}:
            raise FilesystemContractError("Filesystem operation is malformed")
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.request_ref, ContentRef) or not isinstance(self.output_ref, ContentRef):
            raise FilesystemContractError("Filesystem operation requires exact content refs")
        if not isinstance(self.artifact_ref, ArtifactRef) or self.artifact_ref.project_ref != self.project_ref:
            raise FilesystemScopeError("Filesystem Artifact crossed Project scope")
        if not isinstance(self.tool_call_ref, ToolCallRef) or self.tool_call_ref.project_ref != self.project_ref:
            raise FilesystemScopeError("Filesystem ToolCall crossed Project scope")
        object.__setattr__(self, "payload", _freeze_payload(self.payload))
        _timestamp(self.completed_at, "completed_at")
        object.__setattr__(
            self,
            "record_sha256",
            _digest(
                {
                    "artifact_ref": self.artifact_ref.value,
                    "completed_at": self.completed_at,
                    "operation": self.operation,
                    "output_ref": self.output_ref.value,
                    "payload": dict(self.payload),
                    "project_ref": self.project_ref.value,
                    "request_ref": self.request_ref.value,
                    "tool_call_ref": self.tool_call_ref.value,
                }
            ),
        )


@dataclass(frozen=True)
class _StartedOperation:
    call: ToolCall
    request_ref: ContentRef
    request_payload: Mapping[str, object]
    first_claim: bool


class _DescriptorReader:
    """Bounded reader over an already-authorized, no-follow file descriptor."""

    def __init__(self, descriptor: int, cancelled: Callable[[], bool] | None) -> None:
        self._descriptor = descriptor
        self._cancelled = cancelled

    def read(self, size: int = -1) -> bytes:
        _check_cancelled(self._cancelled)
        requested = _CHUNK_SIZE if size < 0 else min(size, _CHUNK_SIZE)
        return os.read(self._descriptor, requested)


def _check_cancelled(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None:
        try:
            value = cancelled()
        except Exception as exc:
            raise FilesystemCancelledError("filesystem cancellation check failed closed") from exc
        if not isinstance(value, bool):
            raise FilesystemContractError("cancellation check must return boolean")
        if value:
            raise FilesystemCancelledError("filesystem operation was cancelled")


class FilesystemAdapter:
    """Project-bound local filesystem adapter; paths never confer authority."""

    def __init__(self, database_path: str | Path, object_store: ObjectStorageBackend) -> None:
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("object_store must implement ObjectStorageBackend")
        self.database_path = Path(database_path).resolve()
        self.object_store = object_store
        self.projects = ProjectStore(self.database_path)
        self.capabilities = CapabilityRegistry(self.database_path)
        self.implementations = CapabilityImplementationRegistry(self.database_path)
        self.calls = CallLedgerService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.runs = RunService(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
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
                CREATE TABLE IF NOT EXISTS filesystem_roots (
                    project_id TEXT NOT NULL,
                    root_id TEXT NOT NULL,
                    canonical_path TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    allow_remove INTEGER NOT NULL,
                    device INTEGER NOT NULL,
                    inode INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, root_id),
                    UNIQUE (project_id, root_id, record_sha256),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS filesystem_root_idempotency (
                    project_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    semantic_sha256 TEXT NOT NULL,
                    root_id TEXT NOT NULL,
                    PRIMARY KEY (project_id, idempotency_key),
                    UNIQUE (project_id, root_id),
                    FOREIGN KEY (project_id, root_id)
                      REFERENCES filesystem_roots(project_id, root_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS filesystem_root_registry_entries (
                    project_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    root_id TEXT NOT NULL,
                    root_record_sha256 TEXT NOT NULL,
                    previous_entry_sha256 TEXT,
                    created_at TEXT NOT NULL,
                    entry_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, sequence),
                    UNIQUE (project_id, sequence, entry_sha256),
                    UNIQUE (project_id, root_id),
                    FOREIGN KEY (project_id, root_id, root_record_sha256)
                      REFERENCES filesystem_roots(project_id, root_id, record_sha256)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS filesystem_root_registry_heads (
                    project_id TEXT PRIMARY KEY,
                    sequence INTEGER NOT NULL,
                    entry_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    head_sha256 TEXT NOT NULL,
                    FOREIGN KEY (project_id, sequence, entry_sha256)
                      REFERENCES filesystem_root_registry_entries(project_id, sequence, entry_sha256)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS filesystem_root_registry_anchors (
                    project_id TEXT PRIMARY KEY,
                    anchor_sha256 TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS filesystem_operation_claims (
                    project_id TEXT NOT NULL,
                    node_attempt_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    request_size INTEGER NOT NULL,
                    request_media_type TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    claim_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, node_attempt_id, idempotency_key),
                    UNIQUE (project_id, call_id),
                    FOREIGN KEY (project_id, call_id) REFERENCES calls(project_id, call_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS filesystem_roots_no_update BEFORE UPDATE ON filesystem_roots
                  BEGIN SELECT RAISE(ABORT, 'FilesystemRoot records are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_roots_no_delete BEFORE DELETE ON filesystem_roots
                  BEGIN SELECT RAISE(ABORT, 'FilesystemRoot history cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_root_idempotency_no_update BEFORE UPDATE ON filesystem_root_idempotency
                  BEGIN SELECT RAISE(ABORT, 'FilesystemRoot idempotency is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_root_idempotency_no_delete BEFORE DELETE ON filesystem_root_idempotency
                  BEGIN SELECT RAISE(ABORT, 'FilesystemRoot idempotency cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_root_registry_entries_no_update BEFORE UPDATE ON filesystem_root_registry_entries
                  BEGIN SELECT RAISE(ABORT, 'FilesystemRoot registry history is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_root_registry_entries_no_delete BEFORE DELETE ON filesystem_root_registry_entries
                  BEGIN SELECT RAISE(ABORT, 'FilesystemRoot registry history cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_root_registry_heads_no_delete BEFORE DELETE ON filesystem_root_registry_heads
                  BEGIN SELECT RAISE(ABORT, 'FilesystemRoot registry head cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_root_registry_heads_monotonic BEFORE UPDATE ON filesystem_root_registry_heads
                  WHEN NEW.project_id != OLD.project_id
                    OR NEW.sequence != OLD.sequence + 1
                    OR NOT EXISTS (
                      SELECT 1 FROM filesystem_root_registry_entries AS entry
                      WHERE entry.project_id=NEW.project_id AND entry.sequence=NEW.sequence
                        AND entry.entry_sha256=NEW.entry_sha256
                        AND entry.previous_entry_sha256=OLD.entry_sha256
                        AND entry.created_at=NEW.updated_at
                    )
                  BEGIN SELECT RAISE(ABORT, 'FilesystemRoot registry head must advance by one verified entry'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_root_registry_anchors_no_update BEFORE UPDATE ON filesystem_root_registry_anchors
                  BEGIN SELECT RAISE(ABORT, 'FilesystemRoot registry anchor is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_root_registry_anchors_no_delete BEFORE DELETE ON filesystem_root_registry_anchors
                  BEGIN SELECT RAISE(ABORT, 'FilesystemRoot registry anchor cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_operation_claims_no_update BEFORE UPDATE ON filesystem_operation_claims
                  BEGIN SELECT RAISE(ABORT, 'Filesystem operation claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS filesystem_operation_claims_no_delete BEFORE DELETE ON filesystem_operation_claims
                  BEGIN SELECT RAISE(ABORT, 'Filesystem operation claims cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def register_capabilities(
        self,
        access: ProjectAccess,
    ) -> Mapping[CapabilityRef, CapabilityImplementation]:
        """Register all eight semantic capabilities and Project implementations."""

        self._authorize(access, access.project_ref)
        registered: dict[CapabilityRef, CapabilityImplementation] = {}
        for capability_id in _CAPABILITY_IDS:
            operation = capability_id.rsplit(".", 1)[1]
            mutating = operation in _MUTATING_OPERATIONS
            capability = self.capabilities.register(
                Capability(
                    CapabilityRef(capability_id, "1.0.0"),
                    f"Authorized provider-neutral filesystem {operation}",
                    input_contract={"request": "schema://minitz/filesystem-request/1"},
                    output_contract={"result": "schema://minitz/filesystem-result/1"},
                    side_effects=(capability_id,) if mutating else (),
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
                        "adapter://minitz/filesystem",
                        "runtime://python/posix-filesystem",
                        tool_ref=f"tool://minitz/filesystem/{operation}",
                        features=("atomic-write", "no-follow", "streaming"),
                        input_features=("content-ref", "filesystem-root-ref"),
                        output_features=("artifact", "content-ref", "tool-call"),
                        side_effect_authority="PROJECT_WRITE" if mutating else "READ_ONLY",
                        resource_kinds=("runtime.host",),
                        resource_fit=ResourceFitRequest(
                            required_available={"cpu.logical_count": 0},
                        ),
                        metadata={"adapter_contract": "filesystem-v1"},
                    ),
                    idempotency_key=f"filesystem-{operation}-implementation",
                )
            if implementation.capability_ref != capability.capability_ref:
                raise FilesystemIntegrityError("Filesystem implementation capability changed")
            registered[capability.capability_ref] = implementation
        return MappingProxyType(registered)

    @staticmethod
    def capability_ref(operation: str) -> CapabilityRef:
        if f"filesystem.{operation}" not in _CAPABILITY_IDS:
            raise FilesystemContractError("filesystem operation is unknown")
        return CapabilityRef(f"filesystem.{operation}", "1.0.0")

    @staticmethod
    def _implementation_ref(project_ref: ProjectRef, operation: str) -> CapabilityImplementationRef:
        identity = hashlib.sha256(f"{project_ref.value}\x00filesystem.{operation}\x001.0.0".encode()).hexdigest()[:32]
        return CapabilityImplementationRef(project_ref, f"cimpl_{identity}")

    def register_root(
        self,
        access: ProjectAccess,
        *,
        path: str | Path,
        scope: FilesystemScope,
        mode: FilesystemMode,
        allow_remove: bool,
        idempotency_key: str,
    ) -> FilesystemRoot:
        _key(idempotency_key)
        if not isinstance(scope, FilesystemScope) or not isinstance(mode, FilesystemMode):
            raise FilesystemContractError("FilesystemRoot scope and mode must be explicit")
        if not isinstance(allow_remove, bool):
            raise FilesystemContractError("allow_remove must be boolean")
        if mode is FilesystemMode.READ_ONLY and allow_remove:
            raise FilesystemContractError("READ_ONLY root cannot authorize removal")
        self._authorize(access, access.project_ref)
        supplied = Path(path).expanduser()
        try:
            supplied_state = supplied.lstat()
            canonical = supplied.resolve(strict=True)
            physical = canonical.stat()
        except OSError as exc:
            raise FilesystemNotFoundError("FilesystemRoot directory is unavailable") from exc
        if stat_module.S_ISLNK(supplied_state.st_mode):
            raise FilesystemContractError("FilesystemRoot cannot be registered through a symlink")
        if not stat_module.S_ISDIR(physical.st_mode):
            raise FilesystemContractError("FilesystemRoot must be a directory")
        semantic = self._root_semantic_sha256(
            access.project_ref,
            os.fspath(canonical),
            scope,
            mode,
            allow_remove,
            physical.st_dev,
            physical.st_ino,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._verify_root_registry(connection, access.project_ref)
            self._ensure_root_anchor(connection, access.project_ref)
            prior = connection.execute(
                "SELECT * FROM filesystem_root_idempotency WHERE project_id=? AND idempotency_key=?",
                (access.project_ref.value, idempotency_key),
            ).fetchone()
            if prior is not None:
                if not hmac.compare_digest(cast(str, prior["semantic_sha256"]), semantic):
                    raise FilesystemConflictError("FilesystemRoot idempotency identity changed")
                root = self._fetch_root(
                    connection,
                    FilesystemRootRef(access.project_ref, cast(str, prior["root_id"])),
                )
                connection.commit()
                self._validate_physical_root(root)
                return root
            created_at = self._database_now(connection)
            root = FilesystemRoot(
                FilesystemRootRef.new(access.project_ref),
                os.fspath(canonical),
                scope,
                mode,
                allow_remove,
                physical.st_dev,
                physical.st_ino,
                created_at,
            )
            connection.execute(
                "INSERT INTO filesystem_roots VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    access.project_ref.value,
                    root.root_ref.root_id,
                    root.canonical_path,
                    root.scope.value,
                    root.mode.value,
                    int(root.allow_remove),
                    root.device,
                    root.inode,
                    root.created_at,
                    root.record_sha256,
                ),
            )
            connection.execute(
                "INSERT INTO filesystem_root_idempotency VALUES (?,?,?,?)",
                (access.project_ref.value, idempotency_key, semantic, root.root_ref.root_id),
            )
            head = connection.execute(
                "SELECT * FROM filesystem_root_registry_heads WHERE project_id=?",
                (access.project_ref.value,),
            ).fetchone()
            sequence = 1 if head is None else cast(int, head["sequence"]) + 1
            previous = None if head is None else cast(str, head["entry_sha256"])
            entry = self._root_entry_sha256(root, sequence, previous)
            connection.execute(
                "INSERT INTO filesystem_root_registry_entries VALUES (?,?,?,?,?,?,?)",
                (
                    access.project_ref.value,
                    sequence,
                    root.root_ref.root_id,
                    root.record_sha256,
                    previous,
                    root.created_at,
                    entry,
                ),
            )
            head_sha = self._root_head_sha256(access.project_ref, sequence, entry, root.created_at)
            if head is None:
                connection.execute(
                    "INSERT INTO filesystem_root_registry_heads VALUES (?,?,?,?,?)",
                    (access.project_ref.value, sequence, entry, root.created_at, head_sha),
                )
            else:
                connection.execute(
                    "UPDATE filesystem_root_registry_heads SET sequence=?,entry_sha256=?,updated_at=?,head_sha256=? WHERE project_id=?",
                    (sequence, entry, root.created_at, head_sha, access.project_ref.value),
                )
            self._verify_root_registry(connection, access.project_ref)
            connection.commit()
            return root
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise FilesystemConflictError("FilesystemRoot registration conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_root(self, access: ProjectAccess, root_ref: FilesystemRootRef) -> FilesystemRoot:
        self._authorize(access, root_ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._verify_root_registry(connection, root_ref.project_ref)
            root = self._fetch_root(connection, root_ref)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        self._validate_physical_root(root)
        return root

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectIntegrityError as exc:
            raise FilesystemIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise FilesystemScopeError("Filesystem Project scope mismatch") from exc

    @staticmethod
    def _database_now(connection: sqlite3.Connection) -> str:
        value = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now')").fetchone()[0]
        if not isinstance(value, str):
            raise FilesystemIntegrityError("durable database time is unavailable")
        return _timestamp(value, "database_now")

    @staticmethod
    def _root_anchor_sha256(project_ref: ProjectRef) -> str:
        return _digest(
            {"kind": "filesystem-root-registry", "project_ref": project_ref.value, "schema_version": 1}
        )

    @staticmethod
    def _root_semantic_sha256(
        project_ref: ProjectRef,
        canonical_path: str,
        scope: FilesystemScope,
        mode: FilesystemMode,
        allow_remove: bool,
        device: int,
        inode: int,
    ) -> str:
        return _digest(
            {
                "allow_remove": allow_remove,
                "canonical_path": canonical_path,
                "device": device,
                "inode": inode,
                "mode": mode.value,
                "project_ref": project_ref.value,
                "scope": scope.value,
            }
        )

    def _ensure_root_anchor(self, connection: sqlite3.Connection, project_ref: ProjectRef) -> None:
        expected = self._root_anchor_sha256(project_ref)
        row = connection.execute(
            "SELECT anchor_sha256 FROM filesystem_root_registry_anchors WHERE project_id=?",
            (project_ref.value,),
        ).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO filesystem_root_registry_anchors VALUES (?,?)",
                (project_ref.value, expected),
            )
        elif not hmac.compare_digest(cast(str, row["anchor_sha256"]), expected):
            raise FilesystemIntegrityError("FilesystemRoot registry Project anchor changed")

    @staticmethod
    def _root_entry_sha256(root: FilesystemRoot, sequence: int, previous: str | None) -> str:
        return _digest(
            {
                "created_at": root.created_at,
                "previous_entry_sha256": previous,
                "project_ref": root.project_ref.value,
                "root_record_sha256": root.record_sha256,
                "root_ref": root.root_ref.value,
                "sequence": sequence,
            }
        )

    @staticmethod
    def _root_head_sha256(project_ref: ProjectRef, sequence: int, entry: str, updated_at: str) -> str:
        return _digest(
            {
                "entry_sha256": entry,
                "project_ref": project_ref.value,
                "sequence": sequence,
                "updated_at": updated_at,
            }
        )

    def _verify_root_registry(self, connection: sqlite3.Connection, project_ref: ProjectRef) -> None:
        roots = connection.execute(
            "SELECT root_id,record_sha256 FROM filesystem_roots WHERE project_id=? ORDER BY root_id",
            (project_ref.value,),
        ).fetchall()
        idempotency = connection.execute(
            "SELECT root_id,semantic_sha256 FROM filesystem_root_idempotency WHERE project_id=? ORDER BY root_id",
            (project_ref.value,),
        ).fetchall()
        entries = connection.execute(
            "SELECT * FROM filesystem_root_registry_entries WHERE project_id=? ORDER BY sequence",
            (project_ref.value,),
        ).fetchall()
        head = connection.execute(
            "SELECT * FROM filesystem_root_registry_heads WHERE project_id=?",
            (project_ref.value,),
        ).fetchone()
        anchor = connection.execute(
            "SELECT anchor_sha256 FROM filesystem_root_registry_anchors WHERE project_id=?",
            (project_ref.value,),
        ).fetchone()
        if not roots:
            if idempotency or entries or head is not None or anchor is not None:
                raise FilesystemIntegrityError("FilesystemRoot empty registry has dependent evidence")
            return
        if anchor is None or not hmac.compare_digest(
            cast(str, anchor["anchor_sha256"]), self._root_anchor_sha256(project_ref)
        ):
            raise FilesystemIntegrityError("FilesystemRoot registry Project anchor is missing or changed")
        if tuple(cast(int, row["sequence"]) for row in entries) != tuple(range(1, len(entries) + 1)):
            raise FilesystemIntegrityError("FilesystemRoot registry sequence has a gap")
        previous: str | None = None
        entry_roots: dict[str, str] = {}
        for row in entries:
            root = self._fetch_root(
                connection,
                FilesystemRootRef(project_ref, cast(str, row["root_id"])),
            )
            expected = self._root_entry_sha256(root, cast(int, row["sequence"]), previous)
            if row["previous_entry_sha256"] != previous or not hmac.compare_digest(
                expected, cast(str, row["entry_sha256"])
            ):
                raise FilesystemIntegrityError("FilesystemRoot registry provenance changed")
            previous = expected
            entry_roots[root.root_ref.root_id] = root.record_sha256
        durable_roots = {cast(str, row["root_id"]): cast(str, row["record_sha256"]) for row in roots}
        claimed_roots: set[str] = set()
        for row in idempotency:
            root = self._fetch_root(
                connection,
                FilesystemRootRef(project_ref, cast(str, row["root_id"])),
            )
            expected_semantic = self._root_semantic_sha256(
                project_ref,
                root.canonical_path,
                root.scope,
                root.mode,
                root.allow_remove,
                root.device,
                root.inode,
            )
            if not hmac.compare_digest(expected_semantic, cast(str, row["semantic_sha256"])):
                raise FilesystemIntegrityError("FilesystemRoot idempotency semantics changed")
            claimed_roots.add(root.root_ref.root_id)
        if entry_roots != durable_roots or set(durable_roots) != claimed_roots:
            raise FilesystemIntegrityError("FilesystemRoot registry identity sets differ")
        if head is None or not entries:
            raise FilesystemIntegrityError("FilesystemRoot registry head is missing")
        last = entries[-1]
        if (
            head["sequence"] != last["sequence"]
            or head["entry_sha256"] != last["entry_sha256"]
            or head["updated_at"] != last["created_at"]
        ):
            raise FilesystemIntegrityError("FilesystemRoot registry head differs from history")
        expected_head = self._root_head_sha256(
            project_ref,
            cast(int, head["sequence"]),
            cast(str, head["entry_sha256"]),
            cast(str, head["updated_at"]),
        )
        if not hmac.compare_digest(expected_head, cast(str, head["head_sha256"])):
            raise FilesystemIntegrityError("FilesystemRoot registry head digest changed")

    def _fetch_root(self, connection: sqlite3.Connection, root_ref: FilesystemRootRef) -> FilesystemRoot:
        row = connection.execute(
            "SELECT * FROM filesystem_roots WHERE project_id=? AND root_id=?",
            (root_ref.project_ref.value, root_ref.root_id),
        ).fetchone()
        if row is None:
            raise FilesystemNotFoundError("FilesystemRoot not found")
        try:
            root = FilesystemRoot(
                root_ref,
                cast(str, row["canonical_path"]),
                FilesystemScope(cast(str, row["scope"])),
                FilesystemMode(cast(str, row["mode"])),
                bool(row["allow_remove"]),
                cast(int, row["device"]),
                cast(int, row["inode"]),
                cast(str, row["created_at"]),
            )
        except (TypeError, ValueError, FilesystemError) as exc:
            raise FilesystemIntegrityError("Persisted FilesystemRoot is malformed") from exc
        if not hmac.compare_digest(root.record_sha256, cast(str, row["record_sha256"])):
            raise FilesystemIntegrityError("FilesystemRoot record digest changed")
        return root

    @staticmethod
    def _validate_physical_root(root: FilesystemRoot) -> None:
        path = Path(root.canonical_path)
        try:
            state = path.lstat()
        except OSError as exc:
            raise FilesystemIntegrityError("FilesystemRoot physical directory is unavailable") from exc
        if (
            not stat_module.S_ISDIR(state.st_mode)
            or stat_module.S_ISLNK(state.st_mode)
            or state.st_dev != root.device
            or state.st_ino != root.inode
        ):
            raise FilesystemIntegrityError("FilesystemRoot physical identity changed")

    @staticmethod
    def _relative_parts(path: str, *, allow_root: bool = True) -> tuple[str, ...]:
        if (
            not isinstance(path, str)
            or not path
            or "\x00" in path
            or len(path.encode()) > 4096
            or any(ord(character) < 32 for character in path)
            or "\\" in path
        ):
            raise FilesystemContractError("filesystem path is malformed")
        if path == ".":
            if allow_root:
                return ()
            raise FilesystemContractError("operation cannot target the root itself")
        candidate = PurePosixPath(path)
        raw_parts = path.split("/")
        if (
            candidate.is_absolute()
            or path.startswith("/")
            or any(part in {"", ".", ".."} for part in raw_parts)
            or any(":" in part for part in raw_parts)
            or tuple(raw_parts) != candidate.parts
        ):
            raise FilesystemContractError("filesystem path must be canonical and relative")
        return tuple(raw_parts)

    @staticmethod
    def _root_descriptor(root: FilesystemRoot) -> int:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(root.canonical_path, flags)
            state = os.fstat(descriptor)
        except OSError as exc:
            raise FilesystemIntegrityError("FilesystemRoot cannot be opened safely") from exc
        if (
            not stat_module.S_ISDIR(state.st_mode)
            or state.st_dev != root.device
            or state.st_ino != root.inode
        ):
            os.close(descriptor)
            raise FilesystemIntegrityError("FilesystemRoot descriptor identity changed")
        return descriptor

    @staticmethod
    def _assert_descriptor_beneath(root: FilesystemRoot, descriptor: int) -> None:
        """Verify a pinned directory still has the registered root as an ancestor."""

        current = os.dup(descriptor)
        try:
            for _ in range(256):
                state = os.fstat(current)
                if state.st_dev == root.device and state.st_ino == root.inode:
                    return
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
                flags |= getattr(os, "O_NOFOLLOW", 0)
                parent = os.open("..", flags, dir_fd=current)
                parent_state = os.fstat(parent)
                if parent_state.st_dev == state.st_dev and parent_state.st_ino == state.st_ino:
                    os.close(parent)
                    break
                os.close(current)
                current = parent
        except OSError as exc:
            raise FilesystemAuthorityError("filesystem directory ancestry could not be verified") from exc
        finally:
            os.close(current)
        raise FilesystemAuthorityError("filesystem directory moved outside its authorized root")

    @classmethod
    def _parent_descriptor(
        cls,
        root: FilesystemRoot,
        parts: tuple[str, ...],
    ) -> tuple[int, str | None]:
        descriptor = cls._root_descriptor(root)
        try:
            for part in parts[:-1]:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
                flags |= getattr(os, "O_NOFOLLOW", 0)
                next_descriptor = os.open(part, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
                cls._assert_descriptor_beneath(root, descriptor)
            cls._assert_descriptor_beneath(root, descriptor)
            return descriptor, None if not parts else parts[-1]
        except OSError as exc:
            os.close(descriptor)
            if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
                raise FilesystemNotFoundError("filesystem parent path is unavailable") from exc
            raise FilesystemAuthorityError("filesystem parent traversal was rejected") from exc

    @staticmethod
    def _safe_state(
        parent_descriptor: int,
        leaf: str | None,
        *,
        allow_directory: bool,
    ) -> os.stat_result:
        try:
            state = os.fstat(parent_descriptor) if leaf is None else os.stat(
                leaf,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError as exc:
            raise FilesystemNotFoundError("filesystem target is unavailable") from exc
        except OSError as exc:
            raise FilesystemAuthorityError("filesystem target could not be inspected safely") from exc
        if stat_module.S_ISLNK(state.st_mode):
            raise FilesystemAuthorityError("symlink or junction targets are not authorized")
        if stat_module.S_ISDIR(state.st_mode):
            if allow_directory:
                return state
            raise FilesystemContractError("filesystem target must be a regular file")
        if not stat_module.S_ISREG(state.st_mode):
            raise FilesystemAuthorityError("unsafe special filesystem target was rejected")
        return state

    @classmethod
    def _open_regular(
        cls,
        root: FilesystemRoot,
        path: str,
    ) -> tuple[int, os.stat_result]:
        parts = cls._relative_parts(path, allow_root=False)
        parent, leaf = cls._parent_descriptor(root, parts)
        assert leaf is not None
        try:
            cls._safe_state(parent, leaf, allow_directory=False)
            flags = os.O_RDONLY | os.O_CLOEXEC
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(leaf, flags, dir_fd=parent)
            state = os.fstat(descriptor)
            if not stat_module.S_ISREG(state.st_mode):
                raise FilesystemAuthorityError("filesystem target changed during secure open")
            return descriptor, state
        except OSError as exc:
            if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
                raise FilesystemNotFoundError("filesystem target is unavailable") from exc
            raise FilesystemAuthorityError("filesystem target could not be opened safely") from exc
        finally:
            os.close(parent)

    def _stream_path_to_store(
        self,
        root: FilesystemRoot,
        path: str,
        *,
        media_type: str,
        cancelled: Callable[[], bool] | None,
    ) -> ContentRef:
        descriptor, before = self._open_regular(root, path)
        try:
            content_ref = self.object_store.put(
                _DescriptorReader(descriptor, cancelled),
                media_type=media_type,
                expected_size=before.st_size,
            )
            after = os.fstat(descriptor)
            if (
                after.st_dev != before.st_dev
                or after.st_ino != before.st_ino
                or after.st_size != before.st_size
                or after.st_mtime_ns != before.st_mtime_ns
            ):
                raise FilesystemConflictError("filesystem source changed while it was streamed")
            _check_cancelled(cancelled)
            return content_ref
        finally:
            os.close(descriptor)

    @staticmethod
    def _write_all(descriptor: int, chunk: bytes) -> None:
        offset = 0
        while offset < len(chunk):
            written = os.write(descriptor, chunk[offset:])
            if written <= 0:
                raise FilesystemIntegrityError("atomic write made no forward progress")
            offset += written

    @classmethod
    def _target_state(cls, parent: int, leaf: str) -> tuple[int, int, int] | None:
        try:
            state = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if stat_module.S_ISLNK(state.st_mode):
            raise FilesystemAuthorityError("symlink or junction destination was rejected")
        if not stat_module.S_ISREG(state.st_mode):
            raise FilesystemAuthorityError("destination is not a safe regular file")
        return state.st_dev, state.st_ino, stat_module.S_IMODE(state.st_mode)

    def _atomic_write(
        self,
        root: FilesystemRoot,
        path: str,
        content_ref: ContentRef,
        *,
        mode: int | None,
        cancelled: Callable[[], bool] | None,
    ) -> ContentRef:
        parts = self._relative_parts(path, allow_root=False)
        parent, leaf = self._parent_descriptor(root, parts)
        assert leaf is not None
        temporary = f".minitz-{uuid4().hex}.tmp"
        temporary_created = False
        try:
            self._assert_descriptor_beneath(root, parent)
            before = self._target_state(parent, leaf)
            target_mode = mode if mode is not None else (before[2] if before is not None else 0o600)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(temporary, flags, 0o600, dir_fd=parent)
            temporary_created = True
            os.fchmod(descriptor, 0o600)
            digest = hashlib.sha256()
            size = 0
            try:
                with self.object_store.open(content_ref) as source:
                    while True:
                        _check_cancelled(cancelled)
                        chunk = source.read(_CHUNK_SIZE)
                        if not isinstance(chunk, bytes):
                            raise FilesystemIntegrityError("content reader returned mutable or invalid bytes")
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                        self._write_all(descriptor, chunk)
                if digest.hexdigest() != content_ref.digest or size != content_ref.size_bytes:
                    raise FilesystemIntegrityError("atomic write source digest or size differed")
                os.fchmod(descriptor, target_mode)
                if stat_module.S_IMODE(os.fstat(descriptor).st_mode) != target_mode:
                    raise FilesystemIntegrityError("atomic write mode verification failed")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            _check_cancelled(cancelled)
            self._assert_descriptor_beneath(root, parent)
            if self._target_state(parent, leaf) != before:
                raise FilesystemConflictError("destination changed during atomic write")
            os.replace(temporary, leaf, src_dir_fd=parent, dst_dir_fd=parent)
            temporary_created = False
            os.fsync(parent)
            written_descriptor, written_state = self._open_regular(root, path)
            try:
                observed = hashlib.sha256()
                observed_size = 0
                while True:
                    chunk = os.read(written_descriptor, _CHUNK_SIZE)
                    if not chunk:
                        break
                    observed.update(chunk)
                    observed_size += len(chunk)
                if (
                    observed.hexdigest() != content_ref.digest
                    or observed_size != content_ref.size_bytes
                    or written_state.st_size != content_ref.size_bytes
                    or stat_module.S_IMODE(written_state.st_mode) != target_mode
                ):
                    raise FilesystemIntegrityError(
                        "published file failed exact content or mode verification"
                    )
            finally:
                os.close(written_descriptor)
            return content_ref
        except OSError as exc:
            raise FilesystemIntegrityError("atomic filesystem write failed") from exc
        finally:
            if temporary_created:
                try:
                    os.unlink(temporary, dir_fd=parent)
                    os.fsync(parent)
                except FileNotFoundError:
                    pass
            os.close(parent)

    def _receipt(self, payload: Mapping[str, object]) -> ContentRef:
        serialized = _json(dict(payload)).encode()
        return self.object_store.put(serialized, media_type=_RESULT_MEDIA_TYPE)

    def _require_root(
        self,
        access: ProjectAccess,
        root_ref: FilesystemRootRef,
        *,
        writable: bool,
        removable: bool = False,
    ) -> FilesystemRoot:
        if not isinstance(root_ref, FilesystemRootRef):
            raise FilesystemContractError("exact FilesystemRootRef is required")
        root = self.get_root(access, root_ref)
        if writable and root.mode is FilesystemMode.READ_ONLY:
            raise FilesystemAuthorityError("READ_ONLY FilesystemRoot denies mutation")
        if removable and not root.allow_remove:
            raise FilesystemAuthorityError("FilesystemRoot denies deletion side effects")
        return root

    def _require_operation_authority(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        operation: str,
    ) -> None:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise FilesystemAuthorityError("NodeExecutionAttempt is required")
        if attempt.node_ref.project_ref != access.project_ref:
            raise FilesystemScopeError("filesystem Node attempt crossed Project scope")
        graph = self.graphs.get_graph(access, attempt.node_ref.graph_ref)
        node = next((item for item in graph.nodes if item.node_ref == attempt.node_ref), None)
        if node is None or self.capability_ref(operation) not in node.required_capabilities:
            raise FilesystemAuthorityError("filesystem capability is not authorized by exact Node")
        task = self.tasks.get_task(access, attempt.task_ref)
        if task.canonical_digest != attempt.task_digest:
            raise FilesystemIntegrityError("filesystem Node attempt Task digest changed")
        if operation in _MUTATING_OPERATIONS:
            allowed = {"PROJECT_WRITE", "EXTERNAL_SIDE_EFFECT"}
            if task.side_effect_authority not in allowed or node.side_effect_requirement not in allowed:
                raise FilesystemAuthorityError("filesystem mutation exceeds Task or Node authority")

    def _request_content(self, payload: Mapping[str, object]) -> ContentRef:
        return self.object_store.put(_json(dict(payload)).encode(), media_type=_REQUEST_MEDIA_TYPE)

    @staticmethod
    def _call_keys(attempt: NodeExecutionAttempt, idempotency_key: str) -> tuple[str, str]:
        material = {"attempt": attempt.record_sha256, "idempotency_key": idempotency_key}
        digest = _digest(material)
        return f"fs-start-{digest[:48]}", f"fs-finish-{digest[:47]}"

    def _start_operation(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        operation: str,
        idempotency_key: str,
        payload: Mapping[str, object],
        input_refs: Sequence[ContentRef] = (),
    ) -> _StartedOperation:
        _key(idempotency_key)
        self._require_operation_authority(access, attempt, operation)
        request_payload = _freeze_payload(payload)
        request_ref = self._request_content(request_payload)
        implementation_ref = self._implementation_ref(access.project_ref, operation)
        try:
            implementation = self.implementations.get(access, implementation_ref)
        except RoutingNotFoundError as exc:
            raise FilesystemAuthorityError("filesystem implementation is not registered") from exc
        capability_ref = self.capability_ref(operation)
        if implementation.capability_ref != capability_ref:
            raise FilesystemIntegrityError("filesystem implementation binding changed")
        start_key, _ = self._call_keys(attempt, idempotency_key)
        try:
            call = self.calls.start_tool_call(
                access,
                attempt,
                idempotency_key=start_key,
                capability_ref=capability_ref,
                purpose="INITIAL",
                retry_of=None,
                parent_model_call_ref=None,
                tool_id=cast(str, implementation.tool_ref),
                implementation_id=implementation.implementation_ref.value,
                runtime_id=implementation.runtime_ref,
                input_refs=(request_ref, *tuple(input_refs)),
                provider_trace_id=None,
            )
        except CallAuthorityError as exc:
            raise FilesystemAuthorityError("filesystem ToolCall authority was rejected") from exc
        except CallConflictError as exc:
            raise FilesystemConflictError("filesystem ToolCall idempotency conflicts") from exc
        first_claim = self._claim_operation(
            attempt,
            idempotency_key,
            operation,
            request_ref,
            call.call_ref,
            call.status,
        )
        return _StartedOperation(call, request_ref, request_payload, first_claim)

    def _claim_operation(
        self,
        attempt: NodeExecutionAttempt,
        idempotency_key: str,
        operation: str,
        request_ref: ContentRef,
        call_ref: ToolCallRef,
        call_status: str,
    ) -> bool:
        claim_payload = {
            "call_ref": call_ref.value,
            "idempotency_key": idempotency_key,
            "node_attempt_id": attempt.attempt_id,
            "operation": operation,
            "project_ref": attempt.node_ref.project_ref.value,
            "request_ref": request_ref.value,
        }
        claim_sha = _digest(claim_payload)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM filesystem_operation_claims WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?",
                (attempt.node_ref.project_ref.value, attempt.attempt_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if (
                    prior["operation"] != operation
                    or prior["request_digest"] != request_ref.digest
                    or prior["request_size"] != request_ref.size_bytes
                    or prior["request_media_type"] != request_ref.media_type
                    or prior["call_id"] != call_ref.call_id
                    or not hmac.compare_digest(cast(str, prior["claim_sha256"]), claim_sha)
                ):
                    raise FilesystemConflictError("filesystem operation idempotency identity changed")
                connection.commit()
                return False
            if call_status != "RUNNING":
                raise FilesystemIntegrityError(
                    "terminal filesystem ToolCall lost its immutable operation claim"
                )
            connection.execute(
                "INSERT INTO filesystem_operation_claims VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    attempt.node_ref.project_ref.value,
                    attempt.attempt_id,
                    idempotency_key,
                    operation,
                    request_ref.digest,
                    request_ref.size_bytes,
                    request_ref.media_type,
                    call_ref.call_id,
                    claim_sha,
                ),
            )
            connection.commit()
            return True
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise FilesystemConflictError("filesystem operation claim conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _run_attempt(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> ExecutionAttempt:
        candidates = self.runs.list_attempts(access, attempt.run_ref)
        run_attempt = next(
            (
                item
                for item in candidates
                if item.attempt_id == attempt.run_attempt_id and item.fence == attempt.run_fence
            ),
            None,
        )
        if run_attempt is None:
            raise FilesystemAuthorityError("exact Run execution authority is unavailable")
        return run_attempt

    @staticmethod
    def _unique_content_refs(values: Sequence[ContentRef]) -> tuple[ContentRef, ...]:
        return tuple(sorted({item.value: item for item in values}.values(), key=lambda item: item.value))

    def _publish_artifact(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        operation: str,
        request_ref: ContentRef,
        output_ref: ContentRef,
        source_refs: Sequence[ContentRef],
    ) -> Artifact:
        run_attempt = self._run_attempt(access, attempt)
        provenance = self._unique_content_refs((request_ref, *tuple(source_refs)))
        return self.artifacts.publish_from_run(
            access,
            producer_attempt=run_attempt,
            expected_task_ref=attempt.task_ref,
            expected_task_digest=attempt.task_digest,
            role=f"filesystem.{operation}.output",
            content_ref=output_ref,
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=provenance,
            derivation_type=f"filesystem.{operation}",
            metadata={
                "media_type": output_ref.media_type,
                "schema_ref": "schema://minitz/filesystem-operation/1",
                "schema_version": "1.0.0",
            },
        )

    def _complete_operation(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        started: _StartedOperation,
        *,
        idempotency_key: str,
        output_ref: ContentRef,
        source_refs: Sequence[ContentRef],
    ) -> FilesystemOperation:
        artifact = self._publish_artifact(
            access,
            attempt,
            operation=cast(str, started.request_payload["operation"]),
            request_ref=started.request_ref,
            output_ref=output_ref,
            source_refs=source_refs,
        )
        _, finish_key = self._call_keys(attempt, idempotency_key)
        call = self.calls.finish_tool_call(
            access,
            attempt,
            started.call.call_ref,
            idempotency_key=finish_key,
            status="SUCCEEDED",
            output_refs=(output_ref, artifact.artifact_ref),
            usage=None,
            cost=None,
            failure_category=None,
            failure_reason=None,
            failure_evidence_refs=(),
        )
        if call.completed_at is None:
            raise FilesystemIntegrityError("successful filesystem ToolCall lacks completion time")
        return FilesystemOperation(
            cast(str, started.request_payload["operation"]),
            access.project_ref,
            started.request_ref,
            output_ref,
            artifact.artifact_ref,
            call.call_ref,
            started.request_payload,
            call.completed_at,
        )

    def _fail_operation(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        started: _StartedOperation,
        *,
        idempotency_key: str,
        cancelled: bool,
    ) -> None:
        if started.call.status != "RUNNING":
            return
        _, finish_key = self._call_keys(attempt, idempotency_key)
        try:
            self.calls.finish_tool_call(
                access,
                attempt,
                started.call.call_ref,
                idempotency_key=finish_key,
                status="CANCELLED" if cancelled else "FAILED",
                output_refs=(),
                usage=None,
                cost=None,
                failure_category="CANCELLED" if cancelled else "FILESYSTEM_FAILURE",
                failure_reason="filesystem operation cancelled" if cancelled else "filesystem operation failed closed",
                failure_evidence_refs=(),
            )
        except (CallAuthorityError, CallConflictError):
            # The original failure remains authoritative. Never claim success when
            # the execution lease no longer permits terminal call publication.
            return

    def _prior_or_raise(
        self,
        access: ProjectAccess,
        started: _StartedOperation,
    ) -> FilesystemOperation | None:
        if started.first_claim:
            return None
        current = self.calls.get_tool_call(access, started.call.call_ref)
        if current.status == "SUCCEEDED":
            return self.get_operation(access, current.call_ref)
        if current.status == "RUNNING":
            raise FilesystemConflictError("filesystem operation is already claimed and incomplete")
        raise FilesystemConflictError("filesystem operation idempotency key is terminal and unsuccessful")

    def _execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        started: _StartedOperation,
        *,
        idempotency_key: str,
        action: Callable[[], tuple[ContentRef, Sequence[ContentRef]]],
    ) -> FilesystemOperation:
        prior = self._prior_or_raise(access, started)
        if prior is not None:
            return prior
        try:
            output_ref, source_refs = action()
            return self._complete_operation(
                access,
                attempt,
                started,
                idempotency_key=idempotency_key,
                output_ref=output_ref,
                source_refs=source_refs,
            )
        except Exception as exc:
            self._fail_operation(
                access,
                attempt,
                started,
                idempotency_key=idempotency_key,
                cancelled=isinstance(exc, FilesystemCancelledError),
            )
            if isinstance(exc, FilesystemError):
                raise
            if isinstance(exc, CallAuthorityError):
                raise FilesystemAuthorityError("filesystem completion authority was rejected") from exc
            if isinstance(exc, CallConflictError):
                raise FilesystemConflictError("filesystem completion conflicts") from exc
            raise FilesystemIntegrityError("filesystem operation dependency failed") from exc

    def get_operation(self, access: ProjectAccess, call_ref: ToolCallRef) -> FilesystemOperation:
        if not isinstance(call_ref, ToolCallRef):
            raise FilesystemContractError("exact ToolCallRef is required")
        self._authorize(access, call_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM filesystem_operation_claims WHERE project_id=? AND call_id=?",
                (call_ref.project_ref.value, call_ref.call_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise FilesystemNotFoundError("filesystem operation claim not found")
        request_ref = ContentRef(
            "sha256",
            cast(str, row["request_digest"]),
            cast(int, row["request_size"]),
            cast(str, row["request_media_type"]),
        )
        expected_claim = _digest(
            {
                "call_ref": call_ref.value,
                "idempotency_key": cast(str, row["idempotency_key"]),
                "node_attempt_id": cast(str, row["node_attempt_id"]),
                "operation": cast(str, row["operation"]),
                "project_ref": call_ref.project_ref.value,
                "request_ref": request_ref.value,
            }
        )
        if not hmac.compare_digest(expected_claim, cast(str, row["claim_sha256"])):
            raise FilesystemIntegrityError("filesystem operation claim digest changed")
        call = self.calls.get_tool_call(access, call_ref)
        if call.status != "SUCCEEDED" or call.completed_at is None:
            raise FilesystemConflictError("filesystem operation is not durably successful")
        artifacts = tuple(item for item in call.output_refs if isinstance(item, ArtifactRef))
        contents = tuple(item for item in call.output_refs if isinstance(item, ContentRef))
        if len(artifacts) != 1 or len(contents) != 1:
            raise FilesystemIntegrityError("filesystem ToolCall outputs are not exact")
        artifact = self.artifacts.get_artifact(access, artifacts[0])
        if artifact.content_ref != contents[0]:
            raise FilesystemIntegrityError("filesystem Artifact and ContentRef differ")
        try:
            raw_payload = json.loads(self.object_store.read(request_ref))
        except (TypeError, ValueError, json.JSONDecodeError, ObjectStorageError) as exc:
            raise FilesystemIntegrityError("filesystem request evidence is malformed") from exc
        if not isinstance(raw_payload, dict) or raw_payload.get("operation") != row["operation"]:
            raise FilesystemIntegrityError("filesystem request operation changed")
        return FilesystemOperation(
            cast(str, row["operation"]),
            access.project_ref,
            request_ref,
            contents[0],
            artifacts[0],
            call_ref,
            cast(dict[str, object], raw_payload),
            call.completed_at,
        )

    def read(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        root_ref: FilesystemRootRef,
        path: str,
        media_type: str,
        idempotency_key: str,
        cancelled: Callable[[], bool] | None = None,
    ) -> FilesystemOperation:
        root = self._require_root(access, root_ref, writable=False)
        self._relative_parts(path, allow_root=False)
        payload = {
            "operation": "read",
            "path": path,
            "root_ref": root.root_ref.value,
            "schema_version": 1,
        }
        started = self._start_operation(
            access,
            attempt,
            operation="read",
            idempotency_key=idempotency_key,
            payload=payload,
        )

        def action() -> tuple[ContentRef, Sequence[ContentRef]]:
            output = self._stream_path_to_store(
                root,
                path,
                media_type=media_type,
                cancelled=cancelled,
            )
            return output, (output,)

        return self._execute(
            access,
            attempt,
            started,
            idempotency_key=idempotency_key,
            action=action,
        )

    def write(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        root_ref: FilesystemRootRef,
        path: str,
        content_ref: ContentRef,
        idempotency_key: str,
        mode: int | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> FilesystemOperation:
        if not isinstance(content_ref, ContentRef):
            raise FilesystemContractError("write requires exact ContentRef input")
        if mode is not None and (
            not isinstance(mode, int)
            or isinstance(mode, bool)
            or mode < 0
            or mode > 0o7777
        ):
            raise FilesystemContractError(
                "write mode must contain only permission and special mode bits"
            )
        root = self._require_root(access, root_ref, writable=True)
        self._relative_parts(path, allow_root=False)
        payload = {
            "content_ref": content_ref.value,
            "operation": "write",
            "path": path,
            "root_ref": root.root_ref.value,
            "schema_version": 2 if mode is not None else 1,
        }
        if mode is not None:
            payload["mode"] = mode
        started = self._start_operation(
            access,
            attempt,
            operation="write",
            idempotency_key=idempotency_key,
            payload=payload,
            input_refs=(content_ref,),
        )

        def action() -> tuple[ContentRef, Sequence[ContentRef]]:
            return self._atomic_write(
                root,
                path,
                content_ref,
                mode=mode,
                cancelled=cancelled,
            ), (content_ref,)

        return self._execute(
            access,
            attempt,
            started,
            idempotency_key=idempotency_key,
            action=action,
        )

    def list(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        root_ref: FilesystemRootRef,
        path: str,
        idempotency_key: str,
        cancelled: Callable[[], bool] | None = None,
    ) -> FilesystemOperation:
        root = self._require_root(access, root_ref, writable=False)
        parts = self._relative_parts(path)
        payload = {
            "operation": "list",
            "path": path,
            "root_ref": root.root_ref.value,
            "schema_version": 1,
        }
        started = self._start_operation(
            access,
            attempt,
            operation="list",
            idempotency_key=idempotency_key,
            payload=payload,
        )

        def action() -> tuple[ContentRef, Sequence[ContentRef]]:
            _check_cancelled(cancelled)
            parent, leaf = self._parent_descriptor(root, parts)
            directory = parent
            close_directory = False
            try:
                self._assert_descriptor_beneath(root, directory)
                if leaf is not None:
                    self._safe_state(parent, leaf, allow_directory=True)
                    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
                    flags |= getattr(os, "O_NOFOLLOW", 0)
                    directory = os.open(leaf, flags, dir_fd=parent)
                    close_directory = True
                    self._assert_descriptor_beneath(root, directory)
                names = sorted(os.listdir(directory))
                if len(names) > 10_000:
                    raise FilesystemContractError("filesystem directory listing is unbounded")
                entries: list[dict[str, object]] = []
                for name in names:
                    _check_cancelled(cancelled)
                    state = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if stat_module.S_ISREG(state.st_mode):
                        kind = "file"
                    elif stat_module.S_ISDIR(state.st_mode):
                        kind = "directory"
                    elif stat_module.S_ISLNK(state.st_mode):
                        kind = "symlink"
                    else:
                        kind = "special"
                    entries.append({"kind": kind, "name": name, "size_bytes": state.st_size})
                result = self._receipt(
                    {
                        "entries": entries,
                        "operation": "list",
                        "root_ref": root.root_ref.value,
                        "schema_version": 1,
                    }
                )
                return result, (started.request_ref,)
            except OSError as exc:
                raise FilesystemAuthorityError("filesystem directory listing was rejected") from exc
            finally:
                if close_directory:
                    os.close(directory)
                os.close(parent)

        return self._execute(
            access,
            attempt,
            started,
            idempotency_key=idempotency_key,
            action=action,
        )

    def stat(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        root_ref: FilesystemRootRef,
        path: str,
        idempotency_key: str,
        cancelled: Callable[[], bool] | None = None,
    ) -> FilesystemOperation:
        root = self._require_root(access, root_ref, writable=False)
        parts = self._relative_parts(path)
        payload = {
            "operation": "stat",
            "path": path,
            "root_ref": root.root_ref.value,
            "schema_version": 1,
        }
        started = self._start_operation(
            access,
            attempt,
            operation="stat",
            idempotency_key=idempotency_key,
            payload=payload,
        )

        def action() -> tuple[ContentRef, Sequence[ContentRef]]:
            _check_cancelled(cancelled)
            parent, leaf = self._parent_descriptor(root, parts)
            try:
                state = self._safe_state(parent, leaf, allow_directory=True)
                result = self._receipt(
                    {
                        "kind": "directory" if stat_module.S_ISDIR(state.st_mode) else "file",
                        "mode": stat_module.S_IMODE(state.st_mode),
                        "modified_ns": state.st_mtime_ns,
                        "operation": "stat",
                        "root_ref": root.root_ref.value,
                        "schema_version": 1,
                        "size_bytes": state.st_size,
                    }
                )
                return result, (started.request_ref,)
            finally:
                os.close(parent)

        return self._execute(
            access,
            attempt,
            started,
            idempotency_key=idempotency_key,
            action=action,
        )

    def mkdir(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        root_ref: FilesystemRootRef,
        path: str,
        idempotency_key: str,
        cancelled: Callable[[], bool] | None = None,
    ) -> FilesystemOperation:
        root = self._require_root(access, root_ref, writable=True)
        parts = self._relative_parts(path, allow_root=False)
        payload = {
            "operation": "mkdir",
            "path": path,
            "root_ref": root.root_ref.value,
            "schema_version": 1,
        }
        started = self._start_operation(
            access,
            attempt,
            operation="mkdir",
            idempotency_key=idempotency_key,
            payload=payload,
        )

        def action() -> tuple[ContentRef, Sequence[ContentRef]]:
            _check_cancelled(cancelled)
            parent, leaf = self._parent_descriptor(root, parts)
            assert leaf is not None
            try:
                self._assert_descriptor_beneath(root, parent)
                os.mkdir(leaf, 0o700, dir_fd=parent)
                os.fsync(parent)
                state = self._safe_state(parent, leaf, allow_directory=True)
                if not stat_module.S_ISDIR(state.st_mode):
                    raise FilesystemIntegrityError("mkdir result is not a directory")
                result = self._receipt(
                    {
                        "kind": "directory",
                        "operation": "mkdir",
                        "root_ref": root.root_ref.value,
                        "schema_version": 1,
                    }
                )
                return result, (started.request_ref,)
            except FileExistsError as exc:
                raise FilesystemConflictError("mkdir target already exists") from exc
            except OSError as exc:
                raise FilesystemIntegrityError("mkdir failed") from exc
            finally:
                os.close(parent)

        return self._execute(
            access,
            attempt,
            started,
            idempotency_key=idempotency_key,
            action=action,
        )

    def copy(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        source_root_ref: FilesystemRootRef,
        source_path: str,
        destination_root_ref: FilesystemRootRef,
        destination_path: str,
        media_type: str,
        idempotency_key: str,
        cancelled: Callable[[], bool] | None = None,
    ) -> FilesystemOperation:
        source_root = self._require_root(access, source_root_ref, writable=False)
        destination_root = self._require_root(access, destination_root_ref, writable=True)
        self._relative_parts(source_path, allow_root=False)
        self._relative_parts(destination_path, allow_root=False)
        payload = {
            "destination_path": destination_path,
            "destination_root_ref": destination_root.root_ref.value,
            "operation": "copy",
            "schema_version": 1,
            "source_path": source_path,
            "source_root_ref": source_root.root_ref.value,
        }
        started = self._start_operation(
            access,
            attempt,
            operation="copy",
            idempotency_key=idempotency_key,
            payload=payload,
        )

        def action() -> tuple[ContentRef, Sequence[ContentRef]]:
            source = self._stream_path_to_store(
                source_root,
                source_path,
                media_type=media_type,
                cancelled=cancelled,
            )
            output = self._atomic_write(
                destination_root,
                destination_path,
                source,
                mode=None,
                cancelled=cancelled,
            )
            return output, (source,)

        return self._execute(
            access,
            attempt,
            started,
            idempotency_key=idempotency_key,
            action=action,
        )

    def move(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        source_root_ref: FilesystemRootRef,
        source_path: str,
        destination_root_ref: FilesystemRootRef,
        destination_path: str,
        media_type: str,
        idempotency_key: str,
        cancelled: Callable[[], bool] | None = None,
    ) -> FilesystemOperation:
        source_root = self._require_root(
            access,
            source_root_ref,
            writable=True,
            removable=True,
        )
        destination_root = self._require_root(access, destination_root_ref, writable=True)
        source_parts = self._relative_parts(source_path, allow_root=False)
        self._relative_parts(destination_path, allow_root=False)
        if source_root.root_ref == destination_root.root_ref and source_path == destination_path:
            raise FilesystemContractError("move source and destination must differ")
        payload = {
            "destination_path": destination_path,
            "destination_root_ref": destination_root.root_ref.value,
            "operation": "move",
            "schema_version": 1,
            "source_path": source_path,
            "source_root_ref": source_root.root_ref.value,
        }
        started = self._start_operation(
            access,
            attempt,
            operation="move",
            idempotency_key=idempotency_key,
            payload=payload,
        )

        def action() -> tuple[ContentRef, Sequence[ContentRef]]:
            source_descriptor, source_state = self._open_regular(source_root, source_path)
            try:
                source = self.object_store.put(
                    _DescriptorReader(source_descriptor, cancelled),
                    media_type=media_type,
                    expected_size=source_state.st_size,
                )
                after = os.fstat(source_descriptor)
                if (
                    after.st_dev != source_state.st_dev
                    or after.st_ino != source_state.st_ino
                    or after.st_size != source_state.st_size
                    or after.st_mtime_ns != source_state.st_mtime_ns
                ):
                    raise FilesystemConflictError("move source changed while it was streamed")
            finally:
                os.close(source_descriptor)
            output = self._atomic_write(
                destination_root,
                destination_path,
                source,
                mode=None,
                cancelled=cancelled,
            )
            _check_cancelled(cancelled)
            parent, leaf = self._parent_descriptor(source_root, source_parts)
            assert leaf is not None
            try:
                self._assert_descriptor_beneath(source_root, parent)
                current = self._safe_state(parent, leaf, allow_directory=False)
                if current.st_dev != source_state.st_dev or current.st_ino != source_state.st_ino:
                    raise FilesystemConflictError("move source changed before deletion")
                os.unlink(leaf, dir_fd=parent)
                os.fsync(parent)
            finally:
                os.close(parent)
            return output, (source,)

        return self._execute(
            access,
            attempt,
            started,
            idempotency_key=idempotency_key,
            action=action,
        )

    def remove(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        root_ref: FilesystemRootRef,
        path: str,
        media_type: str,
        idempotency_key: str,
        cancelled: Callable[[], bool] | None = None,
    ) -> FilesystemOperation:
        root = self._require_root(access, root_ref, writable=True, removable=True)
        parts = self._relative_parts(path, allow_root=False)
        payload = {
            "operation": "remove",
            "path": path,
            "root_ref": root.root_ref.value,
            "schema_version": 1,
        }
        started = self._start_operation(
            access,
            attempt,
            operation="remove",
            idempotency_key=idempotency_key,
            payload=payload,
        )

        def action() -> tuple[ContentRef, Sequence[ContentRef]]:
            _check_cancelled(cancelled)
            parent, leaf = self._parent_descriptor(root, parts)
            assert leaf is not None
            try:
                self._assert_descriptor_beneath(root, parent)
                state = self._safe_state(parent, leaf, allow_directory=True)
                if stat_module.S_ISREG(state.st_mode):
                    descriptor, opened = self._open_regular(root, path)
                    try:
                        output = self.object_store.put(
                            _DescriptorReader(descriptor, cancelled),
                            media_type=media_type,
                            expected_size=opened.st_size,
                        )
                    finally:
                        os.close(descriptor)
                    _check_cancelled(cancelled)
                    self._assert_descriptor_beneath(root, parent)
                    current = self._safe_state(parent, leaf, allow_directory=False)
                    if current.st_dev != opened.st_dev or current.st_ino != opened.st_ino:
                        raise FilesystemConflictError("remove target changed before deletion")
                    os.unlink(leaf, dir_fd=parent)
                    source_refs: Sequence[ContentRef] = (output,)
                else:
                    output = self._receipt(
                        {
                            "kind": "directory",
                            "operation": "remove",
                            "root_ref": root.root_ref.value,
                            "schema_version": 1,
                        }
                    )
                    _check_cancelled(cancelled)
                    self._assert_descriptor_beneath(root, parent)
                    os.rmdir(leaf, dir_fd=parent)
                    source_refs = (started.request_ref,)
                os.fsync(parent)
                return output, source_refs
            except OSError as exc:
                raise FilesystemIntegrityError("remove failed") from exc
            finally:
                os.close(parent)

        return self._execute(
            access,
            attempt,
            started,
            idempotency_key=idempotency_key,
            action=action,
        )
