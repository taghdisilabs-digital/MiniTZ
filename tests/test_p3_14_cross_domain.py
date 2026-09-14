"""P3-14 REAL same-kernel software/video delivery and KV publication proof."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import cast
import zipfile

import pytest

from minitz_os.engine.artifact import Artifact, ArtifactScopeError, ArtifactService, ContentRef
from minitz_os.engine.capability import Capability, CapabilityRef, CapabilityRegistry
from minitz_os.engine.cloudflare_kv_publish import (
    CloudflareKvAuthorityError,
    CloudflareKvHttpTransport,
    CloudflareKvPublishAdapter,
)
from minitz_os.engine.delivery_pack import (
    DeliveryArtifactContentRef,
    DeliveryContractError,
    PackageEntry,
    PackageManifest,
    PublishDestination,
    PublishRequest,
)
from minitz_os.engine.delivery_tool import (
    DeliveryLocalError,
    DeterministicLocalDeliveryTool,
    LocalPackageConfig,
    LocalPackageRequest,
    LocalPackageResult,
    PACKAGE_MANIFEST_PATH,
    PackageInput,
    PackageVerificationEntry,
    verify_local_archive,
)
from minitz_os.engine.execution import NodeExecutionScopeError, NodeExecutionService
from minitz_os.engine.graph import GraphRef, GraphScopeError, GraphService, Node, NodeRef
from minitz_os.engine.object_store import FilesystemObjectStorageBackend
from minitz_os.engine.project import ProjectAccess, ProjectStore
from minitz_os.engine.project_memory import (
    ProjectKnowledge,
    ProjectKnowledgeRef,
    ProjectKnowledgeScopeError,
    ProjectKnowledgeService,
)
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
from minitz_os.engine.run import ExecutionAttempt, RunScopeError, RunService
from minitz_os.engine.scheduler import (
    ResourceClaim,
    ScheduledDispatch,
    Scheduler,
    SchedulerScopeError,
    SchedulingRequest,
)
from minitz_os.engine.task import Task, TaskRevisionService, TaskScopeError


_CREATED_AT = "2026-09-01T00:00:00+00:00"
_LOCAL_ACCOUNT_ID = "a" * 32
_LOCAL_NAMESPACE_ID = "b" * 32
_SOFTWARE_MAIN = b"""from __future__ import annotations

import json
import sys


request = json.load(sys.stdin)
values = request["values"]
response = {"count": len(values), "domain": "software", "total": sum(values)}
sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\\n")
"""
_SOFTWARE_RESPONSE = b'{"count":3,"domain":"software","total":8}\n'


@dataclass(frozen=True)
class _Domain:
    name: str
    database: Path
    objects: FilesystemObjectStorageBackend
    access: ProjectAccess
    task: Task
    run_attempt: ExecutionAttempt
    graph_ref: GraphRef
    node: Node
    dispatch: ScheduledDispatch
    target_ref: str
    auth_ref: str


@dataclass(frozen=True)
class _PublishBinding:
    manifest: PackageManifest
    destination: PublishDestination
    request: PublishRequest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _quantity(value: float, source: QuantitySource) -> ResourceQuantity:
    return ResourceQuantity(value, "count", source, "resource-source://p3-14/slots")


def _create_domain(
    database: Path,
    objects: FilesystemObjectStorageBackend,
    *,
    name: str,
    capability_ref: CapabilityRef,
) -> _Domain:
    registration = ProjectStore(database).create_project(
        namespace=f"p3-14-cross-domain-{name}",
        display_name=f"P3-14 Cross Domain {name.title()}",
    )
    access = registration.access
    project_ref = access.project_ref
    target_ref = (
        f"destination://cloudflare-kv/p3-14-cross-domain/{name}/"
        + hashlib.sha256(project_ref.value.encode()).hexdigest()
    )
    auth_ref = f"secret://p3-14-cross-domain/{name}/cloudflare-api-token"
    task = TaskRevisionService(database).create_task(
        access,
        project_ref=project_ref,
        idempotency_key=f"p3-14-cross-domain-{name}-task",
        task_type=f"{name}.delivery",
        objective=f"Build, package, and externally publish the exact {name} output",
        required_capabilities=(capability_ref,),
        input_refs=(),
        output_contract={"receipt": "schema://minitz/delivery-receipt/1"},
        constraints={"immutable_publish": True},
        side_effect_authority="EXTERNAL_SIDE_EFFECT",
        data_policy_ref=f"policy://p3-14-cross-domain/{name}/project-data",
        egress_policy_ref="policy://p3-14-cross-domain/cloudflare-kv-egress",
        evidence_requirements=("local-full-digest", "remote-full-readback-sha256"),
        acceptance_criteria=("exact package is retained and remotely verified",),
        resource_hints={"slots": 1},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref=f"worker://p3-14-cross-domain/{name}/run",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "generic.delivery.cloudflare-kv",
        (capability_ref,),
        (),
        (),
        {"receipt": "schema://minitz/delivery-receipt/1"},
        None,
        "EXTERNAL_SIDE_EFFECT",
        {},
        ("remote-full-readback-sha256",),
    )
    GraphService(database).create_graph(
        access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(node,),
        compiler_identity="compiler://p3-14/cross-domain/v1",
        compiler_version="1.0.0",
        authority_attempt=run_attempt,
    )
    NodeExecutionService(database).prepare_run(access, run.run_ref)
    resource_ref = ResourceRef(
        project_ref,
        "res_" + hashlib.sha256(f"{name}:{project_ref.value}".encode()).hexdigest()[:32],
    )
    resources = ResourceService(database)
    resources.register_resource(
        access,
        Resource(
            resource_ref,
            "runtime.host",
            f"locality://p3-14-cross-domain/{name}",
            configured_capacity={
                "slots": _quantity(1.0, QuantitySource.CONFIGURED)
            },
        ),
    )
    resources.observe_resource(
        access,
        resource_ref,
        FakeResourceObserver(
            (
                ResourceObservation(
                    observed_at=_now(),
                    fresh_for_seconds=1800,
                    health=ResourceHealth.HEALTHY,
                    physical_capacity={
                        "slots": _quantity(1.0, QuantitySource.MEASURED)
                    },
                    effective_capacity={
                        "slots": _quantity(1.0, QuantitySource.MEASURED)
                    },
                    used_capacity={
                        "slots": _quantity(0.0, QuantitySource.MEASURED)
                    },
                    available_capacity={
                        "slots": _quantity(1.0, QuantitySource.MEASURED)
                    },
                    pressure={"slots": _quantity(0.0, QuantitySource.MEASURED)},
                ),
            )
        ),
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
        owner_ref=f"worker://p3-14-cross-domain/{name}/node",
        lease_seconds=1800,
        idempotency_key=f"p3-14-cross-domain-{name}-reserve",
    )
    dispatch = scheduler.dispatch(
        access,
        allocation,
        authority_attempt=run_attempt,
        lease_seconds=1800,
        idempotency_key=f"p3-14-cross-domain-{name}-dispatch",
    )
    return _Domain(
        name,
        database,
        objects,
        access,
        task,
        run_attempt,
        graph_ref,
        node,
        dispatch,
        target_ref,
        auth_ref,
    )


def _zipapp_bytes() -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        entry = zipfile.ZipInfo("__main__.py", date_time=(1980, 1, 1, 0, 0, 0))
        entry.create_system = 3
        entry.compress_type = zipfile.ZIP_STORED
        entry.external_attr = (stat.S_IFREG | 0o644) << 16
        archive.writestr(entry, _SOFTWARE_MAIN)
    return output.getvalue()


def _run_zipapp(payload: bytes, path: Path) -> bytes:
    path.write_bytes(payload)
    completed = subprocess.run(
        (sys.executable, str(path)),
        input=b'{"values":[3,1,4]}\n',
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    assert completed.stderr == b""
    return completed.stdout


def _mp4_bytes() -> bytes:
    completed = subprocess.run(
        (
            "/usr/bin/ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=660:sample_rate=48000",
            "-t",
            "0.600000",
            "-map_metadata",
            "-1",
            "-codec:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-color_range",
            "tv",
            "-codec:a",
            "aac",
            "-ar",
            "48000",
            "-threads",
            "1",
            "-movflags",
            "+frag_keyframe+empty_moov+default_base_moof",
            "-f",
            "mp4",
            "pipe:1",
        ),
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    assert completed.stdout
    return completed.stdout


def _probe_and_decode_mp4(payload: bytes) -> dict[str, object]:
    probe = subprocess.run(
        (
            "/usr/bin/ffprobe",
            "-hide_banner",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            "pipe:0",
        ),
        input=payload,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert probe.returncode == 0, probe.stderr.decode("utf-8", errors="replace")
    parsed = cast(object, json.loads(probe.stdout))
    assert isinstance(parsed, dict)
    streams_value = parsed.get("streams")
    assert isinstance(streams_value, list)
    streams = tuple(
        cast(dict[str, object], item) for item in streams_value if isinstance(item, dict)
    )
    assert len(streams) == len(streams_value)
    video = next(item for item in streams if item.get("codec_type") == "video")
    assert video.get("codec_name") == "h264"
    assert video.get("width") == 160 and video.get("height") == 90
    assert any(item.get("codec_type") == "audio" for item in streams)
    decode = subprocess.run(
        (
            "/usr/bin/ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-v",
            "error",
            "-i",
            "pipe:0",
            "-map",
            "0",
            "-f",
            "null",
            "-",
        ),
        input=payload,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert decode.returncode == 0, decode.stderr.decode("utf-8", errors="replace")
    return cast(dict[str, object], parsed)


def _publish_output(
    domain: _Domain,
    payload: bytes,
    *,
    role: str,
    media_type: str,
) -> tuple[Artifact, DeliveryArtifactContentRef]:
    content = domain.objects.put(
        payload,
        media_type=media_type,
        expected_digest=hashlib.sha256(payload).hexdigest(),
        expected_size=len(payload),
    )
    artifact = ArtifactService(domain.database).publish_from_run(
        domain.access,
        producer_attempt=domain.run_attempt,
        expected_task_ref=domain.task.task_ref,
        expected_task_digest=domain.task.canonical_digest,
        role=role,
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type=f"{domain.name}.real-output",
        metadata={
            "media_type": media_type,
            "schema_ref": f"schema://minitz/{domain.name}-real-output/1",
        },
    )
    return artifact, DeliveryArtifactContentRef(artifact.artifact_ref, content)


def _remember_output(
    domain: _Domain,
    artifact: Artifact,
    *,
    statement: str,
) -> ProjectKnowledge:
    memories = ProjectKnowledgeService(domain.database)
    candidate = memories.record_candidate(
        domain.access,
        project_ref=domain.access.project_ref,
        idempotency_key=f"p3-14-{domain.name}-output-candidate",
        origin_type="task.evidence",
        knowledge_type="project.delivery-output",
        statement=statement,
        content_ref=None,
        applicability={"domain": domain.name, "task": "p3-14-cross-domain"},
        source_refs=(artifact.artifact_ref,),
        evidence_refs=(),
    )
    return memories.place_candidate(
        domain.access,
        candidate.candidate_ref,
        knowledge_ref=ProjectKnowledgeRef.new(domain.access.project_ref),
        accepted_by=f"owner://p3-14-cross-domain/{domain.name}",
        idempotency_key=f"p3-14-{domain.name}-output-placement",
    )


def _delivery_tool(domain: _Domain) -> DeterministicLocalDeliveryTool:
    return DeterministicLocalDeliveryTool(
        domain.database,
        domain.objects,
        access=domain.access,
        dispatch=domain.dispatch,
    )


def _package_request(
    domain: _Domain,
    source: DeliveryArtifactContentRef,
    *,
    entry_path: str,
    permission: str,
) -> LocalPackageRequest:
    return LocalPackageRequest(
        project_ref=domain.access.project_ref,
        package_id=f"p3-14-{domain.name}-package",
        package_type="bundle",
        target_ref=domain.target_ref,
        inputs=(PackageInput(source, entry_path, permission),),
        source_version_ref=f"source-version://p3-14/{domain.name}/1",
        build_version_ref=f"build-version://sha256/{source.content_ref.digest}",
        toolchains={"delivery": "toolchain://minitz/local-delivery/1"},
        created_at=_CREATED_AT,
        idempotency_key=f"p3-14-{domain.name}-assemble",
        config=LocalPackageConfig(domain.access.project_ref, "store", None),
    )


def _reopen_and_verify_package(
    domain: _Domain,
    result: LocalPackageResult,
    source: DeliveryArtifactContentRef,
    *,
    entry_path: str,
    permission: str,
) -> bytes:
    artifacts = ArtifactService(domain.database)
    reopened_manifest = artifacts.get_artifact(domain.access, result.manifest.artifact_ref)
    reopened_archive = artifacts.get_artifact(domain.access, result.archive.artifact_ref)
    assert reopened_manifest.role == "delivery.manifest"
    assert reopened_archive.role == "delivery.archive"
    assert reopened_manifest.content_ref == result.manifest.content_ref
    assert reopened_archive.content_ref == result.archive.content_ref
    manifest_bytes = domain.objects.read(result.manifest.content_ref)
    archive_bytes = domain.objects.read(result.archive.content_ref)
    assert hashlib.sha256(manifest_bytes).hexdigest() == result.manifest.content_ref.digest
    assert hashlib.sha256(archive_bytes).hexdigest() == result.archive.content_ref.digest
    verification = verify_local_archive(
        archive_bytes,
        manifest_payload=manifest_bytes,
        expected_entries=(
            PackageVerificationEntry(
                entry_path,
                source.content_ref.digest,
                source.content_ref.size_bytes,
                source.content_ref.media_type,
                permission,
            ),
        ),
        compression="store",
        compression_level=None,
    )
    assert verification.canonical_bytes_verified is True
    assert verification.archive_sha256 == result.archive.content_ref.digest
    with zipfile.ZipFile(BytesIO(archive_bytes), "r") as archive:
        assert archive.namelist() == [PACKAGE_MANIFEST_PATH, entry_path]
        return archive.read(entry_path)


def _publish_binding(
    domain: _Domain,
    package: LocalPackageResult,
    *,
    account_id: str,
    namespace_id: str,
    auth_ref: str | None = None,
    idempotency_suffix: str = "publish",
) -> _PublishBinding:
    archive = package.archive
    manifest = PackageManifest.create(
        domain.access.project_ref,
        f"p3-14-{domain.name}-remote-package-{idempotency_suffix}",
        domain.task.task_ref,
        domain.run_attempt.run_ref,
        domain.graph_ref,
        "delivery.zip",
        domain.target_ref,
        (archive,),
        (
            PackageEntry(
                f"{domain.name}-delivery.zip",
                archive.content_ref.digest,
                archive.content_ref.size_bytes,
                archive.content_ref.media_type,
                "0644",
                "forbid",
            ),
        ),
        f"source-version://sha256/{package.preserved.package_manifest.manifest_digest}",
        f"build-version://sha256/{archive.content_ref.digest}",
        {"delivery": "generic-local-delivery-1"},
        package.preserved.package_manifest.config_sha256,
        None,
        _CREATED_AT,
    )
    destination = PublishDestination(
        domain.access.project_ref,
        False,
        CloudflareKvPublishAdapter.adapter_ref,
        "cloudflare-kv",
        f"cloudflare-kv://accounts/{account_id}/namespaces/{namespace_id}",
        domain.auth_ref if auth_ref is None else auth_ref,
        (domain.target_ref,),
        cast(str, domain.task.data_policy_ref),
    )
    request = PublishRequest.create(
        manifest,
        destination,
        domain.target_ref,
        f"release://p3-14-cross-domain/{domain.name}/1",
        "upload",
        False,
        "verification://sha256/full-readback",
        domain.task.task_ref,
        domain.run_attempt.run_ref,
        domain.node.node_ref,
        f"p3-14-{domain.name}-{idempotency_suffix}",
    )
    return _PublishBinding(manifest, destination, request)


def _secret_resolver(authorized_ref: str, token: str) -> Callable[[str], str]:
    def resolve(secret_ref: str) -> str:
        if secret_ref != authorized_ref:
            raise KeyError("secret reference is outside this Project authority")
        return token

    return resolve


def _adapter(
    domain: _Domain,
    *,
    account_id: str,
    namespace_id: str,
    token: str,
    timeout_seconds: float,
) -> CloudflareKvPublishAdapter:
    return CloudflareKvPublishAdapter(
        domain.database,
        domain.objects,
        access=domain.access,
        dispatch=domain.dispatch,
        account_id=account_id,
        namespace_id=namespace_id,
        secret_resolver=_secret_resolver(domain.auth_ref, token),
        transport=CloudflareKvHttpTransport(timeout_seconds=timeout_seconds),
    )


def _publish_evidence(
    domain: _Domain,
    adapter: CloudflareKvPublishAdapter,
    request: PublishRequest,
) -> dict[str, object]:
    evidence_ref = adapter.get_evidence_artifact_ref(request.request_digest)
    evidence = ArtifactService(domain.database).get_artifact(domain.access, evidence_ref)
    assert evidence.role == "delivery.validation-evidence"
    assert evidence.content_ref is not None
    parsed = cast(object, json.loads(domain.objects.read(evidence.content_ref)))
    assert isinstance(parsed, dict)
    return cast(dict[str, object], parsed)


def _assert_real_put_and_readback(
    evidence: dict[str, object],
    *,
    package_key: str,
    package_digest: str,
) -> None:
    assert evidence.get("state") == "VERIFIED"
    assert evidence.get("uploaded") is True
    assert evidence.get("package_key") == package_key
    events_value = evidence.get("events")
    assert isinstance(events_value, list)
    events = tuple(
        cast(dict[str, object], item) for item in events_value if isinstance(item, dict)
    )
    assert len(events) == len(events_value)
    assert any(
        item.get("stage") == "UPLOADED" and item.get("key") == package_key
        for item in events
    )
    assert any(
        item.get("stage") == "READBACK"
        and item.get("key") == package_key
        and item.get("observed_sha256") == package_digest
        for item in events
    )


def test_real_same_kernel_cross_domain_delivery_and_cloudflare_kv(
    tmp_path: Path,
) -> None:
    database = tmp_path / "same-kernel.sqlite3"
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    capability_ref = CapabilityRef("publish.upload", "1.0.0")
    CapabilityRegistry(database).register(
        Capability(
            capability_ref,
            "Upload one exact assembled package",
            output_contract={"receipt": "schema://minitz/delivery-receipt/1"},
        )
    )
    software = _create_domain(
        database, objects, name="software", capability_ref=capability_ref
    )
    video = _create_domain(database, objects, name="video", capability_ref=capability_ref)

    assert software.database == video.database == database
    assert software.objects is video.objects is objects
    assert software.access != video.access
    assert software.task.task_ref != video.task.task_ref
    assert software.run_attempt.run_ref != video.run_attempt.run_ref
    assert software.graph_ref != video.graph_ref
    assert software.node.node_ref != video.node.node_ref
    assert software.dispatch.allocation.allocation_ref != video.dispatch.allocation.allocation_ref
    assert software.dispatch.node_attempt != video.dispatch.node_attempt

    zipapp = _zipapp_bytes()
    assert zipapp == _zipapp_bytes()
    assert _run_zipapp(zipapp, tmp_path / "software-backend.pyz") == _SOFTWARE_RESPONSE
    software_artifact, software_source = _publish_output(
        software,
        zipapp,
        role="software.build.output",
        media_type="application/vnd.python.pyz",
    )
    assert software_artifact.role == "software.build.output"
    assert software_artifact.content_ref == software_source.content_ref
    assert software_artifact.producer_attempt_id == software.run_attempt.attempt_id
    assert software.objects.read(software_source.content_ref) == zipapp

    mp4 = _mp4_bytes()
    initial_probe = _probe_and_decode_mp4(mp4)
    assert isinstance(initial_probe.get("format"), dict)
    video_artifact, video_source = _publish_output(
        video,
        mp4,
        role="video.export",
        media_type="video/mp4",
    )
    assert video_artifact.role == "video.export"
    assert video_artifact.content_ref == video_source.content_ref
    assert video_artifact.producer_attempt_id == video.run_attempt.attempt_id
    assert video.objects.read(video_source.content_ref) == mp4
    assert software_source.project_ref != video_source.project_ref

    memories = ProjectKnowledgeService(database)
    software_knowledge = _remember_output(
        software,
        software_artifact,
        statement="The accepted runnable output is the exact deterministic Python zipapp.",
    )
    video_knowledge = _remember_output(
        video,
        video_artifact,
        statement="The accepted video export is the exact fully decoded MP4.",
    )
    assert memories.get_knowledge(software.access, software_knowledge.knowledge_ref) == software_knowledge
    assert memories.get_knowledge(video.access, video_knowledge.knowledge_ref) == video_knowledge
    with pytest.raises(ProjectKnowledgeScopeError):
        memories.get_knowledge(video.access, software_knowledge.knowledge_ref)
    with pytest.raises(ProjectKnowledgeScopeError):
        memories.get_knowledge(software.access, video_knowledge.knowledge_ref)

    software_request = _package_request(
        software,
        software_source,
        entry_path="app/software-backend.pyz",
        permission="0755",
    )
    video_request = _package_request(
        video,
        video_source,
        entry_path="media/video-export.mp4",
        permission="0644",
    )
    software_tool = _delivery_tool(software)
    video_tool = _delivery_tool(video)
    assert type(software_tool) is type(video_tool) is DeterministicLocalDeliveryTool
    software_package = software_tool.assemble(
        software.access, software.dispatch.node_attempt, software_request
    )
    video_package = video_tool.assemble(
        video.access, video.dispatch.node_attempt, video_request
    )
    reopened_zipapp = _reopen_and_verify_package(
        software,
        software_package,
        software_source,
        entry_path="app/software-backend.pyz",
        permission="0755",
    )
    reopened_mp4 = _reopen_and_verify_package(
        video,
        video_package,
        video_source,
        entry_path="media/video-export.mp4",
        permission="0644",
    )
    assert _run_zipapp(reopened_zipapp, tmp_path / "reopened-software-backend.pyz") == _SOFTWARE_RESPONSE
    reopened_probe = _probe_and_decode_mp4(reopened_mp4)
    assert reopened_probe == initial_probe
    assert software_package.preserved.package_manifest.project_ref == software.access.project_ref
    assert video_package.preserved.package_manifest.project_ref == video.access.project_ref
    assert software_package.preserved.package_manifest.sources == (software_source,)
    assert video_package.preserved.package_manifest.sources == (video_source,)
    assert software_package.archive.content_ref.digest != video_package.archive.content_ref.digest

    with pytest.raises(ArtifactScopeError):
        ArtifactService(database).get_artifact(video.access, software_artifact.artifact_ref)
    with pytest.raises(TaskScopeError):
        TaskRevisionService(database).get_task(video.access, software.task.task_ref)
    with pytest.raises(RunScopeError):
        RunService(database).get_run(video.access, software.run_attempt.run_ref)
    with pytest.raises(GraphScopeError):
        GraphService(database).get_graph(video.access, software.graph_ref)
    with pytest.raises(NodeExecutionScopeError):
        NodeExecutionService(database).get_node_execution(video.access, software.node.node_ref)
    with pytest.raises(SchedulerScopeError):
        Scheduler(database).get_allocation(
            video.access, software.dispatch.allocation.allocation_ref
        )
    with pytest.raises(DeliveryLocalError, match="differs from bound Project"):
        software_tool.assemble(video.access, video.dispatch.node_attempt, video_request)
    with pytest.raises(DeliveryLocalError, match="crossed Project scope"):
        replace(
            software_request,
            inputs=(PackageInput(video_source, "media/cross-project.mp4"),),
        )

    live_enabled = os.environ.get("MINITZ_RUN_LIVE_CLOUDFLARE_KV") == "1"
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID") if live_enabled else _LOCAL_ACCOUNT_ID
    namespace_id = (
        os.environ.get("CLOUDFLARE_KV_NAMESPACE_ID")
        if live_enabled
        else _LOCAL_NAMESPACE_ID
    )
    token = os.environ.get("CLOUDFLARE_API_TOKEN") if live_enabled else "not-used"
    if account_id is None or namespace_id is None or token is None:
        pytest.fail("live Cloudflare KV gate requires the three canonical credential variables")
    software_publish = _publish_binding(
        software,
        software_package,
        account_id=account_id,
        namespace_id=namespace_id,
    )
    video_publish = _publish_binding(
        video,
        video_package,
        account_id=account_id,
        namespace_id=namespace_id,
    )
    assert software_publish.destination.project_ref == software.access.project_ref
    assert video_publish.destination.project_ref == video.access.project_ref
    assert software_publish.destination != video_publish.destination
    assert software_publish.request.overwrite is False
    assert video_publish.request.overwrite is False

    with pytest.raises(DeliveryContractError, match="crossed Project"):
        PublishRequest.create(
            software_publish.manifest,
            video_publish.destination,
            software.target_ref,
            "release://p3-14-cross-domain/software/cross-destination",
            "upload",
            False,
            "verification://sha256/full-readback",
            software.task.task_ref,
            software.run_attempt.run_ref,
            software.node.node_ref,
            "p3-14-software-cross-destination",
        )
    preflight_adapter = _adapter(
        software,
        account_id=account_id,
        namespace_id=namespace_id,
        token=token,
        timeout_seconds=0.1,
    )
    with pytest.raises(CloudflareKvAuthorityError, match="constructor authority"):
        preflight_adapter.publish(
            video.access, video.dispatch.node_attempt, video_publish.request
        )
    cross_auth = _publish_binding(
        software,
        software_package,
        account_id=account_id,
        namespace_id=namespace_id,
        auth_ref=video.auth_ref,
        idempotency_suffix="cross-auth",
    )
    with pytest.raises(CloudflareKvAuthorityError, match="credential reference"):
        preflight_adapter.publish(
            software.access, software.dispatch.node_attempt, cross_auth.request
        )

    if not live_enabled:
        return

    software_adapter = _adapter(
        software,
        account_id=account_id,
        namespace_id=namespace_id,
        token=token,
        timeout_seconds=120.0,
    )
    video_adapter = _adapter(
        video,
        account_id=account_id,
        namespace_id=namespace_id,
        token=token,
        timeout_seconds=120.0,
    )
    assert type(software_adapter) is type(video_adapter) is CloudflareKvPublishAdapter
    software_receipt = software_adapter.publish(
        software.access, software.dispatch.node_attempt, software_publish.request
    )
    video_receipt = video_adapter.publish(
        video.access, video.dispatch.node_attempt, video_publish.request
    )
    software_key = software_adapter.package_key(software_package.archive.content_ref)
    video_key = video_adapter.package_key(video_package.archive.content_ref)
    assert software_receipt.state == video_receipt.state == "VERIFIED"
    assert software_receipt.upload_sha256 == software_package.archive.content_ref.digest
    assert video_receipt.upload_sha256 == video_package.archive.content_ref.digest
    assert software_receipt.remote_identity != video_receipt.remote_identity
    assert software_key != video_key
    assert software_publish.manifest.project_ref != video_publish.manifest.project_ref
    assert software_publish.manifest.sources != video_publish.manifest.sources
    software_evidence = _publish_evidence(
        software, software_adapter, software_publish.request
    )
    video_evidence = _publish_evidence(video, video_adapter, video_publish.request)
    _assert_real_put_and_readback(
        software_evidence,
        package_key=software_key,
        package_digest=software_package.archive.content_ref.digest,
    )
    _assert_real_put_and_readback(
        video_evidence,
        package_key=video_key,
        package_digest=video_package.archive.content_ref.digest,
    )
    assert software.objects.read(software_package.archive.content_ref) == domain_package_bytes(
        software, software_package
    )
    assert video.objects.read(video_package.archive.content_ref) == domain_package_bytes(
        video, video_package
    )
    print(
        "P3-14 REAL cross-domain evidence "
        + json.dumps(
            {
                "software_package_sha256": software_package.archive.content_ref.digest,
                "software_project_ref": software.access.project_ref.value,
                "software_remote_key": software_key,
                "software_receipt_digest": software_receipt.receipt_digest,
                "video_package_sha256": video_package.archive.content_ref.digest,
                "video_project_ref": video.access.project_ref.value,
                "video_remote_key": video_key,
                "video_receipt_digest": video_receipt.receipt_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def domain_package_bytes(domain: _Domain, package: LocalPackageResult) -> bytes:
    """Read retained package bytes without crossing the Project Artifact boundary."""
    artifact = ArtifactService(domain.database).get_artifact(
        domain.access, package.archive.artifact_ref
    )
    assert artifact.content_ref == package.archive.content_ref
    return domain.objects.read(package.archive.content_ref)
