"""Executable guards for truthful, progressive MiniTZ final closure."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = Path("/root/attached-storage/minitz-os-sandbox")
TASK_ID = "MINITZ-FINAL-CLOSURE-01"

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "ops/local-ai"))

import minitz_task_program as task_program
from minitz_completion_truth import (
    installed_source_matches_current,
    owner_acceptance_matches_current,
    runtime_boot_proof_matches_current,
)
from minitz_os.boot_artifact import inspect_current_boot_artifact
from minitz_os.source import source_manifest, verify_source


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _program_path() -> Path:
    configured = os.environ.get("MINITZ_TASK_PROGRAM_PATH")
    if configured:
        return Path(configured)
    mounted = Path("/state/task-program/TASK_PROGRAM.json")
    return mounted if mounted.is_file() else SANDBOX / "state/task-program/TASK_PROGRAM.json"


def test_final_horizon_uses_one_task_authority_and_derived_current_task():
    path = _program_path()
    program = task_program.load(path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert program["program_id"] == "MINITZ_REBORN_SINGLE_TASK_PROGRAM"
    assert program["intended_final_task_program_count"] == 1
    assert program["task_program_authority"] is True
    assert program["production_execution_authority"] is True
    assert program["production_order_status_authority"] is True
    assert "current_execution" not in persisted
    assert "frozen_current_task" not in persisted

    active = [row for row in program["tasks"] if row["status"] in task_program.ACTIVE_STATUSES]
    current = task_program.current_task(program)
    assert (current is None) == (not active)
    if current is not None:
        assert current["task_id"] == active[0]["task_id"]
        current_index = program["tasks"].index(current)
        assert all(
            row["status"] in task_program.COMPLETE_STATUSES
            for row in program["tasks"][:current_index]
        )

    final = task_program.task_by_id(program, TASK_ID)
    assert final["task_record_sha256"] == task_program.task_digest(final)


def test_canonical_source_and_private_main_are_dynamic_current_truth():
    manifest = source_manifest(ROOT)
    assert manifest["product"] == "MiniTZ OS"
    assert manifest["base_os"] == "Ubuntu 26.04"
    assert manifest["source_authority"] == "source-library://minitz/main"
    assert manifest["bootable_disk_image"] is True
    assert manifest["private_state_included"] is False
    assert manifest["credential_values_included"] is False
    assert manifest["files"]
    assert verify_source(ROOT, manifest)["source_sha256"] == manifest["source_sha256"]

    branch = subprocess.check_output(["git", "-C", str(ROOT), "branch", "--show-current"], text=True).strip()
    remote = subprocess.check_output(["git", "-C", str(ROOT), "remote", "get-url", "origin"], text=True).strip()
    assert branch == "main"
    assert remote == "https://github.com/taghdisilabs-digital/MiniTZ.git"


def test_current_boot_artifact_never_falls_back_to_historical_output_bytes():
    program = task_program.load(_program_path())
    final = task_program.task_by_id(program, TASK_ID)
    source = source_manifest(ROOT)
    artifact = inspect_current_boot_artifact(ROOT, SANDBOX)

    if artifact["state"] != "CURRENT_VERIFIED":
        assert final["status"] not in task_program.COMPLETE_STATUSES
        return

    image = Path(artifact["image_path"])
    assert artifact["live_source_sha256"] == source["source_sha256"]
    assert artifact["source_alignment"] in {"MATCHES_LIVE_SOURCE", "FROZEN_RELEASE"}
    assert image.is_file()
    assert _sha256(image) == artifact["image_sha256"]
    assert image.stat().st_size == artifact["image_bytes"]
    build = json.loads(Path(artifact["build_record_path"]).read_text(encoding="utf-8"))
    validation = json.loads(Path(artifact["validation_record_path"]).read_text(encoding="utf-8"))
    assert build["source_sha256"] == validation["source_sha256"] == artifact["source_sha256"]
    assert build["image_sha256"] == validation["image_sha256"] == artifact["image_sha256"]
    assert validation["quality_verdict"] == "PASS"


def test_installed_source_matches_frozen_release_not_later_repo_source(tmp_path: Path, monkeypatch):
    import minitz_completion_truth as completion_truth

    sandbox = tmp_path / "sandbox"
    installed_source = sandbox / "system/current/opt/minitz/source"
    installed_source.mkdir(parents=True)
    manifest_path = sandbox / "system/current/etc/minitz/source.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("{}\n", encoding="utf-8")
    frozen_source = "a" * 64
    later_source = "b" * 64

    monkeypatch.setattr(completion_truth, "verify_source", lambda _source, _manifest: {"source_sha256": frozen_source})
    monkeypatch.setattr(completion_truth, "inspect_current_boot_artifact", lambda _repo, _sandbox: {
        "state": "CURRENT_VERIFIED",
        "source_sha256": frozen_source,
    })
    monkeypatch.setattr(completion_truth, "source_manifest", lambda _repo: {"source_sha256": later_source}, raising=False)

    assert completion_truth.installed_source_matches_current(ROOT, sandbox) is True


def test_final_complete_is_impossible_without_exact_boot_owner_and_install_truth():
    program = task_program.load(_program_path())
    final = task_program.task_by_id(program, TASK_ID)
    if final["status"] not in task_program.COMPLETE_STATUSES:
        return

    artifact = inspect_current_boot_artifact(ROOT, SANDBOX)
    assert artifact["state"] == "CURRENT_VERIFIED"
    assert runtime_boot_proof_matches_current(SANDBOX, artifact)
    assert owner_acceptance_matches_current(program, artifact)
    assert installed_source_matches_current(ROOT, SANDBOX)
    final_index = [row["task_id"] for row in program["tasks"]].index(TASK_ID)
    assert all(
        row["status"] in task_program.COMPLETE_STATUSES
        for row in program["tasks"][:final_index]
    )
