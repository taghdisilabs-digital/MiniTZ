"""Exact-revision, candidate-isolated Git repository adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat as stat_module
from types import MappingProxyType
from typing import cast
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
from .task import TaskRevisionService


_REPOSITORY_ID = re.compile(r"repo_[0-9a-f]{32}")
_WORKSPACE_ID = re.compile(r"rws_[0-9a-f]{32}")
_OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_RECORD_SHA = re.compile(r"[0-9a-f]{64}")
_REF_NAME = re.compile(r"refs/(?:heads|tags)/[A-Za-z0-9][A-Za-z0-9._/-]{0,254}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_REMOTE_REF = re.compile(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,254}")
_OPERATIONS = (
    "inspect",
    "status",
    "diff",
    "read",
    "workspace",
    "apply",
    "commit",
    "fetch",
    "push",
)
_MUTATING = frozenset({"workspace", "apply", "commit", "fetch", "push"})
_DANGEROUS_CONFIG_EXACT = frozenset(
    {
        "core.hookspath",
        "core.fsmonitor",
        "core.sshcommand",
        "credential.helper",
        "protocol.ext.allow",
    }
)
_REQUEST_MEDIA_TYPE = "application/vnd.minitz.git-request+json"
_RECEIPT_MEDIA_TYPE = "application/vnd.minitz.git-receipt+json"
_UNTRACKED_MEDIA_TYPE = "application/vnd.minitz.git-untracked-manifest+json"


class GitAdapterError(Exception):
    """Base class for exact-revision repository failures."""


class GitContractError(GitAdapterError, ValueError):
    """A repository adapter request is malformed."""


class GitScopeError(GitAdapterError):
    """A repository request crossed Project scope."""


class GitAuthorityError(GitAdapterError):
    """A repository request lacks exact Task-derived authority."""


class GitConflictError(GitAdapterError):
    """Repository base, workspace fence, or idempotency changed."""


class GitNotFoundError(GitAdapterError):
    """Exact repository or workspace evidence is unavailable."""


class GitIntegrityError(GitAdapterError):
    """Repository bytes, identity, or durable evidence failed verification."""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise GitContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise GitContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GitContractError(f"{name} must be timezone-aware")
    return value


def _text(value: object, name: str, maximum: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or any(ord(character) < 32 and character not in "\t\r\n" for character in value)
        or len(value.encode()) > maximum
    ):
        raise GitContractError(f"{name} is malformed or unbounded")
    return value


def _object_id(value: object, name: str, object_format: str | None = None) -> str:
    if not isinstance(value, str) or _OBJECT_ID.fullmatch(value) is None:
        raise GitContractError(f"{name} must be a full Git object ID")
    if object_format == "sha1" and len(value) != 40:
        raise GitContractError(f"{name} differs from repository object format")
    if object_format == "sha256" and len(value) != 64:
        raise GitContractError(f"{name} differs from repository object format")
    return value


def _content(value: ContentRef) -> dict[str, object]:
    return {
        "algorithm": value.algorithm,
        "digest": value.digest,
        "media_type": value.media_type,
        "size_bytes": value.size_bytes,
    }


@dataclass(frozen=True)
class RepositoryRef:
    repository_id: str
    project_ref: ProjectRef
    root_ref: FilesystemRootRef
    relative_path: str
    object_format: str
    commit_sha: str
    tree_sha: str
    submodules: Mapping[str, str]
    config_sha256: str
    registered_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.repository_id, str) or _REPOSITORY_ID.fullmatch(self.repository_id) is None:
            raise GitContractError("RepositoryRef identity is malformed")
        if self.root_ref.project_ref != self.project_ref:
            raise GitScopeError("RepositoryRef FilesystemRoot crossed Project scope")
        _text(self.relative_path, "repository relative_path")
        if self.object_format not in {"sha1", "sha256"}:
            raise GitContractError("repository object format is unsupported")
        _object_id(self.commit_sha, "repository commit", self.object_format)
        _object_id(self.tree_sha, "repository tree", self.object_format)
        if not isinstance(self.submodules, Mapping):
            raise GitContractError("repository submodule identities are malformed")
        submodules = dict(self.submodules)
        for path, commit in submodules.items():
            _text(path, "submodule path")
            _object_id(commit, "submodule commit", self.object_format)
        object.__setattr__(self, "submodules", MappingProxyType(dict(sorted(submodules.items()))))
        if not isinstance(self.config_sha256, str) or _RECORD_SHA.fullmatch(self.config_sha256) is None:
            raise GitContractError("repository config evidence is malformed")
        _timestamp(self.registered_at, "registered_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def value(self) -> str:
        return f"repository://{self.project_ref.value}/{self.repository_id}@{self.commit_sha}"

    def payload(self) -> dict[str, object]:
        return {
            "commit_sha": self.commit_sha,
            "config_sha256": self.config_sha256,
            "object_format": self.object_format,
            "project_ref": self.project_ref.value,
            "registered_at": self.registered_at,
            "relative_path": self.relative_path,
            "repository_id": self.repository_id,
            "root_ref": self.root_ref.value,
            "submodules": dict(self.submodules),
            "tree_sha": self.tree_sha,
        }


@dataclass(frozen=True)
class RepositoryWorkspaceRef:
    workspace_id: str
    project_ref: ProjectRef
    repository_id: str
    root_ref: FilesystemRootRef
    relative_path: str
    base_commit_sha: str
    base_tree_sha: str
    current_commit_sha: str
    current_tree_sha: str
    generation: int
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_id, str) or _WORKSPACE_ID.fullmatch(self.workspace_id) is None:
            raise GitContractError("RepositoryWorkspaceRef identity is malformed")
        if not isinstance(self.repository_id, str) or _REPOSITORY_ID.fullmatch(self.repository_id) is None:
            raise GitContractError("workspace repository identity is malformed")
        if self.root_ref.project_ref != self.project_ref:
            raise GitScopeError("workspace FilesystemRoot crossed Project scope")
        _text(self.relative_path, "workspace relative_path")
        for value, name in (
            (self.base_commit_sha, "base commit"),
            (self.base_tree_sha, "base tree"),
            (self.current_commit_sha, "current commit"),
            (self.current_tree_sha, "current tree"),
        ):
            _object_id(value, name)
        if not isinstance(self.generation, int) or isinstance(self.generation, bool) or self.generation < 1:
            raise GitContractError("workspace generation is malformed")
        _timestamp(self.created_at, "created_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def value(self) -> str:
        return f"repository-workspace://{self.project_ref.value}/{self.workspace_id}/{self.generation}"

    def payload(self) -> dict[str, object]:
        return {
            "base_commit_sha": self.base_commit_sha,
            "base_tree_sha": self.base_tree_sha,
            "created_at": self.created_at,
            "current_commit_sha": self.current_commit_sha,
            "current_tree_sha": self.current_tree_sha,
            "generation": self.generation,
            "project_ref": self.project_ref.value,
            "relative_path": self.relative_path,
            "repository_id": self.repository_id,
            "root_ref": self.root_ref.value,
            "workspace_id": self.workspace_id,
        }


@dataclass(frozen=True)
class RepositoryInspectionReceipt:
    repository_ref: RepositoryRef
    head_commit_sha: str
    head_tree_sha: str
    status_ref: ContentRef
    staged_paths: tuple[str, ...]
    unstaged_paths: tuple[str, ...]
    untracked_paths: tuple[str, ...]
    process_call_refs: tuple[ToolCallRef, ...]
    tool_call_ref: ToolCallRef
    artifact_ref: ArtifactRef
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.repository_ref.project_ref
        if self.tool_call_ref.project_ref != project or self.artifact_ref.project_ref != project:
            raise GitScopeError("repository inspection evidence crossed Project scope")
        _object_id(self.head_commit_sha, "inspection HEAD", self.repository_ref.object_format)
        _object_id(self.head_tree_sha, "inspection tree", self.repository_ref.object_format)
        _validate_paths(self.staged_paths, "staged_paths")
        _validate_paths(self.unstaged_paths, "unstaged_paths")
        _validate_paths(self.untracked_paths, "untracked_paths")
        _validate_calls(self.process_call_refs, project)
        _timestamp(self.completed_at, "completed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def dirty(self) -> bool:
        return bool(self.staged_paths or self.unstaged_paths or self.untracked_paths)

    def payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref.value,
            "completed_at": self.completed_at,
            "head_commit_sha": self.head_commit_sha,
            "head_tree_sha": self.head_tree_sha,
            "process_call_refs": [item.value for item in self.process_call_refs],
            "repository_ref": self.repository_ref.value,
            "staged_paths": list(self.staged_paths),
            "status_ref": _content(self.status_ref),
            "tool_call_ref": self.tool_call_ref.value,
            "unstaged_paths": list(self.unstaged_paths),
            "untracked_paths": list(self.untracked_paths),
        }


@dataclass(frozen=True)
class RepositoryDiffReceipt:
    workspace_ref: RepositoryWorkspaceRef
    staged_diff_ref: ContentRef
    unstaged_diff_ref: ContentRef
    untracked_manifest_ref: ContentRef
    untracked_paths: tuple[str, ...]
    process_call_refs: tuple[ToolCallRef, ...]
    tool_call_ref: ToolCallRef
    artifact_ref: ArtifactRef
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.workspace_ref.project_ref
        if self.tool_call_ref.project_ref != project or self.artifact_ref.project_ref != project:
            raise GitScopeError("repository diff evidence crossed Project scope")
        _validate_paths(self.untracked_paths, "untracked_paths")
        _validate_calls(self.process_call_refs, project)
        _timestamp(self.completed_at, "completed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref.value,
            "completed_at": self.completed_at,
            "process_call_refs": [item.value for item in self.process_call_refs],
            "staged_diff_ref": _content(self.staged_diff_ref),
            "tool_call_ref": self.tool_call_ref.value,
            "unstaged_diff_ref": _content(self.unstaged_diff_ref),
            "untracked_manifest_ref": _content(self.untracked_manifest_ref),
            "untracked_paths": list(self.untracked_paths),
            "workspace_ref": self.workspace_ref.value,
        }


@dataclass(frozen=True)
class RepositoryCommitReceipt:
    workspace_ref: RepositoryWorkspaceRef
    parent_commit_sha: str
    parent_tree_sha: str
    commit_sha: str
    tree_sha: str
    diff_artifact_ref: ArtifactRef
    process_call_refs: tuple[ToolCallRef, ...]
    tool_call_ref: ToolCallRef
    artifact_ref: ArtifactRef
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.workspace_ref.project_ref
        if any(item.project_ref != project for item in (self.diff_artifact_ref, self.artifact_ref)):
            raise GitScopeError("repository commit Artifact crossed Project scope")
        if self.tool_call_ref.project_ref != project:
            raise GitScopeError("repository commit ToolCall crossed Project scope")
        for value, name in (
            (self.parent_commit_sha, "parent commit"),
            (self.parent_tree_sha, "parent tree"),
            (self.commit_sha, "commit"),
            (self.tree_sha, "tree"),
        ):
            _object_id(value, name)
        _validate_calls(self.process_call_refs, project)
        _timestamp(self.completed_at, "completed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref.value,
            "commit_sha": self.commit_sha,
            "completed_at": self.completed_at,
            "diff_artifact_ref": self.diff_artifact_ref.value,
            "parent_commit_sha": self.parent_commit_sha,
            "parent_tree_sha": self.parent_tree_sha,
            "process_call_refs": [item.value for item in self.process_call_refs],
            "tool_call_ref": self.tool_call_ref.value,
            "tree_sha": self.tree_sha,
            "workspace_ref": self.workspace_ref.value,
        }


@dataclass(frozen=True)
class RepositoryPushReceipt:
    workspace_ref: RepositoryWorkspaceRef
    destination_url: str
    destination_ref: str
    before_commit_sha: str | None
    pushed_commit_sha: str
    forced: bool
    process_call_refs: tuple[ToolCallRef, ...]
    tool_call_ref: ToolCallRef
    artifact_ref: ArtifactRef
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.workspace_ref.project_ref
        if self.tool_call_ref.project_ref != project or self.artifact_ref.project_ref != project:
            raise GitScopeError("repository push evidence crossed Project scope")
        _text(self.destination_url, "push destination URL")
        if not isinstance(self.destination_ref, str) or _REF_NAME.fullmatch(self.destination_ref) is None:
            raise GitContractError("push destination ref is malformed")
        if self.before_commit_sha is not None:
            _object_id(self.before_commit_sha, "push prior commit")
        _object_id(self.pushed_commit_sha, "pushed commit")
        if not isinstance(self.forced, bool):
            raise GitContractError("push force classification is malformed")
        _validate_calls(self.process_call_refs, project)
        _timestamp(self.completed_at, "completed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref.value,
            "before_commit_sha": self.before_commit_sha,
            "completed_at": self.completed_at,
            "destination_ref": self.destination_ref,
            "destination_url": self.destination_url,
            "forced": self.forced,
            "process_call_refs": [item.value for item in self.process_call_refs],
            "pushed_commit_sha": self.pushed_commit_sha,
            "tool_call_ref": self.tool_call_ref.value,
            "workspace_ref": self.workspace_ref.value,
        }


def _validate_paths(values: tuple[str, ...], name: str) -> None:
    if not isinstance(values, tuple) or len(values) > 100_000 or len(set(values)) != len(values):
        raise GitContractError(f"{name} is duplicated or unbounded")
    for value in values:
        _text(value, name, 4096)


def _validate_calls(values: tuple[ToolCallRef, ...], project_ref: ProjectRef) -> None:
    if not isinstance(values, tuple) or not values:
        raise GitContractError("repository receipt requires process ToolCalls")
    if any(not isinstance(value, ToolCallRef) or value.project_ref != project_ref for value in values):
        raise GitScopeError("repository process ToolCalls crossed Project scope")


@dataclass(frozen=True)
class _StartedOperation:
    call: ToolCall
    request_ref: ContentRef
    first_claim: bool


class GitAdapter:
    """Exact-revision Git implementation using the managed process adapter."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        git_executable: str | Path = "/usr/bin/git",
    ) -> None:
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("object_store must implement ObjectStorageBackend")
        executable = Path(git_executable)
        if not executable.is_absolute():
            raise GitContractError("git executable must be an absolute path")
        try:
            executable_state = executable.stat()
        except OSError as exc:
            raise GitNotFoundError("configured Git executable is unavailable") from exc
        if not stat_module.S_ISREG(executable_state.st_mode) or executable_state.st_mode & 0o111 == 0:
            raise GitAuthorityError("configured Git executable is not executable")
        self.database_path = Path(database_path).resolve()
        self.object_store = object_store
        self.git_executable = str(executable.resolve(strict=True))
        self.projects = ProjectStore(self.database_path)
        self.graphs = GraphService(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.runs = RunService(self.database_path)
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
                CREATE TABLE IF NOT EXISTS git_repository_claims (
                    project_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    semantic_sha256 TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    PRIMARY KEY (project_id,idempotency_key),
                    UNIQUE (project_id,repository_id)
                );
                CREATE TABLE IF NOT EXISTS git_repositories (
                    project_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    repository_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,repository_id)
                );
                CREATE TABLE IF NOT EXISTS git_workspace_claims (
                    project_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    semantic_sha256 TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    PRIMARY KEY (project_id,idempotency_key),
                    UNIQUE (project_id,workspace_id)
                );
                CREATE TABLE IF NOT EXISTS git_workspace_states (
                    project_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    workspace_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,workspace_id,generation)
                );
                CREATE TABLE IF NOT EXISTS git_workspace_heads (
                    project_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,workspace_id)
                );
                CREATE TABLE IF NOT EXISTS git_operation_claims (
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
                CREATE TABLE IF NOT EXISTS git_operation_results (
                    project_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    receipt_type TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,call_id),
                    FOREIGN KEY (project_id,call_id) REFERENCES calls(project_id,call_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS git_repository_claims_no_update BEFORE UPDATE ON git_repository_claims
                  BEGIN SELECT RAISE(ABORT,'Git repository claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS git_repository_claims_no_delete BEFORE DELETE ON git_repository_claims
                  BEGIN SELECT RAISE(ABORT,'Git repository claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS git_repositories_no_update BEFORE UPDATE ON git_repositories
                  BEGIN SELECT RAISE(ABORT,'Git repository identities are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS git_repositories_no_delete BEFORE DELETE ON git_repositories
                  BEGIN SELECT RAISE(ABORT,'Git repository identities cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS git_workspace_claims_no_update BEFORE UPDATE ON git_workspace_claims
                  BEGIN SELECT RAISE(ABORT,'Git workspace claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS git_workspace_claims_no_delete BEFORE DELETE ON git_workspace_claims
                  BEGIN SELECT RAISE(ABORT,'Git workspace claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS git_workspace_states_no_update BEFORE UPDATE ON git_workspace_states
                  BEGIN SELECT RAISE(ABORT,'Git workspace states are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS git_workspace_states_no_delete BEFORE DELETE ON git_workspace_states
                  BEGIN SELECT RAISE(ABORT,'Git workspace states cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS git_workspace_heads_no_delete BEFORE DELETE ON git_workspace_heads
                  BEGIN SELECT RAISE(ABORT,'Git workspace heads cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS git_operation_claims_no_update BEFORE UPDATE ON git_operation_claims
                  BEGIN SELECT RAISE(ABORT,'Git operation claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS git_operation_claims_no_delete BEFORE DELETE ON git_operation_claims
                  BEGIN SELECT RAISE(ABORT,'Git operation claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS git_operation_results_no_update BEFORE UPDATE ON git_operation_results
                  BEGIN SELECT RAISE(ABORT,'Git operation results are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS git_operation_results_no_delete BEFORE DELETE ON git_operation_results
                  BEGIN SELECT RAISE(ABORT,'Git operation results cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def capability_ref(operation: str) -> CapabilityRef:
        if operation not in _OPERATIONS:
            raise GitContractError("repository operation is unsupported")
        return CapabilityRef(f"git.{operation}", "1.0.0")

    @staticmethod
    def _implementation_ref(project_ref: ProjectRef, operation: str) -> CapabilityImplementationRef:
        identity = hashlib.sha256(f"{project_ref.value}\x00git.{operation}\x001.0.0".encode()).hexdigest()[:32]
        return CapabilityImplementationRef(project_ref, f"cimpl_{identity}")

    def register_capabilities(self, access: ProjectAccess) -> Mapping[CapabilityRef, CapabilityImplementation]:
        self._authorize(access, access.project_ref)
        registered: dict[CapabilityRef, CapabilityImplementation] = {}
        for operation in _OPERATIONS:
            capability_ref = self.capability_ref(operation)
            side_effect = (
                "EXTERNAL_WRITE"
                if operation == "push"
                else "PROJECT_WRITE"
                if operation in _MUTATING
                else "READ_ONLY"
            )
            capability = self.capabilities.register(
                Capability(
                    capability_ref,
                    f"Exact-revision Git repository {operation}",
                    input_contract={"request": "schema://minitz/git-request/1"},
                    output_contract={"receipt": "schema://minitz/git-receipt/1"},
                    side_effects=(f"git.{operation}",) if operation in _MUTATING else (),
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
                        "adapter://minitz/git",
                        "runtime://git/cli",
                        tool_ref=f"tool://minitz/git/{operation}",
                        features=("exact-revision", "isolated-candidate", "safe-config"),
                        input_features=("filesystem-root-ref", "content-ref"),
                        output_features=("artifact", "content-ref", "tool-call"),
                        side_effect_authority=side_effect,
                        resource_kinds=("runtime.host",),
                        metadata={"adapter_contract": "git-exact-revision-v1"},
                    ),
                    idempotency_key=f"git-{operation}-implementation",
                )
            registered[capability.capability_ref] = implementation
        return MappingProxyType(registered)

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectIntegrityError as exc:
            raise GitIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise GitScopeError("repository Project scope mismatch") from exc

    def _require_operation_authority(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        operation: str,
    ) -> None:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise GitAuthorityError("NodeExecutionAttempt is required")
        if attempt.node_ref.project_ref != access.project_ref:
            raise GitScopeError("repository Node attempt crossed Project scope")
        graph = self.graphs.get_graph(access, attempt.node_ref.graph_ref)
        node = next((item for item in graph.nodes if item.node_ref == attempt.node_ref), None)
        if node is None or self.capability_ref(operation) not in node.required_capabilities:
            raise GitAuthorityError("repository capability is not authorized by exact Node")
        task = self.tasks.get_task(access, attempt.task_ref)
        if task.canonical_digest != attempt.task_digest:
            raise GitIntegrityError("repository Node attempt Task digest changed")
        levels = {"READ_ONLY": 0, "CANDIDATE_WRITE": 1, "PROJECT_WRITE": 2, "EXTERNAL_SIDE_EFFECT": 3}
        required = 3 if operation == "push" else 1 if operation in _MUTATING else 0
        if levels[task.side_effect_authority] < required or levels[node.side_effect_requirement] < required:
            raise GitAuthorityError("repository operation exceeds Task or Node side-effect authority")

    @staticmethod
    def _key(value: str) -> str:
        if not isinstance(value, str) or _KEY.fullmatch(value) is None:
            raise GitContractError("idempotency_key is malformed")
        return value

    @staticmethod
    def _relative_path(value: str, *, allow_root: bool = True) -> str:
        try:
            parts = FilesystemAdapter._relative_parts(value, allow_root=allow_root)
        except FilesystemContractError as exc:
            raise GitContractError("repository path must be canonical and relative") from exc
        if any(part == ".git" for part in parts):
            raise GitAuthorityError("candidate paths may not target .git")
        return "." if not parts else PurePosixPath(*parts).as_posix()

    def _root_and_absolute(
        self,
        access: ProjectAccess,
        root_ref: FilesystemRootRef,
        relative_path: str,
        *,
        writable: bool,
        must_exist: bool,
    ) -> tuple[FilesystemRoot, Path]:
        try:
            root = self.filesystem._require_root(access, root_ref, writable=writable)
            relative = self._relative_path(relative_path)
            parts = FilesystemAdapter._relative_parts(relative)
            parent, leaf = self.filesystem._parent_descriptor(root, parts)
            try:
                if leaf is None:
                    if not must_exist:
                        raise GitConflictError("workspace cannot replace its FilesystemRoot")
                elif must_exist:
                    state = self.filesystem._safe_state(parent, leaf, allow_directory=True)
                    if not stat_module.S_ISDIR(state.st_mode):
                        raise GitContractError("repository path is not a directory")
                else:
                    try:
                        self.filesystem._safe_state(parent, leaf, allow_directory=True)
                    except FilesystemNotFoundError:
                        pass
                    else:
                        raise GitConflictError("candidate workspace path already exists")
            finally:
                os.close(parent)
            if root.canonical_path is None:
                raise GitIntegrityError("FilesystemRoot lacks canonical path evidence")
            absolute = Path(root.canonical_path).joinpath(*parts)
            return root, absolute
        except FilesystemAuthorityError as exc:
            raise GitAuthorityError("repository FilesystemRoot is not authorized") from exc
        except FilesystemError as exc:
            if isinstance(exc, FilesystemNotFoundError):
                raise GitNotFoundError("repository path was not found") from exc
            raise GitIntegrityError("repository FilesystemRoot failed verification") from exc

    @staticmethod
    def _safe_git_prefix() -> tuple[str, ...]:
        return (
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "commit.gpgSign=false",
            "-c",
            "tag.gpgSign=false",
        )

    def _git(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        root_ref: FilesystemRootRef,
        working_directory: str,
        argv: Sequence[str],
        idempotency_material: str,
        stdin_ref: ContentRef | None = None,
        environment: Mapping[str, str] = MappingProxyType({}),
        timeout_seconds: float = 120.0,
        output_limit: int = 64 * 1024 * 1024,
    ) -> ProcessResult:
        digest = hashlib.sha256(idempotency_material.encode()).hexdigest()[:40]
        overrides = {
            "GIT_ASKPASS": "/bin/false",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C.UTF-8",
            **dict(environment),
        }
        request = ProcessExecutionRequest(
            access.project_ref,
            root_ref,
            working_directory,
            self.git_executable,
            (*self._safe_git_prefix(), *tuple(argv)),
            inherited_environment=("LANG",),
            environment_overrides=overrides,
            stdin_ref=stdin_ref,
            timeout_seconds=timeout_seconds,
            termination_grace_seconds=1.0,
            stdout_limit_bytes=output_limit,
            stderr_limit_bytes=output_limit,
            network_policy=NetworkPolicy.INHERIT,
        )
        result = self.process.execute(
            access,
            attempt,
            request,
            idempotency_key=f"git-proc-{digest}",
        )
        if result.status is not ProcessStatus.SUCCEEDED:
            reason = result.stderr_preview.strip() or result.failure.value if result.failure is not None else "unknown"
            raise GitConflictError(f"Git command failed: {reason}")
        return result

    def _decode(self, result: ProcessResult, name: str) -> str:
        try:
            return self.object_store.read(result.stdout_ref).decode("utf-8")
        except (ObjectStorageError, UnicodeDecodeError) as exc:
            raise GitIntegrityError(f"Git {name} output failed verification") from exc

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
            raise GitAuthorityError("exact Run execution authority is unavailable")
        return result

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
        self._key(idempotency_key)
        self._require_operation_authority(access, attempt, operation)
        request_ref = self.object_store.put(_json(dict(payload)).encode(), media_type=_REQUEST_MEDIA_TYPE)
        implementation_ref = self._implementation_ref(access.project_ref, operation)
        try:
            implementation = self.implementations.get(access, implementation_ref)
        except RoutingNotFoundError as exc:
            raise GitAuthorityError("Git implementation is not registered") from exc
        digest = _digest({"attempt": attempt.record_sha256, "operation": operation, "key": idempotency_key})
        try:
            call = self.calls.start_tool_call(
                access,
                attempt,
                idempotency_key=f"git-start-{digest[:46]}",
                capability_ref=self.capability_ref(operation),
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
            raise GitAuthorityError("Git ToolCall authority was rejected") from exc
        except CallConflictError as exc:
            raise GitConflictError("Git ToolCall idempotency conflicts") from exc
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
                "SELECT * FROM git_operation_claims WHERE project_id=? AND node_attempt_id=? AND operation=? AND idempotency_key=?",
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
                    raise GitConflictError("Git operation idempotency identity changed")
                connection.commit()
                return _StartedOperation(call, request_ref, False)
            if call.status != "RUNNING":
                raise GitIntegrityError("terminal Git ToolCall lost its immutable claim")
            connection.execute(
                "INSERT INTO git_operation_claims VALUES (?,?,?,?,?,?,?,?,?)",
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
            raise GitConflictError("Git operation claim conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _complete_operation(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        started: _StartedOperation,
        *,
        operation: str,
        idempotency_key: str,
        receipt_payload: Mapping[str, object],
        source_refs: Sequence[ContentRef],
    ) -> tuple[ToolCall, Artifact, ContentRef, str]:
        manifest_ref = self.object_store.put(_json(dict(receipt_payload)).encode(), media_type=_RECEIPT_MEDIA_TYPE)
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
            role=f"git.{operation}.receipt",
            content_ref=manifest_ref,
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=unique_sources,
            derivation_type=f"git.{operation}",
            metadata={
                "media_type": manifest_ref.media_type,
                "schema_ref": "schema://minitz/git-receipt/1",
                "schema_version": "1.0.0",
            },
        )
        digest = _digest({"attempt": attempt.record_sha256, "operation": operation, "key": idempotency_key})
        try:
            call = self.calls.finish_tool_call(
                access,
                attempt,
                started.call.call_ref,
                idempotency_key=f"git-finish-{digest[:45]}",
                status="SUCCEEDED",
                output_refs=(manifest_ref, artifact.artifact_ref),
                usage=None,
                cost=None,
                failure_category=None,
                failure_reason=None,
                failure_evidence_refs=(),
            )
        except CallAuthorityError as exc:
            raise GitAuthorityError("Git completion authority was rejected") from exc
        except CallConflictError as exc:
            raise GitConflictError("Git completion conflicts") from exc
        if call.completed_at is None:
            raise GitIntegrityError("successful Git ToolCall lacks completion time")
        return call, artifact, manifest_ref, call.completed_at

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
                idempotency_key=f"git-finish-{digest[:45]}",
                status="FAILED",
                output_refs=(),
                usage=None,
                cost=None,
                failure_category="GIT_ADAPTER_FAILURE",
                failure_reason="Git adapter failed closed",
                failure_evidence_refs=(),
            )
        except (CallAuthorityError, CallConflictError):
            return

    @staticmethod
    def _status_paths(payload: bytes) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        staged: set[str] = set()
        unstaged: set[str] = set()
        untracked: set[str] = set()
        records = payload.split(b"\x00")
        index = 0
        while index < len(records):
            record = records[index]
            index += 1
            if not record:
                continue
            try:
                text = record.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise GitIntegrityError("Git status contains non-UTF-8 paths") from exc
            if text.startswith("? "):
                untracked.add(GitAdapter._relative_path(text[2:], allow_root=False))
                continue
            if text.startswith("! "):
                continue
            fields = text.split(" ")
            if fields[0] not in {"1", "2", "u"} or len(fields) < 9:
                raise GitIntegrityError("Git porcelain status is malformed")
            xy = fields[1]
            path = GitAdapter._relative_path(fields[-1], allow_root=False)
            if xy[0] != ".":
                staged.add(path)
            if xy[1] != ".":
                unstaged.add(path)
            if fields[0] == "2":
                index += 1
        return tuple(sorted(staged)), tuple(sorted(unstaged)), tuple(sorted(untracked))

    def _inspect_exact(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        root_ref: FilesystemRootRef,
        path: str,
        material: str,
    ) -> tuple[str, str, ProcessResult, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[ToolCallRef, ...]]:
        head = self._git(
            access,
            attempt,
            root_ref=root_ref,
            working_directory=path,
            argv=("rev-parse", "--verify", "HEAD^{commit}"),
            idempotency_material=f"{material}-head",
        )
        commit = self._decode(head, "HEAD").strip()
        tree_result = self._git(
            access,
            attempt,
            root_ref=root_ref,
            working_directory=path,
            argv=("rev-parse", "--verify", "HEAD^{tree}"),
            idempotency_material=f"{material}-tree",
        )
        tree = self._decode(tree_result, "tree").strip()
        status = self._git(
            access,
            attempt,
            root_ref=root_ref,
            working_directory=path,
            argv=("status", "--porcelain=v2", "-z", "--untracked-files=all", "--ignore-submodules=none"),
            idempotency_material=f"{material}-status",
        )
        staged, unstaged, untracked = self._status_paths(self.object_store.read(status.stdout_ref))
        return commit, tree, status, staged, unstaged, untracked, (
            head.tool_call_ref,
            tree_result.tool_call_ref,
            status.tool_call_ref,
        )

    @staticmethod
    def _parse_tree(payload: bytes, object_format: str) -> tuple[dict[str, str], tuple[tuple[str, str], ...]]:
        submodules: dict[str, str] = {}
        attributes: list[tuple[str, str]] = []
        for record in payload.split(b"\x00"):
            if not record:
                continue
            try:
                metadata, raw_path = record.split(b"\t", 1)
                mode, kind, object_id = metadata.decode("ascii").split(" ")
                path = raw_path.decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                raise GitIntegrityError("Git tree listing is malformed") from exc
            canonical = GitAdapter._relative_path(path, allow_root=False)
            _object_id(object_id, "tree object", object_format)
            if mode == "160000" and kind == "commit":
                submodules[canonical] = object_id
            if PurePosixPath(canonical).name == ".gitattributes" and kind == "blob":
                attributes.append((canonical, object_id))
        return submodules, tuple(attributes)

    def _preflight_repository(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        root_ref: FilesystemRootRef,
        path: str,
        commit: str,
        material: str,
    ) -> tuple[str, str, Mapping[str, str], ContentRef, tuple[ToolCallRef, ...]]:
        format_result = self._git(
            access,
            attempt,
            root_ref=root_ref,
            working_directory=path,
            argv=("rev-parse", "--show-object-format"),
            idempotency_material=f"{material}-format",
        )
        object_format = self._decode(format_result, "object format").strip()
        if object_format not in {"sha1", "sha256"}:
            raise GitContractError("repository object format is unsupported")
        _object_id(commit, "expected commit", object_format)
        commit_result = self._git(
            access,
            attempt,
            root_ref=root_ref,
            working_directory=path,
            argv=("rev-parse", "--verify", f"{commit}^{{commit}}"),
            idempotency_material=f"{material}-commit",
        )
        observed_commit = self._decode(commit_result, "commit").strip()
        if observed_commit != commit:
            raise GitConflictError("repository did not resolve the exact expected commit")
        tree_result = self._git(
            access,
            attempt,
            root_ref=root_ref,
            working_directory=path,
            argv=("rev-parse", "--verify", f"{commit}^{{tree}}"),
            idempotency_material=f"{material}-tree",
        )
        tree = self._decode(tree_result, "tree").strip()
        _object_id(tree, "repository tree", object_format)
        config_result = self._git(
            access,
            attempt,
            root_ref=root_ref,
            working_directory=path,
            argv=("config", "--local", "--null", "--list"),
            idempotency_material=f"{material}-config",
        )
        config_payload = self.object_store.read(config_result.stdout_ref)
        for raw_entry in config_payload.split(b"\x00"):
            if not raw_entry:
                continue
            key = raw_entry.split(b"\n", 1)[0].decode("utf-8", errors="strict").lower()
            if (
                key in _DANGEROUS_CONFIG_EXACT
                or key.startswith("filter.")
                or key.startswith("diff.")
                or key.endswith(".uploadpack")
                or key.endswith(".receivepack")
                or (key.startswith("url.") and key.endswith(".insteadof"))
            ):
                raise GitAuthorityError(f"unsafe repository Git config is rejected: {key}")
        listing = self._git(
            access,
            attempt,
            root_ref=root_ref,
            working_directory=path,
            argv=("ls-tree", "-rz", "--full-tree", commit),
            idempotency_material=f"{material}-tree-list",
        )
        submodules, attribute_blobs = self._parse_tree(self.object_store.read(listing.stdout_ref), object_format)
        calls = [
            format_result.tool_call_ref,
            commit_result.tool_call_ref,
            tree_result.tool_call_ref,
            config_result.tool_call_ref,
            listing.tool_call_ref,
        ]
        for index, (attribute_path, object_id) in enumerate(attribute_blobs):
            attribute = self._git(
                access,
                attempt,
                root_ref=root_ref,
                working_directory=path,
                argv=("cat-file", "blob", object_id),
                idempotency_material=f"{material}-attributes-{index}",
            )
            calls.append(attribute.tool_call_ref)
            text = self.object_store.read(attribute.stdout_ref).decode("utf-8", errors="replace")
            for line in text.splitlines():
                meaningful = line.split("#", 1)[0]
                if re.search(r"(?:^|\s)(?:filter|diff|merge)(?:=|\s|$)", meaningful):
                    raise GitAuthorityError(f"unsafe Git attributes are rejected: {attribute_path}")
        return object_format, tree, MappingProxyType(submodules), config_result.stdout_ref, tuple(calls)

    @staticmethod
    def _root_ref(value: object, project_ref: ProjectRef) -> FilesystemRootRef:
        if not isinstance(value, str):
            raise GitIntegrityError("persisted FilesystemRootRef is malformed")
        prefix = f"filesystem-root://{project_ref.value}/"
        if not value.startswith(prefix):
            raise GitScopeError("persisted FilesystemRootRef crossed Project scope")
        try:
            return FilesystemRootRef(project_ref, value.removeprefix(prefix))
        except (TypeError, ValueError, FilesystemError) as exc:
            raise GitIntegrityError("persisted FilesystemRootRef is malformed") from exc

    @staticmethod
    def _content_ref(value: object) -> ContentRef:
        if not isinstance(value, dict):
            raise GitIntegrityError("persisted ContentRef is malformed")
        try:
            return ContentRef(
                cast(str, value["algorithm"]),
                cast(str, value["digest"]),
                cast(int, value["size_bytes"]),
                cast(str, value["media_type"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GitIntegrityError("persisted ContentRef is malformed") from exc

    @staticmethod
    def _tool_call_ref(value: object, project_ref: ProjectRef) -> ToolCallRef:
        if not isinstance(value, str):
            raise GitIntegrityError("persisted ToolCallRef is malformed")
        prefix = f"tool-call://{project_ref.value}/"
        if not value.startswith(prefix):
            raise GitScopeError("persisted ToolCallRef crossed Project scope")
        try:
            return ToolCallRef(project_ref, value.removeprefix(prefix))
        except (TypeError, ValueError) as exc:
            raise GitIntegrityError("persisted ToolCallRef is malformed") from exc

    @staticmethod
    def _artifact_ref(value: object, project_ref: ProjectRef) -> ArtifactRef:
        if not isinstance(value, str):
            raise GitIntegrityError("persisted ArtifactRef is malformed")
        prefix = f"artifact://{project_ref.value}/"
        if not value.startswith(prefix):
            raise GitScopeError("persisted ArtifactRef crossed Project scope")
        parts = value.removeprefix(prefix).split("/")
        if len(parts) != 2:
            raise GitIntegrityError("persisted ArtifactRef is malformed")
        try:
            return ArtifactRef(project_ref, parts[0], int(parts[1]))
        except (TypeError, ValueError) as exc:
            raise GitIntegrityError("persisted ArtifactRef is malformed") from exc

    def _repository_from_payload(self, payload: object, project_ref: ProjectRef) -> RepositoryRef:
        if not isinstance(payload, dict) or payload.get("project_ref") != project_ref.value:
            raise GitIntegrityError("persisted RepositoryRef is malformed")
        try:
            return RepositoryRef(
                cast(str, payload["repository_id"]),
                project_ref,
                self._root_ref(payload["root_ref"], project_ref),
                cast(str, payload["relative_path"]),
                cast(str, payload["object_format"]),
                cast(str, payload["commit_sha"]),
                cast(str, payload["tree_sha"]),
                cast(dict[str, str], payload["submodules"]),
                cast(str, payload["config_sha256"]),
                cast(str, payload["registered_at"]),
            )
        except (KeyError, TypeError, ValueError, GitAdapterError) as exc:
            raise GitIntegrityError("persisted RepositoryRef is malformed") from exc

    def _repository_by_id(self, access: ProjectAccess, repository_id: str) -> RepositoryRef:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM git_repositories WHERE project_id=? AND repository_id=?",
                (access.project_ref.value, repository_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise GitIntegrityError("repository registry history is missing")
        try:
            repository = self._repository_from_payload(json.loads(cast(str, row["repository_json"])), access.project_ref)
        except json.JSONDecodeError as exc:
            raise GitIntegrityError("repository registry JSON is malformed") from exc
        if not hmac.compare_digest(cast(str, row["record_sha256"]), repository.record_sha256):
            raise GitIntegrityError("repository registry evidence changed")
        return repository

    def _workspace_from_payload(self, payload: object, project_ref: ProjectRef) -> RepositoryWorkspaceRef:
        if not isinstance(payload, dict) or payload.get("project_ref") != project_ref.value:
            raise GitIntegrityError("persisted RepositoryWorkspaceRef is malformed")
        try:
            return RepositoryWorkspaceRef(
                cast(str, payload["workspace_id"]),
                project_ref,
                cast(str, payload["repository_id"]),
                self._root_ref(payload["root_ref"], project_ref),
                cast(str, payload["relative_path"]),
                cast(str, payload["base_commit_sha"]),
                cast(str, payload["base_tree_sha"]),
                cast(str, payload["current_commit_sha"]),
                cast(str, payload["current_tree_sha"]),
                cast(int, payload["generation"]),
                cast(str, payload["created_at"]),
            )
        except (KeyError, TypeError, ValueError, GitAdapterError) as exc:
            raise GitIntegrityError("persisted RepositoryWorkspaceRef is malformed") from exc

    def _database_now(self) -> str:
        connection = self._connect()
        try:
            value = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')").fetchone()[0]
            return cast(str, value)
        finally:
            connection.close()

    def _persist_receipt(
        self,
        receipt_type: str,
        call_ref: ToolCallRef,
        payload: Mapping[str, object],
        record_sha256: str,
    ) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO git_operation_results VALUES (?,?,?,?,?)",
                (
                    call_ref.project_ref.value,
                    call_ref.call_id,
                    receipt_type,
                    _json(dict(payload)),
                    record_sha256,
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise GitConflictError("Git receipt persistence conflicts") from exc
        finally:
            connection.close()

    @staticmethod
    def _ref_identity(value: object, prefix: str) -> tuple[str, int | None]:
        if not isinstance(value, str) or not value.startswith(prefix):
            raise GitIntegrityError("persisted repository reference is malformed")
        tail = value.removeprefix(prefix)
        if "/" in tail:
            identity, generation_text = tail.split("/", 1)
            try:
                return identity, int(generation_text)
            except ValueError as exc:
                raise GitIntegrityError("persisted workspace generation is malformed") from exc
        return tail.split("@", 1)[0], None

    def get_receipt(
        self,
        access: ProjectAccess,
        call_ref: ToolCallRef,
    ) -> RepositoryInspectionReceipt | RepositoryDiffReceipt | RepositoryCommitReceipt | RepositoryPushReceipt:
        if not isinstance(call_ref, ToolCallRef):
            raise GitContractError("exact ToolCallRef is required")
        self._authorize(access, call_ref.project_ref)
        connection = self._connect()
        try:
            claim = connection.execute(
                "SELECT * FROM git_operation_claims WHERE project_id=? AND call_id=?",
                (access.project_ref.value, call_ref.call_id),
            ).fetchone()
            row = connection.execute(
                "SELECT * FROM git_operation_results WHERE project_id=? AND call_id=?",
                (access.project_ref.value, call_ref.call_id),
            ).fetchone()
        finally:
            connection.close()
        if claim is None or row is None:
            raise GitIntegrityError("Git operation claim or receipt history is missing")
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
            raise GitIntegrityError("Git operation claim digest changed")
        try:
            payload = json.loads(cast(str, row["receipt_json"]))
        except json.JSONDecodeError as exc:
            raise GitIntegrityError("Git receipt JSON is malformed") from exc
        if not isinstance(payload, dict):
            raise GitIntegrityError("Git receipt payload is malformed")
        receipt_type = cast(str, row["receipt_type"])
        try:
            process_calls = tuple(
                self._tool_call_ref(item, access.project_ref)
                for item in cast(list[object], payload["process_call_refs"])
            )
            tool_call = self._tool_call_ref(payload["tool_call_ref"], access.project_ref)
            artifact = self._artifact_ref(payload["artifact_ref"], access.project_ref)
            completed = cast(str, payload["completed_at"])
            if receipt_type == "inspection":
                repository_id, _ = self._ref_identity(
                    payload["repository_ref"],
                    f"repository://{access.project_ref.value}/",
                )
                receipt: RepositoryInspectionReceipt | RepositoryDiffReceipt | RepositoryCommitReceipt | RepositoryPushReceipt = RepositoryInspectionReceipt(
                    self._repository_by_id(access, repository_id),
                    cast(str, payload["head_commit_sha"]),
                    cast(str, payload["head_tree_sha"]),
                    self._content_ref(payload["status_ref"]),
                    tuple(cast(list[str], payload["staged_paths"])),
                    tuple(cast(list[str], payload["unstaged_paths"])),
                    tuple(cast(list[str], payload["untracked_paths"])),
                    process_calls,
                    tool_call,
                    artifact,
                    completed,
                )
            elif receipt_type == "diff":
                workspace_id, generation = self._ref_identity(
                    payload["workspace_ref"],
                    f"repository-workspace://{access.project_ref.value}/",
                )
                if generation is None:
                    raise GitIntegrityError("persisted diff workspace generation is missing")
                receipt = RepositoryDiffReceipt(
                    self._get_workspace_generation(access, workspace_id, generation),
                    self._content_ref(payload["staged_diff_ref"]),
                    self._content_ref(payload["unstaged_diff_ref"]),
                    self._content_ref(payload["untracked_manifest_ref"]),
                    tuple(cast(list[str], payload["untracked_paths"])),
                    process_calls,
                    tool_call,
                    artifact,
                    completed,
                )
            elif receipt_type == "commit":
                workspace_id, generation = self._ref_identity(
                    payload["workspace_ref"],
                    f"repository-workspace://{access.project_ref.value}/",
                )
                if generation is None:
                    raise GitIntegrityError("persisted commit workspace generation is missing")
                receipt = RepositoryCommitReceipt(
                    self._get_workspace_generation(access, workspace_id, generation),
                    cast(str, payload["parent_commit_sha"]),
                    cast(str, payload["parent_tree_sha"]),
                    cast(str, payload["commit_sha"]),
                    cast(str, payload["tree_sha"]),
                    self._artifact_ref(payload["diff_artifact_ref"], access.project_ref),
                    process_calls,
                    tool_call,
                    artifact,
                    completed,
                )
            elif receipt_type == "push":
                workspace_id, generation = self._ref_identity(
                    payload["workspace_ref"],
                    f"repository-workspace://{access.project_ref.value}/",
                )
                if generation is None:
                    raise GitIntegrityError("persisted push workspace generation is missing")
                receipt = RepositoryPushReceipt(
                    self._get_workspace_generation(access, workspace_id, generation),
                    cast(str, payload["destination_url"]),
                    cast(str, payload["destination_ref"]),
                    cast(str | None, payload["before_commit_sha"]),
                    cast(str, payload["pushed_commit_sha"]),
                    cast(bool, payload["forced"]),
                    process_calls,
                    tool_call,
                    artifact,
                    completed,
                )
            else:
                raise GitIntegrityError("Git receipt type is unsupported")
        except (KeyError, TypeError, ValueError, GitAdapterError) as exc:
            if isinstance(exc, GitIntegrityError):
                raise
            raise GitIntegrityError("Git receipt payload is malformed") from exc
        if not hmac.compare_digest(cast(str, row["record_sha256"]), receipt.record_sha256):
            raise GitIntegrityError("Git receipt evidence changed")
        claim_operation = cast(str, claim["operation"])
        expected_operations = {
            "inspection": {"inspect"},
            "diff": {"apply", "diff"},
            "commit": {"commit"},
            "push": {"push"},
        }
        if claim_operation not in expected_operations[receipt_type]:
            raise GitIntegrityError("Git receipt type differs from operation claim")
        call = self.calls.get_tool_call(access, call_ref)
        if call.status != "SUCCEEDED" or call.call_ref != receipt.tool_call_ref:
            raise GitIntegrityError("Git receipt and ToolCall status differ")
        artifact_record = self.artifacts.get_artifact(access, receipt.artifact_ref)
        if artifact_record.content_ref not in call.output_refs or receipt.artifact_ref not in call.output_refs:
            raise GitIntegrityError("Git ToolCall output evidence differs")
        manifest: dict[str, object]
        content_refs: tuple[ContentRef, ...]
        if isinstance(receipt, RepositoryInspectionReceipt):
            manifest = {
                "head_commit_sha": receipt.head_commit_sha,
                "head_tree_sha": receipt.head_tree_sha,
                "operation": claim_operation,
                "process_call_refs": [item.value for item in receipt.process_call_refs],
                "repository_ref": receipt.repository_ref.value,
                "staged_paths": list(receipt.staged_paths),
                "status_ref": _content(receipt.status_ref),
                "unstaged_paths": list(receipt.unstaged_paths),
                "untracked_paths": list(receipt.untracked_paths),
            }
            content_refs = (receipt.status_ref,)
        elif isinstance(receipt, RepositoryDiffReceipt):
            manifest = {
                "operation": claim_operation,
                "process_call_refs": [item.value for item in receipt.process_call_refs],
                "staged_diff_ref": _content(receipt.staged_diff_ref),
                "unstaged_diff_ref": _content(receipt.unstaged_diff_ref),
                "untracked_manifest_ref": _content(receipt.untracked_manifest_ref),
                "untracked_paths": list(receipt.untracked_paths),
                "workspace_ref": receipt.workspace_ref.value,
            }
            content_refs = (
                receipt.staged_diff_ref,
                receipt.unstaged_diff_ref,
                receipt.untracked_manifest_ref,
            )
        elif isinstance(receipt, RepositoryCommitReceipt):
            manifest = {
                "commit_sha": receipt.commit_sha,
                "diff_artifact_ref": receipt.diff_artifact_ref.value,
                "operation": claim_operation,
                "parent_commit_sha": receipt.parent_commit_sha,
                "parent_tree_sha": receipt.parent_tree_sha,
                "process_call_refs": [item.value for item in receipt.process_call_refs],
                "tree_sha": receipt.tree_sha,
                "workspace_ref": receipt.workspace_ref.value,
            }
            self.artifacts.get_artifact(access, receipt.diff_artifact_ref)
            content_refs = ()
        else:
            manifest = {
                "before_commit_sha": receipt.before_commit_sha,
                "destination_ref": receipt.destination_ref,
                "destination_url": receipt.destination_url,
                "forced": receipt.forced,
                "operation": claim_operation,
                "process_call_refs": [item.value for item in receipt.process_call_refs],
                "pushed_commit_sha": receipt.pushed_commit_sha,
                "workspace_ref": receipt.workspace_ref.value,
            }
            content_refs = ()
        try:
            artifact_manifest = self.object_store.read(artifact_record.content_ref)
        except ObjectStorageError as exc:
            raise GitIntegrityError("Git receipt Artifact manifest failed verification") from exc
        if artifact_manifest != _json(manifest).encode():
            raise GitIntegrityError("Git receipt and immutable Artifact manifest differ")
        for process_call_ref in receipt.process_call_refs:
            process_call = self.calls.get_tool_call(access, process_call_ref)
            if process_call.status != "SUCCEEDED":
                raise GitIntegrityError("Git process ToolCall evidence is not successful")
        for content_ref in (request_ref, artifact_record.content_ref, *content_refs):
            try:
                self.object_store.verify(content_ref)
            except ObjectStorageError as exc:
                raise GitIntegrityError("Git receipt ContentRef failed verification") from exc
        return receipt

    def get_repository(self, access: ProjectAccess, repository_ref: RepositoryRef) -> RepositoryRef:
        if not isinstance(repository_ref, RepositoryRef):
            raise GitContractError("exact RepositoryRef is required")
        self._authorize(access, repository_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM git_repositories WHERE project_id=? AND repository_id=?",
                (repository_ref.project_ref.value, repository_ref.repository_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise GitIntegrityError("repository registry history is missing")
        try:
            payload = json.loads(cast(str, row["repository_json"]))
        except json.JSONDecodeError as exc:
            raise GitIntegrityError("repository registry JSON is malformed") from exc
        observed = self._repository_from_payload(payload, access.project_ref)
        if (
            observed != repository_ref
            or not hmac.compare_digest(cast(str, row["record_sha256"]), observed.record_sha256)
        ):
            raise GitIntegrityError("RepositoryRef evidence changed")
        return observed

    def register_repository(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        root_ref: FilesystemRootRef,
        relative_path: str,
        expected_commit_sha: str,
        expected_tree_sha: str,
        idempotency_key: str,
    ) -> RepositoryRef:
        self._authorize(access, root_ref.project_ref)
        self._key(idempotency_key)
        path = self._relative_path(relative_path)
        _object_id(expected_commit_sha, "expected commit")
        _object_id(expected_tree_sha, "expected tree")
        self._root_and_absolute(access, root_ref, path, writable=True, must_exist=True)
        semantic = _digest(
            {
                "commit": expected_commit_sha,
                "path": path,
                "project": access.project_ref.value,
                "root": root_ref.value,
                "tree": expected_tree_sha,
            }
        )
        connection = self._connect()
        try:
            prior = connection.execute(
                "SELECT * FROM git_repository_claims WHERE project_id=? AND idempotency_key=?",
                (access.project_ref.value, idempotency_key),
            ).fetchone()
            if prior is not None:
                if not hmac.compare_digest(cast(str, prior["semantic_sha256"]), semantic):
                    raise GitConflictError("repository registration idempotency changed")
                repository_id = cast(str, prior["repository_id"])
                row = connection.execute(
                    "SELECT repository_json FROM git_repositories WHERE project_id=? AND repository_id=?",
                    (access.project_ref.value, repository_id),
                ).fetchone()
                if row is None:
                    raise GitIntegrityError("repository claim lost registry evidence")
                return self._repository_from_payload(json.loads(cast(str, row[0])), access.project_ref)
        finally:
            connection.close()
        payload = {
            "expected_commit_sha": expected_commit_sha,
            "expected_tree_sha": expected_tree_sha,
            "relative_path": path,
            "root_ref": root_ref.value,
        }
        started = self._start_operation(
            access,
            attempt,
            operation="inspect",
            idempotency_key=idempotency_key,
            payload=payload,
        )
        try:
            object_format, tree, submodules, config_ref, process_calls = self._preflight_repository(
                access,
                attempt,
                root_ref=root_ref,
                path=path,
                commit=expected_commit_sha,
                material=f"register-{semantic}",
            )
            if tree != expected_tree_sha:
                raise GitConflictError("expected repository tree differs from exact commit tree")
            repository = RepositoryRef(
                f"repo_{uuid4().hex}",
                access.project_ref,
                root_ref,
                path,
                object_format,
                expected_commit_sha,
                tree,
                submodules,
                config_ref.digest,
                self._database_now(),
            )
            receipt_payload = {
                "operation": "register_repository",
                "process_call_refs": [item.value for item in process_calls],
                "repository": repository.payload(),
            }
            self._complete_operation(
                access,
                attempt,
                started,
                operation="inspect",
                idempotency_key=idempotency_key,
                receipt_payload=receipt_payload,
                source_refs=(config_ref,),
            )
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO git_repositories VALUES (?,?,?,?)",
                    (
                        access.project_ref.value,
                        repository.repository_id,
                        _json(repository.payload()),
                        repository.record_sha256,
                    ),
                )
                connection.execute(
                    "INSERT INTO git_repository_claims VALUES (?,?,?,?)",
                    (access.project_ref.value, idempotency_key, semantic, repository.repository_id),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise GitConflictError("repository registry conflicts") from exc
            finally:
                connection.close()
            return repository
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="inspect",
                idempotency_key=idempotency_key,
            )
            raise

    def inspect(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        repository_ref: RepositoryRef,
        *,
        idempotency_key: str,
    ) -> RepositoryInspectionReceipt:
        repository = self.get_repository(access, repository_ref)
        payload = {"repository_ref": repository.value}
        started = self._start_operation(
            access,
            attempt,
            operation="inspect",
            idempotency_key=idempotency_key,
            payload=payload,
        )
        if not started.first_claim:
            return cast(RepositoryInspectionReceipt, self.get_receipt(access, started.call.call_ref))
        try:
            head, tree, status, staged, unstaged, untracked, process_calls = self._inspect_exact(
                access,
                attempt,
                root_ref=repository.root_ref,
                path=repository.relative_path,
                material=f"inspect-{repository.repository_id}-{idempotency_key}",
            )
            receipt_basis = {
                "head_commit_sha": head,
                "head_tree_sha": tree,
                "operation": "inspect",
                "process_call_refs": [item.value for item in process_calls],
                "repository_ref": repository.value,
                "staged_paths": list(staged),
                "status_ref": _content(status.stdout_ref),
                "unstaged_paths": list(unstaged),
                "untracked_paths": list(untracked),
            }
            call, artifact, _, completed = self._complete_operation(
                access,
                attempt,
                started,
                operation="inspect",
                idempotency_key=idempotency_key,
                receipt_payload=receipt_basis,
                source_refs=(status.stdout_ref,),
            )
            receipt = RepositoryInspectionReceipt(
                repository,
                head,
                tree,
                status.stdout_ref,
                staged,
                unstaged,
                untracked,
                process_calls,
                call.call_ref,
                artifact.artifact_ref,
                completed,
            )
            self._persist_receipt("inspection", receipt.tool_call_ref, receipt.payload(), receipt.record_sha256)
            return receipt
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="inspect",
                idempotency_key=idempotency_key,
            )
            raise

    status = inspect

    def _persist_workspace(self, workspace: RepositoryWorkspaceRef, *, initial: bool) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if initial:
                connection.execute(
                    "INSERT INTO git_workspace_states VALUES (?,?,?,?,?)",
                    (
                        workspace.project_ref.value,
                        workspace.workspace_id,
                        workspace.generation,
                        _json(workspace.payload()),
                        workspace.record_sha256,
                    ),
                )
                connection.execute(
                    "INSERT INTO git_workspace_heads VALUES (?,?,?,?)",
                    (
                        workspace.project_ref.value,
                        workspace.workspace_id,
                        workspace.generation,
                        workspace.record_sha256,
                    ),
                )
            else:
                prior_generation = workspace.generation - 1
                prior = connection.execute(
                    "SELECT * FROM git_workspace_heads WHERE project_id=? AND workspace_id=?",
                    (workspace.project_ref.value, workspace.workspace_id),
                ).fetchone()
                if prior is None or prior["generation"] != prior_generation:
                    raise GitConflictError("workspace generation changed concurrently")
                connection.execute(
                    "INSERT INTO git_workspace_states VALUES (?,?,?,?,?)",
                    (
                        workspace.project_ref.value,
                        workspace.workspace_id,
                        workspace.generation,
                        _json(workspace.payload()),
                        workspace.record_sha256,
                    ),
                )
                changed = connection.execute(
                    "UPDATE git_workspace_heads SET generation=?,record_sha256=? WHERE project_id=? AND workspace_id=? AND generation=? AND record_sha256=?",
                    (
                        workspace.generation,
                        workspace.record_sha256,
                        workspace.project_ref.value,
                        workspace.workspace_id,
                        prior_generation,
                        prior["record_sha256"],
                    ),
                )
                if changed.rowcount != 1:
                    raise GitConflictError("workspace head changed concurrently")
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise GitConflictError("workspace evidence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _get_workspace_generation(
        self,
        access: ProjectAccess,
        workspace_id: str,
        generation: int,
    ) -> RepositoryWorkspaceRef:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM git_workspace_states WHERE project_id=? AND workspace_id=? AND generation=?",
                (access.project_ref.value, workspace_id, generation),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise GitIntegrityError("workspace state history is missing")
        try:
            workspace = self._workspace_from_payload(json.loads(cast(str, row["workspace_json"])), access.project_ref)
        except json.JSONDecodeError as exc:
            raise GitIntegrityError("workspace state JSON is malformed") from exc
        if not hmac.compare_digest(cast(str, row["record_sha256"]), workspace.record_sha256):
            raise GitIntegrityError("workspace state evidence changed")
        return workspace

    def get_workspace(
        self,
        access: ProjectAccess,
        workspace_ref: RepositoryWorkspaceRef,
        *,
        require_current: bool = True,
    ) -> RepositoryWorkspaceRef:
        if not isinstance(workspace_ref, RepositoryWorkspaceRef):
            raise GitContractError("exact RepositoryWorkspaceRef is required")
        self._authorize(access, workspace_ref.project_ref)
        observed = self._get_workspace_generation(access, workspace_ref.workspace_id, workspace_ref.generation)
        if observed != workspace_ref:
            raise GitIntegrityError("RepositoryWorkspaceRef evidence changed")
        if require_current:
            connection = self._connect()
            try:
                head = connection.execute(
                    "SELECT * FROM git_workspace_heads WHERE project_id=? AND workspace_id=?",
                    (access.project_ref.value, workspace_ref.workspace_id),
                ).fetchone()
            finally:
                connection.close()
            if head is None:
                raise GitIntegrityError("workspace head history is missing")
            if head["generation"] != workspace_ref.generation or not hmac.compare_digest(
                cast(str, head["record_sha256"]), workspace_ref.record_sha256
            ):
                raise GitConflictError("RepositoryWorkspaceRef is stale")
        return observed

    def get_current_workspace(
        self,
        access: ProjectAccess,
        workspace_ref: RepositoryWorkspaceRef,
    ) -> RepositoryWorkspaceRef:
        """Resolve the immutable supplied generation to its exact current generation."""

        observed = self.get_workspace(access, workspace_ref, require_current=False)
        connection = self._connect()
        try:
            head = connection.execute(
                "SELECT * FROM git_workspace_heads WHERE project_id=? AND workspace_id=?",
                (access.project_ref.value, observed.workspace_id),
            ).fetchone()
        finally:
            connection.close()
        if head is None:
            raise GitIntegrityError("workspace head history is missing")
        current = self._get_workspace_generation(
            access,
            observed.workspace_id,
            cast(int, head["generation"]),
        )
        if not hmac.compare_digest(cast(str, head["record_sha256"]), current.record_sha256):
            raise GitIntegrityError("workspace head evidence changed")
        return current

    def export_workspace_bundle(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace_ref: RepositoryWorkspaceRef,
        *,
        idempotency_key: str,
    ) -> tuple[ContentRef | None, tuple[ToolCallRef, ...]]:
        """Persist candidate-only commit objects without duplicating the exact base."""

        self._key(idempotency_key)
        workspace = self.get_current_workspace(access, workspace_ref)
        self._require_operation_authority(access, attempt, "read")
        if workspace.current_commit_sha == workspace.base_commit_sha:
            return None, ()
        material = hashlib.sha256(
            f"{workspace.value}:{idempotency_key}".encode()
        ).hexdigest()[:40]
        bundle_path = f".git/minitz-snapshot-{material}.bundle"
        created = self._git(
            access,
            attempt,
            root_ref=workspace.root_ref,
            working_directory=workspace.relative_path,
            argv=("bundle", "create", bundle_path, "HEAD", f"^{workspace.base_commit_sha}"),
            idempotency_material=f"bundle-export-{material}-create",
            timeout_seconds=600,
        )
        listed = self._git(
            access,
            attempt,
            root_ref=workspace.root_ref,
            working_directory=workspace.relative_path,
            argv=("bundle", "list-heads", bundle_path),
            idempotency_material=f"bundle-export-{material}-list",
        )
        if self._decode(listed, "bundle heads").strip() != f"{workspace.current_commit_sha} HEAD":
            raise GitIntegrityError("candidate bundle HEAD differs from durable workspace authority")
        verified = self._git(
            access,
            attempt,
            root_ref=workspace.root_ref,
            working_directory=workspace.relative_path,
            argv=("bundle", "verify", bundle_path),
            idempotency_material=f"bundle-export-{material}-verify",
        )
        read = self.filesystem.read(
            access,
            attempt,
            root_ref=workspace.root_ref,
            path=f"{workspace.relative_path}/{bundle_path}",
            media_type="application/x-git-bundle",
            idempotency_key=f"git-bundle-read-{material}",
        )
        removed = self.filesystem.remove(
            access,
            attempt,
            root_ref=workspace.root_ref,
            path=f"{workspace.relative_path}/{bundle_path}",
            media_type="application/x-git-bundle",
            idempotency_key=f"git-bundle-remove-{material}",
        )
        return read.output_ref, (
            created.tool_call_ref,
            listed.tool_call_ref,
            verified.tool_call_ref,
            read.tool_call_ref,
            removed.tool_call_ref,
        )

    def restore_workspace_snapshot(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace_ref: RepositoryWorkspaceRef,
        *,
        expected_head_commit: str,
        expected_head_tree: str,
        bundle_ref: ContentRef | None,
        staged_diff_ref: ContentRef,
        unstaged_diff_ref: ContentRef,
        idempotency_key: str,
    ) -> tuple[RepositoryWorkspaceRef, tuple[ToolCallRef, ...]]:
        """Restore exact candidate HEAD, worktree changes, and staged index state."""

        self._key(idempotency_key)
        _object_id(expected_head_commit, "snapshot HEAD")
        _object_id(expected_head_tree, "snapshot HEAD tree")
        for ref in (staged_diff_ref, unstaged_diff_ref):
            try:
                self.object_store.verify(ref)
            except ObjectStorageError as exc:
                raise GitIntegrityError("snapshot Git diff failed verification") from exc
        workspace = self.get_current_workspace(access, workspace_ref)
        if workspace.current_commit_sha != workspace.base_commit_sha:
            raise GitConflictError("snapshot restore requires an exact clean base workspace")
        self._require_operation_authority(access, attempt, "workspace")
        material = hashlib.sha256(
            f"{workspace.value}:{expected_head_commit}:{idempotency_key}".encode()
        ).hexdigest()[:40]
        calls: list[ToolCallRef] = []
        if expected_head_commit != workspace.base_commit_sha:
            if bundle_ref is None:
                raise GitIntegrityError("candidate commit snapshot lacks its durable bundle")
            try:
                self.object_store.verify(bundle_ref)
            except ObjectStorageError as exc:
                raise GitIntegrityError("candidate commit bundle failed verification") from exc
            bundle_path = f".git/minitz-restore-{material}.bundle"
            written = self.filesystem.write(
                access,
                attempt,
                root_ref=workspace.root_ref,
                path=f"{workspace.relative_path}/{bundle_path}",
                content_ref=bundle_ref,
                idempotency_key=f"git-bundle-write-{material}",
            )
            calls.append(written.tool_call_ref)
            verified = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("bundle", "verify", bundle_path),
                idempotency_material=f"bundle-restore-{material}-verify",
            )
            listed = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("bundle", "list-heads", bundle_path),
                idempotency_material=f"bundle-restore-{material}-list",
            )
            if self._decode(listed, "bundle heads").strip() != f"{expected_head_commit} HEAD":
                raise GitIntegrityError("candidate bundle does not contain the exact snapshot HEAD")
            fetched = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("fetch", "--no-tags", "--no-recurse-submodules", bundle_path, "HEAD"),
                idempotency_material=f"bundle-restore-{material}-fetch",
                timeout_seconds=600,
            )
            checked_out = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("checkout", "--detach", "--force", "--no-recurse-submodules", expected_head_commit),
                idempotency_material=f"bundle-restore-{material}-checkout",
                timeout_seconds=600,
            )
            removed = self.filesystem.remove(
                access,
                attempt,
                root_ref=workspace.root_ref,
                path=f"{workspace.relative_path}/{bundle_path}",
                media_type="application/x-git-bundle",
                idempotency_key=f"git-bundle-clean-{material}",
            )
            calls.extend(
                (
                    verified.tool_call_ref,
                    listed.tool_call_ref,
                    fetched.tool_call_ref,
                    checked_out.tool_call_ref,
                    removed.tool_call_ref,
                )
            )
        elif bundle_ref is not None:
            raise GitIntegrityError("base-HEAD snapshot unexpectedly contains a candidate bundle")

        if staged_diff_ref.size_bytes:
            staged_worktree = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("apply", "--recount", "-"),
                stdin_ref=staged_diff_ref,
                idempotency_material=f"snapshot-restore-{material}-staged-worktree",
            )
            calls.append(staged_worktree.tool_call_ref)
        if unstaged_diff_ref.size_bytes:
            unstaged_worktree = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("apply", "--recount", "-"),
                stdin_ref=unstaged_diff_ref,
                idempotency_material=f"snapshot-restore-{material}-unstaged-worktree",
            )
            calls.append(unstaged_worktree.tool_call_ref)
        if staged_diff_ref.size_bytes:
            staged_index = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("apply", "--cached", "--recount", "-"),
                stdin_ref=staged_diff_ref,
                idempotency_material=f"snapshot-restore-{material}-staged-index",
            )
            calls.append(staged_index.tool_call_ref)
        observed_head, observed_tree, _, _, _, _, observed_calls = self._inspect_exact(
            access,
            attempt,
            root_ref=workspace.root_ref,
            path=workspace.relative_path,
            material=f"snapshot-restore-{material}-inspect",
        )
        calls.extend(observed_calls)
        if observed_head != expected_head_commit or observed_tree != expected_head_tree:
            raise GitIntegrityError("restored candidate HEAD/tree differs from durable snapshot")
        if expected_head_commit == workspace.current_commit_sha:
            return workspace, tuple(calls)
        current = RepositoryWorkspaceRef(
            workspace.workspace_id,
            workspace.project_ref,
            workspace.repository_id,
            workspace.root_ref,
            workspace.relative_path,
            workspace.base_commit_sha,
            workspace.base_tree_sha,
            expected_head_commit,
            expected_head_tree,
            workspace.generation + 1,
            workspace.created_at,
        )
        self._persist_workspace(current, initial=False)
        return current, tuple(calls)

    def create_workspace(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        repository_ref: RepositoryRef,
        *,
        candidate_root_ref: FilesystemRootRef,
        relative_path: str,
        require_source_head: bool = True,
        idempotency_key: str,
    ) -> RepositoryWorkspaceRef:
        repository = self.get_repository(access, repository_ref)
        if candidate_root_ref.project_ref != access.project_ref:
            raise GitScopeError("candidate FilesystemRoot crossed Project scope")
        self._key(idempotency_key)
        path = self._relative_path(relative_path, allow_root=False)
        semantic = _digest(
            {
                "candidate_root_ref": candidate_root_ref.value,
                "path": path,
                "repository_ref": repository.value,
                "require_source_head": require_source_head,
            }
        )
        connection = self._connect()
        try:
            prior = connection.execute(
                "SELECT * FROM git_workspace_claims WHERE project_id=? AND idempotency_key=?",
                (access.project_ref.value, idempotency_key),
            ).fetchone()
            if prior is not None:
                if not hmac.compare_digest(cast(str, prior["semantic_sha256"]), semantic):
                    raise GitConflictError("workspace creation idempotency changed")
                workspace_id = cast(str, prior["workspace_id"])
                return self._get_workspace_generation(access, workspace_id, 1)
        finally:
            connection.close()
        _, source_absolute = self._root_and_absolute(
            access,
            repository.root_ref,
            repository.relative_path,
            writable=True,
            must_exist=True,
        )
        _, candidate_absolute = self._root_and_absolute(
            access,
            candidate_root_ref,
            path,
            writable=True,
            must_exist=False,
        )
        payload = {
            "candidate_root_ref": candidate_root_ref.value,
            "relative_path": path,
            "repository_ref": repository.value,
            "require_source_head": require_source_head,
        }
        started = self._start_operation(
            access,
            attempt,
            operation="workspace",
            idempotency_key=idempotency_key,
            payload=payload,
        )
        try:
            process_calls: list[ToolCallRef] = []
            source_refs: list[ContentRef] = []
            if require_source_head:
                head, tree, status, _, _, _, calls = self._inspect_exact(
                    access,
                    attempt,
                    root_ref=repository.root_ref,
                    path=repository.relative_path,
                    material=f"workspace-source-{semantic}",
                )
                process_calls.extend(calls)
                source_refs.append(status.stdout_ref)
                if head != repository.commit_sha or tree != repository.tree_sha:
                    raise GitConflictError("repository source HEAD is stale for current-base workspace authority")
            workspace_id = f"rws_{uuid4().hex}"
            template_path = f".minitz-template-{workspace_id}"
            self.filesystem.mkdir(
                access,
                attempt,
                root_ref=candidate_root_ref,
                path=template_path,
                idempotency_key=f"git-template-{workspace_id[4:]}",
            )
            candidate_root = self.filesystem.get_root(access, candidate_root_ref)
            if candidate_root.canonical_path is None:
                raise GitIntegrityError("candidate FilesystemRoot lacks canonical path")
            template_absolute = Path(candidate_root.canonical_path) / template_path
            clone = self._git(
                access,
                attempt,
                root_ref=candidate_root_ref,
                working_directory=".",
                argv=(
                    "clone",
                    "--no-local",
                    "--no-hardlinks",
                    "--no-checkout",
                    f"--template={template_absolute}",
                    "--upload-pack=/usr/bin/git-upload-pack",
                    "--",
                    str(source_absolute),
                    str(candidate_absolute),
                ),
                idempotency_material=f"workspace-{workspace_id}-{semantic}-clone",
                timeout_seconds=600,
            )
            process_calls.append(clone.tool_call_ref)
            source_refs.extend((clone.stdout_ref, clone.stderr_ref))
            checkout = self._git(
                access,
                attempt,
                root_ref=candidate_root_ref,
                working_directory=path,
                argv=("checkout", "--detach", "--no-recurse-submodules", repository.commit_sha),
                idempotency_material=f"workspace-{workspace_id}-{semantic}-checkout",
                timeout_seconds=600,
            )
            process_calls.append(checkout.tool_call_ref)
            source_refs.extend((checkout.stdout_ref, checkout.stderr_ref))
            remove_remote = self._git(
                access,
                attempt,
                root_ref=candidate_root_ref,
                working_directory=path,
                argv=("remote", "remove", "origin"),
                idempotency_material=f"workspace-{workspace_id}-{semantic}-remove-origin",
            )
            process_calls.append(remove_remote.tool_call_ref)
            head, tree, status, staged, unstaged, untracked, calls = self._inspect_exact(
                access,
                attempt,
                root_ref=candidate_root_ref,
                path=path,
                material=f"workspace-{workspace_id}-{semantic}-verify",
            )
            process_calls.extend(calls)
            source_refs.append(status.stdout_ref)
            if (
                head != repository.commit_sha
                or tree != repository.tree_sha
                or staged
                or unstaged
                or untracked
            ):
                raise GitIntegrityError("isolated candidate did not materialize the exact clean base")
            workspace = RepositoryWorkspaceRef(
                workspace_id,
                access.project_ref,
                repository.repository_id,
                candidate_root_ref,
                path,
                repository.commit_sha,
                repository.tree_sha,
                repository.commit_sha,
                repository.tree_sha,
                1,
                self._database_now(),
            )
            receipt_payload = {
                "operation": "create_workspace",
                "process_call_refs": [item.value for item in process_calls],
                "workspace": workspace.payload(),
            }
            self._complete_operation(
                access,
                attempt,
                started,
                operation="workspace",
                idempotency_key=idempotency_key,
                receipt_payload=receipt_payload,
                source_refs=tuple(source_refs),
            )
            self._persist_workspace(workspace, initial=True)
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO git_workspace_claims VALUES (?,?,?,?)",
                    (access.project_ref.value, idempotency_key, semantic, workspace.workspace_id),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise GitConflictError("workspace claim conflicts") from exc
            finally:
                connection.close()
            return workspace
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="workspace",
                idempotency_key=idempotency_key,
            )
            raise

    def _workspace_current_identity(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace: RepositoryWorkspaceRef,
        material: str,
    ) -> tuple[str, str, ProcessResult, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[ToolCallRef, ...]]:
        observed = self._inspect_exact(
            access,
            attempt,
            root_ref=workspace.root_ref,
            path=workspace.relative_path,
            material=material,
        )
        if observed[0] != workspace.current_commit_sha or observed[1] != workspace.current_tree_sha:
            raise GitConflictError("candidate workspace HEAD differs from exact durable authority")
        return observed

    def _capture_diff(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace: RepositoryWorkspaceRef,
        *,
        operation: str,
        idempotency_key: str,
        started: _StartedOperation,
        preceding_calls: Sequence[ToolCallRef] = (),
        preceding_refs: Sequence[ContentRef] = (),
        excluded_path_components: tuple[str, ...] = (),
        excluded_path_names: tuple[str, ...] = (),
        excluded_path_prefixes: tuple[str, ...] = (),
    ) -> RepositoryDiffReceipt:
        _, _, status, staged_paths, unstaged_paths, untracked_paths, identity_calls = self._workspace_current_identity(
            access,
            attempt,
            workspace,
            f"diff-{workspace.workspace_id}-{idempotency_key}-identity",
        )

        def excluded(path: str) -> bool:
            parts = PurePosixPath(path).parts
            return (
                any(part in excluded_path_components for part in parts)
                or PurePosixPath(path).name in excluded_path_names
                or any(path == prefix or path.startswith(f"{prefix}/") for prefix in excluded_path_prefixes)
            )

        if any(excluded(path) for path in (*staged_paths, *unstaged_paths)):
            raise GitAuthorityError("tracked secret/cache path changes cannot enter a durable Git snapshot")
        staged = self._git(
            access,
            attempt,
            root_ref=workspace.root_ref,
            working_directory=workspace.relative_path,
            argv=("diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", "--"),
            idempotency_material=f"diff-{workspace.workspace_id}-{idempotency_key}-staged",
        )
        unstaged = self._git(
            access,
            attempt,
            root_ref=workspace.root_ref,
            working_directory=workspace.relative_path,
            argv=("diff", "--binary", "--no-ext-diff", "--no-textconv", "--"),
            idempotency_material=f"diff-{workspace.workspace_id}-{idempotency_key}-unstaged",
        )
        untracked_result = self._git(
            access,
            attempt,
            root_ref=workspace.root_ref,
            working_directory=workspace.relative_path,
            argv=("ls-files", "--others", "--exclude-standard", "-z", "--"),
            idempotency_material=f"diff-{workspace.workspace_id}-{idempotency_key}-untracked",
        )
        try:
            observed_untracked_paths = tuple(
                sorted(
                    self._relative_path(item.decode("utf-8"), allow_root=False)
                    for item in self.object_store.read(untracked_result.stdout_ref).split(b"\x00")
                    if item
                )
            )
        except UnicodeDecodeError as exc:
            raise GitIntegrityError("untracked Git paths are not UTF-8") from exc
        if observed_untracked_paths != untracked_paths:
            raise GitConflictError("candidate untracked paths changed during diff capture")
        untracked_paths = tuple(path for path in observed_untracked_paths if not excluded(path))
        manifest: dict[str, object] = {}
        untracked_refs: list[ContentRef] = []
        for index, untracked_path in enumerate(untracked_paths):
            operation_receipt = self.filesystem.read(
                access,
                attempt,
                root_ref=workspace.root_ref,
                path=f"{workspace.relative_path}/{untracked_path}",
                media_type="application/octet-stream",
                idempotency_key=f"git-untracked-{hashlib.sha256(f'{idempotency_key}-{index}'.encode()).hexdigest()[:40]}",
            )
            manifest[untracked_path] = _content(operation_receipt.output_ref)
            untracked_refs.append(operation_receipt.output_ref)
        untracked_manifest = self.object_store.put(
            _json(manifest).encode(),
            media_type=_UNTRACKED_MEDIA_TYPE,
        )
        process_calls = (
            *tuple(preceding_calls),
            *identity_calls,
            staged.tool_call_ref,
            unstaged.tool_call_ref,
            untracked_result.tool_call_ref,
        )
        receipt_basis = {
            "operation": operation,
            "process_call_refs": [item.value for item in process_calls],
            "staged_diff_ref": _content(staged.stdout_ref),
            "unstaged_diff_ref": _content(unstaged.stdout_ref),
            "untracked_manifest_ref": _content(untracked_manifest),
            "untracked_paths": list(untracked_paths),
            "workspace_ref": workspace.value,
        }
        call, artifact, _, completed = self._complete_operation(
            access,
            attempt,
            started,
            operation=operation,
            idempotency_key=idempotency_key,
            receipt_payload=receipt_basis,
            source_refs=(
                *tuple(preceding_refs),
                status.stdout_ref,
                staged.stdout_ref,
                unstaged.stdout_ref,
                untracked_manifest,
                *tuple(untracked_refs),
            ),
        )
        receipt = RepositoryDiffReceipt(
            workspace,
            staged.stdout_ref,
            unstaged.stdout_ref,
            untracked_manifest,
            untracked_paths,
            process_calls,
            call.call_ref,
            artifact.artifact_ref,
            completed,
        )
        self._persist_receipt("diff", receipt.tool_call_ref, receipt.payload(), receipt.record_sha256)
        return receipt

    def diff(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace_ref: RepositoryWorkspaceRef,
        *,
        idempotency_key: str,
        excluded_path_components: Sequence[str] = (),
        excluded_path_names: Sequence[str] = (),
        excluded_path_prefixes: Sequence[str] = (),
    ) -> RepositoryDiffReceipt:
        if not isinstance(workspace_ref, RepositoryWorkspaceRef):
            raise GitContractError("exact RepositoryWorkspaceRef is required")
        self._authorize(access, workspace_ref.project_ref)
        components = tuple(sorted(set(excluded_path_components)))
        names = tuple(sorted(set(excluded_path_names)))
        prefixes = tuple(sorted(set(self._relative_path(item, allow_root=False) for item in excluded_path_prefixes)))
        if any(not isinstance(item, str) or not item or "/" in item or "\\" in item for item in (*components, *names)):
            raise GitContractError("Git snapshot exclusions are malformed")
        started = self._start_operation(
            access,
            attempt,
            operation="diff",
            idempotency_key=idempotency_key,
            payload={
                "excluded_path_components": list(components),
                "excluded_path_names": list(names),
                "excluded_path_prefixes": list(prefixes),
                "workspace_ref": workspace_ref.value,
            },
        )
        if not started.first_claim:
            return cast(RepositoryDiffReceipt, self.get_receipt(access, started.call.call_ref))
        try:
            workspace = self.get_workspace(access, workspace_ref)
            return self._capture_diff(
                access,
                attempt,
                workspace,
                operation="diff",
                idempotency_key=idempotency_key,
                started=started,
                excluded_path_components=components,
                excluded_path_names=names,
                excluded_path_prefixes=prefixes,
            )
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="diff",
                idempotency_key=idempotency_key,
            )
            raise

    def apply_patch(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace_ref: RepositoryWorkspaceRef,
        *,
        patch_ref: ContentRef,
        expected_commit_sha: str,
        idempotency_key: str,
    ) -> RepositoryDiffReceipt:
        if not isinstance(workspace_ref, RepositoryWorkspaceRef):
            raise GitContractError("exact RepositoryWorkspaceRef is required")
        self._authorize(access, workspace_ref.project_ref)
        _object_id(expected_commit_sha, "expected patch base")
        try:
            self.object_store.verify(patch_ref)
        except ObjectStorageError as exc:
            raise GitIntegrityError("patch ContentRef failed verification") from exc
        started = self._start_operation(
            access,
            attempt,
            operation="apply",
            idempotency_key=idempotency_key,
            payload={
                "expected_commit_sha": expected_commit_sha,
                "patch_ref": patch_ref.value,
                "workspace_ref": workspace_ref.value,
            },
            input_refs=(patch_ref,),
        )
        if not started.first_claim:
            return cast(RepositoryDiffReceipt, self.get_receipt(access, started.call.call_ref))
        try:
            workspace = self.get_workspace(access, workspace_ref)
            if expected_commit_sha != workspace.current_commit_sha:
                raise GitConflictError("patch expected base is stale")
            self._workspace_current_identity(
                access,
                attempt,
                workspace,
                f"apply-{workspace.workspace_id}-{idempotency_key}-identity",
            )
            numstat = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("apply", "--numstat", "-z", "--recount", "-"),
                stdin_ref=patch_ref,
                idempotency_material=f"apply-{workspace.workspace_id}-{idempotency_key}-numstat",
            )
            paths: list[str] = []
            for record in self.object_store.read(numstat.stdout_ref).split(b"\x00"):
                if not record:
                    continue
                try:
                    raw_path = record.rsplit(b"\t", 1)[1].decode("utf-8")
                except (IndexError, UnicodeDecodeError) as exc:
                    raise GitIntegrityError("patch path summary is malformed") from exc
                path = self._relative_path(raw_path, allow_root=False)
                if PurePosixPath(path).name in {".gitattributes", ".gitmodules"}:
                    raise GitAuthorityError("patch may not change Git execution-policy files")
                paths.append(path)
            if not paths:
                raise GitContractError("patch contains no bounded file changes")
            check = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("apply", "--check", "--recount", "-"),
                stdin_ref=patch_ref,
                idempotency_material=f"apply-{workspace.workspace_id}-{idempotency_key}-check",
            )
            applied = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("apply", "--recount", "--whitespace=nowarn", "-"),
                stdin_ref=patch_ref,
                idempotency_material=f"apply-{workspace.workspace_id}-{idempotency_key}-apply",
            )
            return self._capture_diff(
                access,
                attempt,
                workspace,
                operation="apply",
                idempotency_key=idempotency_key,
                started=started,
                preceding_calls=(numstat.tool_call_ref, check.tool_call_ref, applied.tool_call_ref),
                preceding_refs=(patch_ref, numstat.stdout_ref, check.stderr_ref, applied.stderr_ref),
            )
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="apply",
                idempotency_key=idempotency_key,
            )
            raise

    @staticmethod
    def _reject_policy_path_changes(paths: Sequence[str]) -> None:
        for path in paths:
            if PurePosixPath(path).name in {".gitattributes", ".gitmodules"} or ".git" in PurePosixPath(path).parts:
                raise GitAuthorityError("candidate may not change Git execution-policy or metadata paths")

    def commit(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace_ref: RepositoryWorkspaceRef,
        *,
        expected_parent_commit_sha: str,
        message: str,
        author_name: str,
        author_email: str,
        idempotency_key: str,
    ) -> RepositoryCommitReceipt:
        if not isinstance(workspace_ref, RepositoryWorkspaceRef):
            raise GitContractError("exact RepositoryWorkspaceRef is required")
        self._authorize(access, workspace_ref.project_ref)
        _object_id(expected_parent_commit_sha, "expected parent commit")
        _text(message, "commit message", 64 * 1024)
        _text(author_name, "commit author name", 512)
        _text(author_email, "commit author email", 512)
        if "@" not in author_email or "\n" in author_email or "\r" in author_email:
            raise GitContractError("commit author email is malformed")
        started = self._start_operation(
            access,
            attempt,
            operation="commit",
            idempotency_key=idempotency_key,
            payload={
                "author_email": author_email,
                "author_name": author_name,
                "expected_parent_commit_sha": expected_parent_commit_sha,
                "message": message,
                "workspace_ref": workspace_ref.value,
            },
        )
        if not started.first_claim:
            return cast(RepositoryCommitReceipt, self.get_receipt(access, started.call.call_ref))
        try:
            workspace = self.get_workspace(access, workspace_ref)
            if expected_parent_commit_sha != workspace.current_commit_sha:
                raise GitConflictError("commit expected parent is stale")
            head, parent_tree, status, staged_paths, unstaged_paths, untracked_paths, identity_calls = self._workspace_current_identity(
                access,
                attempt,
                workspace,
                f"commit-{workspace.workspace_id}-{idempotency_key}-identity",
            )
            if head != expected_parent_commit_sha:
                raise GitConflictError("candidate HEAD changed before commit")
            self._reject_policy_path_changes((*staged_paths, *unstaged_paths, *untracked_paths))
            if not (staged_paths or unstaged_paths or untracked_paths):
                raise GitConflictError("candidate has no changes to commit")
            diff_key = f"commit-diff-{hashlib.sha256(idempotency_key.encode()).hexdigest()[:40]}"
            diff_receipt = self.diff(
                access,
                attempt,
                workspace,
                idempotency_key=diff_key,
            )
            add = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("add", "--all", "--", "."),
                idempotency_material=f"commit-{workspace.workspace_id}-{idempotency_key}-add",
            )
            tree_result = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("write-tree",),
                idempotency_material=f"commit-{workspace.workspace_id}-{idempotency_key}-write-tree",
            )
            tree = self._decode(tree_result, "candidate tree").strip()
            _object_id(tree, "candidate tree")
            if tree == parent_tree:
                raise GitConflictError("candidate commit tree did not change")
            commit_result = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("commit-tree", tree, "-p", expected_parent_commit_sha, "-m", message),
                environment={
                    "GIT_AUTHOR_EMAIL": author_email,
                    "GIT_AUTHOR_NAME": author_name,
                    "GIT_COMMITTER_EMAIL": author_email,
                    "GIT_COMMITTER_NAME": author_name,
                },
                idempotency_material=f"commit-{workspace.workspace_id}-{idempotency_key}-commit-tree",
            )
            commit_sha = self._decode(commit_result, "commit identity").strip()
            _object_id(commit_sha, "candidate commit")
            update = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("update-ref", "--no-deref", "HEAD", commit_sha, expected_parent_commit_sha),
                idempotency_material=f"commit-{workspace.workspace_id}-{idempotency_key}-update-ref",
            )
            observed_commit, observed_tree, verify_status, verify_staged, verify_unstaged, verify_untracked, verify_calls = self._inspect_exact(
                access,
                attempt,
                root_ref=workspace.root_ref,
                path=workspace.relative_path,
                material=f"commit-{workspace.workspace_id}-{idempotency_key}-verify",
            )
            if (
                observed_commit != commit_sha
                or observed_tree != tree
                or verify_staged
                or verify_unstaged
                or verify_untracked
            ):
                raise GitIntegrityError("candidate commit observation differs from exact created commit/tree")
            current = RepositoryWorkspaceRef(
                workspace.workspace_id,
                workspace.project_ref,
                workspace.repository_id,
                workspace.root_ref,
                workspace.relative_path,
                workspace.base_commit_sha,
                workspace.base_tree_sha,
                commit_sha,
                tree,
                workspace.generation + 1,
                workspace.created_at,
            )
            self._persist_workspace(current, initial=False)
            process_calls = (
                *identity_calls,
                add.tool_call_ref,
                tree_result.tool_call_ref,
                commit_result.tool_call_ref,
                update.tool_call_ref,
                *verify_calls,
            )
            receipt_basis = {
                "commit_sha": commit_sha,
                "diff_artifact_ref": diff_receipt.artifact_ref.value,
                "operation": "commit",
                "parent_commit_sha": expected_parent_commit_sha,
                "parent_tree_sha": parent_tree,
                "process_call_refs": [item.value for item in process_calls],
                "tree_sha": tree,
                "workspace_ref": current.value,
            }
            call, artifact, _, completed = self._complete_operation(
                access,
                attempt,
                started,
                operation="commit",
                idempotency_key=idempotency_key,
                receipt_payload=receipt_basis,
                source_refs=(
                    status.stdout_ref,
                    diff_receipt.staged_diff_ref,
                    diff_receipt.unstaged_diff_ref,
                    diff_receipt.untracked_manifest_ref,
                    add.stdout_ref,
                    tree_result.stdout_ref,
                    commit_result.stdout_ref,
                    update.stdout_ref,
                    verify_status.stdout_ref,
                ),
            )
            receipt = RepositoryCommitReceipt(
                current,
                expected_parent_commit_sha,
                parent_tree,
                commit_sha,
                tree,
                diff_receipt.artifact_ref,
                process_calls,
                call.call_ref,
                artifact.artifact_ref,
                completed,
            )
            self._persist_receipt("commit", receipt.tool_call_ref, receipt.payload(), receipt.record_sha256)
            return receipt
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="commit",
                idempotency_key=idempotency_key,
            )
            raise

    @staticmethod
    def _remote_requires_network(destination_url: str) -> bool:
        return bool(re.match(r"(?:https?|ssh|git)://", destination_url)) or (
            ":" in destination_url and not destination_url.startswith("/")
        )

    def push(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace_ref: RepositoryWorkspaceRef,
        *,
        destination_url: str,
        destination_ref: str,
        expected_remote_commit_sha: str | None,
        explicit_authorization: bool,
        allow_network: bool,
        allow_force: bool = False,
        idempotency_key: str,
    ) -> RepositoryPushReceipt:
        if not isinstance(workspace_ref, RepositoryWorkspaceRef):
            raise GitContractError("exact RepositoryWorkspaceRef is required")
        self._authorize(access, workspace_ref.project_ref)
        _text(destination_url, "push destination URL", 4096)
        if not isinstance(destination_ref, str) or _REMOTE_REF.fullmatch(destination_ref) is None:
            raise GitContractError("push destination must be an exact branch ref")
        if expected_remote_commit_sha is not None:
            _object_id(expected_remote_commit_sha, "expected remote commit")
        if explicit_authorization is not True:
            raise GitAuthorityError("push requires explicit external side-effect authorization")
        if allow_force:
            raise GitAuthorityError("force push is not supported by this adapter contract")
        if self._remote_requires_network(destination_url) and not allow_network:
            raise GitAuthorityError("network push requires explicit network policy authorization")
        started = self._start_operation(
            access,
            attempt,
            operation="push",
            idempotency_key=idempotency_key,
            payload={
                "allow_force": allow_force,
                "allow_network": allow_network,
                "destination_ref": destination_ref,
                "destination_url": destination_url,
                "expected_remote_commit_sha": expected_remote_commit_sha,
                "explicit_authorization": explicit_authorization,
                "workspace_ref": workspace_ref.value,
            },
        )
        if not started.first_claim:
            return cast(RepositoryPushReceipt, self.get_receipt(access, started.call.call_ref))
        try:
            workspace = self.get_workspace(access, workspace_ref)
            self._workspace_current_identity(
                access,
                attempt,
                workspace,
                f"push-{workspace.workspace_id}-{idempotency_key}-identity",
            )
            before = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("ls-remote", "--refs", "--", destination_url, destination_ref),
                idempotency_material=f"push-{workspace.workspace_id}-{idempotency_key}-before",
                timeout_seconds=300,
            )
            before_text = self._decode(before, "remote pre-push identity").strip()
            before_commit = before_text.split("\t", 1)[0] if before_text else None
            if before_commit != expected_remote_commit_sha:
                raise GitConflictError("push destination ref differs from expected remote commit")
            pushed = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=(
                    "push",
                    "--porcelain",
                    "--no-verify",
                    "--",
                    destination_url,
                    f"{workspace.current_commit_sha}:{destination_ref}",
                ),
                idempotency_material=f"push-{workspace.workspace_id}-{idempotency_key}-push",
                timeout_seconds=600,
            )
            after = self._git(
                access,
                attempt,
                root_ref=workspace.root_ref,
                working_directory=workspace.relative_path,
                argv=("ls-remote", "--refs", "--", destination_url, destination_ref),
                idempotency_material=f"push-{workspace.workspace_id}-{idempotency_key}-after",
                timeout_seconds=300,
            )
            after_text = self._decode(after, "remote post-push identity").strip()
            after_commit = after_text.split("\t", 1)[0] if after_text else None
            if after_commit != workspace.current_commit_sha:
                raise GitIntegrityError("push did not produce the exact observed destination commit")
            process_calls = (before.tool_call_ref, pushed.tool_call_ref, after.tool_call_ref)
            receipt_basis = {
                "before_commit_sha": before_commit,
                "destination_ref": destination_ref,
                "destination_url": destination_url,
                "forced": False,
                "operation": "push",
                "process_call_refs": [item.value for item in process_calls],
                "pushed_commit_sha": workspace.current_commit_sha,
                "workspace_ref": workspace.value,
            }
            call, artifact, _, completed = self._complete_operation(
                access,
                attempt,
                started,
                operation="push",
                idempotency_key=idempotency_key,
                receipt_payload=receipt_basis,
                source_refs=(before.stdout_ref, pushed.stdout_ref, pushed.stderr_ref, after.stdout_ref),
            )
            receipt = RepositoryPushReceipt(
                workspace,
                destination_url,
                destination_ref,
                before_commit,
                workspace.current_commit_sha,
                False,
                process_calls,
                call.call_ref,
                artifact.artifact_ref,
                completed,
            )
            self._persist_receipt("push", receipt.tool_call_ref, receipt.payload(), receipt.record_sha256)
            return receipt
        except Exception:
            self._fail_operation(
                access,
                attempt,
                started,
                operation="push",
                idempotency_key=idempotency_key,
            )
            raise

    def read_exact(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        repository_ref: RepositoryRef,
        *,
        path: str,
        idempotency_key: str,
    ) -> ContentRef:
        self._key(idempotency_key)
        self._require_operation_authority(access, attempt, "read")
        repository = self.get_repository(access, repository_ref)
        canonical = self._relative_path(path, allow_root=False)
        listing = self._git(
            access,
            attempt,
            root_ref=repository.root_ref,
            working_directory=repository.relative_path,
            argv=("ls-tree", "-z", "--full-tree", repository.commit_sha, "--", f":(literal){canonical}"),
            idempotency_material=f"read-{repository.repository_id}-{idempotency_key}-listing",
        )
        records = tuple(item for item in self.object_store.read(listing.stdout_ref).split(b"\x00") if item)
        if len(records) != 1:
            raise GitNotFoundError("exact repository path was not found as one tree entry")
        try:
            metadata, raw_path = records[0].split(b"\t", 1)
            _, kind, object_id = metadata.decode("ascii").split(" ")
            observed_path = raw_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise GitIntegrityError("exact repository tree entry is malformed") from exc
        if observed_path != canonical or kind != "blob":
            raise GitIntegrityError("exact repository path is not a blob identity")
        result = self._git(
            access,
            attempt,
            root_ref=repository.root_ref,
            working_directory=repository.relative_path,
            argv=("cat-file", "blob", object_id),
            idempotency_material=f"read-{repository.repository_id}-{idempotency_key}-blob",
        )
        return result.stdout_ref

    def fetch(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace_ref: RepositoryWorkspaceRef,
        *,
        source_url: str,
        source_ref: str,
        allow_network: bool,
        idempotency_key: str,
    ) -> ContentRef:
        self._key(idempotency_key)
        workspace = self.get_workspace(access, workspace_ref)
        _text(source_url, "fetch source URL")
        if not isinstance(source_ref, str) or _REF_NAME.fullmatch(source_ref) is None:
            raise GitContractError("fetch source ref is malformed")
        if self._remote_requires_network(source_url) and not allow_network:
            raise GitAuthorityError("network fetch requires explicit network policy authorization")
        self._require_operation_authority(access, attempt, "fetch")
        result = self._git(
            access,
            attempt,
            root_ref=workspace.root_ref,
            working_directory=workspace.relative_path,
            argv=("fetch", "--no-tags", "--no-recurse-submodules", "--", source_url, source_ref),
            idempotency_material=f"fetch-{workspace.workspace_id}-{idempotency_key}",
            timeout_seconds=600,
        )
        return result.stdout_ref
