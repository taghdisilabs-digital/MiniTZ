from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from biella.artifact import ArtifactService, ContentRef
from biella.capability import Capability, CapabilityRef, CapabilityRegistry
from biella.event import (
    Event,
    EventAuthorityError,
    EventConflictError,
    EventContractError,
    EventIntegrityError,
    EventLedger,
    EventRef,
    EventScopeError,
)
from biella.graph import Graph, GraphRef, GraphService, Node, NodeRef
from biella.project import ProjectStore
from biella.run import ExecutionAttempt, Run, RunRef, RunService
from biella.task import Task, TaskRevisionService


ROOT = Path(__file__).resolve().parents[1]


class EventLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "biella.sqlite3"
        self.projects = ProjectStore(self.database_path)
        alpha = self.projects.create_project(namespace="alpha", display_name="Alpha")
        beta = self.projects.create_project(namespace="beta", display_name="Beta")
        self.alpha = alpha.project
        self.alpha_access = alpha.access
        self.beta = beta.project
        self.beta_access = beta.access
        self.capabilities = CapabilityRegistry(self.database_path)
        self.capability_ref = self.capabilities.register(
            Capability(CapabilityRef("event.record", "1.0.0"), "Record Event")
        ).capability_ref
        self.tasks = TaskRevisionService(self.database_path)
        self.task = self._create_task("event-task")
        self.runs = RunService(self.database_path)
        self.run_record, self.attempt = self._create_running_run(self.task, "event-main")
        self.graphs = GraphService(self.database_path)
        self.graph, self.node = self._create_graph(self.run_record.run_ref, self.attempt)
        self.artifacts = ArtifactService(self.database_path)
        self.events = EventLedger(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_task(self, idempotency_key: str, *, beta: bool = False) -> Task:
        access = self.beta_access if beta else self.alpha_access
        project_ref = self.beta.project_ref if beta else self.alpha.project_ref
        return self.tasks.create_task(
            access,
            project_ref=project_ref,
            idempotency_key=idempotency_key,
            task_type="event.record",
            objective="Record meaningful execution Events",
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

    def _create_running_run(
        self,
        task: Task,
        owner: str,
        *,
        beta: bool = False,
    ) -> tuple[Run, ExecutionAttempt]:
        access = self.beta_access if beta else self.alpha_access
        run = self.runs.create_run(access, task_ref=task.task_ref)
        attempt = self.runs.acquire_run_lease(
            access,
            run.run_ref,
            owner_ref=f"executor://{owner}",
            lease_seconds=60,
        )
        return run, attempt

    def _create_graph(
        self,
        run_ref: RunRef,
        attempt: ExecutionAttempt,
    ) -> tuple[Graph, Node]:
        graph_ref = GraphRef.new(run_ref.project_ref)
        node = Node(
            node_ref=NodeRef.new(graph_ref),
            executor_kind="SPECIALIST_TASK",
            required_capabilities=(self.capability_ref,),
            dependencies=(),
            input_bindings=(),
            output_contract={"result": "schema://event/result"},
            condition_ref=None,
            side_effect_requirement="READ_ONLY",
            resource_hints={},
            evidence_requirements=("record event",),
        )
        graph = self.graphs.create_graph(
            self.alpha_access,
            graph_ref=graph_ref,
            task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            run_ref=run_ref,
            nodes=(node,),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=attempt,
        )
        return graph, node

    def _append_run_event(
        self,
        key: str,
        *,
        event_type: str = "NODE_STARTED",
        metadata: dict[str, str | int | float | bool | None] | None = None,
        authority_attempt: ExecutionAttempt | None = None,
    ) -> Event:
        return self.events.appendEvent(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            task_ref=self.task.task_ref,
            run_ref=self.run_record.run_ref,
            graph_ref=self.graph.graph_ref,
            node_ref=self.node.node_ref,
            event_type=event_type,
            idempotency_key=key,
            actor_ref="executor://event-main",
            object_refs=(),
            metadata={} if metadata is None else metadata,
            payload_ref=None,
            authority_attempt=self.attempt if authority_attempt is None else authority_attempt,
        )

    def test_t01_append_project_event_and_read_exact_ref(self) -> None:
        event = self.events.appendEvent(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            task_ref=self.task.task_ref,
            run_ref=None,
            graph_ref=None,
            node_ref=None,
            event_type="TASK_CREATED",
            idempotency_key="task-created",
            actor_ref=None,
            object_refs=(),
            metadata={"source": "controller"},
            payload_ref=None,
            authority_attempt=None,
        )
        self.assertIsInstance(event.event_ref, EventRef)
        self.assertIsNone(event.sequence)
        self.assertEqual(self.events.get_event(self.alpha_access, event.event_ref), event)

    def test_t02_run_query_uses_monotonic_sequence_not_timestamp(self) -> None:
        events = tuple(self._append_run_event(f"ordered-{index}") for index in range(3))
        self.assertEqual(tuple(event.sequence for event in events), (1, 2, 3))
        self.assertEqual(self.events.list_run_events(self.alpha_access, self.run_record.run_ref), events)

    def test_t03_concurrent_run_appends_are_unique_and_gap_free(self) -> None:
        barrier = threading.Barrier(8)

        def append(index: int) -> Event:
            barrier.wait(timeout=5)
            return self._append_run_event(f"concurrent-{index}")

        with ThreadPoolExecutor(max_workers=8) as executor:
            events = tuple(executor.map(append, range(8)))
        self.assertEqual(sorted(event.sequence for event in events), list(range(1, 9)))
        self.assertEqual(len({event.event_ref for event in events}), 8)

    def test_t04_independent_run_ledgers_can_progress(self) -> None:
        second_run, second_attempt = self._create_running_run(self.task, "event-second")
        barrier = threading.Barrier(2)

        def append(run_ref: RunRef, attempt: ExecutionAttempt, key: str) -> Event:
            barrier.wait(timeout=5)
            return self.events.appendEvent(
                self.alpha_access,
                project_ref=self.alpha.project_ref,
                task_ref=self.task.task_ref,
                run_ref=run_ref,
                graph_ref=None,
                node_ref=None,
                event_type="RUN_PROGRESS",
                idempotency_key=key,
                actor_ref=attempt.owner_ref,
                object_refs=(),
                metadata={},
                payload_ref=None,
                authority_attempt=attempt,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            first, second = tuple(
                executor.map(
                    lambda values: append(*values),
                    (
                        (self.run_record.run_ref, self.attempt, "independent-a"),
                        (second_run.run_ref, second_attempt, "independent-b"),
                    ),
                )
            )
        self.assertEqual((first.sequence, second.sequence), (1, 1))

    def test_t05_event_rows_are_append_only(self) -> None:
        event = self._append_run_event("immutable")
        self.assertFalse(hasattr(self.events, "update_event"))
        self.assertFalse(hasattr(self.events, "delete_event"))
        connection = sqlite3.connect(self.database_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE events SET event_type = ? WHERE event_id = ?",
                    ("TAMPERED", event.event_ref.event_id),
                )
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM events WHERE event_id = ?",
                    (event.event_ref.event_id,),
                )
        finally:
            connection.close()

    def test_t06_injected_event_failure_rolls_back_run_cancellation(self) -> None:
        run, attempt = self._create_running_run(self.task, "cancel-fault")
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript(
                """
                CREATE TRIGGER fail_cancel_event BEFORE INSERT ON events
                WHEN NEW.event_type = 'RUN_CANCELLED'
                BEGIN SELECT RAISE(ABORT, 'injected Event failure'); END;
                """
            )
        finally:
            connection.close()
        with self.assertRaises(sqlite3.IntegrityError):
            self.events.request_run_cancellation_with_event(
                self.alpha_access,
                run.run_ref,
                idempotency_key="cancel-fault",
                actor_ref="controller://test",
                metadata={"reason": "test"},
            )
        current = self.runs.get_run(self.alpha_access, run.run_ref)
        self.assertEqual(current.status, "RUNNING")
        self.assertEqual(self.events.list_run_events(self.alpha_access, run.run_ref), ())
        self.runs.assert_current_run_authority(self.alpha_access, attempt)

    def test_t07_cancellation_and_event_commit_atomically_and_retry_idempotently(self) -> None:
        run, _ = self._create_running_run(self.task, "cancel-success")
        cancelled, event = self.events.request_run_cancellation_with_event(
            self.alpha_access,
            run.run_ref,
            idempotency_key="cancel-success",
            actor_ref="controller://test",
            metadata={"reason": "operator"},
        )
        self.assertEqual(cancelled.status, "CANCELLED")
        self.assertEqual(event.event_type, "RUN_CANCELLED")
        retried_run, retried_event = self.events.request_run_cancellation_with_event(
            self.alpha_access,
            run.run_ref,
            idempotency_key="cancel-success",
            actor_ref="controller://test",
            metadata={"reason": "operator"},
        )
        self.assertEqual(retried_run, cancelled)
        self.assertEqual(retried_event, event)
        with self.assertRaises(EventConflictError):
            self.events.request_run_cancellation_with_event(
                self.alpha_access,
                run.run_ref,
                idempotency_key="cancel-success-different",
                actor_ref="controller://test",
                metadata={"reason": "operator"},
            )
        self.assertEqual(len(self.events.list_run_events(self.alpha_access, run.run_ref)), 1)

    def test_generic_append_cannot_create_orphan_run_cancellation_event(self) -> None:
        with self.assertRaises(EventContractError):
            self._append_run_event(
                "orphan-cancel",
                event_type="RUN_CANCELLED",
            )
        self.assertEqual(self.runs.get_run(self.alpha_access, self.run_record.run_ref).status, "RUNNING")
        self.assertEqual(
            self.events.list_run_events(self.alpha_access, self.run_record.run_ref),
            (),
        )

    def test_public_run_cancellation_is_atomic_and_race_idempotent(self) -> None:
        run, _ = self._create_running_run(self.task, "public-cancel")
        with ThreadPoolExecutor(max_workers=2) as executor:
            cancelled = tuple(
                executor.map(
                    lambda _: self.runs.request_run_cancellation(
                        self.alpha_access,
                        run.run_ref,
                    ),
                    range(2),
                )
            )
        self.assertEqual(tuple(item.status for item in cancelled), ("CANCELLED", "CANCELLED"))
        events = self.events.list_run_events(self.alpha_access, run.run_ref)
        self.assertEqual(tuple(item.event_type for item in events), ("RUN_CANCELLED",))
        self.assertFalse(hasattr(self.runs, "request_run_cancellation_in_transaction"))

    def test_transaction_bound_append_obeys_caller_rollback(self) -> None:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            event = self.events.append_event_in_transaction(
                connection,
                self.alpha_access,
                project_ref=self.alpha.project_ref,
                task_ref=self.task.task_ref,
                run_ref=self.run_record.run_ref,
                graph_ref=None,
                node_ref=None,
                event_type="TRANSACTION_BOUND",
                idempotency_key="caller-rollback",
                actor_ref=self.attempt.owner_ref,
                object_refs=(),
                metadata={},
                payload_ref=None,
                authority_attempt=self.attempt,
            )
            self.assertEqual(event.sequence, 1)
            connection.rollback()
        finally:
            connection.close()
        self.assertEqual(
            self.events.list_run_events(self.alpha_access, self.run_record.run_ref),
            (),
        )

    def test_t08_identical_append_retry_returns_same_event(self) -> None:
        first = self._append_run_event("idempotent")
        second = self._append_run_event("idempotent")
        self.assertEqual(second, first)
        self.assertEqual(len(self.events.list_run_events(self.alpha_access, self.run_record.run_ref)), 1)

    def test_t09_conflicting_idempotency_retry_fails(self) -> None:
        self._append_run_event("conflict", metadata={"attempt": 1})
        with self.assertRaises(EventConflictError):
            self._append_run_event("conflict", metadata={"attempt": 2})

    def test_t10_exact_refs_validate_and_cross_project_refs_fail(self) -> None:
        event = self._append_run_event("exact-refs")
        self.assertEqual(event.task_ref, self.task.task_ref)
        self.assertEqual(event.run_ref, self.run_record.run_ref)
        self.assertEqual(event.graph_ref, self.graph.graph_ref)
        self.assertEqual(event.node_ref, self.node.node_ref)
        beta_task = self._create_task("beta-event-task", beta=True)
        beta_run, beta_attempt = self._create_running_run(beta_task, "beta", beta=True)
        with self.assertRaises(EventScopeError):
            self.events.appendEvent(
                self.alpha_access,
                project_ref=self.alpha.project_ref,
                task_ref=self.task.task_ref,
                run_ref=beta_run.run_ref,
                graph_ref=None,
                node_ref=None,
                event_type="CROSS_SCOPE",
                idempotency_key="cross-scope",
                actor_ref=beta_attempt.owner_ref,
                object_refs=(),
                metadata={},
                payload_ref=None,
                authority_attempt=beta_attempt,
            )
        with self.assertRaises(EventScopeError):
            self.events.get_event(self.beta_access, event.event_ref)
        with self.assertRaises(EventScopeError):
            self.events.list_run_events(self.beta_access, self.run_record.run_ref)

    def test_t11_arbitrary_future_event_type_is_data(self) -> None:
        event = self._append_run_event(
            "future-type",
            event_type="QUANTUM_SCENE_PHASE_STABILIZED",
        )
        self.assertEqual(event.event_type, "QUANTUM_SCENE_PHASE_STABILIZED")

    def test_t12_large_payload_is_referenced_not_embedded(self) -> None:
        payload = b"large payload marker" * 10_000
        content_ref = ContentRef.from_bytes(payload, media_type="application/octet-stream")
        artifact = self.artifacts.create_artifact(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            role="event.payload",
            content_ref=content_ref,
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=(),
            derivation_type="event.payload",
            metadata={},
        )
        event = self.events.appendEvent(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            task_ref=self.task.task_ref,
            run_ref=self.run_record.run_ref,
            graph_ref=None,
            node_ref=None,
            event_type="PAYLOAD_RECORDED",
            idempotency_key="payload",
            actor_ref=self.attempt.owner_ref,
            object_refs=(artifact.artifact_ref,),
            metadata={"purpose": "large-payload-reference"},
            payload_ref=content_ref,
            authority_attempt=self.attempt,
        )
        self.assertEqual(event.payload_ref, content_ref)
        connection = sqlite3.connect(self.database_path)
        try:
            row = connection.execute(
                "SELECT metadata_json, payload_ref_json FROM events WHERE event_id = ?",
                (event.event_ref.event_id,),
            ).fetchone()
        finally:
            connection.close()
        self.assertNotIn(payload[:128], row[0].encode())
        self.assertNotIn(payload[:128], row[1].encode())

    def test_t13_secret_and_unbounded_metadata_are_rejected_without_persistence(self) -> None:
        candidates = (
            {"api_key": "sk-test-secret"},
            {"access_key": "AKIAIOSFODNN7EXAMPLE"},
            {"note": "Bearer synthetic-secret"},
            {"note": "ghp_0123456789abcdefghijklmnopqrstuv"},
            {"stdout": "x" * 10_000},
            {"nested": {"secret": "value"}},
        )
        for index, metadata in enumerate(candidates):
            with self.subTest(index=index), self.assertRaises(EventContractError):
                self.events.appendEvent(
                    self.alpha_access,
                    project_ref=self.alpha.project_ref,
                    task_ref=None,
                    run_ref=None,
                    graph_ref=None,
                    node_ref=None,
                    event_type="SECRET_TEST",
                    idempotency_key=f"secret-{index}",
                    actor_ref=None,
                    object_refs=(),
                    metadata=metadata,  # type: ignore[arg-type]
                    payload_ref=None,
                    authority_attempt=None,
                )
        raw = self.database_path.read_bytes()
        self.assertNotIn(b"sk-test-secret", raw)
        self.assertNotIn(b"AKIAIOSFODNN7EXAMPLE", raw)
        self.assertNotIn(b"ghp_0123456789abcdefghijklmnopqrstuv", raw)
        self.assertNotIn(b"synthetic-secret", raw)

    def test_actor_reference_has_a_strict_total_byte_bound(self) -> None:
        actor_ref = f"{'a' * 200_000}://x"
        with self.assertRaises(EventContractError):
            self.events.appendEvent(
                self.alpha_access,
                project_ref=self.alpha.project_ref,
                task_ref=None,
                run_ref=None,
                graph_ref=None,
                node_ref=None,
                event_type="ACTOR_BOUND_TEST",
                idempotency_key="actor-bound",
                actor_ref=actor_ref,
                object_refs=(),
                metadata={},
                payload_ref=None,
                authority_attempt=None,
            )

    def test_t14_stale_run_owner_cannot_append(self) -> None:
        old = self.attempt
        self.runs.release_run_lease(self.alpha_access, old)
        current = self.runs.acquire_run_lease(
            self.alpha_access,
            self.run_record.run_ref,
            owner_ref="executor://event-current",
            lease_seconds=60,
        )
        with self.assertRaises(EventAuthorityError):
            self._append_run_event("stale", authority_attempt=old)
        event = self._append_run_event("current", authority_attempt=current)
        self.assertEqual(event.sequence, 1)

    def test_t15_restart_preserves_events_sequences_and_idempotency(self) -> None:
        first = self._append_run_event("restart-a")
        second = self._append_run_event("restart-b")
        restarted = EventLedger(self.database_path)
        self.assertEqual(
            restarted.list_run_events(self.alpha_access, self.run_record.run_ref),
            (first, second),
        )
        retried = restarted.appendEvent(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            task_ref=self.task.task_ref,
            run_ref=self.run_record.run_ref,
            graph_ref=self.graph.graph_ref,
            node_ref=self.node.node_ref,
            event_type="NODE_STARTED",
            idempotency_key="restart-a",
            actor_ref="executor://event-main",
            object_refs=(),
            metadata={},
            payload_ref=None,
            authority_attempt=self.attempt,
        )
        self.assertEqual(retried, first)

    def test_t16_persisted_event_and_sequence_tampering_fail_closed(self) -> None:
        first = self._append_run_event("tamper-a")
        self._append_run_event("tamper-b")
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER events_no_update")
            connection.execute(
                "UPDATE events SET event_type = ? WHERE event_id = ?",
                ("TAMPERED", first.event_ref.event_id),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(EventIntegrityError):
            self.events.list_run_events(self.alpha_access, self.run_record.run_ref)

    def test_derived_event_scope_tampering_fails_closed(self) -> None:
        event = self._append_run_event("scope-tamper")
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER events_no_update")
            connection.execute(
                "UPDATE events SET event_scope = ? WHERE event_id = ?",
                ("forged-scope", event.event_ref.event_id),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(EventIntegrityError):
            self.events.get_event(self.alpha_access, event.event_ref)

    def test_orphan_graph_node_columns_fail_closed(self) -> None:
        event = self.events.appendEvent(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            task_ref=self.task.task_ref,
            run_ref=None,
            graph_ref=None,
            node_ref=None,
            event_type="PROJECT_EVENT",
            idempotency_key="orphan-columns",
            actor_ref=None,
            object_refs=(),
            metadata={},
            payload_ref=None,
            authority_attempt=None,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER events_no_update")
            connection.execute(
                "UPDATE events SET graph_revision = ?, node_id = ? WHERE event_id = ?",
                (7, "node_00000000000000000000000000000000", event.event_ref.event_id),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(EventIntegrityError):
            self.events.get_event(self.alpha_access, event.event_ref)

    def test_t17_meaningful_chronology_reconstructs_without_logs(self) -> None:
        expected = ("NODE_READY", "NODE_STARTED", "NODE_FINISHED")
        for index, event_type in enumerate(expected):
            self._append_run_event(f"chronology-{index}", event_type=event_type)
        restarted = EventLedger(self.database_path)
        observed = tuple(
            event.event_type
            for event in restarted.list_run_events(
                self.alpha_access,
                self.run_record.run_ref,
            )
        )
        self.assertEqual(observed, expected)

    def test_t18_no_log_ingestion_closed_enum_provider_or_quarantine_coupling(self) -> None:
        source = (ROOT / "src/biella/event.py").read_text(encoding="utf-8")
        syntax = ast.parse(source)
        prohibited = {"provider_id", "model_id", "worker_id", "gpu", "game_engine"}
        self.assertTrue(set(Event.__dataclass_fields__).isdisjoint(prohibited))
        self.assertFalse(hasattr(self.events, "ingest_logs"))
        self.assertNotIn("class EventType", source)
        self.assertNotIn("QuarantineRef", source)
        self.assertGreater(len(tuple(ast.walk(syntax))), 0)
        self.assertEqual(hashlib.sha256(source.encode()).digest_size, 32)


if __name__ == "__main__":
    unittest.main()
