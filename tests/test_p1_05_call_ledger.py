from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
from typing import cast
import unittest
import zipfile

import biella
from biella import (
    Artifact,
    ArtifactRef,
    ArtifactService,
    CallAuthorityError,
    CallConflictError,
    CallContractError,
    CallCost,
    CallIntegrityError,
    CallLedgerService,
    CallScopeError,
    CallUsage,
    Capability,
    CapabilityRef,
    CapabilityRegistry,
    ContentRef,
    GraphRef,
    GraphService,
    ModelCall,
    ModelCallRef,
    Node,
    NodeExecutionAttempt,
    NodeExecutionService,
    NodeRef,
    ProjectAccess,
    ProjectRef,
    ProjectStore,
    RunMemoryService,
    RunService,
    TaskRevisionService,
    ToolCall,
    ToolCallRef,
    UsageMetric,
)


ROOT = Path(__file__).resolve().parents[1]


class CallLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "biella.sqlite3"
        projects = ProjectStore(self.database_path)
        alpha = projects.create_project(namespace="calls-alpha", display_name="Calls Alpha")
        beta = projects.create_project(namespace="calls-beta", display_name="Calls Beta")
        self.alpha = alpha.project.project_ref
        self.alpha_access = alpha.access
        self.beta = beta.project.project_ref
        self.beta_access = beta.access
        self.capability_ref = CapabilityRegistry(self.database_path).register(
            Capability(
                CapabilityRef("calls.invoke", "1.0.0"),
                "Invoke arbitrary provider-neutral model and tool implementations",
            )
        ).capability_ref
        self.tasks = TaskRevisionService(self.database_path)
        self.task = self.tasks.create_task(
            self.alpha_access,
            project_ref=self.alpha,
            idempotency_key="call-ledger-task",
            task_type="calls.invoke",
            objective="Record exact model and tool execution evidence",
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
        self.runs = RunService(self.database_path)
        self.run_record = self.runs.create_run(
            self.alpha_access,
            task_ref=self.task.task_ref,
        )
        self.run_attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            self.run_record.run_ref,
            owner_ref="controller://call-ledger",
            lease_seconds=300,
        )
        graph_ref = GraphRef.new(self.alpha)
        self.node_ref = NodeRef.new(graph_ref)
        self.node = Node(
            self.node_ref,
            "MODEL_OR_TOOL",
            (self.capability_ref,),
            (),
            (),
            {},
            None,
            "PROJECT_WRITE",
            {},
            (),
        )
        self.graph = GraphService(self.database_path).create_graph(
            self.alpha_access,
            graph_ref=graph_ref,
            task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            run_ref=self.run_record.run_ref,
            nodes=(self.node,),
            compiler_identity=None,
            compiler_version=None,
            authority_attempt=self.run_attempt,
        )
        self.executions = NodeExecutionService(self.database_path)
        self.executions.prepare_run(self.alpha_access, self.run_record.run_ref)
        leased = self.executions.lease_node(
            self.alpha_access,
            self.node_ref,
            authority_attempt=self.run_attempt,
            owner_ref="executor://call-ledger",
            lease_seconds=300,
            idempotency_key="call-ledger-node-lease",
        )
        self.node_attempt = leased
        self.executions.start_node(
            self.alpha_access,
            leased,
            idempotency_key="call-ledger-node-start",
        )
        self.artifacts = ArtifactService(self.database_path)
        self.alpha_artifact = self._artifact(
            self.alpha_access,
            self.alpha,
            "alpha-output",
        )
        self.beta_artifact = self._artifact(
            self.beta_access,
            self.beta,
            "beta-output",
        )
        self.request_ref = ContentRef.from_bytes(
            b'{"messages":[{"role":"user","content":"hello"}]}',
            media_type="application/json",
        )
        self.response_ref = ContentRef.from_bytes(
            b'{"result":"hello"}',
            media_type="application/json",
        )
        self.ledger = CallLedgerService(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _artifact(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        marker: str,
    ) -> Artifact:
        return self.artifacts.create_artifact(
            access,
            project_ref=project_ref,
            role=f"call.{marker}",
            content_ref=ContentRef.from_bytes(
                marker.encode(),
                media_type="application/octet-stream",
            ),
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=(),
            derivation_type="call.fixture",
            metadata={},
        )

    def _model(
        self,
        key: str,
        *,
        purpose: str = "INITIAL",
        retry_of: ModelCallRef | None = None,
        provider_id: str = "provider://reference/alpha",
        model_id: str = "model://reference/arbitrary-v1",
        deployment_id: str | None = "deployment://reference/cpu-a",
        runtime_id: str = "runtime://reference/python-3.14",
        provider_trace_id: str | None = "trace-reference-001",
    ) -> ModelCall:
        return self.ledger.start_model_call(
            self.alpha_access,
            self.node_attempt,
            idempotency_key=key,
            capability_ref=self.capability_ref,
            purpose=purpose,
            retry_of=retry_of,
            provider_id=provider_id,
            model_id=model_id,
            deployment_id=deployment_id,
            runtime_id=runtime_id,
            input_refs=(self.request_ref,),
            provider_trace_id=provider_trace_id,
        )

    def _tool(
        self,
        key: str,
        *,
        parent: ModelCallRef | None = None,
        purpose: str = "INITIAL",
        retry_of: ToolCallRef | None = None,
    ) -> ToolCall:
        return self.ledger.start_tool_call(
            self.alpha_access,
            self.node_attempt,
            idempotency_key=key,
            capability_ref=self.capability_ref,
            purpose=purpose,
            retry_of=retry_of,
            parent_model_call_ref=parent,
            tool_id="tool://reference/arbitrary-name",
            implementation_id="implementation://reference/tool-v7",
            runtime_id="runtime://reference/python-3.14",
            input_refs=(self.request_ref,),
            provider_trace_id=None,
        )

    def test_t01_model_call_exact_execution_attribution_round_trip(self) -> None:
        expected_exports = {
            "ModelCall",
            "ToolCall",
            "ModelCallRef",
            "ToolCallRef",
            "CallLedgerService",
            "CallUsage",
            "UsageMetric",
        }
        self.assertTrue(expected_exports.issubset(set(biella.__all__)))
        call = self._model("model-exact-attribution")
        self.assertEqual(call.status, "RUNNING")
        self.assertEqual(call.project_ref, self.alpha)
        self.assertEqual(call.task_ref, self.task.task_ref)
        self.assertEqual(call.run_ref, self.run_record.run_ref)
        self.assertEqual(call.graph_ref, self.graph.graph_ref)
        self.assertEqual(call.node_ref, self.node_ref)
        self.assertEqual(call.node_attempt_id, self.node_attempt.attempt_id)
        self.assertEqual(call.node_fence, self.node_attempt.fence)
        self.assertEqual(call.run_attempt_id, self.node_attempt.run_attempt_id)
        self.assertEqual(call.run_fence, self.node_attempt.run_fence)
        self.assertEqual(
            CallLedgerService(self.database_path).get_model_call(
                self.alpha_access,
                call.call_ref,
            ),
            call,
        )

    def test_t02_direct_tool_call_has_exact_implementation_identity(self) -> None:
        call = self._tool("direct-tool")
        self.assertIsNone(call.parent_model_call_ref)
        self.assertEqual(call.tool_id, "tool://reference/arbitrary-name")
        self.assertEqual(
            call.implementation_id,
            "implementation://reference/tool-v7",
        )
        self.assertEqual(call.attempt.record_sha256, self.node_attempt.record_sha256)

    def test_t03_nested_tool_call_requires_exact_parent_and_authority(self) -> None:
        parent = self._model("nested-model")
        nested = self._tool("nested-tool", parent=parent.call_ref)
        self.assertEqual(nested.parent_model_call_ref, parent.call_ref)
        forged_parent = ModelCallRef(self.beta, parent.call_ref.call_id)
        with self.assertRaises(CallScopeError):
            self._tool("foreign-parent", parent=forged_parent)
        stale_attempt = replace(self.node_attempt, fence=self.node_attempt.fence + 1)
        with self.assertRaises(CallAuthorityError):
            self.ledger.start_tool_call(
                self.alpha_access,
                stale_attempt,
                idempotency_key="stale-tool-authority",
                capability_ref=self.capability_ref,
                purpose="INITIAL",
                retry_of=None,
                parent_model_call_ref=None,
                tool_id="tool://reference/stale",
                implementation_id="implementation://reference/stale",
                runtime_id="runtime://reference/stale",
                input_refs=(),
                provider_trace_id=None,
            )

    def test_t04_success_failure_timeout_and_cancel_are_terminal(self) -> None:
        for status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"):
            with self.subTest(status=status):
                call = self._model(f"terminal-{status.lower()}")
                finished = self.ledger.finish_model_call(
                    self.alpha_access,
                    self.node_attempt,
                    call.call_ref,
                    idempotency_key=f"finish-{status.lower()}",
                    status=status,
                    output_refs=(self.response_ref,) if status == "SUCCEEDED" else (),
                    usage=None,
                    cost=None,
                    failure_category=None if status == "SUCCEEDED" else "PROVIDER_FAILURE",
                    failure_reason=None if status == "SUCCEEDED" else f"durable {status.lower()}",
                    failure_evidence_refs=(),
                )
                self.assertEqual(finished.status, status)
                self.assertIsNotNone(finished.completed_at)

    def test_t05_retries_are_new_calls_and_terminal_state_never_regresses(self) -> None:
        failed = self._model("retry-original")
        terminal = self.ledger.finish_model_call(
            self.alpha_access,
            self.node_attempt,
            failed.call_ref,
            idempotency_key="retry-original-failed",
            status="FAILED",
            output_refs=(),
            usage=None,
            cost=None,
            failure_category="INFRASTRUCTURE",
            failure_reason="reference transport failed",
            failure_evidence_refs=(),
        )
        retry = self._model(
            "retry-new-call",
            purpose="INFRASTRUCTURE_RETRY",
            retry_of=failed.call_ref,
        )
        self.assertNotEqual(retry.call_ref, failed.call_ref)
        self.assertEqual(retry.retry_of, failed.call_ref)
        intentional = self._model(
            "intentional-repeat-call",
            purpose="INTENTIONAL_REPEAT",
            retry_of=failed.call_ref,
        )
        repair = self._model(
            "repair-replan-call",
            purpose="REPAIR_REPLAN",
            retry_of=failed.call_ref,
        )
        self.assertEqual(
            {retry.purpose, intentional.purpose, repair.purpose},
            {"INFRASTRUCTURE_RETRY", "INTENTIONAL_REPEAT", "REPAIR_REPLAN"},
        )
        self.assertEqual(
            len({retry.call_ref, intentional.call_ref, repair.call_ref}),
            3,
        )
        with self.assertRaises(CallConflictError):
            self.ledger.finish_model_call(
                self.alpha_access,
                self.node_attempt,
                terminal.call_ref,
                idempotency_key="terminal-regression",
                status="SUCCEEDED",
                output_refs=(self.response_ref,),
                usage=None,
                cost=None,
                failure_category=None,
                failure_reason=None,
                failure_evidence_refs=(),
            )

    def test_t06_usage_metrics_retain_per_field_measurement_source(self) -> None:
        call = self._model("known-usage")
        usage = CallUsage(
            input_tokens=UsageMetric(120, "PROVIDER_REPORTED"),
            output_tokens=UsageMetric(30, "PROVIDER_REPORTED"),
            reasoning_tokens=UsageMetric(9, "ADAPTER_DERIVED"),
            cached_input_tokens=UsageMetric(80, "PROVIDER_REPORTED"),
            cache_write_tokens=UsageMetric(None, None),
        )
        finished = self.ledger.finish_model_call(
            self.alpha_access,
            self.node_attempt,
            call.call_ref,
            idempotency_key="known-usage-finish",
            status="SUCCEEDED",
            output_refs=(self.response_ref,),
            usage=usage,
            cost=None,
            failure_category=None,
            failure_reason=None,
            failure_evidence_refs=(),
        )
        self.assertEqual(finished.usage, usage)
        self.assertEqual(
            cast(CallUsage, finished.usage).reasoning_tokens.source,
            "ADAPTER_DERIVED",
        )

    def test_t07_unknown_usage_and_cost_remain_unknown(self) -> None:
        call = self._model("unknown-usage")
        finished = self.ledger.finish_model_call(
            self.alpha_access,
            self.node_attempt,
            call.call_ref,
            idempotency_key="unknown-usage-finish",
            status="SUCCEEDED",
            output_refs=(),
            usage=CallUsage.unknown(),
            cost=None,
            failure_category=None,
            failure_reason=None,
            failure_evidence_refs=(),
        )
        self.assertTrue(
            all(item.value is None for item in cast(CallUsage, finished.usage).metrics)
        )
        self.assertIsNone(finished.cost)
        with self.assertRaises(CallContractError):
            UsageMetric(1, None)

    def test_t08_cost_is_optional_exact_and_evidence_backed(self) -> None:
        call = self._model("known-cost")
        cost = CallCost(
            amount_decimal="0.001250",
            currency="USD",
            source="PROVIDER_REPORTED",
            pricing_identity="pricing://provider/invoice-line-v1",
        )
        finished = self.ledger.finish_model_call(
            self.alpha_access,
            self.node_attempt,
            call.call_ref,
            idempotency_key="known-cost-finish",
            status="SUCCEEDED",
            output_refs=(),
            usage=None,
            cost=cost,
            failure_category=None,
            failure_reason=None,
            failure_evidence_refs=(),
        )
        self.assertEqual(finished.cost, cost)
        self.assertNotIn("price", inspect.getsource(biella.CallLedgerService).casefold())

    def test_t09_large_payloads_and_outputs_are_exact_refs_only(self) -> None:
        call = self._model("content-ref-only")
        finished = self.ledger.finish_model_call(
            self.alpha_access,
            self.node_attempt,
            call.call_ref,
            idempotency_key="content-ref-only-finish",
            status="SUCCEEDED",
            output_refs=(self.response_ref, self.alpha_artifact.artifact_ref),
            usage=None,
            cost=None,
            failure_category=None,
            failure_reason=None,
            failure_evidence_refs=(),
        )
        self.assertEqual(
            finished.output_refs,
            tuple(sorted((self.response_ref, self.alpha_artifact.artifact_ref), key=lambda item: item.value)),
        )
        fields = set(ModelCall.__dataclass_fields__)
        self.assertFalse({"prompt", "request_body", "response_body", "api_key"} & fields)

    def test_t10_credentials_and_provider_error_echoes_are_rejected(self) -> None:
        with self.assertRaises(CallContractError):
            self._model("secret-provider", provider_id="provider://sk-secret-value")
        with self.assertRaises(CallContractError):
            self._model(
                "aws-trace-secret",
                provider_trace_id="AKIAABCDEFGHIJKLMNOP",
            )
        with self.assertRaises(CallContractError):
            self._model(
                "github-trace-secret",
                provider_trace_id="ghp_abcdefghijklmnopqrstuvwxyz123456",
            )
        with self.assertRaises(CallContractError):
            self._model(
                "github-fine-grained-secret",
                provider_trace_id="github_pat_abcdefghijklmnopqrstuvwxyz123456",
            )
        with self.assertRaises(CallContractError):
            self._model(
                "generic-access-key-secret",
                provider_trace_id="access_key=abcdefghijklmnopqrstuvwxyz1234567890",
            )
        call = self._model("secret-error-call")
        with self.assertRaises(CallContractError):
            self.ledger.finish_model_call(
                self.alpha_access,
                self.node_attempt,
                call.call_ref,
                idempotency_key="secret-error-finish",
                status="FAILED",
                output_refs=(),
                usage=None,
                cost=None,
                failure_category="AUTHENTICATION",
                failure_reason="Authorization: Bearer sk-secret-value",
                failure_evidence_refs=(),
            )
        database_bytes = self.database_path.read_bytes()
        self.assertNotIn(b"sk-secret-value", database_bytes)
        self.assertNotIn(b"AKIAABCDEFGHIJKLMNOP", database_bytes)
        self.assertNotIn(b"ghp_abcdefghijklmnopqrstuvwxyz123456", database_bytes)
        self.assertNotIn(
            b"github_pat_abcdefghijklmnopqrstuvwxyz123456",
            database_bytes,
        )
        self.assertNotIn(
            b"access_key=abcdefghijklmnopqrstuvwxyz1234567890",
            database_bytes,
        )

    def test_t11_project_isolation_and_foreign_output_fail_closed(self) -> None:
        call = self._model("project-isolation")
        with self.assertRaises(CallScopeError):
            self.ledger.get_model_call(self.beta_access, call.call_ref)
        with self.assertRaises(CallScopeError):
            self.ledger.finish_model_call(
                self.alpha_access,
                self.node_attempt,
                call.call_ref,
                idempotency_key="foreign-output-finish",
                status="SUCCEEDED",
                output_refs=(self.beta_artifact.artifact_ref,),
                usage=None,
                cost=None,
                failure_category=None,
                failure_reason=None,
                failure_evidence_refs=(),
            )

    def test_t12_arbitrary_provider_model_tool_and_runtime_ids_are_open(self) -> None:
        model = self._model(
            "arbitrary-identities",
            provider_id="provider://newco/future-stack",
            model_id="model://newco/unannounced-revision-934",
            deployment_id=None,
            runtime_id="runtime://edge/custom-generation-88",
            provider_trace_id=None,
        )
        tool = self.ledger.start_tool_call(
            self.alpha_access,
            self.node_attempt,
            idempotency_key="arbitrary-tool",
            capability_ref=self.capability_ref,
            purpose="INITIAL",
            retry_of=None,
            parent_model_call_ref=model.call_ref,
            tool_id="tool://newco/unseen-tool-42",
            implementation_id="implementation://newco/rev-ffffffff",
            runtime_id="runtime://wasm/generation-2026-08",
            input_refs=(),
            provider_trace_id="opaque-supplementary-trace",
        )
        self.assertEqual(model.provider_id, "provider://newco/future-stack")
        self.assertEqual(tool.tool_id, "tool://newco/unseen-tool-42")
        memory = RunMemoryService(self.database_path).reconstruct(
            self.alpha_access,
            self.run_record.run_ref,
        )
        self.assertEqual(
            tuple(item.call_ref for item in memory.extension_refs[-2:]),
            (model.call_ref.value, tool.call_ref.value),
        )

    def test_t13_runtime_identity_and_hosted_limitations_are_explicit(self) -> None:
        exact = self._model("runtime-exact")
        limited = self._model(
            "runtime-limited",
            deployment_id=None,
            runtime_id="runtime://hosted/provider-reported-only",
        )
        self.assertIsNotNone(exact.deployment_id)
        self.assertIsNone(limited.deployment_id)
        self.assertEqual(limited.runtime_id, "runtime://hosted/provider-reported-only")

    def test_t14_events_run_memory_and_provider_trace_are_independent(self) -> None:
        model = self._model("memory-model", provider_trace_id=None)
        tool = self._tool("memory-tool", parent=model.call_ref)
        memory = RunMemoryService(self.database_path).reconstruct(
            self.alpha_access,
            self.run_record.run_ref,
        )
        call_events = tuple(
            item for item in memory.extension_refs if item.kind in {"MODEL_CALL", "TOOL_CALL"}
        )
        self.assertEqual(len(call_events), 2)
        self.assertEqual(
            self.ledger.get_model_call_for_event(
                self.alpha_access,
                call_events[0].event_ref,
            ),
            model,
        )
        self.assertEqual(
            self.ledger.get_tool_call_for_event(
                self.alpha_access,
                call_events[1].event_ref,
            ),
            tool,
        )

    def test_t15_idempotency_concurrency_restart_integrity_and_build_gate(self) -> None:
        first = self._model("idempotent-model")
        self.assertEqual(first, self._model("idempotent-model"))
        with self.assertRaises(CallConflictError):
            self._model("idempotent-model", model_id="model://different/revision")

        def create(_: int) -> ModelCall:
            return self._model("concurrent-model")

        with ThreadPoolExecutor(max_workers=8) as executor:
            concurrent = tuple(executor.map(create, range(8)))
        self.assertEqual(len({item.call_ref for item in concurrent}), 1)
        restarted = CallLedgerService(self.database_path).get_model_call(
            self.alpha_access,
            concurrent[0].call_ref,
        )
        self.assertEqual(restarted, concurrent[0])

        anchored = self._model("start-event-anchor")
        forged_start = replace(
            anchored,
            provider_id="provider://attacker/rewritten",
        )
        terminal_source = self._model("terminal-event-anchor")
        terminal = self.ledger.finish_model_call(
            self.alpha_access,
            self.node_attempt,
            terminal_source.call_ref,
            idempotency_key="terminal-event-anchor-finish",
            status="FAILED",
            output_refs=(),
            usage=None,
            cost=None,
            failure_category="PROVIDER_FAILURE",
            failure_reason="anchored provider failure",
            failure_evidence_refs=(),
        )
        forged_state = replace(
            terminal.state,
            status="SUCCEEDED",
            failure_category=None,
            failure_reason=None,
        )
        linked_parent = self._model("linked-parent-integrity")
        linked_tool = self._tool(
            "linked-tool-integrity",
            parent=linked_parent.call_ref,
        )
        linked_predecessor_source = self._model("linked-retry-predecessor")
        linked_predecessor = self.ledger.finish_model_call(
            self.alpha_access,
            self.node_attempt,
            linked_predecessor_source.call_ref,
            idempotency_key="linked-retry-predecessor-finish",
            status="FAILED",
            output_refs=(),
            usage=None,
            cost=None,
            failure_category="TRANSPORT",
            failure_reason="linked retry transport failure",
            failure_evidence_refs=(),
        )
        linked_retry = self._model(
            "linked-retry-integrity",
            purpose="INFRASTRUCTURE_RETRY",
            retry_of=linked_predecessor.call_ref,
        )

        def durable_sha(value: object) -> str:
            return hashlib.sha256(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
            ).hexdigest()

        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER calls_no_update")
            connection.execute("DROP TRIGGER call_status_versions_no_update")
            connection.execute("DROP TRIGGER call_status_heads_monotonic")
            connection.execute("DROP TRIGGER call_status_heads_no_delete")
            connection.execute(
                """
                UPDATE calls SET provider_id = ?, identity_sha256 = ?, record_sha256 = ?
                WHERE project_id = ? AND call_id = ?
                """,
                (
                    forged_start.provider_id,
                    forged_start.identity_sha256,
                    forged_start.record_sha256,
                    anchored.project_ref.value,
                    anchored.call_ref.call_id,
                ),
            )
            connection.execute(
                """
                UPDATE call_status_versions SET
                    status = ?, failure_category = ?, failure_reason = ?,
                    semantic_digest = ?, record_sha256 = ?
                WHERE project_id = ? AND call_id = ? AND state_version = 2
                """,
                (
                    forged_state.status,
                    forged_state.failure_category,
                    forged_state.failure_reason,
                    forged_state.semantic_digest,
                    forged_state.record_sha256,
                    terminal.project_ref.value,
                    terminal.call_ref.call_id,
                ),
            )
            forged_head_sha = durable_sha(
                {
                    "call_ref": terminal.call_ref.value,
                    "current_record_sha256": forged_state.record_sha256,
                    "current_version": forged_state.version,
                    "updated_at": forged_state.recorded_at,
                }
            )
            connection.execute(
                """
                UPDATE call_status_heads SET
                    current_record_sha256 = ?, record_sha256 = ?
                WHERE project_id = ? AND call_id = ?
                """,
                (
                    forged_state.record_sha256,
                    forged_head_sha,
                    terminal.project_ref.value,
                    terminal.call_ref.call_id,
                ),
            )
            connection.execute(
                "UPDATE call_status_heads SET current_record_sha256 = ? WHERE call_id = ?",
                ("0" * 64, first.call_ref.call_id),
            )
            connection.execute(
                "DELETE FROM call_status_heads WHERE project_id = ? AND call_id = ?",
                (linked_parent.project_ref.value, linked_parent.call_ref.call_id),
            )
            connection.execute(
                """
                UPDATE call_status_versions SET status = 'SUCCEEDED'
                WHERE project_id = ? AND call_id = ? AND state_version = 2
                """,
                (
                    linked_predecessor.project_ref.value,
                    linked_predecessor.call_ref.call_id,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(CallIntegrityError):
            self.ledger.get_model_call(self.alpha_access, anchored.call_ref)
        with self.assertRaises(CallIntegrityError):
            self.ledger.get_model_call(self.alpha_access, terminal.call_ref)
        with self.assertRaises(CallIntegrityError):
            self.ledger.get_model_call(self.alpha_access, first.call_ref)
        with self.assertRaises(CallIntegrityError):
            self.ledger.get_tool_call(self.alpha_access, linked_tool.call_ref)
        with self.assertRaises(CallIntegrityError):
            self.ledger.get_model_call(self.alpha_access, linked_retry.call_ref)

        source = (ROOT / "tests/test_p1_05_call_ledger.py").read_text(encoding="utf-8")
        for marker in (
            "TO" "DO",
            "FIX" "ME",
            "place" "holder",
            "@unittest." "skip",
            "pytest.mark." "skip",
            "self." "skipTest",
            "Not" "Implemented",
        ):
            self.assertNotIn(marker, source)

        typecheck = subprocess.run(
            (sys.executable, "-m", "mypy", "--strict", "src", "tests"),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(typecheck.returncode, 0, f"{typecheck.stdout}\n{typecheck.stderr}")

        self.runs.renew_run_lease(
            self.alpha_access,
            self.run_attempt,
            lease_seconds=3600,
        )
        self.executions.heartbeat_node(
            self.alpha_access,
            self.node_attempt,
            lease_seconds=3600,
            idempotency_key="installed-wheel-qualification-heartbeat",
        )

        loader = unittest.TestLoader()
        predecessor = unittest.TestSuite(
            (
                loader.discover(str(ROOT / "tests"), pattern="test_p0_*.py"),
                loader.discover(str(ROOT / "tests"), pattern="test_p1_01*.py"),
                loader.discover(str(ROOT / "tests"), pattern="test_p1_02*.py"),
                loader.discover(str(ROOT / "tests"), pattern="test_p1_03*.py"),
                loader.discover(str(ROOT / "tests"), pattern="test_p1_04*.py"),
            )
        )
        self.assertEqual(predecessor.countTestCases(), 305)
        result = unittest.TestResult()
        predecessor.run(result)
        self.assertEqual(result.testsRun, 305)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.skipped, [])

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
            wheel_path = next(wheel_root.glob("biella_engine-*.whl"))
            source_paths = tuple(sorted((ROOT / "src/biella").glob("*.py")))
            with zipfile.ZipFile(wheel_path) as archive:
                self.assertEqual(
                    {
                        name
                        for name in archive.namelist()
                        if name.startswith("biella/") and name.endswith(".py")
                    },
                    {f"biella/{path.name}" for path in source_paths},
                )
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
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(installed),
                }
            )
            smoke = subprocess.run(
                (
                    sys.executable,
                    "-c",
                    "import biella; from biella import CallLedgerService, ModelCall, ToolCall; "
                    "assert set(('CallLedgerService','ModelCall','ToolCall')).issubset(biella.__all__)",
                ),
                cwd=qualification_root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(smoke.returncode, 0, f"{smoke.stdout}\n{smoke.stderr}")
            configuration_path = qualification_root / "call-config.json"
            evidence_path = qualification_root / "call-evidence.json"
            configuration_path.write_text(
                json.dumps(
                    {
                        "access_token": self.alpha_access.token,
                        "attempt": {
                            "attempt_id": self.node_attempt.attempt_id,
                            "attempt_number": self.node_attempt.attempt_number,
                            "fence": self.node_attempt.fence,
                            "graph_id": self.node_ref.graph_ref.graph_id,
                            "graph_revision": self.node_ref.graph_ref.revision,
                            "lease_acquired_at": self.node_attempt.lease_acquired_at,
                            "lease_expires_at": self.node_attempt.lease_expires_at,
                            "node_id": self.node_ref.node_id,
                            "owner_ref": self.node_attempt.owner_ref,
                            "run_attempt_id": self.node_attempt.run_attempt_id,
                            "run_fence": self.node_attempt.run_fence,
                            "run_id": self.node_attempt.run_ref.run_id,
                            "task_digest": self.node_attempt.task_digest,
                            "task_id": self.node_attempt.task_ref.task_id,
                            "task_revision": self.node_attempt.task_ref.revision,
                        },
                        "capability_id": self.capability_ref.capability_id,
                        "capability_version": self.capability_ref.version,
                        "database_path": str(self.database_path),
                        "project_id": self.alpha.value,
                        "request": {
                            "algorithm": self.request_ref.algorithm,
                            "digest": self.request_ref.digest,
                            "media_type": self.request_ref.media_type,
                            "size_bytes": self.request_ref.size_bytes,
                        },
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            writer = subprocess.run(
                (
                    sys.executable,
                    str(ROOT / "tests/fixtures/p1_05_installed_writer.py"),
                    str(configuration_path),
                    str(evidence_path),
                ),
                cwd=qualification_root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(writer.returncode, 0, f"{writer.stdout}\n{writer.stderr}")
            reader = subprocess.run(
                (
                    sys.executable,
                    str(ROOT / "tests/fixtures/p1_05_installed_reader.py"),
                    str(configuration_path),
                    str(evidence_path),
                ),
                cwd=qualification_root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(reader.returncode, 0, f"{reader.stdout}\n{reader.stderr}")
