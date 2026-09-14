"""Immutable content-addressed Run checkpoints and current-state-wins resume."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from typing import cast
from uuid import uuid4

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .event import Event, EventLedger, EventRef
from .execution import NodeExecution, NodeExecutionAttempt, NodeExecutionService
from .graph import Graph, GraphRef, Node, NodeRef
from .object_store import ObjectStorageBackend, ObjectStorageError
from .project import ProjectAccess, ProjectRef, ProjectScopeError
from .run import ExecutionAttempt, Run, RunAuthorityError, RunError, RunRef
from .run_memory import RunMemory, RunMemoryService
from .task import Task, TaskRef


_CHECKPOINT_ID = re.compile(r"chk_[0-9a-f]{32}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,1056}")
_SCHEMA_VERSION = "minitz.run-checkpoint/v1"
_MEDIA_TYPE = "application/vnd.minitz.run-checkpoint+json"
_TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}
_ACTIVE_NODE_STATUSES = {"LEASED", "RUNNING", "WAITING_EXTERNAL"}
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{4,}"),
    re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{4,}"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(?:^|[?&;,/\s])(?:access[_-]?key|access[_-]?token|api[_-]?key|"
        r"authorization|credential|password|private[_-]?key|refresh[_-]?token|"
        r"secret|token)\s*[:=]\s*[^&;/\s]+",
        re.IGNORECASE,
    ),
    re.compile(r"://[^/\s:@]+:[^/\s@]+@"),
)


class CheckpointError(Exception):
    """Base class for durable checkpoint failures."""


class CheckpointContractError(CheckpointError, ValueError):
    """A checkpoint request or value is malformed."""


class CheckpointScopeError(CheckpointError):
    """A checkpoint operation crossed exact Project scope."""


class CheckpointAuthorityError(CheckpointError, PermissionError):
    """A checkpoint operation lacks current fenced Run authority."""


class CheckpointConflictError(CheckpointError):
    """Checkpoint idempotency or continuation state conflicts."""


class CheckpointNotFoundError(CheckpointError):
    """The exact checkpoint does not exist."""


class CheckpointIntegrityError(CheckpointError):
    """Checkpoint bytes or durable bindings failed integrity verification."""


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _validate_timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise CheckpointContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CheckpointContractError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CheckpointContractError(f"{name} must be timezone-aware")
    return value


def _validate_digest(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise CheckpointIntegrityError(f"{name} is malformed")
    return value


def _validate_key(value: object, name: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise CheckpointContractError(f"{name} is malformed")
    return value


def _validate_opaque_ref(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or _ABSOLUTE_REF.fullmatch(value) is None
        or any(pattern.search(value) is not None for pattern in _SECRET_PATTERNS)
    ):
        raise CheckpointContractError(
            f"{name} must be a bounded credential-free opaque reference"
        )
    return value


def _content_payload(value: ContentRef) -> dict[str, object]:
    return {
        "algorithm": value.algorithm,
        "digest": value.digest,
        "media_type": value.media_type,
        "size_bytes": value.size_bytes,
    }


def _run_value(value: RunRef) -> str:
    return f"run://{value.project_ref.value}/{value.run_id}"


def _task_value(value: TaskRef) -> str:
    return (
        f"task://{value.project_ref.value}/{value.task_id}/{value.revision}"
    )


def _content_from_payload(value: object) -> ContentRef:
    if not isinstance(value, dict) or set(value) != {
        "algorithm",
        "digest",
        "media_type",
        "size_bytes",
    }:
        raise CheckpointIntegrityError("Checkpoint ContentRef is malformed")
    return ContentRef(
        cast(str, value["algorithm"]),
        cast(str, value["digest"]),
        cast(int, value["size_bytes"]),
        cast(str, value["media_type"]),
    )


@dataclass(frozen=True, order=True)
class RunCheckpointRef:
    """Exact opaque identity of one immutable Project-scoped checkpoint."""

    project_ref: ProjectRef
    checkpoint_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise CheckpointContractError("RunCheckpointRef requires ProjectRef")
        if not isinstance(self.checkpoint_id, str) or _CHECKPOINT_ID.fullmatch(
            self.checkpoint_id
        ) is None:
            raise CheckpointContractError("RunCheckpoint identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> RunCheckpointRef:
        return cls(project_ref, f"chk_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"checkpoint://{self.project_ref.value}/{self.checkpoint_id}"


@dataclass(frozen=True)
class CheckpointAttemptRef:
    """Exact immutable attempt/fence summary embedded in checkpoint bytes."""

    attempt_id: str
    attempt_number: int
    fence: int
    run_attempt_id: str
    run_fence: int
    record_sha256: str
    completion_sha256: str | None
    outcome: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_id, str) or re.fullmatch(
            r"natt_[0-9a-f]{32}", self.attempt_id
        ) is None:
            raise CheckpointContractError("Checkpoint attempt identity is malformed")
        for value, name in (
            (self.attempt_number, "attempt_number"),
            (self.fence, "fence"),
            (self.run_fence, "run_fence"),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise CheckpointContractError(f"Checkpoint {name} is malformed")
        if not isinstance(self.run_attempt_id, str) or re.fullmatch(
            r"att_[0-9a-f]{32}", self.run_attempt_id
        ) is None:
            raise CheckpointContractError("Checkpoint Run attempt identity is malformed")
        _validate_digest(self.record_sha256, "Checkpoint attempt digest")
        if (self.completion_sha256 is None) != (self.outcome is None):
            raise CheckpointIntegrityError("Checkpoint attempt completion is incomplete")
        if self.completion_sha256 is not None:
            _validate_digest(self.completion_sha256, "Checkpoint completion digest")
            if self.outcome not in {"SUCCEEDED", "FAILED", "CANCELLED", "STALE"}:
                raise CheckpointIntegrityError("Checkpoint attempt outcome is malformed")

    def payload(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "completion_sha256": self.completion_sha256,
            "fence": self.fence,
            "outcome": self.outcome,
            "record_sha256": self.record_sha256,
            "run_attempt_id": self.run_attempt_id,
            "run_fence": self.run_fence,
        }


@dataclass(frozen=True)
class CheckpointFailureRef:
    """Reference-only failure identity and record digest."""

    failure_ref: str
    category: str
    retry_possible: bool
    record_sha256: str

    def __post_init__(self) -> None:
        _validate_opaque_ref(self.failure_ref, "failure_ref")
        if not isinstance(self.category, str) or re.fullmatch(
            r"[A-Z][A-Z0-9_.-]{0,63}", self.category
        ) is None:
            raise CheckpointContractError("Checkpoint failure category is malformed")
        if not isinstance(self.retry_possible, bool):
            raise CheckpointContractError("Checkpoint retry flag is malformed")
        _validate_digest(self.record_sha256, "Checkpoint failure digest")

    def payload(self) -> dict[str, object]:
        return {
            "category": self.category,
            "failure_ref": self.failure_ref,
            "record_sha256": self.record_sha256,
            "retry_possible": self.retry_possible,
        }


@dataclass(frozen=True)
class CheckpointNodeState:
    """Reference-only snapshot of one exact durable Node state."""

    node_ref: NodeRef
    node_record_sha256: str
    node_semantic_digest: str
    status: str | None
    state_version: int | None
    state_sha256: str | None
    current_attempt_id: str | None
    current_attempt_number: int | None
    current_fence: int
    current_run_attempt_id: str | None
    current_run_fence: int | None
    source_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    attempts: tuple[CheckpointAttemptRef, ...]
    failures: tuple[CheckpointFailureRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.node_ref, NodeRef):
            raise CheckpointContractError("Checkpoint NodeRef is required")
        _validate_digest(self.node_record_sha256, "Checkpoint Node record digest")
        _validate_digest(self.node_semantic_digest, "Checkpoint Node semantic digest")
        if self.status is None:
            if any(
                value is not None
                for value in (
                    self.state_version,
                    self.state_sha256,
                    self.current_attempt_id,
                    self.current_attempt_number,
                    self.current_run_attempt_id,
                    self.current_run_fence,
                )
            ) or self.current_fence != 0 or self.output_refs or self.evidence_refs:
                raise CheckpointIntegrityError(
                    "Uninitialized checkpoint Node claims execution state"
                )
        else:
            if not isinstance(self.state_version, int) or self.state_version < 1:
                raise CheckpointIntegrityError("Checkpoint Node state version is malformed")
            _validate_digest(self.state_sha256, "Checkpoint Node state digest")
        for value in self.source_refs + self.output_refs + self.evidence_refs:
            _validate_opaque_ref(value, "Checkpoint Node object ref")
        object.__setattr__(self, "source_refs", tuple(sorted(set(self.source_refs))))
        object.__setattr__(self, "output_refs", tuple(sorted(set(self.output_refs))))
        object.__setattr__(self, "evidence_refs", tuple(sorted(set(self.evidence_refs))))
        object.__setattr__(self, "attempts", tuple(self.attempts))
        object.__setattr__(self, "failures", tuple(self.failures))

    def payload(self) -> dict[str, object]:
        return {
            "attempts": [item.payload() for item in self.attempts],
            "current_attempt_id": self.current_attempt_id,
            "current_attempt_number": self.current_attempt_number,
            "current_fence": self.current_fence,
            "current_run_attempt_id": self.current_run_attempt_id,
            "current_run_fence": self.current_run_fence,
            "evidence_refs": list(self.evidence_refs),
            "failures": [item.payload() for item in self.failures],
            "node_record_sha256": self.node_record_sha256,
            "node_ref": self.node_ref.value,
            "node_semantic_digest": self.node_semantic_digest,
            "output_refs": list(self.output_refs),
            "source_refs": list(self.source_refs),
            "state_sha256": self.state_sha256,
            "state_version": self.state_version,
            "status": self.status,
        }


@dataclass(frozen=True)
class RunCheckpoint:
    """Verified versioned continuation evidence, never a state rollback command."""

    checkpoint_ref: RunCheckpointRef
    schema_version: str
    run_ref: RunRef
    task_ref: TaskRef
    task_digest: str
    graph_ref: GraphRef
    graph_record_sha256: str
    checkpoint_sequence: int
    created_at: str
    nodes: tuple[CheckpointNodeState, ...]
    completed_output_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    call_refs: tuple[str, ...]
    failure_refs: tuple[str, ...]
    event_high_water_mark: int
    event_anchor_ref: EventRef | None
    event_anchor_record_sha256: str | None
    workspace_snapshot_ref: ContentRef | None
    continuation_refs: tuple[str, ...]
    content_ref: ContentRef
    artifact_ref: ArtifactRef
    event_ref: EventRef
    event_sequence: int
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise CheckpointContractError("RunCheckpoint schema version is unsupported")
        if not all(
            isinstance(value, expected)
            for value, expected in (
                (self.checkpoint_ref, RunCheckpointRef),
                (self.run_ref, RunRef),
                (self.task_ref, TaskRef),
                (self.graph_ref, GraphRef),
                (self.content_ref, ContentRef),
                (self.artifact_ref, ArtifactRef),
                (self.event_ref, EventRef),
            )
        ):
            raise CheckpointContractError("RunCheckpoint exact references are malformed")
        project_ref = self.checkpoint_ref.project_ref
        if any(
            value.project_ref != project_ref
            for value in (
                self.run_ref,
                self.task_ref,
                self.graph_ref,
                self.artifact_ref,
                self.event_ref,
            )
        ):
            raise CheckpointScopeError("RunCheckpoint Project scope differs")
        _validate_digest(self.task_digest, "RunCheckpoint Task digest")
        _validate_digest(self.graph_record_sha256, "RunCheckpoint Graph digest")
        if not isinstance(self.checkpoint_sequence, int) or self.checkpoint_sequence < 1:
            raise CheckpointContractError("RunCheckpoint sequence is malformed")
        if not isinstance(self.event_high_water_mark, int) or self.event_high_water_mark < 0:
            raise CheckpointContractError("RunCheckpoint Event high-water mark is malformed")
        if not isinstance(self.event_sequence, int) or self.event_sequence < 1:
            raise CheckpointContractError("RunCheckpoint Event sequence is malformed")
        if (self.event_anchor_ref is None) != (self.event_anchor_record_sha256 is None):
            raise CheckpointIntegrityError("RunCheckpoint Event anchor is incomplete")
        if self.event_anchor_ref is not None:
            if self.event_anchor_ref.project_ref != project_ref:
                raise CheckpointScopeError("RunCheckpoint Event anchor crossed Project")
            _validate_digest(
                self.event_anchor_record_sha256,
                "RunCheckpoint Event anchor digest",
            )
        if self.event_high_water_mark == 0 and self.event_anchor_ref is not None:
            raise CheckpointIntegrityError("Empty Event chain cannot have an anchor")
        if self.event_high_water_mark > 0 and self.event_anchor_ref is None:
            raise CheckpointIntegrityError("Non-empty Event chain requires an anchor")
        _validate_timestamp(self.created_at, "RunCheckpoint created_at")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        if not self.nodes or any(item.node_ref.graph_ref != self.graph_ref for item in self.nodes):
            raise CheckpointIntegrityError("RunCheckpoint Nodes differ from exact Graph")
        if len({item.node_ref for item in self.nodes}) != len(self.nodes):
            raise CheckpointIntegrityError("RunCheckpoint Node identities are duplicated")
        for name in (
            "completed_output_refs",
            "source_refs",
            "call_refs",
            "failure_refs",
            "continuation_refs",
        ):
            values = tuple(getattr(self, name))
            if len(values) > 4096:
                raise CheckpointContractError(f"RunCheckpoint {name} is unbounded")
            for value in values:
                _validate_opaque_ref(value, f"RunCheckpoint {name}")
            object.__setattr__(self, name, tuple(sorted(set(values))))
        self.content_ref.verify(self.serialized_state())
        semantic_digest = _sha256(self._envelope_payload())
        object.__setattr__(self, "semantic_digest", semantic_digest)
        object.__setattr__(
            self,
            "record_sha256",
            _sha256({"created_at": self.created_at, "semantic_digest": semantic_digest}),
        )

    @property
    def project_ref(self) -> ProjectRef:
        return self.checkpoint_ref.project_ref

    def state_payload(self) -> dict[str, object]:
        return {
            "call_refs": list(self.call_refs),
            "checkpoint_id": self.checkpoint_ref.checkpoint_id,
            "checkpoint_sequence": self.checkpoint_sequence,
            "completed_output_refs": list(self.completed_output_refs),
            "continuation_refs": list(self.continuation_refs),
            "created_at": self.created_at,
            "event_anchor_record_sha256": self.event_anchor_record_sha256,
            "event_anchor_ref": (
                None if self.event_anchor_ref is None else self.event_anchor_ref.value
            ),
            "event_high_water_mark": self.event_high_water_mark,
            "failure_refs": list(self.failure_refs),
            "graph_record_sha256": self.graph_record_sha256,
            "graph_ref": self.graph_ref.value,
            "nodes": [item.payload() for item in self.nodes],
            "project_ref": self.project_ref.value,
            "run_ref": _run_value(self.run_ref),
            "schema_version": self.schema_version,
            "source_refs": list(self.source_refs),
            "task_digest": self.task_digest,
            "task_ref": _task_value(self.task_ref),
            "workspace_snapshot_ref": (
                None
                if self.workspace_snapshot_ref is None
                else _content_payload(self.workspace_snapshot_ref)
            ),
        }

    def serialized_state(self) -> bytes:
        return _json(self.state_payload()).encode()

    def _envelope_payload(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref.value,
            "content_ref": _content_payload(self.content_ref),
            "event_ref": self.event_ref.value,
            "event_sequence": self.event_sequence,
            "state_sha256": hashlib.sha256(self.serialized_state()).hexdigest(),
        }


@dataclass(frozen=True)
class CheckpointNodeDecision:
    """One dependency-aware current-state-wins reconciliation result."""

    node_ref: NodeRef
    action: str
    causes: tuple[str, ...]
    reusable_output_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.action not in {"REUSE_CURRENT", "REUSE_CHECKPOINT", "CONTINUE", "INVALIDATE"}:
            raise CheckpointContractError("Checkpoint reconciliation action is malformed")
        object.__setattr__(self, "causes", tuple(self.causes))
        object.__setattr__(self, "reusable_output_refs", tuple(self.reusable_output_refs))

    def payload(self) -> dict[str, object]:
        return {
            "action": self.action,
            "causes": list(self.causes),
            "node_ref": self.node_ref.value,
            "reusable_output_refs": list(self.reusable_output_refs),
        }


@dataclass(frozen=True)
class CheckpointReconciliation:
    checkpoint_ref: RunCheckpointRef
    current_graph_ref: GraphRef
    decisions: tuple[CheckpointNodeDecision, ...]
    checkpoint_event_high_water_mark: int
    current_event_high_water_mark: int

    @property
    def reused_node_refs(self) -> tuple[NodeRef, ...]:
        return tuple(
            item.node_ref
            for item in self.decisions
            if item.action in {"REUSE_CURRENT", "REUSE_CHECKPOINT"}
        )

    @property
    def invalidated_node_refs(self) -> tuple[NodeRef, ...]:
        return tuple(item.node_ref for item in self.decisions if item.action == "INVALIDATE")

    def payload(self) -> dict[str, object]:
        return {
            "checkpoint_event_high_water_mark": self.checkpoint_event_high_water_mark,
            "checkpoint_ref": self.checkpoint_ref.value,
            "current_event_high_water_mark": self.current_event_high_water_mark,
            "current_graph_ref": self.current_graph_ref.value,
            "decisions": [item.payload() for item in self.decisions],
        }


@dataclass(frozen=True)
class ResumeResult:
    checkpoint: RunCheckpoint
    reconciliation: CheckpointReconciliation
    memory: RunMemory
    recovered_node_refs: tuple[NodeRef, ...]
    event: Event
    evidence_ref: ContentRef


@dataclass(frozen=True)
class _CheckpointStage:
    run: Run
    task: Task
    graph: Graph
    memory: RunMemory
    checkpoint_ref: RunCheckpointRef
    checkpoint_sequence: int
    created_at: str
    nodes: tuple[CheckpointNodeState, ...]
    completed_output_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    call_refs: tuple[str, ...]
    failure_refs: tuple[str, ...]
    event_anchor: Event | None
    serialized: bytes
    source_artifact_refs: tuple[ArtifactRef, ...]
    source_content_refs: tuple[ContentRef, ...]


class CheckpointReconciliationService:
    """Compare immutable checkpoint evidence with newer authoritative state."""

    def reconcile(
        self,
        checkpoint: RunCheckpoint,
        memory: RunMemory,
    ) -> CheckpointReconciliation:
        if checkpoint.project_ref != memory.project_ref:
            raise CheckpointScopeError("Checkpoint and Run Memory Projects differ")
        if checkpoint.run_ref != memory.run.run_ref:
            raise CheckpointConflictError("Checkpoint belongs to another Run")
        if (
            checkpoint.task_ref != memory.task.task_ref
            or not hmac.compare_digest(checkpoint.task_digest, memory.task.canonical_digest)
        ):
            raise CheckpointIntegrityError("Checkpoint Task revision or digest differs")
        if memory.current_graph_ref is None or not memory.graphs:
            raise CheckpointConflictError("Current Run has no Graph to resume")
        current_graph_memory = memory.graphs[-1]
        current_graph = current_graph_memory.graph
        if (
            current_graph.graph_id != checkpoint.graph_ref.graph_id
            or current_graph.revision < checkpoint.graph_ref.revision
        ):
            raise CheckpointConflictError(
                "Checkpoint Graph is incompatible with current durable Graph"
            )
        old = {item.node_ref.node_id: item for item in checkpoint.nodes}
        checkpoint_graph_memory = next(
            (
                item
                for item in memory.graphs
                if item.graph.graph_ref == checkpoint.graph_ref
            ),
            None,
        )
        if checkpoint_graph_memory is None:
            raise CheckpointIntegrityError(
                "Checkpoint Graph is absent from durable Run history"
            )
        checkpoint_nodes = {
            item.node_id: item for item in checkpoint_graph_memory.graph.nodes
        }
        current_states = {item.node_ref.node_id: item for item in current_graph_memory.nodes}
        current_nodes = {item.node_id: item for item in current_graph.nodes}
        invalid: set[str] = set()
        direct_causes: dict[str, tuple[str, ...]] = {}
        for node_id, node in current_nodes.items():
            prior = old.get(node_id)
            if prior is None:
                invalid.add(node_id)
                direct_causes[node_id] = ("node-added-after-checkpoint",)
                continue
            checkpoint_node = checkpoint_nodes.get(node_id)
            if checkpoint_node is None:
                invalid.add(node_id)
                direct_causes[node_id] = ("checkpoint-node-record-missing",)
                continue
            if self._compatibility_digest(node) != self._compatibility_digest(
                checkpoint_node
            ):
                old_sources = self._stable_sources(checkpoint_node)
                new_sources = self._stable_sources(node)
                changed_sources = tuple(
                    f"source:{value}"
                    for value in sorted(old_sources.symmetric_difference(new_sources))
                )
                invalid.add(node_id)
                direct_causes[node_id] = changed_sources or (
                    f"node-semantic-digest:{prior.node_semantic_digest}->{node.semantic_digest}",
                )
        propagated = True
        while propagated:
            propagated = False
            for node_id, node in current_nodes.items():
                if node_id in invalid:
                    continue
                affected = tuple(
                    dependency.node_id
                    for dependency in node.dependencies
                    if dependency.node_id in invalid
                )
                if affected:
                    invalid.add(node_id)
                    direct_causes[node_id] = tuple(
                        f"dependency:{dependency}" for dependency in sorted(affected)
                    )
                    propagated = True
        decisions: list[CheckpointNodeDecision] = []
        same_graph = current_graph.graph_ref == checkpoint.graph_ref
        for node_ref in current_graph.topological_order():
            node_id = node_ref.node_id
            current_memory_node = current_states[node_id]
            latest = current_memory_node.latest
            prior = old.get(node_id)
            if latest is not None and latest.status == "SUCCEEDED":
                decisions.append(
                    CheckpointNodeDecision(
                        node_ref,
                        "REUSE_CURRENT",
                        ("current-durable-state-wins",),
                        tuple(latest.outputs.values()),
                    )
                )
            elif (
                not same_graph
                and latest is not None
                and latest.status not in {"CREATED", "QUEUED", "READY"}
            ):
                decisions.append(
                    CheckpointNodeDecision(
                        node_ref,
                        "CONTINUE",
                        (f"newer-current-state:{latest.status}",),
                        (),
                    )
                )
            elif node_id in invalid:
                decisions.append(
                    CheckpointNodeDecision(
                        node_ref,
                        "INVALIDATE",
                        direct_causes[node_id],
                        (),
                    )
                )
            elif prior is not None and prior.status == "SUCCEEDED" and prior.output_refs:
                decisions.append(
                    CheckpointNodeDecision(
                        node_ref,
                        "REUSE_CHECKPOINT",
                        ("exact-compatible-node-and-inputs",),
                        prior.output_refs,
                    )
                )
            else:
                status = "UNINITIALIZED" if latest is None else latest.status
                decisions.append(
                    CheckpointNodeDecision(
                        node_ref,
                        "CONTINUE",
                        (f"current-state:{status}",),
                        (),
                    )
                )
        return CheckpointReconciliation(
            checkpoint.checkpoint_ref,
            current_graph.graph_ref,
            tuple(decisions),
            checkpoint.event_high_water_mark,
            memory.event_high_water_mark,
        )

    @staticmethod
    def _stable_sources(node: Node) -> set[str]:
        return {
            (
                f"node-output://{binding.source_ref.rsplit('/', 1)[-1]}/"
                f"{binding.output_key}"
                if binding.source_kind == "node_output"
                else binding.source_ref
            )
            for binding in node.input_bindings
        }

    @classmethod
    def _compatibility_digest(cls, node: Node) -> str:
        return _sha256(
            {
                "condition_ref": node.condition_ref,
                "dependencies": [item.node_id for item in node.dependencies],
                "evidence_requirements": list(node.evidence_requirements),
                "executor_kind": node.executor_kind,
                "inputs": [
                    {
                        "input_name": item.input_name,
                        "output_key": item.output_key,
                        "source_kind": item.source_kind,
                        "source_ref": (
                            f"node-output://{item.source_ref.rsplit('/', 1)[-1]}/"
                            f"{item.output_key}"
                            if item.source_kind == "node_output"
                            else item.source_ref
                        ),
                        "identity_digest": (
                            None if item.source_kind == "node_output" else item.identity_digest
                        ),
                    }
                    for item in node.input_bindings
                ],
                "node_id": node.node_id,
                "output_contract": dict(node.output_contract),
                "required_capabilities": [
                    item.value for item in node.required_capabilities
                ],
                "resource_hints": dict(node.resource_hints),
                "side_effect_requirement": node.side_effect_requirement,
            }
        )


class CheckpointService:
    """Create, verify, reconcile, and resume immutable Run checkpoints."""

    def __init__(
        self,
        database_path: str | Path,
        object_storage: ObjectStorageBackend,
    ) -> None:
        if not isinstance(object_storage, ObjectStorageBackend):
            raise CheckpointContractError("object_storage must implement ObjectStorageBackend")
        self.database_path = Path(database_path).resolve()
        self.object_storage = object_storage
        self.executions = NodeExecutionService(self.database_path)
        self.memories = RunMemoryService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.events = EventLedger(self.database_path)
        self.reconciliation = CheckpointReconciliationService()
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
                CREATE UNIQUE INDEX IF NOT EXISTS events_exact_checkpoint_anchor
                    ON events(project_id, event_id, record_sha256);
                CREATE UNIQUE INDEX IF NOT EXISTS artifacts_exact_checkpoint_anchor
                    ON artifact_revisions(project_id, artifact_id, revision, record_sha256);

                CREATE TABLE IF NOT EXISTS run_checkpoints (
                    project_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_revision INTEGER NOT NULL,
                    task_digest TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    graph_record_sha256 TEXT NOT NULL,
                    checkpoint_sequence INTEGER NOT NULL,
                    checkpoint_event_high_water_mark INTEGER NOT NULL,
                    content_json TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_revision INTEGER NOT NULL,
                    artifact_record_sha256 TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_sequence INTEGER NOT NULL,
                    event_record_sha256 TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, checkpoint_id),
                    UNIQUE (project_id, checkpoint_id, record_sha256),
                    UNIQUE (project_id, run_id, checkpoint_sequence),
                    UNIQUE (project_id, run_id, idempotency_key),
                    FOREIGN KEY (project_id, run_id) REFERENCES runs(project_id, run_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, task_id, task_revision, task_digest)
                        REFERENCES task_revisions(project_id, task_id, revision, canonical_digest)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, graph_id, graph_revision, graph_record_sha256)
                        REFERENCES graph_revisions(project_id, graph_id, revision, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, artifact_id, artifact_revision, artifact_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, event_id, event_record_sha256)
                        REFERENCES events(project_id, event_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS run_checkpoint_heads (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    checkpoint_sequence INTEGER NOT NULL,
                    checkpoint_record_sha256 TEXT NOT NULL,
                    event_sequence INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id),
                    FOREIGN KEY (project_id, checkpoint_id, checkpoint_record_sha256)
                        REFERENCES run_checkpoints(project_id, checkpoint_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS run_checkpoints_no_update
                BEFORE UPDATE ON run_checkpoints
                BEGIN SELECT RAISE(ABORT, 'Run checkpoints are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS run_checkpoints_no_delete
                BEFORE DELETE ON run_checkpoints
                BEGIN SELECT RAISE(ABORT, 'Run checkpoints cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS run_checkpoint_heads_no_delete
                BEFORE DELETE ON run_checkpoint_heads
                BEGIN SELECT RAISE(ABORT, 'Run checkpoint head cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS run_checkpoint_heads_monotonic
                BEFORE UPDATE ON run_checkpoint_heads
                WHEN NEW.project_id != OLD.project_id
                  OR NEW.run_id != OLD.run_id
                  OR NEW.checkpoint_sequence != OLD.checkpoint_sequence + 1
                  OR NEW.event_sequence <= OLD.event_sequence
                  OR NEW.updated_at < OLD.updated_at
                BEGIN SELECT RAISE(ABORT, 'Run checkpoint head must advance monotonically'); END;
                """
            )
        finally:
            connection.close()

    def create_checkpoint(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
        *,
        authority_attempt: ExecutionAttempt,
        idempotency_key: str,
        workspace_snapshot_ref: ContentRef | None = None,
        continuation_refs: Sequence[str] = (),
    ) -> RunCheckpoint:
        _validate_key(idempotency_key, "idempotency_key")
        if workspace_snapshot_ref is not None and not isinstance(
            workspace_snapshot_ref, ContentRef
        ):
            raise CheckpointContractError("workspace_snapshot_ref must be ContentRef")
        normalized_continuations = self._normalize_continuation_refs(continuation_refs)
        request_sha256 = _sha256(
            {
                "continuation_refs": list(normalized_continuations),
                "run_ref": _run_value(run_ref),
                "workspace_snapshot_ref": (
                    None
                    if workspace_snapshot_ref is None
                    else _content_payload(workspace_snapshot_ref)
                ),
            }
        )
        existing_checkpoint = self._load_idempotent_checkpoint(
            requesting_access,
            run_ref,
            idempotency_key,
            request_sha256,
        )
        if existing_checkpoint is not None:
            return existing_checkpoint

        staging = self._connect()
        try:
            staging.execute("BEGIN")
            run, task, graph = self.executions._context(
                staging,
                requesting_access,
                run_ref,
            )
            try:
                current_run = self.executions.runs.assert_current_run_authority_in_transaction(
                    staging,
                    requesting_access,
                    authority_attempt,
                )
            except (RunAuthorityError, RunError) as exc:
                raise CheckpointAuthorityError(
                    "Checkpoint creation requires current Run authority"
                ) from exc
            if current_run.run_ref != run_ref or current_run.status != "RUNNING":
                raise CheckpointAuthorityError(
                    "Only the current running Run may create a checkpoint"
                )
            memory = self.memories._reconstruct_in_snapshot(
                staging,
                requesting_access,
                run_ref,
            )
            if any(item.lease_expired for item in memory.graphs[-1].nodes):
                raise CheckpointConflictError(
                    "Checkpoint cannot claim an already stale Node fence"
                )
            checkpoint_sequence = cast(
                int,
                staging.execute(
                    """
                    SELECT COALESCE(MAX(checkpoint_sequence), 0) + 1
                    FROM run_checkpoints WHERE project_id = ? AND run_id = ?
                    """,
                    (run_ref.project_ref.value, run_ref.run_id),
                ).fetchone()[0],
            )
            checkpoint_ref = RunCheckpointRef.new(run.project_ref)
            created_at = self.executions._database_now(staging)
            node_summaries = self._snapshot_nodes(memory)
            completed_outputs = tuple(
                sorted(
                    {
                        output
                        for node in node_summaries
                        for output in node.output_refs
                    }
                )
            )
            source_refs = tuple(
                sorted({source for node in node_summaries for source in node.source_refs})
            )
            call_refs = tuple(
                sorted(
                    {
                        item.call_ref
                        for item in memory.extension_refs
                        if item.call_ref is not None
                    }
                )
            )
            failure_refs = tuple(
                sorted(
                    {
                        failure.failure_ref
                        for node in node_summaries
                        for failure in node.failures
                    }
                )
            )
            event_anchor = None if not memory.events else memory.events[-1]
            serialized = _json(
                self._state_payload(
                    checkpoint_ref=checkpoint_ref,
                    run_ref=run_ref,
                    task_ref=task.task_ref,
                    task_digest=task.canonical_digest,
                    graph=graph,
                    checkpoint_sequence=checkpoint_sequence,
                    created_at=created_at,
                    nodes=node_summaries,
                    completed_output_refs=completed_outputs,
                    source_refs=source_refs,
                    call_refs=call_refs,
                    failure_refs=failure_refs,
                    event_high_water_mark=memory.event_high_water_mark,
                    event_anchor=event_anchor,
                    workspace_snapshot_ref=workspace_snapshot_ref,
                    continuation_refs=normalized_continuations,
                )
            ).encode()
            source_artifacts, source_contents = self._artifact_sources(
                run.project_ref,
                completed_outputs,
                workspace_snapshot_ref,
            )
            stage = _CheckpointStage(
                run,
                task,
                graph,
                memory,
                checkpoint_ref,
                checkpoint_sequence,
                created_at,
                node_summaries,
                completed_outputs,
                source_refs,
                call_refs,
                failure_refs,
                event_anchor,
                serialized,
                source_artifacts,
                source_contents,
            )
            staging.commit()
        except ProjectScopeError as exc:
            staging.rollback()
            raise CheckpointScopeError("Checkpoint Project scope mismatch") from exc
        except Exception:
            staging.rollback()
            raise
        finally:
            staging.close()

        if workspace_snapshot_ref is not None and not self.object_storage.verify(
            workspace_snapshot_ref
        ):
            raise CheckpointIntegrityError(
                "Workspace snapshot content is missing or corrupt"
            )
        content_ref = self.object_storage.put(
            stage.serialized,
            media_type=_MEDIA_TYPE,
            expected_digest=hashlib.sha256(stage.serialized).hexdigest(),
            expected_size=len(stage.serialized),
        )

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT * FROM run_checkpoints
                WHERE project_id = ? AND run_id = ? AND idempotency_key = ?
                """,
                (run_ref.project_ref.value, run_ref.run_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if not hmac.compare_digest(
                    cast(str, existing["request_sha256"]), request_sha256
                ):
                    raise CheckpointConflictError(
                        "Checkpoint idempotency key has conflicting semantics"
                    )
                connection.commit()
                return self.get_checkpoint(
                    requesting_access,
                    RunCheckpointRef(
                        run_ref.project_ref,
                        cast(str, existing["checkpoint_id"]),
                    ),
                )
            run, task, graph = self.executions._context(
                connection,
                requesting_access,
                run_ref,
            )
            try:
                current_run = self.executions.runs.assert_current_run_authority_in_transaction(
                    connection,
                    requesting_access,
                    authority_attempt,
                )
            except (RunAuthorityError, RunError) as exc:
                raise CheckpointAuthorityError(
                    "Checkpoint creation requires current Run authority"
                ) from exc
            if current_run.run_ref != run_ref or current_run.status != "RUNNING":
                raise CheckpointAuthorityError(
                    "Only the current running Run may create a checkpoint"
                )
            memory = self.memories._reconstruct_in_snapshot(
                connection,
                requesting_access,
                run_ref,
            )
            next_sequence = cast(
                int,
                connection.execute(
                    """
                    SELECT COALESCE(MAX(checkpoint_sequence), 0) + 1
                    FROM run_checkpoints WHERE project_id = ? AND run_id = ?
                    """,
                    (run_ref.project_ref.value, run_ref.run_id),
                ).fetchone()[0],
            )
            if (
                run != stage.run
                or task != stage.task
                or graph != stage.graph
                or not hmac.compare_digest(
                    memory.semantic_digest,
                    stage.memory.semantic_digest,
                )
                or next_sequence != stage.checkpoint_sequence
            ):
                raise CheckpointConflictError(
                    "Run changed while checkpoint content was staged"
                )
            artifact = Artifact(
                artifact_ref=ArtifactRef(stage.run.project_ref, f"art_{uuid4().hex}", 1),
                role="run.checkpoint",
                content_ref=content_ref,
                source_refs=(),
                source_artifact_refs=stage.source_artifact_refs,
                source_content_refs=stage.source_content_refs,
                derivation_type="run.checkpoint.snapshot",
                producer_run_ref=run_ref,
                producer_attempt_id=authority_attempt.attempt_id,
                producer_fence=authority_attempt.fence,
                metadata={
                    "schema_version": _SCHEMA_VERSION,
                    "semantic_label": "run-checkpoint",
                },
                created_at=stage.created_at,
            )
            self.artifacts._verify_source_artifacts_in_transaction(
                connection,
                stage.run.project_ref,
                stage.source_artifact_refs,
            )
            self.artifacts._insert_artifact(connection, artifact)
            self.artifacts._insert_source_bindings(connection, artifact)
            self.artifacts._insert_derivation(connection, artifact)
            self.artifacts._insert_initial_head(connection, artifact)
            event = self.events._append_in_transaction(
                connection,
                requesting_access,
                project_ref=stage.run.project_ref,
                task_ref=stage.task.task_ref,
                run_ref=run_ref,
                graph_ref=stage.graph.graph_ref,
                node_ref=None,
                event_type="RUN_CHECKPOINT",
                idempotency_key=self._event_key("checkpoint", run_ref, idempotency_key),
                actor_ref=authority_attempt.owner_ref,
                object_refs=(artifact.artifact_ref, content_ref),
                metadata={
                    "checkpoint_ref": stage.checkpoint_ref.value,
                    "checkpoint_sequence": stage.checkpoint_sequence,
                    "schema_version": _SCHEMA_VERSION,
                },
                payload_ref=content_ref,
                authority_attempt=authority_attempt,
                require_run_authority=True,
                known_artifacts={artifact.artifact_ref.value: artifact},
            )
            checkpoint = RunCheckpoint(
                stage.checkpoint_ref,
                _SCHEMA_VERSION,
                run_ref,
                stage.task.task_ref,
                stage.task.canonical_digest,
                stage.graph.graph_ref,
                stage.graph.record_sha256,
                stage.checkpoint_sequence,
                stage.created_at,
                stage.nodes,
                stage.completed_output_refs,
                stage.source_refs,
                stage.call_refs,
                stage.failure_refs,
                stage.memory.event_high_water_mark,
                None if stage.event_anchor is None else stage.event_anchor.event_ref,
                None if stage.event_anchor is None else stage.event_anchor.record_sha256,
                workspace_snapshot_ref,
                normalized_continuations,
                content_ref,
                artifact.artifact_ref,
                event.event_ref,
                cast(int, event.sequence),
            )
            self._insert_checkpoint(
                connection,
                checkpoint,
                idempotency_key,
                request_sha256,
                artifact.record_sha256,
                event.record_sha256,
            )
            self._advance_head(connection, checkpoint)
            connection.commit()
            return checkpoint
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            if "injected" in str(exc):
                raise
            raise CheckpointConflictError("Checkpoint publication conflicts") from exc
        except (CheckpointError, ObjectStorageError):
            connection.rollback()
            raise
        except ProjectScopeError as exc:
            connection.rollback()
            raise CheckpointScopeError("Checkpoint Project scope mismatch") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _load_idempotent_checkpoint(
        self,
        access: ProjectAccess,
        run_ref: RunRef,
        idempotency_key: str,
        request_sha256: str,
    ) -> RunCheckpoint | None:
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            row = connection.execute(
                """
                SELECT * FROM run_checkpoints
                WHERE project_id = ? AND run_id = ? AND idempotency_key = ?
                """,
                (run_ref.project_ref.value, run_ref.run_id, idempotency_key),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            if not hmac.compare_digest(
                cast(str, row["request_sha256"]),
                request_sha256,
            ):
                raise CheckpointConflictError(
                    "Checkpoint idempotency key has conflicting semantics"
                )
            checkpoint = self._checkpoint_from_row(
                connection,
                access,
                cast(sqlite3.Row, row),
            )
            connection.commit()
            return checkpoint
        except ProjectScopeError as exc:
            connection.rollback()
            raise CheckpointScopeError("Checkpoint Project scope mismatch") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def createCheckpoint(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
        *,
        authority_attempt: ExecutionAttempt,
        idempotency_key: str,
        workspace_snapshot_ref: ContentRef | None = None,
        continuation_refs: Sequence[str] = (),
    ) -> RunCheckpoint:
        return self.create_checkpoint(
            requesting_access,
            run_ref,
            authority_attempt=authority_attempt,
            idempotency_key=idempotency_key,
            workspace_snapshot_ref=workspace_snapshot_ref,
            continuation_refs=continuation_refs,
        )

    def get_checkpoint(
        self,
        requesting_access: ProjectAccess,
        checkpoint_ref: RunCheckpointRef,
    ) -> RunCheckpoint:
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            checkpoint = self._fetch_checkpoint(
                connection,
                requesting_access,
                checkpoint_ref,
            )
            connection.commit()
            return checkpoint
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_latest_checkpoint(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> RunCheckpoint | None:
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self.executions._context_allowing_no_graph(
                connection,
                requesting_access,
                run_ref,
            )
            row = connection.execute(
                """
                SELECT * FROM run_checkpoint_heads
                WHERE project_id = ? AND run_id = ?
                """,
                (run_ref.project_ref.value, run_ref.run_id),
            ).fetchone()
            if row is None:
                checkpoint = None
            else:
                checkpoint = self._fetch_checkpoint(
                    connection,
                    requesting_access,
                    RunCheckpointRef(run_ref.project_ref, cast(str, row["checkpoint_id"])),
                )
                expected_head = self._head_sha256(checkpoint)
                if (
                    row["checkpoint_sequence"] != checkpoint.checkpoint_sequence
                    or row["checkpoint_record_sha256"] != checkpoint.record_sha256
                    or row["event_sequence"] != checkpoint.event_sequence
                    or row["updated_at"] != checkpoint.created_at
                    or not hmac.compare_digest(
                        cast(str, row["record_sha256"]), expected_head
                    )
                ):
                    raise CheckpointIntegrityError(
                        "Run checkpoint latest-ref head differs"
                    )
            connection.commit()
            return checkpoint
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def resume_run(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
        *,
        checkpoint_ref: RunCheckpointRef,
        authority_attempt: ExecutionAttempt,
        idempotency_key: str,
    ) -> ResumeResult:
        _validate_key(idempotency_key, "idempotency_key")
        checkpoint = self.get_checkpoint(requesting_access, checkpoint_ref)
        if checkpoint.run_ref != run_ref:
            raise CheckpointConflictError("Checkpoint belongs to another Run")
        event_key = self._event_key("resume", run_ref, idempotency_key)

        staging = self._connect()
        try:
            staging.execute("BEGIN")
            replay = self._idempotent_resume(
                staging,
                requesting_access,
                run_ref,
                checkpoint,
                event_key,
                idempotency_key,
            )
            if replay is not None:
                staging.commit()
                return replay
            memory = self.memories._reconstruct_in_snapshot(
                staging,
                requesting_access,
                run_ref,
            )
            if memory.run.status in _TERMINAL_RUN_STATUSES:
                raise CheckpointConflictError("Terminal or cancelled Run cannot resume")
            try:
                current_run = self.executions.runs.assert_current_run_authority_in_transaction(
                    staging,
                    requesting_access,
                    authority_attempt,
                )
            except (RunAuthorityError, RunError) as exc:
                raise CheckpointAuthorityError(
                    "Run resume requires current fenced controller authority"
                ) from exc
            if current_run.run_ref != run_ref or current_run.status != "RUNNING":
                raise CheckpointAuthorityError("Run resume authority is not current")
            reconciliation = self.reconciliation.reconcile(checkpoint, memory)
            recovered_refs = tuple(
                item.node_ref
                for item in memory.graphs[-1].nodes
                if item.latest is not None
                and item.latest.status in _ACTIVE_NODE_STATUSES
                and item.latest.current_attempt_id is not None
                and item.lease_expired
            )
            staging.commit()
        except ProjectScopeError as exc:
            staging.rollback()
            raise CheckpointScopeError("Checkpoint Project scope mismatch") from exc
        except Exception:
            staging.rollback()
            raise
        finally:
            staging.close()

        evidence_payload = {
            **reconciliation.payload(),
            "recovered_node_refs": [item.value for item in recovered_refs],
            "resume_idempotency_key": idempotency_key,
        }
        evidence_bytes = _json(evidence_payload).encode()
        evidence_ref = self.object_storage.put(
            evidence_bytes,
            media_type="application/vnd.minitz.checkpoint-reconciliation+json",
            expected_digest=hashlib.sha256(evidence_bytes).hexdigest(),
            expected_size=len(evidence_bytes),
        )

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_event = connection.execute(
                """
                SELECT event_id FROM events
                WHERE project_id = ? AND run_id = ? AND idempotency_key = ?
                """,
                (run_ref.project_ref.value, run_ref.run_id, event_key),
            ).fetchone()
            if existing_event is not None:
                connection.commit()
                return self._load_idempotent_resume(
                    requesting_access,
                    run_ref,
                    checkpoint,
                    event_key,
                    idempotency_key,
                )
            self._revalidate_checkpoint_envelope(
                connection,
                requesting_access,
                checkpoint,
            )
            try:
                current_run = self.executions.runs.assert_current_run_authority_in_transaction(
                    connection,
                    requesting_access,
                    authority_attempt,
                )
            except (RunAuthorityError, RunError) as exc:
                raise CheckpointAuthorityError(
                    "Run resume requires current fenced controller authority"
                ) from exc
            if current_run.run_ref != run_ref or current_run.status != "RUNNING":
                raise CheckpointAuthorityError("Run resume authority is not current")
            current_memory = self.memories._reconstruct_in_snapshot(
                connection,
                requesting_access,
                run_ref,
            )
            if current_memory.run.status in _TERMINAL_RUN_STATUSES:
                raise CheckpointConflictError("Terminal or cancelled Run cannot resume")
            if not hmac.compare_digest(
                current_memory.semantic_digest,
                memory.semantic_digest,
            ):
                raise CheckpointConflictError(
                    "Run changed while resume evidence was staged"
                )
            run, task, graph = self.executions._context(
                connection,
                requesting_access,
                run_ref,
            )
            self.executions._sync_graph(connection, run, task, graph, {})
            now = self.executions._database_now(connection)
            recovered: list[NodeRef] = []
            for node_ref in recovered_refs:
                current = self.executions._fetch_execution(connection, node_ref)
                if (
                    current.status not in _ACTIVE_NODE_STATUSES
                    or current.lease_expires_at is None
                    or current.lease_expires_at > now
                    or current.current_attempt_id is None
                ):
                    raise CheckpointConflictError(
                        "Expired Node fence changed during resume staging"
                    )
                attempt = self.executions._fetch_attempt(
                    connection,
                    current.node_ref,
                    current.current_attempt_id,
                )
                self.executions._complete_attempt(
                    connection,
                    attempt,
                    current.lease_expires_at,
                    "STALE",
                )
                stale = self.executions._next_state(current, "STALE", now)
                self.executions._append_state(connection, current, stale)
                recovered.append(current.node_ref)
            self.executions._refresh_ready(
                connection,
                run,
                task,
                graph,
                include_stale=True,
            )
            self._materialize_checkpoint_reuse(
                connection,
                requesting_access,
                run,
                task,
                graph,
                authority_attempt,
                checkpoint,
                current_memory,
                reconciliation,
                idempotency_key,
            )
            self.executions._refresh_ready(connection, run, task, graph)
            event = self.events._append_in_transaction(
                connection,
                requesting_access,
                project_ref=run.project_ref,
                task_ref=task.task_ref,
                run_ref=run_ref,
                graph_ref=graph.graph_ref,
                node_ref=None,
                event_type="RUN_RESUMED",
                idempotency_key=event_key,
                actor_ref=authority_attempt.owner_ref,
                object_refs=(checkpoint.artifact_ref, checkpoint.content_ref, evidence_ref),
                metadata={
                    "checkpoint_ref": checkpoint.checkpoint_ref.value,
                    "invalidated_count": len(reconciliation.invalidated_node_refs),
                    "recovered_count": len(recovered),
                    "reused_count": len(reconciliation.reused_node_refs),
                },
                payload_ref=evidence_ref,
                authority_attempt=authority_attempt,
                require_run_authority=True,
            )
            self.executions._complete_run_if_ready(
                connection,
                requesting_access,
                run,
                task,
                graph,
            )
            resumed_memory = self.memories._reconstruct_in_snapshot(
                connection,
                requesting_access,
                run_ref,
            )
            connection.commit()
            return ResumeResult(
                checkpoint,
                reconciliation,
                resumed_memory,
                tuple(recovered),
                event,
                evidence_ref,
            )
        except (CheckpointError, ObjectStorageError):
            connection.rollback()
            raise
        except ProjectScopeError as exc:
            connection.rollback()
            raise CheckpointScopeError("Checkpoint Project scope mismatch") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _load_idempotent_resume(
        self,
        access: ProjectAccess,
        run_ref: RunRef,
        checkpoint: RunCheckpoint,
        event_key: str,
        request_key: str,
    ) -> ResumeResult:
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            result = self._idempotent_resume(
                connection,
                access,
                run_ref,
                checkpoint,
                event_key,
                request_key,
            )
            if result is None:
                raise CheckpointConflictError(
                    "Resume idempotency evidence disappeared"
                )
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _materialize_checkpoint_reuse(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        run: Run,
        task: Task,
        graph: Graph,
        authority_attempt: ExecutionAttempt,
        checkpoint: RunCheckpoint,
        memory: RunMemory,
        reconciliation: CheckpointReconciliation,
        resume_idempotency_key: str,
    ) -> None:
        checkpoint_graph = next(
            item for item in memory.graphs if item.graph.graph_ref == checkpoint.graph_ref
        )
        prior_nodes = {item.node_ref.node_id: item for item in checkpoint_graph.nodes}
        checkpoint_summaries = {
            item.node_ref.node_id: item for item in checkpoint.nodes
        }
        current_nodes = {item.node_id: item for item in graph.nodes}
        for decision in reconciliation.decisions:
            if decision.action != "REUSE_CHECKPOINT":
                continue
            self.executions._refresh_ready(connection, run, task, graph)
            current = self.executions._fetch_execution(connection, decision.node_ref)
            if current.status == "SUCCEEDED":
                continue
            if current.status != "READY":
                raise CheckpointConflictError(
                    "Reusable checkpoint Node is not durably READY"
                )
            prior_memory = prior_nodes[decision.node_ref.node_id]
            summary = checkpoint_summaries[decision.node_ref.node_id]
            prior = prior_memory.latest
            node = current_nodes[decision.node_ref.node_id]
            if (
                prior is None
                or prior.status != "SUCCEEDED"
                or prior.state_sha256 != summary.state_sha256
                or tuple(sorted(prior.outputs.values()))
                != decision.reusable_output_refs
                or set(prior.outputs) != set(node.output_contract)
                or set(prior.evidence) != set(node.evidence_requirements)
            ):
                raise CheckpointIntegrityError(
                    "Reusable checkpoint output no longer matches exact Node contract"
                )
            artifacts, artifact_refs = self._binding_artifacts(
                connection,
                run.run_ref,
                tuple(prior.outputs.values()) + tuple(prior.evidence.values()),
            )
            now, expires_at = self.executions.runs._database_lease_times(
                connection,
                60.0,
            )
            attempt_number = self.executions._next_attempt_number(
                connection,
                decision.node_ref,
            )
            attempt = NodeExecutionAttempt(
                f"natt_{uuid4().hex}",
                decision.node_ref,
                run.run_ref,
                task.task_ref,
                task.canonical_digest,
                attempt_number,
                current.current_fence + 1,
                "executor://checkpoint-reconciliation",
                authority_attempt.attempt_id,
                authority_attempt.fence,
                now,
                expires_at,
            )
            self.executions._insert_attempt(connection, attempt)
            leased = self.executions._next_state(
                current,
                "LEASED",
                now,
                attempt=attempt,
                lease_expires_at=expires_at,
            )
            self.executions._append_state(connection, current, leased)
            running = self.executions._next_state(
                leased,
                "RUNNING",
                now,
                attempt=attempt,
                lease_expires_at=expires_at,
            )
            self.executions._append_state(connection, leased, running)
            self.executions._insert_bindings(
                connection,
                decision.node_ref,
                "output",
                prior.outputs,
                artifacts,
            )
            self.executions._insert_bindings(
                connection,
                decision.node_ref,
                "evidence",
                prior.evidence,
                artifacts,
            )
            self.executions._complete_attempt(
                connection,
                attempt,
                now,
                "SUCCEEDED",
            )
            succeeded = self.executions._next_state(
                running,
                "SUCCEEDED",
                now,
                outputs=prior.outputs,
                evidence=prior.evidence,
            )
            self.executions._append_state(connection, running, succeeded)
            self.events._append_in_transaction(
                connection,
                access,
                project_ref=run.project_ref,
                task_ref=task.task_ref,
                run_ref=run.run_ref,
                graph_ref=graph.graph_ref,
                node_ref=decision.node_ref,
                event_type="NODE_OUTPUT_REUSED",
                idempotency_key=self._event_key(
                    f"reuse-{decision.node_ref.node_id}",
                    run.run_ref,
                    resume_idempotency_key,
                ),
                actor_ref=attempt.owner_ref,
                object_refs=artifact_refs,
                metadata={
                    "checkpoint_ref": checkpoint.checkpoint_ref.value,
                    "fence": attempt.fence,
                    "source_graph_revision": checkpoint.graph_ref.revision,
                    "state_version": succeeded.state_version,
                },
                payload_ref=None,
                authority_attempt=authority_attempt,
                require_run_authority=True,
            )

    def _binding_artifacts(
        self,
        connection: sqlite3.Connection,
        run_ref: RunRef,
        values: tuple[str, ...],
    ) -> tuple[dict[str, Artifact], tuple[ArtifactRef, ...]]:
        artifacts: dict[str, Artifact] = {}
        refs: list[ArtifactRef] = []
        for value in values:
            matched = re.fullmatch(
                r"artifact://(prj_[0-9a-f]{32})/(art_[0-9a-f]{32})/([1-9][0-9]*)",
                value,
            )
            if matched is None:
                if re.fullmatch(
                    r"content://sha256/[0-9a-f]{64}\?size=(?:0|[1-9][0-9]*)",
                    value,
                ) is None:
                    raise CheckpointIntegrityError(
                        "Reusable checkpoint binding is not an exact object ref"
                    )
                continue
            if matched.group(1) != run_ref.project_ref.value:
                raise CheckpointScopeError(
                    "Reusable checkpoint Artifact crossed Project scope"
                )
            artifact_ref = ArtifactRef(
                run_ref.project_ref,
                matched.group(2),
                int(matched.group(3)),
            )
            try:
                artifact = self.artifacts._fetch_artifact(connection, artifact_ref)
            except ArtifactError as exc:
                raise CheckpointIntegrityError(
                    "Reusable checkpoint Artifact failed exact verification"
                ) from exc
            if artifact.producer_run_ref != run_ref:
                raise CheckpointIntegrityError(
                    "Reusable checkpoint Artifact belongs to another Run"
                )
            artifacts[value] = artifact
            refs.append(artifact_ref)
        return artifacts, tuple(sorted(set(refs)))

    def resumeRun(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
        *,
        checkpoint_ref: RunCheckpointRef,
        authority_attempt: ExecutionAttempt,
        idempotency_key: str,
    ) -> ResumeResult:
        return self.resume_run(
            requesting_access,
            run_ref,
            checkpoint_ref=checkpoint_ref,
            authority_attempt=authority_attempt,
            idempotency_key=idempotency_key,
        )

    def _idempotent_resume(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        run_ref: RunRef,
        checkpoint: RunCheckpoint,
        event_key: str,
        request_key: str,
    ) -> ResumeResult | None:
        row = connection.execute(
            """
            SELECT * FROM events
            WHERE project_id = ? AND run_id = ? AND idempotency_key = ?
            """,
            (run_ref.project_ref.value, run_ref.run_id, event_key),
        ).fetchone()
        if row is None:
            return None
        event = self.events._event_from_row(connection, cast(sqlite3.Row, row))
        self.events._fetch_verified_run_events(connection, run_ref)
        if (
            event.event_type != "RUN_RESUMED"
            or event.run_ref != run_ref
            or event.metadata.get("checkpoint_ref") != checkpoint.checkpoint_ref.value
            or event.payload_ref is None
        ):
            raise CheckpointConflictError(
                "Resume idempotency key has conflicting durable semantics"
            )
        try:
            loaded: object = json.loads(self.object_storage.read(event.payload_ref).decode())
        except (ObjectStorageError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CheckpointIntegrityError(
                "Resume reconciliation evidence is missing or corrupt"
            ) from exc
        if not isinstance(loaded, dict):
            raise CheckpointIntegrityError("Resume reconciliation evidence is malformed")
        evidence = cast(dict[str, object], loaded)
        if evidence.get("resume_idempotency_key") != request_key:
            raise CheckpointConflictError(
                "Resume evidence idempotency semantics conflict"
            )
        reconciliation = self._reconciliation_from_payload(evidence, checkpoint)
        recovered_values = evidence.get("recovered_node_refs")
        if not isinstance(recovered_values, list):
            raise CheckpointIntegrityError("Resume recovered Node refs are malformed")
        recovered = tuple(
            self._parse_node_ref(cast(str, value), reconciliation.current_graph_ref)
            for value in recovered_values
        )
        memory = self.memories._reconstruct_in_snapshot(connection, access, run_ref)
        return ResumeResult(
            checkpoint,
            reconciliation,
            memory,
            recovered,
            event,
            event.payload_ref,
        )

    def _reconciliation_from_payload(
        self,
        value: Mapping[str, object],
        checkpoint: RunCheckpoint,
    ) -> CheckpointReconciliation:
        try:
            current_graph_ref = self._parse_graph_ref(
                cast(str, value["current_graph_ref"]),
                checkpoint.project_ref,
            )
            raw_decisions = value["decisions"]
            if not isinstance(raw_decisions, list):
                raise CheckpointIntegrityError(
                    "Resume reconciliation decisions are malformed"
                )
            decisions: list[CheckpointNodeDecision] = []
            for raw in raw_decisions:
                if not isinstance(raw, dict):
                    raise CheckpointIntegrityError(
                        "Resume reconciliation decision is malformed"
                    )
                item = cast(dict[str, object], raw)
                decisions.append(
                    CheckpointNodeDecision(
                        self._parse_node_ref(
                            cast(str, item["node_ref"]),
                            current_graph_ref,
                        ),
                        cast(str, item["action"]),
                        self._text_tuple(item["causes"]),
                        self._text_tuple(item["reusable_output_refs"]),
                    )
                )
            return CheckpointReconciliation(
                checkpoint.checkpoint_ref,
                current_graph_ref,
                tuple(decisions),
                cast(int, value["checkpoint_event_high_water_mark"]),
                cast(int, value["current_event_high_water_mark"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CheckpointIntegrityError(
                "Resume reconciliation evidence is malformed"
            ) from exc

    @staticmethod
    def _normalize_continuation_refs(values: Sequence[str]) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise CheckpointContractError("continuation_refs must be a sequence")
        if len(values) > 128:
            raise CheckpointContractError("continuation_refs is unbounded")
        return tuple(sorted({_validate_opaque_ref(value, "continuation_ref") for value in values}))

    @staticmethod
    def _event_key(operation: str, run_ref: RunRef, idempotency_key: str) -> str:
        digest = hashlib.sha256(
            f"{operation}\x00{_run_value(run_ref)}\x00{idempotency_key}".encode()
        ).hexdigest()
        return f"p106-{operation}-{digest}"

    def _snapshot_nodes(self, memory: RunMemory) -> tuple[CheckpointNodeState, ...]:
        graph_memory = memory.graphs[-1]
        nodes = {item.node_ref: item for item in graph_memory.graph.nodes}
        summaries: list[CheckpointNodeState] = []
        for item in graph_memory.nodes:
            node = nodes[item.node_ref]
            latest = item.latest
            attempts = tuple(
                CheckpointAttemptRef(
                    attempt.attempt.attempt_id,
                    attempt.attempt.attempt_number,
                    attempt.attempt.fence,
                    attempt.attempt.run_attempt_id,
                    attempt.attempt.run_fence,
                    attempt.attempt.record_sha256,
                    attempt.completion_sha256,
                    attempt.outcome,
                )
                for attempt in item.attempts
            )
            failures = tuple(
                CheckpointFailureRef(
                    self._failure_ref(failure.node_ref, failure.attempt_id),
                    failure.category,
                    failure.retry_possible,
                    failure.record_sha256,
                )
                for failure in item.failures
            )
            summaries.append(
                CheckpointNodeState(
                    item.node_ref,
                    node.record_sha256,
                    node.semantic_digest,
                    None if latest is None else latest.status,
                    None if latest is None else latest.state_version,
                    None if latest is None else latest.state_sha256,
                    None if latest is None else latest.current_attempt_id,
                    None if latest is None else latest.current_attempt_number,
                    0 if latest is None else latest.current_fence,
                    None if latest is None else latest.current_run_attempt_id,
                    None if latest is None else latest.current_run_fence,
                    tuple(binding.source_ref for binding in node.input_bindings),
                    () if latest is None else tuple(latest.outputs.values()),
                    () if latest is None else tuple(latest.evidence.values()),
                    attempts,
                    failures,
                )
            )
        return tuple(summaries)

    @staticmethod
    def _failure_ref(node_ref: NodeRef, attempt_id: str) -> str:
        return (
            f"node-failure://{node_ref.project_ref.value}/"
            f"{node_ref.graph_ref.graph_id}/{node_ref.graph_ref.revision}/"
            f"{node_ref.node_id}/{attempt_id}"
        )

    @staticmethod
    def _state_payload(
        *,
        checkpoint_ref: RunCheckpointRef,
        run_ref: RunRef,
        task_ref: TaskRef,
        task_digest: str,
        graph: Graph,
        checkpoint_sequence: int,
        created_at: str,
        nodes: tuple[CheckpointNodeState, ...],
        completed_output_refs: tuple[str, ...],
        source_refs: tuple[str, ...],
        call_refs: tuple[str, ...],
        failure_refs: tuple[str, ...],
        event_high_water_mark: int,
        event_anchor: Event | None,
        workspace_snapshot_ref: ContentRef | None,
        continuation_refs: tuple[str, ...],
    ) -> dict[str, object]:
        return {
            "call_refs": list(call_refs),
            "checkpoint_id": checkpoint_ref.checkpoint_id,
            "checkpoint_sequence": checkpoint_sequence,
            "completed_output_refs": list(completed_output_refs),
            "continuation_refs": list(continuation_refs),
            "created_at": created_at,
            "event_anchor_record_sha256": (
                None if event_anchor is None else event_anchor.record_sha256
            ),
            "event_anchor_ref": None if event_anchor is None else event_anchor.event_ref.value,
            "event_high_water_mark": event_high_water_mark,
            "failure_refs": list(failure_refs),
            "graph_record_sha256": graph.record_sha256,
            "graph_ref": graph.graph_ref.value,
            "nodes": [item.payload() for item in nodes],
            "project_ref": checkpoint_ref.project_ref.value,
            "run_ref": _run_value(run_ref),
            "schema_version": _SCHEMA_VERSION,
            "source_refs": list(source_refs),
            "task_digest": task_digest,
            "task_ref": _task_value(task_ref),
            "workspace_snapshot_ref": (
                None
                if workspace_snapshot_ref is None
                else _content_payload(workspace_snapshot_ref)
            ),
        }

    @staticmethod
    def _artifact_sources(
        project_ref: ProjectRef,
        completed_outputs: tuple[str, ...],
        workspace_snapshot_ref: ContentRef | None,
    ) -> tuple[tuple[ArtifactRef, ...], tuple[ContentRef, ...]]:
        artifact_refs: list[ArtifactRef] = []
        content_refs: list[ContentRef] = []
        for value in completed_outputs:
            matched = re.fullmatch(
                r"artifact://(prj_[0-9a-f]{32})/(art_[0-9a-f]{32})/([1-9][0-9]*)",
                value,
            )
            if matched is not None:
                if matched.group(1) != project_ref.value:
                    raise CheckpointScopeError("Checkpoint output crossed Project scope")
                artifact_refs.append(
                    ArtifactRef(project_ref, matched.group(2), int(matched.group(3)))
                )
        if workspace_snapshot_ref is not None:
            content_refs.append(workspace_snapshot_ref)
        return tuple(sorted(set(artifact_refs))), tuple(sorted(set(content_refs)))

    def _insert_checkpoint(
        self,
        connection: sqlite3.Connection,
        checkpoint: RunCheckpoint,
        idempotency_key: str,
        request_sha256: str,
        artifact_record_sha256: str,
        event_record_sha256: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO run_checkpoints (
                project_id, checkpoint_id, schema_version, run_id,
                task_id, task_revision, task_digest, graph_id, graph_revision,
                graph_record_sha256, checkpoint_sequence,
                checkpoint_event_high_water_mark, content_json,
                artifact_id, artifact_revision, artifact_record_sha256,
                event_id, event_sequence, event_record_sha256,
                idempotency_key, request_sha256, created_at,
                semantic_digest, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint.project_ref.value,
                checkpoint.checkpoint_ref.checkpoint_id,
                checkpoint.schema_version,
                checkpoint.run_ref.run_id,
                checkpoint.task_ref.task_id,
                checkpoint.task_ref.revision,
                checkpoint.task_digest,
                checkpoint.graph_ref.graph_id,
                checkpoint.graph_ref.revision,
                checkpoint.graph_record_sha256,
                checkpoint.checkpoint_sequence,
                checkpoint.event_high_water_mark,
                _json(_content_payload(checkpoint.content_ref)),
                checkpoint.artifact_ref.artifact_id,
                checkpoint.artifact_ref.revision,
                artifact_record_sha256,
                checkpoint.event_ref.event_id,
                checkpoint.event_sequence,
                event_record_sha256,
                idempotency_key,
                request_sha256,
                checkpoint.created_at,
                checkpoint.semantic_digest,
                checkpoint.record_sha256,
            ),
        )

    def _advance_head(
        self,
        connection: sqlite3.Connection,
        checkpoint: RunCheckpoint,
    ) -> None:
        head_sha = self._head_sha256(checkpoint)
        existing = connection.execute(
            """
            SELECT * FROM run_checkpoint_heads
            WHERE project_id = ? AND run_id = ?
            """,
            (checkpoint.project_ref.value, checkpoint.run_ref.run_id),
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO run_checkpoint_heads VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.project_ref.value,
                    checkpoint.run_ref.run_id,
                    checkpoint.checkpoint_ref.checkpoint_id,
                    checkpoint.checkpoint_sequence,
                    checkpoint.record_sha256,
                    checkpoint.event_sequence,
                    checkpoint.created_at,
                    head_sha,
                ),
            )
            return
        prior_sequence = cast(int, existing["checkpoint_sequence"])
        updated = connection.execute(
            """
            UPDATE run_checkpoint_heads
            SET checkpoint_id = ?, checkpoint_sequence = ?,
                checkpoint_record_sha256 = ?, event_sequence = ?,
                updated_at = ?, record_sha256 = ?
            WHERE project_id = ? AND run_id = ? AND checkpoint_sequence = ?
              AND checkpoint_record_sha256 = ? AND record_sha256 = ?
            """,
            (
                checkpoint.checkpoint_ref.checkpoint_id,
                checkpoint.checkpoint_sequence,
                checkpoint.record_sha256,
                checkpoint.event_sequence,
                checkpoint.created_at,
                head_sha,
                checkpoint.project_ref.value,
                checkpoint.run_ref.run_id,
                prior_sequence,
                existing["checkpoint_record_sha256"],
                existing["record_sha256"],
            ),
        )
        if updated.rowcount != 1:
            raise CheckpointConflictError("Run checkpoint head changed concurrently")

    @staticmethod
    def _head_sha256(checkpoint: RunCheckpoint) -> str:
        return _sha256(
            {
                "checkpoint_id": checkpoint.checkpoint_ref.checkpoint_id,
                "checkpoint_record_sha256": checkpoint.record_sha256,
                "checkpoint_sequence": checkpoint.checkpoint_sequence,
                "event_sequence": checkpoint.event_sequence,
                "project_id": checkpoint.project_ref.value,
                "run_id": checkpoint.run_ref.run_id,
                "updated_at": checkpoint.created_at,
            }
        )

    def _fetch_checkpoint(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        checkpoint_ref: RunCheckpointRef,
    ) -> RunCheckpoint:
        try:
            authorized = self.executions.projects._authorize(connection, access)
        except ProjectScopeError as exc:
            raise CheckpointScopeError("Checkpoint Project scope mismatch") from exc
        if authorized != checkpoint_ref.project_ref:
            raise CheckpointScopeError("Checkpoint Project scope mismatch")
        row = connection.execute(
            """
            SELECT * FROM run_checkpoints
            WHERE project_id = ? AND checkpoint_id = ?
            """,
            (checkpoint_ref.project_ref.value, checkpoint_ref.checkpoint_id),
        ).fetchone()
        if row is None:
            raise CheckpointNotFoundError("RunCheckpoint was not found")
        return self._checkpoint_from_row(connection, access, cast(sqlite3.Row, row))

    def _checkpoint_from_row(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        row: sqlite3.Row,
    ) -> RunCheckpoint:
        project_ref = ProjectRef(cast(str, row["project_id"]))
        checkpoint_ref = RunCheckpointRef(project_ref, cast(str, row["checkpoint_id"]))
        try:
            content_data: object = json.loads(cast(str, row["content_json"]))
            content_ref = _content_from_payload(content_data)
            serialized = self.object_storage.read(content_ref)
        except (json.JSONDecodeError, UnicodeDecodeError, ObjectStorageError, ValueError) as exc:
            raise CheckpointIntegrityError("Checkpoint content is missing or corrupt") from exc
        try:
            loaded: object = json.loads(serialized.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CheckpointIntegrityError("Checkpoint serialization is malformed") from exc
        if not isinstance(loaded, dict):
            raise CheckpointIntegrityError("Checkpoint serialization is malformed")
        body = cast(dict[str, object], loaded)
        checkpoint = self._checkpoint_from_body(row, body, content_ref)
        if checkpoint.checkpoint_ref != checkpoint_ref:
            raise CheckpointIntegrityError("Checkpoint row and content identity differ")
        self._revalidate_checkpoint_envelope(connection, access, checkpoint, row=row)
        return checkpoint

    def _revalidate_checkpoint_envelope(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        checkpoint: RunCheckpoint,
        *,
        row: sqlite3.Row | None = None,
    ) -> None:
        try:
            authorized = self.executions.projects._authorize(connection, access)
        except ProjectScopeError as exc:
            raise CheckpointScopeError("Checkpoint Project scope mismatch") from exc
        if authorized != checkpoint.project_ref:
            raise CheckpointScopeError("Checkpoint Project scope mismatch")
        if row is None:
            fetched = connection.execute(
                """
                SELECT * FROM run_checkpoints
                WHERE project_id = ? AND checkpoint_id = ?
                """,
                (
                    checkpoint.project_ref.value,
                    checkpoint.checkpoint_ref.checkpoint_id,
                ),
            ).fetchone()
            if fetched is None:
                raise CheckpointNotFoundError("RunCheckpoint was not found")
            row = cast(sqlite3.Row, fetched)
        if (
            row["project_id"] != checkpoint.project_ref.value
            or row["checkpoint_id"] != checkpoint.checkpoint_ref.checkpoint_id
            or row["schema_version"] != checkpoint.schema_version
            or row["run_id"] != checkpoint.run_ref.run_id
            or row["task_id"] != checkpoint.task_ref.task_id
            or row["task_revision"] != checkpoint.task_ref.revision
            or row["task_digest"] != checkpoint.task_digest
            or row["graph_id"] != checkpoint.graph_ref.graph_id
            or row["graph_revision"] != checkpoint.graph_ref.revision
            or row["graph_record_sha256"] != checkpoint.graph_record_sha256
            or row["checkpoint_sequence"] != checkpoint.checkpoint_sequence
            or row["checkpoint_event_high_water_mark"]
            != checkpoint.event_high_water_mark
            or row["content_json"] != _json(_content_payload(checkpoint.content_ref))
            or row["artifact_id"] != checkpoint.artifact_ref.artifact_id
            or row["artifact_revision"] != checkpoint.artifact_ref.revision
            or row["event_id"] != checkpoint.event_ref.event_id
            or row["event_sequence"] != checkpoint.event_sequence
            or row["created_at"] != checkpoint.created_at
            or row["semantic_digest"] != checkpoint.semantic_digest
            or row["record_sha256"] != checkpoint.record_sha256
        ):
            raise CheckpointIntegrityError(
                "Checkpoint durable columns differ from content-addressed state"
            )
        artifact = self.artifacts._fetch_artifact(connection, checkpoint.artifact_ref)
        event_row = connection.execute(
            "SELECT * FROM events WHERE project_id = ? AND event_id = ?",
            (checkpoint.project_ref.value, checkpoint.event_ref.event_id),
        ).fetchone()
        if event_row is None:
            raise CheckpointIntegrityError("Checkpoint Event is missing")
        event = self.events._event_from_row(connection, cast(sqlite3.Row, event_row))
        run_events = self.events._fetch_verified_run_events(connection, checkpoint.run_ref)
        graph = self.executions.graphs._fetch_graph(connection, checkpoint.graph_ref)
        task = self.executions.tasks._fetch_task(connection, checkpoint.task_ref)
        run = self.executions.runs._fetch_run(connection, checkpoint.run_ref)
        if checkpoint.event_high_water_mark >= len(run_events):
            raise CheckpointIntegrityError(
                "Checkpoint Event high-water mark exceeds durable chronology"
            )
        anchor = (
            None
            if checkpoint.event_high_water_mark == 0
            else run_events[checkpoint.event_high_water_mark - 1]
        )
        if (
            graph.record_sha256 != checkpoint.graph_record_sha256
            or task.canonical_digest != checkpoint.task_digest
            or run.task_ref != checkpoint.task_ref
            or run.task_digest != checkpoint.task_digest
            or artifact.content_ref != checkpoint.content_ref
            or artifact.role != "run.checkpoint"
            or artifact.producer_run_ref != checkpoint.run_ref
            or artifact.record_sha256 != row["artifact_record_sha256"]
            or event.record_sha256 != row["event_record_sha256"]
            or event.run_ref != checkpoint.run_ref
            or event.task_ref != checkpoint.task_ref
            or event.graph_ref != checkpoint.graph_ref
            or event.event_type != "RUN_CHECKPOINT"
            or event.payload_ref != checkpoint.content_ref
            or checkpoint.artifact_ref.value not in event.object_refs
            or checkpoint.content_ref.value not in event.object_refs
            or event.metadata.get("checkpoint_ref") != checkpoint.checkpoint_ref.value
            or checkpoint.event_sequence != checkpoint.event_high_water_mark + 1
            or (
                anchor is not None
                and (
                    anchor.event_ref != checkpoint.event_anchor_ref
                    or anchor.record_sha256 != checkpoint.event_anchor_record_sha256
                )
            )
        ):
            raise CheckpointIntegrityError(
                "Checkpoint Artifact, Event, content, or attribution binding differs"
            )

    def _checkpoint_from_body(
        self,
        row: sqlite3.Row,
        body: dict[str, object],
        content_ref: ContentRef,
    ) -> RunCheckpoint:
        required = {
            "call_refs",
            "checkpoint_id",
            "checkpoint_sequence",
            "completed_output_refs",
            "continuation_refs",
            "created_at",
            "event_anchor_record_sha256",
            "event_anchor_ref",
            "event_high_water_mark",
            "failure_refs",
            "graph_record_sha256",
            "graph_ref",
            "nodes",
            "project_ref",
            "run_ref",
            "schema_version",
            "source_refs",
            "task_digest",
            "task_ref",
            "workspace_snapshot_ref",
        }
        if set(body) != required:
            raise CheckpointIntegrityError("Checkpoint serialization schema differs")
        project_ref = ProjectRef(cast(str, body["project_ref"]))
        run_ref = self._parse_run_ref(cast(str, body["run_ref"]), project_ref)
        task_ref = self._parse_task_ref(cast(str, body["task_ref"]), project_ref)
        graph_ref = self._parse_graph_ref(cast(str, body["graph_ref"]), project_ref)
        node_values = body["nodes"]
        if not isinstance(node_values, list):
            raise CheckpointIntegrityError("Checkpoint Nodes are malformed")
        nodes = tuple(self._node_from_payload(item, graph_ref) for item in node_values)
        anchor_value = body["event_anchor_ref"]
        event_anchor = (
            None
            if anchor_value is None
            else self._parse_event_ref(cast(str, anchor_value), project_ref)
        )
        workspace_value = body["workspace_snapshot_ref"]
        workspace = None if workspace_value is None else _content_from_payload(workspace_value)
        return RunCheckpoint(
            RunCheckpointRef(project_ref, cast(str, body["checkpoint_id"])),
            cast(str, body["schema_version"]),
            run_ref,
            task_ref,
            cast(str, body["task_digest"]),
            graph_ref,
            cast(str, body["graph_record_sha256"]),
            cast(int, body["checkpoint_sequence"]),
            cast(str, body["created_at"]),
            nodes,
            self._text_tuple(body["completed_output_refs"]),
            self._text_tuple(body["source_refs"]),
            self._text_tuple(body["call_refs"]),
            self._text_tuple(body["failure_refs"]),
            cast(int, body["event_high_water_mark"]),
            event_anchor,
            cast(str | None, body["event_anchor_record_sha256"]),
            workspace,
            self._text_tuple(body["continuation_refs"]),
            content_ref,
            ArtifactRef(
                project_ref,
                cast(str, row["artifact_id"]),
                cast(int, row["artifact_revision"]),
            ),
            EventRef(project_ref, cast(str, row["event_id"])),
            cast(int, row["event_sequence"]),
        )

    def _node_from_payload(
        self,
        value: object,
        graph_ref: GraphRef,
    ) -> CheckpointNodeState:
        if not isinstance(value, dict):
            raise CheckpointIntegrityError("Checkpoint Node is malformed")
        item = cast(dict[str, object], value)
        required = {
            "attempts",
            "current_attempt_id",
            "current_attempt_number",
            "current_fence",
            "current_run_attempt_id",
            "current_run_fence",
            "evidence_refs",
            "failures",
            "node_record_sha256",
            "node_ref",
            "node_semantic_digest",
            "output_refs",
            "source_refs",
            "state_sha256",
            "state_version",
            "status",
        }
        if set(item) != required:
            raise CheckpointIntegrityError("Checkpoint Node schema differs")
        attempt_values = item["attempts"]
        failure_values = item["failures"]
        if not isinstance(attempt_values, list) or not isinstance(failure_values, list):
            raise CheckpointIntegrityError("Checkpoint attempt or failure refs are malformed")
        attempts = tuple(self._attempt_from_payload(entry) for entry in attempt_values)
        failures = tuple(self._failure_from_payload(entry) for entry in failure_values)
        node_ref = self._parse_node_ref(cast(str, item["node_ref"]), graph_ref)
        return CheckpointNodeState(
            node_ref,
            cast(str, item["node_record_sha256"]),
            cast(str, item["node_semantic_digest"]),
            cast(str | None, item["status"]),
            cast(int | None, item["state_version"]),
            cast(str | None, item["state_sha256"]),
            cast(str | None, item["current_attempt_id"]),
            cast(int | None, item["current_attempt_number"]),
            cast(int, item["current_fence"]),
            cast(str | None, item["current_run_attempt_id"]),
            cast(int | None, item["current_run_fence"]),
            self._text_tuple(item["source_refs"]),
            self._text_tuple(item["output_refs"]),
            self._text_tuple(item["evidence_refs"]),
            attempts,
            failures,
        )

    @staticmethod
    def _attempt_from_payload(value: object) -> CheckpointAttemptRef:
        if not isinstance(value, dict) or set(value) != {
            "attempt_id",
            "attempt_number",
            "completion_sha256",
            "fence",
            "outcome",
            "record_sha256",
            "run_attempt_id",
            "run_fence",
        }:
            raise CheckpointIntegrityError("Checkpoint attempt ref is malformed")
        item = cast(dict[str, object], value)
        return CheckpointAttemptRef(
            cast(str, item["attempt_id"]),
            cast(int, item["attempt_number"]),
            cast(int, item["fence"]),
            cast(str, item["run_attempt_id"]),
            cast(int, item["run_fence"]),
            cast(str, item["record_sha256"]),
            cast(str | None, item["completion_sha256"]),
            cast(str | None, item["outcome"]),
        )

    @staticmethod
    def _failure_from_payload(value: object) -> CheckpointFailureRef:
        if not isinstance(value, dict) or set(value) != {
            "category",
            "failure_ref",
            "record_sha256",
            "retry_possible",
        }:
            raise CheckpointIntegrityError("Checkpoint failure ref is malformed")
        item = cast(dict[str, object], value)
        return CheckpointFailureRef(
            cast(str, item["failure_ref"]),
            cast(str, item["category"]),
            cast(bool, item["retry_possible"]),
            cast(str, item["record_sha256"]),
        )

    @staticmethod
    def _text_tuple(value: object) -> tuple[str, ...]:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise CheckpointIntegrityError("Checkpoint reference collection is malformed")
        return tuple(cast(list[str], value))

    @staticmethod
    def _parse_run_ref(value: str, project_ref: ProjectRef) -> RunRef:
        matched = re.fullmatch(r"run://(prj_[0-9a-f]{32})/(run_[0-9a-f]{32})", value)
        if matched is None or matched.group(1) != project_ref.value:
            raise CheckpointIntegrityError("Checkpoint RunRef is malformed")
        return RunRef(project_ref, matched.group(2))

    @staticmethod
    def _parse_task_ref(value: str, project_ref: ProjectRef) -> TaskRef:
        matched = re.fullmatch(
            r"task://(prj_[0-9a-f]{32})/(tsk_[0-9a-f]{32})/([1-9][0-9]*)",
            value,
        )
        if matched is None or matched.group(1) != project_ref.value:
            raise CheckpointIntegrityError("Checkpoint TaskRef is malformed")
        return TaskRef(project_ref, matched.group(2), int(matched.group(3)))

    @staticmethod
    def _parse_graph_ref(value: str, project_ref: ProjectRef) -> GraphRef:
        matched = re.fullmatch(
            r"graph://(prj_[0-9a-f]{32})/(gph_[0-9a-f]{32})/([1-9][0-9]*)",
            value,
        )
        if matched is None or matched.group(1) != project_ref.value:
            raise CheckpointIntegrityError("Checkpoint GraphRef is malformed")
        return GraphRef(project_ref, matched.group(2), int(matched.group(3)))

    @staticmethod
    def _parse_node_ref(value: str, graph_ref: GraphRef) -> NodeRef:
        matched = re.fullmatch(
            r"node://(prj_[0-9a-f]{32})/(gph_[0-9a-f]{32})/([1-9][0-9]*)/(nod_[0-9a-f]{32})",
            value,
        )
        if (
            matched is None
            or matched.group(1) != graph_ref.project_ref.value
            or matched.group(2) != graph_ref.graph_id
            or int(matched.group(3)) != graph_ref.revision
        ):
            raise CheckpointIntegrityError("Checkpoint NodeRef is malformed")
        return NodeRef(graph_ref, matched.group(4))

    @staticmethod
    def _parse_event_ref(value: str, project_ref: ProjectRef) -> EventRef:
        matched = re.fullmatch(r"event://(prj_[0-9a-f]{32})/(evt_[0-9a-f]{32})", value)
        if matched is None or matched.group(1) != project_ref.value:
            raise CheckpointIntegrityError("Checkpoint EventRef is malformed")
        return EventRef(project_ref, matched.group(2))

# Required semantic interface name.
checkpoint_reconciliation_service = CheckpointReconciliationService
