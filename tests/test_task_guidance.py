from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))

import minitz_task_guidance as guidance
import minitz_booster_sync as booster_sync


def _task(task_id: str, revision: int = 1) -> dict:
    task = {
        "task_id": task_id,
        "revision": revision,
        "status": "PENDING",
        "title": f"Task {task_id}",
        "objective": {"desired_state": f"Deliver {task_id}"},
        "acceptance": [f"{task_id} accepted"],
        "required_evidence": ["exact evidence"],
        "required_capabilities": [f"cap.{task_id.lower()}"],
        "candidate_capabilities": [f"candidate.{task_id.lower()}"],
        "dependencies": [],
        "write_scope": {"authority": "TASK_OWNED_ONLY", "execution_root": "/work", "allowed_paths": ["/work"]},
        "execution_guidance": {"authority": "TASK_RECORD_GUIDANCE_ONLY", "procedure": [f"Execute {task_id}"]},
    }
    body = {k: v for k, v in task.items() if k != "task_record_sha256"}
    task["task_record_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return task


def _program(current: str = "T0", count: int = 9) -> dict:
    tasks = [_task(f"T{i}") for i in range(count)]
    current_task = next(row for row in tasks if row["task_id"] == current)
    return {
        "schema": "minitz.living_task_program/v1",
        "program_id": "MINITZ_REBORN_SINGLE_TASK_PROGRAM",
        "revision": 1,
        "task_count": len(tasks),
        "current_execution": {
            "task_id": current,
            "task_revision": current_task["revision"],
            "task_sha256": current_task["task_record_sha256"],
        },
        "tasks": tasks,
    }


def test_guidance_generation_starts_six_tasks_ahead_and_carries_capability_context():
    program = _program()
    documents = guidance.build_guidance_documents(program, start_offset=6)

    assert list(documents) == ["T6", "T7", "T8"]
    row = documents["T6"]
    assert row["schema"] == "minitz.task_guidance_projection/v1"
    assert row["authority"] == "NONE"
    assert row["progression_authority"] is False
    assert row["task_record_sha256"] == program["tasks"][6]["task_record_sha256"]
    assert row["capability_context"]["required"] == ["cap.t6"]
    assert row["capability_context"]["candidates"] == ["candidate.t6"]
    assert row["capability_context"]["promotion"] == "VALIDATED_CANDIDATE_ONLY"
    assert row["capability_context"]["system_promotion_authority"] is False
    assert row["execution_guidance"]["procedure"] == ["Execute T6"]


def test_writer_persists_boundary_manifest_and_digest_bound_files(tmp_path: Path):
    program = _program()
    program_path = tmp_path / "TASK_PROGRAM.json"
    program_path.write_text(json.dumps(program) + "\n", encoding="utf-8")

    receipt = guidance.write_guidance_documents(program_path, start_offset=6)
    root = tmp_path / "task_guidance"
    manifest = json.loads((root / "MANIFEST.json").read_text())
    row = json.loads((root / "T6.json").read_text())

    assert receipt["first_guided_task"] == "T6"
    assert receipt["guide_count"] == 3
    assert manifest["activation_start_task_id"] == "T6"
    assert manifest["origin_current_task_id"] == "T0"
    assert manifest["origin_offset"] == 6
    assert row["task_id"] == "T6"
    assert row["task_record_sha256"] == program["tasks"][6]["task_record_sha256"]


def test_refresh_preserves_original_activation_boundary_after_current_task_advances(tmp_path: Path):
    program_path = tmp_path / "TASK_PROGRAM.json"
    program_path.write_text(json.dumps(_program()) + "\n", encoding="utf-8")
    guidance.write_guidance_documents(program_path, start_offset=6)

    advanced = _program(current="T2")
    program_path.write_text(json.dumps(advanced) + "\n", encoding="utf-8")
    receipt = guidance.write_guidance_documents(program_path, start_offset=6)

    assert receipt["first_guided_task"] == "T6"
    assert (tmp_path / "task_guidance" / "T6.json").is_file()


def test_loader_rejects_stale_guidance_after_task_identity_changes(tmp_path: Path):
    program = _program()
    root = tmp_path / "task_guidance"
    root.mkdir()
    row = guidance.build_guidance_documents(program, start_offset=6)["T6"]
    (root / "T6.json").write_text(json.dumps(row) + "\n", encoding="utf-8")

    assert guidance.load_task_guidance(program, "T6", root) is not None
    changed = _program()
    changed_task = changed["tasks"][6]
    changed_task["revision"] = 2
    changed_task["title"] = "changed"
    body = {k: v for k, v in changed_task.items() if k != "task_record_sha256"}
    changed_task["task_record_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    assert guidance.load_task_guidance(changed, "T6", root) is None


def test_booster_context_pack_exposes_matching_task_guidance(tmp_path: Path):
    program = _program(current="T6")
    root = tmp_path / "task_guidance"
    root.mkdir()
    row = guidance.build_guidance_for_task(program["tasks"][6])
    (root / "T6.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
    ledger = {"allowed_work_status": [], "items": []}

    pack = booster_sync.build_context_pack(
        program, ledger, "BOOST-02", memory_index={"records": [], "content": {}},
        projection=None, provider_registry={}, guidance_root=root,
    )

    assert pack["selected_task"]["task_id"] == "T6"
    assert pack["task_guidance"]["task_id"] == "T6"
    assert pack["task_guidance"]["capability_context"]["required"] == ["cap.t6"]
    assert "write_scope" not in pack["task_guidance"]


def test_installer_deploys_task_guidance_runtime_module():
    installer = (ROOT / "ops/local-ai/install-biella-ai.sh").read_text(encoding="utf-8")
    assert '"$SOURCE_DIR/minitz_task_guidance.py"' in installer


def test_explicit_offset_change_overrides_stale_derived_manifest_from_same_origin(tmp_path: Path):
    program_path = tmp_path / "TASK_PROGRAM.json"
    program_path.write_text(json.dumps(_program()) + "\n", encoding="utf-8")
    guidance.write_guidance_documents(program_path, start_offset=2)
    first = json.loads((tmp_path / "task_guidance/MANIFEST.json").read_text())
    assert first["activation_start_task_id"] == "T2"

    receipt = guidance.write_guidance_documents(program_path, start_offset=6)
    manifest = json.loads((tmp_path / "task_guidance/MANIFEST.json").read_text())

    assert receipt["first_guided_task"] == "T6"
    assert manifest["origin_current_task_id"] == "T0"
    assert manifest["origin_offset"] == 6
    assert manifest["activation_start_task_id"] == "T6"
    assert not (tmp_path / "task_guidance/T2.json").exists()
