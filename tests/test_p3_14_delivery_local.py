from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
import hashlib
import hmac
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import stat
import sys
from types import ModuleType
from typing import Any, cast
import warnings
import zipfile

import pytest

from minitz_os.engine.artifact import ArtifactService
from minitz_os.engine.delivery_pack import DeliveryArtifactContentRef
from minitz_os.engine.delivery_tool import (
    DeliveryLocalError,
    DeliveryLocalPostPackageError,
    DeterministicLocalDeliveryTool,
    HmacSha256SigningSpec,
    LocalPackageConfig,
    LocalPackageRequest,
    PACKAGE_MANIFEST_PATH,
    PackageInput,
    PackageVerificationEntry,
    RequiredEntriesValidator,
    SecretResolver,
    scan_for_obvious_secrets,
    verify_local_archive,
)
from minitz_os.engine.execution import NodeExecutionAttempt
from minitz_os.engine.object_store import ObjectStorageBackend
from minitz_os.engine.project import ProjectAccess, ProjectRef
from minitz_os.engine.scheduler import ScheduledDispatch, Scheduler


def _fixture_module() -> ModuleType:
    name = "_minitz_p3_05_delivery_fixture"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("P3-05 fixture module is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _environments(tmp_path: Path, count: int = 2) -> tuple[Any, ...]:
    factory = cast(
        Callable[..., tuple[Any, ...]], getattr(_fixture_module(), "_environments")
    )
    return factory(tmp_path, count=count)


def _dispatch(environment: Any) -> ScheduledDispatch:
    database = cast(Path, environment.database)
    access = cast(ProjectAccess, environment.access)
    attempt = cast(NodeExecutionAttempt, environment.attempt)
    allocation = Scheduler(database).get_allocation(access, environment.allocation_ref)
    return ScheduledDispatch(allocation=allocation, node_attempt=attempt)


def _tool(environment: Any) -> DeterministicLocalDeliveryTool:
    return DeterministicLocalDeliveryTool(
        cast(Path, environment.database),
        cast(ObjectStorageBackend, environment.objects),
        access=cast(ProjectAccess, environment.access),
        dispatch=_dispatch(environment),
    )


def _seed(
    environment: Any,
    payload: bytes,
    *,
    media_type: str = "application/octet-stream",
    role: str = "source.package-entry",
) -> DeliveryArtifactContentRef:
    database = cast(Path, environment.database)
    access = cast(ProjectAccess, environment.access)
    attempt = cast(NodeExecutionAttempt, environment.attempt)
    objects = cast(ObjectStorageBackend, environment.objects)
    artifacts = ArtifactService(database)
    content = objects.put(
        payload,
        media_type=media_type,
        expected_digest=hashlib.sha256(payload).hexdigest(),
        expected_size=len(payload),
    )
    producer = next(
        candidate
        for candidate in artifacts.runs.list_attempts(access, attempt.run_ref)
        if candidate.attempt_id == attempt.run_attempt_id
        and candidate.fence == attempt.run_fence
        and candidate.completed_at is None
    )
    artifact = artifacts.publish_from_run(
        access,
        producer_attempt=producer,
        expected_task_ref=attempt.task_ref,
        expected_task_digest=attempt.task_digest,
        role=role,
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="test.fixture.source",
        metadata={"media_type": media_type},
    )
    return DeliveryArtifactContentRef(artifact.artifact_ref, content)


def _request(
    project_ref: ProjectRef,
    inputs: tuple[PackageInput, ...],
    *,
    idempotency_key: str = "delivery-local-test",
    compression: str = "store",
    compression_level: int | None = None,
    validator_ref: str | None = None,
    signing: HmacSha256SigningSpec | None = None,
    package_type: str = "bundle",
    scan_limit: int = 1024 * 1024,
) -> LocalPackageRequest:
    return LocalPackageRequest(
        project_ref=project_ref,
        package_id="desktop-bundle",
        package_type=package_type,
        target_ref="package-target://desktop/linux-x86_64",
        inputs=inputs,
        source_version_ref="source-version://git/fixture-1",
        build_version_ref="build-version://local/fixture-1",
        toolchains={"builder": "toolchain://fixture/builder-1"},
        created_at="2026-09-01T00:00:00+00:00",
        idempotency_key=idempotency_key,
        config=LocalPackageConfig(
            project_ref,
            compression,
            compression_level,
            scan_limit,
            validator_ref,
            signing,
        ),
    )


def _read(environment: Any, source: DeliveryArtifactContentRef) -> bytes:
    return cast(ObjectStorageBackend, environment.objects).read(source.content_ref)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def test_package_artifacts_are_exact_isolated_deterministic_and_installable(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path, 1)[0]
    access = cast(ProjectAccess, environment.access)
    attempt = cast(NodeExecutionAttempt, environment.attempt)
    app = _seed(environment, b"#!/bin/sh\nprintf minitz\n", media_type="text/x-shellscript")
    notice = _seed(environment, b"license fixture\n", media_type="text/plain")
    excluded = _seed(environment, b"MUST-NOT-BE-PACKAGED", media_type="text/plain")
    del excluded
    request = _request(
        access.project_ref,
        (
            PackageInput(notice, "share/NOTICE", "0644"),
            PackageInput(app, "bin/minitz", "0755"),
        ),
        package_type="installable",
        validator_ref="validator://delivery/required-bin/v1",
    )
    validator = RequiredEntriesValidator(
        "validator://delivery/required-bin/v1", ("bin/minitz",)
    )
    first = _tool(environment).assemble(
        access, attempt, request, validator=validator
    )
    second_request = replace(request, idempotency_key="delivery-local-test-second")
    second = _tool(environment).assemble(
        access, attempt, second_request, validator=validator
    )

    archive_payload = _read(environment, first.archive)
    assert archive_payload == _read(environment, second.archive)
    assert first.archive.content_ref.digest == hashlib.sha256(archive_payload).hexdigest()
    assert first.preserved.archive_verification.canonical_bytes_verified is True
    with zipfile.ZipFile(BytesIO(archive_payload), "r") as archive:
        assert archive.namelist() == [PACKAGE_MANIFEST_PATH, "bin/minitz", "share/NOTICE"]
        assert archive.read("bin/minitz") == b"#!/bin/sh\nprintf minitz\n"
        assert archive.read("share/NOTICE") == b"license fixture\n"
        assert b"MUST-NOT-BE-PACKAGED" not in archive_payload
        assert stat.S_IMODE(archive.getinfo("bin/minitz").external_attr >> 16) == 0o755
        assert stat.S_IFMT(archive.getinfo("bin/minitz").external_attr >> 16) == stat.S_IFREG

    manifest_payload = json.loads(_read(environment, first.manifest))
    assert manifest_payload["entry_order"] == ["bin/minitz", "share/NOTICE"]
    assert manifest_payload["entries"] == [
        {
            "content_sha256": hashlib.sha256(b"#!/bin/sh\nprintf minitz\n").hexdigest(),
            "link_policy": "forbid",
            "link_target": None,
            "media_type": "text/x-shellscript",
            "path": "bin/minitz",
            "permission": "0755",
            "size_bytes": 24,
        },
        {
            "content_sha256": hashlib.sha256(b"license fixture\n").hexdigest(),
            "link_policy": "forbid",
            "link_target": None,
            "media_type": "text/plain",
            "path": "share/NOTICE",
            "permission": "0644",
            "size_bytes": 16,
        },
    ]
    evidence = json.loads(_read(environment, first.verification_evidence))
    assert evidence["authority"]["producer_attempt_id"] == attempt.attempt_id
    assert evidence["authority"]["producer_fence"] == attempt.fence
    assert evidence["secret_scan"]["scope"] == "bounded-obvious-patterns-not-exhaustive"
    assert evidence["structural_validation"]["status"] == "verified"
    assert evidence["external_publish_ready"] is True

    artifacts = ArtifactService(cast(Path, environment.database))
    manifest_artifact = artifacts.get_artifact(access, first.manifest.artifact_ref)
    archive_artifact = artifacts.get_artifact(access, first.archive.artifact_ref)
    evidence_artifact = artifacts.get_artifact(access, first.verification_evidence.artifact_ref)
    assert (manifest_artifact.role, archive_artifact.role, evidence_artifact.role) == (
        "delivery.manifest",
        "delivery.archive",
        "delivery.validation-evidence",
    )
    assert manifest_artifact.producer_attempt_id == attempt.run_attempt_id
    assert manifest_artifact.producer_fence == attempt.run_fence
    assert app.artifact_ref in manifest_artifact.source_artifact_refs
    assert first.manifest.artifact_ref in archive_artifact.source_artifact_refs
    assert first.archive.artifact_ref in evidence_artifact.source_artifact_refs


def _raw_zip(
    records: list[tuple[str, bytes, int]],
    *,
    compression: int = zipfile.ZIP_STORED,
) -> bytes:
    output = BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(output, "w", compression=compression) as archive:
            for name, payload, mode in records:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = compression
                info.create_system = 3
                info.external_attr = (mode & 0xFFFF) << 16
                archive.writestr(info, payload, compress_type=compression)
    return output.getvalue()


def test_full_archive_verifier_rejects_corrupt_missing_unsafe_duplicate_and_metadata(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path, 1)[0]
    access = cast(ProjectAccess, environment.access)
    attempt = cast(NodeExecutionAttempt, environment.attempt)
    payload = b"fixed-app"
    source = _seed(environment, payload)
    result = _tool(environment).assemble(
        access,
        attempt,
        _request(access.project_ref, (PackageInput(source, "bin/app", "0755"),)),
    )
    archive_payload = _read(environment, result.archive)
    manifest_payload = _read(environment, result.manifest)
    expected = (
        PackageVerificationEntry(
            "bin/app",
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            "application/octet-stream",
            "0755",
        ),
    )
    verified = verify_local_archive(
        archive_payload,
        manifest_payload=manifest_payload,
        expected_entries=expected,
        compression="store",
        compression_level=None,
    )
    assert verified.archive_sha256 == hashlib.sha256(archive_payload).hexdigest()

    regular_manifest = stat.S_IFREG | 0o644
    regular_app = stat.S_IFREG | 0o755
    malformed = (
        archive_payload[:12] + bytes([archive_payload[12] ^ 0xFF]) + archive_payload[13:],
        _raw_zip([(PACKAGE_MANIFEST_PATH, manifest_payload, regular_manifest)]),
        _raw_zip(
            [
                (PACKAGE_MANIFEST_PATH, manifest_payload, regular_manifest),
                ("bin/app", payload, regular_app),
                ("../escape", b"x", stat.S_IFREG | 0o644),
            ]
        ),
        _raw_zip(
            [
                (PACKAGE_MANIFEST_PATH, manifest_payload, regular_manifest),
                ("bin/app", payload, regular_app),
                ("bin/app", payload, regular_app),
            ]
        ),
        _raw_zip(
            [
                (PACKAGE_MANIFEST_PATH, manifest_payload, regular_manifest),
                ("bin/app", payload, stat.S_IFREG | 0o600),
            ]
        ),
        _raw_zip(
            [
                (PACKAGE_MANIFEST_PATH, manifest_payload, regular_manifest),
                ("bin/app", b"target", stat.S_IFLNK | 0o777),
            ]
        ),
        _raw_zip(
            [
                (PACKAGE_MANIFEST_PATH, manifest_payload, regular_manifest),
                ("bin/app", payload, stat.S_IFIFO | 0o644),
            ]
        ),
        _raw_zip(
            [
                (PACKAGE_MANIFEST_PATH, manifest_payload, regular_manifest),
                ("\\absolute", payload, regular_app),
            ]
        ),
    )
    for candidate in malformed:
        with pytest.raises(DeliveryLocalError):
            verify_local_archive(
                candidate,
                manifest_payload=manifest_payload,
                expected_entries=expected,
                compression="store",
                compression_level=None,
            )


def test_input_contract_rejects_path_link_permission_duplicate_conflict_and_source_change(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path, 1)[0]
    access = cast(ProjectAccess, environment.access)
    attempt = cast(NodeExecutionAttempt, environment.attempt)
    source = _seed(environment, b"one")
    other = _seed(environment, b"two")
    for path in ("../escape", "/absolute", "C:/drive", "a\\b", "a//b"):
        with pytest.raises(DeliveryLocalError):
            PackageInput(source, path)
    with pytest.raises(DeliveryLocalError):
        PackageInput(source, "link", entry_type="symlink", link_target="target")
    with pytest.raises(DeliveryLocalError):
        PackageInput(source, "device", entry_type="special")
    with pytest.raises(DeliveryLocalError):
        PackageInput(source, "bad-mode", "4755")
    with pytest.raises(DeliveryLocalError):
        _request(
            access.project_ref,
            (PackageInput(source, "same"), PackageInput(other, "SAME")),
        )
    with pytest.raises(DeliveryLocalError):
        _request(
            access.project_ref,
            (PackageInput(source, "tree"), PackageInput(other, "tree/leaf")),
        )

    changed = DeliveryArtifactContentRef(source.artifact_ref, other.content_ref)
    request = _request(access.project_ref, (PackageInput(changed, "file"),))
    with pytest.raises(DeliveryLocalError, match="identity changed"):
        _tool(environment).assemble(access, attempt, request)


def test_secret_scan_is_bounded_obvious_and_preserves_verified_local_package(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path, 1)[0]
    access = cast(ProjectAccess, environment.access)
    attempt = cast(NodeExecutionAttempt, environment.attempt)
    secret_payload = b"API_TOKEN=abcdefghijklmnopqrstuvwxyz123456"
    source = _seed(environment, secret_payload, media_type="text/plain")
    request = _request(
        access.project_ref, (PackageInput(source, "config/.env"),)
    )
    with pytest.raises(DeliveryLocalPostPackageError) as captured:
        _tool(environment).assemble(access, attempt, request)
    failure = captured.value
    assert _read(environment, failure.preserved.archive)
    assert {item.rule for item in failure.findings} == {
        "assigned-secret-pattern",
        "environment-file-name",
    }
    assert secret_payload.decode() not in str(failure)

    bounded = scan_for_obvious_secrets(
        {"large.bin": b"x" * 20}, limit_bytes=10
    )
    assert bounded.completed is False
    assert bounded.findings[0].rule == "scan-bound-exceeded"
    private_key = scan_for_obvious_secrets(
        {"key.pem": b"-----BEGIN PRIVATE KEY-----\nfixture"}, limit_bytes=1024
    )
    assert private_key.findings[0].rule == "private-key-marker"


class _MapResolver(SecretResolver):
    def __init__(self, values: Mapping[str, bytes], *, fail: bool = False) -> None:
        self.values = dict(values)
        self.fail = fail

    def resolve_secret(self, access: ProjectAccess, key_ref: str) -> bytes:
        del access
        if self.fail:
            raise RuntimeError(f"resolver must not leak {self.values[key_ref].decode()}")
        return self.values[key_ref]


def test_hmac_signing_verifies_with_safe_metadata_and_never_persists_key_bytes(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path, 1)[0]
    access = cast(ProjectAccess, environment.access)
    attempt = cast(NodeExecutionAttempt, environment.attempt)
    source = _seed(environment, b"signed package")
    key_ref = "secret://project/delivery-test-key"
    key = b"test-only-private-hmac-key-32-bytes"
    signing = HmacSha256SigningSpec(key_ref)
    request = _request(
        access.project_ref,
        (PackageInput(source, "payload.bin"),),
        signing=signing,
    )
    result = _tool(environment).assemble(
        access,
        attempt,
        request,
        secret_resolver=_MapResolver({key_ref: key}),
    )
    assert result.signature is not None
    signature_payload = json.loads(_read(environment, result.signature))
    signed_payload = signature_payload["signed_payload"]
    expected = hmac.new(key, _canonical_json(signed_payload), hashlib.sha256).hexdigest()
    assert signature_payload == {
        "algorithm": "HMAC-SHA256",
        "key_ref": key_ref,
        "signature_hex": expected,
        "signed_payload": signed_payload,
        "signer_ref": "signer://minitz/test-hmac-sha256/v1",
        "verified_after_signing": True,
    }
    evidence_payload = _read(environment, result.verification_evidence)
    assert key not in evidence_payload
    assert key not in _read(environment, result.signature)
    assert key not in _read(environment, result.manifest)
    assert key not in _read(environment, result.archive)
    assert key not in cast(Path, environment.database).read_bytes()
    signature_artifact = ArtifactService(cast(Path, environment.database)).get_artifact(
        access, result.signature.artifact_ref
    )
    assert signature_artifact.role == "delivery.signature"
    assert result.archive.artifact_ref in signature_artifact.source_artifact_refs


def test_replay_recovers_preserved_package_and_rejects_stale_project_or_fence(
    tmp_path: Path,
) -> None:
    first_environment, second_environment = _environments(tmp_path, 2)
    access = cast(ProjectAccess, first_environment.access)
    attempt = cast(NodeExecutionAttempt, first_environment.attempt)
    source = _seed(first_environment, b"replay package")
    key_ref = "secret://project/replay-key"
    key = b"test-only-replay-hmac-key-material"
    request = _request(
        access.project_ref,
        (PackageInput(source, "payload.bin"),),
        signing=HmacSha256SigningSpec(key_ref),
        idempotency_key="delivery-replay",
    )
    tool = _tool(first_environment)
    with pytest.raises(DeliveryLocalPostPackageError) as failed:
        tool.assemble(
            access,
            attempt,
            request,
            secret_resolver=_MapResolver({key_ref: key}, fail=True),
        )
    assert key.decode() not in str(failed.value)
    preserved = failed.value.preserved

    recovered = _tool(first_environment).assemble(
        access,
        attempt,
        request,
        secret_resolver=_MapResolver({key_ref: key}),
    )
    replayed = _tool(first_environment).assemble(
        access,
        attempt,
        request,
        secret_resolver=_MapResolver({key_ref: key}),
    )
    assert recovered.manifest == preserved.manifest
    assert recovered.archive == preserved.archive
    assert replayed.manifest == recovered.manifest
    assert replayed.archive == recovered.archive
    assert replayed.verification_evidence == recovered.verification_evidence
    assert replayed.signature == recovered.signature

    with pytest.raises(DeliveryLocalError, match="bound Project/attempt"):
        tool.assemble(
            cast(ProjectAccess, second_environment.access),
            cast(NodeExecutionAttempt, second_environment.attempt),
            request,
            secret_resolver=_MapResolver({key_ref: key}),
        )
    stale_attempt = replace(attempt, fence=attempt.fence + 1)
    with pytest.raises(DeliveryLocalError, match="bound Project/attempt"):
        tool.assemble(
            access,
            stale_attempt,
            request,
            secret_resolver=_MapResolver({key_ref: key}),
        )
