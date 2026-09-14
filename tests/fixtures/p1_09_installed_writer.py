"""Create durable P1-09 routing state using only the installed wheel."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from minitz_os.engine import (
    Capability,
    CapabilityImplementation,
    CapabilityImplementationRef,
    CapabilityImplementationRegistry,
    CapabilityRef,
    CapabilityRegistry,
    FakeResourceObserver,
    GraphRef,
    GraphService,
    ImplementationKind,
    Node,
    NodeExecutionService,
    NodeRef,
    ProjectStore,
    Resource,
    ResourceFitRequest,
    ResourceHealth,
    ResourceObservation,
    ResourceQuantity,
    ResourceService,
    RoutingPolicy,
    RoutingRequest,
    RoutingService,
    RunService,
    TaskRevisionService,
)


database = Path(os.environ["MINITZ_DATABASE"])
registration = ProjectStore(database).create_project(
    namespace="installed-routing",
    display_name="Installed Routing",
)
capability = CapabilityRegistry(database).register(
    Capability(CapabilityRef("routing.installed", "1.0.0"), "Installed routing")
)
task = TaskRevisionService(database).create_task(
    registration.access,
    project_ref=registration.project.project_ref,
    idempotency_key="installed-routing-task",
    task_type="routing.installed",
    objective="Verify installed routing restart",
    required_capabilities=(capability.capability_ref,),
    input_refs=(),
    output_contract={"result": "contract://installed/result"},
    constraints={},
    side_effect_authority="READ_ONLY",
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
    owner_ref="controller://installed-routing",
    lease_seconds=300,
)
graph_ref = GraphRef.new(registration.project.project_ref)
node = Node(
    NodeRef.new(graph_ref),
    "SPECIALIST_TASK",
    (capability.capability_ref,),
    (),
    (),
    {"result": "contract://installed/result"},
    None,
    "READ_ONLY",
    {},
    (),
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
    authority_attempt=attempt,
)
NodeExecutionService(database).prepare_run(registration.access, run.run_ref)
resource = Resource.create(
    registration.project.project_ref,
    resource_kind="runtime.host",
    locality_ref="host://installed-routing",
)
resources = ResourceService(database)
resources.register_resource(registration.access, resource)
quantity = ResourceQuantity.derived(2, "count", "test://installed/routing")
resources.observe_resource(
    registration.access,
    resource.resource_ref,
    FakeResourceObserver(
        (
            ResourceObservation(
                observed_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                fresh_for_seconds=300,
                health=ResourceHealth.HEALTHY,
                physical_capacity={"cpu.logical_count": ResourceQuantity.measured(2, "count", "test://installed/routing")},
                effective_capacity={"cpu.logical_count": quantity},
                available_capacity={"cpu.logical_count": quantity},
            ),
        ),
        observer_id="test.installed.routing",
    ),
)
implementation = CapabilityImplementation(
    CapabilityImplementationRef.new(registration.project.project_ref),
    capability.capability_ref,
    "1.0.0",
    ImplementationKind.MODEL,
    "adapter://installed-routing",
    "runtime://installed-routing",
    model_ref="model://installed-routing",
    features=("text",),
    input_features=("text",),
    output_features=("text",),
    resource_kinds=("runtime.host",),
    resource_fit=ResourceFitRequest(required_available={"cpu.logical_count": 1}),
)
implementation = CapabilityImplementationRegistry(database).register(
    registration.access,
    implementation,
    idempotency_key="installed-implementation",
)
decision = RoutingService(database).route(
    registration.access,
    RoutingRequest(
        task.task_ref,
        node.node_ref,
        capability.capability_ref,
        attempt,
        RoutingPolicy(registration.project.project_ref, "routing-policy://installed"),
        (resource.resource_ref,),
        required_features=("text",),
        required_input_features=("text",),
        required_output_features=("text",),
        idempotency_key="installed-route",
    ),
)
print(
    json.dumps(
        {
            "decision_id": decision.decision_ref.decision_id,
            "implementation_id": implementation.implementation_ref.implementation_id,
            "project_id": registration.project.project_ref.value,
            "record_sha256": decision.record_sha256,
            "task_digest": task.canonical_digest,
            "token": registration.access.token,
        },
        sort_keys=True,
    )
)
