"""Project-scoped replaceable isolated runtime contracts and Docker adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import tempfile
from types import MappingProxyType
from typing import Protocol, cast, runtime_checkable
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
    FilesystemMode,
    FilesystemNotFoundError,
    FilesystemRoot,
    FilesystemRootRef,
)
from .graph import GraphService
from .object_store import ObjectStorageBackend, ObjectStorageError
from .process import (
    ManagedProcessAdapter,
    NetworkPolicy,
    ProcessExecutionRequest,
    ProcessResult,
    ProcessStatus,
)
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
from .run import ExecutionAttempt, RunService
from .scheduler import ResourceAllocationRef, SchedulerError, SchedulerService
from .task import TaskRevisionService


_RUNTIME_ID = re.compile(r"rt_[0-9a-f]{32}")
_IMAGE_REF = re.compile(r"(?:[a-z0-9][a-z0-9._/-]*@)?sha256:[0-9a-f]{64}")
_RECORD_SHA = re.compile(r"[0-9a-f]{64}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_ENVIRONMENT_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
_SENSITIVE_KEY = re.compile(r"(?:secret|token|pass|credential|auth|api.?key|private.?key)", re.IGNORECASE)
_SECRET_REF = re.compile(r"secret://[^\s\x00-\x1f]{1,1000}")
_OPERATIONS = (
    "create",
    "start",
    "execute",
    "cancel",
    "stop",
    "inspect",
    "collect",
    "cleanup",
    "describe",
)
_MUTATING = frozenset({"create", "start", "execute", "cancel", "stop", "collect", "cleanup"})
_REQUEST_MEDIA_TYPE = "application/vnd.biella.isolated-runtime-request+json"
_RECEIPT_MEDIA_TYPE = "application/vnd.biella.isolated-runtime-receipt+json"


class IsolatedRuntimeError(Exception):
    """Base class for isolated runtime adapter failures."""


class IsolatedRuntimeContractError(IsolatedRuntimeError, ValueError):
    """An isolated runtime request is malformed or unsupported."""


class IsolatedRuntimeScopeError(IsolatedRuntimeError):
    """An isolated runtime request crossed Project scope."""


class IsolatedRuntimeAuthorityError(IsolatedRuntimeError):
    """Task, Node, filesystem, or runtime ownership authority is absent."""


class IsolatedRuntimeConflictError(IsolatedRuntimeError):
    """A runtime generation, state, or idempotency identity is stale."""


class IsolatedRuntimeNotFoundError(IsolatedRuntimeError):
    """Required runtime, image, path, or evidence does not exist."""


class IsolatedRuntimeIntegrityError(IsolatedRuntimeError):
    """Durable or observed isolated-runtime evidence failed verification."""


def _json(payload: Mapping[str, object]) -> str:
    try:
        return json.dumps(
            dict(payload),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise IsolatedRuntimeContractError("runtime payload is not canonical JSON") from exc


def _digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(_json(payload).encode()).hexdigest()


def _text(value: object, name: str, maximum: int = 64 * 1024) -> str:
    if not isinstance(value, str) or not value or len(value.encode()) > maximum or "\x00" in value:
        raise IsolatedRuntimeContractError(f"{name} is malformed or unbounded")
    return value


def _timestamp(value: object, name: str) -> str:
    text = _text(value, name, 128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IsolatedRuntimeContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise IsolatedRuntimeContractError(f"{name} must be timezone-aware")
    return text


def _content(content_ref: ContentRef | None) -> dict[str, object] | None:
    if content_ref is None:
        return None
    return {
        "algorithm": content_ref.algorithm,
        "digest": content_ref.digest,
        "media_type": content_ref.media_type,
        "size_bytes": content_ref.size_bytes,
    }


def _absolute_container_path(value: str, name: str, *, secret: bool = False) -> str:
    text = _text(value, name, 4096)
    path = PurePosixPath(text)
    if not path.is_absolute() or text != path.as_posix() or ".." in path.parts or "." in path.parts:
        raise IsolatedRuntimeContractError(f"{name} must be a canonical absolute container path")
    forbidden = ("/", "/proc", "/sys", "/dev", "/var/run", "/run/docker.sock")
    if text in forbidden or any(text.startswith(item + "/") for item in forbidden[1:]):
        raise IsolatedRuntimeAuthorityError(f"{name} targets a forbidden runtime path")
    if secret and not text.startswith("/run/secrets/"):
        raise IsolatedRuntimeContractError("secret mounts must target /run/secrets")
    return text


def _relative_path(value: str, name: str, *, allow_root: bool = True) -> str:
    try:
        parts = FilesystemAdapter._relative_parts(value, allow_root=allow_root)
    except FilesystemContractError as exc:
        raise IsolatedRuntimeContractError(f"{name} is not a canonical relative path") from exc
    return "." if not parts else PurePosixPath(*parts).as_posix()


class RuntimeNetworkPolicy(str, Enum):
    NONE = "NONE"
    RESTRICTED = "RESTRICTED"
    PROJECT_POLICY = "PROJECT_POLICY"


class RuntimeStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    STOPPED = "STOPPED"
    OUTPUTS_COLLECTED = "OUTPUTS_COLLECTED"
    CLEANED = "CLEANED"


@dataclass(frozen=True)
class RuntimeResourceLimits:
    cpus: float | None = None
    memory_bytes: int | None = None
    gpu_count: int | None = None
    process_count: int | None = None
    storage_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.cpus is not None and (
            isinstance(self.cpus, bool) or not isinstance(self.cpus, (int, float)) or not 0 < float(self.cpus) <= 1024
        ):
            raise IsolatedRuntimeContractError("runtime CPU limit is invalid")
        for value, name in (
            (self.memory_bytes, "memory"),
            (self.process_count, "process"),
            (self.storage_bytes, "storage"),
        ):
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
                raise IsolatedRuntimeContractError(f"runtime {name} limit is invalid")
        if self.gpu_count is not None and (
            not isinstance(self.gpu_count, int) or isinstance(self.gpu_count, bool) or self.gpu_count < 0
        ):
            raise IsolatedRuntimeContractError("runtime GPU limit is invalid")

    def payload(self) -> dict[str, object]:
        return {
            "cpus": None if self.cpus is None else float(self.cpus),
            "gpu_count": self.gpu_count,
            "memory_bytes": self.memory_bytes,
            "process_count": self.process_count,
            "storage_bytes": self.storage_bytes,
        }


@dataclass(frozen=True)
class RuntimeMount:
    root_ref: FilesystemRootRef
    source_path: str
    target_path: str
    read_only: bool

    def __post_init__(self) -> None:
        if not isinstance(self.root_ref, FilesystemRootRef):
            raise IsolatedRuntimeContractError("runtime mount requires a FilesystemRootRef")
        object.__setattr__(self, "source_path", _relative_path(self.source_path, "mount source_path"))
        object.__setattr__(self, "target_path", _absolute_container_path(self.target_path, "mount target_path"))
        if not isinstance(self.read_only, bool):
            raise IsolatedRuntimeContractError("runtime mount access mode is malformed")

    def payload(self) -> dict[str, object]:
        return {
            "read_only": self.read_only,
            "root_ref": self.root_ref.value,
            "source_path": self.source_path,
            "target_path": self.target_path,
        }


@dataclass(frozen=True)
class RuntimeOutput:
    root_ref: FilesystemRootRef
    path: str
    media_type: str = "application/octet-stream"

    def __post_init__(self) -> None:
        if not isinstance(self.root_ref, FilesystemRootRef):
            raise IsolatedRuntimeContractError("runtime output requires a FilesystemRootRef")
        object.__setattr__(self, "path", _relative_path(self.path, "runtime output path", allow_root=False))
        _text(self.media_type, "runtime output media_type", 512)

    def payload(self) -> dict[str, object]:
        return {"media_type": self.media_type, "path": self.path, "root_ref": self.root_ref.value}


@dataclass(frozen=True)
class RuntimeSecretMount:
    secret_ref: str
    target_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.secret_ref, str) or _SECRET_REF.fullmatch(self.secret_ref) is None:
            raise IsolatedRuntimeContractError("runtime secret ref is malformed")
        object.__setattr__(
            self,
            "target_path",
            _absolute_container_path(self.target_path, "secret target_path", secret=True),
        )

    def payload(self) -> dict[str, object]:
        return {"secret_ref": self.secret_ref, "target_path": self.target_path}


@dataclass(frozen=True)
class IsolatedRuntimeSpec:
    project_ref: ProjectRef
    image_ref: str
    entrypoint: str
    args: tuple[str, ...] = ()
    working_directory: str = "/workspace"
    mounts: tuple[RuntimeMount, ...] = ()
    outputs: tuple[RuntimeOutput, ...] = ()
    secret_mounts: tuple[RuntimeSecretMount, ...] = ()
    network_policy: RuntimeNetworkPolicy = RuntimeNetworkPolicy.NONE
    resource_limits: RuntimeResourceLimits = field(default_factory=RuntimeResourceLimits)
    environment: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float = 60.0
    stdout_limit_bytes: int = 16 * 1024 * 1024
    stderr_limit_bytes: int = 16 * 1024 * 1024
    spec_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise IsolatedRuntimeContractError("runtime spec requires an exact ProjectRef")
        if not isinstance(self.image_ref, str) or _IMAGE_REF.fullmatch(self.image_ref) is None:
            raise IsolatedRuntimeContractError("runtime image must be an immutable sha256 ref")
        object.__setattr__(self, "entrypoint", _absolute_container_path(self.entrypoint, "entrypoint"))
        if not isinstance(self.args, tuple) or len(self.args) > 4096:
            raise IsolatedRuntimeContractError("runtime args are duplicated or unbounded")
        for item in self.args:
            _text(item, "runtime arg")
        object.__setattr__(
            self,
            "working_directory",
            _absolute_container_path(self.working_directory, "working_directory"),
        )
        if not isinstance(self.mounts, tuple) or len(self.mounts) > 256 or not all(
            isinstance(item, RuntimeMount) for item in self.mounts
        ):
            raise IsolatedRuntimeContractError("runtime mounts are malformed or unbounded")
        if not isinstance(self.outputs, tuple) or len(self.outputs) > 1024 or not all(
            isinstance(item, RuntimeOutput) for item in self.outputs
        ):
            raise IsolatedRuntimeContractError("runtime outputs are malformed or unbounded")
        if not isinstance(self.secret_mounts, tuple) or len(self.secret_mounts) > 256 or not all(
            isinstance(item, RuntimeSecretMount) for item in self.secret_mounts
        ):
            raise IsolatedRuntimeContractError("runtime secret mounts are malformed or unbounded")
        if len({item.target_path for item in self.mounts}) != len(self.mounts):
            raise IsolatedRuntimeContractError("runtime mount targets are duplicated")
        if len({item.target_path for item in self.secret_mounts}) != len(self.secret_mounts):
            raise IsolatedRuntimeContractError("runtime secret targets are duplicated")
        if len({(item.root_ref.value, item.path) for item in self.outputs}) != len(self.outputs):
            raise IsolatedRuntimeContractError("runtime outputs are duplicated")
        if any(item.root_ref.project_ref != self.project_ref for item in self.mounts + self.outputs):
            raise IsolatedRuntimeScopeError("runtime filesystem reference crossed Project scope")
        for output in self.outputs:
            eligible = tuple(item for item in self.mounts if item.root_ref == output.root_ref and not item.read_only)
            if not any(
                item.source_path == "."
                or PurePosixPath(output.path).is_relative_to(PurePosixPath(item.source_path))
                for item in eligible
            ):
                raise IsolatedRuntimeContractError("runtime output is not within an authorized writable mount")
        if not isinstance(self.network_policy, RuntimeNetworkPolicy):
            raise IsolatedRuntimeContractError("runtime network policy is malformed")
        if not isinstance(self.resource_limits, RuntimeResourceLimits):
            raise IsolatedRuntimeContractError("runtime resource limits are malformed")
        if not isinstance(self.environment, Mapping) or len(self.environment) > 256:
            raise IsolatedRuntimeContractError("runtime environment is malformed or unbounded")
        environment: dict[str, str] = {}
        for key, value in self.environment.items():
            if not isinstance(key, str) or _ENVIRONMENT_KEY.fullmatch(key) is None or _SENSITIVE_KEY.search(key):
                raise IsolatedRuntimeContractError("secret-looking runtime environment requires a secret mount")
            environment[key] = _text(value, "runtime environment value")
        object.__setattr__(self, "environment", MappingProxyType(dict(sorted(environment.items()))))
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or not 0 < float(self.timeout_seconds) <= 31_536_000:
            raise IsolatedRuntimeContractError("runtime timeout is invalid")
        for size_value, name in (
            (self.stdout_limit_bytes, "stdout limit"),
            (self.stderr_limit_bytes, "stderr limit"),
        ):
            if not isinstance(size_value, int) or isinstance(size_value, bool) or size_value < 0 or size_value > 2**63 - 1:
                raise IsolatedRuntimeContractError(f"runtime {name} is invalid")
        object.__setattr__(self, "spec_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "args": list(self.args),
            "entrypoint": self.entrypoint,
            "environment": dict(self.environment),
            "image_ref": self.image_ref,
            "mounts": [item.payload() for item in self.mounts],
            "network_policy": self.network_policy.value,
            "outputs": [item.payload() for item in self.outputs],
            "project_ref": self.project_ref.value,
            "resource_limits": self.resource_limits.payload(),
            "secret_mounts": [item.payload() for item in self.secret_mounts],
            "stderr_limit_bytes": self.stderr_limit_bytes,
            "stdout_limit_bytes": self.stdout_limit_bytes,
            "timeout_seconds": float(self.timeout_seconds),
            "working_directory": self.working_directory,
        }


@dataclass(frozen=True)
class RuntimeRef:
    project_ref: ProjectRef
    runtime_id: str
    generation: int

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_id, str) or _RUNTIME_ID.fullmatch(self.runtime_id) is None:
            raise IsolatedRuntimeContractError("runtime identity is malformed")
        if not isinstance(self.generation, int) or isinstance(self.generation, bool) or self.generation < 1:
            raise IsolatedRuntimeContractError("runtime generation is malformed")

    @property
    def value(self) -> str:
        return f"isolated-runtime://{self.project_ref.value}/{self.runtime_id}/{self.generation}"


@dataclass(frozen=True)
class RuntimeState:
    runtime_ref: RuntimeRef
    spec: IsolatedRuntimeSpec
    control_root_ref: FilesystemRootRef
    status: RuntimeStatus
    implementation_id: str
    image_id: str | None
    container_id: str | None
    container_name: str | None
    container_generation: int | None
    run_id: str
    node_attempt_id: str
    node_fence: int
    resource_allocation_ref: ResourceAllocationRef | None
    host_boot_id: str | None
    runtime_version: str | None
    requested_limits: Mapping[str, object]
    enforced_limits: Mapping[str, object]
    observed_limits: Mapping[str, object]
    exit_code: int | None
    failure: str | None
    outputs_collected: bool
    created_at: str
    started_at: str | None
    completed_at: str | None
    updated_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.runtime_ref.project_ref
        if self.spec.project_ref != project or self.control_root_ref.project_ref != project:
            raise IsolatedRuntimeScopeError("runtime state crossed Project scope")
        if self.resource_allocation_ref is not None and self.resource_allocation_ref.project_ref != project:
            raise IsolatedRuntimeScopeError("runtime ResourceAllocation crossed Project scope")
        if not isinstance(self.status, RuntimeStatus):
            raise IsolatedRuntimeContractError("runtime status is malformed")
        _text(self.implementation_id, "implementation_id", 1024)
        if self.image_id is not None and (not isinstance(self.image_id, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", self.image_id) is None):
            raise IsolatedRuntimeContractError("resolved runtime image identity is malformed")
        if self.container_id is not None and (not isinstance(self.container_id, str) or re.fullmatch(r"[0-9a-f]{64}", self.container_id) is None):
            raise IsolatedRuntimeContractError("container identity is malformed")
        if self.container_name is not None:
            _text(self.container_name, "container_name", 255)
        if self.container_generation is not None and (
            not isinstance(self.container_generation, int)
            or isinstance(self.container_generation, bool)
            or self.container_generation < 1
            or self.container_generation > self.runtime_ref.generation
        ):
            raise IsolatedRuntimeContractError("container generation is malformed")
        _text(self.run_id, "runtime run_id", 256)
        _text(self.node_attempt_id, "runtime node_attempt_id", 256)
        if not isinstance(self.node_fence, int) or isinstance(self.node_fence, bool) or self.node_fence < 1:
            raise IsolatedRuntimeContractError("runtime Node fence is malformed")
        if self.host_boot_id is not None and re.fullmatch(r"[0-9a-f-]{36}", self.host_boot_id) is None:
            raise IsolatedRuntimeContractError("runtime host boot identity is malformed")
        if self.runtime_version is not None:
            _text(self.runtime_version, "runtime version", 512)
        for value, name in (
            (self.requested_limits, "requested_limits"),
            (self.enforced_limits, "enforced_limits"),
            (self.observed_limits, "observed_limits"),
        ):
            if not isinstance(value, Mapping):
                raise IsolatedRuntimeContractError(f"runtime {name} is malformed")
            try:
                canonical = json.loads(_json(dict(value)))
            except json.JSONDecodeError as exc:
                raise IsolatedRuntimeContractError(f"runtime {name} is malformed") from exc
            if not isinstance(canonical, dict):
                raise IsolatedRuntimeContractError(f"runtime {name} is malformed")
            object.__setattr__(self, name, MappingProxyType(cast(dict[str, object], canonical)))
        if self.exit_code is not None and (not isinstance(self.exit_code, int) or isinstance(self.exit_code, bool)):
            raise IsolatedRuntimeContractError("runtime exit code is malformed")
        if self.failure is not None:
            _text(self.failure, "runtime failure", 4096)
        if not isinstance(self.outputs_collected, bool):
            raise IsolatedRuntimeContractError("runtime output collection state is malformed")
        _timestamp(self.created_at, "runtime created_at")
        if self.started_at is not None:
            _timestamp(self.started_at, "runtime started_at")
        if self.completed_at is not None:
            _timestamp(self.completed_at, "runtime completed_at")
        _timestamp(self.updated_at, "runtime updated_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.runtime_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "completed_at": self.completed_at,
            "container_id": self.container_id,
            "container_name": self.container_name,
            "container_generation": self.container_generation,
            "control_root_ref": self.control_root_ref.value,
            "created_at": self.created_at,
            "enforced_limits": dict(self.enforced_limits),
            "exit_code": self.exit_code,
            "failure": self.failure,
            "host_boot_id": self.host_boot_id,
            "image_id": self.image_id,
            "implementation_id": self.implementation_id,
            "node_attempt_id": self.node_attempt_id,
            "node_fence": self.node_fence,
            "observed_limits": dict(self.observed_limits),
            "outputs_collected": self.outputs_collected,
            "requested_limits": dict(self.requested_limits),
            "resource_allocation_ref": None if self.resource_allocation_ref is None else self.resource_allocation_ref.value,
            "run_id": self.run_id,
            "runtime_ref": self.runtime_ref.value,
            "runtime_version": self.runtime_version,
            "spec": self.spec.payload(),
            "spec_sha256": self.spec.spec_sha256,
            "started_at": self.started_at,
            "status": self.status.value,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class RuntimeReceipt:
    operation: str
    state: RuntimeState
    process_call_refs: tuple[ToolCallRef, ...]
    stdout_ref: ContentRef | None
    stderr_ref: ContentRef | None
    output_artifact_refs: tuple[ArtifactRef, ...]
    tool_call_ref: ToolCallRef
    artifact_ref: ArtifactRef
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.operation not in set(_OPERATIONS) - {"describe"}:
            raise IsolatedRuntimeContractError("runtime receipt operation is malformed")
        project = self.state.project_ref
        if self.tool_call_ref.project_ref != project or self.artifact_ref.project_ref != project:
            raise IsolatedRuntimeScopeError("runtime receipt evidence crossed Project scope")
        if any(item.project_ref != project for item in self.process_call_refs):
            raise IsolatedRuntimeScopeError("runtime process ToolCall crossed Project scope")
        if any(item.project_ref != project for item in self.output_artifact_refs):
            raise IsolatedRuntimeScopeError("runtime output Artifact crossed Project scope")
        _timestamp(self.completed_at, "runtime receipt completed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref.value,
            "completed_at": self.completed_at,
            "operation": self.operation,
            "output_artifact_refs": [item.value for item in self.output_artifact_refs],
            "process_call_refs": [item.value for item in self.process_call_refs],
            "state_ref": self.state.runtime_ref.value,
            "stderr_ref": _content(self.stderr_ref),
            "stdout_ref": _content(self.stdout_ref),
            "tool_call_ref": self.tool_call_ref.value,
        }


class RuntimeExecutionReceipt(RuntimeReceipt):
    """Terminal execution receipt with bounded log ContentRefs."""


class RuntimeCollectionReceipt(RuntimeReceipt):
    """Output collection receipt proving Artifact publication before cleanup."""


@dataclass(frozen=True)
class RuntimeDescriptor:
    implementation_id: str
    adapter_kind: str
    executable_digest: str
    runtime_version: str
    host_id: str
    cgroup_version: str
    security_features: tuple[str, ...]
    supported_network_policies: tuple[RuntimeNetworkPolicy, ...]
    enforced_limit_kinds: tuple[str, ...]
    unsupported_limit_kinds: tuple[str, ...]
    gpu_count: int
    process_call_refs: tuple[ToolCallRef, ...]
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for value, name in (
            (self.implementation_id, "implementation_id"),
            (self.adapter_kind, "adapter_kind"),
            (self.executable_digest, "executable_digest"),
            (self.runtime_version, "runtime_version"),
            (self.host_id, "host_id"),
            (self.cgroup_version, "cgroup_version"),
        ):
            _text(value, name, 1024)
        if not isinstance(self.gpu_count, int) or isinstance(self.gpu_count, bool) or self.gpu_count < 0:
            raise IsolatedRuntimeContractError("runtime GPU observation is malformed")
        if not self.process_call_refs:
            raise IsolatedRuntimeContractError("runtime descriptor requires process ToolCalls")
        _timestamp(self.observed_at, "runtime descriptor observed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "adapter_kind": self.adapter_kind,
            "cgroup_version": self.cgroup_version,
            "enforced_limit_kinds": list(self.enforced_limit_kinds),
            "executable_digest": self.executable_digest,
            "gpu_count": self.gpu_count,
            "host_id": self.host_id,
            "implementation_id": self.implementation_id,
            "observed_at": self.observed_at,
            "process_call_refs": [item.value for item in self.process_call_refs],
            "runtime_version": self.runtime_version,
            "security_features": list(self.security_features),
            "supported_network_policies": [item.value for item in self.supported_network_policies],
            "unsupported_limit_kinds": list(self.unsupported_limit_kinds),
        }


@dataclass(frozen=True)
class RuntimeReconciliation:
    recovered: tuple[RuntimeRef, ...]
    cleaned: tuple[RuntimeRef, ...]
    unknown_container_ids: tuple[str, ...]


@runtime_checkable
class IsolatedRuntimeAdapter(Protocol):
    """Provider-neutral contract implemented by isolated-runtime backends."""

    def describe_runtime(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        control_root_ref: FilesystemRootRef,
        idempotency_key: str,
    ) -> RuntimeDescriptor: ...

    def create(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        spec: IsolatedRuntimeSpec,
        *,
        control_root_ref: FilesystemRootRef,
        resource_allocation_ref: ResourceAllocationRef | None = None,
        idempotency_key: str,
    ) -> RuntimeReceipt: ...

    def start(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> RuntimeReceipt: ...

    def execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> RuntimeExecutionReceipt: ...

    def cancel(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        idempotency_key: str,
    ) -> RuntimeReceipt: ...

    def stop(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        idempotency_key: str,
    ) -> RuntimeReceipt: ...

    def inspect(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        idempotency_key: str,
    ) -> RuntimeReceipt: ...

    def collect_outputs(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> RuntimeCollectionReceipt: ...

    def cleanup(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        idempotency_key: str,
    ) -> RuntimeReceipt: ...

    def reconcile_orphans(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        control_root_ref: FilesystemRootRef,
        idempotency_key: str,
    ) -> RuntimeReconciliation: ...


@dataclass(frozen=True)
class _StartedOperation:
    call: ToolCall
    request_ref: ContentRef
    first_claim: bool


class DockerIsolatedRuntimeAdapter:
    """Real OCI-container adapter implemented through the managed Docker CLI."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        runtime_root: str | Path,
        docker_executable: str | Path = "/usr/bin/docker",
    ) -> None:
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("object_store must implement ObjectStorageBackend")
        executable = Path(docker_executable)
        if not executable.is_absolute():
            raise IsolatedRuntimeContractError("Docker executable must be an absolute path")
        try:
            executable_state = executable.stat()
        except OSError as exc:
            raise IsolatedRuntimeNotFoundError("configured Docker executable is unavailable") from exc
        if not stat.S_ISREG(executable_state.st_mode) or executable_state.st_mode & 0o111 == 0:
            raise IsolatedRuntimeAuthorityError("configured Docker executable is not executable")
        root = Path(runtime_root)
        if not root.is_absolute():
            raise IsolatedRuntimeContractError("runtime control root must be absolute")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            root_state = root.lstat()
        except OSError as exc:
            raise IsolatedRuntimeIntegrityError("runtime control root is unavailable") from exc
        if not stat.S_ISDIR(root_state.st_mode) or stat.S_ISLNK(root_state.st_mode):
            raise IsolatedRuntimeAuthorityError("runtime control root must be a real directory")
        os.chmod(root, 0o700)
        self.database_path = Path(database_path).resolve()
        self.object_store = object_store
        self.runtime_root = root.resolve(strict=True)
        self.docker_executable = str(executable.resolve(strict=True))
        self.projects = ProjectStore(self.database_path)
        self.graphs = GraphService(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.runs = RunService(self.database_path)
        self.scheduler = SchedulerService(self.database_path)
        self.calls = CallLedgerService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.capabilities = CapabilityRegistry(self.database_path)
        self.implementations = CapabilityImplementationRegistry(self.database_path)
        self.filesystem = FilesystemAdapter(self.database_path, object_store)
        self.process = ManagedProcessAdapter(
            self.database_path,
            object_store,
            inherited_environment={"LANG": "C.UTF-8"},
        )
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
                CREATE TABLE IF NOT EXISTS isolated_runtime_states (
                    project_id TEXT NOT NULL,
                    runtime_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,runtime_id,generation)
                );
                CREATE TABLE IF NOT EXISTS isolated_runtime_heads (
                    project_id TEXT NOT NULL,
                    runtime_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,runtime_id)
                );
                CREATE TABLE IF NOT EXISTS isolated_runtime_operation_claims (
                    project_id TEXT NOT NULL,
                    node_attempt_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    request_size INTEGER NOT NULL,
                    request_media_type TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    claim_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,node_attempt_id,operation,idempotency_key),
                    UNIQUE (project_id,call_id),
                    FOREIGN KEY (project_id,call_id) REFERENCES calls(project_id,call_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS isolated_runtime_operation_results (
                    project_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,call_id),
                    FOREIGN KEY (project_id,call_id) REFERENCES calls(project_id,call_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS isolated_runtime_states_no_update BEFORE UPDATE ON isolated_runtime_states
                  BEGIN SELECT RAISE(ABORT,'Isolated runtime states are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS isolated_runtime_states_no_delete BEFORE DELETE ON isolated_runtime_states
                  BEGIN SELECT RAISE(ABORT,'Isolated runtime states cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS isolated_runtime_heads_no_delete BEFORE DELETE ON isolated_runtime_heads
                  BEGIN SELECT RAISE(ABORT,'Isolated runtime heads cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS isolated_runtime_heads_monotonic BEFORE UPDATE ON isolated_runtime_heads
                  WHEN NEW.project_id != OLD.project_id OR NEW.runtime_id != OLD.runtime_id OR NEW.generation != OLD.generation + 1
                  BEGIN SELECT RAISE(ABORT,'Isolated runtime generation must advance exactly once'); END;
                CREATE TRIGGER IF NOT EXISTS isolated_runtime_claims_no_update BEFORE UPDATE ON isolated_runtime_operation_claims
                  BEGIN SELECT RAISE(ABORT,'Isolated runtime claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS isolated_runtime_claims_no_delete BEFORE DELETE ON isolated_runtime_operation_claims
                  BEGIN SELECT RAISE(ABORT,'Isolated runtime claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS isolated_runtime_results_no_update BEFORE UPDATE ON isolated_runtime_operation_results
                  BEGIN SELECT RAISE(ABORT,'Isolated runtime results are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS isolated_runtime_results_no_delete BEFORE DELETE ON isolated_runtime_operation_results
                  BEGIN SELECT RAISE(ABORT,'Isolated runtime results cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def capability_ref(operation: str) -> CapabilityRef:
        if operation not in _OPERATIONS:
            raise IsolatedRuntimeContractError("runtime operation is unsupported")
        return CapabilityRef(f"runtime.{operation}", "1.0.0")

    @staticmethod
    def _implementation_ref(project_ref: ProjectRef, operation: str) -> CapabilityImplementationRef:
        identity = hashlib.sha256(f"{project_ref.value}\x00runtime.{operation}\x001.0.0".encode()).hexdigest()[:32]
        return CapabilityImplementationRef(project_ref, f"cimpl_{identity}")

    def register_capabilities(self, access: ProjectAccess) -> Mapping[CapabilityRef, CapabilityImplementation]:
        self._authorize(access, access.project_ref)
        registered: dict[CapabilityRef, CapabilityImplementation] = {}
        for operation in _OPERATIONS:
            capability_ref = self.capability_ref(operation)
            side_effect = "PROJECT_WRITE" if operation in _MUTATING else "READ_ONLY"
            capability = self.capabilities.register(
                Capability(
                    capability_ref,
                    f"Replaceable isolated runtime {operation}",
                    input_contract={"request": "schema://biella/isolated-runtime-request/1"},
                    output_contract={"receipt": "schema://biella/isolated-runtime-receipt/1"},
                    side_effects=(f"runtime.{operation}",) if operation in _MUTATING else (),
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
                        "adapter://biella/isolated-runtime",
                        "runtime://oci/container",
                        tool_ref=f"tool://biella/isolated-runtime/{operation}",
                        features=("exact-image", "owned-runtime", "durable-output-before-cleanup"),
                        input_features=("filesystem-root-ref", "secret-ref", "resource-allocation-ref"),
                        output_features=("artifact", "content-ref", "tool-call", "runtime-receipt"),
                        side_effect_authority=side_effect,
                        resource_kinds=("runtime.host",),
                        metadata={"adapter_contract": "isolated-runtime-v1"},
                    ),
                    idempotency_key=f"runtime-{operation}-implementation",
                )
            registered[capability.capability_ref] = implementation
        return MappingProxyType(registered)

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectIntegrityError as exc:
            raise IsolatedRuntimeIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise IsolatedRuntimeScopeError("runtime Project scope mismatch") from exc

    def _require_operation_authority(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        operation: str,
    ) -> None:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise IsolatedRuntimeAuthorityError("NodeExecutionAttempt is required")
        if attempt.node_ref.project_ref != access.project_ref:
            raise IsolatedRuntimeScopeError("runtime Node attempt crossed Project scope")
        graph = self.graphs.get_graph(access, attempt.node_ref.graph_ref)
        node = next((item for item in graph.nodes if item.node_ref == attempt.node_ref), None)
        if node is None or self.capability_ref(operation) not in node.required_capabilities:
            raise IsolatedRuntimeAuthorityError("runtime capability is not authorized by exact Node")
        task = self.tasks.get_task(access, attempt.task_ref)
        if task.canonical_digest != attempt.task_digest:
            raise IsolatedRuntimeIntegrityError("runtime Node attempt Task digest changed")
        levels = {"READ_ONLY": 0, "CANDIDATE_WRITE": 1, "PROJECT_WRITE": 2, "EXTERNAL_SIDE_EFFECT": 3}
        required = 1 if operation in _MUTATING else 0
        if levels[task.side_effect_authority] < required or levels[node.side_effect_requirement] < required:
            raise IsolatedRuntimeAuthorityError("runtime operation exceeds Task or Node side-effect authority")

    @staticmethod
    def _key(value: str) -> str:
        if not isinstance(value, str) or _KEY.fullmatch(value) is None:
            raise IsolatedRuntimeContractError("runtime idempotency key is malformed")
        return value

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
            raise IsolatedRuntimeAuthorityError("exact Run execution authority is unavailable")
        return result

    def _database_now(self) -> str:
        connection = self._connect()
        try:
            value = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')").fetchone()[0]
            if not isinstance(value, str):
                raise IsolatedRuntimeIntegrityError("durable database time is unavailable")
            return value
        finally:
            connection.close()

    def _validate_control_root(self, access: ProjectAccess, root_ref: FilesystemRootRef) -> FilesystemRoot:
        try:
            root = self.filesystem._require_root(access, root_ref, writable=True)
        except FilesystemAuthorityError as exc:
            raise IsolatedRuntimeAuthorityError("runtime control FilesystemRoot is not writable") from exc
        except FilesystemError as exc:
            raise IsolatedRuntimeIntegrityError("runtime control FilesystemRoot failed verification") from exc
        return root

    @staticmethod
    def _forbidden_host_path(path: Path) -> bool:
        forbidden = (
            Path("/"),
            Path("/proc"),
            Path("/sys"),
            Path("/dev"),
            Path("/etc"),
            Path("/var/run"),
            Path("/run/docker.sock"),
            Path("/root/.ssh"),
            Path("/root/.aws"),
            Path("/root/.docker"),
            Path("/root/.config/gcloud"),
        )
        return path == forbidden[0] or any(
            path == item or path.is_relative_to(item)
            for item in forbidden[1:]
        )

    def _mount_source(
        self,
        access: ProjectAccess,
        mount: RuntimeMount,
    ) -> tuple[FilesystemRoot, Path]:
        try:
            root = self.filesystem._require_root(access, mount.root_ref, writable=not mount.read_only)
            parts = FilesystemAdapter._relative_parts(mount.source_path)
            parent, leaf = self.filesystem._parent_descriptor(root, parts)
            try:
                state = self.filesystem._safe_state(parent, leaf, allow_directory=True)
                if not stat.S_ISDIR(state.st_mode):
                    raise IsolatedRuntimeContractError("runtime mounts must source authorized directories")
            finally:
                os.close(parent)
        except FilesystemAuthorityError as exc:
            raise IsolatedRuntimeAuthorityError("runtime mount is not authorized") from exc
        except FilesystemNotFoundError as exc:
            raise IsolatedRuntimeNotFoundError("runtime mount source is unavailable") from exc
        except FilesystemError as exc:
            raise IsolatedRuntimeIntegrityError("runtime mount source failed verification") from exc
        if root.canonical_path is None:
            raise IsolatedRuntimeIntegrityError("runtime mount root lacks canonical path")
        absolute = Path(root.canonical_path).joinpath(*parts).resolve(strict=True)
        if self._forbidden_host_path(absolute) or "," in os.fspath(absolute):
            raise IsolatedRuntimeAuthorityError("runtime mount exposes a forbidden host path")
        return root, absolute

    def _validate_spec_compatibility(self, access: ProjectAccess, spec: IsolatedRuntimeSpec) -> tuple[Path, ...]:
        self._authorize(access, spec.project_ref)
        if spec.network_policy is not RuntimeNetworkPolicy.NONE:
            raise IsolatedRuntimeContractError("Docker adapter cannot enforce requested restricted Project egress policy")
        if spec.resource_limits.storage_bytes is not None:
            raise IsolatedRuntimeContractError("Docker overlayfs storage quota is unsupported by this adapter")
        if spec.resource_limits.gpu_count not in {None, 0}:
            raise IsolatedRuntimeContractError("GPU visibility is unavailable on this runtime host")
        if spec.resource_limits.memory_bytes is not None and spec.resource_limits.memory_bytes < 6 * 1024 * 1024:
            raise IsolatedRuntimeContractError("Docker memory enforcement requires at least 6 MiB")
        return tuple(self._mount_source(access, item)[1] for item in spec.mounts)

    def _docker(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        control_root_ref: FilesystemRootRef,
        argv: Sequence[str],
        idempotency_material: str,
        timeout_seconds: float = 120.0,
        stdout_limit_bytes: int = 64 * 1024 * 1024,
        stderr_limit_bytes: int = 64 * 1024 * 1024,
        redaction_refs: Mapping[str, str] = MappingProxyType({}),
        redaction_values: Mapping[str, str] = MappingProxyType({}),
        require_success: bool = True,
    ) -> ProcessResult:
        digest = hashlib.sha256(idempotency_material.encode()).hexdigest()[:40]
        request = ProcessExecutionRequest(
            access.project_ref,
            control_root_ref,
            ".",
            self.docker_executable,
            tuple(argv),
            inherited_environment=("LANG",),
            environment_overrides={"LC_ALL": "C.UTF-8"},
            secret_environment_refs=redaction_refs,
            timeout_seconds=timeout_seconds,
            termination_grace_seconds=1.0,
            stdout_limit_bytes=stdout_limit_bytes,
            stderr_limit_bytes=stderr_limit_bytes,
            network_policy=NetworkPolicy.INHERIT,
        )
        result = self.process.execute(
            access,
            attempt,
            request,
            idempotency_key=f"runtime-docker-{digest}",
            secret_values=redaction_values,
        )
        if require_success and result.status is not ProcessStatus.SUCCEEDED:
            reason = result.stderr_preview.strip() or (result.failure.value if result.failure is not None else "unknown")
            raise IsolatedRuntimeConflictError(f"Docker command failed: {reason}")
        return result

    def _decode(self, result: ProcessResult, name: str) -> str:
        try:
            return self.object_store.read(result.stdout_ref).decode("utf-8")
        except (ObjectStorageError, UnicodeDecodeError) as exc:
            raise IsolatedRuntimeIntegrityError(f"Docker {name} output failed verification") from exc

    @staticmethod
    def _json_object(text: str, name: str) -> dict[str, object]:
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise IsolatedRuntimeIntegrityError(f"Docker {name} output is malformed") from exc
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
            return cast(dict[str, object], value[0])
        if not isinstance(value, dict):
            raise IsolatedRuntimeIntegrityError(f"Docker {name} output is malformed")
        return cast(dict[str, object], value)

    def _redaction_environment(
        self,
        spec: IsolatedRuntimeSpec,
        secret_values: Mapping[str, str],
    ) -> tuple[Mapping[str, str], Mapping[str, str]]:
        expected = {item.secret_ref for item in spec.secret_mounts}
        if set(secret_values) != expected:
            raise IsolatedRuntimeAuthorityError("runtime secret values must match exact secret refs")
        refs: dict[str, str] = {}
        values: dict[str, str] = {}
        for index, secret_ref in enumerate(sorted(expected)):
            key = f"BIELLA_RUNTIME_REDACT_{index}"
            refs[key] = secret_ref
            values[key] = _text(secret_values[secret_ref], "runtime secret value")
        return MappingProxyType(refs), MappingProxyType(values)

    def _start_operation(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        operation: str,
        idempotency_key: str,
        payload: Mapping[str, object],
    ) -> _StartedOperation:
        self._key(idempotency_key)
        self._require_operation_authority(access, attempt, operation)
        request_ref = self.object_store.put(_json(payload).encode(), media_type=_REQUEST_MEDIA_TYPE)
        implementation_ref = self._implementation_ref(access.project_ref, operation)
        try:
            implementation = self.implementations.get(access, implementation_ref)
        except RoutingNotFoundError as exc:
            raise IsolatedRuntimeAuthorityError("runtime implementation is not registered") from exc
        digest = _digest({"attempt": attempt.record_sha256, "operation": operation, "key": idempotency_key})
        try:
            call = self.calls.start_tool_call(
                access,
                attempt,
                idempotency_key=f"runtime-start-{digest[:42]}",
                capability_ref=self.capability_ref(operation),
                purpose="INITIAL",
                retry_of=None,
                parent_model_call_ref=None,
                tool_id=cast(str, implementation.tool_ref),
                implementation_id=implementation.implementation_ref.value,
                runtime_id=implementation.runtime_ref,
                input_refs=(request_ref,),
                provider_trace_id=None,
            )
        except CallAuthorityError as exc:
            raise IsolatedRuntimeAuthorityError("runtime ToolCall authority was rejected") from exc
        except CallConflictError as exc:
            raise IsolatedRuntimeConflictError("runtime ToolCall idempotency conflicts") from exc
        claim = {
            "call_ref": call.call_ref.value,
            "idempotency_key": idempotency_key,
            "node_attempt_id": attempt.attempt_id,
            "operation": operation,
            "project_ref": access.project_ref.value,
            "request_ref": request_ref.value,
        }
        claim_sha = _digest(claim)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM isolated_runtime_operation_claims WHERE project_id=? AND node_attempt_id=? AND operation=? AND idempotency_key=?",
                (access.project_ref.value, attempt.attempt_id, operation, idempotency_key),
            ).fetchone()
            if prior is not None:
                if (
                    prior["request_digest"] != request_ref.digest
                    or prior["request_size"] != request_ref.size_bytes
                    or prior["request_media_type"] != request_ref.media_type
                    or prior["call_id"] != call.call_ref.call_id
                    or not hmac.compare_digest(cast(str, prior["claim_sha256"]), claim_sha)
                ):
                    raise IsolatedRuntimeConflictError("runtime operation idempotency identity changed")
                connection.commit()
                return _StartedOperation(call, request_ref, False)
            if call.status != "RUNNING":
                raise IsolatedRuntimeIntegrityError("terminal runtime ToolCall lost its immutable claim")
            connection.execute(
                "INSERT INTO isolated_runtime_operation_claims VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    access.project_ref.value,
                    attempt.attempt_id,
                    operation,
                    idempotency_key,
                    request_ref.digest,
                    request_ref.size_bytes,
                    request_ref.media_type,
                    call.call_ref.call_id,
                    claim_sha,
                ),
            )
            connection.commit()
            return _StartedOperation(call, request_ref, True)
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise IsolatedRuntimeConflictError("runtime operation claim conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _fail_operation(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        started: _StartedOperation,
        *,
        operation: str,
        idempotency_key: str,
    ) -> None:
        current = self.calls.get_tool_call(access, started.call.call_ref)
        if current.status != "RUNNING":
            return
        digest = _digest({"attempt": attempt.record_sha256, "operation": operation, "key": idempotency_key})
        try:
            self.calls.finish_tool_call(
                access,
                attempt,
                current.call_ref,
                idempotency_key=f"runtime-finish-{digest[:41]}",
                status="FAILED",
                output_refs=(),
                usage=None,
                cost=None,
                failure_category="ISOLATED_RUNTIME_FAILURE",
                failure_reason="isolated runtime adapter failed closed",
                failure_evidence_refs=(),
            )
        except (CallAuthorityError, CallConflictError):
            return

    @staticmethod
    def _root_ref(value: object, project_ref: ProjectRef) -> FilesystemRootRef:
        if not isinstance(value, str):
            raise IsolatedRuntimeIntegrityError("persisted FilesystemRootRef is malformed")
        prefix = f"filesystem-root://{project_ref.value}/"
        if not value.startswith(prefix):
            raise IsolatedRuntimeScopeError("persisted FilesystemRootRef crossed Project scope")
        try:
            return FilesystemRootRef(project_ref, value.removeprefix(prefix))
        except (TypeError, ValueError, FilesystemError) as exc:
            raise IsolatedRuntimeIntegrityError("persisted FilesystemRootRef is malformed") from exc

    @staticmethod
    def _allocation_ref(value: object, project_ref: ProjectRef) -> ResourceAllocationRef | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise IsolatedRuntimeIntegrityError("persisted ResourceAllocationRef is malformed")
        prefix = f"resource-allocation://{project_ref.value}/"
        if not value.startswith(prefix):
            raise IsolatedRuntimeScopeError("persisted ResourceAllocationRef crossed Project scope")
        try:
            return ResourceAllocationRef(project_ref, value.removeprefix(prefix))
        except (TypeError, ValueError, SchedulerError) as exc:
            raise IsolatedRuntimeIntegrityError("persisted ResourceAllocationRef is malformed") from exc

    @staticmethod
    def _runtime_ref(value: object, project_ref: ProjectRef) -> RuntimeRef:
        if not isinstance(value, str):
            raise IsolatedRuntimeIntegrityError("persisted RuntimeRef is malformed")
        prefix = f"isolated-runtime://{project_ref.value}/"
        if not value.startswith(prefix):
            raise IsolatedRuntimeScopeError("persisted RuntimeRef crossed Project scope")
        parts = value.removeprefix(prefix).split("/")
        if len(parts) != 2:
            raise IsolatedRuntimeIntegrityError("persisted RuntimeRef is malformed")
        try:
            return RuntimeRef(project_ref, parts[0], int(parts[1]))
        except (TypeError, ValueError, IsolatedRuntimeError) as exc:
            raise IsolatedRuntimeIntegrityError("persisted RuntimeRef is malformed") from exc

    @staticmethod
    def _content_ref(value: object) -> ContentRef | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise IsolatedRuntimeIntegrityError("persisted ContentRef is malformed")
        try:
            return ContentRef(
                cast(str, value["algorithm"]),
                cast(str, value["digest"]),
                cast(int, value["size_bytes"]),
                cast(str, value["media_type"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IsolatedRuntimeIntegrityError("persisted ContentRef is malformed") from exc

    @staticmethod
    def _tool_call_ref(value: object, project_ref: ProjectRef) -> ToolCallRef:
        if not isinstance(value, str):
            raise IsolatedRuntimeIntegrityError("persisted ToolCallRef is malformed")
        prefix = f"tool-call://{project_ref.value}/"
        if not value.startswith(prefix):
            raise IsolatedRuntimeScopeError("persisted ToolCallRef crossed Project scope")
        try:
            return ToolCallRef(project_ref, value.removeprefix(prefix))
        except (TypeError, ValueError) as exc:
            raise IsolatedRuntimeIntegrityError("persisted ToolCallRef is malformed") from exc

    @staticmethod
    def _artifact_ref(value: object, project_ref: ProjectRef) -> ArtifactRef:
        if not isinstance(value, str):
            raise IsolatedRuntimeIntegrityError("persisted ArtifactRef is malformed")
        prefix = f"artifact://{project_ref.value}/"
        if not value.startswith(prefix):
            raise IsolatedRuntimeScopeError("persisted ArtifactRef crossed Project scope")
        parts = value.removeprefix(prefix).split("/")
        if len(parts) != 2:
            raise IsolatedRuntimeIntegrityError("persisted ArtifactRef is malformed")
        try:
            return ArtifactRef(project_ref, parts[0], int(parts[1]))
        except (TypeError, ValueError) as exc:
            raise IsolatedRuntimeIntegrityError("persisted ArtifactRef is malformed") from exc

    def _spec_from_payload(self, payload: object, project_ref: ProjectRef) -> IsolatedRuntimeSpec:
        if not isinstance(payload, dict) or payload.get("project_ref") != project_ref.value:
            raise IsolatedRuntimeIntegrityError("persisted IsolatedRuntimeSpec is malformed")
        try:
            mounts = tuple(
                RuntimeMount(
                    self._root_ref(cast(dict[str, object], item)["root_ref"], project_ref),
                    cast(str, cast(dict[str, object], item)["source_path"]),
                    cast(str, cast(dict[str, object], item)["target_path"]),
                    cast(bool, cast(dict[str, object], item)["read_only"]),
                )
                for item in cast(list[object], payload["mounts"])
            )
            outputs = tuple(
                RuntimeOutput(
                    self._root_ref(cast(dict[str, object], item)["root_ref"], project_ref),
                    cast(str, cast(dict[str, object], item)["path"]),
                    cast(str, cast(dict[str, object], item)["media_type"]),
                )
                for item in cast(list[object], payload["outputs"])
            )
            secrets = tuple(
                RuntimeSecretMount(
                    cast(str, cast(dict[str, object], item)["secret_ref"]),
                    cast(str, cast(dict[str, object], item)["target_path"]),
                )
                for item in cast(list[object], payload["secret_mounts"])
            )
            raw_limits = cast(dict[str, object], payload["resource_limits"])
            return IsolatedRuntimeSpec(
                project_ref,
                cast(str, payload["image_ref"]),
                cast(str, payload["entrypoint"]),
                tuple(cast(list[str], payload["args"])),
                cast(str, payload["working_directory"]),
                mounts,
                outputs,
                secrets,
                RuntimeNetworkPolicy(cast(str, payload["network_policy"])),
                RuntimeResourceLimits(
                    cast(float | None, raw_limits["cpus"]),
                    cast(int | None, raw_limits["memory_bytes"]),
                    cast(int | None, raw_limits["gpu_count"]),
                    cast(int | None, raw_limits["process_count"]),
                    cast(int | None, raw_limits["storage_bytes"]),
                ),
                cast(dict[str, str], payload["environment"]),
                cast(float, payload["timeout_seconds"]),
                cast(int, payload["stdout_limit_bytes"]),
                cast(int, payload["stderr_limit_bytes"]),
            )
        except (KeyError, TypeError, ValueError, IsolatedRuntimeError) as exc:
            raise IsolatedRuntimeIntegrityError("persisted IsolatedRuntimeSpec is malformed") from exc

    def _state_from_payload(self, payload: object, project_ref: ProjectRef) -> RuntimeState:
        if not isinstance(payload, dict):
            raise IsolatedRuntimeIntegrityError("persisted RuntimeState is malformed")
        try:
            runtime_ref = self._runtime_ref(payload["runtime_ref"], project_ref)
            spec = self._spec_from_payload(payload["spec"], project_ref)
            if payload.get("spec_sha256") != spec.spec_sha256:
                raise IsolatedRuntimeIntegrityError("persisted runtime spec digest changed")
            return RuntimeState(
                runtime_ref,
                spec,
                self._root_ref(payload["control_root_ref"], project_ref),
                RuntimeStatus(cast(str, payload["status"])),
                cast(str, payload["implementation_id"]),
                cast(str | None, payload["image_id"]),
                cast(str | None, payload["container_id"]),
                cast(str | None, payload["container_name"]),
                cast(int | None, payload["container_generation"]),
                cast(str, payload["run_id"]),
                cast(str, payload["node_attempt_id"]),
                cast(int, payload["node_fence"]),
                self._allocation_ref(payload["resource_allocation_ref"], project_ref),
                cast(str | None, payload["host_boot_id"]),
                cast(str | None, payload["runtime_version"]),
                cast(dict[str, object], payload["requested_limits"]),
                cast(dict[str, object], payload["enforced_limits"]),
                cast(dict[str, object], payload["observed_limits"]),
                cast(int | None, payload["exit_code"]),
                cast(str | None, payload["failure"]),
                cast(bool, payload["outputs_collected"]),
                cast(str, payload["created_at"]),
                cast(str | None, payload["started_at"]),
                cast(str | None, payload["completed_at"]),
                cast(str, payload["updated_at"]),
            )
        except (KeyError, TypeError, ValueError, IsolatedRuntimeError) as exc:
            if isinstance(exc, IsolatedRuntimeIntegrityError):
                raise
            raise IsolatedRuntimeIntegrityError("persisted RuntimeState is malformed") from exc

    def _persist_state(self, state: RuntimeState, *, initial: bool) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if initial:
                connection.execute(
                    "INSERT INTO isolated_runtime_states VALUES (?,?,?,?,?)",
                    (
                        state.project_ref.value,
                        state.runtime_ref.runtime_id,
                        state.runtime_ref.generation,
                        _json(state.payload()),
                        state.record_sha256,
                    ),
                )
                connection.execute(
                    "INSERT INTO isolated_runtime_heads VALUES (?,?,?,?)",
                    (
                        state.project_ref.value,
                        state.runtime_ref.runtime_id,
                        state.runtime_ref.generation,
                        state.record_sha256,
                    ),
                )
            else:
                prior = connection.execute(
                    "SELECT * FROM isolated_runtime_heads WHERE project_id=? AND runtime_id=?",
                    (state.project_ref.value, state.runtime_ref.runtime_id),
                ).fetchone()
                if prior is None or prior["generation"] != state.runtime_ref.generation - 1:
                    raise IsolatedRuntimeConflictError("runtime generation changed concurrently")
                connection.execute(
                    "INSERT INTO isolated_runtime_states VALUES (?,?,?,?,?)",
                    (
                        state.project_ref.value,
                        state.runtime_ref.runtime_id,
                        state.runtime_ref.generation,
                        _json(state.payload()),
                        state.record_sha256,
                    ),
                )
                changed = connection.execute(
                    "UPDATE isolated_runtime_heads SET generation=?,record_sha256=? WHERE project_id=? AND runtime_id=? AND generation=? AND record_sha256=?",
                    (
                        state.runtime_ref.generation,
                        state.record_sha256,
                        state.project_ref.value,
                        state.runtime_ref.runtime_id,
                        prior["generation"],
                        prior["record_sha256"],
                    ),
                )
                if changed.rowcount != 1:
                    raise IsolatedRuntimeConflictError("runtime head changed concurrently")
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise IsolatedRuntimeConflictError("runtime state evidence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _get_state_generation(self, access: ProjectAccess, runtime_id: str, generation: int) -> RuntimeState:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM isolated_runtime_states WHERE project_id=? AND runtime_id=? AND generation=?",
                (access.project_ref.value, runtime_id, generation),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise IsolatedRuntimeIntegrityError("runtime state history is missing")
        try:
            state = self._state_from_payload(json.loads(cast(str, row["state_json"])), access.project_ref)
        except json.JSONDecodeError as exc:
            raise IsolatedRuntimeIntegrityError("runtime state JSON is malformed") from exc
        if not hmac.compare_digest(cast(str, row["record_sha256"]), state.record_sha256):
            raise IsolatedRuntimeIntegrityError("runtime state evidence changed")
        return state

    def get_state(
        self,
        access: ProjectAccess,
        runtime_ref: RuntimeRef,
        *,
        require_current: bool = True,
    ) -> RuntimeState:
        if not isinstance(runtime_ref, RuntimeRef):
            raise IsolatedRuntimeContractError("exact RuntimeRef is required")
        self._authorize(access, runtime_ref.project_ref)
        state = self._get_state_generation(access, runtime_ref.runtime_id, runtime_ref.generation)
        if state.runtime_ref != runtime_ref:
            raise IsolatedRuntimeIntegrityError("RuntimeRef evidence changed")
        if require_current:
            connection = self._connect()
            try:
                head = connection.execute(
                    "SELECT * FROM isolated_runtime_heads WHERE project_id=? AND runtime_id=?",
                    (access.project_ref.value, runtime_ref.runtime_id),
                ).fetchone()
            finally:
                connection.close()
            if head is None:
                raise IsolatedRuntimeIntegrityError("runtime head history is missing")
            if head["generation"] != runtime_ref.generation or not hmac.compare_digest(
                cast(str, head["record_sha256"]), state.record_sha256
            ):
                raise IsolatedRuntimeConflictError("RuntimeRef generation is stale")
        return state

    @staticmethod
    def _receipt_basis(
        operation: str,
        state: RuntimeState,
        process_call_refs: Sequence[ToolCallRef],
        stdout_ref: ContentRef | None,
        stderr_ref: ContentRef | None,
        output_artifact_refs: Sequence[ArtifactRef],
    ) -> dict[str, object]:
        return {
            "operation": operation,
            "output_artifact_refs": [item.value for item in output_artifact_refs],
            "process_call_refs": [item.value for item in process_call_refs],
            "state_ref": state.runtime_ref.value,
            "stderr_ref": _content(stderr_ref),
            "stdout_ref": _content(stdout_ref),
        }

    def _complete_operation(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        started: _StartedOperation,
        *,
        operation: str,
        idempotency_key: str,
        state: RuntimeState,
        process_call_refs: Sequence[ToolCallRef] = (),
        stdout_ref: ContentRef | None = None,
        stderr_ref: ContentRef | None = None,
        output_artifact_refs: Sequence[ArtifactRef] = (),
        source_refs: Sequence[ContentRef] = (),
    ) -> RuntimeReceipt:
        basis = self._receipt_basis(
            operation,
            state,
            process_call_refs,
            stdout_ref,
            stderr_ref,
            output_artifact_refs,
        )
        manifest_ref = self.object_store.put(_json(basis).encode(), media_type=_RECEIPT_MEDIA_TYPE)
        unique_sources = tuple(
            sorted(
                {item.value: item for item in (started.request_ref, *tuple(source_refs))}.values(),
                key=lambda item: item.value,
            )
        )
        artifact = self.artifacts.publish_from_run(
            access,
            producer_attempt=self._run_attempt(access, attempt),
            expected_task_ref=attempt.task_ref,
            expected_task_digest=attempt.task_digest,
            role=f"runtime.{operation}.receipt",
            content_ref=manifest_ref,
            source_refs=(),
            source_artifact_refs=tuple(output_artifact_refs),
            source_content_refs=unique_sources,
            derivation_type=f"runtime.{operation}",
            metadata={
                "media_type": manifest_ref.media_type,
                "schema_ref": "schema://biella/isolated-runtime-receipt/1",
                "schema_version": "1.0.0",
            },
        )
        digest = _digest({"attempt": attempt.record_sha256, "operation": operation, "key": idempotency_key})
        try:
            call = self.calls.finish_tool_call(
                access,
                attempt,
                started.call.call_ref,
                idempotency_key=f"runtime-finish-{digest[:41]}",
                status="SUCCEEDED",
                output_refs=(manifest_ref, artifact.artifact_ref, *tuple(output_artifact_refs)),
                usage=None,
                cost=None,
                failure_category=None,
                failure_reason=None,
                failure_evidence_refs=(),
            )
        except CallAuthorityError as exc:
            raise IsolatedRuntimeAuthorityError("runtime completion authority was rejected") from exc
        except CallConflictError as exc:
            raise IsolatedRuntimeConflictError("runtime completion conflicts") from exc
        if call.completed_at is None:
            raise IsolatedRuntimeIntegrityError("successful runtime ToolCall lacks completion time")
        receipt_class = (
            RuntimeExecutionReceipt
            if operation == "execute"
            else RuntimeCollectionReceipt
            if operation == "collect"
            else RuntimeReceipt
        )
        receipt = receipt_class(
            operation,
            state,
            tuple(process_call_refs),
            stdout_ref,
            stderr_ref,
            tuple(output_artifact_refs),
            call.call_ref,
            artifact.artifact_ref,
            call.completed_at,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO isolated_runtime_operation_results VALUES (?,?,?,?)",
                (
                    access.project_ref.value,
                    receipt.tool_call_ref.call_id,
                    _json(receipt.payload()),
                    receipt.record_sha256,
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise IsolatedRuntimeConflictError("runtime receipt persistence conflicts") from exc
        finally:
            connection.close()
        return receipt

    def get_receipt(self, access: ProjectAccess, call_ref: ToolCallRef) -> RuntimeReceipt:
        if not isinstance(call_ref, ToolCallRef):
            raise IsolatedRuntimeContractError("exact ToolCallRef is required")
        self._authorize(access, call_ref.project_ref)
        connection = self._connect()
        try:
            claim = connection.execute(
                "SELECT * FROM isolated_runtime_operation_claims WHERE project_id=? AND call_id=?",
                (access.project_ref.value, call_ref.call_id),
            ).fetchone()
            result = connection.execute(
                "SELECT * FROM isolated_runtime_operation_results WHERE project_id=? AND call_id=?",
                (access.project_ref.value, call_ref.call_id),
            ).fetchone()
        finally:
            connection.close()
        if claim is None or result is None:
            raise IsolatedRuntimeIntegrityError("runtime claim or receipt history is missing")
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
                "operation": cast(str, claim["operation"]),
                "project_ref": access.project_ref.value,
                "request_ref": request_ref.value,
            }
        )
        if not hmac.compare_digest(expected_claim, cast(str, claim["claim_sha256"])):
            raise IsolatedRuntimeIntegrityError("runtime operation claim digest changed")
        try:
            payload = json.loads(cast(str, result["receipt_json"]))
        except json.JSONDecodeError as exc:
            raise IsolatedRuntimeIntegrityError("runtime receipt JSON is malformed") from exc
        if not isinstance(payload, dict):
            raise IsolatedRuntimeIntegrityError("runtime receipt payload is malformed")
        try:
            operation = cast(str, payload["operation"])
            if operation != claim["operation"]:
                raise IsolatedRuntimeIntegrityError("runtime receipt operation differs from claim")
            state_ref = self._runtime_ref(payload["state_ref"], access.project_ref)
            state = self._get_state_generation(access, state_ref.runtime_id, state_ref.generation)
            process_calls = tuple(
                self._tool_call_ref(item, access.project_ref)
                for item in cast(list[object], payload["process_call_refs"])
            )
            output_artifacts = tuple(
                self._artifact_ref(item, access.project_ref)
                for item in cast(list[object], payload["output_artifact_refs"])
            )
            stdout_ref = self._content_ref(payload["stdout_ref"])
            stderr_ref = self._content_ref(payload["stderr_ref"])
            tool_call = self._tool_call_ref(payload["tool_call_ref"], access.project_ref)
            artifact = self._artifact_ref(payload["artifact_ref"], access.project_ref)
            completed_at = cast(str, payload["completed_at"])
            receipt_class = (
                RuntimeExecutionReceipt
                if operation == "execute"
                else RuntimeCollectionReceipt
                if operation == "collect"
                else RuntimeReceipt
            )
            receipt = receipt_class(
                operation,
                state,
                process_calls,
                stdout_ref,
                stderr_ref,
                output_artifacts,
                tool_call,
                artifact,
                completed_at,
            )
        except (KeyError, TypeError, ValueError, IsolatedRuntimeError) as exc:
            if isinstance(exc, IsolatedRuntimeIntegrityError):
                raise
            raise IsolatedRuntimeIntegrityError("runtime receipt payload is malformed") from exc
        if not hmac.compare_digest(cast(str, result["record_sha256"]), receipt.record_sha256):
            raise IsolatedRuntimeIntegrityError("runtime receipt evidence changed")
        call = self.calls.get_tool_call(access, call_ref)
        if call.status != "SUCCEEDED" or call.call_ref != receipt.tool_call_ref:
            raise IsolatedRuntimeIntegrityError("runtime receipt and ToolCall status differ")
        artifact_record = self.artifacts.get_artifact(access, receipt.artifact_ref)
        if artifact_record.content_ref not in call.output_refs or receipt.artifact_ref not in call.output_refs:
            raise IsolatedRuntimeIntegrityError("runtime ToolCall output evidence differs")
        expected_manifest = self._receipt_basis(
            receipt.operation,
            receipt.state,
            receipt.process_call_refs,
            receipt.stdout_ref,
            receipt.stderr_ref,
            receipt.output_artifact_refs,
        )
        try:
            if self.object_store.read(artifact_record.content_ref) != _json(expected_manifest).encode():
                raise IsolatedRuntimeIntegrityError("runtime receipt and Artifact manifest differ")
            for content_ref in (request_ref, artifact_record.content_ref, receipt.stdout_ref, receipt.stderr_ref):
                if content_ref is not None:
                    self.object_store.verify(content_ref)
        except ObjectStorageError as exc:
            raise IsolatedRuntimeIntegrityError("runtime receipt ContentRef failed verification") from exc
        for process_call_ref in receipt.process_call_refs:
            if self.calls.get_tool_call(access, process_call_ref).status == "RUNNING":
                raise IsolatedRuntimeIntegrityError("runtime process ToolCall evidence is incomplete")
        for output_artifact in receipt.output_artifact_refs:
            self.artifacts.get_artifact(access, output_artifact)
            if output_artifact not in call.output_refs:
                raise IsolatedRuntimeIntegrityError("runtime output Artifact differs from ToolCall evidence")
        return receipt

    def _prior_receipt(self, access: ProjectAccess, started: _StartedOperation) -> RuntimeReceipt | None:
        if started.first_claim:
            return None
        current = self.calls.get_tool_call(access, started.call.call_ref)
        if current.status == "SUCCEEDED":
            return self.get_receipt(access, current.call_ref)
        if current.status == "RUNNING":
            raise IsolatedRuntimeConflictError("runtime operation is already claimed and incomplete")
        raise IsolatedRuntimeConflictError("runtime operation idempotency key is terminal and unsuccessful")

    @staticmethod
    def _docker_mapping(value: object, name: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise IsolatedRuntimeIntegrityError(f"Docker {name} is malformed")
        return cast(dict[str, object], value)

    def _inspect_container(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        state: RuntimeState,
        *,
        material: str,
    ) -> tuple[dict[str, object], ProcessResult]:
        if state.container_id is None or state.container_generation is None:
            raise IsolatedRuntimeConflictError("runtime has no exact container identity")
        result = self._docker(
            access,
            attempt,
            control_root_ref=state.control_root_ref,
            argv=("container", "inspect", state.container_id),
            idempotency_material=f"{material}-inspect",
        )
        payload = self._json_object(self._decode(result, "container inspection"), "container inspection")
        labels = self._docker_mapping(
            self._docker_mapping(payload.get("Config"), "container config").get("Labels"),
            "container labels",
        )
        expected = {
            "biella.node_attempt": state.node_attempt_id,
            "biella.node_fence": str(state.node_fence),
            "biella.project": state.project_ref.value,
            "biella.runtime": state.runtime_ref.runtime_id,
            "biella.runtime_generation": str(state.container_generation),
            "biella.spec_sha256": state.spec.spec_sha256,
        }
        if any(labels.get(key) != value for key, value in expected.items()):
            raise IsolatedRuntimeAuthorityError("container ownership labels differ from durable runtime identity")
        if payload.get("Id") != state.container_id or payload.get("Image") != state.image_id:
            raise IsolatedRuntimeIntegrityError("container or image identity differs from durable runtime state")
        return payload, result

    @staticmethod
    def _observed_from_inspect(payload: Mapping[str, object]) -> dict[str, object]:
        state = DockerIsolatedRuntimeAdapter._docker_mapping(payload.get("State"), "container state")
        host = DockerIsolatedRuntimeAdapter._docker_mapping(payload.get("HostConfig"), "host config")
        return {
            "configured_memory_bytes": int(cast(int | str, host.get("Memory", 0))),
            "configured_nano_cpus": int(cast(int | str, host.get("NanoCpus", 0))),
            "configured_network_mode": str(host.get("NetworkMode", "")),
            "configured_pids_limit": int(cast(int | str, host.get("PidsLimit") or 0)),
            "dead": bool(state.get("Dead", False)),
            "error": str(state.get("Error", "")),
            "exit_code": int(cast(int | str, state.get("ExitCode", 0))),
            "finished_at": str(state.get("FinishedAt", "")),
            "oom_killed": bool(state.get("OOMKilled", False)),
            "paused": bool(state.get("Paused", False)),
            "pid": int(cast(int | str, state.get("Pid", 0))),
            "restart_count": int(cast(int | str, payload.get("RestartCount", 0))),
            "running": bool(state.get("Running", False)),
            "started_at": str(state.get("StartedAt", "")),
            "status": str(state.get("Status", "unknown")),
        }

    @staticmethod
    def _enforced_from_inspect(payload: Mapping[str, object]) -> dict[str, object]:
        host = DockerIsolatedRuntimeAdapter._docker_mapping(payload.get("HostConfig"), "host config")
        config = DockerIsolatedRuntimeAdapter._docker_mapping(payload.get("Config"), "container config")
        mounts = payload.get("Mounts")
        if not isinstance(mounts, list):
            raise IsolatedRuntimeIntegrityError("Docker mount evidence is malformed")
        return {
            "cap_drop": sorted(str(item) for item in cast(list[object], host.get("CapDrop") or [])),
            "memory_bytes": int(cast(int | str, host.get("Memory", 0))),
            "nano_cpus": int(cast(int | str, host.get("NanoCpus", 0))),
            "network_mode": str(host.get("NetworkMode", "")),
            "pids_limit": int(cast(int | str, host.get("PidsLimit") or 0)),
            "readonly_rootfs": bool(host.get("ReadonlyRootfs", False)),
            "security_opt": sorted(str(item) for item in cast(list[object], host.get("SecurityOpt") or [])),
            "user": str(config.get("User", "")),
            "mounts": sorted(
                (
                    str(DockerIsolatedRuntimeAdapter._docker_mapping(item, "mount").get("Destination", "")),
                    bool(DockerIsolatedRuntimeAdapter._docker_mapping(item, "mount").get("RW", False)),
                )
                for item in mounts
            ),
        }

    @staticmethod
    def _runtime_status(payload: Mapping[str, object]) -> tuple[RuntimeStatus, int | None, str | None]:
        observed = DockerIsolatedRuntimeAdapter._observed_from_inspect(payload)
        if bool(observed["running"]):
            return RuntimeStatus.RUNNING, None, None
        exit_code = cast(int, observed["exit_code"])
        if exit_code == 0:
            return RuntimeStatus.SUCCEEDED, 0, None
        failure = "OOM_KILLED" if bool(observed["oom_killed"]) else f"EXIT_{exit_code}"
        return RuntimeStatus.FAILED, exit_code, failure

    def describe_runtime(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        control_root_ref: FilesystemRootRef,
        idempotency_key: str,
    ) -> RuntimeDescriptor:
        self._key(idempotency_key)
        self._require_operation_authority(access, attempt, "describe")
        self._validate_control_root(access, control_root_ref)
        version = self._docker(
            access,
            attempt,
            control_root_ref=control_root_ref,
            argv=("version", "--format", "{{json .Server}}"),
            idempotency_material=f"describe-{idempotency_key}-version",
        )
        info = self._docker(
            access,
            attempt,
            control_root_ref=control_root_ref,
            argv=("info", "--format", "{{json .}}"),
            idempotency_material=f"describe-{idempotency_key}-info",
        )
        version_payload = self._json_object(self._decode(version, "server version"), "server version")
        info_payload = self._json_object(self._decode(info, "server info"), "server info")
        executable_digest = hashlib.sha256()
        with open(self.docker_executable, "rb") as reader:
            while chunk := reader.read(1024 * 1024):
                executable_digest.update(chunk)
        security = info_payload.get("SecurityOptions")
        if not isinstance(security, list):
            raise IsolatedRuntimeIntegrityError("Docker security feature evidence is malformed")
        return RuntimeDescriptor(
            self._implementation_ref(access.project_ref, "describe").value,
            "oci.container.cli",
            executable_digest.hexdigest(),
            cast(str, version_payload.get("Version")),
            cast(str, info_payload.get("ID")),
            str(info_payload.get("CgroupVersion")),
            tuple(sorted(str(item) for item in security)),
            (RuntimeNetworkPolicy.NONE,),
            ("cpu", "memory", "process"),
            ("gpu", "restricted_network", "storage"),
            0,
            (version.tool_call_ref, info.tool_call_ref),
            self._database_now(),
        )

    def create(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        spec: IsolatedRuntimeSpec,
        *,
        control_root_ref: FilesystemRootRef,
        resource_allocation_ref: ResourceAllocationRef | None = None,
        idempotency_key: str,
    ) -> RuntimeReceipt:
        if not isinstance(spec, IsolatedRuntimeSpec):
            raise IsolatedRuntimeContractError("exact IsolatedRuntimeSpec is required")
        if spec.project_ref != access.project_ref or control_root_ref.project_ref != access.project_ref:
            raise IsolatedRuntimeScopeError("runtime create request crossed Project scope")
        if resource_allocation_ref is not None and resource_allocation_ref.project_ref != access.project_ref:
            raise IsolatedRuntimeScopeError("runtime ResourceAllocation crossed Project scope")
        started = self._start_operation(
            access,
            attempt,
            operation="create",
            idempotency_key=idempotency_key,
            payload={
                "control_root_ref": control_root_ref.value,
                "resource_allocation_ref": None if resource_allocation_ref is None else resource_allocation_ref.value,
                "spec": spec.payload(),
                "spec_sha256": spec.spec_sha256,
            },
        )
        prior = self._prior_receipt(access, started)
        if prior is not None:
            return prior
        try:
            self._validate_control_root(access, control_root_ref)
            self._validate_spec_compatibility(access, spec)
            if resource_allocation_ref is not None:
                allocation = self.scheduler.get_allocation(access, resource_allocation_ref)
                if (
                    allocation.node_ref != attempt.node_ref
                    or allocation.node_attempt_id != attempt.attempt_id
                    or allocation.node_attempt_fence != attempt.fence
                    or allocation.status not in {"DISPATCHING", "DISPATCHED"}
                ):
                    raise IsolatedRuntimeAuthorityError("runtime ResourceAllocation is not current for exact Node attempt")
            image = self._docker(
                access,
                attempt,
                control_root_ref=control_root_ref,
                argv=("image", "inspect", "--format", "{{json .}}", spec.image_ref),
                idempotency_material=f"create-{idempotency_key}-image",
            )
            image_payload = self._json_object(self._decode(image, "image inspection"), "image inspection")
            image_id = cast(str, image_payload.get("Id"))
            if re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
                raise IsolatedRuntimeIntegrityError("Docker did not resolve an exact image identity")
            version = self._docker(
                access,
                attempt,
                control_root_ref=control_root_ref,
                argv=("version", "--format", "{{.Server.Version}}"),
                idempotency_material=f"create-{idempotency_key}-version",
            )
            runtime_version = self._decode(version, "runtime version").strip()
            if not runtime_version:
                raise IsolatedRuntimeIntegrityError("Docker runtime version is unavailable")
            runtime_id = f"rt_{uuid4().hex}"
            now = self._database_now()
            state = RuntimeState(
                RuntimeRef(access.project_ref, runtime_id, 1),
                spec,
                control_root_ref,
                RuntimeStatus.CREATED,
                self._implementation_ref(access.project_ref, "create").value,
                image_id,
                None,
                None,
                None,
                attempt.run_ref.run_id,
                attempt.attempt_id,
                attempt.fence,
                resource_allocation_ref,
                None if image.process_identity is None else image.process_identity.boot_id,
                runtime_version,
                {"network_policy": spec.network_policy.value, **spec.resource_limits.payload()},
                {},
                {},
                None,
                None,
                False,
                now,
                None,
                None,
                now,
            )
            self._persist_state(state, initial=True)
            return self._complete_operation(
                access,
                attempt,
                started,
                operation="create",
                idempotency_key=idempotency_key,
                state=state,
                process_call_refs=(image.tool_call_ref, version.tool_call_ref),
                source_refs=(image.stdout_ref, image.stderr_ref, version.stdout_ref, version.stderr_ref),
            )
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="create",
                idempotency_key=idempotency_key,
            )
            raise

    def execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> RuntimeExecutionReceipt:
        if not isinstance(runtime_ref, RuntimeRef):
            raise IsolatedRuntimeContractError("exact RuntimeRef is required")
        self._authorize(access, runtime_ref.project_ref)
        started = self._start_operation(
            access,
            attempt,
            operation="execute",
            idempotency_key=idempotency_key,
            payload={"runtime_ref": runtime_ref.value, "secret_refs": sorted(secret_values)},
        )
        prior = self._prior_receipt(access, started)
        if prior is not None:
            if not isinstance(prior, RuntimeExecutionReceipt):
                raise IsolatedRuntimeIntegrityError("execute replay receipt type differs")
            return prior
        try:
            state = self.get_state(access, runtime_ref)
            if state.status not in {RuntimeStatus.RUNNING, RuntimeStatus.SUCCEEDED, RuntimeStatus.FAILED}:
                raise IsolatedRuntimeConflictError("runtime is not executable from its current state")
            redaction_refs, redaction_values = self._redaction_environment(state.spec, secret_values)
            process_results: list[ProcessResult] = []
            timed_out = False
            if state.status is RuntimeStatus.RUNNING:
                self._inspect_container(
                    access,
                    attempt,
                    state,
                    material=f"execute-{idempotency_key}-prewait",
                )
                waited = self._docker(
                    access,
                    attempt,
                    control_root_ref=state.control_root_ref,
                    argv=("container", "wait", cast(str, state.container_id)),
                    idempotency_material=f"execute-{idempotency_key}-wait",
                    timeout_seconds=float(state.spec.timeout_seconds),
                    require_success=False,
                )
                process_results.append(waited)
                if waited.status is ProcessStatus.TIMED_OUT:
                    timed_out = True
                    self._inspect_container(
                        access,
                        attempt,
                        state,
                        material=f"execute-{idempotency_key}-timeout-owned",
                    )
                    killed = self._docker(
                        access,
                        attempt,
                        control_root_ref=state.control_root_ref,
                        argv=("container", "kill", cast(str, state.container_id)),
                        idempotency_material=f"execute-{idempotency_key}-timeout-kill",
                        require_success=False,
                    )
                    process_results.append(killed)
                    post_wait = self._docker(
                        access,
                        attempt,
                        control_root_ref=state.control_root_ref,
                        argv=("container", "wait", cast(str, state.container_id)),
                        idempotency_material=f"execute-{idempotency_key}-post-timeout-wait",
                        timeout_seconds=30,
                    )
                    process_results.append(post_wait)
                elif waited.status is not ProcessStatus.SUCCEEDED:
                    raise IsolatedRuntimeConflictError("Docker wait failed before exact terminal observation")
            logs = self._docker(
                access,
                attempt,
                control_root_ref=state.control_root_ref,
                argv=("container", "logs", cast(str, state.container_id)),
                idempotency_material=f"execute-{idempotency_key}-logs",
                stdout_limit_bytes=state.spec.stdout_limit_bytes,
                stderr_limit_bytes=state.spec.stderr_limit_bytes,
                redaction_refs=redaction_refs,
                redaction_values=redaction_values,
            )
            process_results.append(logs)
            inspected_payload, inspected = self._inspect_container(
                access,
                attempt,
                state,
                material=f"execute-{idempotency_key}-terminal",
            )
            process_results.append(inspected)
            observed = self._observed_from_inspect(inspected_payload)
            if bool(observed["running"]):
                raise IsolatedRuntimeIntegrityError("runtime remained active after terminal execution path")
            runtime_status, exit_code, failure = self._runtime_status(inspected_payload)
            if timed_out:
                runtime_status = RuntimeStatus.TIMED_OUT
                failure = "TIMEOUT"
            now = self._database_now()
            current = replace(
                state,
                runtime_ref=RuntimeRef(state.project_ref, state.runtime_ref.runtime_id, state.runtime_ref.generation + 1),
                status=runtime_status,
                observed_limits={**observed, "wait_timed_out": timed_out},
                exit_code=exit_code,
                failure=failure,
                completed_at=now,
                updated_at=now,
            )
            self._persist_state(current, initial=False)
            receipt = self._complete_operation(
                access,
                attempt,
                started,
                operation="execute",
                idempotency_key=idempotency_key,
                state=current,
                process_call_refs=tuple(item.tool_call_ref for item in process_results),
                stdout_ref=logs.stdout_ref,
                stderr_ref=logs.stderr_ref,
                source_refs=tuple(
                    reference
                    for item in process_results
                    for reference in (item.stdout_ref, item.stderr_ref)
                ),
            )
            if not isinstance(receipt, RuntimeExecutionReceipt):
                raise IsolatedRuntimeIntegrityError("execute completion produced wrong receipt type")
            return receipt
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="execute",
                idempotency_key=idempotency_key,
            )
            raise

    def _terminate(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        operation: str,
        idempotency_key: str,
    ) -> RuntimeReceipt:
        if operation not in {"cancel", "stop"}:
            raise IsolatedRuntimeContractError("runtime termination operation is malformed")
        if not isinstance(runtime_ref, RuntimeRef):
            raise IsolatedRuntimeContractError("exact RuntimeRef is required")
        self._authorize(access, runtime_ref.project_ref)
        started = self._start_operation(
            access,
            attempt,
            operation=operation,
            idempotency_key=idempotency_key,
            payload={"runtime_ref": runtime_ref.value},
        )
        prior = self._prior_receipt(access, started)
        if prior is not None:
            return prior
        try:
            state = self.get_state(access, runtime_ref)
            if state.status is not RuntimeStatus.RUNNING:
                raise IsolatedRuntimeConflictError("only a RUNNING runtime may be terminated")
            _, before = self._inspect_container(
                access,
                attempt,
                state,
                material=f"{operation}-{idempotency_key}-owned",
            )
            command = (
                ("container", "kill", cast(str, state.container_id))
                if operation == "cancel"
                else ("container", "stop", "--time", "2", cast(str, state.container_id))
            )
            terminated = self._docker(
                access,
                attempt,
                control_root_ref=state.control_root_ref,
                argv=command,
                idempotency_material=f"{operation}-{idempotency_key}-terminate",
                timeout_seconds=30,
            )
            inspected_payload, inspected = self._inspect_container(
                access,
                attempt,
                state,
                material=f"{operation}-{idempotency_key}-terminal",
            )
            observed = self._observed_from_inspect(inspected_payload)
            if bool(observed["running"]):
                raise IsolatedRuntimeIntegrityError("terminated runtime remains active")
            now = self._database_now()
            current = replace(
                state,
                runtime_ref=RuntimeRef(state.project_ref, state.runtime_ref.runtime_id, state.runtime_ref.generation + 1),
                status=RuntimeStatus.CANCELLED if operation == "cancel" else RuntimeStatus.STOPPED,
                observed_limits=observed,
                exit_code=cast(int, observed["exit_code"]),
                failure="CANCELLED" if operation == "cancel" else "STOPPED",
                completed_at=now,
                updated_at=now,
            )
            self._persist_state(current, initial=False)
            return self._complete_operation(
                access,
                attempt,
                started,
                operation=operation,
                idempotency_key=idempotency_key,
                state=current,
                process_call_refs=(before.tool_call_ref, terminated.tool_call_ref, inspected.tool_call_ref),
                source_refs=(
                    before.stdout_ref,
                    before.stderr_ref,
                    terminated.stdout_ref,
                    terminated.stderr_ref,
                    inspected.stdout_ref,
                    inspected.stderr_ref,
                ),
            )
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation=operation,
                idempotency_key=idempotency_key,
            )
            raise

    def cancel(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        idempotency_key: str,
    ) -> RuntimeReceipt:
        return self._terminate(
            access,
            attempt,
            runtime_ref,
            operation="cancel",
            idempotency_key=idempotency_key,
        )

    def stop(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        idempotency_key: str,
    ) -> RuntimeReceipt:
        return self._terminate(
            access,
            attempt,
            runtime_ref,
            operation="stop",
            idempotency_key=idempotency_key,
        )

    def inspect(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        idempotency_key: str,
    ) -> RuntimeReceipt:
        if not isinstance(runtime_ref, RuntimeRef):
            raise IsolatedRuntimeContractError("exact RuntimeRef is required")
        self._authorize(access, runtime_ref.project_ref)
        started = self._start_operation(
            access,
            attempt,
            operation="inspect",
            idempotency_key=idempotency_key,
            payload={"runtime_ref": runtime_ref.value},
        )
        prior = self._prior_receipt(access, started)
        if prior is not None:
            return prior
        try:
            state = self.get_state(access, runtime_ref)
            calls: tuple[ToolCallRef, ...] = ()
            sources: tuple[ContentRef, ...] = ()
            if state.status not in {RuntimeStatus.CREATED, RuntimeStatus.CLEANED}:
                payload, observed = self._inspect_container(
                    access,
                    attempt,
                    state,
                    material=f"inspect-{idempotency_key}",
                )
                actual_status, actual_exit, _ = self._runtime_status(payload)
                if state.status is RuntimeStatus.RUNNING and actual_status is not RuntimeStatus.RUNNING:
                    raise IsolatedRuntimeConflictError("runtime terminated outside the recorded lifecycle; execute must reconcile it")
                if state.status in {RuntimeStatus.SUCCEEDED, RuntimeStatus.FAILED} and actual_exit != state.exit_code:
                    raise IsolatedRuntimeIntegrityError("terminal runtime exit evidence changed")
                calls = (observed.tool_call_ref,)
                sources = (observed.stdout_ref, observed.stderr_ref)
            return self._complete_operation(
                access,
                attempt,
                started,
                operation="inspect",
                idempotency_key=idempotency_key,
                state=state,
                process_call_refs=calls,
                source_refs=sources,
            )
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="inspect",
                idempotency_key=idempotency_key,
            )
            raise

    def _capture_output_content(
        self,
        access: ProjectAccess,
        output: RuntimeOutput,
        secret_values: Sequence[bytes],
    ) -> ContentRef:
        try:
            root = self.filesystem._require_root(access, output.root_ref, writable=False)
            descriptor, before = self.filesystem._open_regular(root, output.path)
        except FilesystemAuthorityError as exc:
            raise IsolatedRuntimeAuthorityError("runtime output path is not authorized") from exc
        except FilesystemNotFoundError as exc:
            raise IsolatedRuntimeNotFoundError("required runtime output is unavailable") from exc
        except FilesystemError as exc:
            raise IsolatedRuntimeIntegrityError("runtime output path failed verification") from exc
        maximum_secret = max((len(item) for item in secret_values), default=0)
        tail = b""
        try:
            with tempfile.TemporaryFile(dir=self.runtime_root) as snapshot:
                total = 0
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    candidate = tail + chunk
                    if any(secret and secret in candidate for secret in secret_values):
                        raise IsolatedRuntimeAuthorityError("required runtime output contains secret material")
                    tail = candidate[-(maximum_secret - 1) :] if maximum_secret > 1 else b""
                    snapshot.write(chunk)
                    total += len(chunk)
                after = os.fstat(descriptor)
                if (
                    after.st_dev != before.st_dev
                    or after.st_ino != before.st_ino
                    or after.st_size != before.st_size
                    or after.st_mtime_ns != before.st_mtime_ns
                    or total != before.st_size
                ):
                    raise IsolatedRuntimeConflictError("runtime output changed during secure capture")
                snapshot.flush()
                snapshot.seek(0)
                return self.object_store.put(
                    snapshot,
                    media_type=output.media_type,
                    expected_size=before.st_size,
                )
        finally:
            os.close(descriptor)

    def collect_outputs(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> RuntimeCollectionReceipt:
        if not isinstance(runtime_ref, RuntimeRef):
            raise IsolatedRuntimeContractError("exact RuntimeRef is required")
        self._authorize(access, runtime_ref.project_ref)
        started = self._start_operation(
            access,
            attempt,
            operation="collect",
            idempotency_key=idempotency_key,
            payload={"runtime_ref": runtime_ref.value, "secret_refs": sorted(secret_values)},
        )
        prior = self._prior_receipt(access, started)
        if prior is not None:
            if not isinstance(prior, RuntimeCollectionReceipt):
                raise IsolatedRuntimeIntegrityError("collect replay receipt type differs")
            return prior
        try:
            state = self.get_state(access, runtime_ref)
            if state.status not in {
                RuntimeStatus.SUCCEEDED,
                RuntimeStatus.FAILED,
                RuntimeStatus.TIMED_OUT,
                RuntimeStatus.CANCELLED,
                RuntimeStatus.STOPPED,
            }:
                raise IsolatedRuntimeConflictError("runtime outputs require an exact terminal state")
            _, exact_values = self._redaction_environment(state.spec, secret_values)
            secret_bytes = tuple(value.encode() for value in exact_values.values())
            captured = tuple(
                self._capture_output_content(access, output, secret_bytes)
                for output in state.spec.outputs
            )
            artifacts: list[Artifact] = []
            for index, (output, content_ref) in enumerate(zip(state.spec.outputs, captured, strict=True)):
                artifacts.append(
                    self.artifacts.publish_from_run(
                        access,
                        producer_attempt=self._run_attempt(access, attempt),
                        expected_task_ref=attempt.task_ref,
                        expected_task_digest=attempt.task_digest,
                        role="runtime.output",
                        content_ref=content_ref,
                        source_refs=(),
                        source_artifact_refs=(),
                        source_content_refs=(),
                        derivation_type="runtime.collect",
                        metadata={
                            "media_type": output.media_type,
                            "semantic_label": f"runtime-output-{index}",
                            "schema_ref": "schema://biella/runtime-output/1",
                            "schema_version": "1.0.0",
                        },
                    )
                )
            now = self._database_now()
            current = replace(
                state,
                runtime_ref=RuntimeRef(state.project_ref, state.runtime_ref.runtime_id, state.runtime_ref.generation + 1),
                status=RuntimeStatus.OUTPUTS_COLLECTED,
                outputs_collected=True,
                updated_at=now,
            )
            self._persist_state(current, initial=False)
            receipt = self._complete_operation(
                access,
                attempt,
                started,
                operation="collect",
                idempotency_key=idempotency_key,
                state=current,
                output_artifact_refs=tuple(item.artifact_ref for item in artifacts),
                source_refs=captured,
            )
            if not isinstance(receipt, RuntimeCollectionReceipt):
                raise IsolatedRuntimeIntegrityError("collect completion produced wrong receipt type")
            return receipt
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="collect",
                idempotency_key=idempotency_key,
            )
            raise

    def cleanup(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        idempotency_key: str,
    ) -> RuntimeReceipt:
        if not isinstance(runtime_ref, RuntimeRef):
            raise IsolatedRuntimeContractError("exact RuntimeRef is required")
        self._authorize(access, runtime_ref.project_ref)
        started = self._start_operation(
            access,
            attempt,
            operation="cleanup",
            idempotency_key=idempotency_key,
            payload={"runtime_ref": runtime_ref.value},
        )
        prior = self._prior_receipt(access, started)
        if prior is not None:
            return prior
        try:
            state = self.get_state(access, runtime_ref)
            if state.status is RuntimeStatus.RUNNING:
                raise IsolatedRuntimeConflictError("runtime must be terminal before cleanup")
            if state.spec.outputs and not state.outputs_collected:
                raise IsolatedRuntimeConflictError("required outputs must be durable before cleanup")
            process_results: list[ProcessResult] = []
            if state.container_id is not None:
                _, owned = self._inspect_container(
                    access,
                    attempt,
                    state,
                    material=f"cleanup-{idempotency_key}-owned",
                )
                process_results.append(owned)
                removed = self._docker(
                    access,
                    attempt,
                    control_root_ref=state.control_root_ref,
                    argv=("container", "rm", "--force", state.container_id),
                    idempotency_material=f"cleanup-{idempotency_key}-remove",
                    timeout_seconds=60,
                )
                process_results.append(removed)
            now = self._database_now()
            current = replace(
                state,
                runtime_ref=RuntimeRef(state.project_ref, state.runtime_ref.runtime_id, state.runtime_ref.generation + 1),
                status=RuntimeStatus.CLEANED,
                updated_at=now,
            )
            self._persist_state(current, initial=False)
            return self._complete_operation(
                access,
                attempt,
                started,
                operation="cleanup",
                idempotency_key=idempotency_key,
                state=current,
                process_call_refs=tuple(item.tool_call_ref for item in process_results),
                source_refs=tuple(
                    reference
                    for item in process_results
                    for reference in (item.stdout_ref, item.stderr_ref)
                ),
            )
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="cleanup",
                idempotency_key=idempotency_key,
            )
            raise

    def reconcile_orphans(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        control_root_ref: FilesystemRootRef,
        idempotency_key: str,
    ) -> RuntimeReconciliation:
        self._key(idempotency_key)
        self._require_operation_authority(access, attempt, "inspect")
        self._validate_control_root(access, control_root_ref)
        listed = self._docker(
            access,
            attempt,
            control_root_ref=control_root_ref,
            argv=(
                "container",
                "ls",
                "--all",
                "--no-trunc",
                "--filter",
                f"label=biella.project={access.project_ref.value}",
                "--format",
                "{{.ID}}",
            ),
            idempotency_material=f"reconcile-{idempotency_key}-list",
        )
        container_ids = tuple(item for item in self._decode(listed, "owned container listing").splitlines() if item)
        recovered: list[RuntimeRef] = []
        cleaned: list[RuntimeRef] = []
        unknown: list[str] = []
        for index, container_id in enumerate(container_ids):
            inspected = self._docker(
                access,
                attempt,
                control_root_ref=control_root_ref,
                argv=("container", "inspect", container_id),
                idempotency_material=f"reconcile-{idempotency_key}-inspect-{index}",
            )
            payload = self._json_object(self._decode(inspected, "orphan inspection"), "orphan inspection")
            labels = self._docker_mapping(
                self._docker_mapping(payload.get("Config"), "orphan config").get("Labels"),
                "orphan labels",
            )
            runtime_id = labels.get("biella.runtime")
            generation = labels.get("biella.runtime_generation")
            if not isinstance(runtime_id, str) or _RUNTIME_ID.fullmatch(runtime_id) is None or not isinstance(generation, str):
                unknown.append(container_id)
                continue
            try:
                container_generation = int(generation)
                connection = self._connect()
                try:
                    head = connection.execute(
                        "SELECT generation FROM isolated_runtime_heads WHERE project_id=? AND runtime_id=?",
                        (access.project_ref.value, runtime_id),
                    ).fetchone()
                finally:
                    connection.close()
                if head is None:
                    unknown.append(container_id)
                    continue
                state = self._get_state_generation(access, runtime_id, cast(int, head[0]))
                if (
                    state.container_id != payload.get("Id")
                    or state.container_generation != container_generation
                    or state.control_root_ref != control_root_ref
                    or labels.get("biella.spec_sha256") != state.spec.spec_sha256
                    or labels.get("biella.node_attempt") != state.node_attempt_id
                    or labels.get("biella.node_fence") != str(state.node_fence)
                ):
                    unknown.append(container_id)
                    continue
                if state.status is RuntimeStatus.CLEANED:
                    removed = self._docker(
                        access,
                        attempt,
                        control_root_ref=control_root_ref,
                        argv=("container", "rm", "--force", container_id),
                        idempotency_material=f"reconcile-{idempotency_key}-cleanup-{index}",
                    )
                    if removed.status is not ProcessStatus.SUCCEEDED:
                        raise IsolatedRuntimeIntegrityError("owned orphan cleanup was not observed")
                    cleaned.append(state.runtime_ref)
                else:
                    recovered.append(state.runtime_ref)
            except (TypeError, ValueError):
                unknown.append(container_id)
        return RuntimeReconciliation(
            tuple(sorted(recovered, key=lambda item: item.value)),
            tuple(sorted(cleaned, key=lambda item: item.value)),
            tuple(sorted(set(unknown))),
        )

    def _secret_stage(
        self,
        state: RuntimeState,
        secret_values: Mapping[str, str],
        generation: int,
    ) -> tuple[Path, tuple[tuple[RuntimeSecretMount, Path], ...]]:
        self._redaction_environment(state.spec, secret_values)
        stage = self.runtime_root / f"{state.runtime_ref.runtime_id}-g{generation}"
        try:
            os.mkdir(stage, 0o700)
        except FileExistsError as exc:
            raise IsolatedRuntimeConflictError("runtime secret staging identity already exists") from exc
        records: list[tuple[RuntimeSecretMount, Path]] = []
        try:
            for index, secret in enumerate(state.spec.secret_mounts):
                target = stage / f"secret-{index}"
                descriptor = os.open(
                    target,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
                    0o444,
                )
                try:
                    payload = secret_values[secret.secret_ref].encode()
                    offset = 0
                    while offset < len(payload):
                        offset += os.write(descriptor, payload[offset:])
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                records.append((secret, target))
            return stage, tuple(records)
        except Exception:
            for _, target in records:
                target.unlink(missing_ok=True)
            stage.rmdir()
            raise

    @staticmethod
    def _remove_secret_stage(stage: Path, records: Sequence[tuple[RuntimeSecretMount, Path]]) -> None:
        for _, target in records:
            target.unlink(missing_ok=True)
        try:
            stage.rmdir()
        except FileNotFoundError:
            pass

    def _container_create_argv(
        self,
        state: RuntimeState,
        mount_sources: Sequence[Path],
        secret_records: Sequence[tuple[RuntimeSecretMount, Path]],
        *,
        container_name: str,
        container_generation: int,
    ) -> tuple[str, ...]:
        spec = state.spec
        argv: list[str] = [
            "container",
            "create",
            "--name",
            container_name,
            "--label",
            f"biella.project={state.project_ref.value}",
            "--label",
            f"biella.runtime={state.runtime_ref.runtime_id}",
            "--label",
            f"biella.runtime_generation={container_generation}",
            "--label",
            f"biella.node_attempt={state.node_attempt_id}",
            "--label",
            f"biella.node_fence={state.node_fence}",
            "--label",
            f"biella.spec_sha256={spec.spec_sha256}",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65534:65534",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=16777216,mode=1777",
            "--workdir",
            spec.working_directory,
        ]
        limits = spec.resource_limits
        if limits.cpus is not None:
            argv.extend(("--cpus", str(float(limits.cpus))))
        if limits.memory_bytes is not None:
            argv.extend(("--memory", str(limits.memory_bytes)))
        if limits.process_count is not None:
            argv.extend(("--pids-limit", str(limits.process_count)))
        for key, value in spec.environment.items():
            argv.extend(("--env", f"{key}={value}"))
        for mount, source in zip(spec.mounts, mount_sources, strict=True):
            option = f"type=bind,src={source},dst={mount.target_path}"
            if mount.read_only:
                option += ",readonly"
            argv.extend(("--mount", option))
        for secret, source in secret_records:
            argv.extend(("--mount", f"type=bind,src={source},dst={secret.target_path},readonly"))
        argv.extend(("--entrypoint", spec.entrypoint, spec.image_ref, *spec.args))
        return tuple(argv)

    def start(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        runtime_ref: RuntimeRef,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> RuntimeReceipt:
        if not isinstance(runtime_ref, RuntimeRef):
            raise IsolatedRuntimeContractError("exact RuntimeRef is required")
        self._authorize(access, runtime_ref.project_ref)
        started = self._start_operation(
            access,
            attempt,
            operation="start",
            idempotency_key=idempotency_key,
            payload={
                "runtime_ref": runtime_ref.value,
                "secret_refs": sorted(secret_values),
            },
        )
        prior = self._prior_receipt(access, started)
        if prior is not None:
            return prior
        container_id: str | None = None
        state: RuntimeState | None = None
        stage: Path | None = None
        secret_records: tuple[tuple[RuntimeSecretMount, Path], ...] = ()
        try:
            state = self.get_state(access, runtime_ref)
            if state.status is not RuntimeStatus.CREATED:
                raise IsolatedRuntimeConflictError("only a CREATED runtime may start")
            if state.node_attempt_id != attempt.attempt_id or state.node_fence != attempt.fence:
                raise IsolatedRuntimeAuthorityError("runtime Node attempt ownership differs")
            mount_sources = self._validate_spec_compatibility(access, state.spec)
            next_generation = state.runtime_ref.generation + 1
            stage, secret_records = self._secret_stage(state, secret_values, next_generation)
            container_name = f"biella-{state.runtime_ref.runtime_id[3:]}-g{next_generation}"
            created = self._docker(
                access,
                attempt,
                control_root_ref=state.control_root_ref,
                argv=self._container_create_argv(
                    state,
                    mount_sources,
                    secret_records,
                    container_name=container_name,
                    container_generation=next_generation,
                ),
                idempotency_material=f"start-{idempotency_key}-create",
                timeout_seconds=300,
            )
            container_id = self._decode(created, "container create").strip()
            if re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
                raise IsolatedRuntimeIntegrityError("Docker did not return an exact container identity")
            started_container = self._docker(
                access,
                attempt,
                control_root_ref=state.control_root_ref,
                argv=("container", "start", container_id),
                idempotency_material=f"start-{idempotency_key}-start",
                timeout_seconds=300,
            )
            self._remove_secret_stage(stage, secret_records)
            stage = None
            provisional = replace(
                state,
                runtime_ref=RuntimeRef(state.project_ref, state.runtime_ref.runtime_id, next_generation),
                container_id=container_id,
                container_name=container_name,
                container_generation=next_generation,
            )
            inspected_payload, inspected = self._inspect_container(
                access,
                attempt,
                provisional,
                material=f"start-{idempotency_key}",
            )
            runtime_status, exit_code, failure = self._runtime_status(inspected_payload)
            observed = self._observed_from_inspect(inspected_payload)
            started_at = cast(str, observed["started_at"])
            if not started_at or started_at.startswith("0001-"):
                raise IsolatedRuntimeIntegrityError("Docker runtime lacks an exact start time")
            now = self._database_now()
            current = replace(
                provisional,
                status=runtime_status,
                host_boot_id=None if created.process_identity is None else created.process_identity.boot_id,
                enforced_limits=self._enforced_from_inspect(inspected_payload),
                observed_limits=observed,
                exit_code=exit_code,
                failure=failure,
                started_at=started_at,
                completed_at=now if runtime_status is not RuntimeStatus.RUNNING else None,
                updated_at=now,
            )
            self._persist_state(current, initial=False)
            return self._complete_operation(
                access,
                attempt,
                started,
                operation="start",
                idempotency_key=idempotency_key,
                state=current,
                process_call_refs=(
                    created.tool_call_ref,
                    started_container.tool_call_ref,
                    inspected.tool_call_ref,
                ),
                source_refs=(
                    created.stdout_ref,
                    created.stderr_ref,
                    started_container.stdout_ref,
                    started_container.stderr_ref,
                    inspected.stdout_ref,
                    inspected.stderr_ref,
                ),
            )
        except Exception:
            if stage is not None:
                self._remove_secret_stage(stage, secret_records)
            if container_id is not None and state is not None:
                try:
                    self._docker(
                        access,
                        attempt,
                        control_root_ref=state.control_root_ref,
                        argv=("container", "rm", "--force", container_id),
                        idempotency_material=f"start-{idempotency_key}-rollback",
                        require_success=False,
                    )
                except Exception:
                    pass
            self._fail_operation(
                access,
                attempt,
                started,
                operation="start",
                idempotency_key=idempotency_key,
            )
            raise
