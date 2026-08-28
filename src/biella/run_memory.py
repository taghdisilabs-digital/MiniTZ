"""Durable Run reconstruction over Biella's authoritative execution records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import cast

from .artifact import ArtifactError, ContentRef
from .event import Event, EventError, EventRef
from .execution import (
    NodeExecution,
    NodeExecutionAttempt,
    NodeExecutionError,
    NodeExecutionFailure,
    NodeExecutionScopeError,
    NodeExecutionService,
)
from .graph import Graph, GraphError, GraphRef, NodeRef
from .project import ProjectAccess, ProjectRef, ProjectScopeError
from .run import ExecutionAttempt, Run, RunError, RunNotFoundError, RunRef
from .task import Task, TaskError, TaskRef


_EXTENSION_EVENT_TYPES = {"MODEL_CALL", "RUN_CHECKPOINT", "TOOL_CALL"}
_MODEL_CALL_REF_PATTERN = re.compile(
    r"model-call://(prj_[0-9a-f]{32})/(mcall_[0-9a-f]{32})"
)
_TOOL_CALL_REF_PATTERN = re.compile(
    r"tool-call://(prj_[0-9a-f]{32})/(tcall_[0-9a-f]{32})"
)
_CONTINUABLE_NODE_STATUSES = {
    "QUEUED",
    "READY",
    "LEASED",
    "RUNNING",
    "WAITING_EXTERNAL",
    "STALE",
}
_TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}


class RunMemoryError(Exception):
    """Base class for Run Memory reconstruction failures."""


class RunMemoryContractError(RunMemoryError, ValueError):
    """A Run Memory request or value is malformed."""


class RunMemoryScopeError(RunMemoryError):
    """A Run Memory request crossed authenticated Project scope."""


class RunMemoryNotFoundError(RunMemoryError):
    """The requested Run has no durable identity in the Project."""


class RunMemoryIntegrityError(RunMemoryError):
    """Authoritative records cannot form one consistent Run Memory."""


class RunMemoryDivergenceError(RunMemoryIntegrityError):
    """A supplied Run Memory no longer equals authoritative durable state."""


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


def _is_expired(expires_at: str | None, database_now: str) -> bool:
    if expires_at is None:
        return False
    try:
        return datetime.fromisoformat(expires_at) <= datetime.fromisoformat(database_now)
    except ValueError as exc:
        raise RunMemoryIntegrityError("lease timestamp is malformed") from exc


@dataclass(frozen=True)
class RunMemoryNodeAttempt:
    """One exact Node attempt plus its immutable completion evidence, if closed."""

    attempt: NodeExecutionAttempt
    completed_at: str | None
    outcome: str | None
    completion_sha256: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.attempt, NodeExecutionAttempt):
            raise RunMemoryContractError("Node attempt is required")
        completion_values = (
            self.completed_at,
            self.outcome,
            self.completion_sha256,
        )
        if any(value is None for value in completion_values) and not all(
            value is None for value in completion_values
        ):
            raise RunMemoryIntegrityError("Node attempt completion is incomplete")
        if self.completed_at is not None:
            if not isinstance(self.completed_at, str) or not isinstance(self.outcome, str):
                raise RunMemoryIntegrityError("Node attempt completion is malformed")
            try:
                datetime.fromisoformat(self.completed_at)
            except ValueError as exc:
                raise RunMemoryIntegrityError(
                    "Node attempt completion timestamp is malformed"
                ) from exc
            if self.outcome not in {"CANCELLED", "FAILED", "STALE", "SUCCEEDED"}:
                raise RunMemoryIntegrityError("Node attempt completion outcome is malformed")
        if self.completion_sha256 is not None and (
            not isinstance(self.completion_sha256, str)
            or len(self.completion_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.completion_sha256)
        ):
            raise RunMemoryIntegrityError("Node attempt completion digest is malformed")
        if self.completion_sha256 is not None and self.completion_sha256 != _sha256(
            {
                "attempt_id": self.attempt.attempt_id,
                "completed_at": self.completed_at,
                "node_ref": self.attempt.node_ref.value,
                "outcome": self.outcome,
            }
        ):
            raise RunMemoryIntegrityError("Node attempt completion digest differs")


@dataclass(frozen=True)
class RunMemoryNode:
    """Verified current and historical state for one exact Graph Node."""

    node_ref: NodeRef
    latest: NodeExecution | None
    history: tuple[NodeExecution, ...]
    attempts: tuple[RunMemoryNodeAttempt, ...]
    failures: tuple[NodeExecutionFailure, ...]
    lease_expired: bool
    effective_owner_ref: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.node_ref, NodeRef):
            raise RunMemoryContractError("NodeRef is required")
        object.__setattr__(self, "history", tuple(self.history))
        object.__setattr__(self, "attempts", tuple(self.attempts))
        object.__setattr__(self, "failures", tuple(self.failures))
        if self.latest is None:
            if (
                self.history
                or self.attempts
                or self.failures
                or self.lease_expired
                or self.effective_owner_ref is not None
            ):
                raise RunMemoryIntegrityError(
                    "uninitialized Node cannot expose execution evidence"
                )
            return
        if not isinstance(self.latest, NodeExecution):
            raise RunMemoryContractError("latest Node execution is malformed")
        if self.latest.node_ref != self.node_ref:
            raise RunMemoryIntegrityError("latest Node execution identity differs")
        if not self.history or self.history[-1] != self.latest:
            raise RunMemoryIntegrityError("Node history does not end at latest state")
        if any(item.node_ref != self.node_ref for item in self.history):
            raise RunMemoryIntegrityError("Node history identity differs")
        if any(item.attempt.node_ref != self.node_ref for item in self.attempts):
            raise RunMemoryIntegrityError("Node attempt identity differs")
        if any(item.node_ref != self.node_ref for item in self.failures):
            raise RunMemoryIntegrityError("Node failure identity differs")
        if self.lease_expired:
            if self.latest.current_owner_ref is None or self.effective_owner_ref is not None:
                raise RunMemoryIntegrityError("expired Node ownership is inconsistent")
        elif self.effective_owner_ref != self.latest.current_owner_ref:
            raise RunMemoryIntegrityError("effective Node owner differs from authority")

@dataclass(frozen=True)
class RunMemoryGraph:
    """One immutable Graph revision and its reconstructed Node state."""

    graph: Graph
    nodes: tuple[RunMemoryNode, ...]
    condition_results: Mapping[str, bool]
    initialized: bool

    def __post_init__(self) -> None:
        if not isinstance(self.graph, Graph):
            raise RunMemoryContractError("Graph is required")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        expected = tuple(self.graph.topological_order())
        if tuple(item.node_ref for item in self.nodes) != expected:
            raise RunMemoryIntegrityError("Run Memory Nodes differ from exact Graph")
        if not isinstance(self.initialized, bool):
            raise RunMemoryContractError("Graph initialization state is malformed")
        if self.initialized != all(item.latest is not None for item in self.nodes):
            raise RunMemoryIntegrityError("Graph initialization state differs from Nodes")
        copied = dict(self.condition_results)
        if not all(isinstance(key, str) and isinstance(value, bool) for key, value in copied.items()):
            raise RunMemoryContractError("condition results are malformed")
        object.__setattr__(self, "condition_results", MappingProxyType(dict(sorted(copied.items()))))


@dataclass(frozen=True)
class RunMemoryExtensionRef:
    """Reference-only checkpoint, model-call, or tool-call continuation seam."""

    kind: str
    event_ref: EventRef
    sequence: int
    task_ref: TaskRef | None
    graph_ref: GraphRef | None
    object_refs: tuple[str, ...]
    payload_ref: ContentRef | None
    call_ref: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _EXTENSION_EVENT_TYPES:
            raise RunMemoryContractError("Run Memory extension kind is unsupported")
        if not isinstance(self.event_ref, EventRef):
            raise RunMemoryContractError("Run Memory extension EventRef is required")
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 1:
            raise RunMemoryContractError("Run Memory extension sequence is malformed")
        object.__setattr__(self, "object_refs", tuple(self.object_refs))
        pattern = {
            "MODEL_CALL": _MODEL_CALL_REF_PATTERN,
            "TOOL_CALL": _TOOL_CALL_REF_PATTERN,
        }.get(self.kind)
        if pattern is not None and self.call_ref is not None:
            matched = pattern.fullmatch(self.call_ref)
            if matched is None or matched.group(1) != self.event_ref.project_ref.value:
                raise RunMemoryIntegrityError(
                    "Run Memory call extension has invalid Project-scoped call reference"
                )
        elif self.call_ref is not None:
            raise RunMemoryContractError("Non-call extension cannot claim CallRef")
        if not self.object_refs and self.payload_ref is None and self.call_ref is None:
            raise RunMemoryIntegrityError("Run Memory extension Event has no exact reference")


@dataclass(frozen=True)
class RunMemory:
    """Immutable reconstruction of one Run from authoritative durable records."""

    project_ref: ProjectRef
    task: Task
    run: Run
    run_attempts: tuple[ExecutionAttempt, ...]
    graphs: tuple[RunMemoryGraph, ...]
    current_graph_ref: GraphRef | None
    events: tuple[Event, ...]
    event_high_water_mark: int
    extension_refs: tuple[RunMemoryExtensionRef, ...]
    latest_checkpoint_ref: RunMemoryExtensionRef | None
    ready_node_refs: tuple[NodeRef, ...]
    continuation_node_refs: tuple[NodeRef, ...]
    run_lease_expired: bool
    effective_run_owner_ref: str | None
    semantic_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "run_attempts",
            "graphs",
            "events",
            "extension_refs",
            "ready_node_refs",
            "continuation_node_refs",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not isinstance(self.project_ref, ProjectRef):
            raise RunMemoryContractError("ProjectRef is required")
        if self.task.project_ref != self.project_ref or self.run.project_ref != self.project_ref:
            raise RunMemoryIntegrityError("Run Memory Project identity differs")
        if self.run.task_ref != self.task.task_ref or self.run.task_digest != self.task.canonical_digest:
            raise RunMemoryIntegrityError("Run Memory exact Task binding differs")
        if any(attempt.run_ref != self.run.run_ref for attempt in self.run_attempts):
            raise RunMemoryIntegrityError("Run attempt identity differs")
        if self.graphs:
            revisions = tuple(item.graph.revision for item in self.graphs)
            if revisions != tuple(range(1, len(self.graphs) + 1)):
                raise RunMemoryIntegrityError("Run Memory Graph history is not gap-free")
            if self.current_graph_ref != self.graphs[-1].graph.graph_ref:
                raise RunMemoryIntegrityError("current Graph differs from Graph history")
            for item in self.graphs:
                graph = item.graph
                if (
                    graph.project_ref != self.project_ref
                    or graph.run_ref != self.run.run_ref
                    or graph.task_ref != self.task.task_ref
                    or graph.task_digest != self.task.canonical_digest
                ):
                    raise RunMemoryIntegrityError("Run Memory Graph authority differs")
        elif self.current_graph_ref is not None:
            raise RunMemoryIntegrityError("current Graph exists without history")
        if tuple(event.sequence for event in self.events) != tuple(
            range(1, len(self.events) + 1)
        ):
            raise RunMemoryIntegrityError("Run Memory Event history is not gap-free")
        if any(event.run_ref != self.run.run_ref for event in self.events):
            raise RunMemoryIntegrityError("Run Memory Event belongs to another Run")
        expected_high_water = 0 if not self.events else cast(int, self.events[-1].sequence)
        if self.event_high_water_mark != expected_high_water:
            raise RunMemoryIntegrityError("Event high-water mark differs from history")
        event_refs = {event.event_ref for event in self.events}
        if any(item.event_ref not in event_refs for item in self.extension_refs):
            raise RunMemoryIntegrityError("extension reference has no Event evidence")
        if self.latest_checkpoint_ref is not None:
            if (
                self.latest_checkpoint_ref not in self.extension_refs
                or self.latest_checkpoint_ref.kind != "RUN_CHECKPOINT"
                or self.latest_checkpoint_ref.task_ref != self.task.task_ref
                or self.latest_checkpoint_ref.graph_ref != self.current_graph_ref
            ):
                raise RunMemoryIntegrityError("latest checkpoint is incompatible")
        current_nodes = () if not self.graphs else self.graphs[-1].nodes
        current_by_ref = {item.node_ref: item for item in current_nodes}
        if len(set(self.ready_node_refs)) != len(self.ready_node_refs):
            raise RunMemoryIntegrityError("ready set contains duplicate Nodes")
        for node_ref in self.ready_node_refs:
            ready_node = current_by_ref.get(node_ref)
            if ready_node is None or (
                ready_node.latest is not None and ready_node.latest.status != "READY"
            ):
                raise RunMemoryIntegrityError("ready set differs from current Node state")
        if len(set(self.continuation_node_refs)) != len(self.continuation_node_refs):
            raise RunMemoryIntegrityError("continuation set contains duplicate Nodes")
        if any(node_ref not in current_by_ref for node_ref in self.continuation_node_refs):
            raise RunMemoryIntegrityError("continuation set contains foreign Node")
        if self.run.status in _TERMINAL_RUN_STATUSES and self.continuation_node_refs:
            raise RunMemoryIntegrityError("terminal Run cannot expose continuation")
        if self.run_lease_expired:
            if self.run.current_owner_ref is None or self.effective_run_owner_ref is not None:
                raise RunMemoryIntegrityError("expired Run ownership is inconsistent")
        elif self.effective_run_owner_ref != self.run.current_owner_ref:
            raise RunMemoryIntegrityError("effective Run owner differs from authority")
        object.__setattr__(self, "semantic_digest", _sha256(self._semantic_payload()))

    @property
    def run_ref(self) -> RunRef:
        return self.run.run_ref

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "continuation_node_refs": [item.value for item in self.continuation_node_refs],
            "current_graph_ref": None if self.current_graph_ref is None else self.current_graph_ref.value,
            "effective_run_owner_ref": self.effective_run_owner_ref,
            "event_high_water_mark": self.event_high_water_mark,
            "events": [item.record_sha256 for item in self.events],
            "extension_refs": [
                {
                    "event_ref": item.event_ref.value,
                    "graph_ref": None if item.graph_ref is None else item.graph_ref.value,
                    "kind": item.kind,
                    "call_ref": item.call_ref,
                    "object_refs": list(item.object_refs),
                    "payload_ref": None if item.payload_ref is None else item.payload_ref.value,
                    "sequence": item.sequence,
                    "task_ref": (
                        None
                        if item.task_ref is None
                        else {
                            "project_ref": item.task_ref.project_ref.value,
                            "revision": item.task_ref.revision,
                            "task_id": item.task_ref.task_id,
                        }
                    ),
                }
                for item in self.extension_refs
            ],
            "graphs": [
                {
                    "condition_results": dict(item.condition_results),
                    "graph_record_sha256": item.graph.record_sha256,
                    "initialized": item.initialized,
                    "nodes": [
                        {
                            "attempts": [
                                {
                                    "completed_at": node_attempt.completed_at,
                                    "completion_sha256": node_attempt.completion_sha256,
                                    "outcome": node_attempt.outcome,
                                    "record_sha256": node_attempt.attempt.record_sha256,
                                }
                                for node_attempt in node.attempts
                            ],
                            "failures": [failure.record_sha256 for failure in node.failures],
                            "history": [state.state_sha256 for state in node.history],
                            "latest_identity": (
                                None
                                if node.latest is None
                                else node.latest.identity_sha256
                            ),
                            "lease_expired": node.lease_expired,
                            "node_ref": node.node_ref.value,
                            "owner": node.effective_owner_ref,
                        }
                        for node in item.nodes
                    ],
                }
                for item in self.graphs
            ],
            "project_ref": self.project_ref.value,
            "ready_node_refs": [item.value for item in self.ready_node_refs],
            "run_attempts": [
                {
                    "completion": item.completion_sha256,
                    "record": item.record_sha256,
                }
                for item in self.run_attempts
            ],
            "run_identity": self.run.identity_sha256,
            "run_lease_expired": self.run_lease_expired,
            "run_state": self.run.state_sha256,
            "task_record": self.task.record_sha256,
        }


class RunMemoryService:
    """Reconstruct and validate Run Memory on one verified SQLite snapshot."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.executions = NodeExecutionService(self.database_path)

    def reconstruct(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> RunMemory:
        if not isinstance(run_ref, RunRef):
            raise RunMemoryContractError("RunRef is required")
        connection = self.executions._connect()
        try:
            connection.execute("BEGIN")
            memory = self._reconstruct_in_snapshot(
                connection,
                requesting_access,
                run_ref,
            )
            connection.commit()
            return memory
        except NodeExecutionScopeError as exc:
            connection.rollback()
            raise RunMemoryScopeError("Run Memory Project scope mismatch") from exc
        except RunNotFoundError as exc:
            connection.rollback()
            raise RunMemoryNotFoundError("Run Memory Run was not found") from exc
        except (ProjectScopeError, RunError, TaskError, GraphError, NodeExecutionError, EventError, ArtifactError) as exc:
            connection.rollback()
            raise RunMemoryIntegrityError(
                "authoritative records failed Run Memory reconstruction"
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_run_memory(
        self,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> RunMemory:
        """Compatibility spelling for reconstructing Run Memory."""

        return self.reconstruct(requesting_access, run_ref)

    def validate_consistency(
        self,
        requesting_access: ProjectAccess,
        memory: RunMemory,
    ) -> bool:
        if not isinstance(memory, RunMemory):
            raise RunMemoryContractError("RunMemory is required")
        try:
            validated = self._validated_copy(memory)
        except RunMemoryError as exc:
            raise RunMemoryDivergenceError(
                "supplied Run Memory projection is structurally invalid"
            ) from exc
        current = self.reconstruct(requesting_access, memory.run_ref)
        if (
            validated != current
            or validated.semantic_digest != memory.semantic_digest
            or current.semantic_digest != memory.semantic_digest
        ):
            raise RunMemoryDivergenceError(
                "Run Memory differs from current authoritative durable state"
            )
        return True

    @staticmethod
    def _validated_copy(memory: RunMemory) -> RunMemory:
        def copy_extension(item: RunMemoryExtensionRef) -> RunMemoryExtensionRef:
            return RunMemoryExtensionRef(
                kind=item.kind,
                event_ref=item.event_ref,
                sequence=item.sequence,
                task_ref=item.task_ref,
                graph_ref=item.graph_ref,
                object_refs=tuple(item.object_refs),
                payload_ref=item.payload_ref,
                call_ref=item.call_ref,
            )

        graphs = tuple(
            RunMemoryGraph(
                graph=item.graph,
                nodes=tuple(
                    RunMemoryNode(
                        node_ref=node.node_ref,
                        latest=node.latest,
                        history=tuple(node.history),
                        attempts=tuple(
                            RunMemoryNodeAttempt(
                                attempt=attempt.attempt,
                                completed_at=attempt.completed_at,
                                outcome=attempt.outcome,
                                completion_sha256=attempt.completion_sha256,
                            )
                            for attempt in node.attempts
                        ),
                        failures=tuple(node.failures),
                        lease_expired=node.lease_expired,
                        effective_owner_ref=node.effective_owner_ref,
                    )
                    for node in item.nodes
                ),
                condition_results=dict(item.condition_results),
                initialized=item.initialized,
            )
            for item in memory.graphs
        )
        return RunMemory(
            project_ref=memory.project_ref,
            task=memory.task,
            run=memory.run,
            run_attempts=tuple(memory.run_attempts),
            graphs=graphs,
            current_graph_ref=memory.current_graph_ref,
            events=tuple(memory.events),
            event_high_water_mark=memory.event_high_water_mark,
            extension_refs=tuple(copy_extension(item) for item in memory.extension_refs),
            latest_checkpoint_ref=(
                None
                if memory.latest_checkpoint_ref is None
                else copy_extension(memory.latest_checkpoint_ref)
            ),
            ready_node_refs=tuple(memory.ready_node_refs),
            continuation_node_refs=tuple(memory.continuation_node_refs),
            run_lease_expired=memory.run_lease_expired,
            effective_run_owner_ref=memory.effective_run_owner_ref,
        )

    def _reconstruct_in_snapshot(
        self,
        connection: sqlite3.Connection,
        requesting_access: ProjectAccess,
        run_ref: RunRef,
    ) -> RunMemory:
        run, task, current_graph = self.executions._context_allowing_no_graph(
            connection,
            requesting_access,
            run_ref,
        )
        database_now = self.executions._database_now(connection)
        run_attempts = self.executions.runs._fetch_attempts(connection, run)
        graphs: tuple[RunMemoryGraph, ...] = ()
        if current_graph is not None:
            graphs = tuple(
                self._reconstruct_graph(
                    connection,
                    GraphRef(
                        current_graph.project_ref,
                        current_graph.graph_id,
                        revision,
                    ),
                    database_now,
                )
                for revision in range(1, current_graph.revision + 1)
            )
        events = self.executions.events._fetch_verified_run_events(connection, run_ref)
        extension_refs = tuple(
            RunMemoryExtensionRef(
                kind=event.event_type,
                event_ref=event.event_ref,
                sequence=cast(int, event.sequence),
                task_ref=event.task_ref,
                graph_ref=event.graph_ref,
                object_refs=event.object_refs,
                payload_ref=event.payload_ref,
                call_ref=(
                    cast(str, event.metadata["call_ref"])
                    if event.event_type in {"MODEL_CALL", "TOOL_CALL"}
                    and isinstance(event.metadata.get("call_ref"), str)
                    else None
                ),
            )
            for event in events
            if event.event_type in _EXTENSION_EVENT_TYPES
        )
        compatible_checkpoints = tuple(
            item
            for item in extension_refs
            if item.kind == "RUN_CHECKPOINT"
            and item.task_ref == task.task_ref
            and item.graph_ref == (None if current_graph is None else current_graph.graph_ref)
        )
        current_memory_graph = None if not graphs else graphs[-1]
        current_nodes = () if current_memory_graph is None else current_memory_graph.nodes
        if current_memory_graph is None:
            ready_node_refs: tuple[NodeRef, ...] = ()
        elif current_memory_graph.initialized:
            ready_node_refs = tuple(
                item.node_ref
                for item in current_nodes
                if item.latest is not None and item.latest.status == "READY"
            )
        else:
            ready_node_refs = current_memory_graph.graph.ready_set(
                {},
                current_memory_graph.condition_results,
                task,
            )
        continuation_node_refs = (
            ()
            if run.status in _TERMINAL_RUN_STATUSES
            else tuple(item.node_ref for item in current_nodes)
            if current_memory_graph is not None and not current_memory_graph.initialized
            else tuple(
                item.node_ref
                for item in current_nodes
                if item.latest is not None
                and item.latest.status in _CONTINUABLE_NODE_STATUSES
            )
        )
        run_lease_expired = _is_expired(run.lease_expires_at, database_now)
        return RunMemory(
            project_ref=run.project_ref,
            task=task,
            run=run,
            run_attempts=run_attempts,
            graphs=graphs,
            current_graph_ref=None if current_graph is None else current_graph.graph_ref,
            events=events,
            event_high_water_mark=0 if not events else cast(int, events[-1].sequence),
            extension_refs=extension_refs,
            latest_checkpoint_ref=(
                None if not compatible_checkpoints else compatible_checkpoints[-1]
            ),
            ready_node_refs=ready_node_refs,
            continuation_node_refs=continuation_node_refs,
            run_lease_expired=run_lease_expired,
            effective_run_owner_ref=(
                None if run_lease_expired else run.current_owner_ref
            ),
        )

    def _reconstruct_graph(
        self,
        connection: sqlite3.Connection,
        graph_ref: GraphRef,
        database_now: str,
    ) -> RunMemoryGraph:
        graph = self.executions.graphs._fetch_graph(connection, graph_ref)
        conditions = self.executions._condition_results(connection, graph)
        execution_count = cast(
            int,
            connection.execute(
                """
                SELECT COUNT(*) FROM node_executions
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ?
                """,
                (graph.project_ref.value, graph.graph_id, graph.revision),
            ).fetchone()[0],
        )
        if execution_count == 0:
            if conditions:
                raise RunMemoryIntegrityError(
                    "uninitialized Graph has Node condition evidence"
                )
            nodes = tuple(
                RunMemoryNode(
                    node_ref=node_ref,
                    latest=None,
                    history=(),
                    attempts=(),
                    failures=(),
                    lease_expired=False,
                    effective_owner_ref=None,
                )
                for node_ref in graph.topological_order()
            )
            return RunMemoryGraph(
                graph=graph,
                nodes=nodes,
                condition_results=conditions,
                initialized=False,
            )
        if execution_count != len(graph.nodes):
            raise RunMemoryIntegrityError("Graph Node execution initialization is partial")
        executions = self.executions._ordered_current(connection, graph)
        nodes = tuple(
            self._reconstruct_node(connection, execution, database_now)
            for execution in executions
        )
        return RunMemoryGraph(
            graph=graph,
            nodes=nodes,
            condition_results=conditions,
            initialized=True,
        )

    def _reconstruct_node(
        self,
        connection: sqlite3.Connection,
        execution: NodeExecution,
        database_now: str,
    ) -> RunMemoryNode:
        history = self.executions._fetch_history(connection, execution.node_ref)
        self.executions._verify_node_run_completion(connection, history[-1])
        attempt_rows = connection.execute(
            """
            SELECT attempt_id FROM node_execution_attempts
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
            ORDER BY attempt_number
            """,
            self.executions._node_key(execution.node_ref),
        ).fetchall()
        attempts: list[RunMemoryNodeAttempt] = []
        for row in attempt_rows:
            attempt = self.executions._fetch_attempt(
                connection,
                execution.node_ref,
                cast(str, row["attempt_id"]),
            )
            completion = connection.execute(
                """
                SELECT completed_at, outcome, record_sha256
                FROM node_execution_attempt_completions
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ?
                    AND node_id = ? AND attempt_id = ?
                """,
                (*self.executions._node_key(execution.node_ref), attempt.attempt_id),
            ).fetchone()
            attempts.append(
                RunMemoryNodeAttempt(
                    attempt=attempt,
                    completed_at=(
                        None if completion is None else cast(str, completion["completed_at"])
                    ),
                    outcome=None if completion is None else cast(str, completion["outcome"]),
                    completion_sha256=(
                        None
                        if completion is None
                        else cast(str, completion["record_sha256"])
                    ),
                )
            )
        failure_rows = connection.execute(
            """
            SELECT * FROM node_execution_failures
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
            ORDER BY created_at, attempt_id
            """,
            self.executions._node_key(execution.node_ref),
        ).fetchall()
        failures = tuple(
            self.executions._failure_from_row(execution.node_ref, row)
            for row in failure_rows
        )
        lease_expired = _is_expired(execution.lease_expires_at, database_now)
        return RunMemoryNode(
            node_ref=execution.node_ref,
            latest=history[-1],
            history=history,
            attempts=tuple(attempts),
            failures=failures,
            lease_expired=lease_expired,
            effective_owner_ref=(
                None if lease_expired else history[-1].current_owner_ref
            ),
        )
