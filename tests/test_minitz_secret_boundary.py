from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/minitz_secret_boundary.py"


def load_module():
    assert MODULE.is_file(), "SECRET-01 boundary module is not implemented"
    spec = importlib.util.spec_from_file_location("minitz_secret_boundary", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_private_state_contract_separates_vault_memory_and_public_domains():
    mod = load_module()
    contract = mod.private_state_contract()
    assert contract["schema"] == "minitz.secret_private_boundary/v1"
    domains = contract["domains"]
    assert set(domains) == {
        "OWNER_PRIVATE_MEMORY", "OWNER_PRIVATE_CACHE", "API_SECRET_VAULT",
        "CREDENTIAL_VAULT", "PROJECT_MEMORY", "CUSTOMER_MEMORY",
        "PUBLIC_ENGINE_KNOWLEDGE",
    }
    assert domains["API_SECRET_VAULT"]["raw_credential_values_allowed"] is True
    assert domains["CREDENTIAL_VAULT"]["raw_credential_values_allowed"] is True
    assert domains["OWNER_PRIVATE_MEMORY"]["raw_credential_values_allowed"] is False
    assert domains["PROJECT_MEMORY"]["universal_projection_allowed"] is False
    assert domains["CUSTOMER_MEMORY"]["universal_projection_allowed"] is False
    assert domains["PUBLIC_ENGINE_KNOWLEDGE"]["universal_projection_allowed"] is True


def test_ordinary_migration_excludes_legacy_secret_store_and_vault_domains():
    mod = load_module()
    assert mod.ordinary_migration_allowed(
        "/root/.config/biella-ai/runtime.env", "API_SECRET_VAULT"
    ) is False
    assert mod.ordinary_migration_allowed(
        "/var/lib/minitz/credentials/store.bin", "CREDENTIAL_VAULT"
    ) is False
    assert mod.ordinary_migration_allowed(
        "/var/lib/minitz/memory/public/index.json", "PUBLIC_ENGINE_KNOWLEDGE"
    ) is True


def test_private_object_fingerprint_emits_only_privacy_safe_identity(tmp_path: Path):
    mod = load_module()
    raw = b"fixture-private-object-value-123456789"
    path = tmp_path / "owner-private.bin"
    path.write_bytes(raw)
    receipt = mod.private_object_fingerprint(path)
    rendered = str(receipt)
    assert raw.decode() not in rendered
    assert str(path) not in rendered
    assert receipt["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["path_sha256"] == hashlib.sha256(str(path.resolve()).encode()).hexdigest()
    assert receipt["size_bytes"] == len(raw)


def test_booster_handoff_accepts_refs_and_digests_but_rejects_raw_secret_fields():
    mod = load_module()
    safe = {
        "task_id": "SECRET-01",
        "task_revision": 8,
        "credential_ref": "credential://provider/account",
        "credential_digest": "a" * 64,
        "evidence_refs": ["evidence://receipt/1"],
    }
    assert mod.validate_privacy_safe_payload(safe) == safe
    policy_absence = {"raw_credential_values_in_semantic_memory": False}
    assert mod.validate_privacy_safe_payload(policy_absence) == policy_absence
    with pytest.raises(ValueError, match="raw secret field"):
        mod.validate_privacy_safe_payload({"task_id": "T", "api_token": "fixture-token-value"})
    with pytest.raises(ValueError, match="credential-bearing value"):
        mod.validate_privacy_safe_payload({"endpoint": "https://user:password@example.test/path"})


def test_false_policy_metadata_allowlist_is_exact_and_literal():
    mod = load_module()

    assert mod.validate_privacy_safe_payload(
        {"raw_credential_values_in_semantic_memory": False}
    ) == {"raw_credential_values_in_semantic_memory": False}

    for value in (True, 0, "false", None, "fixture-secret"):
        with pytest.raises(ValueError, match="raw secret field"):
            mod.validate_privacy_safe_payload(
                {"raw_credential_values_in_semantic_memory": value}
            )

    with pytest.raises(ValueError, match="raw secret field"):
        mod.validate_privacy_safe_payload({"other_credential_policy": False})


def test_private_extractor_routes_keep_private_domains_out_of_ordinary_extractors():
    mod = load_module()
    assert mod.extractor_route("API_SECRET_VAULT") == "OWNER_PRIVATE_ISOLATED"
    assert mod.extractor_route("CREDENTIAL_VAULT") == "OWNER_PRIVATE_ISOLATED"
    assert mod.extractor_route("OWNER_PRIVATE_MEMORY") == "OWNER_PRIVATE_ISOLATED"
    assert mod.extractor_route("PROJECT_MEMORY") == "PROJECT_SCOPED"
    assert mod.extractor_route("CUSTOMER_MEMORY") == "CUSTOMER_SCOPED"
    assert mod.extractor_route("PUBLIC_ENGINE_KNOWLEDGE") == "ORDINARY_SAFE"


def test_booster_memory_filter_rejects_stale_task_revision_and_preserves_provenance():
    mod = load_module()
    records = [
        {"category": "task_memory", "task_id": "T", "task_revision": 2,
         "task_sha256": "new", "content_ref": "sha256:new", "source_ref": "task/T:2"},
        {"category": "task_memory", "task_id": "T", "task_revision": 1,
         "task_sha256": "old", "content_ref": "sha256:old", "source_ref": "task/T:1"},
        {"category": "instruction", "task_id": None, "scope_ref": "scope://minitz/system",
         "content_ref": "sha256:system", "source_ref": "policy:1"},
        {"category": "task_memory", "task_id": "FOREIGN", "task_revision": 3,
         "task_sha256": "foreign", "content_ref": "sha256:foreign", "source_ref": "task/F:3"},
    ]
    kept = mod.filter_booster_memory(
        records, task_id="T", task_revision=2, task_sha256="new"
    )
    assert [row["content_ref"] for row in kept] == ["sha256:new", "sha256:system"]
    assert all(row.get("source_ref") and row.get("content_ref") for row in kept)


def test_secret_migration_contract_requires_owner_input_kdf_kek_and_domain_keys():
    mod = load_module()
    contract = mod.secret_migration_contract()
    assert contract["owner_authorization_required"] is True
    assert contract["passphrase_persistence"] == "FORBIDDEN"
    assert contract["owner_input_mode"] == "INTERACTIVE_EPHEMERAL"
    assert contract["flow"][:4] == [
        "OWNER_INTERACTIVE_INPUT", "KDF", "ROOT_KEK", "INDEPENDENT_DOMAIN_KEYS"
    ]
    assert contract["independent_domain_keys"] is True


def test_private_extraction_receipt_exposes_only_approved_semantics(tmp_path: Path):
    mod = load_module()
    path = tmp_path / "private.bin"
    path.write_bytes(b"fixture-private-secret-material-987654321")
    fingerprint = mod.private_object_fingerprint(path)
    receipt = mod.private_extraction_receipt(
        "OWNER_PRIVATE_MEMORY",
        fingerprint,
        [{"type": "relationship", "statement": "owner preference belongs to private scope"}],
    )
    rendered = str(receipt)
    assert "fixture-private-secret-material-987654321" not in rendered
    assert receipt["authority"] == "NONE"
    assert receipt["raw_bytes_emitted"] is False
    assert receipt["ordinary_log_safe"] is True
    with pytest.raises(ValueError, match="raw secret field"):
        mod.private_extraction_receipt(
            "OWNER_PRIVATE_MEMORY", fingerprint,
            [{"type": "fact", "password": "fixture-value"}],
        )


def test_booster_context_policy_keeps_projection_derivative_and_evidence_lossless():
    mod = load_module()
    policy = mod.booster_context_policy()
    assert policy["bounded_projection_authority"] == "NONE_DERIVATIVE_ONLY"
    assert policy["lossless_underlying_evidence_required"] is True
    assert policy["task_revision_match_required"] is True
    assert policy["raw_credential_values_allowed"] is False
    assert policy["credential_refs_and_digests_allowed"] is True


def _load_booster_sync():
    path = ROOT / "ops/local-ai/minitz_booster_sync.py"
    spec = importlib.util.spec_from_file_location("secret_boundary_booster_sync", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_booster_context_excludes_stale_task_memory_but_keeps_system_memory():
    sync = _load_booster_sync()
    program = {"program_id": "MINITZ_REBORN_SINGLE_TASK_PROGRAM", "revision": 1, "current_execution": {"task_id": "T"}, "tasks": [{
        "task_id": "T", "revision": 2, "task_record_sha256": "new", "status": "PENDING",
        "title": "private boundary", "objective": {"desired_state": "safe"},
    }]}
    ledger = {"items": [{"booster": "BOOST-05", "canonical_task_id": "T",
        "canonical_task_revision": 2, "canonical_task_sha256": "new",
        "work_status": "QUEUED", "queue_order": 1, "unmet_hard_dependencies": []}]}
    memory = {"content": {
        "sha256:old": {"text": "stale steering"}, "sha256:new": {"text": "current task fact"},
        "sha256:sys": {"text": "MiniTZ system rule"}}, "records": [
        {"category":"task_memory","task_id":"T","task_revision":1,"task_sha256":"old","content_ref":"sha256:old","source_ref":"task/T:1"},
        {"category":"task_memory","task_id":"T","task_revision":2,"task_sha256":"new","content_ref":"sha256:new","source_ref":"task/T:2"},
        {"category":"instruction","scope_ref":"scope://minitz/system","content_ref":"sha256:sys","source_ref":"policy:1"},
    ]}
    pack = sync.build_context_pack(program, ledger, "BOOST-05", memory_index=memory,
        projection=None, provider_registry={"routes": {}, "policy": {}}, maximum_bytes=18000)
    texts = [row["text"] for row in pack["memory"]["records"]]
    assert "current task fact" in texts
    assert "MiniTZ system rule" in texts
    assert "stale steering" not in texts
    assert all(row.get("content_ref") and row.get("source_ref") for row in pack["memory"]["records"])


def test_prepare_local_ai_fails_closed_without_matching_private_receipt(tmp_path: Path, monkeypatch):
    sync = _load_booster_sync()
    context = tmp_path / "context"; context.mkdir()
    cache = tmp_path / "cache"
    (context / "BOOST-05.json").write_text('{"booster_id":"BOOST-05","selected_task":{"task_id":"T"}}')
    calls = []
    monkeypatch.setattr(sync, "_invoke_local_qwen", lambda *_a, **_k: calls.append(1) or {"text":"bad"})
    with pytest.raises(ValueError, match="privacy qualification"):
        sync.prepare_local_ai_for_booster(context, cache, "BOOST-05")
    assert calls == []


def test_privacy_safe_payload_allows_secret_receipt_metadata_not_raw_values():
    mod = load_module()
    payload = {
        "secret_leak_receipt": {
            "path": "evidence://secret-scan",
            "verifier_receipt_digest": "a" * 64,
            "exact_value_hit_count": 0,
            "result": "PASS",
        }
    }
    assert mod.validate_privacy_safe_payload(payload) == payload
