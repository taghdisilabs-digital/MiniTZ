from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import inspect
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import cast
import unittest
import zipfile

import biella
from biella import (
    Artifact,
    ArtifactService,
    Capability,
    CapabilityRef,
    CapabilityRegistry,
    ContentRef,
    EventLedger,
    Graph,
    GraphRef,
    GraphService,
    Node,
    NodeExecutionAttempt,
    NodeExecutionService,
    NodeRef,
    ProjectAccess,
    ProjectRef,
    ProjectStore,
    RunMemory,
    RunMemoryDivergenceError,
    RunMemoryIntegrityError,
    RunMemoryNodeAttempt,
    RunMemoryScopeError,
    RunMemoryService,
    RunRef,
    RunService,
    Task,
    TaskRevisionService,
)


ROOT = Path(__file__).resolve().parents[1]


class RunMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "biella.sqlite3"
        self.projects = ProjectStore(self.database_path)
        alpha = self.projects.create_project(namespace="memory-alpha", display_name="Memory Alpha")
        beta = self.projects.create_project(namespace="memory-beta", display_name="Memory Beta")
        self.alpha = alpha.project
        self.alpha_access = alpha.access
        self.beta_access = beta.access
        self.capabilities = CapabilityRegistry(self.database_path)
        self.capability_ref = self.capabilities.register(
            Capability(CapabilityRef("memory.work", "1.0.0"), "Reconstruct durable work")
        ).capability_ref
        self.tasks = TaskRevisionService(self.database_path)
        self.task = self._create_task("run-memory-task")
        self.runs = RunService(self.database_path)
        self.run_record = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        self.run_attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            self.run_record.run_ref,
            owner_ref="controller://run-memory",
            lease_seconds=60,
        )
        self.graphs = GraphService(self.database_path)
        graph_ref = GraphRef.new(self.alpha.project_ref)
        refs = tuple(NodeRef.new(graph_ref) for _ in range(4))
        self.completed_ref, self.failed_ref, self.expired_ref, self.ready_ref = refs
        self.nodes = (
            Node(
                refs[0],
                "SPECIALIST_TASK",
                (self.capability_ref,),
                (),
                (),
                {"result": "schema://memory/result"},
                None,
                "READ_ONLY",
                {},
                (),
            ),
            Node(refs[1], "SPECIALIST_TASK", (self.capability_ref,), (), (), {}, None, "READ_ONLY", {}, ()),
            Node(refs[2], "SPECIALIST_TASK", (self.capability_ref,), (), (), {}, None, "READ_ONLY", {}, ()),
            Node(refs[3], "SPECIALIST_TASK", (self.capability_ref,), (refs[0],), (), {}, None, "READ_ONLY", {}, ()),
        )
        self.graph = self.graphs.create_graph(
            self.alpha_access,
            graph_ref=graph_ref,
            task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            run_ref=self.run_record.run_ref,
            nodes=self.nodes,
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=self.run_attempt,
        )
        self.artifacts = ArtifactService(self.database_path)
        self.events = EventLedger(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.executions.prepare_run(self.alpha_access, self.run_record.run_ref)

        completed_attempt = self._lease_and_start(self.completed_ref, "completed", 60)
        self.output_artifact = self._artifact("completed-output")
        self.executions.finalize_node(
            self.alpha_access,
            completed_attempt,
            outputs={"result": self.output_artifact.artifact_ref},
            evidence={},
            acceptance_criteria=(),
            idempotency_key="completed-finalize",
        )
        self.executions.prepare_run(self.alpha_access, self.run_record.run_ref)

        failed_attempt = self._lease_and_start(self.failed_ref, "failed", 60)
        self.executions.fail_node(
            self.alpha_access,
            failed_attempt,
            category="TOOL_FAILURE",
            reason="durable synthetic failure",
            evidence_refs=(),
            retry_possible=True,
            idempotency_key="failed-terminal",
        )

        self.expired_attempt = self._lease_and_start(self.expired_ref, "expired", 0.05)
        time.sleep(0.08)
        self.executions.prepare_run(self.alpha_access, self.run_record.run_ref)

        self.checkpoint_content = ContentRef.from_bytes(
            b"checkpoint-ref",
            media_type="application/octet-stream",
        )
        self.checkpoint_event = self.events.append_event(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            task_ref=self.task.task_ref,
            run_ref=self.run_record.run_ref,
            graph_ref=self.graph.graph_ref,
            node_ref=None,
            event_type="RUN_CHECKPOINT",
            idempotency_key="checkpoint-one",
            actor_ref="controller://run-memory",
            object_refs=(self.checkpoint_content,),
            metadata={},
            payload_ref=None,
            authority_attempt=self.run_attempt,
        )
        self.model_call_content = ContentRef.from_bytes(
            b"model-call-ref",
            media_type="application/json",
        )
        self.model_call_event = self.events.append_event(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            task_ref=self.task.task_ref,
            run_ref=self.run_record.run_ref,
            graph_ref=self.graph.graph_ref,
            node_ref=None,
            event_type="MODEL_CALL",
            idempotency_key="model-call-one",
            actor_ref="controller://run-memory",
            object_refs=(),
            metadata={},
            payload_ref=self.model_call_content,
            authority_attempt=self.run_attempt,
        )
        self.memories = RunMemoryService(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_task(self, key: str) -> Task:
        return self.tasks.create_task(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            idempotency_key=key,
            task_type="memory.work",
            objective="Reconstruct exact durable Run state",
            required_capabilities=(self.capability_ref,),
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

    def _lease_and_start(
        self,
        node_ref: NodeRef,
        marker: str,
        lease_seconds: float,
    ) -> NodeExecutionAttempt:
        attempt = self.executions.lease_node(
            self.alpha_access,
            node_ref,
            authority_attempt=self.run_attempt,
            owner_ref=f"executor://{marker}",
            lease_seconds=lease_seconds,
            idempotency_key=f"{marker}-lease",
        )
        self.executions.start_node(
            self.alpha_access,
            attempt,
            idempotency_key=f"{marker}-start",
        )
        return attempt

    def _artifact(self, marker: str) -> Artifact:
        return self.artifacts.publish_from_run(
            self.alpha_access,
            producer_attempt=self.run_attempt,
            expected_task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            role=f"memory.{marker}",
            content_ref=ContentRef.from_bytes(marker.encode(), media_type="text/plain"),
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=(),
            derivation_type="memory.output",
            metadata={},
        )

    def test_t01_public_reconstruction_interfaces_exist(self) -> None:
        for name in (
            "RunMemory",
            "RunMemoryService",
            "RunMemoryIntegrityError",
            "RunMemoryDivergenceError",
        ):
            self.assertTrue(hasattr(biella, name), name)

    def test_t02_exact_task_graph_node_attempt_failure_and_ready_state_reconstruct(self) -> None:
        memory = self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)

        self.assertEqual(memory.project_ref, self.alpha.project_ref)
        self.assertEqual(memory.task.task_ref, self.task.task_ref)
        self.assertEqual(memory.task.canonical_digest, self.task.canonical_digest)
        self.assertEqual(memory.current_graph_ref, self.graph.graph_ref)
        self.assertEqual(len(memory.graphs), 1)
        by_ref = {item.node_ref: item for item in memory.graphs[0].nodes}
        completed = by_ref[self.completed_ref].latest
        failed = by_ref[self.failed_ref].latest
        expired = by_ref[self.expired_ref].latest
        assert completed is not None and failed is not None and expired is not None
        self.assertEqual(completed.status, "SUCCEEDED")
        self.assertEqual(
            dict(completed.outputs),
            {"result": self.output_artifact.artifact_ref.value},
        )
        self.assertEqual(failed.status, "FAILED")
        self.assertEqual(by_ref[self.failed_ref].failures[0].reason, "durable synthetic failure")
        self.assertEqual(expired.status, "RUNNING")
        self.assertEqual(memory.ready_node_refs, (self.ready_ref,))
        self.assertEqual(
            set(memory.continuation_node_refs),
            {self.expired_ref, self.ready_ref},
        )

    def test_t03_process_restart_preserves_semantic_state_outputs_and_failures(self) -> None:
        before = self.memories.get_run_memory(self.alpha_access, self.run_record.run_ref)
        restarted = RunMemoryService(self.database_path).reconstruct(
            self.alpha_access,
            self.run_record.run_ref,
        )

        self.assertEqual(restarted.semantic_digest, before.semantic_digest)
        self.assertEqual(restarted.run_attempts, before.run_attempts)
        self.assertEqual(restarted.events, before.events)
        self.assertEqual(restarted.graphs, before.graphs)
        self.assertTrue(RunMemoryService(self.database_path).validate_consistency(self.alpha_access, before))

    def test_t04_event_high_water_checkpoint_and_model_call_refs_are_reference_only(self) -> None:
        memory = self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)

        self.assertEqual(memory.event_high_water_mark, len(memory.events))
        self.assertEqual(memory.event_high_water_mark, self.model_call_event.sequence)
        self.assertEqual(
            tuple(item.kind for item in memory.extension_refs),
            ("RUN_CHECKPOINT", "MODEL_CALL"),
        )
        assert memory.latest_checkpoint_ref is not None
        self.assertEqual(memory.latest_checkpoint_ref.event_ref, self.checkpoint_event.event_ref)
        self.assertEqual(
            memory.latest_checkpoint_ref.object_refs,
            (self.checkpoint_content.value,),
        )
        self.assertEqual(memory.extension_refs[-1].payload_ref, self.model_call_content)
        self.assertFalse(hasattr(memory, "checkpoint_payload"))

    def test_t05_project_beta_cannot_reconstruct_alpha_run_memory(self) -> None:
        known = RunRef(self.alpha.project_ref, self.run_record.run_id)
        with self.assertRaises(RunMemoryScopeError):
            self.memories.reconstruct(self.beta_access, known)

    def test_t06_validator_rejects_stale_projection_and_cache_is_not_authority(self) -> None:
        stale = self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)
        self.events.append_event(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            task_ref=self.task.task_ref,
            run_ref=self.run_record.run_ref,
            graph_ref=self.graph.graph_ref,
            node_ref=None,
            event_type="TOOL_CALL",
            idempotency_key="tool-call-after-memory",
            actor_ref="controller://run-memory",
            object_refs=(ContentRef.from_bytes(b"tool-call", media_type="application/json"),),
            metadata={},
            payload_ref=None,
            authority_attempt=self.run_attempt,
        )

        with self.assertRaises(RunMemoryDivergenceError):
            self.memories.validate_consistency(self.alpha_access, stale)
        current = RunMemoryService(self.database_path).reconstruct(
            self.alpha_access,
            self.run_record.run_ref,
        )
        self.assertTrue(self.memories.validate_consistency(self.alpha_access, current))
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE name LIKE 'run_memory%'"
                ).fetchall(),
                [],
            )
        finally:
            connection.close()

    def test_projection_collections_are_frozen_and_structural_tampering_is_rejected(self) -> None:
        current = self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)
        mutable_events = list(current.events)
        copied = replace(
            current,
            events=cast(tuple[biella.Event, ...], mutable_events),
        )
        mutable_events.clear()
        self.assertEqual(copied.events, current.events)
        self.assertIsInstance(copied.events, tuple)

        object.__setattr__(copied, "events", [])
        with self.assertRaises(RunMemoryDivergenceError):
            self.memories.validate_consistency(self.alpha_access, copied)

    def test_attempt_completion_exact_record_changes_semantic_digest(self) -> None:
        current = self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)
        graph = current.graphs[0]
        node_index = next(
            index
            for index, node in enumerate(graph.nodes)
            if node.node_ref == self.completed_ref
        )
        node = graph.nodes[node_index]
        completion_index = next(
            index
            for index, item in enumerate(node.attempts)
            if item.completed_at is not None
        )
        prior = node.attempts[completion_index]
        changed_at = "2030-01-01T00:00:00+00:00"
        payload = json.dumps(
            {
                "attempt_id": prior.attempt.attempt_id,
                "completed_at": changed_at,
                "node_ref": prior.attempt.node_ref.value,
                "outcome": prior.outcome,
            },
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        altered_attempt = RunMemoryNodeAttempt(
            attempt=prior.attempt,
            completed_at=changed_at,
            outcome=prior.outcome,
            completion_sha256=hashlib.sha256(payload).hexdigest(),
        )
        altered_attempts = list(node.attempts)
        altered_attempts[completion_index] = altered_attempt
        altered_node = replace(node, attempts=tuple(altered_attempts))
        altered_nodes = list(graph.nodes)
        altered_nodes[node_index] = altered_node
        altered_graph = replace(graph, nodes=tuple(altered_nodes))
        altered_graphs = list(current.graphs)
        altered_graphs[0] = altered_graph
        altered = replace(current, graphs=tuple(altered_graphs))

        self.assertNotEqual(altered.semantic_digest, current.semantic_digest)
        with self.assertRaises(RunMemoryDivergenceError):
            self.memories.validate_consistency(self.alpha_access, altered)

    def test_attempt_completion_outcome_must_match_attempt_terminal_state(self) -> None:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                """
                SELECT attempt_id, completed_at
                FROM node_execution_attempt_completions
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ?
                    AND node_id = ?
                """,
                (
                    self.alpha.project_ref.value,
                    self.graph.graph_id,
                    self.graph.revision,
                    self.completed_ref.node_id,
                ),
            ).fetchone()
            assert row is not None
            record = hashlib.sha256(
                json.dumps(
                    {
                        "attempt_id": row["attempt_id"],
                        "completed_at": row["completed_at"],
                        "node_ref": self.completed_ref.value,
                        "outcome": "FAILED",
                    },
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            connection.execute(
                "DROP TRIGGER node_execution_attempt_completions_no_update"
            )
            connection.execute(
                """
                UPDATE node_execution_attempt_completions
                SET outcome = 'FAILED', record_sha256 = ?
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ?
                    AND node_id = ? AND attempt_id = ?
                """,
                (
                    record,
                    self.alpha.project_ref.value,
                    self.graph.graph_id,
                    self.graph.revision,
                    self.completed_ref.node_id,
                    row["attempt_id"],
                ),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RunMemoryIntegrityError):
            self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)

    def test_t07_missing_event_is_detected_instead_of_silently_reconstructed(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DROP TRIGGER events_no_delete")
            connection.execute(
                "DELETE FROM events WHERE project_id = ? AND event_id = ?",
                (self.alpha.project_ref.value, self.model_call_event.event_ref.event_id),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RunMemoryIntegrityError):
            self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)

    def test_t08_output_artifact_binding_mismatch_fails_closed(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER node_execution_bindings_no_update")
            connection.execute(
                """
                UPDATE node_execution_bindings
                SET artifact_record_sha256 = ?
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ?
                    AND node_id = ? AND binding_kind = 'output'
                """,
                (
                    "0" * 64,
                    self.alpha.project_ref.value,
                    self.graph.graph_id,
                    self.graph.revision,
                    self.completed_ref.node_id,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RunMemoryIntegrityError):
            self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)

    def test_t09_newer_task_revision_does_not_rewrite_existing_run_memory(self) -> None:
        revised = self.tasks.create_revision(
            self.alpha_access,
            prior_ref=self.task.task_ref,
            idempotency_key="run-memory-task-revision-two",
            task_type=self.task.task_type,
            objective="A newer requested outcome",
            required_capabilities=self.task.required_capabilities,
            input_refs=self.task.input_refs,
            output_contract=self.task.output_contract,
            constraints=self.task.constraints,
            side_effect_authority=self.task.side_effect_authority,
            data_policy_ref=self.task.data_policy_ref,
            egress_policy_ref=self.task.egress_policy_ref,
            evidence_requirements=self.task.evidence_requirements,
            acceptance_criteria=self.task.acceptance_criteria,
            resource_hints=self.task.resource_hints,
        )

        memory = self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)
        self.assertEqual(revised.revision, 2)
        self.assertEqual(memory.task.task_ref, self.task.task_ref)
        self.assertEqual(memory.run.task_digest, self.task.canonical_digest)
        self.assertNotEqual(memory.task.canonical_digest, revised.canonical_digest)

    def test_t10_expired_owner_is_preserved_as_attempt_but_not_reported_current(self) -> None:
        memory = self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)
        node = next(item for item in memory.graphs[0].nodes if item.node_ref == self.expired_ref)

        self.assertTrue(node.lease_expired)
        latest = node.latest
        assert latest is not None
        self.assertEqual(latest.current_owner_ref, "executor://expired")
        self.assertIsNone(node.effective_owner_ref)
        self.assertEqual(node.attempts[-1].attempt.attempt_id, self.expired_attempt.attempt_id)
        self.assertIsNone(node.attempts[-1].completed_at)

    def test_t11_superseded_graph_history_remains_visible_without_becoming_current(self) -> None:
        next_ref = GraphRef(self.graph.project_ref, self.graph.graph_id, 2)
        replacement = Node(
            NodeRef.new(next_ref),
            "SPECIALIST_TASK",
            (self.capability_ref,),
            (),
            (),
            {},
            None,
            "READ_ONLY",
            {},
            (),
        )
        revised = self.graphs.create_revision(
            self.alpha_access,
            prior_ref=self.graph.graph_ref,
            nodes=(replacement,),
            compiler_identity="planner://biella/run-memory",
            compiler_version="1.0.0",
            authority_attempt=self.run_attempt,
        )
        self.executions.prepare_run(self.alpha_access, self.run_record.run_ref)

        memory = self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)
        self.assertEqual(memory.current_graph_ref, revised.graph_ref)
        self.assertEqual(tuple(item.graph.graph_ref for item in memory.graphs), (self.graph.graph_ref, revised.graph_ref))
        old = {item.node_ref: item for item in memory.graphs[0].nodes}
        old_completed = old[self.completed_ref].latest
        old_expired = old[self.expired_ref].latest
        assert old_completed is not None and old_expired is not None
        self.assertEqual(old_completed.status, "SUCCEEDED")
        self.assertEqual(old_expired.status, "STALE")
        self.assertEqual(memory.ready_node_refs, (replacement.node_ref,))
        self.assertIsNone(memory.latest_checkpoint_ref)
        self.assertIn(self.checkpoint_event.event_ref, {item.event_ref for item in memory.extension_refs})

    def test_accepted_graph_before_prepare_is_explicitly_uninitialized(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        run_attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="controller://uninitialized-memory",
            lease_seconds=60,
        )
        graph_ref = GraphRef.new(self.alpha.project_ref)
        root_ref = NodeRef.new(graph_ref)
        dependent_ref = NodeRef.new(graph_ref)
        graph = self.graphs.create_graph(
            self.alpha_access,
            graph_ref=graph_ref,
            task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            run_ref=run.run_ref,
            nodes=(
                Node(
                    root_ref,
                    "SPECIALIST_TASK",
                    (self.capability_ref,),
                    (),
                    (),
                    {},
                    None,
                    "READ_ONLY",
                    {},
                    (),
                ),
                Node(
                    dependent_ref,
                    "SPECIALIST_TASK",
                    (self.capability_ref,),
                    (root_ref,),
                    (),
                    {},
                    None,
                    "READ_ONLY",
                    {},
                    (),
                ),
            ),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=run_attempt,
        )

        memory = RunMemoryService(self.database_path).reconstruct(
            self.alpha_access,
            run.run_ref,
        )
        self.assertEqual(memory.current_graph_ref, graph.graph_ref)
        self.assertFalse(memory.graphs[-1].initialized)
        self.assertEqual(
            tuple(node.node_ref for node in memory.graphs[-1].nodes),
            graph.topological_order(),
        )
        self.assertTrue(all(node.latest is None for node in memory.graphs[-1].nodes))
        self.assertEqual(memory.ready_node_refs, (root_ref,))
        self.assertEqual(memory.continuation_node_refs, graph.topological_order())

    def test_orphaned_graph_revision_cannot_downgrade_to_graphless_memory(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DROP TRIGGER run_graph_heads_no_delete")
            connection.execute("DROP TRIGGER run_graph_bindings_no_delete")
            connection.execute(
                "DELETE FROM run_graph_heads WHERE project_id = ? AND run_id = ?",
                (self.alpha.project_ref.value, self.run_record.run_id),
            )
            connection.execute(
                "DELETE FROM run_graph_bindings WHERE project_id = ? AND run_id = ?",
                (self.alpha.project_ref.value, self.run_record.run_id),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RunMemoryIntegrityError):
            self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)

    def test_t12_terminal_run_remains_terminal_with_no_continuation(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        run_attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="controller://terminal-memory",
            lease_seconds=60,
        )
        graph_ref = GraphRef.new(self.alpha.project_ref)
        node = Node(
            NodeRef.new(graph_ref),
            "SPECIALIST_TASK",
            (self.capability_ref,),
            (),
            (),
            {},
            None,
            "READ_ONLY",
            {},
            (),
        )
        self.graphs.create_graph(
            self.alpha_access,
            graph_ref=graph_ref,
            task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            run_ref=run.run_ref,
            nodes=(node,),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=run_attempt,
        )
        service = NodeExecutionService(self.database_path)
        service.prepare_run(self.alpha_access, run.run_ref)
        attempt = service.lease_node(
            self.alpha_access,
            node.node_ref,
            authority_attempt=run_attempt,
            owner_ref="executor://terminal-memory",
            lease_seconds=60,
            idempotency_key="terminal-memory-lease",
        )
        service.start_node(self.alpha_access, attempt, idempotency_key="terminal-memory-start")
        service.finalize_node(
            self.alpha_access,
            attempt,
            outputs={},
            evidence={},
            acceptance_criteria=(),
            idempotency_key="terminal-memory-finalize",
        )

        memory = RunMemoryService(self.database_path).reconstruct(self.alpha_access, run.run_ref)
        self.assertEqual(memory.run.status, "SUCCEEDED")
        latest = memory.graphs[-1].nodes[0].latest
        assert latest is not None
        self.assertEqual(latest.status, "SUCCEEDED")
        self.assertEqual(memory.continuation_node_refs, ())
        self.assertEqual(
            RunMemoryService(self.database_path).reconstruct(self.alpha_access, run.run_ref).semantic_digest,
            memory.semantic_digest,
        )

    def test_t13_reconstruction_has_no_conversation_provider_session_or_second_authority(self) -> None:
        memory = self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)
        prohibited = {
            "conversation_id",
            "provider_session_id",
            "worker_memory",
            "mutable_summary",
        }
        self.assertTrue(set(RunMemory.__dataclass_fields__).isdisjoint(prohibited))
        self.assertTrue(set(memory.__dataclass_fields__).isdisjoint(prohibited))
        source = (ROOT / "src/biella/run_memory.py").read_text(encoding="utf-8")
        syntax = ast.parse(source)
        self.assertGreater(len(tuple(ast.walk(syntax))), 0)
        self.assertNotIn("QuarantineRef", source)
        connection = sqlite3.connect(self.database_path)
        try:
            tables = tuple(
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            )
            before = {
                name: connection.execute(
                    f'SELECT COUNT(*) FROM "{name}"'
                ).fetchone()[0]
                for name in tables
            }
            self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)
            after = {
                name: connection.execute(
                    f'SELECT COUNT(*) FROM "{name}"'
                ).fetchone()[0]
                for name in tables
            }
            self.assertEqual(after, before)
        finally:
            connection.close()

    def test_t14_checkpoint_marker_without_exact_reference_fails_closed(self) -> None:
        self.events.append_event(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            task_ref=self.task.task_ref,
            run_ref=self.run_record.run_ref,
            graph_ref=self.graph.graph_ref,
            node_ref=None,
            event_type="RUN_CHECKPOINT",
            idempotency_key="checkpoint-without-ref",
            actor_ref="controller://run-memory",
            object_refs=(),
            metadata={},
            payload_ref=None,
            authority_attempt=self.run_attempt,
        )

        with self.assertRaises(RunMemoryIntegrityError):
            self.memories.reconstruct(self.alpha_access, self.run_record.run_ref)

    def test_t15_predecessor_typecheck_build_and_installed_restart_gate(self) -> None:
        source = (ROOT / "tests/test_p1_02_run_memory.py").read_text(encoding="utf-8")
        prohibited_markers = (
            "TO" "DO",
            "FIX" "ME",
            "place" "holder",
            "@unittest." "skip",
            "pytest.mark." "skip",
            "self." "skipTest",
            "Not" "Implemented",
        )
        for marker in prohibited_markers:
            self.assertNotIn(marker, source, marker)
        ast.parse(source)

        typecheck = subprocess.run(
            (sys.executable, "-m", "mypy", "--strict", "src", "tests"),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(typecheck.returncode, 0, f"{typecheck.stdout}\n{typecheck.stderr}")

        loader = unittest.TestLoader()
        predecessor = unittest.TestSuite(
            (
                loader.discover(str(ROOT / "tests"), pattern="test_p0_*.py"),
                loader.discover(str(ROOT / "tests"), pattern="test_p1_01*.py"),
            )
        )
        self.assertEqual(predecessor.countTestCases(), 242)
        result = unittest.TestResult()
        predecessor.run(result)
        self.assertEqual(result.testsRun, 242)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.skipped, [])
        self.assertEqual(result.expectedFailures, [])
        self.assertEqual(result.unexpectedSuccesses, [])

        with tempfile.TemporaryDirectory() as temporary_directory:
            qualification_root = Path(temporary_directory)
            wheel_root = qualification_root / "wheel"
            wheel_root.mkdir()
            build = subprocess.run(
                (
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    ".",
                    "--no-deps",
                    "--no-build-isolation",
                    "--wheel-dir",
                    str(wheel_root),
                ),
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, f"{build.stdout}\n{build.stderr}")
            wheels = tuple(wheel_root.glob("biella_engine-*.whl"))
            self.assertEqual(len(wheels), 1)
            wheel_path = wheels[0]
            source_paths = tuple(sorted((ROOT / "src/biella").glob("*.py")))
            with zipfile.ZipFile(wheel_path) as archive:
                source_names = {f"biella/{path.name}" for path in source_paths}
                wheel_names = {
                    name
                    for name in archive.namelist()
                    if name.startswith("biella/") and name.endswith(".py")
                }
                self.assertEqual(wheel_names, source_names)
                for path in source_paths:
                    self.assertEqual(archive.read(f"biella/{path.name}"), path.read_bytes())

            installed = qualification_root / "installed"
            install = subprocess.run(
                (
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--target",
                    str(installed),
                    str(wheel_path),
                ),
                cwd=qualification_root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(install.returncode, 0, f"{install.stdout}\n{install.stderr}")
            environment = os.environ.copy()
            environment.update(
                {
                    "BIELLA_DATABASE": str(qualification_root / "restart.sqlite3"),
                    "BIELLA_INSTALLED": str(installed),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(installed),
                }
            )
            writer_script = inspect.cleandoc(
                """
                import json
                import os
                from pathlib import Path
                import biella
                from biella import ArtifactService, Capability, CapabilityRef, CapabilityRegistry, ContentRef, EventLedger, GraphRef, GraphService, Node, NodeExecutionService, NodeRef, ProjectStore, RunMemoryService, RunService, TaskRevisionService

                installed = Path(os.environ["BIELLA_INSTALLED"]).resolve()
                assert Path(biella.__file__).resolve().is_relative_to(installed)
                database = Path(os.environ["BIELLA_DATABASE"])
                registration = ProjectStore(database).create_project(namespace="wheel-memory", display_name="Wheel Memory")
                capability = CapabilityRegistry(database).register(Capability(CapabilityRef("wheel.memory", "1.0.0"), "Wheel memory"))
                tasks = TaskRevisionService(database)
                task = tasks.create_task(registration.access, project_ref=registration.project.project_ref, idempotency_key="wheel-memory", task_type="wheel.memory", objective="Restart", required_capabilities=(capability.capability_ref,), input_refs=(), output_contract={}, constraints={}, side_effect_authority="PROJECT_WRITE", data_policy_ref=None, egress_policy_ref=None, evidence_requirements=(), acceptance_criteria=(), resource_hints={})
                runs = RunService(database)
                run = runs.create_run(registration.access, task_ref=task.task_ref)
                run_attempt = runs.acquire_run_lease(registration.access, run.run_ref, owner_ref="controller://wheel-memory", lease_seconds=60)
                graph_ref = GraphRef.new(registration.project.project_ref)
                completed_ref, failed_ref, ready_ref = tuple(NodeRef.new(graph_ref) for _ in range(3))
                nodes = (
                    Node(completed_ref, "SPECIALIST_TASK", (capability.capability_ref,), (), (), {"result": "schema://wheel/result"}, None, "READ_ONLY", {}, ()),
                    Node(failed_ref, "SPECIALIST_TASK", (capability.capability_ref,), (), (), {}, None, "READ_ONLY", {}, ()),
                    Node(ready_ref, "SPECIALIST_TASK", (capability.capability_ref,), (completed_ref,), (), {}, None, "READ_ONLY", {}, ()),
                )
                graph = GraphService(database).create_graph(registration.access, graph_ref=graph_ref, task_ref=task.task_ref, expected_task_digest=task.canonical_digest, run_ref=run.run_ref, nodes=nodes, compiler_identity=None, compiler_version=None, authority_attempt=run_attempt)
                executions = NodeExecutionService(database)
                executions.prepare_run(registration.access, run.run_ref)
                completed_attempt = executions.lease_node(registration.access, completed_ref, authority_attempt=run_attempt, owner_ref="executor://wheel-completed", lease_seconds=60, idempotency_key="wheel-completed-lease")
                executions.start_node(registration.access, completed_attempt, idempotency_key="wheel-completed-start")
                output = ArtifactService(database).publish_from_run(registration.access, producer_attempt=run_attempt, expected_task_ref=task.task_ref, expected_task_digest=task.canonical_digest, role="wheel.memory.output", content_ref=ContentRef.from_bytes(b"wheel-output", media_type="text/plain"), source_refs=(), source_artifact_refs=(), source_content_refs=(), derivation_type="wheel.memory", metadata={})
                executions.finalize_node(registration.access, completed_attempt, outputs={"result": output.artifact_ref}, evidence={}, acceptance_criteria=(), idempotency_key="wheel-completed-finalize")
                executions.prepare_run(registration.access, run.run_ref)
                failed_attempt = executions.lease_node(registration.access, failed_ref, authority_attempt=run_attempt, owner_ref="executor://wheel-failed", lease_seconds=60, idempotency_key="wheel-failed-lease")
                executions.start_node(registration.access, failed_attempt, idempotency_key="wheel-failed-start")
                executions.fail_node(registration.access, failed_attempt, category="TOOL_FAILURE", reason="wheel durable failure", evidence_refs=(), retry_possible=True, idempotency_key="wheel-failed-terminal")
                checkpoint_content = ContentRef.from_bytes(b"wheel-checkpoint", media_type="application/octet-stream")
                checkpoint = EventLedger(database).append_event(registration.access, project_ref=registration.project.project_ref, task_ref=task.task_ref, run_ref=run.run_ref, graph_ref=graph.graph_ref, node_ref=None, event_type="RUN_CHECKPOINT", idempotency_key="wheel-checkpoint", actor_ref="controller://wheel-memory", object_refs=(checkpoint_content,), metadata={}, payload_ref=None, authority_attempt=run_attempt)
                memory = RunMemoryService(database).reconstruct(registration.access, run.run_ref)
                by_ref = {node.node_ref.value: node for node in memory.graphs[-1].nodes}
                assert memory.graphs[-1].initialized
                assert by_ref[completed_ref.value].latest.status == "SUCCEEDED"
                assert by_ref[failed_ref.value].latest.status == "FAILED"
                assert by_ref[ready_ref.value].latest.status == "READY"
                print(json.dumps({"project_id": registration.project.project_ref.value, "run_id": run.run_id, "token": registration.access.token, "digest": memory.semantic_digest, "completed_ref": completed_ref.value, "failed_ref": failed_ref.value, "ready_ref": ready_ref.value, "output_ref": output.artifact_ref.value, "checkpoint_ref": checkpoint.event_ref.value, "high_water": memory.event_high_water_mark}))
                """
            )
            writer = subprocess.run(
                (sys.executable, "-c", writer_script),
                cwd=qualification_root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(writer.returncode, 0, f"{writer.stdout}\n{writer.stderr}")
            identity = json.loads(writer.stdout)
            environment.update(
                {
                    "BIELLA_PROJECT_ID": identity["project_id"],
                    "BIELLA_RUN_ID": identity["run_id"],
                    "BIELLA_TOKEN": identity["token"],
                    "BIELLA_MEMORY_DIGEST": identity["digest"],
                    "BIELLA_COMPLETED_REF": identity["completed_ref"],
                    "BIELLA_FAILED_REF": identity["failed_ref"],
                    "BIELLA_READY_REF": identity["ready_ref"],
                    "BIELLA_OUTPUT_REF": identity["output_ref"],
                    "BIELLA_CHECKPOINT_REF": identity["checkpoint_ref"],
                    "BIELLA_HIGH_WATER": str(identity["high_water"]),
                }
            )
            reader_script = inspect.cleandoc(
                """
                import os
                from pathlib import Path
                import biella
                from biella import ProjectAccess, ProjectRef, RunMemoryService, RunRef

                installed = Path(os.environ["BIELLA_INSTALLED"]).resolve()
                assert Path(biella.__file__).resolve().is_relative_to(installed)
                project_ref = ProjectRef(os.environ["BIELLA_PROJECT_ID"])
                access = ProjectAccess(project_ref, os.environ["BIELLA_TOKEN"])
                memory = RunMemoryService(Path(os.environ["BIELLA_DATABASE"])).reconstruct(access, RunRef(project_ref, os.environ["BIELLA_RUN_ID"]))
                assert memory.semantic_digest == os.environ["BIELLA_MEMORY_DIGEST"]
                assert memory.graphs[-1].initialized
                by_ref = {node.node_ref.value: node for node in memory.graphs[-1].nodes}
                completed = by_ref[os.environ["BIELLA_COMPLETED_REF"]]
                failed = by_ref[os.environ["BIELLA_FAILED_REF"]]
                ready = by_ref[os.environ["BIELLA_READY_REF"]]
                assert completed.latest.status == "SUCCEEDED"
                assert completed.latest.outputs["result"] == os.environ["BIELLA_OUTPUT_REF"]
                assert completed.attempts[-1].outcome == "SUCCEEDED"
                assert failed.latest.status == "FAILED"
                assert failed.failures[-1].reason == "wheel durable failure"
                assert failed.attempts[-1].outcome == "FAILED"
                assert ready.latest.status == "READY"
                assert memory.ready_node_refs == (ready.node_ref,)
                assert memory.event_high_water_mark == int(os.environ["BIELLA_HIGH_WATER"])
                assert memory.latest_checkpoint_ref.event_ref.value == os.environ["BIELLA_CHECKPOINT_REF"]
                """
            )
            reader = subprocess.run(
                (sys.executable, "-c", reader_script),
                cwd=qualification_root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(reader.returncode, 0, f"{reader.stdout}\n{reader.stderr}")


if __name__ == "__main__":
    unittest.main()
