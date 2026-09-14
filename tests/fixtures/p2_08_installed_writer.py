"""Create durable P2-08 PostgreSQL evidence through an installed wheel."""

from __future__ import annotations

import json
import os
from pathlib import Path

from minitz_os.engine import (
    DatabaseConnection,
    DatabaseExecutionBinding,
    DatabaseOperationRef,
    DatabaseQueryMode,
    DatabaseQueryRequest,
    DatabaseRestrictions,
    DatabaseTlsConfig,
    DatabaseTlsMode,
    FilesystemObjectStorageBackend,
    GraphRef,
    GraphService,
    LibpqPostgreSQLAdapter,
    Node,
    NodeExecutionService,
    NodeRef,
    ProjectStore,
    RunService,
    TaskRevisionService,
)


def main() -> None:
    database = Path(os.environ["MINITZ_DATABASE"])
    object_root = Path(os.environ["MINITZ_OBJECT_ROOT"])
    evidence_path = Path(os.environ["MINITZ_EVIDENCE"])
    registration = ProjectStore(database).create_project(
        namespace="p2-08-installed",
        display_name="P2-08 Installed",
    )
    objects = FilesystemObjectStorageBackend(object_root)
    adapter = LibpqPostgreSQLAdapter(database, objects)
    capabilities = tuple(sorted(adapter.register_capabilities(registration.access)))
    auth_ref = "secret://database/installed-p2-08"
    connection = DatabaseConnection.create_project(
        registration.project.project_ref,
        endpoint_identity=f"postgresql-endpoint://127.0.0.1:{os.environ['MINITZ_PGPORT']}",
        database_identity=f"postgresql-database://installed/{os.environ['MINITZ_PGDATABASE']}",
        auth_profile_ref=auth_ref,
        tls=DatabaseTlsConfig(DatabaseTlsMode.ALLOW_LOCAL_PLAINTEXT),
        restrictions=DatabaseRestrictions(
            (DatabaseQueryMode.READ_ONLY,),
            allow_transactions=False,
            allow_migrations=False,
            production=False,
        ),
    )
    adapter.register_connection(registration.access, connection, idempotency_key="installed-connection")
    task = TaskRevisionService(database).create_task(
        registration.access,
        project_ref=registration.project.project_ref,
        idempotency_key="installed-postgresql-task",
        task_type="database.postgresql",
        objective="Verify installed PostgreSQL adapter restart",
        required_capabilities=capabilities,
        input_refs=(),
        output_contract={"result": "schema://minitz/postgresql-result/1"},
        constraints={"database.persist_result": True},
        side_effect_authority="EXTERNAL_SIDE_EFFECT",
        data_policy_ref="policy://installed/postgresql-data",
        egress_policy_ref="policy://installed/postgresql-egress",
        evidence_requirements=("tool-call", "artifact", "content-ref"),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(registration.access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        registration.access,
        run.run_ref,
        owner_ref="controller://installed-postgresql",
        lease_seconds=300,
    )
    graph_ref = GraphRef.new(registration.project.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "TOOL",
        capabilities,
        (),
        (),
        {"result": "schema://minitz/postgresql-result/1"},
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
        owner_ref="executor://installed-postgresql",
        lease_seconds=300,
        idempotency_key="installed-postgresql-node",
    )
    executions.start_node(
        registration.access,
        attempt,
        idempotency_key="installed-postgresql-start",
    )
    statement_ref = objects.put(
        b"SELECT $1::text AS installed_value",
        media_type="application/sql",
    )
    parameter_ref = objects.put(
        json.dumps("installed-restart").encode(),
        media_type="application/json",
    )
    operation_ref = DatabaseOperationRef.new(registration.project.project_ref)
    result = adapter.query(
        registration.access,
        attempt,
        DatabaseQueryRequest(
            operation_ref,
            connection.connection_ref,
            DatabaseExecutionBinding.from_attempt(attempt),
            statement_ref,
            (parameter_ref,),
            DatabaseQueryMode.READ_ONLY,
            10,
            10,
            1024 * 1024,
            persist_result=True,
        ),
        auth_values={
            auth_ref: {
                "username": os.environ["MINITZ_PGUSER"],
                "password": os.environ["MINITZ_PGPASSWORD"],
            }
        },
        idempotency_key="installed-postgresql-query",
    )
    assert result.success and result.result_ref is not None
    evidence_path.write_text(
        json.dumps(
            {
                "operation_id": operation_ref.operation_id,
                "project_ref": registration.project.project_ref.value,
                "receipt_digest": result.receipt_ref.digest,
                "result_digest": result.result_ref.digest,
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    adapter.close()
    print(registration.access.token)


if __name__ == "__main__":
    main()
