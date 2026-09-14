"""MiniTZ-native credential, trust, privacy, integrity, and recovery boundary.

The boundary is deliberately provider-neutral and self-contained.  Raw
credential bytes may be supplied to :class:`CredentialVault` by a credential
subsystem, but they are never part of a reference, receipt, snapshot, cache,
evidence record, or recovery manifest.  All decisions are made from local
policy and exact digests; no external authority is consulted.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from typing import Any, TypeVar
from urllib.parse import parse_qsl, urlsplit


SCHEMA = "minitz.security_privacy_boundary/v1"
EVIDENCE_SCHEMA = "minitz.security_privacy_evidence/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REF = re.compile(r"credential://[a-z0-9][a-z0-9._:/-]{0,255}\Z")
_SAFE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,2048}\Z")
_SECRET_PARTS = frozenset({
    "API", "KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD", "CREDENTIAL",
    "COOKIE", "PRIVATE",
})
_SAFE_SENSITIVE_SUFFIXES = (
    "_REF", "_REFS", "_ID", "_IDS", "_DIGEST", "_DIGESTS", "_SHA256",
    "_STATE", "_STATUS", "_TYPE", "_SCOPE", "_COUNT", "_ALLOWED",
)
_T = TypeVar("_T")


class SecurityPrivacyError(ValueError):
    """Base error for a rejected MiniTZ security/privacy operation."""


class CredentialBoundaryError(SecurityPrivacyError):
    """A credential was malformed, leaked, or used outside its reference."""


class TrustError(SecurityPrivacyError):
    """A source was not trusted by the local MiniTZ trust store."""


class PrivacyError(SecurityPrivacyError):
    """A payload or destination would violate data residency."""


class NetworkPolicyError(SecurityPrivacyError):
    """Network use is disallowed by the local online/offline policy."""


class IntegrityError(SecurityPrivacyError):
    """Exact content or recovery state failed integrity verification."""


class RecoveryError(SecurityPrivacyError):
    """A recovery generation or rollback target is unavailable or unsafe."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SecurityPrivacyError("security payload is not canonical JSON") from exc


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_object(value: object) -> str:
    return _sha256(_canonical(value))


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise SecurityPrivacyError(f"{label} must be a SHA-256 digest")
    return value


def _require_reference(value: object, label: str = "reference") -> str:
    if not isinstance(value, str) or _SAFE_REF.fullmatch(value) is None:
        raise SecurityPrivacyError(f"{label} is malformed")
    return value


def _normalized_key(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(value).upper()).strip("_")


def _sensitive_key(value: object) -> bool:
    normalized = _normalized_key(value)
    if any(normalized.endswith(suffix) for suffix in _SAFE_SENSITIVE_SUFFIXES):
        return False
    return bool(set(normalized.split("_")) & _SECRET_PARTS)


def _credential_string(value: str) -> bool:
    lowered = value.lower()
    if "-----begin " in lowered and "private key-----" in lowered:
        return True
    if re.search(r"\bbearer\s+[a-z0-9._~+/=-]{8,}", value, re.I):
        return True
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.username is not None or parsed.password is not None:
        return True
    if parsed.scheme and parsed.netloc:
        return any(
            key.lower() in {"token", "secret", "password", "api_key", "apikey", "access_token", "refresh_token", "signature", "sig"}
            and bool(item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        )
    return False


def assert_privacy_safe(value: object, *, known_secrets: Iterable[bytes] = ()) -> object:
    """Reject raw secret fields and known secret bytes without returning them."""

    known_text = tuple(
        secret.decode("utf-8", errors="surrogateescape")
        for secret in known_secrets
        if isinstance(secret, bytes) and secret
    )

    def walk(item: object, key: object | None = None) -> None:
        normalized = _normalized_key(key) if key is not None else ""
        if normalized.endswith("_REF"):
            if not isinstance(item, str) or _SAFE_REF.fullmatch(item) is None:
                raise PrivacyError("reference field must contain an internal or external reference")
        elif normalized.endswith("_REFS"):
            if not isinstance(item, (list, tuple)) or any(
                not isinstance(ref, str) or _SAFE_REF.fullmatch(ref) is None for ref in item
            ):
                raise PrivacyError("reference list contains a malformed reference")
        elif normalized.endswith("_DIGEST"):
            _require_sha256(item, "digest field")
        elif normalized.endswith("_DIGESTS"):
            if not isinstance(item, (list, tuple)):
                raise PrivacyError("digest list is malformed")
            for digest in item:
                _require_sha256(digest, "digest field")
        if key is not None and _sensitive_key(key):
            if normalized == "RAW_CREDENTIAL_VALUES_IN_SEMANTIC_MEMORY" and item is False:
                pass
            else:
                raise PrivacyError("raw credential value is forbidden in privacy-safe data")
        if isinstance(item, Mapping):
            for child_key, child in item.items():
                walk(child, child_key)
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                walk(child)
            return
        if isinstance(item, str):
            if _credential_string(item) or any(secret in item for secret in known_text):
                raise PrivacyError("credential-bearing value is forbidden in privacy-safe data")
            return
        if isinstance(item, bytes) and any(secret and secret in item for secret in known_secrets):
            raise PrivacyError("credential-bearing bytes are forbidden in privacy-safe data")
        if isinstance(item, bytes):
            raise PrivacyError("binary payloads are forbidden in privacy-safe data")
        if item is None or isinstance(item, (bool, int, float)):
            return
        raise PrivacyError("payload contains an unsupported non-serializable value")

    walk(value)
    return value


class ResidencyDomain(StrEnum):
    CREDENTIAL_VAULT = "CREDENTIAL_VAULT"
    PRIVATE_MEMORY = "PRIVATE_MEMORY"
    PROJECT_MEMORY = "PROJECT_MEMORY"
    CACHE = "CACHE"
    EVIDENCE = "EVIDENCE"
    PUBLIC_ARTIFACT = "PUBLIC_ARTIFACT"


class DataResidencyPolicy:
    """Keep operational state inside MiniTZ and admit only safe references."""

    def validate(self, domain: ResidencyDomain, payload: object, *, known_secrets: Iterable[bytes] = ()) -> object:
        if not isinstance(domain, ResidencyDomain):
            raise PrivacyError("data-residency domain is malformed")
        # Raw values are never an admissible payload, including for the vault;
        # the vault accepts them only through CredentialVault.register/use.
        return assert_privacy_safe(payload, known_secrets=known_secrets)

    def authorize_export(self, domain: ResidencyDomain, destination: str) -> dict[str, str]:
        if not isinstance(domain, ResidencyDomain):
            raise PrivacyError("data-residency domain is malformed")
        _require_reference(destination, "residency destination")
        scheme = urlsplit(destination).scheme
        if scheme not in {"minitz", "unix"}:
            raise PrivacyError("MiniTZ state may not be exported to an external authority")
        return {"domain": domain.value, "destination": destination, "status": "ALLOW_INTERNAL"}


@dataclass(frozen=True)
class CredentialReference:
    """A non-secret handle to a credential owned by the MiniTZ vault."""

    ref: str
    digest: str
    scope: str
    state: str = "AVAILABLE"

    def __post_init__(self) -> None:
        if _REF.fullmatch(self.ref) is None:
            raise CredentialBoundaryError("credential reference is malformed")
        _require_sha256(self.digest, "credential digest")
        if not self.scope or any(ord(char) < 32 for char in self.scope):
            raise CredentialBoundaryError("credential scope is malformed")
        if self.state not in {"AVAILABLE", "DISABLED", "REVOKED", "UNAVAILABLE"}:
            raise CredentialBoundaryError("credential state is malformed")

    def as_dict(self) -> dict[str, str]:
        return {
            "ref": self.ref,
            "digest": self.digest,
            "scope": self.scope,
            "state": self.state,
        }


class CredentialVault:
    """In-process credential boundary; raw values cannot be serialized or read directly."""

    def __init__(self) -> None:
        self._values: dict[str, bytes] = {}
        self._references: dict[str, CredentialReference] = {}

    def register(self, ref: str, value: bytes, *, scope: str) -> CredentialReference:
        if _REF.fullmatch(ref) is None or not isinstance(value, bytes) or not value:
            raise CredentialBoundaryError("credential registration is malformed")
        digest = _sha256(value)
        reference = CredentialReference(ref=ref, digest=digest, scope=scope)
        self._values[ref] = bytes(value)
        self._references[ref] = reference
        return reference

    def reference(self, ref: str) -> CredentialReference:
        try:
            return self._references[ref]
        except KeyError as exc:
            raise CredentialBoundaryError("credential reference is unavailable") from exc

    def use(self, ref: str, consumer: Callable[[bytes], _T]) -> _T:
        """Use a credential only inside a caller-owned operation.

        The consumer result must already be privacy-safe.  Raw bytes returned
        by a consumer are rejected, and consumer failures are sanitized so a
        secret-bearing exception cannot cross this boundary.
        """

        reference = self.reference(ref)
        if reference.state != "AVAILABLE":
            raise CredentialBoundaryError("credential reference is not available")
        value = self._values[ref]
        if not hmac.compare_digest(_sha256(value), reference.digest):
            raise CredentialBoundaryError("credential vault integrity check failed")
        try:
            result = consumer(value)
        except Exception as exc:
            raise CredentialBoundaryError("credential consumer failed") from None
        if isinstance(result, (bytes, bytearray, memoryview)):
            raise CredentialBoundaryError("credential consumer returned raw bytes")
        assert_privacy_safe(result, known_secrets=(value,))
        return result

    def metadata(self) -> list[dict[str, str]]:
        return [self._references[key].as_dict() for key in sorted(self._references)]

    def __repr__(self) -> str:
        return "CredentialVault(<raw-values-hidden>)"


@dataclass(frozen=True)
class TrustReceipt:
    source_ref: str
    content_sha256: str
    anchor_id: str
    status: str

    def as_dict(self) -> dict[str, str]:
        return {
            "source_ref": self.source_ref,
            "content_sha256": self.content_sha256,
            "anchor_id": self.anchor_id,
            "status": self.status,
        }


class TrustStore:
    """Local trust anchors.  There is no provider, browser, or remote authority."""

    def __init__(self) -> None:
        self._anchors: dict[str, tuple[str, frozenset[str]]] = {}

    def add_anchor(self, anchor_id: str, source_ref: str, content_digests: Iterable[str]) -> None:
        if not anchor_id or any(ord(char) < 32 for char in anchor_id):
            raise TrustError("trust anchor is malformed")
        _require_reference(source_ref, "trusted source reference")
        digests = frozenset(_require_sha256(item, "trusted content digest") for item in content_digests)
        if not digests:
            raise TrustError("trust anchor has no content digest")
        self._anchors[anchor_id] = (source_ref, digests)

    def verify(self, source_ref: str, payload: bytes) -> TrustReceipt:
        _require_reference(source_ref, "source reference")
        observed = _sha256(payload)
        for anchor_id, (anchored_ref, digests) in self._anchors.items():
            if anchored_ref == source_ref and observed in digests:
                return TrustReceipt(source_ref, observed, anchor_id, "PASS")
        raise TrustError("source is not trusted by the local MiniTZ trust store")

    def verify_digest(self, source_ref: str, digest: str) -> TrustReceipt:
        _require_sha256(digest, "content digest")
        return self._verify_digest(source_ref, digest)

    def _verify_digest(self, source_ref: str, digest: str) -> TrustReceipt:
        _require_reference(source_ref, "source reference")
        for anchor_id, (anchored_ref, digests) in self._anchors.items():
            if anchored_ref == source_ref and digest in digests:
                return TrustReceipt(source_ref, digest, anchor_id, "PASS")
        raise TrustError("content digest is not trusted by the local MiniTZ trust store")

    def metadata(self) -> list[dict[str, object]]:
        return [
            {"anchor_id": anchor_id, "source_ref": source_ref, "content_digests": sorted(digests)}
            for anchor_id, (source_ref, digests) in sorted(self._anchors.items())
        ]


class NetworkMode(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class NetworkPolicy:
    """Local network/offline authorization with explicit internal and external routes."""

    def __init__(self, mode: NetworkMode = NetworkMode.ONLINE) -> None:
        self.mode = mode
        self._allowed_external: set[str] = set()

    def allow_external(self, destination: str) -> None:
        _require_reference(destination, "network destination")
        parsed = urlsplit(destination)
        if parsed.scheme in {"minitz", "unix"} or not parsed.netloc:
            raise NetworkPolicyError("only explicit external destinations may be allowlisted")
        if parsed.username is not None or parsed.password is not None or parsed.query:
            raise NetworkPolicyError("network destination contains private query or user data")
        self._allowed_external.add(destination)

    def authorize(self, operation: str, destination: str, *, requires_network: bool = True) -> dict[str, object]:
        if not operation or any(ord(char) < 32 for char in operation):
            raise NetworkPolicyError("network operation is malformed")
        _require_reference(destination, "network destination")
        parsed = urlsplit(destination)
        internal = parsed.scheme in {"minitz", "unix"}
        if internal and not requires_network:
            return {"operation": operation, "destination": destination, "mode": self.mode.value, "status": "ALLOW_INTERNAL"}
        if internal:
            return {"operation": operation, "destination": destination, "mode": self.mode.value, "status": "ALLOW_INTERNAL"}
        if not requires_network:
            return {"operation": operation, "destination": destination, "mode": self.mode.value, "status": "ALLOW_LOCAL"}
        if self.mode is NetworkMode.OFFLINE:
            raise NetworkPolicyError("external network use is denied in OFFLINE mode")
        if destination not in self._allowed_external:
            raise NetworkPolicyError("external destination is not locally allowlisted")
        return {"operation": operation, "destination": destination, "mode": self.mode.value, "status": "ALLOW_EXTERNAL"}


class IntegrityManifest:
    """Exact file identity for a recovery generation."""

    def __init__(self, generation: str, entries: Mapping[str, tuple[str, int, int]]) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", generation):
            raise IntegrityError("generation is malformed")
        normalized: dict[str, tuple[str, int, int]] = {}
        for relative, (digest, size, mode) in entries.items():
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or not relative or path.as_posix() != relative:
                raise IntegrityError("manifest path is unsafe")
            normalized[relative] = (_require_sha256(digest, "file digest"), int(size), int(mode))
        self.generation = generation
        self.entries = dict(sorted(normalized.items()))
        self.manifest_sha256 = _digest_object(self._payload())

    def _payload(self) -> dict[str, object]:
        return {"generation": self.generation, "entries": {
            path: {"sha256": digest, "size_bytes": size, "mode": mode}
            for path, (digest, size, mode) in self.entries.items()
        }}

    def as_dict(self) -> dict[str, object]:
        payload = self._payload()
        payload["manifest_sha256"] = self.manifest_sha256
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "IntegrityManifest":
        generation = payload.get("generation")
        raw_entries = payload.get("entries")
        if not isinstance(generation, str) or not isinstance(raw_entries, Mapping):
            raise IntegrityError("manifest is malformed")
        entries: dict[str, tuple[str, int, int]] = {}
        for relative, raw in raw_entries.items():
            if not isinstance(relative, str) or not isinstance(raw, Mapping):
                raise IntegrityError("manifest entry is malformed")
            entries[relative] = (str(raw.get("sha256")), int(raw.get("size_bytes", -1)), int(raw.get("mode", -1)))
        manifest = cls(generation, entries)
        if payload.get("manifest_sha256") != manifest.manifest_sha256:
            raise IntegrityError("manifest digest does not match payload")
        return manifest

    @classmethod
    def from_directory(cls, root: Path, generation: str) -> "IntegrityManifest":
        base = Path(root).resolve(strict=True)
        entries: dict[str, tuple[str, int, int]] = {}
        for path in sorted(item for item in base.rglob("*") if item.is_file() and not item.is_symlink()):
            relative = path.relative_to(base).as_posix()
            data = path.read_bytes()
            entries[relative] = (_sha256(data), len(data), stat.S_IMODE(path.stat().st_mode))
        return cls(generation, entries)

    def verify(self, root: Path) -> dict[str, object]:
        base = Path(root).resolve(strict=True)
        observed: dict[str, tuple[str, int, int]] = {}
        for relative, (expected_digest, expected_size, expected_mode) in self.entries.items():
            raw_target = base / relative
            if raw_target.is_symlink():
                raise IntegrityError("recovery generation contains a symlink")
            target = raw_target.resolve(strict=False)
            if base not in target.parents or not target.is_file():
                raise IntegrityError("recovery file is missing or escapes generation root")
            data = target.read_bytes()
            observed[relative] = (_sha256(data), len(data), stat.S_IMODE(target.stat().st_mode))
            if observed[relative] != (expected_digest, expected_size, expected_mode):
                raise IntegrityError("recovery file failed exact integrity verification")
        for item in base.rglob("*"):
            if item.is_symlink():
                raise IntegrityError("recovery generation contains a symlink")
            if item.is_file() and item.relative_to(base).as_posix() != "manifest.json":
                relative = item.relative_to(base).as_posix()
                if relative not in self.entries:
                    raise IntegrityError("recovery generation contains an unlisted file")
        if set(observed) != set(self.entries):
            raise IntegrityError("recovery generation file set differs from manifest")
        return {"generation": self.generation, "manifest_sha256": self.manifest_sha256, "status": "PASS", "file_count": len(self.entries)}


class RecoveryManager:
    """Atomic local generation publication and verified rollback."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.generations = self.root / "generations"
        self.pointer = self.root / "current.json"
        self.generations.mkdir(parents=True, exist_ok=True)

    def _read_pointer(self) -> dict[str, object]:
        if not self.pointer.is_file():
            raise RecoveryError("active recovery generation is unavailable")
        try:
            payload = json.loads(self.pointer.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RecoveryError("active recovery pointer is unreadable") from exc
        if not isinstance(payload, dict):
            raise RecoveryError("active recovery pointer is malformed")
        return payload

    def _generation(self, generation: str) -> tuple[Path, IntegrityManifest]:
        path = self.generations / generation
        manifest_path = path / "manifest.json"
        if not path.is_dir() or not manifest_path.is_file():
            raise RecoveryError("recovery generation is unavailable")
        try:
            manifest = IntegrityManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RecoveryError("recovery manifest is invalid") from exc
        if manifest.generation != generation:
            raise RecoveryError("recovery manifest generation mismatch")
        return path, manifest

    def publish(self, generation: str, source: Path, *, known_secrets: Iterable[bytes] = ()) -> dict[str, object]:
        source_path = Path(source).resolve(strict=True)
        if not source_path.is_dir():
            raise RecoveryError("recovery source is not a directory")
        secret_values = tuple(known_secrets)
        for item in source_path.rglob("*"):
            if item.is_symlink():
                raise RecoveryError("recovery source contains a symlink")
            if item.is_file():
                data = item.read_bytes()
                if any(secret and secret in data for secret in secret_values):
                    raise PrivacyError("recovery source contains a credential value")
        manifest = IntegrityManifest.from_directory(source_path, generation)
        temporary = Path(tempfile.mkdtemp(prefix=f".{generation}.", dir=self.generations))
        target = self.generations / generation
        try:
            for item in source_path.rglob("*"):
                relative = item.relative_to(source_path)
                destination = temporary / relative
                if item.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif item.is_file() and not item.is_symlink():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, destination)
            (temporary / "manifest.json").write_text(json.dumps(manifest.as_dict(), sort_keys=True) + "\n", encoding="utf-8")
            manifest.verify(temporary)
            if target.exists():
                raise RecoveryError("recovery generation already exists")
            os.replace(temporary, target)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return {"generation": generation, "manifest_sha256": manifest.manifest_sha256, "status": "PUBLISHED"}

    def activate(self, generation: str) -> dict[str, object]:
        path, manifest = self._generation(generation)
        receipt = manifest.verify(path)
        previous = None
        if self.pointer.is_file():
            previous = self._read_pointer().get("generation")
        payload = {"schema": "minitz.recovery_pointer/v1", "generation": generation, "previous_generation": previous, "manifest_sha256": manifest.manifest_sha256}
        temporary = self.pointer.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.pointer)
        return {**receipt, "status": "ACTIVE", "previous_generation": previous}

    def rollback(self) -> dict[str, object]:
        pointer = self._read_pointer()
        previous = pointer.get("previous_generation")
        if not isinstance(previous, str) or not previous:
            raise RecoveryError("no verified previous generation is available for rollback")
        return self.activate(previous)

    def verify_active(self) -> dict[str, object]:
        pointer = self._read_pointer()
        generation = pointer.get("generation")
        digest = pointer.get("manifest_sha256")
        if not isinstance(generation, str) or not isinstance(digest, str):
            raise RecoveryError("active recovery pointer is malformed")
        path, manifest = self._generation(generation)
        if not hmac.compare_digest(manifest.manifest_sha256, digest):
            raise IntegrityError("active recovery pointer digest differs from manifest")
        return manifest.verify(path)


class EvidenceRecorder:
    """Write only privacy-safe, digest-bound evidence records."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def record(self, name: str, payload: Mapping[str, object], *, implementation_refs: Sequence[str]) -> dict[str, object]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name):
            raise SecurityPrivacyError("evidence name is malformed")
        assert_privacy_safe(payload)
        refs = [_require_reference(item, "implementation reference") for item in implementation_refs]
        body = {"schema": EVIDENCE_SCHEMA, "name": name, "payload": dict(payload), "implementation_refs": refs}
        evidence_sha256 = _digest_object(body)
        receipt: dict[str, object] = {**body, "evidence_sha256": evidence_sha256}
        temporary = self.root / f".{name}.tmp"
        target = self.root / f"{name}.json"
        temporary.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
        return receipt


@dataclass(frozen=True)
class SecurityPrivacyBoundary:
    """One local composition point for the task's security/privacy guarantees."""

    credential_vault: CredentialVault
    trust_store: TrustStore
    network_policy: NetworkPolicy
    residency_policy: DataResidencyPolicy

    @classmethod
    def local(cls, *, network_mode: NetworkMode = NetworkMode.ONLINE) -> "SecurityPrivacyBoundary":
        return cls(CredentialVault(), TrustStore(), NetworkPolicy(network_mode), DataResidencyPolicy())

    def validate_evidence(self, payload: Mapping[str, object]) -> dict[str, object]:
        self.residency_policy.validate(ResidencyDomain.EVIDENCE, payload)
        return dict(payload)

    def contract(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "authority": "MINITZ_LOCAL_POLICY",
            "credential_values": "CREDENTIAL_VAULT_ONLY",
            "credential_references": "ALLOWED",
            "raw_secret_leakage": "FORBIDDEN",
            "data_residency": "MINITZ_INTERNAL",
            "trust": "LOCAL_DIGEST_ANCHORS",
            "integrity": "SHA256_EXACT_MANIFEST",
            "network": self.network_policy.mode.value,
            "recovery": "ATOMIC_GENERATIONS_VERIFIED_ROLLBACK",
            "external_authority": "NONE",
        }
