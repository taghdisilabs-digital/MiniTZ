"""Create durable P2-07 browser evidence through an installed wheel."""

from __future__ import annotations

import json
import os
from pathlib import Path

from biella import (
    BrowserAction,
    BrowserActionRef,
    BrowserActionType,
    BrowserExecutionBinding,
    BrowserSessionRef,
    BrowserSessionSpec,
    BrowserSideEffect,
    CapabilityRef,
    FilesystemObjectStorageBackend,
    GraphRef,
    GraphService,
    HttpDestination,
    HttpTlsPolicy,
    Node,
    NodeExecutionService,
    NodeRef,
    ProjectStore,
    ReferenceBrowserAdapter,
    RunService,
    StdlibHttpAdapter,
    TaskRevisionService,
)


def main() -> None:
    database = Path(os.environ["BIELLA_DATABASE"])
    object_root = Path(os.environ["BIELLA_OBJECT_ROOT"])
    evidence_path = Path(os.environ["BIELLA_EVIDENCE"])
    registration = ProjectStore(database).create_project(namespace="p2-07-installed", display_name="P2-07 Installed")
    project_ref = registration.project.project_ref
    objects = FilesystemObjectStorageBackend(object_root)
    data_policy = "policy://installed/browser-data"
    egress_policy = "policy://installed/browser-egress"
    http = StdlibHttpAdapter(
        database,
        objects,
        supported_data_policy_refs=(data_policy,),
        supported_egress_policy_refs=(egress_policy,),
    )
    http.register_capabilities(registration.access)
    destination = http.register_destination(
        registration.access,
        HttpDestination.create(
            project_ref,
            origin="http://installed.invalid",
            allowed_path_prefixes=("/app",),
            auth_profile_ref=None,
            auth_header_name=None,
            data_policy_ref=data_policy,
            egress_policy_ref=egress_policy,
            tls_policy=HttpTlsPolicy.ALLOW_PLAINTEXT,
        ),
        idempotency_key="installed-browser-destination",
    )
    adapter = ReferenceBrowserAdapter(database, objects, http)
    capabilities = tuple(sorted(adapter.register_capabilities(registration.access)))
    task = TaskRevisionService(database).create_task(
        registration.access,
        project_ref=project_ref,
        idempotency_key="installed-browser-task",
        task_type="browser.automation",
        objective="Verify installed browser adapter restart",
        required_capabilities=capabilities,
        input_refs=(),
        output_contract={"result": "schema://biella/browser-action-result/1"},
        constraints={},
        side_effect_authority="EXTERNAL_SIDE_EFFECT",
        data_policy_ref=data_policy,
        egress_policy_ref=egress_policy,
        evidence_requirements=("tool-call", "artifact", "content-ref"),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(registration.access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        registration.access,
        run.run_ref,
        owner_ref="controller://installed-browser",
        lease_seconds=300,
    )
    graph_ref = GraphRef.new(project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "TOOL",
        capabilities,
        (),
        (),
        {"result": "schema://biella/browser-action-result/1"},
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
        owner_ref="executor://installed-browser",
        lease_seconds=300,
        idempotency_key="installed-browser-node",
    )
    executions.start_node(registration.access, attempt, idempotency_key="installed-browser-start")
    binding = BrowserExecutionBinding(
        project_ref,
        task.task_ref,
        task.canonical_digest,
        run.run_ref,
        node.node_ref,
        attempt.attempt_id,
        attempt.fence,
        data_policy,
        egress_policy,
    )
    session_ref = BrowserSessionRef.new(project_ref)
    state = adapter.create_session(
        registration.access,
        attempt,
        BrowserSessionSpec(
            session_ref,
            binding,
            CapabilityRef("browser.open", "1.0.0"),
            None,
            (destination.destination_ref,),
            "installed-reference",
            (),
            "browser-egress://installed/reference-v1",
            5.0,
        ),
        secret_values={},
        idempotency_key="installed-browser-open",
    )
    action_ref = BrowserActionRef.new(project_ref)
    result = adapter.navigate(
        registration.access,
        attempt,
        BrowserAction(
            action_ref,
            binding,
            state.identity,
            state.page_ref,
            CapabilityRef("browser.navigate", "1.0.0"),
            BrowserActionType.NAVIGATE,
            "/app",
            None,
            None,
            destination.destination_ref,
            BrowserSideEffect.READ_ONLY,
            5.0,
            postcondition={"url": "http://installed.invalid/app", "generation": 1},
        ),
        secret_values={},
        idempotency_key="installed-browser-navigate",
    )
    assert result.output_ref is not None and result.page_ref is not None
    evidence_path.write_text(
        json.dumps(
            {
                "action_id": action_ref.action_id,
                "output_digest": result.output_ref.digest,
                "page_url": result.page_ref.current_url,
                "project_ref": project_ref.value,
                "receipt_artifact": result.receipt_artifact_ref.value,
                "session_id": session_ref.session_id,
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(registration.access.token)


if __name__ == "__main__":
    main()
