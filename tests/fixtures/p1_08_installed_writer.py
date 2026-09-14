"""Create durable P1-08 scheduler state using only the installed wheel."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from minitz_os.engine import (
    Capability,
    CapabilityRef,
    CapabilityRegistry,
    FakeResourceObserver,
    GraphRef,
    GraphService,
    Node,
    NodeExecutionService,
    NodeRef,
    ProjectStore,
    Resource,
    ResourceClaim,
    ResourceFitRequest,
    ResourceHealth,
    ResourceObservation,
    ResourceQuantity,
    ResourceService,
    RunService,
    SchedulerService,
    SchedulingRequest,
    TaskRevisionService,
)


database = Path(os.environ["MINITZ_DATABASE"])
registration = ProjectStore(database).create_project(
    namespace="installed-scheduler",
    display_name="Installed Scheduler",
)
capabilities = CapabilityRegistry(database)
capability = capabilities.register(
    Capability(CapabilityRef("scheduler.installed", "1.0.0"), "Installed scheduling")
)
tasks = TaskRevisionService(database)
task = tasks.create_task(
    registration.access,
    project_ref=registration.project.project_ref,
    idempotency_key="installed-scheduler-task",
    task_type="scheduler.installed",
    objective="Verify installed scheduler restart",
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
attempt = runs.acquire_run_lease(
    registration.access,
    run.run_ref,
    owner_ref="controller://installed-scheduler",
    lease_seconds=300,
)
graph_ref = GraphRef.new(registration.project.project_ref)
node_refs = (NodeRef.new(graph_ref), NodeRef.new(graph_ref))
nodes = tuple(
    Node(
        node_ref,
        "SPECIALIST_TASK",
        (capability.capability_ref,),
        (),
        (),
        {},
        None,
        "READ_ONLY",
        {},
        (),
    )
    for node_ref in node_refs
)
GraphService(database).create_graph(
    registration.access,
    graph_ref=graph_ref,
    task_ref=task.task_ref,
    expected_task_digest=task.canonical_digest,
    run_ref=run.run_ref,
    nodes=nodes,
    compiler_identity=None,
    compiler_version=None,
    authority_attempt=attempt,
)
NodeExecutionService(database).prepare_run(registration.access, run.run_ref)
resource = Resource.create(
    registration.project.project_ref,
    resource_kind="runtime.host",
    locality_ref="host://installed-scheduler",
)
resources = ResourceService(database)
resources.register_resource(registration.access, resource)
quantity = ResourceQuantity.derived(1, "count", "test://installed/scheduler")
resources.observe_resource(
    registration.access,
    resource.resource_ref,
    FakeResourceObserver(
        (
            ResourceObservation(
                observed_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                fresh_for_seconds=300,
                health=ResourceHealth.HEALTHY,
                physical_capacity={"cpu.logical_count": ResourceQuantity.measured(1, "count", "test://installed/scheduler")},
                effective_capacity={"cpu.logical_count": quantity},
                available_capacity={"cpu.logical_count": quantity},
            ),
        )
    ),
)
scheduler = SchedulerService(database)
claim = ResourceClaim(
    resource.resource_ref,
    ResourceFitRequest(required_available={"cpu.logical_count": 1}),
    {"cpu.logical_count": 1},
)
allocation = scheduler.reserve(
    registration.access,
    SchedulingRequest(node_refs[0], (claim,)),
    authority_attempt=attempt,
    owner_ref="executor://installed-scheduler",
    lease_seconds=120,
    idempotency_key="installed-reserve",
)
waiting = SchedulingRequest(node_refs[1], (claim,))
result = scheduler.schedule_cycle(
    registration.access,
    (waiting,),
    authority_attempt=attempt,
    owner_ref="executor://installed-waiting",
    lease_seconds=120,
)
assert result.deferred == (node_refs[1],)
print(
    json.dumps(
        {
            "allocation_id": allocation.allocation_ref.allocation_id,
            "project_id": registration.project.project_ref.value,
            "request_digest": waiting.semantic_digest,
            "token": registration.access.token,
        },
        sort_keys=True,
    )
)
