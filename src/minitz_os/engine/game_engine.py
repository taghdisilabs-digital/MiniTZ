"""Provider-neutral game-engine adapter contracts over accepted runtime services."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
from types import MappingProxyType
from typing import Protocol, cast, runtime_checkable

from .artifact import (
    Artifact,
    ArtifactError,
    ArtifactNotFoundError,
    ArtifactRef,
    ArtifactService,
    ContentRef,
)
from .call_ledger import CallLedgerService, ToolCallRef
from .capability import CapabilityRef
from .execution import (
    NodeExecutionAttempt,
    NodeExecutionAuthorityError,
    NodeExecutionError,
    NodeExecutionService,
)
from .filesystem import FilesystemAdapter, FilesystemError, FilesystemRootRef
from .git_adapter import RepositoryRef
from .graph import GraphService
from .isolated_runtime import (
    IsolatedRuntimeAdapter,
    IsolatedRuntimeError,
    IsolatedRuntimeSpec,
    RuntimeDescriptor,
    RuntimeMount,
    RuntimeNetworkPolicy,
    RuntimeReceipt,
    RuntimeRef,
    RuntimeStatus,
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
from .scheduler import ResourceAllocationRef
from .run import ExecutionAttempt, RunAuthorityError, RunError, RunService
from .workspace import (
    WorkspaceError,
    WorkspaceRepositorySource,
    WorkspaceService,
    WorkspaceSnapshotRef,
    WorkspaceType,
)


_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_ROLE = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ASSET_KINDS = frozenset(
    {"3d", "character", "animation", "environment", "image", "audio", "vfx"}
)
_OPERATION_ROLE = {
    "detect": "game.engine.detection",
    "inspect": "game.project.inspection",
    "import": "game.import.output",
    "build": "game.build.output",
    "run": "game.runtime.observation",
    "test": "game.test.result",
    "profile": "game.profile.report",
    "capture": "game.capture.output",
    "export": "game.export.output",
}
_RUNTIME_INPUT_ROOT = "/run/minitz/game-inputs"


class GameEngineError(Exception):
    """Base class for provider-neutral game-engine adapter failures."""


class GameEngineContractError(GameEngineError, ValueError):
    """A game-engine identity, request, or result is malformed."""


class GameEngineScopeError(GameEngineError):
    """Game-engine evidence crossed Project scope."""


class GameEngineAuthorityError(GameEngineError, PermissionError):
    """The exact live Node attempt lacks game-engine authority."""


class GameEngineConflictError(GameEngineError):
    """A game-engine idempotency identity conflicts."""


class GameEngineIntegrityError(GameEngineError):
    """Persisted or provider game-engine evidence failed verification."""


class GameEngineOperation(str, Enum):
    DETECT = "detect"
    INSPECT = "inspect"
    IMPORT = "import"
    BUILD = "build"
    RUN = "run"
    TEST = "test"
    PROFILE = "profile"
    CAPTURE = "capture"
    EXPORT = "export"

    @property
    def capability_ref(self) -> CapabilityRef:
        name = "inspect" if self in {self.DETECT, self.INSPECT} else self.value
        return CapabilityRef(f"game.{name}", "1.0.0")


class GameEngineReality(str, Enum):
    REAL = "REAL"
    REFERENCE = "REFERENCE"
    NOT_RUN = "NOT_RUN"


class GameEngineStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_RUN = "NOT_RUN"


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


def _text(value: object, name: str, maximum: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or any(ord(character) < 32 for character in value)
        or len(value.encode()) > maximum
    ):
        raise GameEngineContractError(f"{name} is malformed or unbounded")
    return value


def _ref(value: object, name: str) -> str:
    if not isinstance(value, str) or _ABSOLUTE_REF.fullmatch(value) is None:
        raise GameEngineContractError(f"{name} must be a bounded absolute reference")
    return value


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise GameEngineContractError(f"{name} must be an exact sha256 digest")
    return value


def _relative(value: object, name: str) -> str:
    text = _text(value, name)
    candidate = PurePosixPath(text)
    if (
        text.startswith("/")
        or "\\" in text
        or tuple(candidate.parts) != tuple(text.split("/"))
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise GameEngineContractError(f"{name} must be a canonical relative path")
    return text


def _content(value: ContentRef | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "algorithm": value.algorithm,
        "digest": value.digest,
        "media_type": value.media_type,
        "size_bytes": value.size_bytes,
    }


def _content_from(value: object) -> ContentRef | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise GameEngineIntegrityError("persisted game-engine ContentRef is malformed")
    try:
        return ContentRef(
            cast(str, value["algorithm"]),
            cast(str, value["digest"]),
            cast(int, value["size_bytes"]),
            cast(str, value["media_type"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GameEngineIntegrityError(
            "persisted game-engine ContentRef is malformed"
        ) from exc


def _artifact_from(value: object, project_ref: ProjectRef) -> ArtifactRef:
    prefix = f"artifact://{project_ref.value}/"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise GameEngineScopeError("persisted game-engine Artifact crossed Project scope")
    try:
        artifact_id, revision = value.removeprefix(prefix).rsplit("/", 1)
        return ArtifactRef(project_ref, artifact_id, int(revision))
    except (TypeError, ValueError) as exc:
        raise GameEngineIntegrityError(
            "persisted game-engine Artifact identity is malformed"
        ) from exc


def _tool_from(value: object, project_ref: ProjectRef) -> ToolCallRef:
    prefix = f"tool-call://{project_ref.value}/"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise GameEngineScopeError("persisted game-engine ToolCall crossed Project scope")
    return ToolCallRef(project_ref, value.removeprefix(prefix))


def _runtime_from(value: object, project_ref: ProjectRef) -> RuntimeRef | None:
    if value is None:
        return None
    prefix = f"isolated-runtime://{project_ref.value}/"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise GameEngineScopeError("persisted game-engine runtime crossed Project scope")
    try:
        runtime_id, generation = value.removeprefix(prefix).rsplit("/", 1)
        return RuntimeRef(project_ref, runtime_id, int(generation))
    except (TypeError, ValueError) as exc:
        raise GameEngineIntegrityError(
            "persisted game-engine runtime identity is malformed"
        ) from exc


@dataclass(frozen=True)
class GameEngineResourceRequirements:
    """Project-selected resource declaration; never a global engine threshold."""

    cpu_cores: float | None = None
    memory_bytes: int | None = None
    storage_bytes: int | None = None
    gpu_required: bool = False
    headless_supported: bool = False
    interactive_supported: bool = False

    def __post_init__(self) -> None:
        if self.cpu_cores is not None and (
            isinstance(self.cpu_cores, bool)
            or not isinstance(self.cpu_cores, (int, float))
            or not 0 < float(self.cpu_cores) <= 65_536
        ):
            raise GameEngineContractError("game CPU requirement is malformed")
        for value, name in (
            (self.memory_bytes, "memory_bytes"),
            (self.storage_bytes, "storage_bytes"),
        ):
            if value is not None and (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
                or value > 2**63 - 1
            ):
                raise GameEngineContractError(f"game {name} requirement is malformed")
        if not all(
            isinstance(value, bool)
            for value in (
                self.gpu_required,
                self.headless_supported,
                self.interactive_supported,
            )
        ):
            raise GameEngineContractError("game runtime support flags must be boolean")

    def payload(self) -> dict[str, object]:
        return {
            "cpu_cores": None if self.cpu_cores is None else float(self.cpu_cores),
            "gpu_required": self.gpu_required,
            "headless_supported": self.headless_supported,
            "interactive_supported": self.interactive_supported,
            "memory_bytes": self.memory_bytes,
            "storage_bytes": self.storage_bytes,
        }


@dataclass(frozen=True, order=True)
class GameAssetInput:
    """Exact downstream-pack Artifact seam, scoped to one Project."""

    kind: str
    artifact_ref: ArtifactRef

    def __post_init__(self) -> None:
        if self.kind not in _ASSET_KINDS:
            raise GameEngineContractError("game asset input kind is unsupported")
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("game asset input requires exact ArtifactRef")

    @property
    def expected_role(self) -> str:
        return f"game.asset.{self.kind}.input"

    def payload(self) -> dict[str, str]:
        return {"artifact_ref": self.artifact_ref.value, "kind": self.kind}


@dataclass(frozen=True)
class GameRuntimeInputBinding:
    """Exact authorized Artifact materialization into one isolated runtime path."""

    artifact_ref: ArtifactRef
    artifact_role: str
    content_ref: ContentRef
    runtime_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("game runtime input requires exact ArtifactRef")
        if (
            not isinstance(self.artifact_role, str)
            or _ROLE.fullmatch(self.artifact_role) is None
        ):
            raise GameEngineContractError("game runtime input Artifact role is malformed")
        if not isinstance(self.content_ref, ContentRef):
            raise TypeError("game runtime input requires exact ContentRef")
        object.__setattr__(
            self,
            "runtime_path",
            _relative(self.runtime_path, "game runtime input path"),
        )
        if self.runtime_path == "bindings.json":
            raise GameEngineContractError(
                "game runtime input path is reserved for exact binding evidence"
            )

    @property
    def container_path(self) -> str:
        return f"{_RUNTIME_INPUT_ROOT}/{self.runtime_path}"

    def payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref.value,
            "artifact_role": self.artifact_role,
            "content_ref": _content(self.content_ref),
            "runtime_path": self.runtime_path,
        }


@dataclass(frozen=True)
class GameProjectIdentity:
    """Exact source, candidate, engine, config, target, and runtime identity."""

    project_ref: ProjectRef
    repository_ref: RepositoryRef
    candidate_snapshot_ref: WorkspaceSnapshotRef
    candidate_artifact_ref: ArtifactRef
    source_commit: str
    source_tree: str
    adapter_ref: str
    engine_name: str
    engine_version: str
    engine_executable_path: str
    engine_version_args: tuple[str, ...]
    project_config_path: str
    project_config_sha256: str
    entry_scene: str
    target: str
    build_export_config_path: str
    build_export_config_sha256: str
    toolchain_ref: str
    runtime_ref: str
    executable_sha256: str
    cache_paths: tuple[str, ...]
    resource_requirements: GameEngineResourceRequirements
    semantic_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("game identity requires exact ProjectRef")
        if not isinstance(self.repository_ref, RepositoryRef):
            raise TypeError("game identity requires exact RepositoryRef")
        if not isinstance(self.candidate_snapshot_ref, WorkspaceSnapshotRef):
            raise TypeError("game identity requires exact WorkspaceSnapshotRef")
        if not isinstance(self.candidate_artifact_ref, ArtifactRef):
            raise TypeError("game identity requires exact candidate ArtifactRef")
        scoped = (
            self.repository_ref.project_ref,
            self.candidate_snapshot_ref.project_ref,
            self.candidate_artifact_ref.project_ref,
        )
        if any(project != self.project_ref for project in scoped):
            raise GameEngineScopeError("game source or candidate crossed Project scope")
        object_length = 40 if self.repository_ref.object_format == "sha1" else 64
        object_pattern = re.compile(rf"[0-9a-f]{{{object_length}}}")
        if object_pattern.fullmatch(self.source_commit) is None:
            raise GameEngineContractError("game source commit identity is malformed")
        if object_pattern.fullmatch(self.source_tree) is None:
            raise GameEngineContractError("game source tree identity is malformed")
        if (
            self.source_commit != self.repository_ref.commit_sha
            or self.source_tree != self.repository_ref.tree_sha
        ):
            raise GameEngineIntegrityError(
                "game source revision differs from exact RepositoryRef"
            )
        object.__setattr__(self, "adapter_ref", _ref(self.adapter_ref, "game adapter_ref"))
        object.__setattr__(self, "engine_name", _text(self.engine_name, "engine_name", 256))
        object.__setattr__(self, "engine_version", _text(self.engine_version, "engine_version", 512))
        if (
            not isinstance(self.engine_executable_path, str)
            or not self.engine_executable_path.startswith("/")
            or "\x00" in self.engine_executable_path
            or PurePosixPath(self.engine_executable_path).as_posix()
            != self.engine_executable_path
            or any(part in {"", ".", ".."} for part in PurePosixPath(self.engine_executable_path).parts[1:])
        ):
            raise GameEngineContractError(
                "engine executable requires an exact absolute runtime path"
            )
        if (
            not isinstance(self.engine_version_args, tuple)
            or not self.engine_version_args
            or len(self.engine_version_args) > 16
            or any(
                not isinstance(item, str)
                or not item
                or "\x00" in item
                or len(item.encode()) > 1024
                for item in self.engine_version_args
            )
        ):
            raise GameEngineContractError(
                "engine version probe arguments are absent or malformed"
            )
        object.__setattr__(
            self,
            "project_config_path",
            _relative(self.project_config_path, "project_config_path"),
        )
        _sha(self.project_config_sha256, "project_config_sha256")
        object.__setattr__(self, "entry_scene", _relative(self.entry_scene, "entry_scene"))
        object.__setattr__(self, "target", _text(self.target, "target", 512))
        object.__setattr__(
            self,
            "build_export_config_path",
            _relative(
                self.build_export_config_path,
                "build_export_config_path",
            ),
        )
        _sha(self.build_export_config_sha256, "build_export_config_sha256")
        object.__setattr__(self, "toolchain_ref", _ref(self.toolchain_ref, "toolchain_ref"))
        object.__setattr__(self, "runtime_ref", _ref(self.runtime_ref, "runtime_ref"))
        _sha(self.executable_sha256, "executable_sha256")
        if (
            not isinstance(self.cache_paths, tuple)
            or len(self.cache_paths) > 64
            or len(set(self.cache_paths)) != len(self.cache_paths)
        ):
            raise GameEngineContractError("game cache paths are duplicated or unbounded")
        object.__setattr__(
            self,
            "cache_paths",
            tuple(sorted(_relative(item, "cache path") for item in self.cache_paths)),
        )
        authoritative_paths = (
            self.project_config_path,
            self.entry_scene,
            self.build_export_config_path,
        )
        for cache_path in self.cache_paths:
            cache = PurePosixPath(cache_path)
            if any(
                PurePosixPath(path) == cache
                or PurePosixPath(path).is_relative_to(cache)
                for path in authoritative_paths
            ):
                raise GameEngineContractError(
                    "game cache cannot contain authoritative Project source"
                )
        if not isinstance(self.resource_requirements, GameEngineResourceRequirements):
            raise TypeError("game identity requires resource requirements")
        object.__setattr__(self, "semantic_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "build_export_config_sha256": self.build_export_config_sha256,
            "build_export_config_path": self.build_export_config_path,
            "cache_paths": list(self.cache_paths),
            "candidate_artifact_ref": self.candidate_artifact_ref.value,
            "candidate_snapshot_ref": self.candidate_snapshot_ref.value,
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "engine_executable_path": self.engine_executable_path,
            "engine_version_args": list(self.engine_version_args),
            "entry_scene": self.entry_scene,
            "executable_sha256": self.executable_sha256,
            "project_config_path": self.project_config_path,
            "project_config_sha256": self.project_config_sha256,
            "project_ref": self.project_ref.value,
            "repository_ref": self.repository_ref.value,
            "repository_record_sha256": self.repository_ref.record_sha256,
            "resource_requirements": self.resource_requirements.payload(),
            "runtime_ref": self.runtime_ref,
            "source_commit": self.source_commit,
            "source_tree": self.source_tree,
            "target": self.target,
            "toolchain_ref": self.toolchain_ref,
        }


@dataclass(frozen=True)
class GameEngineOperationRequest:
    """One exact semantic adapter request; commands remain trusted Task data."""

    operation: GameEngineOperation
    identity: GameProjectIdentity
    control_root_ref: FilesystemRootRef
    runtime_spec: IsolatedRuntimeSpec | None
    build_artifact_ref: ArtifactRef | None
    asset_inputs: tuple[GameAssetInput, ...]
    reference_evidence_refs: tuple[ArtifactRef, ...]
    output_roles: tuple[str, ...]
    requested_metrics: tuple[str, ...]
    required_output_markers: tuple[str, ...] = ()
    forbidden_output_markers: tuple[str, ...] = ()
    resource_allocation_ref: ResourceAllocationRef | None = None
    runtime_input_bindings: tuple[GameRuntimeInputBinding, ...] = ()
    request_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.operation, GameEngineOperation):
            raise GameEngineContractError("game operation is malformed")
        if not isinstance(self.identity, GameProjectIdentity):
            raise TypeError("game request requires exact GameProjectIdentity")
        if not isinstance(self.control_root_ref, FilesystemRootRef):
            raise TypeError("game request requires exact control FilesystemRootRef")
        project = self.identity.project_ref
        if self.control_root_ref.project_ref != project:
            raise GameEngineScopeError("game control root crossed Project scope")
        if self.runtime_spec is not None:
            if not isinstance(self.runtime_spec, IsolatedRuntimeSpec):
                raise TypeError("runtime_spec must implement exact IsolatedRuntimeSpec")
            if self.runtime_spec.project_ref != project:
                raise GameEngineScopeError("game runtime spec crossed Project scope")
        if self.build_artifact_ref is not None and self.build_artifact_ref.project_ref != project:
            raise GameEngineScopeError("game build Artifact crossed Project scope")
        if (
            not isinstance(self.asset_inputs, tuple)
            or len(self.asset_inputs) > 128
            or len(set(self.asset_inputs)) != len(self.asset_inputs)
        ):
            raise GameEngineContractError("game asset inputs are duplicated or unbounded")
        if any(item.artifact_ref.project_ref != project for item in self.asset_inputs):
            raise GameEngineScopeError("game asset input crossed Project scope")
        if (
            not isinstance(self.reference_evidence_refs, tuple)
            or len(self.reference_evidence_refs) > 128
            or len(set(self.reference_evidence_refs)) != len(self.reference_evidence_refs)
        ):
            raise GameEngineContractError("reference evidence is duplicated or unbounded")
        if any(item.project_ref != project for item in self.reference_evidence_refs):
            raise GameEngineScopeError("reference evidence crossed Project scope")
        if (
            not isinstance(self.output_roles, tuple)
            or not self.output_roles
            or len(self.output_roles) > 128
        ):
            raise GameEngineContractError("game output roles are absent or unbounded")
        if any(not isinstance(item, str) or _ROLE.fullmatch(item) is None for item in self.output_roles):
            raise GameEngineContractError("game output role is malformed")
        expected_role = _OPERATION_ROLE[self.operation.value]
        if any(item != expected_role for item in self.output_roles):
            raise GameEngineContractError(
                "game output role differs from the exact adapter operation"
            )
        expected = (
            1
            if self.operation is GameEngineOperation.DETECT
            and self.runtime_spec is not None
            and not self.runtime_spec.outputs
            else (
                len(self.runtime_spec.outputs)
                if self.runtime_spec is not None
                else len(self.reference_evidence_refs)
            )
        )
        if len(self.output_roles) != expected:
            raise GameEngineContractError("game output roles do not match exact outputs")
        if (
            not isinstance(self.requested_metrics, tuple)
            or len(self.requested_metrics) > 128
            or len(set(self.requested_metrics)) != len(self.requested_metrics)
        ):
            raise GameEngineContractError("requested game metrics are duplicated or unbounded")
        object.__setattr__(
            self,
            "requested_metrics",
            tuple(sorted(_text(item, "requested metric", 256) for item in self.requested_metrics)),
        )
        if self.operation is not GameEngineOperation.PROFILE and self.requested_metrics:
            raise GameEngineContractError("game metrics belong only to an explicit profile request")
        for field_name in ("required_output_markers", "forbidden_output_markers"):
            values = getattr(self, field_name)
            if (
                not isinstance(values, tuple)
                or len(values) > 128
                or len(set(values)) != len(values)
            ):
                raise GameEngineContractError(
                    "game output markers are duplicated or unbounded"
                )
            object.__setattr__(
                self,
                field_name,
                tuple(sorted(_text(item, "game output marker", 4096) for item in values)),
            )
        if set(self.required_output_markers) & set(self.forbidden_output_markers):
            raise GameEngineContractError("game output marker requirements conflict")
        if self.resource_allocation_ref is not None and (
            not isinstance(self.resource_allocation_ref, ResourceAllocationRef)
            or self.resource_allocation_ref.project_ref != project
        ):
            raise GameEngineScopeError("game ResourceAllocation crossed Project scope")
        if (
            not isinstance(self.runtime_input_bindings, tuple)
            or len(self.runtime_input_bindings) > 128
            or any(
                not isinstance(item, GameRuntimeInputBinding)
                for item in self.runtime_input_bindings
            )
        ):
            raise GameEngineContractError(
                "game runtime input bindings are malformed or unbounded"
            )
        if any(
            item.artifact_ref.project_ref != project
            for item in self.runtime_input_bindings
        ):
            raise GameEngineScopeError(
                "game runtime input binding crossed Project scope"
            )
        if len({item.artifact_ref for item in self.runtime_input_bindings}) != len(
            self.runtime_input_bindings
        ):
            raise GameEngineContractError(
                "game runtime input Artifact bindings are duplicated"
            )
        if len({item.runtime_path for item in self.runtime_input_bindings}) != len(
            self.runtime_input_bindings
        ):
            raise GameEngineContractError(
                "game runtime input paths are duplicated"
            )
        object.__setattr__(self, "request_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.identity.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "asset_inputs": [item.payload() for item in self.asset_inputs],
            "build_artifact_ref": (
                None if self.build_artifact_ref is None else self.build_artifact_ref.value
            ),
            "control_root_ref": self.control_root_ref.value,
            "identity_digest": self.identity.semantic_digest,
            "operation": self.operation.value,
            "output_roles": list(self.output_roles),
            "reference_evidence_refs": [
                item.value for item in self.reference_evidence_refs
            ],
            "requested_metrics": list(self.requested_metrics),
            "required_output_markers": list(self.required_output_markers),
            "forbidden_output_markers": list(self.forbidden_output_markers),
            "resource_allocation_ref": (
                None
                if self.resource_allocation_ref is None
                else self.resource_allocation_ref.value
            ),
            "runtime_input_bindings": [
                item.payload() for item in self.runtime_input_bindings
            ],
            "runtime_spec": None if self.runtime_spec is None else self.runtime_spec.payload(),
            "runtime_spec_sha256": (
                None if self.runtime_spec is None else self.runtime_spec.spec_sha256
            ),
        }


@dataclass(frozen=True)
class GameEngineOperationResult:
    project_ref: ProjectRef
    operation: GameEngineOperation
    identity_digest: str
    request_sha256: str
    adapter_ref: str
    reality: GameEngineReality
    status: GameEngineStatus
    node_attempt_id: str
    node_fence: int
    runtime_ref: RuntimeRef | None
    receipt_artifact_refs: tuple[ArtifactRef, ...]
    tool_call_refs: tuple[ToolCallRef, ...]
    output_artifact_refs: tuple[ArtifactRef, ...]
    output_roles: tuple[str, ...]
    stdout_ref: ContentRef | None
    stderr_ref: ContentRef | None
    failure_reason: str | None
    runtime_observed: bool
    reused_verified_build: bool
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("game result requires exact ProjectRef")
        if not isinstance(self.operation, GameEngineOperation):
            raise GameEngineContractError("game result operation is malformed")
        _sha(self.identity_digest, "identity_digest")
        _sha(self.request_sha256, "request_sha256")
        object.__setattr__(self, "adapter_ref", _ref(self.adapter_ref, "adapter_ref"))
        if not isinstance(self.reality, GameEngineReality) or not isinstance(
            self.status, GameEngineStatus
        ):
            raise GameEngineContractError("game result classification is malformed")
        if not isinstance(self.node_attempt_id, str) or not self.node_attempt_id:
            raise GameEngineContractError("game result Node attempt is malformed")
        if not isinstance(self.node_fence, int) or isinstance(self.node_fence, bool) or self.node_fence < 1:
            raise GameEngineContractError("game result Node fence is malformed")
        if self.runtime_ref is not None and self.runtime_ref.project_ref != self.project_ref:
            raise GameEngineScopeError("game result runtime crossed Project scope")
        for collection, label in (
            (self.receipt_artifact_refs, "receipt Artifacts"),
            (self.tool_call_refs, "ToolCalls"),
            (self.output_artifact_refs, "output Artifacts"),
        ):
            if not isinstance(collection, tuple) or len(set(collection)) != len(collection):
                raise GameEngineContractError(f"game result {label} are duplicated")
            if any(item.project_ref != self.project_ref for item in collection):
                raise GameEngineScopeError(f"game result {label} crossed Project scope")
        if (
            not isinstance(self.output_roles, tuple)
            or any(not isinstance(item, str) or _ROLE.fullmatch(item) is None for item in self.output_roles)
        ):
            raise GameEngineContractError("game result output roles are malformed")
        if len(self.output_roles) != len(self.output_artifact_refs):
            raise GameEngineContractError("game result lacks exact output role evidence")
        if self.status is GameEngineStatus.SUCCEEDED and not self.output_artifact_refs:
            raise GameEngineContractError("successful game result lacks durable output evidence")
        if self.failure_reason is not None:
            object.__setattr__(self, "failure_reason", _text(self.failure_reason, "failure_reason"))
        if (self.status is GameEngineStatus.SUCCEEDED) == (self.failure_reason is not None):
            raise GameEngineContractError("game status and failure evidence differ")
        if not isinstance(self.runtime_observed, bool):
            raise GameEngineContractError("runtime_observed must be boolean")
        if self.runtime_observed and (
            self.operation is not GameEngineOperation.RUN
            or self.status is not GameEngineStatus.SUCCEEDED
            or "game.runtime.observation" not in self.output_roles
        ):
            raise GameEngineContractError("runtime proof requires a successful exact run output")
        if self.operation is GameEngineOperation.BUILD and self.runtime_observed:
            raise GameEngineContractError("build evidence cannot claim runtime observation")
        if not isinstance(self.reused_verified_build, bool):
            raise GameEngineContractError("verified build reuse classification must be boolean")
        if self.reused_verified_build and (
            self.operation is not GameEngineOperation.BUILD
            or self.status is not GameEngineStatus.SUCCEEDED
            or self.reality is not GameEngineReality.REAL
        ):
            raise GameEngineContractError(
                "only a successful REAL build may reuse verified output"
            )
        if self.reality is GameEngineReality.NOT_RUN:
            if (
                self.status is not GameEngineStatus.NOT_RUN
                or self.runtime_ref is not None
                or self.receipt_artifact_refs
                or self.tool_call_refs
                or self.output_artifact_refs
                or self.runtime_observed
                or self.reused_verified_build
            ):
                raise GameEngineContractError("NOT_RUN evidence is contradictory")
        elif self.status is GameEngineStatus.NOT_RUN:
            raise GameEngineContractError("NOT_RUN status requires NOT_RUN reality")
        if self.reality is GameEngineReality.REFERENCE and self.runtime_observed:
            raise GameEngineContractError("reference evidence cannot claim runtime observation")
        _text(self.observed_at, "observed_at", 128)
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "failure_reason": self.failure_reason,
            "identity_digest": self.identity_digest,
            "node_attempt_id": self.node_attempt_id,
            "node_fence": self.node_fence,
            "observed_at": self.observed_at,
            "operation": self.operation.value,
            "output_artifact_refs": [item.value for item in self.output_artifact_refs],
            "output_roles": list(self.output_roles),
            "project_ref": self.project_ref.value,
            "reality": self.reality.value,
            "receipt_artifact_refs": [item.value for item in self.receipt_artifact_refs],
            "request_sha256": self.request_sha256,
            "runtime_observed": self.runtime_observed,
            "reused_verified_build": self.reused_verified_build,
            "runtime_ref": None if self.runtime_ref is None else self.runtime_ref.value,
            "status": self.status.value,
            "stderr_ref": _content(self.stderr_ref),
            "stdout_ref": _content(self.stdout_ref),
            "tool_call_refs": [item.value for item in self.tool_call_refs],
        }


@dataclass(frozen=True)
class GameEngineRuntimeDescription:
    project_ref: ProjectRef
    identity_digest: str
    adapter_ref: str
    reality: GameEngineReality
    engine_name: str
    engine_version: str
    toolchain_ref: str
    runtime_ref: str
    executable_sha256: str
    resource_requirements: GameEngineResourceRequirements
    backend_kind: str
    backend_version: str
    backend_implementation_id: str
    backend_host_id: str
    cgroup_version: str
    security_features: tuple[str, ...]
    enforced_limit_kinds: tuple[str, ...]
    unsupported_limit_kinds: tuple[str, ...]
    gpu_count: int | None
    supported_network_policies: tuple[str, ...]
    evidence_tool_call_refs: tuple[ToolCallRef, ...]
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("game runtime description requires exact ProjectRef")
        _sha(self.identity_digest, "identity_digest")
        object.__setattr__(self, "adapter_ref", _ref(self.adapter_ref, "adapter_ref"))
        if not isinstance(self.reality, GameEngineReality):
            raise GameEngineContractError("runtime description reality is malformed")
        _text(self.engine_name, "engine_name", 256)
        _text(self.engine_version, "engine_version", 512)
        _ref(self.toolchain_ref, "toolchain_ref")
        _ref(self.runtime_ref, "runtime_ref")
        _sha(self.executable_sha256, "executable_sha256")
        if not isinstance(self.resource_requirements, GameEngineResourceRequirements):
            raise TypeError("runtime description requires resource requirements")
        _text(self.backend_kind, "backend_kind", 512)
        _text(self.backend_version, "backend_version", 512)
        _text(self.backend_implementation_id, "backend_implementation_id", 512)
        _text(self.backend_host_id, "backend_host_id", 512)
        _text(self.cgroup_version, "cgroup_version", 512)
        for values, label in (
            (self.security_features, "security features"),
            (self.enforced_limit_kinds, "enforced limit kinds"),
            (self.unsupported_limit_kinds, "unsupported limit kinds"),
        ):
            if (
                not isinstance(values, tuple)
                or len(set(values)) != len(values)
                or any(not isinstance(item, str) or not item for item in values)
            ):
                raise GameEngineContractError(
                    f"runtime {label} evidence is malformed"
                )
        if self.gpu_count is not None and (
            not isinstance(self.gpu_count, int)
            or isinstance(self.gpu_count, bool)
            or self.gpu_count < 0
        ):
            raise GameEngineContractError("runtime GPU count is malformed")
        if (
            not isinstance(self.supported_network_policies, tuple)
            or len(set(self.supported_network_policies))
            != len(self.supported_network_policies)
            or any(
                not isinstance(item, str) or not item
                for item in self.supported_network_policies
            )
        ):
            raise GameEngineContractError(
                "runtime network policy evidence is malformed"
            )
        if (
            not isinstance(self.evidence_tool_call_refs, tuple)
            or len(set(self.evidence_tool_call_refs))
            != len(self.evidence_tool_call_refs)
            or any(
                item.project_ref != self.project_ref
                for item in self.evidence_tool_call_refs
            )
        ):
            raise GameEngineScopeError("runtime description ToolCall crossed Project scope")
        if self.reality is GameEngineReality.REAL and not self.evidence_tool_call_refs:
            raise GameEngineIntegrityError(
                "REAL runtime description requires durable observed ToolCalls"
            )
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "backend_kind": self.backend_kind,
            "backend_version": self.backend_version,
            "backend_implementation_id": self.backend_implementation_id,
            "backend_host_id": self.backend_host_id,
            "cgroup_version": self.cgroup_version,
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "evidence_tool_call_refs": [item.value for item in self.evidence_tool_call_refs],
            "executable_sha256": self.executable_sha256,
            "gpu_count": self.gpu_count,
            "security_features": list(self.security_features),
            "enforced_limit_kinds": list(self.enforced_limit_kinds),
            "unsupported_limit_kinds": list(self.unsupported_limit_kinds),
            "identity_digest": self.identity_digest,
            "observed_at": self.observed_at,
            "project_ref": self.project_ref.value,
            "reality": self.reality.value,
            "resource_requirements": self.resource_requirements.payload(),
            "runtime_ref": self.runtime_ref,
            "supported_network_policies": list(self.supported_network_policies),
            "toolchain_ref": self.toolchain_ref,
        }


@runtime_checkable
class GameEngineAdapter(Protocol):
    def detect_project(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult: ...

    def inspect_project(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult: ...

    def import_project(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult: ...

    def build(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult: ...

    def run(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult: ...

    def test(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult: ...

    def profile(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult: ...

    def capture(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult: ...

    def export(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult: ...

    def describe_runtime(self, access: ProjectAccess, attempt: NodeExecutionAttempt, identity: GameProjectIdentity, *, control_root_ref: FilesystemRootRef, idempotency_key: str) -> GameEngineRuntimeDescription: ...


@runtime_checkable
class _RuntimeReceiptReader(Protocol):
    def get_receipt(
        self,
        access: ProjectAccess,
        call_ref: ToolCallRef,
    ) -> RuntimeReceipt: ...


class _BaseGameEngineAdapter:
    def __init__(
        self,
        database_path: str | Path,
        *,
        adapter_ref: str,
        reality: GameEngineReality,
        object_store: ObjectStorageBackend | None = None,
    ) -> None:
        if object_store is not None and not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("object_store must implement ObjectStorageBackend")
        self.database_path = Path(database_path).resolve()
        self.adapter_ref = _ref(adapter_ref, "adapter_ref")
        self.reality = reality
        self.object_store = object_store
        self.projects = ProjectStore(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.calls = CallLedgerService(self.database_path)
        self.graphs = GraphService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.runs = RunService(self.database_path)
        self.filesystem = (
            None
            if object_store is None
            else FilesystemAdapter(self.database_path, object_store)
        )
        self.workspaces = (
            None
            if object_store is None or self.filesystem is None
            else WorkspaceService(
                self.database_path,
                object_store,
                self.filesystem,
            )
        )
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS game_engine_operation_claims (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  operation TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  request_sha256 TEXT NOT NULL,
                  claim_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS game_engine_operation_results (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  operation TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  result_json TEXT NOT NULL,
                  record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key),
                  FOREIGN KEY(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key)
                    REFERENCES game_engine_operation_claims(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key)
                    ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS game_engine_operation_inflight (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  operation TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key),
                  FOREIGN KEY(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key)
                    REFERENCES game_engine_operation_claims(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key)
                    ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS game_engine_verified_builds (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  request_sha256 TEXT NOT NULL,
                  result_json TEXT NOT NULL,
                  record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,request_sha256),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS game_engine_verified_detections (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  identity_digest TEXT NOT NULL,
                  result_json TEXT NOT NULL,
                  record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,identity_digest),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS game_engine_runtime_description_claims (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  semantic_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS game_engine_runtime_descriptions (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  description_json TEXT NOT NULL,
                  record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key),
                  FOREIGN KEY(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key)
                    REFERENCES game_engine_runtime_description_claims(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key)
                    ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS game_engine_runtime_description_inflight (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key),
                  FOREIGN KEY(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key)
                    REFERENCES game_engine_runtime_description_claims(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key)
                    ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS game_engine_output_publications (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  artifact_id TEXT NOT NULL,
                  artifact_revision INTEGER NOT NULL,
                  identity_digest TEXT NOT NULL,
                  request_sha256 TEXT NOT NULL,
                  operation TEXT NOT NULL,
                  output_index INTEGER NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  artifact_record_sha256 TEXT NOT NULL,
                  publication_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,artifact_id,artifact_revision),
                  UNIQUE(project_id,adapter_ref,identity_digest,request_sha256,operation,output_index),
                  FOREIGN KEY(project_id,artifact_id,artifact_revision,artifact_record_sha256)
                    REFERENCES artifact_revisions(project_id,artifact_id,revision,record_sha256)
                    ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS game_engine_claims_no_update BEFORE UPDATE ON game_engine_operation_claims
                  BEGIN SELECT RAISE(ABORT,'Game-engine claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_claims_no_delete BEFORE DELETE ON game_engine_operation_claims
                  BEGIN SELECT RAISE(ABORT,'Game-engine claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_results_no_update BEFORE UPDATE ON game_engine_operation_results
                  BEGIN SELECT RAISE(ABORT,'Game-engine results are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_results_no_delete BEFORE DELETE ON game_engine_operation_results
                  BEGIN SELECT RAISE(ABORT,'Game-engine results cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_verified_builds_no_update BEFORE UPDATE ON game_engine_verified_builds
                  BEGIN SELECT RAISE(ABORT,'Verified game builds are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_verified_builds_no_delete BEFORE DELETE ON game_engine_verified_builds
                  BEGIN SELECT RAISE(ABORT,'Verified game builds cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_verified_detections_no_update BEFORE UPDATE ON game_engine_verified_detections
                  BEGIN SELECT RAISE(ABORT,'Verified game detections are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_verified_detections_no_delete BEFORE DELETE ON game_engine_verified_detections
                  BEGIN SELECT RAISE(ABORT,'Verified game detections cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_runtime_description_claims_no_update BEFORE UPDATE ON game_engine_runtime_description_claims
                  BEGIN SELECT RAISE(ABORT,'Game runtime description claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_runtime_description_claims_no_delete BEFORE DELETE ON game_engine_runtime_description_claims
                  BEGIN SELECT RAISE(ABORT,'Game runtime description claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_runtime_descriptions_no_update BEFORE UPDATE ON game_engine_runtime_descriptions
                  BEGIN SELECT RAISE(ABORT,'Game runtime descriptions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_runtime_descriptions_no_delete BEFORE DELETE ON game_engine_runtime_descriptions
                  BEGIN SELECT RAISE(ABORT,'Game runtime descriptions cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_output_publications_no_update BEFORE UPDATE ON game_engine_output_publications
                  BEGIN SELECT RAISE(ABORT,'Game output publications are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS game_engine_output_publications_no_delete BEFORE DELETE ON game_engine_output_publications
                  BEGIN SELECT RAISE(ABORT,'Game output publications cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def _authorize(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        *,
        verify_assets: bool = True,
    ) -> None:
        try:
            self.projects.get_project(access, request.project_ref)
        except ProjectIntegrityError as exc:
            raise GameEngineIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise GameEngineScopeError("game Project scope mismatch") from exc
        if not isinstance(attempt, NodeExecutionAttempt):
            raise GameEngineAuthorityError("exact NodeExecutionAttempt is required")
        if (
            attempt.node_ref.project_ref != request.project_ref
            or attempt.run_ref.project_ref != request.project_ref
            or access.project_ref != request.project_ref
        ):
            raise GameEngineScopeError("game Node attempt crossed Project scope")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            _, _, task, graph = self.executions._require_live_attempt(
                connection,
                access,
                attempt,
                allowed_statuses={"RUNNING"},
            )
        except (NodeExecutionAuthorityError, NodeExecutionError) as exc:
            raise GameEngineAuthorityError(
                "game Node attempt is stale, expired, or differs from durable authority"
            ) from exc
        finally:
            connection.close()
        if task.canonical_digest != attempt.task_digest:
            raise GameEngineIntegrityError("game Node attempt Task digest changed")
        node = next((item for item in graph.nodes if item.node_ref == attempt.node_ref), None)
        if node is None or request.operation.capability_ref not in node.required_capabilities:
            raise GameEngineAuthorityError("game capability is not authorized by exact Node")
        candidate = self.artifacts.get_artifact(access, request.identity.candidate_artifact_ref)
        if candidate.project_ref != request.project_ref:
            raise GameEngineScopeError("game candidate Artifact crossed Project scope")
        if candidate.role != "workspace.snapshot":
            raise GameEngineIntegrityError(
                "game candidate must be an exact Workspace snapshot Artifact"
            )
        self._verify_repository_identity(request.identity)
        workspace_root_ref, workspace_path = self._verify_candidate_identity(
            access,
            request.identity,
            candidate.content_ref,
            request.runtime_spec,
        )
        if request.runtime_spec is not None:
            mounted = any(
                mount.root_ref == workspace_root_ref
                and (
                    mount.source_path == "."
                    or PurePosixPath(workspace_path).is_relative_to(
                        PurePosixPath(mount.source_path)
                    )
                )
                for mount in request.runtime_spec.mounts
            )
            if not mounted:
                raise GameEngineIntegrityError(
                    "game runtime is not mounted from the exact candidate Workspace"
                )
        if request.build_artifact_ref is not None:
            build = self.artifacts.get_artifact(access, request.build_artifact_ref)
            if build.role != "game.build.output":
                raise GameEngineIntegrityError("game build Artifact role changed")
            if request.identity.candidate_artifact_ref not in build.source_artifact_refs:
                raise GameEngineIntegrityError(
                    "game build Artifact is not chained to the exact candidate"
                )
            self._verify_content(build.content_ref, "game build Artifact")
            self._verify_build_origin(request, build.artifact_ref)
        if verify_assets:
            for asset in request.asset_inputs:
                artifact = self.artifacts.get_artifact(access, asset.artifact_ref)
                if artifact.role != asset.expected_role:
                    raise GameEngineIntegrityError("game asset Artifact role changed")
                self._verify_content(artifact.content_ref, "game asset Artifact")

    def _verify_build_origin(
        self,
        request: GameEngineOperationRequest,
        artifact_ref: ArtifactRef,
    ) -> None:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM game_engine_operation_results WHERE project_id=? AND adapter_ref=? AND operation=?",
                (
                    request.project_ref.value,
                    request.identity.adapter_ref,
                    GameEngineOperation.BUILD.value,
                ),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            raise GameEngineIntegrityError(
                "game build origin registry is unavailable"
            ) from exc
        finally:
            connection.close()
        matching = tuple(
            result
            for result in (self._result_from_row(row) for row in rows)
            if artifact_ref in result.output_artifact_refs
        )
        if not matching:
            raise GameEngineIntegrityError(
                "game build Artifact lacks a durable adapter result origin"
            )
        if any(
            result.operation is not GameEngineOperation.BUILD
            or result.status is not GameEngineStatus.SUCCEEDED
            or result.identity_digest != request.identity.semantic_digest
            or result.adapter_ref != request.identity.adapter_ref
            for result in matching
        ):
            raise GameEngineIntegrityError(
                "game build Artifact originated from a different exact identity"
            )

    def _verify_repository_identity(self, identity: GameProjectIdentity) -> None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT repository_json,record_sha256 FROM git_repositories WHERE project_id=? AND repository_id=?",
                (identity.project_ref.value, identity.repository_ref.repository_id),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            raise GameEngineIntegrityError(
                "game source Repository registry is unavailable"
            ) from exc
        finally:
            connection.close()
        if row is None:
            raise GameEngineIntegrityError("game source RepositoryRef is not durably registered")
        try:
            payload = json.loads(cast(str, row["repository_json"]))
        except json.JSONDecodeError as exc:
            raise GameEngineIntegrityError(
                "game source Repository registry is malformed"
            ) from exc
        if (
            payload != identity.repository_ref.payload()
            or not hmac.compare_digest(
                cast(str, row["record_sha256"]),
                identity.repository_ref.record_sha256,
            )
        ):
            raise GameEngineIntegrityError("game source RepositoryRef evidence changed")

    def _verify_candidate_identity(
        self,
        access: ProjectAccess,
        identity: GameProjectIdentity,
        candidate_content_ref: ContentRef | None,
        runtime_spec: IsolatedRuntimeSpec | None,
    ) -> tuple[FilesystemRootRef, str]:
        if self.workspaces is None or self.filesystem is None:
            raise GameEngineIntegrityError(
                "game candidate verification requires exact object storage"
            )
        try:
            snapshot = self.workspaces.get_snapshot(
                access,
                identity.candidate_snapshot_ref,
            )
            receipt = self.workspaces.get_receipt(
                access,
                identity.candidate_snapshot_ref,
            )
            workspace = self.workspaces.get_workspace(
                access,
                identity.candidate_snapshot_ref.workspace_ref,
            )
            policy = self.workspaces.get_policy(
                access,
                workspace.execution_policy_ref,
            )
            root = self.filesystem.get_root(access, workspace.candidate_root_ref)
        except (FilesystemError, WorkspaceError) as exc:
            raise GameEngineIntegrityError(
                "game candidate Workspace evidence failed verification"
            ) from exc
        if (
            workspace.workspace_type is not WorkspaceType.REPOSITORY
            or workspace.latest_snapshot_ref != identity.candidate_snapshot_ref
            or snapshot.snapshot_ref != identity.candidate_snapshot_ref
            or snapshot.artifact_ref != identity.candidate_artifact_ref
            or receipt.snapshot_artifact_ref != identity.candidate_artifact_ref
            or receipt.candidate_manifest_ref != snapshot.manifest_ref
            or snapshot.manifest_ref != candidate_content_ref
        ):
            raise GameEngineIntegrityError(
                "game candidate Workspace identity differs from its exact snapshot"
            )
        expected_source = WorkspaceRepositorySource(identity.repository_ref)
        if workspace.base_sources != (expected_source,):
            raise GameEngineIntegrityError(
                "game candidate Workspace is not derived from the exact RepositoryRef"
            )
        self._verify_content(snapshot.manifest_ref, "game candidate manifest")
        entries = {item.path: item for item in snapshot.entries}
        for path, digest, label in (
            (
                identity.project_config_path,
                identity.project_config_sha256,
                "project configuration",
            ),
            (
                identity.build_export_config_path,
                identity.build_export_config_sha256,
                "build/export configuration",
            ),
        ):
            entry = entries.get(path)
            content = None if entry is None else entry.content_ref
            if (
                entry is None
                or entry.kind != "file"
                or content is None
                or content.algorithm != "sha256"
                or content.digest != digest
            ):
                raise GameEngineIntegrityError(
                    f"exact game {label} differs from candidate bytes"
                )
            self._verify_content(content, f"game {label}")
        scene = entries.get(identity.entry_scene)
        if scene is None or scene.kind != "file":
            raise GameEngineIntegrityError("game entry scene is absent from exact candidate")
        cache_paths = tuple(PurePosixPath(item) for item in identity.cache_paths)
        for entry in snapshot.entries:
            entry_path = PurePosixPath(entry.path)
            if any(
                entry_path == cache_path or entry_path.is_relative_to(cache_path)
                for cache_path in cache_paths
            ):
                raise GameEngineIntegrityError(
                    "declared game cache contains authoritative candidate bytes"
                )
        generated_paths = self._generated_candidate_paths(
            identity,
            workspace.candidate_root_ref,
            workspace.relative_path,
            runtime_spec,
        )
        try:
            candidate_root = Path(root.canonical_path)
            candidate_path = candidate_root.joinpath(
                *PurePosixPath(workspace.relative_path).parts
            )
            state = candidate_path.lstat()
            if not stat.S_ISDIR(state.st_mode) or stat.S_ISLNK(state.st_mode):
                raise OSError("candidate is not a real directory")
            if candidate_path.resolve(strict=True) != candidate_path:
                raise OSError("candidate path traverses a symlink")
            self._verify_live_candidate_tree(
                candidate_path,
                entries,
                policy,
                identity.cache_paths,
                generated_paths,
            )
        except OSError as exc:
            raise GameEngineIntegrityError(
                "live game candidate filesystem differs from its exact snapshot"
            ) from exc
        return workspace.candidate_root_ref, workspace.relative_path

    def _generated_candidate_paths(
        self,
        identity: GameProjectIdentity,
        root_ref: FilesystemRootRef,
        workspace_path: str,
        current_spec: IsolatedRuntimeSpec | None,
    ) -> tuple[str, ...]:
        """Return only output paths explicitly authorized for this exact identity."""

        values: set[str] = set()

        def collect(spec_payload: Mapping[str, object]) -> None:
            outputs = spec_payload.get("outputs")
            if not isinstance(outputs, list):
                return
            workspace = PurePosixPath(workspace_path)
            for raw in outputs:
                if not isinstance(raw, dict):
                    continue
                raw_root = raw.get("root_ref")
                raw_path = raw.get("path")
                if raw_root != root_ref.value or not isinstance(raw_path, str):
                    continue
                path = PurePosixPath(raw_path)
                if path.is_relative_to(workspace) and path != workspace:
                    values.add(path.relative_to(workspace).as_posix())

        if current_spec is not None:
            collect(current_spec.payload())
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT result_json FROM game_engine_operation_results WHERE project_id=? AND adapter_ref=?",
                (identity.project_ref.value, self.adapter_ref),
            ).fetchall()
            for row in rows:
                try:
                    result = json.loads(cast(str, row["result_json"]))
                    if (
                        not isinstance(result, dict)
                        or result.get("identity_digest") != identity.semantic_digest
                        or not isinstance(result.get("runtime_ref"), str)
                    ):
                        continue
                    runtime_parts = cast(str, result["runtime_ref"]).rsplit("/", 2)
                    runtime_id = runtime_parts[-2]
                    generation = int(runtime_parts[-1])
                    state_row = connection.execute(
                        "SELECT state_json FROM isolated_runtime_states WHERE project_id=? AND runtime_id=? AND generation=?",
                        (identity.project_ref.value, runtime_id, generation),
                    ).fetchone()
                    if state_row is None:
                        continue
                    state_payload = json.loads(cast(str, state_row["state_json"]))
                    if isinstance(state_payload, dict) and isinstance(
                        state_payload.get("spec"), dict
                    ):
                        collect(cast(dict[str, object], state_payload["spec"]))
                except (IndexError, TypeError, ValueError, json.JSONDecodeError):
                    raise GameEngineIntegrityError(
                        "persisted game runtime output authorization is malformed"
                    )
        except sqlite3.OperationalError as exc:
            raise GameEngineIntegrityError(
                "persisted game runtime output authorization is unavailable"
            ) from exc
        finally:
            connection.close()
        return tuple(sorted(values))

    @staticmethod
    def _verify_live_candidate_tree(
        candidate_path: Path,
        expected: Mapping[str, object],
        policy: object,
        cache_paths: Sequence[str],
        generated_paths: Sequence[str],
    ) -> None:
        from .workspace import WorkspaceExecutionPolicy, WorkspaceFileEntry

        if not isinstance(policy, WorkspaceExecutionPolicy) or any(
            not isinstance(item, WorkspaceFileEntry) for item in expected.values()
        ):
            raise GameEngineIntegrityError("game candidate manifest types changed")
        exact = cast(Mapping[str, WorkspaceFileEntry], expected)
        caches = tuple(PurePosixPath(item) for item in cache_paths)
        generated = tuple(PurePosixPath(item) for item in generated_paths)
        observed: set[str] = set()

        def is_within(path: PurePosixPath, roots: Sequence[PurePosixPath]) -> bool:
            return any(path == root or path.is_relative_to(root) for root in roots)

        def is_generated_parent(path: PurePosixPath) -> bool:
            return any(value != path and value.is_relative_to(path) for value in generated)

        def visit(directory: Path, prefix: str | None = None) -> None:
            with os.scandir(directory) as children:
                entries = sorted(children, key=lambda item: item.name)
            for child in entries:
                relative = child.name if prefix is None else f"{prefix}/{child.name}"
                relative_path = PurePosixPath(relative)
                if WorkspaceService._is_excluded(policy, relative):
                    continue
                if is_within(relative_path, caches) or is_within(
                    relative_path, generated
                ):
                    continue
                child_state = child.stat(follow_symlinks=False)
                expected_entry = exact.get(relative)
                if child.is_symlink():
                    raise GameEngineIntegrityError(
                        "live game candidate contains an unauthenticated symlink"
                    )
                if child.is_dir(follow_symlinks=False):
                    if expected_entry is None and not is_generated_parent(relative_path):
                        raise GameEngineIntegrityError(
                            "live game candidate contains an unexpected directory"
                        )
                    if expected_entry is not None:
                        if expected_entry.kind != "directory":
                            raise GameEngineIntegrityError(
                                "live game candidate entry kind changed"
                            )
                        observed.add(relative)
                    visit(Path(child.path), relative)
                    continue
                if not child.is_file(follow_symlinks=False):
                    raise GameEngineIntegrityError(
                        "live game candidate contains a special filesystem object"
                    )
                if expected_entry is None or expected_entry.kind != "file":
                    raise GameEngineIntegrityError(
                        "live game candidate contains an unexpected file"
                    )
                content_ref = expected_entry.content_ref
                if content_ref is None or content_ref.algorithm != "sha256":
                    raise GameEngineIntegrityError(
                        "game candidate file lacks exact sha256 identity"
                    )
                digest = hashlib.sha256()
                size = 0
                with open(child.path, "rb") as source:
                    while block := source.read(1024 * 1024):
                        digest.update(block)
                        size += len(block)
                if (
                    digest.hexdigest() != content_ref.digest
                    or size != content_ref.size_bytes
                    or stat.S_IMODE(child_state.st_mode) != expected_entry.mode
                ):
                    raise GameEngineIntegrityError(
                        "live game candidate file bytes or mode changed"
                    )
                observed.add(relative)

        visit(candidate_path)
        missing = set(exact) - observed
        if missing:
            raise GameEngineIntegrityError(
                "live game candidate is missing exact snapshot entries"
            )

    def _verify_content(self, content_ref: ContentRef | None, label: str) -> None:
        if content_ref is None or content_ref.size_bytes < 1:
            raise GameEngineIntegrityError(f"{label} lacks non-empty exact content")
        if self.object_store is not None:
            try:
                self.object_store.verify(content_ref)
            except ObjectStorageError as exc:
                raise GameEngineIntegrityError(
                    f"{label} content failed verification"
                ) from exc

    def _read_verified_content(self, content_ref: ContentRef | None) -> bytes:
        self._verify_content(content_ref, "game evidence")
        if self.object_store is None:
            raise GameEngineIntegrityError("game object storage is unavailable")
        try:
            return self.object_store.read(cast(ContentRef, content_ref))
        except ObjectStorageError as exc:
            raise GameEngineIntegrityError(
                "game evidence content is unavailable"
            ) from exc

    @staticmethod
    def _matches_exact_engine_version(
        evidence: bytes,
        expected_version: str,
    ) -> bool:
        try:
            lines = tuple(
                line.strip()
                for line in evidence.decode("utf-8", errors="strict").splitlines()
                if line.strip()
            )
        except UnicodeDecodeError:
            return False
        return expected_version in lines

    def _run_attempt(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
    ) -> ExecutionAttempt:
        result = next(
            (
                item
                for item in self.runs.list_attempts(access, attempt.run_ref)
                if item.attempt_id == attempt.run_attempt_id
                and item.fence == attempt.run_fence
            ),
            None,
        )
        if result is None:
            raise GameEngineAuthorityError(
                "exact game Run execution authority is unavailable"
            )
        return result

    def _authorize_runtime_description(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: GameProjectIdentity,
        control_root_ref: FilesystemRootRef,
    ) -> None:
        if (
            access.project_ref != identity.project_ref
            or attempt.node_ref.project_ref != identity.project_ref
            or attempt.run_ref.project_ref != identity.project_ref
            or control_root_ref.project_ref != identity.project_ref
        ):
            raise GameEngineScopeError(
                "game runtime description crossed Project scope"
            )
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            _, _, task, graph = self.executions._require_live_attempt(
                connection,
                access,
                attempt,
                allowed_statuses={"RUNNING"},
            )
        except (NodeExecutionAuthorityError, NodeExecutionError) as exc:
            raise GameEngineAuthorityError(
                "game runtime description lacks live Node authority"
            ) from exc
        finally:
            connection.close()
        node = next((item for item in graph.nodes if item.node_ref == attempt.node_ref), None)
        adapter_capabilities = {
            item.capability_ref for item in GameEngineOperation
        }
        if (
            task.canonical_digest != attempt.task_digest
            or node is None
            or not adapter_capabilities.intersection(node.required_capabilities)
        ):
            raise GameEngineAuthorityError(
                "game runtime description lacks exact inspection authority"
            )
        candidate = self.artifacts.get_artifact(
            access,
            identity.candidate_artifact_ref,
        )
        if candidate.role != "workspace.snapshot":
            raise GameEngineIntegrityError(
                "game runtime description candidate role changed"
            )
        self._verify_repository_identity(identity)
        self._verify_candidate_identity(access, identity, candidate.content_ref, None)

    @staticmethod
    def _claim_digest(
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
    ) -> str:
        return _digest(
            {
                "attempt_sha256": attempt.record_sha256,
                "request_sha256": request.request_sha256,
            }
        )

    def _claim(
        self,
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        idempotency_key: str,
    ) -> GameEngineOperationResult | None:
        if not isinstance(idempotency_key, str) or _KEY.fullmatch(idempotency_key) is None:
            raise GameEngineContractError("idempotency_key is malformed")
        request_sha256 = self._claim_digest(attempt, request)
        claim_sha256 = _digest(
            {
                "adapter_ref": self.adapter_ref,
                "idempotency_key": idempotency_key,
                "node_attempt_id": attempt.attempt_id,
                "node_fence": attempt.fence,
                "operation": request.operation.value,
                "project_ref": request.project_ref.value,
                "request_sha256": request_sha256,
            }
        )
        values = (
            request.project_ref.value,
            self.adapter_ref,
            attempt.attempt_id,
            attempt.fence,
            request.operation.value,
            idempotency_key,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM game_engine_operation_claims WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                values,
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO game_engine_operation_claims VALUES (?,?,?,?,?,?,?,?)",
                    (*values, request_sha256, claim_sha256),
                )
                connection.execute(
                    "INSERT INTO game_engine_operation_inflight VALUES (?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%f+00:00','now'))",
                    values,
                )
                connection.commit()
                return None
            if (
                row["request_sha256"] != request_sha256
                or not hmac.compare_digest(cast(str, row["claim_sha256"]), claim_sha256)
            ):
                raise GameEngineConflictError("game-engine idempotency identity changed")
            result_row = connection.execute(
                "SELECT * FROM game_engine_operation_results WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                values,
            ).fetchone()
            connection.commit()
            if result_row is None:
                raise GameEngineConflictError(
                    "game-engine idempotency claim is already in progress or incomplete"
                )
            return self._result_from_row(result_row)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _persist_result(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        result: GameEngineOperationResult,
        idempotency_key: str,
    ) -> GameEngineOperationResult:
        values = (
            result.project_ref.value,
            self.adapter_ref,
            attempt.attempt_id,
            attempt.fence,
            result.operation.value,
            idempotency_key,
        )
        result_json = _json(result.payload())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
            except (NodeExecutionAuthorityError, NodeExecutionError) as exc:
                raise GameEngineAuthorityError(
                    "game result lost exact Node authority before persistence"
                ) from exc
            existing = connection.execute(
                "SELECT * FROM game_engine_operation_results WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                values,
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO game_engine_operation_results VALUES (?,?,?,?,?,?,?,?)",
                    (*values, result_json, result.record_sha256),
                )
                connection.execute(
                    "DELETE FROM game_engine_operation_inflight WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                    values,
                )
                connection.commit()
                return result
            connection.execute(
                "DELETE FROM game_engine_operation_inflight WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                values,
            )
            connection.commit()
            replay = self._result_from_row(existing)
            if replay != result:
                raise GameEngineConflictError("game-engine result identity conflicts")
            return replay
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise GameEngineConflictError("game-engine result persistence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _result_from_row(row: Mapping[str, object]) -> GameEngineOperationResult:
        try:
            payload = json.loads(cast(str, row["result_json"]))
            if not isinstance(payload, dict):
                raise TypeError
            project_ref = ProjectRef(cast(str, payload["project_ref"]))
            result = GameEngineOperationResult(
                project_ref=project_ref,
                operation=GameEngineOperation(cast(str, payload["operation"])),
                identity_digest=cast(str, payload["identity_digest"]),
                request_sha256=cast(str, payload["request_sha256"]),
                adapter_ref=cast(str, payload["adapter_ref"]),
                reality=GameEngineReality(cast(str, payload["reality"])),
                status=GameEngineStatus(cast(str, payload["status"])),
                node_attempt_id=cast(str, payload["node_attempt_id"]),
                node_fence=cast(int, payload["node_fence"]),
                runtime_ref=_runtime_from(payload.get("runtime_ref"), project_ref),
                receipt_artifact_refs=tuple(
                    _artifact_from(item, project_ref)
                    for item in cast(Sequence[object], payload["receipt_artifact_refs"])
                ),
                tool_call_refs=tuple(
                    _tool_from(item, project_ref)
                    for item in cast(Sequence[object], payload["tool_call_refs"])
                ),
                output_artifact_refs=tuple(
                    _artifact_from(item, project_ref)
                    for item in cast(Sequence[object], payload["output_artifact_refs"])
                ),
                output_roles=tuple(cast(Sequence[str], payload["output_roles"])),
                stdout_ref=_content_from(payload.get("stdout_ref")),
                stderr_ref=_content_from(payload.get("stderr_ref")),
                failure_reason=cast(str | None, payload.get("failure_reason")),
                runtime_observed=cast(bool, payload["runtime_observed"]),
                reused_verified_build=cast(bool, payload["reused_verified_build"]),
                observed_at=cast(str, payload["observed_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise GameEngineIntegrityError("persisted game-engine result is malformed") from exc
        if not hmac.compare_digest(result.record_sha256, cast(str, row["record_sha256"])):
            raise GameEngineIntegrityError("persisted game-engine result digest changed")
        return result

    def _persist_verified_build(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        result: GameEngineOperationResult,
    ) -> None:
        if (
            result.operation is not GameEngineOperation.BUILD
            or result.status is not GameEngineStatus.SUCCEEDED
            or result.reality is not GameEngineReality.REAL
        ):
            return
        result_json = _json(result.payload())
        build_semantic_sha256 = self._build_cache_key(request)
        values = (
            request.project_ref.value,
            self.adapter_ref,
            build_semantic_sha256,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
            except (NodeExecutionAuthorityError, NodeExecutionError) as exc:
                raise GameEngineAuthorityError(
                    "verified game build lost exact Node authority"
                ) from exc
            row = connection.execute(
                "SELECT * FROM game_engine_verified_builds WHERE project_id=? AND adapter_ref=? AND request_sha256=?",
                values,
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO game_engine_verified_builds VALUES (?,?,?,?,?)",
                    (*values, result_json, result.record_sha256),
                )
                connection.commit()
                return
            connection.commit()
            prior = self._result_from_row(row)
            if (
                prior.identity_digest != result.identity_digest
                or prior.output_artifact_refs != result.output_artifact_refs
                or prior.output_roles != result.output_roles
                or prior.receipt_artifact_refs != result.receipt_artifact_refs
                or prior.tool_call_refs != result.tool_call_refs
            ):
                raise GameEngineConflictError(
                    "verified game build identity conflicts"
                )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _persist_verified_detection(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: GameProjectIdentity,
        result: GameEngineOperationResult,
    ) -> None:
        if (
            result.operation is not GameEngineOperation.DETECT
            or result.status is not GameEngineStatus.SUCCEEDED
            or result.reality is not GameEngineReality.REAL
        ):
            return
        values = (
            identity.project_ref.value,
            self.adapter_ref,
            identity.semantic_digest,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
            except (NodeExecutionAuthorityError, NodeExecutionError) as exc:
                raise GameEngineAuthorityError(
                    "verified engine detection lost exact Node authority"
                ) from exc
            row = connection.execute(
                "SELECT * FROM game_engine_verified_detections WHERE project_id=? AND adapter_ref=? AND identity_digest=?",
                values,
            ).fetchone()
            if row is None:
                self._validate_verified_detection(access, identity, result)
                connection.execute(
                    "INSERT INTO game_engine_verified_detections VALUES (?,?,?,?,?)",
                    (*values, _json(result.payload()), result.record_sha256),
                )
                connection.commit()
                return
            connection.commit()
            prior = self._result_from_row(row)
            self._validate_verified_detection(access, identity, prior)
            if (
                prior.identity_digest != result.identity_digest
                or prior.output_artifact_refs != result.output_artifact_refs
                or prior.output_roles != result.output_roles
                or prior.runtime_ref != result.runtime_ref
                or prior.receipt_artifact_refs != result.receipt_artifact_refs
                or prior.tool_call_refs != result.tool_call_refs
            ):
                raise GameEngineConflictError(
                    "verified game detection identity conflicts"
                )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _require_verified_detection(
        self,
        access: ProjectAccess,
        identity: GameProjectIdentity,
    ) -> GameEngineOperationResult:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM game_engine_verified_detections WHERE project_id=? AND adapter_ref=? AND identity_digest=?",
                (
                    identity.project_ref.value,
                    self.adapter_ref,
                    identity.semantic_digest,
                ),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise GameEngineAuthorityError(
                "REAL engine identity requires a completed exact detection probe"
            )
        result = self._result_from_row(row)
        self._validate_verified_detection(access, identity, result)
        return result

    def _reuse_verified_detection(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        idempotency_key: str,
    ) -> GameEngineOperationResult | None:
        if request.operation is not GameEngineOperation.DETECT:
            return None
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM game_engine_verified_detections WHERE project_id=? AND adapter_ref=? AND identity_digest=?",
                (
                    request.project_ref.value,
                    self.adapter_ref,
                    request.identity.semantic_digest,
                ),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        prior = self._result_from_row(row)
        self._validate_verified_detection(access, request.identity, prior)
        if prior.output_artifact_refs != (
            self._output_artifact_ref(request, 0),
        ):
            return None
        adopted = replace(
            prior,
            node_attempt_id=attempt.attempt_id,
            node_fence=attempt.fence,
            request_sha256=request.request_sha256,
        )
        self._authorize(access, attempt, request)
        return self._persist_result(
            access,
            attempt,
            adopted,
            idempotency_key,
        )

    def _validate_verified_detection(
        self,
        access: ProjectAccess,
        identity: GameProjectIdentity,
        result: GameEngineOperationResult,
    ) -> None:
        if (
            result.operation is not GameEngineOperation.DETECT
            or result.status is not GameEngineStatus.SUCCEEDED
            or result.reality is not GameEngineReality.REAL
            or result.identity_digest != identity.semantic_digest
            or result.adapter_ref != self.adapter_ref
            or result.runtime_ref is None
            or result.output_roles != ("game.engine.detection",)
            or len(result.output_artifact_refs) != 1
            or not result.tool_call_refs
        ):
            raise GameEngineIntegrityError(
                "verified REAL engine detection evidence is malformed"
            )
        artifact = self.artifacts.get_artifact(
            access,
            result.output_artifact_refs[0],
        )
        self._verify_content(artifact.content_ref, "verified engine detection")
        if (
            artifact.role != "game.engine.detection"
            or identity.candidate_artifact_ref not in artifact.source_artifact_refs
            or not self._matches_exact_engine_version(
                self._read_verified_content(artifact.content_ref),
                identity.engine_version,
            )
            or dict(artifact.metadata).get("semantic_label")
            != f"game-detect-{identity.semantic_digest}-0"
        ):
            raise GameEngineIntegrityError(
                "verified REAL engine detection content or provenance changed"
            )
        connection = self._connect()
        try:
            publication = connection.execute(
                "SELECT * FROM game_engine_output_publications WHERE project_id=? AND adapter_ref=? AND artifact_id=? AND artifact_revision=?",
                (
                    identity.project_ref.value,
                    self.adapter_ref,
                    artifact.artifact_id,
                    artifact.revision,
                ),
            ).fetchone()
            state_row = connection.execute(
                "SELECT state_json FROM isolated_runtime_states WHERE project_id=? AND runtime_id=? AND generation=?",
                (
                    identity.project_ref.value,
                    result.runtime_ref.runtime_id,
                    result.runtime_ref.generation,
                ),
            ).fetchone()
        finally:
            connection.close()
        if publication is None:
            raise GameEngineIntegrityError(
                "verified engine detection lacks atomic publication evidence"
            )
        expected_publication = _digest(
            {
                "adapter_ref": self.adapter_ref,
                "artifact_record_sha256": artifact.record_sha256,
                "artifact_ref": artifact.artifact_ref.value,
                "identity_digest": identity.semantic_digest,
                "node_attempt_id": cast(str, publication["node_attempt_id"]),
                "node_fence": cast(int, publication["node_fence"]),
                "operation": GameEngineOperation.DETECT.value,
                "output_index": 0,
                "project_ref": identity.project_ref.value,
                "request_sha256": result.request_sha256,
            }
        )
        if (
            publication["identity_digest"] != identity.semantic_digest
            or publication["request_sha256"] != result.request_sha256
            or publication["operation"] != GameEngineOperation.DETECT.value
            or publication["output_index"] != 0
            or publication["artifact_record_sha256"] != artifact.record_sha256
            or not hmac.compare_digest(
                cast(str, publication["publication_sha256"]),
                expected_publication,
            )
        ):
            raise GameEngineIntegrityError(
                "verified engine detection atomic publication evidence changed"
            )
        if state_row is None:
            raise GameEngineIntegrityError(
                "verified engine detection runtime state is unavailable"
            )
        try:
            state_payload = json.loads(cast(str, state_row["state_json"]))
            spec_payload = cast(dict[str, object], state_payload["spec"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise GameEngineIntegrityError(
                "verified engine detection runtime state is malformed"
            ) from exc
        self._validate_detection_spec_payload(identity, spec_payload)

    @staticmethod
    def _validate_detection_spec_payload(
        identity: GameProjectIdentity,
        payload: Mapping[str, object],
    ) -> None:
        executable_name = PurePosixPath(identity.engine_executable_path).name
        normalized_name = re.sub(
            r"engine$",
            "",
            re.sub(r"[^a-z0-9]", "", identity.engine_name.lower()),
        )
        normalized_executable = re.sub(
            r"[^a-z0-9]",
            "",
            executable_name.lower(),
        )
        mounts = payload.get("mounts")
        arguments = payload.get("args")
        if not isinstance(mounts, list) or not isinstance(arguments, list):
            raise GameEngineIntegrityError(
                "engine detection command or mount identity is malformed"
            )
        mounted_executable = any(
            isinstance(item, dict)
            and isinstance(item.get("target_path"), str)
            and PurePosixPath(identity.engine_executable_path).is_relative_to(
                PurePosixPath(cast(str, item["target_path"]))
            )
            for item in mounts
        )
        if (
            payload.get("entrypoint") != identity.engine_executable_path
            or tuple(arguments)
            != identity.engine_version_args
            or payload.get("outputs") != []
            or payload.get("secret_mounts") != []
            or payload.get("environment") != {}
            or payload.get("network_policy") != RuntimeNetworkPolicy.NONE.value
            or mounted_executable
            or not normalized_name
            or normalized_name != normalized_executable
        ):
            raise GameEngineIntegrityError(
                "engine detection was not an exact isolated executable probe"
            )

    def _reuse_verified_build(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        idempotency_key: str,
    ) -> GameEngineOperationResult | None:
        if request.operation is not GameEngineOperation.BUILD:
            return None
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM game_engine_verified_builds WHERE project_id=? AND adapter_ref=? AND request_sha256=?",
                (
                    request.project_ref.value,
                    self.adapter_ref,
                    self._build_cache_key(request),
                ),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return self._recover_unindexed_build(
                access,
                attempt,
                request,
                idempotency_key,
            )
        prior = self._result_from_row(row)
        if (
            prior.operation is not GameEngineOperation.BUILD
            or prior.status is not GameEngineStatus.SUCCEEDED
            or prior.reality is not GameEngineReality.REAL
            or prior.identity_digest != request.identity.semantic_digest
        ):
            raise GameEngineIntegrityError("verified game build cache is malformed")
        for index, (artifact_ref, expected_role) in enumerate(zip(
            prior.output_artifact_refs,
            prior.output_roles,
            strict=True,
        )):
            artifact = self.artifacts.get_artifact(access, artifact_ref)
            if (
                artifact.role != expected_role
                or request.identity.candidate_artifact_ref
                not in artifact.source_artifact_refs
            ):
                raise GameEngineIntegrityError(
                    "verified game build provenance changed"
                )
            self._verify_content(artifact.content_ref, "verified game build")
            self._verify_output_publication(
                request,
                artifact,
                index,
                expected_request_sha256=prior.request_sha256,
            )
        reused = replace(
            prior,
            node_attempt_id=attempt.attempt_id,
            node_fence=attempt.fence,
            request_sha256=request.request_sha256,
            runtime_ref=None,
            reused_verified_build=True,
            observed_at=self._now(),
        )
        return self._persist_result(access, attempt, reused, idempotency_key)

    def _recover_unindexed_build(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        idempotency_key: str,
    ) -> GameEngineOperationResult | None:
        return None

    def _verify_output_publication(
        self,
        request: GameEngineOperationRequest,
        artifact: Artifact,
        output_index: int,
        *,
        expected_request_sha256: str | None = None,
    ) -> None:
        return None

    @staticmethod
    def _detection_cache_key(request: GameEngineOperationRequest) -> str:
        if (
            request.operation is not GameEngineOperation.DETECT
            or request.runtime_spec is None
        ):
            raise GameEngineContractError(
                "verified detection identity requires an exact detection request"
            )
        payload = request.payload()
        payload.pop("control_root_ref")
        payload.pop("resource_allocation_ref")
        return _digest(payload)

    @staticmethod
    def _build_cache_key(request: GameEngineOperationRequest) -> str:
        spec = request.runtime_spec
        if spec is None:
            raise GameEngineContractError(
                "verified build identity requires exact runtime specification"
            )
        return _digest(
            {
                "asset_inputs": [item.payload() for item in request.asset_inputs],
                "environment": dict(spec.environment),
                "forbidden_output_markers": list(
                    request.forbidden_output_markers
                ),
                "identity_digest": request.identity.semantic_digest,
                "image_ref": spec.image_ref,
                "entrypoint": spec.entrypoint,
                "args": list(spec.args),
                "working_directory": spec.working_directory,
                "mounts": [
                    {
                        "read_only": item.read_only,
                        "root_ref": item.root_ref.value,
                        "source_path": item.source_path,
                        "target_path": item.target_path,
                    }
                    for item in spec.mounts
                ],
                "network_policy": spec.network_policy.value,
                "output_roles": list(request.output_roles),
                "outputs": [
                    {
                        "media_type": item.media_type,
                        "path": item.path,
                        "root_ref": item.root_ref.value,
                    }
                    for item in spec.outputs
                ],
                "required_output_markers": list(
                    request.required_output_markers
                ),
                "resource_limits": spec.resource_limits.payload(),
                "secret_mounts": [item.payload() for item in spec.secret_mounts],
                "stderr_limit_bytes": spec.stderr_limit_bytes,
                "stdout_limit_bytes": spec.stdout_limit_bytes,
                "timeout_seconds": float(spec.timeout_seconds),
            }
        )

    def _output_artifact_ref(
        self,
        request: GameEngineOperationRequest,
        index: int,
    ) -> ArtifactRef:
        publication_identity = (
            self._build_cache_key(request)
            if request.operation is GameEngineOperation.BUILD
            else self._detection_cache_key(request)
            if request.operation is GameEngineOperation.DETECT
            else request.request_sha256
        )
        return ArtifactRef(
            request.project_ref,
            "art_"
            + hashlib.sha256(
                (
                    f"{request.project_ref.value}\x00{self.adapter_ref}\x00"
                    f"{publication_identity}\x00{index}"
                ).encode()
            ).hexdigest()[:32],
            1,
        )

    def _claim_runtime_description(
        self,
        attempt: NodeExecutionAttempt,
        identity: GameProjectIdentity,
        control_root_ref: FilesystemRootRef,
        idempotency_key: str,
    ) -> GameEngineRuntimeDescription | None:
        if not isinstance(idempotency_key, str) or _KEY.fullmatch(idempotency_key) is None:
            raise GameEngineContractError("idempotency_key is malformed")
        semantic = _digest(
            {
                "attempt_sha256": attempt.record_sha256,
                "control_root_ref": control_root_ref.value,
                "identity_digest": identity.semantic_digest,
            }
        )
        values = (
            identity.project_ref.value,
            self.adapter_ref,
            attempt.attempt_id,
            attempt.fence,
            idempotency_key,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM game_engine_runtime_description_claims WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND idempotency_key=?",
                values,
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO game_engine_runtime_description_claims VALUES (?,?,?,?,?,?)",
                    (*values, semantic),
                )
                connection.execute(
                    "INSERT INTO game_engine_runtime_description_inflight VALUES (?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%f+00:00','now'))",
                    values,
                )
                connection.commit()
                return None
            if not hmac.compare_digest(cast(str, row["semantic_sha256"]), semantic):
                raise GameEngineConflictError(
                    "game runtime description idempotency identity changed"
                )
            result = connection.execute(
                "SELECT * FROM game_engine_runtime_descriptions WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND idempotency_key=?",
                values,
            ).fetchone()
            connection.commit()
            if result is None:
                raise GameEngineConflictError(
                    "game runtime description claim is already in progress or incomplete"
                )
            return self._runtime_description_from_row(result)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _runtime_description_from_row(
        row: Mapping[str, object],
    ) -> GameEngineRuntimeDescription:
        try:
            payload = json.loads(cast(str, row["description_json"]))
            if not isinstance(payload, dict):
                raise TypeError
            project_ref = ProjectRef(cast(str, payload["project_ref"]))
            requirements = cast(dict[str, object], payload["resource_requirements"])
            description = GameEngineRuntimeDescription(
                project_ref=project_ref,
                identity_digest=cast(str, payload["identity_digest"]),
                adapter_ref=cast(str, payload["adapter_ref"]),
                reality=GameEngineReality(cast(str, payload["reality"])),
                engine_name=cast(str, payload["engine_name"]),
                engine_version=cast(str, payload["engine_version"]),
                toolchain_ref=cast(str, payload["toolchain_ref"]),
                runtime_ref=cast(str, payload["runtime_ref"]),
                executable_sha256=cast(str, payload["executable_sha256"]),
                resource_requirements=GameEngineResourceRequirements(
                    cpu_cores=cast(float | None, requirements["cpu_cores"]),
                    memory_bytes=cast(int | None, requirements["memory_bytes"]),
                    storage_bytes=cast(int | None, requirements["storage_bytes"]),
                    gpu_required=cast(bool, requirements["gpu_required"]),
                    headless_supported=cast(bool, requirements["headless_supported"]),
                    interactive_supported=cast(
                        bool,
                        requirements["interactive_supported"],
                    ),
                ),
                backend_kind=cast(str, payload["backend_kind"]),
                backend_version=cast(str, payload["backend_version"]),
                backend_implementation_id=cast(
                    str,
                    payload["backend_implementation_id"],
                ),
                backend_host_id=cast(str, payload["backend_host_id"]),
                cgroup_version=cast(str, payload["cgroup_version"]),
                security_features=tuple(
                    cast(Sequence[str], payload["security_features"])
                ),
                enforced_limit_kinds=tuple(
                    cast(Sequence[str], payload["enforced_limit_kinds"])
                ),
                unsupported_limit_kinds=tuple(
                    cast(Sequence[str], payload["unsupported_limit_kinds"])
                ),
                gpu_count=cast(int | None, payload["gpu_count"]),
                supported_network_policies=tuple(
                    cast(Sequence[str], payload["supported_network_policies"])
                ),
                evidence_tool_call_refs=tuple(
                    _tool_from(item, project_ref)
                    for item in cast(
                        Sequence[object],
                        payload["evidence_tool_call_refs"],
                    )
                ),
                observed_at=cast(str, payload["observed_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise GameEngineIntegrityError(
                "persisted game runtime description is malformed"
            ) from exc
        if not hmac.compare_digest(
            description.record_sha256,
            cast(str, row["record_sha256"]),
        ):
            raise GameEngineIntegrityError(
                "persisted game runtime description digest changed"
            )
        return description

    def _persist_runtime_description(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        description: GameEngineRuntimeDescription,
        idempotency_key: str,
    ) -> GameEngineRuntimeDescription:
        values = (
            description.project_ref.value,
            self.adapter_ref,
            attempt.attempt_id,
            attempt.fence,
            idempotency_key,
        )
        payload = _json(description.payload())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
            except (NodeExecutionAuthorityError, NodeExecutionError) as exc:
                raise GameEngineAuthorityError(
                    "runtime description lost exact Node authority before persistence"
                ) from exc
            row = connection.execute(
                "SELECT * FROM game_engine_runtime_descriptions WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND idempotency_key=?",
                values,
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO game_engine_runtime_descriptions VALUES (?,?,?,?,?,?,?)",
                    (*values, payload, description.record_sha256),
                )
                connection.execute(
                    "DELETE FROM game_engine_runtime_description_inflight WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND idempotency_key=?",
                    values,
                )
                connection.commit()
                return description
            connection.execute(
                "DELETE FROM game_engine_runtime_description_inflight WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND idempotency_key=?",
                values,
            )
            connection.commit()
            prior = self._runtime_description_from_row(row)
            if prior != description:
                raise GameEngineConflictError(
                    "game runtime description result conflicts"
                )
            return prior
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _now(self) -> str:
        connection = self._connect()
        try:
            value = connection.execute(
                "SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')"
            ).fetchone()[0]
        finally:
            connection.close()
        if not isinstance(value, str):
            raise GameEngineIntegrityError("database timestamp is unavailable")
        return value

    def _require_method(
        self,
        request: GameEngineOperationRequest,
        operation: GameEngineOperation,
    ) -> None:
        if request.operation is not operation:
            raise GameEngineContractError("game adapter method and request operation differ")

    def detect_project(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult:
        return self._invoke(access, attempt, request, GameEngineOperation.DETECT, idempotency_key, secret_values)

    def inspect_project(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult:
        return self._invoke(access, attempt, request, GameEngineOperation.INSPECT, idempotency_key, secret_values)

    def import_project(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult:
        return self._invoke(access, attempt, request, GameEngineOperation.IMPORT, idempotency_key, secret_values)

    def build(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult:
        return self._invoke(access, attempt, request, GameEngineOperation.BUILD, idempotency_key, secret_values)

    def run(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult:
        return self._invoke(access, attempt, request, GameEngineOperation.RUN, idempotency_key, secret_values)

    def test(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult:
        return self._invoke(access, attempt, request, GameEngineOperation.TEST, idempotency_key, secret_values)

    def profile(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult:
        return self._invoke(access, attempt, request, GameEngineOperation.PROFILE, idempotency_key, secret_values)

    def capture(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult:
        return self._invoke(access, attempt, request, GameEngineOperation.CAPTURE, idempotency_key, secret_values)

    def export(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, *, idempotency_key: str, secret_values: Mapping[str, str] = MappingProxyType({})) -> GameEngineOperationResult:
        return self._invoke(access, attempt, request, GameEngineOperation.EXPORT, idempotency_key, secret_values)

    def _invoke(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, operation: GameEngineOperation, idempotency_key: str, secret_values: Mapping[str, str]) -> GameEngineOperationResult:
        raise GameEngineContractError(
            "abstract game-engine adapter invocation is unavailable"
        )


class ReferenceGameEngineAdapter(_BaseGameEngineAdapter):
    """Deterministic contract implementation that never claims real execution."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend | None = None,
    ) -> None:
        super().__init__(
            database_path,
            adapter_ref="adapter://game/reference/v1",
            reality=GameEngineReality.REFERENCE,
            object_store=object_store,
        )

    def _invoke(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, operation: GameEngineOperation, idempotency_key: str, secret_values: Mapping[str, str]) -> GameEngineOperationResult:
        self._require_method(request, operation)
        self._authorize(access, attempt, request)
        if request.identity.adapter_ref != self.adapter_ref:
            raise GameEngineIntegrityError("reference adapter identity differs")
        if request.runtime_spec is not None:
            raise GameEngineContractError("reference adapter cannot claim a real runtime spec")
        if secret_values:
            raise GameEngineContractError("reference adapter does not accept runtime secrets")
        prior = self._claim(attempt, request, idempotency_key)
        if prior is not None:
            return prior
        if not request.reference_evidence_refs:
            raise GameEngineContractError("reference operation requires durable evidence")
        for expected_role, artifact_ref in zip(
            request.output_roles,
            request.reference_evidence_refs,
            strict=True,
        ):
            artifact = self.artifacts.get_artifact(access, artifact_ref)
            if artifact.role != expected_role:
                raise GameEngineIntegrityError("reference evidence Artifact role changed")
            self._verify_content(artifact.content_ref, "reference game evidence")
            required_sources = {request.identity.candidate_artifact_ref}
            if request.build_artifact_ref is not None:
                required_sources.add(request.build_artifact_ref)
            required_sources.update(
                item.artifact_ref for item in request.asset_inputs
            )
            if not required_sources <= set(artifact.source_artifact_refs):
                raise GameEngineIntegrityError(
                    "reference evidence is not chained to exact candidate and build"
                )
        if operation in {
            GameEngineOperation.RUN,
            GameEngineOperation.CAPTURE,
            GameEngineOperation.PROFILE,
            GameEngineOperation.EXPORT,
        } and request.build_artifact_ref is None:
            raise GameEngineContractError("operation requires an exact verified build")
        result = GameEngineOperationResult(
            project_ref=request.project_ref,
            operation=operation,
            identity_digest=request.identity.semantic_digest,
            request_sha256=request.request_sha256,
            adapter_ref=self.adapter_ref,
            reality=self.reality,
            status=GameEngineStatus.SUCCEEDED,
            node_attempt_id=attempt.attempt_id,
            node_fence=attempt.fence,
            runtime_ref=None,
            receipt_artifact_refs=(),
            tool_call_refs=(),
            output_artifact_refs=request.reference_evidence_refs,
            output_roles=request.output_roles,
            stdout_ref=None,
            stderr_ref=None,
            failure_reason=None,
            runtime_observed=False,
            reused_verified_build=False,
            observed_at=self._now(),
        )
        return self._persist_result(access, attempt, result, idempotency_key)

    def describe_runtime(self, access: ProjectAccess, attempt: NodeExecutionAttempt, identity: GameProjectIdentity, *, control_root_ref: FilesystemRootRef, idempotency_key: str) -> GameEngineRuntimeDescription:
        self._authorize_runtime_description(
            access,
            attempt,
            identity,
            control_root_ref,
        )
        if identity.adapter_ref != self.adapter_ref:
            raise GameEngineIntegrityError("reference adapter identity differs")
        prior = self._claim_runtime_description(
            attempt,
            identity,
            control_root_ref,
            idempotency_key,
        )
        if prior is not None:
            return prior
        description = GameEngineRuntimeDescription(
            identity.project_ref,
            identity.semantic_digest,
            self.adapter_ref,
            self.reality,
            identity.engine_name,
            identity.engine_version,
            identity.toolchain_ref,
            identity.runtime_ref,
            identity.executable_sha256,
            identity.resource_requirements,
            "reference.semantic",
            "1.0.0",
            "reference.semantic",
            "reference.not-observed",
            "reference.not-observed",
            (),
            (),
            (),
            None,
            (),
            (),
            self._now(),
        )
        return self._persist_runtime_description(
            access,
            attempt,
            description,
            idempotency_key,
        )


class IsolatedRuntimeGameEngineAdapter(_BaseGameEngineAdapter):
    """Real adapter composing exact engine commands through IsolatedRuntimeAdapter."""

    def __init__(
        self,
        database_path: str | Path,
        runtime_adapter: IsolatedRuntimeAdapter,
        object_store: ObjectStorageBackend | None = None,
    ) -> None:
        if not isinstance(runtime_adapter, IsolatedRuntimeAdapter):
            raise TypeError("runtime_adapter must implement IsolatedRuntimeAdapter")
        if object_store is None:
            observed_store = getattr(runtime_adapter, "object_store", None)
            if isinstance(observed_store, ObjectStorageBackend):
                object_store = observed_store
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError(
                "REAL game adapter requires exact content-addressed object storage"
            )
        super().__init__(
            database_path,
            adapter_ref="adapter://game/isolated-runtime/v1",
            reality=GameEngineReality.REAL,
            object_store=object_store,
        )
        self.runtime = runtime_adapter

    @staticmethod
    def _phase_key(
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        idempotency_key: str,
        phase: str,
    ) -> str:
        material = (
            f"{attempt.record_sha256}\x00{request.request_sha256}\x00"
            f"{idempotency_key}\x00{phase}"
        )
        return f"game-{phase}-{hashlib.sha256(material.encode()).hexdigest()[:40]}"

    @staticmethod
    def _receipt_evidence(
        receipts: Sequence[RuntimeReceipt],
    ) -> tuple[tuple[ArtifactRef, ...], tuple[ToolCallRef, ...]]:
        artifacts = tuple(
            sorted(
                {item.artifact_ref.value: item.artifact_ref for item in receipts}.values(),
                key=lambda item: item.value,
            )
        )
        calls = {
            receipt.tool_call_ref.value: receipt.tool_call_ref for receipt in receipts
        }
        for receipt in receipts:
            calls.update({item.value: item for item in receipt.process_call_refs})
        return artifacts, tuple(sorted(calls.values(), key=lambda item: item.value))

    def _validate_runtime_binding(
        self,
        request: GameEngineOperationRequest,
        description: GameEngineRuntimeDescription,
    ) -> None:
        spec = request.runtime_spec
        if spec is None:
            raise GameEngineContractError("real adapter requires runtime specification")
        if description.identity_digest != request.identity.semantic_digest:
            raise GameEngineIntegrityError("runtime description identity changed")
        expected_runtime_ref = f"container-image://{spec.image_ref}"
        if request.identity.runtime_ref != expected_runtime_ref:
            raise GameEngineIntegrityError(
                "game runtime identity differs from exact immutable image"
            )
        if spec.network_policy.value not in description.supported_network_policies:
            raise GameEngineAuthorityError(
                "game runtime cannot enforce requested network policy"
            )
        requirements = request.identity.resource_requirements
        limits = spec.resource_limits
        for required, selected, label in (
            (requirements.cpu_cores, limits.cpus, "CPU"),
            (requirements.memory_bytes, limits.memory_bytes, "memory"),
            (requirements.storage_bytes, limits.storage_bytes, "storage"),
        ):
            if required is not None and selected != required:
                raise GameEngineIntegrityError(
                    f"game {label} requirement differs from runtime limit"
                )
        for required, limit_kind in (
            (requirements.cpu_cores, "cpu"),
            (requirements.memory_bytes, "memory"),
            (requirements.storage_bytes, "storage"),
        ):
            if required is not None and limit_kind not in description.enforced_limit_kinds:
                raise GameEngineAuthorityError(
                    f"game runtime did not prove enforcement of {limit_kind} limits"
                )
        if requirements.gpu_required and (
            limits.gpu_count is None
            or limits.gpu_count < 1
            or description.gpu_count is None
            or description.gpu_count < 1
        ):
            raise GameEngineAuthorityError(
                "game requires GPU resources that the runtime did not observe"
            )

    @staticmethod
    def _runtime_input_operation_key(
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        operation: str,
        path: str,
    ) -> str:
        material = (
            f"{attempt.record_sha256}\x00{request.request_sha256}\x00"
            f"{operation}\x00{path}"
        )
        return f"game-input-{hashlib.sha256(material.encode()).hexdigest()[:40]}"

    def _validated_runtime_inputs(
        self,
        access: ProjectAccess,
        request: GameEngineOperationRequest,
    ) -> tuple[tuple[GameAssetInput, GameRuntimeInputBinding, Artifact], ...]:
        assets = {item.artifact_ref: item for item in request.asset_inputs}
        bindings = {
            item.artifact_ref: item for item in request.runtime_input_bindings
        }
        if not assets and not bindings:
            return ()
        missing = set(assets) - set(bindings)
        extra = set(bindings) - set(assets)
        if missing or extra:
            stale = any(
                missing_ref.artifact_id == extra_ref.artifact_id
                and missing_ref.revision != extra_ref.revision
                for missing_ref in missing
                for extra_ref in extra
            )
            if stale:
                raise GameEngineIntegrityError(
                    "game runtime input binding is stale"
                )
            if missing and not extra:
                raise GameEngineIntegrityError(
                    "game runtime input binding was omitted"
                )
            if extra and not missing:
                raise GameEngineIntegrityError(
                    "game runtime input binding is extra"
                )
            raise GameEngineIntegrityError(
                "game runtime input binding coverage is forged"
            )
        validated: list[
            tuple[GameAssetInput, GameRuntimeInputBinding, Artifact]
        ] = []
        for asset in request.asset_inputs:
            binding = bindings[asset.artifact_ref]
            try:
                artifact = self.artifacts.get_artifact(access, asset.artifact_ref)
            except ArtifactNotFoundError as exc:
                raise GameEngineIntegrityError(
                    "game runtime input Artifact is missing"
                ) from exc
            if (
                artifact.role != asset.expected_role
                or binding.artifact_role != asset.expected_role
                or binding.artifact_role != artifact.role
            ):
                raise GameEngineIntegrityError(
                    "game runtime input Artifact role is wrong"
                )
            if artifact.content_ref is None:
                raise GameEngineIntegrityError(
                    "game runtime input Artifact content is missing"
                )
            if artifact.content_ref != binding.content_ref:
                raise GameEngineIntegrityError(
                    "game runtime input content binding is forged"
                )
            self._verify_content(
                binding.content_ref,
                "game runtime input Artifact",
            )
            validated.append((asset, binding, artifact))
        return tuple(validated)

    @staticmethod
    def _runtime_input_mount_conflicts(mount: RuntimeMount) -> bool:
        target = PurePosixPath(mount.target_path)
        root = PurePosixPath(_RUNTIME_INPUT_ROOT)
        return (
            target == root
            or target.is_relative_to(root)
            or root.is_relative_to(target)
        )

    def _materialize_runtime_inputs(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        spec: IsolatedRuntimeSpec,
    ) -> IsolatedRuntimeSpec:
        validated = self._validated_runtime_inputs(access, request)
        if not validated:
            return spec
        if self.filesystem is None or self.object_store is None:
            raise GameEngineIntegrityError(
                "game runtime input materialization services are unavailable"
            )
        if any(self._runtime_input_mount_conflicts(item) for item in spec.mounts):
            raise GameEngineIntegrityError(
                "game runtime input mount is extra or substitutes adapter authority"
            )
        stage_digest = hashlib.sha256(
            f"{attempt.record_sha256}\x00{request.request_sha256}".encode()
        ).hexdigest()[:40]
        stage_directory = f".minitz-game-inputs-{stage_digest}"
        self.filesystem.mkdir(
            access,
            attempt,
            root_ref=request.control_root_ref,
            path=stage_directory,
            idempotency_key=self._runtime_input_operation_key(
                attempt,
                request,
                "mkdir",
                stage_directory,
            ),
        )
        parents = {
            parent.as_posix()
            for _, binding, _ in validated
            for parent in PurePosixPath(binding.runtime_path).parents
            if parent != PurePosixPath(".")
        }
        for parent in sorted(
            parents,
            key=lambda value: (len(PurePosixPath(value).parts), value),
        ):
            path = f"{stage_directory}/{parent}"
            self.filesystem.mkdir(
                access,
                attempt,
                root_ref=request.control_root_ref,
                path=path,
                idempotency_key=self._runtime_input_operation_key(
                    attempt,
                    request,
                    "mkdir",
                    path,
                ),
            )
        manifest_bindings: list[dict[str, object]] = []
        for asset, binding, _ in sorted(
            validated,
            key=lambda item: item[1].runtime_path,
        ):
            path = f"{stage_directory}/{binding.runtime_path}"
            written = self.filesystem.write(
                access,
                attempt,
                root_ref=request.control_root_ref,
                path=path,
                content_ref=binding.content_ref,
                idempotency_key=self._runtime_input_operation_key(
                    attempt,
                    request,
                    "write",
                    path,
                ),
                mode=0o444,
            )
            observed = self.filesystem.read(
                access,
                attempt,
                root_ref=request.control_root_ref,
                path=path,
                media_type=binding.content_ref.media_type,
                idempotency_key=self._runtime_input_operation_key(
                    attempt,
                    request,
                    "read",
                    path,
                ),
            )
            if (
                written.output_ref != binding.content_ref
                or observed.output_ref != binding.content_ref
            ):
                raise GameEngineIntegrityError(
                    "game runtime input materialized bytes are forged or stale"
                )
            manifest_bindings.append({**binding.payload(), "kind": asset.kind})
        manifest_payload = {
            "bindings": manifest_bindings,
            "project_ref": request.project_ref.value,
            "request_sha256": request.request_sha256,
            "schema_version": 1,
        }
        manifest_ref = self.object_store.put(
            _json(manifest_payload).encode(),
            media_type="application/vnd.minitz.game-runtime-input-bindings+json",
        )
        manifest_path = f"{stage_directory}/bindings.json"
        written_manifest = self.filesystem.write(
            access,
            attempt,
            root_ref=request.control_root_ref,
            path=manifest_path,
            content_ref=manifest_ref,
            idempotency_key=self._runtime_input_operation_key(
                attempt,
                request,
                "write",
                manifest_path,
            ),
            mode=0o444,
        )
        observed_manifest = self.filesystem.read(
            access,
            attempt,
            root_ref=request.control_root_ref,
            path=manifest_path,
            media_type=manifest_ref.media_type,
            idempotency_key=self._runtime_input_operation_key(
                attempt,
                request,
                "read",
                manifest_path,
            ),
        )
        if (
            written_manifest.output_ref != manifest_ref
            or observed_manifest.output_ref != manifest_ref
        ):
            raise GameEngineIntegrityError(
                "game runtime input binding evidence failed materialization"
            )
        root = self.filesystem.get_root(access, request.control_root_ref)
        for relative in sorted(
            {stage_directory, *(f"{stage_directory}/{item}" for item in parents)},
            key=lambda value: len(PurePosixPath(value).parts),
            reverse=True,
        ):
            path = os.fspath(Path(root.canonical_path).joinpath(*PurePosixPath(relative).parts))
            descriptor = os.open(
                path,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
            try:
                state = os.fstat(descriptor)
                if not stat.S_ISDIR(state.st_mode):
                    raise GameEngineIntegrityError(
                        "game runtime input staging path changed kind"
                    )
                os.fchmod(descriptor, 0o555)
            finally:
                os.close(descriptor)
        return replace(
            spec,
            mounts=(
                *spec.mounts,
                RuntimeMount(
                    request.control_root_ref,
                    stage_directory,
                    _RUNTIME_INPUT_ROOT,
                    True,
                ),
            ),
        )

    def _unstaged_runtime_spec(
        self,
        request: GameEngineOperationRequest,
        spec: IsolatedRuntimeSpec,
    ) -> IsolatedRuntimeSpec:
        staged = tuple(
            item for item in spec.mounts if item.target_path == _RUNTIME_INPUT_ROOT
        )
        if request.runtime_input_bindings:
            if (
                len(staged) != 1
                or staged[0].root_ref != request.control_root_ref
                or not staged[0].read_only
                or not staged[0].source_path.startswith(".minitz-game-inputs-")
            ):
                raise GameEngineIntegrityError(
                    "recovered game runtime input mount changed"
                )
        elif staged:
            raise GameEngineIntegrityError(
                "recovered game runtime contains an extra input mount"
            )
        return replace(
            spec,
            mounts=tuple(item for item in spec.mounts if item not in staged),
        )

    def _read_evidence(self, content_ref: ContentRef | None) -> bytes:
        if content_ref is None:
            return b""
        if self.object_store is None:
            raise GameEngineIntegrityError("game object storage is unavailable")
        try:
            return self.object_store.read(content_ref)
        except ObjectStorageError as exc:
            raise GameEngineIntegrityError(
                "game operation evidence content is unavailable"
            ) from exc

    def _verify_output_publication(
        self,
        request: GameEngineOperationRequest,
        artifact: Artifact,
        output_index: int,
        *,
        expected_request_sha256: str | None = None,
    ) -> None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM game_engine_output_publications WHERE project_id=? AND adapter_ref=? AND artifact_id=? AND artifact_revision=?",
                (
                    request.project_ref.value,
                    self.adapter_ref,
                    artifact.artifact_id,
                    artifact.revision,
                ),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise GameEngineIntegrityError(
                "verified game output lacks atomic Node publication evidence"
            )
        stored_request_sha256 = cast(str, row["request_sha256"])
        expected = _digest(
            {
                "adapter_ref": self.adapter_ref,
                "artifact_record_sha256": artifact.record_sha256,
                "artifact_ref": artifact.artifact_ref.value,
                "identity_digest": request.identity.semantic_digest,
                "node_attempt_id": cast(str, row["node_attempt_id"]),
                "node_fence": cast(int, row["node_fence"]),
                "operation": request.operation.value,
                "output_index": output_index,
                "project_ref": request.project_ref.value,
                "request_sha256": stored_request_sha256,
            }
        )
        if (
            artifact.artifact_ref != self._output_artifact_ref(request, output_index)
            or row["identity_digest"] != request.identity.semantic_digest
            or (
                request.operation is not GameEngineOperation.BUILD
                and stored_request_sha256 != request.request_sha256
            )
            or (
                expected_request_sha256 is not None
                and stored_request_sha256 != expected_request_sha256
            )
            or row["operation"] != request.operation.value
            or row["output_index"] != output_index
            or row["artifact_record_sha256"] != artifact.record_sha256
            or not hmac.compare_digest(
                cast(str, row["publication_sha256"]),
                expected,
            )
        ):
            raise GameEngineIntegrityError(
                "verified game output atomic publication evidence changed"
            )

    def _recover_unindexed_build(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        idempotency_key: str,
    ) -> GameEngineOperationResult | None:
        if not isinstance(self.runtime, _RuntimeReceiptReader):
            return None
        expected_sources = {
            request.identity.candidate_artifact_ref,
            *(item.artifact_ref for item in request.asset_inputs),
        }
        output_refs = tuple(
            self._output_artifact_ref(request, index)
            for index in range(len(request.output_roles))
        )
        raw_refs: list[ArtifactRef] = []
        for index, (artifact_ref, role) in enumerate(
            zip(output_refs, request.output_roles, strict=True)
        ):
            try:
                artifact = self.artifacts.get_artifact(access, artifact_ref)
            except ArtifactNotFoundError:
                return None
            self._verify_content(artifact.content_ref, "unindexed verified build")
            raw = tuple(
                source
                for source in artifact.source_artifact_refs
                if self.artifacts.get_artifact(access, source).role == "runtime.output"
            )
            if (
                artifact.role != role
                or not expected_sources <= set(artifact.source_artifact_refs)
                or len(raw) != 1
                or self.artifacts.get_artifact(access, raw[0]).content_ref
                != artifact.content_ref
                or dict(artifact.metadata).get("semantic_label")
                != f"game-build-{request.identity.semantic_digest}-{index}"
            ):
                raise GameEngineIntegrityError(
                    "unindexed game build publication evidence changed"
                )
            self._verify_output_publication(request, artifact, index)
            raw_refs.append(raw[0])
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT call_id,receipt_json FROM isolated_runtime_operation_results WHERE project_id=?",
                (request.project_ref.value,),
            ).fetchall()
        finally:
            connection.close()
        collection: RuntimeReceipt | None = None
        execution: RuntimeReceipt | None = None
        for row in rows:
            try:
                payload = json.loads(cast(str, row["receipt_json"]))
            except json.JSONDecodeError as exc:
                raise GameEngineIntegrityError(
                    "isolated runtime recovery receipt is malformed"
                ) from exc
            if not isinstance(payload, dict):
                raise GameEngineIntegrityError(
                    "isolated runtime recovery receipt is malformed"
                )
            outputs = payload.get("output_artifact_refs")
            if (
                payload.get("operation") == "collect"
                and isinstance(outputs, list)
                and {item.value for item in raw_refs} <= set(outputs)
            ):
                collection = self.runtime.get_receipt(
                    access,
                    ToolCallRef(request.project_ref, cast(str, row["call_id"])),
                )
                break
        if collection is None:
            raise GameEngineIntegrityError(
                "unindexed game build lacks exact collection evidence"
            )
        if (
            collection.state.status is not RuntimeStatus.SUCCEEDED
            or self._build_cache_key(
                replace(
                    request,
                    runtime_spec=self._unstaged_runtime_spec(
                        request,
                        collection.state.spec,
                    ),
                )
            )
            != self._build_cache_key(request)
        ):
            raise GameEngineIntegrityError(
                "unindexed game build runtime identity changed"
            )
        for row in rows:
            try:
                payload = json.loads(cast(str, row["receipt_json"]))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict) or payload.get("operation") != "execute":
                continue
            state_ref = payload.get("state_ref")
            if (
                isinstance(state_ref, str)
                and f"/{collection.state.runtime_ref.runtime_id}/" in state_ref
            ):
                candidate = self.runtime.get_receipt(
                    access,
                    ToolCallRef(request.project_ref, cast(str, row["call_id"])),
                )
                if candidate.state.status is RuntimeStatus.SUCCEEDED:
                    execution = candidate
                    break
        if execution is None:
            raise GameEngineIntegrityError(
                "unindexed game build lacks successful execution evidence"
            )
        receipt_artifacts, tool_calls = self._receipt_evidence(
            (execution, collection)
        )
        recovered = GameEngineOperationResult(
            project_ref=request.project_ref,
            operation=GameEngineOperation.BUILD,
            identity_digest=request.identity.semantic_digest,
            request_sha256=request.request_sha256,
            adapter_ref=self.adapter_ref,
            reality=GameEngineReality.REAL,
            status=GameEngineStatus.SUCCEEDED,
            node_attempt_id=attempt.attempt_id,
            node_fence=attempt.fence,
            runtime_ref=None,
            receipt_artifact_refs=receipt_artifacts,
            tool_call_refs=tool_calls,
            output_artifact_refs=output_refs,
            output_roles=request.output_roles,
            stdout_ref=execution.stdout_ref,
            stderr_ref=execution.stderr_ref,
            failure_reason=None,
            runtime_observed=False,
            reused_verified_build=True,
            observed_at=collection.completed_at,
        )
        self._authorize(access, attempt, request)
        persisted = self._persist_result(
            access,
            attempt,
            recovered,
            idempotency_key,
        )
        self._persist_verified_build(access, attempt, request, persisted)
        return persisted

    def _validate_outputs(
        self,
        access: ProjectAccess,
        request: GameEngineOperationRequest,
        executed: RuntimeReceipt,
        raw_output_refs: tuple[ArtifactRef, ...],
    ) -> None:
        expected_raw_outputs = (
            0
            if request.operation is GameEngineOperation.DETECT
            else len(request.output_roles)
        )
        if len(raw_output_refs) != expected_raw_outputs:
            raise GameEngineIntegrityError(
                "successful process lacks one or more required output Artifacts"
            )
        evidence = bytearray()
        evidence.extend(self._read_evidence(executed.stdout_ref))
        evidence.extend(b"\n")
        evidence.extend(self._read_evidence(executed.stderr_ref))
        for raw_ref in raw_output_refs:
            artifact = self.artifacts.get_artifact(access, raw_ref)
            if artifact.role != "runtime.output":
                raise GameEngineIntegrityError(
                    "isolated runtime output Artifact role changed"
                )
            self._verify_content(artifact.content_ref, "game runtime output")
            evidence.extend(b"\n")
            evidence.extend(self._read_evidence(artifact.content_ref))
        if request.operation is GameEngineOperation.DETECT:
            detected = self._read_evidence(executed.stdout_ref)
            if (
                not detected
                or not self._matches_exact_engine_version(
                    detected,
                    request.identity.engine_version,
                )
            ):
                raise GameEngineIntegrityError(
                    "engine version probe did not observe the exact declared version"
                )
        for marker in request.required_output_markers:
            if marker.encode() not in evidence:
                raise GameEngineIntegrityError(
                    "required game output marker was not observed"
                )
        for marker in request.forbidden_output_markers:
            if marker.encode() in evidence:
                raise GameEngineIntegrityError(
                    "forbidden game failure marker was observed"
                )
        if request.operation is GameEngineOperation.PROFILE:
            for metric in request.requested_metrics:
                if metric.encode() not in evidence:
                    raise GameEngineIntegrityError(
                        "requested game profile metric was not observed"
                    )

    def _publish_outputs(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: GameEngineOperationRequest,
        executed: RuntimeReceipt,
        raw_output_refs: tuple[ArtifactRef, ...],
        result: GameEngineOperationResult,
        idempotency_key: str,
    ) -> GameEngineOperationResult:
        expected_output_refs = tuple(
            self._output_artifact_ref(request, index)
            for index in range(len(request.output_roles))
        )
        if (
            result.status is not GameEngineStatus.SUCCEEDED
            or result.operation is not request.operation
            or result.request_sha256 != request.request_sha256
            or result.node_attempt_id != attempt.attempt_id
            or result.node_fence != attempt.fence
            or result.output_artifact_refs != expected_output_refs
            or result.output_roles != request.output_roles
        ):
            raise GameEngineContractError(
                "atomic game output publication requires the exact success result"
            )
        run_attempt = self._run_attempt(access, attempt)
        shared_sources = {
            request.identity.candidate_artifact_ref,
            *(item.artifact_ref for item in request.asset_inputs),
        }
        if request.build_artifact_ref is not None:
            shared_sources.add(request.build_artifact_ref)
        output_material: tuple[tuple[ArtifactRef, ContentRef, str], ...]
        if request.operation is GameEngineOperation.DETECT:
            self._verify_content(executed.stdout_ref, "game engine detection stdout")
            output_material = (
                (
                    executed.artifact_ref,
                    cast(ContentRef, executed.stdout_ref),
                    request.output_roles[0],
                ),
            )
        else:
            values: list[tuple[ArtifactRef, ContentRef, str]] = []
            for raw_ref, role in zip(
                raw_output_refs,
                request.output_roles,
                strict=True,
            ):
                raw = self.artifacts.get_artifact(access, raw_ref)
                self._verify_content(raw.content_ref, "game runtime output")
                values.append((raw_ref, cast(ContentRef, raw.content_ref), role))
            output_material = tuple(values)
        prepared: list[
            tuple[
                ArtifactRef,
                str,
                ContentRef,
                tuple[ArtifactRef, ...],
                Mapping[str, str],
                int,
            ]
        ] = []
        for index, (raw_ref, content_ref, role) in enumerate(output_material):
            sources = tuple(
                sorted(
                    {*shared_sources, raw_ref},
                    key=lambda item: item.value,
                )
            )
            metadata = {
                "media_type": content_ref.media_type,
                "schema_ref": f"schema://minitz/{role.replace('.', '-')}/1",
                "schema_version": "1.0.0",
                "semantic_label": (
                    f"game-{request.operation.value}-"
                    f"{request.identity.semantic_digest}-{index}"
                ),
            }
            artifact_ref = self._output_artifact_ref(request, index)
            prepared.append(
                (
                    artifact_ref,
                    role,
                    content_ref,
                    sources,
                    metadata,
                    index,
                )
            )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
                current_run = self.runs.assert_current_run_authority_in_transaction(
                    connection,
                    access,
                    run_attempt,
                )
            except (
                NodeExecutionAuthorityError,
                NodeExecutionError,
                RunAuthorityError,
                RunError,
            ) as exc:
                raise GameEngineAuthorityError(
                    "game output lost exact Node or Run authority before publication"
                ) from exc
            if (
                current_run.task_ref != attempt.task_ref
                or current_run.task_digest != attempt.task_digest
            ):
                raise GameEngineAuthorityError(
                    "game output Run Task identity changed"
                )
            published: list[ArtifactRef] = []
            for (
                artifact_ref,
                role,
                content_ref,
                sources,
                prepared_metadata,
                output_index,
            ) in prepared:
                self.artifacts._verify_source_artifacts_in_transaction(
                    connection,
                    request.project_ref,
                    sources,
                )
                publication = connection.execute(
                    "SELECT * FROM game_engine_output_publications WHERE project_id=? AND adapter_ref=? AND artifact_id=? AND artifact_revision=?",
                    (
                        request.project_ref.value,
                        self.adapter_ref,
                        artifact_ref.artifact_id,
                        artifact_ref.revision,
                    ),
                ).fetchone()
                if publication is None:
                    artifact = Artifact(
                        artifact_ref=artifact_ref,
                        role=role,
                        content_ref=content_ref,
                        source_refs=(),
                        source_artifact_refs=sources,
                        source_content_refs=(content_ref,),
                        derivation_type=f"game.engine.{request.operation.value}",
                        producer_run_ref=run_attempt.run_ref,
                        producer_attempt_id=run_attempt.attempt_id,
                        producer_fence=run_attempt.fence,
                        metadata=prepared_metadata,
                        created_at=self.artifacts._database_now(connection),
                    )
                    self.artifacts._insert_artifact(connection, artifact)
                    self.artifacts._insert_source_bindings(connection, artifact)
                    self.artifacts._insert_derivation(connection, artifact)
                    self.artifacts._insert_initial_head(connection, artifact)
                    publication_payload = {
                        "adapter_ref": self.adapter_ref,
                        "artifact_record_sha256": artifact.record_sha256,
                        "artifact_ref": artifact_ref.value,
                        "identity_digest": request.identity.semantic_digest,
                        "node_attempt_id": attempt.attempt_id,
                        "node_fence": attempt.fence,
                        "operation": request.operation.value,
                        "output_index": output_index,
                        "project_ref": request.project_ref.value,
                        "request_sha256": request.request_sha256,
                    }
                    connection.execute(
                        "INSERT INTO game_engine_output_publications VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            request.project_ref.value,
                            self.adapter_ref,
                            artifact_ref.artifact_id,
                            artifact_ref.revision,
                            request.identity.semantic_digest,
                            request.request_sha256,
                            request.operation.value,
                            output_index,
                            attempt.attempt_id,
                            attempt.fence,
                            artifact.record_sha256,
                            _digest(publication_payload),
                        ),
                    )
                else:
                    artifact = self.artifacts._fetch_artifact(
                        connection,
                        artifact_ref,
                    )
                    stored_request_sha256 = cast(
                        str,
                        publication["request_sha256"],
                    )
                    expected_publication_sha256 = _digest(
                        {
                            "adapter_ref": self.adapter_ref,
                            "artifact_record_sha256": artifact.record_sha256,
                            "artifact_ref": artifact_ref.value,
                            "identity_digest": request.identity.semantic_digest,
                            "node_attempt_id": cast(
                                str,
                                publication["node_attempt_id"],
                            ),
                            "node_fence": cast(int, publication["node_fence"]),
                            "operation": request.operation.value,
                            "output_index": output_index,
                            "project_ref": request.project_ref.value,
                            "request_sha256": stored_request_sha256,
                        }
                    )
                    if (
                        publication["identity_digest"]
                        != request.identity.semantic_digest
                        or (
                            request.operation is not GameEngineOperation.BUILD
                            and stored_request_sha256 != request.request_sha256
                        )
                        or publication["operation"] != request.operation.value
                        or publication["output_index"] != output_index
                        or publication["artifact_record_sha256"]
                        != artifact.record_sha256
                        or not hmac.compare_digest(
                            cast(str, publication["publication_sha256"]),
                            expected_publication_sha256,
                        )
                    ):
                        raise GameEngineIntegrityError(
                            "game output publication authority record changed"
                        )
                evidence_sources = tuple(
                    item
                    for item in artifact.source_artifact_refs
                    if item not in shared_sources
                )
                evidence_role = (
                    "runtime.execute.receipt"
                    if request.operation is GameEngineOperation.DETECT
                    else "runtime.output"
                )
                evidence = (
                    None
                    if len(evidence_sources) != 1
                    else self.artifacts._fetch_artifact(
                        connection,
                        evidence_sources[0],
                    )
                )
                if (
                    artifact.role != role
                    or artifact.content_ref != content_ref
                    or not shared_sources <= set(artifact.source_artifact_refs)
                    or len(artifact.source_artifact_refs)
                    != len(shared_sources) + 1
                    or artifact.source_content_refs != (content_ref,)
                    or artifact.derivation_type
                    != f"game.engine.{request.operation.value}"
                    or dict(artifact.metadata) != prepared_metadata
                    or evidence is None
                    or evidence.role != evidence_role
                    or artifact.producer_run_ref != evidence.producer_run_ref
                    or artifact.producer_attempt_id
                    != evidence.producer_attempt_id
                    or artifact.producer_fence != evidence.producer_fence
                    or (
                        evidence_role == "runtime.output"
                        and evidence.content_ref != artifact.content_ref
                    )
                ):
                    raise GameEngineIntegrityError(
                        "deterministic game output publication identity conflicts"
                    )
                published.append(artifact.artifact_ref)
            if tuple(published) != result.output_artifact_refs:
                raise GameEngineIntegrityError(
                    "atomic game output set differs from the exact result"
                )
            result_values = (
                result.project_ref.value,
                self.adapter_ref,
                attempt.attempt_id,
                attempt.fence,
                result.operation.value,
                idempotency_key,
            )
            result_json = _json(result.payload())
            existing_result = connection.execute(
                "SELECT * FROM game_engine_operation_results WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                result_values,
            ).fetchone()
            persisted = result
            if existing_result is None:
                connection.execute(
                    "INSERT INTO game_engine_operation_results VALUES (?,?,?,?,?,?,?,?)",
                    (*result_values, result_json, result.record_sha256),
                )
            else:
                persisted = self._result_from_row(existing_result)
                if persisted != result:
                    raise GameEngineConflictError(
                        "game-engine result identity conflicts"
                    )
            if request.operation is GameEngineOperation.DETECT:
                detection_values = (
                    request.project_ref.value,
                    self.adapter_ref,
                    request.identity.semantic_digest,
                )
                detection = connection.execute(
                    "SELECT * FROM game_engine_verified_detections WHERE project_id=? AND adapter_ref=? AND identity_digest=?",
                    detection_values,
                ).fetchone()
                if detection is None:
                    connection.execute(
                        "INSERT INTO game_engine_verified_detections VALUES (?,?,?,?,?)",
                        (
                            *detection_values,
                            result_json,
                            result.record_sha256,
                        ),
                    )
                else:
                    prior = self._result_from_row(detection)
                    if (
                        prior.identity_digest != result.identity_digest
                        or prior.output_artifact_refs
                        != result.output_artifact_refs
                        or prior.output_roles != result.output_roles
                        or prior.runtime_ref != result.runtime_ref
                        or prior.receipt_artifact_refs
                        != result.receipt_artifact_refs
                        or prior.tool_call_refs != result.tool_call_refs
                    ):
                        raise GameEngineConflictError(
                            "verified game detection identity conflicts"
                        )
            if request.operation is GameEngineOperation.BUILD:
                build_values = (
                    request.project_ref.value,
                    self.adapter_ref,
                    self._build_cache_key(request),
                )
                build = connection.execute(
                    "SELECT * FROM game_engine_verified_builds WHERE project_id=? AND adapter_ref=? AND request_sha256=?",
                    build_values,
                ).fetchone()
                if build is None:
                    connection.execute(
                        "INSERT INTO game_engine_verified_builds VALUES (?,?,?,?,?)",
                        (*build_values, result_json, result.record_sha256),
                    )
                else:
                    prior = self._result_from_row(build)
                    if (
                        prior.identity_digest != result.identity_digest
                        or prior.output_artifact_refs
                        != result.output_artifact_refs
                        or prior.output_roles != result.output_roles
                    ):
                        raise GameEngineConflictError(
                            "verified game build identity conflicts"
                        )
            connection.execute(
                "DELETE FROM game_engine_operation_inflight WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                result_values,
            )
            connection.commit()
            return persisted
        except sqlite3.Error as exc:
            connection.rollback()
            raise GameEngineIntegrityError(
                "atomic game output and result publication failed"
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _invoke(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: GameEngineOperationRequest, operation: GameEngineOperation, idempotency_key: str, secret_values: Mapping[str, str]) -> GameEngineOperationResult:
        self._require_method(request, operation)
        self._authorize(access, attempt, request, verify_assets=False)
        if request.identity.adapter_ref != self.adapter_ref:
            raise GameEngineIntegrityError("real adapter identity differs")
        if request.runtime_spec is None:
            raise GameEngineContractError("real adapter requires exact isolated runtime spec")
        if request.reference_evidence_refs:
            raise GameEngineContractError("real adapter cannot consume reference-only evidence")
        if operation in {
            GameEngineOperation.RUN,
            GameEngineOperation.CAPTURE,
            GameEngineOperation.PROFILE,
            GameEngineOperation.EXPORT,
        } and request.build_artifact_ref is None:
            raise GameEngineContractError("operation requires an exact verified build")
        spec = request.runtime_spec
        if operation is GameEngineOperation.DETECT:
            self._validate_detection_spec_payload(
                request.identity,
                spec.payload(),
            )
        else:
            self._require_verified_detection(access, request.identity)
        prior = self._claim(attempt, request, idempotency_key)
        if prior is not None:
            self._persist_verified_detection(
                access,
                attempt,
                request.identity,
                prior,
            )
            self._persist_verified_build(access, attempt, request, prior)
            return prior
        reused_detection = self._reuse_verified_detection(
            access,
            attempt,
            request,
            idempotency_key,
        )
        if reused_detection is not None:
            return reused_detection
        reused = self._reuse_verified_build(
            access,
            attempt,
            request,
            idempotency_key,
        )
        if reused is not None:
            return reused
        if operation is GameEngineOperation.DETECT:
            descriptor = self._observe_runtime_backend(
                access,
                attempt,
                request.identity,
                request.control_root_ref,
                self._phase_key(
                    attempt,
                    request,
                    idempotency_key,
                    "describe",
                ),
            )
            description = self._description_from_descriptor(
                request.identity,
                descriptor,
                (),
            )
        else:
            description = self.describe_runtime(
                access,
                attempt,
                request.identity,
                control_root_ref=request.control_root_ref,
                idempotency_key=self._phase_key(
                    attempt,
                    request,
                    idempotency_key,
                    "describe",
                ),
            )
        self._validate_runtime_binding(request, description)
        receipts: list[RuntimeReceipt] = []
        executed: RuntimeReceipt | None = None
        current_ref: RuntimeRef | None = None
        raw_output_refs: tuple[ArtifactRef, ...] = ()
        game_output_refs: tuple[ArtifactRef, ...] = ()
        failure_reason: str | None = None
        observed_at = description.observed_at
        try:
            effective_spec = self._materialize_runtime_inputs(
                access,
                attempt,
                request,
                spec,
            )
            created = self.runtime.create(
                access,
                attempt,
                effective_spec,
                control_root_ref=request.control_root_ref,
                resource_allocation_ref=request.resource_allocation_ref,
                idempotency_key=self._phase_key(
                    attempt, request, idempotency_key, "create"
                ),
            )
            receipts.append(created)
            current_ref = created.state.runtime_ref
            started = self.runtime.start(
                access,
                attempt,
                current_ref,
                secret_values=secret_values,
                idempotency_key=self._phase_key(
                    attempt, request, idempotency_key, "start"
                ),
            )
            receipts.append(started)
            current_ref = started.state.runtime_ref
            executed = self.runtime.execute(
                access,
                attempt,
                current_ref,
                secret_values=secret_values,
                idempotency_key=self._phase_key(
                    attempt, request, idempotency_key, "execute"
                ),
            )
            receipts.append(executed)
            current_ref = executed.state.runtime_ref
            observed_at = executed.completed_at
            if executed.state.status is not RuntimeStatus.SUCCEEDED:
                failure_reason = executed.state.failure or (
                    "isolated runtime completed as "
                    f"{executed.state.status.value}"
                )
            try:
                collected = self.runtime.collect_outputs(
                    access,
                    attempt,
                    current_ref,
                    secret_values=secret_values,
                    idempotency_key=self._phase_key(
                        attempt, request, idempotency_key, "collect"
                    ),
                )
                receipts.append(collected)
                current_ref = collected.state.runtime_ref
                raw_output_refs = collected.output_artifact_refs
                observed_at = collected.completed_at
            except IsolatedRuntimeError as exc:
                collection_failure = (
                    "required runtime output was not durably collected: "
                    f"{type(exc).__name__}: {str(exc)[:1024]}"
                )
                failure_reason = (
                    collection_failure
                    if failure_reason is None
                    else f"{failure_reason}; {collection_failure}"
                )
        except (
            ArtifactError,
            FilesystemError,
            GameEngineError,
            IsolatedRuntimeError,
            ObjectStorageError,
        ) as exc:
            failure_reason = (
                "isolated runtime or evidence operation failed: "
                f"{type(exc).__name__}: {str(exc)[:1024]}"
            )
        if current_ref is not None:
            try:
                cleanup = self.runtime.cleanup(
                    access,
                    attempt,
                    current_ref,
                    idempotency_key=self._phase_key(
                        attempt, request, idempotency_key, "cleanup"
                    ),
                )
                receipts.append(cleanup)
                current_ref = cleanup.state.runtime_ref
                observed_at = cleanup.completed_at
            except IsolatedRuntimeError as exc:
                cleanup_failure = (
                    "isolated runtime cleanup failed: "
                    f"{type(exc).__name__}: {str(exc)[:1024]}"
                )
                failure_reason = (
                    cleanup_failure
                    if failure_reason is None
                    else f"{failure_reason}; {cleanup_failure}"
                )
        receipt_artifacts, tool_calls = self._receipt_evidence(receipts)
        tool_calls = tuple(
            sorted(
                {
                    item.value: item
                    for item in (*tool_calls, *description.evidence_tool_call_refs)
                }.values(),
                key=lambda item: item.value,
            )
        )
        if failure_reason is None and executed is not None:
            try:
                self._validate_outputs(
                    access,
                    request,
                    executed,
                    raw_output_refs,
                )
                self._authorize(access, attempt, request)
                game_output_refs = tuple(
                    self._output_artifact_ref(request, index)
                    for index in range(len(request.output_roles))
                )
                success_result = GameEngineOperationResult(
                    project_ref=request.project_ref,
                    operation=operation,
                    identity_digest=request.identity.semantic_digest,
                    request_sha256=request.request_sha256,
                    adapter_ref=self.adapter_ref,
                    reality=self.reality,
                    status=GameEngineStatus.SUCCEEDED,
                    node_attempt_id=attempt.attempt_id,
                    node_fence=attempt.fence,
                    runtime_ref=current_ref,
                    receipt_artifact_refs=receipt_artifacts,
                    tool_call_refs=tool_calls,
                    output_artifact_refs=game_output_refs,
                    output_roles=request.output_roles,
                    stdout_ref=executed.stdout_ref,
                    stderr_ref=executed.stderr_ref,
                    failure_reason=None,
                    runtime_observed=operation is GameEngineOperation.RUN,
                    reused_verified_build=False,
                    observed_at=observed_at,
                )
                return self._publish_outputs(
                    access,
                    attempt,
                    request,
                    executed,
                    raw_output_refs,
                    success_result,
                    idempotency_key,
                )
            except (ArtifactError, GameEngineError) as exc:
                failure_reason = (
                    "game output verification failed: "
                    f"{type(exc).__name__}: {str(exc)[:1024]}"
                )
        if failure_reason is None:
            failure_reason = "isolated runtime produced no execution receipt"
        failed_result = GameEngineOperationResult(
            project_ref=request.project_ref,
            operation=operation,
            identity_digest=request.identity.semantic_digest,
            request_sha256=request.request_sha256,
            adapter_ref=self.adapter_ref,
            reality=self.reality,
            status=GameEngineStatus.FAILED,
            node_attempt_id=attempt.attempt_id,
            node_fence=attempt.fence,
            runtime_ref=current_ref,
            receipt_artifact_refs=receipt_artifacts,
            tool_call_refs=tool_calls,
            output_artifact_refs=(),
            output_roles=(),
            stdout_ref=None if executed is None else executed.stdout_ref,
            stderr_ref=None if executed is None else executed.stderr_ref,
            failure_reason=failure_reason,
            runtime_observed=False,
            reused_verified_build=False,
            observed_at=observed_at,
        )
        self._authorize(access, attempt, request, verify_assets=False)
        return self._persist_result(
            access,
            attempt,
            failed_result,
            idempotency_key,
        )

    def describe_runtime(self, access: ProjectAccess, attempt: NodeExecutionAttempt, identity: GameProjectIdentity, *, control_root_ref: FilesystemRootRef, idempotency_key: str) -> GameEngineRuntimeDescription:
        self._authorize_runtime_description(
            access,
            attempt,
            identity,
            control_root_ref,
        )
        if identity.adapter_ref != self.adapter_ref:
            raise GameEngineIntegrityError("real adapter identity differs")
        detection = self._require_verified_detection(access, identity)
        prior = self._claim_runtime_description(
            attempt,
            identity,
            control_root_ref,
            idempotency_key,
        )
        if prior is not None:
            return prior
        descriptor = self._observe_runtime_backend(
            access,
            attempt,
            identity,
            control_root_ref,
            idempotency_key,
        )
        description = self._description_from_descriptor(
            identity,
            descriptor,
            detection.tool_call_refs,
        )
        return self._persist_runtime_description(
            access,
            attempt,
            description,
            idempotency_key,
        )

    def _observe_runtime_backend(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: GameProjectIdentity,
        control_root_ref: FilesystemRootRef,
        idempotency_key: str,
    ) -> RuntimeDescriptor:
        descriptor = self.runtime.describe_runtime(
            access,
            attempt,
            control_root_ref=control_root_ref,
            idempotency_key=idempotency_key,
        )
        if descriptor.executable_digest != identity.executable_sha256:
            raise GameEngineIntegrityError(
                "runtime adapter executable digest differs from game identity"
            )
        for tool_call_ref in descriptor.process_call_refs:
            tool_call = self.calls.get_tool_call(access, tool_call_ref)
            if tool_call.status != "SUCCEEDED":
                raise GameEngineIntegrityError(
                    "runtime description ToolCall did not succeed"
                )
        return descriptor

    def _description_from_descriptor(
        self,
        identity: GameProjectIdentity,
        descriptor: RuntimeDescriptor,
        detection_tool_calls: Sequence[ToolCallRef],
    ) -> GameEngineRuntimeDescription:
        evidence_calls = tuple(
            sorted(
                {
                    item.value: item
                    for item in (
                        *descriptor.process_call_refs,
                        *detection_tool_calls,
                    )
                }.values(),
                key=lambda item: item.value,
            )
        )
        return GameEngineRuntimeDescription(
            identity.project_ref,
            identity.semantic_digest,
            self.adapter_ref,
            self.reality,
            identity.engine_name,
            identity.engine_version,
            identity.toolchain_ref,
            identity.runtime_ref,
            identity.executable_sha256,
            identity.resource_requirements,
            descriptor.adapter_kind,
            descriptor.runtime_version,
            descriptor.implementation_id,
            descriptor.host_id,
            descriptor.cgroup_version,
            descriptor.security_features,
            descriptor.enforced_limit_kinds,
            descriptor.unsupported_limit_kinds,
            descriptor.gpu_count,
            tuple(item.value for item in descriptor.supported_network_policies),
            evidence_calls,
            descriptor.observed_at,
        )
