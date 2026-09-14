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
    WorkloadProfile,
)
from minitz_os.engine.object_store import MemoryObjectStorageBackend
from minitz_os.engine.project import ProjectAccess, ProjectStore
from minitz_os.engine.resource import Resource, ResourceHealth, ResourceObservation, ResourceRef, ResourceService
from minitz_os.engine.run import ExecutionAttempt, RunRef, RunService
from minitz_os.engine.scheduler import ResourceClaim, ScheduledDispatch, Scheduler, SchedulingRequest
from minitz_os.engine.strategy_evaluation import (
    ExecutionStrategy,
    MatrixKind,
    PromptArtifact,
    SkillArtifact,
    StrategyDimension,
    StrategyEvaluationExperiment,
    StrategyEvaluationRun,
    StrategyMetricSet,
    StrategyPattern,
)
from minitz_os.engine.strategy_evaluation_runtime import (
    StrategyCellCoordinate,
    StrategyCellExecutionProduct,
    StrategyCompletedCellEvidence,
    StrategyEvaluationMatrixRuntime,
    StrategyMatrixAuthorityError,
    StrategyMatrixManifest,
)
from minitz_os.engine.task import TaskRevisionService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _strategy(
    access: ProjectAccess,
    store: MemoryObjectStorageBackend,
    strategy_id: str,
) -> ExecutionStrategy:
    skill = SkillArtifact(
        access.project_ref,
        f"{strategy_id}.skill",
        1,
        store.put(strategy_id.encode(), media_type="text/plain"),
        {"workload": "reference"},
    )
    prompt = PromptArtifact(
        access.project_ref,
        f"{strategy_id}.prompt",
        1,
        store.put(f"prompt-{strategy_id}".encode(), media_type="text/plain"),
        {"workload": "reference"},
    )
    return ExecutionStrategy(
        access.project_ref,
        strategy_id,
        1,
        (StrategyPattern.DIRECT,),
        {"workload": "reference"},
        (skill,),
        (prompt,),
        "decomposition-policy://reference/direct/v1",
        "tool-policy://reference/none/v1",
        "context-policy://reference/exact/v1",
        "model-call-policy://reference/greedy/v1",
        "loop-stop-policy://reference/output-valid/v1",
        "parallel-policy://reference/serial/v1",
        "specialist-policy://reference/generalist/v1",
        ("validation-policy://reference/exact/v1",),
        "failure-policy://reference/preserve/v1",
        "output-policy://reference/exact/v1",
    )


def _experiment(
    access: ProjectAccess,
    store: MemoryObjectStorageBackend,
    *,
    repetitions: int = 1,
) -> StrategyEvaluationExperiment:
    capability = CapabilityRef("strategy.evaluate", "1.0.0")
    profile = WorkloadProfile(
        access.project_ref,
        "reference",
        1,
        store.put(b"profile", media_type="application/json"),
        {"domain": "reference"},
    )
    task = EvaluationTask(
        access.project_ref,
        "task",
        1,
        store.put(b"task", media_type="application/json"),
        capability,
        "template://strategy-evaluation/reference/v1",
        "reference",
        "small",
    )
    task_set = EvaluationTaskSet(
        access.project_ref,
        "tasks",
        1,
        store.put(b"task-set", media_type="application/json"),
        (task,),
        "selection-policy://strategy-evaluation/all/v1",
    )
    model = ModelCandidate(
        access.project_ref,
        "model-a",
        "model-deployment://reference/model-a",
        "a" * 64,
        "adapter://reference/local",
        "runtime://reference/pytorch",
        "revision-a",
        False,
        capability,
    )
    return StrategyEvaluationExperiment(
        access.project_ref,
        "reference.matrix",
        1,
        capability,
        profile,
        task_set,
        EvidenceClass.CONTROLLED,
        MatrixKind.SAME_MODEL,
        {"MODEL_IMPLEMENTATION": "fixed", "TASK_SET": "fixed", "RESOURCE": "fixed", "OUTPUT": "fixed"},
        (StrategyDimension.PROMPT_SKILL,),
        {},
        (model,),
        (_strategy(access, store, "strategy-s1"), _strategy(access, store, "strategy-s2")),
        ("validation-policy://reference/exact/v1",),
        "resource-policy://reference/same-host/v1",
        "order-policy://reference/interleaved/v1",
        "cache-policy://reference/disabled/v1",
        "READ_ONLY",
        repetitions,
    )


@dataclass
class Kernel:
    access: ProjectAccess
    authority: ExecutionAttempt
    experiment: StrategyEvaluationExperiment
    manifest: StrategyMatrixManifest
    manifest_artifact: Artifact
    runtime: StrategyEvaluationMatrixRuntime
    scheduler: Scheduler
    resource_ref: ResourceRef


def _kernel(tmp_path: Path, *, repetitions: int = 1) -> Kernel:
    database = tmp_path / "kernel.sqlite"
    objects = MemoryObjectStorageBackend()
    access = ProjectStore(database).create_project(
        namespace="strategy-evaluation-runtime",
        display_name="Strategy Evaluation Runtime",
    ).access
    experiment = _experiment(access, objects, repetitions=repetitions)
    CapabilityRegistry(database).register(
        Capability(
            experiment.capability_ref,
            "Deterministic strategy evaluation",
            {},
            {"result": "schema://minitz/strategy-evaluation-result"},
        )
    )
    task = TaskRevisionService(database).create_task(
        access,
        project_ref=access.project_ref,
        idempotency_key="strategy-matrix-task",
        task_type="strategy.evaluation",
        objective="Run deterministic strategy matrix",
        required_capabilities=(experiment.capability_ref,),
        input_refs=(),
        output_contract={"result": "schema://minitz/strategy-evaluation-result"},
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
        owner_ref="controller://strategy-evaluation",
        lease_seconds=3600,
    )
    graph_ref = GraphRef(access.project_ref, "gph_" + "2" * 32, 1)
    coordinates: list[StrategyCellCoordinate] = []
    nodes: list[Node] = []
    order = 0
    for model in experiment.models:
        for strategy in experiment.strategies:
            for evaluation_task in experiment.task_set.tasks:
                for repetition in range(1, experiment.repetitions + 1):
                    node_ref = NodeRef(graph_ref, f"nod_{order + 1:032x}")
                    coordinates.append(
                        StrategyCellCoordinate.bind(
                            experiment,
                            model,
                            strategy,
                            evaluation_task,
                            repetition,
                            order,
                            node_ref,
                        )
                    )
                    nodes.append(
                        Node(
                            node_ref,
                            "model",
                            (experiment.capability_ref,),
                            (),
                            (),
                            {"result": "schema://minitz/strategy-evaluation-cell"},
                            None,
                            "READ_ONLY",
                            {},
                            (),
                        )
                    )
                    order += 1
    aggregate_ref = NodeRef(graph_ref, "nod_" + "f" * 32)
    nodes.append(
        Node(
            aggregate_ref,
            "deterministic",
            (),
            tuple(item.node_ref for item in coordinates),
            (),
            {"result": "schema://minitz/strategy-evaluation-result"},
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
        compiler_identity="compiler://strategy-evaluation/reference",
        compiler_version="1.0.0",
        authority_attempt=authority,
    )
    executions = NodeExecutionService(database)
    executions.prepare_run(access, run.run_ref)
    resources = ResourceService(database)
    resource_ref = ResourceRef.new(access.project_ref)
    resource = resources.register_resource(access, Resource(resource_ref, "compute", "host://reference"))
    resources.record_observation(
        access,
        resource_ref,
        "test.reference",
        ResourceObservation(_now(), 3600, ResourceHealth.HEALTHY),
        expected_resource_record_sha256=resource.record_sha256,
    )
    manifest = StrategyMatrixManifest(
        experiment,
        run.run_ref,
        graph.graph_ref,
        graph.record_sha256,
        tuple(coordinates),
        aggregate_ref,
        _now(),
    )
    runtime = StrategyEvaluationMatrixRuntime(
        access,
        GraphService(database),
        executions,
        CheckpointService(database, objects),
        ArtifactService(database),
        objects,
    )
    manifest_artifact = runtime.publish_manifest(manifest, authority_attempt=authority)
    return Kernel(access, authority, experiment, manifest, manifest_artifact, runtime, Scheduler(database), resource_ref)


def _dispatches(kernel: Kernel) -> dict[NodeRef, ScheduledDispatch]:
    result: dict[NodeRef, ScheduledDispatch] = {}
    for coordinate in kernel.manifest.cells:
        allocation = kernel.scheduler.reserve(
            kernel.access,
            SchedulingRequest(coordinate.node_ref, (ResourceClaim(kernel.resource_ref),)),
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
) -> Callable[[StrategyCellCoordinate, ScheduledDispatch], StrategyCellExecutionProduct]:
    def execute(
        coordinate: StrategyCellCoordinate,
        _: ScheduledDispatch,
    ) -> StrategyCellExecutionProduct:
        calls.append(coordinate.canonical_digest)
        strategy_index = 0 if coordinate.strategy_id == "strategy-s1" else 1
        now = _now()
        run = StrategyEvaluationRun(
            experiment=kernel.experiment,
            candidate_id=coordinate.candidate_id,
            strategy_id=coordinate.strategy_id,
            strategy_digest=coordinate.strategy_digest,
            task=kernel.experiment.task_set.tasks[0],
            repetition=coordinate.repetition,
            run_ref=kernel.manifest.run_ref,
            metrics=StrategyMetricSet(
                task_success=bool(strategy_index),
                quality_score=float(strategy_index),
                end_to_end_latency_seconds=1.0 + strategy_index,
                model_calls=1,
                input_tokens=10,
                output_tokens=2,
                context_tokens=8,
                model_latency_seconds=1.0 + strategy_index,
                cost=None,
                tool_calls=0,
                invalid_tool_calls=0,
                redundant_tool_calls=0,
                failed_tool_calls=0,
                tool_latency_seconds=0.0,
                tool_side_effects=0,
                tool_data_bytes=0,
                graph_nodes=len(kernel.manifest.cells) + 1,
                graph_depth=2,
                graph_parallel_width=len(kernel.manifest.cells),
                graph_revisions=1,
                graph_failures=0,
                repairs=0,
                replans=0,
                completed_reuse=0,
                resource_metrics={"cpu.seconds": 1.0},
            ),
            transport_outcome="passed",
            semantic_outcome="passed" if strategy_index else "failed",
            infrastructure_outcome="passed",
            status="completed",
            started_at=now,
            completed_at=now,
            evidence_refs=("artifact://strategy-evaluation/reference",),
        )
        return StrategyCellExecutionProduct(run, "result", ())

    return execute


def test_cancel_resume_reuses_verified_strategy_cells_and_builds_result(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path, repetitions=2)
    dispatches = _dispatches(kernel)
    calls: list[str] = []
    durable: dict[str, StrategyCompletedCellEvidence] = {}
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
    assert first.cancelled and len(first.completed) == 1
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
    assert len(result.runs) == 4
    assert result.pairwise_comparisons[0].conclusion == "INSUFFICIENT_EVIDENCE"
    assert result.mandatory_agent_hierarchy_created is False


def test_stale_strategy_dispatch_and_cross_project_runtime_are_rejected(tmp_path: Path) -> None:
    kernel = _kernel(tmp_path)
    dispatches = _dispatches(kernel)
    coordinate = kernel.manifest.cells[0]
    stale = dispatches[coordinate.node_ref]
    dispatches[coordinate.node_ref] = ScheduledDispatch(
        stale.allocation,
        replace(stale.node_attempt, fence=stale.node_attempt.fence + 1),
    )
    with pytest.raises(StrategyMatrixAuthorityError):
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
        namespace="foreign-strategy-runtime",
        display_name="Foreign Strategy Runtime",
    )
    foreign_runtime = StrategyEvaluationMatrixRuntime(
        foreign.access,
        kernel.runtime.graphs,
        kernel.runtime.executions,
        kernel.runtime.checkpoints,
        kernel.runtime.artifacts,
        kernel.runtime.object_storage,
    )
    with pytest.raises(StrategyMatrixAuthorityError):
        foreign_runtime.publish_manifest(kernel.manifest, authority_attempt=kernel.authority)
