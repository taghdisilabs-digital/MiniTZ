"""Provider-neutral model deployment and execution adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import sqlite3
import threading
import time
from types import MappingProxyType
from typing import Protocol, cast, runtime_checkable
from uuid import uuid4

from .artifact import Artifact, ArtifactRef, ArtifactService, ContentRef
from .call_ledger import (
    CallAuthorityError,
    CallConflictError,
    CallLedgerService,
    CallUsage,
    ModelCall,
    ModelCallRef,
    ToolCallRef,
    UsageMetric,
)
from .capability import Capability, CapabilityRef, CapabilityRegistry
from .execution import NodeExecutionAttempt, NodeExecutionService
from .graph import GraphService, NodeRef
from .http_adapter import (
    HttpAdapter,
    HttpDestinationRef,
    HttpExecutionFailure,
    HttpExecutionRef,
    HttpExecutionRequest,
    HttpRedirectPolicy,
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
from .routing import (
    CapabilityImplementation,
    CapabilityImplementationRef,
    CapabilityImplementationRegistry,
    ImplementationKind,
    RoutingNotFoundError,
)
from .resource import ResourceFitRequest
from .run import ExecutionAttempt, RunRef, RunService
from .task import TaskRef, TaskRevisionService


_DEPLOYMENT_ID = re.compile(r"mdep_[0-9a-f]{32}")
_EXECUTION_ID = re.compile(r"mexec_[0-9a-f]{32}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_REF = re.compile(r"[a-z][a-z0-9+.-]{1,63}://[^\s\x00-\x1f]{1,1000}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_TOOL_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_MEDIA_JSON = "application/json"
_RESULT_MEDIA_TYPE = "application/vnd.biella.model-result+json"
_RECEIPT_MEDIA_TYPE = "application/vnd.biella.model-receipt+json"
_OPERATIONS = ("infer", "embed", "rerank")


class ModelAdapterError(Exception):
    """Base class for model adapter failures."""


class ModelContractError(ModelAdapterError, ValueError):
    """A deployment, request, or provider result is malformed."""


class ModelScopeError(ModelAdapterError):
    """A model operation crossed Project scope."""


class ModelAuthorityError(ModelAdapterError):
    """Task, Node, policy, tool, or execution authority is absent."""


class ModelConflictError(ModelAdapterError):
    """An immutable deployment or execution identity conflicts."""


class ModelNotFoundError(ModelAdapterError):
    """Required deployment or execution evidence is unavailable."""


class ModelIntegrityError(ModelAdapterError):
    """Durable model evidence failed verification."""


def _json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ModelContractError("model evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _text(value: object, name: str, maximum: int = 64 * 1024) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode()) > maximum
        or any(ord(character) < 32 and character not in "\t\n" for character in value)
    ):
        raise ModelContractError(f"{name} is malformed or unbounded")
    return value


def _timestamp(value: object, name: str) -> str:
    text = _text(value, name, 128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ModelContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ModelContractError(f"{name} must be timezone-aware")
    return text


def _ref(value: object, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise ModelContractError(f"{name} is malformed")
    return value


def _refs(values: Sequence[str], name: str, *, empty: bool = True) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ModelContractError(f"{name} must be a sequence")
    copied = tuple(values)
    if (not empty and not copied) or len(copied) > 256 or len(set(copied)) != len(copied):
        raise ModelContractError(f"{name} is empty, duplicated, or unbounded")
    for value in copied:
        _ref(value, name)
    return tuple(sorted(copied))


def _texts(values: Sequence[str], name: str, *, empty: bool = True) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ModelContractError(f"{name} must be a sequence")
    copied = tuple(values)
    if (not empty and not copied) or len(copied) > 256 or len(set(copied)) != len(copied):
        raise ModelContractError(f"{name} is empty, duplicated, or unbounded")
    for value in copied:
        _text(value, name, 1024)
    return tuple(sorted(copied))


def _mapping(values: Mapping[str, object], name: str) -> Mapping[str, object]:
    if not isinstance(values, Mapping) or len(values) > 256:
        raise ModelContractError(f"{name} is malformed or unbounded")
    copied: dict[str, object] = {}
    for key, value in values.items():
        if not isinstance(key, str) or _KEY.fullmatch(key) is None:
            raise ModelContractError(f"{name} key is malformed")
        _json(value)
        copied[key] = value
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


def _object_ref_payload(value: ContentRef | ArtifactRef | None) -> str | None:
    return None if value is None else value.value


class ModelOperation(str, Enum):
    INFER = "infer"
    EMBED = "embed"
    RERANK = "rerank"


class ModelHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class ModelExecutionFailure(str, Enum):
    AUTHORITY_DENIED = "AUTHORITY_DENIED"
    EGRESS_DENIED = "EGRESS_DENIED"
    CONTEXT_LIMIT = "CONTEXT_LIMIT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    STALE_FENCE = "STALE_FENCE"
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    STRUCTURED_OUTPUT_INVALID = "STRUCTURED_OUTPUT_INVALID"
    EMBEDDING_INVALID = "EMBEDDING_INVALID"
    RERANK_INVALID = "RERANK_INVALID"
    UNAUTHORIZED_TOOL = "UNAUTHORIZED_TOOL"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    CONTENT_INTEGRITY_FAILED = "CONTENT_INTEGRITY_FAILED"


@dataclass(frozen=True, order=True)
class ModelDeploymentRef:
    project_ref: ProjectRef
    deployment_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or _DEPLOYMENT_ID.fullmatch(self.deployment_id) is None:
            raise ModelContractError("model deployment identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> ModelDeploymentRef:
        return cls(project_ref, f"mdep_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"model-deployment://{self.project_ref.value}/{self.deployment_id}"


@dataclass(frozen=True, order=True)
class ModelExecutionRef:
    project_ref: ProjectRef
    execution_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or _EXECUTION_ID.fullmatch(self.execution_id) is None:
            raise ModelContractError("model execution identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> ModelExecutionRef:
        return cls(project_ref, f"mexec_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"model-execution://{self.project_ref.value}/{self.execution_id}"


@dataclass(frozen=True)
class ModelRuntimeIdentity:
    adapter_ref: str
    runtime_ref: str
    runtime_generation: str
    provider_ref: str
    model_ref: str
    model_revision: str | None
    model_artifact_ref: ArtifactRef | None
    resource_refs: tuple[str, ...]
    reality: str
    observed_at: str = field(default_factory=_now)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for value, name in (
            (self.adapter_ref, "runtime adapter_ref"),
            (self.runtime_ref, "runtime_ref"),
            (self.provider_ref, "runtime provider_ref"),
            (self.model_ref, "runtime model_ref"),
        ):
            _ref(value, name)
        _text(self.runtime_generation, "runtime generation", 1024)
        if self.model_revision is not None:
            _text(self.model_revision, "model revision", 1024)
        object.__setattr__(self, "resource_refs", _refs(self.resource_refs, "runtime Resource refs"))
        if self.reality not in {"REAL", "REFERENCE"}:
            raise ModelContractError("runtime reality must be REAL or REFERENCE")
        _timestamp(self.observed_at, "runtime observed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "model_artifact_ref": _object_ref_payload(self.model_artifact_ref),
            "model_ref": self.model_ref,
            "model_revision": self.model_revision,
            "observed_at": self.observed_at,
            "provider_ref": self.provider_ref,
            "reality": self.reality,
            "resource_refs": list(self.resource_refs),
            "runtime_generation": self.runtime_generation,
            "runtime_ref": self.runtime_ref,
        }


@dataclass(frozen=True)
class ModelDeployment:
    deployment_ref: ModelDeploymentRef
    adapter_ref: str
    provider_ref: str
    model_ref: str
    model_revision: str | None
    model_artifact_ref: ArtifactRef | None
    endpoint_ref: str | None
    operations: tuple[ModelOperation, ...]
    modalities: tuple[str, ...]
    maximum_context_tokens: int
    structured_output: bool
    tool_support: bool
    embedding_dimensions: int | None
    required_resource_refs: tuple[str, ...]
    data_policy_refs: tuple[str, ...]
    egress_policy_refs: tuple[str, ...]
    remote_egress: bool
    runtime_identity: ModelRuntimeIdentity
    metadata: Mapping[str, object] = field(default_factory=dict)
    created_at: str | None = None
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.deployment_ref.project_ref
        for value, name in (
            (self.adapter_ref, "deployment adapter_ref"),
            (self.provider_ref, "deployment provider_ref"),
            (self.model_ref, "deployment model_ref"),
        ):
            _ref(value, name)
        if self.model_revision is not None:
            _text(self.model_revision, "deployment model revision", 1024)
        if self.model_artifact_ref is not None and self.model_artifact_ref.project_ref != project:
            raise ModelScopeError("model Artifact crossed Project scope")
        _ref(self.endpoint_ref, "deployment endpoint_ref", optional=True)
        if not isinstance(self.operations, tuple) or not self.operations or len(set(self.operations)) != len(self.operations):
            raise ModelContractError("deployment operations are malformed")
        if not all(isinstance(item, ModelOperation) for item in self.operations):
            raise ModelContractError("deployment operation is malformed")
        object.__setattr__(self, "operations", tuple(sorted(self.operations, key=lambda item: item.value)))
        object.__setattr__(self, "modalities", _texts(self.modalities, "deployment modalities", empty=False))
        if not isinstance(self.maximum_context_tokens, int) or isinstance(self.maximum_context_tokens, bool) or self.maximum_context_tokens < 1:
            raise ModelContractError("deployment context limit is malformed")
        if not isinstance(self.structured_output, bool) or not isinstance(self.tool_support, bool):
            raise ModelContractError("deployment feature flags are malformed")
        if self.embedding_dimensions is not None and (
            not isinstance(self.embedding_dimensions, int)
            or isinstance(self.embedding_dimensions, bool)
            or self.embedding_dimensions < 1
        ):
            raise ModelContractError("embedding dimensions are malformed")
        if ModelOperation.EMBED in self.operations and self.embedding_dimensions is None:
            raise ModelContractError("embedding deployment requires exact dimensions")
        object.__setattr__(self, "required_resource_refs", _refs(self.required_resource_refs, "deployment Resource refs"))
        object.__setattr__(self, "data_policy_refs", _refs(self.data_policy_refs, "deployment data policy refs"))
        object.__setattr__(self, "egress_policy_refs", _refs(self.egress_policy_refs, "deployment egress policy refs"))
        if not isinstance(self.remote_egress, bool):
            raise ModelContractError("deployment remote_egress is malformed")
        if self.remote_egress and (self.endpoint_ref is None or not self.egress_policy_refs):
            raise ModelContractError("hosted deployment requires endpoint and egress policy")
        if self.runtime_identity.adapter_ref != self.adapter_ref or self.runtime_identity.provider_ref != self.provider_ref or self.runtime_identity.model_ref != self.model_ref:
            raise ModelIntegrityError("deployment and runtime identity differ")
        if self.runtime_identity.model_revision != self.model_revision or self.runtime_identity.model_artifact_ref != self.model_artifact_ref:
            raise ModelIntegrityError("deployment and runtime generation identity differ")
        if self.runtime_identity.resource_refs != self.required_resource_refs:
            raise ModelIntegrityError("deployment and runtime Resources differ")
        object.__setattr__(self, "metadata", _mapping(self.metadata, "deployment metadata"))
        if self.created_at is not None:
            _timestamp(self.created_at, "deployment created_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.deployment_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "created_at": self.created_at,
            "data_policy_refs": list(self.data_policy_refs),
            "deployment_ref": self.deployment_ref.value,
            "egress_policy_refs": list(self.egress_policy_refs),
            "embedding_dimensions": self.embedding_dimensions,
            "endpoint_ref": self.endpoint_ref,
            "maximum_context_tokens": self.maximum_context_tokens,
            "metadata": dict(self.metadata),
            "modalities": list(self.modalities),
            "model_artifact_ref": _object_ref_payload(self.model_artifact_ref),
            "model_ref": self.model_ref,
            "model_revision": self.model_revision,
            "operations": [item.value for item in self.operations],
            "provider_ref": self.provider_ref,
            "remote_egress": self.remote_egress,
            "required_resource_refs": list(self.required_resource_refs),
            "runtime_identity": self.runtime_identity.payload(),
            "structured_output": self.structured_output,
            "tool_support": self.tool_support,
        }


@dataclass(frozen=True)
class ModelDeploymentHealth:
    deployment_ref: ModelDeploymentRef
    status: ModelHealthStatus
    runtime_identity_sha256: str
    cause: str | None
    observed_at: str = field(default_factory=_now)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.status, ModelHealthStatus) or _SHA256.fullmatch(self.runtime_identity_sha256) is None:
            raise ModelContractError("deployment health identity is malformed")
        if self.cause is not None:
            _text(self.cause, "deployment health cause", 2048)
        _timestamp(self.observed_at, "deployment health observed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "cause": self.cause,
            "deployment_ref": self.deployment_ref.value,
            "observed_at": self.observed_at,
            "runtime_identity_sha256": self.runtime_identity_sha256,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class ModelToolDefinition:
    name: str
    capability_ref: CapabilityRef
    tool_id: str
    implementation_id: str

    def __post_init__(self) -> None:
        if _TOOL_NAME.fullmatch(self.name) is None or not isinstance(self.capability_ref, CapabilityRef):
            raise ModelContractError("model tool definition is malformed")
        _ref(self.tool_id, "model tool_id")
        _ref(self.implementation_id, "model tool implementation_id")

    def payload(self) -> dict[str, object]:
        return {
            "capability_ref": self.capability_ref.value,
            "implementation_id": self.implementation_id,
            "name": self.name,
            "tool_id": self.tool_id,
        }


@dataclass(frozen=True)
class ModelToolProposal:
    name: str
    arguments: Mapping[str, object]
    provider_call_id: str | None = None

    def __post_init__(self) -> None:
        if _TOOL_NAME.fullmatch(self.name) is None:
            raise ModelContractError("model tool proposal name is malformed")
        object.__setattr__(self, "arguments", _mapping(self.arguments, "model tool arguments"))
        if self.provider_call_id is not None:
            _text(self.provider_call_id, "provider tool call ID", 1024)

    def payload(self) -> dict[str, object]:
        return {"arguments": dict(self.arguments), "name": self.name, "provider_call_id": self.provider_call_id}


@dataclass(frozen=True)
class RerankCandidate:
    candidate_id: str
    text: str

    def __post_init__(self) -> None:
        _text(self.candidate_id, "rerank candidate ID", 1024)
        _text(self.text, "rerank candidate text", 1024 * 1024)

    def payload(self) -> dict[str, str]:
        return {"candidate_id": self.candidate_id, "text": self.text}


@dataclass(frozen=True)
class RerankEntry:
    candidate_id: str
    score: float
    rank: int

    def __post_init__(self) -> None:
        _text(self.candidate_id, "rerank entry ID", 1024)
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)) or not math.isfinite(float(self.score)):
            raise ModelContractError("rerank score must be finite")
        if not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank < 1:
            raise ModelContractError("rerank rank is malformed")

    def payload(self) -> dict[str, object]:
        return {"candidate_id": self.candidate_id, "rank": self.rank, "score": float(self.score)}


@dataclass(frozen=True)
class ModelExecutionBinding:
    project_ref: ProjectRef
    execution_ref: ModelExecutionRef
    deployment_ref: ModelDeploymentRef
    capability_ref: CapabilityRef
    task_ref: TaskRef
    task_digest: str
    run_ref: RunRef
    node_ref: NodeRef
    node_attempt_id: str
    node_fence: int
    input_refs: tuple[ContentRef | ArtifactRef, ...]
    context_receipt_ref: ContentRef | ArtifactRef | None
    data_policy_ref: str | None
    egress_policy_ref: str | None
    context_tokens: int
    timeout_seconds: float
    binding_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise ModelContractError("model binding requires exact ProjectRef")
        refs = (
            self.execution_ref.project_ref,
            self.deployment_ref.project_ref,
            self.task_ref.project_ref,
            self.run_ref.project_ref,
            self.node_ref.project_ref,
        )
        if any(item != self.project_ref for item in refs):
            raise ModelScopeError("model binding crossed Project scope")
        if not isinstance(self.capability_ref, CapabilityRef) or _SHA256.fullmatch(self.task_digest) is None:
            raise ModelContractError("model Capability or Task digest is malformed")
        _text(self.node_attempt_id, "model Node attempt ID", 256)
        if not isinstance(self.node_fence, int) or isinstance(self.node_fence, bool) or self.node_fence < 1:
            raise ModelContractError("model Node fence is malformed")
        if not isinstance(self.input_refs, tuple) or len(self.input_refs) > 1024:
            raise ModelContractError("model input refs are malformed or unbounded")
        for value in self.input_refs:
            if not isinstance(value, (ContentRef, ArtifactRef)) or (isinstance(value, ArtifactRef) and value.project_ref != self.project_ref):
                raise ModelScopeError("model input ref crossed Project scope or is malformed")
        if self.context_receipt_ref is not None and (
            not isinstance(self.context_receipt_ref, (ContentRef, ArtifactRef))
            or (isinstance(self.context_receipt_ref, ArtifactRef) and self.context_receipt_ref.project_ref != self.project_ref)
        ):
            raise ModelScopeError("model ContextReceipt crossed Project scope")
        _ref(self.data_policy_ref, "model data policy ref", optional=True)
        _ref(self.egress_policy_ref, "model egress policy ref", optional=True)
        if not isinstance(self.context_tokens, int) or isinstance(self.context_tokens, bool) or self.context_tokens < 0:
            raise ModelContractError("model context token count is malformed")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or not 0 < float(self.timeout_seconds) <= 86_400:
            raise ModelContractError("model timeout is malformed")
        object.__setattr__(self, "binding_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "capability_ref": self.capability_ref.value,
            "context_receipt_ref": _object_ref_payload(self.context_receipt_ref),
            "context_tokens": self.context_tokens,
            "data_policy_ref": self.data_policy_ref,
            "deployment_ref": self.deployment_ref.value,
            "egress_policy_ref": self.egress_policy_ref,
            "execution_ref": self.execution_ref.value,
            "input_refs": [item.value for item in self.input_refs],
            "node_attempt_id": self.node_attempt_id,
            "node_fence": self.node_fence,
            "node_ref": self.node_ref.value,
            "project_ref": self.project_ref.value,
            "run_ref": f"run://{self.project_ref.value}/{self.run_ref.run_id}",
            "task_digest": self.task_digest,
            "task_ref": f"task://{self.project_ref.value}/{self.task_ref.task_id}/{self.task_ref.revision}",
            "timeout_seconds": float(self.timeout_seconds),
        }


@dataclass(frozen=True)
class InferRequest:
    binding: ModelExecutionBinding
    messages_ref: ContentRef
    generation_parameters: Mapping[str, object] = field(default_factory=dict)
    output_schema_ref: ContentRef | None = None
    tools: tuple[ModelToolDefinition, ...] = ()
    request_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ModelExecutionBinding) or not isinstance(self.messages_ref, ContentRef):
            raise ModelContractError("infer request binding or messages ref is malformed")
        if self.messages_ref not in self.binding.input_refs:
            raise ModelIntegrityError("infer messages ref is absent from bound inputs")
        object.__setattr__(self, "generation_parameters", _mapping(self.generation_parameters, "generation parameters"))
        if self.output_schema_ref is not None and self.output_schema_ref not in self.binding.input_refs:
            raise ModelIntegrityError("structured output schema is absent from bound inputs")
        if not isinstance(self.tools, tuple) or len(self.tools) > 128 or len({item.name for item in self.tools}) != len(self.tools):
            raise ModelContractError("model tools are duplicated or unbounded")
        if not all(isinstance(item, ModelToolDefinition) for item in self.tools):
            raise ModelContractError("model tool definition is malformed")
        object.__setattr__(self, "request_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "binding": self.binding.payload(),
            "generation_parameters": dict(self.generation_parameters),
            "messages_ref": _content_payload(self.messages_ref),
            "operation": ModelOperation.INFER.value,
            "output_schema_ref": _content_payload(self.output_schema_ref),
            "tools": [item.payload() for item in self.tools],
        }


@dataclass(frozen=True)
class EmbedRequest:
    binding: ModelExecutionBinding
    inputs_ref: ContentRef
    request_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ModelExecutionBinding) or not isinstance(self.inputs_ref, ContentRef):
            raise ModelContractError("embed request is malformed")
        if self.inputs_ref not in self.binding.input_refs:
            raise ModelIntegrityError("embedding inputs ref is absent from bound inputs")
        object.__setattr__(self, "request_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"binding": self.binding.payload(), "inputs_ref": _content_payload(self.inputs_ref), "operation": ModelOperation.EMBED.value}


@dataclass(frozen=True)
class RerankRequest:
    binding: ModelExecutionBinding
    query_ref: ContentRef
    candidates_ref: ContentRef
    request_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ModelExecutionBinding) or not isinstance(self.query_ref, ContentRef) or not isinstance(self.candidates_ref, ContentRef):
            raise ModelContractError("rerank request is malformed")
        if self.query_ref not in self.binding.input_refs or self.candidates_ref not in self.binding.input_refs:
            raise ModelIntegrityError("rerank inputs are absent from bound inputs")
        object.__setattr__(self, "request_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "binding": self.binding.payload(),
            "candidates_ref": _content_payload(self.candidates_ref),
            "operation": ModelOperation.RERANK.value,
            "query_ref": _content_payload(self.query_ref),
        }


@dataclass(frozen=True)
class ModelResultEvidence:
    execution_ref: ModelExecutionRef
    deployment_ref: ModelDeploymentRef
    model_call_ref: ModelCallRef
    output_ref: ContentRef | None
    output_artifact_ref: ArtifactRef | None
    receipt_artifact_ref: ArtifactRef
    runtime_identity: ModelRuntimeIdentity
    usage: CallUsage | None
    finish_reason: str | None
    provider_trace_id: str | None
    failure: ModelExecutionFailure | None
    tool_call_refs: tuple[ToolCallRef, ...]
    latency_ms: float
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.execution_ref.project_ref
        refs = (self.deployment_ref.project_ref, self.model_call_ref.project_ref, self.receipt_artifact_ref.project_ref)
        if any(item != project for item in refs) or (self.output_artifact_ref is not None and self.output_artifact_ref.project_ref != project):
            raise ModelScopeError("model result evidence crossed Project scope")
        if (self.output_ref is None) != (self.output_artifact_ref is None):
            raise ModelIntegrityError("model output ContentRef and Artifact differ")
        if self.finish_reason is not None:
            _text(self.finish_reason, "model finish reason", 1024)
        if self.provider_trace_id is not None:
            _text(self.provider_trace_id, "model provider trace ID", 1024)
        if self.failure is not None and not isinstance(self.failure, ModelExecutionFailure):
            raise ModelContractError("model failure classification is malformed")
        if self.failure is None and self.output_ref is None:
            raise ModelIntegrityError("successful model result lacks output")
        if not isinstance(self.tool_call_refs, tuple) or any(item.project_ref != project for item in self.tool_call_refs):
            raise ModelScopeError("model ToolCall evidence crossed Project scope")
        if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, (int, float)) or not math.isfinite(float(self.latency_ms)) or self.latency_ms < 0:
            raise ModelContractError("model latency is malformed")
        _timestamp(self.completed_at, "model completed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def succeeded(self) -> bool:
        return self.failure is None

    def payload(self) -> dict[str, object]:
        return {
            "completed_at": self.completed_at,
            "deployment_ref": self.deployment_ref.value,
            "execution_ref": self.execution_ref.value,
            "failure": None if self.failure is None else self.failure.value,
            "finish_reason": self.finish_reason,
            "latency_ms": float(self.latency_ms),
            "model_call_ref": self.model_call_ref.value,
            "output_artifact_ref": _object_ref_payload(self.output_artifact_ref),
            "output_ref": _content_payload(self.output_ref),
            "provider_trace_id": self.provider_trace_id,
            "receipt_artifact_ref": self.receipt_artifact_ref.value,
            "runtime_identity": self.runtime_identity.payload(),
            "tool_call_refs": [item.value for item in self.tool_call_refs],
            "usage": None if self.usage is None else self.usage.payload(),
        }


@dataclass(frozen=True)
class InferResult:
    evidence: ModelResultEvidence
    text: str | None
    structured_value: object | None

    def __post_init__(self) -> None:
        if self.evidence.succeeded and self.text is None:
            raise ModelIntegrityError("successful inference lacks text")
        if self.text is not None:
            _text(self.text, "inference text", 64 * 1024 * 1024)
        _json(self.structured_value)


@dataclass(frozen=True)
class EmbedResult:
    evidence: ModelResultEvidence
    vectors: tuple[tuple[float, ...], ...]
    source_digest: str

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.source_digest) is None:
            raise ModelContractError("embedding source digest is malformed")
        if self.evidence.succeeded and not self.vectors:
            raise ModelIntegrityError("successful embedding result is empty")


@dataclass(frozen=True)
class RerankResult:
    evidence: ModelResultEvidence
    entries: tuple[RerankEntry, ...]
    source_digest: str

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.source_digest) is None:
            raise ModelContractError("rerank source digest is malformed")
        if self.evidence.succeeded and not self.entries:
            raise ModelIntegrityError("successful rerank result is empty")


@dataclass(frozen=True)
class ModelCancellationReceipt:
    execution_ref: ModelExecutionRef
    accepted: bool
    idempotency_key: str
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool) or _KEY.fullmatch(self.idempotency_key) is None:
            raise ModelContractError("model cancellation receipt is malformed")
        _timestamp(self.observed_at, "model cancellation observed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "execution_ref": self.execution_ref.value,
            "idempotency_key": self.idempotency_key,
            "observed_at": self.observed_at,
        }


@runtime_checkable
class ModelToolExecutor(Protocol):
    def execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        definition: ModelToolDefinition,
        arguments_ref: ContentRef,
    ) -> Sequence[ContentRef | ArtifactRef]: ...


@runtime_checkable
class ModelAdapter(Protocol):
    def infer(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: InferRequest, *, credentials: Mapping[str, str], idempotency_key: str) -> InferResult: ...

    def embed(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: EmbedRequest, *, credentials: Mapping[str, str], idempotency_key: str) -> EmbedResult: ...

    def rerank(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: RerankRequest, *, credentials: Mapping[str, str], idempotency_key: str) -> RerankResult: ...

    def health(self, access: ProjectAccess, deployment_ref: ModelDeploymentRef) -> ModelDeploymentHealth: ...

    def cancel(self, access: ProjectAccess, attempt: NodeExecutionAttempt, execution_ref: ModelExecutionRef, *, idempotency_key: str) -> ModelCancellationReceipt: ...

    def describe_runtime(self, access: ProjectAccess, deployment_ref: ModelDeploymentRef) -> ModelRuntimeIdentity: ...


@dataclass(frozen=True)
class HostedModelRoute:
    deployment_ref: ModelDeploymentRef
    destination_ref: HttpDestinationRef
    path: str

    def __post_init__(self) -> None:
        if self.destination_ref.project_ref != self.deployment_ref.project_ref or not self.path.startswith("/") or "?" in self.path or "#" in self.path:
            raise ModelContractError("hosted model route is malformed or crossed Project scope")


@dataclass
class _ActiveExecution:
    cancellation: threading.Event
    http_execution_ref: HttpExecutionRef | None = None


@dataclass(frozen=True)
class _ProviderResult:
    operation: ModelOperation
    value: object | None
    finish_reason: str | None
    usage: CallUsage | None
    provider_trace_id: str | None
    tool_proposals: tuple[ModelToolProposal, ...] = ()


class _ProviderFailure(Exception):
    def __init__(self, failure: ModelExecutionFailure, finish_reason: str | None = None) -> None:
        super().__init__(failure.value)
        self.failure = failure
        self.finish_reason = finish_reason


def _artifact_ref(value: object, project_ref: ProjectRef) -> ArtifactRef | None:
    if value is None:
        return None
    prefix = f"artifact://{project_ref.value}/"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ModelIntegrityError("persisted ArtifactRef is malformed or crossed Project scope")
    try:
        artifact_id, revision = value.removeprefix(prefix).rsplit("/", 1)
        return ArtifactRef(project_ref, artifact_id, int(revision))
    except (TypeError, ValueError) as exc:
        raise ModelIntegrityError("persisted ArtifactRef is malformed") from exc


def _content_ref(value: object) -> ContentRef | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ModelIntegrityError("persisted ContentRef is malformed")
    try:
        return ContentRef(
            cast(str, value["algorithm"]),
            cast(str, value["digest"]),
            cast(int, value["size_bytes"]),
            cast(str, value["media_type"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ModelIntegrityError("persisted ContentRef is malformed") from exc


def _runtime_from_payload(value: object, project_ref: ProjectRef) -> ModelRuntimeIdentity:
    if not isinstance(value, dict):
        raise ModelIntegrityError("persisted model runtime identity is malformed")
    try:
        return ModelRuntimeIdentity(
            cast(str, value["adapter_ref"]),
            cast(str, value["runtime_ref"]),
            cast(str, value["runtime_generation"]),
            cast(str, value["provider_ref"]),
            cast(str, value["model_ref"]),
            cast(str | None, value["model_revision"]),
            _artifact_ref(value["model_artifact_ref"], project_ref),
            tuple(cast(list[str], value["resource_refs"])),
            cast(str, value["reality"]),
            cast(str, value["observed_at"]),
        )
    except (KeyError, TypeError, ValueError, ModelAdapterError) as exc:
        if isinstance(exc, ModelIntegrityError):
            raise
        raise ModelIntegrityError("persisted model runtime identity is malformed") from exc


def _usage_from_payload(value: object) -> CallUsage | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ModelIntegrityError("persisted model usage is malformed")

    def metric(name: str) -> UsageMetric:
        item = value.get(name)
        if not isinstance(item, dict):
            raise ModelIntegrityError("persisted model usage metric is malformed")
        return UsageMetric(cast(int | None, item.get("value")), cast(str | None, item.get("source")))

    try:
        return CallUsage(
            metric("input_tokens"),
            metric("output_tokens"),
            metric("reasoning_tokens"),
            metric("cached_input_tokens"),
            metric("cache_write_tokens"),
        )
    except (TypeError, ValueError) as exc:
        raise ModelIntegrityError("persisted model usage is malformed") from exc


def _schema_validate(value: object, schema: object, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise ModelContractError("structured output schema must be an object")
    supported = {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
        "minLength",
        "maxLength",
    }
    unknown = set(schema).difference(supported)
    if unknown:
        raise ModelContractError("structured output schema contains unsupported keywords")
    if "enum" in schema:
        enum = schema["enum"]
        if not isinstance(enum, list) or value not in enum:
            raise ModelContractError(f"structured output {path} is outside enum")
    kind = schema.get("type")
    valid = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if not isinstance(kind, str) or kind not in valid or not valid[kind]:
        raise ModelContractError(f"structured output {path} has wrong type")
    if kind == "object":
        assert isinstance(value, dict)
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional = schema.get("additionalProperties", True)
        if not isinstance(properties, dict) or not isinstance(required, list) or not all(isinstance(item, str) for item in required) or not isinstance(additional, bool):
            raise ModelContractError("structured output object schema is malformed")
        missing = set(required).difference(value)
        if missing:
            raise ModelContractError(f"structured output {path} lacks required properties")
        if not additional and set(value).difference(properties):
            raise ModelContractError(f"structured output {path} has additional properties")
        for key, item in value.items():
            if key in properties:
                _schema_validate(item, properties[key], f"{path}.{key}")
    elif kind == "array":
        assert isinstance(value, list)
        minimum = schema.get("minItems", 0)
        maximum = schema.get("maxItems", 2**31 - 1)
        if not isinstance(minimum, int) or not isinstance(maximum, int) or not minimum <= len(value) <= maximum:
            raise ModelContractError(f"structured output {path} array bounds failed")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                _schema_validate(item, item_schema, f"{path}[{index}]")
    elif kind == "string":
        assert isinstance(value, str)
        minimum = schema.get("minLength", 0)
        maximum = schema.get("maxLength", 2**31 - 1)
        if not isinstance(minimum, int) or not isinstance(maximum, int) or not minimum <= len(value) <= maximum:
            raise ModelContractError(f"structured output {path} string bounds failed")
    elif kind in {"number", "integer"}:
        assert isinstance(value, (int, float)) and not isinstance(value, bool)
        minimum = schema.get("minimum", -math.inf)
        maximum = schema.get("maximum", math.inf)
        if isinstance(minimum, bool) or isinstance(maximum, bool) or not isinstance(minimum, (int, float)) or not isinstance(maximum, (int, float)) or not float(minimum) <= float(value) <= float(maximum):
            raise ModelContractError(f"structured output {path} numeric bounds failed")


class _BaseModelAdapter:
    adapter_ref: str
    reality: str

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        adapter_ref: str,
        reality: str,
        tool_executor: ModelToolExecutor | None = None,
    ) -> None:
        self.database_path = Path(database_path).resolve()
        self.object_store = object_store
        self.adapter_ref = cast(str, _ref(adapter_ref, "model adapter_ref"))
        if reality not in {"REAL", "REFERENCE"}:
            raise ModelContractError("model adapter reality is malformed")
        self.reality = reality
        self.tool_executor = tool_executor
        self.projects = ProjectStore(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.runs = RunService(self.database_path)
        self.graphs = GraphService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.capabilities = CapabilityRegistry(self.database_path)
        self.implementations = CapabilityImplementationRegistry(self.database_path)
        self.calls = CallLedgerService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self._active: dict[str, _ActiveExecution] = {}
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
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
                CREATE TABLE IF NOT EXISTS model_deployments (
                    project_id TEXT NOT NULL, deployment_id TEXT NOT NULL,
                    deployment_json TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,deployment_id),
                    UNIQUE(project_id,deployment_id,record_sha256),
                    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS model_deployment_claims (
                    project_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                    deployment_id TEXT NOT NULL, semantic_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,idempotency_key),
                    UNIQUE(project_id,deployment_id),
                    FOREIGN KEY(project_id,deployment_id) REFERENCES model_deployments(project_id,deployment_id) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS model_health_observations (
                    project_id TEXT NOT NULL, deployment_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    observation_json TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,deployment_id,sequence),
                    UNIQUE(project_id,deployment_id,sequence,record_sha256),
                    FOREIGN KEY(project_id,deployment_id) REFERENCES model_deployments(project_id,deployment_id) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS model_health_heads (
                    project_id TEXT NOT NULL, deployment_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,deployment_id),
                    FOREIGN KEY(project_id,deployment_id,sequence,record_sha256)
                      REFERENCES model_health_observations(project_id,deployment_id,sequence,record_sha256) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS model_execution_claims (
                    project_id TEXT NOT NULL, execution_id TEXT NOT NULL,
                    adapter_ref TEXT NOT NULL, operation TEXT NOT NULL, request_sha256 TEXT NOT NULL,
                    node_attempt_id TEXT NOT NULL, node_fence INTEGER NOT NULL,
                    model_call_id TEXT NOT NULL, request_json TEXT NOT NULL,
                    PRIMARY KEY(project_id,execution_id),
                    UNIQUE(project_id,model_call_id),
                    FOREIGN KEY(project_id,model_call_id) REFERENCES calls(project_id,call_id) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS model_execution_results (
                    project_id TEXT NOT NULL, execution_id TEXT NOT NULL,
                    operation TEXT NOT NULL, result_json TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,execution_id),
                    UNIQUE(project_id,execution_id,record_sha256),
                    FOREIGN KEY(project_id,execution_id) REFERENCES model_execution_claims(project_id,execution_id) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS model_cancellations (
                    project_id TEXT NOT NULL, execution_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                    receipt_json TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY(project_id,execution_id,idempotency_key),
                    FOREIGN KEY(project_id,execution_id) REFERENCES model_execution_claims(project_id,execution_id) ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS model_deployments_no_update BEFORE UPDATE ON model_deployments BEGIN SELECT RAISE(ABORT,'ModelDeployment is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS model_deployments_no_delete BEFORE DELETE ON model_deployments BEGIN SELECT RAISE(ABORT,'ModelDeployment cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS model_deployment_claims_no_update BEFORE UPDATE ON model_deployment_claims BEGIN SELECT RAISE(ABORT,'ModelDeployment claim is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS model_deployment_claims_no_delete BEFORE DELETE ON model_deployment_claims BEGIN SELECT RAISE(ABORT,'ModelDeployment claim cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS model_health_observations_no_update BEFORE UPDATE ON model_health_observations BEGIN SELECT RAISE(ABORT,'Model health history is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS model_health_observations_no_delete BEFORE DELETE ON model_health_observations BEGIN SELECT RAISE(ABORT,'Model health history cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS model_health_heads_no_delete BEFORE DELETE ON model_health_heads BEGIN SELECT RAISE(ABORT,'Model health head cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS model_health_heads_monotonic BEFORE UPDATE ON model_health_heads
                  WHEN NEW.project_id != OLD.project_id OR NEW.deployment_id != OLD.deployment_id OR NEW.sequence != OLD.sequence + 1
                  BEGIN SELECT RAISE(ABORT,'Model health head must advance by one'); END;
                CREATE TRIGGER IF NOT EXISTS model_execution_claims_no_update BEFORE UPDATE ON model_execution_claims BEGIN SELECT RAISE(ABORT,'Model execution claim is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS model_execution_claims_no_delete BEFORE DELETE ON model_execution_claims BEGIN SELECT RAISE(ABORT,'Model execution claim cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS model_execution_results_no_update BEFORE UPDATE ON model_execution_results BEGIN SELECT RAISE(ABORT,'Model execution result is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS model_execution_results_no_delete BEFORE DELETE ON model_execution_results BEGIN SELECT RAISE(ABORT,'Model execution result cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS model_cancellations_no_update BEFORE UPDATE ON model_cancellations BEGIN SELECT RAISE(ABORT,'Model cancellation is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS model_cancellations_no_delete BEFORE DELETE ON model_cancellations BEGIN SELECT RAISE(ABORT,'Model cancellation cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectIntegrityError as exc:
            raise ModelIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise ModelScopeError("model Project scope mismatch") from exc

    @staticmethod
    def capability_ref(operation: ModelOperation) -> CapabilityRef:
        if operation is ModelOperation.INFER:
            return CapabilityRef("model.infer", "1.0.0")
        if operation is ModelOperation.EMBED:
            return CapabilityRef("retrieval.embed", "1.0.0")
        if operation is ModelOperation.RERANK:
            return CapabilityRef("retrieval.rerank", "1.0.0")
        raise ModelContractError("model operation is unsupported")

    def _implementation_ref(self, project_ref: ProjectRef, deployment: ModelDeployment, operation: ModelOperation) -> CapabilityImplementationRef:
        identity = hashlib.sha256(f"{project_ref.value}\0{self.adapter_ref}\0{deployment.deployment_ref.value}\0{operation.value}".encode()).hexdigest()[:32]
        return CapabilityImplementationRef(project_ref, f"cimpl_{identity}")

    def register_capabilities(self, access: ProjectAccess, deployment: ModelDeployment) -> Mapping[CapabilityRef, CapabilityImplementation]:
        self._authorize(access, deployment.project_ref)
        if deployment.adapter_ref != self.adapter_ref:
            raise ModelAuthorityError("deployment belongs to another adapter")
        registered: dict[CapabilityRef, CapabilityImplementation] = {}
        for operation in deployment.operations:
            capability_ref = self.capability_ref(operation)
            capability = self.capabilities.register(
                Capability(
                    capability_ref,
                    f"Provider-neutral model {operation.value}",
                    input_contract={"request": f"schema://biella/model-{operation.value}-request/1"},
                    output_contract={"result": f"schema://biella/model-{operation.value}-result/1"},
                    side_effects=(),
                )
            )
            implementation_ref = self._implementation_ref(access.project_ref, deployment, operation)
            try:
                implementation = self.implementations.get(access, implementation_ref)
            except RoutingNotFoundError:
                implementation = self.implementations.register(
                    access,
                    CapabilityImplementation(
                        implementation_ref,
                        capability.capability_ref,
                        "1.0.0",
                        ImplementationKind.MODEL,
                        deployment.adapter_ref,
                        deployment.runtime_identity.runtime_ref,
                        provider_ref=deployment.provider_ref,
                        model_ref=deployment.model_ref,
                        features=tuple(
                            item
                            for item, enabled in (
                                ("structured-output", deployment.structured_output),
                                ("tool-calling", deployment.tool_support),
                                ("exact-runtime-identity", True),
                                ("model-call-ledger", True),
                            )
                            if enabled
                        ),
                        input_features=("content-ref", "context-receipt", "exact-deployment"),
                        output_features=("artifact", "content-ref", "model-call", "runtime-identity"),
                        side_effect_authority="EXTERNAL_WRITE" if deployment.remote_egress else "READ_ONLY",
                        supported_data_policy_refs=deployment.data_policy_refs,
                        remote_egress=deployment.remote_egress,
                        supported_egress_policy_refs=deployment.egress_policy_refs,
                        maximum_context_tokens=deployment.maximum_context_tokens,
                        maximum_tool_count=128 if deployment.tool_support else 0,
                        resource_kinds=("managed.model",) if deployment.remote_egress else ("cpu.reference",),
                        resource_fit=ResourceFitRequest(),
                        metadata={
                            "adapter_reality": self.reality.lower(),
                            "deployment_ref": deployment.deployment_ref.value,
                        },
                    ),
                    idempotency_key=f"model-{operation.value}-{deployment.deployment_ref.deployment_id[:16]}",
                )
            registered[capability_ref] = implementation
        return MappingProxyType(registered)

    def register_deployment(self, access: ProjectAccess, deployment: ModelDeployment, *, idempotency_key: str) -> ModelDeployment:
        if _KEY.fullmatch(idempotency_key) is None:
            raise ModelContractError("model deployment idempotency key is malformed")
        self._authorize(access, deployment.project_ref)
        if deployment.adapter_ref != self.adapter_ref or deployment.runtime_identity.reality != self.reality:
            raise ModelAuthorityError("model deployment adapter identity is not owned here")
        value = deployment if deployment.created_at is not None else replace(deployment, created_at=_now())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM model_deployment_claims WHERE project_id=? AND idempotency_key=?",
                (access.project_ref.value, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior["deployment_id"] != value.deployment_ref.deployment_id or not hmac.compare_digest(cast(str, prior["semantic_sha256"]), value.record_sha256):
                    raise ModelConflictError("model deployment idempotency conflicts")
                connection.commit()
                return self.get_deployment(access, value.deployment_ref)
            connection.execute(
                "INSERT INTO model_deployments VALUES (?,?,?,?)",
                (access.project_ref.value, value.deployment_ref.deployment_id, _json(value.payload()), value.record_sha256),
            )
            connection.execute(
                "INSERT INTO model_deployment_claims VALUES (?,?,?,?)",
                (access.project_ref.value, idempotency_key, value.deployment_ref.deployment_id, value.record_sha256),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ModelConflictError("model deployment identity conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        self.register_capabilities(access, value)
        self.record_health(
            access,
            ModelDeploymentHealth(value.deployment_ref, ModelHealthStatus.UNKNOWN, value.runtime_identity.record_sha256, "not yet observed"),
        )
        return value

    def _deployment_from_payload(self, payload: object, project_ref: ProjectRef) -> ModelDeployment:
        if not isinstance(payload, dict):
            raise ModelIntegrityError("persisted ModelDeployment is malformed")
        try:
            prefix = f"model-deployment://{project_ref.value}/"
            value = cast(str, payload["deployment_ref"])
            if not value.startswith(prefix):
                raise ModelScopeError("persisted ModelDeployment crossed Project scope")
            return ModelDeployment(
                ModelDeploymentRef(project_ref, value.removeprefix(prefix)),
                cast(str, payload["adapter_ref"]),
                cast(str, payload["provider_ref"]),
                cast(str, payload["model_ref"]),
                cast(str | None, payload["model_revision"]),
                _artifact_ref(payload["model_artifact_ref"], project_ref),
                cast(str | None, payload["endpoint_ref"]),
                tuple(ModelOperation(item) for item in cast(list[str], payload["operations"])),
                tuple(cast(list[str], payload["modalities"])),
                cast(int, payload["maximum_context_tokens"]),
                cast(bool, payload["structured_output"]),
                cast(bool, payload["tool_support"]),
                cast(int | None, payload["embedding_dimensions"]),
                tuple(cast(list[str], payload["required_resource_refs"])),
                tuple(cast(list[str], payload["data_policy_refs"])),
                tuple(cast(list[str], payload["egress_policy_refs"])),
                cast(bool, payload["remote_egress"]),
                _runtime_from_payload(payload["runtime_identity"], project_ref),
                cast(dict[str, object], payload["metadata"]),
                cast(str, payload["created_at"]),
            )
        except (KeyError, TypeError, ValueError, ModelAdapterError) as exc:
            if isinstance(exc, (ModelIntegrityError, ModelScopeError)):
                raise
            raise ModelIntegrityError("persisted ModelDeployment is malformed") from exc

    def get_deployment(self, access: ProjectAccess, deployment_ref: ModelDeploymentRef) -> ModelDeployment:
        self._authorize(access, deployment_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM model_deployments WHERE project_id=? AND deployment_id=?",
                (access.project_ref.value, deployment_ref.deployment_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ModelNotFoundError("ModelDeployment is unavailable")
        try:
            value = self._deployment_from_payload(json.loads(cast(str, row["deployment_json"])), access.project_ref)
        except json.JSONDecodeError as exc:
            raise ModelIntegrityError("ModelDeployment JSON is malformed") from exc
        if value.deployment_ref != deployment_ref or not hmac.compare_digest(value.record_sha256, cast(str, row["record_sha256"])):
            raise ModelIntegrityError("ModelDeployment evidence changed")
        return value

    def record_health(self, access: ProjectAccess, observation: ModelDeploymentHealth) -> ModelDeploymentHealth:
        self._authorize(access, observation.deployment_ref.project_ref)
        deployment = self.get_deployment(access, observation.deployment_ref)
        if observation.runtime_identity_sha256 != deployment.runtime_identity.record_sha256:
            raise ModelIntegrityError("model health observed another runtime identity")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            head = connection.execute(
                "SELECT sequence FROM model_health_heads WHERE project_id=? AND deployment_id=?",
                (access.project_ref.value, observation.deployment_ref.deployment_id),
            ).fetchone()
            sequence = 1 if head is None else cast(int, head["sequence"]) + 1
            connection.execute(
                "INSERT INTO model_health_observations VALUES (?,?,?,?,?)",
                (access.project_ref.value, observation.deployment_ref.deployment_id, sequence, _json(observation.payload()), observation.record_sha256),
            )
            if head is None:
                connection.execute(
                    "INSERT INTO model_health_heads VALUES (?,?,?,?)",
                    (access.project_ref.value, observation.deployment_ref.deployment_id, sequence, observation.record_sha256),
                )
            else:
                connection.execute(
                    "UPDATE model_health_heads SET sequence=?,record_sha256=? WHERE project_id=? AND deployment_id=?",
                    (sequence, observation.record_sha256, access.project_ref.value, observation.deployment_ref.deployment_id),
                )
            connection.commit()
            return observation
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def health(self, access: ProjectAccess, deployment_ref: ModelDeploymentRef) -> ModelDeploymentHealth:
        deployment = self.get_deployment(access, deployment_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT observation_json,record_sha256 FROM model_health_observations WHERE project_id=? AND deployment_id=? ORDER BY sequence DESC LIMIT 1",
                (access.project_ref.value, deployment_ref.deployment_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ModelNotFoundError("model health is unavailable")
        try:
            payload = json.loads(cast(str, row["observation_json"]))
            value = ModelDeploymentHealth(
                deployment_ref,
                ModelHealthStatus(cast(str, payload["status"])),
                cast(str, payload["runtime_identity_sha256"]),
                cast(str | None, payload["cause"]),
                cast(str, payload["observed_at"]),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, ModelAdapterError) as exc:
            raise ModelIntegrityError("model health evidence is malformed") from exc
        if value.runtime_identity_sha256 != deployment.runtime_identity.record_sha256 or not hmac.compare_digest(value.record_sha256, cast(str, row["record_sha256"])):
            raise ModelIntegrityError("model health evidence changed")
        return value

    def describe_runtime(self, access: ProjectAccess, deployment_ref: ModelDeploymentRef) -> ModelRuntimeIdentity:
        return self.get_deployment(access, deployment_ref).runtime_identity

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
            raise ModelAuthorityError("exact Run execution authority is unavailable")
        return result

    def _require_live_node(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> None:
        execution = self.executions.get_node_execution(access, attempt.node_ref)
        if (
            execution.status not in {"RUNNING", "WAITING_EXTERNAL"}
            or execution.current_attempt_id != attempt.attempt_id
            or execution.current_fence != attempt.fence
            or execution.current_run_attempt_id != attempt.run_attempt_id
            or execution.current_run_fence != attempt.run_fence
        ):
            raise ModelAuthorityError("late or stale model Node authority was rejected")

    def _validate_binding(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        binding: ModelExecutionBinding,
        deployment: ModelDeployment,
        operation: ModelOperation,
    ) -> None:
        self._authorize(access, binding.project_ref)
        if (
            binding.task_ref != attempt.task_ref
            or binding.task_digest != attempt.task_digest
            or binding.run_ref != attempt.run_ref
            or binding.node_ref != attempt.node_ref
            or binding.node_attempt_id != attempt.attempt_id
            or binding.node_fence != attempt.fence
        ):
            raise ModelAuthorityError("model request and Node attempt differ")
        if binding.deployment_ref != deployment.deployment_ref or deployment.adapter_ref != self.adapter_ref:
            raise ModelAuthorityError("model deployment is not owned by this adapter")
        if operation not in deployment.operations or binding.capability_ref != self.capability_ref(operation):
            raise ModelAuthorityError("model operation or Capability is unsupported")
        task = self.tasks.get_task(access, binding.task_ref)
        if task.canonical_digest != binding.task_digest or binding.capability_ref not in task.required_capabilities:
            raise ModelAuthorityError("model Task authority is absent")
        if binding.data_policy_ref != task.data_policy_ref or binding.egress_policy_ref != task.egress_policy_ref:
            raise ModelAuthorityError("model request policy differs from exact Task")
        if binding.data_policy_ref is not None and binding.data_policy_ref not in deployment.data_policy_refs:
            raise _ProviderFailure(ModelExecutionFailure.EGRESS_DENIED, "data_policy_denied")
        if deployment.remote_egress and (
            binding.egress_policy_ref is None or binding.egress_policy_ref not in deployment.egress_policy_refs
        ):
            raise _ProviderFailure(ModelExecutionFailure.EGRESS_DENIED, "egress_policy_denied")
        if binding.context_tokens > deployment.maximum_context_tokens:
            raise _ProviderFailure(ModelExecutionFailure.CONTEXT_LIMIT, "context_limit")
        self._run_attempt(access, attempt)
        self._require_live_node(access, attempt)
        for item in binding.input_refs:
            if isinstance(item, ContentRef):
                self.object_store.verify(item)
            else:
                artifact = self.artifacts.get_artifact(access, item)
                if artifact.content_ref is not None:
                    self.object_store.verify(artifact.content_ref)
        if binding.context_receipt_ref is not None:
            if isinstance(binding.context_receipt_ref, ContentRef):
                self.object_store.verify(binding.context_receipt_ref)
            else:
                self.artifacts.get_artifact(access, binding.context_receipt_ref)

    @staticmethod
    def _request_parts(request: InferRequest | EmbedRequest | RerankRequest) -> tuple[ModelExecutionBinding, ModelOperation, str, dict[str, object]]:
        if isinstance(request, InferRequest):
            return request.binding, ModelOperation.INFER, request.request_sha256, request.payload()
        if isinstance(request, EmbedRequest):
            return request.binding, ModelOperation.EMBED, request.request_sha256, request.payload()
        if isinstance(request, RerankRequest):
            return request.binding, ModelOperation.RERANK, request.request_sha256, request.payload()
        raise ModelContractError("exact model request is required")

    def _claim_execution(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: InferRequest | EmbedRequest | RerankRequest,
        operation: ModelOperation,
        call: ModelCall,
    ) -> bool:
        binding, _, request_sha256, payload = self._request_parts(request)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM model_execution_claims WHERE project_id=? AND execution_id=?",
                (access.project_ref.value, binding.execution_ref.execution_id),
            ).fetchone()
            if prior is not None:
                if (
                    prior["adapter_ref"] != self.adapter_ref
                    or prior["operation"] != operation.value
                    or prior["request_sha256"] != request_sha256
                    or prior["node_attempt_id"] != attempt.attempt_id
                    or cast(int, prior["node_fence"]) != attempt.fence
                    or prior["model_call_id"] != call.call_ref.call_id
                ):
                    raise ModelConflictError("model execution identity conflicts")
                connection.commit()
                return False
            connection.execute(
                "INSERT INTO model_execution_claims VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    access.project_ref.value,
                    binding.execution_ref.execution_id,
                    self.adapter_ref,
                    operation.value,
                    request_sha256,
                    attempt.attempt_id,
                    attempt.fence,
                    call.call_ref.call_id,
                    _json(payload),
                ),
            )
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _start_call(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: InferRequest | EmbedRequest | RerankRequest,
        deployment: ModelDeployment,
        operation: ModelOperation,
    ) -> tuple[ModelCall, bool]:
        binding, _, _, _ = self._request_parts(request)
        input_refs = list(binding.input_refs)
        if binding.context_receipt_ref is not None and binding.context_receipt_ref not in input_refs:
            input_refs.append(binding.context_receipt_ref)
        try:
            call = self.calls.start_model_call(
                access,
                attempt,
                idempotency_key=f"model-{binding.execution_ref.execution_id}",
                capability_ref=binding.capability_ref,
                purpose="INITIAL",
                retry_of=None,
                provider_id=deployment.provider_ref,
                model_id=deployment.model_ref,
                deployment_id=deployment.deployment_ref.value,
                runtime_id=deployment.runtime_identity.runtime_ref,
                input_refs=input_refs,
                provider_trace_id=None,
            )
        except CallAuthorityError as exc:
            raise ModelAuthorityError("ModelCall authority was rejected") from exc
        except CallConflictError as exc:
            raise ModelConflictError("ModelCall identity conflicts") from exc
        return call, self._claim_execution(access, attempt, request, operation, call)

    def _cancelled(self, execution_ref: ModelExecutionRef) -> bool:
        connection = self._connect()
        try:
            return connection.execute(
                "SELECT 1 FROM model_cancellations WHERE project_id=? AND execution_id=? LIMIT 1",
                (execution_ref.project_ref.value, execution_ref.execution_id),
            ).fetchone() is not None
        finally:
            connection.close()

    def _execute_tools(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: InferRequest,
        model_call: ModelCall,
        proposals: tuple[ModelToolProposal, ...],
        execution_ref: ModelExecutionRef,
    ) -> tuple[ToolCallRef, ...]:
        definitions = {item.name: item for item in request.tools}
        refs: list[ToolCallRef] = []
        for index, proposal in enumerate(proposals):
            definition = definitions.get(proposal.name)
            if definition is None:
                raise _ProviderFailure(ModelExecutionFailure.UNAUTHORIZED_TOOL, "unauthorized_tool")
            arguments_ref = self.object_store.put(_json(dict(proposal.arguments)).encode(), media_type=_MEDIA_JSON)
            tool = self.calls.start_tool_call(
                access,
                attempt,
                idempotency_key=f"model-tool-{execution_ref.execution_id[:20]}-{index}",
                capability_ref=definition.capability_ref,
                purpose="INITIAL",
                retry_of=None,
                parent_model_call_ref=model_call.call_ref,
                tool_id=definition.tool_id,
                implementation_id=definition.implementation_id,
                runtime_id=model_call.runtime_id,
                input_refs=(arguments_ref,),
                provider_trace_id=proposal.provider_call_id,
            )
            if self.tool_executor is None:
                self.calls.finish_tool_call(
                    access,
                    attempt,
                    tool.call_ref,
                    idempotency_key=f"model-tool-finish-{execution_ref.execution_id[:16]}-{index}",
                    status="FAILED",
                    output_refs=(),
                    usage=None,
                    cost=None,
                    failure_category="TOOL_EXECUTOR_UNAVAILABLE",
                    failure_reason="Authorized model tool has no configured executor",
                    failure_evidence_refs=(arguments_ref,),
                )
                raise _ProviderFailure(ModelExecutionFailure.TOOL_EXECUTION_FAILED, "tool_executor_unavailable")
            try:
                outputs = tuple(self.tool_executor.execute(access, attempt, definition, arguments_ref))
                completed = self.calls.finish_tool_call(
                    access,
                    attempt,
                    tool.call_ref,
                    idempotency_key=f"model-tool-finish-{execution_ref.execution_id[:16]}-{index}",
                    status="SUCCEEDED",
                    output_refs=outputs,
                    usage=None,
                    cost=None,
                    failure_category=None,
                    failure_reason=None,
                    failure_evidence_refs=(),
                )
            except Exception as exc:
                if self.calls.get_tool_call(access, tool.call_ref).status == "RUNNING":
                    self.calls.finish_tool_call(
                        access,
                        attempt,
                        tool.call_ref,
                        idempotency_key=f"model-tool-finish-{execution_ref.execution_id[:16]}-{index}",
                        status="FAILED",
                        output_refs=(),
                        usage=None,
                        cost=None,
                        failure_category="TOOL_EXECUTION_FAILED",
                        failure_reason="Authorized model tool executor failed",
                        failure_evidence_refs=(arguments_ref,),
                    )
                raise _ProviderFailure(ModelExecutionFailure.TOOL_EXECUTION_FAILED, "tool_execution_failed") from exc
            refs.append(completed.call_ref)
        return tuple(refs)

    def _validate_provider_result(
        self,
        request: InferRequest | EmbedRequest | RerankRequest,
        deployment: ModelDeployment,
        provider: _ProviderResult,
    ) -> tuple[object, object | None]:
        if provider.operation not in deployment.operations:
            raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "operation_mismatch")
        if isinstance(request, InferRequest):
            if provider.operation is not ModelOperation.INFER or not isinstance(provider.value, str) or not provider.value:
                raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, provider.finish_reason)
            structured: object | None = None
            if request.output_schema_ref is not None:
                if not deployment.structured_output:
                    raise _ProviderFailure(ModelExecutionFailure.STRUCTURED_OUTPUT_INVALID, "structured_output_unsupported")
                try:
                    structured = json.loads(provider.value)
                    schema = json.loads(self.object_store.read(request.output_schema_ref))
                    _schema_validate(structured, schema)
                except (json.JSONDecodeError, ObjectStorageError, ModelAdapterError) as exc:
                    raise _ProviderFailure(ModelExecutionFailure.STRUCTURED_OUTPUT_INVALID, "structured_output_invalid") from exc
            if provider.tool_proposals and not deployment.tool_support:
                raise _ProviderFailure(ModelExecutionFailure.UNAUTHORIZED_TOOL, "deployment_tool_support_absent")
            return provider.value, structured
        if isinstance(request, EmbedRequest):
            if provider.operation is not ModelOperation.EMBED or not isinstance(provider.value, (list, tuple)):
                raise _ProviderFailure(ModelExecutionFailure.EMBEDDING_INVALID, "embedding_shape")
            try:
                inputs = json.loads(self.object_store.read(request.inputs_ref))
            except (json.JSONDecodeError, ObjectStorageError) as exc:
                raise _ProviderFailure(ModelExecutionFailure.CONTENT_INTEGRITY_FAILED, "embedding_input") from exc
            if not isinstance(inputs, list) or not inputs or not all(isinstance(item, str) and item for item in inputs):
                raise _ProviderFailure(ModelExecutionFailure.CONTENT_INTEGRITY_FAILED, "embedding_input")
            vectors: list[tuple[float, ...]] = []
            for vector in provider.value:
                if not isinstance(vector, (list, tuple)):
                    raise _ProviderFailure(ModelExecutionFailure.EMBEDDING_INVALID, "embedding_vector")
                values = tuple(float(item) for item in vector)
                if deployment.embedding_dimensions is None or len(values) != deployment.embedding_dimensions or not all(math.isfinite(item) for item in values):
                    raise _ProviderFailure(ModelExecutionFailure.EMBEDDING_INVALID, "embedding_dimension_or_finiteness")
                vectors.append(values)
            if len(vectors) != len(inputs):
                raise _ProviderFailure(ModelExecutionFailure.EMBEDDING_INVALID, "embedding_cardinality")
            return tuple(vectors), None
        if not isinstance(request, RerankRequest) or provider.operation is not ModelOperation.RERANK or not isinstance(provider.value, (list, tuple)):
            raise _ProviderFailure(ModelExecutionFailure.RERANK_INVALID, "rerank_shape")
        try:
            raw_candidates = json.loads(self.object_store.read(request.candidates_ref))
            candidates = tuple(RerankCandidate(cast(str, item["candidate_id"]), cast(str, item["text"])) for item in raw_candidates)
            entries = tuple(
                item if isinstance(item, RerankEntry) else RerankEntry(cast(str, item["candidate_id"]), cast(float, item["score"]), cast(int, item["rank"]))
                for item in provider.value
            )
        except (json.JSONDecodeError, ObjectStorageError, KeyError, TypeError, ValueError, ModelAdapterError) as exc:
            raise _ProviderFailure(ModelExecutionFailure.RERANK_INVALID, "rerank_payload") from exc
        candidate_ids = [item.candidate_id for item in candidates]
        entry_ids = [item.candidate_id for item in entries]
        if len(set(candidate_ids)) != len(candidate_ids) or set(entry_ids) != set(candidate_ids) or len(entry_ids) != len(candidate_ids) or [item.rank for item in entries] != list(range(1, len(entries) + 1)) or any(entries[index].score < entries[index + 1].score for index in range(len(entries) - 1)):
            raise _ProviderFailure(ModelExecutionFailure.RERANK_INVALID, "rerank_coverage_or_order")
        return entries, None

    def _publish_result(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: InferRequest | EmbedRequest | RerankRequest,
        deployment: ModelDeployment,
        operation: ModelOperation,
        call: ModelCall,
        value: object | None,
        structured: object | None,
        provider: _ProviderResult | None,
        failure: ModelExecutionFailure | None,
        tool_call_refs: tuple[ToolCallRef, ...],
        latency_ms: float,
        idempotency_key: str,
    ) -> InferResult | EmbedResult | RerankResult:
        binding, _, _, _ = self._request_parts(request)
        self._require_live_node(access, attempt)
        output_ref: ContentRef | None = None
        output_artifact: Artifact | None = None
        operation_payload: dict[str, object]
        if failure is None:
            if operation is ModelOperation.INFER:
                operation_payload = {"structured_value": structured, "text": value}
            elif operation is ModelOperation.EMBED:
                operation_payload = {"source_digest": cast(EmbedRequest, request).inputs_ref.digest, "vectors": value}
            else:
                assert isinstance(value, tuple)
                operation_payload = {
                    "entries": [cast(RerankEntry, item).payload() for item in value],
                    "source_digest": cast(RerankRequest, request).candidates_ref.digest,
                }
            output_ref = self.object_store.put(
                _json({"operation": operation.value, **operation_payload}).encode(),
                media_type=_RESULT_MEDIA_TYPE,
            )
            output_artifact = self.artifacts.publish_from_run(
                access,
                producer_attempt=self._run_attempt(access, attempt),
                expected_task_ref=attempt.task_ref,
                expected_task_digest=attempt.task_digest,
                role=f"model.{operation.value}.output",
                content_ref=output_ref,
                source_refs=(),
                source_artifact_refs=tuple(item for item in binding.input_refs if isinstance(item, ArtifactRef)),
                source_content_refs=tuple(item for item in binding.input_refs if isinstance(item, ContentRef)),
                derivation_type=f"model.{operation.value}",
                metadata={
                    "media_type": output_ref.media_type,
                    "schema_ref": f"schema://biella/model-{operation.value}-result/1",
                    "schema_version": "1.0.0",
                    "semantic_label": operation.value,
                },
            )
        else:
            operation_payload = {}
        completed_at = _now()
        finish_reason = None if provider is None else provider.finish_reason
        usage = None if provider is None else provider.usage
        receipt_basis = {
            "completed_at": completed_at,
            "deployment_ref": deployment.deployment_ref.value,
            "execution_ref": binding.execution_ref.value,
            "failure": None if failure is None else failure.value,
            "finish_reason": finish_reason,
            "latency_ms": float(latency_ms),
            "model_call_ref": call.call_ref.value,
            "operation": operation.value,
            "output_artifact_ref": None if output_artifact is None else output_artifact.artifact_ref.value,
            "output_ref": _content_payload(output_ref),
            "provider_trace_id": None if provider is None else provider.provider_trace_id,
            "runtime_identity": deployment.runtime_identity.payload(),
            "tool_call_refs": [item.value for item in tool_call_refs],
            "usage": None if usage is None else usage.payload(),
            **operation_payload,
        }
        receipt_ref = self.object_store.put(_json(receipt_basis).encode(), media_type=_RECEIPT_MEDIA_TYPE)
        receipt_artifact = self.artifacts.publish_from_run(
            access,
            producer_attempt=self._run_attempt(access, attempt),
            expected_task_ref=attempt.task_ref,
            expected_task_digest=attempt.task_digest,
            role=f"model.{operation.value}.receipt",
            content_ref=receipt_ref,
            source_refs=(),
            source_artifact_refs=() if output_artifact is None else (output_artifact.artifact_ref,),
            source_content_refs=tuple(item for item in (*binding.input_refs, output_ref) if isinstance(item, ContentRef)),
            derivation_type=f"model.{operation.value}",
            metadata={"media_type": receipt_ref.media_type, "schema_ref": "schema://biella/model-receipt/1", "schema_version": "1.0.0"},
        )
        finish_key = hashlib.sha256(f"{attempt.record_sha256}\0{idempotency_key}".encode()).hexdigest()[:45]
        try:
            terminal = self.calls.finish_model_call(
                access,
                attempt,
                call.call_ref,
                idempotency_key=f"model-finish-{finish_key}",
                status="SUCCEEDED" if failure is None else ("TIMED_OUT" if failure is ModelExecutionFailure.TIMEOUT else "CANCELLED" if failure is ModelExecutionFailure.CANCELLED else "FAILED"),
                output_refs=tuple(item for item in (output_ref, None if output_artifact is None else output_artifact.artifact_ref, receipt_ref, receipt_artifact.artifact_ref) if item is not None) if failure is None else (),
                usage=usage,
                cost=None,
                failure_category=None if failure is None else failure.value,
                failure_reason=None if failure is None else f"Model execution failed: {failure.value}",
                failure_evidence_refs=() if failure is None else (receipt_ref, receipt_artifact.artifact_ref),
            )
        except CallAuthorityError as exc:
            raise ModelAuthorityError("late or stale model result was rejected") from exc
        except CallConflictError as exc:
            raise ModelConflictError("model completion conflicts") from exc
        evidence = ModelResultEvidence(
            binding.execution_ref,
            deployment.deployment_ref,
            terminal.call_ref,
            output_ref,
            None if output_artifact is None else output_artifact.artifact_ref,
            receipt_artifact.artifact_ref,
            deployment.runtime_identity,
            usage,
            finish_reason,
            None if provider is None else provider.provider_trace_id,
            failure,
            tool_call_refs,
            latency_ms,
            completed_at,
        )
        if isinstance(request, InferRequest):
            result: InferResult | EmbedResult | RerankResult = InferResult(evidence, cast(str | None, value), structured)
            persisted_operation = {"text": cast(str | None, value), "structured_value": structured}
        elif isinstance(request, EmbedRequest):
            vectors = () if value is None else cast(tuple[tuple[float, ...], ...], value)
            result = EmbedResult(evidence, vectors, request.inputs_ref.digest)
            persisted_operation = {"source_digest": request.inputs_ref.digest, "vectors": [list(item) for item in vectors]}
        else:
            entries = () if value is None else cast(tuple[RerankEntry, ...], value)
            result = RerankResult(evidence, entries, request.candidates_ref.digest)
            persisted_operation = {"entries": [item.payload() for item in entries], "source_digest": request.candidates_ref.digest}
        result_payload = {"evidence": evidence.payload(), **persisted_operation}
        record_sha256 = _digest(result_payload)
        connection = self._connect()
        try:
            connection.execute(
                "INSERT INTO model_execution_results VALUES (?,?,?,?,?)",
                (access.project_ref.value, binding.execution_ref.execution_id, operation.value, _json(result_payload), record_sha256),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ModelConflictError("model result persistence conflicts") from exc
        finally:
            connection.close()
        return result

    def _execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: InferRequest | EmbedRequest | RerankRequest,
        *,
        credentials: Mapping[str, str],
        idempotency_key: str,
    ) -> InferResult | EmbedResult | RerankResult:
        if _KEY.fullmatch(idempotency_key) is None or not isinstance(credentials, Mapping):
            raise ModelContractError("model execution idempotency or credentials are malformed")
        binding, operation, _, _ = self._request_parts(request)
        self._authorize(access, binding.project_ref)
        deployment = self.get_deployment(access, binding.deployment_ref)
        started_at = time.monotonic()
        try:
            self._validate_binding(access, attempt, binding, deployment, operation)
        except _ProviderFailure as exc:
            call, first = self._start_call(access, attempt, request, deployment, operation)
            if not first:
                return self.get_result(access, binding.execution_ref)
            return self._publish_result(access, attempt, request, deployment, operation, call, None, None, None, exc.failure, (), (time.monotonic() - started_at) * 1000, idempotency_key)
        except ObjectStorageError as exc:
            raise ModelIntegrityError("model input ContentRef failed verification") from exc
        call, first = self._start_call(access, attempt, request, deployment, operation)
        if not first:
            if call.status == "RUNNING":
                raise ModelConflictError("model execution is already claimed and incomplete")
            return self.get_result(access, binding.execution_ref)
        active = _ActiveExecution(threading.Event())
        self._active[binding.execution_ref.value] = active
        if self._cancelled(binding.execution_ref):
            active.cancellation.set()
        provider: _ProviderResult | None = None
        value: object | None = None
        structured: object | None = None
        failure: ModelExecutionFailure | None = None
        tool_refs: tuple[ToolCallRef, ...] = ()
        try:
            try:
                provider = self._invoke(access, attempt, request, deployment, credentials, active)
                self.record_health(
                    access,
                    ModelDeploymentHealth(
                        deployment.deployment_ref,
                        ModelHealthStatus.HEALTHY,
                        deployment.runtime_identity.record_sha256,
                        None,
                    ),
                )
                if active.cancellation.is_set():
                    raise _ProviderFailure(ModelExecutionFailure.CANCELLED, "cancelled")
                value, structured = self._validate_provider_result(request, deployment, provider)
                if isinstance(request, InferRequest) and provider.tool_proposals:
                    tool_refs = self._execute_tools(access, attempt, request, call, provider.tool_proposals, binding.execution_ref)
            except _ProviderFailure as exc:
                failure = exc.failure
                if failure is ModelExecutionFailure.PROVIDER_UNAVAILABLE:
                    self.record_health(
                        access,
                        ModelDeploymentHealth(
                            deployment.deployment_ref,
                            ModelHealthStatus.UNAVAILABLE,
                            deployment.runtime_identity.record_sha256,
                            "provider unavailable",
                        ),
                    )
                if provider is None:
                    provider = _ProviderResult(operation, None, exc.finish_reason, None, None)
            return self._publish_result(
                access,
                attempt,
                request,
                deployment,
                operation,
                call,
                value,
                structured,
                provider,
                failure,
                tool_refs,
                (time.monotonic() - started_at) * 1000,
                idempotency_key,
            )
        finally:
            self._active.pop(binding.execution_ref.value, None)

    def infer(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: InferRequest, *, credentials: Mapping[str, str], idempotency_key: str) -> InferResult:
        return cast(InferResult, self._execute(access, attempt, request, credentials=credentials, idempotency_key=idempotency_key))

    def embed(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: EmbedRequest, *, credentials: Mapping[str, str], idempotency_key: str) -> EmbedResult:
        return cast(EmbedResult, self._execute(access, attempt, request, credentials=credentials, idempotency_key=idempotency_key))

    def rerank(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: RerankRequest, *, credentials: Mapping[str, str], idempotency_key: str) -> RerankResult:
        return cast(RerankResult, self._execute(access, attempt, request, credentials=credentials, idempotency_key=idempotency_key))

    def cancel(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        execution_ref: ModelExecutionRef,
        *,
        idempotency_key: str,
    ) -> ModelCancellationReceipt:
        if _KEY.fullmatch(idempotency_key) is None:
            raise ModelContractError("model cancellation idempotency key is malformed")
        self._authorize(access, execution_ref.project_ref)
        self._run_attempt(access, attempt)
        receipt = ModelCancellationReceipt(execution_ref, True, idempotency_key, _now())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            claim = connection.execute(
                "SELECT * FROM model_execution_claims WHERE project_id=? AND execution_id=?",
                (access.project_ref.value, execution_ref.execution_id),
            ).fetchone()
            if claim is None:
                raise ModelNotFoundError("model execution claim is unavailable for cancellation")
            if claim["node_attempt_id"] != attempt.attempt_id or cast(int, claim["node_fence"]) != attempt.fence:
                raise ModelAuthorityError("model cancellation crossed Node attempt ownership")
            prior = connection.execute(
                "SELECT * FROM model_cancellations WHERE project_id=? AND execution_id=? AND idempotency_key=?",
                (access.project_ref.value, execution_ref.execution_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                payload = json.loads(cast(str, prior["receipt_json"]))
                value = ModelCancellationReceipt(execution_ref, cast(bool, payload["accepted"]), cast(str, payload["idempotency_key"]), cast(str, payload["observed_at"]))
                if not hmac.compare_digest(value.record_sha256, cast(str, prior["record_sha256"])):
                    raise ModelIntegrityError("model cancellation evidence changed")
                connection.commit()
                return value
            connection.execute(
                "INSERT INTO model_cancellations VALUES (?,?,?,?,?)",
                (access.project_ref.value, execution_ref.execution_id, idempotency_key, _json(receipt.payload()), receipt.record_sha256),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        active = self._active.get(execution_ref.value)
        if active is not None:
            active.cancellation.set()
            self._cancel_provider(access, attempt, active, idempotency_key)
        return receipt

    def _result_from_payload(self, payload: object, project_ref: ProjectRef, operation: ModelOperation) -> InferResult | EmbedResult | RerankResult:
        if not isinstance(payload, dict) or not isinstance(payload.get("evidence"), dict):
            raise ModelIntegrityError("persisted model result is malformed")
        evidence_payload = cast(dict[str, object], payload["evidence"])
        try:
            execution_value = cast(str, evidence_payload["execution_ref"])
            deployment_value = cast(str, evidence_payload["deployment_ref"])
            call_value = cast(str, evidence_payload["model_call_ref"])
            execution_prefix = f"model-execution://{project_ref.value}/"
            deployment_prefix = f"model-deployment://{project_ref.value}/"
            call_prefix = f"model-call://{project_ref.value}/"
            if not execution_value.startswith(execution_prefix) or not deployment_value.startswith(deployment_prefix) or not call_value.startswith(call_prefix):
                raise ModelScopeError("persisted model result crossed Project scope")
            receipt_ref = _artifact_ref(evidence_payload["receipt_artifact_ref"], project_ref)
            if receipt_ref is None:
                raise ModelIntegrityError("persisted model receipt Artifact is absent")
            tool_refs: list[ToolCallRef] = []
            tool_prefix = f"tool-call://{project_ref.value}/"
            for item in cast(list[str], evidence_payload["tool_call_refs"]):
                if not item.startswith(tool_prefix):
                    raise ModelScopeError("persisted model ToolCall crossed Project scope")
                tool_refs.append(ToolCallRef(project_ref, item.removeprefix(tool_prefix)))
            evidence = ModelResultEvidence(
                ModelExecutionRef(project_ref, execution_value.removeprefix(execution_prefix)),
                ModelDeploymentRef(project_ref, deployment_value.removeprefix(deployment_prefix)),
                ModelCallRef(project_ref, call_value.removeprefix(call_prefix)),
                _content_ref(evidence_payload["output_ref"]),
                _artifact_ref(evidence_payload["output_artifact_ref"], project_ref),
                receipt_ref,
                _runtime_from_payload(evidence_payload["runtime_identity"], project_ref),
                _usage_from_payload(evidence_payload["usage"]),
                cast(str | None, evidence_payload["finish_reason"]),
                cast(str | None, evidence_payload["provider_trace_id"]),
                None if evidence_payload["failure"] is None else ModelExecutionFailure(cast(str, evidence_payload["failure"])),
                tuple(tool_refs),
                cast(float, evidence_payload["latency_ms"]),
                cast(str, evidence_payload["completed_at"]),
            )
            if operation is ModelOperation.INFER:
                return InferResult(evidence, cast(str | None, payload["text"]), payload["structured_value"])
            if operation is ModelOperation.EMBED:
                vectors = tuple(tuple(float(item) for item in vector) for vector in cast(list[list[float]], payload["vectors"]))
                return EmbedResult(evidence, vectors, cast(str, payload["source_digest"]))
            entries = tuple(RerankEntry(cast(str, item["candidate_id"]), cast(float, item["score"]), cast(int, item["rank"])) for item in cast(list[dict[str, object]], payload["entries"]))
            return RerankResult(evidence, entries, cast(str, payload["source_digest"]))
        except (KeyError, TypeError, ValueError, ModelAdapterError) as exc:
            if isinstance(exc, (ModelIntegrityError, ModelScopeError)):
                raise
            raise ModelIntegrityError("persisted model result is malformed") from exc

    def get_result(self, access: ProjectAccess, execution_ref: ModelExecutionRef) -> InferResult | EmbedResult | RerankResult:
        self._authorize(access, execution_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM model_execution_results WHERE project_id=? AND execution_id=?",
                (access.project_ref.value, execution_ref.execution_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ModelNotFoundError("model execution result is unavailable")
        try:
            payload = json.loads(cast(str, row["result_json"]))
            result = self._result_from_payload(payload, access.project_ref, ModelOperation(cast(str, row["operation"])))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ModelIntegrityError("model execution result is malformed") from exc
        if result.evidence.execution_ref != execution_ref or not hmac.compare_digest(_digest(payload), cast(str, row["record_sha256"])):
            raise ModelIntegrityError("model execution result evidence changed")
        call = self.calls.get_model_call(access, result.evidence.model_call_ref)
        expected_status = "SUCCEEDED" if result.evidence.succeeded else "TIMED_OUT" if result.evidence.failure is ModelExecutionFailure.TIMEOUT else "CANCELLED" if result.evidence.failure is ModelExecutionFailure.CANCELLED else "FAILED"
        if call.status != expected_status or call.usage != result.evidence.usage:
            raise ModelIntegrityError("model result and ModelCall state differ")
        try:
            receipt = self.artifacts.get_artifact(access, result.evidence.receipt_artifact_ref)
            if receipt.content_ref is None:
                raise ModelIntegrityError("model receipt Artifact lacks content")
            self.object_store.verify(receipt.content_ref)
            receipt_payload = json.loads(self.object_store.read(receipt.content_ref))
            if isinstance(result, InferResult):
                operation = ModelOperation.INFER
                operation_payload: dict[str, object] = {
                    "structured_value": result.structured_value,
                    "text": result.text,
                }
            elif isinstance(result, EmbedResult):
                operation = ModelOperation.EMBED
                operation_payload = {
                    "source_digest": result.source_digest,
                    "vectors": [list(item) for item in result.vectors],
                }
            else:
                operation = ModelOperation.RERANK
                operation_payload = {
                    "entries": [item.payload() for item in result.entries],
                    "source_digest": result.source_digest,
                }
            expected_receipt = {
                "completed_at": result.evidence.completed_at,
                "deployment_ref": result.evidence.deployment_ref.value,
                "execution_ref": result.evidence.execution_ref.value,
                "failure": None if result.evidence.failure is None else result.evidence.failure.value,
                "finish_reason": result.evidence.finish_reason,
                "latency_ms": float(result.evidence.latency_ms),
                "model_call_ref": result.evidence.model_call_ref.value,
                "operation": operation.value,
                "output_artifact_ref": _object_ref_payload(result.evidence.output_artifact_ref),
                "output_ref": _content_payload(result.evidence.output_ref),
                "provider_trace_id": result.evidence.provider_trace_id,
                "runtime_identity": result.evidence.runtime_identity.payload(),
                "tool_call_refs": [item.value for item in result.evidence.tool_call_refs],
                "usage": None if result.evidence.usage is None else result.evidence.usage.payload(),
                **operation_payload,
            }
            if receipt_payload != expected_receipt:
                raise ModelIntegrityError("model result and receipt manifest differ")
            expected_receipt_refs = {receipt.content_ref, receipt.artifact_ref}
            if result.evidence.succeeded:
                expected_outputs = set(expected_receipt_refs)
                if result.evidence.output_ref is not None:
                    expected_outputs.add(result.evidence.output_ref)
                    self.object_store.verify(result.evidence.output_ref)
                if result.evidence.output_artifact_ref is not None:
                    expected_outputs.add(result.evidence.output_artifact_ref)
                    output_artifact = self.artifacts.get_artifact(access, result.evidence.output_artifact_ref)
                    if output_artifact.content_ref != result.evidence.output_ref:
                        raise ModelIntegrityError("model output Artifact and ContentRef differ")
                if set(call.output_refs) != expected_outputs or call.failure_evidence_refs:
                    raise ModelIntegrityError("model result and successful ModelCall evidence differ")
            elif set(call.failure_evidence_refs) != expected_receipt_refs or call.output_refs:
                raise ModelIntegrityError("model result and failed ModelCall evidence differ")
        except (ObjectStorageError, json.JSONDecodeError) as exc:
            raise ModelIntegrityError("model ContentRef evidence failed verification") from exc
        for tool_ref in result.evidence.tool_call_refs:
            tool = self.calls.get_tool_call(access, tool_ref)
            if tool.parent_model_call_ref != call.call_ref or tool.status != "SUCCEEDED":
                raise ModelIntegrityError("model tool evidence differs from ModelCall")
        return result

    def _invoke(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: InferRequest | EmbedRequest | RerankRequest,
        deployment: ModelDeployment,
        credentials: Mapping[str, str],
        active: _ActiveExecution,
    ) -> _ProviderResult:
        raise ModelContractError("model adapter implementation is unavailable")

    def _cancel_provider(self, access: ProjectAccess, attempt: NodeExecutionAttempt, active: _ActiveExecution, idempotency_key: str) -> None:
        return


class ReferenceModelAdapter(_BaseModelAdapter):
    """Deterministic REFERENCE implementation of infer, embed, and rerank."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        latency_seconds: float = 0.0,
        tool_executor: ModelToolExecutor | None = None,
    ) -> None:
        if isinstance(latency_seconds, bool) or not isinstance(latency_seconds, (int, float)) or latency_seconds < 0:
            raise ModelContractError("reference model latency is malformed")
        self.latency_seconds = float(latency_seconds)
        super().__init__(
            database_path,
            object_store,
            adapter_ref="adapter://biella/model/reference-v1",
            reality="REFERENCE",
            tool_executor=tool_executor,
        )

    def health(self, access: ProjectAccess, deployment_ref: ModelDeploymentRef) -> ModelDeploymentHealth:
        deployment = self.get_deployment(access, deployment_ref)
        current = super().health(access, deployment_ref)
        if current.status is ModelHealthStatus.UNKNOWN:
            return self.record_health(
                access,
                ModelDeploymentHealth(deployment_ref, ModelHealthStatus.HEALTHY, deployment.runtime_identity.record_sha256, None),
            )
        return current

    def _wait(self, binding: ModelExecutionBinding, active: _ActiveExecution) -> None:
        deadline = time.monotonic() + float(binding.timeout_seconds)
        remaining_delay = self.latency_seconds
        while remaining_delay > 0:
            if active.cancellation.is_set():
                raise _ProviderFailure(ModelExecutionFailure.CANCELLED, "cancelled")
            if time.monotonic() >= deadline:
                raise _ProviderFailure(ModelExecutionFailure.TIMEOUT, "timeout")
            interval = min(0.01, remaining_delay, max(0.0, deadline - time.monotonic()))
            if interval <= 0:
                raise _ProviderFailure(ModelExecutionFailure.TIMEOUT, "timeout")
            time.sleep(interval)
            remaining_delay -= interval

    def _invoke(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: InferRequest | EmbedRequest | RerankRequest,
        deployment: ModelDeployment,
        credentials: Mapping[str, str],
        active: _ActiveExecution,
    ) -> _ProviderResult:
        if credentials:
            raise _ProviderFailure(ModelExecutionFailure.AUTHORITY_DENIED, "reference_credentials_forbidden")
        self._wait(request.binding, active)
        try:
            if isinstance(request, InferRequest):
                payload = json.loads(self.object_store.read(request.messages_ref))
                messages = payload.get("messages") if isinstance(payload, dict) else payload
                if not isinstance(messages, list) or not messages:
                    raise ModelContractError("reference messages are malformed")
                last = messages[-1]
                if not isinstance(last, dict) or not isinstance(last.get("content"), str) or not last["content"]:
                    raise ModelContractError("reference message content is malformed")
                content = cast(str, last["content"])
                proposals: tuple[ModelToolProposal, ...] = ()
                try:
                    possible = json.loads(content)
                    tool_value = possible.get("tool_call") if isinstance(possible, dict) else None
                    if isinstance(tool_value, dict):
                        proposals = (
                            ModelToolProposal(
                                cast(str, tool_value["name"]),
                                cast(dict[str, object], tool_value["arguments"]),
                                "reference-tool-proposal-1",
                            ),
                        )
                except (json.JSONDecodeError, KeyError, TypeError, ModelAdapterError):
                    proposals = ()
                return _ProviderResult(ModelOperation.INFER, content, "stop", None, None, proposals)
            if isinstance(request, EmbedRequest):
                inputs = json.loads(self.object_store.read(request.inputs_ref))
                if not isinstance(inputs, list) or not inputs or not all(isinstance(item, str) and item for item in inputs):
                    raise ModelContractError("reference embedding inputs are malformed")
                assert deployment.embedding_dimensions is not None
                vectors: list[list[float]] = []
                for item in inputs:
                    digest = hashlib.sha256(cast(str, item).encode()).digest()
                    vectors.append([((digest[index % len(digest)] / 255.0) * 2.0) - 1.0 for index in range(deployment.embedding_dimensions)])
                return _ProviderResult(ModelOperation.EMBED, vectors, "complete", None, None)
            query = json.loads(self.object_store.read(request.query_ref))
            raw_candidates = json.loads(self.object_store.read(request.candidates_ref))
            if not isinstance(query, str) or not query or not isinstance(raw_candidates, list) or not raw_candidates:
                raise ModelContractError("reference rerank inputs are malformed")
            candidates = tuple(RerankCandidate(cast(str, item["candidate_id"]), cast(str, item["text"])) for item in raw_candidates)
            query_terms = set(re.findall(r"\w+", query.lower()))
            scored = sorted(
                (
                    (candidate.candidate_id, float(len(query_terms.intersection(re.findall(r"\w+", candidate.text.lower())))))
                    for candidate in candidates
                ),
                key=lambda item: (-item[1], item[0]),
            )
            entries = tuple(RerankEntry(candidate_id, score, index + 1) for index, (candidate_id, score) in enumerate(scored))
            return _ProviderResult(ModelOperation.RERANK, entries, "complete", None, None)
        except (json.JSONDecodeError, ObjectStorageError, KeyError, TypeError, ModelAdapterError) as exc:
            raise _ProviderFailure(ModelExecutionFailure.CONTENT_INTEGRITY_FAILED, "reference_input_invalid") from exc


class HostedHttpModelAdapter(_BaseModelAdapter):
    """REAL hosted model implementation routed through the P2-05 HTTP adapter."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        http_adapter: HttpAdapter,
        routes: Mapping[ModelDeploymentRef, HostedModelRoute],
        *,
        tool_executor: ModelToolExecutor | None = None,
    ) -> None:
        if not isinstance(http_adapter, HttpAdapter) or not isinstance(routes, Mapping):
            raise ModelContractError("hosted model HTTP adapter or routes are malformed")
        copied = dict(routes)
        if not copied or len(copied) > 256:
            raise ModelContractError("hosted model routes are empty or unbounded")
        for key, value in copied.items():
            if not isinstance(key, ModelDeploymentRef) or not isinstance(value, HostedModelRoute) or key != value.deployment_ref:
                raise ModelContractError("hosted model route identity is malformed")
        self.http = http_adapter
        self.routes = MappingProxyType(copied)
        super().__init__(
            database_path,
            object_store,
            adapter_ref="adapter://biella/model/hosted-http-v1",
            reality="REAL",
            tool_executor=tool_executor,
        )

    @staticmethod
    def _usage(payload: object) -> CallUsage | None:
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "usage_shape")

        def known(name: str) -> UsageMetric:
            value = payload.get(name)
            if value is None:
                return UsageMetric(None, None)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "usage_value")
            return UsageMetric(value, "PROVIDER_REPORTED")

        return CallUsage(
            known("prompt_tokens"),
            known("completion_tokens"),
            known("reasoning_tokens"),
            known("cached_tokens"),
            known("cache_write_tokens"),
        )

    @staticmethod
    def _tool_proposals(value: object) -> tuple[ModelToolProposal, ...]:
        if value is None:
            return ()
        if not isinstance(value, list) or len(value) > 128:
            raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "tool_call_shape")
        proposals: list[ModelToolProposal] = []
        for item in value:
            try:
                if not isinstance(item, dict) or not isinstance(item.get("function"), dict):
                    raise TypeError
                function = cast(dict[str, object], item["function"])
                arguments = function["arguments"]
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                if not isinstance(arguments, dict):
                    raise TypeError
                proposals.append(ModelToolProposal(cast(str, function["name"]), arguments, cast(str | None, item.get("id"))))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, ModelAdapterError) as exc:
                raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "tool_call_shape") from exc
        return tuple(proposals)

    def _parse_response(self, operation: ModelOperation, payload: object) -> _ProviderResult:
        if not isinstance(payload, dict):
            raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "provider_envelope")
        if payload.get("success") is False:
            raise _ProviderFailure(ModelExecutionFailure.PROVIDER_UNAVAILABLE, "provider_error")
        result = payload.get("result", payload)
        if not isinstance(result, dict):
            raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "provider_result")
        trace = result.get("id")
        if trace is not None and not isinstance(trace, str):
            raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "provider_trace")
        usage = self._usage(result.get("usage"))
        if operation is ModelOperation.INFER:
            finish = result.get("finish_reason")
            if finish is not None and not isinstance(finish, str):
                raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "finish_reason")
            if isinstance(result.get("response"), str):
                return _ProviderResult(operation, result["response"], finish, usage, trace, self._tool_proposals(result.get("tool_calls")))
            choices = result.get("choices")
            if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
                raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "provider_choices")
            choice = cast(dict[str, object], choices[0])
            message = choice.get("message")
            if not isinstance(message, dict):
                raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "provider_message")
            choice_finish = choice.get("finish_reason")
            if choice_finish is not None and not isinstance(choice_finish, str):
                raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "finish_reason")
            return _ProviderResult(
                operation,
                message.get("content"),
                choice_finish,
                usage,
                trace,
                self._tool_proposals(message.get("tool_calls")),
            )
        finish = result.get("finish_reason", "complete")
        if not isinstance(finish, str):
            raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "finish_reason")
        if operation is ModelOperation.EMBED:
            return _ProviderResult(operation, result.get("data"), finish, usage, trace)
        entries = result.get("data", result.get("results"))
        return _ProviderResult(operation, entries, finish, usage, trace)

    def _invoke(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: InferRequest | EmbedRequest | RerankRequest,
        deployment: ModelDeployment,
        credentials: Mapping[str, str],
        active: _ActiveExecution,
    ) -> _ProviderResult:
        route = self.routes.get(deployment.deployment_ref)
        if route is None or deployment.endpoint_ref != route.destination_ref.value:
            raise _ProviderFailure(ModelExecutionFailure.AUTHORITY_DENIED, "hosted_route_missing")
        provider_model_name = deployment.metadata.get("provider_model_name")
        if not isinstance(provider_model_name, str) or not provider_model_name:
            raise _ProviderFailure(ModelExecutionFailure.AUTHORITY_DENIED, "provider_model_name_missing")
        try:
            if isinstance(request, InferRequest):
                messages_value = json.loads(self.object_store.read(request.messages_ref))
                messages = messages_value.get("messages") if isinstance(messages_value, dict) else messages_value
                if not isinstance(messages, list):
                    raise ModelContractError("hosted messages are malformed")
                provider_input: dict[str, object] = {"messages": messages, **dict(request.generation_parameters)}
                if request.output_schema_ref is not None:
                    provider_input["response_format"] = {"type": "json_schema", "json_schema": json.loads(self.object_store.read(request.output_schema_ref))}
                if request.tools:
                    provider_input["tools"] = [
                        {"type": "function", "function": {"name": item.name, "parameters": {"type": "object", "properties": {}}}}
                        for item in request.tools
                    ]
                operation = ModelOperation.INFER
            elif isinstance(request, EmbedRequest):
                provider_input = {"text": json.loads(self.object_store.read(request.inputs_ref))}
                operation = ModelOperation.EMBED
            else:
                query = json.loads(self.object_store.read(request.query_ref))
                candidates = json.loads(self.object_store.read(request.candidates_ref))
                provider_input = {"query": query, "contexts": candidates}
                operation = ModelOperation.RERANK
        except (json.JSONDecodeError, ObjectStorageError, ModelAdapterError) as exc:
            raise _ProviderFailure(ModelExecutionFailure.CONTENT_INTEGRITY_FAILED, "hosted_input_invalid") from exc
        body_ref = self.object_store.put(_json({"input": provider_input, "model": provider_model_name}).encode(), media_type=_MEDIA_JSON)
        http_identity = hashlib.sha256(request.binding.execution_ref.value.encode()).hexdigest()[:32]
        http_execution_ref = HttpExecutionRef(request.binding.project_ref, f"hexec_{http_identity}")
        active.http_execution_ref = http_execution_ref
        http_request = HttpExecutionRequest(
            request.binding.project_ref,
            http_execution_ref,
            route.destination_ref,
            request.binding.task_ref,
            request.binding.task_digest,
            request.binding.run_ref,
            request.binding.node_ref,
            request.binding.node_attempt_id,
            request.binding.node_fence,
            cast(str, request.binding.data_policy_ref),
            cast(str, request.binding.egress_policy_ref),
            "POST",
            route.path,
            {},
            {"content-type": _MEDIA_JSON},
            {},
            body_ref,
            HttpRedirectPolicy.NONE,
            0,
            32 * 1024 * 1024,
            request.binding.timeout_seconds,
            None,
        )
        result = self.http.execute(
            access,
            attempt,
            http_request,
            secret_values=credentials,
            idempotency_key=f"model-http-{request.binding.execution_ref.execution_id[:32]}",
        )
        if not result.transport_success or result.response_ref is None:
            if result.failure is HttpExecutionFailure.TIMEOUT:
                failure = ModelExecutionFailure.TIMEOUT
            elif result.failure is HttpExecutionFailure.CANCELLED:
                failure = ModelExecutionFailure.CANCELLED
            elif result.failure is HttpExecutionFailure.EGRESS_DENIED:
                failure = ModelExecutionFailure.EGRESS_DENIED
            else:
                failure = ModelExecutionFailure.PROVIDER_UNAVAILABLE
            raise _ProviderFailure(failure, None if result.failure is None else result.failure.value)
        if result.status_code is None or not 200 <= result.status_code < 300:
            raise _ProviderFailure(ModelExecutionFailure.PROVIDER_UNAVAILABLE, f"http_{result.status_code}")
        try:
            payload = json.loads(self.object_store.read(result.response_ref))
        except (json.JSONDecodeError, ObjectStorageError) as exc:
            raise _ProviderFailure(ModelExecutionFailure.MALFORMED_OUTPUT, "provider_json") from exc
        return self._parse_response(operation, payload)

    def _cancel_provider(self, access: ProjectAccess, attempt: NodeExecutionAttempt, active: _ActiveExecution, idempotency_key: str) -> None:
        if active.http_execution_ref is not None:
            self.http.cancel(
                access,
                attempt,
                active.http_execution_ref,
                idempotency_key=f"model-http-cancel-{idempotency_key[:31]}",
            )
