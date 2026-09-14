from __future__ import annotations
import hashlib
import json
import tarfile
from pathlib import Path
import pytest


def fixture_source(tmp_path):
    root=tmp_path / "source"
    (root / "src/minitz_os").mkdir(parents=True)
    (root / "src/minitz_os/__init__.py").write_text('PRODUCT = "MiniTZ OS"\n')
    (root / "pyproject.toml").write_text('[project]\nname="minitz-os"\nversion="0.1.0"\n')
    return root


def test_release_identity_tracks_actual_source_bytes_not_only_git_head(tmp_path):
    from minitz_os.source import source_manifest
    root=fixture_source(tmp_path)
    first=source_manifest(root)
    (root / "src/minitz_os/__init__.py").write_text('PRODUCT = "MiniTZ OS"\nVERSION = 2\n')
    second=source_manifest(root)
    assert first["source_sha256"] != second["source_sha256"]
    assert first["product"] == "MiniTZ OS"


def test_release_is_deterministic_and_does_not_package_private_state(tmp_path):
    from minitz_os.source import build_release
    root=fixture_source(tmp_path)
    (root / "state").mkdir()
    (root / "state/auth.json").write_text('{"credential":"private"}')
    first=build_release(root,tmp_path / "one")
    second=build_release(root,tmp_path / "two")
    assert first["artifact_sha256"] == second["artifact_sha256"]
    with tarfile.open(first["artifact_path"],"r:gz") as archive:
        names=archive.getnames()
        assert "usr/bin/minitz" in names
        assert "etc/minitz/source.json" in names
        assert not any("auth.json" in name or name.startswith("state/") for name in names)


def test_installed_source_verification_rejects_tampering(tmp_path):
    from minitz_os.source import source_manifest, verify_source
    root=fixture_source(tmp_path)
    manifest=source_manifest(root)
    assert verify_source(root,manifest)["verified"] is True
    (root / "src/minitz_os/__init__.py").write_text('PRODUCT = "wrong"\n')
    with pytest.raises(ValueError,match="source"):
        verify_source(root,manifest)


def test_source_bundle_never_follows_external_symlinks(tmp_path):
    from minitz_os.source import source_manifest
    root=fixture_source(tmp_path)
    donor=tmp_path / "external.py";donor.write_text('secret = "outside"')
    (root / "src/minitz_os/outside.py").symlink_to(donor)
    with pytest.raises(ValueError,match="symlink"):
        source_manifest(root)


def test_credential_material_blocks_distribution_without_printing_secret(tmp_path):
    from minitz_os.source import source_manifest
    root=fixture_source(tmp_path)
    value='sk-proj-'+'x'*48
    (root / "src/minitz_os/leak.py").write_text('KEY = '+repr(value))
    with pytest.raises(ValueError,match="credential") as error:
        source_manifest(root)
    assert value not in str(error.value)


def test_identical_release_reuses_verified_artifact(tmp_path):
    from minitz_os.source import build_release
    root=fixture_source(tmp_path)
    first=build_release(root,tmp_path / "out")
    second=build_release(root,tmp_path / "out")
    assert first["cache_hit"] is False and second["cache_hit"] is True
    assert first["artifact_path"] == second["artifact_path"]


def test_installed_source_rejects_injected_code(tmp_path):
    from minitz_os.source import source_manifest,verify_source
    root=fixture_source(tmp_path);manifest=source_manifest(root)
    (root / "src/minitz_os/injected.py").write_text('INJECTED=True\n')
    with pytest.raises(ValueError,match="source"):
        verify_source(root,manifest)


def test_install_uses_same_content_identity_and_one_active_pointer(tmp_path):
    from minitz_os.source import build_release,install_release,verify_source
    root=fixture_source(tmp_path);release=build_release(root,tmp_path / "out")
    installed=install_release(Path(release["artifact_path"]),tmp_path / "system",release["artifact_sha256"])
    current=tmp_path / "system/current"
    assert current.is_symlink()
    manifest=json.loads((current/"etc/minitz/source.json").read_text())
    assert verify_source(current/"opt/minitz/source",manifest)["source_sha256"] == release["source_sha256"]
    assert (current/"usr/bin/minitz").stat().st_mode & 0o111
    again=install_release(Path(release["artifact_path"]),tmp_path / "system",release["artifact_sha256"])
    assert again["cache_hit"] is True


def test_damaged_release_cannot_replace_active_installation(tmp_path):
    from minitz_os.source import build_release,install_release
    root=fixture_source(tmp_path);release=build_release(root,tmp_path / "out")
    system=tmp_path/"system"
    install_release(Path(release["artifact_path"]),system,release["artifact_sha256"])
    before=(system/"current").resolve()
    Path(release["artifact_path"]).write_bytes(b"corrupted")
    with pytest.raises(ValueError,match="artifact"):
        install_release(Path(release["artifact_path"]),system,release["artifact_sha256"])
    assert (system/"current").resolve()==before


def test_signed_update_first_boot_rollback_and_restart_preserve_continuity(tmp_path):
    from minitz_os.source import (
        apply_signed_update,
        build_signed_update,
        provision_first_boot,
        read_continuity,
        recover_installation,
        rollback_installation,
    )

    root = fixture_source(tmp_path)
    system = tmp_path / "system"
    key = b"task-owned-test-signing-key"
    provision_first_boot(
        system,
        task_state={"task_id": "MINITZ-INSTALL-UPDATE-01", "status": "WORKING"},
        memory_state={"current_task_ref": "memory://minitz/current-task"},
        resource_state={"resource_ref": "resource://minitz/qwen"},
    )
    first = build_signed_update(root, tmp_path / "release-one", key)
    installed = apply_signed_update(Path(first["update_path"]), system, key)
    assert installed["signed_update"] is True
    assert installed["source_sha256"] == first["source_sha256"]

    (root / "src/minitz_os/__init__.py").write_text('PRODUCT = "MiniTZ OS"\nVERSION = 2\n')
    second = build_signed_update(root, tmp_path / "release-two", key)
    updated = apply_signed_update(Path(second["update_path"]), system, key)
    assert updated["source_sha256"] == second["source_sha256"]
    assert updated["source_sha256"] != first["source_sha256"]

    recovered = recover_installation(system)
    assert recovered["source"]["source_sha256"] == second["source_sha256"]
    assert recovered["continuity"]["task_state"]["task_id"] == "MINITZ-INSTALL-UPDATE-01"
    assert read_continuity(system)["resource_state"]["resource_ref"] == "resource://minitz/qwen"

    rolled_back = rollback_installation(system)
    assert rolled_back["source_sha256"] == first["source_sha256"]
    assert recover_installation(system)["source"]["source_sha256"] == first["source_sha256"]


def test_signed_update_rejects_wrong_key_before_activation(tmp_path):
    from minitz_os.source import apply_signed_update, build_signed_update

    root = fixture_source(tmp_path)
    system = tmp_path / "system"
    update = build_signed_update(root, tmp_path / "release", b"task-owned-test-signing-key")
    with pytest.raises(ValueError, match="verification"):
        apply_signed_update(Path(update["update_path"]), system, b"another-key-that-is-long")
    assert not (system / "current").exists()
