#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL")
_STATES = ("NOT_CONFIGURED", "NEEDS_LOCATOR", "CONNECTED", "CONFIGURED", "DEGRADED")


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _parse_shell_value(lines: list[str], index: int, raw_value: str) -> tuple[str | None, int]:
    value = raw_value.strip()
    if not value:
        return "", index
    if value[0] in {"'", '"'}:
        quote = value[0]
        combined = value
        while True:
            try:
                parsed = shlex.split(combined, posix=True)
            except ValueError:
                index += 1
                if index >= len(lines):
                    return None, index
                combined += "\n" + lines[index]
                continue
            return (parsed[0] if len(parsed) == 1 else None), index
    try:
        parsed = shlex.split(value, comments=True, posix=True)
    except ValueError:
        return None, index
    return (parsed[0] if len(parsed) == 1 else None), index

def parse_env_file(path: Path) -> dict[str, str]:
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    result: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line or line.startswith("#") or "=" not in line:
            index += 1
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not _ENV_KEY.fullmatch(key):
            index += 1
            continue
        value, final_index = _parse_shell_value(lines, index, raw_value)
        if value is not None:
            result[key] = value
        index = final_index + 1
    return result


def _valid_config_value(value: str) -> bool:
    return bool(value) and not any(ord(char) < 32 or ord(char) == 127 for char in value)


def _valid_secret_value(key: str, value: str) -> bool:
    if not _valid_config_value(value):
        return False
    upper = key.upper()
    if any(hint in upper for hint in _SECRET_HINTS) and len(value.encode("utf-8")) < 8:
        return False
    return True


def select_provider_values(registry: Mapping[str, Any], parsed: Mapping[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    selected: dict[str, str] = {}
    invalid: dict[str, str] = {}
    for provider in registry.get("providers", {}).values():
        for key in provider.get("required_env", []):
            key = str(key)
            if key not in parsed:
                continue
            if _valid_secret_value(key, parsed[key]):
                selected[key] = parsed[key]
            else:
                invalid[key] = "invalid_secret_value"
        for key in provider.get("locator_env", []):
            key = str(key)
            if key in parsed and _valid_config_value(parsed[key]):
                selected[key] = parsed[key]
    return selected, invalid

def _atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_provider_env(path: Path, values: Mapping[str, str]) -> None:
    lines = [f"{key}={shlex.quote(str(values[key]))}" for key in sorted(values)]
    _atomic_write(Path(path), "\n".join(lines) + ("\n" if lines else ""), 0o600)


def _credential_type(key: str) -> str:
    upper = key.upper()
    if "TOKEN" in upper:
        return "api_token"
    if "PASSWORD" in upper or "PASSWD" in upper:
        return "password"
    if "KEY" in upper:
        return "api_key"
    return "other"


def _credential_id(provider_id: str, key: str) -> str:
    return f"credential.provider.{_slug(provider_id)}.{key.lower()}"


def build_credential_registry(registry: Mapping[str, Any], selected: Mapping[str, str], invalid: Mapping[str, str], backend_path: Path) -> dict[str, Any]:
    credentials: dict[str, Any] = {}
    for provider_id, provider in registry.get("providers", {}).items():
        for key in provider.get("required_env", []):
            key = str(key)
            if key not in selected:
                continue
            credential_id = _credential_id(str(provider_id), key)
            credentials[credential_id] = {
                "credential_id": credential_id,
                "credential_type": _credential_type(key),
                "owner_scope": "system",
                "resource_ids": [f"resource.provider.{provider_id}"],
                "service_identity": provider.get("display_name", provider_id),
                "secret_backend_ref": f"protected-file:{Path(backend_path)}#{key}",
                "allowed_consumers": ["minitz.connectors", f"resource.provider.{provider_id}"],
                "rotation_state": "current",
                "revocation_state": "unknown",
                "health": "unknown",
            }
    return {"schema": "minitz.credential_registry/v1", "credentials": credentials, "invalid_entries": dict(sorted(invalid.items()))}

def parse_provider_check(output: str, registry: Mapping[str, Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for provider_id, provider in registry.get("providers", {}).items():
        aliases[_normalized(str(provider_id))] = str(provider_id)
        aliases[_normalized(str(provider.get("display_name", provider_id)))] = str(provider_id)
    states: dict[str, str] = {}
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = re.search(r"\b(" + "|".join(_STATES) + r")\b", line)
        if not match:
            continue
        label = _normalized(line[:match.start()])
        provider_id = aliases.get(label)
        if provider_id:
            states[provider_id] = match.group(1)
    return states


def _account_evidence_for(provider_id: str, provider: Mapping[str, Any], evidence: Mapping[str, Any]) -> tuple[str | None, Mapping[str, Any] | None]:
    candidates = {_normalized(provider_id), _normalized(str(provider.get("display_name", provider_id)))}
    for name, item in evidence.items():
        if _normalized(str(name)) in candidates and isinstance(item, Mapping):
            return str(name), item
    return None, None


def _availability_from_probe(state: str | None, configured: bool, invalid_required: bool) -> tuple[str, str]:
    if invalid_required:
        return "Needs Setup", "authentication_required"
    if state == "CONNECTED":
        return "Ready", "ready"
    if state == "CONFIGURED":
        return "Degraded", "health_check_failed"
    if state == "DEGRADED":
        return "Unavailable", "health_check_failed"
    if state == "NEEDS_LOCATOR":
        return "Needs Setup", "configuration_missing"
    if state == "NOT_CONFIGURED":
        return "Needs Setup", "authentication_required"
    if configured:
        return "Unavailable", "health_check_failed"
    return "Needs Setup", "authentication_required"


def _health(availability: str) -> str:
    if availability == "Ready":
        return "Healthy"
    if availability in {"Unavailable", "Degraded"}:
        return "Unhealthy"
    return "Unknown"

def build_resource_inventory(
    registry: Mapping[str, Any],
    selected: Mapping[str, str],
    invalid: Mapping[str, str],
    probe_states: Mapping[str, str],
    account_evidence: Mapping[str, Any],
    external_validations: Mapping[str, Any],
) -> dict[str, Any]:
    resources: dict[str, Any] = {}
    matched_evidence: set[str] = set()
    for provider_id, provider in registry.get("providers", {}).items():
        provider_id = str(provider_id)
        required = [str(key) for key in provider.get("required_env", [])]
        locators = [str(key) for key in provider.get("locator_env", [])]
        configured = all(key in selected for key in required + locators)
        invalid_required = any(key in invalid for key in required)
        availability, reason = _availability_from_probe(probe_states.get(provider_id), configured, invalid_required)
        evidence_name, evidence = _account_evidence_for(provider_id, provider, account_evidence)
        if evidence_name is not None:
            matched_evidence.add(evidence_name)
        if evidence:
            availability = str(evidence.get("availability", availability))
            reason = str(evidence.get("availability_reason", reason))
        credential_refs = [_credential_id(provider_id, key) for key in required if key in selected]
        resources[f"resource.provider.{provider_id}"] = {
            "resource_id": f"resource.provider.{provider_id}",
            "resource_type": "external_service",
            "service_identity": provider.get("display_name", provider_id),
            "support_tier": "Managed",
            "availability": availability,
            "availability_reason": reason,
            "health": _health(availability),
            "capabilities": list(provider.get("capabilities", [])),
            "credential_refs": credential_refs,
            "account_confirmed": bool(evidence and evidence.get("account_confirmed")) or availability == "Ready",
            "evidence": list(evidence.get("evidence", [])) if evidence else [],
            "implementation_source": "legacy_provider_adapter",
        }
    for name, evidence in account_evidence.items():
        if name in matched_evidence or not isinstance(evidence, Mapping):
            continue
        validation = external_validations.get(name, {})
        if not isinstance(validation, Mapping):
            validation = {}
        availability = str(validation.get("availability", evidence.get("availability", "Needs Setup")))
        reason = str(validation.get("availability_reason", evidence.get("availability_reason", "authentication_required")))
        credential_refs: list[str] = []
        credential_ref = validation.get("credential_ref")
        if credential_ref:
            credential_refs.append(str(credential_ref))
        resource_id = f"resource.account.{_slug(str(name))}"
        resources[resource_id] = {
            "resource_id": resource_id,
            "resource_type": "external_account",
            "service_identity": str(name),
            "support_tier": str(validation.get("support_tier", "Compatible")),
            "availability": availability,
            "availability_reason": reason,
            "health": _health(availability),
            "capabilities": list(validation.get("capabilities", [])),
            "credential_refs": credential_refs,
            "account_confirmed": bool(evidence.get("account_confirmed")),
            "evidence": list(evidence.get("evidence", [])),
            "implementation_source": str(validation.get("implementation_source", "account_evidence_only")),
        }
    return {"schema": "minitz.connector_resource_registry/v1", "resources": resources}


def write_json_protected(path: Path, payload: Mapping[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    _atomic_write(Path(path), text, 0o600)