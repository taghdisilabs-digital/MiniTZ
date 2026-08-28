"""Bounded direct-executable and explicit-shell managed process adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import resource
import selectors
import signal
import sqlite3
import stat as stat_module
import subprocess
import tempfile
import time
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
from .filesystem import (
    FilesystemAdapter,
    FilesystemAuthorityError,
    FilesystemContractError,
    FilesystemError,
    FilesystemRoot,
    FilesystemRootRef,
)
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
from .scheduler import (
    ResourceAllocationRef,
    SchedulerAuthorityError,
    SchedulerConflictError,
    SchedulerContractError,
    SchedulerIntegrityError,
    SchedulerNotFoundError,
    SchedulerScopeError,
    SchedulerService,
)


_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_ENVIRONMENT_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,1024}")
_EXECUTION_ID = re.compile(r"pexec_[0-9a-f]{32}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SHELL_NAMES = frozenset({"sh", "bash", "dash", "zsh", "ksh", "fish", "cmd", "cmd.exe", "powershell", "pwsh"})
_SENSITIVE_KEY = re.compile(r"(?:secret|token|password|passwd|credential|api[_-]?key|private[_-]?key)", re.IGNORECASE)
_SENSITIVE_VALUE = re.compile(r"(?:bearer\s+|-----BEGIN [A-Z ]+PRIVATE KEY-----|(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{16,})", re.IGNORECASE)
_REQUEST_MEDIA_TYPE = "application/vnd.biella.process-request+json"
_RESULT_MEDIA_TYPE = "application/vnd.biella.process-result+json"
_STDOUT_MEDIA_TYPE = "application/vnd.biella.process-output"
_STDERR_MEDIA_TYPE = "application/vnd.biella.process-output"
_READ_CHUNK = 64 * 1024


class ProcessError(Exception):
    """Base class for managed process failures."""


class ProcessContractError(ProcessError, ValueError):
    """A managed process request is malformed."""


class ProcessScopeError(ProcessError):
    """A managed process request crossed Project scope."""


class ProcessAuthorityError(ProcessError):
    """A managed process request lacks exact execution authority."""


class ProcessConflictError(ProcessError):
    """Managed process identity or idempotency conflicts."""


class ProcessNotFoundError(ProcessError):
    """Managed process evidence was not found."""


class ProcessIntegrityError(ProcessError):
    """Managed process evidence or runtime identity failed verification."""


class NetworkPolicy(str, Enum):
    INHERIT = "INHERIT"
    NONE = "NONE"
    RESTRICTED = "RESTRICTED"


class ProcessStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


class ProcessFailure(str, Enum):
    EXECUTABLE_NOT_FOUND = "EXECUTABLE_NOT_FOUND"
    SPAWN_FAILED = "SPAWN_FAILED"
    EXIT_NONZERO = "EXIT_NONZERO"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    OUTPUT_LIMIT = "OUTPUT_LIMIT"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    POLICY_DENIED = "POLICY_DENIED"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ProcessContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProcessContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProcessContractError(f"{name} must be timezone-aware")
    return value


def _key(value: object, name: str = "idempotency_key") -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise ProcessContractError(f"{name} is malformed")
    return value


def _text(value: object, name: str, *, maximum: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or "\x00" in value
        or any(ord(character) < 32 and character not in "\t" for character in value)
        or len(value.encode()) > maximum
    ):
        raise ProcessContractError(f"{name} is malformed or unbounded")
    return value


def _preview_text(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or "\x00" in value
        or any(ord(character) < 32 and character not in "\t\r\n" for character in value)
        or len(value.encode()) > 8192
    ):
        raise ProcessContractError(f"{name} is malformed or unbounded")
    return value


def _freeze_environment(value: Mapping[str, str], name: str, *, secret_refs: bool) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or len(value) > 256:
        raise ProcessContractError(f"{name} is malformed or unbounded")
    copied = dict(value)
    for key, item in copied.items():
        if not isinstance(key, str) or _ENVIRONMENT_KEY.fullmatch(key) is None:
            raise ProcessContractError(f"{name} contains malformed environment keys")
        if secret_refs:
            if not isinstance(item, str) or _ABSOLUTE_REF.fullmatch(item) is None:
                raise ProcessContractError("secret environment values must be exact secret refs")
        else:
            _text(item, f"{name} value", maximum=16 * 1024)
            if _SENSITIVE_KEY.search(key) is not None or _SENSITIVE_VALUE.search(item) is not None:
                raise ProcessContractError("secret-looking environment data requires a secret ref")
    return MappingProxyType(dict(sorted(copied.items())))


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
        raise ProcessIntegrityError("persisted process content identity is malformed")
    try:
        return ContentRef(
            cast(str, value["algorithm"]),
            cast(str, value["digest"]),
            cast(int, value["size_bytes"]),
            cast(str, value["media_type"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProcessIntegrityError("persisted process content identity is malformed") from exc


@dataclass(frozen=True)
class ProcessResourcePolicy:
    cpu_seconds: int | None = None
    memory_bytes: int | None = None
    file_size_bytes: int | None = None
    process_count: int | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.cpu_seconds, "cpu_seconds"),
            (self.memory_bytes, "memory_bytes"),
            (self.file_size_bytes, "file_size_bytes"),
            (self.process_count, "process_count"),
        ):
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
                raise ProcessContractError(f"{name} must be a positive integer when requested")

    def payload(self) -> dict[str, int | None]:
        return {
            "cpu_seconds": self.cpu_seconds,
            "file_size_bytes": self.file_size_bytes,
            "memory_bytes": self.memory_bytes,
            "process_count": self.process_count,
        }


@dataclass(frozen=True)
class ProcessExecutionRequest:
    project_ref: ProjectRef
    working_root_ref: FilesystemRootRef
    working_directory: str
    executable: str
    argv: tuple[str, ...] = ()
    inherited_environment: tuple[str, ...] = ()
    environment_overrides: Mapping[str, str] = field(default_factory=dict)
    secret_environment_refs: Mapping[str, str] = field(default_factory=dict)
    stdin_ref: ContentRef | None = None
    timeout_seconds: float = 60.0
    termination_grace_seconds: float = 1.0
    stdout_limit_bytes: int = 16 * 1024 * 1024
    stderr_limit_bytes: int = 16 * 1024 * 1024
    network_policy: NetworkPolicy = NetworkPolicy.INHERIT
    resource_policy: ProcessResourcePolicy = field(default_factory=ProcessResourcePolicy)
    resource_allocation_ref: ResourceAllocationRef | None = None
    shell: bool = False
    request_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.working_root_ref, FilesystemRootRef):
            raise ProcessContractError("process request requires exact Project and FilesystemRoot")
        if self.working_root_ref.project_ref != self.project_ref:
            raise ProcessScopeError("process working root crossed Project scope")
        try:
            FilesystemAdapter._relative_parts(self.working_directory)
        except FilesystemContractError as exc:
            raise ProcessContractError("working_directory must be canonical and relative") from exc
        executable = _text(self.executable, "executable")
        if not os.path.isabs(executable):
            raise ProcessContractError("executable must be an absolute path, not PATH lookup")
        if not isinstance(self.argv, tuple) or len(self.argv) > 4096:
            raise ProcessContractError("argv must be a bounded tuple")
        for item in self.argv:
            _text(item, "argv item", maximum=64 * 1024)
        if (
            not isinstance(self.inherited_environment, tuple)
            or len(self.inherited_environment) > 256
            or len(set(self.inherited_environment)) != len(self.inherited_environment)
        ):
            raise ProcessContractError("inherited_environment is duplicated or unbounded")
        for key in self.inherited_environment:
            if not isinstance(key, str) or _ENVIRONMENT_KEY.fullmatch(key) is None or _SENSITIVE_KEY.search(key) is not None:
                raise ProcessContractError("inherited_environment contains unsafe keys")
        object.__setattr__(self, "inherited_environment", tuple(sorted(self.inherited_environment)))
        object.__setattr__(self, "environment_overrides", _freeze_environment(self.environment_overrides, "environment_overrides", secret_refs=False))
        object.__setattr__(self, "secret_environment_refs", _freeze_environment(self.secret_environment_refs, "secret_environment_refs", secret_refs=True))
        if set(self.environment_overrides) & set(self.secret_environment_refs):
            raise ProcessContractError("environment and secret environment keys overlap")
        if self.stdin_ref is not None and not isinstance(self.stdin_ref, ContentRef):
            raise ProcessContractError("stdin_ref must be exact ContentRef")
        for value, name in (
            (self.timeout_seconds, "timeout_seconds"),
            (self.termination_grace_seconds, "termination_grace_seconds"),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < float(value) <= 31_536_000:
                raise ProcessContractError(f"{name} is invalid")
        for value, name in (
            (self.stdout_limit_bytes, "stdout_limit_bytes"),
            (self.stderr_limit_bytes, "stderr_limit_bytes"),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 2**63 - 1:
                raise ProcessContractError(f"{name} is invalid")
        if not isinstance(self.network_policy, NetworkPolicy) or not isinstance(self.resource_policy, ProcessResourcePolicy):
            raise ProcessContractError("network or resource policy is malformed")
        if self.resource_allocation_ref is not None and (
            not isinstance(self.resource_allocation_ref, ResourceAllocationRef)
            or self.resource_allocation_ref.project_ref != self.project_ref
        ):
            raise ProcessScopeError("process ResourceAllocation crossed Project scope")
        if not isinstance(self.shell, bool):
            raise ProcessContractError("shell classification must be boolean")
        object.__setattr__(self, "request_sha256", _digest(self.payload()))

    @property
    def capability_ref(self) -> CapabilityRef:
        return CapabilityRef("process.shell" if self.shell else "process.execute", "1.0.0")

    def payload(self) -> dict[str, object]:
        return {
            "argv": list(self.argv),
            "environment_overrides": dict(self.environment_overrides),
            "executable": self.executable,
            "inherited_environment": list(self.inherited_environment),
            "network_policy": self.network_policy.value,
            "project_ref": self.project_ref.value,
            "resource_allocation_ref": None if self.resource_allocation_ref is None else self.resource_allocation_ref.value,
            "resource_policy": self.resource_policy.payload(),
            "secret_environment_refs": dict(self.secret_environment_refs),
            "shell": self.shell,
            "stderr_limit_bytes": self.stderr_limit_bytes,
            "stdin_ref": _content_payload(self.stdin_ref),
            "stdout_limit_bytes": self.stdout_limit_bytes,
            "termination_grace_seconds": float(self.termination_grace_seconds),
            "timeout_seconds": float(self.timeout_seconds),
            "working_directory": self.working_directory,
            "working_root_ref": self.working_root_ref.value,
        }


@dataclass(frozen=True)
class ManagedProcessIdentity:
    execution_id: str
    project_ref: ProjectRef
    tool_call_ref: ToolCallRef
    pid: int
    process_group_id: int
    boot_id: str
    start_ticks: int
    executable_sha256: str
    executable_device: int
    executable_inode: int
    started_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, str) or _EXECUTION_ID.fullmatch(self.execution_id) is None:
            raise ProcessContractError("managed process execution identity is malformed")
        if self.tool_call_ref.project_ref != self.project_ref:
            raise ProcessScopeError("managed process ToolCall crossed Project scope")
        for value, name in (
            (self.pid, "pid"),
            (self.process_group_id, "process_group_id"),
            (self.start_ticks, "start_ticks"),
            (self.executable_device, "executable_device"),
            (self.executable_inode, "executable_inode"),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ProcessContractError(f"managed process {name} is malformed")
        if not isinstance(self.boot_id, str) or re.fullmatch(r"[0-9a-f-]{36}", self.boot_id) is None:
            raise ProcessContractError("managed process boot identity is malformed")
        if not isinstance(self.executable_sha256, str) or _SHA256.fullmatch(self.executable_sha256) is None:
            raise ProcessContractError("managed process executable digest is malformed")
        _timestamp(self.started_at, "started_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "boot_id": self.boot_id,
            "executable_device": self.executable_device,
            "executable_inode": self.executable_inode,
            "executable_sha256": self.executable_sha256,
            "execution_id": self.execution_id,
            "pid": self.pid,
            "process_group_id": self.process_group_id,
            "project_ref": self.project_ref.value,
            "start_ticks": self.start_ticks,
            "started_at": self.started_at,
            "tool_call_ref": self.tool_call_ref.value,
        }


@dataclass(frozen=True)
class ProcessResult:
    project_ref: ProjectRef
    tool_call_ref: ToolCallRef
    request_ref: ContentRef
    result_ref: ContentRef
    artifact_ref: ArtifactRef
    process_identity: ManagedProcessIdentity | None
    status: ProcessStatus
    failure: ProcessFailure | None
    exit_code: int | None
    signal_number: int | None
    stdout_ref: ContentRef
    stderr_ref: ContentRef
    stdout_truncated: bool
    stderr_truncated: bool
    stdout_preview: str
    stderr_preview: str
    termination_method: str
    process_tree_state: str
    network_enforcement: str
    resource_enforcement: Mapping[str, str]
    started_at: str
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.tool_call_ref.project_ref != self.project_ref or self.artifact_ref.project_ref != self.project_ref:
            raise ProcessScopeError("process result crossed Project scope")
        for content_identity in (self.request_ref, self.result_ref, self.stdout_ref, self.stderr_ref):
            if not isinstance(content_identity, ContentRef):
                raise ProcessContractError("process result requires exact ContentRefs")
        if self.process_identity is not None and self.process_identity.project_ref != self.project_ref:
            raise ProcessScopeError("process identity crossed Project scope")
        if not isinstance(self.status, ProcessStatus) or not isinstance(self.failure, (ProcessFailure, type(None))):
            raise ProcessContractError("process result status is malformed")
        if (self.status is ProcessStatus.SUCCEEDED) != (self.failure is None):
            raise ProcessContractError("process success and failure taxonomy differ")
        for numeric_value, name in ((self.exit_code, "exit_code"), (self.signal_number, "signal_number")):
            if numeric_value is not None and (not isinstance(numeric_value, int) or isinstance(numeric_value, bool)):
                raise ProcessContractError(f"process {name} is malformed")
        if not isinstance(self.stdout_truncated, bool) or not isinstance(self.stderr_truncated, bool):
            raise ProcessContractError("process truncation evidence is malformed")
        for preview_value, name in ((self.stdout_preview, "stdout_preview"), (self.stderr_preview, "stderr_preview")):
            _preview_text(preview_value, name)
        for evidence_value, name in (
            (self.termination_method, "termination_method"),
            (self.process_tree_state, "process_tree_state"),
            (self.network_enforcement, "network_enforcement"),
        ):
            _text(evidence_value, name, maximum=256)
        if not isinstance(self.resource_enforcement, Mapping):
            raise ProcessContractError("resource enforcement evidence must be a mapping")
        enforcement = dict(self.resource_enforcement)
        for key, enforcement_value in enforcement.items():
            _text(key, "resource enforcement key", maximum=64)
            _text(enforcement_value, "resource enforcement value", maximum=128)
        object.__setattr__(self, "resource_enforcement", MappingProxyType(dict(sorted(enforcement.items()))))
        _timestamp(self.started_at, "started_at")
        _timestamp(self.completed_at, "completed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref.value,
            "completed_at": self.completed_at,
            "exit_code": self.exit_code,
            "failure": None if self.failure is None else self.failure.value,
            "network_enforcement": self.network_enforcement,
            "process_identity": None if self.process_identity is None else self.process_identity.payload(),
            "process_tree_state": self.process_tree_state,
            "project_ref": self.project_ref.value,
            "request_ref": _content_payload(self.request_ref),
            "resource_enforcement": dict(self.resource_enforcement),
            "result_ref": _content_payload(self.result_ref),
            "signal_number": self.signal_number,
            "started_at": self.started_at,
            "status": self.status.value,
            "stderr_preview": self.stderr_preview,
            "stderr_ref": _content_payload(self.stderr_ref),
            "stderr_truncated": self.stderr_truncated,
            "stdout_preview": self.stdout_preview,
            "stdout_ref": _content_payload(self.stdout_ref),
            "stdout_truncated": self.stdout_truncated,
            "termination_method": self.termination_method,
            "tool_call_ref": self.tool_call_ref.value,
        }


class _BoundedRedactingSink:
    """Disk-backed bounded stream that redacts injected values across chunks."""

    def __init__(self, limit: int, secrets: Sequence[bytes]) -> None:
        self.limit = limit
        self.secrets = tuple(sorted(set(secrets), key=len, reverse=True))
        self.maximum_secret = max((len(item) for item in self.secrets), default=1)
        self.file = tempfile.TemporaryFile(mode="w+b")
        self.observed_bytes = 0
        self.accepted_bytes = 0
        self.truncated = False
        self._carry = b""

    def feed(self, chunk: bytes) -> None:
        if not isinstance(chunk, bytes):
            raise ProcessIntegrityError("process output stream returned invalid bytes")
        self.observed_bytes += len(chunk)
        remaining = max(0, self.limit - self.accepted_bytes)
        accepted = chunk[:remaining]
        self.accepted_bytes += len(accepted)
        if len(accepted) != len(chunk):
            self.truncated = True
        if accepted:
            combined = self._redact(self._carry + accepted)
            keep = min(len(combined), self.maximum_secret - 1)
            emit = combined[:-keep] if keep else combined
            self._carry = combined[-keep:] if keep else b""
            self.file.write(emit)

    def finish(self) -> None:
        if self._carry:
            self.file.write(self._redact(self._carry))
            self._carry = b""
        self.file.flush()
        self.file.seek(0)

    def _redact(self, value: bytes) -> bytes:
        result = value
        for secret in self.secrets:
            result = result.replace(secret, b"[REDACTED]")
        return result

    def preview(self) -> str:
        position = self.file.tell()
        self.file.seek(0, os.SEEK_END)
        size = self.file.tell()
        self.file.seek(0)
        if size <= 4096:
            payload = self.file.read()
        else:
            head = self.file.read(2048)
            self.file.seek(-2048, os.SEEK_END)
            payload = head + b"\n...[bounded tail]...\n" + self.file.read(2048)
        self.file.seek(position)
        return payload.decode("utf-8", errors="replace")

    def close(self) -> None:
        self.file.close()


@dataclass(frozen=True)
class _StartedCall:
    call: ToolCall
    request_ref: ContentRef
    first_claim: bool


@dataclass(frozen=True)
class _ProcessObservation:
    identity: ManagedProcessIdentity | None
    status: ProcessStatus
    failure: ProcessFailure | None
    exit_code: int | None
    signal_number: int | None
    stdout_ref: ContentRef
    stderr_ref: ContentRef
    stdout_truncated: bool
    stderr_truncated: bool
    stdout_preview: str
    stderr_preview: str
    termination_method: str
    process_tree_state: str
    network_enforcement: str
    resource_enforcement: Mapping[str, str]
    started_at: str
    completed_at: str


class ManagedProcessAdapter:
    """Synchronous managed-process tool implementation for the current Linux host."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        inherited_environment: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("object_store must implement ObjectStorageBackend")
        source_environment = os.environ if inherited_environment is None else inherited_environment
        if not isinstance(source_environment, Mapping):
            raise ProcessContractError("inherited environment source must be a mapping")
        copied_environment: dict[str, str] = {}
        for key, value in source_environment.items():
            if isinstance(key, str) and isinstance(value, str):
                copied_environment[key] = value
        self.database_path = Path(database_path).resolve()
        self.object_store = object_store
        self.inherited_environment = MappingProxyType(copied_environment)
        self.projects = ProjectStore(self.database_path)
        self.capabilities = CapabilityRegistry(self.database_path)
        self.implementations = CapabilityImplementationRegistry(self.database_path)
        self.calls = CallLedgerService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.runs = RunService(self.database_path)
        self.filesystem = FilesystemAdapter(self.database_path, object_store)
        self.scheduler = SchedulerService(self.database_path)
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
                CREATE TABLE IF NOT EXISTS managed_process_claims (
                    project_id TEXT NOT NULL,
                    node_attempt_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
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
                CREATE TABLE IF NOT EXISTS managed_process_executions (
                    project_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    pid INTEGER NOT NULL,
                    process_group_id INTEGER NOT NULL,
                    boot_id TEXT NOT NULL,
                    start_ticks INTEGER NOT NULL,
                    executable_sha256 TEXT NOT NULL,
                    executable_device INTEGER NOT NULL,
                    executable_inode INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, execution_id),
                    UNIQUE (project_id, call_id),
                    FOREIGN KEY (project_id, call_id) REFERENCES calls(project_id, call_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS managed_process_results (
                    project_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, call_id),
                    FOREIGN KEY (project_id, call_id) REFERENCES calls(project_id, call_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS managed_process_claims_no_update BEFORE UPDATE ON managed_process_claims
                  BEGIN SELECT RAISE(ABORT, 'Managed process claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS managed_process_claims_no_delete BEFORE DELETE ON managed_process_claims
                  BEGIN SELECT RAISE(ABORT, 'Managed process claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS managed_process_executions_no_update BEFORE UPDATE ON managed_process_executions
                  BEGIN SELECT RAISE(ABORT, 'Managed process identities are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS managed_process_executions_no_delete BEFORE DELETE ON managed_process_executions
                  BEGIN SELECT RAISE(ABORT, 'Managed process identities cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS managed_process_results_no_update BEFORE UPDATE ON managed_process_results
                  BEGIN SELECT RAISE(ABORT, 'Managed process results are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS managed_process_results_no_delete BEFORE DELETE ON managed_process_results
                  BEGIN SELECT RAISE(ABORT, 'Managed process results cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def capability_ref(*, shell: bool) -> CapabilityRef:
        return CapabilityRef("process.shell" if shell else "process.execute", "1.0.0")

    @staticmethod
    def _implementation_ref(project_ref: ProjectRef, *, shell: bool) -> CapabilityImplementationRef:
        capability_id = "process.shell" if shell else "process.execute"
        identity = hashlib.sha256(f"{project_ref.value}\x00{capability_id}\x001.0.0".encode()).hexdigest()[:32]
        return CapabilityImplementationRef(project_ref, f"cimpl_{identity}")

    def register_capabilities(
        self,
        access: ProjectAccess,
    ) -> Mapping[CapabilityRef, CapabilityImplementation]:
        self._authorize(access, access.project_ref)
        registered: dict[CapabilityRef, CapabilityImplementation] = {}
        for shell in (False, True):
            capability_ref = self.capability_ref(shell=shell)
            capability = self.capabilities.register(
                Capability(
                    capability_ref,
                    "Explicit shell interpreter process execution" if shell else "Bounded direct executable process execution",
                    input_contract={"request": "schema://biella/process-request/1"},
                    output_contract={"result": "schema://biella/process-result/1"},
                    side_effects=(capability_ref.capability_id,),
                )
            )
            implementation_ref = self._implementation_ref(access.project_ref, shell=shell)
            try:
                implementation = self.implementations.get(access, implementation_ref)
            except RoutingNotFoundError:
                operation = "shell" if shell else "execute"
                implementation = self.implementations.register(
                    access,
                    CapabilityImplementation(
                        implementation_ref,
                        capability.capability_ref,
                        "1.0.0",
                        ImplementationKind.TOOL,
                        "adapter://biella/managed-process",
                        "runtime://python/posix-process",
                        tool_ref=f"tool://biella/process/{operation}",
                        features=("argv", "bounded-output", "process-group", "streaming"),
                        input_features=("content-ref", "filesystem-root-ref"),
                        output_features=("artifact", "content-ref", "tool-call"),
                        side_effect_authority="PROJECT_WRITE",
                        resource_kinds=("runtime.host",),
                        resource_fit=ResourceFitRequest(required_available={"cpu.logical_count": 0}),
                        metadata={"adapter_contract": "managed-process-v1"},
                    ),
                    idempotency_key=f"managed-process-{operation}-implementation",
                )
            if implementation.capability_ref != capability.capability_ref:
                raise ProcessIntegrityError("managed process implementation capability changed")
            registered[capability.capability_ref] = implementation
        return MappingProxyType(registered)

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectIntegrityError as exc:
            raise ProcessIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise ProcessScopeError("managed process Project scope mismatch") from exc

    @staticmethod
    def _database_now(connection: sqlite3.Connection) -> str:
        value = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now')").fetchone()[0]
        if not isinstance(value, str):
            raise ProcessIntegrityError("durable database time is unavailable")
        return _timestamp(value, "database_now")

    def _request_ref(self, request: ProcessExecutionRequest) -> ContentRef:
        return self.object_store.put(_json(request.payload()).encode(), media_type=_REQUEST_MEDIA_TYPE)

    @staticmethod
    def _call_keys(attempt: NodeExecutionAttempt, idempotency_key: str) -> tuple[str, str]:
        digest = _digest({"attempt": attempt.record_sha256, "idempotency_key": idempotency_key})
        return f"proc-start-{digest[:46]}", f"proc-finish-{digest[:45]}"

    def _start_call(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ProcessExecutionRequest,
        *,
        idempotency_key: str,
    ) -> _StartedCall:
        _key(idempotency_key)
        if not isinstance(attempt, NodeExecutionAttempt):
            raise ProcessAuthorityError("NodeExecutionAttempt is required")
        if attempt.node_ref.project_ref != access.project_ref or request.project_ref != access.project_ref:
            raise ProcessScopeError("managed process execution crossed Project scope")
        request_ref = self._request_ref(request)
        implementation_ref = self._implementation_ref(access.project_ref, shell=request.shell)
        try:
            implementation = self.implementations.get(access, implementation_ref)
        except RoutingNotFoundError as exc:
            raise ProcessAuthorityError("managed process implementation is not registered") from exc
        start_key, _ = self._call_keys(attempt, idempotency_key)
        inputs = (request_ref,) if request.stdin_ref is None else (request_ref, request.stdin_ref)
        try:
            call = self.calls.start_tool_call(
                access,
                attempt,
                idempotency_key=start_key,
                capability_ref=request.capability_ref,
                purpose="INITIAL",
                retry_of=None,
                parent_model_call_ref=None,
                tool_id=cast(str, implementation.tool_ref),
                implementation_id=implementation.implementation_ref.value,
                runtime_id=implementation.runtime_ref,
                input_refs=inputs,
                provider_trace_id=None,
            )
        except CallAuthorityError as exc:
            raise ProcessAuthorityError("managed process ToolCall authority was rejected") from exc
        except CallConflictError as exc:
            raise ProcessConflictError("managed process ToolCall idempotency conflicts") from exc
        first_claim = self._claim(attempt, idempotency_key, request_ref, call)
        return _StartedCall(call, request_ref, first_claim)

    def _claim(
        self,
        attempt: NodeExecutionAttempt,
        idempotency_key: str,
        request_ref: ContentRef,
        call: ToolCall,
    ) -> bool:
        claim = {
            "call_ref": call.call_ref.value,
            "idempotency_key": idempotency_key,
            "node_attempt_id": attempt.attempt_id,
            "project_ref": attempt.node_ref.project_ref.value,
            "request_ref": request_ref.value,
        }
        claim_sha = _digest(claim)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM managed_process_claims WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?",
                (attempt.node_ref.project_ref.value, attempt.attempt_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if (
                    prior["request_digest"] != request_ref.digest
                    or prior["request_size"] != request_ref.size_bytes
                    or prior["request_media_type"] != request_ref.media_type
                    or prior["call_id"] != call.call_ref.call_id
                    or not hmac.compare_digest(cast(str, prior["claim_sha256"]), claim_sha)
                ):
                    raise ProcessConflictError("managed process idempotency identity changed")
                connection.commit()
                return False
            if call.status != "RUNNING":
                raise ProcessIntegrityError("terminal process ToolCall lost its immutable claim")
            connection.execute(
                "INSERT INTO managed_process_claims VALUES (?,?,?,?,?,?,?,?)",
                (
                    attempt.node_ref.project_ref.value,
                    attempt.attempt_id,
                    idempotency_key,
                    request_ref.digest,
                    request_ref.size_bytes,
                    request_ref.media_type,
                    call.call_ref.call_id,
                    claim_sha,
                ),
            )
            connection.commit()
            return True
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ProcessConflictError("managed process claim conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _current_time(self) -> str:
        connection = self._connect()
        try:
            return self._database_now(connection)
        finally:
            connection.close()

    def _validate_allocation(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ProcessExecutionRequest,
    ) -> str:
        if request.resource_allocation_ref is None:
            return "NOT_BOUND"
        try:
            allocation = self.scheduler.get_allocation(access, request.resource_allocation_ref)
        except SchedulerScopeError as exc:
            raise ProcessScopeError("process ResourceAllocation crossed Project scope") from exc
        except SchedulerContractError as exc:
            raise ProcessContractError("process ResourceAllocation is malformed") from exc
        except SchedulerIntegrityError as exc:
            raise ProcessIntegrityError("process ResourceAllocation evidence failed verification") from exc
        except (SchedulerAuthorityError, SchedulerConflictError, SchedulerNotFoundError) as exc:
            raise ProcessAuthorityError("process ResourceAllocation is unavailable or stale") from exc
        if (
            allocation.status != "DISPATCHED"
            or allocation.node_ref != attempt.node_ref
            or allocation.run_ref != attempt.run_ref
            or allocation.run_attempt_id != attempt.run_attempt_id
            or allocation.run_attempt_fence != attempt.run_fence
            or allocation.node_attempt_id != attempt.attempt_id
            or allocation.node_attempt_fence != attempt.fence
        ):
            raise ProcessAuthorityError("process ResourceAllocation is not exact and currently dispatched")
        return allocation.allocation_ref.value

    def _working_directory(self, access: ProjectAccess, request: ProcessExecutionRequest) -> tuple[FilesystemRoot, int]:
        try:
            root = self.filesystem._require_root(
                access,
                request.working_root_ref,
                writable=True,
            )
            parts = self.filesystem._relative_parts(request.working_directory)
            parent, leaf = self.filesystem._parent_descriptor(root, parts)
            if leaf is None:
                directory = parent
            else:
                try:
                    state = self.filesystem._safe_state(parent, leaf, allow_directory=True)
                    if not stat_module.S_ISDIR(state.st_mode):
                        raise ProcessContractError("process working directory must be a directory")
                    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
                    flags |= getattr(os, "O_NOFOLLOW", 0)
                    directory = os.open(leaf, flags, dir_fd=parent)
                    self.filesystem._assert_descriptor_beneath(root, directory)
                finally:
                    os.close(parent)
            return root, directory
        except FilesystemContractError as exc:
            raise ProcessContractError("process working directory is malformed") from exc
        except FilesystemAuthorityError as exc:
            raise ProcessAuthorityError("process working directory is not authorized") from exc
        except FilesystemError as exc:
            raise ProcessIntegrityError("process working directory failed verification") from exc

    @staticmethod
    def _open_executable(request: ProcessExecutionRequest) -> tuple[int, str, os.stat_result]:
        try:
            canonical = Path(request.executable).resolve(strict=True)
            state = canonical.lstat()
            flags = os.O_RDONLY | os.O_CLOEXEC
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(canonical, flags)
            opened = os.fstat(descriptor)
        except FileNotFoundError as exc:
            raise ProcessNotFoundError("process executable was not found") from exc
        except OSError as exc:
            raise ProcessIntegrityError("process executable could not be opened safely") from exc
        if (
            not stat_module.S_ISREG(state.st_mode)
            or not stat_module.S_ISREG(opened.st_mode)
            or state.st_dev != opened.st_dev
            or state.st_ino != opened.st_ino
            or opened.st_mode & 0o111 == 0
        ):
            os.close(descriptor)
            raise ProcessAuthorityError("process executable is not an authorized executable file")
        shell_name = canonical.name.lower()
        is_shell = shell_name in _SHELL_NAMES
        if request.shell != is_shell:
            os.close(descriptor)
            if is_shell:
                raise ProcessAuthorityError("shell interpreter requires process.shell capability")
            raise ProcessContractError("process.shell capability requires an explicit shell interpreter")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        os.lseek(descriptor, 0, os.SEEK_SET)
        return descriptor, digest.hexdigest(), opened

    def _environment(
        self,
        request: ProcessExecutionRequest,
        secret_values: Mapping[str, str],
    ) -> tuple[dict[str, str], tuple[bytes, ...]]:
        if not isinstance(secret_values, Mapping) or set(secret_values) != set(request.secret_environment_refs):
            raise ProcessContractError("secret values must exactly match secret environment refs")
        environment: dict[str, str] = {}
        for key in request.inherited_environment:
            if key not in self.inherited_environment:
                raise ProcessContractError("requested inherited environment key is unavailable")
            environment[key] = self.inherited_environment[key]
        environment.update(request.environment_overrides)
        secrets: list[bytes] = []
        for key, value in secret_values.items():
            if not isinstance(value, str) or "\x00" in value or not 8 <= len(value.encode()) <= 64 * 1024:
                raise ProcessContractError("secret environment value is malformed or unbounded")
            environment[key] = value
            secrets.append(value.encode())
        return environment, tuple(secrets)

    @staticmethod
    def _resource_enforcement(policy: ProcessResourcePolicy) -> Mapping[str, str]:
        values: dict[str, str] = {}
        for name, requested, limit_name in (
            ("cpu_seconds", policy.cpu_seconds, "RLIMIT_CPU"),
            ("memory_bytes", policy.memory_bytes, "RLIMIT_AS"),
            ("file_size_bytes", policy.file_size_bytes, "RLIMIT_FSIZE"),
            ("process_count", policy.process_count, "RLIMIT_NPROC"),
        ):
            if requested is None:
                values[name] = "NOT_REQUESTED"
            elif hasattr(resource, limit_name):
                values[name] = (
                    "CONFIGURED_RLIMIT_ROOT_EFFECT_NOT_GUARANTEED"
                    if name == "process_count" and os.geteuid() == 0
                    else f"ENFORCED_{limit_name}"
                )
            else:
                values[name] = "UNSUPPORTED"
        return MappingProxyType(values)

    @staticmethod
    def _limit_preexec(policy: ProcessResourcePolicy) -> Callable[[], None]:
        def apply_limits() -> None:
            requested = (
                (policy.cpu_seconds, getattr(resource, "RLIMIT_CPU", None)),
                (policy.memory_bytes, getattr(resource, "RLIMIT_AS", None)),
                (policy.file_size_bytes, getattr(resource, "RLIMIT_FSIZE", None)),
                (policy.process_count, getattr(resource, "RLIMIT_NPROC", None)),
            )
            for value, limit in requested:
                if value is not None and limit is not None:
                    hard = value + 1 if limit == getattr(resource, "RLIMIT_CPU", None) else value
                    resource.setrlimit(limit, (value, hard))

        return apply_limits

    @staticmethod
    def _boot_id() -> str:
        try:
            value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        except OSError as exc:
            raise ProcessIntegrityError("Linux boot identity is unavailable") from exc
        if re.fullmatch(r"[0-9a-f-]{36}", value) is None:
            raise ProcessIntegrityError("Linux boot identity is malformed")
        return value

    @staticmethod
    def _start_ticks(pid: int) -> int:
        try:
            raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
            tail = raw.rsplit(")", 1)[1].strip().split()
            value = int(tail[19])
        except (OSError, ValueError, IndexError) as exc:
            raise ProcessIntegrityError("managed process start identity is unavailable") from exc
        if value < 1:
            raise ProcessIntegrityError("managed process start identity is malformed")
        return value

    def _identity(
        self,
        access: ProjectAccess,
        call_ref: ToolCallRef,
        process: subprocess.Popen[bytes],
        executable_sha256: str,
        executable_state: os.stat_result,
        started_at: str,
    ) -> ManagedProcessIdentity:
        identity = ManagedProcessIdentity(
            f"pexec_{uuid4().hex}",
            access.project_ref,
            call_ref,
            process.pid,
            os.getpgid(process.pid),
            self._boot_id(),
            self._start_ticks(process.pid),
            executable_sha256,
            executable_state.st_dev,
            executable_state.st_ino,
            started_at,
        )
        if identity.process_group_id != identity.pid:
            raise ProcessIntegrityError("managed process did not receive an isolated process group")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO managed_process_executions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identity.project_ref.value,
                    identity.execution_id,
                    identity.tool_call_ref.call_id,
                    identity.pid,
                    identity.process_group_id,
                    identity.boot_id,
                    identity.start_ticks,
                    identity.executable_sha256,
                    identity.executable_device,
                    identity.executable_inode,
                    identity.started_at,
                    identity.record_sha256,
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ProcessConflictError("managed process identity conflicts") from exc
        finally:
            connection.close()
        return identity

    def _identity_is_current(self, identity: ManagedProcessIdentity) -> bool:
        try:
            return (
                self._boot_id() == identity.boot_id
                and self._start_ticks(identity.pid) == identity.start_ticks
                and os.getpgid(identity.pid) == identity.process_group_id
            )
        except (OSError, ProcessIntegrityError):
            return False

    @staticmethod
    def _owned_group_states(identity: ManagedProcessIdentity) -> tuple[str, ...]:
        states: list[str] = []
        try:
            entries = tuple(Path("/proc").iterdir())
        except OSError as exc:
            raise ProcessIntegrityError("managed process group membership is unavailable") from exc
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / "stat").read_text(encoding="ascii")
                tail = raw.rsplit(")", 1)[1].strip().split()
                process_group_id = int(tail[2])
                session_id = int(tail[3])
                state = tail[0]
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            except (OSError, ValueError, IndexError) as exc:
                raise ProcessIntegrityError("managed process group membership is malformed") from exc
            if process_group_id == identity.process_group_id and session_id == identity.pid:
                states.append(state)
        return tuple(states)

    def _owned_group_has_live_members(self, identity: ManagedProcessIdentity) -> bool:
        return any(state != "Z" for state in self._owned_group_states(identity))

    def _terminate_owned(
        self,
        process: subprocess.Popen[bytes],
        identity: ManagedProcessIdentity,
        grace_seconds: float,
        *,
        pidfd: int | None = None,
    ) -> str:
        parent_running = process.poll() is None
        parent_is_current = self._identity_is_current(identity) if parent_running else False
        group_live = self._owned_group_has_live_members(identity)
        if not parent_running and not group_live:
            return "ALREADY_EXITED"
        if not parent_is_current and not (not parent_running and pidfd is not None and group_live):
            raise ProcessAuthorityError("managed process identity changed; no signal was sent")
        try:
            os.killpg(identity.process_group_id, signal.SIGTERM)
        except ProcessLookupError:
            return "ALREADY_EXITED"
        deadline = time.monotonic() + grace_seconds
        while self._owned_group_has_live_members(identity) and time.monotonic() < deadline:
            time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
        if not self._owned_group_has_live_members(identity):
            if process.poll() is None:
                process.wait(timeout=5)
            return "SIGTERM_PROCESS_GROUP"
        if not self._identity_is_current(identity) and pidfd is None:
            raise ProcessAuthorityError("managed process identity changed before escalation; no SIGKILL was sent")
        try:
            os.killpg(identity.process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            if not self._owned_group_has_live_members(identity):
                return "SIGTERM_PROCESS_GROUP"
            raise
        kill_deadline = time.monotonic() + 5
        while self._owned_group_has_live_members(identity) and time.monotonic() < kill_deadline:
            time.sleep(0.02)
        if self._owned_group_has_live_members(identity):
            raise ProcessIntegrityError("owned process group remained live after SIGKILL")
        if process.poll() is None:
            process.wait(timeout=5)
        return "SIGTERM_THEN_SIGKILL_PROCESS_GROUP"

    def _empty_observation(
        self,
        *,
        started_at: str,
        status: ProcessStatus,
        failure: ProcessFailure,
        network_enforcement: str,
        resource_enforcement: Mapping[str, str],
    ) -> _ProcessObservation:
        empty = self.object_store.put(b"", media_type=_STDOUT_MEDIA_TYPE)
        return _ProcessObservation(
            None,
            status,
            failure,
            None,
            None,
            empty,
            empty,
            False,
            False,
            "",
            "",
            "NOT_STARTED",
            "NOT_STARTED",
            network_enforcement,
            resource_enforcement,
            started_at,
            self._current_time(),
        )

    def _run_process(
        self,
        access: ProjectAccess,
        started: _StartedCall,
        request: ProcessExecutionRequest,
        *,
        secret_values: Mapping[str, str],
        cancelled: Callable[[], bool] | None,
    ) -> _ProcessObservation:
        started_at = self._current_time()
        resource_enforcement = self._resource_enforcement(request.resource_policy)
        if request.network_policy is not NetworkPolicy.INHERIT:
            return self._empty_observation(
                started_at=started_at,
                status=ProcessStatus.FAILED,
                failure=ProcessFailure.POLICY_DENIED,
                network_enforcement=f"UNSUPPORTED_{request.network_policy.value}_POLICY_DENIED",
                resource_enforcement=resource_enforcement,
            )
        if any(value == "UNSUPPORTED" for value in resource_enforcement.values()):
            return self._empty_observation(
                started_at=started_at,
                status=ProcessStatus.FAILED,
                failure=ProcessFailure.POLICY_DENIED,
                network_enforcement="INHERITED_NOT_ISOLATED",
                resource_enforcement=resource_enforcement,
            )
        environment, secret_bytes = self._environment(request, secret_values)
        _, working_descriptor = self._working_directory(access, request)
        executable_descriptor: int | None = None
        pidfd: int | None = None
        stdin_reader: BinaryIO | None = None
        stdout_sink = _BoundedRedactingSink(request.stdout_limit_bytes, secret_bytes)
        stderr_sink = _BoundedRedactingSink(request.stderr_limit_bytes, secret_bytes)
        try:
            try:
                executable_descriptor, executable_sha256, executable_state = self._open_executable(request)
            except ProcessNotFoundError:
                return self._empty_observation(
                    started_at=started_at,
                    status=ProcessStatus.FAILED,
                    failure=ProcessFailure.EXECUTABLE_NOT_FOUND,
                    network_enforcement="INHERITED_NOT_ISOLATED",
                    resource_enforcement=resource_enforcement,
                )
            if request.stdin_ref is not None:
                stdin_reader = self.object_store.open(request.stdin_ref)
            args = (request.executable, *request.argv)
            pass_descriptors = (working_descriptor, executable_descriptor)
            try:
                process = subprocess.Popen(
                    args,
                    executable=f"/proc/self/fd/{executable_descriptor}",
                    cwd=f"/proc/self/fd/{working_descriptor}",
                    env=environment,
                    stdin=subprocess.DEVNULL if stdin_reader is None else stdin_reader,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                    pass_fds=pass_descriptors,
                    preexec_fn=self._limit_preexec(request.resource_policy),
                )
            except (OSError, subprocess.SubprocessError):
                return self._empty_observation(
                    started_at=started_at,
                    status=ProcessStatus.FAILED,
                    failure=ProcessFailure.SPAWN_FAILED,
                    network_enforcement="INHERITED_NOT_ISOLATED",
                    resource_enforcement=resource_enforcement,
                )
            try:
                pidfd = os.pidfd_open(process.pid, 0)
            except (AttributeError, OSError) as exc:
                if process.poll() is None and os.getpgid(process.pid) == process.pid:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                raise ProcessIntegrityError("managed process pidfd identity is unavailable") from exc
            try:
                identity = self._identity(
                    access,
                    started.call.call_ref,
                    process,
                    executable_sha256,
                    executable_state,
                    started_at,
                )
            except Exception:
                if process.poll() is None and os.getpgid(process.pid) == process.pid:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                raise
            assert process.stdout is not None and process.stderr is not None
            os.set_blocking(process.stdout.fileno(), False)
            os.set_blocking(process.stderr.fileno(), False)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ, stdout_sink)
            selector.register(process.stderr, selectors.EVENT_READ, stderr_sink)
            deadline = time.monotonic() + float(request.timeout_seconds)
            termination_method = "NATURAL_EXIT"
            forced_failure: ProcessFailure | None = None
            try:
                while True:
                    parent_running = process.poll() is None
                    group_live = self._owned_group_has_live_members(identity)
                    if not selector.get_map() and not parent_running and not group_live:
                        break
                    if (parent_running or group_live) and forced_failure is None:
                        if cancelled is not None:
                            try:
                                cancellation_value = cancelled()
                            except Exception as exc:
                                termination_method = self._terminate_owned(
                                    process,
                                    identity,
                                    float(request.termination_grace_seconds),
                                    pidfd=pidfd,
                                )
                                raise ProcessContractError("process cancellation check failed closed") from exc
                            if not isinstance(cancellation_value, bool):
                                termination_method = self._terminate_owned(
                                    process,
                                    identity,
                                    float(request.termination_grace_seconds),
                                    pidfd=pidfd,
                                )
                                raise ProcessContractError("process cancellation check must return boolean")
                            if cancellation_value:
                                forced_failure = ProcessFailure.CANCELLED
                        if forced_failure is None and time.monotonic() >= deadline:
                            forced_failure = ProcessFailure.TIMEOUT
                        if forced_failure is not None:
                            termination_method = self._terminate_owned(
                                process,
                                identity,
                                float(request.termination_grace_seconds),
                                pidfd=pidfd,
                            )
                    for selection, _ in selector.select(0.02):
                        stream = cast(BinaryIO, selection.fileobj)
                        sink = cast(_BoundedRedactingSink, selection.data)
                        try:
                            chunk = os.read(stream.fileno(), _READ_CHUNK)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(stream)
                            continue
                        sink.feed(chunk)
                        if sink.truncated and forced_failure is None:
                            forced_failure = ProcessFailure.OUTPUT_LIMIT
                            termination_method = self._terminate_owned(
                                process,
                                identity,
                                float(request.termination_grace_seconds),
                                pidfd=pidfd,
                            )
                exit_code = process.wait(timeout=5)
            except Exception:
                if process.poll() is None or self._owned_group_has_live_members(identity):
                    self._terminate_owned(
                        process,
                        identity,
                        float(request.termination_grace_seconds),
                        pidfd=pidfd,
                    )
                raise
            finally:
                selector.close()
                process.stdout.close()
                process.stderr.close()
            stdout_sink.finish()
            stderr_sink.finish()
            stdout_ref = self.object_store.put(stdout_sink.file, media_type=_STDOUT_MEDIA_TYPE)
            stderr_ref = self.object_store.put(stderr_sink.file, media_type=_STDERR_MEDIA_TYPE)
            signal_number = -exit_code if exit_code < 0 else None
            if forced_failure is ProcessFailure.TIMEOUT:
                status = ProcessStatus.TIMED_OUT
                failure = ProcessFailure.TIMEOUT
            elif forced_failure is ProcessFailure.CANCELLED:
                status = ProcessStatus.CANCELLED
                failure = ProcessFailure.CANCELLED
            elif forced_failure is ProcessFailure.OUTPUT_LIMIT:
                status = ProcessStatus.FAILED
                failure = ProcessFailure.OUTPUT_LIMIT
            elif exit_code == 0:
                status = ProcessStatus.SUCCEEDED
                failure = None
            elif signal_number in {
                getattr(signal, "SIGXCPU", -1),
                getattr(signal, "SIGXFSZ", -1),
            }:
                status = ProcessStatus.FAILED
                failure = ProcessFailure.RESOURCE_LIMIT
            else:
                status = ProcessStatus.FAILED
                failure = ProcessFailure.EXIT_NONZERO
            return _ProcessObservation(
                identity,
                status,
                failure,
                exit_code if exit_code >= 0 else None,
                signal_number,
                stdout_ref,
                stderr_ref,
                stdout_sink.truncated,
                stderr_sink.truncated,
                stdout_sink.preview(),
                stderr_sink.preview(),
                termination_method,
                (
                    "OWNED_PROCESS_GROUP_TERMINATED_NO_LIVE_MEMBERS"
                    if forced_failure is not None
                    else "OWNED_PROCESS_GROUP_NATURALLY_EXITED_NO_LIVE_MEMBERS"
                ),
                "INHERITED_NOT_ISOLATED",
                resource_enforcement,
                started_at,
                self._current_time(),
            )
        finally:
            stdout_sink.close()
            stderr_sink.close()
            if stdin_reader is not None:
                stdin_reader.close()
            if executable_descriptor is not None:
                os.close(executable_descriptor)
            if pidfd is not None:
                os.close(pidfd)
            os.close(working_descriptor)

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
            raise ProcessAuthorityError("exact Run execution authority is unavailable")
        return result

    @staticmethod
    def _unique_content_refs(values: Sequence[ContentRef]) -> tuple[ContentRef, ...]:
        return tuple(sorted({item.value: item for item in values}.values(), key=lambda item: item.value))

    def _result_manifest(
        self,
        request: ProcessExecutionRequest,
        observation: _ProcessObservation,
        allocation_evidence: str,
    ) -> tuple[ContentRef, dict[str, object]]:
        payload: dict[str, object] = {
            "allocation_evidence": allocation_evidence,
            "completed_at": observation.completed_at,
            "exit_code": observation.exit_code,
            "failure": None if observation.failure is None else observation.failure.value,
            "network_enforcement": observation.network_enforcement,
            "process_identity": None if observation.identity is None else observation.identity.payload(),
            "process_tree_state": observation.process_tree_state,
            "request_sha256": request.request_sha256,
            "resource_enforcement": dict(observation.resource_enforcement),
            "schema_version": 1,
            "signal_number": observation.signal_number,
            "started_at": observation.started_at,
            "status": observation.status.value,
            "stderr_preview": observation.stderr_preview,
            "stderr_ref": _content_payload(observation.stderr_ref),
            "stderr_truncated": observation.stderr_truncated,
            "stdout_preview": observation.stdout_preview,
            "stdout_ref": _content_payload(observation.stdout_ref),
            "stdout_truncated": observation.stdout_truncated,
            "termination_method": observation.termination_method,
        }
        return self.object_store.put(_json(payload).encode(), media_type=_RESULT_MEDIA_TYPE), payload

    def _publish_artifact(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ProcessExecutionRequest,
        request_ref: ContentRef,
        result_ref: ContentRef,
        observation: _ProcessObservation,
    ) -> Artifact:
        sources = [request_ref, observation.stdout_ref, observation.stderr_ref]
        if request.stdin_ref is not None:
            sources.append(request.stdin_ref)
        return self.artifacts.publish_from_run(
            access,
            producer_attempt=self._run_attempt(access, attempt),
            expected_task_ref=attempt.task_ref,
            expected_task_digest=attempt.task_digest,
            role="process.execution.result",
            content_ref=result_ref,
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=self._unique_content_refs(sources),
            derivation_type="process.execution",
            metadata={
                "media_type": result_ref.media_type,
                "schema_ref": "schema://biella/process-result/1",
                "schema_version": "1.0.0",
            },
        )

    def _complete(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ProcessExecutionRequest,
        started: _StartedCall,
        observation: _ProcessObservation,
        *,
        allocation_evidence: str,
        idempotency_key: str,
    ) -> ProcessResult:
        result_ref, _ = self._result_manifest(request, observation, allocation_evidence)
        artifact = self._publish_artifact(
            access,
            attempt,
            request,
            started.request_ref,
            result_ref,
            observation,
        )
        _, finish_key = self._call_keys(attempt, idempotency_key)
        call_status = {
            ProcessStatus.SUCCEEDED: "SUCCEEDED",
            ProcessStatus.FAILED: "FAILED",
            ProcessStatus.TIMED_OUT: "TIMED_OUT",
            ProcessStatus.CANCELLED: "CANCELLED",
        }[observation.status]
        successful = observation.status is ProcessStatus.SUCCEEDED
        try:
            call = self.calls.finish_tool_call(
                access,
                attempt,
                started.call.call_ref,
                idempotency_key=finish_key,
                status=call_status,
                output_refs=(result_ref, artifact.artifact_ref) if successful else (),
                usage=None,
                cost=None,
                failure_category=None if successful else cast(ProcessFailure, observation.failure).value,
                failure_reason=None if successful else "managed process completed without success",
                failure_evidence_refs=() if successful else (result_ref, artifact.artifact_ref),
            )
        except CallAuthorityError as exc:
            raise ProcessAuthorityError("managed process completion authority was rejected") from exc
        except CallConflictError as exc:
            raise ProcessConflictError("managed process completion conflicts") from exc
        result = ProcessResult(
            access.project_ref,
            call.call_ref,
            started.request_ref,
            result_ref,
            artifact.artifact_ref,
            observation.identity,
            observation.status,
            observation.failure,
            observation.exit_code,
            observation.signal_number,
            observation.stdout_ref,
            observation.stderr_ref,
            observation.stdout_truncated,
            observation.stderr_truncated,
            observation.stdout_preview,
            observation.stderr_preview,
            observation.termination_method,
            observation.process_tree_state,
            observation.network_enforcement,
            observation.resource_enforcement,
            observation.started_at,
            observation.completed_at,
        )
        self._persist_result(result)
        return result

    def _persist_result(self, result: ProcessResult) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO managed_process_results VALUES (?,?,?,?,?)",
                (
                    result.project_ref.value,
                    result.tool_call_ref.call_id,
                    _json(result.payload()),
                    result.completed_at,
                    result.record_sha256,
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ProcessConflictError("managed process result conflicts") from exc
        finally:
            connection.close()

    def execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ProcessExecutionRequest,
        *,
        idempotency_key: str,
        secret_values: Mapping[str, str] = MappingProxyType({}),
        cancelled: Callable[[], bool] | None = None,
    ) -> ProcessResult:
        if not isinstance(request, ProcessExecutionRequest):
            raise ProcessContractError("ProcessExecutionRequest is required")
        self._authorize(access, request.project_ref)
        started = self._start_call(
            access,
            attempt,
            request,
            idempotency_key=idempotency_key,
        )
        if not started.first_claim:
            current = self.calls.get_tool_call(access, started.call.call_ref)
            if current.status == "RUNNING":
                raise ProcessConflictError("managed process is already claimed and incomplete")
            return self.get_result(access, current.call_ref)
        try:
            allocation_evidence = self._validate_allocation(access, attempt, request)
            observation = self._run_process(
                access,
                started,
                request,
                secret_values=secret_values,
                cancelled=cancelled,
            )
            return self._complete(
                access,
                attempt,
                request,
                started,
                observation,
                allocation_evidence=allocation_evidence,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            self._fail_call(
                access,
                attempt,
                started,
                idempotency_key=idempotency_key,
            )
            if isinstance(exc, ProcessError):
                raise
            if isinstance(exc, (ObjectStorageError, FilesystemError, OSError)):
                raise ProcessIntegrityError("managed process dependency failed") from exc
            raise

    def _fail_call(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        started: _StartedCall,
        *,
        idempotency_key: str,
    ) -> None:
        current = self.calls.get_tool_call(access, started.call.call_ref)
        if current.status != "RUNNING":
            return
        _, finish_key = self._call_keys(attempt, idempotency_key)
        try:
            self.calls.finish_tool_call(
                access,
                attempt,
                current.call_ref,
                idempotency_key=finish_key,
                status="FAILED",
                output_refs=(),
                usage=None,
                cost=None,
                failure_category="PROCESS_ADAPTER_FAILURE",
                failure_reason="managed process adapter failed closed",
                failure_evidence_refs=(),
            )
        except (CallAuthorityError, CallConflictError):
            return

    @staticmethod
    def _artifact_ref(value: object, project_ref: ProjectRef) -> ArtifactRef:
        if not isinstance(value, str) or not value.startswith("artifact://"):
            raise ProcessIntegrityError("persisted process ArtifactRef is malformed")
        parts = value.removeprefix("artifact://").split("/")
        if len(parts) != 3 or parts[0] != project_ref.value:
            raise ProcessIntegrityError("persisted process ArtifactRef crossed Project scope")
        try:
            return ArtifactRef(project_ref, parts[1], int(parts[2]))
        except (TypeError, ValueError) as exc:
            raise ProcessIntegrityError("persisted process ArtifactRef is malformed") from exc

    @staticmethod
    def _identity_from_payload(
        value: object,
        project_ref: ProjectRef,
        call_ref: ToolCallRef,
    ) -> ManagedProcessIdentity | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ProcessIntegrityError("persisted managed process identity is malformed")
        try:
            return ManagedProcessIdentity(
                cast(str, value["execution_id"]),
                project_ref,
                call_ref,
                cast(int, value["pid"]),
                cast(int, value["process_group_id"]),
                cast(str, value["boot_id"]),
                cast(int, value["start_ticks"]),
                cast(str, value["executable_sha256"]),
                cast(int, value["executable_device"]),
                cast(int, value["executable_inode"]),
                cast(str, value["started_at"]),
            )
        except (KeyError, TypeError, ValueError, ProcessError) as exc:
            raise ProcessIntegrityError("persisted managed process identity is malformed") from exc

    def _result_from_payload(
        self,
        payload: object,
        project_ref: ProjectRef,
        call_ref: ToolCallRef,
    ) -> ProcessResult:
        if not isinstance(payload, dict):
            raise ProcessIntegrityError("persisted process result is malformed")
        try:
            request_ref = _content_from_payload(payload["request_ref"])
            result_ref = _content_from_payload(payload["result_ref"])
            stdout_ref = _content_from_payload(payload["stdout_ref"])
            stderr_ref = _content_from_payload(payload["stderr_ref"])
            if None in (request_ref, result_ref, stdout_ref, stderr_ref):
                raise ProcessIntegrityError("persisted process result lacks exact content")
            failure_value = cast(str | None, payload["failure"])
            return ProcessResult(
                project_ref,
                call_ref,
                cast(ContentRef, request_ref),
                cast(ContentRef, result_ref),
                self._artifact_ref(payload["artifact_ref"], project_ref),
                self._identity_from_payload(payload["process_identity"], project_ref, call_ref),
                ProcessStatus(cast(str, payload["status"])),
                None if failure_value is None else ProcessFailure(failure_value),
                cast(int | None, payload["exit_code"]),
                cast(int | None, payload["signal_number"]),
                cast(ContentRef, stdout_ref),
                cast(ContentRef, stderr_ref),
                cast(bool, payload["stdout_truncated"]),
                cast(bool, payload["stderr_truncated"]),
                cast(str, payload["stdout_preview"]),
                cast(str, payload["stderr_preview"]),
                cast(str, payload["termination_method"]),
                cast(str, payload["process_tree_state"]),
                cast(str, payload["network_enforcement"]),
                cast(dict[str, str], payload["resource_enforcement"]),
                cast(str, payload["started_at"]),
                cast(str, payload["completed_at"]),
            )
        except (KeyError, TypeError, ValueError, ProcessError) as exc:
            raise ProcessIntegrityError("persisted process result is malformed") from exc

    def _verify_result_manifest(self, result: ProcessResult) -> None:
        try:
            manifest = json.loads(self.object_store.read(result.result_ref))
        except (ObjectStorageError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProcessIntegrityError("managed process result manifest failed verification") from exc
        if not isinstance(manifest, dict):
            raise ProcessIntegrityError("managed process result manifest is malformed")
        allocation_evidence = manifest.get("allocation_evidence")
        allocation_prefix = f"resource-allocation://{result.project_ref.value}/"
        if not isinstance(allocation_evidence, str) or (
            allocation_evidence != "NOT_BOUND" and not allocation_evidence.startswith(allocation_prefix)
        ):
            raise ProcessIntegrityError("managed process allocation evidence is malformed")
        expected: dict[str, object] = {
            "allocation_evidence": allocation_evidence,
            "completed_at": result.completed_at,
            "exit_code": result.exit_code,
            "failure": None if result.failure is None else result.failure.value,
            "network_enforcement": result.network_enforcement,
            "process_identity": None if result.process_identity is None else result.process_identity.payload(),
            "process_tree_state": result.process_tree_state,
            "request_sha256": result.request_ref.digest,
            "resource_enforcement": dict(result.resource_enforcement),
            "schema_version": 1,
            "signal_number": result.signal_number,
            "started_at": result.started_at,
            "status": result.status.value,
            "stderr_preview": result.stderr_preview,
            "stderr_ref": _content_payload(result.stderr_ref),
            "stderr_truncated": result.stderr_truncated,
            "stdout_preview": result.stdout_preview,
            "stdout_ref": _content_payload(result.stdout_ref),
            "stdout_truncated": result.stdout_truncated,
            "termination_method": result.termination_method,
        }
        if manifest != expected:
            raise ProcessIntegrityError("managed process durable result and result manifest differ")

    def _verify_persisted_identity(
        self,
        connection: sqlite3.Connection,
        identity: ManagedProcessIdentity | None,
    ) -> None:
        if identity is None:
            return
        row = connection.execute(
            "SELECT * FROM managed_process_executions WHERE project_id=? AND execution_id=?",
            (identity.project_ref.value, identity.execution_id),
        ).fetchone()
        if row is None:
            raise ProcessIntegrityError("managed process identity history is missing")
        expected = (
            row["call_id"] == identity.tool_call_ref.call_id
            and row["pid"] == identity.pid
            and row["process_group_id"] == identity.process_group_id
            and row["boot_id"] == identity.boot_id
            and row["start_ticks"] == identity.start_ticks
            and row["executable_sha256"] == identity.executable_sha256
            and row["executable_device"] == identity.executable_device
            and row["executable_inode"] == identity.executable_inode
            and row["started_at"] == identity.started_at
            and hmac.compare_digest(cast(str, row["record_sha256"]), identity.record_sha256)
        )
        if not expected:
            raise ProcessIntegrityError("managed process identity evidence changed")

    def get_result(self, access: ProjectAccess, call_ref: ToolCallRef) -> ProcessResult:
        if not isinstance(call_ref, ToolCallRef):
            raise ProcessContractError("exact ToolCallRef is required")
        self._authorize(access, call_ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            claim = connection.execute(
                "SELECT * FROM managed_process_claims WHERE project_id=? AND call_id=?",
                (call_ref.project_ref.value, call_ref.call_id),
            ).fetchone()
            row = connection.execute(
                "SELECT * FROM managed_process_results WHERE project_id=? AND call_id=?",
                (call_ref.project_ref.value, call_ref.call_id),
            ).fetchone()
            if claim is None or row is None:
                raise ProcessIntegrityError("managed process claim or result history is missing")
            request_ref = ContentRef(
                "sha256",
                cast(str, claim["request_digest"]),
                cast(int, claim["request_size"]),
                cast(str, claim["request_media_type"]),
            )
            expected_claim = _digest(
                {
                    "call_ref": call_ref.value,
                    "idempotency_key": cast(str, claim["idempotency_key"]),
                    "node_attempt_id": cast(str, claim["node_attempt_id"]),
                    "project_ref": call_ref.project_ref.value,
                    "request_ref": request_ref.value,
                }
            )
            if not hmac.compare_digest(expected_claim, cast(str, claim["claim_sha256"])):
                raise ProcessIntegrityError("managed process claim digest changed")
            try:
                payload = json.loads(cast(str, row["result_json"]))
            except json.JSONDecodeError as exc:
                raise ProcessIntegrityError("managed process result JSON is malformed") from exc
            result = self._result_from_payload(payload, access.project_ref, call_ref)
            if (
                row["completed_at"] != result.completed_at
                or not hmac.compare_digest(cast(str, row["record_sha256"]), result.record_sha256)
                or result.request_ref != request_ref
            ):
                raise ProcessIntegrityError("managed process result evidence changed")
            self._verify_persisted_identity(connection, result.process_identity)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        call = self.calls.get_tool_call(access, call_ref)
        expected_call_status = {
            ProcessStatus.SUCCEEDED: "SUCCEEDED",
            ProcessStatus.FAILED: "FAILED",
            ProcessStatus.TIMED_OUT: "TIMED_OUT",
            ProcessStatus.CANCELLED: "CANCELLED",
        }[result.status]
        if call.status != expected_call_status:
            raise ProcessIntegrityError("managed process result and ToolCall status differ")
        evidence = call.output_refs if result.status is ProcessStatus.SUCCEEDED else call.failure_evidence_refs
        if {item.value for item in evidence} != {result.result_ref.value, result.artifact_ref.value}:
            raise ProcessIntegrityError("managed process ToolCall result evidence differs")
        artifact = self.artifacts.get_artifact(access, result.artifact_ref)
        if artifact.content_ref != result.result_ref:
            raise ProcessIntegrityError("managed process Artifact content differs")
        for content_ref in (
            result.request_ref,
            result.result_ref,
            result.stdout_ref,
            result.stderr_ref,
        ):
            try:
                self.object_store.verify(content_ref)
            except ObjectStorageError as exc:
                raise ProcessIntegrityError("managed process ContentRef failed verification") from exc
        self._verify_result_manifest(result)
        return result
