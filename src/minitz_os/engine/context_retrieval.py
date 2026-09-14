"""Project-scoped context compilation and rebuildable derived retrieval."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import cast
from uuid import uuid4

from .artifact import (
    Artifact,
    ArtifactError,
    ArtifactRef,
    ArtifactService,
    ContentRef,
)
from .call_ledger import CallError, CallLedgerService, ModelCallRef
from .engine_memory import Knowledge, KnowledgeRef
from .execution import NodeExecutionAttempt, NodeExecutionService
from .graph import GraphRef, NodeRef
from .model_adapter import (
    EmbedRequest,
    EmbedResult,
    ModelAdapter,
    ModelDeployment,
    ModelExecutionBinding,
    ModelExecutionRef,
    ModelOperation,
    RerankEntry,
    RerankRequest,
    RerankResult,
)
from .object_store import ObjectStorageBackend, ObjectStorageError
from .project import ProjectAccess, ProjectRef, ProjectScopeError, ProjectStore
from .project_memory import (
    ProjectKnowledge,
    ProjectKnowledgeError,
    ProjectKnowledgeRef,
    ProjectKnowledgeService,
)
from .run import RunRef
from .run_memory import RunMemory, RunMemoryError, RunMemoryService
from .task import Task, TaskRef, TaskRevisionService
from .capability import CapabilityRef


_SHA256 = re.compile(r"[0-9a-f]{64}")
_INDEX_ID = re.compile(r"idx_[0-9a-f]{32}")
_RECEIPT_ID = re.compile(r"rrc_[0-9a-f]{32}")
_MANIFEST_ID = re.compile(r"cmf_[0-9a-f]{32}")
_CONTEXT_RECEIPT_ID = re.compile(r"crc_[0-9a-f]{32}")
_INDEX_KEY = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+){0,15}")
_VERSION = re.compile(r"[a-z0-9][a-z0-9_.-]{0,127}")
_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}")
_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,2048}")
_FAILURE_REF = re.compile(r"failure://sha256/[0-9a-f]{64}")
_MAX_CHUNKS = 100_000
_MAX_VECTOR_DIMENSION = 65_536


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


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ContextRetrievalContractError(f"{name} is malformed")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ContextRetrievalContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContextRetrievalContractError(f"{name} is malformed")
    return value


def _refs(values: Sequence[str], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or len(values) > 100_000:
        raise ContextRetrievalContractError(f"{name} is malformed or unbounded")
    copied = tuple(values)
    if any(not isinstance(item, str) or _ABSOLUTE_REF.fullmatch(item) is None for item in copied):
        raise ContextRetrievalContractError(f"{name} contains a malformed reference")
    if len(set(copied)) != len(copied):
        raise ContextRetrievalContractError(f"{name} contains duplicate references")
    return tuple(sorted(copied))


def _artifact_refs(
    values: Sequence[ArtifactRef],
    project_ref: ProjectRef,
    name: str,
) -> tuple[ArtifactRef, ...]:
    if isinstance(values, (str, bytes)) or len(values) > 10_000:
        raise ContextRetrievalContractError(f"{name} is malformed or unbounded")
    copied = tuple(values)
    if not all(isinstance(item, ArtifactRef) for item in copied):
        raise ContextRetrievalContractError(f"{name} must contain ArtifactRef")
    if any(item.project_ref != project_ref for item in copied):
        raise ContextRetrievalScopeError(f"{name} crossed Project scope")
    if len(set(copied)) != len(copied):
        raise ContextRetrievalContractError(f"{name} contains duplicate ArtifactRef")
    return tuple(sorted(copied, key=lambda item: (item.artifact_id, item.revision)))


def _failure_ref(stage: str, error: BaseException | None = None) -> str:
    category = "none" if error is None else type(error).__name__
    return f"failure://sha256/{hashlib.sha256(f'{stage}:{category}'.encode()).hexdigest()}"


class ContextRetrievalError(Exception):
    """Base class for context and retrieval failures."""


class ContextRetrievalContractError(ContextRetrievalError, ValueError):
    """A context or retrieval contract is malformed."""


class ContextRetrievalScopeError(ContextRetrievalError):
    """A context or retrieval operation crossed Project or source scope."""


class ContextRetrievalIntegrityError(ContextRetrievalError):
    """Derived state or provenance failed exact verification."""


class ContextRetrievalConflictError(ContextRetrievalError):
    """Idempotency, build fencing, or activation state conflicts."""


class ContextRetrievalNotFoundError(ContextRetrievalError):
    """An exact context, index, chunk, or receipt does not exist."""


class ContextLimitError(ContextRetrievalError):
    """Required model-visible content cannot fit the explicit budget."""


class RetrievalIndexState(str, Enum):
    BUILDING = "BUILDING"
    READY = "READY"
    STALE = "STALE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ContextReductionPolicy(str, Enum):
    BLOCK = "BLOCK"
    EXCLUDE_OPTIONAL = "EXCLUDE_OPTIONAL"
    USE_EXPLICIT_REDUCTIONS = "USE_EXPLICIT_REDUCTIONS"


class ContextTokenCountSource(str, Enum):
    EXACT_CALLER_TOKENIZER = "EXACT_CALLER_TOKENIZER"
    ESTIMATE_UNICODE_SEGMENTS = "ESTIMATE_UNICODE_SEGMENTS"


@dataclass(frozen=True, order=True)
class RetrievalIndexRef:
    project_ref: ProjectRef
    index_id: str
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise ContextRetrievalContractError("RetrievalIndexRef requires ProjectRef")
        if not isinstance(self.index_id, str) or _INDEX_ID.fullmatch(self.index_id) is None:
            raise ContextRetrievalContractError("RetrievalIndex identity is malformed")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise ContextRetrievalContractError("RetrievalIndex version is malformed")

    @property
    def value(self) -> str:
        return f"retrieval-index://{self.project_ref.value}/{self.index_id}/{self.version}"


@dataclass(frozen=True, order=True)
class RetrievalReceiptRef:
    project_ref: ProjectRef
    receipt_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or _RECEIPT_ID.fullmatch(self.receipt_id) is None:
            raise ContextRetrievalContractError("RetrievalReceiptRef is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "RetrievalReceiptRef":
        return cls(project_ref, f"rrc_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"retrieval-receipt://{self.project_ref.value}/{self.receipt_id}"


@dataclass(frozen=True, order=True)
class ContextManifestRef:
    project_ref: ProjectRef
    manifest_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or _MANIFEST_ID.fullmatch(self.manifest_id) is None:
            raise ContextRetrievalContractError("ContextManifestRef is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "ContextManifestRef":
        return cls(project_ref, f"cmf_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"context-manifest://{self.project_ref.value}/{self.manifest_id}"


@dataclass(frozen=True, order=True)
class ContextReceiptRef:
    project_ref: ProjectRef
    receipt_id: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.project_ref, ProjectRef)
            or _CONTEXT_RECEIPT_ID.fullmatch(self.receipt_id) is None
        ):
            raise ContextRetrievalContractError("ContextReceiptRef is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "ContextReceiptRef":
        return cls(project_ref, f"crc_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"context-receipt://{self.project_ref.value}/{self.receipt_id}"


@dataclass(frozen=True, order=True)
class SourceSnapshot:
    artifact_ref: ArtifactRef
    content_ref: ContentRef
    artifact_record_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_ref, ArtifactRef) or not isinstance(self.content_ref, ContentRef):
            raise ContextRetrievalContractError("source snapshot identity is malformed")
        if _SHA256.fullmatch(self.artifact_record_sha256) is None:
            raise ContextRetrievalContractError("source snapshot record digest is malformed")

    def payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref.value,
            "artifact_record_sha256": self.artifact_record_sha256,
            "content_digest": self.content_ref.digest,
            "content_media_type": self.content_ref.media_type,
            "content_size_bytes": self.content_ref.size_bytes,
        }


@dataclass(frozen=True)
class RetrievalIndex:
    """One versioned derived index descriptor and current build state."""

    index_ref: RetrievalIndexRef
    index_key: str
    state: RetrievalIndexState
    source_snapshots: tuple[SourceSnapshot, ...]
    chunker_version: str
    embedding_deployment_ref: str
    embedding_runtime_sha256: str
    dimension: int
    metric: str
    created_at: str
    verified_at: str | None
    failure_ref: str | None
    build_fence: int
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.index_ref, RetrievalIndexRef):
            raise ContextRetrievalContractError("RetrievalIndexRef is required")
        if _INDEX_KEY.fullmatch(self.index_key) is None or not isinstance(self.state, RetrievalIndexState):
            raise ContextRetrievalContractError("RetrievalIndex key or state is malformed")
        snapshots = tuple(self.source_snapshots)
        if not snapshots or len(snapshots) > 10_000 or not all(
            isinstance(item, SourceSnapshot) for item in snapshots
        ):
            raise ContextRetrievalContractError("RetrievalIndex sources are malformed")
        if any(item.artifact_ref.project_ref != self.index_ref.project_ref for item in snapshots):
            raise ContextRetrievalScopeError("RetrievalIndex source crossed Project scope")
        if len({item.artifact_ref for item in snapshots}) != len(snapshots):
            raise ContextRetrievalContractError("RetrievalIndex source is duplicated")
        object.__setattr__(
            self,
            "source_snapshots",
            tuple(sorted(snapshots, key=lambda item: item.artifact_ref.value)),
        )
        if _VERSION.fullmatch(self.chunker_version) is None:
            raise ContextRetrievalContractError("chunker version is malformed")
        if _ABSOLUTE_REF.fullmatch(self.embedding_deployment_ref) is None:
            raise ContextRetrievalContractError("embedding deployment ref is malformed")
        if _SHA256.fullmatch(self.embedding_runtime_sha256) is None:
            raise ContextRetrievalContractError("embedding runtime digest is malformed")
        if (
            not isinstance(self.dimension, int)
            or isinstance(self.dimension, bool)
            or not 0 < self.dimension <= _MAX_VECTOR_DIMENSION
            or self.metric != "COSINE"
            or not isinstance(self.build_fence, int)
            or isinstance(self.build_fence, bool)
            or self.build_fence < 1
        ):
            raise ContextRetrievalContractError("index vector or fence contract is malformed")
        _timestamp(self.created_at, "index created_at")
        if self.verified_at is not None:
            _timestamp(self.verified_at, "index verified_at")
        if (self.state is RetrievalIndexState.READY) != (self.verified_at is not None):
            raise ContextRetrievalIntegrityError("only READY indexes carry verified_at")
        if self.failure_ref is not None and _FAILURE_REF.fullmatch(self.failure_ref) is None:
            raise ContextRetrievalContractError("index failure ref is malformed")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.index_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "build_fence": self.build_fence,
            "chunker_version": self.chunker_version,
            "created_at": self.created_at,
            "dimension": self.dimension,
            "embedding_deployment_ref": self.embedding_deployment_ref,
            "embedding_runtime_sha256": self.embedding_runtime_sha256,
            "failure_ref": self.failure_ref,
            "index_key": self.index_key,
            "index_ref": self.index_ref.value,
            "metric": self.metric,
            "source_snapshots": [item.payload() for item in self.source_snapshots],
            "state": self.state.value,
            "verified_at": self.verified_at,
        }


@dataclass(frozen=True)
class RetrievalChunk:
    chunk_id: str
    index_ref: RetrievalIndexRef
    source_snapshot: SourceSnapshot
    content_ref: ContentRef
    chunker_version: str
    ordinal: int
    character_offset: int
    character_length: int
    chunk_digest: str
    embedding_deployment_ref: str
    embedding_runtime_sha256: str
    embedding_model_call_ref: ModelCallRef
    vector: tuple[float, ...]
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.chunk_id, str) or re.fullmatch(r"chk_[0-9a-f]{32}", self.chunk_id) is None:
            raise ContextRetrievalContractError("chunk identity is malformed")
        if self.source_snapshot.artifact_ref.project_ref != self.index_ref.project_ref:
            raise ContextRetrievalScopeError("chunk source crossed Project scope")
        if not isinstance(self.content_ref, ContentRef) or self.content_ref.digest != self.chunk_digest:
            raise ContextRetrievalIntegrityError("chunk ContentRef and digest differ")
        if self.chunker_version != self.chunker_version.strip() or _VERSION.fullmatch(self.chunker_version) is None:
            raise ContextRetrievalContractError("chunker version is malformed")
        for value, name in (
            (self.ordinal, "ordinal"),
            (self.character_offset, "character_offset"),
            (self.character_length, "character_length"),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ContextRetrievalContractError(f"chunk {name} is malformed")
        if self.character_length < 1:
            raise ContextRetrievalContractError("chunk length must be positive")
        if _ABSOLUTE_REF.fullmatch(self.embedding_deployment_ref) is None or _SHA256.fullmatch(self.embedding_runtime_sha256) is None:
            raise ContextRetrievalContractError("chunk embedding provenance is malformed")
        if self.embedding_model_call_ref.project_ref != self.index_ref.project_ref:
            raise ContextRetrievalScopeError("chunk ModelCall crossed Project scope")
        vector = tuple(float(item) for item in self.vector)
        if not vector or len(vector) > _MAX_VECTOR_DIMENSION or any(not math.isfinite(item) for item in vector):
            raise ContextRetrievalIntegrityError("chunk vector is empty, non-finite, or unbounded")
        object.__setattr__(self, "vector", vector)
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def value(self) -> str:
        return f"retrieval-chunk://{self.index_ref.project_ref.value}/{self.index_ref.index_id}/{self.index_ref.version}/{self.chunk_id}"

    def payload(self) -> dict[str, object]:
        return {
            "character_length": self.character_length,
            "character_offset": self.character_offset,
            "chunk_digest": self.chunk_digest,
            "chunk_id": self.chunk_id,
            "chunker_version": self.chunker_version,
            "content_digest": self.content_ref.digest,
            "content_media_type": self.content_ref.media_type,
            "content_size_bytes": self.content_ref.size_bytes,
            "embedding_deployment_ref": self.embedding_deployment_ref,
            "embedding_model_call_ref": self.embedding_model_call_ref.value,
            "embedding_runtime_sha256": self.embedding_runtime_sha256,
            "index_ref": self.index_ref.value,
            "ordinal": self.ordinal,
            "source_snapshot": self.source_snapshot.payload(),
            "vector": list(self.vector),
        }


@dataclass(frozen=True, order=True)
class RetrievalCandidate:
    chunk_ref: str
    source_artifact_ref: ArtifactRef
    content_ref: ContentRef = field(compare=False)
    score: float = field(compare=False)
    rank: int = field(compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.chunk_ref, str) or not self.chunk_ref.startswith("retrieval-chunk://"):
            raise ContextRetrievalContractError("candidate chunk ref is malformed")
        if not isinstance(self.source_artifact_ref, ArtifactRef) or not isinstance(self.content_ref, ContentRef):
            raise ContextRetrievalContractError("candidate source or content is malformed")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)) or not math.isfinite(float(self.score)):
            raise ContextRetrievalIntegrityError("candidate score is non-finite")
        if not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank < 1:
            raise ContextRetrievalContractError("candidate rank is malformed")

    def payload(self) -> dict[str, object]:
        return {
            "chunk_ref": self.chunk_ref,
            "content_digest": self.content_ref.digest,
            "content_media_type": self.content_ref.media_type,
            "content_size_bytes": self.content_ref.size_bytes,
            "rank": self.rank,
            "score": float(self.score),
            "source_artifact_ref": self.source_artifact_ref.value,
        }


@dataclass(frozen=True)
class RetrievalReceipt:
    receipt_ref: RetrievalReceiptRef
    query_ref: ContentRef
    source_scope: tuple[ArtifactRef, ...]
    index_ref: RetrievalIndexRef
    candidates: tuple[RetrievalCandidate, ...]
    reranked_candidates: tuple[RetrievalCandidate, ...]
    embedding_deployment_ref: str
    embedding_runtime_sha256: str
    embedding_model_call_ref: ModelCallRef
    reranker_deployment_ref: str | None
    reranker_runtime_sha256: str | None
    reranker_model_call_ref: ModelCallRef | None
    run_ref: RunRef
    node_ref: NodeRef
    node_attempt_id: str
    node_fence: int
    receipt_content_ref: ContentRef
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.receipt_ref.project_ref
        if self.index_ref.project_ref != project or self.run_ref.project_ref != project or self.node_ref.project_ref != project:
            raise ContextRetrievalScopeError("retrieval receipt crossed Project scope")
        scope = _artifact_refs(self.source_scope, project, "retrieval source scope")
        object.__setattr__(self, "source_scope", scope)
        candidates = tuple(self.candidates)
        reranked = tuple(self.reranked_candidates)
        if len(candidates) > 1000 or len(reranked) > len(candidates):
            raise ContextRetrievalContractError("retrieval candidates are unbounded")
        if any(item.source_artifact_ref not in scope for item in (*candidates, *reranked)):
            raise ContextRetrievalScopeError("retrieval candidate escaped source scope")
        candidate_ids = {item.chunk_ref for item in candidates}
        if len(candidate_ids) != len(candidates) or any(item.chunk_ref not in candidate_ids for item in reranked):
            raise ContextRetrievalIntegrityError("reranker changed candidate-set identity")
        if len({item.chunk_ref for item in reranked}) != len(reranked):
            raise ContextRetrievalIntegrityError("reranker duplicated a candidate")
        if self.embedding_model_call_ref.project_ref != project:
            raise ContextRetrievalScopeError("embedding ModelCall crossed Project scope")
        optional_rerank = (
            self.reranker_deployment_ref,
            self.reranker_runtime_sha256,
            self.reranker_model_call_ref,
        )
        if any(item is not None for item in optional_rerank) != all(item is not None for item in optional_rerank):
            raise ContextRetrievalIntegrityError("reranker provenance is incomplete")
        if self.reranker_model_call_ref is not None and self.reranker_model_call_ref.project_ref != project:
            raise ContextRetrievalScopeError("reranker ModelCall crossed Project scope")
        if _SHA256.fullmatch(self.embedding_runtime_sha256) is None or (
            self.reranker_runtime_sha256 is not None and _SHA256.fullmatch(self.reranker_runtime_sha256) is None
        ):
            raise ContextRetrievalContractError("retrieval runtime digest is malformed")
        if not isinstance(self.receipt_content_ref, ContentRef):
            raise ContextRetrievalContractError("receipt ContentRef is required")
        _timestamp(self.created_at, "retrieval receipt created_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "candidates": [item.payload() for item in self.candidates],
            "created_at": self.created_at,
            "embedding_deployment_ref": self.embedding_deployment_ref,
            "embedding_model_call_ref": self.embedding_model_call_ref.value,
            "embedding_runtime_sha256": self.embedding_runtime_sha256,
            "index_ref": self.index_ref.value,
            "node_attempt_id": self.node_attempt_id,
            "node_fence": self.node_fence,
            "node_ref": self.node_ref.value,
            "query_digest": self.query_ref.digest,
            "query_size_bytes": self.query_ref.size_bytes,
            "receipt_ref": self.receipt_ref.value,
            "reranked_candidates": [item.payload() for item in self.reranked_candidates],
            "reranker_deployment_ref": self.reranker_deployment_ref,
            "reranker_model_call_ref": None if self.reranker_model_call_ref is None else self.reranker_model_call_ref.value,
            "reranker_runtime_sha256": self.reranker_runtime_sha256,
            "run_ref": f"run://{self.run_ref.project_ref.value}/{self.run_ref.run_id}",
            "source_scope": [item.value for item in self.source_scope],
        }


@dataclass(frozen=True)
class IndexBuildRequest:
    index_key: str
    source_artifact_refs: tuple[ArtifactRef, ...]
    chunker_version: str
    maximum_chunk_characters: int
    require_current_sources: bool
    embedding_deployment: ModelDeployment
    embedding_capability_ref: CapabilityRef
    request_id: str

    def __post_init__(self) -> None:
        if _INDEX_KEY.fullmatch(self.index_key) is None or _VERSION.fullmatch(self.chunker_version) is None:
            raise ContextRetrievalContractError("index build key or chunker version is malformed")
        if not isinstance(self.source_artifact_refs, tuple) or not self.source_artifact_refs:
            raise ContextRetrievalContractError("index build requires exact source ArtifactRefs")
        if not all(isinstance(item, ArtifactRef) for item in self.source_artifact_refs):
            raise ContextRetrievalContractError("index build sources must be ArtifactRef")
        if len(set(self.source_artifact_refs)) != len(self.source_artifact_refs):
            raise ContextRetrievalContractError("index build source ArtifactRef is duplicated")
        if (
            not isinstance(self.maximum_chunk_characters, int)
            or isinstance(self.maximum_chunk_characters, bool)
            or not 16 <= self.maximum_chunk_characters <= 1_000_000
            or not isinstance(self.require_current_sources, bool)
        ):
            raise ContextRetrievalContractError("index chunk or currentness contract is malformed")
        if not isinstance(self.embedding_deployment, ModelDeployment) or not isinstance(self.embedding_capability_ref, CapabilityRef):
            raise ContextRetrievalContractError("index embedding deployment or capability is malformed")
        if _REQUEST_ID.fullmatch(self.request_id) is None:
            raise ContextRetrievalContractError("index request identity is malformed")


@dataclass(frozen=True)
class IndexBuildResult:
    index: RetrievalIndex
    chunks: tuple[RetrievalChunk, ...]
    embedding_inputs_ref: ContentRef
    embedding_model_call_ref: ModelCallRef | None


@dataclass(frozen=True)
class RetrievalSearchRequest:
    index_key: str
    query: str
    source_scope: tuple[ArtifactRef, ...]
    maximum_candidates: int
    rerank: bool
    embedding_deployment: ModelDeployment
    embedding_capability_ref: CapabilityRef
    reranker_deployment: ModelDeployment | None
    reranker_capability_ref: CapabilityRef | None
    context_receipt_ref: ContentRef | None
    request_id: str

    def __post_init__(self) -> None:
        if _INDEX_KEY.fullmatch(self.index_key) is None:
            raise ContextRetrievalContractError("retrieval index key is malformed")
        if not isinstance(self.query, str) or not self.query.strip() or len(self.query.encode()) > 1_000_000:
            raise ContextRetrievalContractError("retrieval query is malformed or unbounded")
        if (
            not isinstance(self.source_scope, tuple)
            or not self.source_scope
            or not all(isinstance(item, ArtifactRef) for item in self.source_scope)
            or len(set(self.source_scope)) != len(self.source_scope)
        ):
            raise ContextRetrievalContractError("retrieval source scope is empty or duplicated")
        if not 1 <= self.maximum_candidates <= 1000:
            raise ContextRetrievalContractError("candidate bound is malformed")
        if not isinstance(self.rerank, bool):
            raise ContextRetrievalContractError("rerank must be boolean")
        if self.rerank != (self.reranker_deployment is not None and self.reranker_capability_ref is not None):
            raise ContextRetrievalContractError("reranker deployment and capability are incomplete")
        if _REQUEST_ID.fullmatch(self.request_id) is None:
            raise ContextRetrievalContractError("retrieval request identity is malformed")


@dataclass(frozen=True, order=True)
class ContextBudget:
    maximum_tokens: int
    reserved_output_tokens: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.maximum_tokens, int)
            or isinstance(self.maximum_tokens, bool)
            or not 1 <= self.maximum_tokens <= 10_000_000
            or not isinstance(self.reserved_output_tokens, int)
            or isinstance(self.reserved_output_tokens, bool)
            or not 0 <= self.reserved_output_tokens < self.maximum_tokens
        ):
            raise ContextRetrievalContractError("context budget is malformed")

    @property
    def available_tokens(self) -> int:
        return self.maximum_tokens - self.reserved_output_tokens


@dataclass(frozen=True, order=True)
class ContextReductionEvidence:
    source_ref: str
    reduced_content_ref: ContentRef
    model_call_ref: ModelCallRef

    def __post_init__(self) -> None:
        if _ABSOLUTE_REF.fullmatch(self.source_ref) is None or not isinstance(self.reduced_content_ref, ContentRef):
            raise ContextRetrievalContractError("context reduction source or content is malformed")

    def payload(self) -> dict[str, object]:
        return {
            "model_call_ref": self.model_call_ref.value,
            "reduced_content_digest": self.reduced_content_ref.digest,
            "reduced_content_media_type": self.reduced_content_ref.media_type,
            "reduced_content_size_bytes": self.reduced_content_ref.size_bytes,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True)
class ContextManifest:
    manifest_ref: ContextManifestRef
    task_ref: TaskRef
    task_digest: str
    run_ref: RunRef
    graph_ref: GraphRef
    node_ref: NodeRef
    node_attempt_id: str
    node_fence: int
    objective_ref: str
    explicit_input_refs: tuple[str, ...]
    project_knowledge_refs: tuple[str, ...]
    engine_knowledge_refs: tuple[str, ...]
    run_refs: tuple[str, ...]
    retrieval_scope: tuple[str, ...]
    retrieval_receipt_refs: tuple[str, ...]
    tool_output_refs: tuple[str, ...]
    data_policy_ref: str | None
    egress_policy_ref: str | None
    budget: ContextBudget
    reduction_policy: ContextReductionPolicy
    optional_refs: tuple[str, ...]
    created_at: str
    manifest_digest: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.manifest_ref.project_ref
        if (
            self.task_ref.project_ref != project
            or self.run_ref.project_ref != project
            or self.graph_ref.project_ref != project
            or self.node_ref.project_ref != project
        ):
            raise ContextRetrievalScopeError("ContextManifest crossed Project scope")
        if self.node_ref.graph_ref != self.graph_ref or _SHA256.fullmatch(self.task_digest) is None:
            raise ContextRetrievalIntegrityError("ContextManifest exact execution binding differs")
        if not isinstance(self.node_fence, int) or isinstance(self.node_fence, bool) or self.node_fence < 1:
            raise ContextRetrievalContractError("ContextManifest node fence is malformed")
        if _ABSOLUTE_REF.fullmatch(self.objective_ref) is None:
            raise ContextRetrievalContractError("ContextManifest objective ref is malformed")
        for name in (
            "explicit_input_refs",
            "project_knowledge_refs",
            "engine_knowledge_refs",
            "run_refs",
            "retrieval_scope",
            "retrieval_receipt_refs",
            "tool_output_refs",
            "optional_refs",
        ):
            object.__setattr__(self, name, _refs(cast(Sequence[str], getattr(self, name)), name))
        all_material = set(
            (
                self.objective_ref,
                *self.explicit_input_refs,
                *self.project_knowledge_refs,
                *self.engine_knowledge_refs,
                *self.run_refs,
                *self.retrieval_receipt_refs,
                *self.tool_output_refs,
            )
        )
        if not set(self.optional_refs).issubset(all_material):
            raise ContextRetrievalContractError("optional context ref is not in manifest material")
        if not isinstance(self.budget, ContextBudget) or not isinstance(self.reduction_policy, ContextReductionPolicy):
            raise ContextRetrievalContractError("ContextManifest budget or reduction policy is malformed")
        _timestamp(self.created_at, "manifest created_at")
        semantic = self.payload()
        semantic.pop("created_at")
        semantic.pop("manifest_ref")
        object.__setattr__(self, "manifest_digest", _digest(semantic))

    @property
    def project_ref(self) -> ProjectRef:
        return self.manifest_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "budget": {
                "maximum_tokens": self.budget.maximum_tokens,
                "reserved_output_tokens": self.budget.reserved_output_tokens,
            },
            "created_at": self.created_at,
            "data_policy_ref": self.data_policy_ref,
            "egress_policy_ref": self.egress_policy_ref,
            "engine_knowledge_refs": list(self.engine_knowledge_refs),
            "explicit_input_refs": list(self.explicit_input_refs),
            "graph_ref": self.graph_ref.value,
            "manifest_ref": self.manifest_ref.value,
            "node_attempt_id": self.node_attempt_id,
            "node_fence": self.node_fence,
            "node_ref": self.node_ref.value,
            "objective_ref": self.objective_ref,
            "optional_refs": list(self.optional_refs),
            "project_knowledge_refs": list(self.project_knowledge_refs),
            "reduction_policy": self.reduction_policy.value,
            "retrieval_receipt_refs": list(self.retrieval_receipt_refs),
            "retrieval_scope": list(self.retrieval_scope),
            "run_ref": f"run://{self.run_ref.project_ref.value}/{self.run_ref.run_id}",
            "run_refs": list(self.run_refs),
            "task_digest": self.task_digest,
            "task_ref": f"task://{self.task_ref.project_ref.value}/{self.task_ref.task_id}/{self.task_ref.revision}",
            "tool_output_refs": list(self.tool_output_refs),
        }


@dataclass(frozen=True)
class ContextReceipt:
    receipt_ref: ContextReceiptRef
    manifest_ref: ContextManifestRef
    manifest_digest: str
    status: str
    context_ref: ContentRef | None
    receipt_content_ref: ContentRef
    included_refs: tuple[str, ...]
    excluded_refs: tuple[str, ...]
    retrieval_refs: tuple[str, ...]
    tool_refs: tuple[str, ...]
    token_count: int
    token_count_source: ContextTokenCountSource
    token_count_exact: bool
    tokenizer_ref: str | None
    reduction_evidence: tuple[ContextReductionEvidence, ...]
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.receipt_ref.project_ref != self.manifest_ref.project_ref or _SHA256.fullmatch(self.manifest_digest) is None:
            raise ContextRetrievalScopeError("ContextReceipt manifest scope or digest differs")
        if self.status not in {"COMPILED", "CONTEXT_LIMIT"}:
            raise ContextRetrievalContractError("ContextReceipt status is malformed")
        if (self.status == "COMPILED") != (self.context_ref is not None):
            raise ContextRetrievalIntegrityError("ContextReceipt status and content differ")
        if not isinstance(self.receipt_content_ref, ContentRef):
            raise ContextRetrievalContractError("ContextReceipt content evidence is required")
        for name in ("included_refs", "excluded_refs", "retrieval_refs", "tool_refs"):
            object.__setattr__(self, name, _refs(cast(Sequence[str], getattr(self, name)), name))
        if set(self.included_refs) & set(self.excluded_refs):
            raise ContextRetrievalIntegrityError("one context ref cannot be included and excluded")
        if not isinstance(self.token_count, int) or isinstance(self.token_count, bool) or self.token_count < 0:
            raise ContextRetrievalContractError("context token count is malformed")
        if not isinstance(self.token_count_source, ContextTokenCountSource) or not isinstance(self.token_count_exact, bool):
            raise ContextRetrievalContractError("context token count source is malformed")
        if self.token_count_exact != (self.token_count_source is ContextTokenCountSource.EXACT_CALLER_TOKENIZER):
            raise ContextRetrievalIntegrityError("context exact-token claim differs from source")
        if self.token_count_exact:
            if (
                not isinstance(self.tokenizer_ref, str)
                or _ABSOLUTE_REF.fullmatch(self.tokenizer_ref) is None
            ):
                raise ContextRetrievalContractError("exact tokenizer identity is required")
        elif self.tokenizer_ref is not None:
            raise ContextRetrievalIntegrityError("estimated token count cannot name an exact tokenizer")
        reductions = tuple(self.reduction_evidence)
        if not all(isinstance(item, ContextReductionEvidence) for item in reductions):
            raise ContextRetrievalContractError("context reduction evidence is malformed")
        object.__setattr__(self, "reduction_evidence", reductions)
        _timestamp(self.created_at, "context receipt created_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.receipt_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "context_digest": None if self.context_ref is None else self.context_ref.digest,
            "context_size_bytes": None if self.context_ref is None else self.context_ref.size_bytes,
            "created_at": self.created_at,
            "excluded_refs": list(self.excluded_refs),
            "included_refs": list(self.included_refs),
            "manifest_digest": self.manifest_digest,
            "manifest_ref": self.manifest_ref.value,
            "receipt_ref": self.receipt_ref.value,
            "reduction_evidence": [item.payload() for item in self.reduction_evidence],
            "retrieval_refs": list(self.retrieval_refs),
            "status": self.status,
            "token_count": self.token_count,
            "token_count_exact": self.token_count_exact,
            "token_count_source": self.token_count_source.value,
            "tokenizer_ref": self.tokenizer_ref,
            "tool_refs": list(self.tool_refs),
        }


@dataclass(frozen=True)
class ContextCompileRequest:
    explicit_input_refs: tuple[ArtifactRef, ...]
    project_knowledge: tuple[ProjectKnowledge, ...]
    engine_knowledge: tuple[Knowledge, ...]
    run_memory: RunMemory
    retrieval_receipt_refs: tuple[RetrievalReceiptRef, ...]
    tool_output_refs: tuple[ArtifactRef, ...]
    retrieval_scope: tuple[ArtifactRef, ...]
    budget: ContextBudget
    reduction_policy: ContextReductionPolicy
    optional_refs: tuple[str, ...]
    reductions: tuple[ContextReductionEvidence, ...]
    request_id: str
    exact_token_count: int | None = None
    exact_tokenizer_ref: str | None = None

    def __post_init__(self) -> None:
        if _REQUEST_ID.fullmatch(self.request_id) is None:
            raise ContextRetrievalContractError("context request identity is malformed")
        if (self.exact_token_count is None) != (self.exact_tokenizer_ref is None):
            raise ContextRetrievalContractError("exact token count and tokenizer ref are incomplete")
        if self.exact_token_count is not None and (
            not isinstance(self.exact_token_count, int)
            or isinstance(self.exact_token_count, bool)
            or self.exact_token_count < 0
            or _ABSOLUTE_REF.fullmatch(cast(str, self.exact_tokenizer_ref)) is None
        ):
            raise ContextRetrievalContractError("exact tokenizer evidence is malformed")


def _parse_project_scoped_uri(value: str, scheme: str) -> tuple[ProjectRef, tuple[str, ...]]:
    prefix = f"{scheme}://"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ContextRetrievalIntegrityError(f"persisted {scheme} reference is malformed")
    parts = tuple(value.removeprefix(prefix).split("/"))
    if len(parts) < 2:
        raise ContextRetrievalIntegrityError(f"persisted {scheme} reference is malformed")
    return ProjectRef(parts[0]), parts[1:]


def _parse_artifact_ref(value: str) -> ArtifactRef:
    project_ref, parts = _parse_project_scoped_uri(value, "artifact")
    if len(parts) != 2:
        raise ContextRetrievalIntegrityError("persisted ArtifactRef is malformed")
    return ArtifactRef(project_ref, parts[0], int(parts[1]))


def _parse_content(payload: Mapping[str, object]) -> ContentRef:
    return ContentRef(
        "sha256",
        cast(str, payload["content_digest"]),
        cast(int, payload["content_size_bytes"]),
        cast(str, payload["content_media_type"]),
    )


class RetrievalService:
    """Versioned build, verify, activate, scoped search, rerank, and rebuild service."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
    ) -> None:
        self.database_path = Path(database_path).resolve()
        if not isinstance(object_store, ObjectStorageBackend):
            raise ContextRetrievalContractError("ObjectStorageBackend is required")
        self.object_store = object_store
        self.projects = ProjectStore(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
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
                CREATE TABLE IF NOT EXISTS retrieval_index_builds (
                    project_id TEXT NOT NULL,
                    index_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    index_key TEXT NOT NULL,
                    build_fence INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    descriptor_json TEXT NOT NULL,
                    embedding_inputs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, index_id, version),
                    UNIQUE (project_id, request_id)
                );

                CREATE TABLE IF NOT EXISTS retrieval_build_heads (
                    project_id TEXT NOT NULL,
                    index_key TEXT NOT NULL,
                    index_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    build_fence INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    PRIMARY KEY (project_id, index_key)
                );

                CREATE TABLE IF NOT EXISTS retrieval_index_states (
                    project_id TEXT NOT NULL,
                    index_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, index_id, version, sequence)
                );

                CREATE TABLE IF NOT EXISTS retrieval_index_state_heads (
                    project_id TEXT NOT NULL,
                    index_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, index_id, version)
                );

                CREATE TABLE IF NOT EXISTS retrieval_active_heads (
                    project_id TEXT NOT NULL,
                    index_key TEXT NOT NULL,
                    index_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    activated_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, index_key)
                );

                CREATE TABLE IF NOT EXISTS retrieval_chunks (
                    project_id TEXT NOT NULL,
                    index_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    chunk_id TEXT NOT NULL,
                    source_artifact_id TEXT NOT NULL,
                    source_revision INTEGER NOT NULL,
                    chunk_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, index_id, version, chunk_id)
                );

                CREATE INDEX IF NOT EXISTS retrieval_chunks_source_scope
                    ON retrieval_chunks (
                        project_id, index_id, version,
                        source_artifact_id, source_revision
                    );

                CREATE TABLE IF NOT EXISTS retrieval_receipts (
                    project_id TEXT NOT NULL,
                    receipt_id TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    receipt_content_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, receipt_id)
                );

                CREATE TABLE IF NOT EXISTS retrieval_search_claims (
                    project_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    receipt_id TEXT NOT NULL,
                    PRIMARY KEY (project_id, request_id)
                );

                CREATE TABLE IF NOT EXISTS retrieval_build_cancellations (
                    project_id TEXT NOT NULL,
                    index_key TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, index_key, request_id)
                );

                CREATE TRIGGER IF NOT EXISTS retrieval_index_builds_no_update
                BEFORE UPDATE ON retrieval_index_builds
                BEGIN SELECT RAISE(ABORT, 'retrieval builds are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS retrieval_index_builds_no_delete
                BEFORE DELETE ON retrieval_index_builds
                BEGIN SELECT RAISE(ABORT, 'retrieval builds cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS retrieval_index_states_no_update
                BEFORE UPDATE ON retrieval_index_states
                BEGIN SELECT RAISE(ABORT, 'retrieval states are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS retrieval_index_states_no_delete
                BEFORE DELETE ON retrieval_index_states
                BEGIN SELECT RAISE(ABORT, 'retrieval states are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS retrieval_receipts_no_update
                BEFORE UPDATE ON retrieval_receipts
                BEGIN SELECT RAISE(ABORT, 'retrieval receipts are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS retrieval_receipts_no_delete
                BEFORE DELETE ON retrieval_receipts
                BEGIN SELECT RAISE(ABORT, 'retrieval receipts cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS retrieval_search_claims_no_update
                BEFORE UPDATE ON retrieval_search_claims
                BEGIN SELECT RAISE(ABORT, 'retrieval search claims are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS retrieval_search_claims_no_delete
                BEFORE DELETE ON retrieval_search_claims
                BEGIN SELECT RAISE(ABORT, 'retrieval search claims cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectScopeError as exc:
            raise ContextRetrievalScopeError("Project retrieval scope mismatch") from exc

    def _task_for_attempt(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
    ) -> Task:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise ContextRetrievalContractError("NodeExecutionAttempt is required")
        self._authorize(access, attempt.node_ref.project_ref)
        task = self.tasks.get_task(access, attempt.task_ref)
        if task.canonical_digest != attempt.task_digest:
            raise ContextRetrievalIntegrityError("retrieval Task digest differs")
        execution = self.executions.get_node_execution(access, attempt.node_ref)
        if (
            execution.status not in {"RUNNING", "WAITING_EXTERNAL"}
            or execution.current_attempt_id != attempt.attempt_id
            or execution.current_fence != attempt.fence
            or execution.current_run_attempt_id != attempt.run_attempt_id
            or execution.current_run_fence != attempt.run_fence
        ):
            raise ContextRetrievalConflictError("stale Node attempt cannot create retrieval state")
        return task

    def _snapshot(
        self,
        access: ProjectAccess,
        artifact_ref: ArtifactRef,
    ) -> SourceSnapshot:
        if not isinstance(artifact_ref, ArtifactRef):
            raise TypeError("ArtifactRef is required for retrieval source authority")
        artifact = self.artifacts.get_artifact(access, artifact_ref)
        if artifact.content_ref is None:
            raise ContextRetrievalContractError("retrieval source Artifact has no content")
        try:
            self.object_store.verify(artifact.content_ref)
        except ObjectStorageError as exc:
            raise ContextRetrievalIntegrityError("retrieval source content failed verification") from exc
        return SourceSnapshot(artifact.artifact_ref, artifact.content_ref, artifact.record_sha256)

    def _current_artifact_revision(self, artifact_ref: ArtifactRef) -> int:
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT current_revision FROM artifact_heads
                WHERE project_id = ? AND artifact_id = ?
                """,
                (artifact_ref.project_ref.value, artifact_ref.artifact_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ContextRetrievalIntegrityError("retrieval source Artifact head is absent")
        return cast(int, row["current_revision"])

    def _sources_current(self, snapshots: Sequence[SourceSnapshot]) -> bool:
        return all(
            self._current_artifact_revision(item.artifact_ref) == item.artifact_ref.revision
            for item in snapshots
        )

    @staticmethod
    def _index_id(project_ref: ProjectRef, index_key: str) -> str:
        digest = hashlib.sha256(f"{project_ref.value}\0{index_key}".encode()).hexdigest()
        return f"idx_{digest[:32]}"

    def _begin_build(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: IndexBuildRequest,
        snapshots: tuple[SourceSnapshot, ...],
        chunks: Sequence[tuple[SourceSnapshot, int, int, str, ContentRef]],
        inputs_ref: ContentRef,
    ) -> tuple[RetrievalIndex, bool]:
        project_ref = attempt.node_ref.project_ref
        request_payload = {
            "chunker_version": request.chunker_version,
            "embedding_capability_ref": request.embedding_capability_ref.value,
            "embedding_deployment_ref": request.embedding_deployment.deployment_ref.value,
            "embedding_inputs_digest": inputs_ref.digest,
            "index_key": request.index_key,
            "maximum_chunk_characters": request.maximum_chunk_characters,
            "node_attempt_record_sha256": attempt.record_sha256,
            "require_current_sources": request.require_current_sources,
            "sources": [item.payload() for item in snapshots],
        }
        request_sha256 = _digest(request_payload)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior_claim = connection.execute(
                """
                SELECT * FROM retrieval_index_builds
                WHERE project_id = ? AND request_id = ?
                """,
                (project_ref.value, request.request_id),
            ).fetchone()
            if prior_claim is not None:
                if not hmac.compare_digest(cast(str, prior_claim["request_sha256"]), request_sha256):
                    raise ContextRetrievalConflictError("index build idempotency conflicts")
                index_ref = RetrievalIndexRef(
                    project_ref,
                    cast(str, prior_claim["index_id"]),
                    cast(int, prior_claim["version"]),
                )
                connection.commit()
                return self.getIndex(access, index_ref), False
            head = connection.execute(
                "SELECT * FROM retrieval_build_heads WHERE project_id = ? AND index_key = ?",
                (project_ref.value, request.index_key),
            ).fetchone()
            version = 1 if head is None else cast(int, head["version"]) + 1
            fence = 1 if head is None else cast(int, head["build_fence"]) + 1
            index_ref = RetrievalIndexRef(
                project_ref,
                self._index_id(project_ref, request.index_key),
                version,
            )
            created_at = _now()
            index = RetrievalIndex(
                index_ref,
                request.index_key,
                RetrievalIndexState.BUILDING,
                snapshots,
                request.chunker_version,
                request.embedding_deployment.deployment_ref.value,
                request.embedding_deployment.runtime_identity.record_sha256,
                cast(int, request.embedding_deployment.embedding_dimensions),
                "COSINE",
                created_at,
                None,
                None,
                fence,
            )
            descriptor = {
                "index": index.payload(),
                "request": request_payload,
                "chunk_count": len(chunks),
            }
            connection.execute(
                """
                INSERT INTO retrieval_index_builds (
                    project_id, index_id, version, index_key, build_fence,
                    request_id, request_sha256, descriptor_json,
                    embedding_inputs_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_ref.value,
                    index_ref.index_id,
                    version,
                    request.index_key,
                    fence,
                    request.request_id,
                    request_sha256,
                    _json(descriptor),
                    _json(
                        {
                            "algorithm": inputs_ref.algorithm,
                            "digest": inputs_ref.digest,
                            "media_type": inputs_ref.media_type,
                            "size_bytes": inputs_ref.size_bytes,
                        }
                    ),
                    created_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO retrieval_build_heads (
                    project_id, index_key, index_id, version,
                    build_fence, request_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, index_key) DO UPDATE SET
                    index_id = excluded.index_id,
                    version = excluded.version,
                    build_fence = excluded.build_fence,
                    request_id = excluded.request_id
                """,
                (
                    project_ref.value,
                    request.index_key,
                    index_ref.index_id,
                    version,
                    fence,
                    request.request_id,
                ),
            )
            self._append_index_state_in_transaction(connection, index)
            connection.commit()
            return index, True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _append_index_state_in_transaction(
        connection: sqlite3.Connection,
        index: RetrievalIndex,
    ) -> None:
        head = connection.execute(
            """
            SELECT sequence FROM retrieval_index_state_heads
            WHERE project_id = ? AND index_id = ? AND version = ?
            """,
            (index.project_ref.value, index.index_ref.index_id, index.index_ref.version),
        ).fetchone()
        sequence = 1 if head is None else cast(int, head["sequence"]) + 1
        connection.execute(
            """
            INSERT INTO retrieval_index_states (
                project_id, index_id, version, sequence,
                state_json, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                index.project_ref.value,
                index.index_ref.index_id,
                index.index_ref.version,
                sequence,
                _json(index.payload()),
                index.record_sha256,
            ),
        )
        connection.execute(
            """
            INSERT INTO retrieval_index_state_heads (
                project_id, index_id, version, sequence, record_sha256
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(project_id, index_id, version) DO UPDATE SET
                sequence = excluded.sequence,
                record_sha256 = excluded.record_sha256
            """,
            (
                index.project_ref.value,
                index.index_ref.index_id,
                index.index_ref.version,
                sequence,
                index.record_sha256,
            ),
        )

    def _transition_index(
        self,
        index: RetrievalIndex,
        state: RetrievalIndexState,
        *,
        failure_ref: str | None = None,
        activate: bool = False,
    ) -> RetrievalIndex:
        transitioned = RetrievalIndex(
            index.index_ref,
            index.index_key,
            state,
            index.source_snapshots,
            index.chunker_version,
            index.embedding_deployment_ref,
            index.embedding_runtime_sha256,
            index.dimension,
            index.metric,
            index.created_at,
            _now() if state is RetrievalIndexState.READY else None,
            failure_ref,
            index.build_fence,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if activate:
                head = connection.execute(
                    """
                    SELECT * FROM retrieval_build_heads
                    WHERE project_id = ? AND index_key = ?
                    """,
                    (index.project_ref.value, index.index_key),
                ).fetchone()
                if (
                    head is None
                    or head["index_id"] != index.index_ref.index_id
                    or cast(int, head["version"]) != index.index_ref.version
                    or cast(int, head["build_fence"]) != index.build_fence
                ):
                    raise ContextRetrievalConflictError("stale index builder cannot activate")
            self._append_index_state_in_transaction(connection, transitioned)
            if activate:
                connection.execute(
                    """
                    INSERT INTO retrieval_active_heads (
                        project_id, index_key, index_id, version,
                        record_sha256, activated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id, index_key) DO UPDATE SET
                        index_id = excluded.index_id,
                        version = excluded.version,
                        record_sha256 = excluded.record_sha256,
                        activated_at = excluded.activated_at
                    """,
                    (
                        index.project_ref.value,
                        index.index_key,
                        index.index_ref.index_id,
                        index.index_ref.version,
                        transitioned.record_sha256,
                        cast(str, transitioned.verified_at),
                    ),
                )
            connection.commit()
            return transitioned
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _current_build(self, index: RetrievalIndex) -> bool:
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT * FROM retrieval_build_heads
                WHERE project_id = ? AND index_key = ?
                """,
                (index.project_ref.value, index.index_key),
            ).fetchone()
        finally:
            connection.close()
        return bool(
            row is not None
            and row["index_id"] == index.index_ref.index_id
            and row["version"] == index.index_ref.version
            and row["build_fence"] == index.build_fence
        )

    def cancelIndexBuild(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        *,
        index_key: str,
        request_id: str,
    ) -> None:
        self._authorize(access, project_ref)
        if _INDEX_KEY.fullmatch(index_key) is None or _REQUEST_ID.fullmatch(request_id) is None:
            raise ContextRetrievalContractError("index cancellation identity is malformed")
        connection = self._connect()
        try:
            connection.execute(
                """
                INSERT INTO retrieval_build_cancellations (
                    project_id, index_key, request_id, requested_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id, index_key, request_id) DO NOTHING
                """,
                (project_ref.value, index_key, request_id, _now()),
            )
            connection.commit()
        finally:
            connection.close()

    def _cancelled(self, project_ref: ProjectRef, index_key: str, request_id: str) -> bool:
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT 1 FROM retrieval_build_cancellations
                WHERE project_id = ? AND index_key = ? AND request_id = ?
                """,
                (project_ref.value, index_key, request_id),
            ).fetchone()
            return row is not None
        finally:
            connection.close()

    def buildIndex(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: IndexBuildRequest,
        adapter: ModelAdapter,
        *,
        credentials: Mapping[str, str],
    ) -> IndexBuildResult:
        """Extract, chunk, embed, verify, and atomically activate one derived index."""

        task = self._task_for_attempt(access, attempt)
        project_ref = attempt.node_ref.project_ref
        if request.embedding_deployment.project_ref != project_ref:
            raise ContextRetrievalScopeError("embedding deployment crossed Project scope")
        if (
            ModelOperation.EMBED not in request.embedding_deployment.operations
            or request.embedding_deployment.embedding_dimensions is None
            or request.embedding_capability_ref not in task.required_capabilities
        ):
            raise ContextRetrievalContractError("embedding capability or dimension is unavailable")
        source_refs = _artifact_refs(request.source_artifact_refs, project_ref, "index sources")
        snapshots = tuple(self._snapshot(access, item) for item in source_refs)
        if request.require_current_sources and not self._sources_current(snapshots):
            raise ContextRetrievalConflictError("index source is not its current Artifact revision")
        prepared: list[tuple[SourceSnapshot, int, int, str, ContentRef]] = []
        texts: list[str] = []
        for snapshot in snapshots:
            try:
                source_text = self.object_store.read(snapshot.content_ref).decode("utf-8")
            except (ObjectStorageError, UnicodeDecodeError) as exc:
                raise ContextRetrievalIntegrityError("retrieval UTF-8 extraction failed") from exc
            if not source_text:
                raise ContextRetrievalContractError("retrieval source text is empty")
            ordinal = 0
            for offset in range(0, len(source_text), request.maximum_chunk_characters):
                text_value = source_text[offset : offset + request.maximum_chunk_characters]
                if not text_value:
                    continue
                content_ref = self.object_store.put(
                    text_value.encode(),
                    media_type="text/plain",
                )
                prepared.append((snapshot, ordinal, offset, text_value, content_ref))
                texts.append(text_value)
                ordinal += 1
                if len(prepared) > _MAX_CHUNKS:
                    raise ContextRetrievalContractError("retrieval chunk count is unbounded")
        inputs_ref = self.object_store.put(
            _json(texts).encode(),
            media_type="application/json",
        )
        index, first = self._begin_build(
            access,
            attempt,
            request,
            snapshots,
            prepared,
            inputs_ref,
        )
        if not first:
            chunks = self.listChunks(access, index.index_ref)
            call_ref = None if not chunks else chunks[0].embedding_model_call_ref
            return IndexBuildResult(index, chunks, inputs_ref, call_ref)
        if self._cancelled(project_ref, request.index_key, request.request_id):
            cancelled = self._transition_index(
                index,
                RetrievalIndexState.CANCELLED,
                failure_ref=_failure_ref("build-cancelled"),
            )
            return IndexBuildResult(cancelled, (), inputs_ref, None)
        binding = ModelExecutionBinding(
            project_ref,
            ModelExecutionRef.new(project_ref),
            request.embedding_deployment.deployment_ref,
            request.embedding_capability_ref,
            task.task_ref,
            task.canonical_digest,
            attempt.run_ref,
            attempt.node_ref,
            attempt.attempt_id,
            attempt.fence,
            (inputs_ref, *source_refs),
            None,
            task.data_policy_ref,
            task.egress_policy_ref,
            0,
            300.0,
        )
        result: EmbedResult | None = None
        try:
            result = adapter.embed(
                access,
                attempt,
                EmbedRequest(binding, inputs_ref),
                credentials=credentials,
                idempotency_key=f"retrieval-embed-{request.request_id}",
            )
            if not result.evidence.succeeded:
                failed = self._transition_index(
                    index,
                    RetrievalIndexState.FAILED,
                    failure_ref=_failure_ref("embedding-failed"),
                )
                return IndexBuildResult(
                    failed,
                    (),
                    inputs_ref,
                    result.evidence.model_call_ref,
                )
            if (
                result.source_digest != inputs_ref.digest
                or result.evidence.deployment_ref != request.embedding_deployment.deployment_ref
                or result.evidence.runtime_identity.record_sha256
                != request.embedding_deployment.runtime_identity.record_sha256
                or len(result.vectors) != len(prepared)
            ):
                raise ContextRetrievalIntegrityError("embedding result provenance or cardinality differs")
            expected_dimension = request.embedding_deployment.embedding_dimensions
            if any(
                len(vector) != expected_dimension
                or any(not math.isfinite(float(item)) for item in vector)
                for vector in result.vectors
            ):
                raise ContextRetrievalIntegrityError("embedding vector dimension or finiteness differs")
            if self._cancelled(project_ref, request.index_key, request.request_id):
                cancelled = self._transition_index(
                    index,
                    RetrievalIndexState.CANCELLED,
                    failure_ref=_failure_ref("build-cancelled-after-embedding"),
                )
                return IndexBuildResult(
                    cancelled,
                    (),
                    inputs_ref,
                    result.evidence.model_call_ref,
                )
            if not self._current_build(index):
                stale = self._transition_index(
                    index,
                    RetrievalIndexState.STALE,
                    failure_ref=_failure_ref("stale-build-owner"),
                )
                return IndexBuildResult(
                    stale,
                    (),
                    inputs_ref,
                    result.evidence.model_call_ref,
                )
            if request.require_current_sources and not self._sources_current(snapshots):
                stale = self._transition_index(
                    index,
                    RetrievalIndexState.STALE,
                    failure_ref=_failure_ref("source-changed-during-build"),
                )
                return IndexBuildResult(
                    stale,
                    (),
                    inputs_ref,
                    result.evidence.model_call_ref,
                )
            chunks = tuple(
                RetrievalChunk(
                    chunk_id=(
                        "chk_"
                        + hashlib.sha256(
                            f"{index.index_ref.value}\0{snapshot.artifact_ref.value}\0{ordinal}\0{content_ref.digest}".encode()
                        ).hexdigest()[:32]
                    ),
                    index_ref=index.index_ref,
                    source_snapshot=snapshot,
                    content_ref=content_ref,
                    chunker_version=request.chunker_version,
                    ordinal=ordinal,
                    character_offset=offset,
                    character_length=len(text_value),
                    chunk_digest=content_ref.digest,
                    embedding_deployment_ref=request.embedding_deployment.deployment_ref.value,
                    embedding_runtime_sha256=request.embedding_deployment.runtime_identity.record_sha256,
                    embedding_model_call_ref=result.evidence.model_call_ref,
                    vector=tuple(float(item) for item in vector),
                )
                for (snapshot, ordinal, offset, text_value, content_ref), vector in zip(
                    prepared,
                    result.vectors,
                    strict=True,
                )
            )
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                for chunk in chunks:
                    connection.execute(
                        """
                        INSERT INTO retrieval_chunks (
                            project_id, index_id, version, chunk_id,
                            source_artifact_id, source_revision,
                            chunk_json, record_sha256
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            project_ref.value,
                            index.index_ref.index_id,
                            index.index_ref.version,
                            chunk.chunk_id,
                            chunk.source_snapshot.artifact_ref.artifact_id,
                            chunk.source_snapshot.artifact_ref.revision,
                            _json(chunk.payload()),
                            chunk.record_sha256,
                        ),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
            ready = self._transition_index(
                index,
                RetrievalIndexState.READY,
                activate=True,
            )
            return IndexBuildResult(
                ready,
                chunks,
                inputs_ref,
                result.evidence.model_call_ref,
            )
        except ContextRetrievalError:
            failed = self._transition_index(
                index,
                RetrievalIndexState.FAILED,
                failure_ref=_failure_ref("build-integrity"),
            )
            return IndexBuildResult(
                failed,
                (),
                inputs_ref,
                None if result is None else result.evidence.model_call_ref,
            )
        except Exception as exc:
            failed = self._transition_index(
                index,
                RetrievalIndexState.FAILED,
                failure_ref=_failure_ref("build-failed", exc),
            )
            return IndexBuildResult(
                failed,
                (),
                inputs_ref,
                None if result is None else result.evidence.model_call_ref,
            )

    @staticmethod
    def _source_snapshot_from_payload(payload: Mapping[str, object]) -> SourceSnapshot:
        return SourceSnapshot(
            _parse_artifact_ref(cast(str, payload["artifact_ref"])),
            _parse_content(payload),
            cast(str, payload["artifact_record_sha256"]),
        )

    @classmethod
    def _index_from_payload(cls, payload: Mapping[str, object]) -> RetrievalIndex:
        project_ref, parts = _parse_project_scoped_uri(cast(str, payload["index_ref"]), "retrieval-index")
        if len(parts) != 2:
            raise ContextRetrievalIntegrityError("persisted RetrievalIndexRef is malformed")
        return RetrievalIndex(
            RetrievalIndexRef(project_ref, parts[0], int(parts[1])),
            cast(str, payload["index_key"]),
            RetrievalIndexState(cast(str, payload["state"])),
            tuple(
                cls._source_snapshot_from_payload(cast(dict[str, object], item))
                for item in cast(list[object], payload["source_snapshots"])
            ),
            cast(str, payload["chunker_version"]),
            cast(str, payload["embedding_deployment_ref"]),
            cast(str, payload["embedding_runtime_sha256"]),
            cast(int, payload["dimension"]),
            cast(str, payload["metric"]),
            cast(str, payload["created_at"]),
            cast(str | None, payload["verified_at"]),
            cast(str | None, payload["failure_ref"]),
            cast(int, payload["build_fence"]),
        )

    def getIndex(
        self,
        access: ProjectAccess,
        index_ref: RetrievalIndexRef,
    ) -> RetrievalIndex:
        if not isinstance(index_ref, RetrievalIndexRef):
            raise TypeError("RetrievalIndexRef is required")
        self._authorize(access, index_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT s.state_json, s.record_sha256, h.record_sha256 AS head_record_sha256
                FROM retrieval_index_state_heads h
                JOIN retrieval_index_states s
                  ON s.project_id = h.project_id
                 AND s.index_id = h.index_id
                 AND s.version = h.version
                 AND s.sequence = h.sequence
                WHERE h.project_id = ? AND h.index_id = ? AND h.version = ?
                """,
                (index_ref.project_ref.value, index_ref.index_id, index_ref.version),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ContextRetrievalNotFoundError("RetrievalIndex does not exist")
        try:
            payload = cast(dict[str, object], json.loads(cast(str, row["state_json"])))
            index = self._index_from_payload(payload)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, ContextRetrievalError) as exc:
            raise ContextRetrievalIntegrityError("persisted RetrievalIndex is malformed") from exc
        if (
            index.index_ref != index_ref
            or not hmac.compare_digest(index.record_sha256, cast(str, row["record_sha256"]))
            or not hmac.compare_digest(index.record_sha256, cast(str, row["head_record_sha256"]))
        ):
            raise ContextRetrievalIntegrityError("RetrievalIndex durable evidence changed")
        return index

    def getActiveIndex(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        index_key: str,
    ) -> RetrievalIndex:
        self._authorize(access, project_ref)
        if _INDEX_KEY.fullmatch(index_key) is None:
            raise ContextRetrievalContractError("index key is malformed")
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT * FROM retrieval_active_heads
                WHERE project_id = ? AND index_key = ?
                """,
                (project_ref.value, index_key),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ContextRetrievalNotFoundError("active RetrievalIndex is unavailable")
        index = self.getIndex(
            access,
            RetrievalIndexRef(project_ref, cast(str, row["index_id"]), cast(int, row["version"])),
        )
        if index.state is not RetrievalIndexState.READY or not hmac.compare_digest(
            index.record_sha256,
            cast(str, row["record_sha256"]),
        ):
            raise ContextRetrievalIntegrityError("active RetrievalIndex is not verified READY")
        return index

    @classmethod
    def _chunk_from_payload(cls, payload: Mapping[str, object]) -> RetrievalChunk:
        project_ref, index_parts = _parse_project_scoped_uri(
            cast(str, payload["index_ref"]),
            "retrieval-index",
        )
        call_project, call_parts = _parse_project_scoped_uri(
            cast(str, payload["embedding_model_call_ref"]),
            "model-call",
        )
        if len(index_parts) != 2 or len(call_parts) != 1:
            raise ContextRetrievalIntegrityError("persisted chunk provenance is malformed")
        return RetrievalChunk(
            cast(str, payload["chunk_id"]),
            RetrievalIndexRef(project_ref, index_parts[0], int(index_parts[1])),
            cls._source_snapshot_from_payload(cast(dict[str, object], payload["source_snapshot"])),
            _parse_content(payload),
            cast(str, payload["chunker_version"]),
            cast(int, payload["ordinal"]),
            cast(int, payload["character_offset"]),
            cast(int, payload["character_length"]),
            cast(str, payload["chunk_digest"]),
            cast(str, payload["embedding_deployment_ref"]),
            cast(str, payload["embedding_runtime_sha256"]),
            ModelCallRef(call_project, call_parts[0]),
            tuple(float(item) for item in cast(list[float], payload["vector"])),
        )

    def listChunks(
        self,
        access: ProjectAccess,
        index_ref: RetrievalIndexRef,
        *,
        source_scope: Sequence[ArtifactRef] | None = None,
    ) -> tuple[RetrievalChunk, ...]:
        index = self.getIndex(access, index_ref)
        scope = (
            tuple(item.artifact_ref for item in index.source_snapshots)
            if source_scope is None
            else _artifact_refs(source_scope, index.project_ref, "chunk source scope")
        )
        allowed = set(scope)
        if not allowed.issubset({item.artifact_ref for item in index.source_snapshots}):
            raise ContextRetrievalScopeError("chunk source scope widens RetrievalIndex")
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT * FROM retrieval_chunks
                WHERE project_id = ? AND index_id = ? AND version = ?
                ORDER BY source_artifact_id, source_revision, chunk_id
                """,
                (index.project_ref.value, index_ref.index_id, index_ref.version),
            ).fetchall()
        finally:
            connection.close()
        chunks: list[RetrievalChunk] = []
        for row in rows:
            if ArtifactRef(
                index.project_ref,
                cast(str, row["source_artifact_id"]),
                cast(int, row["source_revision"]),
            ) not in allowed:
                continue
            try:
                chunk = self._chunk_from_payload(
                    cast(dict[str, object], json.loads(cast(str, row["chunk_json"])))
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError, ContextRetrievalError) as exc:
                raise ContextRetrievalIntegrityError("persisted retrieval chunk is malformed") from exc
            if not hmac.compare_digest(chunk.record_sha256, cast(str, row["record_sha256"])):
                raise ContextRetrievalIntegrityError("retrieval chunk durable evidence changed")
            try:
                self.object_store.verify(chunk.content_ref)
            except ObjectStorageError as exc:
                raise ContextRetrievalIntegrityError("retrieval chunk content failed verification") from exc
            chunks.append(chunk)
        return tuple(
            sorted(
                chunks,
                key=lambda item: (
                    item.source_snapshot.artifact_ref.artifact_id,
                    item.source_snapshot.artifact_ref.revision,
                    item.ordinal,
                    item.chunk_id,
                ),
            )
        )

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        if len(left) != len(right) or not left:
            raise ContextRetrievalIntegrityError("query and chunk vector dimensions differ")
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(item * item for item in left))
        right_norm = math.sqrt(sum(item * item for item in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        score = dot / (left_norm * right_norm)
        if not math.isfinite(score):
            raise ContextRetrievalIntegrityError("retrieval score is non-finite")
        return score

    def _assert_index_sources_current(self, index: RetrievalIndex) -> None:
        if not self._sources_current(index.source_snapshots):
            try:
                self._transition_index(
                    index,
                    RetrievalIndexState.STALE,
                    failure_ref=_failure_ref("active-source-changed"),
                )
            finally:
                connection = self._connect()
                try:
                    connection.execute(
                        "DELETE FROM retrieval_active_heads WHERE project_id = ? AND index_key = ?",
                        (index.project_ref.value, index.index_key),
                    )
                    connection.commit()
                finally:
                    connection.close()
            raise ContextRetrievalConflictError("active RetrievalIndex source is stale")

    def search(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: RetrievalSearchRequest,
        adapter: ModelAdapter,
        *,
        credentials: Mapping[str, str],
    ) -> RetrievalReceipt:
        """Prefilter exact Project/source scope, embed, rank, and optionally rerank."""

        task = self._task_for_attempt(access, attempt)
        project_ref = attempt.node_ref.project_ref
        scope = _artifact_refs(request.source_scope, project_ref, "retrieval search scope")
        request_payload = {
            "context_receipt_digest": None if request.context_receipt_ref is None else request.context_receipt_ref.digest,
            "embedding_deployment_ref": request.embedding_deployment.deployment_ref.value,
            "index_key": request.index_key,
            "maximum_candidates": request.maximum_candidates,
            "node_attempt_record_sha256": attempt.record_sha256,
            "query_sha256": hashlib.sha256(request.query.encode()).hexdigest(),
            "rerank": request.rerank,
            "reranker_deployment_ref": None if request.reranker_deployment is None else request.reranker_deployment.deployment_ref.value,
            "source_scope": [item.value for item in scope],
        }
        request_sha256 = _digest(request_payload)
        connection = self._connect()
        try:
            prior = connection.execute(
                "SELECT * FROM retrieval_search_claims WHERE project_id = ? AND request_id = ?",
                (project_ref.value, request.request_id),
            ).fetchone()
        finally:
            connection.close()
        if prior is not None:
            if not hmac.compare_digest(cast(str, prior["request_sha256"]), request_sha256):
                raise ContextRetrievalConflictError("retrieval search idempotency conflicts")
            return self.getReceipt(
                access,
                RetrievalReceiptRef(project_ref, cast(str, prior["receipt_id"])),
            )
        index = self.getActiveIndex(access, project_ref, request.index_key)
        if not set(scope).issubset({item.artifact_ref for item in index.source_snapshots}):
            raise ContextRetrievalScopeError("search scope widens active RetrievalIndex")
        self._assert_index_sources_current(index)
        chunks = self.listChunks(access, index.index_ref, source_scope=scope)
        if not chunks:
            raise ContextRetrievalNotFoundError("search scope has no indexed chunks")
        query_ref = self.object_store.put(
            _json(request.query).encode(),
            media_type="application/json",
        )
        query_embedding_inputs_ref = self.object_store.put(
            _json([request.query]).encode(),
            media_type="application/json",
        )
        query_binding = ModelExecutionBinding(
            project_ref,
            ModelExecutionRef.new(project_ref),
            request.embedding_deployment.deployment_ref,
            request.embedding_capability_ref,
            task.task_ref,
            task.canonical_digest,
            attempt.run_ref,
            attempt.node_ref,
            attempt.attempt_id,
            attempt.fence,
            (query_embedding_inputs_ref,),
            request.context_receipt_ref,
            task.data_policy_ref,
            task.egress_policy_ref,
            0,
            300.0,
        )
        query_result = adapter.embed(
            access,
            attempt,
            EmbedRequest(query_binding, query_embedding_inputs_ref),
            credentials=credentials,
            idempotency_key=f"retrieval-query-{request.request_id}",
        )
        if not query_result.evidence.succeeded:
            failure = query_result.evidence.failure
            category = "UNKNOWN" if failure is None else failure.value
            raise ContextRetrievalIntegrityError(f"query embedding failed: {category}")
        if (
            len(query_result.vectors) != 1
            or len(query_result.vectors[0]) != index.dimension
            or any(not math.isfinite(item) for item in query_result.vectors[0])
            or query_result.source_digest != query_embedding_inputs_ref.digest
        ):
            raise ContextRetrievalIntegrityError("query embedding vector is invalid")
        if (
            query_result.evidence.deployment_ref.value != index.embedding_deployment_ref
            or query_result.evidence.runtime_identity.record_sha256
            != index.embedding_runtime_sha256
        ):
            raise ContextRetrievalIntegrityError("query embedding deployment or runtime differs")
        self._assert_index_sources_current(index)
        scored = sorted(
            (
                (
                    chunk,
                    self._cosine(query_result.vectors[0], chunk.vector),
                )
                for chunk in chunks
            ),
            key=lambda item: (-item[1], item[0].value),
        )[: request.maximum_candidates]
        candidates = tuple(
            RetrievalCandidate(
                chunk.value,
                chunk.source_snapshot.artifact_ref,
                chunk.content_ref,
                score,
                rank,
            )
            for rank, (chunk, score) in enumerate(scored, 1)
        )
        reranked: tuple[RetrievalCandidate, ...] = ()
        rerank_result: RerankResult | None = None
        if request.rerank:
            assert request.reranker_deployment is not None
            assert request.reranker_capability_ref is not None
            candidate_values = [
                {
                    "candidate_id": item.chunk_ref,
                    "text": self.object_store.read(item.content_ref).decode("utf-8"),
                }
                for item in candidates
            ]
            candidates_ref = self.object_store.put(
                _json(candidate_values).encode(),
                media_type="application/json",
            )
            rerank_binding = ModelExecutionBinding(
                project_ref,
                ModelExecutionRef.new(project_ref),
                request.reranker_deployment.deployment_ref,
                request.reranker_capability_ref,
                task.task_ref,
                task.canonical_digest,
                attempt.run_ref,
                attempt.node_ref,
                attempt.attempt_id,
                attempt.fence,
                (query_ref, candidates_ref),
                request.context_receipt_ref,
                task.data_policy_ref,
                task.egress_policy_ref,
                0,
                300.0,
            )
            rerank_result = adapter.rerank(
                access,
                attempt,
                RerankRequest(rerank_binding, query_ref, candidates_ref),
                credentials=credentials,
                idempotency_key=f"retrieval-rerank-{request.request_id}",
            )
            allowed = {item.chunk_ref: item for item in candidates}
            if (
                not rerank_result.evidence.succeeded
                or rerank_result.source_digest != candidates_ref.digest
                or len(rerank_result.entries) != len(candidates)
                or len({item.candidate_id for item in rerank_result.entries}) != len(candidates)
                or any(item.candidate_id not in allowed for item in rerank_result.entries)
            ):
                raise ContextRetrievalIntegrityError("reranker changed candidate-set identity")
            ordered_entries = tuple(sorted(rerank_result.entries, key=lambda item: item.rank))
            if tuple(item.rank for item in ordered_entries) != tuple(range(1, len(ordered_entries) + 1)):
                raise ContextRetrievalIntegrityError("reranker ranks are not gap-free")
            reranked = tuple(
                RetrievalCandidate(
                    entry.candidate_id,
                    allowed[entry.candidate_id].source_artifact_ref,
                    allowed[entry.candidate_id].content_ref,
                    entry.score,
                    entry.rank,
                )
                for entry in ordered_entries
            )
            self._assert_index_sources_current(index)
        receipt_ref = RetrievalReceiptRef.new(project_ref)
        created_at = _now()
        receipt_basis = {
            "candidates": [item.payload() for item in candidates],
            "created_at": created_at,
            "embedding_deployment_ref": request.embedding_deployment.deployment_ref.value,
            "embedding_model_call_ref": query_result.evidence.model_call_ref.value,
            "embedding_runtime_sha256": query_result.evidence.runtime_identity.record_sha256,
            "index_ref": index.index_ref.value,
            "node_attempt_id": attempt.attempt_id,
            "node_fence": attempt.fence,
            "node_ref": attempt.node_ref.value,
            "query_digest": query_ref.digest,
            "query_size_bytes": query_ref.size_bytes,
            "receipt_ref": receipt_ref.value,
            "reranked_candidates": [item.payload() for item in reranked],
            "reranker_deployment_ref": None if rerank_result is None else cast(ModelDeployment, request.reranker_deployment).deployment_ref.value,
            "reranker_model_call_ref": None if rerank_result is None else rerank_result.evidence.model_call_ref.value,
            "reranker_runtime_sha256": None if rerank_result is None else rerank_result.evidence.runtime_identity.record_sha256,
            "run_ref": f"run://{project_ref.value}/{attempt.run_ref.run_id}",
            "source_scope": [item.value for item in scope],
        }
        receipt_content_ref = self.object_store.put(
            _json(receipt_basis).encode(),
            media_type="application/vnd.minitz.retrieval-receipt+json",
        )
        receipt = RetrievalReceipt(
            receipt_ref,
            query_ref,
            scope,
            index.index_ref,
            candidates,
            reranked,
            request.embedding_deployment.deployment_ref.value,
            query_result.evidence.runtime_identity.record_sha256,
            query_result.evidence.model_call_ref,
            None if rerank_result is None else cast(ModelDeployment, request.reranker_deployment).deployment_ref.value,
            None if rerank_result is None else rerank_result.evidence.runtime_identity.record_sha256,
            None if rerank_result is None else rerank_result.evidence.model_call_ref,
            attempt.run_ref,
            attempt.node_ref,
            attempt.attempt_id,
            attempt.fence,
            receipt_content_ref,
            created_at,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO retrieval_receipts (
                    project_id, receipt_id, receipt_json,
                    receipt_content_json, record_sha256
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_ref.value,
                    receipt_ref.receipt_id,
                    _json(receipt.payload()),
                    _json(
                        {
                            "algorithm": receipt_content_ref.algorithm,
                            "digest": receipt_content_ref.digest,
                            "media_type": receipt_content_ref.media_type,
                            "size_bytes": receipt_content_ref.size_bytes,
                        }
                    ),
                    receipt.record_sha256,
                ),
            )
            connection.execute(
                """
                INSERT INTO retrieval_search_claims (
                    project_id, request_id, request_sha256, receipt_id
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    project_ref.value,
                    request.request_id,
                    request_sha256,
                    receipt_ref.receipt_id,
                ),
            )
            connection.commit()
            return receipt
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ContextRetrievalConflictError("retrieval receipt persistence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _candidate_from_payload(payload: Mapping[str, object], project_ref: ProjectRef) -> RetrievalCandidate:
        return RetrievalCandidate(
            cast(str, payload["chunk_ref"]),
            _parse_artifact_ref(cast(str, payload["source_artifact_ref"])),
            ContentRef(
                "sha256",
                cast(str, payload["content_digest"]),
                cast(int, payload["content_size_bytes"]),
                cast(str, payload["content_media_type"]),
            ),
            float(cast(float, payload["score"])),
            cast(int, payload["rank"]),
        )

    def getReceipt(
        self,
        access: ProjectAccess,
        receipt_ref: RetrievalReceiptRef,
    ) -> RetrievalReceipt:
        if not isinstance(receipt_ref, RetrievalReceiptRef):
            raise TypeError("RetrievalReceiptRef is required")
        self._authorize(access, receipt_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT * FROM retrieval_receipts
                WHERE project_id = ? AND receipt_id = ?
                """,
                (receipt_ref.project_ref.value, receipt_ref.receipt_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ContextRetrievalNotFoundError("RetrievalReceipt does not exist")
        try:
            payload = cast(dict[str, object], json.loads(cast(str, row["receipt_json"])))
            content_payload = cast(dict[str, object], json.loads(cast(str, row["receipt_content_json"])))
            project_ref, index_parts = _parse_project_scoped_uri(cast(str, payload["index_ref"]), "retrieval-index")
            query_ref = ContentRef(
                "sha256",
                cast(str, payload["query_digest"]),
                cast(int, payload["query_size_bytes"]),
                "application/json",
            )
            embedding_project, embedding_parts = _parse_project_scoped_uri(
                cast(str, payload["embedding_model_call_ref"]),
                "model-call",
            )
            rerank_call_value = cast(str | None, payload["reranker_model_call_ref"])
            rerank_call: ModelCallRef | None = None
            if rerank_call_value is not None:
                rerank_project, rerank_parts = _parse_project_scoped_uri(rerank_call_value, "model-call")
                rerank_call = ModelCallRef(rerank_project, rerank_parts[0])
            run_project, run_parts = _parse_project_scoped_uri(cast(str, payload["run_ref"]), "run")
            node_project, node_parts = _parse_project_scoped_uri(cast(str, payload["node_ref"]), "node")
            if (
                len(index_parts) != 2
                or len(embedding_parts) != 1
                or len(run_parts) != 1
                or len(node_parts) != 3
            ):
                raise ContextRetrievalIntegrityError("persisted receipt references are malformed")
            receipt = RetrievalReceipt(
                receipt_ref,
                query_ref,
                tuple(_parse_artifact_ref(item) for item in cast(list[str], payload["source_scope"])),
                RetrievalIndexRef(project_ref, index_parts[0], int(index_parts[1])),
                tuple(
                    self._candidate_from_payload(cast(dict[str, object], item), receipt_ref.project_ref)
                    for item in cast(list[object], payload["candidates"])
                ),
                tuple(
                    self._candidate_from_payload(cast(dict[str, object], item), receipt_ref.project_ref)
                    for item in cast(list[object], payload["reranked_candidates"])
                ),
                cast(str, payload["embedding_deployment_ref"]),
                cast(str, payload["embedding_runtime_sha256"]),
                ModelCallRef(embedding_project, embedding_parts[0]),
                cast(str | None, payload["reranker_deployment_ref"]),
                cast(str | None, payload["reranker_runtime_sha256"]),
                rerank_call,
                RunRef(run_project, run_parts[0]),
                NodeRef(
                    GraphRef(node_project, node_parts[0], int(node_parts[1])),
                    node_parts[2],
                ),
                cast(str, payload["node_attempt_id"]),
                cast(int, payload["node_fence"]),
                ContentRef(
                    cast(str, content_payload["algorithm"]),
                    cast(str, content_payload["digest"]),
                    cast(int, content_payload["size_bytes"]),
                    cast(str, content_payload["media_type"]),
                ),
                cast(str, payload["created_at"]),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, ContextRetrievalError) as exc:
            raise ContextRetrievalIntegrityError("persisted RetrievalReceipt is malformed") from exc
        if not hmac.compare_digest(receipt.record_sha256, cast(str, row["record_sha256"])):
            raise ContextRetrievalIntegrityError("RetrievalReceipt durable evidence changed")
        try:
            self.object_store.verify(receipt.receipt_content_ref)
        except ObjectStorageError as exc:
            raise ContextRetrievalIntegrityError("RetrievalReceipt content failed verification") from exc
        return receipt

    def deleteIndexCache(
        self,
        access: ProjectAccess,
        index_ref: RetrievalIndexRef,
    ) -> RetrievalIndex:
        """Delete only derived chunk/vector rows; source Artifacts remain authoritative."""

        index = self.getIndex(access, index_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                DELETE FROM retrieval_chunks
                WHERE project_id = ? AND index_id = ? AND version = ?
                """,
                (index.project_ref.value, index_ref.index_id, index_ref.version),
            )
            connection.execute(
                """
                DELETE FROM retrieval_active_heads
                WHERE project_id = ? AND index_key = ?
                  AND index_id = ? AND version = ?
                """,
                (
                    index.project_ref.value,
                    index.index_key,
                    index_ref.index_id,
                    index_ref.version,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self._transition_index(
            index,
            RetrievalIndexState.STALE,
            failure_ref=_failure_ref("derived-cache-deleted"),
        )


@dataclass(frozen=True)
class _ContextMaterial:
    source_ref: str
    kind: str
    content_ref: ContentRef
    required: bool
    priority: int


class ContextCompiler:
    """Compile exact model-visible context and durable inclusion/exclusion receipts."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
    ) -> None:
        self.database_path = Path(database_path).resolve()
        if not isinstance(object_store, ObjectStorageBackend):
            raise ContextRetrievalContractError("ObjectStorageBackend is required")
        self.object_store = object_store
        self.projects = ProjectStore(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.calls = CallLedgerService(self.database_path)
        self.project_knowledge = ProjectKnowledgeService(self.database_path)
        self.run_memory = RunMemoryService(self.database_path)
        self.retrieval = RetrievalService(self.database_path, object_store)
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
                CREATE TABLE IF NOT EXISTS context_manifests (
                    project_id TEXT NOT NULL,
                    manifest_id TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    manifest_digest TEXT NOT NULL,
                    PRIMARY KEY (project_id, manifest_id)
                );

                CREATE TABLE IF NOT EXISTS context_receipts (
                    project_id TEXT NOT NULL,
                    receipt_id TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    context_content_json TEXT,
                    receipt_content_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, receipt_id)
                );

                CREATE TABLE IF NOT EXISTS context_compile_claims (
                    project_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    manifest_id TEXT NOT NULL,
                    receipt_id TEXT NOT NULL,
                    PRIMARY KEY (project_id, request_id)
                );

                CREATE TRIGGER IF NOT EXISTS context_manifests_no_update
                BEFORE UPDATE ON context_manifests
                BEGIN SELECT RAISE(ABORT, 'ContextManifest records are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS context_manifests_no_delete
                BEFORE DELETE ON context_manifests
                BEGIN SELECT RAISE(ABORT, 'ContextManifest records cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS context_receipts_no_update
                BEFORE UPDATE ON context_receipts
                BEGIN SELECT RAISE(ABORT, 'ContextReceipt records are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS context_receipts_no_delete
                BEFORE DELETE ON context_receipts
                BEGIN SELECT RAISE(ABORT, 'ContextReceipt records cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS context_compile_claims_no_update
                BEFORE UPDATE ON context_compile_claims
                BEGIN SELECT RAISE(ABORT, 'context compile claims are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS context_compile_claims_no_delete
                BEFORE DELETE ON context_compile_claims
                BEGIN SELECT RAISE(ABORT, 'context compile claims cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectScopeError as exc:
            raise ContextRetrievalScopeError("Project context scope mismatch") from exc

    def _task_for_attempt(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
    ) -> Task:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise ContextRetrievalContractError("NodeExecutionAttempt is required")
        self._authorize(access, attempt.node_ref.project_ref)
        task = self.tasks.get_task(access, attempt.task_ref)
        if task.canonical_digest != attempt.task_digest:
            raise ContextRetrievalIntegrityError("context Task digest differs")
        execution = self.executions.get_node_execution(access, attempt.node_ref)
        if (
            execution.status not in {"RUNNING", "WAITING_EXTERNAL"}
            or execution.current_attempt_id != attempt.attempt_id
            or execution.current_fence != attempt.fence
        ):
            raise ContextRetrievalConflictError("stale Node attempt cannot compile context")
        return task

    def _artifact_material(
        self,
        access: ProjectAccess,
        artifact_ref: ArtifactRef,
        *,
        kind: str,
        required: bool,
        priority: int,
    ) -> _ContextMaterial:
        if not isinstance(artifact_ref, ArtifactRef):
            raise TypeError("ArtifactRef is required for model-visible context")
        artifact = self.artifacts.get_artifact(access, artifact_ref)
        if artifact.content_ref is None:
            raise ContextRetrievalContractError("context Artifact has no content")
        try:
            self.object_store.verify(artifact.content_ref)
        except ObjectStorageError as exc:
            raise ContextRetrievalIntegrityError("context Artifact content failed verification") from exc
        return _ContextMaterial(
            artifact_ref.value,
            kind,
            artifact.content_ref,
            required,
            priority,
        )

    def _inline_material(
        self,
        source_ref: str,
        kind: str,
        text: str,
        required: bool,
        priority: int,
    ) -> _ContextMaterial:
        if not isinstance(text, str) or not text or len(text.encode()) > 64 * 1024 * 1024:
            raise ContextRetrievalContractError("inline context is empty or unbounded")
        content_ref = self.object_store.put(text.encode(), media_type="text/plain")
        return _ContextMaterial(source_ref, kind, content_ref, required, priority)

    @staticmethod
    def _estimate_tokens(payload: bytes) -> int:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContextRetrievalIntegrityError("model-visible context must be UTF-8") from exc
        segments = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        return max(1, len(segments))

    @staticmethod
    def _content_json(content_ref: ContentRef | None) -> str | None:
        if content_ref is None:
            return None
        return _json(
            {
                "algorithm": content_ref.algorithm,
                "digest": content_ref.digest,
                "media_type": content_ref.media_type,
                "size_bytes": content_ref.size_bytes,
            }
        )

    def _materials(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        task: Task,
        request: ContextCompileRequest,
    ) -> tuple[
        tuple[_ContextMaterial, ...],
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
    ]:
        project_ref = attempt.node_ref.project_ref
        explicit_refs = _artifact_refs(
            request.explicit_input_refs,
            project_ref,
            "explicit context inputs",
        )
        tool_refs = _artifact_refs(
            request.tool_output_refs,
            project_ref,
            "context tool outputs",
        )
        retrieval_scope = _artifact_refs(
            request.retrieval_scope,
            project_ref,
            "context retrieval scope",
        )
        if request.run_memory.project_ref != project_ref or request.run_memory.run_ref != attempt.run_ref:
            raise ContextRetrievalScopeError("RunMemory crossed exact context Run")
        if (
            request.run_memory.task.task_ref != task.task_ref
            or request.run_memory.task.canonical_digest != task.canonical_digest
        ):
            raise ContextRetrievalIntegrityError("RunMemory Task binding differs")
        try:
            self.run_memory.validate_consistency(access, request.run_memory)
        except RunMemoryError as exc:
            raise ContextRetrievalIntegrityError("RunMemory is not the current durable state") from exc
        optional = _refs(request.optional_refs, "optional context refs")
        optional_set = set(optional)
        materials: list[_ContextMaterial] = []
        objective_ref = (
            f"task://{project_ref.value}/{task.task_id}/{task.revision}/objective"
        )
        materials.append(
            self._inline_material(
                objective_ref,
                "TASK_OBJECTIVE",
                task.objective,
                True,
                0,
            )
        )
        for item in explicit_refs:
            materials.append(
                self._artifact_material(
                    access,
                    item,
                    kind="EXPLICIT_INPUT",
                    required=item.value not in optional_set,
                    priority=10,
                )
            )
        project_knowledge_refs: list[str] = []
        for project_knowledge in request.project_knowledge:
            if not isinstance(project_knowledge, ProjectKnowledge):
                raise ContextRetrievalContractError("ProjectKnowledge is required")
            if project_knowledge.project_ref != project_ref:
                raise ContextRetrievalScopeError("ProjectKnowledge crossed Project context")
            try:
                stored_knowledge = self.project_knowledge.get_knowledge(
                    access,
                    project_knowledge.knowledge_ref,
                )
                resolution = self.project_knowledge.resolve_current(
                    access,
                    project_knowledge.knowledge_ref,
                )
            except ProjectKnowledgeError as exc:
                raise ContextRetrievalIntegrityError(
                    "ProjectKnowledge is not accepted durable state"
                ) from exc
            if (
                stored_knowledge != project_knowledge
                or resolution.status != "CURRENT"
                or resolution.current != project_knowledge
            ):
                raise ContextRetrievalIntegrityError(
                    "ProjectKnowledge is not the current accepted revision"
                )
            project_knowledge_refs.append(project_knowledge.knowledge_ref.value)
            if project_knowledge.statement is not None:
                materials.append(
                    self._inline_material(
                        project_knowledge.knowledge_ref.value,
                        "PROJECT_KNOWLEDGE",
                        project_knowledge.statement,
                        project_knowledge.knowledge_ref.value not in optional_set,
                        20,
                    )
                )
            elif project_knowledge.content_ref is not None:
                self.object_store.verify(project_knowledge.content_ref)
                materials.append(
                    _ContextMaterial(
                        project_knowledge.knowledge_ref.value,
                        "PROJECT_KNOWLEDGE",
                        project_knowledge.content_ref,
                        project_knowledge.knowledge_ref.value not in optional_set,
                        20,
                    )
                )
        engine_knowledge_refs: list[str] = []
        for engine_knowledge in request.engine_knowledge:
            if (
                not isinstance(engine_knowledge, Knowledge)
                or engine_knowledge.scope != "ENGINE"
                or engine_knowledge.project_ref is not None
            ):
                raise ContextRetrievalScopeError("only supported global ENGINE Knowledge may enter context")
            engine_knowledge_refs.append(engine_knowledge.knowledge_ref.value)
            if engine_knowledge.statement is not None:
                materials.append(
                    self._inline_material(
                        engine_knowledge.knowledge_ref.value,
                        "ENGINE_KNOWLEDGE",
                        engine_knowledge.statement,
                        engine_knowledge.knowledge_ref.value not in optional_set,
                        30,
                    )
                )
            elif engine_knowledge.content_ref is not None:
                self.object_store.verify(engine_knowledge.content_ref)
                materials.append(
                    _ContextMaterial(
                        engine_knowledge.knowledge_ref.value,
                        "ENGINE_KNOWLEDGE",
                        engine_knowledge.content_ref,
                        engine_knowledge.knowledge_ref.value not in optional_set,
                        30,
                    )
                )
        run_memory_ref = (
            f"run-memory://{project_ref.value}/{attempt.run_ref.run_id}/"
            f"{request.run_memory.semantic_digest}"
        )
        run_summary = _json(
            {
                "continuation_node_refs": [
                    item.value for item in request.run_memory.continuation_node_refs
                ],
                "event_high_water_mark": request.run_memory.event_high_water_mark,
                "ready_node_refs": [
                    item.value for item in request.run_memory.ready_node_refs
                ],
                "run_ref": f"run://{project_ref.value}/{attempt.run_ref.run_id}",
                "semantic_digest": request.run_memory.semantic_digest,
                "status": request.run_memory.run.status,
            }
        )
        materials.append(
            self._inline_material(
                run_memory_ref,
                "RUN_MEMORY",
                run_summary,
                run_memory_ref not in optional_set,
                40,
            )
        )
        retrieval_receipt_values: list[str] = []
        for receipt_ref in request.retrieval_receipt_refs:
            if not isinstance(receipt_ref, RetrievalReceiptRef) or receipt_ref.project_ref != project_ref:
                raise ContextRetrievalScopeError("RetrievalReceipt crossed Project context")
            receipt = self.retrieval.getReceipt(access, receipt_ref)
            if receipt.run_ref != attempt.run_ref or receipt.node_ref != attempt.node_ref:
                raise ContextRetrievalScopeError("RetrievalReceipt crossed exact Run or Node")
            if not set(receipt.source_scope).issubset(set(retrieval_scope)):
                raise ContextRetrievalScopeError("RetrievalReceipt widens manifest scope")
            retrieval_receipt_values.append(receipt_ref.value)
            selected = receipt.reranked_candidates or receipt.candidates
            for candidate in selected:
                materials.append(
                    _ContextMaterial(
                        candidate.chunk_ref,
                        "RETRIEVAL_CHUNK",
                        candidate.content_ref,
                        candidate.chunk_ref not in optional_set,
                        50 + candidate.rank,
                    )
                )
        for item in tool_refs:
            materials.append(
                self._artifact_material(
                    access,
                    item,
                    kind="TOOL_OUTPUT",
                    required=item.value not in optional_set,
                    priority=80,
                )
            )
        identities = [item.source_ref for item in materials]
        if len(set(identities)) != len(identities):
            raise ContextRetrievalContractError("context material identity is duplicated")
        if not optional_set.issubset(set(identities)):
            raise ContextRetrievalContractError("optional context ref is not materialized")
        return (
            tuple(sorted(materials, key=lambda item: (item.priority, item.source_ref))),
            tuple(sorted(project_knowledge_refs)),
            tuple(sorted(engine_knowledge_refs)),
            (run_memory_ref,),
            tuple(sorted(retrieval_receipt_values)),
            (objective_ref,),
        )

    def compileContext(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ContextCompileRequest,
    ) -> tuple[ContextManifest, ContextReceipt]:
        """Compile deterministic bounded context with explicit exclusion evidence."""

        task = self._task_for_attempt(access, attempt)
        project_ref = attempt.node_ref.project_ref
        if (
            request.reductions
            and request.reduction_policy
            is not ContextReductionPolicy.USE_EXPLICIT_REDUCTIONS
        ):
            raise ContextRetrievalContractError(
                "context reductions require the explicit reduction policy"
            )
        (
            materials,
            project_knowledge_refs,
            engine_knowledge_refs,
            run_refs,
            retrieval_receipt_values,
            objective_values,
        ) = self._materials(access, attempt, task, request)
        material_by_ref = {item.source_ref: item for item in materials}
        reduction_by_ref: dict[str, ContextReductionEvidence] = {}
        for reduction in request.reductions:
            if not isinstance(reduction, ContextReductionEvidence):
                raise ContextRetrievalContractError("ContextReductionEvidence is required")
            if reduction.model_call_ref.project_ref != project_ref:
                raise ContextRetrievalScopeError("context reduction ModelCall crossed Project")
            if reduction.source_ref in reduction_by_ref:
                raise ContextRetrievalContractError("context reduction source is duplicated")
            self.object_store.verify(reduction.reduced_content_ref)
            try:
                reduction_call = self.calls.get_model_call(
                    access,
                    reduction.model_call_ref,
                )
            except CallError as exc:
                raise ContextRetrievalIntegrityError(
                    "context reduction ModelCall is unavailable"
                ) from exc
            source_material = material_by_ref.get(reduction.source_ref)
            if (
                source_material is None
                or reduction_call.status != "SUCCEEDED"
                or reduction_call.run_ref != attempt.run_ref
                or reduction_call.node_ref != attempt.node_ref
                or reduction_call.node_attempt_id != attempt.attempt_id
                or reduction_call.node_fence != attempt.fence
                or reduction.reduced_content_ref not in reduction_call.output_refs
                or (
                    source_material.content_ref not in reduction_call.input_refs
                    and reduction.source_ref
                    not in {item.value for item in reduction_call.input_refs}
                )
            ):
                raise ContextRetrievalIntegrityError(
                    "context reduction ModelCall provenance differs"
                )
            reduction_by_ref[reduction.source_ref] = reduction
        if not set(reduction_by_ref).issubset(material_by_ref):
            raise ContextRetrievalContractError("context reduction source is absent")
        request_payload = {
            "attempt_record_sha256": attempt.record_sha256,
            "budget": {
                "maximum_tokens": request.budget.maximum_tokens,
                "reserved_output_tokens": request.budget.reserved_output_tokens,
            },
            "exact_token_count": request.exact_token_count,
            "exact_tokenizer_ref": request.exact_tokenizer_ref,
            "engine_knowledge_refs": list(engine_knowledge_refs),
            "explicit_input_refs": sorted(item.value for item in request.explicit_input_refs),
            "material": [
                {
                    "content_digest": item.content_ref.digest,
                    "kind": item.kind,
                    "priority": item.priority,
                    "required": item.required,
                    "source_ref": item.source_ref,
                }
                for item in materials
            ],
            "reduction_policy": request.reduction_policy.value,
            "reductions": [
                item.payload()
                for item in sorted(request.reductions, key=lambda value: value.source_ref)
            ],
            "retrieval_receipt_refs": list(retrieval_receipt_values),
            "retrieval_scope": sorted(item.value for item in request.retrieval_scope),
            "run_refs": list(run_refs),
            "task_digest": task.canonical_digest,
            "tool_output_refs": sorted(item.value for item in request.tool_output_refs),
            "project_knowledge_refs": list(project_knowledge_refs),
        }
        request_sha256 = _digest(request_payload)
        connection = self._connect()
        try:
            prior = connection.execute(
                """
                SELECT * FROM context_compile_claims
                WHERE project_id = ? AND request_id = ?
                """,
                (project_ref.value, request.request_id),
            ).fetchone()
        finally:
            connection.close()
        if prior is not None:
            if not hmac.compare_digest(cast(str, prior["request_sha256"]), request_sha256):
                raise ContextRetrievalConflictError("context compilation idempotency conflicts")
            return (
                self.getManifest(
                    access,
                    ContextManifestRef(project_ref, cast(str, prior["manifest_id"])),
                ),
                self.getReceipt(
                    access,
                    ContextReceiptRef(project_ref, cast(str, prior["receipt_id"])),
                ),
            )
        manifest = ContextManifest(
            ContextManifestRef.new(project_ref),
            task.task_ref,
            task.canonical_digest,
            attempt.run_ref,
            attempt.node_ref.graph_ref,
            attempt.node_ref,
            attempt.attempt_id,
            attempt.fence,
            objective_values[0],
            tuple(item.value for item in request.explicit_input_refs),
            project_knowledge_refs,
            engine_knowledge_refs,
            run_refs,
            tuple(item.value for item in request.retrieval_scope),
            retrieval_receipt_values,
            tuple(item.value for item in request.tool_output_refs),
            task.data_policy_ref,
            task.egress_policy_ref,
            request.budget,
            request.reduction_policy,
            request.optional_refs,
            _now(),
        )
        available = request.budget.available_tokens
        included: list[str] = []
        excluded: list[str] = []
        reductions_used: list[ContextReductionEvidence] = []
        selected: list[tuple[_ContextMaterial, bytes]] = []
        estimated_tokens = 0
        context_limit = False
        for material in materials:
            payload = self.object_store.read(material.content_ref)
            tokens = self._estimate_tokens(payload)
            selected_payload = payload
            selected_tokens = tokens
            available_reduction = reduction_by_ref.get(material.source_ref)
            if estimated_tokens + selected_tokens > available and available_reduction is not None:
                reduced_payload = self.object_store.read(available_reduction.reduced_content_ref)
                reduced_tokens = self._estimate_tokens(reduced_payload)
                if estimated_tokens + reduced_tokens <= available:
                    selected_payload = reduced_payload
                    selected_tokens = reduced_tokens
                    reductions_used.append(available_reduction)
            if estimated_tokens + selected_tokens <= available:
                included.append(material.source_ref)
                selected.append((material, selected_payload))
                estimated_tokens += selected_tokens
                continue
            excluded.append(material.source_ref)
            if material.required or request.reduction_policy is ContextReductionPolicy.BLOCK:
                context_limit = True
        if context_limit:
            excluded = [item.source_ref for item in materials]
            included = []
            selected = []
            reductions_used = []
        framed = bytearray()
        if not context_limit:
            for material, payload in selected:
                header = _json(
                    {
                        "content_sha256": hashlib.sha256(payload).hexdigest(),
                        "kind": material.kind,
                        "source_ref": material.source_ref,
                    }
                ).encode()
                framed.extend(b"[MINITZ_CONTEXT_BEGIN]")
                framed.extend(header)
                framed.extend(b"\n")
                framed.extend(payload)
                framed.extend(b"\n[MINITZ_CONTEXT_END]\n")
        token_count = 0 if context_limit else (
            request.exact_token_count
            if request.exact_token_count is not None
            else estimated_tokens
        )
        if not context_limit and token_count > available:
            context_limit = True
            excluded = [item.source_ref for item in materials]
            included = []
            reductions_used = []
            framed = bytearray()
            token_count = 0
        token_count_exact = not context_limit and request.exact_token_count is not None
        tokenizer_ref = request.exact_tokenizer_ref if token_count_exact else None
        context_ref = (
            None
            if context_limit
            else self.object_store.put(
                bytes(framed),
                media_type="application/vnd.minitz.compiled-context",
            )
        )
        receipt_ref = ContextReceiptRef.new(project_ref)
        created_at = _now()
        receipt_basis = {
            "context_digest": None if context_ref is None else context_ref.digest,
            "context_size_bytes": None if context_ref is None else context_ref.size_bytes,
            "created_at": created_at,
            "excluded_refs": sorted(excluded),
            "included_refs": sorted(included),
            "manifest_digest": manifest.manifest_digest,
            "manifest_ref": manifest.manifest_ref.value,
            "receipt_ref": receipt_ref.value,
            "reduction_evidence": [item.payload() for item in reductions_used],
            "retrieval_refs": list(retrieval_receipt_values),
            "status": "CONTEXT_LIMIT" if context_limit else "COMPILED",
            "token_count": token_count,
            "token_count_exact": token_count_exact,
            "token_count_source": (
                ContextTokenCountSource.EXACT_CALLER_TOKENIZER.value
                if token_count_exact
                else ContextTokenCountSource.ESTIMATE_UNICODE_SEGMENTS.value
            ),
            "tokenizer_ref": tokenizer_ref,
            "tool_refs": [item.value for item in request.tool_output_refs],
        }
        receipt_content_ref = self.object_store.put(
            _json(receipt_basis).encode(),
            media_type="application/vnd.minitz.context-receipt+json",
        )
        receipt = ContextReceipt(
            receipt_ref,
            manifest.manifest_ref,
            manifest.manifest_digest,
            "CONTEXT_LIMIT" if context_limit else "COMPILED",
            context_ref,
            receipt_content_ref,
            tuple(included),
            tuple(excluded),
            retrieval_receipt_values,
            tuple(item.value for item in request.tool_output_refs),
            token_count,
            (
                ContextTokenCountSource.EXACT_CALLER_TOKENIZER
                if token_count_exact
                else ContextTokenCountSource.ESTIMATE_UNICODE_SEGMENTS
            ),
            token_count_exact,
            tokenizer_ref,
            tuple(reductions_used),
            created_at,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO context_manifests VALUES (?, ?, ?, ?)",
                (
                    project_ref.value,
                    manifest.manifest_ref.manifest_id,
                    _json(manifest.payload()),
                    manifest.manifest_digest,
                ),
            )
            connection.execute(
                "INSERT INTO context_receipts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    project_ref.value,
                    receipt.receipt_ref.receipt_id,
                    _json(receipt.payload()),
                    self._content_json(context_ref),
                    cast(str, self._content_json(receipt_content_ref)),
                    receipt.record_sha256,
                ),
            )
            connection.execute(
                "INSERT INTO context_compile_claims VALUES (?, ?, ?, ?, ?)",
                (
                    project_ref.value,
                    request.request_id,
                    request_sha256,
                    manifest.manifest_ref.manifest_id,
                    receipt.receipt_ref.receipt_id,
                ),
            )
            connection.commit()
            return manifest, receipt
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ContextRetrievalConflictError("context compilation persistence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _task_ref(value: str) -> TaskRef:
        project_ref, parts = _parse_project_scoped_uri(value, "task")
        if len(parts) != 2:
            raise ContextRetrievalIntegrityError("persisted TaskRef is malformed")
        return TaskRef(project_ref, parts[0], int(parts[1]))

    @staticmethod
    def _graph_ref(value: str) -> GraphRef:
        project_ref, parts = _parse_project_scoped_uri(value, "graph")
        if len(parts) != 2:
            raise ContextRetrievalIntegrityError("persisted GraphRef is malformed")
        return GraphRef(project_ref, parts[0], int(parts[1]))

    @classmethod
    def _node_ref(cls, value: str) -> NodeRef:
        project_ref, parts = _parse_project_scoped_uri(value, "node")
        if len(parts) != 3:
            raise ContextRetrievalIntegrityError("persisted NodeRef is malformed")
        return NodeRef(GraphRef(project_ref, parts[0], int(parts[1])), parts[2])

    def getManifest(
        self,
        access: ProjectAccess,
        manifest_ref: ContextManifestRef,
    ) -> ContextManifest:
        if not isinstance(manifest_ref, ContextManifestRef):
            raise TypeError("ContextManifestRef is required")
        self._authorize(access, manifest_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM context_manifests WHERE project_id = ? AND manifest_id = ?",
                (manifest_ref.project_ref.value, manifest_ref.manifest_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ContextRetrievalNotFoundError("ContextManifest does not exist")
        try:
            payload = cast(dict[str, object], json.loads(cast(str, row["manifest_json"])))
            run_project, run_parts = _parse_project_scoped_uri(cast(str, payload["run_ref"]), "run")
            budget_payload = cast(dict[str, object], payload["budget"])
            manifest = ContextManifest(
                manifest_ref,
                self._task_ref(cast(str, payload["task_ref"])),
                cast(str, payload["task_digest"]),
                RunRef(run_project, run_parts[0]),
                self._graph_ref(cast(str, payload["graph_ref"])),
                self._node_ref(cast(str, payload["node_ref"])),
                cast(str, payload["node_attempt_id"]),
                cast(int, payload["node_fence"]),
                cast(str, payload["objective_ref"]),
                tuple(cast(list[str], payload["explicit_input_refs"])),
                tuple(cast(list[str], payload["project_knowledge_refs"])),
                tuple(cast(list[str], payload["engine_knowledge_refs"])),
                tuple(cast(list[str], payload["run_refs"])),
                tuple(cast(list[str], payload["retrieval_scope"])),
                tuple(cast(list[str], payload["retrieval_receipt_refs"])),
                tuple(cast(list[str], payload["tool_output_refs"])),
                cast(str | None, payload["data_policy_ref"]),
                cast(str | None, payload["egress_policy_ref"]),
                ContextBudget(
                    cast(int, budget_payload["maximum_tokens"]),
                    cast(int, budget_payload["reserved_output_tokens"]),
                ),
                ContextReductionPolicy(cast(str, payload["reduction_policy"])),
                tuple(cast(list[str], payload["optional_refs"])),
                cast(str, payload["created_at"]),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, ContextRetrievalError) as exc:
            raise ContextRetrievalIntegrityError("persisted ContextManifest is malformed") from exc
        if not hmac.compare_digest(manifest.manifest_digest, cast(str, row["manifest_digest"])):
            raise ContextRetrievalIntegrityError("ContextManifest durable evidence changed")
        return manifest

    @staticmethod
    def _content_from_json(value: str | None) -> ContentRef | None:
        if value is None:
            return None
        payload = cast(dict[str, object], json.loads(value))
        return ContentRef(
            cast(str, payload["algorithm"]),
            cast(str, payload["digest"]),
            cast(int, payload["size_bytes"]),
            cast(str, payload["media_type"]),
        )

    def getReceipt(
        self,
        access: ProjectAccess,
        receipt_ref: ContextReceiptRef,
    ) -> ContextReceipt:
        if not isinstance(receipt_ref, ContextReceiptRef):
            raise TypeError("ContextReceiptRef is required")
        self._authorize(access, receipt_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM context_receipts WHERE project_id = ? AND receipt_id = ?",
                (receipt_ref.project_ref.value, receipt_ref.receipt_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ContextRetrievalNotFoundError("ContextReceipt does not exist")
        try:
            payload = cast(dict[str, object], json.loads(cast(str, row["receipt_json"])))
            manifest_project, manifest_parts = _parse_project_scoped_uri(
                cast(str, payload["manifest_ref"]),
                "context-manifest",
            )
            reductions: list[ContextReductionEvidence] = []
            for item_value in cast(list[object], payload["reduction_evidence"]):
                item = cast(dict[str, object], item_value)
                call_project, call_parts = _parse_project_scoped_uri(
                    cast(str, item["model_call_ref"]),
                    "model-call",
                )
                reductions.append(
                    ContextReductionEvidence(
                        cast(str, item["source_ref"]),
                        ContentRef(
                            "sha256",
                            cast(str, item["reduced_content_digest"]),
                            cast(int, item["reduced_content_size_bytes"]),
                            cast(str, item["reduced_content_media_type"]),
                        ),
                        ModelCallRef(call_project, call_parts[0]),
                    )
                )
            receipt = ContextReceipt(
                receipt_ref,
                ContextManifestRef(manifest_project, manifest_parts[0]),
                cast(str, payload["manifest_digest"]),
                cast(str, payload["status"]),
                self._content_from_json(cast(str | None, row["context_content_json"])),
                cast(ContentRef, self._content_from_json(cast(str, row["receipt_content_json"]))),
                tuple(cast(list[str], payload["included_refs"])),
                tuple(cast(list[str], payload["excluded_refs"])),
                tuple(cast(list[str], payload["retrieval_refs"])),
                tuple(cast(list[str], payload["tool_refs"])),
                cast(int, payload["token_count"]),
                ContextTokenCountSource(cast(str, payload["token_count_source"])),
                cast(bool, payload["token_count_exact"]),
                cast(str | None, payload["tokenizer_ref"]),
                tuple(reductions),
                cast(str, payload["created_at"]),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, ContextRetrievalError) as exc:
            raise ContextRetrievalIntegrityError("persisted ContextReceipt is malformed") from exc
        if not hmac.compare_digest(receipt.record_sha256, cast(str, row["record_sha256"])):
            raise ContextRetrievalIntegrityError("ContextReceipt durable evidence changed")
        self.object_store.verify(receipt.receipt_content_ref)
        if receipt.context_ref is not None:
            self.object_store.verify(receipt.context_ref)
        return receipt

    def bindingWithContext(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        manifest: ContextManifest,
        receipt: ContextReceipt,
        *,
        deployment: ModelDeployment,
        capability_ref: CapabilityRef,
        additional_input_refs: Sequence[ContentRef | ArtifactRef] = (),
        timeout_seconds: float = 300.0,
    ) -> ModelExecutionBinding:
        """Bind a significant ModelCall to one exact successful ContextReceipt."""

        task = self._task_for_attempt(access, attempt)
        if (
            manifest.project_ref != attempt.node_ref.project_ref
            or manifest.task_ref != task.task_ref
            or manifest.run_ref != attempt.run_ref
            or manifest.node_ref != attempt.node_ref
            or receipt.manifest_ref != manifest.manifest_ref
            or receipt.manifest_digest != manifest.manifest_digest
            or receipt.status != "COMPILED"
            or receipt.context_ref is None
        ):
            raise ContextRetrievalIntegrityError("ContextReceipt cannot bind this ModelCall")
        inputs = tuple(additional_input_refs)
        if receipt.context_ref not in inputs:
            inputs = (*inputs, receipt.context_ref)
        return ModelExecutionBinding(
            attempt.node_ref.project_ref,
            ModelExecutionRef.new(attempt.node_ref.project_ref),
            deployment.deployment_ref,
            capability_ref,
            task.task_ref,
            task.canonical_digest,
            attempt.run_ref,
            attempt.node_ref,
            attempt.attempt_id,
            attempt.fence,
            inputs,
            receipt.receipt_content_ref,
            task.data_policy_ref,
            task.egress_policy_ref,
            receipt.token_count,
            timeout_seconds,
        )
