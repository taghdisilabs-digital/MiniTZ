from __future__ import annotations

import json
import os
from pathlib import Path

import biella
from biella import (
    ArtifactService,
    Capability,
    CapabilityRef,
    CapabilityRegistry,
    CheckpointService,
    ContentRef,
    FilesystemObjectStorageBackend,
    GraphRef,
    GraphService,
    Node,
    NodeExecutionService,
    NodeInputBinding,
    NodeRef,
    ProjectStore,
    RunService,
    TaskRevisionService,
)


installed = Path(os.environ["BIELLA_INSTALLED"]).resolve()
assert Path(biella.__file__).resolve().is_relative_to(installed)
database = Path(os.environ["BIELLA_DATABASE"])
object_root = Path(os.environ["BIELLA_OBJECT_ROOT"])
registration = ProjectStore(database).create_project(
    namespace="wheel-checkpoint",
    display_name="Wheel Checkpoint",
)
capability = CapabilityRegistry(database).register(
    Capability(CapabilityRef("wheel.checkpoint", "1.0.0"), "Wheel checkpoint")
)
tasks = TaskRevisionService(database)
task = tasks.create_task(
    registration.access,
    project_ref=registration.project.project_ref,
    idempotency_key="wheel-checkpoint",
    task_type="wheel.checkpoint",
    objective="Resume from installed wheel after process loss",
    required_capabilities=(capability.capability_ref,),
    input_refs=(),
    output_contract={},
    constraints={},
    side_effect_authority="PROJECT_WRITE",
    data_policy_ref=None,
    egress_policy_ref=None,
    evidence_requirements=(),
    acceptance_criteria=(),
    resource_hints={},
)
runs = RunService(database)
run = runs.create_run(registration.access, task_ref=task.task_ref)
authority = runs.acquire_run_lease(
    registration.access,
    run.run_ref,
    owner_ref="controller://wheel-checkpoint",
    lease_seconds=120,
)
graph_ref = GraphRef.new(registration.project.project_ref)
a_ref = NodeRef.new(graph_ref)
b_ref = NodeRef.new(graph_ref)
nodes = (
    Node(
        a_ref,
        "SPECIALIST_TASK",
        (capability.capability_ref,),
        (),
        (),
        {"result": "schema://wheel/result"},
        None,
        "READ_ONLY",
        {},
        (),
    ),
    Node(
        b_ref,
        "SPECIALIST_TASK",
        (capability.capability_ref,),
        (a_ref,),
        (NodeInputBinding.from_node_output("a-result", a_ref, "result"),),
        {"result": "schema://wheel/result"},
        None,
        "READ_ONLY",
        {},
        (),
    ),
)
graph = GraphService(database).create_graph(
    registration.access,
    graph_ref=graph_ref,
    task_ref=task.task_ref,
    expected_task_digest=task.canonical_digest,
    run_ref=run.run_ref,
    nodes=nodes,
    compiler_identity=None,
    compiler_version=None,
    authority_attempt=authority,
)
executions = NodeExecutionService(database)
executions.prepare_run(registration.access, run.run_ref)
a_attempt = executions.lease_node(
    registration.access,
    a_ref,
    authority_attempt=authority,
    owner_ref="executor://wheel-a",
    lease_seconds=60,
    idempotency_key="wheel-a-lease",
)
executions.start_node(
    registration.access,
    a_attempt,
    idempotency_key="wheel-a-start",
)
output = ArtifactService(database).publish_from_run(
    registration.access,
    producer_attempt=authority,
    expected_task_ref=task.task_ref,
    expected_task_digest=task.canonical_digest,
    role="wheel.checkpoint-output",
    content_ref=ContentRef.from_bytes(b"wheel-output", media_type="text/plain"),
    source_refs=(),
    source_artifact_refs=(),
    source_content_refs=(),
    derivation_type="wheel.checkpoint",
    metadata={},
)
executions.finalize_node(
    registration.access,
    a_attempt,
    outputs={"result": output.artifact_ref},
    evidence={},
    acceptance_criteria=(),
    idempotency_key="wheel-a-finalize",
)
executions.prepare_run(registration.access, run.run_ref)
checkpoint = CheckpointService(
    database,
    FilesystemObjectStorageBackend(object_root),
).create_checkpoint(
    registration.access,
    run.run_ref,
    authority_attempt=authority,
    idempotency_key="wheel-before-b",
)
b_attempt = executions.lease_node(
    registration.access,
    b_ref,
    authority_attempt=authority,
    owner_ref="executor://wheel-b-old",
    lease_seconds=0.05,
    idempotency_key="wheel-b-old-lease",
)
executions.start_node(
    registration.access,
    b_attempt,
    idempotency_key="wheel-b-old-start",
)
print(
    json.dumps(
        {
            "a_ref": a_ref.value,
            "b_ref": b_ref.value,
            "checkpoint_id": checkpoint.checkpoint_ref.checkpoint_id,
            "old_fence": b_attempt.fence,
            "output_ref": output.artifact_ref.value,
            "project_id": registration.project.project_ref.value,
            "run_id": run.run_id,
            "token": registration.access.token,
        },
        sort_keys=True,
    )
)
