"""P2-05 universal HTTP/API execution adapter acceptance tests."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
import ast
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import biella
import json
import os
from pathlib import Path
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from types import MappingProxyType
from typing import cast
from urllib.parse import parse_qs, urlsplit
import zipfile

import pytest
from biella import (
    ArtifactService,
    CapabilityRef,
    FilesystemObjectStorageBackend,
    GraphRef,
    GraphService,
    HttpAdapter,
    HttpConflictError,
    HttpContractError,
    HttpDestination,
    HttpExecutionFailure,
    HttpExecutionRef,
    HttpExecutionRequest,
    HttpRedirectPolicy,
    HttpScopeError,
    HttpTlsPolicy,
    Node,
    NodeExecutionAttempt,
    NodeExecutionService,
    NodeRef,
    ProjectAccess,
    ProjectRef,
    ProjectStore,
    RunService,
    StdlibHttpAdapter,
    Task,
    TaskRevisionService,
)


def test_t01_public_http_contracts_are_active_exports() -> None:
    expected = {
        "HttpAdapter",
        "HttpCancellationReceipt",
        "HttpDestination",
        "HttpDestinationRef",
        "HttpExecutionFailure",
        "HttpExecutionRef",
        "HttpExecutionRequest",
        "HttpExecutionResult",
        "HttpRedirectPolicy",
        "HttpTlsPolicy",
        "StdlibHttpAdapter",
    }
    assert expected.issubset(set(biella.__all__))


_LARGE_BINARY = bytes(range(256)) * 8192


@dataclass
class _ServerState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    hits: dict[str, int] = field(default_factory=dict)
    observed_authorization: list[str | None] = field(default_factory=list)
    upload_sha256: str | None = None
    cross_origin: str | None = None
    slow_started: threading.Event = field(default_factory=threading.Event)

    def hit(self, path: str) -> None:
        with self.lock:
            self.hits[path] = self.hits.get(path, 0) + 1


class _TestServer(ThreadingHTTPServer):
    state: _ServerState


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _state(self) -> _ServerState:
        return cast(_TestServer, self.server).state

    def _respond(self, status: int, payload: bytes, media_type: str = "application/octet-stream") -> None:
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Unsafe-Server-Secret", "must-not-persist")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _handle(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        state = self._state()
        state.hit(path)
        if path == "/api/get":
            payload = json.dumps(
                {
                    "query": parse_qs(parsed.query),
                    "x-normal": self.headers.get("X-Normal"),
                },
                sort_keys=True,
            ).encode()
            self._respond(200, payload, "application/json")
            return
        if path == "/api/status":
            self._respond(200, b"not-semantic-task-success", "text/plain")
            return
        if path == "/api/auth":
            authorization = self.headers.get("Authorization")
            state.observed_authorization.append(authorization)
            self._respond(200 if authorization == "Bearer exact-secret" else 401, b"authorized")
            return
        if path == "/api/echo":
            remaining = int(self.headers.get("Content-Length", "0"))
            digest = hashlib.sha256()
            chunks: list[bytes] = []
            while remaining:
                chunk = self.rfile.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                digest.update(chunk)
                chunks.append(chunk)
            state.upload_sha256 = digest.hexdigest()
            self._respond(200, b"".join(chunks), self.headers.get("Content-Type", "application/octet-stream"))
            return
        if path == "/api/large":
            self._respond(200, _LARGE_BINARY)
            return
        if path == "/api/slow":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(4096 * 200))
            self.end_headers()
            state.slow_started.set()
            try:
                for _ in range(200):
                    self.wfile.write(b"s" * 4096)
                    self.wfile.flush()
                    time.sleep(0.02)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if path == "/api/redirect-same":
            self.send_response(302)
            self.send_header("Location", "/api/get?redirected=yes")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/api/redirect-cross":
            assert state.cross_origin is not None
            self.send_response(302)
            self.send_header("Location", f"{state.cross_origin}/api/capture")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/api/capture":
            state.observed_authorization.append(self.headers.get("Authorization"))
            self._respond(200, b"cross-origin-captured", "text/plain")
            return
        self._respond(404, b"missing", "text/plain")

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()


@contextmanager
def _server() -> Iterator[tuple[str, _ServerState]]:
    state = _ServerState()
    server = _TestServer(("127.0.0.1", 0), _Handler)
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


@contextmanager
def _tls_server(tmp_path: Path) -> Iterator[tuple[str, _ServerState]]:
    certificate = tmp_path / "self-signed.crt"
    private_key = tmp_path / "self-signed.key"
    generated = subprocess.run(
        (
            "/usr/bin/openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert generated.returncode == 0, generated.stderr
    state = _ServerState()
    server = _TestServer(("127.0.0.1", 0), _Handler)
    server.state = state
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, private_key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = cast(tuple[str, int], server.server_address)
        yield f"https://{host}:{port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@dataclass(frozen=True)
class _Environment:
    database: Path
    objects: FilesystemObjectStorageBackend
    access: ProjectAccess
    project_ref: ProjectRef
    task: Task
    attempt: NodeExecutionAttempt
    http: StdlibHttpAdapter


def _environment(tmp_path: Path, *, namespace: str = "http-adapter") -> _Environment:
    tmp_path.mkdir(parents=True, exist_ok=True)
    database = tmp_path / f"{namespace}.sqlite3"
    registration = ProjectStore(database).create_project(namespace=namespace, display_name=namespace.title())
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    adapter = StdlibHttpAdapter(
        database,
        objects,
        supported_data_policy_refs=(f"policy://{namespace}/data",),
        supported_egress_policy_refs=(f"policy://{namespace}/egress",),
    )
    implementations = adapter.register_capabilities(registration.access)
    capabilities = tuple(sorted(implementations))
    task = TaskRevisionService(database).create_task(
        registration.access,
        project_ref=registration.project.project_ref,
        idempotency_key="http-task",
        task_type="transport.http",
        objective="Verify policy-bound HTTP transport",
        required_capabilities=capabilities,
        input_refs=(),
        output_contract={"result": "schema://biella/http-execution-result/1"},
        constraints={},
        side_effect_authority="EXTERNAL_SIDE_EFFECT",
        data_policy_ref=f"policy://{namespace}/data",
        egress_policy_ref=f"policy://{namespace}/egress",
        evidence_requirements=("tool-call", "artifact", "content-ref"),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(registration.access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        registration.access,
        run.run_ref,
        owner_ref="controller://http-tests",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(registration.project.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "TOOL",
        capabilities,
        (),
        (),
        {"result": "schema://biella/http-execution-result/1"},
        None,
        "EXTERNAL_SIDE_EFFECT",
        {},
        ("tool-call", "artifact", "content-ref"),
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
        owner_ref="executor://http-tests",
        lease_seconds=1800,
        idempotency_key="http-node-lease",
    )
    executions.start_node(registration.access, attempt, idempotency_key="http-node-start")
    return _Environment(
        database,
        objects,
        registration.access,
        registration.project.project_ref,
        task,
        attempt,
        adapter,
    )


def _destination(
    env: _Environment,
    origin: str,
    *,
    auth_profile_ref: str | None = None,
    auth_header_name: str | None = None,
    redirect_path_allowlist: dict[str, tuple[str, ...]] | None = None,
    tls_policy: HttpTlsPolicy = HttpTlsPolicy.ALLOW_PLAINTEXT,
    key: str = "http-destination",
) -> HttpDestination:
    destination = HttpDestination.create(
        env.project_ref,
        origin=origin,
        allowed_path_prefixes=("/api",),
        auth_profile_ref=auth_profile_ref,
        auth_header_name=auth_header_name,
        data_policy_ref=cast(str, env.task.data_policy_ref),
        egress_policy_ref=cast(str, env.task.egress_policy_ref),
        tls_policy=tls_policy,
        redirect_path_allowlist={} if redirect_path_allowlist is None else redirect_path_allowlist,
    )
    return env.http.register_destination(env.access, destination, idempotency_key=key)


def _request(
    env: _Environment,
    destination: HttpDestination,
    *,
    method: str = "GET",
    path: str = "/api/get",
    query: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    secret_header_refs: dict[str, str] | None = None,
    body_ref: biella.ContentRef | None = None,
    redirect_policy: HttpRedirectPolicy = HttpRedirectPolicy.NONE,
    max_redirects: int = 0,
    max_response_bytes: int = 16 * 1024 * 1024,
    timeout_seconds: float = 10,
    expected_response_sha256: str | None = None,
    data_policy_ref: str | None = None,
) -> HttpExecutionRequest:
    return HttpExecutionRequest(
        env.project_ref,
        HttpExecutionRef.new(env.project_ref),
        destination.destination_ref,
        env.task.task_ref,
        env.task.canonical_digest,
        env.attempt.run_ref,
        env.attempt.node_ref,
        env.attempt.attempt_id,
        env.attempt.fence,
        cast(str, env.task.data_policy_ref) if data_policy_ref is None else data_policy_ref,
        cast(str, env.task.egress_policy_ref),
        method,
        path,
        {} if query is None else query,
        {} if headers is None else headers,
        {} if secret_header_refs is None else secret_header_refs,
        body_ref,
        redirect_policy,
        max_redirects,
        max_response_bytes,
        timeout_seconds,
        expected_response_sha256,
    )


def test_t02_capabilities_descriptor_destination_restart_and_scope(tmp_path: Path) -> None:
    with _server() as (origin, _):
        env = _environment(tmp_path / "alpha", namespace="http-alpha")
        implementations = env.http.register_capabilities(env.access)
        assert set(implementations) == {
            CapabilityRef("http.execute", "1.0.0"),
            CapabilityRef("http.cancel", "1.0.0"),
            CapabilityRef("http.describe", "1.0.0"),
        }
        execute_implementation = implementations[CapabilityRef("http.execute", "1.0.0")]
        assert execute_implementation.remote_egress
        assert execute_implementation.supported_data_policy_refs == (env.task.data_policy_ref,)
        assert execute_implementation.supported_egress_policy_refs == (env.task.egress_policy_ref,)
        assert isinstance(env.http, HttpAdapter)
        descriptor = env.http.describe(env.access, env.attempt)
        assert descriptor.transport_kind == "stdlib.http.client"
        assert descriptor.verified_tls and descriptor.streaming_upload and descriptor.streaming_download
        destination = _destination(env, origin)
        assert env.http.register_destination(env.access, destination, idempotency_key="http-destination") == destination
        unconfigured = StdlibHttpAdapter(env.database, env.objects)
        with pytest.raises(biella.HttpAuthorityError, match="not supported"):
            unconfigured.register_destination(
                env.access,
                HttpDestination.create(
                    env.project_ref,
                    origin=origin,
                    allowed_path_prefixes=("/api",),
                    auth_profile_ref=None,
                    auth_header_name=None,
                    data_policy_ref=cast(str, env.task.data_policy_ref),
                    egress_policy_ref=cast(str, env.task.egress_policy_ref),
                    tls_policy=HttpTlsPolicy.ALLOW_PLAINTEXT,
                ),
                idempotency_key="unconfigured-destination",
            )
        restarted = StdlibHttpAdapter(env.database, FilesystemObjectStorageBackend(tmp_path / "alpha" / "objects"))
        assert restarted.get_destination(env.access, destination.destination_ref) == destination
        changed = HttpDestination(
            destination.destination_ref,
            destination.origin,
            ("/different",),
            destination.auth_profile_ref,
            destination.auth_header_name,
            destination.data_policy_ref,
            destination.egress_policy_ref,
            destination.tls_policy,
            destination.redirect_path_allowlist,
        )
        with pytest.raises(HttpConflictError):
            env.http.register_destination(env.access, changed, idempotency_key="http-destination")
        beta = ProjectStore(env.database).create_project(namespace="http-beta", display_name="HTTP Beta")
        with pytest.raises(HttpScopeError):
            env.http.get_destination(beta.access, destination.destination_ref)


def test_t03_real_get_safe_headers_artifact_idempotency_and_transport_only_success(tmp_path: Path) -> None:
    with _server() as (origin, _):
        env = _environment(tmp_path)
        destination = _destination(env, origin)
        request = _request(env, destination, query={"value": "exact"}, headers={"x-normal": "safe"})
        result = env.http.execute(env.access, env.attempt, request, secret_values={}, idempotency_key="real-get")
        assert result.transport_success and result.failure is None and result.status_code == 200
        assert result.semantic_success is None
        assert result.response_ref is not None and result.response_artifact_ref is not None
        payload = json.loads(env.objects.read(result.response_ref))
        assert payload == {"query": {"value": ["exact"]}, "x-normal": "safe"}
        assert set(result.response_headers).issubset(
            {"cache-control", "content-encoding", "content-language", "content-length", "content-type", "etag", "last-modified"}
        )
        assert env.http.execute(env.access, env.attempt, request, secret_values={}, idempotency_key="real-get") == result
        artifact = ArtifactService(env.database).get_artifact(env.access, result.response_artifact_ref)
        assert artifact.content_ref == result.response_ref
        assert env.http.get_result(env.access, request.execution_ref) == result
        semantic = _request(env, destination, path="/api/status")
        semantic_result = env.http.execute(
            env.access,
            env.attempt,
            semantic,
            secret_values={},
            idempotency_key="semantic-status",
        )
        assert semantic_result.transport_success and semantic_result.status_code == 200
        assert semantic_result.semantic_success is None
        missing = _request(env, destination, path="/api/missing")
        missing_result = env.http.execute(
            env.access,
            env.attempt,
            missing,
            secret_values={},
            idempotency_key="http-error-status",
        )
        assert missing_result.transport_success and missing_result.status_code == 404
        assert missing_result.failure is HttpExecutionFailure.HTTP_ERROR


def test_t04_streamed_binary_post_upload_and_download_are_exact(tmp_path: Path) -> None:
    with _server() as (origin, state):
        env = _environment(tmp_path)
        destination = _destination(env, origin)
        source = env.objects.put(_LARGE_BINARY, media_type="application/octet-stream")
        request = _request(
            env,
            destination,
            method="POST",
            path="/api/echo",
            body_ref=source,
            max_response_bytes=len(_LARGE_BINARY),
            expected_response_sha256=hashlib.sha256(_LARGE_BINARY).hexdigest(),
        )
        result = env.http.execute(env.access, env.attempt, request, secret_values={}, idempotency_key="binary-echo")
        assert result.transport_success and result.failure is None
        assert result.bytes_sent == result.bytes_received == len(_LARGE_BINARY)
        assert state.upload_sha256 == source.digest
        assert result.response_ref is not None
        assert result.response_ref.digest == source.digest
        assert env.objects.read(result.response_ref) == _LARGE_BINARY


def test_t05_credentials_injected_after_policy_and_absent_from_normal_evidence(tmp_path: Path) -> None:
    with _server() as (origin, state):
        env = _environment(tmp_path)
        secret_ref = "secret://http/auth-profile"
        secret = "Bearer exact-secret"
        destination = _destination(
            env,
            origin,
            auth_profile_ref=secret_ref,
            auth_header_name="authorization",
        )
        request = _request(env, destination, path="/api/auth")
        result = env.http.execute(
            env.access,
            env.attempt,
            request,
            secret_values={secret_ref: secret},
            idempotency_key="credential-get",
        )
        assert result.transport_success and result.status_code == 200 and result.failure is None
        assert state.observed_authorization == [secret]
        rejected = _request(env, destination, path="/api/auth")
        rejected_result = env.http.execute(
            env.access,
            env.attempt,
            rejected,
            secret_values={secret_ref: "Bearer wrong-secret"},
            idempotency_key="rejected-credential-get",
        )
        assert rejected_result.transport_success and rejected_result.status_code == 401
        assert rejected_result.failure is HttpExecutionFailure.AUTH_FAILED
        missing = _request(env, destination, path="/api/auth")
        missing_result = env.http.execute(
            env.access,
            env.attempt,
            missing,
            secret_values={},
            idempotency_key="missing-credential-get",
        )
        assert not missing_result.transport_success
        assert missing_result.failure is HttpExecutionFailure.AUTH_FAILED
        database_bytes = env.database.read_bytes()
        assert secret.encode() not in database_bytes
        assert b"Bearer wrong-secret" not in database_bytes
        for content_path in (tmp_path / "objects" / "objects" / "sha256").rglob("content"):
            content = content_path.read_bytes()
            assert secret.encode() not in content
            assert b"Bearer wrong-secret" not in content
        with pytest.raises(HttpContractError, match="sensitive"):
            _request(env, destination, headers={"authorization": secret})
        with pytest.raises(HttpContractError, match="query"):
            _request(env, destination, query={"api_key": "secret"})


def test_t06_egress_denied_before_body_or_secret_transfer_and_project_scope(tmp_path: Path) -> None:
    with _server() as (origin, state):
        env = _environment(tmp_path / "alpha", namespace="http-denied-alpha")
        destination = _destination(env, origin)
        body = env.objects.put(_LARGE_BINARY, media_type="application/octet-stream")
        denied = _request(
            env,
            destination,
            method="POST",
            path="/forbidden",
            body_ref=body,
            data_policy_ref="policy://wrong/data",
        )
        result = env.http.execute(
            env.access,
            env.attempt,
            denied,
            secret_values={"secret://not-authorized": "must-not-be-read"},
            idempotency_key="egress-denied",
        )
        assert not result.transport_success and result.failure is HttpExecutionFailure.EGRESS_DENIED
        assert result.bytes_sent == 0 and result.response_ref is None
        assert state.hits.get("/forbidden", 0) == 0
        beta = ProjectStore(env.database).create_project(namespace="http-denied-beta", display_name="HTTP Denied Beta")
        with pytest.raises(HttpScopeError):
            HttpExecutionRequest(
                beta.project.project_ref,
                HttpExecutionRef.new(beta.project.project_ref),
                destination.destination_ref,
                env.task.task_ref,
                env.task.canonical_digest,
                env.attempt.run_ref,
                env.attempt.node_ref,
                env.attempt.attempt_id,
                env.attempt.fence,
                cast(str, env.task.data_policy_ref),
                cast(str, env.task.egress_policy_ref),
                "GET",
                "/api/get",
            )


def test_t07_redirects_reauthorize_origin_path_and_drop_cross_origin_credentials(tmp_path: Path) -> None:
    with _server() as (target_origin, target_state), _server() as (source_origin, source_state):
        source_state.cross_origin = target_origin
        env = _environment(tmp_path)
        same_destination = _destination(env, source_origin, key="same-destination")
        same = _request(
            env,
            same_destination,
            path="/api/redirect-same",
            redirect_policy=HttpRedirectPolicy.SAME_ORIGIN,
            max_redirects=2,
        )
        same_result = env.http.execute(env.access, env.attempt, same, secret_values={}, idempotency_key="same-redirect")
        assert same_result.transport_success and same_result.redirect_chain == (f"{source_origin}/api/get",)

        denied_destination = _destination(env, source_origin, key="denied-cross-destination")
        denied = _request(
            env,
            denied_destination,
            path="/api/redirect-cross",
            redirect_policy=HttpRedirectPolicy.ALLOWLIST,
            max_redirects=2,
        )
        denied_result = env.http.execute(
            env.access,
            env.attempt,
            denied,
            secret_values={},
            idempotency_key="denied-cross-redirect",
        )
        assert not denied_result.transport_success
        assert denied_result.failure is HttpExecutionFailure.REDIRECT_DENIED
        assert target_state.hits.get("/api/capture", 0) == 0

        secret_ref = "secret://http/redirect-auth"
        allowed_destination = _destination(
            env,
            source_origin,
            auth_profile_ref=secret_ref,
            auth_header_name="authorization",
            redirect_path_allowlist={target_origin: ("/api",)},
            key="allowed-cross-destination",
        )
        allowed = _request(
            env,
            allowed_destination,
            path="/api/redirect-cross",
            redirect_policy=HttpRedirectPolicy.ALLOWLIST,
            max_redirects=2,
        )
        allowed_result = env.http.execute(
            env.access,
            env.attempt,
            allowed,
            secret_values={secret_ref: "Bearer exact-secret"},
            idempotency_key="allowed-cross-redirect",
        )
        assert allowed_result.transport_success and allowed_result.status_code == 200
        assert target_state.observed_authorization == [None]


def test_t08_response_cap_and_expected_digest_fail_without_authoritative_partial_content(tmp_path: Path) -> None:
    with _server() as (origin, _):
        env = _environment(tmp_path)
        destination = _destination(env, origin)
        capped = _request(env, destination, path="/api/large", max_response_bytes=1024)
        capped_result = env.http.execute(env.access, env.attempt, capped, secret_values={}, idempotency_key="capped-response")
        assert not capped_result.transport_success
        assert capped_result.failure is HttpExecutionFailure.OUTPUT_LIMIT
        assert capped_result.bytes_received == 1025 and capped_result.response_ref is None
        integrity = _request(env, destination, path="/api/get", expected_response_sha256="0" * 64)
        integrity_result = env.http.execute(
            env.access,
            env.attempt,
            integrity,
            secret_values={},
            idempotency_key="integrity-response",
        )
        assert not integrity_result.transport_success
        assert integrity_result.failure is HttpExecutionFailure.CONTENT_INTEGRITY_FAILED
        assert integrity_result.response_ref is None


def test_t09_timeout_and_concurrent_cancellation_close_streams_without_partial_success(tmp_path: Path) -> None:
    with _server() as (origin, state):
        env = _environment(tmp_path)
        destination = _destination(env, origin)
        timeout = _request(env, destination, path="/api/slow", timeout_seconds=0.08)
        timeout_result = env.http.execute(env.access, env.attempt, timeout, secret_values={}, idempotency_key="timeout-response")
        assert not timeout_result.transport_success
        assert timeout_result.failure is HttpExecutionFailure.TIMEOUT
        assert timeout_result.response_ref is None

        state.slow_started.clear()
        cancelled = _request(env, destination, path="/api/slow", timeout_seconds=10)
        with pytest.raises(biella.HttpNotFoundError, match="claim"):
            env.http.cancel(
                env.access,
                env.attempt,
                HttpExecutionRef.new(env.project_ref),
                idempotency_key="reject-unowned-cancel",
            )
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(
                env.http.execute,
                env.access,
                env.attempt,
                cancelled,
                secret_values={},
                idempotency_key="cancelled-response",
            )
            assert state.slow_started.wait(timeout=3)
            receipt = env.http.cancel(
                env.access,
                env.attempt,
                cancelled.execution_ref,
                idempotency_key="cancel-http-execution",
            )
            result = future.result(timeout=5)
        assert receipt.accepted
        assert env.http.cancel(
            env.access,
            env.attempt,
            cancelled.execution_ref,
            idempotency_key="cancel-http-execution",
        ) == receipt
        assert not result.transport_success and result.failure is HttpExecutionFailure.CANCELLED
        assert result.response_ref is None


def test_t10_restart_idempotency_scope_tamper_and_content_erasure_fail_closed(tmp_path: Path) -> None:
    with _server() as (origin, _):
        env = _environment(tmp_path / "restart", namespace="http-restart")
        destination = _destination(env, origin)
        request = _request(env, destination)
        result = env.http.execute(env.access, env.attempt, request, secret_values={}, idempotency_key="restart-get")
        restarted = StdlibHttpAdapter(env.database, FilesystemObjectStorageBackend(tmp_path / "restart" / "objects"))
        assert restarted.get_result(env.access, request.execution_ref) == result
        changed = _request(env, destination, path="/api/status")
        with pytest.raises(HttpConflictError):
            env.http.execute(env.access, env.attempt, changed, secret_values={}, idempotency_key="restart-get")
        beta = ProjectStore(env.database).create_project(namespace="http-result-beta", display_name="HTTP Result Beta")
        with pytest.raises(HttpScopeError):
            restarted.get_result(beta.access, request.execution_ref)
        with sqlite3.connect(env.database) as connection:
            connection.execute("DROP TRIGGER http_execution_results_no_update")
            connection.execute(
                "UPDATE http_execution_results SET record_sha256=? WHERE project_id=? AND execution_id=?",
                ("0" * 64, env.project_ref.value, request.execution_ref.execution_id),
            )
        with pytest.raises(biella.HttpIntegrityError, match="evidence changed"):
            restarted.get_result(env.access, request.execution_ref)

        erased = _environment(tmp_path / "erased", namespace="http-erased")
        erased_destination = _destination(erased, origin)
        erased_request = _request(erased, erased_destination)
        erased_result = erased.http.execute(
            erased.access,
            erased.attempt,
            erased_request,
            secret_values={},
            idempotency_key="erased-get",
        )
        assert erased_result.response_ref is not None
        digest = erased_result.response_ref.digest
        object_path = tmp_path / "erased" / "objects" / "objects" / "sha256" / digest[:2] / digest[2:4] / digest / "content"
        object_path.unlink()
        with pytest.raises(biella.HttpIntegrityError, match="ContentRef evidence"):
            erased.http.get_result(erased.access, erased_request.execution_ref)

        destination_tamper = _environment(tmp_path / "destination", namespace="http-destination-tamper")
        tampered_destination = _destination(destination_tamper, origin)
        with sqlite3.connect(destination_tamper.database) as connection:
            connection.execute("DROP TRIGGER http_destinations_no_update")
            connection.execute(
                "UPDATE http_destinations SET record_sha256=? WHERE project_id=? AND destination_id=?",
                ("0" * 64, destination_tamper.project_ref.value, tampered_destination.destination_ref.destination_id),
            )
        with pytest.raises(biella.HttpIntegrityError, match="evidence changed"):
            destination_tamper.http.get_destination(destination_tamper.access, tampered_destination.destination_ref)


def test_t11_invalid_tls_certificate_is_never_silently_accepted(tmp_path: Path) -> None:
    tls_root = tmp_path / "tls"
    tls_root.mkdir()
    with _tls_server(tls_root) as (origin, _):
        env = _environment(tmp_path / "environment", namespace="http-tls")
        destination = _destination(
            env,
            origin,
            tls_policy=HttpTlsPolicy.REQUIRE_VERIFIED_TLS,
        )
        request = _request(env, destination)
        result = env.http.execute(env.access, env.attempt, request, secret_values={}, idempotency_key="invalid-tls")
        assert not result.transport_success
        assert result.failure is HttpExecutionFailure.TLS_FAILED
        assert result.response_ref is None


def test_t12_kernel_contracts_have_no_provider_http_types() -> None:
    root = Path(__file__).parents[1]
    request = HttpExecutionRequest
    assert request is not None
    for provider_type in ("HTTPConnection", "HTTPSConnection", "http.client", "requests.Session", "aiohttp"):
        assert provider_type not in (root / "src/biella/task.py").read_text(encoding="utf-8")
        assert provider_type not in (root / "src/biella/graph.py").read_text(encoding="utf-8")


def test_t15_type_build_exact_wheel_and_separate_installed_restart() -> None:
    root = Path(__file__).resolve().parents[1]
    source_paths = (
        root / "src/biella/__init__.py",
        root / "src/biella/http_adapter.py",
        root / "tests/test_p2_05_http_adapter.py",
        root / "tests/fixtures/p2_05_installed_writer.py",
        root / "tests/fixtures/p2_05_installed_reader.py",
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
        for path in sorted((root / "src/biella").glob("*.py"))
        if path.name != "migration.py"
    )
    assert "QuarantineRef" not in active_runtime
    typecheck = subprocess.run(
        (sys.executable, "-m", "mypy", "--strict", "src", "tests"),
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
        wheels = tuple(wheel_root.glob("biella_engine-*.whl"))
        assert len(wheels) == 1
        wheel = wheels[0]
        package_paths = tuple(sorted((root / "src/biella").glob("*.py")))
        with zipfile.ZipFile(wheel) as archive:
            wheel_names = {
                name
                for name in archive.namelist()
                if name.startswith("biella/") and name.endswith(".py")
            }
            assert wheel_names == {f"biella/{path.name}" for path in package_paths}
            for path in package_paths:
                assert hashlib.sha256(archive.read(f"biella/{path.name}")).hexdigest() == hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        installed = temporary / "installed"
        install = subprocess.run(
            (
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(installed),
                str(wheel),
            ),
            cwd=temporary,
            check=False,
            capture_output=True,
            text=True,
        )
        assert install.returncode == 0, f"{install.stdout}\n{install.stderr}"
        environment = os.environ.copy()
        environment.update(
            {
                "BIELLA_DATABASE": str(temporary / "restart.sqlite3"),
                "BIELLA_OBJECT_ROOT": str(temporary / "objects"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(installed),
            }
        )
        writer = subprocess.run(
            (sys.executable, str(root / "tests/fixtures/p2_05_installed_writer.py")),
            cwd=temporary,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert writer.returncode == 0, f"{writer.stdout}\n{writer.stderr}"
        identity = json.loads(writer.stdout)
        environment["BIELLA_EXPECTED"] = json.dumps(identity, sort_keys=True)
        reader = subprocess.run(
            (sys.executable, str(root / "tests/fixtures/p2_05_installed_reader.py")),
            cwd=temporary,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert reader.returncode == 0, f"{reader.stdout}\n{reader.stderr}"
        observed = json.loads(reader.stdout)
        assert observed["record_sha256"] == identity["record_sha256"]
        assert observed["response_artifact_ref"] == identity["response_artifact_ref"]
        assert observed["response_digest"] == identity["response_digest"]
        assert observed["tool_call_id"] == identity["tool_call_id"]
