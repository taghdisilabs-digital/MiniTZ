"""Durable Project-scoped candidate Workspaces and reconstructable snapshots.

Local directories are disposable materializations.  Exact Project/Task/Run/Graph/
Node authority, immutable base identities, adapter ToolCalls, and content-addressed
snapshot bytes are the durable authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
import hashlib
import hmac
import json
from pathlib import PurePosixPath, Path
import re
import sqlite3
from types import MappingProxyType
from typing import Callable, Mapping, Sequence, cast
from uuid import uuid4

from .artifact import ArtifactRef, ArtifactService, ContentRef
from .call_ledger import CallLedgerService, ToolCallRef
from .capability import CapabilityRef
from .execution import NodeExecutionAttempt, NodeExecutionService
from .filesystem import (
    FilesystemAdapter,
    FilesystemConflictError,
    FilesystemMode,
    FilesystemNotFoundError,
    FilesystemRootRef,
)
from .git_adapter import GitAdapter, RepositoryDiffReceipt, RepositoryRef, RepositoryWorkspaceRef
from .graph import GraphRef, NodeRef
from .object_store import ObjectStorageBackend, ObjectStorageError
from .project import ProjectAccess, ProjectNotFoundError, ProjectRef, ProjectScopeError, ProjectStore
from .run import RunRef
from .scheduler import ResourceAllocationRef, SchedulerError, SchedulerService
from .task import TaskRef, TaskRevisionService


class WorkspaceError(Exception):
    """Base candidate Workspace failure."""


class WorkspaceContractError(WorkspaceError, ValueError):
    """A Workspace request or persisted value is malformed."""


class WorkspaceScopeError(WorkspaceError):
    """A Workspace request crossed Project authority."""


class WorkspaceAuthorityError(WorkspaceError, PermissionError):
    """Workspace execution policy or fenced authority rejected an operation."""


class WorkspaceConflictError(WorkspaceError):
    """Workspace state changed concurrently or idempotency semantics changed."""


class WorkspaceNotFoundError(WorkspaceError):
    """Exact durable Workspace evidence was not found."""


class WorkspaceIntegrityError(WorkspaceError):
    """Workspace evidence or materialized bytes failed verification."""


class WorkspaceLostAttemptError(WorkspaceError):
    """Uncaptured local candidate mutation was lost and cannot be fabricated."""


class WorkspaceCancelledError(WorkspaceAuthorityError):
    """The Workspace no longer accepts execution results."""


class WorkspaceType(str, Enum):
    REPOSITORY = "REPOSITORY"
    FILES = "FILES"
    ASSET = "ASSET"
    BUILD = "BUILD"
    TEMPORARY = "TEMPORARY"


class WorkspaceNetworkPolicy(str, Enum):
    NONE = "NONE"
    RESTRICTED = "RESTRICTED"
    PROJECT_POLICY = "PROJECT_POLICY"


class WorkspaceLifecycleState(str, Enum):
    CREATED = "CREATED"
    MATERIALIZED = "MATERIALIZED"
    EXECUTING = "EXECUTING"
    PERSISTED = "PERSISTED"
    RECONSTRUCTED = "RECONSTRUCTED"
    CLEANED = "CLEANED"
    CANCELLED = "CANCELLED"
    LOST_UNCAPTURED = "LOST_UNCAPTURED"
    CLEANUP_FAILED = "CLEANUP_FAILED"


_ID = re.compile(r"[a-z]+_[0-9a-f]{32}")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_SHA = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]+")
_SIDE_EFFECTS = {"NONE", "PROJECT_WRITE", "EXTERNAL_SIDE_EFFECT"}
_SKIP_COMPONENTS = {".git", ".cache", ".mypy_cache", ".pytest_cache", ".venv", "__pycache__", "node_modules"}
_DEFAULT_SECRET_NAMES = {".env", "credentials", "id_dsa", "id_ed25519", "id_rsa", "service-account.json"}


def _json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise WorkspaceContractError("Workspace evidence must be canonical JSON") from exc


def _sha(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise WorkspaceContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise WorkspaceContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WorkspaceContractError(f"{name} must be timezone-aware")
    return value


def _key(value: object) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise WorkspaceContractError("idempotency_key is malformed")
    return value


def _adapter_key(*parts: object) -> str:
    return f"workspace-{hashlib.sha256(_json(list(parts)).encode()).hexdigest()[:48]}"


def _relative(value: object, *, allow_root: bool = False) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value or len(value.encode()) > 4096:
        raise WorkspaceContractError("Workspace path is malformed")
    if value == "." and allow_root:
        return value
    candidate = PurePosixPath(value)
    parts = value.split("/")
    if candidate.is_absolute() or any(part in {"", ".", ".."} or ":" in part for part in parts) or tuple(parts) != candidate.parts:
        raise WorkspaceContractError("Workspace path must be canonical and relative")
    return value


def _content_payload(ref: ContentRef | None) -> dict[str, object] | None:
    if ref is None:
        return None
    return {"algorithm": ref.algorithm, "digest": ref.digest, "media_type": ref.media_type, "size_bytes": ref.size_bytes}


def _content_from(value: Mapping[str, object]) -> ContentRef:
    return ContentRef(cast(str, value["algorithm"]), cast(str, value["digest"]), cast(int, value["size_bytes"]), cast(str, value["media_type"]))


@dataclass(frozen=True, order=True)
class WorkspaceRef:
    project_ref: ProjectRef
    workspace_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.workspace_id, str) or re.fullmatch(r"wsp_[0-9a-f]{32}", self.workspace_id) is None:
            raise WorkspaceContractError("Workspace identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "WorkspaceRef":
        return cls(project_ref, f"wsp_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"workspace://{self.project_ref.value}/{self.workspace_id}"


@dataclass(frozen=True, order=True)
class WorkspaceExecutionPolicyRef:
    project_ref: ProjectRef
    policy_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.policy_id, str) or re.fullmatch(r"wpol_[0-9a-f]{32}", self.policy_id) is None:
            raise WorkspaceContractError("Workspace policy identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "WorkspaceExecutionPolicyRef":
        return cls(project_ref, f"wpol_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"workspace-policy://{self.project_ref.value}/{self.policy_id}"


@dataclass(frozen=True, order=True)
class WorkspaceSnapshotRef:
    workspace_ref: WorkspaceRef
    sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_ref, WorkspaceRef):
            raise TypeError("workspace_ref must be WorkspaceRef")
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 1:
            raise WorkspaceContractError("Workspace snapshot sequence is malformed")

    @property
    def project_ref(self) -> ProjectRef:
        return self.workspace_ref.project_ref

    @property
    def value(self) -> str:
        return f"workspace-snapshot://{self.project_ref.value}/{self.workspace_ref.workspace_id}/{self.sequence}"


@dataclass(frozen=True, order=True)
class WorkspaceRootGrant:
    root_ref: FilesystemRootRef
    mode: str

    def __post_init__(self) -> None:
        if not isinstance(self.root_ref, FilesystemRootRef):
            raise TypeError("root_ref must be FilesystemRootRef")
        if self.mode not in {"READ_ONLY", "READ_WRITE", "TEMPORARY"}:
            raise WorkspaceContractError("Workspace root grant mode is malformed")


@dataclass(frozen=True, order=True)
class WorkspaceFileSource:
    relative_path: str
    artifact_ref: ArtifactRef

    def __post_init__(self) -> None:
        object.__setattr__(self, "relative_path", _relative(self.relative_path))
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("artifact_ref must be ArtifactRef")

    @property
    def project_ref(self) -> ProjectRef:
        return self.artifact_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {"artifact_id": self.artifact_ref.artifact_id, "artifact_revision": self.artifact_ref.revision, "kind": "FILE", "project_ref": self.project_ref.value, "relative_path": self.relative_path}


@dataclass(frozen=True)
class WorkspaceRepositorySource:
    repository_ref: RepositoryRef

    def __post_init__(self) -> None:
        if not isinstance(self.repository_ref, RepositoryRef):
            raise TypeError("repository_ref must be RepositoryRef")

    @property
    def project_ref(self) -> ProjectRef:
        return self.repository_ref.project_ref

    def payload(self) -> dict[str, object]:
        repository = self.repository_ref
        return {
            "kind": "REPOSITORY",
            "repository": repository.payload(),
            "repository_ref": repository.value,
        }


WorkspaceSource = WorkspaceFileSource | WorkspaceRepositorySource


@dataclass(frozen=True)
class WorkspaceExecutionPolicy:
    policy_ref: WorkspaceExecutionPolicyRef
    root_grants: tuple[WorkspaceRootGrant, ...]
    network_policy: WorkspaceNetworkPolicy
    restricted_destination_refs: tuple[str, ...]
    allowed_capabilities: tuple[CapabilityRef, ...]
    resource_allocation_ref: ResourceAllocationRef | None
    secret_refs: tuple[str, ...]
    secret_mount_paths: tuple[str, ...]
    side_effect_boundary: str
    timeout_seconds: float
    process_limit: int
    created_at: str
    semantic_sha256: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.policy_ref, WorkspaceExecutionPolicyRef):
            raise TypeError("policy_ref must be WorkspaceExecutionPolicyRef")
        if not isinstance(self.root_grants, tuple) or not self.root_grants or not all(isinstance(item, WorkspaceRootGrant) for item in self.root_grants):
            raise WorkspaceContractError("Workspace policy requires root grants")
        roots = tuple(sorted(set(self.root_grants), key=lambda item: item.root_ref.root_id))
        if len(roots) > 32 or any(item.root_ref.project_ref != self.project_ref for item in roots):
            raise WorkspaceScopeError("Workspace root grant crossed Project scope")
        object.__setattr__(self, "root_grants", roots)
        if not isinstance(self.network_policy, WorkspaceNetworkPolicy):
            raise WorkspaceContractError("Workspace network policy is malformed")
        destinations = tuple(sorted(set(self.restricted_destination_refs)))
        if len(destinations) > 64 or any(not isinstance(item, str) or _REF.fullmatch(item) is None for item in destinations):
            raise WorkspaceContractError("Workspace restricted destinations are malformed")
        if self.network_policy is WorkspaceNetworkPolicy.RESTRICTED and not destinations:
            raise WorkspaceContractError("RESTRICTED network requires exact destinations")
        if self.network_policy is not WorkspaceNetworkPolicy.RESTRICTED and destinations:
            raise WorkspaceContractError("Only RESTRICTED network accepts destinations")
        object.__setattr__(self, "restricted_destination_refs", destinations)
        capabilities = tuple(sorted(set(self.allowed_capabilities)))
        if len(capabilities) > 128 or not all(isinstance(item, CapabilityRef) for item in capabilities):
            raise WorkspaceContractError("Workspace allowed capabilities are malformed")
        object.__setattr__(self, "allowed_capabilities", capabilities)
        if self.resource_allocation_ref is not None and (not isinstance(self.resource_allocation_ref, ResourceAllocationRef) or self.resource_allocation_ref.project_ref != self.project_ref):
            raise WorkspaceScopeError("Workspace ResourceAllocation crossed Project scope")
        secrets = tuple(sorted(set(self.secret_refs)))
        if len(secrets) > 64 or any(not isinstance(item, str) or _REF.fullmatch(item) is None for item in secrets):
            raise WorkspaceContractError("Workspace secret refs are malformed")
        object.__setattr__(self, "secret_refs", secrets)
        mounts = tuple(sorted(set(_relative(item) for item in self.secret_mount_paths)))
        if len(mounts) > 64:
            raise WorkspaceContractError("Workspace secret mounts are unbounded")
        object.__setattr__(self, "secret_mount_paths", mounts)
        if self.side_effect_boundary not in _SIDE_EFFECTS:
            raise WorkspaceContractError("Workspace side-effect boundary is malformed")
        if not isinstance(self.timeout_seconds, (int, float)) or isinstance(self.timeout_seconds, bool) or not 0.01 <= float(self.timeout_seconds) <= 86400:
            raise WorkspaceContractError("Workspace timeout is malformed")
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))
        if not isinstance(self.process_limit, int) or isinstance(self.process_limit, bool) or not 1 <= self.process_limit <= 4096:
            raise WorkspaceContractError("Workspace process limit is malformed")
        _timestamp(self.created_at, "Workspace policy created_at")
        semantic = _sha(self.semantic_payload())
        object.__setattr__(self, "semantic_sha256", semantic)
        object.__setattr__(self, "record_sha256", _sha({"created_at": self.created_at, "policy_ref": self.policy_ref.value, "semantic_sha256": semantic}))

    @property
    def project_ref(self) -> ProjectRef:
        return self.policy_ref.project_ref

    def semantic_payload(self) -> dict[str, object]:
        return {
            "allowed_capabilities": [f"{item.capability_id}@{item.version}" for item in self.allowed_capabilities],
            "network_policy": self.network_policy.value,
            "process_limit": self.process_limit,
            "resource_allocation_ref": None if self.resource_allocation_ref is None else self.resource_allocation_ref.value,
            "restricted_destination_refs": list(self.restricted_destination_refs),
            "root_grants": [{"mode": item.mode, "root_ref": item.root_ref.value} for item in self.root_grants],
            "secret_mount_paths": list(self.secret_mount_paths),
            "secret_refs": list(self.secret_refs),
            "side_effect_boundary": self.side_effect_boundary,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True, order=True)
class WorkspaceFileEntry:
    path: str
    kind: str
    mode: int | None
    content_ref: ContentRef | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _relative(self.path))
        if self.kind not in {"directory", "file", "symlink"}:
            raise WorkspaceContractError("Workspace manifest entry kind is malformed")
        if self.kind == "file":
            if not isinstance(self.content_ref, ContentRef) or not isinstance(self.mode, int):
                raise WorkspaceContractError("Workspace file entry lacks exact content or mode")
        elif self.content_ref is not None:
            raise WorkspaceContractError("Non-file Workspace entry cannot carry content")
        if self.mode is not None and (not isinstance(self.mode, int) or isinstance(self.mode, bool) or not 0 <= self.mode <= 0o7777):
            raise WorkspaceContractError("Workspace entry mode is malformed")

    def payload(self) -> dict[str, object]:
        return {"content_ref": _content_payload(self.content_ref), "kind": self.kind, "mode": self.mode, "path": self.path}


@dataclass(frozen=True)
class Workspace:
    workspace_ref: WorkspaceRef
    task_ref: TaskRef
    run_ref: RunRef
    graph_ref: GraphRef
    node_ref: NodeRef
    node_attempt_id: str
    node_attempt_fence: int
    workspace_type: WorkspaceType
    base_sources: tuple[WorkspaceSource, ...]
    base_revision: str
    execution_policy_ref: WorkspaceExecutionPolicyRef
    resource_allocation_ref: ResourceAllocationRef | None
    candidate_root_ref: FilesystemRootRef
    relative_path: str
    repository_workspace_ref: RepositoryWorkspaceRef | None
    materialization_manifest_ref: ContentRef | None
    latest_snapshot_ref: WorkspaceSnapshotRef | None
    status: WorkspaceLifecycleState
    generation: int
    created_at: str
    updated_at: str
    state_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_ref, WorkspaceRef) or not isinstance(self.task_ref, TaskRef) or not isinstance(self.run_ref, RunRef):
            raise WorkspaceContractError("Workspace exact identity is malformed")
        if not isinstance(self.graph_ref, GraphRef) or not isinstance(self.node_ref, NodeRef):
            raise WorkspaceContractError("Workspace Graph/Node identity is malformed")
        project = self.workspace_ref.project_ref
        refs = (self.task_ref.project_ref, self.run_ref.project_ref, self.graph_ref.project_ref, self.node_ref.project_ref, self.execution_policy_ref.project_ref, self.candidate_root_ref.project_ref)
        if any(item != project for item in refs) or self.node_ref.graph_ref != self.graph_ref:
            raise WorkspaceScopeError("Workspace identity crossed Project or Graph scope")
        if not isinstance(self.node_attempt_id, str) or re.fullmatch(r"natt_[0-9a-f]{32}", self.node_attempt_id) is None or not isinstance(self.node_attempt_fence, int) or self.node_attempt_fence < 1:
            raise WorkspaceContractError("Workspace Node attempt authority is malformed")
        if not isinstance(self.workspace_type, WorkspaceType) or not isinstance(self.base_sources, tuple):
            raise WorkspaceContractError("Workspace type or sources are malformed")
        if any(not isinstance(item, (WorkspaceFileSource, WorkspaceRepositorySource)) for item in self.base_sources) or any(item.project_ref != project for item in self.base_sources):
            raise WorkspaceScopeError("Workspace base source crossed Project scope")
        if not isinstance(self.base_revision, str) or _SHA.fullmatch(self.base_revision) is None:
            raise WorkspaceContractError("Workspace base revision is not exact")
        if self.resource_allocation_ref is not None and self.resource_allocation_ref.project_ref != project:
            raise WorkspaceScopeError("Workspace ResourceAllocation crossed Project scope")
        object.__setattr__(self, "relative_path", _relative(self.relative_path))
        if self.repository_workspace_ref is not None and self.repository_workspace_ref.project_ref != project:
            raise WorkspaceScopeError("Workspace repository materialization crossed Project scope")
        if self.latest_snapshot_ref is not None and self.latest_snapshot_ref.workspace_ref != self.workspace_ref:
            raise WorkspaceScopeError("Workspace snapshot identity differs")
        if not isinstance(self.status, WorkspaceLifecycleState) or not isinstance(self.generation, int) or self.generation < 1:
            raise WorkspaceContractError("Workspace lifecycle state is malformed")
        _timestamp(self.created_at, "Workspace created_at")
        _timestamp(self.updated_at, "Workspace updated_at")
        object.__setattr__(self, "state_sha256", _sha(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.workspace_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "base_revision": self.base_revision,
            "base_sources": [item.payload() for item in self.base_sources],
            "candidate_root_ref": self.candidate_root_ref.value,
            "created_at": self.created_at,
            "execution_policy_ref": self.execution_policy_ref.value,
            "generation": self.generation,
            "graph_id": self.graph_ref.graph_id,
            "graph_revision": self.graph_ref.revision,
            "latest_snapshot_sequence": None if self.latest_snapshot_ref is None else self.latest_snapshot_ref.sequence,
            "materialization_manifest_ref": _content_payload(self.materialization_manifest_ref),
            "node_attempt_fence": self.node_attempt_fence,
            "node_attempt_id": self.node_attempt_id,
            "node_id": self.node_ref.node_id,
            "project_ref": self.project_ref.value,
            "relative_path": self.relative_path,
            "repository_workspace": None if self.repository_workspace_ref is None else self.repository_workspace_ref.payload(),
            "resource_allocation_id": None if self.resource_allocation_ref is None else self.resource_allocation_ref.allocation_id,
            "run_id": self.run_ref.run_id,
            "status": self.status.value,
            "task_id": self.task_ref.task_id,
            "task_revision": self.task_ref.revision,
            "updated_at": self.updated_at,
            "workspace_id": self.workspace_ref.workspace_id,
            "workspace_type": self.workspace_type.value,
        }


@dataclass(frozen=True)
class WorkspaceSnapshot:
    snapshot_ref: WorkspaceSnapshotRef
    workspace_generation: int
    base_revision: str
    entries: tuple[WorkspaceFileEntry, ...]
    deleted_paths: tuple[str, ...]
    manifest_ref: ContentRef
    repository_head_commit: str | None
    repository_head_tree: str | None
    staged_diff_ref: ContentRef | None
    unstaged_diff_ref: ContentRef | None
    untracked_manifest_ref: ContentRef | None
    repository_bundle_ref: ContentRef | None
    tool_call_refs: tuple[ToolCallRef, ...]
    artifact_ref: ArtifactRef
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_ref, WorkspaceSnapshotRef):
            raise TypeError("snapshot_ref must be WorkspaceSnapshotRef")
        if not isinstance(self.workspace_generation, int) or self.workspace_generation < 1:
            raise WorkspaceContractError("Workspace snapshot generation is malformed")
        if not isinstance(self.base_revision, str) or _SHA.fullmatch(self.base_revision) is None:
            raise WorkspaceContractError("Workspace snapshot base is malformed")
        entries = tuple(sorted(set(self.entries), key=lambda item: item.path))
        if len(entries) > 100_000 or len(entries) != len({item.path for item in entries}):
            raise WorkspaceContractError("Workspace snapshot entries are duplicated or unbounded")
        object.__setattr__(self, "entries", entries)
        deleted = tuple(sorted(set(_relative(item) for item in self.deleted_paths)))
        if len(deleted) > 100_000:
            raise WorkspaceContractError("Workspace deleted paths are unbounded")
        object.__setattr__(self, "deleted_paths", deleted)
        if not isinstance(self.manifest_ref, ContentRef) or not isinstance(self.artifact_ref, ArtifactRef):
            raise WorkspaceContractError("Workspace snapshot evidence is incomplete")
        project = self.snapshot_ref.project_ref
        if self.artifact_ref.project_ref != project:
            raise WorkspaceScopeError("Workspace snapshot Artifact crossed Project scope")
        repository_values = (self.repository_head_commit, self.repository_head_tree)
        if any(value is not None for value in repository_values) and not all(value is not None for value in repository_values):
            raise WorkspaceContractError("Workspace repository HEAD evidence is incomplete")
        for value in repository_values:
            if value is not None and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is None:
                raise WorkspaceContractError("Workspace repository object identity is malformed")
        diff_values = (self.staged_diff_ref, self.unstaged_diff_ref, self.untracked_manifest_ref)
        if any(value is not None for value in diff_values) and not all(value is not None for value in diff_values):
            raise WorkspaceContractError("Workspace repository diff evidence is incomplete")
        if any(value is not None and not isinstance(value, ContentRef) for value in (*diff_values, self.repository_bundle_ref)):
            raise WorkspaceContractError("Workspace repository content evidence is malformed")
        if self.repository_bundle_ref is not None and self.repository_head_commit is None:
            raise WorkspaceContractError("Workspace candidate bundle lacks repository HEAD evidence")
        calls = tuple(sorted(set(self.tool_call_refs), key=lambda item: item.call_id))
        if len(calls) > 100_000 or any(item.project_ref != project for item in calls):
            raise WorkspaceScopeError("Workspace snapshot ToolCall crossed Project scope")
        object.__setattr__(self, "tool_call_refs", calls)
        _timestamp(self.created_at, "Workspace snapshot created_at")
        object.__setattr__(self, "record_sha256", _sha(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.snapshot_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref.value,
            "base_revision": self.base_revision,
            "created_at": self.created_at,
            "deleted_paths": list(self.deleted_paths),
            "entries": [item.payload() for item in self.entries],
            "manifest_ref": _content_payload(self.manifest_ref),
            "repository_head_commit": self.repository_head_commit,
            "repository_head_tree": self.repository_head_tree,
            "repository_bundle_ref": _content_payload(self.repository_bundle_ref),
            "snapshot_ref": self.snapshot_ref.value,
            "staged_diff_ref": _content_payload(self.staged_diff_ref),
            "tool_call_refs": [item.value for item in self.tool_call_refs],
            "unstaged_diff_ref": _content_payload(self.unstaged_diff_ref),
            "untracked_manifest_ref": _content_payload(self.untracked_manifest_ref),
            "workspace_generation": self.workspace_generation,
        }


@dataclass(frozen=True)
class CandidateWorkspaceReceipt:
    workspace_ref: WorkspaceRef
    snapshot_ref: WorkspaceSnapshotRef
    base_revision: str
    candidate_manifest_ref: ContentRef
    changed_content_refs: tuple[ContentRef, ...]
    deleted_paths: tuple[str, ...]
    repository_head_commit: str | None
    repository_head_tree: str | None
    staged_diff_ref: ContentRef | None
    unstaged_diff_ref: ContentRef | None
    untracked_manifest_ref: ContentRef | None
    repository_bundle_ref: ContentRef | None
    test_artifact_refs: tuple[ArtifactRef, ...]
    tool_call_refs: tuple[ToolCallRef, ...]
    snapshot_artifact_ref: ArtifactRef
    created_at: str
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_ref, WorkspaceRef) or not isinstance(self.snapshot_ref, WorkspaceSnapshotRef):
            raise WorkspaceContractError("Candidate Workspace receipt identity is malformed")
        project = self.workspace_ref.project_ref
        if self.snapshot_ref.workspace_ref != self.workspace_ref or self.snapshot_artifact_ref.project_ref != project:
            raise WorkspaceScopeError("Candidate Workspace receipt scope differs")
        if _SHA.fullmatch(self.base_revision) is None:
            raise WorkspaceContractError("Candidate Workspace base is malformed")
        if not isinstance(self.candidate_manifest_ref, ContentRef):
            raise WorkspaceContractError("Candidate Workspace manifest identity is malformed")
        repository_values = (self.repository_head_commit, self.repository_head_tree)
        if any(value is not None for value in repository_values) and not all(value is not None for value in repository_values):
            raise WorkspaceContractError("Candidate Workspace repository HEAD evidence is incomplete")
        for value in repository_values:
            if value is not None and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is None:
                raise WorkspaceContractError("Candidate Workspace repository object identity is malformed")
        diff_values = (self.staged_diff_ref, self.unstaged_diff_ref, self.untracked_manifest_ref)
        if any(value is not None for value in diff_values) and not all(value is not None for value in diff_values):
            raise WorkspaceContractError("Candidate Workspace repository diff evidence is incomplete")
        if any(value is not None and not isinstance(value, ContentRef) for value in (*diff_values, self.repository_bundle_ref)):
            raise WorkspaceContractError("Candidate Workspace repository content evidence is malformed")
        if self.repository_bundle_ref is not None and self.repository_head_commit is None:
            raise WorkspaceContractError("Candidate Workspace bundle lacks repository HEAD evidence")
        if any(not isinstance(item, ContentRef) for item in self.changed_content_refs):
            raise WorkspaceContractError("Candidate Workspace content evidence is malformed")
        changed = tuple(sorted(set(self.changed_content_refs), key=lambda item: (item.digest, item.size_bytes, item.media_type)))
        object.__setattr__(self, "changed_content_refs", changed)
        tests = tuple(sorted(set(self.test_artifact_refs), key=lambda item: (item.artifact_id, item.revision)))
        if any(item.project_ref != project for item in tests):
            raise WorkspaceScopeError("Candidate Workspace test Artifact crossed Project scope")
        object.__setattr__(self, "test_artifact_refs", tests)
        calls = tuple(sorted(set(self.tool_call_refs), key=lambda item: item.call_id))
        if any(item.project_ref != project for item in calls):
            raise WorkspaceScopeError("Candidate Workspace ToolCall crossed Project scope")
        object.__setattr__(self, "tool_call_refs", calls)
        object.__setattr__(self, "deleted_paths", tuple(sorted(set(_relative(item) for item in self.deleted_paths))))
        _timestamp(self.created_at, "Candidate Workspace receipt created_at")
        object.__setattr__(self, "receipt_sha256", _sha(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.workspace_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "base_revision": self.base_revision,
            "candidate_manifest_ref": _content_payload(self.candidate_manifest_ref),
            "changed_content_refs": [_content_payload(item) for item in self.changed_content_refs],
            "created_at": self.created_at,
            "deleted_paths": list(self.deleted_paths),
            "repository_head_commit": self.repository_head_commit,
            "repository_head_tree": self.repository_head_tree,
            "repository_bundle_ref": _content_payload(self.repository_bundle_ref),
            "snapshot_artifact_ref": self.snapshot_artifact_ref.value,
            "snapshot_ref": self.snapshot_ref.value,
            "staged_diff_ref": _content_payload(self.staged_diff_ref),
            "test_artifact_refs": [item.value for item in self.test_artifact_refs],
            "tool_call_refs": [item.value for item in self.tool_call_refs],
            "unstaged_diff_ref": _content_payload(self.unstaged_diff_ref),
            "untracked_manifest_ref": _content_payload(self.untracked_manifest_ref),
            "workspace_ref": self.workspace_ref.value,
        }


class WorkspaceService:
    """Durable coordinator over filesystem/Git/object/process execution evidence."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        filesystem: FilesystemAdapter,
        git: GitAdapter | None = None,
    ) -> None:
        if not isinstance(object_store, ObjectStorageBackend) or not isinstance(filesystem, FilesystemAdapter):
            raise TypeError("WorkspaceService requires ObjectStorageBackend and FilesystemAdapter")
        if git is not None and not isinstance(git, GitAdapter):
            raise TypeError("git must be GitAdapter")
        self.database_path = Path(database_path).resolve()
        self.object_store = object_store
        self.filesystem = filesystem
        self.git = git
        self.projects = ProjectStore(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.calls = CallLedgerService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
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
                CREATE TABLE IF NOT EXISTS workspace_policies (
                  project_id TEXT NOT NULL, policy_id TEXT NOT NULL, policy_json TEXT NOT NULL,
                  semantic_sha256 TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,policy_id), UNIQUE(project_id,policy_id,record_sha256),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS workspace_policy_claims (
                  project_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, semantic_sha256 TEXT NOT NULL,
                  policy_id TEXT NOT NULL, PRIMARY KEY(project_id,idempotency_key), UNIQUE(project_id,policy_id),
                  FOREIGN KEY(project_id,policy_id) REFERENCES workspace_policies(project_id,policy_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS workspace_identities (
                  project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, identity_json TEXT NOT NULL,
                  identity_sha256 TEXT NOT NULL, PRIMARY KEY(project_id,workspace_id),
                  UNIQUE(project_id,workspace_id,identity_sha256),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS workspace_create_claims (
                  project_id TEXT NOT NULL, node_attempt_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                  semantic_sha256 TEXT NOT NULL, workspace_id TEXT NOT NULL,
                  PRIMARY KEY(project_id,node_attempt_id,idempotency_key), UNIQUE(project_id,workspace_id),
                  FOREIGN KEY(project_id,workspace_id) REFERENCES workspace_identities(project_id,workspace_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS workspace_states (
                  project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, generation INTEGER NOT NULL,
                  state_json TEXT NOT NULL, state_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,workspace_id,generation), UNIQUE(project_id,workspace_id,generation,state_sha256),
                  FOREIGN KEY(project_id,workspace_id) REFERENCES workspace_identities(project_id,workspace_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS workspace_state_heads (
                  project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, generation INTEGER NOT NULL,
                  state_sha256 TEXT NOT NULL, updated_at TEXT NOT NULL, head_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,workspace_id),
                  FOREIGN KEY(project_id,workspace_id,generation,state_sha256) REFERENCES workspace_states(project_id,workspace_id,generation,state_sha256) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS workspace_operation_claims (
                  project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, operation TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL, semantic_sha256 TEXT NOT NULL, result_generation INTEGER,
                  snapshot_sequence INTEGER, receipt_sha256 TEXT,
                  PRIMARY KEY(project_id,workspace_id,operation,idempotency_key),
                  FOREIGN KEY(project_id,workspace_id) REFERENCES workspace_identities(project_id,workspace_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS workspace_snapshots (
                  project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                  snapshot_json TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,workspace_id,sequence), UNIQUE(project_id,workspace_id,sequence,record_sha256),
                  FOREIGN KEY(project_id,workspace_id) REFERENCES workspace_identities(project_id,workspace_id) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS workspace_receipts (
                  project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, snapshot_sequence INTEGER NOT NULL,
                  receipt_json TEXT NOT NULL, receipt_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,workspace_id,snapshot_sequence),
                  UNIQUE(project_id,workspace_id,snapshot_sequence,receipt_sha256),
                  FOREIGN KEY(project_id,workspace_id,snapshot_sequence) REFERENCES workspace_snapshots(project_id,workspace_id,sequence) ON DELETE RESTRICT);
                CREATE TABLE IF NOT EXISTS workspace_tool_evidence (
                  project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, call_id TEXT NOT NULL,
                  call_record_sha256 TEXT NOT NULL, recorded_at TEXT NOT NULL, evidence_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,workspace_id,call_id),
                  FOREIGN KEY(project_id,workspace_id) REFERENCES workspace_identities(project_id,workspace_id) ON DELETE RESTRICT,
                  FOREIGN KEY(project_id,call_id) REFERENCES calls(project_id,call_id) ON DELETE RESTRICT);
                CREATE TRIGGER IF NOT EXISTS workspace_policies_no_update BEFORE UPDATE ON workspace_policies BEGIN SELECT RAISE(ABORT,'Workspace policies are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_policies_no_delete BEFORE DELETE ON workspace_policies BEGIN SELECT RAISE(ABORT,'Workspace policies cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_policy_claims_no_update BEFORE UPDATE ON workspace_policy_claims BEGIN SELECT RAISE(ABORT,'Workspace policy claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_policy_claims_no_delete BEFORE DELETE ON workspace_policy_claims BEGIN SELECT RAISE(ABORT,'Workspace policy claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_identities_no_update BEFORE UPDATE ON workspace_identities BEGIN SELECT RAISE(ABORT,'Workspace identities are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_identities_no_delete BEFORE DELETE ON workspace_identities BEGIN SELECT RAISE(ABORT,'Workspace identities cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_create_claims_no_update BEFORE UPDATE ON workspace_create_claims BEGIN SELECT RAISE(ABORT,'Workspace create claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_create_claims_no_delete BEFORE DELETE ON workspace_create_claims BEGIN SELECT RAISE(ABORT,'Workspace create claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_states_no_update BEFORE UPDATE ON workspace_states BEGIN SELECT RAISE(ABORT,'Workspace states are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_states_no_delete BEFORE DELETE ON workspace_states BEGIN SELECT RAISE(ABORT,'Workspace states cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_state_heads_no_delete BEFORE DELETE ON workspace_state_heads BEGIN SELECT RAISE(ABORT,'Workspace heads cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_state_heads_monotonic BEFORE UPDATE ON workspace_state_heads
                  WHEN NEW.project_id!=OLD.project_id OR NEW.workspace_id!=OLD.workspace_id OR NEW.generation!=OLD.generation+1
                    OR NOT EXISTS(SELECT 1 FROM workspace_states s WHERE s.project_id=NEW.project_id AND s.workspace_id=NEW.workspace_id AND s.generation=NEW.generation AND s.state_sha256=NEW.state_sha256)
                  BEGIN SELECT RAISE(ABORT,'Workspace head must advance by one exact state'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_operation_claims_no_delete BEFORE DELETE ON workspace_operation_claims BEGIN SELECT RAISE(ABORT,'Workspace operation claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_operation_claims_semantic_immutable BEFORE UPDATE ON workspace_operation_claims
                  WHEN NEW.project_id!=OLD.project_id OR NEW.workspace_id!=OLD.workspace_id OR NEW.operation!=OLD.operation OR NEW.idempotency_key!=OLD.idempotency_key OR NEW.semantic_sha256!=OLD.semantic_sha256 OR OLD.result_generation IS NOT NULL
                  BEGIN SELECT RAISE(ABORT,'Workspace operation claim identity is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_snapshots_no_update BEFORE UPDATE ON workspace_snapshots BEGIN SELECT RAISE(ABORT,'Workspace snapshots are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_snapshots_no_delete BEFORE DELETE ON workspace_snapshots BEGIN SELECT RAISE(ABORT,'Workspace snapshots cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_receipts_no_update BEFORE UPDATE ON workspace_receipts BEGIN SELECT RAISE(ABORT,'Workspace receipts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_receipts_no_delete BEFORE DELETE ON workspace_receipts BEGIN SELECT RAISE(ABORT,'Workspace receipts cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_tool_evidence_no_update BEFORE UPDATE ON workspace_tool_evidence BEGIN SELECT RAISE(ABORT,'Workspace ToolCall evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS workspace_tool_evidence_no_delete BEFORE DELETE ON workspace_tool_evidence BEGIN SELECT RAISE(ABORT,'Workspace ToolCall evidence cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def _now(connection: sqlite3.Connection) -> str:
        value = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now')").fetchone()[0]
        return _timestamp(value, "database_now")

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise WorkspaceScopeError("Workspace Project scope mismatch") from exc
        except Exception as exc:
            raise WorkspaceIntegrityError("Workspace Project evidence failed verification") from exc

    def _require_attempt(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> None:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise WorkspaceAuthorityError("exact NodeExecutionAttempt is required")
        self._authorize(access, attempt.node_ref.project_ref)
        execution = self.executions.get_node_execution(access, attempt.node_ref)
        if (
            execution.status not in {"RUNNING", "WAITING_EXTERNAL"}
            or execution.current_attempt_id != attempt.attempt_id
            or execution.current_fence != attempt.fence
            or execution.current_run_attempt_id != attempt.run_attempt_id
            or execution.current_run_fence != attempt.run_fence
        ):
            raise WorkspaceAuthorityError("Workspace Node attempt is stale or inactive")
        task = self.tasks.get_task(access, attempt.task_ref)
        if task.canonical_digest != attempt.task_digest:
            raise WorkspaceIntegrityError("Workspace Task digest changed")

    def create_policy(
        self,
        access: ProjectAccess,
        *,
        root_grants: Sequence[WorkspaceRootGrant],
        network_policy: WorkspaceNetworkPolicy,
        allowed_capabilities: Sequence[CapabilityRef],
        side_effect_boundary: str,
        timeout_seconds: int | float,
        process_limit: int,
        restricted_destination_refs: Sequence[str] = (),
        resource_allocation_ref: ResourceAllocationRef | None = None,
        secret_refs: Sequence[str] = (),
        secret_mount_paths: Sequence[str] = (),
        idempotency_key: str,
    ) -> WorkspaceExecutionPolicy:
        _key(idempotency_key)
        self._authorize(access, access.project_ref)
        semantic = _sha(
            {
                "allowed_capabilities": [f"{item.capability_id}@{item.version}" for item in sorted(set(allowed_capabilities))],
                "network_policy": network_policy.value if isinstance(network_policy, WorkspaceNetworkPolicy) else network_policy,
                "process_limit": process_limit,
                "resource_allocation_ref": None if resource_allocation_ref is None else resource_allocation_ref.value,
                "restricted_destination_refs": sorted(set(restricted_destination_refs)),
                "root_grants": [{"mode": item.mode, "root_ref": item.root_ref.value} for item in sorted(set(root_grants), key=lambda item: item.root_ref.root_id)],
                "secret_mount_paths": sorted(set(secret_mount_paths)),
                "secret_refs": sorted(set(secret_refs)),
                "side_effect_boundary": side_effect_boundary,
                "timeout_seconds": float(timeout_seconds),
            }
        )
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM workspace_policy_claims WHERE project_id=? AND idempotency_key=?", (access.project_ref.value, idempotency_key)).fetchone()
            if row is not None:
                if not hmac.compare_digest(cast(str, row["semantic_sha256"]), semantic):
                    raise WorkspaceConflictError("Workspace policy idempotency semantics changed")
                return self._fetch_policy(connection, WorkspaceExecutionPolicyRef(access.project_ref, cast(str, row["policy_id"])))
            connection.execute("BEGIN IMMEDIATE")
            now = self._now(connection)
            policy = WorkspaceExecutionPolicy(
                WorkspaceExecutionPolicyRef.new(access.project_ref), tuple(root_grants), network_policy,
                tuple(restricted_destination_refs), tuple(allowed_capabilities), resource_allocation_ref,
                tuple(secret_refs), tuple(secret_mount_paths), side_effect_boundary, float(timeout_seconds),
                process_limit, now,
            )
            payload = _json(self._policy_payload(policy))
            connection.execute("INSERT INTO workspace_policies VALUES (?,?,?,?,?)", (access.project_ref.value, policy.policy_ref.policy_id, payload, policy.semantic_sha256, policy.record_sha256))
            connection.execute("INSERT INTO workspace_policy_claims VALUES (?,?,?,?)", (access.project_ref.value, idempotency_key, semantic, policy.policy_ref.policy_id))
            connection.commit()
            return policy
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise WorkspaceConflictError("Workspace policy creation conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _policy_payload(policy: WorkspaceExecutionPolicy) -> dict[str, object]:
        result = policy.semantic_payload()
        result.update({"created_at": policy.created_at, "policy_id": policy.policy_ref.policy_id, "project_ref": policy.project_ref.value})
        return result

    def _fetch_policy(self, connection: sqlite3.Connection, ref: WorkspaceExecutionPolicyRef) -> WorkspaceExecutionPolicy:
        row = connection.execute("SELECT * FROM workspace_policies WHERE project_id=? AND policy_id=?", (ref.project_ref.value, ref.policy_id)).fetchone()
        if row is None:
            raise WorkspaceNotFoundError("Workspace execution policy not found")
        try:
            value = cast(dict[str, object], json.loads(cast(str, row["policy_json"])))
            grants = tuple(
                WorkspaceRootGrant(FilesystemRootRef(ref.project_ref, cast(str, item["root_ref"]).rsplit("/", 1)[1]), cast(str, item["mode"]))
                for item in cast(list[dict[str, object]], value["root_grants"])
            )
            capabilities = tuple(CapabilityRef(*item.rsplit("@", 1)) for item in cast(list[str], value["allowed_capabilities"]))
            allocation_value = value["resource_allocation_ref"]
            allocation = None if allocation_value is None else ResourceAllocationRef(ref.project_ref, cast(str, allocation_value).rsplit("/", 1)[1])
            policy = WorkspaceExecutionPolicy(
                ref, grants, WorkspaceNetworkPolicy(cast(str, value["network_policy"])),
                tuple(cast(list[str], value["restricted_destination_refs"])), capabilities, allocation,
                tuple(cast(list[str], value["secret_refs"])), tuple(cast(list[str], value["secret_mount_paths"])),
                cast(str, value["side_effect_boundary"]), cast(float, value["timeout_seconds"]),
                cast(int, value["process_limit"]), cast(str, value["created_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise WorkspaceIntegrityError("Persisted Workspace policy is malformed") from exc
        if not hmac.compare_digest(policy.semantic_sha256, cast(str, row["semantic_sha256"])) or not hmac.compare_digest(policy.record_sha256, cast(str, row["record_sha256"])):
            raise WorkspaceIntegrityError("Workspace policy evidence changed")
        return policy

    def get_policy(self, access: ProjectAccess, ref: WorkspaceExecutionPolicyRef) -> WorkspaceExecutionPolicy:
        if not isinstance(ref, WorkspaceExecutionPolicyRef):
            raise WorkspaceContractError("exact WorkspaceExecutionPolicyRef is required")
        self._authorize(access, ref.project_ref)
        connection = self._connect()
        try:
            return self._fetch_policy(connection, ref)
        finally:
            connection.close()

    @staticmethod
    def _base_revision(sources: Sequence[WorkspaceSource], workspace_type: WorkspaceType) -> str:
        if not sources:
            if workspace_type is not WorkspaceType.TEMPORARY:
                raise WorkspaceContractError("Non-temporary Workspace requires exact base sources")
            return _sha({"empty_temporary_base": True, "schema_version": 1})
        return _sha({"sources": [item.payload() for item in sources], "workspace_type": workspace_type.value})

    def create_workspace(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        workspace_type: WorkspaceType,
        base_sources: Sequence[WorkspaceSource],
        execution_policy_ref: WorkspaceExecutionPolicyRef,
        candidate_root_ref: FilesystemRootRef,
        relative_path: str,
        idempotency_key: str,
    ) -> Workspace:
        _key(idempotency_key)
        self._require_attempt(access, attempt)
        if not isinstance(workspace_type, WorkspaceType):
            raise WorkspaceContractError("Workspace type is malformed")
        sources = tuple(base_sources)
        if any(not isinstance(item, (WorkspaceFileSource, WorkspaceRepositorySource)) for item in sources):
            raise WorkspaceContractError("Workspace sources must be exact active source identities")
        if any(item.project_ref != access.project_ref for item in sources):
            raise WorkspaceScopeError("Workspace base source crossed Project scope")
        repositories = tuple(item for item in sources if isinstance(item, WorkspaceRepositorySource))
        if workspace_type is WorkspaceType.REPOSITORY and len(repositories) != 1:
            raise WorkspaceContractError("REPOSITORY Workspace requires one exact RepositoryRef")
        if workspace_type is not WorkspaceType.REPOSITORY and repositories:
            raise WorkspaceContractError("Repository source requires REPOSITORY Workspace")
        path = _relative(relative_path)
        policy = self.get_policy(access, execution_policy_ref)
        grant = next((item for item in policy.root_grants if item.root_ref == candidate_root_ref), None)
        if grant is None or grant.mode not in {"READ_WRITE", "TEMPORARY"}:
            raise WorkspaceAuthorityError("Workspace candidate root lacks write grant")
        candidate_root = self.filesystem.get_root(access, candidate_root_ref)
        if candidate_root.mode not in {FilesystemMode.READ_WRITE, FilesystemMode.TEMPORARY} or not candidate_root.allow_remove:
            raise WorkspaceAuthorityError("Workspace candidate root must be writable and cleanup-capable")
        base_revision = self._base_revision(sources, workspace_type)
        semantic = _sha({"attempt": attempt.record_sha256, "base_revision": base_revision, "candidate_root_ref": candidate_root_ref.value, "execution_policy_ref": execution_policy_ref.value, "relative_path": path, "workspace_type": workspace_type.value})
        connection = self._connect()
        try:
            prior = connection.execute("SELECT * FROM workspace_create_claims WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?", (access.project_ref.value, attempt.attempt_id, idempotency_key)).fetchone()
            if prior is not None:
                if not hmac.compare_digest(cast(str, prior["semantic_sha256"]), semantic):
                    raise WorkspaceConflictError("Workspace creation idempotency semantics changed")
                return self._fetch_workspace(connection, WorkspaceRef(access.project_ref, cast(str, prior["workspace_id"])), None)
            connection.execute("BEGIN IMMEDIATE")
            now = self._now(connection)
            workspace = Workspace(
                WorkspaceRef.new(access.project_ref), attempt.task_ref, attempt.run_ref,
                attempt.node_ref.graph_ref, attempt.node_ref, attempt.attempt_id, attempt.fence,
                workspace_type, sources, base_revision, execution_policy_ref,
                policy.resource_allocation_ref, candidate_root_ref, path, None, None, None,
                WorkspaceLifecycleState.CREATED, 1, now, now,
            )
            identity = {key: value for key, value in workspace.payload().items() if key not in {"generation", "latest_snapshot_sequence", "materialization_manifest_ref", "repository_workspace", "status", "updated_at"}}
            identity_sha = _sha(identity)
            connection.execute("INSERT INTO workspace_identities VALUES (?,?,?,?)", (access.project_ref.value, workspace.workspace_ref.workspace_id, _json(identity), identity_sha))
            connection.execute("INSERT INTO workspace_create_claims VALUES (?,?,?,?,?)", (access.project_ref.value, attempt.attempt_id, idempotency_key, semantic, workspace.workspace_ref.workspace_id))
            self._insert_initial_state(connection, workspace)
            connection.commit()
            return workspace
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise WorkspaceConflictError("Workspace creation conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _insert_initial_state(self, connection: sqlite3.Connection, workspace: Workspace) -> None:
        connection.execute("INSERT INTO workspace_states VALUES (?,?,?,?,?)", (workspace.project_ref.value, workspace.workspace_ref.workspace_id, workspace.generation, _json(workspace.payload()), workspace.state_sha256))
        head_sha = _sha({"generation": workspace.generation, "state_sha256": workspace.state_sha256, "updated_at": workspace.updated_at, "workspace_ref": workspace.workspace_ref.value})
        connection.execute("INSERT INTO workspace_state_heads VALUES (?,?,?,?,?,?)", (workspace.project_ref.value, workspace.workspace_ref.workspace_id, workspace.generation, workspace.state_sha256, workspace.updated_at, head_sha))

    def _advance(
        self,
        connection: sqlite3.Connection,
        prior: Workspace,
        *,
        status: WorkspaceLifecycleState,
        repository_workspace_ref: RepositoryWorkspaceRef | None = None,
        materialization_manifest_ref: ContentRef | None = None,
        latest_snapshot_ref: WorkspaceSnapshotRef | None = None,
    ) -> Workspace:
        current = replace(
            prior,
            status=status,
            repository_workspace_ref=prior.repository_workspace_ref if repository_workspace_ref is None else repository_workspace_ref,
            materialization_manifest_ref=prior.materialization_manifest_ref if materialization_manifest_ref is None else materialization_manifest_ref,
            latest_snapshot_ref=prior.latest_snapshot_ref if latest_snapshot_ref is None else latest_snapshot_ref,
            generation=prior.generation + 1,
            updated_at=self._now(connection),
        )
        connection.execute("INSERT INTO workspace_states VALUES (?,?,?,?,?)", (current.project_ref.value, current.workspace_ref.workspace_id, current.generation, _json(current.payload()), current.state_sha256))
        head_sha = _sha({"generation": current.generation, "state_sha256": current.state_sha256, "updated_at": current.updated_at, "workspace_ref": current.workspace_ref.value})
        changed = connection.execute("UPDATE workspace_state_heads SET generation=?,state_sha256=?,updated_at=?,head_sha256=? WHERE project_id=? AND workspace_id=? AND generation=? AND state_sha256=?", (current.generation, current.state_sha256, current.updated_at, head_sha, current.project_ref.value, current.workspace_ref.workspace_id, prior.generation, prior.state_sha256))
        if changed.rowcount != 1:
            raise WorkspaceConflictError("Workspace state changed concurrently")
        return current

    @staticmethod
    def _repository_from_payload(project_ref: ProjectRef, value: Mapping[str, object]) -> RepositoryRef:
        root_value = cast(str, value["root_ref"])
        return RepositoryRef(
            cast(str, value["repository_id"]), project_ref,
            FilesystemRootRef(project_ref, root_value.rsplit("/", 1)[1]),
            cast(str, value["relative_path"]), cast(str, value["object_format"]),
            cast(str, value["commit_sha"]), cast(str, value["tree_sha"]),
            cast(dict[str, str], value["submodules"]), cast(str, value["config_sha256"]),
            cast(str, value["registered_at"]),
        )

    @staticmethod
    def _repository_workspace_from_payload(project_ref: ProjectRef, value: Mapping[str, object]) -> RepositoryWorkspaceRef:
        return RepositoryWorkspaceRef(
            cast(str, value["workspace_id"]), project_ref, cast(str, value["repository_id"]),
            FilesystemRootRef(project_ref, cast(str, value["root_ref"]).rsplit("/", 1)[1]),
            cast(str, value["relative_path"]), cast(str, value["base_commit_sha"]),
            cast(str, value["base_tree_sha"]), cast(str, value["current_commit_sha"]),
            cast(str, value["current_tree_sha"]), cast(int, value["generation"]), cast(str, value["created_at"]),
        )

    @classmethod
    def _source_from_payload(cls, project_ref: ProjectRef, value: Mapping[str, object]) -> WorkspaceSource:
        if value.get("kind") == "FILE":
            return WorkspaceFileSource(
                cast(str, value["relative_path"]),
                ArtifactRef(project_ref, cast(str, value["artifact_id"]), cast(int, value["artifact_revision"])),
            )
        if value.get("kind") == "REPOSITORY":
            return WorkspaceRepositorySource(cls._repository_from_payload(project_ref, cast(dict[str, object], value["repository"])))
        raise WorkspaceIntegrityError("Persisted Workspace source kind is unsupported")

    @classmethod
    def _workspace_from_payload(cls, project_ref: ProjectRef, value: Mapping[str, object]) -> Workspace:
        from .graph import GraphRef, NodeRef
        graph = GraphRef(project_ref, cast(str, value["graph_id"]), cast(int, value["graph_revision"]))
        workspace_ref = WorkspaceRef(project_ref, cast(str, value["workspace_id"]))
        snapshot_sequence = value["latest_snapshot_sequence"]
        materialization = value["materialization_manifest_ref"]
        repository_workspace = value["repository_workspace"]
        allocation_id = value["resource_allocation_id"]
        return Workspace(
            workspace_ref,
            TaskRef(project_ref, cast(str, value["task_id"]), cast(int, value["task_revision"])),
            RunRef(project_ref, cast(str, value["run_id"])), graph,
            NodeRef(graph, cast(str, value["node_id"])), cast(str, value["node_attempt_id"]),
            cast(int, value["node_attempt_fence"]), WorkspaceType(cast(str, value["workspace_type"])),
            tuple(cls._source_from_payload(project_ref, item) for item in cast(list[dict[str, object]], value["base_sources"])),
            cast(str, value["base_revision"]),
            WorkspaceExecutionPolicyRef(project_ref, cast(str, value["execution_policy_ref"]).rsplit("/", 1)[1]),
            None if allocation_id is None else ResourceAllocationRef(project_ref, cast(str, allocation_id)),
            FilesystemRootRef(project_ref, cast(str, value["candidate_root_ref"]).rsplit("/", 1)[1]),
            cast(str, value["relative_path"]),
            None if repository_workspace is None else cls._repository_workspace_from_payload(project_ref, cast(dict[str, object], repository_workspace)),
            None if materialization is None else _content_from(cast(dict[str, object], materialization)),
            None if snapshot_sequence is None else WorkspaceSnapshotRef(workspace_ref, cast(int, snapshot_sequence)),
            WorkspaceLifecycleState(cast(str, value["status"])), cast(int, value["generation"]),
            cast(str, value["created_at"]), cast(str, value["updated_at"]),
        )

    def _fetch_workspace(self, connection: sqlite3.Connection, ref: WorkspaceRef, generation: int | None) -> Workspace:
        if generation is None:
            head = connection.execute("SELECT * FROM workspace_state_heads WHERE project_id=? AND workspace_id=?", (ref.project_ref.value, ref.workspace_id)).fetchone()
            if head is None:
                raise WorkspaceNotFoundError("Workspace not found")
            generation = cast(int, head["generation"])
        row = connection.execute("SELECT * FROM workspace_states WHERE project_id=? AND workspace_id=? AND generation=?", (ref.project_ref.value, ref.workspace_id, generation)).fetchone()
        if row is None:
            raise WorkspaceIntegrityError("Workspace state history is missing")
        try:
            workspace = self._workspace_from_payload(ref.project_ref, cast(dict[str, object], json.loads(cast(str, row["state_json"]))))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, WorkspaceError) as exc:
            raise WorkspaceIntegrityError("Persisted Workspace state is malformed") from exc
        if workspace.workspace_ref != ref or not hmac.compare_digest(workspace.state_sha256, cast(str, row["state_sha256"])):
            raise WorkspaceIntegrityError("Workspace state evidence changed")
        if generation is not None:
            head = connection.execute("SELECT * FROM workspace_state_heads WHERE project_id=? AND workspace_id=?", (ref.project_ref.value, ref.workspace_id)).fetchone()
            if head is None:
                raise WorkspaceIntegrityError("Workspace state head is missing")
            head_state = connection.execute("SELECT state_sha256,state_json FROM workspace_states WHERE project_id=? AND workspace_id=? AND generation=?", (ref.project_ref.value, ref.workspace_id, cast(int, head["generation"]))).fetchone()
            if head_state is None:
                raise WorkspaceIntegrityError("Workspace state head target is missing")
            try:
                head_updated_at = cast(str, cast(dict[str, object], json.loads(cast(str, head_state["state_json"])))["updated_at"])
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise WorkspaceIntegrityError("Workspace head target state is malformed") from exc
            expected_head = _sha({"generation": cast(int, head["generation"]), "state_sha256": cast(str, head["state_sha256"]), "updated_at": cast(str, head["updated_at"]), "workspace_ref": ref.value})
            if head["state_sha256"] != head_state["state_sha256"] or head["updated_at"] != head_updated_at or not hmac.compare_digest(expected_head, cast(str, head["head_sha256"])):
                raise WorkspaceIntegrityError("Workspace state head evidence changed")
        return workspace

    def get_workspace(self, access: ProjectAccess, ref: WorkspaceRef) -> Workspace:
        if not isinstance(ref, WorkspaceRef):
            raise WorkspaceContractError("exact WorkspaceRef is required")
        self._authorize(access, ref.project_ref)
        connection = self._connect()
        try:
            return self._fetch_workspace(connection, ref, None)
        finally:
            connection.close()

    def _claim_operation(self, connection: sqlite3.Connection, workspace: Workspace, operation: str, key: str, semantic: str) -> sqlite3.Row | None:
        row = connection.execute("SELECT * FROM workspace_operation_claims WHERE project_id=? AND workspace_id=? AND operation=? AND idempotency_key=?", (workspace.project_ref.value, workspace.workspace_ref.workspace_id, operation, key)).fetchone()
        if row is not None:
            if not hmac.compare_digest(cast(str, row["semantic_sha256"]), semantic):
                raise WorkspaceConflictError(f"Workspace {operation} idempotency semantics changed")
            return cast(sqlite3.Row, row)
        connection.execute("INSERT INTO workspace_operation_claims(project_id,workspace_id,operation,idempotency_key,semantic_sha256) VALUES (?,?,?,?,?)", (workspace.project_ref.value, workspace.workspace_ref.workspace_id, operation, key, semantic))
        return None

    @staticmethod
    def _finish_claim(connection: sqlite3.Connection, workspace: Workspace, operation: str, key: str, *, generation: int, snapshot_sequence: int | None = None, receipt_sha256: str | None = None) -> None:
        changed = connection.execute("UPDATE workspace_operation_claims SET result_generation=?,snapshot_sequence=?,receipt_sha256=? WHERE project_id=? AND workspace_id=? AND operation=? AND idempotency_key=? AND result_generation IS NULL", (generation, snapshot_sequence, receipt_sha256, workspace.project_ref.value, workspace.workspace_ref.workspace_id, operation, key))
        if changed.rowcount != 1:
            raise WorkspaceConflictError(f"Workspace {operation} result claim changed concurrently")

    def _require_capability(self, policy: WorkspaceExecutionPolicy, capability: CapabilityRef) -> None:
        if capability not in policy.allowed_capabilities:
            raise WorkspaceAuthorityError(f"Workspace policy denies {capability.capability_id}")

    def _mkdir_parents(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace: Workspace, path: str, *, material: str, calls: list[ToolCallRef]) -> None:
        parent = PurePosixPath(path).parent
        if str(parent) == ".":
            return
        current: list[str] = []
        for part in parent.parts:
            current.append(part)
            target = f"{workspace.relative_path}/{'/'.join(current)}"
            try:
                operation = self.filesystem.mkdir(access, attempt, root_ref=workspace.candidate_root_ref, path=target, idempotency_key=_adapter_key(material, "mkdir", current))
                calls.append(operation.tool_call_ref)
            except FilesystemConflictError:
                continue

    def materialize(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace_ref: WorkspaceRef, *, idempotency_key: str) -> Workspace:
        _key(idempotency_key)
        self._require_attempt(access, attempt)
        workspace = self.get_workspace(access, workspace_ref)
        if (workspace.node_attempt_id, workspace.node_attempt_fence) != (attempt.attempt_id, attempt.fence):
            raise WorkspaceAuthorityError("Workspace belongs to a different Node attempt")
        policy = self.get_policy(access, workspace.execution_policy_ref)
        semantic = _sha({"base_revision": workspace.base_revision, "workspace_ref": workspace_ref.value})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch_workspace(connection, workspace_ref, None)
            prior = self._claim_operation(connection, current, "MATERIALIZE", idempotency_key, semantic)
            if prior is not None and prior["result_generation"] is not None:
                result = self._fetch_workspace(connection, workspace_ref, cast(int, prior["result_generation"]))
                connection.commit()
                return result
            if current.status is not WorkspaceLifecycleState.CREATED:
                raise WorkspaceConflictError("Workspace cannot materialize from current lifecycle state")
            connection.commit()
        finally:
            connection.close()
        calls: list[ToolCallRef] = []
        repository_workspace: RepositoryWorkspaceRef | None = None
        self._require_capability(policy, FilesystemAdapter.capability_ref("list"))
        self._require_capability(policy, FilesystemAdapter.capability_ref("read"))
        if current.workspace_type is WorkspaceType.REPOSITORY:
            if self.git is None:
                raise WorkspaceAuthorityError("REPOSITORY Workspace requires GitAdapter")
            self._require_capability(policy, GitAdapter.capability_ref("workspace"))
            source = cast(WorkspaceRepositorySource, current.base_sources[0])
            repository_workspace = self.git.create_workspace(
                access, attempt, source.repository_ref,
                candidate_root_ref=current.candidate_root_ref, relative_path=current.relative_path,
                require_source_head=False, idempotency_key=_adapter_key(idempotency_key, "git-workspace"),
            )
            calls.extend(self._calls_for_attempt(access, attempt, capability=GitAdapter.capability_ref("workspace")))
        else:
            self._require_capability(policy, FilesystemAdapter.capability_ref("mkdir"))
            self._require_capability(policy, FilesystemAdapter.capability_ref("write"))
            made = self.filesystem.mkdir(access, attempt, root_ref=current.candidate_root_ref, path=current.relative_path, idempotency_key=_adapter_key(idempotency_key, "root"))
            calls.append(made.tool_call_ref)
            for index, file_source in enumerate(cast(tuple[WorkspaceFileSource, ...], current.base_sources)):
                artifact = self.artifacts.get_artifact(access, file_source.artifact_ref)
                if artifact.content_ref is None:
                    raise WorkspaceIntegrityError("Workspace file source Artifact has no exact content")
                self.object_store.verify(artifact.content_ref)
                self._mkdir_parents(access, attempt, current, file_source.relative_path, material=f"{idempotency_key}-{index}", calls=calls)
                written = self.filesystem.write(access, attempt, root_ref=current.candidate_root_ref, path=f"{current.relative_path}/{file_source.relative_path}", content_ref=artifact.content_ref, idempotency_key=_adapter_key(idempotency_key, "write", index))
                calls.append(written.tool_call_ref)
        entries, capture_calls = self._scan(access, attempt, current, policy, idempotency_material=f"{idempotency_key}-base")
        calls.extend(capture_calls)
        manifest_ref = self._store_manifest(current, entries, base=True)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            head = self._fetch_workspace(connection, workspace_ref, None)
            if head.generation != current.generation:
                raise WorkspaceConflictError("Workspace changed while materializing")
            result = self._advance(connection, head, status=WorkspaceLifecycleState.MATERIALIZED, repository_workspace_ref=repository_workspace, materialization_manifest_ref=manifest_ref)
            self._record_calls(connection, result, calls)
            self._finish_claim(connection, result, "MATERIALIZE", idempotency_key, generation=result.generation)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _calls_for_attempt(self, access: ProjectAccess, attempt: NodeExecutionAttempt, *, capability: CapabilityRef | None = None) -> tuple[ToolCallRef, ...]:
        connection = self._connect()
        try:
            query = "SELECT call_id FROM calls WHERE project_id=? AND node_attempt_id=? AND call_kind='TOOL'"
            parameters: list[object] = [access.project_ref.value, attempt.attempt_id]
            if capability is not None:
                query += " AND capability_id=? AND capability_version=?"
                parameters.extend((capability.capability_id, capability.version))
            query += " ORDER BY created_at,call_id"
            rows = connection.execute(query, tuple(parameters)).fetchall()
        finally:
            connection.close()
        return tuple(ToolCallRef(access.project_ref, cast(str, row["call_id"])) for row in rows)

    def _workspace_evidence_refs(self, workspace_ref: WorkspaceRef) -> tuple[ToolCallRef, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT call_id FROM workspace_tool_evidence WHERE project_id=? AND workspace_id=? ORDER BY call_id",
                (workspace_ref.project_ref.value, workspace_ref.workspace_id),
            ).fetchall()
        finally:
            connection.close()
        return tuple(ToolCallRef(workspace_ref.project_ref, cast(str, row["call_id"])) for row in rows)

    @staticmethod
    def _is_excluded(policy: WorkspaceExecutionPolicy, path: str) -> bool:
        parts = PurePosixPath(path).parts
        if any(part in _SKIP_COMPONENTS for part in parts):
            return True
        if PurePosixPath(path).name in _DEFAULT_SECRET_NAMES:
            return True
        return any(path == mount or path.startswith(f"{mount}/") for mount in policy.secret_mount_paths)

    def _scan(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace: Workspace,
        policy: WorkspaceExecutionPolicy,
        *,
        idempotency_material: str,
        cancelled: Callable[[], bool] | None = None,
    ) -> tuple[tuple[WorkspaceFileEntry, ...], tuple[ToolCallRef, ...]]:
        entries: list[WorkspaceFileEntry] = []
        calls: list[ToolCallRef] = []
        seen = 0

        def visit(relative: str) -> None:
            nonlocal seen
            if cancelled is not None and cancelled():
                raise WorkspaceCancelledError("Workspace scan was cancelled")
            full = workspace.relative_path if relative == "." else f"{workspace.relative_path}/{relative}"
            identity = hashlib.sha256(relative.encode()).hexdigest()[:24]
            listing = self.filesystem.list(
                access, attempt, root_ref=workspace.candidate_root_ref, path=full,
                idempotency_key=_adapter_key(idempotency_material, "list", identity), cancelled=cancelled,
            )
            calls.append(listing.tool_call_ref)
            try:
                payload = json.loads(self.object_store.read(listing.output_ref))
                children = cast(list[dict[str, object]], payload["entries"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, ObjectStorageError) as exc:
                raise WorkspaceIntegrityError("Filesystem list receipt is malformed") from exc
            for child in children:
                name = cast(str, child.get("name"))
                kind = cast(str, child.get("kind"))
                candidate = name if relative == "." else f"{relative}/{name}"
                candidate = _relative(candidate)
                if self._is_excluded(policy, candidate):
                    continue
                seen += 1
                if seen > 100_000:
                    raise WorkspaceContractError("Workspace snapshot tree is unbounded")
                if kind == "directory":
                    entries.append(WorkspaceFileEntry(candidate, "directory", None, None))
                    visit(candidate)
                elif kind == "file":
                    read = self.filesystem.read(
                        access, attempt, root_ref=workspace.candidate_root_ref,
                        path=f"{workspace.relative_path}/{candidate}", media_type="application/octet-stream",
                        idempotency_key=_adapter_key(idempotency_material, "read", candidate), cancelled=cancelled,
                    )
                    state = self.filesystem.stat(
                        access, attempt, root_ref=workspace.candidate_root_ref,
                        path=f"{workspace.relative_path}/{candidate}",
                        idempotency_key=_adapter_key(idempotency_material, "stat", candidate), cancelled=cancelled,
                    )
                    calls.extend((read.tool_call_ref, state.tool_call_ref))
                    try:
                        state_payload = cast(dict[str, object], json.loads(self.object_store.read(state.output_ref)))
                        mode = cast(int, state_payload["mode"])
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError, ObjectStorageError) as exc:
                        raise WorkspaceIntegrityError("Filesystem stat receipt is malformed") from exc
                    entries.append(WorkspaceFileEntry(candidate, "file", mode, read.output_ref))
                elif kind == "symlink":
                    if workspace.workspace_type is not WorkspaceType.REPOSITORY:
                        raise WorkspaceAuthorityError("Symlink in non-repository Workspace was rejected")
                    entries.append(WorkspaceFileEntry(candidate, "symlink", None, None))
                else:
                    raise WorkspaceAuthorityError("Special filesystem object in Workspace was rejected")

        visit(".")
        return tuple(entries), tuple(calls)

    def _store_manifest(self, workspace: Workspace, entries: Sequence[WorkspaceFileEntry], *, base: bool) -> ContentRef:
        payload = {
            "base_revision": workspace.base_revision,
            "entries": [item.payload() for item in sorted(entries, key=lambda item: item.path)],
            "kind": "BASE" if base else "CANDIDATE",
            "schema_version": 1,
            "workspace_ref": workspace.workspace_ref.value,
        }
        return self.object_store.put(_json(payload).encode(), media_type="application/vnd.biella.workspace-manifest+json")

    def _load_manifest(self, ref: ContentRef) -> tuple[WorkspaceFileEntry, ...]:
        try:
            raw = cast(dict[str, object], json.loads(self.object_store.read(ref)))
            entries = tuple(
                WorkspaceFileEntry(
                    cast(str, item["path"]), cast(str, item["kind"]), cast(int | None, item["mode"]),
                    None if item["content_ref"] is None else _content_from(cast(dict[str, object], item["content_ref"])),
                )
                for item in cast(list[dict[str, object]], raw["entries"])
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ObjectStorageError, WorkspaceError) as exc:
            raise WorkspaceIntegrityError("Workspace manifest evidence is malformed") from exc
        if tuple(sorted(entries, key=lambda item: item.path)) != entries:
            raise WorkspaceIntegrityError("Workspace manifest ordering changed")
        return entries

    def _record_calls(self, connection: sqlite3.Connection, workspace: Workspace, refs: Sequence[ToolCallRef]) -> None:
        policy = self._fetch_policy(connection, workspace.execution_policy_ref)
        for ref in sorted(set(refs), key=lambda item: item.call_id):
            # CallLedger authorization needs the caller's original access token.  Validate
            # immutable persisted identity in this transaction, then callers re-read via
            # CallLedger in public verification paths.
            row = connection.execute("SELECT * FROM calls WHERE project_id=? AND call_id=?", (workspace.project_ref.value, ref.call_id)).fetchone()
            state = connection.execute(
                "SELECT version.* FROM call_status_heads head JOIN call_status_versions version ON version.project_id=head.project_id AND version.call_id=head.call_id AND version.state_version=head.current_version AND version.record_sha256=head.current_record_sha256 WHERE head.project_id=? AND head.call_id=?",
                (workspace.project_ref.value, ref.call_id),
            ).fetchone()
            if row is None or state is None:
                raise WorkspaceIntegrityError("Workspace ToolCall evidence is missing")
            if row["node_attempt_id"] != workspace.node_attempt_id or row["node_fence"] != workspace.node_attempt_fence:
                raise WorkspaceAuthorityError("Workspace ToolCall crossed Node attempt fence")
            capability = CapabilityRef(cast(str, row["capability_id"]), cast(str, row["capability_version"]))
            self._require_capability(policy, capability)
            if state["status"] != "SUCCEEDED":
                raise WorkspaceConflictError("Workspace cannot persist an unsuccessful ToolCall as output")
            record_sha = cast(str, row["record_sha256"])
            recorded_at = self._now(connection)
            evidence_sha = _sha({"call_record_sha256": record_sha, "recorded_at": recorded_at, "tool_call_ref": ref.value, "workspace_ref": workspace.workspace_ref.value})
            connection.execute("INSERT OR IGNORE INTO workspace_tool_evidence VALUES (?,?,?,?,?,?)", (workspace.project_ref.value, workspace.workspace_ref.workspace_id, ref.call_id, record_sha, recorded_at, evidence_sha))

    @staticmethod
    def _side_effect_allows(boundary: str, requested: str) -> bool:
        rank = {"NONE": 0, "PROJECT_WRITE": 1, "EXTERNAL_SIDE_EFFECT": 2}
        return requested in rank and rank[requested] <= rank[boundary]

    def record_tool_call(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace_ref: WorkspaceRef,
        tool_call_ref: ToolCallRef,
        *,
        network_used: bool,
        destination_ref: str | None = None,
        side_effect: str = "PROJECT_WRITE",
    ) -> Workspace:
        workspace = self.get_workspace(access, workspace_ref)
        if workspace.status in {WorkspaceLifecycleState.CANCELLED, WorkspaceLifecycleState.CLEANED, WorkspaceLifecycleState.LOST_UNCAPTURED}:
            raise WorkspaceCancelledError("Workspace does not accept late ToolCall results")
        self._require_attempt(access, attempt)
        if (workspace.node_attempt_id, workspace.node_attempt_fence) != (attempt.attempt_id, attempt.fence):
            raise WorkspaceAuthorityError("Workspace ToolCall attempt is stale")
        call = self.calls.get_tool_call(access, tool_call_ref)
        if call.attempt.record_sha256 != attempt.record_sha256 or call.status != "SUCCEEDED":
            raise WorkspaceAuthorityError("Workspace ToolCall is not a successful exact attempt result")
        policy = self.get_policy(access, workspace.execution_policy_ref)
        self._require_capability(policy, call.capability_ref)
        if not self._side_effect_allows(policy.side_effect_boundary, side_effect):
            raise WorkspaceAuthorityError("Workspace ToolCall exceeds side-effect boundary")
        if not isinstance(network_used, bool):
            raise WorkspaceContractError("network_used must be boolean")
        if network_used:
            if policy.network_policy is WorkspaceNetworkPolicy.NONE:
                raise WorkspaceAuthorityError("Workspace network policy is NONE")
            if destination_ref is None or _REF.fullmatch(destination_ref) is None:
                raise WorkspaceContractError("Network ToolCall requires exact destination ref")
            if policy.network_policy is WorkspaceNetworkPolicy.RESTRICTED and destination_ref not in policy.restricted_destination_refs:
                raise WorkspaceAuthorityError("Workspace restricted network destination was denied")
            if policy.network_policy is WorkspaceNetworkPolicy.PROJECT_POLICY:
                task = self.tasks.get_task(access, workspace.task_ref)
                if task.egress_policy_ref is None:
                    raise WorkspaceAuthorityError("PROJECT_POLICY network lacks exact Task egress policy")
        elif destination_ref is not None:
            raise WorkspaceContractError("Offline ToolCall cannot claim a destination")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch_workspace(connection, workspace_ref, None)
            if current.generation != workspace.generation:
                raise WorkspaceConflictError("Workspace changed before ToolCall recording")
            existing = connection.execute("SELECT call_record_sha256 FROM workspace_tool_evidence WHERE project_id=? AND workspace_id=? AND call_id=?", (workspace.project_ref.value, workspace.workspace_ref.workspace_id, tool_call_ref.call_id)).fetchone()
            if existing is not None:
                if not hmac.compare_digest(cast(str, existing["call_record_sha256"]), call.record_sha256):
                    raise WorkspaceIntegrityError("Workspace ToolCall evidence changed")
                connection.commit()
                return current
            self._record_calls(connection, current, (tool_call_ref,))
            target = WorkspaceLifecycleState.EXECUTING if current.status in {WorkspaceLifecycleState.MATERIALIZED, WorkspaceLifecycleState.RECONSTRUCTED, WorkspaceLifecycleState.PERSISTED} else current.status
            result = current if target is current.status else self._advance(connection, current, status=target)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def begin_execution(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace_ref: WorkspaceRef, *, idempotency_key: str) -> Workspace:
        _key(idempotency_key)
        self._require_attempt(access, attempt)
        workspace = self.get_workspace(access, workspace_ref)
        semantic = _sha({"attempt": attempt.record_sha256, "workspace_ref": workspace_ref.value})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch_workspace(connection, workspace_ref, None)
            prior = self._claim_operation(connection, current, "EXECUTE", idempotency_key, semantic)
            if prior is not None and prior["result_generation"] is not None:
                result = self._fetch_workspace(connection, workspace_ref, cast(int, prior["result_generation"]))
                connection.commit()
                return result
            if current.status not in {WorkspaceLifecycleState.MATERIALIZED, WorkspaceLifecycleState.RECONSTRUCTED, WorkspaceLifecycleState.PERSISTED}:
                raise WorkspaceConflictError("Workspace cannot enter execution from current state")
            result = self._advance(connection, current, status=WorkspaceLifecycleState.EXECUTING)
            self._finish_claim(connection, result, "EXECUTE", idempotency_key, generation=result.generation)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def capture(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        workspace_ref: WorkspaceRef,
        *,
        test_artifact_refs: Sequence[ArtifactRef] = (),
        idempotency_key: str,
        cancelled: Callable[[], bool] | None = None,
    ) -> CandidateWorkspaceReceipt:
        _key(idempotency_key)
        self._require_attempt(access, attempt)
        workspace = self.get_workspace(access, workspace_ref)
        if workspace.status not in {WorkspaceLifecycleState.MATERIALIZED, WorkspaceLifecycleState.EXECUTING, WorkspaceLifecycleState.RECONSTRUCTED, WorkspaceLifecycleState.PERSISTED}:
            raise WorkspaceConflictError("Workspace cannot capture from current state")
        if workspace.materialization_manifest_ref is None:
            raise WorkspaceIntegrityError("Workspace lacks exact materialization manifest")
        tests = tuple(test_artifact_refs)
        for ref in tests:
            if not isinstance(ref, ArtifactRef) or ref.project_ref != workspace.project_ref:
                raise WorkspaceScopeError("Workspace test Artifact crossed Project scope")
            self.artifacts.get_artifact(access, ref)
        semantic = _sha({"test_artifact_refs": [item.value for item in sorted(tests, key=lambda item: item.value)], "workspace_ref": workspace_ref.value})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch_workspace(connection, workspace_ref, None)
            prior = self._claim_operation(connection, current, "CAPTURE", idempotency_key, semantic)
            if prior is not None and prior["snapshot_sequence"] is not None:
                receipt = self._fetch_receipt(connection, WorkspaceSnapshotRef(workspace_ref, cast(int, prior["snapshot_sequence"])))
                connection.commit()
                return receipt
            connection.commit()
        finally:
            connection.close()

        policy = self.get_policy(access, workspace.execution_policy_ref)
        entries, scan_calls = self._scan(access, attempt, workspace, policy, idempotency_material=f"{idempotency_key}-candidate", cancelled=cancelled)
        base_entries = self._load_manifest(workspace.materialization_manifest_ref)
        base = {item.path: item for item in base_entries}
        candidate = {item.path: item for item in entries}
        base_symlinks = {path for path, item in base.items() if item.kind == "symlink"}
        candidate_symlinks = {path for path, item in candidate.items() if item.kind == "symlink"}
        if base_symlinks != candidate_symlinks:
            raise WorkspaceAuthorityError("Changed candidate symlink state requires an exact Git adapter snapshot")
        deleted = tuple(sorted(set(base) - set(candidate)))
        changed_refs = tuple(
            item.content_ref for path, item in candidate.items()
            if item.kind == "file" and item.content_ref is not None and base.get(path) != item
        )
        manifest_ref = self._store_manifest(workspace, entries, base=False)
        diff: RepositoryDiffReceipt | None = None
        repository_head: str | None = None
        repository_tree: str | None = None
        repository_bundle: ContentRef | None = None
        git_calls: tuple[ToolCallRef, ...] = ()
        if workspace.workspace_type is WorkspaceType.REPOSITORY:
            if self.git is None or workspace.repository_workspace_ref is None:
                raise WorkspaceIntegrityError("Repository Workspace lacks Git materialization")
            self._require_capability(policy, GitAdapter.capability_ref("diff"))
            self._require_capability(policy, GitAdapter.capability_ref("read"))
            repository = self.git.get_current_workspace(access, workspace.repository_workspace_ref)
            repository_head = repository.current_commit_sha
            repository_tree = repository.current_tree_sha
            repository_bundle, bundle_calls = self.git.export_workspace_bundle(
                access,
                attempt,
                repository,
                idempotency_key=_adapter_key(idempotency_key, "git-bundle"),
            )
            diff = self.git.diff(
                access,
                attempt,
                repository,
                idempotency_key=_adapter_key(idempotency_key, "git-diff"),
                excluded_path_components=tuple(_SKIP_COMPONENTS),
                excluded_path_names=tuple(_DEFAULT_SECRET_NAMES),
                excluded_path_prefixes=policy.secret_mount_paths,
            )
            git_calls = tuple((*bundle_calls, *diff.process_call_refs, diff.tool_call_ref))
        all_calls = tuple(sorted(set((*self._workspace_evidence_refs(workspace_ref), *scan_calls, *git_calls)), key=lambda item: item.call_id))
        source_artifacts = tuple(item.artifact_ref for item in workspace.base_sources if isinstance(item, WorkspaceFileSource)) + tests
        evidence_refs = tuple(ref for ref in (manifest_ref, *changed_refs, repository_bundle, None if diff is None else diff.staged_diff_ref, None if diff is None else diff.unstaged_diff_ref, None if diff is None else diff.untracked_manifest_ref) if isinstance(ref, ContentRef))
        artifact = self.artifacts.create_artifact(
            access, project_ref=workspace.project_ref, role="workspace.snapshot", content_ref=manifest_ref,
            source_refs=(), source_artifact_refs=source_artifacts,
            source_content_refs=evidence_refs, derivation_type="workspace.capture",
            metadata={"schema_ref": "schema://biella/workspace-snapshot/1", "schema_version": "1", "semantic_label": "candidate-workspace-snapshot"},
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            head = self._fetch_workspace(connection, workspace_ref, None)
            if head.generation != workspace.generation:
                raise WorkspaceConflictError("Workspace changed while capturing")
            row = connection.execute("SELECT COALESCE(MAX(sequence),0)+1 AS next FROM workspace_snapshots WHERE project_id=? AND workspace_id=?", (workspace.project_ref.value, workspace.workspace_ref.workspace_id)).fetchone()
            sequence = cast(int, row["next"])
            now = self._now(connection)
            snapshot_ref = WorkspaceSnapshotRef(workspace_ref, sequence)
            snapshot = WorkspaceSnapshot(
                snapshot_ref, workspace.generation, workspace.base_revision, entries, deleted, manifest_ref,
                repository_head, repository_tree,
                None if diff is None else diff.staged_diff_ref,
                None if diff is None else diff.unstaged_diff_ref,
                None if diff is None else diff.untracked_manifest_ref,
                repository_bundle,
                all_calls, artifact.artifact_ref, now,
            )
            receipt = CandidateWorkspaceReceipt(
                workspace_ref, snapshot_ref, workspace.base_revision, manifest_ref, changed_refs, deleted,
                repository_head, repository_tree,
                None if diff is None else diff.staged_diff_ref,
                None if diff is None else diff.unstaged_diff_ref,
                None if diff is None else diff.untracked_manifest_ref,
                repository_bundle,
                tests, all_calls, artifact.artifact_ref, now,
            )
            connection.execute("INSERT INTO workspace_snapshots VALUES (?,?,?,?,?)", (workspace.project_ref.value, workspace.workspace_ref.workspace_id, sequence, _json(snapshot.payload()), snapshot.record_sha256))
            connection.execute("INSERT INTO workspace_receipts VALUES (?,?,?,?,?)", (workspace.project_ref.value, workspace.workspace_ref.workspace_id, sequence, _json(receipt.payload()), receipt.receipt_sha256))
            result = self._advance(
                connection,
                head,
                status=WorkspaceLifecycleState.PERSISTED,
                repository_workspace_ref=None if diff is None else diff.workspace_ref,
                latest_snapshot_ref=snapshot_ref,
            )
            self._record_calls(connection, result, all_calls)
            self._finish_claim(connection, result, "CAPTURE", idempotency_key, generation=result.generation, snapshot_sequence=sequence, receipt_sha256=receipt.receipt_sha256)
            connection.commit()
            return receipt
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise WorkspaceConflictError("Workspace snapshot persistence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _fetch_snapshot(self, connection: sqlite3.Connection, ref: WorkspaceSnapshotRef) -> WorkspaceSnapshot:
        row = connection.execute("SELECT * FROM workspace_snapshots WHERE project_id=? AND workspace_id=? AND sequence=?", (ref.project_ref.value, ref.workspace_ref.workspace_id, ref.sequence)).fetchone()
        if row is None:
            raise WorkspaceNotFoundError("Workspace snapshot not found")
        try:
            value = cast(dict[str, object], json.loads(cast(str, row["snapshot_json"])))
            entries = tuple(
                WorkspaceFileEntry(cast(str, item["path"]), cast(str, item["kind"]), cast(int | None, item["mode"]), None if item["content_ref"] is None else _content_from(cast(dict[str, object], item["content_ref"])))
                for item in cast(list[dict[str, object]], value["entries"])
            )
            artifact_value = cast(str, value["artifact_ref"])
            artifact_parts = artifact_value.split("/")
            snapshot = WorkspaceSnapshot(
                ref, cast(int, value["workspace_generation"]), cast(str, value["base_revision"]),
                entries, tuple(cast(list[str], value["deleted_paths"])),
                _content_from(cast(dict[str, object], value["manifest_ref"])),
                cast(str | None, value["repository_head_commit"]), cast(str | None, value["repository_head_tree"]),
                None if value["staged_diff_ref"] is None else _content_from(cast(dict[str, object], value["staged_diff_ref"])),
                None if value["unstaged_diff_ref"] is None else _content_from(cast(dict[str, object], value["unstaged_diff_ref"])),
                None if value["untracked_manifest_ref"] is None else _content_from(cast(dict[str, object], value["untracked_manifest_ref"])),
                None if value["repository_bundle_ref"] is None else _content_from(cast(dict[str, object], value["repository_bundle_ref"])),
                tuple(ToolCallRef(ref.project_ref, item.rsplit("/", 1)[1]) for item in cast(list[str], value["tool_call_refs"])),
                ArtifactRef(ref.project_ref, artifact_parts[-2], int(artifact_parts[-1])), cast(str, value["created_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, WorkspaceError) as exc:
            raise WorkspaceIntegrityError("Persisted Workspace snapshot is malformed") from exc
        if not hmac.compare_digest(snapshot.record_sha256, cast(str, row["record_sha256"])):
            raise WorkspaceIntegrityError("Workspace snapshot evidence changed")
        durable_refs = tuple(
            ref_value
            for ref_value in (
                snapshot.manifest_ref,
                snapshot.staged_diff_ref,
                snapshot.unstaged_diff_ref,
                snapshot.untracked_manifest_ref,
                snapshot.repository_bundle_ref,
                *(item.content_ref for item in snapshot.entries),
            )
            if isinstance(ref_value, ContentRef)
        )
        try:
            for durable_ref in durable_refs:
                self.object_store.verify(durable_ref)
        except ObjectStorageError as exc:
            raise WorkspaceIntegrityError("Workspace snapshot content is unavailable") from exc
        if self._load_manifest(snapshot.manifest_ref) != snapshot.entries:
            raise WorkspaceIntegrityError("Workspace snapshot entries differ from its durable manifest")
        return snapshot

    def _fetch_receipt(self, connection: sqlite3.Connection, ref: WorkspaceSnapshotRef) -> CandidateWorkspaceReceipt:
        row = connection.execute("SELECT * FROM workspace_receipts WHERE project_id=? AND workspace_id=? AND snapshot_sequence=?", (ref.project_ref.value, ref.workspace_ref.workspace_id, ref.sequence)).fetchone()
        if row is None:
            raise WorkspaceNotFoundError("Candidate Workspace receipt not found")
        try:
            value = cast(dict[str, object], json.loads(cast(str, row["receipt_json"])))
            artifact_parts = cast(str, value["snapshot_artifact_ref"]).split("/")
            receipt = CandidateWorkspaceReceipt(
                ref.workspace_ref, ref, cast(str, value["base_revision"]),
                _content_from(cast(dict[str, object], value["candidate_manifest_ref"])),
                tuple(_content_from(item) for item in cast(list[dict[str, object]], value["changed_content_refs"])),
                tuple(cast(list[str], value["deleted_paths"])),
                cast(str | None, value["repository_head_commit"]), cast(str | None, value["repository_head_tree"]),
                None if value["staged_diff_ref"] is None else _content_from(cast(dict[str, object], value["staged_diff_ref"])),
                None if value["unstaged_diff_ref"] is None else _content_from(cast(dict[str, object], value["unstaged_diff_ref"])),
                None if value["untracked_manifest_ref"] is None else _content_from(cast(dict[str, object], value["untracked_manifest_ref"])),
                None if value["repository_bundle_ref"] is None else _content_from(cast(dict[str, object], value["repository_bundle_ref"])),
                tuple(ArtifactRef(ref.project_ref, item.split("/")[-2], int(item.split("/")[-1])) for item in cast(list[str], value["test_artifact_refs"])),
                tuple(ToolCallRef(ref.project_ref, item.rsplit("/", 1)[1]) for item in cast(list[str], value["tool_call_refs"])),
                ArtifactRef(ref.project_ref, artifact_parts[-2], int(artifact_parts[-1])), cast(str, value["created_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, WorkspaceError) as exc:
            raise WorkspaceIntegrityError("Persisted Candidate Workspace receipt is malformed") from exc
        if not hmac.compare_digest(receipt.receipt_sha256, cast(str, row["receipt_sha256"])):
            raise WorkspaceIntegrityError("Candidate Workspace receipt evidence changed")
        snapshot = self._fetch_snapshot(connection, ref)
        workspace = self._fetch_workspace(connection, ref.workspace_ref, None)
        if workspace.materialization_manifest_ref is None:
            raise WorkspaceIntegrityError("Workspace receipt lacks its exact base manifest")
        base = {item.path: item for item in self._load_manifest(workspace.materialization_manifest_ref)}
        expected_changed = tuple(
            item.content_ref
            for item in snapshot.entries
            if item.kind == "file" and item.content_ref is not None and base.get(item.path) != item
        )
        if (
            receipt.candidate_manifest_ref != snapshot.manifest_ref
            or receipt.snapshot_artifact_ref != snapshot.artifact_ref
            or receipt.base_revision != snapshot.base_revision
            or receipt.changed_content_refs != tuple(sorted(set(expected_changed), key=lambda item: (item.digest, item.size_bytes, item.media_type)))
            or receipt.deleted_paths != snapshot.deleted_paths
            or receipt.repository_head_commit != snapshot.repository_head_commit
            or receipt.repository_head_tree != snapshot.repository_head_tree
            or receipt.staged_diff_ref != snapshot.staged_diff_ref
            or receipt.unstaged_diff_ref != snapshot.unstaged_diff_ref
            or receipt.untracked_manifest_ref != snapshot.untracked_manifest_ref
            or receipt.repository_bundle_ref != snapshot.repository_bundle_ref
            or receipt.tool_call_refs != snapshot.tool_call_refs
        ):
            raise WorkspaceIntegrityError("Workspace snapshot and receipt evidence differ")
        return receipt

    def get_snapshot(self, access: ProjectAccess, ref: WorkspaceSnapshotRef) -> WorkspaceSnapshot:
        if not isinstance(ref, WorkspaceSnapshotRef):
            raise WorkspaceContractError("exact WorkspaceSnapshotRef is required")
        self._authorize(access, ref.project_ref)
        connection = self._connect()
        try:
            return self._fetch_snapshot(connection, ref)
        finally:
            connection.close()

    def get_receipt(self, access: ProjectAccess, ref: WorkspaceSnapshotRef) -> CandidateWorkspaceReceipt:
        if not isinstance(ref, WorkspaceSnapshotRef):
            raise WorkspaceContractError("exact WorkspaceSnapshotRef is required")
        self._authorize(access, ref.project_ref)
        connection = self._connect()
        try:
            return self._fetch_receipt(connection, ref)
        finally:
            connection.close()

    def snapshot(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace_ref: WorkspaceRef, *, test_artifact_refs: Sequence[ArtifactRef] = (), idempotency_key: str, cancelled: Callable[[], bool] | None = None) -> CandidateWorkspaceReceipt:
        return self.capture(access, attempt, workspace_ref, test_artifact_refs=test_artifact_refs, idempotency_key=idempotency_key, cancelled=cancelled)

    def _path_exists(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace: Workspace, *, material: str) -> bool:
        try:
            self.filesystem.stat(access, attempt, root_ref=workspace.candidate_root_ref, path=workspace.relative_path, idempotency_key=_adapter_key(material, "exists"))
            return True
        except FilesystemNotFoundError:
            return False

    def _materialize_base_for_reconstruction(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace: Workspace, *, material: str, calls: list[ToolCallRef]) -> RepositoryWorkspaceRef | None:
        if workspace.workspace_type is WorkspaceType.REPOSITORY:
            if self.git is None:
                raise WorkspaceAuthorityError("REPOSITORY reconstruction requires GitAdapter")
            source = cast(WorkspaceRepositorySource, workspace.base_sources[0])
            result = self.git.create_workspace(
                access, attempt, source.repository_ref,
                candidate_root_ref=workspace.candidate_root_ref, relative_path=workspace.relative_path,
                require_source_head=False, idempotency_key=_adapter_key(material, "git-workspace"),
            )
            calls.extend(self._calls_for_attempt(access, attempt, capability=GitAdapter.capability_ref("workspace")))
            return result
        made = self.filesystem.mkdir(access, attempt, root_ref=workspace.candidate_root_ref, path=workspace.relative_path, idempotency_key=_adapter_key(material, "root"))
        calls.append(made.tool_call_ref)
        for index, file_source in enumerate(cast(tuple[WorkspaceFileSource, ...], workspace.base_sources)):
            artifact = self.artifacts.get_artifact(access, file_source.artifact_ref)
            if artifact.content_ref is None:
                raise WorkspaceIntegrityError("Workspace base Artifact content disappeared")
            self._mkdir_parents(access, attempt, workspace, file_source.relative_path, material=f"{material}-{index}", calls=calls)
            written = self.filesystem.write(access, attempt, root_ref=workspace.candidate_root_ref, path=f"{workspace.relative_path}/{file_source.relative_path}", content_ref=artifact.content_ref, idempotency_key=_adapter_key(material, "write", index))
            calls.append(written.tool_call_ref)
        return None

    def _remove_entries(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace: Workspace, entries: Sequence[WorkspaceFileEntry], *, material: str, calls: list[ToolCallRef]) -> None:
        for item in sorted((entry for entry in entries if entry.kind == "file"), key=lambda entry: entry.path, reverse=True):
            removed = self.filesystem.remove(access, attempt, root_ref=workspace.candidate_root_ref, path=f"{workspace.relative_path}/{item.path}", media_type="application/octet-stream", idempotency_key=_adapter_key(material, "file", item.path))
            calls.append(removed.tool_call_ref)
        for item in sorted((entry for entry in entries if entry.kind == "directory"), key=lambda entry: (len(PurePosixPath(entry.path).parts), entry.path), reverse=True):
            removed = self.filesystem.remove(access, attempt, root_ref=workspace.candidate_root_ref, path=f"{workspace.relative_path}/{item.path}", media_type="application/octet-stream", idempotency_key=_adapter_key(material, "dir", item.path))
            calls.append(removed.tool_call_ref)

    def reconstruct(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace_ref: WorkspaceRef, *, idempotency_key: str) -> Workspace:
        _key(idempotency_key)
        self._require_attempt(access, attempt)
        workspace = self.get_workspace(access, workspace_ref)
        if workspace.latest_snapshot_ref is None:
            if not self._path_exists(access, attempt, workspace, material=f"{idempotency_key}-uncaptured"):
                connection = self._connect()
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    head = self._fetch_workspace(connection, workspace_ref, None)
                    if head.latest_snapshot_ref is None:
                        self._advance(connection, head, status=WorkspaceLifecycleState.LOST_UNCAPTURED)
                    connection.commit()
                finally:
                    connection.close()
                raise WorkspaceLostAttemptError("Local Workspace disappeared before capture; current attempt mutation is lost")
            raise WorkspaceConflictError("Workspace has no durable snapshot to reconstruct")
        snapshot = self.get_snapshot(access, workspace.latest_snapshot_ref)
        semantic = _sha({"snapshot_record_sha256": snapshot.record_sha256, "workspace_ref": workspace_ref.value})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch_workspace(connection, workspace_ref, None)
            prior = self._claim_operation(connection, current, "RECONSTRUCT", idempotency_key, semantic)
            if prior is not None and prior["result_generation"] is not None:
                result = self._fetch_workspace(connection, workspace_ref, cast(int, prior["result_generation"]))
                connection.commit()
                return result
            connection.commit()
        finally:
            connection.close()

        policy = self.get_policy(access, workspace.execution_policy_ref)
        calls: list[ToolCallRef] = []
        repository_workspace = workspace.repository_workspace_ref
        exists = self._path_exists(access, attempt, workspace, material=f"{idempotency_key}-candidate")
        if not exists:
            repository_workspace = self._materialize_base_for_reconstruction(access, attempt, workspace, material=f"{idempotency_key}-base", calls=calls)
            if workspace.workspace_type is WorkspaceType.REPOSITORY:
                if (
                    self.git is None
                    or repository_workspace is None
                    or snapshot.repository_head_commit is None
                    or snapshot.repository_head_tree is None
                    or snapshot.staged_diff_ref is None
                    or snapshot.unstaged_diff_ref is None
                ):
                    raise WorkspaceIntegrityError("Repository snapshot reconstruction evidence is incomplete")
                repository_workspace, restore_calls = self.git.restore_workspace_snapshot(
                    access,
                    attempt,
                    repository_workspace,
                    expected_head_commit=snapshot.repository_head_commit,
                    expected_head_tree=snapshot.repository_head_tree,
                    bundle_ref=snapshot.repository_bundle_ref,
                    staged_diff_ref=snapshot.staged_diff_ref,
                    unstaged_diff_ref=snapshot.unstaged_diff_ref,
                    idempotency_key=_adapter_key(idempotency_key, "git-restore"),
                )
                calls.extend(restore_calls)
        elif workspace.workspace_type is WorkspaceType.REPOSITORY:
            if self.git is None or repository_workspace is None:
                raise WorkspaceIntegrityError("Repository Workspace lacks current Git materialization")
            repository_workspace = self.git.get_current_workspace(access, repository_workspace)
        observed, observed_calls = self._scan(access, attempt, workspace, policy, idempotency_material=f"{idempotency_key}-before")
        calls.extend(observed_calls)
        observed_by_path = {item.path: item for item in observed}
        desired_by_path = {item.path: item for item in snapshot.entries}
        removable = tuple(item for path, item in observed_by_path.items() if path not in desired_by_path and item.kind != "symlink")
        self._remove_entries(access, attempt, workspace, removable, material=f"{idempotency_key}-remove", calls=calls)
        for item in sorted((entry for entry in snapshot.entries if entry.kind == "directory"), key=lambda entry: (len(PurePosixPath(entry.path).parts), entry.path)):
            if item.path not in observed_by_path:
                made = self.filesystem.mkdir(access, attempt, root_ref=workspace.candidate_root_ref, path=f"{workspace.relative_path}/{item.path}", idempotency_key=_adapter_key(idempotency_key, "mkdir", item.path))
                calls.append(made.tool_call_ref)
        for item in (entry for entry in snapshot.entries if entry.kind == "file"):
            assert item.content_ref is not None
            self._mkdir_parents(access, attempt, workspace, item.path, material=f"{idempotency_key}-parent-{hashlib.sha256(item.path.encode()).hexdigest()[:12]}", calls=calls)
            written = self.filesystem.write(access, attempt, root_ref=workspace.candidate_root_ref, path=f"{workspace.relative_path}/{item.path}", content_ref=item.content_ref, idempotency_key=_adapter_key(idempotency_key, "write", item.path))
            calls.append(written.tool_call_ref)
        verified, verified_calls = self._scan(access, attempt, workspace, policy, idempotency_material=f"{idempotency_key}-verify")
        calls.extend(verified_calls)
        if verified != snapshot.entries:
            raise WorkspaceIntegrityError("Reconstructed Workspace differs from durable snapshot")
        if workspace.workspace_type is WorkspaceType.REPOSITORY:
            if (
                self.git is None
                or repository_workspace is None
                or snapshot.repository_head_commit is None
                or snapshot.repository_head_tree is None
                or snapshot.staged_diff_ref is None
                or snapshot.unstaged_diff_ref is None
                or snapshot.untracked_manifest_ref is None
            ):
                raise WorkspaceIntegrityError("Repository snapshot verification evidence is incomplete")
            observed_repository = self.git.get_current_workspace(access, repository_workspace)
            observed_diff = self.git.diff(
                access,
                attempt,
                observed_repository,
                idempotency_key=_adapter_key(idempotency_key, "git-verify"),
                excluded_path_components=tuple(_SKIP_COMPONENTS),
                excluded_path_names=tuple(_DEFAULT_SECRET_NAMES),
                excluded_path_prefixes=policy.secret_mount_paths,
            )
            calls.extend((*observed_diff.process_call_refs, observed_diff.tool_call_ref))
            if (
                observed_repository.current_commit_sha != snapshot.repository_head_commit
                or observed_repository.current_tree_sha != snapshot.repository_head_tree
                or observed_diff.staged_diff_ref != snapshot.staged_diff_ref
                or observed_diff.unstaged_diff_ref != snapshot.unstaged_diff_ref
                or observed_diff.untracked_manifest_ref != snapshot.untracked_manifest_ref
            ):
                raise WorkspaceIntegrityError("Reconstructed repository Git state differs from durable snapshot")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            head = self._fetch_workspace(connection, workspace_ref, None)
            if head.generation != workspace.generation:
                raise WorkspaceConflictError("Workspace changed while reconstructing")
            result = self._advance(connection, head, status=WorkspaceLifecycleState.RECONSTRUCTED, repository_workspace_ref=repository_workspace)
            self._record_calls(connection, result, calls)
            self._finish_claim(connection, result, "RECONSTRUCT", idempotency_key, generation=result.generation, snapshot_sequence=snapshot.snapshot_ref.sequence)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _cleanup_walk(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace: Workspace, *, material: str) -> tuple[tuple[WorkspaceFileEntry, ...], tuple[ToolCallRef, ...]]:
        entries: list[WorkspaceFileEntry] = []
        calls: list[ToolCallRef] = []

        def visit(relative: str) -> None:
            full = workspace.relative_path if relative == "." else f"{workspace.relative_path}/{relative}"
            listing = self.filesystem.list(access, attempt, root_ref=workspace.candidate_root_ref, path=full, idempotency_key=_adapter_key(material, "list", relative))
            calls.append(listing.tool_call_ref)
            try:
                children = cast(list[dict[str, object]], cast(dict[str, object], json.loads(self.object_store.read(listing.output_ref)))["entries"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, ObjectStorageError) as exc:
                raise WorkspaceIntegrityError("Workspace cleanup listing is malformed") from exc
            for child in children:
                name = cast(str, child["name"])
                kind = cast(str, child["kind"])
                path = _relative(name if relative == "." else f"{relative}/{name}")
                if kind == "directory":
                    entries.append(WorkspaceFileEntry(path, kind, None, None))
                    visit(path)
                elif kind == "file":
                    entries.append(WorkspaceFileEntry(path, kind, 0, ContentRef.from_bytes(b"", media_type="application/octet-stream")))
                elif kind == "symlink":
                    entries.append(WorkspaceFileEntry(path, kind, None, None))
                else:
                    raise WorkspaceAuthorityError("Workspace cleanup rejected special filesystem object")

        visit(".")
        return tuple(entries), tuple(calls)

    def cleanup(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace_ref: WorkspaceRef, *, idempotency_key: str) -> Workspace:
        _key(idempotency_key)
        self._require_attempt(access, attempt)
        workspace = self.get_workspace(access, workspace_ref)
        if workspace.latest_snapshot_ref is None:
            raise WorkspaceAuthorityError("Workspace cleanup requires a durable snapshot")
        if workspace.status is WorkspaceLifecycleState.CLEANED:
            return workspace
        semantic = _sha({"snapshot_ref": workspace.latest_snapshot_ref.value, "workspace_ref": workspace_ref.value})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch_workspace(connection, workspace_ref, None)
            prior = self._claim_operation(connection, current, "CLEANUP", idempotency_key, semantic)
            if prior is not None and prior["result_generation"] is not None:
                result = self._fetch_workspace(connection, workspace_ref, cast(int, prior["result_generation"]))
                connection.commit()
                return result
            connection.commit()
        finally:
            connection.close()
        calls: list[ToolCallRef] = []
        try:
            if self._path_exists(access, attempt, workspace, material=f"{idempotency_key}-candidate"):
                entries, listing_calls = self._cleanup_walk(access, attempt, workspace, material=f"{idempotency_key}-walk")
                calls.extend(listing_calls)
                symlinks = tuple(item.path for item in entries if item.kind == "symlink")
                if symlinks:
                    raise WorkspaceAuthorityError("Workspace cleanup cannot safely remove candidate symlinks through the current FilesystemAdapter")
                self._remove_entries(access, attempt, workspace, entries, material=f"{idempotency_key}-remove", calls=calls)
                root_removed = self.filesystem.remove(access, attempt, root_ref=workspace.candidate_root_ref, path=workspace.relative_path, media_type="application/octet-stream", idempotency_key=_adapter_key(idempotency_key, "remove-root"))
                calls.append(root_removed.tool_call_ref)
        except Exception as exc:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                head = self._fetch_workspace(connection, workspace_ref, None)
                if head.generation == workspace.generation:
                    self._advance(connection, head, status=WorkspaceLifecycleState.CLEANUP_FAILED)
                connection.commit()
            finally:
                connection.close()
            raise WorkspaceIntegrityError("Workspace cleanup failed and remains durably visible") from exc
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            head = self._fetch_workspace(connection, workspace_ref, None)
            if head.generation != workspace.generation:
                raise WorkspaceConflictError("Workspace changed while cleaning")
            result = self._advance(connection, head, status=WorkspaceLifecycleState.CLEANED)
            self._record_calls(connection, result, calls)
            self._finish_claim(connection, result, "CLEANUP", idempotency_key, generation=result.generation, snapshot_sequence=workspace.latest_snapshot_ref.sequence)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def cancel(self, access: ProjectAccess, attempt: NodeExecutionAttempt, workspace_ref: WorkspaceRef, *, idempotency_key: str, capture_valid_outputs: bool = True) -> Workspace:
        _key(idempotency_key)
        self._require_attempt(access, attempt)
        workspace = self.get_workspace(access, workspace_ref)
        if workspace.status is WorkspaceLifecycleState.CANCELLED:
            return workspace
        if capture_valid_outputs and workspace.latest_snapshot_ref is None and self._path_exists(access, attempt, workspace, material=f"{idempotency_key}-candidate"):
            self.capture(access, attempt, workspace_ref, idempotency_key=f"{idempotency_key}-capture")
            workspace = self.get_workspace(access, workspace_ref)
        if workspace.resource_allocation_ref is not None:
            try:
                allocation = self.scheduler.get_allocation(access, workspace.resource_allocation_ref)
                if allocation.status in {"RESERVED", "DISPATCHING", "DISPATCHED"}:
                    if allocation.node_attempt_id is not None:
                        self.executions.cancel_run(
                            access,
                            workspace.run_ref,
                            idempotency_key=_adapter_key(idempotency_key, "cancel-run"),
                            actor_ref=workspace.workspace_ref.value,
                        )
                    self.scheduler.release(access, allocation, outcome="CANCELLED", idempotency_key=f"{idempotency_key}-release")
            except SchedulerError as exc:
                raise WorkspaceIntegrityError("Workspace cancellation could not release ResourceAllocation") from exc
        semantic = _sha({"capture_valid_outputs": capture_valid_outputs, "latest_snapshot_ref": None if workspace.latest_snapshot_ref is None else workspace.latest_snapshot_ref.value, "workspace_ref": workspace_ref.value})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch_workspace(connection, workspace_ref, None)
            prior = self._claim_operation(connection, current, "CANCEL", idempotency_key, semantic)
            if prior is not None and prior["result_generation"] is not None:
                result = self._fetch_workspace(connection, workspace_ref, cast(int, prior["result_generation"]))
                connection.commit()
                return result
            result = self._advance(connection, current, status=WorkspaceLifecycleState.CANCELLED)
            self._finish_claim(connection, result, "CANCEL", idempotency_key, generation=result.generation, snapshot_sequence=None if result.latest_snapshot_ref is None else result.latest_snapshot_ref.sequence)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # Canonical camel-case compatibility for prompt/API consumers.
    createWorkspace = create_workspace
    createPolicy = create_policy
    beginExecution = begin_execution
    recordToolCall = record_tool_call
    getWorkspace = get_workspace
    getSnapshot = get_snapshot
    getReceipt = get_receipt


__all__ = [
    "CandidateWorkspaceReceipt", "Workspace", "WorkspaceAuthorityError",
    "WorkspaceCancelledError", "WorkspaceConflictError", "WorkspaceContractError",
    "WorkspaceError", "WorkspaceExecutionPolicy", "WorkspaceExecutionPolicyRef",
    "WorkspaceFileEntry", "WorkspaceFileSource", "WorkspaceIntegrityError",
    "WorkspaceLifecycleState", "WorkspaceLostAttemptError", "WorkspaceNetworkPolicy",
    "WorkspaceNotFoundError", "WorkspaceRef", "WorkspaceRepositorySource",
    "WorkspaceRootGrant", "WorkspaceScopeError", "WorkspaceService",
    "WorkspaceSnapshot", "WorkspaceSnapshotRef", "WorkspaceType",
]
