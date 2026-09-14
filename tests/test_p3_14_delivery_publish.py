from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import BinaryIO, cast

import pytest

from minitz_os.engine.artifact import Artifact, ArtifactService, ContentRef
from minitz_os.engine.capability import Capability, CapabilityRef, CapabilityRegistry
from minitz_os.engine.cloudflare_kv_publish import (
    CloudflareKvAuthorityError,
    CloudflareKvHttpTransport,
    CloudflareKvPublishAdapter,
    CloudflareKvTransportResponse,
)
from minitz_os.engine.delivery_pack import (
    DeliveryArtifactContentRef,
    PackageEntry,
    PackageManifest,
    PublishDestination,
    PublishRequest,
)
from minitz_os.engine.execution import NodeExecutionService
from minitz_os.engine.graph import GraphRef, GraphService, Node, NodeInputBinding, NodeRef
from minitz_os.engine.object_store import FilesystemObjectStorageBackend
from minitz_os.engine.project import ProjectAccess, ProjectRef, ProjectStore
from minitz_os.engine.resource import (
    FakeResourceObserver,
    QuantitySource,
    Resource,
    ResourceFitRequest,
    ResourceHealth,
    ResourceObservation,
    ResourceQuantity,
    ResourceRef,
    ResourceService,
)
from minitz_os.engine.run import RunRef, RunService
from minitz_os.engine.scheduler import (
    ResourceClaim,
    ScheduledDispatch,
    Scheduler,
    SchedulingRequest,
)
from minitz_os.engine.task import Task, TaskRevisionService


_TOKEN = "cloudflare-test-token-never-persist"
_AUTH_REF = "secret://delivery/cloudflare-api-token"
_ACCOUNT = "a" * 32
_NAMESPACE = "b" * 32


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class FakeKvTransport:
    def __init__(
        self,
        *,
        corrupt_package_readback: bool = False,
        raise_after_put: bool = False,
    ) -> None:
        self.values: dict[str, bytes] = {}
        self.get_calls: list[str] = []
        self.put_calls: list[str] = []
        self.tokens: list[str] = []
        self.corrupt_package_readback = corrupt_package_readback
        self.raise_after_put = raise_after_put

    def get(
        self,
        account_id: str,
        namespace_id: str,
        key: str,
        token: str,
    ) -> CloudflareKvTransportResponse:
        assert account_id == _ACCOUNT
        assert namespace_id == _NAMESPACE
        self.get_calls.append(key)
        self.tokens.append(token)
        if key not in self.values:
            return CloudflareKvTransportResponse(404, b"", {"authorization": token})
        value = self.values[key]
        if (
            self.corrupt_package_readback
            and key.startswith("minitz/packages/")
            and key in self.put_calls
        ):
            value = value + b"-corrupt"
        return CloudflareKvTransportResponse(
            200,
            value,
            {
                "authorization": token,
                "content-length": str(len(value)),
                "etag": "provider-etag-is-not-a-sha256",
            },
        )

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
        assert account_id == _ACCOUNT
        assert namespace_id == _NAMESPACE
        assert content_type
        payload = body.read()
        assert len(payload) == content_length
        assert hashlib.sha256(payload).hexdigest() == content_sha256
        self.put_calls.append(key)
        self.tokens.append(token)
        self.values[key] = payload
        if self.raise_after_put:
            raise RuntimeError(f"cancelled after mutation with {token}")
        return CloudflareKvTransportResponse(
            200,
            b'{"success":true}',
            {"authorization": token, "etag": "not-content-sha256"},
        )


@dataclass(frozen=True)
class PublishEnvironment:
    database: Path
    objects: FilesystemObjectStorageBackend
    access: ProjectAccess
    project_ref: ProjectRef
    task: Task
    run_ref: RunRef
    node: Node
    dispatch: ScheduledDispatch
    scheduler: Scheduler
    package_artifact: Artifact
    package_ref: ContentRef
    package_bytes: bytes
    request: PublishRequest


def _quantity(value: float, source: QuantitySource) -> ResourceQuantity:
    return ResourceQuantity(value, "count", source, "resource-source://test/slots")


def _environment(
    root: Path,
    *,
    name: str,
    package_bytes: bytes = b"exact delivery package\n",
    task_authority: str = "EXTERNAL_SIDE_EFFECT",
    node_authority: str = "EXTERNAL_SIDE_EFFECT",
    overwrite: bool = False,
    account_id: str = _ACCOUNT,
    namespace_id: str = _NAMESPACE,
) -> PublishEnvironment:
    root.mkdir(parents=True, exist_ok=True)
    database = root / "kernel.db"
    objects = FilesystemObjectStorageBackend(root / "objects")
    registration = ProjectStore(database).create_project(
        namespace=f"delivery-{name}",
        display_name=f"Delivery {name}",
    )
    access = registration.access
    project_ref = registration.project.project_ref
    artifacts = ArtifactService(database)
    package_ref = objects.put(
        package_bytes,
        media_type="application/octet-stream",
    )
    package_artifact = artifacts.create_artifact(
        access,
        project_ref=project_ref,
        role="delivery.package",
        content_ref=package_ref,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(package_ref,),
        derivation_type="delivery.test-package",
        metadata={
            "media_type": package_ref.media_type,
            "schema_ref": "schema://minitz/delivery-test-package/1",
        },
    )
    task_input = artifacts.create_task_input_ref(
        access,
        project_ref=project_ref,
        identity=package_artifact.artifact_ref,
    )
    capability_ref = CapabilityRef("publish.upload", "1.0.0")
    CapabilityRegistry(database).register(
        Capability(
            capability_ref,
            "Upload an exact delivery package",
            output_contract={"receipt": "schema://minitz/delivery-receipt/1"},
        )
    )
    task = TaskRevisionService(database).create_task(
        access,
        project_ref=project_ref,
        idempotency_key=f"task-{name}",
        task_type="delivery.publish",
        objective="Publish one exact package through the provider adapter",
        required_capabilities=(capability_ref,),
        input_refs=(task_input,),
        output_contract={"receipt": "schema://minitz/delivery-receipt/1"},
        constraints={},
        side_effect_authority=task_authority,
        data_policy_ref="policy://delivery/project-data",
        egress_policy_ref="policy://delivery/cloudflare-egress",
        evidence_requirements=("remote-readback-sha256",),
        acceptance_criteria=("exact remote bytes",),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="worker://delivery/run-owner",
        lease_seconds=600,
    )
    graph_ref = GraphRef.new(project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "adapter.cloudflare-kv-publish",
        (capability_ref,),
        (),
        (
            NodeInputBinding(
                project_ref,
                "package",
                "task",
                task_input.source_ref,
                task_input.content_sha256,
            ),
        ),
        {"receipt": "schema://minitz/delivery-receipt/1"},
        None,
        node_authority,
        {},
        ("remote-readback-sha256",),
    )
    GraphService(database).create_graph(
        access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(node,),
        compiler_identity="compiler://delivery/test",
        compiler_version="1.0.0",
        authority_attempt=run_attempt,
    )
    NodeExecutionService(database).prepare_run(access, run.run_ref)
    resource_ref = ResourceRef(
        project_ref,
        "res_" + hashlib.sha256(name.encode()).hexdigest()[:32],
    )
    resources = ResourceService(database)
    resources.register_resource(
        access,
        Resource(
            resource_ref,
            "runtime.host",
            "locality://delivery/test-host",
            configured_capacity={"slots": _quantity(1.0, QuantitySource.CONFIGURED)},
        ),
    )
    resources.observe_resource(
        access,
        resource_ref,
        FakeResourceObserver(
            (
                ResourceObservation(
                    observed_at=_now(),
                    fresh_for_seconds=600,
                    health=ResourceHealth.HEALTHY,
                    physical_capacity={"slots": _quantity(1.0, QuantitySource.MEASURED)},
                    effective_capacity={"slots": _quantity(1.0, QuantitySource.MEASURED)},
                    used_capacity={"slots": _quantity(0.0, QuantitySource.MEASURED)},
                    available_capacity={"slots": _quantity(1.0, QuantitySource.MEASURED)},
                    pressure={"slots": _quantity(0.0, QuantitySource.MEASURED)},
                ),
            )
        ),
    )
    target_ref = "destination://cloudflare-kv/" + hashlib.sha256(name.encode()).hexdigest()
    manifest = PackageManifest.create(
        project_ref,
        f"package-{name}",
        task.task_ref,
        run.run_ref,
        graph_ref,
        "opaque-package",
        target_ref,
        (DeliveryArtifactContentRef(package_artifact.artifact_ref, package_ref),),
        (
            PackageEntry(
                "package.bin",
                package_ref.digest,
                package_ref.size_bytes,
                package_ref.media_type,
                "0644",
                "forbid",
            ),
        ),
        "source-version://delivery/test/1",
        "build-version://delivery/test/1",
        {"assembler": "test-exact-bytes"},
        hashlib.sha256(b"config").hexdigest(),
        None,
        _now(),
    )
    endpoint_ref = (
        f"cloudflare-kv://accounts/{account_id}/namespaces/{namespace_id}"
    )
    destination = PublishDestination(
        project_ref,
        False,
        CloudflareKvPublishAdapter.adapter_ref,
        "cloudflare-kv",
        endpoint_ref,
        _AUTH_REF,
        (target_ref,),
        "policy://delivery/project-data",
    )
    request = PublishRequest.create(
        manifest,
        destination,
        target_ref,
        "release://delivery/test/1",
        "upload",
        overwrite,
        "verification://sha256/full-readback",
        task.task_ref,
        run.run_ref,
        node.node_ref,
        f"publish-{name}",
    )
    scheduler = Scheduler(database)
    allocation = scheduler.reserve(
        access,
        SchedulingRequest(
            node.node_ref,
            (
                ResourceClaim(
                    resource_ref,
                    ResourceFitRequest(required_available={"slots": 1.0}),
                    requested_capacity={"slots": 1.0},
                ),
            ),
            side_effect_targets=(target_ref,),
        ),
        authority_attempt=run_attempt,
        owner_ref="worker://delivery/node-owner",
        lease_seconds=600,
        idempotency_key=f"reserve-{name}",
    )
    dispatch = scheduler.dispatch(
        access,
        allocation,
        authority_attempt=run_attempt,
        lease_seconds=600,
        idempotency_key=f"dispatch-{name}",
    )
    return PublishEnvironment(
        database,
        objects,
        access,
        project_ref,
        task,
        run.run_ref,
        node,
        dispatch,
        scheduler,
        package_artifact,
        package_ref,
        package_bytes,
        request,
    )


def _resolver(values: Mapping[str, str]) -> Callable[[str], str]:
    def resolve(secret_ref: str) -> str:
        return values[secret_ref]

    return resolve


def _adapter(
    env: PublishEnvironment,
    transport: FakeKvTransport | CloudflareKvHttpTransport,
    *,
    token: str = _TOKEN,
    account_id: str = _ACCOUNT,
    namespace_id: str = _NAMESPACE,
) -> CloudflareKvPublishAdapter:
    return CloudflareKvPublishAdapter(
        env.database,
        env.objects,
        access=env.access,
        dispatch=env.dispatch,
        account_id=account_id,
        namespace_id=namespace_id,
        secret_resolver=_resolver({_AUTH_REF: token}),
        transport=transport,
    )


def _evidence(
    env: PublishEnvironment,
    adapter: CloudflareKvPublishAdapter,
) -> dict[str, object]:
    artifact_ref = adapter.get_evidence_artifact_ref(env.request.request_digest)
    artifact = ArtifactService(env.database).get_artifact(env.access, artifact_ref)
    assert artifact.content_ref is not None
    parsed = cast(object, json.loads(env.objects.read(artifact.content_ref)))
    assert isinstance(parsed, dict)
    return cast(dict[str, object], parsed)


def test_success_full_readback_and_durable_idempotent_replay(tmp_path: Path) -> None:
    env = _environment(tmp_path / "success", name="success")
    transport = FakeKvTransport()
    adapter = _adapter(env, transport)

    receipt = adapter.publish(env.access, env.dispatch.node_attempt, env.request)

    assert receipt.state == "VERIFIED"
    assert receipt.upload_sha256 == env.package_ref.digest
    assert receipt.verification_evidence_ref is not None
    package_key = adapter.package_key(env.package_ref)
    assert transport.values[package_key] == env.package_bytes
    assert len([key for key in transport.values if key.startswith("minitz/manifests/")]) == 1
    assert env.objects.read(env.package_ref) == env.package_bytes
    puts = tuple(transport.put_calls)
    gets = tuple(transport.get_calls)

    replay = adapter.publish(env.access, env.dispatch.node_attempt, env.request)

    assert replay == receipt
    assert tuple(transport.put_calls) == puts
    assert tuple(transport.get_calls) == gets
    evidence = _evidence(env, adapter)
    assert evidence["state"] == "VERIFIED"
    assert evidence["uploaded"] is True


def test_readback_mismatch_is_failed_after_upload_and_retains_source(tmp_path: Path) -> None:
    env = _environment(tmp_path / "verify-fail", name="verify-fail")
    transport = FakeKvTransport(corrupt_package_readback=True)
    adapter = _adapter(env, transport)

    receipt = adapter.publish(env.access, env.dispatch.node_attempt, env.request)

    assert receipt.state == "FAILED"
    assert receipt.failure_ref is not None
    assert receipt.verification_evidence_ref is None
    assert receipt.upload_sha256 is None
    assert env.objects.read(env.package_ref) == env.package_bytes
    evidence = _evidence(env, adapter)
    assert evidence["state"] == "FAILED"
    assert evidence["category"] == "READBACK_DIGEST_MISMATCH"
    assert evidence["uploaded"] is True
    assert not any(
        isinstance(event, dict) and event.get("stage") == "VERIFIED"
        for event in cast(list[object], evidence["events"])
    )


def test_existing_conflicting_digest_target_fails_closed(tmp_path: Path) -> None:
    env = _environment(tmp_path / "conflict", name="conflict")
    transport = FakeKvTransport()
    adapter = _adapter(env, transport)
    transport.values[adapter.package_key(env.package_ref)] = b"wrong existing bytes"

    receipt = adapter.publish(env.access, env.dispatch.node_attempt, env.request)

    assert receipt.state == "FAILED"
    assert receipt.failure_ref is not None
    assert transport.put_calls == []
    assert _evidence(env, adapter)["category"] == "TARGET_CONTENT_CONFLICT"


def test_project_auth_and_side_effect_authority_are_isolated(tmp_path: Path) -> None:
    first = _environment(tmp_path / "first", name="first")
    second = _environment(tmp_path / "second", name="second")
    first_transport = FakeKvTransport()
    first_adapter = _adapter(first, first_transport)

    with pytest.raises(CloudflareKvAuthorityError):
        first_adapter.publish(second.access, second.dispatch.node_attempt, second.request)
    assert first_transport.get_calls == []

    missing_auth_adapter = CloudflareKvPublishAdapter(
        first.database,
        first.objects,
        access=first.access,
        dispatch=first.dispatch,
        account_id=_ACCOUNT,
        namespace_id=_NAMESPACE,
        secret_resolver=_resolver({"secret://delivery/another-project": _TOKEN}),
        transport=first_transport,
    )
    with pytest.raises(CloudflareKvAuthorityError):
        missing_auth_adapter.publish(
            first.access,
            first.dispatch.node_attempt,
            first.request,
        )
    assert first_transport.get_calls == []

    weak_task = _environment(
        tmp_path / "weak-task",
        name="weak-task",
        task_authority="READ_ONLY",
        node_authority="READ_ONLY",
    )
    with pytest.raises(CloudflareKvAuthorityError):
        _adapter(weak_task, FakeKvTransport()).publish(
            weak_task.access,
            weak_task.dispatch.node_attempt,
            weak_task.request,
        )
    weak_node = _environment(
        tmp_path / "weak-node",
        name="weak-node",
        node_authority="PROJECT_WRITE",
    )
    with pytest.raises(CloudflareKvAuthorityError):
        _adapter(weak_node, FakeKvTransport()).publish(
            weak_node.access,
            weak_node.dispatch.node_attempt,
            weak_node.request,
        )


def test_stale_allocation_fence_is_rejected_before_transport(tmp_path: Path) -> None:
    env = _environment(tmp_path / "stale", name="stale")
    transport = FakeKvTransport()
    adapter = _adapter(env, transport)
    env.scheduler.heartbeat(env.access, env.dispatch.allocation, lease_seconds=600)

    with pytest.raises(CloudflareKvAuthorityError):
        adapter.publish(env.access, env.dispatch.node_attempt, env.request)

    assert transport.get_calls == []
    assert transport.put_calls == []


def test_cancel_after_mutation_is_unknown_and_secret_is_redacted(tmp_path: Path) -> None:
    env = _environment(tmp_path / "cancel", name="cancel")
    transport = FakeKvTransport(raise_after_put=True)
    adapter = _adapter(env, transport)

    receipt = adapter.publish(env.access, env.dispatch.node_attempt, env.request)

    assert receipt.state == "OUTCOME_UNKNOWN"
    assert receipt.remote_identity is None
    assert receipt.upload_sha256 is None
    assert transport.values[adapter.package_key(env.package_ref)] == env.package_bytes
    assert env.objects.read(env.package_ref) == env.package_bytes
    evidence_bytes = json.dumps(_evidence(env, adapter), sort_keys=True).encode()
    assert _TOKEN.encode() not in evidence_bytes
    assert b"authorization" not in evidence_bytes.lower()


def test_live_cloudflare_kv_exact_put_get_without_delete(tmp_path: Path) -> None:
    if os.environ.get("MINITZ_RUN_LIVE_CLOUDFLARE_KV") != "1":
        pytest.skip("live Cloudflare KV gate is disabled")
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    namespace_id = os.environ.get("CLOUDFLARE_KV_NAMESPACE_ID")
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if account_id is None or namespace_id is None or token is None:
        pytest.fail("live Cloudflare KV gate requires all credential references")
    env = _environment(
        tmp_path / "live",
        name="live",
        package_bytes=b"minitz-cloudflare-kv-live-p3-14\n",
        account_id=account_id,
        namespace_id=namespace_id,
    )
    adapter = _adapter(
        env,
        CloudflareKvHttpTransport(timeout_seconds=120),
        token=token,
        account_id=account_id,
        namespace_id=namespace_id,
    )

    receipt = adapter.publish(env.access, env.dispatch.node_attempt, env.request)

    assert receipt.state == "VERIFIED"
    assert receipt.upload_sha256 == hashlib.sha256(env.package_bytes).hexdigest()
    assert adapter.package_key(env.package_ref).endswith(env.package_ref.digest)
    assert env.objects.read(env.package_ref) == env.package_bytes
