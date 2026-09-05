from pathlib import Path
import importlib.util
import json
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))
import biella_production_state as state
import biella_codex_routing as routing

MODULE = LOCAL_AI / "biella_production_evidence.py"
spec = importlib.util.spec_from_file_location("biella_production_evidence", MODULE)
assert spec and spec.loader
evidence = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evidence
spec.loader.exec_module(evidence)


def fixture(root: Path):
    repo = root / "repo"; project = repo / "projects/biella-games"
    (repo / "docs/project-state").mkdir(parents=True); (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").write_text("active_execution:\n  id: D01-030\n  state: PENDING\ngames:\n  completed_demo_tasks: 29\n  queued_successor: D01-030\n", encoding="utf-8")
    (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").write_text("task:\n  id: D01-030\n  project: Biella Games\n  section: demo01\n  class: hard\n  title: Rival combat\n  status: PENDING\n", encoding="utf-8")
    (project / "docs/PRODUCTION.md").write_text("# P\n\nStatus: `IN_PROGRESS`\nCurrent section: `demo01`\nCurrent task: `D01-030`\n\n## Section: demo01 | Demo | IN_PROGRESS\n\n- [x] D01-029 | hard | Prior | COMPLETE | prior\n- [ ] D01-030 | hard | Rival combat | PENDING | \n- [ ] D01-031 | hard | Interaction | PENDING | \n", encoding="utf-8")
    return repo, project


def write_result(path: Path, task_id: str, status: str, evidence_items=None):
    path.write_text(json.dumps({"task_id": task_id, "status": status, "summary": "done", "evidence": evidence_items or []}), encoding="utf-8")
    return path


def test_result_task_id_must_match(tmp_path: Path):
    path = write_result(tmp_path / "result.json", "D01-999", "COMPLETE", ["runtime pass"])
    with pytest.raises(ValueError, match="task_id mismatch"):
        evidence.parse_result(path, "D01-030")


def test_complete_requires_evidence(tmp_path: Path):
    path = write_result(tmp_path / "result.json", "D01-030", "COMPLETE", [])
    with pytest.raises(ValueError, match="evidence"):
        evidence.parse_result(path, "D01-030")


def test_complete_updates_project_and_active_task(tmp_path: Path):
    repo, project = fixture(tmp_path)
    result = evidence.TaskResult("D01-030", "COMPLETE", "done", ("runtime pass",))
    evidence.apply_result(repo, project, result, routing.Route("gpt-6-astra", "ultra"))
    assert state.find_task(state.load_project_production(project), "D01-030").status == "COMPLETE"
    assert state.load_active_task(repo).id == "D01-031"


def test_continue_does_not_advance(tmp_path: Path):
    repo, project = fixture(tmp_path)
    result = evidence.TaskResult("D01-030", "CONTINUE", "more work", ("partial",))
    evidence.apply_result(repo, project, result, routing.Route("gpt-6-astra", "ultra"))
    assert state.load_active_task(repo).id == "D01-030"
