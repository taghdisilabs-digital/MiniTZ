"""Durable Graph/Scheduler coordination for execution-strategy matrices."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re

from .artifact import Artifact, ArtifactRef, ArtifactService, ContentRef
from .checkpoint import CheckpointService, ResumeResult, RunCheckpoint, RunCheckpointRef
from .execution import NodeExecution, NodeExecutionService
from .graph import Graph, GraphRef, GraphService, Node, NodeRef
from .model_evaluation import EvaluationTask, ModelCandidate
from .model_evaluation_runtime import ArtifactEvidence, ProjectKnowledgeCandidatePayload
from .object_store import ObjectStorageBackend
from .project import ProjectAccess, ProjectRef
from .run import ExecutionAttempt, RunRef
from .scheduler import ScheduledDispatch
from .strategy_evaluation import (
    ExecutionStrategy,
    StrategyEvaluationExperiment,
    StrategyEvaluationResult,
    StrategyEvaluationRun,
    build_strategy_evaluation_result,
)


_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class StrategyEvaluationRuntimeError(Exception):
    """Base strategy-matrix coordination failure."""


class StrategyMatrixContractError(StrategyEvaluationRuntimeError, ValueError):
    """A strategy matrix identity or callback product is malformed."""


class StrategyMatrixAuthorityError(StrategyEvaluationRuntimeError):
    """A strategy Graph, Node, dispatch, attempt, or fence is stale."""


class StrategyMatrixEvidenceError(StrategyEvaluationRuntimeError):
    """Claimed strategy-cell completion lacks exact durable evidence."""


class StrategyMatrixRecoveryError(StrategyEvaluationRuntimeError):
    """A checkpoint cannot reconcile to this exact strategy matrix."""


class StrategyCellInfrastructureFailure(StrategyEvaluationRuntimeError):
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
        raise StrategyMatrixContractError("strategy matrix evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require_key(value: object, label: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise StrategyMatrixContractError(f"{label} is malformed")
    return value


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise StrategyMatrixContractError(f"{label} must be a SHA-256 digest")
    return value


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise StrategyMatrixContractError("timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StrategyMatrixContractError("timestamp must be timezone-aware")
    return parsed


def _run_value(run_ref: RunRef) -> str:
    return f"run://{run_ref.project_ref.value}/{run_ref.run_id}"


@dataclass(frozen=True)
class StrategyCellCoordinate:
    project_ref: ProjectRef
    experiment_digest: str
    candidate_id: str
    model_digest: str
    strategy_id: str
    strategy_digest: str
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
            raise StrategyMatrixContractError("strategy cell Project/Node identities are required")
        if self.node_ref.project_ref != self.project_ref:
            raise StrategyMatrixContractError("strategy cell Node crossed Project scope")
        for value, label in (
            (self.experiment_digest, "experiment digest"),
            (self.model_digest, "model digest"),
            (self.strategy_digest, "strategy digest"),
            (self.task_digest, "task digest"),
            (self.cache_identity, "cache identity"),
        ):
            _require_sha(value, label)
        for value, label in (
            (self.candidate_id, "model identity"),
            (self.strategy_id, "strategy identity"),
            (self.task_id, "task identity"),
            (self.output_key, "output key"),
        ):
            _require_key(value, label)
        if not isinstance(self.repetition, int) or isinstance(self.repetition, bool) or self.repetition < 1:
            raise StrategyMatrixContractError("strategy cell repetition must be positive")
        if not isinstance(self.order_index, int) or isinstance(self.order_index, bool) or self.order_index < 0:
            raise StrategyMatrixContractError("strategy cell order must be non-negative")
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    @classmethod
    def bind(
        cls,
        experiment: StrategyEvaluationExperiment,
        model: ModelCandidate,
        strategy: ExecutionStrategy,
        task: EvaluationTask,
        repetition: int,
        order_index: int,
        node_ref: NodeRef,
        *,
        output_key: str = "result",
    ) -> StrategyCellCoordinate:
        cache_identity = _digest(
            {
                "cache_policy": experiment.cache_policy_ref,
                "experiment": experiment.canonical_digest,
                "model": model.canonical_digest,
                "repetition": repetition,
                "strategy": strategy.canonical_digest,
                "task": task.canonical_digest,
            }
        )
        return cls(
            experiment.project_ref,
            experiment.canonical_digest,
            model.candidate_id,
            model.canonical_digest,
            strategy.strategy_id,
            strategy.canonical_digest,
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
            f"strategy-evaluation-cell://{self.project_ref.value}/{self.experiment_digest}/"
            f"{self.candidate_id}/{self.strategy_digest}/{self.task_digest}/{self.repetition}"
        )

    def payload(self) -> dict[str, object]:
        return {
            "cache_identity": self.cache_identity,
            "experiment_digest": self.experiment_digest,
            "model_digest": self.model_digest,
            "model_id": self.candidate_id,
            "node_ref": self.node_ref.value,
            "order_index": self.order_index,
            "output_key": self.output_key,
            "project_ref": self.project_ref.value,
            "repetition": self.repetition,
            "strategy_digest": self.strategy_digest,
            "strategy_id": self.strategy_id,
            "task_digest": self.task_digest,
            "task_id": self.task_id,
        }


@dataclass(frozen=True)
class StrategyMatrixManifest:
    experiment: StrategyEvaluationExperiment
    run_ref: RunRef
    graph_ref: GraphRef
    graph_record_sha256: str
    cells: tuple[StrategyCellCoordinate, ...]
    aggregate_node_ref: NodeRef
    created_at: str
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.experiment, StrategyEvaluationExperiment)
            or not isinstance(self.run_ref, RunRef)
            or not isinstance(self.graph_ref, GraphRef)
            or not isinstance(self.aggregate_node_ref, NodeRef)
        ):
            raise StrategyMatrixContractError("strategy matrix exact identities are required")
        project = self.experiment.project_ref
        if (
            self.run_ref.project_ref != project
            or self.graph_ref.project_ref != project
            or self.aggregate_node_ref.project_ref != project
            or self.aggregate_node_ref.graph_ref != self.graph_ref
        ):
            raise StrategyMatrixContractError("strategy matrix crossed Project/Graph scope")
        _require_sha(self.graph_record_sha256, "Graph record digest")
        _timestamp(self.created_at)
        cells = tuple(self.cells)
        if not cells or any(
            item.project_ref != project
            or item.node_ref.graph_ref != self.graph_ref
            or item.experiment_digest != self.experiment.canonical_digest
            for item in cells
        ):
            raise StrategyMatrixContractError("strategy cells crossed exact experiment/Graph scope")
        if self.aggregate_node_ref in {item.node_ref for item in cells}:
            raise StrategyMatrixContractError("aggregate Node cannot be a strategy cell")
        if len({item.node_ref for item in cells}) != len(cells) or len({item.canonical_digest for item in cells}) != len(cells):
            raise StrategyMatrixContractError("strategy matrix repeats a Node or coordinate")
        if {item.order_index for item in cells} != set(range(len(cells))):
            raise StrategyMatrixContractError("strategy matrix order is not one exact permutation")
        expected = {
            (
                model.candidate_id,
                model.canonical_digest,
                strategy.strategy_id,
                strategy.canonical_digest,
                task.task_id,
                task.canonical_digest,
                repetition,
            )
            for model in self.experiment.models
            for strategy in self.experiment.strategies
            for task in self.experiment.task_set.tasks
            for repetition in range(1, self.experiment.repetitions + 1)
        }
        observed = {
            (
                item.candidate_id,
                item.model_digest,
                item.strategy_id,
                item.strategy_digest,
                item.task_id,
                item.task_digest,
                item.repetition,
            )
            for item in cells
        }
        if observed != expected:
            raise StrategyMatrixContractError("strategy matrix does not cover the declared experiment")
        for item in cells:
            expected_cache = _digest(
                {
                    "cache_policy": self.experiment.cache_policy_ref,
                    "experiment": self.experiment.canonical_digest,
                    "model": item.model_digest,
                    "repetition": item.repetition,
                    "strategy": item.strategy_digest,
                    "task": item.task_digest,
                }
            )
            if item.cache_identity != expected_cache:
                raise StrategyMatrixContractError("strategy cell cache identity differs from experiment")
        object.__setattr__(self, "cells", tuple(sorted(cells, key=lambda item: item.order_index)))
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.experiment.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "aggregate_node_ref": self.aggregate_node_ref.value,
            "cache_policy_ref": self.experiment.cache_policy_ref,
            "cells": [item.payload() for item in self.cells],
            "created_at": self.created_at,
            "experiment_digest": self.experiment.canonical_digest,
            "graph_record_sha256": self.graph_record_sha256,
            "graph_ref": self.graph_ref.value,
            "order_policy_ref": self.experiment.order_policy_ref,
            "project_ref": self.project_ref.value,
            "run_ref": _run_value(self.run_ref),
            "task_set_digest": self.experiment.task_set.canonical_digest,
        }


@dataclass(frozen=True)
class StrategyCellExecutionProduct:
    evaluation_run: StrategyEvaluationRun
    output_key: str
    evidence_artifacts: tuple[ArtifactEvidence, ...]
    acceptance_criteria: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation_run, StrategyEvaluationRun):
            raise StrategyMatrixContractError("strategy callback must return StrategyEvaluationRun")
        _require_key(self.output_key, "strategy cell output key")
        evidence = tuple(self.evidence_artifacts)
        if not all(isinstance(item, ArtifactEvidence) for item in evidence):
            raise StrategyMatrixContractError("strategy cell Artifact evidence is malformed")
        if len({item.node_key for item in evidence}) != len(evidence):
            raise StrategyMatrixContractError("strategy cell repeats a Node evidence key")
        criteria = tuple(self.acceptance_criteria)
        if len(set(criteria)) != len(criteria) or not all(isinstance(item, str) and item for item in criteria):
            raise StrategyMatrixContractError("strategy cell acceptance criteria are malformed")
        object.__setattr__(self, "evidence_artifacts", tuple(sorted(evidence, key=lambda item: item.node_key)))
        object.__setattr__(self, "acceptance_criteria", criteria)


@dataclass(frozen=True)
class StrategyCompletedCellEvidence:
    coordinate: StrategyCellCoordinate
    evaluation_run: StrategyEvaluationRun
    result_artifact: ArtifactEvidence
    evidence_artifacts: tuple[ArtifactEvidence, ...]
    node_attempt_id: str
    node_attempt_fence: int


@dataclass(frozen=True)
class StrategyMatrixBatchResult:
    completed: tuple[StrategyCompletedCellEvidence, ...]
    skipped: tuple[StrategyCompletedCellEvidence, ...]
    failed: tuple[StrategyCellCoordinate, ...]
    pending: tuple[StrategyCellCoordinate, ...]
    checkpoint: RunCheckpoint
    cancelled: bool


@dataclass(frozen=True)
class StrategyMatrixRecovery:
    resume_result: ResumeResult
    reusable_cells: tuple[StrategyCellCoordinate, ...]
    invalidated_cells: tuple[StrategyCellCoordinate, ...]


StrategyCellCallback = Callable[[StrategyCellCoordinate, ScheduledDispatch], StrategyCellExecutionProduct]
StrategyCompletedEvidenceLoader = Callable[[StrategyCellCoordinate], StrategyCompletedCellEvidence | None]
CancellationProbe = Callable[[], bool]


class StrategyEvaluationMatrixRuntime:
    """Coordinator over current Graph, execution, Artifact, and checkpoint authority."""

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

    def _live_graph(self, manifest: StrategyMatrixManifest) -> Graph:
        if manifest.project_ref != self.access.project_ref:
            raise StrategyMatrixAuthorityError("strategy matrix crossed ProjectAccess scope")
        graph = self.graphs.get_graph(self.access, manifest.graph_ref)
        if graph.run_ref != manifest.run_ref or graph.record_sha256 != manifest.graph_record_sha256:
            raise StrategyMatrixAuthorityError("strategy matrix Graph or Run identity changed")
        graph_nodes = {item.node_ref for item in graph.nodes}
        expected = {item.node_ref for item in manifest.cells} | {manifest.aggregate_node_ref}
        if not expected <= graph_nodes:
            raise StrategyMatrixAuthorityError("strategy matrix Node is absent from exact Graph")
        return graph

    @staticmethod
    def _node(graph: Graph, node_ref: NodeRef) -> Node:
        node = next((item for item in graph.nodes if item.node_ref == node_ref), None)
        if node is None:
            raise StrategyMatrixAuthorityError("strategy matrix Node is absent from exact Graph")
        return node

    def publish_manifest(
        self,
        manifest: StrategyMatrixManifest,
        *,
        authority_attempt: ExecutionAttempt,
    ) -> Artifact:
        self._live_graph(manifest)
        data = _canonical(manifest.payload())
        content = self.object_storage.put(
            data,
            media_type="application/vnd.minitz.strategy-evaluation-matrix+json",
            expected_digest=hashlib.sha256(data).hexdigest(),
            expected_size=len(data),
        )
        source_contents = tuple(
            dict.fromkeys(
                (
                    manifest.experiment.workload_profile.content_ref,
                    manifest.experiment.task_set.content_ref,
                    *(item.content_ref for item in manifest.experiment.task_set.tasks),
                    *(skill.content_ref for strategy in manifest.experiment.strategies for skill in strategy.skill_artifacts),
                    *(prompt.content_ref for strategy in manifest.experiment.strategies for prompt in strategy.prompt_artifacts),
                )
            )
        )
        return self.artifacts.publish_from_run(
            self.access,
            producer_attempt=authority_attempt,
            expected_task_ref=authority_attempt.task_ref,
            expected_task_digest=authority_attempt.task_digest,
            role="strategy.evaluation.matrix-manifest",
            content_ref=content,
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=source_contents,
            derivation_type="strategy.evaluation.matrix-compile",
            metadata={},
        )

    def _verify_artifact(self, binding: ArtifactEvidence, run_ref: RunRef) -> Artifact:
        if binding.artifact_ref.project_ref != self.access.project_ref:
            raise StrategyMatrixEvidenceError("strategy evidence Artifact crossed Project scope")
        artifact = self.artifacts.get_artifact(self.access, binding.artifact_ref)
        if (
            artifact.record_sha256 != binding.artifact_record_sha256
            or artifact.content_ref != binding.content_ref
            or artifact.role != binding.role
            or artifact.producer_run_ref != run_ref
            or artifact.content_ref is None
        ):
            raise StrategyMatrixEvidenceError("strategy evidence Artifact provenance differs")
        if not self.object_storage.verify(binding.content_ref):
            raise StrategyMatrixEvidenceError("strategy evidence Artifact content failed verification")
        return artifact

    @staticmethod
    def _validate_run_coordinate(
        manifest: StrategyMatrixManifest,
        coordinate: StrategyCellCoordinate,
        evaluation_run: StrategyEvaluationRun,
    ) -> None:
        model = next(item for item in manifest.experiment.models if item.candidate_id == coordinate.candidate_id)
        if (
            evaluation_run.experiment.canonical_digest != manifest.experiment.canonical_digest
            or evaluation_run.run_ref != manifest.run_ref
            or evaluation_run.candidate_id != coordinate.candidate_id
            or model.canonical_digest != coordinate.model_digest
            or evaluation_run.strategy_id != coordinate.strategy_id
            or evaluation_run.strategy_digest != coordinate.strategy_digest
            or evaluation_run.task.canonical_digest != coordinate.task_digest
            or evaluation_run.repetition != coordinate.repetition
        ):
            raise StrategyMatrixEvidenceError("StrategyEvaluationRun differs from exact matrix coordinate")
        if evaluation_run.completed_at is None or evaluation_run.status not in {"completed", "succeeded"}:
            raise StrategyMatrixEvidenceError("strategy cell lacks completed run evidence")
        if _timestamp(evaluation_run.completed_at) < _timestamp(evaluation_run.started_at):
            raise StrategyMatrixEvidenceError("strategy cell completion precedes start")

    def _validate_completed(
        self,
        manifest: StrategyMatrixManifest,
        coordinate: StrategyCellCoordinate,
        completed: StrategyCompletedCellEvidence,
        state: NodeExecution,
        node: Node,
    ) -> None:
        if completed.coordinate.canonical_digest != coordinate.canonical_digest:
            raise StrategyMatrixEvidenceError("completed strategy evidence belongs to another coordinate")
        self._validate_run_coordinate(manifest, coordinate, completed.evaluation_run)
        if (
            state.status != "SUCCEEDED"
            or state.node_ref != coordinate.node_ref
            or state.run_ref != manifest.run_ref
            or state.current_attempt_id != completed.node_attempt_id
            or state.current_fence != completed.node_attempt_fence
        ):
            raise StrategyMatrixAuthorityError("completed strategy Node attempt/fence is not current")
        result = completed.result_artifact
        if (
            result.node_key != coordinate.output_key
            or result.subject_ref != coordinate.value
            or result.subject_record_sha256 != completed.evaluation_run.canonical_digest
        ):
            raise StrategyMatrixEvidenceError("strategy cell result Artifact does not bind exact run")
        self._verify_artifact(result, manifest.run_ref)
        if dict(state.outputs) != {coordinate.output_key: result.artifact_ref.value}:
            raise StrategyMatrixEvidenceError("current strategy Node output differs from result Artifact")
        expected_evidence = {item.node_key: item.artifact_ref.value for item in completed.evidence_artifacts}
        if dict(state.evidence) != expected_evidence or set(node.evidence_requirements) != set(expected_evidence):
            raise StrategyMatrixEvidenceError("strategy Node evidence differs from exact cell evidence")
        if set(node.output_contract) != {coordinate.output_key}:
            raise StrategyMatrixContractError("strategy cell Node requires one exact result output")
        for item in completed.evidence_artifacts:
            self._verify_artifact(item, manifest.run_ref)

    @staticmethod
    def _validate_dispatch(
        manifest: StrategyMatrixManifest,
        coordinate: StrategyCellCoordinate,
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
            raise StrategyMatrixAuthorityError("strategy ScheduledDispatch allocation/attempt/fence is stale")

    def _publish_cell_result(
        self,
        manifest: StrategyMatrixManifest,
        coordinate: StrategyCellCoordinate,
        product: StrategyCellExecutionProduct,
        manifest_artifact: Artifact,
        authority_attempt: ExecutionAttempt,
    ) -> Artifact:
        data = _canonical(product.evaluation_run.payload())
        content = self.object_storage.put(
            data,
            media_type="application/vnd.minitz.strategy-evaluation-cell+json",
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
            role="strategy.evaluation.cell-result",
            content_ref=content,
            source_refs=(),
            source_artifact_refs=sources,
            source_content_refs=(product.evaluation_run.task.content_ref,),
            derivation_type="strategy.evaluation.cell-execute",
            metadata={},
        )

    def execute_batch(
        self,
        manifest: StrategyMatrixManifest,
        *,
        manifest_artifact: Artifact,
        authority_attempt: ExecutionAttempt,
        dispatches: Mapping[NodeRef, ScheduledDispatch],
        cell_callback: StrategyCellCallback,
        completed_evidence_loader: StrategyCompletedEvidenceLoader,
        batch_idempotency_key: str,
        cancellation_probe: CancellationProbe | None = None,
    ) -> StrategyMatrixBatchResult:
        _require_key(batch_idempotency_key, "strategy batch idempotency key")
        graph = self._live_graph(manifest)
        if (
            manifest_artifact.project_ref != manifest.project_ref
            or manifest_artifact.role != "strategy.evaluation.matrix-manifest"
            or manifest_artifact.producer_run_ref != manifest.run_ref
            or manifest_artifact.content_ref is None
        ):
            raise StrategyMatrixEvidenceError("strategy manifest Artifact is not exact Run evidence")
        self.object_storage.verify(manifest_artifact.content_ref)
        completed: list[StrategyCompletedCellEvidence] = []
        skipped: list[StrategyCompletedCellEvidence] = []
        failed: list[StrategyCellCoordinate] = []
        pending: list[StrategyCellCoordinate] = []
        cancelled = False
        for coordinate in manifest.cells:
            node = self._node(graph, coordinate.node_ref)
            state = self.executions.get_node_execution(self.access, coordinate.node_ref)
            if state.status == "SUCCEEDED":
                prior = completed_evidence_loader(coordinate)
                if prior is None:
                    raise StrategyMatrixEvidenceError("SUCCEEDED strategy cell lost durable evidence")
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
                raise StrategyMatrixAuthorityError("strategy callback requires current RUNNING Node")
            try:
                product = cell_callback(coordinate, dispatch)
            except StrategyCellInfrastructureFailure as exc:
                self.executions.fail_node(
                    self.access,
                    dispatch.node_attempt,
                    category="STRATEGY_EVALUATION.INFRASTRUCTURE",
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
                    category="STRATEGY_EVALUATION.INFRASTRUCTURE",
                    reason=type(exc).__name__,
                    evidence_refs=(),
                    retry_possible=True,
                    idempotency_key=f"{batch_idempotency_key}.fail.{coordinate.order_index}",
                )
                failed.append(coordinate)
                continue
            if product.output_key != coordinate.output_key:
                raise StrategyMatrixContractError("strategy callback output differs from coordinate")
            self._validate_run_coordinate(manifest, coordinate, product.evaluation_run)
            if set(node.output_contract) != {coordinate.output_key}:
                raise StrategyMatrixContractError("strategy cell Node requires one exact result output")
            evidence_map = {item.node_key: item.artifact_ref for item in product.evidence_artifacts}
            if set(node.evidence_requirements) != set(evidence_map):
                raise StrategyMatrixEvidenceError("strategy callback evidence differs from Node contract")
            for item in product.evidence_artifacts:
                self._verify_artifact(item, manifest.run_ref)
            result_artifact = self._publish_cell_result(
                manifest,
                coordinate,
                product,
                manifest_artifact,
                authority_attempt,
            )
            if result_artifact.content_ref is None:
                raise StrategyMatrixEvidenceError("strategy cell result Artifact has no content")
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
            record = StrategyCompletedCellEvidence(
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
        return StrategyMatrixBatchResult(
            tuple(completed),
            tuple(skipped),
            tuple(failed),
            tuple(pending),
            checkpoint,
            cancelled,
        )

    def resume_matrix(
        self,
        manifest: StrategyMatrixManifest,
        *,
        checkpoint_ref: RunCheckpointRef,
        authority_attempt: ExecutionAttempt,
        idempotency_key: str,
    ) -> StrategyMatrixRecovery:
        _require_key(idempotency_key, "strategy resume idempotency key")
        self._live_graph(manifest)
        resumed = self.checkpoints.resume_run(
            self.access,
            manifest.run_ref,
            checkpoint_ref=checkpoint_ref,
            authority_attempt=authority_attempt,
            idempotency_key=idempotency_key,
        )
        if resumed.reconciliation.current_graph_ref != manifest.graph_ref:
            raise StrategyMatrixRecoveryError("strategy checkpoint reconciled to another Graph revision")
        by_node = {item.node_ref: item for item in manifest.cells}
        reusable: list[StrategyCellCoordinate] = []
        invalidated: list[StrategyCellCoordinate] = []
        for decision in resumed.reconciliation.decisions:
            coordinate = by_node.get(decision.node_ref)
            if coordinate is None:
                continue
            if decision.action in {"REUSE_CURRENT", "REUSE_CHECKPOINT"}:
                reusable.append(coordinate)
            elif decision.action == "INVALIDATE":
                invalidated.append(coordinate)
        return StrategyMatrixRecovery(
            resumed,
            tuple(sorted(reusable, key=lambda item: item.order_index)),
            tuple(sorted(invalidated, key=lambda item: item.order_index)),
        )

    def validate_completed_cells(
        self,
        manifest: StrategyMatrixManifest,
        records: Sequence[StrategyCompletedCellEvidence],
    ) -> tuple[StrategyCompletedCellEvidence, ...]:
        graph = self._live_graph(manifest)
        exact = tuple(records)
        by_digest = {item.coordinate.canonical_digest: item for item in exact}
        if len(by_digest) != len(exact):
            raise StrategyMatrixEvidenceError("completed strategy evidence is duplicated")
        validated: list[StrategyCompletedCellEvidence] = []
        for coordinate in manifest.cells:
            record = by_digest.get(coordinate.canonical_digest)
            if record is None:
                continue
            state = self.executions.get_node_execution(self.access, coordinate.node_ref)
            self._validate_completed(manifest, coordinate, record, state, self._node(graph, coordinate.node_ref))
            validated.append(record)
        return tuple(validated)

    def build_result(
        self,
        manifest: StrategyMatrixManifest,
        completed: Sequence[StrategyCompletedCellEvidence],
    ) -> StrategyEvaluationResult:
        validated = self.validate_completed_cells(manifest, completed)
        if not validated:
            raise StrategyMatrixEvidenceError("strategy matrix has no verified completed cells")
        return build_strategy_evaluation_result(
            manifest.experiment,
            tuple(item.evaluation_run for item in validated),
        )

    def publish_result(
        self,
        manifest: StrategyMatrixManifest,
        result: StrategyEvaluationResult,
        *,
        manifest_artifact: Artifact,
        completed: Sequence[StrategyCompletedCellEvidence],
        authority_attempt: ExecutionAttempt,
    ) -> Artifact:
        if result.experiment_digest != manifest.experiment.canonical_digest:
            raise StrategyMatrixEvidenceError("aggregate strategy result differs from experiment")
        validated = self.validate_completed_cells(manifest, completed)
        if {item.evaluation_run.canonical_digest for item in validated} != {
            item.canonical_digest for item in result.runs
        }:
            raise StrategyMatrixEvidenceError("aggregate strategy result differs from verified cells")
        data = _canonical(result.payload())
        content = self.object_storage.put(
            data,
            media_type="application/vnd.minitz.strategy-evaluation-result+json",
            expected_digest=hashlib.sha256(data).hexdigest(),
            expected_size=len(data),
        )
        return self.artifacts.publish_from_run(
            self.access,
            producer_attempt=authority_attempt,
            expected_task_ref=authority_attempt.task_ref,
            expected_task_digest=authority_attempt.task_digest,
            role="strategy.evaluation.aggregate-result",
            content_ref=content,
            source_refs=(),
            source_artifact_refs=(
                manifest_artifact.artifact_ref,
                *(item.result_artifact.artifact_ref for item in validated),
            ),
            source_content_refs=(),
            derivation_type="strategy.evaluation.aggregate",
            metadata={},
        )

    @staticmethod
    def knowledge_candidate_payload(
        manifest: StrategyMatrixManifest,
        result_artifact: Artifact,
        *,
        manifest_artifact: Artifact,
        completed: Sequence[StrategyCompletedCellEvidence],
    ) -> ProjectKnowledgeCandidatePayload:
        if result_artifact.content_ref is None:
            raise StrategyMatrixEvidenceError("aggregate strategy result Artifact has no content")
        evidence = (
            manifest_artifact.artifact_ref,
            *(item.result_artifact.artifact_ref for item in completed),
        )
        return ProjectKnowledgeCandidatePayload(
            manifest.project_ref,
            f"strategy-evaluation.{manifest.canonical_digest[:32]}",
            "strategy.evaluation",
            "strategy.evaluation.result",
            result_artifact.content_ref,
            {
                "evidence_class": manifest.experiment.evidence_class.value,
                "experiment_digest": manifest.experiment.canonical_digest,
            },
            (result_artifact.artifact_ref,),
            tuple(dict.fromkeys(evidence)),
        )


__all__ = [
    "StrategyCellCoordinate",
    "StrategyCellExecutionProduct",
    "StrategyCellInfrastructureFailure",
    "StrategyCompletedCellEvidence",
    "StrategyEvaluationMatrixRuntime",
    "StrategyEvaluationRuntimeError",
    "StrategyMatrixAuthorityError",
    "StrategyMatrixBatchResult",
    "StrategyMatrixContractError",
    "StrategyMatrixEvidenceError",
    "StrategyMatrixManifest",
    "StrategyMatrixRecovery",
    "StrategyMatrixRecoveryError",
]
