"""MiniTZ SECRET-01 private-state and secret-boundary contract.

This module carries only privacy-safe policy/receipt behavior.  It never opens the
live credential store, never migrates secrets, and never returns raw private bytes.
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlsplit

SCHEMA = "minitz.secret_private_boundary/v1"
FINGERPRINT_SCHEMA = "minitz.private_object_fingerprint/v1"
EXTRACTION_SCHEMA = "minitz.private_extraction_receipt/v1"
LEGACY_PROTECTED_SECRET_ROOT = Path("/root/.config/biella-ai")

_DOMAINS: dict[str, dict[str, Any]] = {
    "OWNER_PRIVATE_MEMORY": {"raw_credential_values_allowed": False, "universal_projection_allowed": False, "extractor_route": "OWNER_PRIVATE_ISOLATED"},
    "OWNER_PRIVATE_CACHE": {"raw_credential_values_allowed": False, "universal_projection_allowed": False, "extractor_route": "OWNER_PRIVATE_ISOLATED"},
    "API_SECRET_VAULT": {"raw_credential_values_allowed": True, "universal_projection_allowed": False, "extractor_route": "OWNER_PRIVATE_ISOLATED"},
    "CREDENTIAL_VAULT": {"raw_credential_values_allowed": True, "universal_projection_allowed": False, "extractor_route": "OWNER_PRIVATE_ISOLATED"},
    "PROJECT_MEMORY": {"raw_credential_values_allowed": False, "universal_projection_allowed": False, "extractor_route": "PROJECT_SCOPED"},
    "CUSTOMER_MEMORY": {"raw_credential_values_allowed": False, "universal_projection_allowed": False, "extractor_route": "CUSTOMER_SCOPED"},
    "PUBLIC_ENGINE_KNOWLEDGE": {"raw_credential_values_allowed": False, "universal_projection_allowed": True, "extractor_route": "ORDINARY_SAFE"},
}

_ALLOWED_SENSITIVE_METADATA_SUFFIXES = (
    "_REF", "_REFS", "_ID", "_IDS", "_DIGEST", "_DIGESTS", "_SHA256",
    "_STATE", "_STATUS", "_TYPE", "_SCOPE", "_COUNT", "_ALLOWED",
)
_FALSE_POLICY_METADATA_KEYS = frozenset(
    {
        "RAW_CREDENTIAL_VALUES_IN_SEMANTIC_MEMORY",
    }
)
_SAFE_METADATA_CONTAINER_KEYS = frozenset(
    {
        "SECRET_LEAK_RECEIPT",
    }
)
_SENSITIVE_SEGMENTS = {
    "SECRET", "TOKEN", "PASSWORD", "PASSWD", "APIKEY", "API_KEY",
    "PRIVATE_KEY", "CREDENTIAL", "CREDENTIALS", "COOKIE",
}
_SECRET_QUERY_KEYS = {
    "token", "secret", "password", "passwd", "api_key", "apikey",
    "access_key", "access_token", "refresh_token", "credential", "signature", "sig",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _domain(name: str) -> dict[str, Any]:
    key = str(name).strip().upper()
    if key not in _DOMAINS:
        raise ValueError(f"unknown private-state domain: {name}")
    return _DOMAINS[key]


def private_state_contract() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "authority": "MINITZ_PRIVATE_STATE_BOUNDARY",
        "domains": json.loads(json.dumps(_DOMAINS)),
        "raw_secret_values_outside_vaults": "FORBIDDEN",
        "ordinary_extractors_receive_raw_private_bytes": False,
    }


def ordinary_migration_allowed(path: str | Path, domain: str) -> bool:
    info = _domain(domain)
    resolved = Path(path).expanduser().resolve(strict=False)
    legacy = LEGACY_PROTECTED_SECRET_ROOT.resolve(strict=False)
    if resolved == legacy or legacy in resolved.parents:
        return False
    if str(domain).upper() in {"API_SECRET_VAULT", "CREDENTIAL_VAULT"}:
        return False
    return bool(info)


def private_object_fingerprint(path: Path) -> dict[str, Any]:
    target = Path(path).resolve(strict=True)
    data = target.read_bytes()
    mode = stat.S_IMODE(target.stat().st_mode)
    return {
        "schema": FINGERPRINT_SCHEMA,
        "path_sha256": _sha(str(target).encode("utf-8")),
        "content_sha256": _sha(data),
        "size_bytes": len(data),
        "mode_octal": f"{mode:04o}",
        "raw_bytes_emitted": False,
        "raw_path_emitted": False,
    }


def extractor_route(domain: str) -> str:
    return str(_domain(domain)["extractor_route"])


def _normalized_key(key: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(key).upper()).strip("_")


def _sensitive_key(key: object) -> bool:
    normalized = _normalized_key(key)
    if any(normalized.endswith(suffix) for suffix in _ALLOWED_SENSITIVE_METADATA_SUFFIXES):
        return False
    parts = set(normalized.split("_")) if normalized else set()
    return bool(parts & {"SECRET", "TOKEN", "PASSWORD", "PASSWD", "CREDENTIAL", "COOKIE"}) or normalized in _SENSITIVE_SEGMENTS


def _privacy_safe_sensitive_metadata(key: object, value: Any) -> bool:
    normalized = _normalized_key(key)
    if normalized in _FALSE_POLICY_METADATA_KEYS:
        return value is False
    return normalized in _SAFE_METADATA_CONTAINER_KEYS and isinstance(value, Mapping)


def _credential_bearing_string(value: str) -> bool:
    lowered = value.lower()
    if "-----begin " in lowered and "private key-----" in lowered:
        return True
    if re.search(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", value, re.I):
        return True
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme and parsed.netloc:
        if parsed.password is not None:
            return True
        for key, item in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in _SECRET_QUERY_KEYS and item:
                return True
    return False


def validate_privacy_safe_payload(payload: Any) -> Any:
    def walk(value: Any, key: object | None = None) -> None:
        if (
            key is not None
            and _sensitive_key(key)
            and not _privacy_safe_sensitive_metadata(key, value)
        ):
            raise ValueError(f"raw secret field forbidden in privacy-safe payload: {key}")
        if isinstance(value, Mapping):
            for child_key, child in value.items():
                walk(child, child_key)
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                walk(child)
            return
        if isinstance(value, str) and _credential_bearing_string(value):
            raise ValueError("credential-bearing value forbidden in privacy-safe payload")
    walk(payload)
    return payload


def filter_booster_memory(
    records: Sequence[Mapping[str, Any]], *, task_id: str, task_revision: int,
    task_sha256: str,
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for raw in records:
        row = dict(raw)
        if not row.get("source_ref") or not row.get("content_ref"):
            continue
        record_task = row.get("task_id")
        if record_task:
            if str(record_task) != str(task_id):
                continue
            if int(row.get("task_revision") or -1) != int(task_revision):
                continue
            if str(row.get("task_sha256") or "") != str(task_sha256):
                continue
        else:
            if str(row.get("scope_ref") or "") != "scope://minitz/system":
                continue
        validate_privacy_safe_payload(row)
        kept.append(row)
    return kept


def secret_migration_contract() -> dict[str, Any]:
    return {
        "schema": "minitz.secret_migration_contract/v1",
        "owner_authorization_required": True,
        "ordinary_filesystem_migration": False,
        "owner_input_mode": "INTERACTIVE_EPHEMERAL",
        "passphrase_persistence": "FORBIDDEN",
        "flow": [
            "OWNER_INTERACTIVE_INPUT", "KDF", "ROOT_KEK", "INDEPENDENT_DOMAIN_KEYS",
            "ENCRYPTED_IMPORT", "FUNCTIONAL_VALIDATE", "CUTOVER", "RETIRE_UNNEEDED_PLAINTEXT_DUPLICATE",
        ],
        "kdf_required": True,
        "root_kek_required": True,
        "independent_domain_keys": True,
        "raw_secret_values_in_task_state": False,
        "raw_secret_values_in_logs": False,
    }


def private_extraction_receipt(
    domain: str, fingerprint: Mapping[str, Any],
    semantic_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    _domain(domain)
    if str(fingerprint.get("schema") or "") != FINGERPRINT_SCHEMA:
        raise ValueError("invalid private object fingerprint")
    safe_results = [dict(item) for item in semantic_results]
    for item in safe_results:
        validate_privacy_safe_payload(item)
    safe_fingerprint = {
        key: fingerprint.get(key)
        for key in (
            "schema", "path_sha256", "content_sha256", "size_bytes", "mode_octal",
            "raw_bytes_emitted", "raw_path_emitted",
        )
    }
    receipt = {
        "schema": EXTRACTION_SCHEMA,
        "authority": "NONE",
        "domain": str(domain).upper(),
        "extractor_route": extractor_route(domain),
        "object_fingerprint": safe_fingerprint,
        "semantic_results": safe_results,
        "raw_bytes_emitted": False,
        "ordinary_log_safe": True,
    }
    validate_privacy_safe_payload(receipt)
    return receipt


def booster_context_policy() -> dict[str, Any]:
    return {
        "schema": "minitz.booster_privacy_context_policy/v1",
        "raw_credential_values_allowed": False,
        "credential_refs_and_digests_allowed": True,
        "bounded_projection_authority": "NONE_DERIVATIVE_ONLY",
        "lossless_underlying_evidence_required": True,
        "task_revision_match_required": True,
        "foreign_task_memory_injection_allowed": False,
        "system_memory_scope": "MINITZ_WIDE",
        "provider_native_session_memory_authority": False,
        "provenance_refs_required": ["content_ref", "source_ref"],
        "codex_handoff_requires_privacy_safe_payload": True,
    }
