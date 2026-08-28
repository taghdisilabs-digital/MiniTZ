"""Immutable Project-scoped Graph revisions and productive Node contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import TypeAlias, cast
from uuid import uuid4

from .artifact import (
    ArtifactError,
    ArtifactRef,
    ArtifactService,
    ContentRef,
    SourceRef,
)
from .capability import CapabilityNotFoundError, CapabilityRef, CapabilityRegistry
from .project import ProjectAccess, ProjectRef, ProjectScopeError, ProjectStore
from .run import (
    ExecutionAttempt,
    Run,
    RunAuthorityError,
    RunError,
    RunRef,
    RunService,
)
from .task import (
    Task,
    TaskInputRef,
    TaskRef,
    TaskRevisionService,
    TaskSideEffectError,
)


GraphValue: TypeAlias = str | int | float | bool | None

_GRAPH_ID_PATTERN = re.compile(r"gph_[0-9a-f]{32}")
_NODE_ID_PATTERN = re.compile(r"nod_[0-9a-f]{32}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_EXECUTOR_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}")
_VERSION_PATTERN = re.compile(r"[0-9A-Za-z][0-9A-Za-z_.+-]{0,127}")
_ABSOLUTE_REF_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,1024}")
_SIDE_EFFECT_LEVELS = {
    "READ_ONLY": 0,
    "CANDIDATE_WRITE": 1,
    "PROJECT_WRITE": 2,
    "EXTERNAL_SIDE_EFFECT": 3,
}
_TERMINAL_STATUSES = {"SUCCEEDED", "SATISFIED", "SKIPPED", "FAILED", "CANCELLED"}
_SATISFIED_STATUSES = {"SUCCEEDED", "SATISFIED", "SKIPPED"}


class GraphError(Exception):
    """Base class for immutable Graph failures."""


class GraphContractError(GraphError, ValueError):
    """A Graph, Node, or binding contract is malformed."""


class GraphScopeError(GraphError):
    """A Graph operation crossed its authenticated Project scope."""


class GraphConflictError(GraphError):
    """An immutable Graph identity or revision conflicts with durable state."""


class GraphNotFoundError(GraphError):
    """An exact Graph revision does not exist."""


class GraphIntegrityError(GraphError):
    """Persisted Graph evidence failed integrity verification."""


class GraphSideEffectError(GraphError):
    """A Node requires more side-effect authority than its Task."""


class GraphAuthorityError(GraphError):
    """A Graph revision publisher lacks current fenced Run authority."""


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
        raise GraphContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise GraphContractError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GraphContractError(f"{name} must be timezone-aware")
    return value


def _freeze_values(value: Mapping[str, GraphValue], name: str) -> Mapping[str, GraphValue]:
    if not isinstance(value, Mapping):
        raise GraphContractError(f"{name} must be a mapping")
    copied = dict(value)
    if len(copied) > 64:
        raise GraphContractError(f"{name} is unbounded")
    for key, item in copied.items():
        if not isinstance(key, str) or _KEY_PATTERN.fullmatch(key) is None:
            raise GraphContractError(f"{name} key is malformed")
        if not isinstance(item, (str, int, float, bool, type(None))):
            raise GraphContractError(f"{name} value must be a JSON scalar")
        if isinstance(item, float) and not math.isfinite(item):
            raise GraphContractError(f"{name} contains non-finite value")
        if isinstance(item, str) and len(item) > 2048:
            raise GraphContractError(f"{name} value is unbounded")
    return MappingProxyType(copied)


def _freeze_output(value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise GraphContractError("output_contract must be a mapping")
    copied = dict(value)
    if len(copied) > 64:
        raise GraphContractError("output_contract is unbounded")
    for key, reference in copied.items():
        if not isinstance(key, str) or _KEY_PATTERN.fullmatch(key) is None:
            raise GraphContractError("output_contract key is malformed")
        if (
            not isinstance(reference, str)
            or len(reference) > 1056
            or _ABSOLUTE_REF_PATTERN.fullmatch(reference) is None
        ):
            raise GraphContractError("output_contract reference is malformed")
    return MappingProxyType(copied)


def _freeze_text(values: Sequence[str], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise GraphContractError(f"{name} must be a sequence")
    copied = tuple(values)
    if len(copied) > 64:
        raise GraphContractError(f"{name} is unbounded")
    if not all(isinstance(item, str) and 0 < len(item) <= 512 for item in copied):
        raise GraphContractError(f"{name} contains malformed text")
    return tuple(sorted(set(copied)))


@dataclass(frozen=True, order=True)
class GraphRef:
    """Exact identity of one immutable Project-scoped Graph revision."""

    project_ref: ProjectRef
    graph_id: str
    revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.graph_id, str) or _GRAPH_ID_PATTERN.fullmatch(self.graph_id) is None:
            raise GraphContractError("Graph identity is malformed")
        if not isinstance(self.revision, int) or isinstance(self.revision, bool) or self.revision < 1:
            raise GraphContractError("Graph revision must be positive")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "GraphRef":
        return cls(project_ref, f"gph_{uuid4().hex}", 1)

    @property
    def value(self) -> str:
        return f"graph://{self.project_ref.value}/{self.graph_id}/{self.revision}"


@dataclass(frozen=True, order=True)
class NodeRef:
    """Exact Node identity inside one immutable Graph revision."""

    graph_ref: GraphRef
    node_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.graph_ref, GraphRef):
            raise TypeError("graph_ref must be GraphRef")
        if not isinstance(self.node_id, str) or _NODE_ID_PATTERN.fullmatch(self.node_id) is None:
            raise GraphContractError("Node identity is malformed")

    @classmethod
    def new(cls, graph_ref: GraphRef) -> "NodeRef":
        return cls(graph_ref, f"nod_{uuid4().hex}")

    @property
    def project_ref(self) -> ProjectRef:
        return self.graph_ref.project_ref

    @property
    def value(self) -> str:
        return f"node://{self.project_ref.value}/{self.graph_ref.graph_id}/{self.graph_ref.revision}/{self.node_id}"


@dataclass(frozen=True, order=True)
class NodeInputBinding:
    """Exact immutable semantic input to one productive Node."""

    project_ref: ProjectRef
    input_name: str
    source_kind: str
    source_ref: str
    identity_digest: str
    output_key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.input_name, str) or _KEY_PATTERN.fullmatch(self.input_name) is None:
            raise GraphContractError("Node input name is malformed")
        if self.source_kind not in {"task", "artifact", "source", "content", "node_output"}:
            raise GraphContractError("Node input source kind is unsupported")
        if (
            not isinstance(self.source_ref, str)
            or len(self.source_ref) > 1056
            or _ABSOLUTE_REF_PATTERN.fullmatch(self.source_ref) is None
        ):
            raise GraphContractError("Node input source identity is malformed")
        if not isinstance(self.identity_digest, str) or _SHA256_PATTERN.fullmatch(self.identity_digest) is None:
            raise GraphContractError("Node input digest is malformed")
        if self.source_kind == "node_output":
            if self.output_key is None or _KEY_PATTERN.fullmatch(self.output_key) is None:
                raise GraphContractError("Node output binding key is malformed")
        elif self.output_key is not None:
            raise GraphContractError("Only Node output bindings may name output_key")

    @classmethod
    def from_task_input(cls, input_name: str, identity: TaskInputRef) -> "NodeInputBinding":
        if not isinstance(identity, TaskInputRef):
            raise GraphContractError("TaskInputRef is required")
        return cls(
            identity.project_ref,
            input_name,
            "task",
            identity.source_ref,
            identity.content_sha256,
        )

    @classmethod
    def from_identity(
        cls,
        input_name: str,
        project_ref: ProjectRef,
        identity: ArtifactRef | SourceRef | ContentRef,
    ) -> "NodeInputBinding":
        if isinstance(identity, ArtifactRef):
            if identity.project_ref != project_ref:
                raise GraphScopeError("Node input Project scope mismatch")
            source_kind = "artifact"
            source_ref = identity.value
            digest = hashlib.sha256(source_ref.encode()).hexdigest()
        elif isinstance(identity, SourceRef):
            if identity.project_ref != project_ref:
                raise GraphScopeError("Node input Project scope mismatch")
            source_kind = "source"
            source_ref = identity.value
            digest = identity.canonical_digest
        elif isinstance(identity, ContentRef):
            source_kind = "content"
            source_ref = identity.value
            digest = identity.digest
        else:
            raise GraphContractError("Node input must be an active exact identity")
        return cls(project_ref, input_name, source_kind, source_ref, digest)

    @classmethod
    def from_node_output(
        cls,
        input_name: str,
        node_ref: NodeRef,
        output_key: str,
    ) -> "NodeInputBinding":
        if not isinstance(node_ref, NodeRef):
            raise GraphContractError("NodeRef is required")
        digest = hashlib.sha256(f"{node_ref.value}\x00{output_key}".encode()).hexdigest()
        return cls(
            node_ref.project_ref,
            input_name,
            "node_output",
            node_ref.value,
            digest,
            output_key,
        )


@dataclass(frozen=True)
class Node:
    """One productive, provider-neutral unit in an immutable Graph revision."""

    node_ref: NodeRef
    executor_kind: str
    required_capabilities: tuple[CapabilityRef, ...]
    dependencies: tuple[NodeRef, ...]
    input_bindings: tuple[NodeInputBinding, ...]
    output_contract: Mapping[str, str]
    condition_ref: str | None
    side_effect_requirement: str
    resource_hints: Mapping[str, GraphValue]
    evidence_requirements: tuple[str, ...]
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.node_ref, NodeRef):
            raise TypeError("node_ref must be NodeRef")
        if not isinstance(self.executor_kind, str) or _EXECUTOR_PATTERN.fullmatch(self.executor_kind) is None:
            raise GraphContractError("executor_kind is malformed")
        if not isinstance(self.required_capabilities, tuple) or not all(
            isinstance(item, CapabilityRef) for item in self.required_capabilities
        ):
            raise GraphContractError("Node capabilities must contain CapabilityRef")
        if not isinstance(self.dependencies, tuple) or not all(
            isinstance(item, NodeRef) for item in self.dependencies
        ):
            raise GraphContractError("Node dependencies must contain NodeRef")
        if not isinstance(self.input_bindings, tuple) or not all(
            isinstance(item, NodeInputBinding) for item in self.input_bindings
        ):
            raise GraphContractError("Node inputs must contain NodeInputBinding")
        capabilities = tuple(sorted(set(self.required_capabilities)))
        dependencies = tuple(sorted(set(self.dependencies), key=lambda item: item.node_id))
        inputs = tuple(sorted(set(self.input_bindings), key=lambda item: item.input_name))
        if len(capabilities) > 64 or len(dependencies) > 256 or len(inputs) > 128:
            raise GraphContractError("Node collection is unbounded")
        if len(inputs) != len({item.input_name for item in inputs}):
            raise GraphContractError("Node input names are duplicated")
        if any(item.graph_ref != self.graph_ref for item in dependencies):
            raise GraphScopeError("Node dependency Graph scope mismatch")
        if any(item.project_ref != self.project_ref for item in inputs):
            raise GraphScopeError("Node input Project scope mismatch")
        object.__setattr__(self, "required_capabilities", capabilities)
        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(self, "input_bindings", inputs)
        object.__setattr__(self, "output_contract", _freeze_output(self.output_contract))
        if self.condition_ref is not None and (
            not isinstance(self.condition_ref, str)
            or _ABSOLUTE_REF_PATTERN.fullmatch(self.condition_ref) is None
        ):
            raise GraphContractError("Node condition reference is malformed")
        if self.side_effect_requirement not in _SIDE_EFFECT_LEVELS:
            raise GraphContractError("Node side-effect requirement is malformed")
        object.__setattr__(self, "resource_hints", _freeze_values(self.resource_hints, "resource_hints"))
        object.__setattr__(
            self,
            "evidence_requirements",
            _freeze_text(self.evidence_requirements, "evidence_requirements"),
        )
        object.__setattr__(self, "semantic_digest", _sha256(self._semantic_payload()))
        object.__setattr__(
            self,
            "record_sha256",
            _sha256({"node_ref": self.node_ref.value, "semantic_digest": self.semantic_digest}),
        )

    @property
    def graph_ref(self) -> GraphRef:
        return self.node_ref.graph_ref

    @property
    def project_ref(self) -> ProjectRef:
        return self.node_ref.project_ref

    @property
    def node_id(self) -> str:
        return self.node_ref.node_id

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "condition_ref": self.condition_ref,
            "dependencies": [item.node_id for item in self.dependencies],
            "evidence_requirements": list(self.evidence_requirements),
            "executor_kind": self.executor_kind,
            "input_bindings": [
                {
                    "identity_digest": item.identity_digest,
                    "input_name": item.input_name,
                    "output_key": item.output_key,
                    "source_kind": item.source_kind,
                    "source_ref": item.source_ref,
                }
                for item in self.input_bindings
            ],
            "node_id": self.node_id,
            "output_contract": dict(self.output_contract),
            "required_capabilities": [item.value for item in self.required_capabilities],
            "resource_hints": dict(self.resource_hints),
            "side_effect_requirement": self.side_effect_requirement,
        }


def validate_dag(nodes: Sequence[Node]) -> tuple[NodeRef, ...]:
    """Validate one exact DAG and return its deterministic topological order."""

    if isinstance(nodes, (str, bytes)) or not isinstance(nodes, Sequence):
        raise GraphContractError("Graph nodes must be a sequence")
    copied = tuple(nodes)
    if not copied or len(copied) > 4096:
        raise GraphContractError("Graph must contain a bounded productive Node set")
    if not all(isinstance(node, Node) for node in copied):
        raise GraphContractError("Graph nodes must contain Node")
    graph_ref = copied[0].graph_ref
    if any(node.graph_ref != graph_ref for node in copied):
        raise GraphScopeError("DAG Nodes must share one exact Graph revision")
    by_id = {node.node_id: node for node in copied}
    if len(by_id) != len(copied):
        raise GraphContractError("Graph contains duplicate Node identity")
    indegree = {node_id: 0 for node_id in by_id}
    dependents: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    for node in copied:
        for dependency in node.dependencies:
            if dependency.node_id == node.node_id:
                raise GraphContractError("Node cannot depend on itself")
            if dependency.node_id not in by_id:
                raise GraphContractError("Node dependency is missing")
            indegree[node.node_id] += 1
            dependents[dependency.node_id].append(node.node_id)
    ready = sorted(node_id for node_id, count in indegree.items() if count == 0)
    ordered: list[NodeRef] = []
    while ready:
        node_id = ready.pop(0)
        ordered.append(by_id[node_id].node_ref)
        for dependent in sorted(dependents[node_id]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
                ready.sort()
    if len(ordered) != len(copied):
        raise GraphContractError("Graph contains a dependency cycle")
    return tuple(ordered)


@dataclass(frozen=True)
class Graph:
    """One immutable exact Task/Run-bound dynamic execution plan revision."""

    graph_ref: GraphRef
    task_ref: TaskRef
    task_digest: str
    run_ref: RunRef
    nodes: tuple[Node, ...]
    prior_ref: GraphRef | None
    compiler_identity: str | None
    compiler_version: str | None
    created_at: str
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.graph_ref, GraphRef):
            raise TypeError("graph_ref must be GraphRef")
        if not isinstance(self.task_ref, TaskRef) or not isinstance(self.run_ref, RunRef):
            raise GraphContractError("Graph requires exact TaskRef and RunRef")
        if self.task_ref.project_ref != self.project_ref or self.run_ref.project_ref != self.project_ref:
            raise GraphScopeError("Graph Project scope mismatch")
        if not isinstance(self.task_digest, str) or _SHA256_PATTERN.fullmatch(self.task_digest) is None:
            raise GraphContractError("Graph Task digest is malformed")
        if not isinstance(self.nodes, tuple) or not all(isinstance(node, Node) for node in self.nodes):
            raise GraphContractError("Graph nodes must contain Node")
        if any(node.graph_ref != self.graph_ref for node in self.nodes):
            raise GraphScopeError("Node belongs to another Graph revision")
        validate_dag(self.nodes)
        nodes = tuple(sorted(self.nodes, key=lambda node: node.node_id))
        object.__setattr__(self, "nodes", nodes)
        if self.revision == 1:
            if self.prior_ref is not None:
                raise GraphContractError("Initial Graph revision cannot have prior_ref")
        elif (
            self.prior_ref is None
            or self.prior_ref.project_ref != self.project_ref
            or self.prior_ref.graph_id != self.graph_id
            or self.prior_ref.revision != self.revision - 1
        ):
            raise GraphContractError("Graph revision requires exact immediate prior_ref")
        compiler_values = (self.compiler_identity, self.compiler_version)
        if any(item is not None for item in compiler_values) and not all(
            item is not None for item in compiler_values
        ):
            raise GraphContractError("Compiler identity and version are all-or-none")
        if self.compiler_identity is not None and (
            _ABSOLUTE_REF_PATTERN.fullmatch(self.compiler_identity) is None
            or self.compiler_version is None
            or _VERSION_PATTERN.fullmatch(self.compiler_version) is None
        ):
            raise GraphContractError("Compiler provenance is malformed")
        _validate_timestamp(self.created_at, "created_at")
        object.__setattr__(self, "semantic_digest", _sha256(self._semantic_payload()))
        object.__setattr__(
            self,
            "record_sha256",
            _sha256(
                {
                    "created_at": self.created_at,
                    "graph_id": self.graph_id,
                    "prior_ref": None if self.prior_ref is None else self.prior_ref.value,
                    "project_id": self.project_ref.value,
                    "revision": self.revision,
                    "semantic_digest": self.semantic_digest,
                }
            ),
        )

    @classmethod
    def build(
        cls,
        graph_ref: GraphRef,
        task_ref: TaskRef,
        task_digest: str,
        run_ref: RunRef,
        nodes: Sequence[Node],
        *,
        created_at: str,
        prior_ref: GraphRef | None = None,
        compiler_identity: str | None = None,
        compiler_version: str | None = None,
    ) -> "Graph":
        if isinstance(nodes, (str, bytes)) or not isinstance(nodes, Sequence):
            raise GraphContractError("Graph nodes must be a sequence")
        return cls(
            graph_ref,
            task_ref,
            task_digest,
            run_ref,
            tuple(nodes),
            prior_ref,
            compiler_identity,
            compiler_version,
            created_at,
        )

    @property
    def project_ref(self) -> ProjectRef:
        return self.graph_ref.project_ref

    @property
    def graph_id(self) -> str:
        return self.graph_ref.graph_id

    @property
    def revision(self) -> int:
        return self.graph_ref.revision

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "compiler_identity": self.compiler_identity,
            "compiler_version": self.compiler_version,
            "nodes": [node._semantic_payload() for node in self.nodes],
            "project_id": self.project_ref.value,
            "run_id": self.run_ref.run_id,
            "task_digest": self.task_digest,
            "task_id": self.task_ref.task_id,
            "task_revision": self.task_ref.revision,
        }

    def topological_order(self) -> tuple[NodeRef, ...]:
        return validate_dag(self.nodes)

    def ready_set(
        self,
        terminal_states: Mapping[NodeRef, str],
        condition_results: Mapping[str, bool],
        task: Task,
    ) -> tuple[NodeRef, ...]:
        if not isinstance(terminal_states, Mapping) or not isinstance(condition_results, Mapping):
            raise GraphContractError("ready_set state inputs must be mappings")
        if (
            not isinstance(task, Task)
            or task.task_ref != self.task_ref
            or not hmac.compare_digest(task.canonical_digest, self.task_digest)
        ):
            raise GraphContractError("ready_set requires the exact bound Task authority")
        nodes = {node.node_ref: node for node in self.nodes}
        known_conditions = {
            node.condition_ref for node in self.nodes if node.condition_ref is not None
        }
        for node_ref, status in terminal_states.items():
            if node_ref not in nodes or status not in _TERMINAL_STATUSES:
                raise GraphContractError("ready_set requires exact terminal Node state")
        for condition_ref, result in condition_results.items():
            if (
                not isinstance(condition_ref, str)
                or condition_ref not in known_conditions
                or not isinstance(result, bool)
            ):
                raise GraphContractError("condition result is malformed")

        def condition(node: Node) -> bool | None:
            if node.condition_ref is None:
                return True
            return condition_results.get(node.condition_ref)

        def dependency_satisfied(node_ref: NodeRef) -> bool:
            status = terminal_states.get(node_ref)
            if status is not None:
                return status in _SATISFIED_STATUSES
            return condition(nodes[node_ref]) is False

        ready: list[NodeRef] = []
        for node in self.nodes:
            try:
                TaskRevisionService.require_side_effect_within(
                    task,
                    node.side_effect_requirement,
                )
            except TaskSideEffectError as exc:
                raise GraphSideEffectError(
                    "Node exceeds exact Task authority during readiness"
                ) from exc
            state = terminal_states.get(node.node_ref)
            if condition(node) is False and state not in {None, "SATISFIED", "SKIPPED"}:
                raise GraphContractError(
                    "Terminal Node state contradicts deterministic false condition"
                )
            if node.node_ref in terminal_states:
                continue
            if condition(node) is not True:
                continue
            if all(dependency_satisfied(dependency) for dependency in node.dependencies):
                ready.append(node.node_ref)
        return tuple(sorted(ready, key=lambda item: item.node_id))


class GraphService:
    """Atomic durable Graph revision, binding, and read service."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.runs = RunService(self.database_path)
        self.capabilities = CapabilityRegistry(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
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
                CREATE TABLE IF NOT EXISTS graph_revisions (
                    project_id TEXT NOT NULL, graph_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    task_id TEXT NOT NULL, task_revision INTEGER NOT NULL, task_digest TEXT NOT NULL,
                    run_id TEXT NOT NULL, prior_revision INTEGER,
                    compiler_identity TEXT, compiler_version TEXT, created_at TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, revision),
                    UNIQUE (project_id, graph_id, revision, record_sha256),
                    FOREIGN KEY (project_id, task_id, task_revision, task_digest)
                        REFERENCES task_revisions(project_id, task_id, revision, canonical_digest)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, run_id) REFERENCES runs(project_id, run_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, graph_id, prior_revision)
                        REFERENCES graph_revisions(project_id, graph_id, revision)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS graph_nodes (
                    project_id TEXT NOT NULL, graph_id TEXT NOT NULL, graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL, executor_kind TEXT NOT NULL,
                    required_capabilities_json TEXT NOT NULL, dependencies_json TEXT NOT NULL,
                    input_bindings_json TEXT NOT NULL, output_contract_json TEXT NOT NULL,
                    condition_ref TEXT, side_effect_requirement TEXT NOT NULL,
                    resource_hints_json TEXT NOT NULL, evidence_requirements_json TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id),
                    FOREIGN KEY (project_id, graph_id, graph_revision)
                        REFERENCES graph_revisions(project_id, graph_id, revision) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS graph_dependencies (
                    project_id TEXT NOT NULL, graph_id TEXT NOT NULL, graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL, dependency_node_id TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id, dependency_node_id),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id)
                        REFERENCES graph_nodes(project_id, graph_id, graph_revision, node_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, graph_id, graph_revision, dependency_node_id)
                        REFERENCES graph_nodes(project_id, graph_id, graph_revision, node_id)
                        ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS graph_input_bindings (
                    project_id TEXT NOT NULL, graph_id TEXT NOT NULL, graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL, input_name TEXT NOT NULL, source_kind TEXT NOT NULL,
                    source_ref TEXT NOT NULL, identity_digest TEXT NOT NULL, output_key TEXT,
                    source_artifact_id TEXT, source_artifact_revision INTEGER,
                    source_record_sha256 TEXT,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id, input_name),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id)
                        REFERENCES graph_nodes(project_id, graph_id, graph_revision, node_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, source_artifact_id,
                        source_artifact_revision, source_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    CHECK (
                        (source_kind = 'artifact' AND source_artifact_id IS NOT NULL
                            AND source_artifact_revision IS NOT NULL
                            AND source_record_sha256 IS NOT NULL)
                        OR
                        (source_kind != 'artifact' AND source_artifact_id IS NULL
                            AND source_artifact_revision IS NULL
                            AND source_record_sha256 IS NULL)
                    )
                );

                CREATE TABLE IF NOT EXISTS graph_heads (
                    project_id TEXT NOT NULL, graph_id TEXT NOT NULL,
                    current_revision INTEGER NOT NULL, current_record_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id),
                    FOREIGN KEY (project_id, graph_id, current_revision, current_record_sha256)
                        REFERENCES graph_revisions(project_id, graph_id, revision, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS run_graph_bindings (
                    project_id TEXT NOT NULL, run_id TEXT NOT NULL, graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL, graph_record_sha256 TEXT NOT NULL,
                    bound_at TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id, graph_revision),
                    UNIQUE (project_id, run_id, graph_id, graph_revision, record_sha256),
                    FOREIGN KEY (project_id, run_id) REFERENCES runs(project_id, run_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, graph_id, graph_revision, graph_record_sha256)
                        REFERENCES graph_revisions(project_id, graph_id, revision, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS run_graph_heads (
                    project_id TEXT NOT NULL, run_id TEXT NOT NULL, graph_id TEXT NOT NULL,
                    current_graph_revision INTEGER NOT NULL,
                    current_binding_sha256 TEXT NOT NULL, updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id),
                    FOREIGN KEY (project_id, run_id, graph_id, current_graph_revision, current_binding_sha256)
                        REFERENCES run_graph_bindings(
                            project_id, run_id, graph_id, graph_revision, record_sha256
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS graph_revisions_no_update BEFORE UPDATE ON graph_revisions
                BEGIN SELECT RAISE(ABORT, 'Graph revisions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS graph_revisions_no_delete BEFORE DELETE ON graph_revisions
                BEGIN SELECT RAISE(ABORT, 'Graph revisions cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS graph_nodes_no_update BEFORE UPDATE ON graph_nodes
                BEGIN SELECT RAISE(ABORT, 'Graph Nodes are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS graph_nodes_no_delete BEFORE DELETE ON graph_nodes
                BEGIN SELECT RAISE(ABORT, 'Graph Nodes cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS graph_dependencies_no_update BEFORE UPDATE ON graph_dependencies
                BEGIN SELECT RAISE(ABORT, 'Graph dependencies are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS graph_dependencies_no_delete BEFORE DELETE ON graph_dependencies
                BEGIN SELECT RAISE(ABORT, 'Graph dependencies cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS graph_input_bindings_no_update BEFORE UPDATE ON graph_input_bindings
                BEGIN SELECT RAISE(ABORT, 'Graph input bindings are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS graph_input_bindings_no_delete BEFORE DELETE ON graph_input_bindings
                BEGIN SELECT RAISE(ABORT, 'Graph input bindings cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS run_graph_bindings_no_update BEFORE UPDATE ON run_graph_bindings
                BEGIN SELECT RAISE(ABORT, 'Run Graph bindings are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS run_graph_bindings_no_delete BEFORE DELETE ON run_graph_bindings
                BEGIN SELECT RAISE(ABORT, 'Run Graph bindings cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS graph_heads_no_delete BEFORE DELETE ON graph_heads
                BEGIN SELECT RAISE(ABORT, 'Graph heads cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS run_graph_heads_no_delete BEFORE DELETE ON run_graph_heads
                BEGIN SELECT RAISE(ABORT, 'Run Graph heads cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS graph_heads_monotonic BEFORE UPDATE ON graph_heads
                WHEN NEW.current_revision != OLD.current_revision + 1
                  OR NEW.project_id != OLD.project_id OR NEW.graph_id != OLD.graph_id
                BEGIN SELECT RAISE(ABORT, 'Graph head must advance monotonically'); END;
                CREATE TRIGGER IF NOT EXISTS run_graph_heads_monotonic BEFORE UPDATE ON run_graph_heads
                WHEN NEW.current_graph_revision != OLD.current_graph_revision + 1
                  OR NEW.project_id != OLD.project_id OR NEW.run_id != OLD.run_id
                  OR NEW.graph_id != OLD.graph_id
                BEGIN SELECT RAISE(ABORT, 'Run Graph head must advance monotonically'); END;
                """
            )
        finally:
            connection.close()

    def create_graph(
        self,
        requesting_access: ProjectAccess,
        *,
        graph_ref: GraphRef,
        task_ref: TaskRef,
        expected_task_digest: str,
        run_ref: RunRef,
        nodes: Sequence[Node],
        compiler_identity: str | None,
        compiler_version: str | None,
        authority_attempt: ExecutionAttempt,
    ) -> Graph:
        if not isinstance(graph_ref, GraphRef) or graph_ref.revision != 1:
            raise GraphContractError("Initial GraphRef revision must be one")
        task, run = self._validate_authority(
            requesting_access,
            graph_ref.project_ref,
            task_ref,
            expected_task_digest,
            run_ref,
        )
        self._validate_nodes(requesting_access, task, graph_ref, nodes)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._require_publication_authority(
                connection,
                requesting_access,
                authority_attempt,
                run_ref,
                task_ref,
                expected_task_digest,
            )
            graph = Graph.build(
                graph_ref,
                task_ref,
                expected_task_digest,
                run_ref,
                nodes,
                created_at=self._database_now(connection),
                compiler_identity=compiler_identity,
                compiler_version=compiler_version,
            )
            self._insert_graph(connection, graph)
            self._insert_initial_heads(connection, graph)
            connection.commit()
            return graph
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise GraphConflictError("Initial Graph identity conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_revision(
        self,
        requesting_access: ProjectAccess,
        *,
        prior_ref: GraphRef,
        nodes: Sequence[Node],
        compiler_identity: str | None,
        compiler_version: str | None,
        authority_attempt: ExecutionAttempt,
    ) -> Graph:
        prior = self.get_graph(requesting_access, prior_ref)
        next_ref = GraphRef(prior.project_ref, prior.graph_id, prior.revision + 1)
        self._validate_nodes(requesting_access, self.tasks.get_task(requesting_access, prior.task_ref), next_ref, nodes)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._require_publication_authority(
                connection,
                requesting_access,
                authority_attempt,
                prior.run_ref,
                prior.task_ref,
                prior.task_digest,
            )
            head = self._fetch_graph_head(connection, prior_ref)
            if (
                head["current_revision"] != prior.revision
                or head["current_record_sha256"] != prior.record_sha256
                or head["updated_at"] != prior.created_at
            ):
                raise GraphConflictError("Graph revision predecessor is stale")
            self._verify_digest(
                self._graph_head_sha256(prior),
                head["record_sha256"],
                "Graph head",
            )
            self._verify_active_run_head(connection, prior)
            graph = Graph.build(
                next_ref,
                prior.task_ref,
                prior.task_digest,
                prior.run_ref,
                nodes,
                created_at=self._database_now(connection),
                prior_ref=prior.graph_ref,
                compiler_identity=compiler_identity,
                compiler_version=compiler_version,
            )
            if graph.semantic_digest == prior.semantic_digest:
                raise GraphConflictError("Graph revision requires a material replan")
            self._insert_graph(connection, graph)
            self._advance_heads(connection, prior, graph)
            connection.commit()
            return graph
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise GraphConflictError("Graph revision conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_graph(self, requesting_access: ProjectAccess, graph_ref: GraphRef) -> Graph:
        self._authorize(requesting_access, graph_ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            graph = self._fetch_graph(connection, graph_ref)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        task, _ = self._validate_authority(
            requesting_access,
            graph.project_ref,
            graph.task_ref,
            graph.task_digest,
            graph.run_ref,
        )
        self._validate_nodes(requesting_access, task, graph.graph_ref, graph.nodes)
        return graph

    def get_active_graph(self, requesting_access: ProjectAccess, run_ref: RunRef) -> Graph:
        self._authorize(requesting_access, run_ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            head = connection.execute(
                "SELECT * FROM run_graph_heads WHERE project_id = ? AND run_id = ?",
                (run_ref.project_ref.value, run_ref.run_id),
            ).fetchone()
            if head is None:
                binding_exists = connection.execute(
                    """
                    SELECT 1 FROM run_graph_bindings
                    WHERE project_id = ? AND run_id = ? LIMIT 1
                    """,
                    (run_ref.project_ref.value, run_ref.run_id),
                ).fetchone()
                if binding_exists is not None:
                    raise GraphIntegrityError("Active Run Graph head is missing")
                raise GraphNotFoundError("Run has no active Graph")
            expected_head = self._run_head_sha256(
                run_ref,
                cast(str, head["graph_id"]),
                cast(int, head["current_graph_revision"]),
                cast(str, head["current_binding_sha256"]),
                cast(str, head["updated_at"]),
            )
            self._verify_digest(expected_head, head["record_sha256"], "Run Graph head")
            self._verify_run_binding_history(connection, run_ref, head)
            binding = connection.execute(
                """
                SELECT * FROM run_graph_bindings
                WHERE project_id = ? AND run_id = ? AND graph_id = ? AND graph_revision = ?
                """,
                (
                    run_ref.project_ref.value,
                    run_ref.run_id,
                    head["graph_id"],
                    head["current_graph_revision"],
                ),
            ).fetchone()
            if binding is None:
                raise GraphIntegrityError("Active Run Graph binding is missing")
            self._verify_digest(
                self._run_binding_sha256(
                    run_ref,
                    cast(str, binding["graph_id"]),
                    cast(int, binding["graph_revision"]),
                    cast(str, binding["graph_record_sha256"]),
                    cast(str, binding["bound_at"]),
                ),
                binding["record_sha256"],
                "Run Graph binding",
            )
            if binding["record_sha256"] != head["current_binding_sha256"]:
                raise GraphIntegrityError("Run Graph head and binding differ")
            graph = self._fetch_graph(
                connection,
                GraphRef(
                    run_ref.project_ref,
                    cast(str, head["graph_id"]),
                    cast(int, head["current_graph_revision"]),
                ),
            )
            if graph.record_sha256 != binding["graph_record_sha256"]:
                raise GraphIntegrityError("Run Graph binding record differs")
            graph_head = self._fetch_graph_head(connection, graph.graph_ref)
            if (
                graph_head["current_revision"] != graph.revision
                or graph_head["current_record_sha256"] != graph.record_sha256
            ):
                raise GraphIntegrityError("Run Graph head is not the active Graph revision")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        task, _ = self._validate_authority(
            requesting_access,
            graph.project_ref,
            graph.task_ref,
            graph.task_digest,
            graph.run_ref,
        )
        self._validate_nodes(requesting_access, task, graph.graph_ref, graph.nodes)
        return graph

    def _validate_authority(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        task_ref: TaskRef,
        task_digest: str,
        run_ref: RunRef,
    ) -> tuple[Task, Run]:
        self._authorize(access, project_ref)
        if task_ref.project_ref != project_ref or run_ref.project_ref != project_ref:
            raise GraphScopeError("Graph Project scope mismatch")
        task = self.tasks.get_task(access, task_ref)
        run = self.runs.get_run(access, run_ref)
        if not hmac.compare_digest(task.canonical_digest, task_digest):
            raise GraphContractError("Graph expected Task digest does not match")
        if run.task_ref != task_ref or not hmac.compare_digest(run.task_digest, task_digest):
            raise GraphContractError("Graph Run Task binding does not match")
        return task, run

    def _require_publication_authority(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        attempt: ExecutionAttempt,
        run_ref: RunRef,
        task_ref: TaskRef,
        task_digest: str,
    ) -> Run:
        try:
            run = self.runs.assert_current_run_authority_in_transaction(
                connection,
                access,
                attempt,
            )
        except (RunAuthorityError, RunError) as exc:
            raise GraphAuthorityError(
                "Graph publication requires current fenced Run authority"
            ) from exc
        if (
            run.run_ref != run_ref
            or run.task_ref != task_ref
            or not hmac.compare_digest(run.task_digest, task_digest)
        ):
            raise GraphAuthorityError(
                "Graph publication authority does not match its exact Run and Task"
            )
        return run

    def _validate_nodes(
        self,
        access: ProjectAccess,
        task: Task,
        graph_ref: GraphRef,
        nodes: Sequence[Node],
    ) -> None:
        validate_dag(nodes)
        for node in nodes:
            if node.graph_ref != graph_ref:
                raise GraphScopeError("Node belongs to another Graph revision")
            try:
                TaskRevisionService.require_side_effect_within(
                    task,
                    node.side_effect_requirement,
                )
            except TaskSideEffectError as exc:
                raise GraphSideEffectError("Node exceeds Task side-effect authority") from exc
            for capability_ref in node.required_capabilities:
                try:
                    self.capabilities.get(capability_ref)
                except CapabilityNotFoundError as exc:
                    raise GraphContractError("Node requires unknown CapabilityRef") from exc
            for binding in node.input_bindings:
                self._validate_input(access, task, graph_ref, node, binding, nodes)

    def _validate_input(
        self,
        access: ProjectAccess,
        task: Task,
        graph_ref: GraphRef,
        node: Node,
        binding: NodeInputBinding,
        nodes: Sequence[Node],
    ) -> None:
        if binding.project_ref != graph_ref.project_ref:
            raise GraphScopeError("Node input Project scope mismatch")
        if binding.source_kind == "task":
            if not any(
                item.source_ref == binding.source_ref
                and item.content_sha256 == binding.identity_digest
                for item in task.input_refs
            ):
                raise GraphContractError("Node Task input is not bound by exact Task revision")
        elif binding.source_kind == "artifact":
            matched = re.fullmatch(
                r"artifact://(prj_[0-9a-f]{32})/(art_[0-9a-f]{32})/([1-9][0-9]*)",
                binding.source_ref,
            )
            if matched is None:
                raise GraphContractError("Artifact Node input is malformed")
            if matched.group(1) != graph_ref.project_ref.value:
                raise GraphScopeError("Artifact Node input Project scope mismatch")
            artifact_ref = ArtifactRef(ProjectRef(matched.group(1)), matched.group(2), int(matched.group(3)))
            self.artifacts.get_artifact(access, artifact_ref)
            if not hmac.compare_digest(
                hashlib.sha256(binding.source_ref.encode()).hexdigest(),
                binding.identity_digest,
            ):
                raise GraphContractError("Artifact Node input digest is inconsistent")
        elif binding.source_kind == "source":
            matched = re.fullmatch(
                r"source://(prj_[0-9a-f]{32})/sha256/([0-9a-f]{64})",
                binding.source_ref,
            )
            if matched is None:
                raise GraphContractError("Source Node input is malformed")
            if matched.group(1) != graph_ref.project_ref.value:
                raise GraphScopeError("Source Node input Project scope mismatch")
            if not hmac.compare_digest(matched.group(2), binding.identity_digest):
                raise GraphContractError("Source Node input digest is inconsistent")
        elif binding.source_kind == "content":
            matched = re.fullmatch(
                r"content://sha256/([0-9a-f]{64})\?size=(0|[1-9][0-9]*)",
                binding.source_ref,
            )
            if matched is None or not hmac.compare_digest(
                matched.group(1),
                binding.identity_digest,
            ):
                raise GraphContractError("Content Node input digest is inconsistent")
        elif binding.source_kind == "node_output":
            matched = re.fullmatch(
                r"node://(prj_[0-9a-f]{32})/(gph_[0-9a-f]{32})/([1-9][0-9]*)/(nod_[0-9a-f]{32})",
                binding.source_ref,
            )
            by_ref = {candidate.node_ref: candidate for candidate in nodes}
            if matched is None:
                raise GraphContractError("Node output input is malformed")
            source_ref = NodeRef(
                GraphRef(ProjectRef(matched.group(1)), matched.group(2), int(matched.group(3))),
                matched.group(4),
            )
            source_node = by_ref.get(source_ref)
            if source_node is None or source_ref not in node.dependencies:
                raise GraphContractError("Node output must come from an exact dependency")
            if binding.output_key not in source_node.output_contract:
                raise GraphContractError("Node output contract key does not exist")
            expected = hashlib.sha256(
                f"{source_ref.value}\x00{binding.output_key}".encode()
            ).hexdigest()
            if not hmac.compare_digest(expected, binding.identity_digest):
                raise GraphContractError("Node output binding digest is inconsistent")

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectScopeError as exc:
            raise GraphScopeError("Graph Project scope mismatch") from exc

    @staticmethod
    def _database_now(connection: sqlite3.Connection) -> str:
        value = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')").fetchone()[0]
        if not isinstance(value, str):
            raise GraphIntegrityError("Durable database time is unavailable")
        return _validate_timestamp(value, "database_now")

    def _insert_graph(self, connection: sqlite3.Connection, graph: Graph) -> None:
        connection.execute(
            """
            INSERT INTO graph_revisions (
                project_id, graph_id, revision, task_id, task_revision, task_digest,
                run_id, prior_revision, compiler_identity, compiler_version,
                created_at, semantic_digest, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                graph.project_ref.value, graph.graph_id, graph.revision,
                graph.task_ref.task_id, graph.task_ref.revision, graph.task_digest,
                graph.run_ref.run_id,
                None if graph.prior_ref is None else graph.prior_ref.revision,
                graph.compiler_identity, graph.compiler_version, graph.created_at,
                graph.semantic_digest, graph.record_sha256,
            ),
        )
        for node in graph.nodes:
            connection.execute(
                """
                INSERT INTO graph_nodes (
                    project_id, graph_id, graph_revision, node_id, executor_kind,
                    required_capabilities_json, dependencies_json, input_bindings_json,
                    output_contract_json, condition_ref, side_effect_requirement,
                    resource_hints_json, evidence_requirements_json,
                    semantic_digest, record_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    graph.project_ref.value, graph.graph_id, graph.revision, node.node_id,
                    node.executor_kind,
                    _json([item.value for item in node.required_capabilities]),
                    _json([item.node_id for item in node.dependencies]),
                    _json([self._binding_payload(item) for item in node.input_bindings]),
                    _json(dict(node.output_contract)), node.condition_ref,
                    node.side_effect_requirement, _json(dict(node.resource_hints)),
                    _json(list(node.evidence_requirements)),
                    node.semantic_digest, node.record_sha256,
                ),
            )
        for node in graph.nodes:
            connection.executemany(
                """
                INSERT INTO graph_dependencies (
                    project_id, graph_id, graph_revision, node_id, dependency_node_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (graph.project_ref.value, graph.graph_id, graph.revision, node.node_id, dep.node_id)
                    for dep in node.dependencies
                ),
            )
            for binding in node.input_bindings:
                source_artifact = None
                if binding.source_kind == "artifact":
                    source_artifact = self.artifacts._fetch_artifact(
                        connection,
                        self._artifact_ref_from_binding(binding),
                    )
                connection.execute(
                    """
                    INSERT INTO graph_input_bindings (
                        project_id, graph_id, graph_revision, node_id, input_name,
                        source_kind, source_ref, identity_digest, output_key,
                        source_artifact_id, source_artifact_revision,
                        source_record_sha256, record_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        graph.project_ref.value, graph.graph_id, graph.revision, node.node_id,
                        binding.input_name, binding.source_kind, binding.source_ref,
                        binding.identity_digest, binding.output_key,
                        None if source_artifact is None else source_artifact.artifact_id,
                        None if source_artifact is None else source_artifact.revision,
                        None if source_artifact is None else source_artifact.record_sha256,
                        self._binding_sha256(
                            graph.graph_ref,
                            node.node_id,
                            binding,
                            None if source_artifact is None else source_artifact.record_sha256,
                        ),
                    ),
                )

    def _insert_initial_heads(self, connection: sqlite3.Connection, graph: Graph) -> None:
        connection.execute(
            "INSERT INTO graph_heads VALUES (?, ?, ?, ?, ?, ?)",
            (
                graph.project_ref.value, graph.graph_id, graph.revision,
                graph.record_sha256, graph.created_at, self._graph_head_sha256(graph),
            ),
        )
        binding_sha = self._run_binding_sha256(
            graph.run_ref, graph.graph_id, graph.revision, graph.record_sha256, graph.created_at
        )
        connection.execute(
            "INSERT INTO run_graph_bindings VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                graph.project_ref.value, graph.run_ref.run_id, graph.graph_id,
                graph.revision, graph.record_sha256, graph.created_at, binding_sha,
            ),
        )
        connection.execute(
            "INSERT INTO run_graph_heads VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                graph.project_ref.value, graph.run_ref.run_id, graph.graph_id,
                graph.revision, binding_sha, graph.created_at,
                self._run_head_sha256(
                    graph.run_ref, graph.graph_id, graph.revision, binding_sha, graph.created_at
                ),
            ),
        )

    def _advance_heads(self, connection: sqlite3.Connection, prior: Graph, graph: Graph) -> None:
        prior_binding_sha = self._run_binding_sha256(
            prior.run_ref,
            prior.graph_id,
            prior.revision,
            prior.record_sha256,
            prior.created_at,
        )
        binding_sha = self._run_binding_sha256(
            graph.run_ref, graph.graph_id, graph.revision, graph.record_sha256, graph.created_at
        )
        connection.execute(
            "INSERT INTO run_graph_bindings VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                graph.project_ref.value, graph.run_ref.run_id, graph.graph_id,
                graph.revision, graph.record_sha256, graph.created_at, binding_sha,
            ),
        )
        updated_graph = connection.execute(
            """
            UPDATE graph_heads SET current_revision = ?, current_record_sha256 = ?,
                updated_at = ?, record_sha256 = ?
            WHERE project_id = ? AND graph_id = ? AND current_revision = ?
                AND current_record_sha256 = ? AND updated_at = ? AND record_sha256 = ?
            """,
            (
                graph.revision, graph.record_sha256, graph.created_at,
                self._graph_head_sha256(graph), graph.project_ref.value, graph.graph_id,
                prior.revision, prior.record_sha256, prior.created_at,
                self._graph_head_sha256(prior),
            ),
        )
        updated_run = connection.execute(
            """
            UPDATE run_graph_heads SET current_graph_revision = ?, current_binding_sha256 = ?,
                updated_at = ?, record_sha256 = ?
            WHERE project_id = ? AND run_id = ? AND graph_id = ?
                AND current_graph_revision = ? AND current_binding_sha256 = ?
                AND updated_at = ? AND record_sha256 = ?
            """,
            (
                graph.revision, binding_sha, graph.created_at,
                self._run_head_sha256(
                    graph.run_ref, graph.graph_id, graph.revision, binding_sha, graph.created_at
                ),
                graph.project_ref.value, graph.run_ref.run_id, graph.graph_id,
                prior.revision, prior_binding_sha, prior.created_at,
                self._run_head_sha256(
                    prior.run_ref,
                    prior.graph_id,
                    prior.revision,
                    prior_binding_sha,
                    prior.created_at,
                ),
            ),
        )
        if updated_graph.rowcount != 1 or updated_run.rowcount != 1:
            raise GraphConflictError("Graph active revision changed concurrently")

    def _verify_active_run_head(
        self,
        connection: sqlite3.Connection,
        graph: Graph,
    ) -> sqlite3.Row:
        head = connection.execute(
            "SELECT * FROM run_graph_heads WHERE project_id = ? AND run_id = ?",
            (graph.project_ref.value, graph.run_ref.run_id),
        ).fetchone()
        if head is None:
            raise GraphIntegrityError("Active Run Graph head is missing")
        binding_sha = self._run_binding_sha256(
            graph.run_ref,
            graph.graph_id,
            graph.revision,
            graph.record_sha256,
            graph.created_at,
        )
        if (
            head["graph_id"] != graph.graph_id
            or head["current_graph_revision"] != graph.revision
            or head["current_binding_sha256"] != binding_sha
            or head["updated_at"] != graph.created_at
        ):
            raise GraphIntegrityError("Active Run Graph head does not match predecessor")
        self._verify_digest(
            self._run_head_sha256(
                graph.run_ref,
                graph.graph_id,
                graph.revision,
                binding_sha,
                graph.created_at,
            ),
            head["record_sha256"],
            "Run Graph head",
        )
        return cast(sqlite3.Row, head)

    def _verify_run_binding_history(
        self,
        connection: sqlite3.Connection,
        run_ref: RunRef,
        head: sqlite3.Row,
    ) -> None:
        bindings = connection.execute(
            """
            SELECT * FROM run_graph_bindings
            WHERE project_id = ? AND run_id = ? ORDER BY graph_revision
            """,
            (run_ref.project_ref.value, run_ref.run_id),
        ).fetchall()
        expected_revisions = tuple(range(1, cast(int, head["current_graph_revision"]) + 1))
        if tuple(row["graph_revision"] for row in bindings) != expected_revisions:
            raise GraphIntegrityError("Run Graph binding history is not gap-free")
        for binding in bindings:
            if binding["graph_id"] != head["graph_id"]:
                raise GraphIntegrityError("Run Graph binding history changed Graph identity")
            graph_row = connection.execute(
                """
                SELECT record_sha256, created_at FROM graph_revisions
                WHERE project_id = ? AND graph_id = ? AND revision = ?
                """,
                (
                    run_ref.project_ref.value,
                    binding["graph_id"],
                    binding["graph_revision"],
                ),
            ).fetchone()
            if (
                graph_row is None
                or graph_row["record_sha256"] != binding["graph_record_sha256"]
                or graph_row["created_at"] != binding["bound_at"]
            ):
                raise GraphIntegrityError("Run Graph binding does not match Graph history")
            self._verify_digest(
                self._run_binding_sha256(
                    run_ref,
                    cast(str, binding["graph_id"]),
                    cast(int, binding["graph_revision"]),
                    cast(str, binding["graph_record_sha256"]),
                    cast(str, binding["bound_at"]),
                ),
                binding["record_sha256"],
                "Run Graph binding",
            )

    def _fetch_graph(self, connection: sqlite3.Connection, graph_ref: GraphRef) -> Graph:
        if not connection.in_transaction:
            raise GraphIntegrityError("Graph reads require one durable snapshot")
        rows = connection.execute(
            "SELECT * FROM graph_revisions WHERE project_id = ? AND graph_id = ? ORDER BY revision",
            (graph_ref.project_ref.value, graph_ref.graph_id),
        ).fetchall()
        if not rows:
            raise GraphNotFoundError("Graph revision not found")
        if tuple(row["revision"] for row in rows) != tuple(range(1, len(rows) + 1)):
            raise GraphIntegrityError("Graph revisions are not gap-free")
        graphs = tuple(self._graph_from_row(connection, row) for row in rows)
        first = graphs[0]
        for index, graph in enumerate(graphs):
            expected_prior = None if index == 0 else graphs[index - 1].graph_ref
            if (
                graph.prior_ref != expected_prior
                or graph.task_ref != first.task_ref
                or not hmac.compare_digest(graph.task_digest, first.task_digest)
                or graph.run_ref != first.run_ref
            ):
                raise GraphIntegrityError("Graph revision lineage is inconsistent")
        head = self._fetch_graph_head(connection, graph_ref)
        latest = graphs[-1]
        if (
            head["current_revision"] != latest.revision
            or head["current_record_sha256"] != latest.record_sha256
            or head["updated_at"] != latest.created_at
        ):
            raise GraphIntegrityError("Graph history does not match durable head")
        selected = next((graph for graph in graphs if graph.revision == graph_ref.revision), None)
        if selected is None:
            raise GraphNotFoundError("Graph revision not found")
        self._verify_digest(
            self._graph_head_sha256(latest),
            head["record_sha256"],
            "Graph head",
        )
        run_head = self._verify_active_run_head(connection, latest)
        self._verify_run_binding_history(connection, latest.run_ref, run_head)
        return selected

    def _graph_from_row(self, connection: sqlite3.Connection, row: sqlite3.Row) -> Graph:
        graph_ref = GraphRef(ProjectRef(cast(str, row["project_id"])), cast(str, row["graph_id"]), cast(int, row["revision"]))
        node_rows = connection.execute(
            """
            SELECT * FROM graph_nodes
            WHERE project_id = ? AND graph_id = ? AND graph_revision = ? ORDER BY node_id
            """,
            (graph_ref.project_ref.value, graph_ref.graph_id, graph_ref.revision),
        ).fetchall()
        try:
            nodes = tuple(self._node_from_row(graph_ref, node_row) for node_row in node_rows)
            graph = Graph.build(
                graph_ref,
                TaskRef(graph_ref.project_ref, cast(str, row["task_id"]), cast(int, row["task_revision"])),
                cast(str, row["task_digest"]),
                RunRef(graph_ref.project_ref, cast(str, row["run_id"])),
                nodes,
                created_at=cast(str, row["created_at"]),
                prior_ref=(
                    None
                    if row["prior_revision"] is None
                    else GraphRef(graph_ref.project_ref, graph_ref.graph_id, cast(int, row["prior_revision"]))
                ),
                compiler_identity=cast(str | None, row["compiler_identity"]),
                compiler_version=cast(str | None, row["compiler_version"]),
            )
        except (TypeError, ValueError, KeyError, json.JSONDecodeError, GraphError) as exc:
            raise GraphIntegrityError("Persisted Graph is malformed") from exc
        self._verify_digest(graph.semantic_digest, row["semantic_digest"], "Graph semantic contract")
        self._verify_digest(graph.record_sha256, row["record_sha256"], "Graph revision")
        self._verify_relationships(connection, graph)
        return graph

    def _node_from_row(self, graph_ref: GraphRef, row: sqlite3.Row) -> Node:
        try:
            node = Node(
                NodeRef(graph_ref, cast(str, row["node_id"])),
                cast(str, row["executor_kind"]),
                tuple(self._parse_capability(value) for value in cast(list[str], json.loads(cast(str, row["required_capabilities_json"])))),
                tuple(NodeRef(graph_ref, value) for value in cast(list[str], json.loads(cast(str, row["dependencies_json"])))),
                tuple(self._parse_binding(graph_ref.project_ref, value) for value in cast(list[dict[str, object]], json.loads(cast(str, row["input_bindings_json"])))),
                cast(dict[str, str], json.loads(cast(str, row["output_contract_json"]))),
                cast(str | None, row["condition_ref"]),
                cast(str, row["side_effect_requirement"]),
                cast(dict[str, GraphValue], json.loads(cast(str, row["resource_hints_json"]))),
                tuple(cast(list[str], json.loads(cast(str, row["evidence_requirements_json"])))),
            )
        except (TypeError, ValueError, KeyError, json.JSONDecodeError, GraphError) as exc:
            raise GraphIntegrityError("Persisted Node is malformed") from exc
        self._verify_digest(node.semantic_digest, row["semantic_digest"], "Node semantic contract")
        self._verify_digest(node.record_sha256, row["record_sha256"], "Node record")
        return node

    def _verify_relationships(self, connection: sqlite3.Connection, graph: Graph) -> None:
        for node in graph.nodes:
            dependency_rows = connection.execute(
                """
                SELECT dependency_node_id FROM graph_dependencies
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
                ORDER BY dependency_node_id
                """,
                (graph.project_ref.value, graph.graph_id, graph.revision, node.node_id),
            ).fetchall()
            if tuple(row["dependency_node_id"] for row in dependency_rows) != tuple(
                item.node_id for item in node.dependencies
            ):
                raise GraphIntegrityError("Graph dependency bindings are inconsistent")
            input_rows = connection.execute(
                """
                SELECT * FROM graph_input_bindings
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ? AND node_id = ?
                ORDER BY input_name
                """,
                (graph.project_ref.value, graph.graph_id, graph.revision, node.node_id),
            ).fetchall()
            bindings: list[NodeInputBinding] = []
            for row in input_rows:
                binding = NodeInputBinding(
                    graph.project_ref,
                    cast(str, row["input_name"]),
                    cast(str, row["source_kind"]),
                    cast(str, row["source_ref"]),
                    cast(str, row["identity_digest"]),
                    cast(str | None, row["output_key"]),
                )
                source_record_sha256 = cast(str | None, row["source_record_sha256"])
                if binding.source_kind == "artifact":
                    artifact_ref = self._artifact_ref_from_binding(binding)
                    if (
                        row["source_artifact_id"] != artifact_ref.artifact_id
                        or row["source_artifact_revision"] != artifact_ref.revision
                        or source_record_sha256 is None
                    ):
                        raise GraphIntegrityError(
                            "Artifact Node input evidence is inconsistent"
                        )
                    try:
                        artifact = self.artifacts._fetch_artifact(connection, artifact_ref)
                    except ArtifactError as exc:
                        raise GraphIntegrityError(
                            "Artifact Node input identity is no longer valid"
                        ) from exc
                    self._verify_digest(
                        artifact.record_sha256,
                        source_record_sha256,
                        "Artifact Node input record",
                    )
                elif any(
                    row[name] is not None
                    for name in (
                        "source_artifact_id",
                        "source_artifact_revision",
                        "source_record_sha256",
                    )
                ):
                    raise GraphIntegrityError(
                        "Non-Artifact Node input carries Artifact evidence"
                    )
                self._verify_digest(
                    self._binding_sha256(
                        graph.graph_ref,
                        node.node_id,
                        binding,
                        source_record_sha256,
                    ),
                    row["record_sha256"],
                    "Node input binding",
                )
                bindings.append(binding)
            if tuple(bindings) != node.input_bindings:
                raise GraphIntegrityError("Graph input bindings are inconsistent")

    def _fetch_graph_head(self, connection: sqlite3.Connection, graph_ref: GraphRef) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM graph_heads WHERE project_id = ? AND graph_id = ?",
            (graph_ref.project_ref.value, graph_ref.graph_id),
        ).fetchone()
        if row is None:
            raise GraphIntegrityError("Graph head is missing")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _parse_capability(value: str) -> CapabilityRef:
        capability_id, separator, version = value.rpartition("@")
        if not separator:
            raise GraphIntegrityError("Persisted CapabilityRef is malformed")
        return CapabilityRef(capability_id, version)

    @staticmethod
    def _binding_payload(binding: NodeInputBinding) -> dict[str, object]:
        return {
            "identity_digest": binding.identity_digest,
            "input_name": binding.input_name,
            "output_key": binding.output_key,
            "source_kind": binding.source_kind,
            "source_ref": binding.source_ref,
        }

    @staticmethod
    def _artifact_ref_from_binding(binding: NodeInputBinding) -> ArtifactRef:
        matched = re.fullmatch(
            r"artifact://(prj_[0-9a-f]{32})/(art_[0-9a-f]{32})/([1-9][0-9]*)",
            binding.source_ref,
        )
        if binding.source_kind != "artifact" or matched is None:
            raise GraphContractError("Artifact Node input is malformed")
        return ArtifactRef(
            ProjectRef(matched.group(1)),
            matched.group(2),
            int(matched.group(3)),
        )

    @classmethod
    def _parse_binding(cls, project_ref: ProjectRef, value: Mapping[str, object]) -> NodeInputBinding:
        return NodeInputBinding(
            project_ref,
            cast(str, value["input_name"]),
            cast(str, value["source_kind"]),
            cast(str, value["source_ref"]),
            cast(str, value["identity_digest"]),
            cast(str | None, value["output_key"]),
        )

    @classmethod
    def _binding_sha256(
        cls,
        graph_ref: GraphRef,
        node_id: str,
        binding: NodeInputBinding,
        source_record_sha256: str | None,
    ) -> str:
        return _sha256(
            {
                "binding": cls._binding_payload(binding),
                "graph_ref": graph_ref.value,
                "node_id": node_id,
                "source_record_sha256": source_record_sha256,
            }
        )

    @staticmethod
    def _graph_head_sha256(graph: Graph) -> str:
        return _sha256(
            {
                "current_record_sha256": graph.record_sha256,
                "current_revision": graph.revision,
                "graph_id": graph.graph_id,
                "project_id": graph.project_ref.value,
                "updated_at": graph.created_at,
            }
        )

    @staticmethod
    def _run_binding_sha256(
        run_ref: RunRef,
        graph_id: str,
        revision: int,
        graph_record_sha256: str,
        bound_at: str,
    ) -> str:
        return _sha256(
            {
                "bound_at": bound_at,
                "graph_id": graph_id,
                "graph_record_sha256": graph_record_sha256,
                "graph_revision": revision,
                "project_id": run_ref.project_ref.value,
                "run_id": run_ref.run_id,
            }
        )

    @staticmethod
    def _run_head_sha256(
        run_ref: RunRef,
        graph_id: str,
        revision: int,
        binding_sha256: str,
        updated_at: str,
    ) -> str:
        return _sha256(
            {
                "current_binding_sha256": binding_sha256,
                "current_graph_revision": revision,
                "graph_id": graph_id,
                "project_id": run_ref.project_ref.value,
                "run_id": run_ref.run_id,
                "updated_at": updated_at,
            }
        )

    @staticmethod
    def _verify_digest(expected: str, persisted: object, label: str) -> None:
        if (
            not isinstance(persisted, str)
            or _SHA256_PATTERN.fullmatch(persisted) is None
            or not hmac.compare_digest(expected, persisted)
        ):
            raise GraphIntegrityError(f"{label} failed integrity verification")
