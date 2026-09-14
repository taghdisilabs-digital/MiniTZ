from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from minitz_os.engine.artifact import ArtifactService, ContentRef, SourceRef
from minitz_os.engine.capability import Capability, CapabilityRef, CapabilityRegistry
from minitz_os.engine.graph import (
    Graph,
    GraphAuthorityError,
    GraphConflictError,
    GraphContractError,
    GraphIntegrityError,
    GraphRef,
    GraphScopeError,
    GraphService,
    GraphSideEffectError,
    Node,
    NodeInputBinding,
    NodeRef,
    validate_dag,
)
from minitz_os.engine.migration import QuarantineRef
from minitz_os.engine.project import ProjectAccess, ProjectRef, ProjectStore
from minitz_os.engine.run import ExecutionAttempt, RunRef, RunService
from minitz_os.engine.task import Task, TaskRevisionService


ROOT = Path(__file__).resolve().parents[1]


class GraphContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "minitz.sqlite3"
        self.projects = ProjectStore(self.database_path)
        alpha = self.projects.create_project(namespace="alpha", display_name="Alpha")
        beta = self.projects.create_project(namespace="beta", display_name="Beta")
        self.alpha = alpha.project
        self.alpha_access = alpha.access
        self.beta = beta.project
        self.beta_access = beta.access
        self.capabilities = CapabilityRegistry(self.database_path)
        self.capability_ref = self.capabilities.register(
            Capability(CapabilityRef("graph.execute", "1.0.0"), "Execute Graph Node")
        ).capability_ref
        self.tasks = TaskRevisionService(self.database_path)
        self.task = self._create_task("graph-task")
        self.runs = RunService(self.database_path)
        self.run_record = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        self.authority_attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            self.run_record.run_ref,
            owner_ref="planner://test-authority",
            lease_seconds=60,
        )
        self.artifacts = ArtifactService(self.database_path)
        self.graphs = GraphService(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_task(
        self,
        idempotency_key: str,
        *,
        access: ProjectAccess | None = None,
        project_ref: ProjectRef | None = None,
        side_effect_authority: str = "READ_ONLY",
    ) -> Task:
        selected_access = self.alpha_access if access is None else access
        selected_project_ref = self.alpha.project_ref if project_ref is None else project_ref
        return self.tasks.create_task(
            selected_access,
            project_ref=selected_project_ref,
            idempotency_key=idempotency_key,
            task_type="graph.execute",
            objective="Execute an immutable dynamic Graph",
            required_capabilities=(self.capability_ref,),
            input_refs=(), output_contract={}, constraints={},
            side_effect_authority=side_effect_authority,
            data_policy_ref=None, egress_policy_ref=None,
            evidence_requirements=(), acceptance_criteria=(), resource_hints={},
        )

    def _node(
        self,
        graph_ref: GraphRef,
        label: str,
        *,
        dependencies: tuple[NodeRef, ...] = (),
        inputs: tuple[NodeInputBinding, ...] = (),
        executor_kind: str = "SPECIALIST_TASK",
        side_effect: str = "READ_ONLY",
        condition_ref: str | None = None,
        capability_refs: tuple[CapabilityRef, ...] | None = None,
    ) -> Node:
        return Node(
            node_ref=NodeRef(graph_ref, f"nod_{label * 32}"),
            executor_kind=executor_kind,
            required_capabilities=(self.capability_ref,) if capability_refs is None else capability_refs,
            dependencies=dependencies,
            input_bindings=inputs,
            output_contract={"result": "schema://graph/result"},
            condition_ref=condition_ref,
            side_effect_requirement=side_effect,
            resource_hints={"cpu": 1},
            evidence_requirements=("record exact output",),
        )

    def _create_graph(self, nodes: tuple[Node, ...], graph_ref: GraphRef) -> Graph:
        return self.graphs.create_graph(
            self.alpha_access,
            graph_ref=graph_ref,
            task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            run_ref=self.run_record.run_ref,
            nodes=nodes,
            compiler_identity="planner://minitz/kernel",
            compiler_version="1.0.0",
            authority_attempt=self.authority_attempt,
        )

    def test_t01_one_node_graph_round_trips(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        node = self._node(graph_ref, "a")
        graph = self._create_graph((node,), graph_ref)
        self.assertEqual(graph.topological_order(), (node.node_ref,))
        self.assertEqual(graph.ready_set({}, {}, self.task), (node.node_ref,))
        self.assertEqual(self.graphs.get_graph(self.alpha_access, graph_ref), graph)

    def test_t02_sequential_topology_and_ready_set_are_deterministic(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        first = self._node(graph_ref, "a")
        second = self._node(graph_ref, "b", dependencies=(first.node_ref,))
        graph = self._create_graph((second, first), graph_ref)
        self.assertEqual(graph.topological_order(), (first.node_ref, second.node_ref))
        self.assertEqual(graph.ready_set({}, {}, self.task), (first.node_ref,))
        self.assertEqual(
            graph.ready_set({first.node_ref: "SUCCEEDED"}, {}, self.task),
            (second.node_ref,),
        )

    def test_t03_fan_out_siblings_are_ready_together(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        root = self._node(graph_ref, "a")
        left = self._node(graph_ref, "b", dependencies=(root.node_ref,))
        right = self._node(graph_ref, "c", dependencies=(root.node_ref,))
        graph = self._create_graph((right, root, left), graph_ref)
        ready = graph.ready_set({root.node_ref: "SUCCEEDED"}, {}, self.task)
        self.assertEqual(ready, tuple(sorted((left.node_ref, right.node_ref), key=lambda item: item.node_id)))

    def test_t04_fan_in_waits_for_both_dependencies(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        root = self._node(graph_ref, "a")
        left = self._node(graph_ref, "b", dependencies=(root.node_ref,))
        right = self._node(graph_ref, "c", dependencies=(root.node_ref,))
        joined = self._node(graph_ref, "d", dependencies=(left.node_ref, right.node_ref))
        graph = self._create_graph((root, left, right, joined), graph_ref)
        self.assertNotIn(
            joined.node_ref,
            graph.ready_set({left.node_ref: "SUCCEEDED"}, {}, self.task),
        )
        self.assertIn(
            joined.node_ref,
            graph.ready_set(
                {left.node_ref: "SUCCEEDED", right.node_ref: "SUCCEEDED"},
                {},
                self.task,
            ),
        )

    def test_t05_cycle_self_cycle_and_missing_dependency_fail(self) -> None:
        for case in ("self", "direct_cycle", "indirect_cycle", "missing"):
            graph_ref = GraphRef.new(self.alpha.project_ref)
            a_ref = NodeRef(graph_ref, "nod_" + "a" * 32)
            b_ref = NodeRef(graph_ref, "nod_" + "b" * 32)
            c_ref = NodeRef(graph_ref, "nod_" + "c" * 32)
            missing = NodeRef(graph_ref, "nod_" + "f" * 32)
            nodes: tuple[Node, ...]
            if case == "self":
                nodes = (self._node(graph_ref, "a", dependencies=(a_ref,)),)
            elif case == "direct_cycle":
                nodes = (
                    self._node(graph_ref, "a", dependencies=(b_ref,)),
                    self._node(graph_ref, "b", dependencies=(a_ref,)),
                )
            elif case == "indirect_cycle":
                nodes = (
                    self._node(graph_ref, "a", dependencies=(c_ref,)),
                    self._node(graph_ref, "b", dependencies=(a_ref,)),
                    self._node(graph_ref, "c", dependencies=(b_ref,)),
                )
            else:
                nodes = (self._node(graph_ref, "a", dependencies=(missing,)),)
            with self.subTest(case=case), self.assertRaises(GraphContractError):
                self._create_graph(nodes, graph_ref)

    def test_t06_duplicate_node_fails_without_partial_rows(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        node = self._node(graph_ref, "a")
        with self.assertRaises(GraphContractError):
            self._create_graph((node, node), graph_ref)
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM graph_revisions").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0], 0)
        finally:
            connection.close()

    def test_t07_equivalent_semantics_have_stable_digest_and_order(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        a = self._node(graph_ref, "a")
        b = self._node(graph_ref, "b", dependencies=(a.node_ref,))
        first = Graph.build(
            graph_ref, self.task.task_ref, self.task.canonical_digest,
            self.run_record.run_ref, (a, b), created_at="2026-08-28T00:00:00+00:00",
        )
        second = Graph.build(
            graph_ref, self.task.task_ref, self.task.canonical_digest,
            self.run_record.run_ref, (b, a), created_at="2026-08-28T00:00:00+00:00",
        )
        self.assertEqual(first.semantic_digest, second.semantic_digest)
        self.assertEqual(first.topological_order(), second.topological_order())

    def test_t08_false_optional_condition_satisfies_downstream_dependency(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        optional = self._node(graph_ref, "a", condition_ref="condition://optional")
        downstream = self._node(graph_ref, "b", dependencies=(optional.node_ref,))
        graph = self._create_graph((optional, downstream), graph_ref)
        self.assertEqual(
            graph.ready_set({}, {"condition://optional": False}, self.task),
            (downstream.node_ref,),
        )
        with self.assertRaises(GraphContractError):
            graph.ready_set(
                {optional.node_ref: "FAILED"},
                {"condition://optional": False},
                self.task,
            )
        with self.assertRaises(GraphContractError):
            graph.ready_set({optional.node_ref: "PENDING"}, {}, self.task)
        with self.assertRaises(GraphContractError):
            graph.ready_set({}, {"condition://unknown": True}, self.task)
        with self.assertRaises(GraphContractError):
            graph.ready_set({}, {}, self._create_task("wrong-ready-task"))

    def test_t09_unknown_future_executor_kind_is_data(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        node = self._node(graph_ref, "a", executor_kind="QUANTUM_SCENE_COMPOSE")
        self.assertEqual(self._create_graph((node,), graph_ref).nodes[0].executor_kind, "QUANTUM_SCENE_COMPOSE")

    def test_t10_unknown_capability_ref_fails_closed(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        unknown = CapabilityRef("future.unknown", "99.0.0")
        with self.assertRaises(GraphContractError):
            self._create_graph((self._node(graph_ref, "a", capability_refs=(unknown,)),), graph_ref)

    def test_t11_node_cannot_escalate_task_side_effect_authority(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        with self.assertRaises(GraphSideEffectError):
            self._create_graph(
                (self._node(graph_ref, "a", side_effect="EXTERNAL_SIDE_EFFECT"),),
                graph_ref,
            )

    def test_t12_graph_binds_exact_project_task_digest_and_run(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        node = self._node(graph_ref, "a")
        with self.assertRaises(GraphContractError):
            self.graphs.create_graph(
                self.alpha_access, graph_ref=graph_ref, task_ref=self.task.task_ref,
                expected_task_digest="0" * 64, run_ref=self.run_record.run_ref, nodes=(node,),
                compiler_identity=None, compiler_version=None,
                authority_attempt=self.authority_attempt,
            )
        beta_task = self._create_task(
            "beta-task", access=self.beta_access, project_ref=self.beta.project_ref
        )
        beta_run = self.runs.create_run(self.beta_access, task_ref=beta_task.task_ref)
        with self.assertRaises(GraphScopeError):
            self.graphs.create_graph(
                self.alpha_access, graph_ref=graph_ref, task_ref=self.task.task_ref,
                expected_task_digest=self.task.canonical_digest,
                run_ref=beta_run.run_ref, nodes=(node,),
                compiler_identity=None, compiler_version=None,
                authority_attempt=self.authority_attempt,
            )

    def test_t13_exact_inputs_and_node_outputs_bind_without_quarantine(self) -> None:
        content = ContentRef.from_bytes(b"graph input", media_type="text/plain")
        source = SourceRef.git(
            self.alpha.project_ref, repository="https://example.invalid/graph.git",
            commit="1" * 40, tree="2" * 40,
        )
        artifact = self.artifacts.create_artifact(
            self.alpha_access, project_ref=self.alpha.project_ref,
            role="document.source", content_ref=content, source_refs=(source,),
            source_artifact_refs=(), source_content_refs=(),
            derivation_type="artifact.derived", metadata={},
        )
        task_input = self.artifacts.create_task_input_ref(
            self.alpha_access, project_ref=self.alpha.project_ref,
            identity=artifact.artifact_ref,
        )
        bound_task = self.tasks.create_task(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            idempotency_key="graph-bound-input-task",
            task_type="graph.execute",
            objective="Execute Graph with exact Task input",
            required_capabilities=(self.capability_ref,), input_refs=(task_input,),
            output_contract={}, constraints={}, side_effect_authority="READ_ONLY",
            data_policy_ref=None, egress_policy_ref=None,
            evidence_requirements=(), acceptance_criteria=(), resource_hints={},
        )
        bound_run = self.runs.create_run(
            self.alpha_access,
            task_ref=bound_task.task_ref,
        )
        bound_attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            bound_run.run_ref,
            owner_ref="planner://bound-input",
            lease_seconds=60,
        )
        graph_ref = GraphRef.new(self.alpha.project_ref)
        first = self._node(
            graph_ref, "a",
            inputs=(
                NodeInputBinding.from_identity("artifact", self.alpha.project_ref, artifact.artifact_ref),
                NodeInputBinding.from_identity("source", self.alpha.project_ref, source),
                NodeInputBinding.from_identity("content", self.alpha.project_ref, content),
                NodeInputBinding.from_task_input("task", task_input),
            ),
        )
        second = self._node(
            graph_ref, "b", dependencies=(first.node_ref,),
            inputs=(NodeInputBinding.from_node_output("prior", first.node_ref, "result"),),
        )
        graph = self.graphs.create_graph(
            self.alpha_access,
            graph_ref=graph_ref,
            task_ref=bound_task.task_ref,
            expected_task_digest=bound_task.canonical_digest,
            run_ref=bound_run.run_ref,
            nodes=(first, second),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=bound_attempt,
        )
        self.assertEqual(len(graph.nodes[0].input_bindings), 4)
        quarantine = QuarantineRef(
            raw_sha256=content.digest, source_locator="fixture://raw", source_type="text/plain",
            source_manifest_identity=None, byte_size=content.size_bytes,
            acquisition_time="2026-08-28T00:00:00+00:00", immutable_metadata={},
        )
        with self.assertRaises(GraphContractError):
            NodeInputBinding.from_identity("raw", self.alpha.project_ref, quarantine)  # type: ignore[arg-type]
        foreign_source = SourceRef.git(
            self.beta.project_ref,
            repository="https://example.invalid/foreign.git",
            commit="3" * 40,
            tree="4" * 40,
        )
        with self.assertRaises(GraphScopeError):
            NodeInputBinding.from_identity(
                "foreign",
                self.alpha.project_ref,
                foreign_source,
            )
        foreign_artifact_ref = ArtifactService(self.database_path).create_artifact(
            self.beta_access,
            project_ref=self.beta.project_ref,
            role="foreign.input",
            content_ref=content,
            source_refs=(foreign_source,),
            source_artifact_refs=(),
            source_content_refs=(),
            derivation_type="graph.input",
            metadata={},
        ).artifact_ref
        forged_foreign = NodeInputBinding(
            self.alpha.project_ref,
            "forged_foreign",
            "artifact",
            foreign_artifact_ref.value,
            hashlib.sha256(foreign_artifact_ref.value.encode()).hexdigest(),
        )
        forged_ref = GraphRef.new(self.alpha.project_ref)
        with self.assertRaises(GraphScopeError):
            self._create_graph(
                (self._node(forged_ref, "c", inputs=(forged_foreign,)),),
                forged_ref,
            )

    def test_t14_revision_two_preserves_revision_one(self) -> None:
        first_ref = GraphRef.new(self.alpha.project_ref)
        first = self._create_graph((self._node(first_ref, "a"),), first_ref)
        second_ref = GraphRef(first_ref.project_ref, first_ref.graph_id, 2)
        a = self._node(second_ref, "a")
        b = self._node(second_ref, "b", dependencies=(a.node_ref,))
        second = self.graphs.create_revision(
            self.alpha_access, prior_ref=first.graph_ref, nodes=(a, b),
            compiler_identity="planner://minitz/kernel", compiler_version="1.1.0",
            authority_attempt=self.authority_attempt,
        )
        self.assertEqual(second.prior_ref, first.graph_ref)
        self.assertEqual(self.graphs.get_graph(self.alpha_access, first.graph_ref), first)
        self.assertEqual(
            self.graphs.get_active_graph(self.alpha_access, self.run_record.run_ref),
            second,
        )

    def test_t15_guards_integrity_and_fault_rollback(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        first = self._node(graph_ref, "a")
        second = self._node(
            graph_ref,
            "b",
            dependencies=(first.node_ref,),
            inputs=(NodeInputBinding.from_node_output("prior", first.node_ref, "result"),),
        )
        graph = self._create_graph((first, second), graph_ref)

        fault_ref = GraphRef.new(self.alpha.project_ref)
        fault_first = self._node(fault_ref, "c")
        fault_second = self._node(
            fault_ref,
            "d",
            dependencies=(fault_first.node_ref,),
            inputs=(
                NodeInputBinding.from_node_output(
                    "prior",
                    fault_first.node_ref,
                    "result",
                ),
            ),
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                CREATE TRIGGER fail_graph_input_binding
                BEFORE INSERT ON graph_input_bindings
                BEGIN SELECT RAISE(ABORT, 'injected Graph binding fault'); END
                """
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(GraphConflictError):
            self._create_graph((fault_first, fault_second), fault_ref)
        check = sqlite3.connect(self.database_path)
        try:
            for table in (
                "graph_revisions",
                "graph_nodes",
                "graph_dependencies",
                "graph_input_bindings",
                "graph_heads",
                "run_graph_bindings",
            ):
                with self.subTest(table=table, operation="fault_rollback"):
                    self.assertEqual(
                        check.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE graph_id = ?",
                            (fault_ref.graph_id,),
                        ).fetchone()[0],
                        0,
                    )
        finally:
            check.close()

        connection = sqlite3.connect(self.database_path)
        try:
            for table in ("graph_revisions", "graph_nodes", "graph_dependencies", "graph_input_bindings"):
                with self.subTest(table=table):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(f"DELETE FROM {table}")
                    connection.rollback()
            connection.execute("DROP TRIGGER graph_nodes_no_update")
            connection.execute("UPDATE graph_nodes SET executor_kind = ?", ("TAMPERED",))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(GraphIntegrityError):
            self.graphs.get_graph(self.alpha_access, graph.graph_ref)

    def test_t16_restart_preserves_graph_nodes_bindings_and_active_run_graph(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        a = self._node(graph_ref, "a")
        b = self._node(
            graph_ref, "b", dependencies=(a.node_ref,),
            inputs=(NodeInputBinding.from_node_output("prior", a.node_ref, "result"),),
        )
        graph = self._create_graph((a, b), graph_ref)
        restarted = GraphService(self.database_path)
        self.assertEqual(restarted.get_graph(self.alpha_access, graph_ref), graph)
        self.assertEqual(
            restarted.get_active_graph(self.alpha_access, self.run_record.run_ref),
            graph,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            connection.close()

    def test_t17_concurrent_conflicting_revision_has_one_winner(self) -> None:
        second_run = self.runs.create_run(
            self.alpha_access,
            task_ref=self.task.task_ref,
        )
        second_attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            second_run.run_ref,
            owner_ref="planner://independent",
            lease_seconds=60,
        )
        independent_barrier = threading.Barrier(2)

        def create_independent(
            run_ref: RunRef,
            authority_attempt: ExecutionAttempt,
            label: str,
        ) -> Graph:
            graph_ref = GraphRef.new(self.alpha.project_ref)
            node = self._node(graph_ref, label)
            independent_barrier.wait(timeout=5)
            return self.graphs.create_graph(
                self.alpha_access,
                graph_ref=graph_ref,
                task_ref=self.task.task_ref,
                expected_task_digest=self.task.canonical_digest,
                run_ref=run_ref,
                nodes=(node,),
                compiler_identity=None,
                compiler_version=None,
                authority_attempt=authority_attempt,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            independent = tuple(
                future.result()
                for future in (
                    executor.submit(
                        create_independent,
                        self.run_record.run_ref,
                        self.authority_attempt,
                        "a",
                    ),
                    executor.submit(
                        create_independent,
                        second_run.run_ref,
                        second_attempt,
                        "d",
                    ),
                )
            )
        self.assertEqual({graph.run_ref for graph in independent}, {self.run_record.run_ref, second_run.run_ref})
        first = next(graph for graph in independent if graph.run_ref == self.run_record.run_ref)
        first_ref = first.graph_ref
        barrier = threading.Barrier(2)

        def revise(label: str) -> str:
            next_ref = GraphRef(first_ref.project_ref, first_ref.graph_id, 2)
            a = self._node(next_ref, "a")
            extra = self._node(next_ref, label, dependencies=(a.node_ref,))
            barrier.wait(timeout=5)
            try:
                self.graphs.create_revision(
                    self.alpha_access, prior_ref=first.graph_ref, nodes=(a, extra),
                    compiler_identity=None, compiler_version=None,
                    authority_attempt=self.authority_attempt,
                )
            except GraphConflictError:
                return "conflict"
            return "created"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(executor.map(revise, ("b", "c")))
        self.assertEqual(outcomes.count("created"), 1)
        self.assertEqual(outcomes.count("conflict"), 1)

    def test_stale_run_authority_cannot_replace_active_graph_binding(self) -> None:
        first_ref = GraphRef.new(self.alpha.project_ref)
        first = self._create_graph((self._node(first_ref, "a"),), first_ref)
        old_attempt = self.authority_attempt
        second_ref = GraphRef(first_ref.project_ref, first_ref.graph_id, 2)
        second = self.graphs.create_revision(
            self.alpha_access,
            prior_ref=first.graph_ref,
            nodes=(self._node(second_ref, "b"),),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=old_attempt,
        )
        self.runs.release_run_lease(self.alpha_access, old_attempt)
        current_attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            self.run_record.run_ref,
            owner_ref="planner://current",
            lease_seconds=30,
        )
        third_ref = GraphRef(first_ref.project_ref, first_ref.graph_id, 3)
        third_node = self._node(third_ref, "c")
        with self.assertRaises(GraphAuthorityError):
            self.graphs.create_revision(
                self.alpha_access,
                prior_ref=second.graph_ref,
                nodes=(third_node,),
                compiler_identity=None,
                compiler_version=None,
                authority_attempt=old_attempt,
            )
        self.assertEqual(
            self.graphs.get_active_graph(self.alpha_access, self.run_record.run_ref),
            second,
        )
        third = self.graphs.create_revision(
            self.alpha_access,
            prior_ref=second.graph_ref,
            nodes=(third_node,),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=current_attempt,
        )
        self.assertEqual(third.revision, 3)

    def test_cross_project_reads_fail_without_foreign_graph_disclosure(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        graph = self._create_graph((self._node(graph_ref, "a"),), graph_ref)
        with self.assertRaises(GraphScopeError):
            self.graphs.get_graph(self.beta_access, graph.graph_ref)
        with self.assertRaises(GraphScopeError):
            self.graphs.get_active_graph(self.beta_access, graph.run_ref)

    def test_public_dag_validator_rejects_mixed_graph_revisions(self) -> None:
        first_ref = GraphRef.new(self.alpha.project_ref)
        second_ref = GraphRef.new(self.alpha.project_ref)
        with self.assertRaises(GraphScopeError):
            validate_dag(
                (
                    self._node(first_ref, "a"),
                    self._node(second_ref, "b"),
                )
            )

    def test_deleted_active_head_and_truncated_revision_fail_integrity(self) -> None:
        first_ref = GraphRef.new(self.alpha.project_ref)
        first = self._create_graph((self._node(first_ref, "a"),), first_ref)
        second_ref = GraphRef(first_ref.project_ref, first_ref.graph_id, 2)
        second = self.graphs.create_revision(
            self.alpha_access,
            prior_ref=first.graph_ref,
            nodes=(self._node(second_ref, "b"),),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=self.authority_attempt,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DROP TRIGGER graph_revisions_no_delete")
            connection.execute(
                "DELETE FROM graph_revisions WHERE project_id = ? AND graph_id = ? AND revision = ?",
                (second.project_ref.value, second.graph_id, second.revision),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(GraphIntegrityError):
            self.graphs.get_graph(self.alpha_access, first.graph_ref)

    def test_missing_active_run_graph_head_is_integrity_failure(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        graph = self._create_graph((self._node(graph_ref, "a"),), graph_ref)
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER run_graph_heads_no_delete")
            connection.execute(
                "DELETE FROM run_graph_heads WHERE project_id = ? AND run_id = ?",
                (graph.project_ref.value, graph.run_ref.run_id),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(GraphIntegrityError):
            self.graphs.get_active_graph(self.alpha_access, graph.run_ref)

    def test_missing_run_graph_binding_invalidates_exact_graph_read(self) -> None:
        graph_ref = GraphRef.new(self.alpha.project_ref)
        graph = self._create_graph((self._node(graph_ref, "a"),), graph_ref)
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DROP TRIGGER run_graph_bindings_no_delete")
            connection.execute(
                """
                DELETE FROM run_graph_bindings
                WHERE project_id = ? AND run_id = ? AND graph_revision = ?
                """,
                (graph.project_ref.value, graph.run_ref.run_id, graph.revision),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(GraphIntegrityError):
            self.graphs.get_graph(self.alpha_access, graph.graph_ref)

    def test_intermediate_revision_corruption_invalidates_latest_read(self) -> None:
        first_ref = GraphRef.new(self.alpha.project_ref)
        first = self._create_graph((self._node(first_ref, "a"),), first_ref)
        second_ref = GraphRef(first_ref.project_ref, first_ref.graph_id, 2)
        second = self.graphs.create_revision(
            self.alpha_access,
            prior_ref=first.graph_ref,
            nodes=(self._node(second_ref, "b"),),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=self.authority_attempt,
        )
        third_ref = GraphRef(first_ref.project_ref, first_ref.graph_id, 3)
        third = self.graphs.create_revision(
            self.alpha_access,
            prior_ref=second.graph_ref,
            nodes=(self._node(third_ref, "c"),),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=self.authority_attempt,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER graph_nodes_no_update")
            connection.execute(
                """
                UPDATE graph_nodes SET executor_kind = ?
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ?
                """,
                ("TAMPERED", second.project_ref.value, second.graph_id, second.revision),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(GraphIntegrityError):
            self.graphs.get_graph(self.alpha_access, third.graph_ref)

    def test_deleted_bound_artifact_invalidates_graph_read(self) -> None:
        content = ContentRef.from_bytes(b"bound graph artifact", media_type="text/plain")
        artifact = self.artifacts.create_artifact(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            role="graph.input",
            content_ref=content,
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=(),
            derivation_type="graph.input",
            metadata={},
        )
        graph_ref = GraphRef.new(self.alpha.project_ref)
        graph = self._create_graph(
            (
                self._node(
                    graph_ref,
                    "a",
                    inputs=(
                        NodeInputBinding.from_identity(
                            "artifact",
                            self.alpha.project_ref,
                            artifact.artifact_ref,
                        ),
                    ),
                ),
            ),
            graph_ref,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DROP TRIGGER artifact_revisions_no_delete")
            connection.execute(
                """
                DELETE FROM artifact_revisions
                WHERE project_id = ? AND artifact_id = ? AND revision = ?
                """,
                (
                    artifact.project_ref.value,
                    artifact.artifact_id,
                    artifact.revision,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(GraphIntegrityError):
            self.graphs.get_graph(self.alpha_access, graph.graph_ref)

    def test_cancellation_and_graph_creation_are_one_authority_race(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="planner://cancellation-race",
            lease_seconds=30,
        )
        graph_ref = GraphRef.new(self.alpha.project_ref)
        node = self._node(graph_ref, "a")
        barrier = threading.Barrier(2)

        def create() -> str:
            barrier.wait(timeout=5)
            try:
                self.graphs.create_graph(
                    self.alpha_access,
                    graph_ref=graph_ref,
                    task_ref=self.task.task_ref,
                    expected_task_digest=self.task.canonical_digest,
                    run_ref=run.run_ref,
                    nodes=(node,),
                    compiler_identity=None,
                    compiler_version=None,
                    authority_attempt=attempt,
                )
            except GraphAuthorityError:
                return "rejected-after-cancellation"
            return "created-before-cancellation"

        def cancel() -> str:
            barrier.wait(timeout=5)
            self.runs.request_run_cancellation(self.alpha_access, run.run_ref)
            return "cancelled"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(
                future.result()
                for future in (executor.submit(create), executor.submit(cancel))
            )
        self.assertIn(
            outcomes[0],
            {"created-before-cancellation", "rejected-after-cancellation"},
        )
        self.assertEqual(outcomes[1], "cancelled")
        connection = sqlite3.connect(self.database_path)
        try:
            created = connection.execute(
                "SELECT COUNT(*) FROM graph_revisions WHERE graph_id = ?",
                (graph_ref.graph_id,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(created, 1 if outcomes[0] == "created-before-cancellation" else 0)

    def test_readers_observe_consistent_snapshot_during_revision(self) -> None:
        first_ref = GraphRef.new(self.alpha.project_ref)
        first = self._create_graph((self._node(first_ref, "a"),), first_ref)
        second_ref = GraphRef(first_ref.project_ref, first_ref.graph_id, 2)
        second_node = self._node(second_ref, "b")
        barrier = threading.Barrier(2)

        def read() -> tuple[int, ...]:
            barrier.wait(timeout=5)
            return tuple(
                self.graphs.get_active_graph(
                    self.alpha_access,
                    self.run_record.run_ref,
                ).revision
                for _ in range(40)
            )

        def revise() -> Graph:
            barrier.wait(timeout=5)
            return self.graphs.create_revision(
                self.alpha_access,
                prior_ref=first.graph_ref,
                nodes=(second_node,),
                compiler_identity=None,
                compiler_version=None,
                authority_attempt=self.authority_attempt,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            observed_future = executor.submit(read)
            revised_future = executor.submit(revise)
            observed = observed_future.result()
            second = revised_future.result()
        self.assertTrue(set(observed).issubset({1, 2}))
        self.assertEqual(second.revision, 2)
        self.assertEqual(
            self.graphs.get_active_graph(
                self.alpha_access,
                self.run_record.run_ref,
            ),
            second,
        )

    def test_t18_no_provider_scheduler_domain_or_fixed_pipeline_coupling(self) -> None:
        source = (ROOT / "src/minitz_os/engine/graph.py").read_text(encoding="utf-8")
        syntax = ast.parse(source)
        prohibited = {"provider", "model_id", "worker_id", "gpu", "game_engine", "maker", "critic"}
        node_fields = Node.__dataclass_fields__.keys()
        graph_fields = Graph.__dataclass_fields__.keys()
        self.assertTrue(set(node_fields).isdisjoint(prohibited))
        self.assertTrue(set(graph_fields).isdisjoint(prohibited))
        self.assertNotIn("class ExecutorKind", source)
        self.assertNotIn("QuarantineRef", source)
        self.assertGreater(len(tuple(ast.walk(syntax))), 0)


if __name__ == "__main__":
    unittest.main()
