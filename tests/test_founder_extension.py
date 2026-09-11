from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))

import minitz_founder_extension as extension
import minitz_task_program as minitz

LIVE = Path("/root/biella/analysis/live_audit/TASK_PROGRAM.json")


def test_extension_is_seven_linux_only_nonduplicate_tasks():
    tasks = extension.extension_tasks()
    ids = [task["task_id"] for task in tasks]
    assert ids == [
        "HAL-LINUX-01", "HAL-FOUNDER-01", "TRUST-NODE-01",
        "GPU-RESIDENCY-01", "BOOST-FABRIC-01", "BROWSER-SWARM-01",
        "SYSTEM-QUALIFY-01",
    ]
    assert len(ids) == len(set(ids)) == 7
    rendered = json.dumps(tasks).lower()
    assert "windows" not in rendered
    assert all(task["active_task_survival"] is True for task in tasks)
    assert all(task["review_state"] == "VALUE_GATE_PASSED" for task in tasks)


def test_extension_dependencies_are_internal_or_existing_canonical_tasks():
    tasks = extension.extension_tasks()
    program = json.loads(LIVE.read_text(encoding="utf-8"))
    known = {task["task_id"] for task in program["tasks"]} | {task["task_id"] for task in tasks}
    for task in tasks:
        for dep in task["dependencies"]:
            assert dep["task_ref"] in known
            assert dep["task_ref"] != task["task_id"]


def test_extension_apply_is_idempotent_and_preserves_canonical_os_order(tmp_path):
    raw = json.loads(LIVE.read_text(encoding="utf-8"))
    path = tmp_path / "TASK_PROGRAM.json"
    raw["current_live_production_authority"] = str(path.resolve())
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    before = minitz.load(path)
    identity = extension.apply_extension(path=path)
    after = minitz.load(path)
    assert identity["task_count"] == before["task_count"]
    assert after["current_execution"] == before["current_execution"]
    assert [task["task_id"] for task in after["tasks"]] == [task["task_id"] for task in before["tasks"]]
    assert [task["task_id"] for task in extension.extension_tasks(path=path)] == [
        "HAL-LINUX-01", "HAL-FOUNDER-01", "TRUST-NODE-01",
        "GPU-RESIDENCY-01", "BOOST-FABRIC-01", "BROWSER-SWARM-01",
        "SYSTEM-QUALIFY-01",
    ]


def test_local_ai_installer_carries_boost_and_founder_modules():
    text = (ROOT / "ops/local-ai/install-biella-ai.sh").read_text(encoding="utf-8")
    assert '"$SOURCE_DIR/minitz_boost_fabric.py"' in text
    assert '"$SOURCE_DIR/minitz_founder_extension.py"' in text
