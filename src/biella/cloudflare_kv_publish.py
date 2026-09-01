"""Replaceable Cloudflare KV transport for provider-neutral delivery publishing."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import http.client
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import BinaryIO, Protocol, cast
from urllib.parse import quote

from .artifact import Artifact, ArtifactRef, ArtifactService, ContentRef
from .capability import CapabilityRef
from .delivery_pack import PublishReceipt, PublishRequest
from .execution import NodeExecutionAttempt, NodeExecutionService
from .graph import GraphService, Node
from .object_store import ObjectStorageBackend
from .project import ProjectAccess, ProjectRef
from .run import ExecutionAttempt, RunService
from .scheduler import ResourceAllocation, ScheduledDispatch, Scheduler
from .task import TaskRevisionService


_IDENTITY = re.compile(r"[A-Za-z0-9_-]{1,128}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ADAPTER_REF = "adapter://cloudflare/kv-publish/v1"
_DESTINATION_TYPE = "cloudflare-kv"
_EVIDENCE_MEDIA_TYPE = "application/vnd.biella.cloudflare-kv-publish-evidence+json"
_MANIFEST_MEDIA_TYPE = "application/vnd.biella.cloudflare-kv-package-manifest+json"


class CloudflareKvPublishError(RuntimeError):
    """Base failure for the provider adapter."""


class CloudflareKvContractError(CloudflareKvPublishError):
    """The provider-neutral request cannot be represented exactly in KV."""


class CloudflareKvAuthorityError(CloudflareKvPublishError):
    """Current kernel authority is insufficient or stale."""


class CloudflareKvConflictError(CloudflareKvPublishError):
    """An idempotency claim conflicts with durable evidence."""


class CloudflareKvIntegrityError(CloudflareKvPublishError):
    """Durable local or remote evidence failed verification."""


class _KnownFailure(Exception):
    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


class _OutcomeUnknown(Exception):
    pass


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CloudflareKvIntegrityError("authority lease timestamp is malformed") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise CloudflareKvIntegrityError("authority lease timestamp lacks timezone")
    return result


def _content_equal(left: ContentRef, right: ContentRef) -> bool:
    return (
        left.algorithm == right.algorithm
        and hmac.compare_digest(left.digest, right.digest)
        and left.size_bytes == right.size_bytes
        and left.media_type == right.media_type
    )


@dataclass(frozen=True)
class CloudflareKvTransportResponse:
    """Bounded transport observation; request credentials are never represented."""

    status_code: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.status_code, int)
            or isinstance(self.status_code, bool)
            or not 100 <= self.status_code <= 599
        ):
            raise CloudflareKvContractError("Cloudflare transport status is malformed")
        if not isinstance(self.body, bytes):
            raise CloudflareKvContractError("Cloudflare transport body must be bytes")
        if not isinstance(self.headers, Mapping) or len(self.headers) > 256:
            raise CloudflareKvContractError("Cloudflare response headers are unbounded")
        copied: dict[str, str] = {}
        for name, value in self.headers.items():
            if not isinstance(name, str) or not isinstance(value, str):
                raise CloudflareKvContractError("Cloudflare response headers are malformed")
            copied[name.lower()] = value
        object.__setattr__(self, "headers", MappingProxyType(dict(sorted(copied.items()))))


class CloudflareKvTransport(Protocol):
    """Provider transport seam; replaceable by a safe fake or real HTTP client."""

    def get(
        self,
        account_id: str,
        namespace_id: str,
        key: str,
        token: str,
    ) -> CloudflareKvTransportResponse: ...

    def put(
        self,
        account_id: str,
        namespace_id: str,
        key: str,
        body: BinaryIO,
        *,
        content_length: int,
        content_sha256: str,
        content_type: str,
        token: str,
    ) -> CloudflareKvTransportResponse: ...


class CloudflareKvHttpTransport:
    """Minimal real Cloudflare v4 API transport with streaming request bodies."""

    def __init__(self, *, timeout_seconds: float = 60.0) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not 0 < float(timeout_seconds) <= 600
        ):
            raise CloudflareKvContractError("Cloudflare timeout is invalid")
        self.timeout_seconds = float(timeout_seconds)

    @staticmethod
    def _path(account_id: str, namespace_id: str, key: str) -> str:
        return (
            "/client/v4/accounts/"
            + quote(account_id, safe="")
            + "/storage/kv/namespaces/"
            + quote(namespace_id, safe="")
            + "/values/"
            + quote(key, safe="")
        )

    @staticmethod
    def _response(response: http.client.HTTPResponse) -> CloudflareKvTransportResponse:
        return CloudflareKvTransportResponse(
            response.status,
            response.read(),
            {name.lower(): value for name, value in response.getheaders()},
        )

    def get(
        self,
        account_id: str,
        namespace_id: str,
        key: str,
        token: str,
    ) -> CloudflareKvTransportResponse:
        connection = http.client.HTTPSConnection(
            "api.cloudflare.com",
            timeout=self.timeout_seconds,
        )
        try:
            connection.request(
                "GET",
                self._path(account_id, namespace_id, key),
                headers={"Authorization": f"Bearer {token}"},
            )
            return self._response(connection.getresponse())
        finally:
            connection.close()

    def put(
        self,
        account_id: str,
        namespace_id: str,
        key: str,
        body: BinaryIO,
        *,
        content_length: int,
        content_sha256: str,
        content_type: str,
        token: str,
    ) -> CloudflareKvTransportResponse:
        del content_sha256
        connection = http.client.HTTPSConnection(
            "api.cloudflare.com",
            timeout=self.timeout_seconds,
        )
        try:
            connection.putrequest("PUT", self._path(account_id, namespace_id, key))
            connection.putheader("Authorization", f"Bearer {token}")
            connection.putheader("Content-Type", content_type)
            connection.putheader("Content-Length", str(content_length))
            connection.endheaders()
            remaining = content_length
            while remaining:
                chunk = body.read(min(1024 * 1024, remaining))
                if not isinstance(chunk, bytes) or not chunk:
                    raise CloudflareKvIntegrityError(
                        "verified package stream ended before its declared size"
                    )
                connection.send(chunk)
                remaining -= len(chunk)
            if body.read(1):
                raise CloudflareKvIntegrityError(
                    "verified package stream exceeded its declared size"
                )
            return self._response(connection.getresponse())
        finally:
            connection.close()


@dataclass(frozen=True)
class _PackageSource:
    artifact: Artifact
    content_ref: ContentRef


class CloudflareKvPublishAdapter:
    """Cloudflare KV implementation of the provider-neutral PublishAdapter."""

    adapter_ref = _ADAPTER_REF

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        access: ProjectAccess,
        dispatch: ScheduledDispatch,
        account_id: str,
        namespace_id: str,
        secret_resolver: Callable[[str], str],
        transport: CloudflareKvTransport,
    ) -> None:
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("object_store must implement ObjectStorageBackend")
        if not isinstance(access, ProjectAccess):
            raise TypeError("access must be ProjectAccess")
        if not isinstance(dispatch, ScheduledDispatch):
            raise TypeError("dispatch must be ScheduledDispatch")
        if dispatch.allocation.project_ref != access.project_ref:
            raise CloudflareKvAuthorityError("ScheduledDispatch crossed Project scope")
        for value, field_name in (
            (account_id, "account_id"),
            (namespace_id, "namespace_id"),
        ):
            if not isinstance(value, str) or _IDENTITY.fullmatch(value) is None:
                raise CloudflareKvContractError(f"Cloudflare {field_name} is malformed")
        if not callable(secret_resolver):
            raise TypeError("secret_resolver must be callable")
        self.database_path = Path(database_path).resolve()
        self.object_store = object_store
        self.access = access
        self.project_ref: ProjectRef = access.project_ref
        self.dispatch = dispatch
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.secret_resolver = secret_resolver
        self.transport = transport
        self.tasks = TaskRevisionService(self.database_path)
        self.runs = RunService(self.database_path)
        self.graphs = GraphService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.scheduler = Scheduler(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self._initialize_schema()

    @property
    def endpoint_ref(self) -> str:
        return (
            f"cloudflare-kv://accounts/{self.account_id}"
            f"/namespaces/{self.namespace_id}"
        )

    @staticmethod
    def package_key(content_ref: ContentRef) -> str:
        if not isinstance(content_ref, ContentRef):
            raise TypeError("content_ref must be ContentRef")
        return f"biella/packages/{content_ref.digest}"

    @staticmethod
    def manifest_key(manifest_bytes: bytes) -> str:
        if not isinstance(manifest_bytes, bytes):
            raise TypeError("manifest_bytes must be bytes")
        return f"biella/manifests/{hashlib.sha256(manifest_bytes).hexdigest()}"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cloudflare_kv_publish_claims (
                    project_id TEXT NOT NULL,
                    node_attempt_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    request_record_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, node_attempt_id, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS cloudflare_kv_publish_results (
                    project_id TEXT NOT NULL,
                    node_attempt_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    evidence_artifact_id TEXT NOT NULL,
                    evidence_artifact_revision INTEGER NOT NULL,
                    evidence_artifact_record_sha256 TEXT NOT NULL,
                    result_record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, node_attempt_id, idempotency_key),
                    UNIQUE (project_id, request_digest),
                    FOREIGN KEY (project_id, node_attempt_id, idempotency_key)
                        REFERENCES cloudflare_kv_publish_claims
                            (project_id, node_attempt_id, idempotency_key)
                );

                CREATE TRIGGER IF NOT EXISTS cloudflare_kv_publish_claims_no_update
                BEFORE UPDATE ON cloudflare_kv_publish_claims BEGIN
                    SELECT RAISE(ABORT, 'Cloudflare KV publish claims are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS cloudflare_kv_publish_claims_no_delete
                BEFORE DELETE ON cloudflare_kv_publish_claims BEGIN
                    SELECT RAISE(ABORT, 'Cloudflare KV publish claims are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS cloudflare_kv_publish_results_no_update
                BEFORE UPDATE ON cloudflare_kv_publish_results BEGIN
                    SELECT RAISE(ABORT, 'Cloudflare KV publish results are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS cloudflare_kv_publish_results_no_delete
                BEFORE DELETE ON cloudflare_kv_publish_results BEGIN
                    SELECT RAISE(ABORT, 'Cloudflare KV publish results are immutable');
                END;
                """
            )
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _request_payload(request: PublishRequest) -> dict[str, object]:
        return {
            "adapter_ref": request.destination.adapter_ref,
            "destination": request.destination.payload(),
            "idempotency_key": request.idempotency_key,
            "manifest_digest": request.manifest.manifest_digest,
            "mode": request.mode,
            "node_ref": request.node_ref.value,
            "overwrite": request.overwrite,
            "release_ref": request.release_ref,
            "request_digest": request.request_digest,
            "run_id": request.run_ref.run_id,
            "source_bindings": [item.payload() for item in request.manifest.sources],
            "target_ref": request.target_ref,
            "task_id": request.task_ref.task_id,
            "task_revision": request.task_ref.revision,
            "verification_ref": request.verification_ref,
        }

    @staticmethod
    def _receipt_payload(receipt: PublishReceipt) -> dict[str, object]:
        return {
            "failure_ref": receipt.failure_ref,
            "recorded_at": receipt.recorded_at,
            "receipt_digest": receipt.receipt_digest,
            "remote_identity": receipt.remote_identity,
            "remote_version": receipt.remote_version,
            "request_digest": receipt.request_digest,
            "state": receipt.state,
            "upload_sha256": receipt.upload_sha256,
            "verification_evidence_ref": receipt.verification_evidence_ref,
        }

    @staticmethod
    def _required_text(payload: Mapping[str, object], name: str) -> str:
        value = payload.get(name)
        if not isinstance(value, str):
            raise CloudflareKvIntegrityError("persisted publish receipt is malformed")
        return value

    @staticmethod
    def _optional_text(payload: Mapping[str, object], name: str) -> str | None:
        value = payload.get(name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise CloudflareKvIntegrityError("persisted publish receipt is malformed")
        return value

    @classmethod
    def _receipt_from_json(cls, value: str) -> PublishReceipt:
        parsed = cast(object, json.loads(value))
        if not isinstance(parsed, dict):
            raise CloudflareKvIntegrityError("persisted publish receipt is malformed")
        payload = cast(Mapping[str, object], parsed)
        try:
            return PublishReceipt(
                request_digest=cls._required_text(payload, "request_digest"),
                state=cls._required_text(payload, "state"),
                remote_identity=cls._optional_text(payload, "remote_identity"),
                remote_version=cls._optional_text(payload, "remote_version"),
                upload_sha256=cls._optional_text(payload, "upload_sha256"),
                verification_evidence_ref=cls._optional_text(
                    payload,
                    "verification_evidence_ref",
                ),
                recorded_at=cls._required_text(payload, "recorded_at"),
                failure_ref=cls._optional_text(payload, "failure_ref"),
                receipt_digest=cls._required_text(payload, "receipt_digest"),
            )
        except ValueError as exc:
            raise CloudflareKvIntegrityError(
                "persisted publish receipt failed contract verification"
            ) from exc

    def _claim_or_replay(
        self,
        attempt: NodeExecutionAttempt,
        request: PublishRequest,
    ) -> PublishReceipt | None:
        request_json = _canonical_json(self._request_payload(request)).decode("utf-8")
        request_record_sha256 = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                """
                SELECT * FROM cloudflare_kv_publish_claims
                WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?
                """,
                (self.project_ref.value, attempt.attempt_id, request.idempotency_key),
            ).fetchone()
            if prior is None:
                connection.execute(
                    "INSERT INTO cloudflare_kv_publish_claims VALUES (?,?,?,?,?,?,?)",
                    (
                        self.project_ref.value,
                        attempt.attempt_id,
                        request.idempotency_key,
                        request.request_digest,
                        request_json,
                        request_record_sha256,
                        _now(),
                    ),
                )
                connection.commit()
                return None
            if (
                prior["request_digest"] != request.request_digest
                or prior["request_json"] != request_json
                or prior["request_record_sha256"] != request_record_sha256
            ):
                raise CloudflareKvConflictError(
                    "Cloudflare KV idempotency key is bound to another request"
                )
            result = connection.execute(
                """
                SELECT * FROM cloudflare_kv_publish_results
                WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?
                """,
                (self.project_ref.value, attempt.attempt_id, request.idempotency_key),
            ).fetchone()
            if result is None:
                raise CloudflareKvConflictError(
                    "Cloudflare KV publish claim is incomplete"
                )
            result_basis = {
                "evidence_artifact_id": result["evidence_artifact_id"],
                "evidence_artifact_record_sha256": result[
                    "evidence_artifact_record_sha256"
                ],
                "evidence_artifact_revision": result["evidence_artifact_revision"],
                "receipt_json": result["receipt_json"],
                "request_digest": result["request_digest"],
            }
            if not hmac.compare_digest(
                hashlib.sha256(_canonical_json(result_basis)).hexdigest(),
                cast(str, result["result_record_sha256"]),
            ):
                raise CloudflareKvIntegrityError("persisted publish result changed")
            evidence_ref = ArtifactRef(
                self.project_ref,
                cast(str, result["evidence_artifact_id"]),
                cast(int, result["evidence_artifact_revision"]),
            )
            evidence = self.artifacts.get_artifact(self.access, evidence_ref)
            if not hmac.compare_digest(
                evidence.record_sha256,
                cast(str, result["evidence_artifact_record_sha256"]),
            ):
                raise CloudflareKvIntegrityError("publish evidence Artifact changed")
            if evidence.content_ref is None or not self.object_store.verify(evidence.content_ref):
                raise CloudflareKvIntegrityError("publish evidence bytes are unavailable")
            receipt = self._receipt_from_json(cast(str, result["receipt_json"]))
            if receipt.request_digest != request.request_digest:
                raise CloudflareKvIntegrityError("persisted receipt request binding changed")
            connection.commit()
            return receipt
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _store_result(
        self,
        attempt: NodeExecutionAttempt,
        request: PublishRequest,
        receipt: PublishReceipt,
        evidence: Artifact,
    ) -> None:
        receipt_json = _canonical_json(self._receipt_payload(receipt)).decode("utf-8")
        basis = {
            "evidence_artifact_id": evidence.artifact_id,
            "evidence_artifact_record_sha256": evidence.record_sha256,
            "evidence_artifact_revision": evidence.revision,
            "receipt_json": receipt_json,
            "request_digest": request.request_digest,
        }
        record_sha256 = hashlib.sha256(_canonical_json(basis)).hexdigest()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO cloudflare_kv_publish_results VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    self.project_ref.value,
                    attempt.attempt_id,
                    request.idempotency_key,
                    request.request_digest,
                    receipt_json,
                    evidence.artifact_id,
                    evidence.revision,
                    evidence.record_sha256,
                    record_sha256,
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise CloudflareKvConflictError(
                "Cloudflare KV result persistence conflicts"
            ) from exc
        finally:
            connection.close()

    def get_evidence_artifact_ref(self, request_digest: str) -> ArtifactRef:
        if not isinstance(request_digest, str) or _SHA256.fullmatch(request_digest) is None:
            raise CloudflareKvContractError("request_digest is malformed")
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT evidence_artifact_id, evidence_artifact_revision,
                       evidence_artifact_record_sha256
                FROM cloudflare_kv_publish_results
                WHERE project_id=? AND request_digest=?
                """,
                (self.project_ref.value, request_digest),
            ).fetchall()
        finally:
            connection.close()
        if len(rows) != 1:
            raise CloudflareKvIntegrityError("publish evidence is unavailable or ambiguous")
        artifact_ref = ArtifactRef(
            self.project_ref,
            cast(str, rows[0]["evidence_artifact_id"]),
            cast(int, rows[0]["evidence_artifact_revision"]),
        )
        artifact = self.artifacts.get_artifact(self.access, artifact_ref)
        if artifact.record_sha256 != rows[0]["evidence_artifact_record_sha256"]:
            raise CloudflareKvIntegrityError("publish evidence Artifact changed")
        return artifact_ref

    @staticmethod
    def _required_capability(request: PublishRequest) -> CapabilityRef:
        capability_id = {
            "upload": "publish.upload",
            "deploy": "publish.deploy",
            "release": "publish.release",
            "distribute": "publish.distribute",
            "copy": "delivery.copy",
            "sync": "delivery.sync",
        }[request.mode]
        return CapabilityRef(capability_id, "1.0.0")

    def _validate_destination(self, request: PublishRequest) -> None:
        destination = request.destination
        if destination.project_ref != self.project_ref:
            raise CloudflareKvAuthorityError(
                "Cloudflare KV destination must be bound to the exact Project"
            )
        if destination.adapter_ref != self.adapter_ref:
            raise CloudflareKvAuthorityError("publish destination selected another adapter")
        if destination.destination_type != _DESTINATION_TYPE:
            raise CloudflareKvContractError("publish destination is not Cloudflare KV")
        if destination.endpoint_ref != self.endpoint_ref:
            raise CloudflareKvAuthorityError(
                "Cloudflare account or namespace differs from destination"
            )
        if request.target_ref != request.manifest.target_ref:
            raise CloudflareKvAuthorityError(
                "publish request target differs from package target"
            )

    def _run_attempt(self, attempt: NodeExecutionAttempt) -> ExecutionAttempt:
        matches = tuple(
            item
            for item in self.runs.list_attempts(self.access, attempt.run_ref)
            if item.attempt_id == attempt.run_attempt_id and item.fence == attempt.run_fence
        )
        if len(matches) != 1:
            raise CloudflareKvAuthorityError("exact parent Run attempt is unavailable")
        return matches[0]

    def _revalidate(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: PublishRequest,
    ) -> ExecutionAttempt:
        if access != self.access or access.project_ref != self.project_ref:
            raise CloudflareKvAuthorityError("publish access differs from constructor authority")
        if attempt != self.dispatch.node_attempt:
            raise CloudflareKvAuthorityError("Node attempt differs from ScheduledDispatch")
        if (
            request.task_ref != attempt.task_ref
            or request.run_ref != attempt.run_ref
            or request.node_ref != attempt.node_ref
        ):
            raise CloudflareKvAuthorityError("publish request execution binding is not exact")
        self._validate_destination(request)
        task = self.tasks.get_task(access, attempt.task_ref)
        if (
            task.side_effect_authority != "EXTERNAL_SIDE_EFFECT"
            or not hmac.compare_digest(task.canonical_digest, attempt.task_digest)
        ):
            raise CloudflareKvAuthorityError(
                "Task revision lacks exact external side-effect authority"
            )
        TaskRevisionService.require_side_effect_within(task, "EXTERNAL_SIDE_EFFECT")
        if (
            task.data_policy_ref != request.destination.data_policy_ref
            or task.egress_policy_ref is None
        ):
            raise CloudflareKvAuthorityError("publish data/egress policy is not exact")
        graph = self.graphs.get_graph(access, attempt.node_ref.graph_ref)
        active_graph = self.graphs.get_active_graph(access, attempt.run_ref)
        if graph.graph_ref != active_graph.graph_ref:
            raise CloudflareKvAuthorityError("publish Graph revision is not active")
        if (
            graph.task_ref != attempt.task_ref
            or graph.run_ref != attempt.run_ref
            or not hmac.compare_digest(graph.task_digest, attempt.task_digest)
        ):
            raise CloudflareKvAuthorityError("publish Graph Task/Run binding changed")
        node: Node | None = next(
            (item for item in graph.nodes if item.node_ref == attempt.node_ref),
            None,
        )
        if (
            node is None
            or node.side_effect_requirement != "EXTERNAL_SIDE_EFFECT"
            or self._required_capability(request) not in node.required_capabilities
        ):
            raise CloudflareKvAuthorityError(
                "Node lacks exact publish capability or external authority"
            )
        run_attempt = self._run_attempt(attempt)
        self.runs.assert_current_run_authority(access, run_attempt)
        node_state = self.executions.get_node_execution(access, attempt.node_ref)
        database_now = datetime.now(timezone.utc)
        if (
            node_state.status != "RUNNING"
            or node_state.current_attempt_id != attempt.attempt_id
            or node_state.current_attempt_number != attempt.attempt_number
            or node_state.current_fence != attempt.fence
            or node_state.current_owner_ref != attempt.owner_ref
            or node_state.current_run_attempt_id != attempt.run_attempt_id
            or node_state.current_run_fence != attempt.run_fence
            or node_state.task_ref != attempt.task_ref
            or not hmac.compare_digest(node_state.task_digest, attempt.task_digest)
            or node_state.lease_expires_at is None
            or _timestamp(node_state.lease_expires_at) <= database_now
            or _timestamp(attempt.lease_expires_at) <= database_now
        ):
            raise CloudflareKvAuthorityError("Node attempt no longer has live authority")
        allocation: ResourceAllocation = self.scheduler.get_allocation(
            access,
            self.dispatch.allocation.allocation_ref,
        )
        if (
            allocation != self.dispatch.allocation
            or allocation.status != "DISPATCHED"
            or allocation.run_ref != attempt.run_ref
            or allocation.run_attempt_id != attempt.run_attempt_id
            or allocation.run_attempt_fence != attempt.run_fence
            or allocation.node_ref != attempt.node_ref
            or allocation.node_attempt_id != attempt.attempt_id
            or allocation.node_attempt_fence != attempt.fence
            or allocation.owner_ref != attempt.owner_ref
            or allocation.lease_expires_at is None
            or _timestamp(allocation.lease_expires_at) <= database_now
            or allocation.side_effect_targets != (request.target_ref,)
        ):
            raise CloudflareKvAuthorityError(
                "ScheduledDispatch allocation is stale or not destination-exclusive"
            )
        return run_attempt

    def _package_source(self, request: PublishRequest) -> _PackageSource:
        if len(request.manifest.sources) != 1 or len(request.manifest.entries) != 1:
            raise CloudflareKvContractError(
                "Cloudflare KV publishing requires one exact assembled package source"
            )
        source = request.manifest.sources[0]
        entry = request.manifest.entries[0]
        artifact = self.artifacts.get_artifact(self.access, source.artifact_ref)
        if artifact.content_ref is None or not _content_equal(
            artifact.content_ref,
            source.content_ref,
        ):
            raise CloudflareKvIntegrityError(
                "package Artifact and ContentRef binding is not exact"
            )
        if (
            entry.content_sha256 != source.content_ref.digest
            or entry.size_bytes != source.content_ref.size_bytes
            or entry.media_type != source.content_ref.media_type
        ):
            raise CloudflareKvIntegrityError("package entry does not describe exact bytes")
        if not self.object_store.verify(source.content_ref):
            raise CloudflareKvIntegrityError("package bytes failed local verification")
        return _PackageSource(artifact, source.content_ref)

    def _resolve_token(self, auth_ref: str) -> str:
        try:
            token = self.secret_resolver(auth_ref)
        except Exception as exc:
            raise CloudflareKvAuthorityError(
                "Cloudflare credential reference could not be resolved"
            ) from exc
        if (
            not isinstance(token, str)
            or not token
            or len(token) > 16_384
            or "\r" in token
            or "\n" in token
        ):
            raise CloudflareKvAuthorityError("resolved Cloudflare credential is invalid")
        return token

    @staticmethod
    def _safe_response(response: CloudflareKvTransportResponse) -> dict[str, object]:
        content_length: int | None = None
        raw_length = response.headers.get("content-length")
        if raw_length is not None and raw_length.isdigit():
            content_length = int(raw_length)
        return {
            "content_length": content_length,
            "etag_present": "etag" in response.headers,
            "status_code": response.status_code,
        }

    def _preflight(
        self,
        key: str,
        *,
        expected_sha256: str,
        expected_size: int,
        overwrite: bool,
        token: str,
        events: list[dict[str, object]],
    ) -> bool:
        try:
            response = self.transport.get(
                self.account_id,
                self.namespace_id,
                key,
                token,
            )
        except Exception as exc:
            raise _KnownFailure("PREFLIGHT_TRANSPORT_FAILED") from exc
        events.append(
            {
                "key": key,
                "response": self._safe_response(response),
                "stage": "PREFLIGHT",
            }
        )
        if response.status_code == 404:
            return True
        if response.status_code != 200:
            raise _KnownFailure("PREFLIGHT_REJECTED")
        observed_sha256 = hashlib.sha256(response.body).hexdigest()
        same = (
            len(response.body) == expected_size
            and hmac.compare_digest(observed_sha256, expected_sha256)
        )
        if same:
            events.append({"key": key, "stage": "IDEMPOTENT_PRESENT"})
            return False
        if not overwrite:
            raise _KnownFailure("TARGET_CONTENT_CONFLICT")
        events.append({"key": key, "stage": "REPLACE_AUTHORIZED"})
        return True

    def _put_stream(
        self,
        key: str,
        body: BinaryIO,
        *,
        content_ref: ContentRef,
        token: str,
        events: list[dict[str, object]],
    ) -> None:
        try:
            response = self.transport.put(
                self.account_id,
                self.namespace_id,
                key,
                body,
                content_length=content_ref.size_bytes,
                content_sha256=content_ref.digest,
                content_type=content_ref.media_type,
                token=token,
            )
        except Exception as exc:
            raise _OutcomeUnknown() from exc
        events.append(
            {
                "key": key,
                "response": self._safe_response(response),
                "stage": "UPLOADED",
            }
        )
        if not 200 <= response.status_code <= 299:
            raise _OutcomeUnknown()

    def _put_bytes(
        self,
        key: str,
        payload: bytes,
        *,
        token: str,
        events: list[dict[str, object]],
    ) -> None:
        from io import BytesIO

        content_ref = ContentRef.from_bytes(payload, media_type=_MANIFEST_MEDIA_TYPE)
        with BytesIO(payload) as reader:
            self._put_stream(
                key,
                reader,
                content_ref=content_ref,
                token=token,
                events=events,
            )

    def _verify_remote(
        self,
        key: str,
        *,
        expected_sha256: str,
        expected_size: int,
        token: str,
        events: list[dict[str, object]],
    ) -> str:
        try:
            response = self.transport.get(
                self.account_id,
                self.namespace_id,
                key,
                token,
            )
        except Exception as exc:
            raise _KnownFailure("VERIFICATION_TRANSPORT_FAILED") from exc
        observed_sha256 = hashlib.sha256(response.body).hexdigest()
        events.append(
            {
                "bytes_read": len(response.body),
                "key": key,
                "observed_sha256": observed_sha256,
                "response": self._safe_response(response),
                "stage": "READBACK",
            }
        )
        if (
            response.status_code != 200
            or len(response.body) != expected_size
            or not hmac.compare_digest(observed_sha256, expected_sha256)
        ):
            raise _KnownFailure("READBACK_DIGEST_MISMATCH")
        return observed_sha256

    def _remote_identity(self, package_key: str) -> str:
        return (
            f"cloudflare-kv://accounts/{self.account_id}"
            f"/namespaces/{self.namespace_id}/values/{package_key}"
        )

    def _manifest_bytes(
        self,
        request: PublishRequest,
        source: _PackageSource,
        package_key: str,
    ) -> bytes:
        return _canonical_json(
            {
                "adapter_ref": self.adapter_ref,
                "destination": request.destination.payload(),
                "package": {
                    "artifact_ref": source.artifact.artifact_ref.value,
                    "content_ref": source.content_ref.value,
                    "content_sha256": source.content_ref.digest,
                    "key": package_key,
                    "size_bytes": source.content_ref.size_bytes,
                },
                "package_manifest_digest": request.manifest.manifest_digest,
                "project_ref": self.project_ref.value,
                "release_ref": request.release_ref,
                "request_digest": request.request_digest,
                "schema_ref": "schema://biella/cloudflare-kv-package-manifest/1",
                "source_bindings": [
                    item.payload() for item in request.manifest.sources
                ],
                "target_ref": request.target_ref,
            }
        )

    def _finish(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: PublishRequest,
        source: _PackageSource,
        *,
        state: str,
        category: str | None,
        uploaded: bool,
        package_key: str,
        manifest_key: str,
        events: list[dict[str, object]],
    ) -> PublishReceipt:
        run_attempt = self._revalidate(access, attempt, request)
        recorded_at = _now()
        evidence_payload = {
            "account_id": self.account_id,
            "adapter_ref": self.adapter_ref,
            "category": category,
            "destination": request.destination.payload(),
            "events": events,
            "manifest_key": manifest_key,
            "namespace_id": self.namespace_id,
            "package_key": package_key,
            "package_manifest_digest": request.manifest.manifest_digest,
            "project_ref": self.project_ref.value,
            "recorded_at": recorded_at,
            "release_ref": request.release_ref,
            "remote_identity": self._remote_identity(package_key),
            "request_digest": request.request_digest,
            "schema_ref": "schema://biella/cloudflare-kv-publish-evidence/1",
            "source_bindings": [item.payload() for item in request.manifest.sources],
            "state": state,
            "target_ref": request.target_ref,
            "uploaded": uploaded,
        }
        evidence_ref = self.object_store.put(
            _canonical_json(evidence_payload),
            media_type=_EVIDENCE_MEDIA_TYPE,
        )
        evidence = self.artifacts.publish_from_run(
            access,
            producer_attempt=run_attempt,
            expected_task_ref=attempt.task_ref,
            expected_task_digest=attempt.task_digest,
            role="delivery.validation-evidence",
            content_ref=evidence_ref,
            source_refs=(),
            source_artifact_refs=(source.artifact.artifact_ref,),
            source_content_refs=(source.content_ref,),
            derivation_type="cloudflare-kv.publish",
            metadata={
                "media_type": evidence_ref.media_type,
                "schema_ref": "schema://biella/cloudflare-kv-publish-evidence/1",
                "schema_version": "1.0.0",
                "semantic_label": f"cloudflare-kv-{state.lower()}",
            },
        )
        remote_identity: str | None = None
        remote_version: str | None = None
        upload_sha256: str | None = None
        verification_evidence_ref: str | None = None
        failure_ref: str | None = None
        if state == "VERIFIED":
            remote_identity = self._remote_identity(package_key)
            manifest_digest = manifest_key.rsplit("/", 1)[-1]
            remote_version = f"sha256:{source.content_ref.digest}:manifest:{manifest_digest}"
            upload_sha256 = source.content_ref.digest
            verification_evidence_ref = evidence.artifact_ref.value
        elif state == "FAILED":
            failure_ref = evidence.artifact_ref.value
        receipt = PublishReceipt.create(
            request,
            state=state,
            remote_identity=remote_identity,
            remote_version=remote_version,
            upload_sha256=upload_sha256,
            verification_evidence_ref=verification_evidence_ref,
            recorded_at=recorded_at,
            failure_ref=failure_ref,
        )
        self._store_result(attempt, request, receipt, evidence)
        return receipt

    def publish(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: PublishRequest,
    ) -> PublishReceipt:
        if not isinstance(request, PublishRequest):
            raise TypeError("request must be PublishRequest")
        self._revalidate(access, attempt, request)
        source = self._package_source(request)
        replay = self._claim_or_replay(attempt, request)
        if replay is not None:
            return replay
        token = self._resolve_token(request.destination.auth_secret_ref)
        package_key = self.package_key(source.content_ref)
        manifest_bytes = self._manifest_bytes(request, source, package_key)
        manifest_ref = ContentRef.from_bytes(
            manifest_bytes,
            media_type=_MANIFEST_MEDIA_TYPE,
        )
        manifest_key = self.manifest_key(manifest_bytes)
        events: list[dict[str, object]] = []
        uploaded = False
        try:
            package_put = self._preflight(
                package_key,
                expected_sha256=source.content_ref.digest,
                expected_size=source.content_ref.size_bytes,
                overwrite=request.overwrite,
                token=token,
                events=events,
            )
            manifest_put = self._preflight(
                manifest_key,
                expected_sha256=manifest_ref.digest,
                expected_size=manifest_ref.size_bytes,
                overwrite=request.overwrite,
                token=token,
                events=events,
            )
            if package_put:
                self._revalidate(access, attempt, request)
                with self.object_store.open(source.content_ref) as package_reader:
                    self._put_stream(
                        package_key,
                        package_reader,
                        content_ref=source.content_ref,
                        token=token,
                        events=events,
                    )
                uploaded = True
            if manifest_put:
                self._revalidate(access, attempt, request)
                self._put_bytes(
                    manifest_key,
                    manifest_bytes,
                    token=token,
                    events=events,
                )
                uploaded = True
            self._revalidate(access, attempt, request)
            self._verify_remote(
                package_key,
                expected_sha256=source.content_ref.digest,
                expected_size=source.content_ref.size_bytes,
                token=token,
                events=events,
            )
            self._verify_remote(
                manifest_key,
                expected_sha256=manifest_ref.digest,
                expected_size=manifest_ref.size_bytes,
                token=token,
                events=events,
            )
            events.append({"stage": "VERIFIED"})
            return self._finish(
                access,
                attempt,
                request,
                source,
                state="VERIFIED",
                category=None,
                uploaded=uploaded,
                package_key=package_key,
                manifest_key=manifest_key,
                events=events,
            )
        except _KnownFailure as exc:
            return self._finish(
                access,
                attempt,
                request,
                source,
                state="FAILED",
                category=exc.category,
                uploaded=uploaded,
                package_key=package_key,
                manifest_key=manifest_key,
                events=events,
            )
        except _OutcomeUnknown:
            return self._finish(
                access,
                attempt,
                request,
                source,
                state="OUTCOME_UNKNOWN",
                category="MUTATION_OUTCOME_UNKNOWN",
                uploaded=uploaded,
                package_key=package_key,
                manifest_key=manifest_key,
                events=events,
            )
        except CloudflareKvAuthorityError:
            if not uploaded:
                raise
            return self._finish(
                access,
                attempt,
                request,
                source,
                state="OUTCOME_UNKNOWN",
                category="AUTHORITY_CHANGED_AFTER_MUTATION",
                uploaded=True,
                package_key=package_key,
                manifest_key=manifest_key,
                events=events,
            )


CloudflareKVPublishAdapter = CloudflareKvPublishAdapter
