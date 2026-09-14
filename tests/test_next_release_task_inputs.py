from pathlib import Path
import hashlib
import json
import os
import sys
import pytest

ROOT = Path(os.environ.get("MINITZ_TEST_REPO", Path(__file__).resolve().parents[1]))
GAME = ROOT / "projects/minitz-games"
sys.path.insert(0, str(ROOT / "ops/local-ai"))
import minitz_production_state as state
import minitz_production_runner as runner
import minitz_execution_map as execution_map
import minitz_task_ledger as ledger

IDS = [*(f"D15-{n:02d}" for n in range(1,5)), *(f"D16-{n:02d}" for n in range(1,9))]

@pytest.mark.parametrize("task_id", IDS)
def test_next_task_has_current_game_scoped_source_and_real_guide(task_id):
    entry = execution_map.task_entry(ROOT, task_id)
    assert entry["execution_root"] == "projects/minitz-games"
    assert entry["lane"] == "Games"
    relative = f"projects/minitz-games/docs/task-guides/{task_id}.md"
    guide = ROOT / relative
    assert guide.is_file(), relative
    refs = {ref["path"]:ref for ref in entry["source_refs"]}
    assert relative in refs
    assert not any(path.startswith("docs/future/") for path in refs)
    assert hashlib.sha256(guide.read_bytes()).hexdigest() == refs[relative]["sha256"]
    for section in ("Objective", "Required deliverable", "Validation contract", "Required evidence", "Reuse boundary"):
        assert f"## {section}" in guide.read_text()
    assert execution_map.task_working_directory(ROOT, GAME, task_id) == GAME.resolve()

@pytest.mark.parametrize("task_id", IDS)
def test_authoritative_runner_embeds_current_guide_without_old_control_envelope(task_id, tmp_path):
    production = state.load_project_production(GAME)
    task = state.find_task(production, task_id)
    context = runner._task_prompt(ROOT, production, task,
        {"session_task_id":task_id,"task_session_id":"test-resume-session"}, tmp_path / "capsule.json")
    assert f"# {task_id} Task Guide" in context
    assert "docs/future/aaa-challenger" not in context
    assert "FUTURE_BLOCKED" not in context
    assert "PRODUCTION_PRIORITY: GAME_FIRST" in context
    assert "Reuse boundary" in context


def test_release_reuse_preserves_real_reproducibility_and_platform_evidence():
    d08 = (GAME / "docs/task-guides/D08-01.md").read_text()
    d1601 = (GAME / "docs/task-guides/D16-01.md").read_text()
    d1602 = (GAME / "docs/task-guides/D16-02.md").read_text()
    d1603 = (GAME / "docs/task-guides/D16-03.md").read_text()
    assert "Cross-task evidence reuse" in d08
    assert "same material inputs" in d1601
    assert "two distinct actual executions" in d1602
    assert "different source" in d1602
    assert "outside the editor" in d1603
    assert "Windows PC x64 first" in d08
    assert "Do not silently call a Linux package" in d08
    assert "D08-01-resource-observation.json" in d08


def test_ledger_uses_same_operational_inputs_and_order():
    production = state.load_project_production(GAME)
    built = ledger.build_task_ledger(ROOT, production)
    entries = {row["task_id"]:row for row in built["tasks"]}
    assert built["registry_is_queue"] is False
    assert built["priority_policy"] == "GAME_FIRST"
    for task_id in IDS:
        assert entries[task_id]["execution"]["lane"] == "Games"
        assert entries[task_id]["execution"]["source_refs"] == execution_map.task_entry(ROOT, task_id)["source_refs"]
    order = built["execution_order"]
    assert order.index("D08-01") < order.index("D15-01") < order.index("D16-01") < order.index("D09-06")


def test_metadata_tasks_bind_existing_proof_without_runtime_or_publication_gate():
    for task_id in IDS[:4]:
        guide = (GAME / f"docs/task-guides/{task_id}.md").read_text()
        assert "does not freeze" in guide
        assert "no build or runtime rerun" in guide
        assert "publication cursor" in guide
    final = execution_map.task_entry(ROOT, "D16-08")
    assert "only when published" in final["required_evidence"]
    assert "reviewer" not in final["objective"].lower()
