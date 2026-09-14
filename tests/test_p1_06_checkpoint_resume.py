from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import ast
import hashlib
import inspect
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from typing import TypeVar
import unittest
import zipfile

import minitz_os.engine as minitz_engine
from minitz_os.engine import (
    Artifact,
    ArtifactService,
    Capability,
    CapabilityRef,
    CapabilityRegistry,
    CallLedgerService,
    CallUsage,
    CheckpointContractError,
    CheckpointConflictError,
    CheckpointIntegrityError,
    CheckpointScopeError,
    CheckpointService,
    ContentRef,
    EventLedger,
    ExecutionAttempt,
    Graph,
    FilesystemObjectStorageBackend,
    GraphRef,
    GraphService,
    Node,
    NodeExecutionAttempt,
    NodeExecutionAuthorityError,
    NodeExecutionService,
    NodeInputBinding,
    NodeRef,
    ProjectStore,
    RunCheckpointRef,
    RunCheckpoint,
    Run,
    RunMemoryService,
    RunService,
    Task,
    TaskRevisionService,
)
from minitz_os.engine.object_store import ContentSource


ROOT = Path(__file__).resolve().parents[1]
T = TypeVar("T")


class BlockingFilesystemObjectStorageBackend(FilesystemObjectStorageBackend):
    def __init__(self, root: str | Path) -> None:
        super().__init__(root)
        self.entered = threading.Event()
        self.release = threading.Event()
        self.operation: str | None = None

    def block_next(self, operation: str) -> None:
        self.operation = operation
        self.entered.clear()
        self.release.clear()

    def _wait_if_blocked(self, operation: str) -> None:
        if self.operation != operation:
            return
        self.operation = None
        self.entered.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test object-store operation was not released")

    def put(
        self,
        source: ContentSource,
        *,
        media_type: str,
        expected_digest: str | None = None,
        expected_size: int | None = None,
    ) -> ContentRef:
        self._wait_if_blocked("put")
        return super().put(
            source,
            media_type=media_type,
            expected_digest=expected_digest,
            expected_size=expected_size,
        )

    def read(self, content_ref: ContentRef) -> bytes:
        self._wait_if_blocked("read")
        return super().read(content_ref)


class CheckpointResumeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.database = root / "minitz_engine.sqlite3"
        self.store_root = root / "objects"
        self.projects = ProjectStore(self.database)
        alpha = self.projects.create_project(
            namespace="checkpoint-alpha",
            display_name="Checkpoint Alpha",
        )
        beta = self.projects.create_project(
            namespace="checkpoint-beta",
            display_name="Checkpoint Beta",
        )
        self.project = alpha.project
        self.access = alpha.access
        self.beta_access = beta.access
        self.capabilities = CapabilityRegistry(self.database)
        self.capability_ref = self.capabilities.register(
            Capability(
                CapabilityRef("checkpoint.work", "1.0.0"),
                "Resume durable checkpoint work",
            )
        ).capability_ref
        self.tasks = TaskRevisionService(self.database)
        self.task = self._create_task("checkpoint-task")
        self.runs = RunService(self.database)
        self.run_record = self.runs.create_run(self.access, task_ref=self.task.task_ref)
        self.run_attempt = self.runs.acquire_run_lease(
            self.access,
            self.run_record.run_ref,
            owner_ref="controller://checkpoint",
            lease_seconds=120,
        )
        self.graphs = GraphService(self.database)
        graph_ref = GraphRef.new(self.project.project_ref)
        self.node_a_ref = NodeRef.new(graph_ref)
        self.node_b_ref = NodeRef.new(graph_ref)
        self.node_c_ref = NodeRef.new(graph_ref)
        self.nodes = (
            Node(
                self.node_a_ref,
                "SPECIALIST_TASK",
                (self.capability_ref,),
                (),
                (),
                {"result": "schema://checkpoint/result"},
                None,
                "READ_ONLY",
                {},
                (),
            ),
            Node(
                self.node_b_ref,
                "SPECIALIST_TASK",
                (self.capability_ref,),
                (self.node_a_ref,),
                (
                    NodeInputBinding.from_node_output(
                        "a-result",
                        self.node_a_ref,
                        "result",
                    ),
                ),
                {"result": "schema://checkpoint/result"},
                None,
                "READ_ONLY",
                {},
                (),
            ),
            Node(
                self.node_c_ref,
                "SPECIALIST_TASK",
                (self.capability_ref,),
                (),
                (),
                {"result": "schema://checkpoint/result"},
                None,
                "READ_ONLY",
                {},
                (),
            ),
        )
        self.graph = self.graphs.create_graph(
            self.access,
            graph_ref=graph_ref,
            task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            run_ref=self.run_record.run_ref,
            nodes=self.nodes,
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=self.run_attempt,
        )
        self.executions = NodeExecutionService(self.database)
        self.executions.prepare_run(self.access, self.run_record.run_ref)
        self.artifacts = ArtifactService(self.database)
        self.backend = FilesystemObjectStorageBackend(self.store_root)
        self.checkpoints = CheckpointService(self.database, self.backend)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _create_task(self, key: str) -> Task:
        return self.tasks.create_task(
            self.access,
            project_ref=self.project.project_ref,
            idempotency_key=key,
            task_type="checkpoint.work",
            objective="Resume exact durable work after process loss",
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
        seconds: float = 60,
    ) -> NodeExecutionAttempt:
        attempt = self.executions.lease_node(
            self.access,
            node_ref,
            authority_attempt=self.run_attempt,
            owner_ref=f"executor://{marker}",
            lease_seconds=seconds,
            idempotency_key=f"{marker}-lease",
        )
        self.executions.start_node(
            self.access,
            attempt,
            idempotency_key=f"{marker}-start",
        )
        return attempt

    def _artifact(self, marker: str) -> Artifact:
        return self.artifacts.publish_from_run(
            self.access,
            producer_attempt=self.run_attempt,
            expected_task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            role=f"checkpoint.{marker}",
            content_ref=ContentRef.from_bytes(marker.encode(), media_type="text/plain"),
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=(),
            derivation_type="checkpoint.output",
            metadata={},
        )

    def _complete_a(self) -> Artifact:
        attempt = self._lease_and_start(self.node_a_ref, "a")
        output = self._artifact("a-output")
        self.executions.finalize_node(
            self.access,
            attempt,
            outputs={"result": output.artifact_ref},
            evidence={},
            acceptance_criteria=(),
            idempotency_key="a-finalize",
        )
        self.executions.prepare_run(self.access, self.run_record.run_ref)
        return output

    def _complete_c(self) -> Artifact:
        attempt = self._lease_and_start(self.node_c_ref, "c")
        output = self._artifact("c-output")
        self.executions.finalize_node(
            self.access,
            attempt,
            outputs={"result": output.artifact_ref},
            evidence={},
            acceptance_criteria=(),
            idempotency_key="c-finalize",
        )
        self.executions.prepare_run(self.access, self.run_record.run_ref)
        return output

    def _revise_graph(self, *, change_a_source: bool) -> Graph:
        next_ref = GraphRef(
            self.graph.project_ref,
            self.graph.graph_id,
            self.graph.revision + 1,
        )
        a_ref = NodeRef(next_ref, self.node_a_ref.node_id)
        b_ref = NodeRef(next_ref, self.node_b_ref.node_id)
        c_ref = NodeRef(next_ref, self.node_c_ref.node_id)
        a_inputs = (
            (
                NodeInputBinding.from_identity(
                    "changed-source",
                    self.project.project_ref,
                    ContentRef.from_bytes(b"changed-source", media_type="text/plain"),
                ),
            )
            if change_a_source
            else ()
        )
        nodes = (
            Node(
                a_ref,
                "SPECIALIST_TASK",
                (self.capability_ref,),
                (),
                a_inputs,
                {"result": "schema://checkpoint/result"},
                None,
                "READ_ONLY",
                {},
                (),
            ),
            Node(
                b_ref,
                "SPECIALIST_TASK",
                (self.capability_ref,),
                (a_ref,),
                (NodeInputBinding.from_node_output("a-result", a_ref, "result"),),
                {"result": "schema://checkpoint/result"},
                None,
                "READ_ONLY",
                {},
                (),
            ),
            Node(
                c_ref,
                "SPECIALIST_TASK",
                (self.capability_ref,),
                (),
                (),
                {"result": "schema://checkpoint/result"},
                None,
                "READ_ONLY",
                {},
                (),
            ),
        )
        return self.graphs.create_revision(
            self.access,
            prior_ref=self.graph.graph_ref,
            nodes=nodes,
            compiler_identity="compiler://checkpoint/replan",
            compiler_version="2.0.0",
            authority_attempt=self.run_attempt,
        )

    def _new_single_run(
        self,
        marker: str,
    ) -> tuple[Run, ExecutionAttempt, Graph, NodeRef, NodeExecutionService, CheckpointService]:
        run = self.runs.create_run(self.access, task_ref=self.task.task_ref)
        authority = self.runs.acquire_run_lease(
            self.access,
            run.run_ref,
            owner_ref=f"controller://{marker}",
            lease_seconds=120,
        )
        graph_ref = GraphRef.new(self.project.project_ref)
        node_ref = NodeRef.new(graph_ref)
        node = Node(
            node_ref,
            "SPECIALIST_TASK",
            (self.capability_ref,),
            (),
            (),
            {"result": "schema://checkpoint/result"},
            None,
            "READ_ONLY",
            {},
            (),
        )
        graph = self.graphs.create_graph(
            self.access,
            graph_ref=graph_ref,
            task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            run_ref=run.run_ref,
            nodes=(node,),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=authority,
        )
        executions = NodeExecutionService(self.database)
        executions.prepare_run(self.access, run.run_ref)
        checkpoints = CheckpointService(self.database, self.backend)
        return run, authority, graph, node_ref, executions, checkpoints

    def test_t01_public_checkpoint_interfaces_exist(self) -> None:
        for name in (
            "RunCheckpoint",
            "RunCheckpointRef",
            "CheckpointReconciliationService",
            "CheckpointService",
            "CheckpointIntegrityError",
        ):
            self.assertTrue(hasattr(minitz, name), name)
        self.assertTrue(callable(getattr(CheckpointService, "createCheckpoint")))
        self.assertTrue(callable(getattr(CheckpointService, "resumeRun")))
        self.assertIs(
            minitz_engine.checkpoint_reconciliation_service,
            minitz_engine.CheckpointReconciliationService,
        )
        self.assertIn(
            "latest_checkpoint_ref",
            inspect.signature(minitz_engine.RunMemory).parameters,
        )

    def test_t02_checkpoint_atomically_binds_content_artifact_event_and_latest_ref(self) -> None:
        output = self._complete_a()
        workspace = self.backend.put(b"workspace", media_type="application/octet-stream")
        checkpoint = self.checkpoints.createCheckpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="checkpoint-one",
            workspace_snapshot_ref=workspace,
            continuation_refs=("runtime://checkpoint/provider-neutral",),
        )

        self.assertEqual(checkpoint.schema_version, "minitz_engine.run-checkpoint/v1")
        self.assertEqual(checkpoint.task_ref, self.task.task_ref)
        self.assertEqual(checkpoint.task_digest, self.task.canonical_digest)
        self.assertEqual(checkpoint.graph_ref, self.graph.graph_ref)
        self.assertEqual(checkpoint.graph_record_sha256, self.graph.record_sha256)
        self.assertIn(output.artifact_ref.value, checkpoint.completed_output_refs)
        self.assertTrue(self.backend.verify(checkpoint.content_ref))
        checkpoint_artifact = self.artifacts.get_artifact(
            self.access,
            checkpoint.artifact_ref,
        )
        self.assertEqual(
            checkpoint_artifact.source_artifact_refs,
            (output.artifact_ref,),
        )
        self.assertEqual(
            checkpoint_artifact.source_content_refs,
            (workspace,),
        )
        self.assertEqual(checkpoint_artifact.producer_run_ref, self.run_record.run_ref)
        self.assertEqual(
            checkpoint_artifact.producer_attempt_id,
            self.run_attempt.attempt_id,
        )
        checkpoint_event = EventLedger(self.database).get_event(
            self.access,
            checkpoint.event_ref,
        )
        self.assertEqual(checkpoint_event.payload_ref, checkpoint.content_ref)
        self.assertIn(checkpoint.artifact_ref.value, checkpoint_event.object_refs)
        self.assertEqual(
            self.checkpoints.get_latest_checkpoint(self.access, self.run_record.run_ref),
            checkpoint,
        )
        memory = RunMemoryService(self.database).reconstruct(self.access, self.run_record.run_ref)
        assert memory.latest_checkpoint_ref is not None
        self.assertEqual(memory.latest_checkpoint_ref.event_ref, checkpoint.event_ref)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM run_checkpoints").fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM run_checkpoint_heads").fetchone()[0],
                1,
            )
        second = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="checkpoint-two",
        )
        self.assertEqual(second.checkpoint_sequence, checkpoint.checkpoint_sequence + 1)
        self.assertGreater(second.event_sequence, checkpoint.event_sequence)
        self.assertEqual(
            self.checkpoints.get_latest_checkpoint(self.access, self.run_record.run_ref),
            second,
        )

    def test_t03_process_death_resume_preserves_a_and_recovers_b_with_new_fence(self) -> None:
        output = self._complete_a()
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="before-b",
        )
        old_attempt = self._lease_and_start(self.node_b_ref, "b-old", 0.05)
        time.sleep(0.08)

        restarted = CheckpointService(
            self.database,
            FilesystemObjectStorageBackend(self.store_root),
        )
        result = restarted.resumeRun(
            self.access,
            self.run_record.run_ref,
            checkpoint_ref=checkpoint.checkpoint_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="resume-b",
        )
        by_ref = {item.node_ref: item for item in result.memory.graphs[-1].nodes}
        latest_a = by_ref[self.node_a_ref].latest
        latest_b = by_ref[self.node_b_ref].latest
        assert latest_a is not None
        assert latest_b is not None
        self.assertEqual(latest_a.status, "SUCCEEDED")
        self.assertEqual(
            latest_a.outputs["result"],
            output.artifact_ref.value,
        )
        self.assertEqual(latest_b.status, "READY")
        self.assertEqual(result.recovered_node_refs, (self.node_b_ref,))
        new_attempt = self.executions.lease_node(
            self.access,
            self.node_b_ref,
            authority_attempt=self.run_attempt,
            owner_ref="executor://b-new",
            lease_seconds=60,
            idempotency_key="b-new-lease",
        )
        self.assertEqual(new_attempt.fence, old_attempt.fence + 1)

    def test_t04_late_old_fence_result_is_rejected_after_resume(self) -> None:
        self._complete_a()
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="late-checkpoint",
        )
        old_attempt = self._lease_and_start(self.node_b_ref, "late-old", 0.05)
        time.sleep(0.08)
        self.checkpoints.resume_run(
            self.access,
            self.run_record.run_ref,
            checkpoint_ref=checkpoint.checkpoint_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="late-resume",
        )
        self.executions.lease_node(
            self.access,
            self.node_b_ref,
            authority_attempt=self.run_attempt,
            owner_ref="executor://late-new",
            lease_seconds=60,
            idempotency_key="late-new-lease",
        )
        with self.assertRaises(NodeExecutionAuthorityError):
            self.executions.finalize_node(
                self.access,
                old_attempt,
                outputs={"result": self._artifact("late-output").artifact_ref},
                evidence={},
                acceptance_criteria=(),
                idempotency_key="late-old-finalize",
            )

    def test_t05_provider_cache_browser_conversation_and_workspace_are_not_authority(self) -> None:
        self._complete_a()
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="loss-checkpoint",
            continuation_refs=("provider-session://lost/opaque",),
        )
        for name in ("cache", "browser", "conversation", "workspace"):
            directory = Path(self.temporary.name) / name
            directory.mkdir()
            directory.rmdir()

        restarted = CheckpointService(
            self.database,
            FilesystemObjectStorageBackend(self.store_root),
        )
        result = restarted.resume_run(
            self.access,
            self.run_record.run_ref,
            checkpoint_ref=checkpoint.checkpoint_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="loss-resume",
        )
        self.assertEqual(result.checkpoint, checkpoint)
        self.assertEqual(result.memory.run.run_ref, self.run_record.run_ref)
        self.assertIn(self.node_a_ref, result.reconciliation.reused_node_refs)

    def test_t06_newer_events_and_current_state_win_over_older_checkpoint(self) -> None:
        self._complete_a()
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="older-checkpoint",
        )
        newer = EventLedger(self.database).append_event(
            self.access,
            project_ref=self.project.project_ref,
            task_ref=self.task.task_ref,
            run_ref=self.run_record.run_ref,
            graph_ref=self.graph.graph_ref,
            node_ref=None,
            event_type="CONTROLLER_OBSERVED",
            idempotency_key="newer-than-checkpoint",
            actor_ref="controller://checkpoint",
            object_refs=(),
            metadata={"observation": "durable-newer-truth"},
            payload_ref=None,
            authority_attempt=self.run_attempt,
        )
        result = self.checkpoints.resume_run(
            self.access,
            self.run_record.run_ref,
            checkpoint_ref=checkpoint.checkpoint_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="newer-resume",
        )
        self.assertGreater(
            result.reconciliation.current_event_high_water_mark,
            checkpoint.event_high_water_mark,
        )
        self.assertIn(newer.event_ref, tuple(item.event_ref for item in result.memory.events))
        a_decision = next(
            item
            for item in result.reconciliation.decisions
            if item.node_ref.node_id == self.node_a_ref.node_id
        )
        self.assertEqual(a_decision.action, "REUSE_CURRENT")

    def test_t07_current_graph_v2_wins_and_exact_compatible_output_is_reusable(self) -> None:
        output = self._complete_a()
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="v1-checkpoint",
        )
        graph_v2 = self._revise_graph(change_a_source=False)

        result = self.checkpoints.resume_run(
            self.access,
            self.run_record.run_ref,
            checkpoint_ref=checkpoint.checkpoint_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="v2-resume",
        )
        self.assertEqual(result.memory.current_graph_ref, graph_v2.graph_ref)
        self.assertEqual(result.reconciliation.current_graph_ref, graph_v2.graph_ref)
        a_decision = next(
            item
            for item in result.reconciliation.decisions
            if item.node_ref.node_id == self.node_a_ref.node_id
        )
        self.assertEqual(a_decision.action, "REUSE_CHECKPOINT")
        self.assertEqual(a_decision.reusable_output_refs, (output.artifact_ref.value,))
        current = {item.node_ref.node_id: item for item in result.memory.graphs[-1].nodes}
        a_latest = current[self.node_a_ref.node_id].latest
        b_latest = current[self.node_b_ref.node_id].latest
        assert a_latest is not None
        assert b_latest is not None
        self.assertEqual(a_latest.status, "SUCCEEDED")
        self.assertEqual(a_latest.outputs["result"], output.artifact_ref.value)
        self.assertEqual(b_latest.status, "READY")
        self.assertTrue(
            any(event.event_type == "NODE_OUTPUT_REUSED" for event in result.memory.events)
        )

    def test_t07b_newer_graph_success_wins_over_old_source_invalidation(self) -> None:
        old_output = self._complete_a()
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="newer-success-checkpoint",
        )
        graph_v2 = self._revise_graph(change_a_source=True)
        self.executions.prepare_run(self.access, self.run_record.run_ref)
        a_v2 = next(
            item.node_ref
            for item in graph_v2.nodes
            if item.node_id == self.node_a_ref.node_id
        )
        attempt = self.executions.lease_node(
            self.access,
            a_v2,
            authority_attempt=self.run_attempt,
            owner_ref="executor://newer-a",
            lease_seconds=60,
            idempotency_key="newer-a-lease",
        )
        self.executions.start_node(
            self.access,
            attempt,
            idempotency_key="newer-a-start",
        )
        current_output = self._artifact("newer-a-output")
        self.executions.finalize_node(
            self.access,
            attempt,
            outputs={"result": current_output.artifact_ref},
            evidence={},
            acceptance_criteria=(),
            idempotency_key="newer-a-finalize",
        )

        result = self.checkpoints.resume_run(
            self.access,
            self.run_record.run_ref,
            checkpoint_ref=checkpoint.checkpoint_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="newer-a-resume",
        )
        decision = next(
            item
            for item in result.reconciliation.decisions
            if item.node_ref.node_id == self.node_a_ref.node_id
        )
        self.assertEqual(decision.action, "REUSE_CURRENT")
        self.assertEqual(
            decision.reusable_output_refs,
            (current_output.artifact_ref.value,),
        )
        self.assertNotEqual(
            decision.reusable_output_refs,
            (old_output.artifact_ref.value,),
        )

    def test_t08_wrong_scope_missing_and_corrupt_content_fail_before_state_change(self) -> None:
        self._complete_a()
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="tamper-checkpoint",
        )
        before = RunMemoryService(self.database).reconstruct(self.access, self.run_record.run_ref)
        with self.assertRaises(CheckpointScopeError):
            self.checkpoints.get_checkpoint(self.beta_access, checkpoint.checkpoint_ref)
        wrong_run, wrong_authority, _, _, _, _ = self._new_single_run("wrong-run")
        with self.assertRaises(CheckpointConflictError):
            self.checkpoints.resume_run(
                self.access,
                wrong_run.run_ref,
                checkpoint_ref=checkpoint.checkpoint_ref,
                authority_attempt=wrong_authority,
                idempotency_key="wrong-run-resume",
            )
        wrong_ref = RunCheckpointRef(self.project.project_ref, "chk_" + "0" * 32)
        with self.assertRaises(Exception):
            self.checkpoints.resume_run(
                self.access,
                self.run_record.run_ref,
                checkpoint_ref=wrong_ref,
                authority_attempt=self.run_attempt,
                idempotency_key="wrong-resume",
            )
        locator = self.backend.location(checkpoint.content_ref).locator
        self.assertTrue(locator.startswith("file://"))
        content_path = Path(locator.removeprefix("file://"))
        content_path.write_bytes(b"corrupt")
        with self.assertRaises(CheckpointIntegrityError):
            self.checkpoints.resume_run(
                self.access,
                self.run_record.run_ref,
                checkpoint_ref=checkpoint.checkpoint_ref,
                authority_attempt=self.run_attempt,
                idempotency_key="corrupt-resume",
            )
        after = RunMemoryService(self.database).reconstruct(self.access, self.run_record.run_ref)
        self.assertEqual(after.semantic_digest, before.semantic_digest)

    def test_t09_succeeded_failed_and_cancelled_runs_cannot_resume(self) -> None:
        cases: list[tuple[Run, ExecutionAttempt, RunCheckpointRef, CheckpointService]] = []

        succeeded_run, succeeded_authority, _, succeeded_node, succeeded_exec, succeeded_cp = (
            self._new_single_run("succeeded")
        )
        succeeded_checkpoint = succeeded_cp.create_checkpoint(
            self.access,
            succeeded_run.run_ref,
            authority_attempt=succeeded_authority,
            idempotency_key="succeeded-before-terminal",
        )
        succeeded_attempt = succeeded_exec.lease_node(
            self.access,
            succeeded_node,
            authority_attempt=succeeded_authority,
            owner_ref="executor://succeeded",
            lease_seconds=60,
            idempotency_key="succeeded-lease",
        )
        succeeded_exec.start_node(
            self.access,
            succeeded_attempt,
            idempotency_key="succeeded-start",
        )
        succeeded_output = ArtifactService(self.database).publish_from_run(
            self.access,
            producer_attempt=succeeded_authority,
            expected_task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            role="checkpoint.succeeded-output",
            content_ref=ContentRef.from_bytes(b"succeeded", media_type="text/plain"),
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=(),
            derivation_type="checkpoint.output",
            metadata={},
        )
        succeeded_exec.finalize_node(
            self.access,
            succeeded_attempt,
            outputs={"result": succeeded_output.artifact_ref},
            evidence={},
            acceptance_criteria=(),
            idempotency_key="succeeded-finalize",
        )
        cases.append(
            (
                succeeded_run,
                succeeded_authority,
                succeeded_checkpoint.checkpoint_ref,
                succeeded_cp,
            )
        )

        failed_run, failed_authority, _, failed_node, failed_exec, failed_cp = (
            self._new_single_run("failed")
        )
        failed_checkpoint = failed_cp.create_checkpoint(
            self.access,
            failed_run.run_ref,
            authority_attempt=failed_authority,
            idempotency_key="failed-before-terminal",
        )
        failed_attempt = failed_exec.lease_node(
            self.access,
            failed_node,
            authority_attempt=failed_authority,
            owner_ref="executor://failed",
            lease_seconds=60,
            idempotency_key="failed-lease",
        )
        failed_exec.start_node(self.access, failed_attempt, idempotency_key="failed-start")
        failed_exec.fail_node(
            self.access,
            failed_attempt,
            category="DEPENDENCY_UNAVAILABLE",
            reason="terminal failure preserved exactly",
            evidence_refs=(),
            retry_possible=False,
            idempotency_key="failed-terminal",
        )
        cases.append((failed_run, failed_authority, failed_checkpoint.checkpoint_ref, failed_cp))

        cancelled_run, cancelled_authority, _, _, cancelled_exec, cancelled_cp = (
            self._new_single_run("cancelled")
        )
        cancelled_checkpoint = cancelled_cp.create_checkpoint(
            self.access,
            cancelled_run.run_ref,
            authority_attempt=cancelled_authority,
            idempotency_key="cancelled-before-terminal",
        )
        cancelled_exec.cancel_run(
            self.access,
            cancelled_run.run_ref,
            idempotency_key="cancelled-terminal",
            actor_ref="controller://cancelled",
        )
        cases.append(
            (
                cancelled_run,
                cancelled_authority,
                cancelled_checkpoint.checkpoint_ref,
                cancelled_cp,
            )
        )

        for index, (run, authority, checkpoint_ref, service) in enumerate(cases):
            with self.subTest(run=run.run_ref.run_id):
                with self.assertRaises(CheckpointConflictError):
                    service.resume_run(
                        self.access,
                        run.run_ref,
                        checkpoint_ref=checkpoint_ref,
                        authority_attempt=authority,
                        idempotency_key=f"terminal-resume-{index}",
                    )

    def test_t10_cross_project_checkpoint_reference_binding_fails_closed(self) -> None:
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="scope-checkpoint",
        )
        forged = RunCheckpointRef(
            self.beta_access.project_ref,
            checkpoint.checkpoint_ref.checkpoint_id,
        )
        with self.assertRaises(CheckpointScopeError):
            self.checkpoints.get_checkpoint(self.access, forged)
        with self.assertRaises(Exception):
            self.checkpoints.get_checkpoint(self.beta_access, forged)

    def test_t11_source_change_invalidates_only_dependent_branch_with_exact_cause(self) -> None:
        self._complete_a()
        c_output = self._complete_c()
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="source-v1-checkpoint",
        )
        graph_v2 = self._revise_graph(change_a_source=True)
        result = self.checkpoints.resume_run(
            self.access,
            self.run_record.run_ref,
            checkpoint_ref=checkpoint.checkpoint_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="source-v2-resume",
        )
        decisions = {item.node_ref.node_id: item for item in result.reconciliation.decisions}
        self.assertEqual(decisions[self.node_a_ref.node_id].action, "INVALIDATE")
        self.assertTrue(
            any(
                cause.startswith("source:")
                for cause in decisions[self.node_a_ref.node_id].causes
            )
        )
        self.assertEqual(decisions[self.node_b_ref.node_id].action, "INVALIDATE")
        self.assertIn(
            f"dependency:{self.node_a_ref.node_id}",
            decisions[self.node_b_ref.node_id].causes,
        )
        self.assertEqual(decisions[self.node_c_ref.node_id].action, "REUSE_CHECKPOINT")
        self.assertEqual(
            decisions[self.node_c_ref.node_id].reusable_output_refs,
            (c_output.artifact_ref.value,),
        )
        self.assertEqual(result.memory.current_graph_ref, graph_v2.graph_ref)
        current = {item.node_ref.node_id: item for item in result.memory.graphs[-1].nodes}
        c_latest = current[self.node_c_ref.node_id].latest
        assert c_latest is not None
        self.assertEqual(c_latest.status, "SUCCEEDED")
        self.assertEqual(c_latest.outputs["result"], c_output.artifact_ref.value)
        evidence = self.backend.read(result.evidence_ref).decode()
        self.assertIn(self.node_a_ref.node_id, evidence)
        self.assertIn(self.node_b_ref.node_id, evidence)

    def test_t12_concurrent_checkpoint_creation_is_idempotent_and_run_scoped(self) -> None:
        def create() -> RunCheckpoint:
            return CheckpointService(
                self.database,
                FilesystemObjectStorageBackend(self.store_root),
            ).create_checkpoint(
                self.access,
                self.run_record.run_ref,
                authority_attempt=self.run_attempt,
                idempotency_key="concurrent-checkpoint",
            )

        with ThreadPoolExecutor(max_workers=6) as executor:
            results = tuple(executor.map(lambda _: create(), range(12)))
        self.assertEqual(len({item.checkpoint_ref for item in results}), 1)
        self.assertEqual(len({item.content_ref for item in results}), 1)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM run_checkpoints WHERE run_id = ?",
                    (self.run_record.run_ref.run_id,),
                ).fetchone()[0],
                1,
            )
        first_resume = self.checkpoints.resume_run(
            self.access,
            self.run_record.run_ref,
            checkpoint_ref=results[0].checkpoint_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="concurrent-resume",
        )
        replayed_resume = CheckpointService(
            self.database,
            FilesystemObjectStorageBackend(self.store_root),
        ).resume_run(
            self.access,
            self.run_record.run_ref,
            checkpoint_ref=results[0].checkpoint_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="concurrent-resume",
        )
        self.assertEqual(replayed_resume.event, first_resume.event)
        self.assertEqual(replayed_resume.evidence_ref, first_resume.evidence_ref)
        self.assertEqual(
            replayed_resume.reconciliation,
            first_resume.reconciliation,
        )

        blocking_backend = BlockingFilesystemObjectStorageBackend(self.store_root)
        blocking_service = CheckpointService(self.database, blocking_backend)

        def while_storage_blocked(
            operation: str,
            action: Callable[[], T],
        ) -> T:
            blocking_backend.block_next(operation)
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(action)
                self.assertTrue(blocking_backend.entered.wait(timeout=2))
                unrelated_writer = sqlite3.connect(self.database, timeout=0.2)
                try:
                    unrelated_writer.execute("BEGIN IMMEDIATE")
                    unrelated_writer.rollback()
                finally:
                    unrelated_writer.close()
                    blocking_backend.release.set()
                return future.result(timeout=5)

        unlocked_checkpoint = while_storage_blocked(
            "put",
            lambda: blocking_service.create_checkpoint(
                self.access,
                self.run_record.run_ref,
                authority_attempt=self.run_attempt,
                idempotency_key="unlocked-storage-checkpoint",
            ),
        )
        self.assertIsInstance(unlocked_checkpoint, RunCheckpoint)
        verified_read = while_storage_blocked(
            "read",
            lambda: blocking_service.get_checkpoint(
                self.access,
                unlocked_checkpoint.checkpoint_ref,
            ),
        )
        self.assertEqual(verified_read, unlocked_checkpoint)
        unlocked_resume = while_storage_blocked(
            "put",
            lambda: blocking_service.resume_run(
                self.access,
                self.run_record.run_ref,
                checkpoint_ref=unlocked_checkpoint.checkpoint_ref,
                authority_attempt=self.run_attempt,
                idempotency_key="unlocked-storage-resume",
            ),
        )
        self.assertIsInstance(unlocked_resume, minitz_engine.ResumeResult)

    def test_t13_optional_continuation_refs_round_trip_and_reject_credentials(self) -> None:
        call_attempt = self._lease_and_start(self.node_c_ref, "call-node")
        calls = CallLedgerService(self.database)
        model = calls.start_model_call(
            self.access,
            call_attempt,
            idempotency_key="checkpoint-model-start",
            capability_ref=self.capability_ref,
            purpose="INITIAL",
            retry_of=None,
            provider_id="provider://checkpoint/neutral",
            model_id="model://checkpoint/test",
            deployment_id=None,
            runtime_id="runtime://checkpoint/model",
            input_refs=(),
            provider_trace_id=None,
        )
        tool = calls.start_tool_call(
            self.access,
            call_attempt,
            idempotency_key="checkpoint-tool-start",
            capability_ref=self.capability_ref,
            purpose="INITIAL",
            retry_of=None,
            parent_model_call_ref=model.call_ref,
            tool_id="tool://checkpoint/test",
            implementation_id="implementation://checkpoint/test/v1",
            runtime_id="runtime://checkpoint/tool",
            input_refs=(),
            provider_trace_id=None,
        )
        calls.finish_model_call(
            self.access,
            call_attempt,
            model.call_ref,
            idempotency_key="checkpoint-model-finish",
            status="SUCCEEDED",
            output_refs=(),
            usage=CallUsage.unknown(),
            cost=None,
            failure_category=None,
            failure_reason=None,
            failure_evidence_refs=(),
        )
        calls.finish_tool_call(
            self.access,
            call_attempt,
            tool.call_ref,
            idempotency_key="checkpoint-tool-finish",
            status="SUCCEEDED",
            output_refs=(),
            usage=CallUsage.unknown(),
            cost=None,
            failure_category=None,
            failure_reason=None,
            failure_evidence_refs=(),
        )
        self.executions.fail_node(
            self.access,
            call_attempt,
            category="TOOL_FAILURE",
            reason="exact durable failure for checkpoint round trip",
            evidence_refs=(),
            retry_possible=True,
            idempotency_key="checkpoint-call-node-failure",
        )
        workspace = self.backend.put(b"workspace", media_type="application/octet-stream")
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="refs-checkpoint",
            workspace_snapshot_ref=workspace,
            continuation_refs=(
                "runtime://local/session-opaque",
                "workspace://snapshot/materialization",
            ),
        )
        loaded = CheckpointService(
            self.database,
            FilesystemObjectStorageBackend(self.store_root),
        ).get_checkpoint(self.access, checkpoint.checkpoint_ref)
        self.assertEqual(loaded.workspace_snapshot_ref, workspace)
        self.assertEqual(loaded.continuation_refs, checkpoint.continuation_refs)
        self.assertEqual(
            set(loaded.call_refs),
            {model.call_ref.value, tool.call_ref.value},
        )
        call_node = next(
            item for item in loaded.nodes if item.node_ref == self.node_c_ref
        )
        self.assertEqual(call_node.attempts[-1].attempt_id, call_attempt.attempt_id)
        self.assertEqual(call_node.attempts[-1].fence, call_attempt.fence)
        self.assertEqual(call_node.failures[-1].category, "TOOL_FAILURE")
        self.assertIn(call_node.failures[-1].failure_ref, loaded.failure_refs)
        hostile_refs = (
            "https://user:password@example.invalid/session",
            "runtime://local/session?access_key=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            "runtime://local/session?token=credential-material",
            "runtime://local/session?private_key=credential-material",
        )
        for index, hostile_ref in enumerate(hostile_refs):
            with self.subTest(hostile_ref=hostile_ref):
                with self.assertRaises(CheckpointContractError):
                    self.checkpoints.create_checkpoint(
                        self.access,
                        self.run_record.run_ref,
                        authority_attempt=self.run_attempt,
                        idempotency_key=f"secret-checkpoint-{index}",
                        continuation_refs=(hostile_ref,),
                    )

    def test_t14_restart_readback_is_cache_independent_and_tamper_evident(self) -> None:
        self._complete_a()
        checkpoint = self.checkpoints.create_checkpoint(
            self.access,
            self.run_record.run_ref,
            authority_attempt=self.run_attempt,
            idempotency_key="restart-checkpoint",
        )
        restarted = CheckpointService(
            self.database,
            FilesystemObjectStorageBackend(self.store_root),
        )
        loaded = restarted.get_checkpoint(self.access, checkpoint.checkpoint_ref)
        self.assertEqual(loaded, checkpoint)
        memory = RunMemoryService(self.database).reconstruct(
            self.access,
            self.run_record.run_ref,
        )
        assert memory.latest_checkpoint_ref is not None
        self.assertEqual(memory.latest_checkpoint_ref.event_ref, checkpoint.event_ref)
        connection = sqlite3.connect(self.database)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE run_checkpoints SET graph_record_sha256 = ?",
                    ("0" * 64,),
                )
            connection.rollback()
            connection.execute("DROP TRIGGER run_checkpoints_no_update")
            connection.execute(
                "UPDATE run_checkpoints SET graph_record_sha256 = ?",
                ("0" * 64,),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(CheckpointIntegrityError):
            restarted.get_checkpoint(self.access, checkpoint.checkpoint_ref)

    def test_t15_predecessors_typecheck_build_and_installed_restart_pass(self) -> None:
        source = (ROOT / "tests/test_p1_06_checkpoint_resume.py").read_text(
            encoding="utf-8"
        )
        fixture_sources = tuple(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "tests/fixtures/p1_06_installed_writer.py",
                ROOT / "tests/fixtures/p1_06_installed_reader.py",
            )
        )
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
            for fixture_source in fixture_sources:
                self.assertNotIn(marker, fixture_source, marker)
        ast.parse(source)
        for fixture_source in fixture_sources:
            ast.parse(fixture_source)

        typecheck = subprocess.run(
            (sys.executable, "-m", "mypy", "--strict", "src"),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            typecheck.returncode,
            0,
            f"{typecheck.stdout}\n{typecheck.stderr}",
        )

        loader = unittest.TestLoader()
        predecessor = loader.loadTestsFromName("tests.test_p1_05_call_ledger")
        self.assertEqual(predecessor.countTestCases(), 16)

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
            wheels = tuple(wheel_root.glob("minitz_engine-*.whl"))
            self.assertEqual(len(wheels), 1)
            wheel_path = wheels[0]
            source_paths = tuple(sorted((ROOT / "src/minitz").glob("*.py")))
            with zipfile.ZipFile(wheel_path) as archive:
                wheel_names = {
                    name
                    for name in archive.namelist()
                    if name.startswith("minitz/") and name.endswith(".py")
                }
                self.assertEqual(
                    wheel_names,
                    {f"minitz/{path.name}" for path in source_paths},
                )
                for path in source_paths:
                    self.assertEqual(
                        hashlib.sha256(archive.read(f"minitz/{path.name}")).hexdigest(),
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
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
                    "MINITZ_DATABASE": str(qualification_root / "restart.sqlite3"),
                    "MINITZ_INSTALLED": str(installed),
                    "MINITZ_OBJECT_ROOT": str(qualification_root / "object-store"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(installed),
                }
            )
            writer = subprocess.run(
                (
                    sys.executable,
                    str(ROOT / "tests/fixtures/p1_06_installed_writer.py"),
                ),
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
                    "MINITZ_A_REF": identity["a_ref"],
                    "MINITZ_B_REF": identity["b_ref"],
                    "MINITZ_CHECKPOINT_ID": identity["checkpoint_id"],
                    "MINITZ_OLD_FENCE": str(identity["old_fence"]),
                    "MINITZ_OUTPUT_REF": identity["output_ref"],
                    "MINITZ_PROJECT_ID": identity["project_id"],
                    "MINITZ_RUN_ID": identity["run_id"],
                    "MINITZ_TOKEN": identity["token"],
                }
            )
            time.sleep(0.08)
            reader = subprocess.run(
                (
                    sys.executable,
                    str(ROOT / "tests/fixtures/p1_06_installed_reader.py"),
                ),
                cwd=qualification_root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(reader.returncode, 0, f"{reader.stdout}\n{reader.stderr}")


if __name__ == "__main__":
    unittest.main()
