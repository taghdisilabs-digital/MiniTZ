from __future__ import annotations

import ast
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
import hashlib
import inspect
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest

from minitz_os.engine.capability import Capability, CapabilityRef, CapabilityRegistry
from minitz_os.engine.project import Project, ProjectAccess, ProjectStore
from minitz_os.engine.run import (
    ExecutionAttempt,
    Run,
    RunAuthorityError,
    RunCancelledError,
    RunIntegrityError,
    RunLeaseConflictError,
    RunRef,
    RunScopeError,
    RunService,
)
from minitz_os.engine.task import Task, TaskRevisionService


ROOT = Path(__file__).resolve().parents[1]


class RunLeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "minitz.sqlite3"
        self.projects = ProjectStore(self.database_path)
        self.capabilities = CapabilityRegistry(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.runs = RunService(self.database_path)
        alpha_registration = self.projects.create_project(
            namespace="alpha",
            display_name="Alpha",
        )
        beta_registration = self.projects.create_project(
            namespace="beta",
            display_name="Beta",
        )
        self.alpha = alpha_registration.project
        self.alpha_access = alpha_registration.access
        self.beta = beta_registration.project
        self.beta_access = beta_registration.access
        self.capability_ref = self.capabilities.register(
            Capability(
                CapabilityRef("production.execute", "1.0.0"),
                "Execute a durable provider-neutral production attempt",
            )
        ).capability_ref
        self.task = self._create_task("run-task-1")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_task(self, idempotency_key: str, objective: str = "Produce output") -> Task:
        return self.tasks.create_task(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            idempotency_key=idempotency_key,
            task_type="production.execute",
            objective=objective,
            required_capabilities=(self.capability_ref,),
            input_refs=(),
            output_contract={},
            constraints={},
            side_effect_authority="READ_ONLY",
            data_policy_ref=None,
            egress_policy_ref=None,
            evidence_requirements=(),
            acceptance_criteria=(),
            resource_hints={},
        )

    def _expire_and_replace(
        self,
        *,
        first_owner: str = "executor://worker-a",
        second_owner: str = "executor://worker-b",
    ) -> tuple[Run, ExecutionAttempt, ExecutionAttempt]:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        first = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref=first_owner,
            lease_seconds=0.04,
        )
        time.sleep(0.08)
        second = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref=second_owner,
            lease_seconds=10,
        )
        return run, first, second

    def test_t01_run_binds_exact_project_task_revision_and_digest(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        self.assertIsInstance(run, Run)
        self.assertIsInstance(run.run_ref, RunRef)
        self.assertEqual(run.project_ref, self.alpha.project_ref)
        self.assertEqual(run.task_ref, self.task.task_ref)
        self.assertEqual(run.task_digest, self.task.canonical_digest)
        self.assertEqual(run.status, "PENDING")
        self.assertEqual(self.runs.get_run(self.alpha_access, run.run_ref), run)

    def test_t02_later_task_revision_does_not_change_existing_run(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        revision_two = self.tasks.create_revision(
            self.alpha_access,
            prior_ref=self.task.task_ref,
            idempotency_key="run-task-2",
            task_type=self.task.task_type,
            objective="Changed output",
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
        observed = self.runs.get_run(self.alpha_access, run.run_ref)
        self.assertEqual(observed.task_ref, self.task.task_ref)
        self.assertEqual(observed.task_digest, self.task.canonical_digest)
        self.assertNotEqual(observed.task_ref, revision_two.task_ref)

    def test_t03_two_owners_race_and_exactly_one_wins(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        barrier = threading.Barrier(2)

        def acquire(owner: str) -> str:
            barrier.wait(timeout=5)
            try:
                self.runs.acquire_run_lease(
                    self.alpha_access,
                    run.run_ref,
                    owner_ref=owner,
                    lease_seconds=10,
                )
            except RunLeaseConflictError:
                return "conflict"
            return "acquired"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(
                executor.map(acquire, ("executor://worker-a", "executor://worker-b"))
            )
        self.assertEqual(outcomes.count("acquired"), 1)
        self.assertEqual(outcomes.count("conflict"), 1)
        self.assertEqual(len(self.runs.list_attempts(self.alpha_access, run.run_ref)), 1)

    def test_t04_independent_runs_acquire_independently(self) -> None:
        first_run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        second_run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        barrier = threading.Barrier(2)

        def acquire(run_ref: RunRef) -> ExecutionAttempt:
            barrier.wait(timeout=5)
            return self.runs.acquire_run_lease(
                self.alpha_access,
                run_ref,
                owner_ref="executor://shared-pool",
                lease_seconds=10,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            attempts = tuple(executor.map(acquire, (first_run.run_ref, second_run.run_ref)))
        self.assertEqual({attempt.run_ref for attempt in attempts}, {first_run.run_ref, second_run.run_ref})

    def test_t05_expiry_replacement_gets_higher_fence(self) -> None:
        run, first, second = self._expire_and_replace()
        self.assertEqual(first.fence, 1)
        self.assertEqual(second.fence, 2)
        self.assertEqual(second.attempt_number, 2)
        attempts = self.runs.list_attempts(self.alpha_access, run.run_ref)
        self.assertEqual(tuple(attempt.fence for attempt in attempts), (1, 2))
        self.assertEqual(attempts[0].terminal_outcome, "LEASE_EXPIRED")
        self.assertIsNotNone(attempts[0].completed_at)
        self.assertIsNone(attempts[1].terminal_outcome)

    def test_t06_owner_identity_reuse_does_not_restore_old_fence(self) -> None:
        _, first, second = self._expire_and_replace(second_owner="executor://worker-a")
        self.assertEqual(first.owner_ref, second.owner_ref)
        self.assertGreater(second.fence, first.fence)
        with self.assertRaises(RunAuthorityError):
            self.runs.assertCurrentRunAuthority(self.alpha_access, first)
        self.runs.assertCurrentRunAuthority(self.alpha_access, second)

    def test_t07_old_fence_renewal_fails(self) -> None:
        _, first, second = self._expire_and_replace()
        with self.assertRaises(RunAuthorityError):
            self.runs.renew_run_lease(self.alpha_access, first, lease_seconds=10)
        renewed = self.runs.renew_run_lease(self.alpha_access, second, lease_seconds=10)
        self.assertEqual(renewed.current_fence, second.fence)

    def test_t08_old_fence_release_cannot_release_newer_owner(self) -> None:
        run, first, second = self._expire_and_replace()
        with self.assertRaises(RunAuthorityError):
            self.runs.release_run_lease(self.alpha_access, first)
        self.runs.assertCurrentRunAuthority(self.alpha_access, second)
        released = self.runs.release_run_lease(self.alpha_access, second)
        self.assertEqual(released.status, "PENDING")
        self.assertIsNone(released.current_owner_ref)
        completed = self.runs.list_attempts(self.alpha_access, run.run_ref)[-1]
        self.assertEqual(completed.started_at, second.started_at)
        self.assertIsNotNone(completed.completed_at)
        self.assertEqual(completed.terminal_outcome, "RELEASED")
        replacement = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://worker-c",
            lease_seconds=10,
        )
        self.assertEqual(replacement.fence, 3)

    def test_t09_late_old_finalization_authority_check_fails(self) -> None:
        _, first, second = self._expire_and_replace()
        with self.assertRaises(RunAuthorityError):
            self.runs.assert_current_run_authority(self.alpha_access, first)
        self.assertEqual(
            self.runs.assert_current_run_authority(self.alpha_access, second).current_fence,
            second.fence,
        )

    def test_t10_cancellation_blocks_renew_acquire_and_authority(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://worker-a",
            lease_seconds=10,
        )
        cancelled = self.runs.requestRunCancellation(self.alpha_access, run.run_ref)
        self.assertEqual(cancelled.status, "CANCELLED")
        self.assertIsNotNone(cancelled.cancellation_requested_at)
        with self.assertRaises(RunCancelledError):
            self.runs.renew_run_lease(self.alpha_access, attempt, lease_seconds=10)
        with self.assertRaises(RunCancelledError):
            self.runs.acquire_run_lease(
                self.alpha_access,
                run.run_ref,
                owner_ref="executor://worker-b",
                lease_seconds=10,
            )
        with self.assertRaises(RunCancelledError):
            self.runs.assertCurrentRunAuthority(self.alpha_access, attempt)
        attempts = self.runs.list_attempts(self.alpha_access, run.run_ref)
        self.assertEqual(tuple(item.attempt_id for item in attempts), (attempt.attempt_id,))
        self.assertEqual(attempts[0].terminal_outcome, "CANCELLED")
        self.assertIsNotNone(attempts[0].completed_at)
        self.assertEqual(
            self.runs.request_run_cancellation(self.alpha_access, run.run_ref),
            cancelled,
        )

    def test_cancellation_race_cannot_leave_live_authority(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://worker-a",
            lease_seconds=10,
        )
        barrier = threading.Barrier(2)

        def renew() -> str:
            barrier.wait(timeout=5)
            try:
                self.runs.renew_run_lease(
                    self.alpha_access,
                    attempt,
                    lease_seconds=10,
                )
            except RunCancelledError:
                return "cancelled"
            return "renewed-before-cancellation"

        def cancel() -> str:
            barrier.wait(timeout=5)
            self.runs.request_run_cancellation(self.alpha_access, run.run_ref)
            return "cancelled"

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = tuple(executor.submit(operation) for operation in (renew, cancel))
            outcomes = tuple(future.result() for future in futures)
        self.assertIn(outcomes[0], {"cancelled", "renewed-before-cancellation"})
        observed = self.runs.get_run(self.alpha_access, run.run_ref)
        self.assertEqual(observed.status, "CANCELLED")
        self.assertIsNone(observed.current_owner_ref)
        with self.assertRaises(RunCancelledError):
            self.runs.assert_current_run_authority(self.alpha_access, attempt)

    def test_t11_transaction_fault_rolls_back_fence_owner_and_attempt(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript(
                """
                CREATE TRIGGER fail_run_acquisition_state
                BEFORE INSERT ON run_state_versions
                WHEN NEW.current_attempt_id IS NOT NULL
                BEGIN
                    SELECT RAISE(ABORT, 'injected acquisition fault');
                END;
                """
            )
        finally:
            connection.close()
        with self.assertRaises(sqlite3.IntegrityError):
            self.runs.acquire_run_lease(
                self.alpha_access,
                run.run_ref,
                owner_ref="executor://worker-a",
                lease_seconds=10,
            )
        observed = self.runs.get_run(self.alpha_access, run.run_ref)
        self.assertEqual(observed.current_fence, 0)
        self.assertIsNone(observed.current_owner_ref)
        self.assertEqual(self.runs.list_attempts(self.alpha_access, run.run_ref), ())

    def test_t12_restart_preserves_run_attempt_fence_and_cancellation(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://worker-a",
            lease_seconds=10,
        )
        cancelled = self.runs.request_run_cancellation(self.alpha_access, run.run_ref)
        restarted = RunService(self.database_path)
        self.assertEqual(restarted.get_run(self.alpha_access, run.run_ref), cancelled)
        attempts = restarted.list_attempts(self.alpha_access, run.run_ref)
        self.assertEqual(tuple(item.attempt_id for item in attempts), (attempt.attempt_id,))
        self.assertEqual(attempts[0].terminal_outcome, "CANCELLED")
        with self.assertRaises(RunCancelledError):
            restarted.assert_current_run_authority(self.alpha_access, attempt)

    def test_t13_worker_clock_cannot_be_supplied_as_authority(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        self.assertNotIn("now", inspect.signature(self.runs.acquire_run_lease).parameters)
        with self.assertRaises(TypeError):
            self.runs.acquire_run_lease(
                self.alpha_access,
                run.run_ref,
                owner_ref="executor://worker-a",
                lease_seconds=10,
                now="2099-01-01T00:00:00+00:00",  # type: ignore[call-arg]
            )
        source = (ROOT / "src/minitz_os/engine/run.py").read_text(encoding="utf-8")
        self.assertNotIn("datetime.now", source)
        self.assertNotIn("time.time", source)

    def test_t14_run_has_no_provider_hardware_scheduler_or_routing_coupling(self) -> None:
        prohibited = {
            "provider", "model", "cpu", "gpu", "h100", "worker_category",
            "scheduler", "resource_lock", "route", "coding_agent",
        }
        self.assertTrue({field.name for field in fields(Run)}.isdisjoint(prohibited))
        source = (ROOT / "src/minitz_os/engine/run.py").read_text(encoding="utf-8")
        syntax = ast.parse(source)
        for node in ast.walk(syntax):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name != "minitz.migration" for alias in node.names))
            elif isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, "migration")

    def test_project_scope_fails_closed_without_foreign_identity_leak(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        with self.assertRaises(RunScopeError) as caught:
            self.runs.get_run(self.beta_access, run.run_ref)
        self.assertNotIn(self.alpha.project_ref.value, str(caught.exception))
        foreign_ref = RunRef(self.beta.project_ref, run.run_ref.run_id)
        with self.assertRaises(RunScopeError):
            self.runs.get_run(self.alpha_access, foreign_ref)

    def test_persisted_run_and_attempt_integrity_is_enforced(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://worker-a",
            lease_seconds=10,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            for table in ("runs", "run_state_versions", "execution_attempts"):
                with self.subTest(table=table, operation="update"):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(f"UPDATE {table} SET record_sha256 = ?", ("0" * 64,))
                    connection.rollback()
                with self.subTest(table=table, operation="delete"):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(f"DELETE FROM {table}")
                    connection.rollback()
            connection.execute("DROP TRIGGER execution_attempts_no_update")
            connection.execute(
                "UPDATE execution_attempts SET owner_ref = ? WHERE project_id = ? AND run_id = ? AND attempt_id = ?",
                (
                    "executor://tampered",
                    self.alpha.project_ref.value,
                    run.run_ref.run_id,
                    attempt.attempt_id,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(RunIntegrityError):
            self.runs.list_attempts(self.alpha_access, run.run_ref)

    def test_run_identity_and_state_digest_tampering_fail_closed(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER runs_no_update")
            connection.execute(
                "UPDATE runs SET created_at = ? WHERE project_id = ? AND run_id = ?",
                ("2030-01-01T00:00:00+00:00", self.alpha.project_ref.value, run.run_id),
            )
            connection.commit()
            with self.assertRaises(RunIntegrityError):
                self.runs.get_run(self.alpha_access, run.run_ref)
            connection.execute(
                "UPDATE runs SET created_at = ? WHERE project_id = ? AND run_id = ?",
                (run.created_at, self.alpha.project_ref.value, run.run_id),
            )
            connection.commit()
            self.assertEqual(self.runs.get_run(self.alpha_access, run.run_ref), run)

            connection.execute("DROP TRIGGER run_state_versions_no_update")
            connection.execute(
                "UPDATE run_state_versions SET updated_at = ? "
                "WHERE project_id = ? AND run_id = ? AND state_version = 1",
                ("2030-01-01T00:00:00+00:00", self.alpha.project_ref.value, run.run_id),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(RunIntegrityError):
            self.runs.get_run(self.alpha_access, run.run_ref)

    def test_cancellation_state_suffix_truncation_cannot_restore_authority(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://worker-a",
            lease_seconds=10,
        )
        cancelled = self.runs.request_run_cancellation(self.alpha_access, run.run_ref)
        connection = sqlite3.connect(self.database_path)
        try:
            marker = connection.execute(
                "SELECT cancellation_requested_at FROM run_cancellations "
                "WHERE project_id = ? AND run_id = ?",
                (self.alpha.project_ref.value, run.run_id),
            ).fetchone()
            self.assertEqual(marker[0], cancelled.cancellation_requested_at)
            connection.execute("DROP TRIGGER run_state_versions_no_delete")
            connection.execute(
                "DELETE FROM run_state_versions "
                "WHERE project_id = ? AND run_id = ? AND state_version = ?",
                (
                    self.alpha.project_ref.value,
                    run.run_id,
                    cancelled.state_version,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(RunIntegrityError):
            self.runs.get_run(self.alpha_access, run.run_ref)
        with self.assertRaises(RunIntegrityError):
            self.runs.assert_current_run_authority(self.alpha_access, attempt)

    def test_completion_head_and_cancellation_markers_are_guarded(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://worker-a",
            lease_seconds=10,
        )
        self.runs.release_run_lease(self.alpha_access, attempt)
        self.runs.request_run_cancellation(self.alpha_access, run.run_ref)
        connection = sqlite3.connect(self.database_path)
        try:
            for table in (
                "execution_attempt_completions",
                "run_state_heads",
                "run_cancellations",
            ):
                with self.subTest(table=table, operation="update"):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(
                            f"UPDATE {table} SET record_sha256 = ?",
                            ("0" * 64,),
                        )
                    connection.rollback()
                with self.subTest(table=table, operation="delete"):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(f"DELETE FROM {table}")
                    connection.rollback()
        finally:
            connection.close()

    def test_reader_snapshots_remain_consistent_during_transitions(self) -> None:
        def race(
            run: Run,
            transition: Callable[[], object],
            allowed_statuses: set[str],
        ) -> tuple[str, ...]:
            barrier = threading.Barrier(2)

            def read_repeatedly() -> tuple[str, ...]:
                barrier.wait(timeout=5)
                return tuple(
                    self.runs.get_run(self.alpha_access, run.run_ref).status
                    for _ in range(40)
                )

            def perform_transition() -> None:
                barrier.wait(timeout=5)
                transition()

            with ThreadPoolExecutor(max_workers=2) as executor:
                reader = executor.submit(read_repeatedly)
                writer = executor.submit(perform_transition)
                statuses = reader.result()
                writer.result()
            self.assertTrue(set(statuses) <= allowed_statuses)
            return statuses

        acquire_run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        race(
            acquire_run,
            lambda: self.runs.acquire_run_lease(
                self.alpha_access,
                acquire_run.run_ref,
                owner_ref="executor://acquirer",
                lease_seconds=10,
            ),
            {"PENDING", "RUNNING"},
        )

        renew_run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        renew_attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            renew_run.run_ref,
            owner_ref="executor://renewer",
            lease_seconds=10,
        )

        def renew_repeatedly() -> None:
            for _ in range(20):
                self.runs.renew_run_lease(
                    self.alpha_access,
                    renew_attempt,
                    lease_seconds=0.1,
                )

        race(renew_run, renew_repeatedly, {"RUNNING"})

        cancel_run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        self.runs.acquire_run_lease(
            self.alpha_access,
            cancel_run.run_ref,
            owner_ref="executor://canceller",
            lease_seconds=10,
        )
        race(
            cancel_run,
            lambda: self.runs.request_run_cancellation(
                self.alpha_access,
                cancel_run.run_ref,
            ),
            {"RUNNING", "CANCELLED"},
        )

    def test_superseded_attempt_completion_truncation_fails_closed(self) -> None:
        run, first, _ = self._expire_and_replace()
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER execution_attempt_completions_no_delete")
            connection.execute(
                "DELETE FROM execution_attempt_completions "
                "WHERE project_id = ? AND run_id = ? AND attempt_id = ?",
                (
                    self.alpha.project_ref.value,
                    run.run_id,
                    first.attempt_id,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(RunIntegrityError):
            self.runs.get_run(self.alpha_access, run.run_ref)
        with self.assertRaises(RunIntegrityError):
            self.runs.list_attempts(self.alpha_access, run.run_ref)


if __name__ == "__main__":
    unittest.main()
