from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from biella.security_privacy import (
    CredentialBoundaryError,
    CredentialVault,
    DataResidencyPolicy,
    IntegrityError,
    IntegrityManifest,
    NetworkMode,
    NetworkPolicy,
    NetworkPolicyError,
    PrivacyError,
    RecoveryError,
    RecoveryManager,
    ResidencyDomain,
    SecurityPrivacyBoundary,
    TrustError,
    TrustStore,
    assert_privacy_safe,
)


def test_credentials_cross_boundary_only_as_reference_and_digest() -> None:
    vault = CredentialVault()
    test_value = bytes(range(1, 33))
    reference = vault.register(
        "credential://provider/primary", test_value, scope="provider:primary"
    )
    assert reference.ref == "credential://provider/primary"
    assert reference.digest == hashlib.sha256(test_value).hexdigest()
    assert vault.metadata() == [reference.as_dict()]
    assert test_value.hex() not in repr(vault)
    assert vault.use(reference.ref, lambda value: hashlib.sha256(value).hexdigest()) == reference.digest

    with pytest.raises(CredentialBoundaryError, match="raw bytes"):
        vault.use(reference.ref, lambda value: value)
    with pytest.raises(CredentialBoundaryError, match="consumer failed"):
        vault.use(reference.ref, lambda _value: (_ for _ in ()).throw(RuntimeError("opaque-value")))


def test_privacy_rejects_raw_secret_fields_and_known_secret_bytes() -> None:
    with pytest.raises(PrivacyError):
        assert_privacy_safe({"api_token": "not-a-reference"})
    with pytest.raises(PrivacyError):
        assert_privacy_safe(b"safe prefix" + bytes(range(1, 33)), known_secrets=(bytes(range(1, 33)),))
    with pytest.raises(PrivacyError, match="binary payloads"):
        assert_privacy_safe(b"unclassified binary payload")
    with pytest.raises(PrivacyError, match="reference"):
        assert_privacy_safe({"credential_ref": "raw-secret-value"})
    assert_privacy_safe({"credential_ref": "credential://provider/primary", "credential_digest": "a" * 64})


def test_data_residency_allows_only_internal_export() -> None:
    policy = DataResidencyPolicy()
    result = policy.authorize_export(ResidencyDomain.EVIDENCE, "minitz://evidence/current")
    assert result["status"] == "ALLOW_INTERNAL"
    with pytest.raises(PrivacyError, match="external authority"):
        policy.authorize_export(ResidencyDomain.EVIDENCE, "https://example.test/evidence")


def test_trust_is_local_digest_anchored_and_rejects_untrusted_bytes() -> None:
    trust = TrustStore()
    payload = b"verified MiniTZ source"
    source = "minitz://source/security-privacy"
    trust.add_anchor("anchor-local", source, [hashlib.sha256(payload).hexdigest()])
    receipt = trust.verify(source, payload)
    assert receipt.status == "PASS"
    assert trust.verify_digest(source, receipt.content_sha256).anchor_id == "anchor-local"
    with pytest.raises(TrustError):
        trust.verify(source, b"tampered source")


def test_network_policy_has_explicit_online_allowlist_and_offline_denial() -> None:
    offline = NetworkPolicy(NetworkMode.OFFLINE)
    with pytest.raises(NetworkPolicyError, match="OFFLINE"):
        offline.authorize("provider-call", "https://provider.example/api")
    assert offline.authorize("local-call", "minitz://model/qwen", requires_network=False)["status"] == "ALLOW_INTERNAL"

    online = NetworkPolicy(NetworkMode.ONLINE)
    with pytest.raises(NetworkPolicyError, match="allowlisted"):
        online.authorize("provider-call", "https://provider.example/api")
    online.allow_external("https://provider.example/api")
    assert online.authorize("provider-call", "https://provider.example/api")["status"] == "ALLOW_EXTERNAL"
    with pytest.raises(NetworkPolicyError):
        online.allow_external("https://provider.example/api?token=secret")


def test_integrity_manifest_detects_tamper_without_external_authority(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "state.json").write_text('{"state":"accepted"}\n', encoding="utf-8")
    manifest = IntegrityManifest.from_directory(source, "g1")
    assert manifest.verify(source)["status"] == "PASS"
    (source / "state.json").write_text('{"state":"tampered"}\n', encoding="utf-8")
    with pytest.raises(IntegrityError, match="exact integrity"):
        manifest.verify(source)

    (source / "state.json").write_text('{"state":"accepted"}\n', encoding="utf-8")
    (source / "extra.json").write_text('{"extra":true}\n', encoding="utf-8")
    with pytest.raises(IntegrityError, match="unlisted file"):
        manifest.verify(source)


def test_recovery_publishes_verifies_and_rolls_back_atomically(tmp_path: Path) -> None:
    source_one = tmp_path / "one"; source_one.mkdir()
    source_two = tmp_path / "two"; source_two.mkdir()
    (source_one / "state.json").write_text('{"generation":1}\n', encoding="utf-8")
    (source_two / "state.json").write_text('{"generation":2}\n', encoding="utf-8")
    manager = RecoveryManager(tmp_path / "recovery")
    assert manager.publish("g1", source_one)["status"] == "PUBLISHED"
    assert manager.publish("g2", source_two)["status"] == "PUBLISHED"
    assert manager.activate("g1")["status"] == "ACTIVE"
    assert manager.activate("g2")["previous_generation"] == "g1"
    assert manager.verify_active()["generation"] == "g2"
    assert manager.rollback()["generation"] == "g1"
    assert manager.verify_active()["generation"] == "g1"

    (tmp_path / "one" / "symlink").symlink_to(tmp_path / "one" / "state.json")
    with pytest.raises(RecoveryError, match="symlink"):
        RecoveryManager(tmp_path / "other-recovery").publish("g1", tmp_path / "one")

    pointer = tmp_path / "recovery" / "current.json"
    pointer.write_text(pointer.read_text(encoding="utf-8").replace("g1", "g2"), encoding="utf-8")
    with pytest.raises(IntegrityError, match="pointer digest"):
        manager.verify_active()


def test_composed_boundary_has_no_external_authority() -> None:
    boundary = SecurityPrivacyBoundary.local(network_mode=NetworkMode.OFFLINE)
    contract = boundary.contract()
    assert contract["authority"] == "MINITZ_LOCAL_POLICY"
    assert contract["external_authority"] == "NONE"
    assert boundary.validate_evidence({"credential_ref": "credential://provider/primary"})["credential_ref"]
