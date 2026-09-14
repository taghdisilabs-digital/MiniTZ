from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))

import minitz_task_program as minitz

LIVE = minitz.program_path()
if not LIVE.is_file():
    LIVE = Path("/minitz-live/TASK_PROGRAM.json")


def program_copy(tmp_path: Path) -> Path:
    raw = json.loads(LIVE.read_text(encoding="utf-8"))
    active = [row for row in raw["tasks"] if row.get("status") in minitz.ACTIVE_STATUSES]
    if active and active[0].get("status") == "WORKING":
        first = active[0]
        first["status"] = "PENDING"
        first.pop("workers", None)
        first.pop("worker_state_sha256", None)
        first["task_record_sha256"] = minitz.task_digest(first)
    raw.pop("current_execution", None)
    path = tmp_path / "TASK_PROGRAM.json"
    raw["current_live_production_authority"] = str(path.resolve())
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    return path


def task(task_id: str, dependency: str) -> dict:
    return {
        "task_id": task_id, "revision": 1, "status": "PENDING",
        "active_task_survival": True, "review_state": "VALUE_GATE_PASSED",
        "title": task_id, "scope": "MINITZ DEEP ENGINEERING",
        "dependencies": [{"dependency_type": "HARD", "task_ref": dependency}],
        "write_scope": {
            "authority": "TASK_OWNED_ONLY",
            "execution_root": "/root/biella/repos/biella-engine",
            "allowed_paths": [f"src/biella/{task_id.lower().replace('-', '_')}.py"],
        },
        "objective": {"desired_state": f"Implement {task_id}."},
        "deliverables": [f"{task_id} implementation"],
        "acceptance": ["functional evidence exists"],
        "negative_controls": ["no second progression authority"],
        "required_capabilities": ["system.integration.qualify"],
        "source_refs": [], "required_evidence": [], "validation": [],
    }


def test_insert_tasks_is_transactional_and_preserves_current_execution(tmp_path):
    path = program_copy(tmp_path)
    before = minitz.load(path)
    current = copy.deepcopy(before["current_execution"])
    revision = before["revision"]
    count = before["task_count"]
    anchor_id = current["task_id"]
    new = [task("HAL-LINUX-TEST", anchor_id), task("TRUST-TEST", "HAL-LINUX-TEST")]
    identity = minitz.insert_tasks_after(
        anchor_id, new, evidence=["owner-approved architecture expansion"], path=path
    )
    after = minitz.load(path)
    assert identity["task_count"] == count + 2
    assert after["revision"] == revision + 1
    assert after["current_execution"] == current
    ids = [row["task_id"] for row in after["tasks"]]
    anchor = ids.index(anchor_id)
    assert ids[anchor + 1:anchor + 3] == ["HAL-LINUX-TEST", "TRUST-TEST"]
    assert minitz.task_by_id(after, "HAL-LINUX-TEST")["task_record_sha256"] == minitz.task_digest(
        minitz.task_by_id(after, "HAL-LINUX-TEST")
    )


def test_insert_tasks_is_idempotent_only_for_exact_existing_extension(tmp_path):
    path = program_copy(tmp_path)
    anchor_id = minitz.load(path)["current_execution"]["task_id"]
    new = [task("HAL-LINUX-TEST", anchor_id)]
    first = minitz.insert_tasks_after(
        anchor_id, new, evidence=["owner-approved architecture expansion"], path=path
    )
    second = minitz.insert_tasks_after(
        anchor_id, new, evidence=["owner-approved architecture expansion"], path=path
    )
    assert second == first
    conflict = task("HAL-LINUX-TEST", anchor_id)
    conflict["title"] = "different"
    with pytest.raises(ValueError):
        minitz.insert_tasks_after(
            anchor_id, [conflict], evidence=["owner-approved architecture expansion"], path=path
        )


def test_public_program_never_persists_derived_current_execution(tmp_path):
    path = program_copy(tmp_path)
    loaded = minitz.load(path)
    assert loaded["current_execution"]["task_id"]
    public = minitz.public_program(loaded)
    assert "current_execution" not in public


def test_first_active_row_is_the_only_current_task_even_if_later_task_is_dependency_runnable(tmp_path):
    path = program_copy(tmp_path)
    raw = json.loads(path.read_text())
    active = [row for row in raw["tasks"] if row["status"] in minitz.ACTIVE_STATUSES]
    first, later = active[0], active[1]
    first["dependencies"] = [{"dependency_type": "HARD", "task_ref": later["task_id"], "reason": "blocked on later row for negative control"}]
    first["task_record_sha256"] = minitz.task_digest(first)
    raw.pop("current_execution", None)
    path.write_text(json.dumps(raw, indent=2) + "\n")
    program = minitz.load(path)
    with pytest.raises(ValueError, match="first active MiniTZ task is blocked"):
        minitz.current_task(program)


def test_claim_task_marks_same_task_working_and_records_writer_in_same_row(tmp_path):
    path = program_copy(tmp_path)
    before = minitz.load(path)
    current = minitz.current_task(before)
    assert current is not None
    identity = minitz.claim_task(
        current["task_id"], worker_id="codex:gpt-5.6", worker_role="PRIMARY_WRITER",
        write_authority=True, evidence=["owner single-task authority test"], path=path,
    )
    assert identity["revision"] == before["revision"] + 1
    raw = json.loads(path.read_text())
    assert "current_execution" not in raw
    claimed = next(row for row in raw["tasks"] if row["task_id"] == current["task_id"])
    assert claimed["status"] == "WORKING"
    assert claimed["workers"][0]["worker_id"] == "codex:gpt-5.6"
    assert claimed["workers"][0]["status"] == "WORKING"
    loaded = minitz.load(path)
    assert loaded["current_execution"]["task_id"] == current["task_id"]
    assert minitz.current_task(loaded)["task_id"] == current["task_id"]


def test_read_only_worker_can_join_without_changing_task_definition_digest(tmp_path):
    path = program_copy(tmp_path)
    current = minitz.current_task(minitz.load(path))
    assert current is not None
    minitz.claim_task(current["task_id"], worker_id="codex:writer", worker_role="PRIMARY_WRITER", write_authority=True,
                      evidence=["writer claim"], path=path)
    working = minitz.task_by_id(minitz.load(path), current["task_id"])
    revision = working["revision"]
    definition_digest = working["task_record_sha256"]
    minitz.claim_task(current["task_id"], worker_id="qwen:helper", worker_role="READ_ONLY_ASSIST", write_authority=False,
                      evidence=["helper claim"], path=path)
    joined = minitz.task_by_id(minitz.load(path), current["task_id"])
    assert joined["revision"] == revision
    assert joined["task_record_sha256"] == definition_digest
    assert [worker["worker_id"] for worker in joined["workers"]] == ["codex:writer", "qwen:helper"]


def test_complete_task_requires_working_and_completes_workers(tmp_path):
    path = program_copy(tmp_path)
    current = minitz.current_task(minitz.load(path))
    assert current is not None
    with pytest.raises(ValueError, match="must be WORKING"):
        minitz.complete_task(current["task_id"], "COMPLETE", ["should fail"], path=path)
    minitz.claim_task(current["task_id"], worker_id="codex:writer", worker_role="PRIMARY_WRITER", write_authority=True,
                      evidence=["writer claim"], path=path)
    minitz.complete_task(current["task_id"], "COMPLETE", ["validated completion"], path=path)
    completed = minitz.task_by_id(minitz.load(path), current["task_id"])
    assert completed["status"] == "COMPLETE"
    assert all(worker["status"] == "COMPLETE" for worker in completed["workers"])


def test_rewrite_future_horizon_preserves_current_row_and_replaces_only_suffix(tmp_path):
    path = program_copy(tmp_path)
    before = minitz.load(path)
    current = minitz.current_task(before)
    assert current is not None
    current_before = copy.deepcopy(current)
    future = [copy.deepcopy(row) for row in before["tasks"] if before["tasks"].index(row) > before["tasks"].index(current)]
    inserted = task("CAP-OWNER-TEST", current["task_id"])
    inserted["context_policy"] = {"mode": "TASK_LOCAL_MINIMUM", "hard_token_limit": 24000}
    rewritten = [inserted, *future]
    identity = minitz.rewrite_future_horizon(
        current["task_id"], rewritten,
        program_updates={"task_system_contract": {"authority": "tasks[]", "persisted_task_lists": 1}},
        evidence=["owner requested one detailed task list"], path=path,
    )
    after = minitz.load(path)
    assert identity["revision"] == before["revision"] + 1
    assert minitz.task_by_id(after, current["task_id"]) == current_before
    ids = [row["task_id"] for row in after["tasks"]]
    assert ids[ids.index(current["task_id"]) + 1] == "CAP-OWNER-TEST"
    assert after["task_system_contract"]["authority"] == "tasks[]"
    assert "current_execution" not in json.loads(path.read_text())


def test_task_context_payload_is_bounded_to_declared_task_fields():
    row = task("CTX-TEST", "RUNTIME-AI-01")
    row["procedure"] = ["read exact source", "execute bounded change", "validate"]
    row["context_policy"] = {
        "mode": "TASK_LOCAL_MINIMUM",
        "target_token_budget": 8000,
        "hard_token_limit": 16000,
        "default_fields": ["task_id", "status", "title", "objective", "procedure", "dependencies", "write_scope"],
    }
    row["unrelated_blob"] = "x" * 1000
    payload = minitz.task_context_payload(row)
    assert payload["task_id"] == "CTX-TEST"
    assert payload["procedure"] == row["procedure"]
    assert "unrelated_blob" not in payload
    assert payload["context_policy"]["mode"] == "TASK_LOCAL_MINIMUM"
