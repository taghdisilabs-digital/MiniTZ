from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "ops/local-ai"))

import minitz_task_program as task_program
from minitz_os.source import source_manifest


def _write_json(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def _artifact_fixture(tmp_path: Path):
    from minitz_os.boot_artifact import publish_validated_boot_artifact, stage_boot_artifact_candidate

    sandbox = tmp_path / "sandbox"
    state = sandbox / "state/image-build"
    output = sandbox / "output/images"
    output.mkdir(parents=True)
    manifest = source_manifest(ROOT)
    image = output / f"MiniTZ-OS-{manifest['source_sha256'][:16]}.raw"
    image.write_bytes(b"exact-current-image-bytes")
    image_sha = hashlib.sha256(image.read_bytes()).hexdigest()
    build = _write_json(state / "build.json", {
        "schema": "minitz.boot_image_build/v1",
        "product": "MiniTZ OS",
        "base_os": "Ubuntu 26.04",
        "artifact_kind": "BOOTABLE_DISK_IMAGE",
        "bootable_disk_image": True,
        "source_sha256": manifest["source_sha256"],
        "image_path": "/build/ignored-internal-path.raw",
        "image_sha256": image_sha,
        "image_bytes": image.stat().st_size,
        "rootfs_bytes": 1,
        "kernel": "vmlinuz-test",
    })
    validation = _write_json(state / "validation/validation.json", {
        "schema": "minitz.boot_image_validation/v1",
        "product": "MiniTZ OS",
        "base_os": "Ubuntu 26.04",
        "artifact_kind": "BOOTABLE_DISK_IMAGE",
        "bootable_disk_image": True,
        "source_sha256": manifest["source_sha256"],
        "image_path": str(image),
        "image_sha256": image_sha,
        "image_bytes": image.stat().st_size,
        "partition_table": "GPT",
        "efi_system_partition": "PASS",
        "root_filesystem": "EXT4_PASS",
        "kernel_present": "PASS",
        "source_identity_embedded": "PASS",
        "image_boot_executed": False,
        "quality_verdict": "PASS",
    })
    stage_boot_artifact_candidate(ROOT, sandbox, image, build)
    current = publish_validated_boot_artifact(ROOT, sandbox, image, build, validation)
    return sandbox, current


def test_current_boot_artifact_is_exact_source_bound_and_never_falls_back_to_old_output(tmp_path: Path):
    from minitz_os.boot_artifact import inspect_current_boot_artifact

    sandbox, current = _artifact_fixture(tmp_path)
    observed = inspect_current_boot_artifact(ROOT, sandbox)
    assert observed["state"] == "CURRENT_VERIFIED"
    assert observed["source_sha256"] == source_manifest(ROOT)["source_sha256"]
    assert observed["image_sha256"] == current["image_sha256"]

    # Old files may remain as historical bytes, but they can never become current
    # by directory ordering or by a stale build.json.
    old = sandbox / "output/images/MiniTZ-OS-old.raw"
    old.write_bytes(b"older-image")
    stale = json.loads((sandbox / "state/image-build/current.json").read_text())
    stale["source_sha256"] = "0" * 64
    _write_json(sandbox / "state/image-build/current.json", stale)
    observed = inspect_current_boot_artifact(ROOT, sandbox)
    assert observed["state"] == "STALE_SOURCE"
    assert observed.get("image_path") != str(old)


def test_publish_rejects_validation_not_bound_to_exact_current_image(tmp_path: Path):
    from minitz_os.boot_artifact import publish_validated_boot_artifact, stage_boot_artifact_candidate

    sandbox = tmp_path / "sandbox"
    state = sandbox / "state/image-build"
    output = sandbox / "output/images"
    output.mkdir(parents=True)
    source = source_manifest(ROOT)["source_sha256"]
    image = output / f"MiniTZ-OS-{source[:16]}.raw"
    image.write_bytes(b"image-a")
    image_sha = hashlib.sha256(image.read_bytes()).hexdigest()
    build = _write_json(state / "build.json", {
        "schema":"minitz.boot_image_build/v1", "product":"MiniTZ OS", "base_os":"Ubuntu 26.04",
        "artifact_kind":"BOOTABLE_DISK_IMAGE", "bootable_disk_image":True,
        "source_sha256":source, "image_path":"/build/a.raw", "image_sha256":image_sha,
        "image_bytes":image.stat().st_size, "rootfs_bytes":1, "kernel":"vmlinuz-test",
    })
    validation = _write_json(state / "validation/validation.json", {
        "schema":"minitz.boot_image_validation/v1", "product":"MiniTZ OS", "base_os":"Ubuntu 26.04",
        "source_sha256":source, "image_path":str(image), "image_sha256":"f" * 64,
        "image_bytes":image.stat().st_size, "bootable_disk_image":True, "partition_table":"GPT",
        "efi_system_partition":"PASS", "root_filesystem":"EXT4_PASS", "kernel_present":"PASS",
        "source_identity_embedded":"PASS", "quality_verdict":"PASS",
    })
    stage_boot_artifact_candidate(ROOT, sandbox, image, build)
    with pytest.raises(ValueError, match="validation.*image|image.*validation"):
        publish_validated_boot_artifact(ROOT, sandbox, image, build, validation)
    assert not (state / "current.json").exists()


def test_model_result_cannot_auto_accept_owner_task(tmp_path: Path):
    from minitz_completion_truth import admit_model_result

    sandbox, _ = _artifact_fixture(tmp_path)
    decision = admit_model_result(
        ROOT, sandbox, "MINITZ-OWNER-ACCEPTANCE-01", "COMPLETE", "all tests passed", ("137 passed",)
    )
    assert decision["status"] == "CONTINUE"
    assert decision["summary"].startswith("REQUIRES_OWNER_ACCEPTANCE:")
    assert any("owner://minitz/exact-artifact-acceptance" in item for item in decision["evidence"])


def test_model_completion_for_system_qualification_requires_current_material_artifact(tmp_path: Path):
    from minitz_completion_truth import admit_model_result

    sandbox, _ = _artifact_fixture(tmp_path)
    accepted = admit_model_result(
        ROOT, sandbox, "MINITZ-SYSTEM-QUALIFY-01", "COMPLETE", "qualified", ("tests passed",)
    )
    assert accepted["status"] == "CONTINUE"
    assert accepted["summary"].startswith("REQUIRES_OWNER_RAW_IMAGE_BOOT_AUTHORIZATION:")

    (sandbox / "state/image-build/current.json").unlink()
    rejected = admit_model_result(
        ROOT, sandbox, "MINITZ-SYSTEM-QUALIFY-01", "COMPLETE", "qualified", ("tests passed",)
    )
    assert rejected["status"] == "CONTINUE"
    assert rejected["summary"].startswith("MATERIAL_PROOF_REQUIRED:")


def _program_copy(tmp_path: Path) -> Path:
    live = Path("/root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json")
    raw = json.loads(live.read_text(encoding="utf-8"))
    path = tmp_path / "TASK_PROGRAM.json"
    raw["current_live_production_authority"] = str(path)
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    return path


def test_reopen_from_invalid_material_boundary_preserves_valid_prefix_and_history(tmp_path: Path):
    path = _program_copy(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    for task_id in ("MINITZ-SYSTEM-QUALIFY-01", "MINITZ-OWNER-ACCEPTANCE-01", "MINITZ-FINAL-CLOSURE-01"):
        row = next(item for item in raw["tasks"] if item["task_id"] == task_id)
        history = row.get("completion_history") or []
        assert history
        row["completion"] = history[-1]["completion"]
        row["status"] = "COMPLETE"
        row["active_task_survival"] = False
        row["task_record_sha256"] = task_program.task_digest(row)
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    before = task_program.load(path)
    boot_before = dict(task_program.task_by_id(before, "MINITZ-BOOTABLE-IMAGE-01"))

    task_program.reopen_from(
        "MINITZ-SYSTEM-QUALIFY-01",
        evidence=["current exact artifact proof is absent; deterministic material-truth reconciliation"],
        path=path,
    )
    after = task_program.load(path)
    assert task_program.task_by_id(after, "MINITZ-BOOTABLE-IMAGE-01") == boot_before
    for task_id in ("MINITZ-SYSTEM-QUALIFY-01", "MINITZ-OWNER-ACCEPTANCE-01", "MINITZ-FINAL-CLOSURE-01"):
        task = task_program.task_by_id(after, task_id)
        assert task["status"] == "PENDING"
        assert task["active_task_survival"] is True
        assert "completion" not in task
        assert task["completion_history"]
    assert task_program.current_task(after)["task_id"] == "MINITZ-SYSTEM-QUALIFY-01"
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert "frozen_current_task" not in persisted
    assert "current_execution" not in persisted


def test_material_truth_reconciliation_reopens_only_invalid_final_suffix(tmp_path: Path):
    from minitz_completion_truth import reconcile_material_truth

    path = _program_copy(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Reconstruct the just-before-repair completed suffix from preserved history
    # so this test stays valid after the live program has itself been repaired.
    for task_id in ("MINITZ-SYSTEM-QUALIFY-01", "MINITZ-OWNER-ACCEPTANCE-01", "MINITZ-FINAL-CLOSURE-01"):
        row = next(item for item in raw["tasks"] if item["task_id"] == task_id)
        if row.get("status") != "COMPLETE":
            history = row.get("completion_history") or []
            assert history
            row["completion"] = history[-1]["completion"]
            row["status"] = "COMPLETE"
            row["active_task_survival"] = False
            row["task_record_sha256"] = task_program.task_digest(row)
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    sandbox = tmp_path / "sandbox"  # no current verified artifact
    result = reconcile_material_truth(ROOT, sandbox, program_path=path)
    assert result["changed"] is True
    assert result["reopened_from"] == "MINITZ-SYSTEM-QUALIFY-01"
    after = task_program.load(path)
    assert task_program.task_by_id(after, "MINITZ-BOOTABLE-IMAGE-01")["status"] == "COMPLETE"
    assert task_program.task_by_id(after, "MINITZ-SYSTEM-QUALIFY-01")["status"] == "PENDING"
    assert task_program.task_by_id(after, "MINITZ-OWNER-ACCEPTANCE-01")["status"] == "PENDING"
    assert task_program.task_by_id(after, "MINITZ-FINAL-CLOSURE-01")["status"] == "PENDING"


def test_public_program_removes_obsolete_frozen_current_pointer(tmp_path: Path):
    path = _program_copy(tmp_path)
    loaded = task_program.load(path)
    loaded["frozen_current_task"] = {"task_id": "MINITZ-STARTUP-FOUNDATION-01", "session_id": None}
    public = task_program.public_program(loaded)
    assert "frozen_current_task" not in public
    assert "current_execution" not in public


def test_production_result_normalization_enforces_material_truth_when_repo_is_known(tmp_path: Path, monkeypatch):
    import minitz_production_runner as runner
    from minitz_production_evidence import TaskResult
    import minitz_codex_routing as routing

    seen = {}
    def fake_admit(repo_root, sandbox_root, task_id, status, summary, evidence, **kwargs):
        seen.update({"repo": Path(repo_root), "sandbox": Path(sandbox_root), "task": task_id, "status": status})
        return {"status":"CONTINUE", "summary":"MATERIAL_PROOF_REQUIRED: fake", "evidence":tuple(evidence) + ("proof",)}

    monkeypatch.setattr(runner.completion_truth, "admit_model_result", fake_admit)
    result = TaskResult("MINITZ-SYSTEM-QUALIFY-01", "COMPLETE", "done", ("tests",))
    normalized = runner._normalize_result_for_route(
        result, routing.Route("gpt-5.6-luna", "high"), repo_root=ROOT, sandbox_root=tmp_path / "sandbox"
    )
    assert normalized.status == "CONTINUE"
    assert normalized.summary.startswith("MATERIAL_PROOF_REQUIRED:")
    assert seen["task"] == "MINITZ-SYSTEM-QUALIFY-01"


def test_image_scripts_publish_only_through_exact_artifact_authority():
    build_local = (ROOT / "ops/workstation/minitz-os-sandbox/build-image-local.sh").read_text()
    build_docker = (ROOT / "ops/workstation/minitz-os-sandbox/build-image.sh").read_text()
    validate_local = (ROOT / "ops/workstation/minitz-os-sandbox/validate-image-local.sh").read_text()
    validate_docker = (ROOT / "ops/workstation/minitz-os-sandbox/validate-image.sh").read_text()
    assert 'REPO="$SANDBOX/workspace/repo"' in validate_docker
    for build in (build_local, build_docker):
        assert "stage_boot_artifact_candidate" in build
    for validate in (validate_local, validate_docker):
        assert "publish_validated_boot_artifact" in validate


def test_system_qualification_does_not_wait_for_runtime_boot_proof(tmp_path: Path):
    from minitz_completion_truth import admit_model_result

    sandbox, current = _artifact_fixture(tmp_path)
    decision = admit_model_result(
        ROOT, sandbox, "MINITZ-SYSTEM-QUALIFY-01", "COMPLETE", "all non-boot checks pass", ("tests passed",)
    )
    assert decision["status"] == "COMPLETE"


def test_exact_runtime_boot_proof_is_source_and_image_bound(tmp_path: Path):
    from minitz_completion_truth import record_runtime_boot_proof, runtime_boot_proof_matches_current

    sandbox, current = _artifact_fixture(tmp_path)
    log = sandbox / "state/image-build/validation/explicit-owner-boot.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    marker = f"MINITZ_BOOT_OK source_sha256={current['source_sha256']}"
    log.write_text("booting\n" + marker + "\n", encoding="utf-8")
    record_runtime_boot_proof(ROOT, sandbox, log, method="QEMU_UEFI_OWNER_AUTHORIZED")
    assert runtime_boot_proof_matches_current(sandbox, current)

    log.write_text("tampered\n" + marker + "\n", encoding="utf-8")
    assert not runtime_boot_proof_matches_current(sandbox, current)
