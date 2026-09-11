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

LIVE = Path("/root/biella/analysis/live_audit/TASK_PROGRAM.json")


def program_copy(tmp_path: Path) -> Path:
    raw = json.loads(LIVE.read_text(encoding="utf-8"))
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
    new = [task("HAL-LINUX-TEST", "RUNTIME-AI-01"), task("TRUST-TEST", "HAL-LINUX-TEST")]
    identity = minitz.insert_tasks_after(
        "RUNTIME-AI-01", new, evidence=["owner-approved architecture expansion"], path=path
    )
    after = minitz.load(path)
    assert identity["task_count"] == count + 2
    assert after["revision"] == revision + 1
    assert after["current_execution"] == current
    ids = [row["task_id"] for row in after["tasks"]]
    anchor = ids.index("RUNTIME-AI-01")
    assert ids[anchor + 1:anchor + 3] == ["HAL-LINUX-TEST", "TRUST-TEST"]
    assert minitz.task_by_id(after, "HAL-LINUX-TEST")["task_record_sha256"] == minitz.task_digest(
        minitz.task_by_id(after, "HAL-LINUX-TEST")
    )


def test_insert_tasks_is_idempotent_only_for_exact_existing_extension(tmp_path):
    path = program_copy(tmp_path)
    new = [task("HAL-LINUX-TEST", "RUNTIME-AI-01")]
    first = minitz.insert_tasks_after(
        "RUNTIME-AI-01", new, evidence=["owner-approved architecture expansion"], path=path
    )
    second = minitz.insert_tasks_after(
        "RUNTIME-AI-01", new, evidence=["owner-approved architecture expansion"], path=path
    )
    assert second == first
    conflict = task("HAL-LINUX-TEST", "RUNTIME-AI-01")
    conflict["title"] = "different"
    with pytest.raises(ValueError):
        minitz.insert_tasks_after(
            "RUNTIME-AI-01", [conflict], evidence=["owner-approved architecture expansion"], path=path
        )
