from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))
import biella_codex_routing as routing
import biella_production_state as state

MODULE = LOCAL_AI / "biella_production_runner.py"
spec = importlib.util.spec_from_file_location("biella_production_runner", MODULE)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


@pytest.fixture(autouse=True)
def isolate_derived_drive_publication(monkeypatch):
    monkeypatch.setattr(runner.evidence, "publish_derived_task_ledger", lambda _repo: None)


def test_long_child_keeps_runtime_heartbeat_fresh(tmp_path: Path, monkeypatch):
    fake = tmp_path / "slow.py"; output = tmp_path / "result.json"
    fake.write_text("import json,os,time\ntime.sleep(0.14)\nopen(os.environ['OUT'],'w').write(json.dumps({'task_id':'T','status':'COMPLETE','summary':'ok','evidence':['pass']}))\n")
    monkeypatch.setenv("OUT", str(output))
    monkeypatch.setattr(routing, "build_codex_command", lambda *_args: [sys.executable, str(fake)])
    runtime_path = tmp_path / "runtime.json"; telemetry = runner.initial_runtime()
    beats = []
    rc, _error = runner.invoke_structured("prompt", routing.Route("gpt-6-astra", "ultra"), tmp_path / "schema", output, tmp_path / "out.log", tmp_path / "err.log", runtime_path, telemetry, heartbeat_interval=0.02, on_heartbeat=lambda at: beats.append(at))
    assert rc == 0
    assert len(beats) >= 2
    assert runner.load_runtime(runtime_path)["heartbeat_at"] is not None


def test_single_flight_lock_rejects_second_holder(tmp_path: Path):
    first = runner.ProductionLock(tmp_path / "run.lock"); first.acquire()
    try:
        with pytest.raises(runner.AlreadyRunning):
            runner.ProductionLock(tmp_path / "run.lock").acquire()
    finally:
        first.release()


def write_repo_fixture(root: Path):
    repo = root / "repo"; project = repo / "projects/biella-games"
    (repo / "docs/project-state").mkdir(parents=True); (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").write_text("active_execution:\n  id: D01-030\n  state: PENDING\ngames:\n  completed_demo_tasks: 0\n  queued_successor: D01-030\n")
    (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").write_text("task:\n  id: D01-030\n  project: Biella Games\n  section: demo01\n  class: hard\n  title: Rival combat\n  status: PENDING\n")
    (project / "docs/PRODUCTION.md").write_text("# P\n\nStatus: `IN_PROGRESS`\nCurrent section: `demo01`\nCurrent task: `D01-030`\n\n## Section: demo01 | Demo | IN_PROGRESS\n\n- [ ] D01-030 | hard | Rival combat | PENDING | \n")
    return repo, project


def test_status_uses_service_plus_fresh_heartbeat(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path); runtime = tmp_path / "runtime.json"
    now = datetime(2026, 9, 5, 2, 0, tzinfo=timezone.utc)
    payload = runner.initial_runtime(); payload["status"] = "RUNNING"; payload["heartbeat_at"] = (now - timedelta(seconds=20)).isoformat(); runner.save_runtime(runtime, payload)
    monkeypatch.setattr(runner, "service_active", lambda: True)
    assert runner.production_status(repo, project, runtime, now=now)["status"] == "ACTIVE"
    old = payload.copy(); old["heartbeat_at"] = (now - timedelta(seconds=100)).isoformat(); runner.save_runtime(runtime, old)
    assert runner.production_status(repo, project, runtime, now=now)["status"] == "STALE"


def test_run_completes_canonical_task_and_exits(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path); runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda: {"gpt-6-astra": {"ultra"}})
    def command(_route, _schema, output, _cwd):
        payload = {"task_id": "D01-030", "status": "COMPLETE", "summary": "done", "evidence": ["runtime pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]
    monkeypatch.setattr(runner.routing, "build_codex_command", command)
    persisted = []
    monkeypatch.setattr(runner.evidence, "persist_continuity", lambda _repo, task_id, **_kw: persisted.append(task_id) or {"commit": "c", "tree": "t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.02) == 0
    assert persisted == ["D01-30", "SECTION-demo01"]
    production = state.load_project_production(project)
    assert state.find_task(production, "D01-030").status == "COMPLETE"
    assert state.load_active_task(repo).id == "NONE"
    telemetry = runner.load_runtime(runtime_root / "runtime.json")
    assert telemetry["status"] == "COMPLETE"


def test_public_unit_name_is_single_monorepo_unit():
    assert runner.UNIT_NAME == "biella-codex-production"


def test_runner_plans_and_audits_empty_next_section(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"; project = repo / "projects/biella-games"; runtime_root = tmp_path / "runtime"
    (repo / "docs/project-state").mkdir(parents=True); (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").write_text("active_execution:\n  id: NONE\n  state: READY\ngames:\n  completed_demo_tasks: 1\n  queued_successor: NONE\n")
    (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").write_text("task:\n  id: NONE\n  project: Biella Games\n  section: NONE\n  class: NONE\n  title: No active Project task\n  status: COMPLETE\n")
    (project / "docs/PRODUCTION.md").write_text("# P\n\nStatus: `IN_PROGRESS`\nCurrent section: `stage2`\nCurrent task: `NONE`\n\n## Section: demo01 | Demo | COMPLETE\n\n- [x] D01-050 | deep_memory | Close demo | COMPLETE | pass\n\n## Section: stage2 | Expansion | PENDING_UNPLANNED\n")
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda: {"gpt-6-astra": {"ultra"}, "gpt-5.6-luna": {"medium"}})
    calls = {"plan": 0}
    def command(_route, schema, output, _cwd):
        if Path(schema).name == "section-plan-schema.json":
            calls["plan"] += 1
            payload = {"section_id": "stage2", "complete": False, "summary": "planned", "evidence": ["sequence"], "tasks": [{"class": "simple", "title": "Implement streaming continuity"}]} if calls["plan"] == 1 else {"section_id": "stage2", "complete": True, "summary": "audited", "evidence": ["runtime"], "tasks": []}
        else:
            payload = {"task_id": "S2-001", "status": "COMPLETE", "summary": "done", "evidence": ["runtime pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]
    monkeypatch.setattr(runner.routing, "build_codex_command", command)
    monkeypatch.setattr(runner.evidence, "persist_continuity", lambda _repo, task_id, **_kw: {"commit": task_id, "tree": "t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.02) == 0
    production = state.load_project_production(project)
    assert state.find_task(production, "S2-001").status == "COMPLETE"
    assert next(s for s in production.sections if s.id == "stage2").status == "COMPLETE"
    assert calls["plan"] == 2


def test_observed_limit_falls_back_to_next_eligible_model(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path); runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda: {"gpt-6-astra": {"ultra"}, "gpt-5.6-terra": {"ultra"}})
    used = []
    def command(route, _schema, output, _cwd):
        used.append(route.model)
        if route.model == "gpt-6-astra":
            return [sys.executable, "-c", "import sys; print('usage_limit_exceeded', file=sys.stderr); sys.exit(1)"]
        payload = {"task_id": "D01-030", "status": "COMPLETE", "summary": "done", "evidence": ["runtime pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]
    monkeypatch.setattr(runner.routing, "build_codex_command", command)
    monkeypatch.setattr(runner.evidence, "persist_continuity", lambda _repo, task_id, **_kw: {"commit": task_id, "tree": "t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.02) == 0
    assert used[:2] == ["gpt-6-astra", "gpt-5.6-terra"]
    telemetry = runner.load_runtime(runtime_root / "runtime.json")
    assert "gpt-6-astra" in telemetry["cooldowns"]


def test_runner_is_directly_executable():
    completed = subprocess.run([str(MODULE), "--help"], text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert "production" in completed.stdout.lower() or "usage" in completed.stdout.lower()


def test_start_production_uses_persistent_systemd_unit(tmp_path: Path, monkeypatch):
    calls = []
    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""
    monkeypatch.setattr(runner, "service_active", lambda: False)
    monkeypatch.setattr(runner.state, "resolve_current_task", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(runner.subprocess, "run", lambda cmd, **kwargs: calls.append(cmd) or Completed())
    assert runner.start_production(tmp_path, tmp_path / "project", tmp_path / "runtime") == 0
    assert calls == [["systemctl", "start", "biella-codex-production.service"]]


def test_persistent_production_unit_is_enabled_resume_contract():
    unit = (LOCAL_AI / "biella-codex-production.service").read_text()
    assert "ExecStart=/usr/local/bin/biella-codex production run" in unit
    assert "Restart=on-failure" in unit
    assert "RestartSec=10" in unit
    assert "RestartPreventExitStatus=" not in unit
    assert "WatchdogSec=" not in unit
    assert "NotifyAccess=" not in unit
    assert "WantedBy=multi-user.target" in unit



def test_public_cli_has_no_stop_command():
    parser = runner._parser()
    choices = parser._subparsers._group_actions[0].choices
    assert "stop" not in choices


def test_status_stays_active_during_model_recovery(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime.json"
    payload = runner.initial_runtime()
    payload["status"] = "RECOVERING_MODEL"
    payload["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
    runner.save_runtime(runtime, payload)
    monkeypatch.setattr(runner, "service_active", lambda: True)
    assert runner.production_status(repo, project, runtime)["status"] == "ACTIVE"


def test_runner_does_not_reject_dirty_inflight_workspace():
    source = MODULE.read_text()
    assert "assert_clean_task_workspace(repo_root)" not in source


def test_task_result_schema_has_no_terminal_blockers():
    allowed = set(runner.evidence.result_schema()["properties"]["status"]["enum"])
    assert allowed == {"COMPLETE", "COMPLETE_ALREADY", "CONTINUE"}


def test_persistence_failure_retries_without_runner_exit(tmp_path: Path, monkeypatch):
    runtime = tmp_path / "runtime.json"
    telemetry = runner.initial_runtime()
    telemetry.update({"status": "RUNNING", "task_id": "D01-033"})
    calls = {"n": 0}

    def persist(_repo, _task_id):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("temporary push failure")
        return {"commit": "c", "tree": "t"}

    monkeypatch.setattr(runner.evidence, "persist_continuity", persist)
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    result = runner._persist_until_success(tmp_path, "D01-033", runtime, telemetry)
    assert result == {"commit": "c", "tree": "t"}
    assert calls["n"] == 2
    assert telemetry["status"] == "RUNNING"
    assert telemetry["last_result"]["status"] == "RECOVERED_PERSISTENCE"


def test_section_planner_emits_canonical_d_series_ids(tmp_path: Path):
    repo = tmp_path / "repo"
    project = repo / "projects/biella-games"
    (repo / "docs/project-state").mkdir(parents=True)
    (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").write_text("active_execution:\n  id: NONE\n  state: READY\n")
    (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").write_text("task:\n  id: NONE\n  project: Biella Games\n  section: NONE\n  class: NONE\n  title: No active Project task\n  status: COMPLETE\n")
    (project / "docs/PRODUCTION.md").write_text("# P\n\nStatus: `IN_PROGRESS`\nCurrent section: `stage2`\nCurrent task: `NONE`\n\n## Section: demo01 | Demo | COMPLETE\n\n- [x] D01-50 | deep_memory | Close demo | COMPLETE | pass\n\n## Section: stage2 | Expansion | PENDING_UNPLANNED\n")
    state.apply_section_plan(repo, project, "stage2", {"section_id": "stage2", "complete": False, "summary": "planned", "evidence": [], "tasks": [{"class": "simple", "title": "Implement streaming continuity"}]})
    production = state.load_project_production(project)
    task = next(s.tasks[0] for s in production.sections if s.id == "stage2")
    assert task.id == "D02-01"
    assert "S2-001" not in (project / "docs/PRODUCTION.md").read_text()


def test_derived_ledger_failure_never_blocks_critical_persistence(tmp_path: Path, monkeypatch):
    runtime = tmp_path / "runtime.json"
    telemetry = runner.initial_runtime()
    telemetry.update({"status": "RUNNING", "task_id": "D01-37"})
    monkeypatch.setattr(
        runner.evidence,
        "persist_continuity",
        lambda _repo, _task_id: {"commit": "c", "tree": "t"},
    )
    monkeypatch.setattr(
        runner.evidence,
        "publish_derived_task_ledger",
        lambda _repo: (_ for _ in ()).throw(RuntimeError("drive temporarily unavailable")),
    )
    result = runner._persist_until_success(tmp_path, "D01-37", runtime, telemetry)
    assert result == {"commit": "c", "tree": "t"}
    assert telemetry["status"] == "RUNNING"
    assert telemetry["last_result"]["derived_ledger"]["status"] == "PENDING_RETRY"
