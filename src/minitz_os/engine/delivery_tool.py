"""Deterministic, dispatch-bound local package assembly and verification."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
from types import MappingProxyType
from typing import Protocol, cast
import zipfile
import zlib

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .delivery_pack import DeliveryArtifactContentRef, PackageEntry, PackageManifest
from .execution import NodeExecutionAttempt, NodeExecutionError, NodeExecutionService
from .object_store import ObjectStorageBackend, ObjectStorageError
from .project import ProjectAccess, ProjectRef
from .run import ExecutionAttempt
from .scheduler import ScheduledDispatch


PACKAGE_MANIFEST_PATH = "PACKAGE-MANIFEST.json"
_VERSION = "1.0.0"
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_PACKAGE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_IDEMPOTENCY = re.compile(r"[A-Za-z0-9_.:-]{1,192}")
_PERMISSION = re.compile(r"0[0-7]{3}")
_PRIVATE_KEY = re.compile(
    br"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
)
_ASSIGNED_SECRET = re.compile(
    br"(?i)(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret|token)"
    br"[ \t]*[:=][ \t]*[\"']?[A-Za-z0-9_./+=-]{12,}"
)
_KNOWN_TOKEN = re.compile(
    br"(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})"
)


class DeliveryLocalError(ValueError):
    """Fail-closed local delivery error."""


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _absolute_ref(value: object, field: str) -> str:
    if not isinstance(value, str) or _ABSOLUTE_REF.fullmatch(value) is None:
        raise DeliveryLocalError(f"{field} is not an absolute reference")
    return value


def _safe_path(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 1024
        or "\\" in value
        or value.startswith("/")
        or "//" in value
        or "\x00" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise DeliveryLocalError(f"{field} is an unsafe relative package path")
    parts = value.split("/")
    if (
        any(part in {"", ".", ".."} for part in parts)
        or re.fullmatch(r"[A-Za-z]:", parts[0]) is not None
        or ":" in parts[0]
        or PurePosixPath(value).as_posix() != value
    ):
        raise DeliveryLocalError(f"{field} is an unsafe relative package path")
    return value


def _permission(value: object, field: str) -> str:
    if not isinstance(value, str) or _PERMISSION.fullmatch(value) is None:
        raise DeliveryLocalError(f"{field} is not a regular-file permission")
    return value


def _timestamp(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise DeliveryLocalError(f"{field} is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise DeliveryLocalError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DeliveryLocalError(f"{field} must include a timezone")
    return value


def _string_map(value: Mapping[str, str], field: str) -> Mapping[str, str]:
    copied: dict[str, str] = {}
    for key, item in value.items():
        if (
            not isinstance(key, str)
            or not key
            or len(key) > 128
            or not isinstance(item, str)
            or not item
            or len(item) > 512
        ):
            raise DeliveryLocalError(f"{field} is malformed")
        copied[key] = item
    return MappingProxyType(dict(sorted(copied.items())))


def _require_no_path_conflicts(paths: Sequence[str]) -> None:
    folded = tuple(tuple(part.casefold() for part in path.split("/")) for path in paths)
    for index, left in enumerate(folded):
        for right in folded[index + 1 :]:
            common = min(len(left), len(right))
            if left[:common] == right[:common]:
                raise DeliveryLocalError("package entries duplicate or conflict as file/parent")


@dataclass(frozen=True)
class PackageInput:
    """One exact Artifact+Content binding to one regular archive entry."""

    source: DeliveryArtifactContentRef
    entry_path: str
    permission: str = "0644"
    entry_type: str = "file"
    link_target: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, DeliveryArtifactContentRef):
            raise DeliveryLocalError("PackageInput requires exact Artifact+Content identity")
        object.__setattr__(self, "entry_path", _safe_path(self.entry_path, "PackageInput path"))
        object.__setattr__(self, "permission", _permission(self.permission, "PackageInput permission"))
        if self.entry_type != "file":
            raise DeliveryLocalError("local packages reject symlink and special entries")
        if self.link_target is not None:
            raise DeliveryLocalError("local packages reject link targets")

    def payload(self) -> dict[str, object]:
        return {
            "entry_path": self.entry_path,
            "entry_type": self.entry_type,
            "link_target": self.link_target,
            "permission": self.permission,
            "source": self.source.payload(),
        }


@dataclass(frozen=True)
class HmacSha256SigningSpec:
    """Safe references for the optional test signer; never key bytes."""

    key_ref: str
    signer_ref: str = "signer://minitz/test-hmac-sha256/v1"
    metadata_ref: str = "signature-config://minitz/test-hmac-sha256/v1"

    def __post_init__(self) -> None:
        if not self.key_ref.startswith(("secret://", "key://")):
            raise DeliveryLocalError("HMAC signing requires a secret/key reference")
        _absolute_ref(self.key_ref, "HMAC key_ref")
        _absolute_ref(self.signer_ref, "HMAC signer_ref")
        _absolute_ref(self.metadata_ref, "HMAC metadata_ref")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm": "HMAC-SHA256",
            "key_ref": self.key_ref,
            "metadata_ref": self.metadata_ref,
            "signer_ref": self.signer_ref,
        }


@dataclass(frozen=True)
class LocalPackageConfig:
    """Project-scoped deterministic archive and validation configuration."""

    project_ref: ProjectRef
    compression: str
    compression_level: int | None
    secret_scan_limit_bytes: int = 8 * 1024 * 1024
    validator_ref: str | None = None
    signing: HmacSha256SigningSpec | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise DeliveryLocalError("package config requires exact ProjectRef")
        if self.compression == "store":
            if self.compression_level is not None:
                raise DeliveryLocalError("stored ZIP must not claim a compression level")
        elif self.compression == "deflate":
            if (
                not isinstance(self.compression_level, int)
                or isinstance(self.compression_level, bool)
                or not 0 <= self.compression_level <= 9
            ):
                raise DeliveryLocalError("deflate ZIP requires explicit level 0..9")
        else:
            raise DeliveryLocalError("package compression must be store or deflate")
        if (
            not isinstance(self.secret_scan_limit_bytes, int)
            or isinstance(self.secret_scan_limit_bytes, bool)
            or not 1 <= self.secret_scan_limit_bytes <= 64 * 1024 * 1024
        ):
            raise DeliveryLocalError("secret scan bound is invalid")
        if self.validator_ref is not None:
            _absolute_ref(self.validator_ref, "validator_ref")
        if self.signing is not None and not isinstance(self.signing, HmacSha256SigningSpec):
            raise DeliveryLocalError("signing config is invalid")

    def payload(self) -> dict[str, object]:
        return {
            "compression": self.compression,
            "compression_level": self.compression_level,
            "project_ref": self.project_ref.value,
            "secret_scan_limit_bytes": self.secret_scan_limit_bytes,
            "signing": None if self.signing is None else self.signing.payload(),
            "validator_ref": self.validator_ref,
        }

    @property
    def config_sha256(self) -> str:
        return _sha256(_json_bytes(self.payload()))


@dataclass(frozen=True)
class LocalPackageRequest:
    project_ref: ProjectRef
    package_id: str
    package_type: str
    target_ref: str
    inputs: tuple[PackageInput, ...]
    source_version_ref: str
    build_version_ref: str
    toolchains: Mapping[str, str]
    created_at: str
    idempotency_key: str
    config: LocalPackageConfig

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise DeliveryLocalError("local package requires exact ProjectRef")
        if _PACKAGE_ID.fullmatch(self.package_id) is None:
            raise DeliveryLocalError("package_id is invalid")
        if not isinstance(self.package_type, str) or not self.package_type or len(self.package_type) > 128:
            raise DeliveryLocalError("package_type is invalid")
        _absolute_ref(self.target_ref, "target_ref")
        _absolute_ref(self.source_version_ref, "source_version_ref")
        _absolute_ref(self.build_version_ref, "build_version_ref")
        _timestamp(self.created_at, "created_at")
        if _IDEMPOTENCY.fullmatch(self.idempotency_key) is None:
            raise DeliveryLocalError("idempotency_key is invalid")
        if not isinstance(self.config, LocalPackageConfig) or self.config.project_ref != self.project_ref:
            raise DeliveryLocalError("package config crossed Project scope")
        values = tuple(self.inputs)
        if not values or len(values) > 4096 or not all(isinstance(item, PackageInput) for item in values):
            raise DeliveryLocalError("package inputs are empty, malformed, or unbounded")
        if any(item.source.project_ref != self.project_ref for item in values):
            raise DeliveryLocalError("PackageInput crossed Project scope")
        ordered = tuple(sorted(values, key=lambda item: item.entry_path))
        paths = tuple(item.entry_path for item in ordered)
        if (
            len({path.casefold() for path in paths}) != len(paths)
            or PACKAGE_MANIFEST_PATH.casefold() in {path.casefold() for path in paths}
        ):
            raise DeliveryLocalError("package input paths are duplicate or reserved")
        _require_no_path_conflicts(paths)
        object.__setattr__(self, "inputs", ordered)
        normalized_toolchains = _string_map(self.toolchains, "toolchains")
        if "local-package-runtime" in normalized_toolchains:
            raise DeliveryLocalError("local-package-runtime toolchain is runtime-owned")
        object.__setattr__(self, "toolchains", normalized_toolchains)
        if self.package_type == "installable" and self.config.validator_ref is None:
            raise DeliveryLocalError("installable package requires a structural validator")

    def payload(self) -> dict[str, object]:
        return {
            "build_version_ref": self.build_version_ref,
            "config": self.config.payload(),
            "created_at": self.created_at,
            "idempotency_key": self.idempotency_key,
            "inputs": [item.payload() for item in self.inputs],
            "package_id": self.package_id,
            "package_type": self.package_type,
            "project_ref": self.project_ref.value,
            "source_version_ref": self.source_version_ref,
            "target_ref": self.target_ref,
            "toolchains": dict(self.toolchains),
        }


@dataclass(frozen=True)
class PackageVerificationEntry:
    path: str
    content_sha256: str
    size_bytes: int
    media_type: str
    permission: str
    link_policy: str = "forbid"
    link_target: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _safe_path(self.path, "verification entry path"))
        if _SHA256.fullmatch(self.content_sha256) is None:
            raise DeliveryLocalError("verification entry digest is invalid")
        if (
            not isinstance(self.size_bytes, int)
            or isinstance(self.size_bytes, bool)
            or self.size_bytes < 0
        ):
            raise DeliveryLocalError("verification entry size is invalid")
        if not isinstance(self.media_type, str) or not self.media_type:
            raise DeliveryLocalError("verification entry media type is invalid")
        object.__setattr__(self, "permission", _permission(self.permission, "verification entry permission"))
        if self.link_policy != "forbid" or self.link_target is not None:
            raise DeliveryLocalError("local archive verification forbids links and targets")

    def payload(self) -> dict[str, object]:
        return {
            "content_sha256": self.content_sha256,
            "link_policy": self.link_policy,
            "link_target": self.link_target,
            "media_type": self.media_type,
            "path": self.path,
            "permission": self.permission,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class ArchiveVerification:
    archive_sha256: str
    archive_size_bytes: int
    compression: str
    compression_level: int | None
    entries: tuple[PackageVerificationEntry, ...]
    manifest_sha256: str
    canonical_bytes_verified: bool

    def payload(self) -> dict[str, object]:
        return {
            "archive_sha256": self.archive_sha256,
            "archive_size_bytes": self.archive_size_bytes,
            "canonical_bytes_verified": self.canonical_bytes_verified,
            "compression": self.compression,
            "compression_level": self.compression_level,
            "entries": [item.payload() for item in self.entries],
            "manifest_path": PACKAGE_MANIFEST_PATH,
            "manifest_sha256": self.manifest_sha256,
        }


@dataclass(frozen=True)
class SecretFinding:
    entry_path: str
    rule: str

    def payload(self) -> dict[str, str]:
        return {"entry_path": self.entry_path, "rule": self.rule}


@dataclass(frozen=True)
class SecretScanEvidence:
    completed: bool
    scanned_bytes: int
    limit_bytes: int
    findings: tuple[SecretFinding, ...]
    scope: str = "bounded-obvious-patterns-not-exhaustive"

    def payload(self) -> dict[str, object]:
        return {
            "completed": self.completed,
            "findings": [item.payload() for item in self.findings],
            "limit_bytes": self.limit_bytes,
            "scanned_bytes": self.scanned_bytes,
            "scope": self.scope,
        }


@dataclass(frozen=True)
class PreservedLocalPackage:
    project_ref: ProjectRef
    request_digest: str
    manifest: DeliveryArtifactContentRef
    archive: DeliveryArtifactContentRef
    package_manifest: PackageManifest
    archive_verification: ArchiveVerification
    producer_attempt_id: str
    producer_fence: int


class DeliveryLocalPostPackageError(DeliveryLocalError):
    """A post-package gate failed; verified local artifacts remain durable."""

    def __init__(
        self,
        message: str,
        preserved: PreservedLocalPackage,
        findings: Sequence[SecretFinding] = (),
    ) -> None:
        super().__init__(message)
        self.preserved = preserved
        self.findings = tuple(findings)


@dataclass(frozen=True)
class LocalPackageResult:
    preserved: PreservedLocalPackage
    verification_evidence: DeliveryArtifactContentRef
    signature: DeliveryArtifactContentRef | None
    secret_scan: SecretScanEvidence
    structural_validation: Mapping[str, str]

    def __post_init__(self) -> None:
        project_ref = self.preserved.project_ref
        if (
            self.verification_evidence.project_ref != project_ref
            or (self.signature is not None and self.signature.project_ref != project_ref)
        ):
            raise DeliveryLocalError("local package result crossed Project scope")
        object.__setattr__(
            self,
            "structural_validation",
            _string_map(self.structural_validation, "structural validation"),
        )

    @property
    def manifest(self) -> DeliveryArtifactContentRef:
        return self.preserved.manifest

    @property
    def archive(self) -> DeliveryArtifactContentRef:
        return self.preserved.archive


class SecretResolver(Protocol):
    def resolve_secret(self, access: ProjectAccess, key_ref: str) -> bytes: ...


class InstallableStructuralValidator(Protocol):
    @property
    def validator_ref(self) -> str: ...

    def validate(
        self, manifest: PackageManifest, entries: Mapping[str, bytes]
    ) -> Mapping[str, str]: ...


@dataclass(frozen=True)
class RequiredEntriesValidator:
    """Small in-process structural validator for explicitly required paths."""

    validator_ref: str
    required_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        _absolute_ref(self.validator_ref, "validator_ref")
        values = tuple(_safe_path(item, "required path") for item in self.required_paths)
        if not values or len(values) != len(set(item.casefold() for item in values)):
            raise DeliveryLocalError("required validator paths are empty or duplicate")
        object.__setattr__(self, "required_paths", tuple(sorted(values)))

    def validate(
        self, manifest: PackageManifest, entries: Mapping[str, bytes]
    ) -> Mapping[str, str]:
        del manifest
        missing = tuple(path for path in self.required_paths if path not in entries)
        if missing:
            raise DeliveryLocalError("installable package is missing required entries")
        return MappingProxyType(
            {
                "required_entry_count": str(len(self.required_paths)),
                "status": "verified",
                "validator_ref": self.validator_ref,
            }
        )


def scan_for_obvious_secrets(
    entries: Mapping[str, bytes], *, limit_bytes: int
) -> SecretScanEvidence:
    """Bounded heuristic scan. Passing is explicitly not proof that no secret exists."""

    if (
        not isinstance(limit_bytes, int)
        or isinstance(limit_bytes, bool)
        or not 1 <= limit_bytes <= 64 * 1024 * 1024
    ):
        raise DeliveryLocalError("secret scan bound is invalid")
    findings: list[SecretFinding] = []
    scanned = 0
    for raw_path in sorted(entries):
        path = _safe_path(raw_path, "secret scan entry path")
        payload = entries[raw_path]
        if not isinstance(payload, bytes):
            raise DeliveryLocalError("secret scan accepts bytes only")
        if scanned + len(payload) > limit_bytes:
            findings.append(SecretFinding(path, "scan-bound-exceeded"))
            return SecretScanEvidence(False, scanned, limit_bytes, tuple(findings))
        scanned += len(payload)
        basename = path.rsplit("/", 1)[-1].casefold()
        if basename == ".env" or basename.startswith(".env."):
            findings.append(SecretFinding(path, "environment-file-name"))
        for rule, pattern in (
            ("private-key-marker", _PRIVATE_KEY),
            ("assigned-secret-pattern", _ASSIGNED_SECRET),
            ("known-token-shape", _KNOWN_TOKEN),
        ):
            if pattern.search(payload) is not None:
                findings.append(SecretFinding(path, rule))
    unique = {
        (finding.entry_path, finding.rule): finding for finding in findings
    }
    ordered = tuple(unique[key] for key in sorted(unique))
    return SecretScanEvidence(True, scanned, limit_bytes, ordered)


@dataclass(frozen=True)
class _ArchiveMaterial:
    path: str
    payload: bytes
    permission: str


def _compression_values(
    compression: str, compression_level: int | None
) -> tuple[int, int | None]:
    if compression == "store" and compression_level is None:
        return zipfile.ZIP_STORED, None
    if (
        compression == "deflate"
        and isinstance(compression_level, int)
        and not isinstance(compression_level, bool)
        and 0 <= compression_level <= 9
    ):
        return zipfile.ZIP_DEFLATED, compression_level
    raise DeliveryLocalError("archive compression configuration is invalid")


def _build_archive(
    materials: Sequence[_ArchiveMaterial],
    *,
    compression: str,
    compression_level: int | None,
) -> bytes:
    compression_type, level = _compression_values(compression, compression_level)
    ordered = tuple(sorted(materials, key=lambda item: item.path))
    paths = tuple(_safe_path(item.path, "archive material path") for item in ordered)
    if len(paths) != len(set(path.casefold() for path in paths)):
        raise DeliveryLocalError("archive material paths are duplicate")
    _require_no_path_conflicts(paths)
    output = BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=compression_type,
        compresslevel=level,
        allowZip64=True,
        strict_timestamps=True,
    ) as archive:
        archive.comment = b""
        for material in ordered:
            info = zipfile.ZipInfo(material.path, date_time=_ZIP_TIME)
            info.compress_type = compression_type
            info.create_system = 3
            info.external_attr = (
                (stat.S_IFREG | int(_permission(material.permission, "archive permission"), 8))
                & 0xFFFF
            ) << 16
            info.internal_attr = 0
            info.extra = b""
            info.comment = b""
            archive.writestr(
                info,
                material.payload,
                compress_type=compression_type,
                compresslevel=level,
            )
    return output.getvalue()


def verify_local_archive(
    archive_payload: bytes,
    *,
    manifest_payload: bytes,
    expected_entries: Sequence[PackageVerificationEntry],
    compression: str,
    compression_level: int | None,
) -> ArchiveVerification:
    """Reopen, enumerate, fully read, and byte-canonicalize one local ZIP."""

    if not isinstance(archive_payload, bytes) or not archive_payload:
        raise DeliveryLocalError("package archive is missing or empty")
    if not isinstance(manifest_payload, bytes) or not manifest_payload:
        raise DeliveryLocalError("canonical package manifest is missing or empty")
    compression_type, _ = _compression_values(compression, compression_level)
    entries = tuple(sorted(expected_entries, key=lambda item: item.path))
    if not entries or not all(isinstance(item, PackageVerificationEntry) for item in entries):
        raise DeliveryLocalError("archive expected entries are invalid")
    paths = tuple(item.path for item in entries)
    if (
        len(paths) != len(set(path.casefold() for path in paths))
        or PACKAGE_MANIFEST_PATH.casefold() in {path.casefold() for path in paths}
    ):
        raise DeliveryLocalError("archive expected paths are duplicate or reserved")
    _require_no_path_conflicts(paths)
    expected = {item.path: item for item in entries}
    expected_names = {PACKAGE_MANIFEST_PATH, *expected}
    read_payloads: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(BytesIO(archive_payload), mode="r") as archive:
            if archive.comment:
                raise DeliveryLocalError("package archive comment is not canonical")
            infos = tuple(archive.infolist())
            names = tuple(info.filename for info in infos)
            if (
                len(names) != len(set(names))
                or len(names) != len(set(name.casefold() for name in names))
            ):
                raise DeliveryLocalError("package archive contains duplicate entries")
            for name in names:
                _safe_path(name, "archive entry path")
            _require_no_path_conflicts(names)
            if set(names) != expected_names:
                raise DeliveryLocalError("package archive has missing or unexpected entries")
            for info in infos:
                if info.is_dir() or info.filename.endswith("/"):
                    raise DeliveryLocalError("package archive contains a directory entry")
                if info.flag_bits & 0x1:
                    raise DeliveryLocalError("encrypted package entries are forbidden")
                if (
                    info.create_system != 3
                    or info.date_time != _ZIP_TIME
                    or info.extra
                    or info.comment
                    or info.compress_type != compression_type
                ):
                    raise DeliveryLocalError("package archive metadata is not canonical")
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_IFMT(mode) != stat.S_IFREG:
                    raise DeliveryLocalError("package archive contains a symlink or special entry")
                expected_permission = (
                    "0644"
                    if info.filename == PACKAGE_MANIFEST_PATH
                    else expected[info.filename].permission
                )
                if stat.S_IMODE(mode) != int(expected_permission, 8):
                    raise DeliveryLocalError("package archive entry permission changed")
                expected_size = (
                    len(manifest_payload)
                    if info.filename == PACKAGE_MANIFEST_PATH
                    else expected[info.filename].size_bytes
                )
                if info.file_size != expected_size:
                    raise DeliveryLocalError("package archive entry size changed")
                payload = archive.read(info)
                if len(payload) != expected_size:
                    raise DeliveryLocalError("package archive entry is truncated")
                expected_digest = (
                    _sha256(manifest_payload)
                    if info.filename == PACKAGE_MANIFEST_PATH
                    else expected[info.filename].content_sha256
                )
                if _sha256(payload) != expected_digest:
                    raise DeliveryLocalError("package archive entry digest changed")
                if info.filename == PACKAGE_MANIFEST_PATH and payload != manifest_payload:
                    raise DeliveryLocalError("embedded package manifest changed")
                read_payloads[info.filename] = payload
    except DeliveryLocalError:
        raise
    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        RuntimeError,
        EOFError,
        OSError,
        NotImplementedError,
        zlib.error,
    ) as exc:
        raise DeliveryLocalError("package archive is corrupt or unreadable") from exc
    canonical_materials = [
        _ArchiveMaterial(PACKAGE_MANIFEST_PATH, manifest_payload, "0644")
    ]
    canonical_materials.extend(
        _ArchiveMaterial(item.path, read_payloads[item.path], item.permission)
        for item in entries
    )
    canonical = _build_archive(
        canonical_materials,
        compression=compression,
        compression_level=compression_level,
    )
    if canonical != archive_payload:
        raise DeliveryLocalError("package archive byte order or encoding is not canonical")
    return ArchiveVerification(
        _sha256(archive_payload),
        len(archive_payload),
        compression,
        compression_level,
        entries,
        _sha256(manifest_payload),
        True,
    )


@dataclass(frozen=True)
class _ResolvedInput:
    contract: DeliveryArtifactContentRef
    artifact: Artifact
    content_ref: ContentRef
    payload: bytes


@dataclass(frozen=True)
class _JournalRecord:
    request_digest: str
    producer_fence: int
    manifest_artifact_ref: str | None
    archive_artifact_ref: str | None
    signature_artifact_ref: str | None
    evidence_artifact_ref: str | None


class DeterministicLocalDeliveryTool:
    """Provider-neutral local package node using existing scheduling authorities."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        access: ProjectAccess,
        dispatch: ScheduledDispatch,
        tool_ref: str = "tool://minitz/local-delivery/1.0.0",
        runtime_ref: str = "runtime://minitz/local-delivery/python-stdlib/1",
    ) -> None:
        if not isinstance(access, ProjectAccess):
            raise DeliveryLocalError("exact ProjectAccess is required")
        if not isinstance(dispatch, ScheduledDispatch):
            raise DeliveryLocalError("exact ScheduledDispatch is required")
        if not isinstance(object_store, ObjectStorageBackend):
            raise DeliveryLocalError("ObjectStorageBackend is required")
        _absolute_ref(tool_ref, "tool_ref")
        _absolute_ref(runtime_ref, "runtime_ref")
        self.database_path = Path(database_path)
        self.objects = object_store
        self.access = access
        self.project_ref = access.project_ref
        self.dispatch = dispatch
        self.tool_ref = tool_ref
        self.runtime_ref = runtime_ref
        self.artifacts = ArtifactService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self._initialize_journal()

    def _initialize_journal(self) -> None:
        try:
            with sqlite3.connect(self.database_path, timeout=30.0) as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS delivery_local_package_journal (
                        project_ref TEXT NOT NULL,
                        node_attempt_id TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        request_digest TEXT NOT NULL,
                        producer_fence INTEGER NOT NULL,
                        manifest_artifact_ref TEXT,
                        archive_artifact_ref TEXT,
                        signature_artifact_ref TEXT,
                        evidence_artifact_ref TEXT,
                        PRIMARY KEY(project_ref, node_attempt_id, idempotency_key)
                    )
                    """
                )
        except sqlite3.Error as exc:
            raise DeliveryLocalError("local package replay journal is unavailable") from exc

    def _require_dispatch(
        self,
        dispatch: ScheduledDispatch,
        producer_attempt_id: str,
        producer_fence: int,
    ) -> NodeExecutionAttempt:
        if not isinstance(dispatch, ScheduledDispatch):
            raise DeliveryLocalError("exact ScheduledDispatch is required")
        allocation, attempt = dispatch.allocation, dispatch.node_attempt
        if (
            allocation.project_ref != self.project_ref
            or attempt.node_ref.project_ref != self.project_ref
            or producer_attempt_id != attempt.attempt_id
            or producer_fence != attempt.fence
        ):
            raise DeliveryLocalError("package producer attempt/fence crossed authority")
        if (
            allocation.status != "DISPATCHED"
            or allocation.node_ref != attempt.node_ref
            or allocation.run_ref != attempt.run_ref
            or allocation.run_attempt_id != attempt.run_attempt_id
            or allocation.run_attempt_fence != attempt.run_fence
            or allocation.node_attempt_id != attempt.attempt_id
            or allocation.node_attempt_fence != attempt.fence
            or allocation.owner_ref != attempt.owner_ref
            or allocation.lease_expires_at is None
        ):
            raise DeliveryLocalError("package dispatch allocation/attempt evidence is stale")
        try:
            current = self.executions.get_node_execution(self.access, attempt.node_ref)
        except NodeExecutionError as exc:
            raise DeliveryLocalError("package Node attempt evidence is unavailable") from exc
        if (
            current.status in {"CANCELLED", "FAILED", "SUCCEEDED"}
            or current.current_attempt_id != attempt.attempt_id
            or current.current_fence != attempt.fence
            or current.current_owner_ref != attempt.owner_ref
            or current.current_run_attempt_id != attempt.run_attempt_id
            or current.current_run_fence != attempt.run_fence
            or current.run_ref != attempt.run_ref
            or current.task_ref != attempt.task_ref
            or current.task_digest != attempt.task_digest
        ):
            raise DeliveryLocalError("package Node attempt is not current")
        try:
            node_expiry = datetime.fromisoformat(attempt.lease_expires_at)
            allocation_expiry = datetime.fromisoformat(allocation.lease_expires_at)
            now = datetime.now(node_expiry.tzinfo)
        except (TypeError, ValueError) as exc:
            raise DeliveryLocalError("package dispatch lease is malformed") from exc
        if node_expiry <= now or allocation_expiry <= now:
            raise DeliveryLocalError("package dispatch lease is stale")
        return attempt

    def _producer(self, attempt: NodeExecutionAttempt) -> ExecutionAttempt:
        run = self.artifacts.runs.get_run(self.access, attempt.run_ref)
        if (
            run.status != "RUNNING"
            or run.current_attempt_id != attempt.run_attempt_id
            or run.current_fence != attempt.run_fence
            or run.task_ref != attempt.task_ref
            or run.task_digest != attempt.task_digest
        ):
            raise DeliveryLocalError("package producer Run authority is stale")
        matches = tuple(
            candidate
            for candidate in self.artifacts.runs.list_attempts(self.access, attempt.run_ref)
            if candidate.attempt_id == attempt.run_attempt_id
            and candidate.fence == attempt.run_fence
            and candidate.completed_at is None
        )
        if len(matches) != 1:
            raise DeliveryLocalError("package producer Run attempt/fence is stale")
        return matches[0]

    def _resolve_input(self, source: DeliveryArtifactContentRef) -> _ResolvedInput:
        if not isinstance(source, DeliveryArtifactContentRef) or source.project_ref != self.project_ref:
            raise DeliveryLocalError("package source crossed Project scope")
        try:
            artifact = self.artifacts.get_artifact(self.access, source.artifact_ref)
        except ArtifactError as exc:
            raise DeliveryLocalError("package source Artifact is missing or stale") from exc
        content = artifact.content_ref
        if content is None or content != source.content_ref:
            raise DeliveryLocalError("package source Artifact/Content identity changed")
        try:
            if not self.objects.verify(content):
                raise DeliveryLocalError("package source Content is missing or corrupt")
            payload = self.objects.read(content)
            content.verify(payload)
        except (ArtifactError, ObjectStorageError) as exc:
            raise DeliveryLocalError("package source Content is missing or corrupt") from exc
        return _ResolvedInput(source, artifact, content, payload)

    def _revalidate_sources(self, values: Sequence[_ResolvedInput]) -> None:
        for item in values:
            try:
                if not self.objects.verify(item.content_ref):
                    raise DeliveryLocalError("package source mutated during assembly")
                payload = self.objects.read(item.content_ref)
                item.content_ref.verify(payload)
            except (ArtifactError, ObjectStorageError) as exc:
                raise DeliveryLocalError("package source mutated during assembly") from exc
            if payload != item.payload:
                raise DeliveryLocalError("package source mutated during assembly")

    @staticmethod
    def _unique_artifact_refs(values: Sequence[ArtifactRef]) -> tuple[ArtifactRef, ...]:
        return tuple(sorted(set(values), key=lambda value: value.value))

    @staticmethod
    def _unique_content_refs(values: Sequence[ContentRef]) -> tuple[ContentRef, ...]:
        unique: dict[tuple[str, str, int], ContentRef] = {}
        for value in values:
            unique[(value.algorithm, value.digest, value.size_bytes)] = value
        return tuple(unique[key] for key in sorted(unique))

    def _publish(
        self,
        *,
        role: str,
        payload: bytes,
        media_type: str,
        sources: Sequence[_ResolvedInput],
        derivation: str,
        request_digest: str,
    ) -> DeliveryArtifactContentRef:
        attempt = self._require_dispatch(
            self.dispatch,
            self.dispatch.node_attempt.attempt_id,
            self.dispatch.node_attempt.fence,
        )
        producer = self._producer(attempt)
        try:
            content = self.objects.put(
                payload,
                media_type=media_type,
                expected_digest=_sha256(payload),
                expected_size=len(payload),
            )
            if not self.objects.verify(content) or self.objects.read(content) != payload:
                raise DeliveryLocalError("fresh package Content verification failed")
        except ObjectStorageError as exc:
            raise DeliveryLocalError("fresh package Content verification failed") from exc
        artifact = self.artifacts.publish_from_run(
            self.access,
            producer_attempt=producer,
            expected_task_ref=attempt.task_ref,
            expected_task_digest=attempt.task_digest,
            role=role,
            content_ref=content,
            source_refs=(),
            source_artifact_refs=self._unique_artifact_refs(
                tuple(item.artifact.artifact_ref for item in sources)
            ),
            source_content_refs=self._unique_content_refs(
                tuple(item.content_ref for item in sources)
            ),
            derivation_type=derivation,
            metadata={
                "media_type": media_type,
                "schema_ref": "schema://minitz/delivery-local-artifact/1",
                "schema_version": "1.0.0",
            },
        )
        reopened = self.artifacts.get_artifact(self.access, artifact.artifact_ref)
        try:
            reopened_payload = self.objects.read(content)
        except ObjectStorageError as exc:
            raise DeliveryLocalError("fresh package Artifact verification failed") from exc
        if reopened.content_ref != content or reopened_payload != payload:
            raise DeliveryLocalError("fresh package Artifact verification failed")
        return DeliveryArtifactContentRef(artifact.artifact_ref, content)

    def _resolve_output(
        self, value: str, *, role: str, expected_payload: bytes
    ) -> _ResolvedInput:
        reference = self._artifact_ref(value)
        try:
            artifact = self.artifacts.get_artifact(self.access, reference)
        except ArtifactError as exc:
            raise DeliveryLocalError("journaled package Artifact is missing") from exc
        content = artifact.content_ref
        if artifact.role != role or content is None:
            raise DeliveryLocalError("journaled package Artifact role/content changed")
        try:
            if not self.objects.verify(content):
                raise DeliveryLocalError("journaled package Content is corrupt")
            payload = self.objects.read(content)
            content.verify(payload)
        except (ArtifactError, ObjectStorageError) as exc:
            raise DeliveryLocalError("journaled package Content is corrupt") from exc
        if payload != expected_payload:
            raise DeliveryLocalError("journaled package payload does not match replay")
        contract = DeliveryArtifactContentRef(reference, content)
        return _ResolvedInput(contract, artifact, content, payload)

    def _artifact_ref(self, value: str) -> ArtifactRef:
        parts = value.rsplit("/", 2)
        if len(parts) != 3 or parts[0] != f"artifact://{self.project_ref.value}":
            raise DeliveryLocalError("journaled ArtifactRef crossed Project scope")
        try:
            return ArtifactRef(self.project_ref, parts[1], int(parts[2]))
        except (TypeError, ValueError) as exc:
            raise DeliveryLocalError("journaled ArtifactRef is malformed") from exc

    def _package_manifest(
        self, request: LocalPackageRequest, attempt: NodeExecutionAttempt
    ) -> PackageManifest:
        entries = tuple(
            PackageEntry(
                item.entry_path,
                item.source.content_ref.digest,
                item.source.content_ref.size_bytes,
                item.source.content_ref.media_type,
                item.permission,
                "forbid",
                None,
            )
            for item in request.inputs
        )
        toolchains = {
            "local-package-runtime": self.tool_ref,
            **dict(request.toolchains),
        }
        signing_ref = (
            None if request.config.signing is None else request.config.signing.metadata_ref
        )
        return PackageManifest.create(
            self.project_ref,
            request.package_id,
            attempt.task_ref,
            attempt.run_ref,
            attempt.node_ref.graph_ref,
            request.package_type,
            request.target_ref,
            tuple(item.source for item in request.inputs),
            entries,
            request.source_version_ref,
            request.build_version_ref,
            toolchains,
            request.config.config_sha256,
            signing_ref,
            request.created_at,
        )

    @staticmethod
    def _manifest_payload(
        manifest: PackageManifest, request: LocalPackageRequest
    ) -> bytes:
        payload = {
            "bindings": [
                {
                    "entry": entry.payload(),
                    "source": package_input.source.payload(),
                }
                for entry, package_input in zip(
                    manifest.entries, request.inputs, strict=True
                )
            ],
            "build_version_ref": manifest.build_version_ref,
            "config_sha256": manifest.config_sha256,
            "created_at": manifest.created_at,
            "entries": [item.payload() for item in manifest.entries],
            "entry_order": [item.path for item in manifest.entries],
            "graph_ref": manifest.graph_ref.value,
            "manifest_digest": manifest.manifest_digest,
            "package_id": manifest.package_id,
            "package_type": manifest.package_type,
            "project_ref": manifest.project_ref.value,
            "run_ref": f"run://{manifest.run_ref.project_ref.value}/{manifest.run_ref.run_id}",
            "schema_ref": "schema://minitz/delivery-local-package-manifest/1",
            "schema_version": "1.0.0",
            "signing_metadata_ref": manifest.signing_metadata_ref,
            "source_version_ref": manifest.source_version_ref,
            "sources": [item.payload() for item in manifest.sources],
            "target_ref": manifest.target_ref,
            "task_ref": (
                f"task://{manifest.task_ref.project_ref.value}/"
                f"{manifest.task_ref.task_id}/{manifest.task_ref.revision}"
            ),
            "toolchains": dict(manifest.toolchains),
        }
        return _json_bytes(payload)

    def _request_digest(
        self, request: LocalPackageRequest, manifest: PackageManifest
    ) -> str:
        return _sha256(
            _json_bytes(
                {
                    "manifest_digest": manifest.manifest_digest,
                    "request": request.payload(),
                    "runtime_ref": self.runtime_ref,
                    "tool_ref": self.tool_ref,
                    "tool_version": _VERSION,
                }
            )
        )

    def _claim(
        self, request: LocalPackageRequest, attempt: NodeExecutionAttempt, digest: str
    ) -> _JournalRecord:
        try:
            with sqlite3.connect(self.database_path, timeout=30.0) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT OR IGNORE INTO delivery_local_package_journal(
                        project_ref, node_attempt_id, idempotency_key,
                        request_digest, producer_fence
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.project_ref.value,
                        attempt.attempt_id,
                        request.idempotency_key,
                        digest,
                        attempt.fence,
                    ),
                )
                raw = connection.execute(
                    """
                    SELECT request_digest, producer_fence, manifest_artifact_ref,
                           archive_artifact_ref, signature_artifact_ref,
                           evidence_artifact_ref
                    FROM delivery_local_package_journal
                    WHERE project_ref = ? AND node_attempt_id = ? AND idempotency_key = ?
                    """,
                    (
                        self.project_ref.value,
                        attempt.attempt_id,
                        request.idempotency_key,
                    ),
                ).fetchone()
        except sqlite3.Error as exc:
            raise DeliveryLocalError("local package replay claim failed") from exc
        row = cast(tuple[object, ...] | None, raw)
        if row is None or len(row) != 6:
            raise DeliveryLocalError("local package replay claim disappeared")
        request_digest, fence, manifest_ref, archive_ref, signature_ref, evidence_ref = row
        if (
            not isinstance(request_digest, str)
            or not isinstance(fence, int)
            or any(
                item is not None and not isinstance(item, str)
                for item in (manifest_ref, archive_ref, signature_ref, evidence_ref)
            )
        ):
            raise DeliveryLocalError("local package replay journal is malformed")
        if request_digest != digest:
            raise DeliveryLocalError("idempotency key was reused for a different package")
        if fence != attempt.fence:
            raise DeliveryLocalError("replay journal fence is stale")
        return _JournalRecord(
            request_digest,
            fence,
            cast(str | None, manifest_ref),
            cast(str | None, archive_ref),
            cast(str | None, signature_ref),
            cast(str | None, evidence_ref),
        )

    def _save_refs(
        self,
        request: LocalPackageRequest,
        attempt: NodeExecutionAttempt,
        digest: str,
        *,
        manifest_ref: str | None = None,
        archive_ref: str | None = None,
        signature_ref: str | None = None,
        evidence_ref: str | None = None,
    ) -> None:
        assignments: list[str] = []
        values: list[object] = []
        for column, value in (
            ("manifest_artifact_ref", manifest_ref),
            ("archive_artifact_ref", archive_ref),
            ("signature_artifact_ref", signature_ref),
            ("evidence_artifact_ref", evidence_ref),
        ):
            if value is not None:
                assignments.append(f"{column} = ?")
                values.append(value)
        if not assignments:
            return
        values.extend(
            (
                self.project_ref.value,
                attempt.attempt_id,
                request.idempotency_key,
                digest,
                attempt.fence,
            )
        )
        try:
            with sqlite3.connect(self.database_path, timeout=30.0) as connection:
                cursor = connection.execute(
                    f"""
                    UPDATE delivery_local_package_journal
                    SET {', '.join(assignments)}
                    WHERE project_ref = ? AND node_attempt_id = ?
                      AND idempotency_key = ? AND request_digest = ?
                      AND producer_fence = ?
                    """,
                    values,
                )
                if cursor.rowcount != 1:
                    raise DeliveryLocalError("local package replay update lost authority")
        except sqlite3.Error as exc:
            raise DeliveryLocalError("local package replay update failed") from exc

    def _local_package(
        self,
        record: _JournalRecord,
        request: LocalPackageRequest,
        manifest: PackageManifest,
        manifest_payload: bytes,
        archive_payload: bytes,
        verification: ArchiveVerification,
        resolved: Sequence[_ResolvedInput],
        request_digest: str,
        attempt: NodeExecutionAttempt,
    ) -> tuple[PreservedLocalPackage, _ResolvedInput, _ResolvedInput]:
        if (record.manifest_artifact_ref is None) != (record.archive_artifact_ref is None):
            raise DeliveryLocalError("replay journal contains an incomplete local package")
        if record.manifest_artifact_ref is None:
            manifest_ref = self._publish(
                role="delivery.manifest",
                payload=manifest_payload,
                media_type="application/vnd.minitz.delivery-manifest+json",
                sources=resolved,
                derivation="delivery.package.manifest",
                request_digest=request_digest,
            )
            manifest_resolved = self._resolve_input(manifest_ref)
            archive_ref = self._publish(
                role="delivery.archive",
                payload=archive_payload,
                media_type="application/zip",
                sources=(*resolved, manifest_resolved),
                derivation="delivery.package.archive",
                request_digest=request_digest,
            )
            archive_resolved = self._resolve_input(archive_ref)
            self._save_refs(
                request,
                attempt,
                request_digest,
                manifest_ref=manifest_ref.artifact_ref.value,
                archive_ref=archive_ref.artifact_ref.value,
            )
        else:
            manifest_resolved = self._resolve_output(
                record.manifest_artifact_ref,
                role="delivery.manifest",
                expected_payload=manifest_payload,
            )
            archive_resolved = self._resolve_output(
                cast(str, record.archive_artifact_ref),
                role="delivery.archive",
                expected_payload=archive_payload,
            )
            verify_local_archive(
                archive_resolved.payload,
                manifest_payload=manifest_resolved.payload,
                expected_entries=verification.entries,
                compression=request.config.compression,
                compression_level=request.config.compression_level,
            )
        preserved = PreservedLocalPackage(
            self.project_ref,
            request_digest,
            manifest_resolved.contract,
            archive_resolved.contract,
            manifest,
            verification,
            attempt.attempt_id,
            attempt.fence,
        )
        return preserved, manifest_resolved, archive_resolved

    def _validate_structure(
        self,
        request: LocalPackageRequest,
        manifest: PackageManifest,
        staged: Mapping[str, bytes],
        validator: InstallableStructuralValidator | None,
    ) -> Mapping[str, str]:
        expected_ref = request.config.validator_ref
        if expected_ref is None:
            if validator is not None:
                raise DeliveryLocalError("unexpected structural validator was supplied")
            return MappingProxyType({"status": "not-requested"})
        if validator is None or validator.validator_ref != expected_ref:
            raise DeliveryLocalError("exact configured structural validator is unavailable")
        try:
            result = validator.validate(manifest, staged)
        except Exception:
            raise DeliveryLocalError("structural package validation failed") from None
        return _string_map(result, "structural validator result")

    def _signature_report(
        self,
        request_digest: str,
        manifest: PackageManifest,
        archive_verification: ArchiveVerification,
        spec: HmacSha256SigningSpec,
        resolver: SecretResolver | None,
    ) -> tuple[bytes, Mapping[str, object]]:
        if resolver is None:
            raise DeliveryLocalError("configured HMAC secret resolver is unavailable")
        signed_payload = {
            "algorithm": "HMAC-SHA256",
            "archive_sha256": archive_verification.archive_sha256,
            "key_ref": spec.key_ref,
            "manifest_digest": manifest.manifest_digest,
            "request_digest": request_digest,
            "signer_ref": spec.signer_ref,
        }
        message = _json_bytes(signed_payload)
        try:
            resolved_secret = resolver.resolve_secret(self.access, spec.key_ref)
        except Exception:
            raise DeliveryLocalError("HMAC secret resolution failed") from None
        if not isinstance(resolved_secret, bytes) or not 16 <= len(resolved_secret) <= 4096:
            raise DeliveryLocalError("HMAC resolver returned invalid key material")
        key = bytearray(resolved_secret)
        del resolved_secret
        try:
            signature = hmac.new(key, message, hashlib.sha256).hexdigest()
            verified = hmac.compare_digest(
                signature, hmac.new(key, message, hashlib.sha256).hexdigest()
            )
        finally:
            for index in range(len(key)):
                key[index] = 0
        if not verified:
            raise DeliveryLocalError("HMAC signature verification failed")
        report: Mapping[str, object] = MappingProxyType(
            {
                "algorithm": "HMAC-SHA256",
                "key_ref": spec.key_ref,
                "signature_hex": signature,
                "signed_payload": signed_payload,
                "signer_ref": spec.signer_ref,
                "verified_after_signing": True,
            }
        )
        return _json_bytes(dict(report)), report

    def _evidence_payload(
        self,
        request: LocalPackageRequest,
        preserved: PreservedLocalPackage,
        secret_scan: SecretScanEvidence,
        structural_validation: Mapping[str, str],
        signature_ref: DeliveryArtifactContentRef | None,
        signature_report: Mapping[str, object] | None,
        attempt: NodeExecutionAttempt,
    ) -> bytes:
        return _json_bytes(
            {
                "archive_verification": preserved.archive_verification.payload(),
                "authority": {
                    "node_ref": attempt.node_ref.value,
                    "producer_attempt_id": attempt.attempt_id,
                    "producer_fence": attempt.fence,
                    "project_ref": self.project_ref.value,
                    "run_ref": f"run://{attempt.run_ref.project_ref.value}/{attempt.run_ref.run_id}",
                    "task_ref": (
                        f"task://{attempt.task_ref.project_ref.value}/"
                        f"{attempt.task_ref.task_id}/{attempt.task_ref.revision}"
                    ),
                },
                "external_publish_ready": True,
                "local_artifacts": {
                    "archive": preserved.archive.payload(),
                    "manifest": preserved.manifest.payload(),
                    "signature": None if signature_ref is None else signature_ref.payload(),
                },
                "manifest_digest": preserved.package_manifest.manifest_digest,
                "request_digest": preserved.request_digest,
                "schema_ref": "schema://minitz/delivery-local-verification/1",
                "schema_version": "1.0.0",
                "secret_scan": secret_scan.payload(),
                "signature": None if signature_report is None else dict(signature_report),
                "source_mapping": [item.payload() for item in request.inputs],
                "structural_validation": dict(structural_validation),
                "tool_ref": self.tool_ref,
                "tool_version": _VERSION,
            }
        )

    def assemble(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: LocalPackageRequest,
        *,
        validator: InstallableStructuralValidator | None = None,
        secret_resolver: SecretResolver | None = None,
    ) -> LocalPackageResult:
        if access != self.access or attempt != self.dispatch.node_attempt:
            raise DeliveryLocalError("package execution differs from bound Project/attempt")
        active = self._require_dispatch(self.dispatch, attempt.attempt_id, attempt.fence)
        if not isinstance(request, LocalPackageRequest) or request.project_ref != self.project_ref:
            raise DeliveryLocalError("package request crossed Project scope")
        resolved = tuple(self._resolve_input(item.source) for item in request.inputs)
        staged = MappingProxyType(
            {item.entry_path: source.payload for item, source in zip(request.inputs, resolved, strict=True)}
        )
        manifest = self._package_manifest(request, active)
        manifest_payload = self._manifest_payload(manifest, request)
        expected_entries = tuple(
            PackageVerificationEntry(
                item.entry_path,
                source.content_ref.digest,
                source.content_ref.size_bytes,
                source.content_ref.media_type,
                item.permission,
            )
            for item, source in zip(request.inputs, resolved, strict=True)
        )
        materials = [_ArchiveMaterial(PACKAGE_MANIFEST_PATH, manifest_payload, "0644")]
        materials.extend(
            _ArchiveMaterial(item.entry_path, source.payload, item.permission)
            for item, source in zip(request.inputs, resolved, strict=True)
        )
        archive_payload = _build_archive(
            materials,
            compression=request.config.compression,
            compression_level=request.config.compression_level,
        )
        archive_verification = verify_local_archive(
            archive_payload,
            manifest_payload=manifest_payload,
            expected_entries=expected_entries,
            compression=request.config.compression,
            compression_level=request.config.compression_level,
        )
        self._revalidate_sources(resolved)
        request_digest = self._request_digest(request, manifest)
        record = self._claim(request, active, request_digest)
        preserved, manifest_resolved, archive_resolved = self._local_package(
            record,
            request,
            manifest,
            manifest_payload,
            archive_payload,
            archive_verification,
            resolved,
            request_digest,
            active,
        )
        findings: tuple[SecretFinding, ...] = ()
        try:
            secret_scan = scan_for_obvious_secrets(
                staged, limit_bytes=request.config.secret_scan_limit_bytes
            )
            findings = secret_scan.findings
            if not secret_scan.completed or secret_scan.findings:
                raise DeliveryLocalPostPackageError(
                    "bounded obvious-secret scan rejected external publication readiness",
                    preserved,
                    secret_scan.findings,
                )
            structural = self._validate_structure(request, manifest, staged, validator)
            signature_ref: DeliveryArtifactContentRef | None = None
            signature_resolved: _ResolvedInput | None = None
            signature_report: Mapping[str, object] | None = None
            signing = request.config.signing
            if signing is None:
                if record.signature_artifact_ref is not None:
                    raise DeliveryLocalError("replay journal fabricated an unconfigured signature")
            else:
                signature_payload, signature_report = self._signature_report(
                    request_digest,
                    manifest,
                    archive_verification,
                    signing,
                    secret_resolver,
                )
                if record.signature_artifact_ref is None:
                    signature_ref = self._publish(
                        role="delivery.signature",
                        payload=signature_payload,
                        media_type="application/vnd.minitz.delivery-signature+json",
                        sources=(manifest_resolved, archive_resolved),
                        derivation="delivery.package.sign.hmac-sha256",
                        request_digest=request_digest,
                    )
                    signature_resolved = self._resolve_input(signature_ref)
                    self._save_refs(
                        request,
                        active,
                        request_digest,
                        signature_ref=signature_ref.artifact_ref.value,
                    )
                else:
                    signature_resolved = self._resolve_output(
                        record.signature_artifact_ref,
                        role="delivery.signature",
                        expected_payload=signature_payload,
                    )
                    signature_ref = signature_resolved.contract
            evidence_payload = self._evidence_payload(
                request,
                preserved,
                secret_scan,
                structural,
                signature_ref,
                signature_report,
                active,
            )
            evidence_sources: tuple[_ResolvedInput, ...] = (
                *resolved,
                manifest_resolved,
                archive_resolved,
                *((signature_resolved,) if signature_resolved is not None else ()),
            )
            if record.evidence_artifact_ref is None:
                evidence_ref = self._publish(
                    role="delivery.validation-evidence",
                    payload=evidence_payload,
                    media_type="application/vnd.minitz.delivery-verification+json",
                    sources=evidence_sources,
                    derivation="delivery.package.verify",
                    request_digest=request_digest,
                )
                self._save_refs(
                    request,
                    active,
                    request_digest,
                    evidence_ref=evidence_ref.artifact_ref.value,
                )
            else:
                evidence_ref = self._resolve_output(
                    record.evidence_artifact_ref,
                    role="delivery.validation-evidence",
                    expected_payload=evidence_payload,
                ).contract
            return LocalPackageResult(
                preserved,
                evidence_ref,
                signature_ref,
                secret_scan,
                structural,
            )
        except DeliveryLocalPostPackageError:
            raise
        except DeliveryLocalError as exc:
            raise DeliveryLocalPostPackageError(
                "post-package verification failed; verified local package is preserved",
                preserved,
                findings,
            ) from exc
        except Exception:
            raise DeliveryLocalPostPackageError(
                "post-package verification failed; verified local package is preserved",
                preserved,
                findings,
            ) from None


__all__ = [
    "ArchiveVerification",
    "DeliveryLocalError",
    "DeliveryLocalPostPackageError",
    "DeterministicLocalDeliveryTool",
    "HmacSha256SigningSpec",
    "InstallableStructuralValidator",
    "LocalPackageConfig",
    "LocalPackageRequest",
    "LocalPackageResult",
    "PACKAGE_MANIFEST_PATH",
    "PackageInput",
    "PackageVerificationEntry",
    "PreservedLocalPackage",
    "RequiredEntriesValidator",
    "SecretFinding",
    "SecretResolver",
    "SecretScanEvidence",
    "scan_for_obvious_secrets",
    "verify_local_archive",
]
