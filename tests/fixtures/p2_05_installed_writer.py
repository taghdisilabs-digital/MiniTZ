"""Create P2-05 HTTP evidence using only an installed wheel."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from typing import cast

from minitz_os.engine import (
    FilesystemObjectStorageBackend,
    GraphRef,
    GraphService,
    HttpDestination,
    HttpExecutionRef,
    HttpExecutionRequest,
    HttpRedirectPolicy,
    HttpTlsPolicy,
    Node,
    NodeExecutionService,
    NodeRef,
    ProjectStore,
    RunService,
    StdlibHttpAdapter,
    TaskRevisionService,
)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:
        remaining = int(self.headers.get("Content-Length", "0"))
        chunks: list[bytes] = []
        while remaining:
            chunk = self.rfile.read(min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


database = Path(os.environ["MINITZ_DATABASE"])
objects = FilesystemObjectStorageBackend(Path(os.environ["MINITZ_OBJECT_ROOT"]))
server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    host, port = cast(tuple[str, int], server.server_address)
    origin = f"http://{host}:{port}"
    registration = ProjectStore(database).create_project(
        namespace="installed-http",
        display_name="Installed HTTP",
    )
    adapter = StdlibHttpAdapter(
        database,
        objects,
        supported_data_policy_refs=("policy://installed-http/data",),
        supported_egress_policy_refs=("policy://installed-http/egress",),
    )
    capabilities = tuple(sorted(adapter.register_capabilities(registration.access)))
    task = TaskRevisionService(database).create_task(
        registration.access,
        project_ref=registration.project.project_ref,
        idempotency_key="installed-http-task",
        task_type="transport.http.installed",
        objective="Verify installed HTTP restart",
        required_capabilities=capabilities,
        input_refs=(),
        output_contract={"result": "schema://minitz/http-execution-result/1"},
        constraints={},
        side_effect_authority="EXTERNAL_SIDE_EFFECT",
        data_policy_ref="policy://installed-http/data",
        egress_policy_ref="policy://installed-http/egress",
        evidence_requirements=("tool-call", "artifact", "content-ref"),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(registration.access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        registration.access,
        run.run_ref,
        owner_ref="controller://installed-http",
        lease_seconds=600,
    )
    graph_ref = GraphRef.new(registration.project.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "TOOL",
        capabilities,
        (),
        (),
        {"result": "schema://minitz/http-execution-result/1"},
        None,
        "EXTERNAL_SIDE_EFFECT",
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
        owner_ref="executor://installed-http",
        lease_seconds=600,
        idempotency_key="installed-http-node-lease",
    )
    executions.start_node(registration.access, attempt, idempotency_key="installed-http-node-start")
    destination = adapter.register_destination(
        registration.access,
        HttpDestination.create(
            registration.project.project_ref,
            origin=origin,
            allowed_path_prefixes=("/api",),
            auth_profile_ref=None,
            auth_header_name=None,
            data_policy_ref="policy://installed-http/data",
            egress_policy_ref="policy://installed-http/egress",
            tls_policy=HttpTlsPolicy.ALLOW_PLAINTEXT,
        ),
        idempotency_key="installed-http-destination",
    )
    body = objects.put(b"installed-http-binary\x00response", media_type="application/octet-stream")
    execution_ref = HttpExecutionRef.new(registration.project.project_ref)
    request = HttpExecutionRequest(
        registration.project.project_ref,
        execution_ref,
        destination.destination_ref,
        task.task_ref,
        task.canonical_digest,
        attempt.run_ref,
        attempt.node_ref,
        attempt.attempt_id,
        attempt.fence,
        "policy://installed-http/data",
        "policy://installed-http/egress",
        "POST",
        "/api/echo",
        {},
        {},
        {},
        body,
        HttpRedirectPolicy.NONE,
        0,
        1024 * 1024,
        30,
        body.digest,
    )
    result = adapter.execute(
        registration.access,
        attempt,
        request,
        secret_values={},
        idempotency_key="installed-http-execute",
    )
    print(
        json.dumps(
            {
                "execution_id": execution_ref.execution_id,
                "project_id": registration.project.project_ref.value,
                "record_sha256": result.record_sha256,
                "response_artifact_ref": result.response_artifact_ref.value if result.response_artifact_ref is not None else None,
                "response_digest": result.response_ref.digest if result.response_ref is not None else None,
                "token": registration.access.token,
                "tool_call_id": result.tool_call_ref.call_id,
            },
            sort_keys=True,
        )
    )
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
