"""Create P2-04 isolated-runtime evidence using only an installed wheel."""

from __future__ import annotations

import json
import os
from pathlib import Path

from biella import (
    DockerIsolatedRuntimeAdapter,
    FilesystemAdapter,
    FilesystemMode,
    FilesystemObjectStorageBackend,
    FilesystemScope,
    GraphRef,
    GraphService,
    IsolatedRuntimeSpec,
    Node,
    NodeExecutionService,
    NodeRef,
    ProjectStore,
    RunService,
    RuntimeMount,
    RuntimeNetworkPolicy,
    RuntimeOutput,
    RuntimeResourceLimits,
    TaskRevisionService,
)


IMAGE_REF = "sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce"

database = Path(os.environ["BIELLA_DATABASE"])
object_root = Path(os.environ["BIELLA_OBJECT_ROOT"])
control_path = Path(os.environ["BIELLA_CONTROL_ROOT"])
output_path = Path(os.environ["BIELLA_OUTPUT_ROOT"])
runtime_path = Path(os.environ["BIELLA_RUNTIME_ROOT"])
control_path.mkdir(parents=True)
output_path.mkdir(parents=True)
output_path.chmod(0o777)

registration = ProjectStore(database).create_project(
    namespace="installed-isolated-runtime",
    display_name="Installed Isolated Runtime",
)
objects = FilesystemObjectStorageBackend(object_root)
filesystem = FilesystemAdapter(database, objects)
filesystem_capabilities = filesystem.register_capabilities(registration.access)
runtime = DockerIsolatedRuntimeAdapter(database, objects, runtime_root=runtime_path)
process_capabilities = runtime.process.register_capabilities(registration.access)
runtime_capabilities = runtime.register_capabilities(registration.access)
capabilities = tuple(sorted((*filesystem_capabilities, *process_capabilities, *runtime_capabilities)))
task = TaskRevisionService(database).create_task(
    registration.access,
    project_ref=registration.project.project_ref,
    idempotency_key="installed-runtime-task",
    task_type="runtime.installed",
    objective="Verify installed isolated runtime restart",
    required_capabilities=capabilities,
    input_refs=(),
    output_contract={"result": "schema://biella/isolated-runtime-receipt/1"},
    constraints={},
    side_effect_authority="PROJECT_WRITE",
    data_policy_ref=None,
    egress_policy_ref=None,
    evidence_requirements=("tool-call", "artifact", "content-ref"),
    acceptance_criteria=(),
    resource_hints={},
)
runs = RunService(database)
run = runs.create_run(registration.access, task_ref=task.task_ref)
run_attempt = runs.acquire_run_lease(
    registration.access,
    run.run_ref,
    owner_ref="controller://installed-runtime",
    lease_seconds=600,
)
graph_ref = GraphRef.new(registration.project.project_ref)
node = Node(
    NodeRef.new(graph_ref),
    "TOOL",
    capabilities,
    (),
    (),
    {"result": "schema://biella/isolated-runtime-receipt/1"},
    None,
    "PROJECT_WRITE",
    {},
    ("tool-call", "artifact", "content-ref"),
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
    owner_ref="executor://installed-runtime",
    lease_seconds=600,
    idempotency_key="installed-runtime-node-lease",
)
executions.start_node(registration.access, attempt, idempotency_key="installed-runtime-node-start")
control_root = filesystem.register_root(
    registration.access,
    path=control_path,
    scope=FilesystemScope.PROJECT,
    mode=FilesystemMode.READ_WRITE,
    allow_remove=True,
    idempotency_key="installed-runtime-control-root",
)
output_root = filesystem.register_root(
    registration.access,
    path=output_path,
    scope=FilesystemScope.PROJECT,
    mode=FilesystemMode.READ_WRITE,
    allow_remove=True,
    idempotency_key="installed-runtime-output-root",
)
spec = IsolatedRuntimeSpec(
    registration.project.project_ref,
    IMAGE_REF,
    "/bin/sh",
    ("-c", "printf 'installed isolated output\\n' > /workspace/output/result.txt"),
    "/workspace",
    (RuntimeMount(output_root.root_ref, ".", "/workspace/output", False),),
    (RuntimeOutput(output_root.root_ref, "result.txt", "text/plain"),),
    (),
    RuntimeNetworkPolicy.NONE,
    RuntimeResourceLimits(cpus=0.25, memory_bytes=64 * 1024 * 1024, process_count=16),
    {"BIELLA_INSTALLED_TEST": "exact"},
    30,
    1024 * 1024,
    1024 * 1024,
)
created = runtime.create(
    registration.access,
    attempt,
    spec,
    control_root_ref=control_root.root_ref,
    idempotency_key="installed-runtime-create",
)
started = runtime.start(
    registration.access,
    attempt,
    created.state.runtime_ref,
    secret_values={},
    idempotency_key="installed-runtime-start",
)
executed = runtime.execute(
    registration.access,
    attempt,
    started.state.runtime_ref,
    secret_values={},
    idempotency_key="installed-runtime-execute",
)
collected = runtime.collect_outputs(
    registration.access,
    attempt,
    executed.state.runtime_ref,
    secret_values={},
    idempotency_key="installed-runtime-collect",
)
cleaned = runtime.cleanup(
    registration.access,
    attempt,
    collected.state.runtime_ref,
    idempotency_key="installed-runtime-cleanup",
)
print(
    json.dumps(
        {
            "cleanup_call_id": cleaned.tool_call_ref.call_id,
            "cleanup_record_sha256": cleaned.record_sha256,
            "collection_call_id": collected.tool_call_ref.call_id,
            "collection_record_sha256": collected.record_sha256,
            "output_artifact_ref": collected.output_artifact_refs[0].value,
            "project_id": registration.project.project_ref.value,
            "runtime_generation": cleaned.state.runtime_ref.generation,
            "runtime_id": cleaned.state.runtime_ref.runtime_id,
            "token": registration.access.token,
        },
        sort_keys=True,
    )
)
