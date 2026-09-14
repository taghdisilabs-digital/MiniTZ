"""MiniTZ semantic-memory residency boundary.

All non-credential operational knowledge stays inside MiniTZ. Raw authentication
and API credential values remain owned by the credential subsystem and are not
admitted into semantic memory, experience, cache, prompts, or public projections.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import minitz_private_secret_verifier as secret_verifier

SCHEMA = "minitz.data_residency/v1"

_RETAINED = (
    "memory", "experience", "learning", "cache", "task_state", "session_state",
    "evidence", "failure_history", "provenance", "capability_metadata",
    "resource_metadata", "non_secret_runtime_history",
)


def semantic_memory_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "owner": "MiniTZ",
        "retained_inside_minitz": list(_RETAINED),
        "excluded_raw_value_classes": [
            "API_AUTH_CREDENTIAL_VALUE", "LOGIN_AUTH_CREDENTIAL_VALUE",
        ],
        "credential_references_allowed": True,
        "credential_digests_allowed": True,
        "raw_credential_values_in_semantic_memory": False,
        "authority": "MINITZ_CREDENTIAL_SUBSYSTEM_FOR_RAW_VALUES",
    }


def default_credential_source() -> Path:
    raw = (
        os.environ.get("MINITZ_CREDENTIAL_SOURCE")
        or os.environ.get("MINITZ_AI_RUNTIME_ENV")
        or "/root/attached-storage/minitz-os-sandbox/state/credentials/runtime.env"
    )
    return Path(raw).expanduser()


def assert_no_raw_auth_credentials(payload: bytes, credential_source: Path | None = None) -> None:
    source = Path(credential_source or default_credential_source())
    if not source.is_file():
        return
    secrets, _config_count, unknown_count = secret_verifier._classified_entries(source)
    if unknown_count:
        raise ValueError("credential source contains unclassified entries")
    if any(secret and secret in payload for secret in secrets):
        raise ValueError("raw API/login credential value detected in MiniTZ semantic memory")


_REDACTION = b"[MINITZ_AUTH_CREDENTIAL_REDACTED]"

def redact_raw_auth_credentials(payload: bytes, credential_source: Path | None = None) -> bytes:
    source = Path(credential_source or default_credential_source())
    if not source.is_file():
        return payload
    secrets, _config_count, unknown_count = secret_verifier._classified_entries(source)
    if unknown_count:
        raise ValueError("credential source contains unclassified entries")
    result = bytes(payload)
    for secret in secrets:
        if not secret:
            continue
        result = result.replace(secret, _REDACTION)
        try:
            escaped = json.dumps(secret.decode("utf-8"), ensure_ascii=False)[1:-1].encode("utf-8")
        except UnicodeDecodeError:
            escaped = b""
        if escaped and escaped != secret:
            result = result.replace(escaped, _REDACTION)
    assert_no_raw_auth_credentials(result, source)
    return result
