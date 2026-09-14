"""Durable coordination of deterministic model-evaluation matrix Nodes.

This module deliberately owns no scheduler or model execution authority.  A
matrix cell is an existing Graph Node, execution is supplied as an already
fenced ScheduledDispatch plus callback, and NodeExecution is the durable cell
state.  Run checkpoints provide recovery; Artifacts provide immutable matrix,
cell, and aggregate evidence.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import re
import statistics
from types import MappingProxyType

from .artifact import Artifact, ArtifactRef, ArtifactService, ContentRef
from .checkpoint import CheckpointService, ResumeResult, RunCheckpoint, RunCheckpointRef
from .execution import NodeExecution, NodeExecutionService
from .graph import Graph, GraphRef, GraphService, Node, NodeRef
from .model_evaluation import (
    DescriptiveStatistics,
    EvaluationContractError,
    EvaluationTask,
    ModelCandidate,
    ModelEvaluationResult,
    ModelEvaluationRun,
    ModelEvaluationSuite,
    PairwiseComparison,
)
from .object_store import ObjectStorageBackend
from .project import ProjectAccess, ProjectRef
from .run import ExecutionAttempt, RunRef
from .scheduler import ScheduledDispatch


_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[a-z][a-z0-9+.-]{1,63}://[^\s\x00-\x1f]{1,1024}")
_SUCCESS = frozenset({"ok", "pass", "passed", "success", "succeeded"})
_TERMINAL_CALLS = frozenset(
    {
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "TIMED_OUT",
        "DENIED",
        "OUTCOME_UNKNOWN",
    }
)


class ModelEvaluationRuntimeError(Exception):
    """Base class for deterministic matrix coordination failures."""


class MatrixContractError(ModelEvaluationRuntimeError, ValueError):
    """A matrix identity or callback product is malformed."""


class MatrixAuthorityError(ModelEvaluationRuntimeError):
    """A Graph, Node, allocation, attempt, or fence is not current."""


class MatrixEvidenceError(ModelEvaluationRuntimeError):
    """Claimed cell completion lacks exact immutable evidence."""


class MatrixRecoveryError(ModelEvaluationRuntimeError):
    """Checkpoint recovery cannot be reconciled with this matrix."""


class CellInfrastructureFailure(ModelEvaluationRuntimeError):
    """Retryable infrastructure failure raised by a cell callback."""

    def __init__(
        self,
        reason: str,
        *,
        evidence_refs: Sequence[ArtifactRef] = (),
        retry_possible: bool = True,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.evidence_refs = tuple(evidence_refs)
        self.retry_possible = retry_possible


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise MatrixContractError("matrix evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise MatrixContractError(f"{label} must be a SHA-256 digest")
    return value


def _require_key(value: object, label: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise MatrixContractError(f"{label} is malformed")
    return value


def _require_ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise MatrixContractError(f"{label} must be an exact reference")
    return value


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise MatrixContractError("matrix timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MatrixContractError("matrix timestamp must be timezone-aware")
    return parsed


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _run_value(run_ref: RunRef) -> str:
    return f"run://{run_ref.project_ref.value}/{run_ref.run_id}"


@dataclass(frozen=True)
class EvaluationCellCoordinate:
    """One exact suite/candidate/task/repetition bound to an existing Node."""

    project_ref: ProjectRef
    suite_digest: str
    candidate_id: str
    candidate_digest: str
    task_id: str
    task_digest: str
    repetition: int
    order_index: int
    cache_identity: str
    node_ref: NodeRef
    output_key: str = "result"
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.node_ref, NodeRef):
            raise MatrixContractError("cell Project and Node identities are required")
        if self.node_ref.project_ref != self.project_ref:
            raise MatrixContractError("cell Node crossed Project scope")
        _require_sha(self.suite_digest, "suite digest")
        _require_key(self.candidate_id, "candidate identity")
        _require_sha(self.candidate_digest, "candidate digest")
        _require_key(self.task_id, "task identity")
        _require_sha(self.task_digest, "task digest")
        if not isinstance(self.repetition, int) or isinstance(self.repetition, bool) or self.repetition < 1:
            raise MatrixContractError("cell repetition must be positive")
        if not isinstance(self.order_index, int) or isinstance(self.order_index, bool) or self.order_index < 0:
            raise MatrixContractError("cell order index must be non-negative")
        _require_sha(self.cache_identity, "cache identity")
        _require_key(self.output_key, "cell output key")
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    @classmethod
    def bind(
        cls,
        suite: ModelEvaluationSuite,
        candidate: ModelCandidate,
        task: EvaluationTask,
        repetition: int,
        order_index: int,
        node_ref: NodeRef,
        *,
        output_key: str = "result",
    ) -> EvaluationCellCoordinate:
        cache_identity = _digest(
            {
                "cache_policy": suite.cache_policy_ref,
                "candidate": candidate.canonical_digest,
                "repetition": repetition,
                "suite": suite.canonical_digest,
                "task": task.canonical_digest,
            }
        )
        return cls(
            suite.project_ref,
            suite.canonical_digest,
            candidate.candidate_id,
            candidate.canonical_digest,
            task.task_id,
            task.canonical_digest,
            repetition,
            order_index,
            cache_identity,
            node_ref,
            output_key,
        )

    @property
    def value(self) -> str:
        return (
            f"evaluation-cell://{self.project_ref.value}/{self.suite_digest}/"
            f"{self.candidate_id}/{self.task_digest}/{self.repetition}"
        )

    def payload(self) -> dict[str, object]:
        return {
            "cache_identity": self.cache_identity,
            "candidate_digest": self.candidate_digest,
            "candidate_id": self.candidate_id,
            "node_ref": self.node_ref.value,
            "order_index": self.order_index,
            "output_key": self.output_key,
            "project_ref": self.project_ref.value,
            "repetition": self.repetition,
            "suite_digest": self.suite_digest,
            "task_digest": self.task_digest,
            "task_id": self.task_id,
        }


@dataclass(frozen=True)
class MatrixManifest:
    """Immutable Cartesian matrix identity over an existing Graph."""

    suite: ModelEvaluationSuite
    run_ref: RunRef
    graph_ref: GraphRef
    graph_record_sha256: str
    cells: tuple[EvaluationCellCoordinate, ...]
    aggregate_node_ref: NodeRef
    created_at: str
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.suite, ModelEvaluationSuite)
            or not isinstance(self.run_ref, RunRef)
            or not isinstance(self.graph_ref, GraphRef)
            or not isinstance(self.aggregate_node_ref, NodeRef)
        ):
            raise MatrixContractError("matrix exact identities are required")
        project = self.suite.project_ref
        if (
            self.run_ref.project_ref != project
            or self.graph_ref.project_ref != project
            or self.aggregate_node_ref.project_ref != project
            or self.aggregate_node_ref.graph_ref != self.graph_ref
        ):
            raise MatrixContractError("matrix crossed Project or Graph scope")
        _require_sha(self.graph_record_sha256, "Graph record digest")
        _timestamp(self.created_at)
        cells = tuple(self.cells)
        if not cells or any(
            item.project_ref != project
            or item.node_ref.graph_ref != self.graph_ref
            or item.suite_digest != self.suite.canonical_digest
            for item in cells
        ):
            raise MatrixContractError("matrix cells crossed exact suite or Graph scope")
        if self.aggregate_node_ref in {item.node_ref for item in cells}:
            raise MatrixContractError("aggregate Node cannot also be a cell")
        if len({item.node_ref for item in cells}) != len(cells):
            raise MatrixContractError("matrix repeats a Node")
        if len({item.canonical_digest for item in cells}) != len(cells):
            raise MatrixContractError("matrix repeats a coordinate")
        if {item.order_index for item in cells} != set(range(len(cells))):
            raise MatrixContractError("matrix order is not one exact permutation")
        expected = {
            (candidate.candidate_id, candidate.canonical_digest, task.task_id, task.canonical_digest, repetition)
            for candidate in self.suite.candidates
            for task in self.suite.task_set.tasks
            for repetition in range(1, self.suite.repetitions + 1)
        }
        observed = {
            (item.candidate_id, item.candidate_digest, item.task_id, item.task_digest, item.repetition)
            for item in cells
        }
        if observed != expected:
            raise MatrixContractError("matrix does not exactly cover the declared suite")
        for item in cells:
            expected_cache = _digest(
                {
                    "cache_policy": self.suite.cache_policy_ref,
                    "candidate": item.candidate_digest,
                    "repetition": item.repetition,
                    "suite": self.suite.canonical_digest,
                    "task": item.task_digest,
                }
            )
            if item.cache_identity != expected_cache:
                raise MatrixContractError("cell cache identity differs from exact suite policy")
        object.__setattr__(self, "cells", tuple(sorted(cells, key=lambda item: item.order_index)))
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.suite.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "aggregate_node_ref": self.aggregate_node_ref.value,
            "cache_policy_ref": self.suite.cache_policy_ref,
            "cells": [item.payload() for item in self.cells],
            "created_at": self.created_at,
            "graph_record_sha256": self.graph_record_sha256,
            "graph_ref": self.graph_ref.value,
            "order_policy_ref": self.suite.order_policy_ref,
            "project_ref": self.project_ref.value,
            "run_ref": _run_value(self.run_ref),
            "suite_digest": self.suite.canonical_digest,
            "task_set_digest": self.suite.task_set.canonical_digest,
        }


@dataclass(frozen=True)
class ArtifactEvidence:
    """Exact Artifact revision binding one underlying evidence record."""

    node_key: str
    artifact_ref: ArtifactRef
    artifact_record_sha256: str
    content_ref: ContentRef
    role: str
    subject_ref: str
    subject_record_sha256: str

    def __post_init__(self) -> None:
        _require_key(self.node_key, "Node evidence key")
        if not isinstance(self.artifact_ref, ArtifactRef) or not isinstance(self.content_ref, ContentRef):
            raise MatrixContractError("Artifact evidence exact refs are required")
        _require_sha(self.artifact_record_sha256, "Artifact record digest")
        _require_key(self.role, "Artifact role")
        _require_ref(self.subject_ref, "evidence subject")
        _require_sha(self.subject_record_sha256, "evidence subject digest")


@dataclass(frozen=True)
class CellExecutionProduct:
    """Evidence returned by the supplied cell executor before Node finalization."""

    evaluation_run: ModelEvaluationRun
    output_key: str
    evidence_artifacts: tuple[ArtifactEvidence, ...]
    acceptance_criteria: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation_run, ModelEvaluationRun):
            raise MatrixContractError("cell callback must return ModelEvaluationRun")
        _require_key(self.output_key, "cell output key")
        evidence = tuple(self.evidence_artifacts)
        if not all(isinstance(item, ArtifactEvidence) for item in evidence):
            raise MatrixContractError("cell evidence artifacts are malformed")
        if len({item.node_key for item in evidence}) != len(evidence):
            raise MatrixContractError("cell repeats a Node evidence key")
        object.__setattr__(self, "evidence_artifacts", tuple(sorted(evidence, key=lambda item: item.node_key)))
        criteria = tuple(self.acceptance_criteria)
        if len(set(criteria)) != len(criteria) or not all(isinstance(item, str) and item for item in criteria):
            raise MatrixContractError("cell acceptance criteria are malformed")
        object.__setattr__(self, "acceptance_criteria", criteria)


@dataclass(frozen=True)
class CompletedCellEvidence:
    coordinate: EvaluationCellCoordinate
    evaluation_run: ModelEvaluationRun
    result_artifact: ArtifactEvidence
    evidence_artifacts: tuple[ArtifactEvidence, ...]
    node_attempt_id: str
    node_attempt_fence: int


@dataclass(frozen=True)
class MatrixBatchResult:
    completed: tuple[CompletedCellEvidence, ...]
    skipped: tuple[CompletedCellEvidence, ...]
    failed: tuple[EvaluationCellCoordinate, ...]
    pending: tuple[EvaluationCellCoordinate, ...]
    checkpoint: RunCheckpoint
    cancelled: bool


@dataclass(frozen=True)
class MatrixRecovery:
    resume_result: ResumeResult
    reusable_cells: tuple[EvaluationCellCoordinate, ...]
    invalidated_cells: tuple[EvaluationCellCoordinate, ...]


@dataclass(frozen=True)
class ProjectKnowledgeCandidatePayload:
    """Arguments for ProjectKnowledgeService.record_candidate, never placement."""

    project_ref: ProjectRef
    idempotency_key: str
    origin_type: str
    knowledge_type: str
    content_ref: ContentRef
    applicability: Mapping[str, str]
    source_refs: tuple[ArtifactRef, ...]
    evidence_refs: tuple[ArtifactRef, ...]

    def __post_init__(self) -> None:
        _require_key(self.idempotency_key, "knowledge candidate idempotency key")
        _require_key(self.origin_type, "knowledge candidate origin")
        _require_key(self.knowledge_type, "knowledge candidate type")
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.content_ref, ContentRef):
            raise MatrixContractError("knowledge candidate Project/content is malformed")
        applicability = dict(self.applicability)
        if not applicability or len(applicability) > 32:
            raise MatrixContractError("knowledge candidate applicability is malformed")
        if any(not isinstance(key, str) or not isinstance(value, str) or not value for key, value in applicability.items()):
            raise MatrixContractError("knowledge candidate applicability is malformed")
        sources = tuple(self.source_refs)
        evidence = tuple(self.evidence_refs)
        if not sources or any(item.project_ref != self.project_ref for item in sources + evidence):
            raise MatrixContractError("knowledge candidate evidence crossed Project scope")
        object.__setattr__(self, "applicability", MappingProxyType(dict(sorted(applicability.items()))))
        object.__setattr__(self, "source_refs", tuple(sorted(set(sources))))
        object.__setattr__(self, "evidence_refs", tuple(sorted(set(evidence))))

    def as_record_candidate_kwargs(self) -> dict[str, object]:
        return {
            "project_ref": self.project_ref,
            "idempotency_key": self.idempotency_key,
            "origin_type": self.origin_type,
            "knowledge_type": self.knowledge_type,
            "statement": None,
            "content_ref": self.content_ref,
            "applicability": dict(self.applicability),
            "source_refs": self.source_refs,
            "evidence_refs": self.evidence_refs,
        }


CellCallback = Callable[[EvaluationCellCoordinate, ScheduledDispatch], CellExecutionProduct]
CompletedEvidenceLoader = Callable[[EvaluationCellCoordinate], CompletedCellEvidence | None]
CancellationProbe = Callable[[], bool]


class ModelEvaluationMatrixRuntime:
    """Coordinator over accepted Graph, execution, Artifact, and checkpoint authority."""

    def __init__(
        self,
        access: ProjectAccess,
        graph_service: GraphService,
        executions: NodeExecutionService,
        checkpoints: CheckpointService,
        artifacts: ArtifactService,
        object_storage: ObjectStorageBackend,
    ) -> None:
        if not isinstance(access, ProjectAccess):
            raise TypeError("ProjectAccess is required")
        self.access = access
        self.graphs = graph_service
        self.executions = executions
        self.checkpoints = checkpoints
        self.artifacts = artifacts
        self.object_storage = object_storage

    def _live_graph(self, manifest: MatrixManifest) -> Graph:
        if manifest.project_ref != self.access.project_ref:
            raise MatrixAuthorityError("matrix crossed ProjectAccess scope")
        graph = self.graphs.get_graph(self.access, manifest.graph_ref)
        if graph.run_ref != manifest.run_ref or graph.record_sha256 != manifest.graph_record_sha256:
            raise MatrixAuthorityError("matrix Graph or Run identity changed")
        nodes = {item.node_ref for item in graph.nodes}
        expected = {item.node_ref for item in manifest.cells} | {manifest.aggregate_node_ref}
        if not expected <= nodes:
            raise MatrixAuthorityError("matrix Node is absent from exact Graph")
        return graph

    @staticmethod
    def _node(graph: Graph, node_ref: NodeRef) -> Node:
        node = next((item for item in graph.nodes if item.node_ref == node_ref), None)
        if node is None:
            raise MatrixAuthorityError("matrix Node is absent from exact Graph")
        return node

    def publish_manifest(
        self,
        manifest: MatrixManifest,
        *,
        authority_attempt: ExecutionAttempt,
    ) -> Artifact:
        self._live_graph(manifest)
        data = _canonical(manifest.payload())
        content = self.object_storage.put(
            data,
            media_type="application/vnd.minitz.model-evaluation-matrix+json",
            expected_digest=hashlib.sha256(data).hexdigest(),
            expected_size=len(data),
        )
        source_contents = tuple(
            dict.fromkeys(
                (
                    manifest.suite.workload_profile.content_ref,
                    manifest.suite.task_set.content_ref,
                    *(item.content_ref for item in manifest.suite.task_set.tasks),
                )
            )
        )
        return self.artifacts.publish_from_run(
            self.access,
            producer_attempt=authority_attempt,
            expected_task_ref=authority_attempt.task_ref,
            expected_task_digest=authority_attempt.task_digest,
            role="model.evaluation.matrix-manifest",
            content_ref=content,
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=source_contents,
            derivation_type="model.evaluation.matrix-compile",
            metadata={},
        )

    def _verify_artifact(self, binding: ArtifactEvidence, run_ref: RunRef) -> Artifact:
        if binding.artifact_ref.project_ref != self.access.project_ref:
            raise MatrixEvidenceError("evidence Artifact crossed Project scope")
        artifact = self.artifacts.get_artifact(self.access, binding.artifact_ref)
        if (
            artifact.record_sha256 != binding.artifact_record_sha256
            or artifact.content_ref != binding.content_ref
            or artifact.role != binding.role
            or artifact.producer_run_ref != run_ref
            or artifact.content_ref is None
        ):
            raise MatrixEvidenceError("evidence Artifact revision or provenance differs")
        if not self.object_storage.verify(binding.content_ref):
            raise MatrixEvidenceError("evidence Artifact content failed verification")
        return artifact

    @staticmethod
    def _expected_subjects(evaluation_run: ModelEvaluationRun) -> dict[str, str]:
        expected: dict[str, str] = {}
        for model_call in evaluation_run.model_calls:
            if model_call.status not in _TERMINAL_CALLS:
                raise MatrixEvidenceError("ModelCall is not terminal")
            expected[model_call.call_ref.value] = model_call.record_sha256
        for tool_call in evaluation_run.tool_calls:
            if tool_call.status not in _TERMINAL_CALLS:
                raise MatrixEvidenceError("ToolCall is not terminal")
            expected[tool_call.call_ref.value] = tool_call.record_sha256
        for validation_result in evaluation_run.validation_results:
            if validation_result.evidence_state.value != "CURRENT":
                raise MatrixEvidenceError("historical ValidationResult cannot complete a current cell")
            expected[validation_result.result_ref.value] = validation_result.record_sha256
        for evaluation_result in evaluation_run.evaluation_results:
            expected[evaluation_result.evaluation_ref.value] = evaluation_result.record_sha256
        if evaluation_run.context_receipt is not None:
            expected[evaluation_run.context_receipt.receipt_ref.value] = evaluation_run.context_receipt.record_sha256
        for snapshot in evaluation_run.resource_snapshots:
            expected[snapshot.snapshot_ref.value] = snapshot.record_sha256
        return expected

    def _validate_run_coordinate(
        self,
        manifest: MatrixManifest,
        coordinate: EvaluationCellCoordinate,
        evaluation_run: ModelEvaluationRun,
    ) -> None:
        if (
            evaluation_run.suite.canonical_digest != manifest.suite.canonical_digest
            or evaluation_run.run_ref != manifest.run_ref
            or evaluation_run.candidate_id != coordinate.candidate_id
            or evaluation_run.task.canonical_digest != coordinate.task_digest
            or evaluation_run.repetition != coordinate.repetition
        ):
            raise MatrixEvidenceError("ModelEvaluationRun differs from exact matrix coordinate")
        if evaluation_run.completed_at is None or evaluation_run.status not in {"completed", "succeeded"}:
            raise MatrixEvidenceError("cell does not carry completed ModelEvaluationRun evidence")
        if _timestamp(evaluation_run.completed_at) < _timestamp(evaluation_run.started_at):
            raise MatrixEvidenceError("cell completion precedes start")

    def _validate_underlying_evidence(
        self,
        evaluation_run: ModelEvaluationRun,
        bindings: Sequence[ArtifactEvidence],
    ) -> None:
        expected = self._expected_subjects(evaluation_run)
        observed = {item.subject_ref: item.subject_record_sha256 for item in bindings}
        if observed != expected or len(observed) != len(tuple(bindings)):
            raise MatrixEvidenceError("cell evidence does not exactly bind every underlying record")
        for item in bindings:
            self._verify_artifact(item, evaluation_run.run_ref)

    def _validate_completed(
        self,
        manifest: MatrixManifest,
        coordinate: EvaluationCellCoordinate,
        completed: CompletedCellEvidence,
        state: NodeExecution,
        node: Node,
    ) -> None:
        if completed.coordinate.canonical_digest != coordinate.canonical_digest:
            raise MatrixEvidenceError("completed evidence belongs to another coordinate")
        self._validate_run_coordinate(manifest, coordinate, completed.evaluation_run)
        if (
            state.status != "SUCCEEDED"
            or state.node_ref != coordinate.node_ref
            or state.run_ref != manifest.run_ref
            or state.current_attempt_id != completed.node_attempt_id
            or state.current_fence != completed.node_attempt_fence
        ):
            raise MatrixAuthorityError("completed cell Node attempt or fence is not current")
        result = completed.result_artifact
        if (
            result.node_key != coordinate.output_key
            or result.subject_ref != coordinate.value
            or result.subject_record_sha256 != completed.evaluation_run.canonical_digest
        ):
            raise MatrixEvidenceError("cell result Artifact does not bind the exact run")
        self._verify_artifact(result, manifest.run_ref)
        if dict(state.outputs) != {coordinate.output_key: result.artifact_ref.value}:
            raise MatrixEvidenceError("current Node output differs from cell result Artifact")
        expected_node_evidence = {item.node_key: item.artifact_ref.value for item in completed.evidence_artifacts}
        if dict(state.evidence) != expected_node_evidence:
            raise MatrixEvidenceError("current Node evidence differs from exact cell evidence")
        if set(node.output_contract) != {coordinate.output_key}:
            raise MatrixContractError("cell Node must have one exact result output")
        if set(node.evidence_requirements) != set(expected_node_evidence):
            raise MatrixEvidenceError("cell evidence differs from Node evidence contract")
        self._validate_underlying_evidence(completed.evaluation_run, completed.evidence_artifacts)

    @staticmethod
    def _validate_dispatch(
        manifest: MatrixManifest,
        coordinate: EvaluationCellCoordinate,
        dispatch: ScheduledDispatch,
        state: NodeExecution,
    ) -> None:
        allocation = dispatch.allocation
        attempt = dispatch.node_attempt
        if (
            allocation.status != "DISPATCHED"
            or allocation.node_ref != coordinate.node_ref
            or allocation.run_ref != manifest.run_ref
            or attempt.node_ref != coordinate.node_ref
            or attempt.run_ref != manifest.run_ref
            or allocation.node_attempt_id != attempt.attempt_id
            or allocation.node_attempt_fence != attempt.fence
            or state.current_attempt_id != attempt.attempt_id
            or state.current_fence != attempt.fence
            or state.current_run_attempt_id != attempt.run_attempt_id
            or state.current_run_fence != attempt.run_fence
            or state.status not in {"LEASED", "RUNNING"}
        ):
            raise MatrixAuthorityError("ScheduledDispatch attempt, allocation, or fence is stale")

    def _publish_cell_result(
        self,
        manifest: MatrixManifest,
        coordinate: EvaluationCellCoordinate,
        product: CellExecutionProduct,
        manifest_artifact: Artifact,
        authority_attempt: ExecutionAttempt,
    ) -> Artifact:
        data = _canonical(product.evaluation_run.payload())
        content = self.object_storage.put(
            data,
            media_type="application/vnd.minitz.model-evaluation-cell+json",
            expected_digest=hashlib.sha256(data).hexdigest(),
            expected_size=len(data),
        )
        sources = tuple(
            dict.fromkeys(
                (
                    manifest_artifact.artifact_ref,
                    *(item.artifact_ref for item in product.evidence_artifacts),
                )
            )
        )
        return self.artifacts.publish_from_run(
            self.access,
            producer_attempt=authority_attempt,
            expected_task_ref=authority_attempt.task_ref,
            expected_task_digest=authority_attempt.task_digest,
            role="model.evaluation.cell-result",
            content_ref=content,
            source_refs=(),
            source_artifact_refs=sources,
            source_content_refs=(product.evaluation_run.task.content_ref,),
            derivation_type="model.evaluation.cell-execute",
            metadata={},
        )

    def execute_batch(
        self,
        manifest: MatrixManifest,
        *,
        manifest_artifact: Artifact,
        authority_attempt: ExecutionAttempt,
        dispatches: Mapping[NodeRef, ScheduledDispatch],
        cell_callback: CellCallback,
        completed_evidence_loader: CompletedEvidenceLoader,
        batch_idempotency_key: str,
        cancellation_probe: CancellationProbe | None = None,
    ) -> MatrixBatchResult:
        _require_key(batch_idempotency_key, "batch idempotency key")
        graph = self._live_graph(manifest)
        if (
            manifest_artifact.project_ref != manifest.project_ref
            or manifest_artifact.role != "model.evaluation.matrix-manifest"
            or manifest_artifact.producer_run_ref != manifest.run_ref
            or manifest_artifact.content_ref is None
        ):
            raise MatrixEvidenceError("matrix manifest Artifact is not exact Run evidence")
        self.object_storage.verify(manifest_artifact.content_ref)
        completed: list[CompletedCellEvidence] = []
        skipped: list[CompletedCellEvidence] = []
        failed: list[EvaluationCellCoordinate] = []
        pending: list[EvaluationCellCoordinate] = []
        cancelled = False
        for coordinate in manifest.cells:
            node = self._node(graph, coordinate.node_ref)
            state = self.executions.get_node_execution(self.access, coordinate.node_ref)
            if state.status == "SUCCEEDED":
                prior = completed_evidence_loader(coordinate)
                if prior is None:
                    raise MatrixEvidenceError("SUCCEEDED cell lost its durable evidence loader record")
                self._validate_completed(manifest, coordinate, prior, state, node)
                skipped.append(prior)
                continue
            if cancellation_probe is not None and cancellation_probe():
                cancelled = True
                pending.extend(item for item in manifest.cells if item.order_index >= coordinate.order_index)
                break
            dispatch = dispatches.get(coordinate.node_ref)
            if dispatch is None:
                pending.append(coordinate)
                continue
            self._validate_dispatch(manifest, coordinate, dispatch, state)
            if state.status == "LEASED":
                state = self.executions.start_node(
                    self.access,
                    dispatch.node_attempt,
                    idempotency_key=f"{batch_idempotency_key}.start.{coordinate.order_index}",
                )
            if state.status != "RUNNING":
                raise MatrixAuthorityError("cell callback requires current RUNNING Node")
            try:
                product = cell_callback(coordinate, dispatch)
            except CellInfrastructureFailure as exc:
                self.executions.fail_node(
                    self.access,
                    dispatch.node_attempt,
                    category="MODEL_EVALUATION.INFRASTRUCTURE",
                    reason=exc.reason,
                    evidence_refs=exc.evidence_refs,
                    retry_possible=exc.retry_possible,
                    idempotency_key=f"{batch_idempotency_key}.fail.{coordinate.order_index}",
                )
                failed.append(coordinate)
                continue
            except Exception as exc:
                self.executions.fail_node(
                    self.access,
                    dispatch.node_attempt,
                    category="MODEL_EVALUATION.INFRASTRUCTURE",
                    reason=type(exc).__name__,
                    evidence_refs=(),
                    retry_possible=True,
                    idempotency_key=f"{batch_idempotency_key}.fail.{coordinate.order_index}",
                )
                failed.append(coordinate)
                continue
            if product.output_key != coordinate.output_key:
                raise MatrixContractError("callback output differs from matrix coordinate")
            self._validate_run_coordinate(manifest, coordinate, product.evaluation_run)
            self._validate_underlying_evidence(product.evaluation_run, product.evidence_artifacts)
            if set(node.output_contract) != {coordinate.output_key}:
                raise MatrixContractError("cell Node must have one exact result output")
            evidence_map = {item.node_key: item.artifact_ref for item in product.evidence_artifacts}
            if set(node.evidence_requirements) != set(evidence_map):
                raise MatrixEvidenceError("callback evidence differs from Node evidence contract")
            result_artifact = self._publish_cell_result(
                manifest,
                coordinate,
                product,
                manifest_artifact,
                authority_attempt,
            )
            if result_artifact.content_ref is None:
                raise MatrixEvidenceError("cell result Artifact has no content")
            final_state = self.executions.finalize_node(
                self.access,
                dispatch.node_attempt,
                outputs={coordinate.output_key: result_artifact.artifact_ref},
                evidence=evidence_map,
                acceptance_criteria=product.acceptance_criteria,
                idempotency_key=f"{batch_idempotency_key}.complete.{coordinate.order_index}",
            )
            result_binding = ArtifactEvidence(
                coordinate.output_key,
                result_artifact.artifact_ref,
                result_artifact.record_sha256,
                result_artifact.content_ref,
                result_artifact.role,
                coordinate.value,
                product.evaluation_run.canonical_digest,
            )
            record = CompletedCellEvidence(
                coordinate,
                product.evaluation_run,
                result_binding,
                product.evidence_artifacts,
                dispatch.node_attempt.attempt_id,
                dispatch.node_attempt.fence,
            )
            self._validate_completed(manifest, coordinate, record, final_state, node)
            completed.append(record)
        continuation_refs = tuple(
            dict.fromkeys(
                (
                    manifest_artifact.artifact_ref.value,
                    *(item.result_artifact.artifact_ref.value for item in (*skipped, *completed)),
                )
            )
        )
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            manifest.run_ref,
            authority_attempt=authority_attempt,
            idempotency_key=f"{batch_idempotency_key}.checkpoint",
            continuation_refs=continuation_refs,
        )
        return MatrixBatchResult(
            tuple(completed),
            tuple(skipped),
            tuple(failed),
            tuple(pending),
            checkpoint,
            cancelled,
        )

    def resume_matrix(
        self,
        manifest: MatrixManifest,
        *,
        checkpoint_ref: RunCheckpointRef,
        authority_attempt: ExecutionAttempt,
        idempotency_key: str,
    ) -> MatrixRecovery:
        _require_key(idempotency_key, "resume idempotency key")
        self._live_graph(manifest)
        resumed = self.checkpoints.resume_run(
            self.access,
            manifest.run_ref,
            checkpoint_ref=checkpoint_ref,
            authority_attempt=authority_attempt,
            idempotency_key=idempotency_key,
        )
        if resumed.reconciliation.current_graph_ref != manifest.graph_ref:
            raise MatrixRecoveryError("checkpoint reconciled to another Graph revision")
        by_node = {item.node_ref: item for item in manifest.cells}
        reusable: list[EvaluationCellCoordinate] = []
        invalidated: list[EvaluationCellCoordinate] = []
        for decision in resumed.reconciliation.decisions:
            coordinate = by_node.get(decision.node_ref)
            if coordinate is None:
                continue
            if decision.action in {"REUSE_CURRENT", "REUSE_CHECKPOINT"}:
                reusable.append(coordinate)
            elif decision.action == "INVALIDATE":
                invalidated.append(coordinate)
        return MatrixRecovery(
            resumed,
            tuple(sorted(reusable, key=lambda item: item.order_index)),
            tuple(sorted(invalidated, key=lambda item: item.order_index)),
        )

    def validate_completed_cells(
        self,
        manifest: MatrixManifest,
        records: Sequence[CompletedCellEvidence],
    ) -> tuple[CompletedCellEvidence, ...]:
        graph = self._live_graph(manifest)
        by_digest = {item.coordinate.canonical_digest: item for item in records}
        if len(by_digest) != len(tuple(records)):
            raise MatrixEvidenceError("completed cell evidence is duplicated")
        validated: list[CompletedCellEvidence] = []
        for coordinate in manifest.cells:
            record = by_digest.get(coordinate.canonical_digest)
            if record is None:
                continue
            state = self.executions.get_node_execution(self.access, coordinate.node_ref)
            self._validate_completed(
                manifest,
                coordinate,
                record,
                state,
                self._node(graph, coordinate.node_ref),
            )
            validated.append(record)
        return tuple(validated)

    @staticmethod
    def _success(value: str) -> float:
        return 1.0 if value.casefold() in _SUCCESS else 0.0

    @classmethod
    def _run_metrics(cls, run: ModelEvaluationRun) -> tuple[dict[str, float | None], dict[str, str]]:
        values: dict[str, float | None] = {
            "reliability.infrastructure": cls._success(run.infrastructure_outcome),
            "reliability.semantic": cls._success(run.semantic_outcome),
            "reliability.transport": cls._success(run.transport_outcome),
            "tools.calls": float(len(run.tool_calls)),
            "usage.tokens": None if run.token_count is None else float(run.token_count),
            "cost.amount": None if run.cost is None else float(run.cost),
        }
        units: dict[str, str] = {
            "reliability.infrastructure": "ratio",
            "reliability.semantic": "ratio",
            "reliability.transport": "ratio",
            "tools.calls": "count",
            "usage.tokens": "tokens",
            "cost.amount": "currency",
        }
        for validation_result in run.validation_results:
            for metric in validation_result.metrics:
                key = f"quality.{metric.name}"
                values.setdefault(key, metric.value)
                units.setdefault(key, metric.unit)
        for evaluation_result in run.evaluation_results:
            for metric in evaluation_result.metrics:
                key = f"quality.{metric.name}"
                values.setdefault(key, metric.value)
                units.setdefault(key, metric.unit)
            for composite in evaluation_result.composites:
                key = f"quality.{composite.name}"
                values.setdefault(key, composite.score)
                units.setdefault(key, "score")
        for resource_key, resource_value in run.resource_metrics.items():
            resource_metric = (
                resource_key
                if resource_key.startswith("latency.")
                else f"resource.{resource_key}"
            )
            values[resource_metric] = resource_value
            units[resource_metric] = (
                "seconds" if resource_metric.startswith("latency.") else "observed"
            )
        return values, units

    @staticmethod
    def _statistics(
        runs: Sequence[ModelEvaluationRun],
    ) -> tuple[DescriptiveStatistics, ...]:
        metric_maps: list[dict[str, float | None]] = []
        units: dict[str, str] = {}
        for run in runs:
            values, run_units = ModelEvaluationMatrixRuntime._run_metrics(run)
            metric_maps.append(values)
            units.update(run_units)
        names = sorted({name for values in metric_maps for name in values})
        result: list[DescriptiveStatistics] = []
        for name in names:
            observed = [values.get(name) for values in metric_maps]
            known = [float(value) for value in observed if value is not None]
            if known:
                mean: float | None = statistics.fmean(known)
                deviation: float | None = statistics.stdev(known) if len(known) > 1 else None
                minimum: float | None = min(known)
                maximum: float | None = max(known)
                count = len(known)
            else:
                mean = deviation = minimum = maximum = None
                count = len(runs)
            result.append(
                DescriptiveStatistics(
                    name,
                    count,
                    mean,
                    deviation,
                    minimum,
                    maximum,
                    units[name],
                )
            )
        return tuple(result)

    @classmethod
    def _quality_value(cls, run: ModelEvaluationRun) -> float:
        values, _ = cls._run_metrics(run)
        quality = [value for key, value in sorted(values.items()) if key.startswith("quality.") and value is not None]
        return cls._success(run.semantic_outcome) if not quality else float(quality[0])

    @classmethod
    def _comparisons(
        cls,
        suite: ModelEvaluationSuite,
        runs: Sequence[ModelEvaluationRun],
    ) -> tuple[PairwiseComparison, ...]:
        by_candidate: dict[str, dict[tuple[str, int], ModelEvaluationRun]] = {}
        for run in runs:
            by_candidate.setdefault(run.candidate_id, {})[(run.task.canonical_digest, run.repetition)] = run
        comparisons: list[PairwiseComparison] = []
        for left, right in itertools.combinations((item.candidate_id for item in suite.candidates), 2):
            left_runs = by_candidate.get(left, {})
            right_runs = by_candidate.get(right, {})
            keys = sorted(set(left_runs) & set(right_runs))
            wins = losses = ties = 0
            resource_confounder: str | None = None
            for key in keys:
                left_run = left_runs[key]
                right_run = right_runs[key]
                left_value = cls._quality_value(left_run)
                right_value = cls._quality_value(right_run)
                if math.isclose(left_value, right_value, rel_tol=1e-12, abs_tol=1e-12):
                    ties += 1
                elif left_value > right_value:
                    wins += 1
                else:
                    losses += 1
                left_resources = tuple(item.record_sha256 for item in left_run.resource_snapshots)
                right_resources = tuple(item.record_sha256 for item in right_run.resource_snapshots)
                if left_resources != right_resources or dict(left_run.resource_metrics) != dict(right_run.resource_metrics):
                    resource_confounder = (
                        left_run.resource_snapshots[0].snapshot_ref.value
                        if left_run.resource_snapshots
                        else right_run.resource_snapshots[0].snapshot_ref.value
                        if right_run.resource_snapshots
                        else suite.resource_policy_ref
                    )
            conclusion = "INSUFFICIENT_EVIDENCE" if len(keys) < 3 else "DESCRIPTIVE"
            comparisons.append(
                PairwiseComparison(
                    suite,
                    left,
                    right,
                    wins,
                    losses,
                    ties,
                    conclusion,
                    resource_confounder,
                )
            )
        return tuple(comparisons)

    def build_result(
        self,
        manifest: MatrixManifest,
        completed: Sequence[CompletedCellEvidence],
    ) -> ModelEvaluationResult:
        validated = self.validate_completed_cells(manifest, completed)
        runs = tuple(item.evaluation_run for item in validated)
        if not runs:
            raise MatrixEvidenceError("matrix has no verified completed cells")
        return ModelEvaluationResult(
            manifest.suite,
            runs,
            self._statistics(runs),
            self._comparisons(manifest.suite, runs),
        )

    def publish_result(
        self,
        manifest: MatrixManifest,
        result: ModelEvaluationResult,
        *,
        manifest_artifact: Artifact,
        completed: Sequence[CompletedCellEvidence],
        authority_attempt: ExecutionAttempt,
    ) -> Artifact:
        if result.suite_digest != manifest.suite.canonical_digest:
            raise MatrixEvidenceError("aggregate result differs from exact suite")
        validated = self.validate_completed_cells(manifest, completed)
        if {item.evaluation_run.canonical_digest for item in validated} != {
            item.canonical_digest for item in result.runs
        }:
            raise MatrixEvidenceError("aggregate result differs from verified cells")
        data = _canonical(result.payload())
        content = self.object_storage.put(
            data,
            media_type="application/vnd.minitz.model-evaluation-result+json",
            expected_digest=hashlib.sha256(data).hexdigest(),
            expected_size=len(data),
        )
        return self.artifacts.publish_from_run(
            self.access,
            producer_attempt=authority_attempt,
            expected_task_ref=authority_attempt.task_ref,
            expected_task_digest=authority_attempt.task_digest,
            role="model.evaluation.aggregate-result",
            content_ref=content,
            source_refs=(),
            source_artifact_refs=(
                manifest_artifact.artifact_ref,
                *(item.result_artifact.artifact_ref for item in validated),
            ),
            source_content_refs=(),
            derivation_type="model.evaluation.aggregate",
            metadata={},
        )

    @staticmethod
    def knowledge_candidate_payload(
        manifest: MatrixManifest,
        result_artifact: Artifact,
        *,
        manifest_artifact: Artifact,
        completed: Sequence[CompletedCellEvidence],
    ) -> ProjectKnowledgeCandidatePayload:
        if result_artifact.content_ref is None:
            raise MatrixEvidenceError("aggregate result Artifact has no content")
        evidence = (
            manifest_artifact.artifact_ref,
            *(item.result_artifact.artifact_ref for item in completed),
        )
        return ProjectKnowledgeCandidatePayload(
            manifest.project_ref,
            f"model-evaluation.{manifest.canonical_digest[:32]}",
            "model.evaluation",
            "model.evaluation.result",
            result_artifact.content_ref,
            {
                "evidence_class": manifest.suite.evidence_class.value,
                "suite_digest": manifest.suite.canonical_digest,
            },
            (result_artifact.artifact_ref,),
            tuple(dict.fromkeys(evidence)),
        )


__all__ = [
    "ArtifactEvidence",
    "CellExecutionProduct",
    "CellInfrastructureFailure",
    "CompletedCellEvidence",
    "EvaluationCellCoordinate",
    "MatrixAuthorityError",
    "MatrixBatchResult",
    "MatrixContractError",
    "MatrixEvidenceError",
    "MatrixManifest",
    "MatrixRecovery",
    "MatrixRecoveryError",
    "ModelEvaluationMatrixRuntime",
    "ProjectKnowledgeCandidatePayload",
]
