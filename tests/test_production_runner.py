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


def test_invoke_structured_rotates_idle_executor_without_productive_descendant(tmp_path: Path, monkeypatch):
    fake = tmp_path / "idle.py"; output = tmp_path / "result.json"
    fake.write_text("import time\ntime.sleep(5)\n")
    monkeypatch.setenv("BIELLA_CODEX_STALL_SECONDS", "0.08")
    monkeypatch.setattr(routing, "build_codex_command", lambda *_args, **_kwargs: [sys.executable, str(fake)])
    monkeypatch.setattr(runner, "_has_productive_descendant", lambda _pid: False)
    runtime = tmp_path / "runtime.json"; telemetry = runner.initial_runtime()
    journal = runner.production_events.ProductionEventJournal(tmp_path / "events.jsonl", failure_path=tmp_path / "failures.jsonl")
    rc, detail = runner.invoke_structured(
        "prompt", routing.Route("gpt-6-astra", "ultra"), tmp_path / "schema", output,
        tmp_path / "stdout.log", tmp_path / "stderr.log", runtime, telemetry,
        heartbeat_interval=0.01, event_journal=journal, session_task_id="D03-01", cwd=tmp_path,
    )
    assert rc != 0
    assert "BIELLA_EXECUTOR_STALL_ROTATION" in detail
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert any(e["type"] == "task.executor_stall_recovery" for e in events)


def test_invoke_structured_does_not_rotate_when_productive_descendant_exists(tmp_path: Path, monkeypatch):
    fake = tmp_path / "slow_valid.py"; output = tmp_path / "result.json"
    fake.write_text(
        "import json,os,time\n"
        "time.sleep(0.14)\n"
        "open(os.environ['OUT'],'w').write(json.dumps({'task_id':'T','status':'CONTINUE','summary':'ok','evidence':['pass']}))\n"
    )
    monkeypatch.setenv("OUT", str(output))
    monkeypatch.setenv("BIELLA_CODEX_STALL_SECONDS", "0.05")
    monkeypatch.setattr(routing, "build_codex_command", lambda *_args, **_kwargs: [sys.executable, str(fake)])
    monkeypatch.setattr(runner, "_has_productive_descendant", lambda _pid: True)
    telemetry = runner.initial_runtime()
    rc, detail = runner.invoke_structured(
        "prompt", routing.Route("gpt-6-astra", "ultra"), tmp_path / "schema", output,
        tmp_path / "stdout.log", tmp_path / "stderr.log", tmp_path / "runtime.json", telemetry,
        heartbeat_interval=0.01, cwd=tmp_path,
    )
    assert rc == 0, detail


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


def test_pre_task_reconcile_defers_when_current_task_output_is_dirty(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda: {"gpt-6-astra": {"ultra"}})

    def command(_route, _schema, output, _cwd):
        payload = {"task_id": "D01-030", "status": "COMPLETE", "summary": "done", "evidence": ["runtime pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]

    monkeypatch.setattr(runner.routing, "build_codex_command", command)
    monkeypatch.setattr(runner.evidence, "continuity_changes", lambda _repo: True)
    monkeypatch.setattr(runner.evidence, "unexpected_dirty_paths", lambda _repo: {"projects/biella-games/partial.cpp"})
    persisted = []
    monkeypatch.setattr(runner.evidence, "persist_continuity", lambda _repo, task_id, **_kw: persisted.append(task_id) or {"commit": "c", "tree": "t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.02) == 0
    assert "RECONCILE-D01-30" not in persisted
    assert "D01-30" in persisted


def test_runner_startup_clears_stale_child_pid_before_first_work(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    project = repo / "projects/biella-games"
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(parents=True)
    stale = runner.initial_runtime()
    stale["child_pid"] = 999999
    runner.save_runtime(runtime_root / "runtime.json", stale)
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda: {})
    monkeypatch.setattr(runner.state, "sync_project_metadata", lambda _project: (_ for _ in ()).throw(RuntimeError("stop after startup")))
    with pytest.raises(RuntimeError, match="stop after startup"):
        runner.run_production(repo, project, runtime_root)
    assert runner.load_runtime(runtime_root / "runtime.json")["child_pid"] is None


def test_extract_codex_session_id_from_jsonl(tmp_path: Path):
    log = tmp_path / "stdout.log"
    log.write_text('{"type":"thread.started","thread_id":"01a-task-session"}\n{"type":"turn.started"}\n')
    assert runner._extract_codex_session_id(log) == "01a-task-session"


def test_task_session_is_reused_only_for_same_task():
    telemetry = runner.initial_runtime()
    telemetry["task_session_id"] = "session-d02"
    telemetry["session_task_id"] = "D02-01"
    assert runner._resume_session_for(telemetry, "D02-01") == "session-d02"
    assert runner._resume_session_for(telemetry, "D02-02") is None


def test_runtime_persists_task_session_identity(tmp_path: Path):
    runtime = tmp_path / "runtime.json"
    telemetry = runner.initial_runtime()
    telemetry["task_session_id"] = "session-d02"
    telemetry["session_task_id"] = "D02-01"
    runner.save_runtime(runtime, telemetry)
    loaded = runner.load_runtime(runtime)
    assert loaded["task_session_id"] == "session-d02"
    assert loaded["session_task_id"] == "D02-01"


def test_task_capsule_path_is_stable_per_task(tmp_path: Path):
    assert runner._task_capsule_path(tmp_path, "D02-01") == tmp_path / "task-memory" / "D02-01.json"


def test_resume_uses_delta_packet_when_session_exists(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    production = state.load_project_production(project)
    task = state.find_task(production, "D01-030")
    telemetry = runner.initial_runtime()
    telemetry["task_session_id"] = "session-d01"
    telemetry["session_task_id"] = task.id
    capsule = runner._task_capsule_path(tmp_path / "runtime", task.id)
    prompt = runner._task_prompt(repo, production, task, telemetry, capsule)
    assert "RESUME_EXISTING_TASK_SESSION" in prompt
    assert "--- ACTIVE CONTRACT ---" not in prompt


def test_capsule_write_preserves_same_task_progress(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    production = state.load_project_production(project)
    task = state.find_task(production, "D01-030")
    telemetry = runner.initial_runtime()
    telemetry["task_session_id"] = "session-d01"
    telemetry["session_task_id"] = task.id
    telemetry["last_result"] = {"task_id": task.id, "status": "CONTINUE", "summary": "partial", "evidence": ["build pass"]}
    path = runner._write_task_capsule(repo, project, tmp_path / "runtime", task, telemetry)
    payload = json.loads(path.read_text())
    assert payload["task_id"] == task.id
    assert payload["session_id"] == "session-d01"
    assert payload["summary"] == "partial"
    assert payload["evidence"] == ["build pass"]


def test_capsule_keeps_existing_task_memory_when_runtime_last_result_is_unrelated(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    production = state.load_project_production(project)
    task = state.find_task(production, "D01-030")
    runtime_root = tmp_path / "runtime"
    path = runner._task_capsule_path(runtime_root, task.id)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"task_id": task.id, "summary": "preserved hypothesis", "evidence": ["runtime evidence"]}))
    telemetry = runner.initial_runtime()
    telemetry["task_session_id"] = "session-d01"
    telemetry["session_task_id"] = task.id
    telemetry["last_result"] = {"task_id": "SECTION-demo01", "status": "COMPLETE", "summary": "unrelated", "evidence": []}
    runner._write_task_capsule(repo, project, runtime_root, task, telemetry)
    payload = json.loads(path.read_text())
    assert payload["summary"] == "preserved hypothesis"
    assert payload["evidence"] == ["runtime evidence"]


def test_invoke_structured_streams_safe_codex_events(tmp_path: Path, monkeypatch):
    fake = tmp_path / "stream.py"
    output = tmp_path / "result.json"
    fake.write_text(
        "import json,os,time\n"
        "print(json.dumps({'type':'thread.started','thread_id':'session-live'}), flush=True)\n"
        "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'live progress'}}), flush=True)\n"
        "time.sleep(0.05)\n"
        "open(os.environ['OUT'],'w').write(json.dumps({'task_id':'D01-030','status':'CONTINUE','summary':'more','evidence':['partial']}))\n"
    )
    monkeypatch.setenv("OUT", str(output))
    monkeypatch.setattr(runner.routing, "build_codex_command", lambda *_args, **_kwargs: [sys.executable, str(fake)])
    runtime = tmp_path / "runtime.json"
    telemetry = runner.initial_runtime()
    journal = runner.production_events.ProductionEventJournal(tmp_path / "events.jsonl")
    rc, _ = runner.invoke_structured(
        "prompt", routing.Route("gpt-6-astra", "ultra"), tmp_path / "schema", output,
        tmp_path / "stdout.log", tmp_path / "stderr.log", runtime, telemetry,
        heartbeat_interval=0.01, event_journal=journal, session_task_id="D01-030", cwd=tmp_path,
    )
    assert rc == 0
    entries = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert any(item["type"] == "agent.message" and item.get("text") == "live progress" for item in entries)
    assert telemetry["task_session_id"] == "session-live"


def test_live_session_identity_is_persisted_before_child_finishes(tmp_path: Path, monkeypatch):
    fake = tmp_path / "live_session.py"
    output = tmp_path / "result.json"
    fake.write_text(
        "import json,os,time\n"
        "print(json.dumps({'type':'thread.started','thread_id':'session-while-running'}), flush=True)\n"
        "time.sleep(0.12)\n"
        "open(os.environ['OUT'],'w').write(json.dumps({'task_id':'D01-030','status':'CONTINUE','summary':'more','evidence':['partial']}))\n"
    )
    monkeypatch.setenv("OUT", str(output))
    monkeypatch.setattr(runner.routing, "build_codex_command", lambda *_args, **_kwargs: [sys.executable, str(fake)])
    runtime = tmp_path / "runtime.json"
    telemetry = runner.initial_runtime()
    seen = []
    def heartbeat(_at):
        payload = runner.load_runtime(runtime)
        if payload.get("child_pid"):
            seen.append(payload.get("task_session_id"))
    rc, _ = runner.invoke_structured(
        "prompt", routing.Route("gpt-6-astra", "ultra"), tmp_path / "schema", output,
        tmp_path / "stdout.log", tmp_path / "stderr.log", runtime, telemetry,
        heartbeat_interval=0.01, on_heartbeat=heartbeat, session_task_id="D01-030", cwd=tmp_path,
        event_journal=runner.production_events.ProductionEventJournal(tmp_path / "events.jsonl"),
    )
    assert rc == 0
    assert "session-while-running" in seen


def test_codex_subagent_fanout_is_never_enabled_by_production(monkeypatch):
    monkeypatch.setenv("BIELLA_CODEX_ONE_HELPER_TASKS", "*")
    assert runner._helper_allowed("D02-01") is False


def test_task_prompt_injects_prepared_task_guide_for_new_and_resumed_turns(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    production = state.load_project_production(project)
    task = state.find_task(production, "D01-030")
    guide = project / "docs/task-guides" / f"{task.id}.md"
    guide.parent.mkdir(parents=True)
    guide.write_text("# prepared guide\n", encoding="utf-8")
    capsule = runner._task_capsule_path(tmp_path / "runtime", task.id)

    fresh = runner._task_prompt(repo, production, task, runner.initial_runtime(), capsule)
    assert f"TASK_GUIDE: {guide}" in fresh
    assert "Read TASK_GUIDE before broad source search" in fresh
    assert "# prepared guide" in fresh
    assert "--- TASK GUIDE CONTENT ---" in fresh

    telemetry = runner.initial_runtime()
    telemetry["task_session_id"] = "session-d01"
    telemetry["session_task_id"] = task.id
    resumed = runner._task_prompt(repo, production, task, telemetry, capsule)
    assert "RESUME_EXISTING_TASK_SESSION" in resumed
    assert f"TASK_GUIDE: {guide}" in resumed
    assert "# prepared guide" in resumed


def test_task_prompt_references_compacted_memory_projection(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    production = state.load_project_production(project)
    task = state.find_task(production, "D01-030")
    telemetry = runner.initial_runtime()
    capsule = runner._task_capsule_path(tmp_path / "runtime", task.id)
    projection = tmp_path / "runtime" / "memory" / "current-task.json"
    projection.parent.mkdir(parents=True)
    projection.write_text('{}\n')
    prompt = runner._task_prompt(repo, production, task, telemetry, capsule, projection)
    assert f"MEMORY_PROJECTION: {projection}" in prompt
    assert "never overrides current source or task authority" in prompt


def test_memory_compaction_failure_never_blocks_task_execution(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime"
    journal = runner.production_events.ProductionEventJournal(
        runtime / "events.jsonl", failure_path=runtime / "failures.jsonl"
    )
    monkeypatch.setattr(
        runner.memory_compactor, "refresh_compacted_memory",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("broken compactor")),
    )
    assert runner._refresh_memory_projection(repo, project, runtime, "D01-030", journal) is None
    events = [json.loads(line) for line in (runtime / "events.jsonl").read_text().splitlines()]
    assert events[-1]["type"] == "memory.compaction_failed"
    failures = [json.loads(line) for line in (runtime / "failures.jsonl").read_text().splitlines()]
    assert failures[-1]["failure_type"] == "memory.compaction_failed"


def test_local_resource_assist_is_cached_by_meaningful_projection(tmp_path: Path, monkeypatch):
    projection = tmp_path / "memory" / "current-task.json"
    projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({
        "task_id":"D02-01", "generated_at":"one",
        "task_memory":{"task_class":"hard_creation","title":"Streaming","summary":"partial","next_action":"fix build","updated_at":"ignored"},
        "failures":[{"task_id":"D02-01","status":"FAILED","detail":"build permissions"}],
        "capabilities":{"unreal.assist":["ollama-qwen"]}, "verified_actions":[]
    }))
    calls = []
    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({
            "capability":"llm.fast","provider":"ollama-qwen","model":"qwen3-coder-next:biella",
            "text":"repair generated permissions only","usage":{"total_tokens":22}
        })+"\n", stderr="")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    first = runner._ensure_local_resource_assist(tmp_path, "D02-01", projection)
    assert first and first.exists()
    payload = json.loads(first.read_text())
    assert payload["provider"] == "ollama-qwen"
    assert payload["text"] == "repair generated permissions only"
    projection.write_text(projection.read_text().replace('"generated_at": "one"', '"generated_at": "two"').replace('"updated_at": "ignored"', '"updated_at": "later"'))
    second = runner._ensure_local_resource_assist(tmp_path, "D02-01", projection)
    assert second == first
    assert len(calls) == 1


def test_local_resource_assist_failure_is_non_blocking_and_recorded(tmp_path: Path, monkeypatch):
    projection = tmp_path / "memory" / "current-task.json"
    projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"D02-01","task_memory":{"summary":"x"},"failures":[],"capabilities":{}}))
    monkeypatch.setattr(runner.subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 2, stdout="", stderr="local resource unavailable"))
    journal = runner.production_events.ProductionEventJournal(tmp_path / "events.jsonl", failure_path=tmp_path / "failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path, "D02-01", projection, journal) is None
    failures = [json.loads(line) for line in (tmp_path / "failures.jsonl").read_text().splitlines()]
    assert failures[-1]["failure_type"] == "resource.local_assist_failed"


def test_runtime_failure_does_not_cooldown_model():
    telemetry = runner.initial_runtime()
    route = routing.Route("gpt-6-astra", "ultra")
    runner._set_failure(telemetry, route, "ActiveTurnOutputSchemaMismatch", "D01-030")
    assert telemetry["status"] == "RECOVERING_RUNTIME"
    assert "gpt-6-astra" not in telemetry.get("cooldowns", {})
    assert telemetry["last_result"]["status"] == "RUNTIME_RECOVERY"


def test_stale_resume_schema_error_is_classified_for_session_rotation():
    assert runner._is_stale_resume_error("turn/start failed: ActiveTurnOutputSchemaMismatch (code -32603)")
    assert not runner._is_stale_resume_error("usage_limit_exceeded")
    assert not runner._is_stale_resume_error("ordinary build failure")


def test_stale_resume_rotates_session_and_retries_same_astra_route(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    production = state.load_project_production(project)
    task = state.find_task(production, "D01-030")
    telemetry = runner.initial_runtime()
    telemetry["task_session_id"] = "stale-session"
    telemetry["session_task_id"] = task.id
    runner.save_runtime(runtime_root / "runtime.json", telemetry)
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda: {
        "gpt-6-astra": {"ultra"}, "gpt-5.6-terra": {"ultra"}
    })
    used = []
    def resume_command(route, _schema, _output, session_id, **_kwargs):
        used.append(("resume", route.model, session_id))
        return [sys.executable, "-c", "import sys; print('ActiveTurnOutputSchemaMismatch', file=sys.stderr); sys.exit(1)"]
    def new_command(route, _schema, output, _cwd, **_kwargs):
        used.append(("new", route.model, None))
        payload = {"task_id":"D01-030","status":"COMPLETE","summary":"done","evidence":["pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]
    monkeypatch.setattr(runner.routing, "build_codex_resume_command", resume_command)
    monkeypatch.setattr(runner.routing, "build_codex_command", new_command)
    monkeypatch.setattr(runner.evidence, "persist_continuity", lambda _repo, task_id, **_kw: {"commit":task_id,"tree":"t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.01) == 0
    assert used[:2] == [("resume", "gpt-6-astra", "stale-session"), ("new", "gpt-6-astra", None)]
    assert all(model != "gpt-5.6-terra" for _kind, model, _session in used)


def test_local_resource_assist_rejects_hallucinated_file_paths_and_caches_rejection(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/biella-games"
    project.mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "tests/real_test.py").write_text("pass\n")
    projection = tmp_path / "memory/current-task.json"
    projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({
        "task_id":"D02-03","task_memory":{"task_class":"hard_creation","summary":"verified","next_action":"finalize"},
        "failures":[],"capabilities":{},"verified_actions":[]
    }))
    calls=[]
    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({
            "provider":"ollama-qwen","model":"qwen3-coder-next:biella",
            "text":"Inspect `Backends/Vehicle/invented.cpp` then run `tests/real_test.py`.","usage":{"total_tokens":10}
        }), stderr="")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    journal=runner.production_events.ProductionEventJournal(tmp_path/"events.jsonl", failure_path=tmp_path/"failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path,"D02-03",projection,journal,project_root=project) is None
    assert len(calls)==1
    # Same meaningful projection reuses the rejection marker instead of calling Qwen again.
    assert runner._ensure_local_resource_assist(tmp_path,"D02-03",projection,journal,project_root=project) is None
    assert len(calls)==1
    events=[json.loads(line) for line in (tmp_path/"events.jsonl").read_text().splitlines()]
    assert any(e["type"]=="resource.local_assist_recovery" and e["status"]=="RECOVERED" for e in events)


def test_local_resource_assist_accepts_existing_project_and_unreal_asset_paths(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/biella-games"
    (project / "tests").mkdir(parents=True)
    (project / "tests/real_test.py").write_text("pass\n")
    (project / "Content/Vehicle/Audio").mkdir(parents=True)
    (project / "Content/Vehicle/Audio/S_VehicleEngine.uasset").write_bytes(b"asset")
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"D02-03","task_memory":{"task_class":"hard_creation","summary":"Inspect tests/real_test.py and /Game/Vehicle/Audio/S_VehicleEngine for the current task"},"failures":[],"capabilities":{}}))
    text="Inspect `tests/real_test.py` and `/Game/Vehicle/Audio/S_VehicleEngine`."
    monkeypatch.setattr(runner.subprocess,"run",lambda argv,**kwargs: subprocess.CompletedProcess(argv,0,stdout=json.dumps({"provider":"ollama-qwen","model":"qwen","text":text,"usage":{}}),stderr=""))
    path=runner._ensure_local_resource_assist(tmp_path,"D02-03",projection,project_root=project)
    assert path and json.loads(path.read_text())["text"]==text


def test_local_assist_rejects_invented_failure_when_projection_has_no_failure(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/biella-games"
    project.mkdir(parents=True)
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({
        "task_id":"D02-04","task_memory":{"task_class":"hard_creation","summary":"clean boundary","next_action":"implement task"},
        "failures":[],"capabilities":{},"verified_actions":[]
    }))
    calls=[]
    bogus = "(1) Next smallest action: Retry the failing operation.\n(2) Likely failure cause if any: State inconsistency due to stale cache.\n(3) Exact files/tests/tools to inspect or run: none.\n(4) Reusable verified pattern: preserve state."
    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv,0,stdout=json.dumps({"provider":"ollama-qwen","model":"qwen","text":bogus,"usage":{}}),stderr="")
    monkeypatch.setattr(runner.subprocess,"run",fake_run)
    journal=runner.production_events.ProductionEventJournal(tmp_path/"events.jsonl",failure_path=tmp_path/"failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path,"D02-04",projection,journal,project_root=project) is None
    assert len(calls)==1
    assert runner._ensure_local_resource_assist(tmp_path,"D02-04",projection,journal,project_root=project) is None
    assert len(calls)==1
    rejected=list((tmp_path/"memory/local-assist").glob("D02-04-*.rejected"))
    assert len(rejected)==1
    payload=json.loads(rejected[0].read_text())
    assert payload["reason"]=="ungrounded_failure_claim"
    events=[json.loads(line) for line in (tmp_path/"events.jsonl").read_text().splitlines()]
    assert any(e["type"]=="resource.local_assist_recovery" and "invented failure" in e.get("text","").lower() for e in events)


def test_local_assist_hydrates_bare_verified_action_refs_from_full_index(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/biella-games"; project.mkdir(parents=True)
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    ref = "sha256:" + "a" * 64
    projection.write_text(json.dumps({
        "task_id":"D02-04","task_memory":{"task_class":"hard_creation","summary":"x"},
        "failures":[{"failure_type":"runtime_validation","status":"CONTINUE","detail":"real blocker"}],
        "capabilities":{},"verified_actions":[ref],"full_index":"memory/compacted-memory.json"
    }))
    (tmp_path/"memory/compacted-memory.json").write_text(json.dumps({"content":{ref:{"text":"Local commit: exact-verified-commit"}}}))
    prompts=[]
    def fake_run(argv, **kwargs):
        prompts.append(argv[argv.index('--prompt')+1])
        return subprocess.CompletedProcess(argv,0,stdout=json.dumps({
            "provider":"ollama-qwen","model":"qwen",
            "text":"(1) Inspect current task.\n(2) Likely failure cause if any: NONE\n(3) Exact files/tests/tools to inspect: none\n(4) Reusable verified pattern if supported: NONE",
            "usage":{}
        }),stderr="")
    monkeypatch.setattr(runner.subprocess,"run",fake_run)
    path=runner._ensure_local_resource_assist(tmp_path,"D02-04",projection,project_root=project)
    assert path
    assert len(prompts)==1
    assert '"content_ref":"'+ref+'"' in prompts[0]
    assert '"text":"Local commit: exact-verified-commit"' in prompts[0]


def test_local_assist_rejects_semantic_relabel_of_verified_action_ref(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/biella-games"; project.mkdir(parents=True)
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    ref = "sha256:" + "b" * 64
    projection.write_text(json.dumps({
        "task_id":"D02-04","task_memory":{"task_class":"hard_creation","summary":"x"},
        "failures":[],"capabilities":{},"verified_actions":[ref],"full_index":"memory/compacted-memory.json"
    }))
    exact="Local commit: 600fdda86b6f1b1845966a7d24312eada9593548"
    (tmp_path/"memory/compacted-memory.json").write_text(json.dumps({"content":{ref:{"text":exact}}}))
    bogus=f"(1) Continue task.\n(2) Likely failure cause if any: NONE\n(3) Exact files/tests/tools to inspect: none\n(4) Reusable verified pattern: `{ref}` (bounded interaction + localized recovery)"
    monkeypatch.setattr(runner.subprocess,"run",lambda argv,**kwargs: subprocess.CompletedProcess(argv,0,stdout=json.dumps({"provider":"ollama-qwen","model":"qwen","text":bogus,"usage":{}}),stderr=""))
    journal=runner.production_events.ProductionEventJournal(tmp_path/"events.jsonl",failure_path=tmp_path/"failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path,"D02-04",projection,journal,project_root=project) is None
    rejected=list((tmp_path/"memory/local-assist").glob("D02-04-*.rejected"))
    assert len(rejected)==1
    assert json.loads(rejected[0].read_text())["reason"]=="ungrounded_verified_action_claim"


def test_no_failure_local_assist_omits_cross_task_verified_actions(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/biella-games"; project.mkdir(parents=True)
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    ref = "sha256:" + "c" * 64
    projection.write_text(json.dumps({
        "task_id":"D02-04","task_memory":{"task_class":"hard_creation","summary":"inspect Build/Environment","next_action":"implement D02-04"},
        "failures":[],"capabilities":{},"verified_actions":[ref],"full_index":"memory/compacted-memory.json"
    }))
    (tmp_path/"memory/compacted-memory.json").write_text(json.dumps({"content":{ref:{"text":"Unrelated predecessor acceptance"}}}))
    prompts=[]
    def fake_run(argv, **kwargs):
        prompt=argv[argv.index('--prompt')+1]; prompts.append(prompt)
        return subprocess.CompletedProcess(argv,0,stdout=json.dumps({
            "provider":"ollama-qwen","model":"qwen",
            "text":"(1) Inspect current task capsule.\n(2) Likely failure cause if any: NONE\n(3) Exact files/tests/tools to inspect or run: none\n(4) Reusable verified pattern if supported: NONE","usage":{}
        }),stderr="")
    monkeypatch.setattr(runner.subprocess,"run",fake_run)
    assert runner._ensure_local_resource_assist(tmp_path,"D02-04",projection,project_root=project)
    assert len(prompts)==1
    assert 'Unrelated predecessor acceptance' not in prompts[0]
    assert '"verified_actions":[]' in prompts[0]


def test_clean_local_assist_rejects_existing_but_unmentioned_predecessor_path(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/biella-games"
    old = project / "Build/Demo01/D01-040-acceptance.md"
    old.parent.mkdir(parents=True)
    old.write_text("old predecessor")
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({
        "task_id":"D03-01",
        "task_memory":{"task_class":"hard_creation","summary":"Stage 3 current task","next_action":"inspect current rendering source"},
        "failures":[],"capabilities":{},"verified_actions":[]
    }))
    text=f"(1) Inspect `{old}`.\n(2) Likely failure cause if any: NONE\n(3) Exact files/tests/tools to inspect or run: `{old}`\n(4) Reusable verified pattern if supported: NONE"
    monkeypatch.setattr(runner.subprocess,"run",lambda argv,**kwargs: subprocess.CompletedProcess(argv,0,stdout=json.dumps({"provider":"ollama-qwen","model":"qwen","text":text,"usage":{}}),stderr=""))
    journal=runner.production_events.ProductionEventJournal(tmp_path/"events.jsonl",failure_path=tmp_path/"failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path,"D03-01",projection,journal,project_root=project) is None
    rejected=list((tmp_path/"memory/local-assist").glob("D03-01-*.rejected"))
    assert len(rejected)==1
    assert json.loads(rejected[0].read_text())["reason"]=="out_of_scope_paths"


def test_clean_local_assist_accepts_path_present_in_current_task_memory(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/biella-games"
    current = project / "Config/DefaultEngine.ini"
    current.parent.mkdir(parents=True)
    current.write_text("[Renderer]")
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({
        "task_id":"D03-01",
        "task_memory":{"task_class":"hard_creation","summary":"Inspect Config/DefaultEngine.ini for Stage 3 rendering state","next_action":"bound first change"},
        "failures":[],"capabilities":{},"verified_actions":[]
    }))
    text="(1) Inspect `Config/DefaultEngine.ini`.\n(2) Likely failure cause if any: NONE\n(3) Exact files/tests/tools to inspect or run: `Config/DefaultEngine.ini`\n(4) Reusable verified pattern if supported: NONE"
    monkeypatch.setattr(runner.subprocess,"run",lambda argv,**kwargs: subprocess.CompletedProcess(argv,0,stdout=json.dumps({"provider":"ollama-qwen","model":"qwen","text":text,"usage":{}}),stderr=""))
    path=runner._ensure_local_resource_assist(tmp_path,"D03-01",projection,project_root=project)
    assert path and json.loads(path.read_text())["text"]==text


def test_local_provider_compatibility_failure_cools_local_route_without_hot_loop():
    telemetry = runner.initial_runtime()
    route = routing.Route("qwen3-coder-next:biella", "none", "ollama")
    before = datetime.now(timezone.utc)
    runner._set_failure(telemetry, route, '"qwen3-coder-next:biella" does not support thinking', "D03-01")
    until = datetime.fromisoformat(telemetry["cooldowns"][route.model])
    assert until > before
    assert telemetry["status"] == "RECOVERING_MODEL"
    assert telemetry["last_result"]["status"] == "MODEL_RECOVERY"


def test_account_usage_limit_reserves_luna_then_spark_before_local():
    telemetry = runner.initial_runtime()
    detail = "You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at Sep 12th, 2026 9:41 PM."
    expected = "2026-09-12T21:41:00+00:00"

    runner._set_failure(telemetry, routing.Route("gpt-6-astra", "ultra"), detail, "D03-01")
    assert telemetry["status"] == "RECOVERING_MODEL"
    assert telemetry["cooldowns"].get("gpt-5.6-luna") is None
    assert telemetry["cooldowns"].get("gpt-5.3-codex-spark") is None
    assert all(
        telemetry["cooldowns"].get(model) == expected
        for model in routing.cloud_models()
        if model not in {"gpt-5.6-luna", "gpt-5.3-codex-spark"}
    )

    runner._set_failure(telemetry, routing.Route("gpt-5.6-luna", "max"), detail, "D03-01")
    assert telemetry["cooldowns"].get("gpt-5.6-luna") == expected
    assert telemetry["cooldowns"].get("gpt-5.3-codex-spark") is None

    runner._set_failure(telemetry, routing.Route("gpt-5.3-codex-spark", "xhigh"), detail, "D03-01")
    assert all(telemetry["cooldowns"].get(model) == expected for model in routing.cloud_models())
    assert telemetry["last_result"]["retry_at"] == expected


def test_account_usage_limit_falls_back_to_local_codex_route(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path); runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda: {
        "gpt-6-astra": {"ultra"},
        "gpt-5.6-terra": {"ultra"},
        "gpt-5.6-sol": {"ultra"},
        "gpt-5.6-luna": {"max"},
        "gpt-5.3-codex-spark": {"xhigh"},
        "qwen3-coder-next:biella": {"local"},
    })
    used = []
    def command(route, _schema, output, _cwd):
        used.append((route.model, route.provider))
        if route.provider == "openai":
            return [sys.executable, "-c", "import sys; print(\"You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at Sep 12th, 2026 9:41 PM.\", file=sys.stderr); sys.exit(1)"]
        payload = {"task_id": "D01-030", "status": "COMPLETE", "summary": "done locally through Codex continuity", "evidence": ["runtime pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]
    monkeypatch.setattr(runner.routing, "build_codex_command", command)
    monkeypatch.setattr(runner.evidence, "persist_continuity", lambda _repo, task_id, **_kw: {"commit": task_id, "tree": "t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.02) == 0
    assert used[:4] == [
        ("gpt-6-astra", "openai"),
        ("gpt-5.6-luna", "openai"),
        ("gpt-5.3-codex-spark", "openai"),
        ("qwen3-coder-next:biella", "ollama"),
    ]


def test_cross_provider_compaction_resume_error_is_session_incompatible():
    detail = '{"error":{"message":"input[42]: unknown input item type: \"compaction\"","type":"invalid_request_error"}}'
    assert runner._is_resume_protocol_incompatible(detail)
    assert not runner._is_resume_protocol_incompatible("ordinary native process failed")


def test_local_fallback_rotates_only_incompatible_codex_session_and_keeps_task(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path); runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(parents=True)
    existing = runner.initial_runtime()
    existing.update({
        "status": "RUNNING", "project": "biella-games", "task_id": "D01-030",
        "task_session_id": "cloud-session-old", "session_task_id": "D01-30",
        "cooldowns": {model: "2026-09-12T21:41:00+00:00" for model in routing.cloud_models()},
        "last_result": {"task_id": "D01-030", "status": "CONTINUE", "summary": "preserved task work", "evidence": ["preserved-evidence"]},
    })
    runner.save_runtime(runtime_root / "runtime.json", existing)
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda: {"qwen3-coder-next:biella": {"local"}})
    calls = []
    def resume_command(route, _schema, _output, session_id, **_kw):
        calls.append(("resume", route.provider, session_id))
        return [sys.executable, "-c", "import sys; print('input[42]: unknown input item type: \"compaction\"', file=sys.stderr); sys.exit(1)"]
    def new_command(route, _schema, output, _cwd, **_kw):
        calls.append(("new", route.provider, None))
        payload = {"task_id": "D01-030", "status": "COMPLETE", "summary": "continued from preserved task state", "evidence": ["preserved-evidence", "local-pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]
    monkeypatch.setattr(runner.routing, "build_codex_resume_command", resume_command)
    monkeypatch.setattr(runner.routing, "build_codex_command", new_command)
    monkeypatch.setattr(runner.evidence, "persist_continuity", lambda _repo, task_id, **_kw: {"commit": task_id, "tree": "t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.01) == 0
    assert calls[:2] == [("resume", "ollama", "cloud-session-old"), ("new", "ollama", None)]
    production = state.load_project_production(project)
    assert state.find_task(production, "D01-030").status == "COMPLETE"
    events = [json.loads(line) for line in (runtime_root / "events.jsonl").read_text().splitlines()]
    recovery = [event for event in events if event.get("type") == "task.session_recovery"]
    assert recovery and recovery[-1].get("stale_session_id") == "cloud-session-old"
    assert "provider-incompatible" in recovery[-1].get("text", "").lower()
