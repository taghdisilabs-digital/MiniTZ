from __future__ import annotations

import importlib.util
import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/minitz_boost_fabric.py"
TASK_PROGRAM = Path("/root/biella/analysis/live_audit/TASK_PROGRAM.json")


def load_module():
    assert MODULE.is_file(), "five-Boost fabric is not implemented"
    spec = importlib.util.spec_from_file_location("minitz_boost_fabric", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def live_program() -> dict:
    return json.loads(TASK_PROGRAM.read_text(encoding="utf-8"))


def test_exactly_five_boosts_partition_all_thirty_commanders_once():
    mod = load_module()
    groups = mod.boost_groups()
    assert [g.boost_id for g in groups] == [f"BOOST-{i:02d}" for i in range(1, 6)]
    assert all(len(g.commander_lanes) == 6 for g in groups)
    lanes = [lane for group in groups for lane in group.commander_lanes]
    assert sorted(lanes) == [f"CMD-{i:02d}" for i in range(1, 31)]
    assert len(lanes) == len(set(lanes)) == 30


def test_task_plan_keeps_canonical_task_count_and_creates_five_derived_lists():
    mod = load_module()
    program = live_program()
    plan = mod.build_task_plan(program)
    assert plan["schema"] == "minitz.five_boost_task_plan/v1"
    assert plan["authority"] == "NONE"
    assert plan["progression_authority"] is False
    assert plan["canonical_task_count"] == len(program["tasks"]) == 800
    assert set(plan["boost_task_lists"]) == {f"BOOST-{i:02d}" for i in range(1, 6)}
    assert all(len(rows) == 800 for rows in plan["boost_task_lists"].values())
    assert plan["source_program_id"] == program["program_id"]
    assert plan["source_program_revision"] == program["revision"]


def test_each_task_has_disjoint_boost_write_paths_and_preserves_union():
    mod = load_module()
    program = live_program()
    plan = mod.build_task_plan(program)
    by_id = {task["task_id"]: task for task in program["tasks"]}
    for task_id in list(by_id)[:80]:
        task = by_id[task_id]
        sections = [plan["boost_task_lists"][f"BOOST-{i:02d}"][list(by_id).index(task_id)] for i in range(1, 6)]
        path_sets = [set(row["allowed_write_paths"]) for row in sections]
        for i, left in enumerate(path_sets):
            for right in path_sets[i + 1:]:
                assert left.isdisjoint(right)
        expected = set((task.get("write_scope") or {}).get("allowed_paths") or [])
        assert set().union(*path_sets) == expected


def test_boost_plan_uses_reserved_usage_without_quota_probe_and_waits_for_owner_resume():
    mod = load_module()
    plan = mod.build_task_plan(live_program())
    routing = plan["reserved_usage_policy"]
    assert routing["preferred_model"] == "gpt-reserve"
    assert routing["catalog_eligibility_required"] is True
    assert routing["quota_probe_forbidden"] is True
    assert routing["fallback_to_task_class_routes"] is True
    assert plan["start_policy"] == "WITH_PRODUCTION_OWNER_RESUME"
    assert plan["runtime_state"] == "ARMED_NOT_STARTED"
    assert plan["desired_boost_workers"] == 5


def test_current_task_sections_bind_exact_task_revision_and_digest():
    mod = load_module()
    program = live_program()
    current_id = program["current_execution"]["task_id"]
    task = next(row for row in program["tasks"] if row["task_id"] == current_id)
    plan = mod.build_task_plan(program)
    for boost_id, rows in plan["boost_task_lists"].items():
        row = next(item for item in rows if item["canonical_task_id"] == current_id)
        assert row["section_id"] == f"{current_id}::{boost_id}"
        assert row["task_revision"] == task["revision"]
        assert row["task_record_sha256"] == task["task_record_sha256"]
        assert row["progression_authority"] is False


def test_refresh_writes_one_shared_current_and_five_exact_assignments(tmp_path):
    mod = load_module()
    plan_path, current_path = mod.refresh_runtime(tmp_path, live_program())
    assert plan_path.is_file() and current_path.is_file()
    current = json.loads(current_path.read_text(encoding="utf-8"))
    assert current["schema"] == "minitz.boost_fabric/v1"
    assert current["authority"] == "NONE"
    assert current["progression_authority"] is False
    assert current["runtime_state"] == "ARMED_NOT_STARTED"
    assert len(current["boosts"]) == 5
    assert all(Path(row["assignment_path"]).is_file() for row in current["boosts"])


def test_public_summary_hides_private_assignment_paths_and_write_scope(tmp_path):
    mod = load_module()
    _, current_path = mod.refresh_runtime(tmp_path, live_program())
    current = json.loads(current_path.read_text(encoding="utf-8"))
    public = mod.public_summary(current)
    rendered = json.dumps(public)
    assert public["total_boosts"] == 5
    assert public["total_commanders"] == 30
    assert "assignment_path" not in rendered
    assert "allowed_write_paths" not in rendered


def test_worker_report_is_bound_to_exact_boost_task_and_updates_status(tmp_path):
    mod = load_module(); program = live_program()
    _, current_path = mod.refresh_runtime(tmp_path, program)
    task = next(row for row in program["tasks"] if row["task_id"] == program["current_execution"]["task_id"])
    report = mod.record_worker_report(
        tmp_path, "BOOST-02", task_id=task["task_id"], task_record_sha256=task["task_record_sha256"],
        status="ACTIVE", summary="core implementation", source_program_sha256=mod.build_task_plan(program)["source_program_sha256"],
    )
    assert report.is_file()
    _, current_path = mod.refresh_runtime(tmp_path, program)
    current = json.loads(current_path.read_text())
    boost = next(row for row in current["boosts"] if row["boost_id"] == "BOOST-02")
    assert boost["status"] == "ACTIVE"
    assert boost["worker_report_path"] == str(report)


def test_worker_report_rejects_stale_or_foreign_task_identity(tmp_path):
    mod = load_module(); program = live_program(); task = next(row for row in program["tasks"] if row["task_id"] == program["current_execution"]["task_id"])
    mod.refresh_runtime(tmp_path, program)
    with pytest.raises(ValueError):
        mod.record_worker_report(tmp_path, "BOOST-02", task_id="OTHER", task_record_sha256=task["task_record_sha256"], status="ACTIVE", source_program_sha256=mod.build_task_plan(program)["source_program_sha256"])
    with pytest.raises(ValueError):
        mod.record_worker_report(tmp_path, "BOOST-02", task_id=task["task_id"], task_record_sha256="0"*64, status="ACTIVE", source_program_sha256=mod.build_task_plan(program)["source_program_sha256"])


def test_plan_declares_linux_hal_trust_browser_and_cache_prerequisites_without_false_ready_claims():
    mod = load_module(); plan = mod.build_task_plan(live_program())
    q = plan["qualification_prerequisites"]
    assert q["hal"]["driver_domain"] == "LINUX_ONLY"
    assert q["hal"]["host_kernel_bypass_claimed"] is False
    assert q["hal"]["state"] == "QUALIFICATION_REQUIRED"
    assert q["trust"]["raw_secret_values_allowed"] is False
    assert q["trust"]["state"] == "QUALIFICATION_REQUIRED"
    assert q["swarm"]["desired_boost_workers"] == 5
    assert q["swarm"]["desired_commander_lanes"] == 30
    assert q["swarm"]["desired_browser_automation_slots"] == 30
    assert q["swarm"]["runtime_state"] == "ARMED_NOT_STARTED"
    assert q["validation"]["digest"] == "SHA-256"
    assert q["validation"]["cache_efficiency_target"] == 0.98
    assert q["validation"]["observed_cache_efficiency"] is None
