"""Create P2-02 managed-process evidence using only an installed wheel."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from biella import (
    FilesystemAdapter,
    FilesystemMode,
    FilesystemObjectStorageBackend,
    FilesystemScope,
    GraphRef,
    GraphService,
    ManagedProcessAdapter,
    NetworkPolicy,
    Node,
    NodeExecutionService,
    NodeRef,
    ProcessExecutionRequest,
    ProjectStore,
    RunService,
    TaskRevisionService,
)


database = Path(os.environ["BIELLA_DATABASE"])
physical_root = Path(os.environ["BIELLA_PROCESS_ROOT"])
object_root = Path(os.environ["BIELLA_OBJECT_ROOT"])
registration = ProjectStore(database).create_project(
    namespace="installed-process",
    display_name="Installed Process",
)
objects = FilesystemObjectStorageBackend(object_root)
filesystem = FilesystemAdapter(database, objects)
filesystem_capabilities = filesystem.register_capabilities(registration.access)
process = ManagedProcessAdapter(database, objects, inherited_environment={"LANG": "C.UTF-8"})
process_capabilities = process.register_capabilities(registration.access)
capabilities = tuple(sorted((*filesystem_capabilities, *process_capabilities)))
task = TaskRevisionService(database).create_task(
    registration.access,
    project_ref=registration.project.project_ref,
    idempotency_key="installed-process-task",
    task_type="process.installed",
    objective="Verify installed managed-process restart",
    required_capabilities=capabilities,
    input_refs=(),
    output_contract={"result": "schema://biella/process-result/1"},
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
    owner_ref="controller://installed-process",
    lease_seconds=600,
)
graph_ref = GraphRef.new(registration.project.project_ref)
node = Node(
    NodeRef.new(graph_ref),
    "TOOL",
    capabilities,
    (),
    (),
    {"result": "schema://biella/process-result/1"},
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
    owner_ref="executor://installed-process",
    lease_seconds=600,
    idempotency_key="installed-process-node-lease",
)
executions.start_node(
    registration.access,
    attempt,
    idempotency_key="installed-process-node-start",
)
root = filesystem.register_root(
    registration.access,
    path=physical_root,
    scope=FilesystemScope.PROJECT,
    mode=FilesystemMode.READ_WRITE,
    allow_remove=True,
    idempotency_key="installed-process-root",
)
stdin_ref = objects.put(b"installed process stdin", media_type="text/plain")
request = ProcessExecutionRequest(
    registration.project.project_ref,
    root.root_ref,
    ".",
    sys.executable,
    (
        "-c",
        "import pathlib,sys; data=sys.stdin.buffer.read(); pathlib.Path('generated.txt').write_bytes(data); sys.stdout.buffer.write(data.upper())",
    ),
    inherited_environment=("LANG",),
    stdin_ref=stdin_ref,
    timeout_seconds=10,
    stdout_limit_bytes=1024 * 1024,
    stderr_limit_bytes=1024 * 1024,
    network_policy=NetworkPolicy.INHERIT,
)
result = process.execute(
    registration.access,
    attempt,
    request,
    idempotency_key="installed-process-execute",
)
assert result.process_identity is not None
print(
    json.dumps(
        {
            "artifact_ref": result.artifact_ref.value,
            "call_id": result.tool_call_ref.call_id,
            "process_record_sha256": result.process_identity.record_sha256,
            "project_id": registration.project.project_ref.value,
            "record_sha256": result.record_sha256,
            "result_ref": result.result_ref.value,
            "root_id": root.root_ref.root_id,
            "stdout_ref": result.stdout_ref.value,
            "token": registration.access.token,
        },
        sort_keys=True,
    )
)
