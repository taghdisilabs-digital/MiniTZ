from pathlib import Path
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))
import biella_production_state as state

MODULE = LOCAL_AI / "biella_task_ledger.py"
spec = importlib.util.spec_from_file_location("biella_task_ledger", MODULE)
assert spec and spec.loader
ledger = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ledger
spec.loader.exec_module(ledger)


def write_registry(repo: Path):
    folder = repo / "docs/task-program"
    folder.mkdir(parents=True)
    rows = """# Map
| Task | Title | Status | Depends on | Legacy alias |
|---|---|---|---|---|
| `D01-29` | Prior task | `PENDING` | D01-28 | `D01-029` |
| `D01-30` | Current task | `COMPLETE` | D01-29 | `D01-030` |
| `D02-01` | Streaming continuity | `PENDING_UNPLANNED` | D01-50 | `GAME-20-WORLD-STREAMING` |
"""
    (folder / "D00_D08_ENGINE_GAMES.md").write_text(rows)
    (folder / "D09_D14_WEBSITE.md").write_text("# Website\n")
    (folder / "D15_D24_AAA_CHALLENGER.md").write_text("# AAA\n")


def write_production(repo: Path):
    project = repo / "projects/biella-games"
    (project / "docs").mkdir(parents=True)
    (project / "docs/PRODUCTION.md").write_text(
        "# Production\n\nStatus: `IN_PROGRESS`\nCurrent section: `demo01`\n"
        "Current task: `D01-030`\n\n"
        "## Section: demo01 | Demo | IN_PROGRESS\n\n"
        "- [x] D01-029 | hard | Prior task | COMPLETE | runtime evidence\n"
        "- [ ] D01-030 | hard | Current task | PENDING | \n\n"
        "## Section: stage2 | Expansion | PENDING_UNPLANNED\n",
        encoding="utf-8",
    )
    return project


def test_ledger_overlays_live_project_status_over_stale_registry(tmp_path: Path):
    repo = tmp_path / "repo"
    write_registry(repo)
    project = write_production(repo)
    production = state.load_project_production(project)
    payload = ledger.sync_task_ledger(repo, production)
    rows = {item["task_id"]: item for item in payload["tasks"]}
    assert rows["D01-29"]["status"] == "COMPLETE"
    assert rows["D01-30"]["status"] == "PENDING"
    assert rows["D01-29"]["status_source"] == "projects/biella-games/docs/PRODUCTION.md"
    assert rows["D02-01"]["status"] == "PENDING_UNPLANNED"
    assert payload["registry_is_queue"] is False
    assert payload["current_task"] == "D01-30"
    assert all(ledger.CANONICAL_ID_RE.fullmatch(item["task_id"]) for item in payload["tasks"])


def test_ledger_bytes_are_deterministic_when_state_is_unchanged(tmp_path: Path):
    repo = tmp_path / "repo"
    write_registry(repo)
    project = write_production(repo)
    production = state.load_project_production(project)
    ledger.sync_task_ledger(repo, production)
    path = repo / "docs/task-program/D_TASK_LEDGER.json"
    first = path.read_bytes()
    ledger.sync_task_ledger(repo, production)
    assert path.read_bytes() == first


def test_ledger_adds_live_dynamic_tasks_not_yet_in_registry(tmp_path: Path):
    repo = tmp_path / "repo"
    write_registry(repo)
    project = write_production(repo)
    path = project / "docs/PRODUCTION.md"
    text = path.read_text().replace(
        "## Section: stage2 | Expansion | PENDING_UNPLANNED\n",
        "## Section: stage2 | Expansion | IN_PROGRESS\n\n- [ ] D02-02 | medium | Population scaling | PENDING | \n",
    )
    path.write_text(text)
    payload = ledger.sync_task_ledger(repo, state.load_project_production(project))
    rows = {item["task_id"]: item for item in payload["tasks"]}
    assert rows["D02-02"]["title"] == "Population scaling"
    assert rows["D02-02"]["status_source"] == "projects/biella-games/docs/PRODUCTION.md"
