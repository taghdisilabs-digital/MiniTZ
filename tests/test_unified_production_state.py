from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ops/local-ai/biella_codex_feeder.py"
spec = importlib.util.spec_from_file_location("unified_feeder", MODULE_PATH)
assert spec and spec.loader
feeder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = feeder
spec.loader.exec_module(feeder)


def write_project(root: Path) -> Path:
    docs = root / "docs"
    docs.mkdir(parents=True)
    (docs / "PRODUCTION.md").write_text(
        "# Biella Games Production\n\n"
        "Status: `IN_PROGRESS`\nCurrent section: `demo01`\nCurrent task: `D01-003`\n\n"
        "## Section: demo01 | Demo | IN_PROGRESS\n\n"
        "- [x] D01-001 | deep_memory | Resolve truth | COMPLETE | observed\n"
        "- [x] D01-002 | simple | Build | COMPLETE_ALREADY | build pass\n"
        "- [ ] D01-003 | medium | Add weapon | PENDING | input-to-hit evidence\n\n"
        "## Section: stage2 | Open world | PENDING_UNPLANNED\n\n"
        "Roadmap source.\n",
        encoding="utf-8",
    )
    return root


def test_project_production_is_the_only_durable_completion_source(tmp_path: Path):
    project = write_project(tmp_path / "projects/biella-games")
    state = feeder.load_project_production(project)
    assert state["current_section"] == "demo01"
    assert state["current_task"] == "D01-003"
    assert [t["id"] for t in state["sections"][0]["tasks"]] == ["D01-001", "D01-002", "D01-003"]
    assert feeder.next_production_task(state).id == "D01-003"
    assert not (tmp_path / "games-production.json").exists()


def test_runtime_state_contains_telemetry_not_completion(tmp_path: Path):
    runtime = feeder.initial_runtime_state()
    assert set(runtime) >= {"status", "cooldowns", "attempt_seq", "last_result", "heartbeat_at"}
    for forbidden in ("sections", "tasks", "completed", "current_section", "current_task"):
        assert forbidden not in runtime
    path = tmp_path / "runtime.json"
    feeder.save_runtime_state(path, runtime)
    assert feeder.load_runtime_state(path) == runtime


def test_status_derives_progress_from_project_and_liveness_from_runtime(tmp_path: Path, monkeypatch):
    project = write_project(tmp_path / "projects/biella-games")
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    runtime = feeder.initial_runtime_state()
    runtime.update({"status": "RUNNING", "active_model": "gpt-6-astra", "active_reasoning": "ultra", "heartbeat_at": "2026-09-05T00:00:00+00:00"})
    feeder.save_runtime_state(runtime_root / "runtime.json", runtime)
    monkeypatch.setattr(feeder, "_service_active", lambda _unit: True)
    now = datetime(2026, 9, 5, 0, 0, 30, tzinfo=timezone.utc)
    payload = feeder.production_status_payload(project, runtime_root=runtime_root, now=now)
    assert payload["status"] == "ACTIVE"
    assert payload["completed"] == 2 and payload["total"] == 3
    assert payload["current_task"] == "D01-003"
    assert payload["active_model"] == "gpt-6-astra"
    stale = feeder.production_status_payload(project, runtime_root=runtime_root, now=datetime(2026, 9, 5, 0, 3, 0, tzinfo=timezone.utc))
    assert stale["status"] == "STALE"


def test_complete_result_updates_same_production_file(tmp_path: Path):
    project = write_project(tmp_path / "projects/biella-games")
    feeder.mark_project_task_complete(project, "D01-003", "COMPLETE", ["runtime hit pass"])
    state = feeder.load_project_production(project)
    task = feeder.find_task(state, "D01-003")
    assert task["status"] == "COMPLETE"
    assert task["evidence"] == ["runtime hit pass"]
    assert state["current_section"] == "stage2"
    assert state["current_task"] is None


def test_cli_status_uses_project_root_without_legacy_production_file(tmp_path: Path):
    import os
    import subprocess
    project = write_project(tmp_path / "projects/biella-games")
    runtime_root = tmp_path / "runtime"
    env = os.environ.copy()
    env["BIELLA_GAMES_PROJECT_ROOT"] = str(project)
    env["BIELLA_CODEX_FEED_RUNTIME_ROOT"] = str(runtime_root)
    result = subprocess.run([sys.executable, str(MODULE_PATH), "status"], env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "STOPPED"
    assert payload["current_task"] == "D01-003"
    help_result = subprocess.run([sys.executable, str(MODULE_PATH), "--help"], env=env, text=True, capture_output=True, check=False)
    assert help_result.returncode == 0
    assert "init" not in help_result.stdout
    assert "sync" in help_result.stdout
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "BIELLA_GAMES_PRODUCTION_FILE" not in source
    assert "/root/biella/work/games-production.json" not in source


def test_section_plan_persists_into_same_project_file(tmp_path: Path):
    project = write_project(tmp_path / "projects/biella-games")
    # Complete Demo so stage2 is current and unplanned.
    feeder.mark_project_task_complete(project, "D01-003", "COMPLETE", ["done"])
    plan = {
        "section_id": "stage2",
        "complete": False,
        "summary": "bounded stage2 work",
        "evidence": ["roadmap"],
        "tasks": [
            {"class": "hard", "title": "Implement world streaming continuity"},
            {"class": "creation", "title": "Create readable streamed-region transition"},
        ],
    }
    feeder.apply_section_plan_to_project(project, "stage2", plan)
    state = feeder.load_project_production(project)
    stage2 = next(section for section in state["sections"] if section["id"] == "stage2")
    assert [task["id"] for task in stage2["tasks"]] == ["S2-001", "S2-002"]
    assert state["current_task"] == "S2-001"
    text = (project / "docs/PRODUCTION.md").read_text(encoding="utf-8")
    assert "S2-001 | hard | Implement world streaming continuity" in text
    assert "S2-002 | creation | Create readable streamed-region transition" in text


def test_task_prompt_delegates_specialized_work_before_expensive_codex_reasoning(tmp_path: Path):
    project = write_project(tmp_path / "projects/biella-games")
    production = feeder.load_project_production(project)
    task = feeder.next_production_task(production)
    assert task is not None
    prompt = feeder.build_production_task_prompt(production, task)
    assert "biella resource route" in prompt
    assert "free/trial/prepaid" in prompt
    assert "paid" in prompt
    assert "do not probe quota" in prompt.lower()
