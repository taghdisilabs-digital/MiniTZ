"""Create P2-01 filesystem evidence using only an installed wheel."""

from __future__ import annotations

import json
import os
from pathlib import Path

from biella import (
    FilesystemAdapter,
    FilesystemMode,
    FilesystemObjectStorageBackend,
    FilesystemScope,
    GraphRef,
    GraphService,
    Node,
    NodeExecutionService,
    NodeRef,
    ProjectStore,
    RunService,
    TaskRevisionService,
)


database = Path(os.environ["BIELLA_DATABASE"])
physical_root = Path(os.environ["BIELLA_FILESYSTEM_ROOT"])
object_root = Path(os.environ["BIELLA_OBJECT_ROOT"])
registration = ProjectStore(database).create_project(
    namespace="installed-filesystem",
    display_name="Installed Filesystem",
)
objects = FilesystemObjectStorageBackend(object_root)
adapter = FilesystemAdapter(database, objects)
implementations = adapter.register_capabilities(registration.access)
capabilities = tuple(sorted(implementations))
task = TaskRevisionService(database).create_task(
    registration.access,
    project_ref=registration.project.project_ref,
    idempotency_key="installed-filesystem-task",
    task_type="filesystem.installed",
    objective="Verify installed filesystem restart",
    required_capabilities=capabilities,
    input_refs=(),
    output_contract={"result": "schema://biella/filesystem-result/1"},
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
    owner_ref="controller://installed-filesystem",
    lease_seconds=600,
)
graph_ref = GraphRef.new(registration.project.project_ref)
node = Node(
    NodeRef.new(graph_ref),
    "TOOL",
    capabilities,
    (),
    (),
    {"result": "schema://biella/filesystem-result/1"},
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
    owner_ref="executor://installed-filesystem",
    lease_seconds=600,
    idempotency_key="installed-filesystem-node-lease",
)
executions.start_node(
    registration.access,
    attempt,
    idempotency_key="installed-filesystem-node-start",
)
root = adapter.register_root(
    registration.access,
    path=physical_root,
    scope=FilesystemScope.PROJECT,
    mode=FilesystemMode.READ_WRITE,
    allow_remove=True,
    idempotency_key="installed-filesystem-root",
)
source = objects.put(b"installed-wheel-filesystem", media_type="text/plain")
written = adapter.write(
    registration.access,
    attempt,
    root_ref=root.root_ref,
    path="installed.txt",
    content_ref=source,
    idempotency_key="installed-filesystem-write",
)
read = adapter.read(
    registration.access,
    attempt,
    root_ref=root.root_ref,
    path="installed.txt",
    media_type="text/plain",
    idempotency_key="installed-filesystem-read",
)
print(
    json.dumps(
        {
            "artifact_ref": read.artifact_ref.value,
            "call_id": read.tool_call_ref.call_id,
            "content_ref": read.output_ref.value,
            "project_id": registration.project.project_ref.value,
            "record_sha256": read.record_sha256,
            "root_id": root.root_ref.root_id,
            "token": registration.access.token,
            "write_artifact_ref": written.artifact_ref.value,
        },
        sort_keys=True,
    )
)
