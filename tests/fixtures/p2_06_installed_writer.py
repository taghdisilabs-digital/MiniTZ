"""Create durable P2-06 model evidence through an installed wheel."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

from minitz_os.engine import (
    FilesystemObjectStorageBackend,
    GraphRef,
    GraphService,
    InferRequest,
    ModelDeployment,
    ModelDeploymentRef,
    ModelExecutionBinding,
    ModelExecutionRef,
    ModelOperation,
    ModelRuntimeIdentity,
    Node,
    NodeExecutionService,
    NodeRef,
    ProjectStore,
    ReferenceModelAdapter,
    RunService,
    TaskRevisionService,
)


def main() -> None:
    database = Path(os.environ["MINITZ_DATABASE"])
    object_root = Path(os.environ["MINITZ_OBJECT_ROOT"])
    evidence_path = Path(os.environ["MINITZ_EVIDENCE"])
    registration = ProjectStore(database).create_project(namespace="p2-06-installed", display_name="P2-06 Installed")
    objects = FilesystemObjectStorageBackend(object_root)
    adapter = ReferenceModelAdapter(database, objects)
    runtime = ModelRuntimeIdentity(
        adapter.adapter_ref,
        "runtime://python/installed-reference-v1",
        "installed-generation-1",
        "provider://minitz/reference",
        "model://minitz/installed-reference-v1",
        "installed-reference-v1",
        None,
        (),
        "REFERENCE",
    )
    deployment = adapter.register_deployment(
        registration.access,
        ModelDeployment(
            ModelDeploymentRef.new(registration.project.project_ref),
            adapter.adapter_ref,
            runtime.provider_ref,
            runtime.model_ref,
            runtime.model_revision,
            None,
            None,
            (ModelOperation.INFER,),
            ("text",),
            128,
            True,
            False,
            None,
            (),
            ("policy://installed/data",),
            (),
            False,
            runtime,
        ),
        idempotency_key="installed-deployment",
    )
    capabilities = tuple(adapter.register_capabilities(registration.access, deployment))
    task = TaskRevisionService(database).create_task(
        registration.access,
        project_ref=registration.project.project_ref,
        idempotency_key="installed-model-task",
        task_type="model.execute",
        objective="Verify installed model adapter restart",
        required_capabilities=capabilities,
        input_refs=(),
        output_contract={"result": "schema://minitz/model-infer-result/1"},
        constraints={},
        side_effect_authority="PROJECT_WRITE",
        data_policy_ref="policy://installed/data",
        egress_policy_ref=None,
        evidence_requirements=("model-call", "artifact", "content-ref"),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(registration.access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        registration.access,
        run.run_ref,
        owner_ref="controller://installed-model",
        lease_seconds=300,
    )
    graph_ref = GraphRef.new(registration.project.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "MODEL",
        capabilities,
        (),
        (),
        {"result": "schema://minitz/model-infer-result/1"},
        None,
        "PROJECT_WRITE",
        {},
        ("model-call", "artifact", "content-ref"),
    )
    GraphService(database).create_graph(
        registration.access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(node,),
        compiler_identity=None,
        compiler_version=None,
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    executions.prepare_run(registration.access, run.run_ref)
    attempt = executions.lease_node(
        registration.access,
        node.node_ref,
        authority_attempt=run_attempt,
        owner_ref="executor://installed-model",
        lease_seconds=300,
        idempotency_key="installed-model-node",
    )
    executions.start_node(registration.access, attempt, idempotency_key="installed-model-start")
    messages_ref = objects.put(
        b'{"messages":[{"content":"installed restart exact","role":"user"}]}',
        media_type="application/json",
    )
    binding = ModelExecutionBinding(
        registration.project.project_ref,
        ModelExecutionRef.new(registration.project.project_ref),
        deployment.deployment_ref,
        adapter.capability_ref(ModelOperation.INFER),
        task.task_ref,
        task.canonical_digest,
        run.run_ref,
        node.node_ref,
        attempt.attempt_id,
        attempt.fence,
        (messages_ref,),
        None,
        cast(str, task.data_policy_ref),
        None,
        4,
        5.0,
    )
    result = adapter.infer(
        registration.access,
        attempt,
        InferRequest(binding, messages_ref),
        credentials={},
        idempotency_key="installed-model-infer",
    )
    assert result.evidence.output_ref is not None
    evidence_path.write_text(
        json.dumps(
            {
                "deployment_id": deployment.deployment_ref.deployment_id,
                "execution_id": binding.execution_ref.execution_id,
                "model_call_id": result.evidence.model_call_ref.call_id,
                "output_digest": result.evidence.output_ref.digest,
                "project_ref": registration.project.project_ref.value,
                "receipt_artifact": result.evidence.receipt_artifact_ref.value,
                "text": result.text,
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(registration.access.token)


if __name__ == "__main__":
    main()
