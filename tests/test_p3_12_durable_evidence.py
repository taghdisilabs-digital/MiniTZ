"""Durable Engine importer for retained REAL P3-12 audio evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
from typing import cast

import pytest

from minitz_os.engine.artifact import Artifact, ArtifactService, ContentRef
from minitz_os.engine.capability import Capability, CapabilityRef, CapabilityRegistry
from minitz_os.engine.event import EventLedger
from minitz_os.engine.execution import NodeExecutionService
from minitz_os.engine.graph import GraphRef, GraphService, Node, NodeRef
from minitz_os.engine.object_store import FilesystemObjectStorageBackend
from minitz_os.engine.project import ProjectStore
from minitz_os.engine.run import RunService
from minitz_os.engine.task import TaskRevisionService
from minitz_os.engine.validation import (
    MetricMeasurement,
    ProjectValidationCriteria,
    ValidationCheck,
    ValidationEvidenceState,
    ValidationService,
    ValidationVerdict,
)


_SCHEMA = "minitz.p3-12.retained-real-evidence/v1"
_OUTPUT_SCHEMA = "minitz.p3-12.durable-engine-evidence/v1"
_MANIFEST_PATH = "evidence/manifest.json"
_CHECKSUM_PATH = "evidence/manifest.sha256"
_ACCEPTED_IMPLEMENTATION_COMMIT = "3dcc194253bb54d2a171cf7230877af95231ebe7"
_ACCEPTED_IMPLEMENTATION_TREE = "8835d92e6651ea13ec5f02b87487f0520fb7bae6"
_IMPLEMENTATION_HASHES = {
    "src/minitz_os/engine/audio_pack.py": "864017ddd61fd4900634a897f7eee5cc767f17548713758fd61806e1ea9afa70",
    "src/minitz_os/engine/audio_tool.py": "45232f37884ef80ea6c60f9d88170fca62ccf3c4735e5749c8c0e63cf710b346",
    "src/minitz_os/engine/cloudflare_audio_model.py": "24f4ac0d6ce3244922b76de0207e374c8dcbc11a49cdf42563c88fcd7c2b3bd5",
}
_CHECK_NAMES = (
    "decode",
    "source_immutable",
    "operations",
    "mix",
    "concurrency",
    "failure_recovery",
    "handoffs",
)
_KPI_NAMES = (
    "invalid_audio_claimed_valid",
    "source_audio_destructively_mutated",
    "project_loudness_target_globalized",
    "implicit_sample_rate_or_channel_conversion",
    "mix_without_exact_stem_identity",
)
_OPERATION_KEYS = (
    "trim",
    "segment",
    "resample",
    "convert_mono",
    "convert_mp3",
    "filter",
    "clean",
    "normalize",
    "master",
    "preview",
    "export",
)
_HEX = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,1024}")
_ROLE = re.compile(r"[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+")
_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_MEMBERS = 4096
_MAX_MEMBER_BYTES = 128 * 1024 * 1024
_SECRET_MARKERS = (b"cfat_",)


class EvidenceArchiveError(ValueError):
    """Retained evidence does not satisfy the exact P3-12 contract."""


@dataclass(frozen=True)
class RetainedFile:
    path: str
    sha256: str
    size: int
    media_type: str
    role: str
    source_artifact_ref: str
    source_content_ref: str
    payload: bytes


@dataclass(frozen=True)
class RetainedAudioEvidence:
    manifest: Mapping[str, object]
    manifest_bytes: bytes
    files: tuple[RetainedFile, ...]
    archive_bytes: bytes
    archive_sha256: str


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise EvidenceArchiveError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise EvidenceArchiveError(f"{label} must be an array")
    return cast(Sequence[object], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise EvidenceArchiveError(f"{label} must be bounded text")
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise EvidenceArchiveError(f"{label} must be an integer >= {minimum}")
    return value


def _sha(value: object, label: str) -> str:
    text = _text(value, label)
    if _HEX.fullmatch(text) is None:
        raise EvidenceArchiveError(f"{label} must be SHA-256")
    return text


def _ref(value: object, label: str) -> str:
    text = _text(value, label)
    if _REF.fullmatch(text) is None:
        raise EvidenceArchiveError(f"{label} must be an absolute ref")
    return text


def _safe_path(value: object, label: str) -> str:
    text = _text(value, label)
    pure = PurePosixPath(text)
    if pure.is_absolute() or ".." in pure.parts or str(pure) != text:
        raise EvidenceArchiveError(f"{label} is unsafe")
    return text


def _checksum_index(payload: bytes) -> Mapping[str, str]:
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise EvidenceArchiveError("checksum index must be ASCII") from exc
    result: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise EvidenceArchiveError("checksum index line is invalid")
        digest, path = parts
        path = _safe_path(path, "checksum path")
        if _HEX.fullmatch(digest) is None or path in result:
            raise EvidenceArchiveError("checksum index entry is invalid")
        result[path] = digest
    if not result:
        raise EvidenceArchiveError("checksum index is empty")
    return result


def _json(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceArchiveError(f"{label} is not valid JSON") from exc
    return _mapping(value, label)


def _evidence_refs(value: object, payload_paths: set[str], label: str) -> tuple[str, ...]:
    refs = tuple(_safe_path(item, label) for item in _sequence(value, label))
    if not refs or any(item not in payload_paths for item in refs):
        raise EvidenceArchiveError(f"{label} must bind retained payloads")
    return refs


def _load_retained_evidence(path_value: str | Path) -> RetainedAudioEvidence:
    path = Path(path_value)
    if not path.is_file() or path.stat().st_size < 1 or path.stat().st_size > _MAX_ARCHIVE_BYTES:
        raise EvidenceArchiveError("retained archive is missing or oversized")
    archive_bytes = path.read_bytes()
    members: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:gz") as archive:
            infos = archive.getmembers()
            if not infos or len(infos) > _MAX_MEMBERS:
                raise EvidenceArchiveError("archive member count is invalid")
            for info in infos:
                name = _safe_path(info.name, "archive member")
                if not info.isfile() or info.size < 0 or info.size > _MAX_MEMBER_BYTES:
                    raise EvidenceArchiveError("archive contains unsupported member")
                if name in members:
                    raise EvidenceArchiveError("archive contains duplicate member")
                stream = archive.extractfile(info)
                if stream is None:
                    raise EvidenceArchiveError("archive member is unreadable")
                payload = stream.read(_MAX_MEMBER_BYTES + 1)
                if len(payload) != info.size:
                    raise EvidenceArchiveError("archive member size mismatch")
                members[name] = payload
    except (tarfile.TarError, OSError) as exc:
        raise EvidenceArchiveError("retained archive is invalid") from exc

    if _MANIFEST_PATH not in members or _CHECKSUM_PATH not in members:
        raise EvidenceArchiveError("manifest or checksum index is missing")
    checksums = _checksum_index(members[_CHECKSUM_PATH])
    expected_index = set(members) - {_CHECKSUM_PATH}
    if set(checksums) != expected_index:
        raise EvidenceArchiveError("checksum index does not exactly cover archive")
    for name, digest in checksums.items():
        if hashlib.sha256(members[name]).hexdigest() != digest:
            raise EvidenceArchiveError(f"checksum mismatch for {name}")

    manifest = _json(members[_MANIFEST_PATH], _MANIFEST_PATH)
    if set(manifest) != {"schema", "source", "runtime", "resource", "files", "checks", "kpis"}:
        raise EvidenceArchiveError("manifest top-level contract is invalid")
    if manifest["schema"] != _SCHEMA:
        raise EvidenceArchiveError("manifest schema is invalid")

    source = _mapping(manifest["source"], "source")
    if source.get("accepted_implementation_commit") != _ACCEPTED_IMPLEMENTATION_COMMIT:
        raise EvidenceArchiveError("accepted implementation commit is invalid")
    declared_files = _sequence(source.get("implementation_files"), "source.implementation_files")
    declared_hashes: dict[str, str] = {}
    for index, item in enumerate(declared_files):
        record = _mapping(item, f"implementation_files[{index}]")
        declared_hashes[_safe_path(record.get("path"), "implementation path")] = _sha(
            record.get("sha256"), "implementation sha256"
        )
    if declared_hashes != _IMPLEMENTATION_HASHES:
        raise EvidenceArchiveError("implementation source hashes are invalid")
    for relative, digest in _IMPLEMENTATION_HASHES.items():
        current = Path(relative)
        if not current.is_file() or hashlib.sha256(current.read_bytes()).hexdigest() != digest:
            raise EvidenceArchiveError("current implementation source identity changed")

    runtime = _mapping(manifest["runtime"], "runtime")
    if runtime.get("classification") != "REAL" or runtime.get("gpu_acceleration_claimed") is not False:
        raise EvidenceArchiveError("runtime classification is invalid")
    for tool in ("ffmpeg", "ffprobe"):
        identity = _mapping(runtime.get(tool), f"runtime.{tool}")
        if not _text(identity.get("version"), f"{tool} version").startswith("8.0.1"):
            raise EvidenceArchiveError(f"{tool} 8.0.1 identity is required")
        _sha(identity.get("binary_sha256"), f"{tool} binary sha256")

    payload_names = {name for name in members if name.startswith("evidence/payload/")}
    indexed: list[RetainedFile] = []
    seen_paths: set[str] = set()
    seen_artifacts: set[str] = set()
    for index, item in enumerate(_sequence(manifest["files"], "files")):
        record = _mapping(item, f"files[{index}]")
        logical_path = _safe_path(record.get("path"), "payload path")
        if not logical_path.startswith("evidence/payload/") or logical_path in seen_paths:
            raise EvidenceArchiveError("payload index path is invalid")
        digest = _sha(record.get("sha256"), "payload sha256")
        size = _integer(record.get("size"), "payload size")
        media_type = _text(record.get("media_type"), "payload media_type")
        role = _text(record.get("role"), "payload role")
        artifact_ref = _ref(record.get("artifact_ref"), "payload artifact_ref")
        content_ref = _ref(record.get("content_ref"), "payload content_ref")
        if _ROLE.fullmatch(role) is None or artifact_ref in seen_artifacts:
            raise EvidenceArchiveError("payload role or Artifact identity is invalid")
        if logical_path not in members:
            raise EvidenceArchiveError("indexed payload is missing")
        payload = members[logical_path]
        if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
            raise EvidenceArchiveError("indexed payload bytes do not match")
        if content_ref != f"content://sha256/{digest}?size={size}":
            raise EvidenceArchiveError("ContentRef does not bind exact payload bytes")
        if any(marker in payload for marker in _SECRET_MARKERS):
            raise EvidenceArchiveError("retained evidence contains a secret marker")
        indexed.append(
            RetainedFile(
                logical_path,
                digest,
                size,
                media_type,
                role,
                artifact_ref,
                content_ref,
                payload,
            )
        )
        seen_paths.add(logical_path)
        seen_artifacts.add(artifact_ref)
    if seen_paths != payload_names:
        raise EvidenceArchiveError("payload index is not exhaustive")

    checks = _mapping(manifest["checks"], "checks")
    if set(checks) != set(_CHECK_NAMES):
        raise EvidenceArchiveError("check topology is invalid")
    for name in _CHECK_NAMES:
        check = _mapping(checks[name], f"checks.{name}")
        if check.get("status") != "PASS":
            raise EvidenceArchiveError(f"{name} did not pass")
        _evidence_refs(check.get("evidence_refs"), payload_names, f"{name} evidence_refs")
    decode = _mapping(checks["decode"], "checks.decode")
    if decode.get("corrupt_rejected") is not True or decode.get("media_mismatch_rejected") is not True:
        raise EvidenceArchiveError("decode rejection evidence is invalid")
    for kind, rate, channels in (("wav", 48000, 2), ("mp3", 48000, 2)):
        decoded = _mapping(decode.get(kind), f"decode.{kind}")
        if decoded.get("sample_rate") != rate or decoded.get("channels") != channels:
            raise EvidenceArchiveError(f"{kind} decoded identity is invalid")
        if not _text(decoded.get("decoder"), f"{kind} decoder").startswith("ffmpeg://8.0.1/"):
            raise EvidenceArchiveError(f"{kind} decoder is invalid")
    immutable = _mapping(checks["source_immutable"], "source_immutable")
    if immutable.get("all_unchanged") is not True or _integer(
        immutable.get("source_count"), "source_count", minimum=1
    ) < 2:
        raise EvidenceArchiveError("source immutability evidence is invalid")
    operations = _mapping(checks["operations"], "operations")
    if (
        operations.get("count") != len(_OPERATION_KEYS)
        or tuple(_sequence(operations.get("operation_keys"), "operation_keys")) != _OPERATION_KEYS
        or operations.get("all_new_artifacts") is not True
        or operations.get("all_new_content") is not True
        or set(_sequence(operations.get("implicit_mutations_rejected"), "implicit mutations"))
        != {"sample_rate", "channel_layout", "loudness_gain"}
    ):
        raise EvidenceArchiveError("operation evidence is invalid")
    mix = _mapping(checks["mix"], "mix")
    levels = _mapping(mix.get("levels_json"), "mix levels")
    if mix.get("exact_processed_stem_count") != 2 or set(levels) != {"first", "second"}:
        raise EvidenceArchiveError("mix does not bind exactly two stems")
    for value in levels.values():
        level = _json(_text(value, "mix level").encode(), "mix level")
        if set(level) != {"effects", "gain_db", "offset_seconds", "pan"}:
            raise EvidenceArchiveError("mix level contract is incomplete")
    _ref(mix.get("mix_output_artifact_ref"), "mix Artifact")
    _ref(mix.get("mix_output_content_ref"), "mix ContentRef")
    _ref(mix.get("session_artifact_ref"), "session Artifact")
    _ref(mix.get("session_content_ref"), "session ContentRef")
    concurrency = _mapping(checks["concurrency"], "concurrency")
    if concurrency.get("distinct_dispatched_attempts") is not True or _integer(
        concurrency.get("measured_max_active"), "measured concurrency", minimum=2
    ) < 2:
        raise EvidenceArchiveError("true concurrency was not measured")
    recovery = _mapping(checks["failure_recovery"], "failure_recovery")
    if recovery.get("bad_failed") is not True or recovery.get("good_output_retained") is not True:
        raise EvidenceArchiveError("partial stem recovery evidence is invalid")
    handoffs = _mapping(checks["handoffs"], "handoffs")
    for kind in ("game", "video"):
        binding = _mapping(handoffs.get(kind), f"handoffs.{kind}")
        if not _text(binding.get("integration_ref"), f"{kind} integration").startswith(
            f"integration://{kind}/"
        ):
            raise EvidenceArchiveError(f"{kind} handoff is invalid")

    kpis = _mapping(manifest["kpis"], "kpis")
    if set(kpis) != set(_KPI_NAMES):
        raise EvidenceArchiveError("KPI topology is invalid")
    for name in _KPI_NAMES:
        measurement = _mapping(kpis[name], f"kpis.{name}")
        if measurement.get("observed") != 0:
            raise EvidenceArchiveError(f"{name} is nonzero")
        _evidence_refs(
            measurement.get("evidence_refs"), payload_names, f"{name} evidence_refs"
        )

    return RetainedAudioEvidence(
        manifest,
        members[_MANIFEST_PATH],
        tuple(indexed),
        archive_bytes,
        hashlib.sha256(archive_bytes).hexdigest(),
    )


def _import_engine_evidence(
    package: RetainedAudioEvidence,
    package_path: Path,
    tmp_path: Path,
    *,
    output_target: Path | None,
) -> Mapping[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    database = tmp_path / "p3-12-durable-evidence.sqlite3"
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    capability_ref = CapabilityRef("audio.validate", "1.0.0")
    output_contract = {
        "audio_evidence": "schema://minitz/p3-12/audio-evidence/1",
        "evidence_manifest": "schema://minitz/p3-12/durable-evidence/1",
    }
    CapabilityRegistry(database).register(
        Capability(
            capability_ref,
            "Validate retained REAL P3-12 audio evidence",
            output_contract=output_contract,
        )
    )
    registration = ProjectStore(database).create_project(
        namespace="p3-12-durable-evidence",
        display_name="P3-12 Durable Audio Evidence",
        metadata={
            "accepted_implementation_commit": _ACCEPTED_IMPLEMENTATION_COMMIT,
            "accepted_implementation_tree": _ACCEPTED_IMPLEMENTATION_TREE,
        },
    )
    access = registration.access
    project_ref = access.project_ref
    task = TaskRevisionService(database).create_task(
        access,
        project_ref=project_ref,
        idempotency_key="p3-12-durable-evidence-task",
        task_type="audio.durable-evidence",
        objective="Retain and validate exact REAL P3-12 audio outputs",
        required_capabilities=(capability_ref,),
        input_refs=(),
        output_contract=output_contract,
        constraints={
            "expected_checks": len(_CHECK_NAMES),
            "expected_payloads": len(package.files),
            "named_zero_kpis": len(_KPI_NAMES),
        },
        side_effect_authority="READ_ONLY",
        data_policy_ref="policy://p3-12/retained-evidence",
        egress_policy_ref="policy://p3-12/no-egress",
        evidence_requirements=("artifact", "content-ref", "provenance", "runtime"),
        acceptance_criteria=("validation.success_rule=ALL_REQUIRED_PASS",),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="worker://p3-12/durable-evidence/run",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(project_ref)
    check_nodes = {
        name: Node(
            NodeRef.new(graph_ref),
            "generic.audio.retained-check",
            (capability_ref,),
            (),
            (),
            output_contract,
            None,
            "READ_ONLY",
            {},
            ("artifact", "content-ref", "provenance", "runtime"),
        )
        for name in _CHECK_NAMES
    }
    integration_node = Node(
        NodeRef.new(graph_ref),
        "generic.audio.evidence-integration",
        (capability_ref,),
        tuple(node.node_ref for node in check_nodes.values()),
        (),
        output_contract,
        None,
        "READ_ONLY",
        {},
        ("artifact", "content-ref", "provenance", "runtime"),
    )
    graphs = GraphService(database)
    graph = graphs.create_graph(
        access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(*check_nodes.values(), integration_node),
        compiler_identity="compiler://p3-12/durable-evidence/v1",
        compiler_version="1.0.0",
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    prepared = executions.prepare_run(access, run.run_ref)
    assert {item.node_ref for item in prepared if item.status == "READY"} == {
        node.node_ref for node in check_nodes.values()
    }

    artifacts = ArtifactService(database)
    package_content = objects.put(
        package.archive_bytes,
        media_type="application/gzip",
        expected_digest=package.archive_sha256,
        expected_size=len(package.archive_bytes),
    )
    package_artifact = artifacts.publish_from_run(
        access,
        producer_attempt=run_attempt,
        expected_task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        role="audio.retained-package",
        content_ref=package_content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="audio.captured-real-evidence",
        metadata={"semantic_label": "P3_12_FINAL_REAL_EVIDENCE.tar.gz"},
    )
    manifest_content = objects.put(
        package.manifest_bytes,
        media_type="application/json",
        expected_digest=hashlib.sha256(package.manifest_bytes).hexdigest(),
        expected_size=len(package.manifest_bytes),
    )
    manifest_artifact = artifacts.publish_from_run(
        access,
        producer_attempt=run_attempt,
        expected_task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        role="audio.validation-evidence",
        content_ref=manifest_content,
        source_refs=(),
        source_artifact_refs=(package_artifact.artifact_ref,),
        source_content_refs=(package_content,),
        derivation_type="audio.extracted-retained-package",
        metadata={"semantic_label": _MANIFEST_PATH},
    )
    published_by_path: dict[str, Artifact] = {}
    for retained in package.files:
        content = objects.put(
            retained.payload,
            media_type=retained.media_type,
            expected_digest=retained.sha256,
            expected_size=retained.size,
        )
        artifact = artifacts.publish_from_run(
            access,
            producer_attempt=run_attempt,
            expected_task_ref=task.task_ref,
            expected_task_digest=task.canonical_digest,
            role=retained.role,
            content_ref=content,
            source_refs=(),
            source_artifact_refs=(package_artifact.artifact_ref,),
            source_content_refs=(package_content,),
            derivation_type="audio.extracted-retained-package",
            metadata={"semantic_label": retained.path},
        )
        assert objects.verify(content) is True
        published_by_path[retained.path] = artifact

    checks = _mapping(package.manifest["checks"], "checks")
    runtime_artifact = published_by_path["evidence/payload/qualification/runtime.json"]
    integration_artifact = published_by_path[
        "evidence/payload/qualification/qualification.json"
    ]
    node_attempts: dict[str, object] = {}
    node_statuses: dict[str, str] = {}
    for name, node in check_nodes.items():
        check = _mapping(checks[name], f"checks.{name}")
        evidence_paths = tuple(
            cast(str, item) for item in _sequence(check["evidence_refs"], "evidence refs")
        )
        representative = published_by_path[evidence_paths[0]]
        attempt = executions.lease_node(
            access,
            node.node_ref,
            authority_attempt=run_attempt,
            owner_ref=f"worker://p3-12/durable-evidence/{name}",
            lease_seconds=1800,
            idempotency_key=f"p3-12-{name}-lease",
        )
        assert executions.start_node(
            access, attempt, idempotency_key=f"p3-12-{name}-start"
        ).status == "RUNNING"
        completed = executions.finalize_node(
            access,
            attempt,
            outputs={
                "audio_evidence": representative.artifact_ref,
                "evidence_manifest": manifest_artifact.artifact_ref,
            },
            evidence={
                "artifact": representative.artifact_ref,
                "content-ref": cast(ContentRef, representative.content_ref),
                "provenance": package_artifact.artifact_ref,
                "runtime": runtime_artifact.artifact_ref,
            },
            acceptance_criteria=(),
            idempotency_key=f"p3-12-{name}-finalize",
        )
        assert completed.status == "SUCCEEDED"
        node_attempts[name] = attempt
        node_statuses[name] = completed.status

    assert {
        item.node_ref
        for item in executions.prepare_run(access, run.run_ref)
        if item.status == "READY"
    } == {integration_node.node_ref}
    integration_attempt = executions.lease_node(
        access,
        integration_node.node_ref,
        authority_attempt=run_attempt,
        owner_ref="worker://p3-12/durable-evidence/integration",
        lease_seconds=1800,
        idempotency_key="p3-12-integration-lease",
    )
    assert executions.start_node(
        access, integration_attempt, idempotency_key="p3-12-integration-start"
    ).status == "RUNNING"

    all_artifacts = (package_artifact, manifest_artifact, *published_by_path.values())
    validations = ValidationService(database)
    subjects = tuple(
        validations.bind_artifact_subject(
            access,
            artifact.artifact_ref,
            producer_dimensions={
                "content_ref": cast(ContentRef, artifact.content_ref).value,
                "source_commit": f"source://git/commit/{_ACCEPTED_IMPLEMENTATION_COMMIT}",
                "source_tree": f"source://git/tree/{_ACCEPTED_IMPLEMENTATION_TREE}",
            },
        )
        for artifact in all_artifacts
    )
    validation_checks = tuple(
        ValidationCheck(
            capability_ref,
            True,
            "project.criteria:p3-12-audio-check",
            ("artifact", "content_ref", "provenance"),
            (),
            {"requirement": name},
        )
        for name in _CHECK_NAMES
    ) + tuple(
        ValidationCheck(
            capability_ref,
            True,
            "project.criteria:p3-12-audio-kpi",
            ("artifact", "content_ref", "provenance"),
            (),
            {"expected": 0, "kpi": name},
        )
        for name in _KPI_NAMES
    )
    plan = validations.compile_plan(
        access,
        integration_attempt,
        subjects=subjects,
        project_criteria=ProjectValidationCriteria(
            project_ref,
            validation_checks,
            "criteria://p3-12/audio-durable-evidence/v1",
        ),
        idempotency_key="p3-12-durable-evidence-validation-plan",
    )
    evidence_refs = tuple(
        [artifact.artifact_ref.value for artifact in all_artifacts]
        + [cast(ContentRef, artifact.content_ref).value for artifact in all_artifacts]
    )
    kpis = _mapping(package.manifest["kpis"], "kpis")
    runtime_ref = _ref(
        _mapping(package.manifest["runtime"], "runtime")["audio_runtime_ref"],
        "audio runtime ref",
    )
    results = []
    observed_kpis: set[str] = set()
    for check in plan.checks:
        kpi_name = check.parameters.get("kpi")
        metrics: tuple[MetricMeasurement, ...] = ()
        if isinstance(kpi_name, str):
            measurement = _mapping(kpis[kpi_name], f"kpis.{kpi_name}")
            assert measurement["observed"] == 0
            metrics = (
                MetricMeasurement(
                    kpi_name,
                    0.0,
                    "count",
                    f"Measured {kpi_name} violations in retained P3-12 REAL evidence",
                    integration_artifact.artifact_ref.value,
                ),
            )
            observed_kpis.add(kpi_name)
        result = validations.record_result(
            access,
            integration_attempt,
            plan.plan_ref,
            check_id=check.check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref="validator://p3-12/durable-evidence/v1",
            runtime_ref=runtime_ref,
            validator_dimensions={
                "source_commit": f"source://git/commit/{_ACCEPTED_IMPLEMENTATION_COMMIT}",
                "source_tree": f"source://git/tree/{_ACCEPTED_IMPLEMENTATION_TREE}",
            },
            evidence_refs=evidence_refs,
            metrics=metrics,
            idempotency_key=f"p3-12-result-{check.check_id}",
        )
        assert result.verdict is ValidationVerdict.PASS
        assert result.evidence_state is ValidationEvidenceState.CURRENT
        results.append(result)
    assert observed_kpis == set(_KPI_NAMES)
    aggregate = validations.aggregate(
        access,
        integration_attempt,
        plan.plan_ref,
        idempotency_key="p3-12-durable-evidence-validation-aggregate",
    )
    assert aggregate.verdict is ValidationVerdict.PASS
    assert aggregate.accepted is True
    assert aggregate.evidence_state is ValidationEvidenceState.CURRENT
    assert aggregate.missing_required_check_ids == ()

    event_ledger = EventLedger(database)
    evidence_event = event_ledger.append_event(
        access,
        project_ref=project_ref,
        task_ref=task.task_ref,
        run_ref=run.run_ref,
        graph_ref=graph_ref,
        node_ref=integration_node.node_ref,
        event_type="P3_12_DURABLE_AUDIO_EVIDENCE_RETAINED",
        idempotency_key="p3-12-durable-audio-evidence-retained",
        actor_ref="worker://p3-12/durable-evidence",
        object_refs=tuple(artifact.artifact_ref for artifact in all_artifacts),
        metadata={
            "artifact_count": len(all_artifacts),
            "check_count": len(_CHECK_NAMES),
            "kpi_count": len(_KPI_NAMES),
            "payload_count": len(package.files),
            "source_commit": _ACCEPTED_IMPLEMENTATION_COMMIT,
            "source_tree": _ACCEPTED_IMPLEMENTATION_TREE,
            "validation_aggregate_sha256": aggregate.aggregate_sha256,
        },
        payload_ref=cast(ContentRef, integration_artifact.content_ref),
        authority_attempt=run_attempt,
    )
    acceptance_event = executions.record_run_acceptance(
        access,
        run.run_ref,
        criterion="validation.success_rule=ALL_REQUIRED_PASS",
        evidence_ref=integration_artifact.artifact_ref,
        authority_attempt=run_attempt,
        actor_ref=run_attempt.owner_ref,
        idempotency_key="p3-12-durable-evidence-acceptance",
    )
    completed_integration = executions.finalize_node(
        access,
        integration_attempt,
        outputs={
            "audio_evidence": integration_artifact.artifact_ref,
            "evidence_manifest": manifest_artifact.artifact_ref,
        },
        evidence={
            "artifact": integration_artifact.artifact_ref,
            "content-ref": cast(ContentRef, integration_artifact.content_ref),
            "provenance": package_artifact.artifact_ref,
            "runtime": runtime_artifact.artifact_ref,
        },
        acceptance_criteria=(),
        idempotency_key="p3-12-integration-finalize",
    )
    assert completed_integration.status == "SUCCEEDED"
    completed_run = runs.get_run(access, run.run_ref)
    assert completed_run.status == "SUCCEEDED"
    assert GraphService(database).get_graph(access, graph_ref) == graph
    assert EventLedger(database).get_event(access, evidence_event.event_ref) == evidence_event
    assert EventLedger(database).get_event(access, acceptance_event.event_ref) == acceptance_event
    for artifact in all_artifacts:
        assert ArtifactService(database).get_artifact(access, artifact.artifact_ref) == artifact
        assert objects.verify(cast(ContentRef, artifact.content_ref)) is True

    output: Mapping[str, object] = {
        "schema": _OUTPUT_SCHEMA,
        "source": {
            "accepted_implementation_commit": _ACCEPTED_IMPLEMENTATION_COMMIT,
            "accepted_implementation_tree": _ACCEPTED_IMPLEMENTATION_TREE,
            "implementation_sha256": dict(_IMPLEMENTATION_HASHES),
        },
        "retained_package": {
            "artifact_ref": package_artifact.artifact_ref.value,
            "content_ref": package_content.value,
            "path": str(package_path),
            "sha256": package.archive_sha256,
            "size": len(package.archive_bytes),
            "status": "VERIFIED",
        },
        "engine": {
            "project_ref": project_ref.value,
            "task_ref": {
                "project_ref": task.task_ref.project_ref.value,
                "task_id": task.task_ref.task_id,
                "revision": task.task_ref.revision,
            },
            "run_ref": {
                "project_ref": run.run_ref.project_ref.value,
                "run_id": run.run_ref.run_id,
            },
            "run_state_sha256": completed_run.state_sha256,
            "graph_ref": graph_ref.value,
            "graph_sha256": graph.record_sha256,
            "integration_node_ref": integration_node.node_ref.value,
        },
        "engine_status": completed_run.status,
        "checks": [
            {
                "name": name,
                "node_ref": check_nodes[name].node_ref.value,
                "attempt_id": cast(object, node_attempts[name]).attempt_id,
                "status": node_statuses[name],
            }
            for name in _CHECK_NAMES
        ],
        "integration": {
            "artifact_ref": integration_artifact.artifact_ref.value,
            "content_ref": cast(ContentRef, integration_artifact.content_ref).value,
            "status": completed_integration.status,
        },
        "kpis": {
            name: cast(Mapping[str, object], kpis[name])["observed"]
            for name in _KPI_NAMES
        },
        "validation": {
            "accepted": aggregate.accepted,
            "aggregate_sha256": aggregate.aggregate_sha256,
            "plan_ref": plan.plan_ref.value,
            "result_refs": [result.result_ref.value for result in results],
            "verdict": aggregate.verdict.value,
        },
        "events": {
            "acceptance": acceptance_event.event_ref.value,
            "evidence": evidence_event.event_ref.value,
        },
        "reconstruction": "PASS",
        "unresolved_failures": 0,
    }
    if output_target is not None:
        output_target.parent.mkdir(parents=True, exist_ok=True)
        output_target.write_text(
            json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        assert _json(output_target.read_bytes(), str(output_target)) == output
    return output


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(payload)
    member.mode = 0o600
    archive.addfile(member, BytesIO(payload))


def test_retained_evidence_rejects_payload_omitted_from_checksum_index(
    tmp_path: Path,
) -> None:
    manifest = json.dumps({}, sort_keys=True, separators=(",", ":")).encode()
    checksum = f"{hashlib.sha256(manifest).hexdigest()}  evidence/manifest.json\n".encode()
    archive_path = tmp_path / "smuggled.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        _add_bytes(archive, _MANIFEST_PATH, manifest)
        _add_bytes(archive, _CHECKSUM_PATH, checksum)
        _add_bytes(archive, "evidence/payload/unindexed.bin", b"smuggled")
    with pytest.raises(EvidenceArchiveError, match="checksum index"):
        _load_retained_evidence(archive_path)


def test_retained_evidence_rejects_unsafe_member(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        _add_bytes(archive, "../escape", b"unsafe")
    with pytest.raises(EvidenceArchiveError, match="unsafe"):
        _load_retained_evidence(archive_path)


def test_p3_12_final_retained_package_import(tmp_path: Path) -> None:
    archive_value = os.environ.get("MINITZ_P3_12_EVIDENCE_ARCHIVE")
    if not archive_value:
        pytest.skip("MINITZ_P3_12_EVIDENCE_ARCHIVE is not set")
    archive = Path(archive_value)
    package = _load_retained_evidence(archive)
    output_value = os.environ.get("MINITZ_P3_12_ENGINE_EVIDENCE_OUT")
    output = _import_engine_evidence(
        package,
        archive,
        tmp_path / "engine",
        output_target=None if not output_value else Path(output_value),
    )
    assert output["schema"] == _OUTPUT_SCHEMA
    assert output["engine_status"] == "SUCCEEDED"
    assert output["reconstruction"] == "PASS"
    assert output["unresolved_failures"] == 0
