from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))

import minitz_data_residency as residency


def test_semantic_memory_policy_keeps_all_noncredential_experience_inside_minitz():
    policy = residency.semantic_memory_policy()
    assert policy["schema"] == "minitz.data_residency/v1"
    assert policy["owner"] == "MiniTZ"
    assert set(policy["retained_inside_minitz"]) >= {
        "memory", "experience", "learning", "cache", "task_state", "session_state",
        "evidence", "failure_history", "provenance", "capability_metadata",
        "resource_metadata", "non_secret_runtime_history",
    }
    assert policy["excluded_raw_value_classes"] == [
        "API_AUTH_CREDENTIAL_VALUE", "LOGIN_AUTH_CREDENTIAL_VALUE"
    ]
    assert policy["credential_references_allowed"] is True
    assert policy["credential_digests_allowed"] is True


def test_raw_api_and_login_values_are_rejected_but_nonsecret_memory_is_preserved(tmp_path: Path):
    source = tmp_path / "runtime.env"
    source.write_text(
        "GROQ_API_KEY=api-value-123456789\n"
        "LOGIN_PASSWORD=login-value-987654321\n"
        "MODEL=qwen3-coder-next:minitz\n"
        "HOST=127.0.0.1\n",
        encoding="utf-8",
    )
    safe = json.dumps({
        "memory": "Keep all verified engineering experience.",
        "model": "qwen3-coder-next:minitz",
        "host": "127.0.0.1",
        "credential_ref": "credential://groq/default",
    }).encode()
    residency.assert_no_raw_auth_credentials(safe, source)

    with pytest.raises(ValueError, match="raw API/login credential value"):
        residency.assert_no_raw_auth_credentials(
            b"cached output includes api-value-123456789", source
        )
    with pytest.raises(ValueError, match="raw API/login credential value"):
        residency.assert_no_raw_auth_credentials(
            b"dialog includes login-value-987654321", source
        )


def test_missing_credential_source_does_not_delete_or_block_nonsecret_memory(tmp_path: Path):
    payload = b"memory experience cache evidence"
    residency.assert_no_raw_auth_credentials(payload, tmp_path / "missing.env")


def test_redaction_removes_only_raw_credential_values_and_keeps_context(tmp_path: Path):
    source = tmp_path / "runtime.env"
    source.write_text(
        "API_TOKEN=token-value-123456789\n"
        "LOGIN_PASSWORD=password-value-987654321\n"
        "MODEL=qwen3-coder-next:minitz\n",
        encoding="utf-8",
    )
    payload = json.dumps({
        "experience": "provider retry used token-value-123456789 and then recovered",
        "model": "qwen3-coder-next:minitz",
        "login_note": "password-value-987654321",
    }, sort_keys=True).encode()
    redacted = residency.redact_raw_auth_credentials(payload, source)
    text = redacted.decode()
    assert "token-value-123456789" not in text
    assert "password-value-987654321" not in text
    assert "provider retry used" in text and "then recovered" in text
    assert "qwen3-coder-next:minitz" in text
    assert text.count("[MINITZ_AUTH_CREDENTIAL_REDACTED]") == 2


def test_ai_installer_includes_residency_and_credential_verifier():
    text = (ROOT / "ops/local-ai/install-minitz-ai.sh").read_text(encoding="utf-8")
    assert '"$SOURCE_DIR/minitz_data_residency.py"' in text
    assert '"$SOURCE_DIR/minitz_private_secret_verifier.py"' in text
