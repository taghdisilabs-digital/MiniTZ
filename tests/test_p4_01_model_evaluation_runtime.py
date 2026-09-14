from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pytest

from minitz_os.engine.artifact import Artifact, ArtifactService
from minitz_os.engine.capability import Capability, CapabilityRef, CapabilityRegistry
from minitz_os.engine.checkpoint import CheckpointService
from minitz_os.engine.execution import NodeExecutionService
from minitz_os.engine.graph import GraphRef, GraphService, Node, NodeRef
from minitz_os.engine.model_evaluation import (
    EvidenceClass,
    EvaluationTask,
    EvaluationTaskSet,
    ModelCandidate,
    ModelEvaluationRun,
    ModelEvaluationSuite,
    WorkloadProfile,
)
from minitz_os.engine.model_evaluation_runtime import (
    CellExecutionProduct,
    CompletedCellEvidence,
    EvaluationCellCoordinate,
    MatrixAuthorityError,
    MatrixManifest,
    ModelEvaluationMatrixRuntime,
)
from minitz_os.engine.object_store import MemoryObjectStorageBackend
from minitz_os.engine.project import ProjectAccess, ProjectStore
from minitz_os.engine.resource import (
    Resource,
    ResourceHealth,
    ResourceObservation,
    ResourceRef,
    ResourceService,
)
from minitz_os.engine.run import ExecutionAttempt, RunService
from minitz_os.engine.scheduler import ResourceClaim, ScheduledDispatch, Scheduler, SchedulingRequest
from minitz_os.engine.task import TaskRevisionService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass
class Kernel:
    access: ProjectAccess
    authority: ExecutionAttempt
    suite: ModelEvaluationSuite
    manifest: MatrixManifest
    manifest_artifact: Artifact
    runtime: ModelEvaluationMatrixRuntime
    scheduler: Scheduler
    executions: NodeExecutionService
    resource_ref: ResourceRef


def _suite(
    access: ProjectAccess,
    store: MemoryObjectStorageBackend,
    *,
    repetitions: int = 1,
    version: int = 1,
) -> ModelEvaluationSuite:
    capability = CapabilityRef("model.evaluate", "1.0.0")
    profile_content = store.put(b"profile", media_type="application/json")
    task_content = store.put(b"task", media_type="application/json")
    task_set_content = store.put(b"task-set", media_type="application/json")
    profile = WorkloadProfile(
        access.project_ref,
        "reference",
        version,
        profile_content,
        {"domain": "reference"},
    )
    task = EvaluationTask(
        access.project_ref,
        "task",
        version,
        task_content,
        capability,
        "template://reference/exact",
        "reference",
        "small",
    )
    task_set = EvaluationTaskSet(
        access.project_ref,
        "tasks",
        version,
        task_set_content,
        (task,),
        "selection://reference/all",
    )
    candidates = (
        ModelCandidate(
            access.project_ref,
            "candidate.a",
            "deployment://reference/a",
            "a" * 64,
            "adapter://reference/deterministic",
            "runtime://reference/a",
            "rev-a",
            False,
            capability,
        ),
        ModelCandidate(
            access.project_ref,
            "candidate.b",
            "deployment://reference/b",
            "b" * 64,
            "adapter://reference/deterministic",
            "runtime://reference/b",
            "rev-b",
            False,
            capability,
        ),
    )
    return ModelEvaluationSuite(
        access.project_ref,
        "reference.matrix",
        version,
        capability,
        profile,
        task_set,
        EvidenceClass.CONTROLLED,
        {"MODEL_IMPLEMENTATION": "varied", "prompt": "fixed"},
        {},
        candidates,
        "execution://reference/exact",
        "tool-policy://reference/none",
        "context-policy://reference/exact",
        "validation-policy://reference/deterministic",
        "resource-policy://reference/same-host",
        "generation-policy://reference/greedy",
        "order-policy://reference/interleaved",
        "cache-policy://reference/disabled",
        repetitions,
        None,
    )


def _kernel(tmp_path: Path, *, repetitions: int = 1) -> Kernel:
    database = tmp_path / "kernel.sqlite"
    objects = MemoryObjectStorageBackend()
    registration = ProjectStore(database).create_project(
        namespace="evaluation-runtime",
        display_name="Evaluation Runtime",
    )
    access = registration.access
    suite = _suite(access, objects, repetitions=repetitions)
    CapabilityRegistry(database).register(
        Capability(
            suite.capability_ref,
            "Deterministic model evaluation",
            {},
            {"result": "schema://minitz/model-evaluation-result"},
        )
    )
    task = TaskRevisionService(database).create_task(
        access,
        project_ref=access.project_ref,
        idempotency_key="matrix-task",
        task_type="model.evaluation",
        objective="Run deterministic reference matrix",
        required_capabilities=(suite.capability_ref,),
        input_refs=(),
        output_contract={"result": "schema://minitz/model-evaluation-result"},
        constraints={},
        side_effect_authority="READ_ONLY",
        data_policy_ref=None,
        egress_policy_ref=None,
        evidence_requirements=(),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    authority = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="controller://model-evaluation",
        lease_seconds=3600,
    )
    graph_ref = GraphRef(access.project_ref, "gph_" + "1" * 32, 1)
    cell_refs = tuple(
        NodeRef(graph_ref, f"nod_{index:032x}")
        for index in range(1, len(suite.candidates) * len(suite.task_set.tasks) * repetitions + 1)
    )
    aggregate_ref = NodeRef(graph_ref, "nod_" + "f" * 32)
    coordinates: list[EvaluationCellCoordinate] = []
    nodes: list[Node] = []
    index = 0
    for candidate in suite.candidates:
        for evaluation_task in suite.task_set.tasks:
            for repetition in range(1, repetitions + 1):
                node_ref = cell_refs[index]
                coordinates.append(
                    EvaluationCellCoordinate.bind(
                        suite,
                        candidate,
                        evaluation_task,
                        repetition,
                        index,
                        node_ref,
                    )
                )
                nodes.append(
                    Node(
                        node_ref,
                        "model",
                        (suite.capability_ref,),
                        (),
                        (),
                        {"result": "schema://minitz/model-evaluation-cell"},
                        None,
                        "READ_ONLY",
                        {},
                        (),
                    )
                )
                index += 1
    nodes.append(
        Node(
            aggregate_ref,
            "deterministic",
            (),
            cell_refs,
            (),
            {"result": "schema://minitz/model-evaluation-result"},
            None,
            "READ_ONLY",
            {},
            (),
        )
    )
    graph = GraphService(database).create_graph(
        access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=nodes,
        compiler_identity="compiler://model-evaluation/reference",
        compiler_version="1.0.0",
        authority_attempt=authority,
    )
    executions = NodeExecutionService(database)
    executions.prepare_run(access, run.run_ref)
    resources = ResourceService(database)
    resource_ref = ResourceRef.new(access.project_ref)
    resource = resources.register_resource(
        access,
        Resource(resource_ref, "compute", "host://reference"),
    )
    resources.record_observation(
        access,
        resource_ref,
        "test.reference",
        ResourceObservation(_now(), 3600, ResourceHealth.HEALTHY),
        expected_resource_record_sha256=resource.record_sha256,
    )
    manifest = MatrixManifest(
        suite,
        run.run_ref,
        graph.graph_ref,
        graph.record_sha256,
        tuple(coordinates),
        aggregate_ref,
        _now(),
    )
    artifacts = ArtifactService(database)
    checkpoints = CheckpointService(database, objects)
    runtime = ModelEvaluationMatrixRuntime(
        access,
        GraphService(database),
        executions,
        checkpoints,
        artifacts,
        objects,
    )
    manifest_artifact = runtime.publish_manifest(manifest, authority_attempt=authority)
    return Kernel(
        access,
        authority,
        suite,
        manifest,
        manifest_artifact,
        runtime,
        Scheduler(database),
        executions,
        resource_ref,
    )


def _dispatches(kernel: Kernel) -> dict[NodeRef, ScheduledDispatch]:
    result: dict[NodeRef, ScheduledDispatch] = {}
    for coordinate in kernel.manifest.cells:
        allocation = kernel.scheduler.reserve(
            kernel.access,
            SchedulingRequest(
                coordinate.node_ref,
                (ResourceClaim(kernel.resource_ref),),
            ),
            authority_attempt=kernel.authority,
            owner_ref="worker://reference",
            lease_seconds=3600,
            idempotency_key=f"reserve-{coordinate.order_index}",
        )
        result[coordinate.node_ref] = kernel.scheduler.dispatch(
            kernel.access,
            allocation,
            authority_attempt=kernel.authority,
            lease_seconds=3600,
            idempotency_key=f"dispatch-{coordinate.order_index}",
        )
    return result


def _callback(
    kernel: Kernel,
    calls: list[str],
) -> Callable[[EvaluationCellCoordinate, ScheduledDispatch], CellExecutionProduct]:
    def execute(
        coordinate: EvaluationCellCoordinate,
        _: ScheduledDispatch,
    ) -> CellExecutionProduct:
        calls.append(coordinate.canonical_digest)
        candidate_index = 0 if coordinate.candidate_id == "candidate.a" else 1
        started = _now()
        run = ModelEvaluationRun(
            kernel.suite,
            coordinate.candidate_id,
            next(item for item in kernel.suite.task_set.tasks if item.canonical_digest == coordinate.task_digest),
            coordinate.repetition,
            kernel.manifest.run_ref,
            (),
            (),
            (),
            (),
            None,
            (),
            "ok",
            "ok" if candidate_index == 0 else "failed",
            "ok",
            "completed",
            started,
            _now(),
            {"latency.seconds": 1.0 + candidate_index},
            None,
            None,
        )
        return CellExecutionProduct(run, "result", ())

    return execute


def test_manifest_is_deterministic_and_binds_exact_versions(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    rebuilt = MatrixManifest(
        kernel.suite,
        kernel.manifest.run_ref,
        kernel.manifest.graph_ref,
        kernel.manifest.graph_record_sha256,
        kernel.manifest.cells,
        kernel.manifest.aggregate_node_ref,
        kernel.manifest.created_at,
    )
    assert rebuilt.canonical_digest == kernel.manifest.canonical_digest
    changed_suite = _suite(kernel.access, MemoryObjectStorageBackend(), version=2)
    assert changed_suite.canonical_digest != kernel.suite.canonical_digest


def test_cancel_resume_skips_completed_cells_on_real_kernel(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    dispatches = _dispatches(kernel)
    calls: list[str] = []
    durable: dict[str, CompletedCellEvidence] = {}
    probes = 0

    def cancel_after_one() -> bool:
        nonlocal probes
        probes += 1
        return probes > 1

    first = kernel.runtime.execute_batch(
        kernel.manifest,
        manifest_artifact=kernel.manifest_artifact,
        authority_attempt=kernel.authority,
        dispatches=dispatches,
        cell_callback=_callback(kernel, calls),
        completed_evidence_loader=lambda coordinate: durable.get(coordinate.canonical_digest),
        batch_idempotency_key="batch-first",
        cancellation_probe=cancel_after_one,
    )
    assert first.cancelled
    assert len(first.completed) == 1
    durable.update({item.coordinate.canonical_digest: item for item in first.completed})
    first_call = calls[0]
    recovery = kernel.runtime.resume_matrix(
        kernel.manifest,
        checkpoint_ref=first.checkpoint.checkpoint_ref,
        authority_attempt=kernel.authority,
        idempotency_key="resume-first",
    )
    assert recovery.reusable_cells == (kernel.manifest.cells[0],)
    second = kernel.runtime.execute_batch(
        kernel.manifest,
        manifest_artifact=kernel.manifest_artifact,
        authority_attempt=kernel.authority,
        dispatches=dispatches,
        cell_callback=_callback(kernel, calls),
        completed_evidence_loader=lambda coordinate: durable.get(coordinate.canonical_digest),
        batch_idempotency_key="batch-second",
    )
    assert [item.coordinate for item in second.skipped] == [kernel.manifest.cells[0]]
    assert calls.count(first_call) == 1
    durable.update({item.coordinate.canonical_digest: item for item in second.completed})
    result = kernel.runtime.build_result(kernel.manifest, tuple(durable.values()))
    comparison = result.pairwise_comparisons[0]
    assert comparison.conclusion == "INSUFFICIENT_EVIDENCE"
    assert comparison.winner is None
    assert comparison.resource_confounder_ref == kernel.suite.resource_policy_ref
    unknown = {item.metric: item for item in result.statistics}
    assert unknown["usage.tokens"].mean is None
    assert unknown["cost.amount"].mean is None
    assert unknown["reliability.semantic"].mean == 0.5
    assert unknown["reliability.infrastructure"].mean == 1.0


def test_stale_dispatch_and_private_project_scope_are_rejected(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    dispatches = _dispatches(kernel)
    coordinate = kernel.manifest.cells[0]
    stale = dispatches[coordinate.node_ref]
    dispatches[coordinate.node_ref] = ScheduledDispatch(
        stale.allocation,
        replace(stale.node_attempt, fence=stale.node_attempt.fence + 1),
    )
    with pytest.raises(MatrixAuthorityError):
        kernel.runtime.execute_batch(
            kernel.manifest,
            manifest_artifact=kernel.manifest_artifact,
            authority_attempt=kernel.authority,
            dispatches=dispatches,
            cell_callback=_callback(kernel, []),
            completed_evidence_loader=lambda _: None,
            batch_idempotency_key="stale-batch",
        )
    foreign = ProjectStore(tmp_path / "kernel.sqlite").create_project(
        namespace="foreign-evaluation-runtime",
        display_name="Foreign Evaluation Runtime",
    )
    foreign_runtime = ModelEvaluationMatrixRuntime(
        foreign.access,
        kernel.runtime.graphs,
        kernel.runtime.executions,
        kernel.runtime.checkpoints,
        kernel.runtime.artifacts,
        kernel.runtime.object_storage,
    )
    with pytest.raises(MatrixAuthorityError):
        foreign_runtime.publish_manifest(
            kernel.manifest,
            authority_attempt=kernel.authority,
        )


def test_knowledge_output_is_project_candidate_payload_only(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    dispatches = _dispatches(kernel)
    completed = kernel.runtime.execute_batch(
        kernel.manifest,
        manifest_artifact=kernel.manifest_artifact,
        authority_attempt=kernel.authority,
        dispatches=dispatches,
        cell_callback=_callback(kernel, []),
        completed_evidence_loader=lambda _: None,
        batch_idempotency_key="knowledge-batch",
    ).completed
    result = kernel.runtime.build_result(kernel.manifest, completed)
    artifact = kernel.runtime.publish_result(
        kernel.manifest,
        result,
        manifest_artifact=kernel.manifest_artifact,
        completed=completed,
        authority_attempt=kernel.authority,
    )
    payload = kernel.runtime.knowledge_candidate_payload(
        kernel.manifest,
        artifact,
        manifest_artifact=kernel.manifest_artifact,
        completed=completed,
    )
    kwargs = payload.as_record_candidate_kwargs()
    assert payload.project_ref == kernel.access.project_ref
    assert kwargs["origin_type"] == "model.evaluation"
    assert "accepted_by" not in kwargs
    assert "promoted_by" not in kwargs
    assert "winner" not in kwargs
