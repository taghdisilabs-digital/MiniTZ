"""Executable proof for the final one-OS MiniTZ closure boundary."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "MINITZ-FINAL-CLOSURE-01"
TASK_DIGEST = "647f0a29a212a351816d974f327aacc45d2e7ebff36cc6d5853c795347a95c0f"
SOURCE_DIGEST = "0c787d365739f2166290cbce9db04764ae425c912f0dc8d84a5e4eb7ad6aea72"
IMAGE_DIGEST = "7c9b3594890360cd43e65f3f52d8140580639958d25498a75f4b0631cb06026f"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _task_program() -> tuple[Path, dict]:
    path = Path(os.environ.get("MINITZ_TASK_PROGRAM_PATH", "/state/task-program/TASK_PROGRAM.json"))
    return path, _json(path)


def test_final_task_program_is_single_authority_and_at_closure_boundary():
    sys.path.insert(0, str(ROOT / "ops/local-ai"))
    import minitz_task_program as task_program

    path, program = _task_program()
    assert path == Path("/state/task-program/TASK_PROGRAM.json")
    assert program["program_id"] == "MINITZ_REBORN_SINGLE_TASK_PROGRAM"
    assert program["intended_final_task_program_count"] == 1
    assert program["task_program_authority"] is True
    assert program["production_execution_authority"] is True
    assert program["production_order_status_authority"] is True
    final = next(row for row in program["tasks"] if row["task_id"] == TASK_ID)
    assert final["revision"] == 2
    assert task_program.task_digest(final) == TASK_DIGEST
    active = [row for row in program["tasks"] if row["status"] in task_program.ACTIVE_STATUSES]
    assert not active or active == [final]
    assert all(
        row["status"] in task_program.COMPLETE_STATUSES
        for row in program["tasks"]
        if row is not final
    )


def test_canonical_source_and_private_main_read_back_exactly():
    from minitz_os.source import source_manifest, verify_source

    manifest = source_manifest(ROOT)
    assert manifest["product"] == "MiniTZ OS"
    assert manifest["base_os"] == "Ubuntu 26.04"
    assert manifest["source_authority"] == "source-library://minitz/main"
    assert manifest["source_sha256"] == SOURCE_DIGEST
    assert manifest["bootable_disk_image"] is True
    assert manifest["private_state_included"] is False
    assert manifest["credential_values_included"] is False
    assert len(manifest["files"]) == 175
    assert verify_source(ROOT, manifest)["source_sha256"] == SOURCE_DIGEST

    branch = subprocess.check_output(["git", "-C", str(ROOT), "branch", "--show-current"], text=True).strip()
    remote = subprocess.check_output(["git", "-C", str(ROOT), "remote", "get-url", "origin"], text=True).strip()
    assert branch == "main"
    assert remote == "https://github.com/taghdisilabs-digital/MiniTZ.git"
    assert subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-remote", "origin", "refs/heads/main"], text=True
    ).strip().endswith("refs/heads/main")


def test_one_authoritative_boot_artifact_and_runtime_marker_read_back():
    sandbox = Path("/root/attached-storage/minitz-os-sandbox")
    build = _json(sandbox / "state/image-build/build.json")
    validation_path = sandbox / "state/image-build/validation/validation.json"
    validation = _json(validation_path)
    artifact = Path(validation["image_path"])
    assert build["product"] == validation["product"] == "MiniTZ OS"
    assert build["base_os"] == validation["base_os"] == "Ubuntu 26.04"
    assert build["source_sha256"] == validation["source_sha256"] == SOURCE_DIGEST
    assert build["image_sha256"] == validation["image_sha256"] == IMAGE_DIGEST
    assert artifact.is_file()
    assert artifact.stat().st_size == validation["image_bytes"] == 3_758_096_384
    assert _sha256(artifact) == IMAGE_DIGEST
    assert validation["partition_table"] == "GPT"
    assert validation["efi_system_partition"] == "PASS"
    assert validation["root_filesystem"] == "EXT4_PASS"
    assert validation["kernel_present"] == "PASS"
    assert validation["source_identity_embedded"] == "PASS"
    assert validation["quality_verdict"] == "PASS"

    log = sandbox / "state/image-build/validation/qemu-serial-snapshot-20260915-repaired-120.log"
    assert f"MINITZ_BOOT_OK source_sha256={SOURCE_DIGEST}" in log.read_text(encoding="utf-8", errors="replace")
