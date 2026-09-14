"""P2-06 provider-neutral model execution adapter acceptance tests."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ast
import minitz_os.engine as minitz_engine
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from typing import cast
import zipfile

import pytest
from minitz_os.engine import (
    ArtifactRef,
    Capability,
    CapabilityRef,
    CapabilityRegistry,
    ContentRef,
    EmbedRequest,
    FilesystemObjectStorageBackend,
    GraphRef,
    GraphService,
    HostedHttpModelAdapter,
    HostedModelRoute,
    HttpDestination,
    HttpTlsPolicy,
    InferRequest,
    ModelAdapter,
    ModelConflictError,
    ModelDeployment,
    ModelDeploymentHealth,
    ModelDeploymentRef,
    ModelExecutionBinding,
    ModelExecutionFailure,
    ModelExecutionRef,
    ModelHealthStatus,
    ModelOperation,
    ModelRuntimeIdentity,
    ModelScopeError,
    ModelToolDefinition,
    Node,
    NodeExecutionAttempt,
    NodeExecutionService,
    NodeRef,
    ProjectAccess,
    ProjectRef,
    ProjectStore,
    ReferenceModelAdapter,
    RerankRequest,
    RunService,
    StdlibHttpAdapter,
    Task,
    TaskRevisionService,
)


def test_t01_public_model_execution_contracts_are_active_exports() -> None:
    expected = {
        "EmbedRequest",
        "EmbedResult",
        "HostedHttpModelAdapter",
        "InferRequest",
        "InferResult",
        "ModelAdapter",
        "ModelCancellationReceipt",
        "ModelDeployment",
        "ModelDeploymentHealth",
        "ModelDeploymentRef",
        "ModelExecutionFailure",
        "ModelExecutionRef",
        "ModelHealthStatus",
        "ModelOperation",
        "ModelRuntimeIdentity",
        "ModelToolDefinition",
        "ModelToolProposal",
        "ReferenceModelAdapter",
        "RerankCandidate",
        "RerankEntry",
        "RerankRequest",
        "RerankResult",
    }
    assert expected.issubset(set(minitz_engine.__all__))


@dataclass
class _ProviderState:
    hits: int = 0
    authorization: list[str | None] = field(default_factory=list)
    slow_started: threading.Event = field(default_factory=threading.Event)


class _ProviderServer(ThreadingHTTPServer):
    state: _ProviderState


class _ProviderHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, payload: object) -> None:
        body = json.dumps(payload, allow_nan=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self) -> None:
        state = cast(_ProviderServer, self.server).state
        state.hits += 1
        state.authorization.append(self.headers.get("Authorization"))
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        assert isinstance(payload, dict) and isinstance(payload.get("input"), dict)
        provider_input = cast(dict[str, object], payload["input"])
        if "messages" in provider_input:
            messages = cast(list[dict[str, object]], provider_input["messages"])
            content = cast(str, messages[-1]["content"])
            if content == "UNAVAILABLE":
                self._send(503, {"success": False, "errors": [{"code": 7505}]})
                return
            if content == "SLOW":
                state.slow_started.set()
                time.sleep(0.25)
            if content == "NULL_OUTPUT":
                result_content: str | None = None
                finish = "length"
            elif content == "STRUCT_BAD":
                result_content = '{"count":"bad"}'
                finish = "stop"
            else:
                result_content = content
                finish = "stop"
            tool_calls: list[dict[str, object]] = []
            try:
                possible = json.loads(content)
                tool = possible.get("provider_tool") if isinstance(possible, dict) else None
                if isinstance(tool, dict):
                    tool_calls = [
                        {
                            "id": "provider-tool-1",
                            "type": "function",
                            "function": {
                                "name": tool["name"],
                                "arguments": json.dumps(tool["arguments"], separators=(",", ":")),
                            },
                        }
                    ]
            except json.JSONDecodeError:
                pass
            self._send(
                200,
                {
                    "success": True,
                    "result": {
                        "id": "provider-call-real-1",
                        "choices": [
                            {
                                "finish_reason": finish,
                                "message": {"content": result_content, "tool_calls": tool_calls},
                            }
                        ],
                        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "cached_tokens": 0},
                    },
                },
            )
            return
        if "text" in provider_input:
            values = cast(list[str], provider_input["text"])
            if values[0] == "BAD_NAN":
                vectors = [[math.nan, 0.0, 1.0] for _ in values]
            elif values[0] == "BAD_DIM":
                vectors = [[0.0, 1.0] for _ in values]
            elif values[0] == "BAD_COUNT":
                vectors = [[0.0, 1.0, 2.0]]
            else:
                vectors = [[float(index), float(index + 1), float(index + 2)] for index, _ in enumerate(values)]
            self._send(200, {"success": True, "result": {"id": "provider-embed-1", "data": vectors}})
            return
        query = cast(str, provider_input["query"])
        contexts = cast(list[dict[str, object]], provider_input["contexts"])
        if query == "BAD_RERANK":
            entries = [
                {"candidate_id": contexts[0]["candidate_id"], "score": 1.0, "rank": 1},
                {"candidate_id": contexts[0]["candidate_id"], "score": 0.5, "rank": 2},
            ]
        else:
            entries = [
                {"candidate_id": item["candidate_id"], "score": float(len(contexts) - index), "rank": index + 1}
                for index, item in enumerate(contexts)
            ]
        self._send(200, {"success": True, "result": {"id": "provider-rerank-1", "data": entries}})


@contextmanager
def _provider_server() -> Iterator[tuple[str, _ProviderState]]:
    state = _ProviderState()
    server = _ProviderServer(("127.0.0.1", 0), _ProviderHandler)
    server.state = state
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = cast(tuple[str, int], server.server_address)
        yield f"http://{host}:{port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@dataclass
class _SafeToolExecutor:
    objects: FilesystemObjectStorageBackend
    calls: list[tuple[str, ContentRef]] = field(default_factory=list)

    def execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        definition: ModelToolDefinition,
        arguments_ref: ContentRef,
    ) -> Sequence[ContentRef | ArtifactRef]:
        self.calls.append((definition.name, arguments_ref))
        return (self.objects.put(b'{"safe":true}', media_type="application/json"),)


@dataclass(frozen=True)
class _Environment:
    database: Path
    objects: FilesystemObjectStorageBackend
    access: ProjectAccess
    project_ref: ProjectRef
    task: Task
    attempt: NodeExecutionAttempt
    reference: ReferenceModelAdapter
    hosted: HostedHttpModelAdapter
    http: StdlibHttpAdapter
    reference_deployment: ModelDeployment
    hosted_deployment: ModelDeployment
    tool_definition: ModelToolDefinition
    tool_executor: _SafeToolExecutor


def _runtime(
    *,
    adapter_ref: str,
    provider_ref: str,
    model_ref: str,
    revision: str | None,
    reality: str,
) -> ModelRuntimeIdentity:
    return ModelRuntimeIdentity(
        adapter_ref,
        "runtime://python/model-adapter-v1",
        "generation-1",
        provider_ref,
        model_ref,
        revision,
        None,
        (),
        reality,
    )


def _environment(tmp_path: Path, origin: str, *, namespace: str = "model-adapter") -> _Environment:
    database = tmp_path / f"{namespace}.sqlite3"
    registration = ProjectStore(database).create_project(namespace=namespace, display_name=namespace.title())
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    data_policy = f"policy://{namespace}/data"
    egress_policy = f"policy://{namespace}/egress"
    http = StdlibHttpAdapter(
        database,
        objects,
        supported_data_policy_refs=(data_policy,),
        supported_egress_policy_refs=(egress_policy,),
    )
    http_implementations = http.register_capabilities(registration.access)
    destination = http.register_destination(
        registration.access,
        HttpDestination.create(
            registration.project.project_ref,
            origin=origin,
            allowed_path_prefixes=("/client/v4/accounts/test/ai",),
            auth_profile_ref="secret://cloudflare/api-token",
            auth_header_name="authorization",
            data_policy_ref=data_policy,
            egress_policy_ref=egress_policy,
            tls_policy=HttpTlsPolicy.ALLOW_PLAINTEXT,
        ),
        idempotency_key="model-http-destination",
    )
    tool_executor = _SafeToolExecutor(objects)
    reference = ReferenceModelAdapter(database, objects, tool_executor=tool_executor)
    reference_ref = ModelDeploymentRef.new(registration.project.project_ref)
    reference_deployment = reference.register_deployment(
        registration.access,
        ModelDeployment(
            reference_ref,
            reference.adapter_ref,
            "provider://minitz/reference",
            "model://minitz/deterministic-reference-v1",
            "reference-v1",
            None,
            None,
            (ModelOperation.INFER, ModelOperation.EMBED, ModelOperation.RERANK),
            ("text",),
            256,
            True,
            True,
            4,
            (),
            (data_policy,),
            (),
            False,
            _runtime(
                adapter_ref=reference.adapter_ref,
                provider_ref="provider://minitz/reference",
                model_ref="model://minitz/deterministic-reference-v1",
                revision="reference-v1",
                reality="REFERENCE",
            ),
        ),
        idempotency_key="reference-deployment",
    )
    hosted_ref = ModelDeploymentRef.new(registration.project.project_ref)
    route = HostedModelRoute(hosted_ref, destination.destination_ref, "/client/v4/accounts/test/ai/run")
    hosted = HostedHttpModelAdapter(database, objects, http, {hosted_ref: route}, tool_executor=tool_executor)
    hosted_deployment = hosted.register_deployment(
        registration.access,
        ModelDeployment(
            hosted_ref,
            hosted.adapter_ref,
            "provider://cloudflare/workers-ai",
            "model://cloudflare/mutable-test-alias",
            None,
            None,
            destination.destination_ref.value,
            (ModelOperation.INFER, ModelOperation.EMBED, ModelOperation.RERANK),
            ("text",),
            256,
            True,
            True,
            3,
            (),
            (data_policy,),
            (egress_policy,),
            True,
            _runtime(
                adapter_ref=hosted.adapter_ref,
                provider_ref="provider://cloudflare/workers-ai",
                model_ref="model://cloudflare/mutable-test-alias",
                revision=None,
                reality="REAL",
            ),
            {"provider_model_name": "@cf/test/model"},
        ),
        idempotency_key="hosted-deployment",
    )
    model_capabilities = set(reference.register_capabilities(registration.access, reference_deployment))
    model_capabilities.update(hosted.register_capabilities(registration.access, hosted_deployment))
    tool_capability = CapabilityRegistry(database).register(
        Capability(CapabilityRef("tool.safe-echo", "1.0.0"), "Execute one bounded safe test tool")
    ).capability_ref
    required_capabilities = tuple(sorted((*model_capabilities, *http_implementations, tool_capability)))
    task = TaskRevisionService(database).create_task(
        registration.access,
        project_ref=registration.project.project_ref,
        idempotency_key="model-task",
        task_type="model.execute",
        objective="Execute one provider-neutral model Task",
        required_capabilities=required_capabilities,
        input_refs=(),
        output_contract={"result": "schema://minitz/model-result/1"},
        constraints={},
        side_effect_authority="EXTERNAL_SIDE_EFFECT",
        data_policy_ref=data_policy,
        egress_policy_ref=egress_policy,
        evidence_requirements=("model-call", "artifact", "content-ref"),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(registration.access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(registration.access, run.run_ref, owner_ref="controller://model-tests", lease_seconds=1800)
    graph_ref = GraphRef.new(registration.project.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "MODEL",
        required_capabilities,
        (),
        (),
        {"result": "schema://minitz/model-result/1"},
        None,
        "EXTERNAL_SIDE_EFFECT",
        {},
        ("model-call", "artifact", "content-ref"),
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
        owner_ref="executor://model-tests",
        lease_seconds=1800,
        idempotency_key="model-node-lease",
    )
    executions.start_node(registration.access, attempt, idempotency_key="model-node-start")
    return _Environment(
        database,
        objects,
        registration.access,
        registration.project.project_ref,
        task,
        attempt,
        reference,
        hosted,
        http,
        reference_deployment,
        hosted_deployment,
        ModelToolDefinition("safe.echo", tool_capability, "tool://minitz/safe-echo", "implementation://minitz/safe-echo-v1"),
        tool_executor,
    )


def _put_json(env: _Environment, value: object) -> ContentRef:
    return env.objects.put(json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode(), media_type="application/json")


def _binding(
    env: _Environment,
    deployment: ModelDeployment,
    operation: ModelOperation,
    input_refs: tuple[ContentRef | ArtifactRef, ...],
    *,
    context_tokens: int = 8,
    timeout_seconds: float = 5.0,
) -> ModelExecutionBinding:
    return ModelExecutionBinding(
        env.project_ref,
        ModelExecutionRef.new(env.project_ref),
        deployment.deployment_ref,
        env.reference.capability_ref(operation),
        env.task.task_ref,
        env.task.canonical_digest,
        env.attempt.run_ref,
        env.attempt.node_ref,
        env.attempt.attempt_id,
        env.attempt.fence,
        input_refs,
        None,
        cast(str, env.task.data_policy_ref),
        cast(str, env.task.egress_policy_ref),
        context_tokens,
        timeout_seconds,
    )


def _infer(
    env: _Environment,
    deployment: ModelDeployment,
    content: str,
    *,
    schema_ref: ContentRef | None = None,
    tools: tuple[ModelToolDefinition, ...] = (),
    context_tokens: int = 8,
    timeout_seconds: float = 5.0,
) -> InferRequest:
    messages_ref = _put_json(env, {"messages": [{"role": "user", "content": content}]})
    refs: tuple[ContentRef | ArtifactRef, ...] = (messages_ref,) if schema_ref is None else (messages_ref, schema_ref)
    return InferRequest(
        _binding(env, deployment, ModelOperation.INFER, refs, context_tokens=context_tokens, timeout_seconds=timeout_seconds),
        messages_ref,
        {"max_tokens": 128, "temperature": 0},
        schema_ref,
        tools,
    )


def _credentials(adapter: ReferenceModelAdapter | HostedHttpModelAdapter) -> dict[str, str]:
    return {} if isinstance(adapter, ReferenceModelAdapter) else {"secret://cloudflare/api-token": "Bearer exact-provider-token"}


def test_t02_deployment_registry_health_capabilities_scope_and_immutable_identity(tmp_path: Path) -> None:
    with _provider_server() as (origin, _):
        env = _environment(tmp_path, origin)
        assert isinstance(env.reference, ModelAdapter)
        assert isinstance(env.hosted, ModelAdapter)
        assert env.reference.get_deployment(env.access, env.reference_deployment.deployment_ref) == env.reference_deployment
        assert env.hosted.get_deployment(env.access, env.hosted_deployment.deployment_ref) == env.hosted_deployment
        assert env.reference.health(env.access, env.reference_deployment.deployment_ref).status is ModelHealthStatus.HEALTHY
        assert env.hosted.health(env.access, env.hosted_deployment.deployment_ref).status is ModelHealthStatus.UNKNOWN
        assert env.hosted_deployment.model_revision is None
        reference_caps = env.reference.register_capabilities(env.access, env.reference_deployment)
        hosted_caps = env.hosted.register_capabilities(env.access, env.hosted_deployment)
        assert set(reference_caps) == set(hosted_caps)
        assert all(reference_caps[item].implementation_ref != hosted_caps[item].implementation_ref for item in reference_caps)
        assert all(hosted_caps[item].remote_egress for item in hosted_caps)
        assert all(not reference_caps[item].remote_egress for item in reference_caps)
        restarted = ReferenceModelAdapter(env.database, env.objects, tool_executor=env.tool_executor)
        assert restarted.get_deployment(env.access, env.reference_deployment.deployment_ref) == env.reference_deployment
        beta = ProjectStore(env.database).create_project(namespace="model-beta", display_name="Model Beta")
        with pytest.raises(ModelScopeError):
            restarted.get_deployment(beta.access, env.reference_deployment.deployment_ref)
        with sqlite3.connect(env.database) as connection, pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE model_deployments SET deployment_json='{}' WHERE deployment_id=?",
                (env.reference_deployment.deployment_ref.deployment_id,),
            )


def test_t03_same_task_infers_across_reference_and_real_hosted_adapters_with_modelcall_evidence(tmp_path: Path) -> None:
    with _provider_server() as (origin, state):
        env = _environment(tmp_path, origin)
        reference_request = _infer(env, env.reference_deployment, "provider-neutral hello")
        hosted_request = _infer(env, env.hosted_deployment, "provider-neutral hello")
        reference = env.reference.infer(env.access, env.attempt, reference_request, credentials={}, idempotency_key="reference-infer")
        hosted = env.hosted.infer(
            env.access,
            env.attempt,
            hosted_request,
            credentials=_credentials(env.hosted),
            idempotency_key="hosted-infer",
        )
        assert reference.evidence.succeeded and hosted.evidence.succeeded
        assert reference.text == hosted.text == "provider-neutral hello"
        assert reference_request.binding.task_ref == hosted_request.binding.task_ref == env.task.task_ref
        assert reference_request.binding.capability_ref == hosted_request.binding.capability_ref
        assert reference.evidence.runtime_identity.reality == "REFERENCE"
        assert hosted.evidence.runtime_identity.reality == "REAL"
        assert hosted.evidence.provider_trace_id == "provider-call-real-1"
        assert hosted.evidence.usage is not None
        assert hosted.evidence.usage.input_tokens.value == 7
        assert state.authorization == ["Bearer exact-provider-token"]
        assert env.hosted.health(env.access, env.hosted_deployment.deployment_ref).status is ModelHealthStatus.HEALTHY
        assert env.reference.get_result(env.access, reference_request.binding.execution_ref) == reference
        restarted = HostedHttpModelAdapter(
            env.database,
            env.objects,
            env.http,
            {
                env.hosted_deployment.deployment_ref: HostedModelRoute(
                    env.hosted_deployment.deployment_ref,
                    env.hosted.routes[env.hosted_deployment.deployment_ref].destination_ref,
                    "/client/v4/accounts/test/ai/run",
                )
            },
            tool_executor=env.tool_executor,
        )
        assert restarted.get_result(env.access, hosted_request.binding.execution_ref) == hosted
        replay = env.hosted.infer(
            env.access,
            env.attempt,
            hosted_request,
            credentials=_credentials(env.hosted),
            idempotency_key="hosted-infer",
        )
        assert replay == hosted
        assert state.hits == 1


def test_t04_structured_output_valid_invalid_and_null_provider_output_fail_closed(tmp_path: Path) -> None:
    with _provider_server() as (origin, _):
        env = _environment(tmp_path, origin)
        schema = _put_json(
            env,
            {
                "type": "object",
                "properties": {"count": {"type": "integer", "minimum": 0}},
                "required": ["count"],
                "additionalProperties": False,
            },
        )
        valid_request = _infer(env, env.reference_deployment, '{"count":2}', schema_ref=schema)
        valid = env.reference.infer(env.access, env.attempt, valid_request, credentials={}, idempotency_key="structured-valid")
        assert valid.evidence.succeeded and valid.structured_value == {"count": 2}
        invalid_request = _infer(env, env.reference_deployment, '{"count":"bad"}', schema_ref=schema)
        invalid = env.reference.infer(env.access, env.attempt, invalid_request, credentials={}, idempotency_key="structured-invalid")
        assert invalid.evidence.failure is ModelExecutionFailure.STRUCTURED_OUTPUT_INVALID
        assert invalid.evidence.output_ref is None
        null_request = _infer(env, env.hosted_deployment, "NULL_OUTPUT")
        null_result = env.hosted.infer(
            env.access,
            env.attempt,
            null_request,
            credentials=_credentials(env.hosted),
            idempotency_key="null-provider-output",
        )
        assert null_result.evidence.failure is ModelExecutionFailure.MALFORMED_OUTPUT
        assert null_result.text is None


def test_t05_embedding_cardinality_dimension_finiteness_and_source_digest(tmp_path: Path) -> None:
    with _provider_server() as (origin, _):
        env = _environment(tmp_path, origin)
        inputs_ref = _put_json(env, ["alpha", "beta"])
        request = EmbedRequest(_binding(env, env.reference_deployment, ModelOperation.EMBED, (inputs_ref,)), inputs_ref)
        result = env.reference.embed(env.access, env.attempt, request, credentials={}, idempotency_key="reference-embed")
        assert result.evidence.succeeded
        assert len(result.vectors) == 2 and all(len(vector) == 4 for vector in result.vectors)
        assert all(math.isfinite(value) for vector in result.vectors for value in vector)
        assert result.source_digest == inputs_ref.digest
        for marker, expected in (
            ("BAD_NAN", ModelExecutionFailure.EMBEDDING_INVALID),
            ("BAD_DIM", ModelExecutionFailure.EMBEDDING_INVALID),
            ("BAD_COUNT", ModelExecutionFailure.EMBEDDING_INVALID),
        ):
            bad_ref = _put_json(env, [marker, "second"])
            bad_request = EmbedRequest(_binding(env, env.hosted_deployment, ModelOperation.EMBED, (bad_ref,)), bad_ref)
            bad = env.hosted.embed(
                env.access,
                env.attempt,
                bad_request,
                credentials=_credentials(env.hosted),
                idempotency_key=f"embed-{marker.lower().replace('_', '-')}",
            )
            assert bad.evidence.failure is expected
            assert bad.vectors == ()


def test_t06_rerank_complete_ordered_finite_and_invalid_candidate_coverage_rejected(tmp_path: Path) -> None:
    with _provider_server() as (origin, _):
        env = _environment(tmp_path, origin)
        query_ref = _put_json(env, "alpha beta")
        candidates_ref = _put_json(
            env,
            [
                {"candidate_id": "one", "text": "alpha beta gamma"},
                {"candidate_id": "two", "text": "alpha"},
            ],
        )
        request = RerankRequest(
            _binding(env, env.reference_deployment, ModelOperation.RERANK, (query_ref, candidates_ref)),
            query_ref,
            candidates_ref,
        )
        result = env.reference.rerank(env.access, env.attempt, request, credentials={}, idempotency_key="reference-rerank")
        assert [entry.candidate_id for entry in result.entries] == ["one", "two"]
        assert [entry.rank for entry in result.entries] == [1, 2]
        assert all(math.isfinite(entry.score) for entry in result.entries)
        bad_query_ref = _put_json(env, "BAD_RERANK")
        bad_request = RerankRequest(
            _binding(env, env.hosted_deployment, ModelOperation.RERANK, (bad_query_ref, candidates_ref)),
            bad_query_ref,
            candidates_ref,
        )
        bad = env.hosted.rerank(
            env.access,
            env.attempt,
            bad_request,
            credentials=_credentials(env.hosted),
            idempotency_key="hosted-bad-rerank",
        )
        assert bad.evidence.failure is ModelExecutionFailure.RERANK_INVALID
        assert bad.entries == ()


def test_t07_provider_tool_proposals_become_authorized_child_toolcalls_and_unauthorized_are_inert(tmp_path: Path) -> None:
    with _provider_server() as (origin, _):
        env = _environment(tmp_path, origin)
        content = json.dumps({"tool_call": {"name": "safe.echo", "arguments": {"value": "hello"}}}, separators=(",", ":"))
        request = _infer(env, env.reference_deployment, content, tools=(env.tool_definition,))
        result = env.reference.infer(env.access, env.attempt, request, credentials={}, idempotency_key="authorized-tool")
        assert result.evidence.succeeded and len(result.evidence.tool_call_refs) == 1
        tool = minitz_engine.CallLedgerService(env.database).get_tool_call(env.access, result.evidence.tool_call_refs[0])
        assert tool.parent_model_call_ref == result.evidence.model_call_ref
        assert tool.status == "SUCCEEDED"
        assert env.tool_executor.calls[0][0] == "safe.echo"
        hosted_content = json.dumps({"provider_tool": {"name": "safe.echo", "arguments": {"value": "hosted"}}}, separators=(",", ":"))
        hosted_request = _infer(env, env.hosted_deployment, hosted_content, tools=(env.tool_definition,))
        hosted = env.hosted.infer(
            env.access,
            env.attempt,
            hosted_request,
            credentials=_credentials(env.hosted),
            idempotency_key="hosted-authorized-tool",
        )
        assert hosted.evidence.succeeded and len(hosted.evidence.tool_call_refs) == 1
        hosted_tool = minitz_engine.CallLedgerService(env.database).get_tool_call(env.access, hosted.evidence.tool_call_refs[0])
        assert hosted_tool.parent_model_call_ref == hosted.evidence.model_call_ref
        assert hosted_tool.status == "SUCCEEDED"
        before = len(env.tool_executor.calls)
        denied_content = json.dumps({"tool_call": {"name": "host.shell", "arguments": {"argv": ["rm", "-rf", "/"]}}}, separators=(",", ":"))
        denied_request = _infer(env, env.reference_deployment, denied_content)
        denied = env.reference.infer(env.access, env.attempt, denied_request, credentials={}, idempotency_key="unauthorized-tool")
        assert denied.evidence.failure is ModelExecutionFailure.UNAUTHORIZED_TOOL
        assert denied.evidence.tool_call_refs == ()
        assert len(env.tool_executor.calls) == before


def test_t08_context_egress_provider_unavailable_timeout_and_cancel_are_explicit(tmp_path: Path) -> None:
    with _provider_server() as (origin, state):
        env = _environment(tmp_path, origin)
        context_request = _infer(env, env.reference_deployment, "context", context_tokens=257)
        context_result = env.reference.infer(env.access, env.attempt, context_request, credentials={}, idempotency_key="context-limit")
        assert context_result.evidence.failure is ModelExecutionFailure.CONTEXT_LIMIT
        hits_before = state.hits
        denied_ref = ModelDeploymentRef.new(env.project_ref)
        route = HostedModelRoute(
            denied_ref,
            env.hosted.routes[env.hosted_deployment.deployment_ref].destination_ref,
            "/client/v4/accounts/test/ai/run",
        )
        denied_adapter = HostedHttpModelAdapter(env.database, env.objects, env.http, {denied_ref: route})
        denied_deployment = denied_adapter.register_deployment(
            env.access,
            ModelDeployment(
                denied_ref,
                denied_adapter.adapter_ref,
                "provider://cloudflare/workers-ai",
                "model://cloudflare/egress-denied",
                None,
                None,
                route.destination_ref.value,
                (ModelOperation.INFER,),
                ("text",),
                256,
                False,
                False,
                None,
                (),
                (cast(str, env.task.data_policy_ref),),
                ("policy://different/egress",),
                True,
                _runtime(
                    adapter_ref=denied_adapter.adapter_ref,
                    provider_ref="provider://cloudflare/workers-ai",
                    model_ref="model://cloudflare/egress-denied",
                    revision=None,
                    reality="REAL",
                ),
                {"provider_model_name": "@cf/test/model"},
            ),
            idempotency_key="denied-deployment",
        )
        denied_request = _infer(env, denied_deployment, "must-not-egress")
        denied_result = denied_adapter.infer(
            env.access,
            env.attempt,
            denied_request,
            credentials=_credentials(denied_adapter),
            idempotency_key="egress-denied",
        )
        assert denied_result.evidence.failure is ModelExecutionFailure.EGRESS_DENIED
        assert state.hits == hits_before
        unavailable_request = _infer(env, env.hosted_deployment, "UNAVAILABLE")
        unavailable = env.hosted.infer(
            env.access,
            env.attempt,
            unavailable_request,
            credentials=_credentials(env.hosted),
            idempotency_key="provider-unavailable",
        )
        assert unavailable.evidence.failure is ModelExecutionFailure.PROVIDER_UNAVAILABLE
        assert env.hosted.health(env.access, env.hosted_deployment.deployment_ref).status is ModelHealthStatus.UNAVAILABLE
        timeout_request = _infer(env, env.hosted_deployment, "SLOW", timeout_seconds=0.05)
        timeout = env.hosted.infer(
            env.access,
            env.attempt,
            timeout_request,
            credentials=_credentials(env.hosted),
            idempotency_key="provider-timeout",
        )
        assert timeout.evidence.failure is ModelExecutionFailure.TIMEOUT
        slow_reference = ReferenceModelAdapter(env.database, env.objects, latency_seconds=0.25, tool_executor=env.tool_executor)
        cancel_request = _infer(env, env.reference_deployment, "cancel me", timeout_seconds=1.0)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                slow_reference.infer,
                env.access,
                env.attempt,
                cancel_request,
                credentials={},
                idempotency_key="cancel-model",
            )
            deadline = time.monotonic() + 2
            while cancel_request.binding.execution_ref.value not in slow_reference._active and time.monotonic() < deadline:
                time.sleep(0.005)
            receipt = slow_reference.cancel(
                env.access,
                env.attempt,
                cancel_request.binding.execution_ref,
                idempotency_key="cancel-model-request",
            )
            cancelled = future.result(timeout=5)
        assert receipt.accepted
        assert cancelled.evidence.failure is ModelExecutionFailure.CANCELLED


def test_t09_idempotency_restart_scope_row_tamper_and_content_erasure_fail_closed(tmp_path: Path) -> None:
    with _provider_server() as (origin, _):
        env = _environment(tmp_path, origin)
        request = _infer(env, env.reference_deployment, "durable result")
        first = env.reference.infer(env.access, env.attempt, request, credentials={}, idempotency_key="durable-result")
        assert env.reference.infer(env.access, env.attempt, request, credentials={}, idempotency_key="durable-result") == first
        restarted = ReferenceModelAdapter(env.database, env.objects, tool_executor=env.tool_executor)
        assert restarted.get_result(env.access, request.binding.execution_ref) == first
        changed_messages = _put_json(env, {"messages": [{"role": "user", "content": "changed"}]})
        changed = InferRequest(
            ModelExecutionBinding(
                env.project_ref,
                request.binding.execution_ref,
                request.binding.deployment_ref,
                request.binding.capability_ref,
                request.binding.task_ref,
                request.binding.task_digest,
                request.binding.run_ref,
                request.binding.node_ref,
                request.binding.node_attempt_id,
                request.binding.node_fence,
                (changed_messages,),
                None,
                request.binding.data_policy_ref,
                request.binding.egress_policy_ref,
                request.binding.context_tokens,
                request.binding.timeout_seconds,
            ),
            changed_messages,
        )
        with pytest.raises(ModelConflictError):
            restarted.infer(env.access, env.attempt, changed, credentials={}, idempotency_key="durable-result")
        beta = ProjectStore(env.database).create_project(namespace="result-beta", display_name="Result Beta")
        with pytest.raises(ModelScopeError):
            restarted.get_result(beta.access, request.binding.execution_ref)
        assert first.evidence.output_ref is not None
        locator = env.objects.location(first.evidence.output_ref).locator
        assert locator.startswith("file://")
        Path(locator.removeprefix("file://")).unlink()
        with pytest.raises(minitz_engine.ModelIntegrityError):
            restarted.get_result(env.access, request.binding.execution_ref)


def test_t10_late_result_is_rejected_after_node_attempt_loses_its_fence(tmp_path: Path) -> None:
    with _provider_server() as (origin, _):
        env = _environment(tmp_path, origin)
        slow = ReferenceModelAdapter(env.database, env.objects, latency_seconds=0.15, tool_executor=env.tool_executor)
        request = _infer(env, env.reference_deployment, "late result", timeout_seconds=1.0)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                slow.infer,
                env.access,
                env.attempt,
                request,
                credentials={},
                idempotency_key="late-stale-result",
            )
            deadline = time.monotonic() + 2
            while request.binding.execution_ref.value not in slow._active and time.monotonic() < deadline:
                time.sleep(0.005)
            NodeExecutionService(env.database).fail_node(
                env.access,
                env.attempt,
                category="STALE_EXECUTION",
                reason="replace model owner before late provider response",
                evidence_refs=(),
                retry_possible=True,
                idempotency_key="fail-for-stale-model",
            )
            with pytest.raises(minitz_engine.ModelAuthorityError):
                future.result(timeout=5)
        with sqlite3.connect(env.database) as connection:
            result_count = connection.execute(
                "SELECT COUNT(*) FROM model_execution_results WHERE execution_id=?",
                (request.binding.execution_ref.execution_id,),
            ).fetchone()
        assert result_count == (0,)


def test_t11_kernel_contracts_have_no_provider_sdk_types_or_quarantine_dependency() -> None:
    root = Path(__file__).parents[1]
    for path in (root / "src/minitz_os/engine/task.py", root / "src/minitz_os/engine/run.py", root / "src/minitz_os/engine/graph.py"):
        source = path.read_text(encoding="utf-8")
        for provider_type in ("cloudflare", "Workers AI", "OpenAI", "Anthropic", "HTTPConnection", "requests.Session"):
            assert provider_type not in source
    active_runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "src/minitz").glob("*.py"))
        if path.name != "migration.py"
    )
    assert "QuarantineRef" not in active_runtime


def test_t15_type_build_exact_wheel_and_separate_installed_restart() -> None:
    root = Path(__file__).resolve().parents[1]
    source_paths = (
        root / "src/minitz_os/engine/__init__.py",
        root / "src/minitz_os/engine/model_adapter.py",
        root / "tests/test_p2_06_model_adapter.py",
        root / "tests/fixtures/p2_06_installed_writer.py",
        root / "tests/fixtures/p2_06_installed_reader.py",
    )
    prohibited = (
        "TO" "DO",
        "FIX" "ME",
        "place" "holder",
        "pytest.mark." "skip",
        "@unittest." "skip",
        "Not" "Implemented",
    )
    for path in source_paths:
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        assert all(marker not in source for marker in prohibited)
    active_runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "src/minitz").glob("*.py"))
        if path.name != "migration.py"
    )
    assert "QuarantineRef" not in active_runtime
    typecheck = subprocess.run(
        (sys.executable, "-m", "mypy", "--strict", "src"),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert typecheck.returncode == 0, f"{typecheck.stdout}\n{typecheck.stderr}"
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary = Path(temporary_directory)
        wheel_root = temporary / "wheel"
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
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert build.returncode == 0, f"{build.stdout}\n{build.stderr}"
        wheels = tuple(wheel_root.glob("minitz_engine-*.whl"))
        assert len(wheels) == 1
        wheel = wheels[0]
        package_paths = tuple(sorted((root / "src/minitz").glob("*.py")))
        with zipfile.ZipFile(wheel) as archive:
            wheel_names = {
                name
                for name in archive.namelist()
                if name.startswith("minitz/") and name.endswith(".py")
            }
            assert wheel_names == {f"minitz/{path.name}" for path in package_paths}
            for path in package_paths:
                assert hashlib.sha256(archive.read(f"minitz/{path.name}")).hexdigest() == hashlib.sha256(path.read_bytes()).hexdigest()
        installed = temporary / "installed"
        install = subprocess.run(
            (sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(installed), str(wheel)),
            cwd=temporary,
            check=False,
            capture_output=True,
            text=True,
        )
        assert install.returncode == 0, f"{install.stdout}\n{install.stderr}"
        environment = os.environ.copy()
        environment.update(
            {
                "MINITZ_DATABASE": str(temporary / "restart.sqlite3"),
                "MINITZ_EVIDENCE": str(temporary / "evidence.json"),
                "MINITZ_OBJECT_ROOT": str(temporary / "objects"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(installed),
            }
        )
        writer = subprocess.run(
            (sys.executable, str(root / "tests/fixtures/p2_06_installed_writer.py")),
            cwd=temporary,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert writer.returncode == 0, f"{writer.stdout}\n{writer.stderr}"
        environment["MINITZ_TOKEN"] = writer.stdout.strip()
        reader = subprocess.run(
            (sys.executable, str(root / "tests/fixtures/p2_06_installed_reader.py")),
            cwd=temporary,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert reader.returncode == 0, f"{reader.stdout}\n{reader.stderr}"
        assert json.loads(reader.stdout) == {"restart": "verified", "text": "installed restart exact"}
