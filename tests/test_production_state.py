from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/biella_production_state.py"
spec = importlib.util.spec_from_file_location("biella_production_state", MODULE)
assert spec and spec.loader
state = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = state
spec.loader.exec_module(state)


def write_fixture(root: Path, *, active_id: str, project_id: str, d01_029: str = "COMPLETE"):
    repo = root / "repo"
    project = repo / "projects/biella-games"
    (repo / "docs/project-state").mkdir(parents=True)
    (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").write_text(
        f"active_execution:\n  id: {active_id}\n  state: READY\n", encoding="utf-8")
    (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").write_text(
        f"task:\n  id: {active_id}\n  project: Biella Games\n  section: demo01\n  class: hard\n  title: Active task\n  status: PENDING\n", encoding="utf-8")
    production = (
        "# Biella Games Production\n\nStatus: `IN_PROGRESS`\nCurrent section: `demo01`\n"
        f"Current task: `{project_id}`\n\n## Section: demo01 | Demo | IN_PROGRESS\n\n"
        f"- [x] D01-029 | hard | Prior task | {d01_029} | prior evidence\n"
        "- [ ] D01-030 | hard | Current task | PENDING | current evidence\n"
        "- [ ] D01-031 | hard | Next task | PENDING | next evidence\n")
    (project / "docs/PRODUCTION.md").write_text(production, encoding="utf-8")
    return repo, project


def test_resolve_current_task_requires_active_and_project_to_agree(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    resolved = state.resolve_current_task(repo, project)
    assert resolved.id == "D01-030"
    assert resolved.task_class == "hard"


def test_completed_project_task_repairs_stale_active_pointer(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-029", project_id="D01-030")
    resolved = state.resolve_current_task(repo, project)
    assert resolved.id == "D01-030"
    active = state.load_active_task(repo)
    assert active.id == "D01-030"


def test_mark_complete_advances_project_and_active_task(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    state.mark_task_complete(repo, project, "D01-030", "COMPLETE", ["runtime pass"])
    production = state.load_project_production(project)
    assert state.find_task(production, "D01-030").status == "COMPLETE"
    assert production.current_task == "D01-031"
    assert state.load_active_task(repo).id == "D01-031"


def test_no_legacy_json_state_is_created(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    state.resolve_current_task(repo, project)
    assert not list(tmp_path.rglob("games-production.json"))


def test_resolve_migrates_legacy_feeder_fields_to_runner(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    p03 = repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md"
    p04 = repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md"
    p03.write_text(p03.read_text().replace("  state: READY\n", "  state: READY\n  feeder: STOPPED_BY_OWNER\n"))
    p04.write_text(p04.read_text().replace("  status: PENDING\n", "  status: PENDING\n  feeder: STOPPED_BY_OWNER\n"))
    resolved = state.resolve_current_task(repo, project)
    assert resolved.id == "D01-030"
    assert "feeder:" not in p03.read_text()
    assert "feeder:" not in p04.read_text()
    assert "runner:" in p03.read_text()
    assert "runner:" in p04.read_text()
