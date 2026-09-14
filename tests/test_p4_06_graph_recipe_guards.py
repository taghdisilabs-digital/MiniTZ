from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from minitz_os.engine.capability import CapabilityRef
from minitz_os.engine.graph import Graph, GraphRef, GraphSideEffectError, Node, NodeRef
from minitz_os.engine.production_recipe_learning import (
    RecipeScope,
    extract_from_graph,
    instantiate_graph,
)
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.run import RunRef
from minitz_os.engine.task import Task, TaskRef


_CREATED_AT = "2026-09-01T00:00:00+00:00"
_CAPABILITY = CapabilityRef("production.recipe", "1.0.0")
_OPTIONAL_CONDITION = "condition://production/optional-validation"


def _task(
    project_ref: ProjectRef,
    task_digit: str,
    *,
    side_effect_authority: str = "READ_ONLY",
    identity_metadata: bool = False,
) -> Task:
    constraints: dict[str, str | int | float | bool | None] = {
        "quality": "production"
    }
    resource_hints: dict[str, str | int | float | bool | None] = {"cpu": 1}
    if identity_metadata:
        constraints.update(
            {
                "provider": "provider-source-only",
                "host": "host-source-only",
                "path": "/source-only/workspace",
                "project_id": project_ref.value,
            }
        )
        resource_hints.update(
            {
                "provider": "provider-source-only",
                "host": "host-source-only",
                "path": "/source-only/workspace",
            }
        )
    return Task(
        task_ref=TaskRef(project_ref, f"tsk_{task_digit * 32}", 1),
        idempotency_key=f"recipe-task-{task_digit}",
        task_type="production.recipe",
        objective="Produce and validate one exact production result.",
        required_capabilities=(_CAPABILITY,),
        input_refs=(),
        output_contract={"result": "schema://production/result"},
        constraints=constraints,
        side_effect_authority=side_effect_authority,
        data_policy_ref=None,
        egress_policy_ref=None,
        evidence_requirements=("artifact.real",),
        acceptance_criteria=("validation.pass",),
        resource_hints=resource_hints,
        created_at=_CREATED_AT,
    )


def _node(
    graph_ref: GraphRef,
    node_digit: str,
    executor_kind: str,
    *,
    dependencies: tuple[NodeRef, ...] = (),
    condition_ref: str | None = None,
    side_effect_requirement: str = "READ_ONLY",
    identity_metadata: bool = False,
) -> Node:
    resource_hints: dict[str, str | int | float | bool | None] = {"cpu": 1}
    if identity_metadata:
        resource_hints.update(
            {
                "provider": "provider-source-only",
                "host": "host-source-only",
                "path": "/source-only/workspace",
                "node_id": f"nod_{node_digit * 32}",
            }
        )
    return Node(
        node_ref=NodeRef(graph_ref, f"nod_{node_digit * 32}"),
        executor_kind=executor_kind,
        required_capabilities=(_CAPABILITY,),
        dependencies=dependencies,
        input_bindings=(),
        output_contract={"result": f"schema://production/{executor_kind.lower()}"},
        condition_ref=condition_ref,
        side_effect_requirement=side_effect_requirement,
        resource_hints=resource_hints,
        evidence_requirements=(f"evidence.{executor_kind.lower()}",),
    )


def _source_graph(
    project_ref: ProjectRef,
    task: Task,
    *,
    write_requirement: str = "READ_ONLY",
) -> Graph:
    graph_ref = GraphRef(project_ref, "gph_" + "a" * 32, 1)
    prepare = _node(
        graph_ref,
        "1",
        "PREPARE",
        side_effect_requirement=write_requirement,
        identity_metadata=True,
    )
    build = _node(
        graph_ref,
        "2",
        "BUILD",
        dependencies=(prepare.node_ref,),
        side_effect_requirement=write_requirement,
    )
    validate = _node(
        graph_ref,
        "3",
        "VALIDATE",
        dependencies=(prepare.node_ref,),
        condition_ref=_OPTIONAL_CONDITION,
        side_effect_requirement=write_requirement,
    )
    publish = _node(
        graph_ref,
        "4",
        "ASSEMBLE",
        dependencies=(build.node_ref, validate.node_ref),
        side_effect_requirement=write_requirement,
    )
    return Graph.build(
        graph_ref,
        task.task_ref,
        task.canonical_digest,
        RunRef(project_ref, "run_" + "b" * 32),
        (publish, validate, build, prepare),
        created_at=_CREATED_AT,
        compiler_identity="compiler://source-host-only",
        compiler_version="1.0.0",
    )


def _semantic_payload(recipe: object) -> Mapping[str, Any]:
    payload = getattr(recipe, "semantic_payload")
    value = payload() if callable(payload) else payload
    assert isinstance(value, Mapping)
    return value


def _by_executor(graph: Graph) -> dict[str, Node]:
    return {node.executor_kind: node for node in graph.nodes}


def test_engine_recipe_normalizes_real_task_graph_without_losing_semantics() -> None:
    source_project = ProjectRef.new()
    source_task = _task(source_project, "c", identity_metadata=True)
    source_graph = _source_graph(source_project, source_task)

    recipe = extract_from_graph(
        source_project,
        source_task,
        source_graph,
        scope=RecipeScope.ENGINE,
        applicability={"kind": "production"},
        parameter_schema={},
        learning_evidence=("artifact://recipe-learning/exact",),
    )
    payload = _semantic_payload(recipe)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    for forbidden in (
        source_project.value,
        source_task.task_ref.task_id,
        source_graph.run_ref.run_id,
        source_graph.graph_ref.graph_id,
        *(node.node_ref.node_id for node in source_graph.nodes),
        "provider-source-only",
        "host-source-only",
        "/source-only/workspace",
        "compiler://source-host-only",
    ):
        assert forbidden not in serialized
    assert _CAPABILITY.value in serialized
    assert _OPTIONAL_CONDITION in serialized
    assert "artifact.real" in serialized
    assert "validation.pass" in serialized
    for node in source_graph.nodes:
        assert node.evidence_requirements[0] in serialized


def test_instantiate_graph_preserves_dag_optional_branch_and_parallelism() -> None:
    source_project = ProjectRef.new()
    source_task = _task(source_project, "d", identity_metadata=True)
    source_graph = _source_graph(source_project, source_task)
    recipe = extract_from_graph(
        source_project,
        source_task,
        source_graph,
        scope=RecipeScope.ENGINE,
        applicability={"kind": "production"},
        parameter_schema={},
        learning_evidence=("artifact://recipe-learning/exact",),
    )

    target_project = ProjectRef.new()
    target_task = _task(target_project, "e")
    target_run_ref = RunRef(target_project, "run_" + "f" * 32)
    target_graph_ref = GraphRef(target_project, "gph_" + "9" * 32, 1)
    instantiated = instantiate_graph(
        target_project,
        recipe,
        target_task,
        target_run_ref,
        target_graph_ref,
        input_bindings=(),
    )

    assert isinstance(instantiated, Graph)
    assert instantiated.graph_ref == target_graph_ref
    assert instantiated.task_ref == target_task.task_ref
    assert instantiated.task_digest == target_task.canonical_digest
    assert instantiated.run_ref == target_run_ref
    assert instantiated.prior_ref is None
    assert all(node.graph_ref == target_graph_ref for node in instantiated.nodes)
    assert {node.node_ref for node in instantiated.nodes}.isdisjoint(
        {node.node_ref for node in source_graph.nodes}
    )

    nodes = _by_executor(instantiated)
    dependency_kinds = {
        kind: {instantiated_node.executor_kind for instantiated_node in instantiated.nodes if instantiated_node.node_ref in node.dependencies}
        for kind, node in nodes.items()
    }
    assert dependency_kinds == {
        "PREPARE": set(),
        "BUILD": {"PREPARE"},
        "VALIDATE": {"PREPARE"},
        "ASSEMBLE": {"BUILD", "VALIDATE"},
    }
    assert nodes["VALIDATE"].condition_ref == _OPTIONAL_CONDITION
    assert nodes["BUILD"].node_ref not in nodes["VALIDATE"].dependencies
    assert nodes["VALIDATE"].node_ref not in nodes["BUILD"].dependencies
    assert all(node.required_capabilities == (_CAPABILITY,) for node in instantiated.nodes)
    assert all(node.evidence_requirements for node in instantiated.nodes)

    ready = instantiated.ready_set(
        {nodes["PREPARE"].node_ref: "SUCCEEDED"},
        {_OPTIONAL_CONDITION: True},
        target_task,
    )
    assert set(ready) == {nodes["BUILD"].node_ref, nodes["VALIDATE"].node_ref}
    skipped_ready = instantiated.ready_set(
        {
            nodes["PREPARE"].node_ref: "SUCCEEDED",
            nodes["BUILD"].node_ref: "SUCCEEDED",
        },
        {_OPTIONAL_CONDITION: False},
        target_task,
    )
    assert skipped_ready == (nodes["ASSEMBLE"].node_ref,)


def test_instantiate_graph_rejects_recipe_side_effect_escalation() -> None:
    source_project = ProjectRef.new()
    source_task = _task(
        source_project,
        "6",
        side_effect_authority="CANDIDATE_WRITE",
    )
    source_graph = _source_graph(
        source_project,
        source_task,
        write_requirement="CANDIDATE_WRITE",
    )
    recipe = extract_from_graph(
        source_project,
        source_task,
        source_graph,
        scope=RecipeScope.ENGINE,
        applicability={"kind": "production"},
        parameter_schema={},
        learning_evidence=("artifact://recipe-learning/write",),
    )

    target_project = ProjectRef.new()
    read_only_task = _task(target_project, "7", side_effect_authority="READ_ONLY")
    with pytest.raises(GraphSideEffectError):
        instantiate_graph(
            target_project,
            recipe,
            read_only_task,
            RunRef(target_project, "run_" + "8" * 32),
            GraphRef(target_project, "gph_" + "8" * 32, 1),
            input_bindings=(),
        )
