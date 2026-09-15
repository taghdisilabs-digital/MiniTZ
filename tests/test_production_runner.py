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
import minitz_codex_routing as routing
import minitz_production_state as state

MODULE = LOCAL_AI / "minitz_production_runner.py"
spec = importlib.util.spec_from_file_location("minitz_production_runner", MODULE)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


@pytest.fixture(autouse=True)
def isolate_derived_drive_publication(monkeypatch):
    monkeypatch.setattr(runner.evidence, "publish_derived_task_ledger", lambda _repo: None)


@pytest.fixture(autouse=True)
def isolate_remote_source_guard(monkeypatch):
    monkeypatch.setattr(
        runner.evidence, "assert_remote_source_current",
        lambda _repo: {"state": "ALIGNED", "commit": "test", "tree": "test", "remote_commit": "test"},
    )


@pytest.fixture(autouse=True)
def isolate_publication_and_state_only_fixture_git(monkeypatch):
    monkeypatch.setattr(runner.publication, "start_worker", lambda _repo, **_kwargs: None)
    monkeypatch.setattr(runner.publication, "stop_worker", lambda _repo: None)
    monkeypatch.setattr(runner.publication, "request_publication", lambda *_args: {"status": "PENDING"})
    real = runner.evidence.enforce_clean_completion_boundary
    def finalize(repo, result, **kwargs):
        # These pre-existing state-machine fixtures deliberately have no Git repository.
        return real(repo, result, **kwargs) if (Path(repo) / ".git").exists() else result
    monkeypatch.setattr(runner.evidence, "enforce_clean_completion_boundary", finalize)


def test_invoke_structured_never_rotates_silent_executor_on_timer(tmp_path: Path, monkeypatch):
    fake = tmp_path / "slow_valid.py"; output = tmp_path / "result.json"
    fake.write_text(
        "import json,os,time\n"
        "time.sleep(0.4)\n"
        "open(os.environ['OUT'],'w').write(json.dumps({'task_id':'T','status':'CONTINUE','summary':'ok','evidence':['pass']}))\n"
    )
    monkeypatch.setenv("OUT", str(output))
    monkeypatch.setenv("MINITZ_CODEX_STALL_SECONDS", "0.02")
    monkeypatch.setattr(routing, "build_codex_command", lambda *_args, **_kwargs: [sys.executable, str(fake)])
    telemetry = runner.initial_runtime()
    journal = runner.production_events.ProductionEventJournal(tmp_path / "events.jsonl", failure_path=tmp_path / "failures.jsonl")
    rc, detail = runner.invoke_structured(
        "prompt", routing.Route("gpt-6-astra", "ultra"), tmp_path / "schema", output,
        tmp_path / "stdout.log", tmp_path / "stderr.log", tmp_path / "runtime.json", telemetry,
        heartbeat_interval=0.01, event_journal=journal, session_task_id="D03-01", cwd=tmp_path,
    )
    assert rc == 0, detail
    assert "MINITZ_EXECUTOR_STALL_ROTATION" not in detail
    event_path = tmp_path / "events.jsonl"
    events = [json.loads(line) for line in event_path.read_text().splitlines()] if event_path.exists() else []
    assert not any(e.get("type") == "task.executor_stall_recovery" for e in events)

def test_invoke_structured_slow_valid_executor_finishes_without_watchdog(tmp_path: Path, monkeypatch):
    fake = tmp_path / "slow_valid.py"; output = tmp_path / "result.json"
    fake.write_text(
        "import json,os,time\n"
        "time.sleep(0.14)\n"
        "open(os.environ['OUT'],'w').write(json.dumps({'task_id':'T','status':'CONTINUE','summary':'ok','evidence':['pass']}))\n"
    )
    monkeypatch.setenv("OUT", str(output))
    monkeypatch.setenv("MINITZ_CODEX_STALL_SECONDS", "0.05")
    monkeypatch.setattr(routing, "build_codex_command", lambda *_args, **_kwargs: [sys.executable, str(fake)])
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
    repo = root / "repo"; project = repo / "projects/minitz-games"
    (repo / "docs/project-state").mkdir(parents=True); (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/03_MINITZ_CURRENT_STATE.md").write_text("active_execution:\n  id: D01-030\n  state: PENDING\ngames:\n  completed_demo_tasks: 0\n  queued_successor: D01-030\n")
    (repo / "docs/project-state/04_MINITZ_ACTIVE_TASK.md").write_text("task:\n  id: D01-030\n  project: MiniTZ Games\n  section: demo01\n  class: hard\n  title: Rival combat\n  status: PENDING\n")
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
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda **_kwargs: {"gpt-6-astra": {"ultra"}})
    def command(_route, _schema, output, _cwd):
        payload = {"task_id": "D01-030", "status": "COMPLETE", "summary": "done", "evidence": ["runtime pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]
    monkeypatch.setattr(runner.routing, "build_codex_command", command)
    persisted = []
    monkeypatch.setattr(runner.evidence, "persist_local_continuity", lambda _repo, task_id, **_kw: persisted.append(task_id) or {"commit": "c", "tree": "t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.02) == 0
    assert persisted == ["D01-30", "SECTION-demo01"]
    production = state.load_project_production(project)
    assert state.find_task(production, "D01-030").status == "COMPLETE"
    assert state.load_active_task(repo).id == "NONE"
    telemetry = runner.load_runtime(runtime_root / "runtime.json")
    assert telemetry["status"] == "COMPLETE"


def test_public_unit_name_is_single_monorepo_unit():
    assert runner.UNIT_NAME == "minitz-production"


def test_runner_plans_and_audits_empty_next_section(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"; project = repo / "projects/minitz-games"; runtime_root = tmp_path / "runtime"
    (repo / "docs/project-state").mkdir(parents=True); (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/03_MINITZ_CURRENT_STATE.md").write_text("active_execution:\n  id: NONE\n  state: READY\ngames:\n  completed_demo_tasks: 1\n  queued_successor: NONE\n")
    (repo / "docs/project-state/04_MINITZ_ACTIVE_TASK.md").write_text("task:\n  id: NONE\n  project: MiniTZ Games\n  section: NONE\n  class: NONE\n  title: No active Project task\n  status: COMPLETE\n")
    (project / "docs/PRODUCTION.md").write_text("# P\n\nStatus: `IN_PROGRESS`\nCurrent section: `stage2`\nCurrent task: `NONE`\n\n## Section: demo01 | Demo | COMPLETE\n\n- [x] D01-050 | deep_memory | Close demo | COMPLETE | pass\n\n## Section: stage2 | Expansion | PENDING_UNPLANNED\n")
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda **_kwargs: {"gpt-6-astra": {"ultra"}, "gpt-5.6-luna": {"medium"}})
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
    monkeypatch.setattr(runner.evidence, "persist_local_continuity", lambda _repo, task_id, **_kw: {"commit": task_id, "tree": "t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.02) == 0
    production = state.load_project_production(project)
    assert state.find_task(production, "S2-001").status == "COMPLETE"
    assert next(s for s in production.sections if s.id == "stage2").status == "COMPLETE"
    assert calls["plan"] == 2


def test_observed_limit_falls_back_to_next_eligible_model(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path); runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda **_kwargs: {"gpt-6-astra": {"ultra"}, "gpt-5.6-terra": {"ultra"}})
    used = []
    def command(route, _schema, output, _cwd):
        used.append(route.model)
        if route.model == "gpt-6-astra":
            return [sys.executable, "-c", "import sys; print('usage_limit_exceeded', file=sys.stderr); sys.exit(1)"]
        payload = {"task_id": "D01-030", "status": "COMPLETE", "summary": "done", "evidence": ["runtime pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]
    monkeypatch.setattr(runner.routing, "build_codex_command", command)
    monkeypatch.setattr(runner.evidence, "persist_local_continuity", lambda _repo, task_id, **_kw: {"commit": task_id, "tree": "t"})
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
    assert calls == [["systemctl", "enable", "--now", "minitz-production.service"]]


def test_persistent_production_unit_is_enabled_resume_contract():
    unit = (LOCAL_AI / "minitz-production.service").read_text()
    assert "ExecStart=/usr/local/bin/minitz-codex production run" in unit
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


def test_local_persistence_failure_is_not_a_remote_retry_spin(tmp_path: Path, monkeypatch):
    runtime = tmp_path / "runtime.json"; telemetry = runner.initial_runtime()
    calls = []
    def persist(*_args):
        calls.append(True)
        raise RuntimeError("local storage unavailable")
    monkeypatch.setattr(runner.evidence, "persist_local_continuity", persist)
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: pytest.fail("no blocking retry loop"))
    with pytest.raises(RuntimeError, match="local storage"):
        runner._persist_until_success(tmp_path, "D01-33", runtime, telemetry)
    assert len(calls) == 1


def test_section_planner_emits_canonical_d_series_ids(tmp_path: Path):
    repo = tmp_path / "repo"
    project = repo / "projects/minitz-games"
    (repo / "docs/project-state").mkdir(parents=True)
    (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/03_MINITZ_CURRENT_STATE.md").write_text("active_execution:\n  id: NONE\n  state: READY\n")
    (repo / "docs/project-state/04_MINITZ_ACTIVE_TASK.md").write_text("task:\n  id: NONE\n  project: MiniTZ Games\n  section: NONE\n  class: NONE\n  title: No active Project task\n  status: COMPLETE\n")
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
        "persist_local_continuity",
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
    assert telemetry["last_result"]["status"] == "LOCAL_PERSISTED_PUBLICATION_PENDING"


def test_pre_task_reconcile_defers_when_current_task_output_is_dirty(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda **_kwargs: {"gpt-6-astra": {"ultra"}})

    def command(_route, _schema, output, _cwd):
        payload = {"task_id": "D01-030", "status": "COMPLETE", "summary": "done", "evidence": ["runtime pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]

    monkeypatch.setattr(runner.routing, "build_codex_command", command)
    monkeypatch.setattr(runner.evidence, "continuity_changes", lambda _repo: True)
    monkeypatch.setattr(runner.evidence, "unexpected_dirty_paths", lambda _repo: {"projects/minitz-games/partial.cpp"})
    persisted = []
    monkeypatch.setattr(runner.evidence, "persist_local_continuity", lambda _repo, task_id, **_kw: persisted.append(task_id) or {"commit": "c", "tree": "t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.02) == 0
    assert "RECONCILE-D01-30" not in persisted
    assert "D01-30" in persisted


def test_runner_startup_clears_stale_child_pid_before_first_work(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    project = repo / "projects/minitz-games"
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(parents=True)
    stale = runner.initial_runtime()
    stale["child_pid"] = 999999
    runner.save_runtime(runtime_root / "runtime.json", stale)
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda **_kwargs: {})
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
    monkeypatch.setenv("MINITZ_CODEX_ONE_HELPER_TASKS", "*")
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


def test_task_prompt_consumes_booster_handoff_from_context_directory(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    production = state.load_project_production(project)
    task = state.find_task(production, "D01-030")
    capsule = runner._task_capsule_path(tmp_path / "runtime", task.id)
    booster_root = capsule.parent.parent / "boost-work-program"
    booster_root.mkdir(parents=True)
    (booster_root / "BOOSTER_TASK_LIST.json").write_text('{}\n')
    handoff = booster_root / "context" / "main-coder-context.json"
    handoff.parent.mkdir(parents=True)
    handoff.write_text(json.dumps({"task_id": task.id, "booster_results": []}) + "\n")

    prompt = runner._task_prompt(repo, production, task, runner.initial_runtime(), capsule)

    assert f"BOOSTER_MAIN_CODER_HANDOFF: {handoff}" in prompt


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
            "capability":"llm.fast","provider":"ollama-qwen","model":"qwen3-coder-next:minitz",
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


def test_local_resource_assist_pins_qwen_without_cloud_failover(tmp_path: Path, monkeypatch):
    projection = tmp_path / "memory/current-task.json"
    projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"D02-01","task_memory":{"task_class":"hard","summary":"route assist"},"failures":[],"capabilities":{}}))
    calls = []
    monkeypatch.setattr(runner.subprocess, "run", lambda argv, **kwargs: calls.append(argv) or subprocess.CompletedProcess(argv, 2, stdout="", stderr="qwen unavailable"))
    assert runner._ensure_local_resource_assist(tmp_path, "D02-01", projection) is None
    argv = calls[0]
    assert argv[argv.index("--provider") + 1] == "ollama-qwen"
    assert argv[argv.index("--max-failover-attempts") + 1] == "1"


def test_local_resource_assist_uses_live_registry_pool_and_persists_routing_evidence(tmp_path: Path, monkeypatch):
    projection = tmp_path / "memory/current-task.json"
    projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"D02-01","task_memory":{"task_class":"hard","summary":"route assist"},"failures":[],"capabilities":{}}))
    calls = []
    def fake_run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({
            "capability":"llm.fast","provider":"groq","model":"qwen/test","latency_ms":17,
            "text":"Likely failure cause if any: NONE","usage":{"total_tokens":9},
            "routing_evidence":{"authority":"RESOURCE_IMPLEMENTATION","capability":"llm.fast","attempt_limit":3,
                "attempted":[{"provider":"ollama-qwen","status":"FAILED","failure_code":"TRANSPORT_ERROR"},{"provider":"groq","status":"SUCCEEDED"}],
                "fallback_used":True,"selection":"ordered-capability-route"}
        })+"\n", stderr="")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    path = runner._ensure_local_resource_assist(tmp_path, "D02-01", projection)
    assert path
    assert len(calls) == 1
    assert "--provider" in calls[0] and calls[0][calls[0].index("--provider")+1] == "ollama-qwen"
    payload = json.loads(path.read_text())
    assert payload["provider"] == "groq"
    assert payload["latency_ms"] == 17
    assert payload["routing_evidence"]["fallback_used"] is True
    assert [x["provider"] for x in payload["routing_evidence"]["attempted"]] == ["ollama-qwen", "groq"]


def test_local_resource_assist_failure_is_non_blocking_and_recorded(tmp_path: Path, monkeypatch):
    projection = tmp_path / "memory" / "current-task.json"
    projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"D02-01","task_memory":{"summary":"x"},"failures":[],"capabilities":{}}))
    monkeypatch.setattr(runner.subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 2, stdout="", stderr="local resource unavailable"))
    journal = runner.production_events.ProductionEventJournal(tmp_path / "events.jsonl", failure_path=tmp_path / "failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path, "D02-01", projection, journal) is None
    failures = [json.loads(line) for line in (tmp_path / "failures.jsonl").read_text().splitlines()]
    assert failures[-1]["failure_type"] == "PROCESS_FAILED"
    assert failures[-1]["event_type"] == "resource.local_assist_failed"


def test_runtime_failure_does_not_cooldown_model():
    telemetry = runner.initial_runtime()
    route = routing.Route("gpt-6-astra", "ultra")
    runner._set_failure(telemetry, route, "ActiveTurnOutputSchemaMismatch", "D01-030")
    assert telemetry["status"] == "RECOVERING_RUNTIME"
    assert "gpt-6-astra" not in telemetry.get("cooldowns", {})
    assert telemetry["last_result"]["status"] == "RUNTIME_RECOVERY"


def test_explicit_model_unavailable_failure_refreshes_catalog_but_generic_runtime_does_not(tmp_path: Path, monkeypatch):
    telemetry = runner.initial_runtime()
    route = routing.Route("gpt-6-astra", "ultra")
    detail = "provider rejected request: model unavailable"
    runner._set_failure(telemetry, route, detail, "UNIFY-02")

    assert telemetry["status"] == "RECOVERING_MODEL"
    assert telemetry["last_result"]["status"] == "MODEL_RECOVERY"
    assert telemetry["last_result"]["catalog_refresh_required"] is True
    assert route.model in telemetry["cooldowns"]

    discovered = []
    monkeypatch.setattr(
        runner,
        "_discover_runtime_catalog",
        lambda runtime_root: discovered.append(runtime_root) or {"gpt-5.6-luna": {"max"}},
    )
    refreshed = runner._refresh_catalog_after_route_failure(tmp_path, telemetry, detail)
    assert refreshed == {"gpt-5.6-luna": {"max"}}
    assert discovered == [tmp_path]
    assert telemetry["last_result"]["catalog_refresh"] == {
        "status": "REFRESHED",
        "models": ["gpt-5.6-luna"],
    }

    generic = runner.initial_runtime()
    assert runner._refresh_catalog_after_route_failure(tmp_path, generic, "ordinary native process failed") is None
    assert discovered == [tmp_path]


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
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda **_kwargs: {
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
    monkeypatch.setattr(runner.evidence, "persist_local_continuity", lambda _repo, task_id, **_kw: {"commit":task_id,"tree":"t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.01) == 0
    assert used[:2] == [("resume", "gpt-6-astra", "stale-session"), ("new", "gpt-6-astra", None)]
    assert all(model != "gpt-5.6-terra" for _kind, model, _session in used)


def test_local_resource_assist_rejects_hallucinated_file_paths_and_caches_rejection(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/minitz-games"
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
            "provider":"ollama-qwen","model":"qwen3-coder-next:minitz",
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
    project = tmp_path / "repo/projects/minitz-games"
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
    project = tmp_path / "repo/projects/minitz-games"
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
    project = tmp_path / "repo/projects/minitz-games"; project.mkdir(parents=True)
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
    project = tmp_path / "repo/projects/minitz-games"; project.mkdir(parents=True)
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
    project = tmp_path / "repo/projects/minitz-games"; project.mkdir(parents=True)
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
    project = tmp_path / "repo/projects/minitz-games"
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
    project = tmp_path / "repo/projects/minitz-games"
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
    route = routing.Route("qwen3-coder-next:minitz", "none", "ollama")
    before = datetime.now(timezone.utc)
    runner._set_failure(telemetry, route, '"qwen3-coder-next:minitz" does not support thinking', "D03-01")
    until = datetime.fromisoformat(telemetry["cooldowns"][route.model])
    assert until > before
    assert telemetry["status"] == "RECOVERING_MODEL"
    assert telemetry["last_result"]["status"] == "MODEL_RECOVERY"


def test_account_usage_limit_cools_only_the_observed_failed_model():
    telemetry = runner.initial_runtime()
    detail = "You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at Sep 12th, 2026 9:41 PM."

    expected_models = []
    for model, reasoning in (
        ("gpt-6-astra", "ultra"),
        ("gpt-5.6-terra", "ultra"),
        ("gpt-5.6-sol", "ultra"),
        ("gpt-5.6-luna", "max"),
        ("gpt-5.3-codex-spark", "xhigh"),
    ):
        before = datetime.now(timezone.utc)
        runner._set_failure(telemetry, routing.Route(model, reasoning), detail, "D03-01")
        retry_at = datetime.fromisoformat(telemetry["cooldowns"][model])
        assert retry_at > before
        expected_models.append(model)
        assert set(telemetry["cooldowns"]) == set(expected_models)
    assert telemetry["status"] == "RECOVERING_MODEL"
    assert datetime.fromisoformat(telemetry["last_result"]["retry_at"]) > before


def test_account_usage_limit_fallback_sequence_reaches_bounded_local_route(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    task = state.find_task(state.load_project_production(project), "D01-030")
    catalog = {
        "gpt-6-astra": {"ultra"},
        "gpt-5.6-terra": {"ultra"},
        "gpt-5.6-sol": {"ultra"},
        "gpt-5.6-luna": {"max"},
        "gpt-5.3-codex-spark": {"xhigh"},
        "qwen3-coder-next:minitz": {"local"},
    }
    telemetry = runner.initial_runtime()
    detail = "You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at Sep 12th, 2026 9:41 PM."
    sequence = [
        routing.Route("gpt-6-astra", "ultra"),
        routing.Route("gpt-5.6-terra", "ultra"),
        routing.Route("gpt-5.6-sol", "ultra"),
        routing.Route("gpt-5.6-luna", "max"),
        routing.Route("gpt-5.3-codex-spark", "xhigh"),
    ]
    for failed, expected_next in zip(sequence, sequence[1:]):
        runner._set_failure(telemetry, failed, detail, task.id)
        route, _packet = runner._select_task_route(
            task, catalog, telemetry["cooldowns"], datetime.now(timezone.utc), telemetry, repo, project
        )
        assert route == expected_next
    runner._set_failure(telemetry, sequence[-1], detail, task.id)
    route, packet = runner._select_task_route(
        task, catalog, telemetry["cooldowns"], datetime.now(timezone.utc), telemetry, repo, project
    )
    assert route == routing.Route("qwen3-coder-next:minitz", "none", "ollama")
    assert routing.is_bounded_fallback(route)
    assert packet


def test_cross_provider_compaction_resume_error_is_session_incompatible():
    detail = '{"error":{"message":"input[42]: unknown input item type: \"compaction\"","type":"invalid_request_error"}}'
    assert runner._is_resume_protocol_incompatible(detail)
    assert not runner._is_resume_protocol_incompatible("ordinary native process failed")


def test_bounded_fallback_uses_fresh_executor_without_replacing_persistent_session():
    telemetry = runner.initial_runtime()
    telemetry.update({"task_session_id": "persistent-session", "session_task_id": "D03-01"})
    assert runner._resume_session_for_route(telemetry, "D03-01", routing.Route("gpt-5.6-luna", "max")) == "persistent-session"
    assert runner._resume_session_for_route(telemetry, "D03-01", routing.Route("gpt-5.3-codex-spark", "xhigh")) is None
    assert runner._resume_session_for_route(telemetry, "D03-01", routing.Route("qwen3-coder-next:minitz", "none", "ollama")) is None
    assert telemetry["task_session_id"] == "persistent-session"


def test_bounded_invoke_never_overwrites_persistent_session_identity(tmp_path: Path, monkeypatch):
    fake = tmp_path / "bounded.py"
    fake.write_text(
        "import json\n"
        "print(json.dumps({'type':'thread.started','thread_id':'bounded-fresh-session'}), flush=True)\n"
    )
    monkeypatch.setattr(
        routing, "build_codex_command",
        lambda *_args, **_kwargs: [sys.executable, str(fake)],
    )
    telemetry = runner.initial_runtime()
    telemetry.update({"task_session_id": "persistent-strong-session", "session_task_id": "D03-01"})
    rc, _detail = runner.invoke_structured(
        "prompt", routing.Route("gpt-5.3-codex-spark", "xhigh"), tmp_path / "schema.json",
        tmp_path / "result.json", tmp_path / "stdout.jsonl", tmp_path / "stderr.log",
        tmp_path / "runtime.json", telemetry, heartbeat_interval=0.01, cwd=tmp_path,
        session_task_id="D03-01", persist_session_identity=False,
    )
    assert rc == 0
    assert telemetry["task_session_id"] == "persistent-strong-session"
    assert telemetry["session_task_id"] == "D03-01"


def test_bounded_fallback_result_can_never_close_whole_task():
    complete = runner.evidence.TaskResult("D03-01", "COMPLETE", "bounded work says done", ("runtime pass",))
    bounded = runner._normalize_result_for_route(complete, routing.Route("qwen3-coder-next:minitz", "none", "ollama"))
    assert bounded.status == "COMPLETE"
    assert bounded.evidence == ("runtime pass",)
    assert bounded.summary == "bounded work says done"
    strong = runner._normalize_result_for_route(complete, routing.Route("gpt-6-astra", "ultra"))
    assert strong == complete


def test_bounded_fallback_no_progress_never_creates_a_wait_state(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    task = state.find_task(state.load_project_production(project), "D01-030")
    qwen = routing.Route("qwen3-coder-next:minitz", "none", "ollama")
    telemetry = runner.initial_runtime()
    telemetry["bounded_no_progress"] = {qwen.model: runner._bounded_packet_id(repo, project, task)}
    route, packet = runner._select_task_route(
        task, {qwen.model: {"local"}}, {}, datetime.now(timezone.utc), telemetry, repo, project
    )
    assert route == qwen
    assert packet is not None
    assert "bounded_no_progress" not in runner.initial_runtime()


def test_bounded_workspace_fingerprint_changes_only_when_project_working_bytes_change(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    first = runner._task_workspace_fingerprint(repo, project)
    assert first == runner._task_workspace_fingerprint(repo, project)
    (project / "bounded.txt").write_text("real bounded progress", encoding="utf-8")
    second = runner._task_workspace_fingerprint(repo, project)
    assert second != first


def test_source_difference_becomes_inline_repair_not_a_runner_stop(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime_root = tmp_path / "runtime"; runtime_root.mkdir()
    telemetry = runner.initial_runtime()
    telemetry.update({"status": "RUNNING", "task_id": "D05-01", "task_session_id": "retained-session"})
    monkeypatch.setattr(runner.evidence, "assert_remote_source_current", lambda _repo: (_ for _ in ()).throw(runner.evidence.SourceAlignmentError("VPS source behind origin/main")))
    journal = runner.production_events.ProductionEventJournal(runtime_root / "events.jsonl", failure_path=runtime_root / "failures.jsonl")
    assert runner._guard_source_alignment(repo, runtime_root / "runtime.json", telemetry, journal)
    assert telemetry["status"] == "RUNNING"
    assert telemetry["task_session_id"] == "retained-session"
    assert telemetry["source_alignment"]["state"] == "RECONCILIATION_REQUIRED"


def test_runner_rechecks_source_after_model_before_accepting_result(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime_root = tmp_path / "runtime"
    checks = {"n": 0}

    def guard(_repo):
        checks["n"] += 1
        if checks["n"] == 2:
            raise runner.evidence.SourceAlignmentError("origin/main changed during task turn")
        return {"state": "ALIGNED", "commit": "c", "tree": "t", "remote_commit": "c"}

    monkeypatch.setattr(runner.evidence, "assert_remote_source_current", guard)
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda **_kwargs: {"gpt-6-astra": {"ultra"}})

    def command(_route, _schema, output, _cwd):
        payload = {"task_id": "D01-030", "status": "COMPLETE", "summary": "done", "evidence": ["runtime pass"]}
        code = f"import pathlib; pathlib.Path({str(output)!r}).write_text({json.dumps(json.dumps(payload))})"
        return [sys.executable, "-c", code]

    monkeypatch.setattr(runner.routing, "build_codex_command", command)
    persisted = []
    monkeypatch.setattr(runner.evidence, "persist_local_continuity", lambda *_args, **_kwargs: persisted.append(True) or {"commit": "c", "tree": "t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.01) == 0
    assert state.find_task(state.load_project_production(project), "D01-030").status == "COMPLETE"
    assert persisted
    assert checks["n"] >= 4


def test_persistent_unit_has_no_optional_qwen_startup_blocker():
    unit = (LOCAL_AI / "minitz-production.service").read_text()
    source_pre = "ExecStartPre=/usr/local/lib/minitz-ai/minitz-source-sync.sh"
    assert source_pre in unit
    assert "ExecStartPre=/usr/local/lib/minitz-workstation/minitz-qwen-ready.sh" not in unit
    assert "Requires=minitz-ollama.service" not in unit
    assert "Environment=MINITZ_PRODUCTION_RUNNER=/root/attached-storage/minitz-os-sandbox/workspace/repo/ops/local-ai/minitz_production_runner.py" in unit
    assert "Environment=MINITZ_CODEX_PREFER_MODEL=gpt-6-astra" in unit
    assert "Environment=MINITZ_CODEX_EXCLUDE_MODELS=gpt-5.6-luna" in unit
    assert "Environment=MINITZ_CODEX_FORCE_MODEL=" not in unit
    assert "Environment=HOME=/root" in unit


def test_installer_never_toggles_production_service_outside_lifecycle_controller():
    installer = (LOCAL_AI / "install-minitz-ai.sh").read_text()
    assert "systemctl disable minitz-production.service" not in installer
    assert "systemctl enable minitz-production.service" not in installer
    assert "/etc/systemd/system/minitz-on.target" in installer


def test_status_exposes_last_source_alignment_receipt(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime.json"
    payload = runner.initial_runtime()
    payload["source_alignment"] = {"state": "ALIGNED", "commit": "abc", "tree": "def", "remote_commit": "abc"}
    payload["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
    runner.save_runtime(runtime, payload)
    monkeypatch.setattr(runner, "service_active", lambda: True)
    assert runner.production_status(repo, project, runtime)["source_alignment"]["commit"] == "abc"


def test_source_alignment_failure_does_not_spin_persistence_retry(tmp_path: Path, monkeypatch):
    runtime = tmp_path / "runtime.json"
    telemetry = runner.initial_runtime()
    sleeps = []
    monkeypatch.setattr(
        runner.evidence,
        "persist_local_continuity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(runner.evidence.SourceAlignmentError("remote moved")),
    )
    monkeypatch.setattr(runner.time, "sleep", lambda seconds: sleeps.append(seconds))
    with pytest.raises(runner.evidence.SourceAlignmentError):
        runner._persist_until_success(tmp_path, "D03-01", runtime, telemetry)
    assert sleeps == []
    assert telemetry["last_result"] is None


def test_installer_copies_source_sync_bootstrap():
    installer = (LOCAL_AI / "install-minitz-ai.sh").read_text()
    assert '"$SOURCE_DIR/minitz-source-sync.sh"' in installer


def test_customer_pause_file_is_not_a_production_authority():
    source = (LOCAL_AI / "minitz_production_runner.py").read_text()
    assert "customer-pause-request.json" not in source
    assert "PAUSED_FOR_CUSTOMER" not in source
    assert "minitz-off-request.json" not in source


def test_strong_task_prompt_forbids_hard_class_stall_and_scope_growth(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    production = state.load_project_production(project)
    task = state.find_task(production, "D01-030")
    capsule = tmp_path / "capsule.json"; capsule.write_text("{}")
    monkeypatch.setattr(runner.packets, "compile_task_packet", lambda *_args: "BASE")
    prompt = runner._task_prompt(repo, production, task, runner.initial_runtime(), capsule)
    assert "TASK_CLASS_IS_NOT_A_BLOCKER" in prompt
    assert "DO_NOT_EXPAND_ACCEPTANCE_SCOPE" in prompt
    assert "CONTINUE_REQUIRES_EXACT_UNMET_CRITERION" in prompt
    assert "NO_MONITOR_ONLY_STALL" in prompt


def test_owner_accept_current_task_closes_and_advances_without_model_turn(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path); runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    telemetry = runner.initial_runtime(); telemetry.update({"status":"RUNNING","task_id":"D01-30","task_session_id":"sess","session_task_id":"D01-30"})
    runner.save_runtime(runtime_root / "runtime.json", telemetry)
    persisted=[]
    monkeypatch.setattr(runner.evidence, "persist_local_continuity", lambda _repo, task_id, **_kw: persisted.append(task_id) or {"commit":"c","tree":"t"})
    result = runner.accept_current_task(repo, project, runtime_root, "D01-30", ["OWNER_ACCEPTED: verified pass"])
    production = state.load_project_production(project)
    assert state.find_task(production, "D01-30").status == "COMPLETE"
    assert result["accepted_task"] == "D01-30"
    assert result["next_task"] is None
    after = runner.load_runtime(runtime_root / "runtime.json")
    assert after["task_session_id"] is None
    assert after["session_task_id"] is None
    assert after["status"] == "COMPLETE"
    assert persisted == ["D01-30"]


def test_parser_exposes_owner_accept_fast_path():
    args = runner._parser().parse_args(["accept", "--task", "D04-01", "--evidence", "OWNER_ACCEPTED: pass"])
    assert args.command == "accept"
    assert args.task == "D04-01"
    assert args.evidence == ["OWNER_ACCEPTED: pass"]
    assert args.no_resume is False


def test_runner_commits_validated_task_output_without_extra_model_turn(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path); runtime_root = tmp_path / "runtime"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "MiniTZ Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda **_kwargs: {"gpt-6-astra": {"ultra"}})
    calls = {"n": 0}
    def command(_route, _schema, output, _cwd):
        calls["n"] += 1
        if calls["n"] == 1:
            code = (
                "import json,pathlib; "
                f"pathlib.Path({str(project / 'dirty.txt')!r}).write_text('task bytes'); "
                f"pathlib.Path({str(output)!r}).write_text(json.dumps({{'task_id':'D01-030','status':'COMPLETE','summary':'done','evidence':['runtime pass']}}))"
            )
        else:
            code = (
                "import json,pathlib,subprocess; "
                f"subprocess.run(['git','-C',{str(repo)!r},'add','projects/minitz-games/dirty.txt'],check=True); "
                f"subprocess.run(['git','-C',{str(repo)!r},'commit','-qm','task output'],check=True); "
                f"pathlib.Path({str(output)!r}).write_text(json.dumps({{'task_id':'D01-030','status':'COMPLETE','summary':'done','evidence':['runtime pass']}}))"
            )
        return [sys.executable, "-c", code]
    monkeypatch.setattr(runner.routing, "build_codex_command", command)
    persisted=[]
    monkeypatch.setattr(runner.evidence, "persist_local_continuity", lambda _repo, task_id, **_kw: persisted.append(task_id) or {"commit":"c","tree":"t"})
    assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.01) == 0
    assert calls["n"] == 1
    assert state.find_task(state.load_project_production(project), "D01-030").status == "COMPLETE"
    events=[json.loads(line) for line in (runtime_root/'events.jsonl').read_text().splitlines()]
    task_events=[e for e in events if e.get('task_id') in ('D01-030','D01-30') and e.get('type') in ('task.continue','task.completed')]
    assert not any(e.get("type") == "task.continue" for e in task_events)
    assert task_events[-1].get('type') == 'task.completed'


def _write_taskbooster_local_assist(runtime: Path, text: str) -> Path:
    path = runtime / "memory/taskbooster-test-local.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"provider":"ollama-qwen","model":"qwen3-coder-next:minitz","text":text,"usage":{}}))
    return path


def test_taskbooster_accepts_grounded_spark_assist_for_strong_route(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime"; runtime.mkdir()
    target = project / "Config/DefaultEngine.ini"; target.parent.mkdir(parents=True); target.write_text("[Renderer]\nr.Test=1\n")
    task = state.find_task(state.load_project_production(project), "D01-030")
    local = _write_taskbooster_local_assist(runtime, "Inspect `Config/DefaultEngine.ini` exactly.")
    monkeypatch.setattr(runner, "_bounded_packet_id", lambda *_args: "state-1")
    output_holder = {}
    monkeypatch.setattr(runner.routing, "build_taskbooster_command", lambda _route,_schema,output,_cwd: output_holder.setdefault("cmd", ["spark-fake", str(output)]))
    real_run = runner.subprocess.run
    def fake_run(argv, **kwargs):
        if argv and argv[0] == "spark-fake":
            prompt = kwargs["input"]; packet = json.loads(prompt.split("TASKBOOSTER_PACKET_JSON:\n",1)[1])
            result = {"booster_id":packet["booster_id"],"status":"USEFUL","finding":"r.Test is enabled","evidence_refs":[{"path":"Config/DefaultEngine.ini","sha256":packet["allowed_reads"][0]["sha256"],"line_start":2,"line_end":2,"quote":"r.Test=1"}],"candidate_actions":[],"candidate_patch":"","recommended_commands":[],"uncertainties":[]}
            Path(argv[1]).write_text(json.dumps(result)); return subprocess.CompletedProcess(argv,0,stdout="{}\n",stderr="")
        return real_run(argv, **kwargs)
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    journal = runner.production_events.ProductionEventJournal(runtime/"events.jsonl", failure_path=runtime/"failures.jsonl")
    path = runner._ensure_taskbooster_assist(repo, project, runtime, task, routing.Route("gpt-6-astra","ultra"), {"gpt-5.3-codex-spark":{"xhigh"}}, local, journal)
    assert path and path.exists()
    payload = json.loads(path.read_text())
    assert payload["authority"] == "NONE"
    assert payload["result"]["finding"] == "r.Test is enabled"


def test_taskbooster_skips_bounded_route_and_no_grounded_target(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime"; runtime.mkdir()
    task = state.find_task(state.load_project_production(project), "D01-030")
    called = []
    monkeypatch.setattr(runner.routing, "build_taskbooster_command", lambda *_a,**_k: called.append(True) or ["never"])
    local = _write_taskbooster_local_assist(runtime, "No exact project path is named here.")
    catalog = {"gpt-5.3-codex-spark":{"xhigh"}}
    assert runner._ensure_taskbooster_assist(repo, project, runtime, task, routing.Route("gpt-5.3-codex-spark","xhigh"), catalog, local) is None
    assert runner._ensure_taskbooster_assist(repo, project, runtime, task, routing.Route("gpt-6-astra","ultra"), catalog, local) is None
    assert called == []


def test_taskbooster_process_failure_is_preserved_and_nonblocking(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime"; runtime.mkdir()
    target = project / "Config/DefaultEngine.ini"; target.parent.mkdir(parents=True); target.write_text("x=1\n")
    task = state.find_task(state.load_project_production(project), "D01-030")
    local = _write_taskbooster_local_assist(runtime, "Inspect `Config/DefaultEngine.ini`.")
    monkeypatch.setattr(runner, "_bounded_packet_id", lambda *_args: "state-1")
    monkeypatch.setattr(runner.routing, "build_taskbooster_command", lambda *_a,**_k: ["spark-fail"])
    real_run = runner.subprocess.run
    monkeypatch.setattr(runner.subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv,9,stdout="partial spark output",stderr="spark failed") if argv[0]=="spark-fail" else real_run(argv,**kwargs))
    journal = runner.production_events.ProductionEventJournal(runtime/"events.jsonl", failure_path=runtime/"failures.jsonl")
    result = runner._ensure_taskbooster_assist(repo, project, runtime, task, routing.Route("gpt-6-astra","ultra"), {"gpt-5.3-codex-spark":{"xhigh"}}, local, journal)
    assert result is None
    rejected = list((runtime/"memory/taskbooster").glob("*.rejected.json")); assert len(rejected)==1
    failure = json.loads(rejected[0].read_text()); assert failure["reason"] == "PROCESS_FAILED"
    rows = [json.loads(line) for line in (runtime/"failures.jsonl").read_text().splitlines()]
    assert any(row["failure_type"] == "PROCESS_FAILED" and row["event_type"] == "resource.taskbooster_failed" for row in rows)


def test_taskbooster_stale_input_is_rejected_without_blocking(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime"; runtime.mkdir()
    target = project / "Config/DefaultEngine.ini"; target.parent.mkdir(parents=True); target.write_text("x=1\n")
    task = state.find_task(state.load_project_production(project), "D01-030")
    local = _write_taskbooster_local_assist(runtime, "Inspect `Config/DefaultEngine.ini`.")
    monkeypatch.setattr(runner, "_bounded_packet_id", lambda *_args: "state-1")
    holder = {}
    monkeypatch.setattr(runner.routing, "build_taskbooster_command", lambda _route,_schema,output,_cwd: holder.setdefault("cmd", ["spark-stale", str(output)]))
    real_run = runner.subprocess.run
    def fake_run(argv, **kwargs):
        if argv[0] == "spark-stale":
            packet = json.loads(kwargs["input"].split("TASKBOOSTER_PACKET_JSON:\n",1)[1])
            target.write_text("x=2\n")
            Path(argv[1]).write_text(json.dumps({"booster_id":packet["booster_id"],"status":"NO_ACTION","finding":"","evidence_refs":[],"candidate_actions":[],"candidate_patch":"","recommended_commands":[],"uncertainties":[]}))
            return subprocess.CompletedProcess(argv,0,stdout="{}",stderr="")
        return real_run(argv, **kwargs)
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    journal = runner.production_events.ProductionEventJournal(runtime/"events.jsonl", failure_path=runtime/"failures.jsonl")
    assert runner._ensure_taskbooster_assist(repo, project, runtime, task, routing.Route("gpt-6-astra","ultra"), {"gpt-5.3-codex-spark":{"xhigh"}}, local, journal) is None
    rejected = list((runtime/"memory/taskbooster").glob("*.rejected.json")); assert len(rejected)==1
    assert json.loads(rejected[0].read_text())["reason"] == "STALE_INPUT_DIGEST"
    rows = [json.loads(line) for line in (runtime / "failures.jsonl").read_text().splitlines()]
    assert any(row["failure_type"] == "STALE_INPUT" and row["event_type"] == "resource.taskbooster_rejected" for row in rows)


def test_task_prompt_injects_taskbooster_as_non_authoritative_assist(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    production = state.load_project_production(project); task = state.find_task(production, "D01-030")
    capsule = tmp_path / "task.json"; capsule.write_text("{}")
    booster_path = tmp_path / "booster.json"; booster_path.write_text("{}")
    prompt = runner._task_prompt(repo, production, task, runner.initial_runtime(), capsule, taskbooster_path=booster_path, route=routing.Route("gpt-6-astra","ultra"))
    assert f"TASKBOOSTER_ASSIST: {booster_path}" in prompt
    assert "non-authoritative" in prompt.lower()
    assert "validate" in prompt.lower()



def test_commander_resource_command_uses_provider_structured_contract(monkeypatch):
    seen = {}
    def fake_build(provider, **kwargs):
        seen["provider"] = provider
        seen.update(kwargs)
        return ["commander", provider]
    monkeypatch.setattr(runner.commander, "build_resource_command", fake_build)
    registry = {
        "providers": {
            "cloudflare": {
                "commander_structured_output": True,
                "commander_disable_reasoning": True,
            }
        }
    }
    assert runner._commander_resource_command(registry, "cloudflare") == ["commander", "cloudflare"]
    assert seen["response_schema"] == runner.commander.commander_result_schema()
    assert seen["disable_reasoning"] is True

def test_prepare_optional_task_assists_uses_available_resource_without_qwen_residency_gate(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime"; runtime.mkdir()
    task = state.find_task(state.load_project_production(project), "D01-030")
    projection = runtime / "memory/current-task.json"; projection.parent.mkdir(parents=True); projection.write_text("{}")
    local = _write_taskbooster_local_assist(runtime, "Inspect `Config/DefaultEngine.ini`.")
    booster_path = runtime / "memory/taskbooster/accepted.json"; booster_path.parent.mkdir(parents=True); booster_path.write_text("{}")
    calls = []
    monkeypatch.setattr(runner, "_local_qwen_resident", lambda: True)
    monkeypatch.setattr(runner, "_ensure_local_resource_assist", lambda *_a, **_k: calls.append("qwen") or local)
    monkeypatch.setattr(runner, "_ensure_taskbooster_assist", lambda *_a, **_k: calls.append("spark") or booster_path)
    strong = routing.Route("gpt-6-astra", "ultra")
    result = runner._prepare_optional_task_assists(repo, project, runtime, task, strong, {"gpt-5.3-codex-spark":{"xhigh"}}, projection)
    assert result == (local, None)
    assert calls == ["qwen"]
    calls.clear(); monkeypatch.setattr(runner, "_local_qwen_resident", lambda: False)
    assert runner._prepare_optional_task_assists(repo, project, runtime, task, strong, {}, projection) == (local, None)
    assert calls == ["qwen"]
    calls.clear()
    monkeypatch.setattr(runner, "_local_qwen_resident", lambda: True)
    assert runner._prepare_optional_task_assists(repo, project, runtime, task, routing.Route("gpt-5.3-codex-spark","xhigh"), {"gpt-5.3-codex-spark":{"xhigh"}}, projection) == (None, None)
    assert calls == []


def test_prepare_optional_task_assists_uses_fast_llm_pool_when_qwen_not_resident(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime"; runtime.mkdir()
    task = state.find_task(state.load_project_production(project), "D01-030")
    projection = runtime / "memory/current-task.json"; projection.parent.mkdir(parents=True); projection.write_text("{}")
    assist = runtime / "memory/local-assist/external.json"; assist.parent.mkdir(parents=True); assist.write_text("{}")
    booster = runtime / "memory/taskbooster/external.json"; booster.parent.mkdir(parents=True); booster.write_text("{}")
    calls = []
    monkeypatch.setattr(runner, "_local_qwen_resident", lambda: False)
    monkeypatch.setattr(runner, "_ensure_local_resource_assist", lambda *_a, **_k: calls.append("fast-llm") or assist)
    monkeypatch.setattr(runner, "_ensure_taskbooster_assist", lambda *_a, **_k: calls.append("booster") or booster)
    result = runner._prepare_optional_task_assists(repo, project, runtime, task, routing.Route("gpt-6-astra", "ultra"), {}, projection)
    assert result == (assist, None)
    assert calls == ["fast-llm"]


def test_local_assist_invalid_json_preserves_raw_provider_result(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/minitz-games"; project.mkdir(parents=True)
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"D04-01","task_memory":{"task_class":"hard","summary":"Inspect current task"},"failures":[],"capabilities":{}}))
    raw = "not-json-from-qwen"
    monkeypatch.setattr(runner.subprocess,"run",lambda argv,**kwargs: subprocess.CompletedProcess(argv,0,stdout=raw,stderr=""))
    journal=runner.production_events.ProductionEventJournal(tmp_path/"events.jsonl",failure_path=tmp_path/"failures.jsonl")
    assert runner._ensure_local_resource_assist(tmp_path,"D04-01",projection,journal,project_root=project) is None
    raw_files=list((tmp_path/"memory/local-assist").glob("D04-01-*.raw.json"))
    assert len(raw_files)==1
    assert raw_files[0].read_text()==raw
    rows=[json.loads(line) for line in (tmp_path/"failures.jsonl").read_text().splitlines()]
    assert any(row["failure_type"]=="INVALID_RESULT" and row["event_type"]=="resource.local_assist_failed" for row in rows)


def test_local_assist_scope_rejection_preserves_raw_provider_result(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo/projects/minitz-games"; project.mkdir(parents=True)
    projection = tmp_path / "memory/current-task.json"; projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({"task_id":"D04-02","task_memory":{"task_class":"hard","summary":"Current bounded task"},"failures":[],"capabilities":{}}))
    envelope={"provider":"ollama-qwen","model":"qwen3-coder-next:minitz","text":"Inspect `invented/path.cpp`.","usage":{}}
    raw=json.dumps(envelope)
    monkeypatch.setattr(runner.subprocess,"run",lambda argv,**kwargs: subprocess.CompletedProcess(argv,0,stdout=raw,stderr=""))
    assert runner._ensure_local_resource_assist(tmp_path,"D04-02",projection,project_root=project) is None
    raw_files=list((tmp_path/"memory/local-assist").glob("D04-02-*.raw.json")); assert len(raw_files)==1
    assert raw_files[0].read_text()==raw
    rejected=list((tmp_path/"memory/local-assist").glob("D04-02-*.rejected")); assert len(rejected)==1
    assert json.loads(rejected[0].read_text())["raw_result_path"] == str(raw_files[0])


def test_taskbooster_invalid_json_is_preserved_as_rejected_evidence(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime"; runtime.mkdir()
    target = project / "Config/DefaultEngine.ini"; target.parent.mkdir(parents=True); target.write_text("x=1\n")
    task = state.find_task(state.load_project_production(project), "D01-030")
    local = _write_taskbooster_local_assist(runtime, "Inspect `Config/DefaultEngine.ini`.")
    monkeypatch.setattr(runner, "_bounded_packet_id", lambda *_args: "state-1")
    monkeypatch.setattr(runner.routing, "build_taskbooster_command", lambda _route,_schema,output,_cwd: ["spark-invalid", str(output)])
    real_run = runner.subprocess.run
    def fake_run(argv, **kwargs):
        if argv[0] == "spark-invalid":
            Path(argv[1]).write_text('{"broken":')
            return subprocess.CompletedProcess(argv,0,stdout="{}",stderr="")
        return real_run(argv, **kwargs)
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    journal = runner.production_events.ProductionEventJournal(runtime/"events.jsonl", failure_path=runtime/"failures.jsonl")
    assert runner._ensure_taskbooster_assist(repo, project, runtime, task, routing.Route("gpt-6-astra","ultra"), {"gpt-5.3-codex-spark":{"xhigh"}}, local, journal) is None
    rejected = list((runtime/"memory/taskbooster").glob("*.rejected.json")); assert len(rejected)==1
    payload=json.loads(rejected[0].read_text()); assert payload["reason"]=="INVALID_RESULT"
    assert payload["preserve_raw"] is True
    assert Path(payload["raw_result_path"]).read_text()=='{"broken":'


def test_runtime_has_shared_main_coder_state():
    telemetry = runner.initial_runtime()
    assert telemetry["active_coder"] == "codex"
    assert telemetry["coder_sessions"] == {}
    assert telemetry["coder_statuses"] == {"codex": "NEEDS_MODIFICATION"}


def test_task_native_sessions_are_scoped_per_coder():
    telemetry = runner.initial_runtime()
    runner._record_task_session(telemetry, "D02-01", "codex-session", coder_id="codex")
    runner._record_task_session(telemetry, "D02-01", "agr-conversation", coder_id="agr")
    assert runner._resume_session_for(telemetry, "D02-01", coder_id="codex") == "codex-session"
    assert runner._resume_session_for(telemetry, "D02-01", coder_id="agr") == "agr-conversation"
    assert telemetry["coder_sessions"]["D02-01"] == {
        "codex": "codex-session",
        "agr": "agr-conversation",
    }


def test_legacy_task_session_migrates_to_codex_backend(tmp_path: Path):
    runtime = tmp_path / "runtime.json"
    runtime.write_text(json.dumps({
        "task_session_id": "legacy-session",
        "session_task_id": "D02-01",
        "task_sessions": {"D02-01": "legacy-session"},
    }))
    telemetry = runner.load_runtime(runtime)
    assert telemetry["coder_sessions"]["D02-01"]["codex"] == "legacy-session"
    assert runner._resume_session_for(telemetry, "D02-01", coder_id="codex") == "legacy-session"




def test_task_capsule_records_all_native_sessions_without_splitting_memory(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    production = state.load_project_production(project)
    task = state.find_task(production, "D01-030")
    telemetry = runner.initial_runtime()
    runner._record_task_session(telemetry, task.id, "codex-session", coder_id="codex")
    runner._record_task_session(telemetry, task.id, "agr-session", coder_id="agr")
    path = runner._write_task_capsule(repo, project, tmp_path / "runtime", task, telemetry)
    payload = json.loads(path.read_text())
    assert payload["coder_sessions"] == {"codex": "codex-session", "agr": "agr-session"}
    assert payload["task_id"] == task.id













def _typed_test_completion(task_id: str) -> dict:
    return {
        "kind": "VALIDATION", "task_id": task_id, "task_revision": 1,
        "task_digest": "0" * 64, "scope_ref": f"task://test/{task_id}",
        "evidence_ref": "test://runtime-pass", "evidence_sha256": "1" * 64,
        "implementation_ref": "test://implementation", "verdict": "PASS",
    }







def test_peer_assist_cache_prevents_duplicate_dispatch(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    task = state.find_task(state.load_project_production(project), "D01-030")
    capsule = tmp_path / "runtime/task-memory/D01-30.json"; capsule.parent.mkdir(parents=True); capsule.write_text('{"summary":"shared"}')
    projection = tmp_path / "runtime/memory/current-task.json"; projection.parent.mkdir(parents=True); projection.write_text('{"task_id":"D01-30"}')
    peer_root = tmp_path / "runtime/memory/main-coder-peer"; peer_root.mkdir(parents=True)
    key = runner._main_coder_peer_key(project, task, "x" * 64, "agr", "claude-opus-4-6-thinking", capsule, projection)
    (peer_root / f"{task.id}-{key}.accepted.json").write_text(json.dumps({"task_state_digest":"x" * 64,"authority":"NONE"}))
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("duplicate peer must not launch")))
    inflight = {}
    assert runner._launch_main_coder_peer_assist(
        repo, project, tmp_path / "runtime", task, "x" * 64,
        primary_coder="codex", peer_coder="agr",
        peer_route=routing.Route("claude-opus-4-6-thinking", "high", "antigravity"),
        capsule_path=capsule, projection_path=projection, inflight=inflight,
    ) is False


def test_primary_prompt_consumes_current_peer_assist_without_making_it_authority(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    production = state.load_project_production(project)
    task = state.find_task(production, "D01-030")
    capsule = tmp_path / "runtime/task-memory/D01-30.json"; capsule.parent.mkdir(parents=True); capsule.write_text('{"summary":"shared"}')
    peer = tmp_path / "runtime/memory/main-coder-peer/peer.accepted.json"; peer.parent.mkdir(parents=True); peer.write_text('{"authority":"NONE","result":{"status":"USEFUL"}}')
    prompt = runner._task_prompt(repo, production, task, runner.initial_runtime(), capsule, peer_assist_path=peer)
    assert f"MAIN_CODER_PEER_ASSIST: {peer}" in prompt
    assert "non-authoritative" in prompt.lower()
    assert "cannot complete, advance, reorder" in prompt.lower()








def test_production_status_exposes_main_coder_four_state_truth(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime = tmp_path / "runtime.json"
    now = datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc)
    telemetry = runner.initial_runtime()
    telemetry["heartbeat_at"] = now.isoformat()
    telemetry["active_coder"] = "codex"
    telemetry["coder_statuses"] = {"codex": "ACTIVE", "agr": "NEEDS_MODIFICATION"}
    telemetry["coder_status_detail"] = {"agr": "eligibility check failed"}
    runner.save_runtime(runtime, telemetry)
    monkeypatch.setattr(runner, "service_active", lambda: True)
    payload = runner.production_status(repo, project, runtime, now=now)
    assert payload["active_coder"] == "codex"
    assert payload["main_coders"] == {"codex": "ACTIVE", "agr": "NEEDS_MODIFICATION"}
    assert payload["main_coder_detail"]["agr"] == "eligibility check failed"










class _CommanderFakeStdin:
    def __init__(self):
        self.text = ""; self.closed = False
    def write(self, value):
        self.text += value
    def close(self):
        self.closed = True


class _CommanderFakeProcess:
    _next_pid = 50000
    def __init__(self, *, rc=None, stdout_handle=None, stdout_payload=None):
        type(self)._next_pid += 1
        self.pid = type(self)._next_pid
        self.stdin = _CommanderFakeStdin()
        self._rc = rc
        self.terminated = False
        if stdout_handle is not None and stdout_payload is not None:
            stdout_handle.write(stdout_payload); stdout_handle.flush()
    def poll(self): return self._rc
    def terminate(self): self.terminated = True; self._rc = -15


def _commander_projection_digest(capsule: Path, projection: Path) -> str:
    import hashlib
    capsule_data=json.loads(capsule.read_text())
    projection_data=json.loads(projection.read_text())
    context=runner.commander.bounded_context(capsule_data, projection_data)
    return hashlib.sha256(json.dumps(context,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


def _commander_fixture(tmp_path: Path):
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "ops/workstation").mkdir(parents=True)
    (repo / "ops/workstation/provider-registry.json").write_text(json.dumps({
        "schema":"minitz.provider_registry/v1",
        "providers":{"groq":{"required_env":["GROQ_API_KEY"],"default_model":"qwen"}},
        "routes":{"llm.fast":["groq"]},
    }))
    project = repo / "projects/game"; project.mkdir(parents=True)
    runtime = tmp_path / "runtime"; (runtime / "memory").mkdir(parents=True)
    capsule = runtime / "task-memory/T.json"; capsule.parent.mkdir(parents=True)
    capsule.write_text(json.dumps({"task_id":"T","task_class":"hard","title":"Task","summary":"Current state","evidence":["src/x.py"],"scope_ref":"task://minitz/T/1"}))
    projection = runtime / "memory/current-task.json"
    projection.write_text(json.dumps({"task_id":"T","task_memory":{"task_id":"T","summary":"Current state"},"failures":[],"source_refs":["src/x.py"],"capabilities":{}}))
    task = state.TaskRecord("T", "hard", "Task", "PENDING")
    return repo, project, runtime, capsule, projection, task


def test_commander_launch_is_nonblocking_and_writes_exact_thirty_lane_index(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq","cerebras","mistral"))
    monkeypatch.setattr(runner.commander, "build_resource_command", lambda provider, **_k: ["commander", provider])
    created=[]
    def popen(command, stdin=None, text=None, stdout=None, stderr=None, env=None, cwd=None, umask=None):
        proc=_CommanderFakeProcess(); created.append((command, proc)); return proc
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    inflight={}
    index = runner._launch_commander_assists(repo, project, runtime, task, "a"*64, capsule, projection, inflight)
    assert index == runtime / "memory/commander-fabric/current.json"
    assert len(inflight) == 3 and len(created) == 3
    assert {handle.requested_provider for handle in inflight.values()} == {"groq", "cerebras", "mistral"}
    assert all(handle.process.poll() is None for handle in inflight.values())
    assert all(handle.process.stdin.closed for handle in inflight.values())
    assert all("AUTHORITY: NONE" in handle.process.stdin.text for handle in inflight.values())
    payload=json.loads(index.read_text())
    assert payload["total_lanes"] == 30
    assert len(payload["lanes"]) == 30
    assert sum(row["status"] == "ACTIVE" and row["activity"] == "RUNNING" for row in payload["lanes"]) == 3
    assert sum(row["activity"] == "UNASSIGNED" for row in payload["lanes"]) == 27
    assert all(row["provider"] in {"groq", "cerebras", "mistral"} for row in payload["lanes"])
    assert {provider: sum(row["provider"] == provider for row in payload["lanes"]) for provider in ("groq","cerebras","mistral")} == {"groq":10,"cerebras":10,"mistral":10}



def test_commander_qualified_local_route_suppresses_paid_remote_candidates(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    registry={
        "schema":"minitz.provider_registry/v1",
        "providers":{
            "ollama-qwen":{"required_env":[],"default_model":"qwen3-coder-next:minitz","commander_structured_output":True},
            "groq":{"required_env":["GROQ_API_KEY"],"default_model":"qwen"},
        },
        "routes":{"llm.fast":["ollama-qwen","groq"]},
    }
    (repo/"ops/workstation/provider-registry.json").write_text(json.dumps(registry))
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    monkeypatch.setattr(runner, "_local_qwen_resident", lambda: True)
    monkeypatch.setenv("MINITZ_LOCAL_QWEN_PARALLEL", "2")
    monkeypatch.setattr(runner.local_capacity, "observe_local_capacity", lambda: {
        "ram_available_mib": 64000, "gpu_free_mib": 6800, "memory_pressure_full_avg10": 0.0,
    })
    monkeypatch.setattr(runner.commander, "build_resource_command", lambda provider, **_k: ["commander", provider])
    spawned=[]
    def popen(command, stdin=None, text=None, stdout=None, stderr=None, env=None, cwd=None, umask=None):
        proc=_CommanderFakeProcess(); spawned.append(command); return proc
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    inflight={}
    index=runner._launch_commander_assists(repo,project,runtime,task,"a"*64,capsule,projection,inflight)
    assert len(inflight)==2
    assert {handle.requested_provider for handle in inflight.values()}=={"ollama-qwen"}
    assert all("groq" not in command for command in spawned)
    payload=json.loads(index.read_text())
    assert payload["eligible_providers"]==["ollama-qwen"]
    assert payload["lanes"][0]["route_reason"]=="LOCAL_FIRST_WITH_CAPACITY"


def test_commander_qwen_offline_falls_back_without_task_mutation(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    registry={
        "schema":"minitz.provider_registry/v1",
        "providers":{
            "ollama-qwen":{"required_env":[],"default_model":"qwen3-coder-next:minitz"},
            "groq":{"required_env":["GROQ_API_KEY"],"default_model":"qwen"},
        },
        "routes":{"llm.fast":["ollama-qwen","groq"]},
    }
    (repo/"ops/workstation/provider-registry.json").write_text(json.dumps(registry))
    monkeypatch.setattr(runner, "_local_qwen_resident", lambda: False)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    monkeypatch.setattr(runner.local_capacity, "observe_local_capacity", lambda: {"ram_available_mib":64000,"gpu_free_mib":6000,"memory_pressure_full_avg10":0.0})
    monkeypatch.setattr(runner.commander, "build_resource_command", lambda provider, **_k: ["commander", provider])
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: _CommanderFakeProcess())
    before_task = task
    before_capsule = capsule.read_bytes()
    inflight={}
    index=runner._launch_commander_assists(repo,project,runtime,task,"a"*64,capsule,projection,inflight)
    assert inflight and {h.requested_provider for h in inflight.values()} == {"groq"}
    assert task == before_task
    assert capsule.read_bytes() == before_capsule
    payload=json.loads(index.read_text())
    assert payload["authority"] == "NONE" and payload["progression_authority"] is False

def test_commander_launch_with_zero_providers_never_blocks_or_spawns(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ())
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not spawn")))
    inflight={}
    index = runner._launch_commander_assists(repo, project, runtime, task, "a"*64, capsule, projection, inflight)
    assert inflight == {}
    payload=json.loads(index.read_text())
    assert payload["total_lanes"] == 30
    assert len(payload["lanes"]) == 30
    assert all(row["status"] == "OFFLINE" for row in payload["lanes"])


def test_commander_cached_accepted_result_suppresses_duplicate_lane_work(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    monkeypatch.setenv("MINITZ_COMMANDER_PROVIDER_MAX_INFLIGHT", "1")
    digest=_commander_projection_digest(capsule, projection)
    lane=runner.commander.commander_lanes()[0]
    key=runner.commander.commander_cache_key("minitz","T","a"*64,digest,lane.lane_id,lane.role,"groq")
    root=runtime/"memory/commander-fabric"; root.mkdir(parents=True,exist_ok=True)
    (root/f"{key}.accepted.json").write_text(json.dumps({"authority":"NONE","project_scope":"minitz","task_id":"T","task_state_digest":"a"*64,"projection_digest":digest,"lane_id":"CMD-01","role":"requirements","requested_provider":"groq","result":{"lane_id":"CMD-01","status":"USEFUL","summary":"cached","findings":[],"evidence_refs":[],"candidate_actions":[],"uncertainties":[]}}))
    spawned=[]
    def popen(command,stdin=None,text=None,stdout=None,stderr=None,env=None,cwd=None,umask=None):
        proc=_CommanderFakeProcess(); spawned.append(proc); return proc
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    inflight={}
    index=runner._launch_commander_assists(repo, project, runtime, task, "a"*64, capsule, projection, inflight)
    row=json.loads(index.read_text())["lanes"][0]
    assert row["activity"] == "USEFUL" and row["status"] == "ACTIVE"
    assert len(inflight) == 1 and len(spawned) == 1
    assert next(iter(inflight.values())).lane_id == "CMD-02"


def test_commander_collect_validates_and_persists_result_without_task_mutation(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    monkeypatch.setenv("MINITZ_REMOTE_COMMANDER_PROVIDER_MAX_INFLIGHT", "1")
    monkeypatch.setattr(runner.local_capacity, "observe_local_capacity", lambda: {"ram_available_mib":64000,"gpu_free_mib":6000,"memory_pressure_full_avg10":0.0})
    body={"lane_id":"CMD-01","status":"USEFUL","summary":"check overlap","findings":["overlap"],"evidence_refs":["src/x.py"],"candidate_actions":["test overlap"],"uncertainties":[]}
    envelope=json.dumps({"provider":"groq","model":"qwen","latency_ms":1,"text":json.dumps(body),"usage":{}})
    def popen(command, stdin=None, text=None, stdout=None, stderr=None, env=None, cwd=None, umask=None):
        return _CommanderFakeProcess(rc=0, stdout_handle=stdout, stdout_payload=envelope)
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    inflight={}
    index=runner._launch_commander_assists(repo, project, runtime, task, "a"*64, capsule, projection, inflight)
    assert len(inflight)==1
    handle=next(iter(inflight.values())); lease=handle.lease_path
    assert lease.exists()
    runner._collect_commander_assists(runtime, inflight)
    assert inflight == {} and not lease.exists() and handle.accepted_path.exists()
    accepted=json.loads(handle.accepted_path.read_text())
    assert accepted["authority"] == "NONE" and accepted["result"]["status"] == "USEFUL"
    row=json.loads(index.read_text())["lanes"][0]
    assert row["status"] == "ACTIVE" and row["activity"] == "USEFUL"


def test_commander_prompt_reference_is_non_authoritative_and_never_waits(tmp_path: Path, monkeypatch):
    task=state.TaskRecord("T","hard","Task","PENDING")
    production=state.ProductionState(tmp_path,"IN_PROGRESS","s","T",[state.SectionRecord("s","S","IN_PROGRESS",[task])],run_id="minitz-task-program")
    capsule=tmp_path/"capsule.json"; capsule.write_text('{}')
    index=tmp_path/"current.json"; index.write_text('{"authority":"NONE","total_lanes":30}')
    monkeypatch.setattr(runner, "_task_working_directory", lambda *_a: tmp_path)
    monkeypatch.setattr(runner, "_task_has_shared_continuity", lambda *_a: True)
    monkeypatch.setattr(runner.packets, "compile_resume_packet", lambda *_a: "BASE")
    monkeypatch.setattr(runner.execution_map, "task_context", lambda *_a: "")
    monkeypatch.setattr(runner.execution_style, "proven_execution_style_prompt", lambda: "")
    monkeypatch.setattr(runner, "_minitz_owner_direction", lambda *_a: "")
    monkeypatch.setattr(runner.main_coder, "shared_policy_paths", lambda *_a: ())
    prompt=runner._task_prompt(tmp_path,production,task,runner.initial_runtime(),capsule,commander_index_path=index)
    assert f"COMMANDER_FABRIC_INDEX: {index}" in prompt
    assert "AUTHORITY: NONE" in prompt
    assert "never wait" in prompt.lower()
    assert "cannot complete, advance, reorder, commit, publish, or mutate" in prompt


def test_terminate_commander_assists_terminates_only_owned_children_and_removes_leases(tmp_path: Path):
    lease=tmp_path/"lease.json"; lease.write_text('{}')
    proc=_CommanderFakeProcess(rc=None)
    handle=runner.CommanderHandle(
        key="k", lane_id="CMD-01", role="requirements", requested_provider="groq",
        project_scope="minitz", task_id="T", task_state_digest="a"*64, projection_digest="b"*64,
        process=proc, stdout_path=tmp_path/"out", stderr_path=tmp_path/"err",
        lease_path=lease, accepted_path=tmp_path/"a.json", rejected_path=tmp_path/"r.json",
    )
    inflight={"k":handle}
    runner._terminate_commander_assists(tmp_path, inflight)
    assert proc.terminated is True
    assert inflight == {} and not lease.exists()


def test_production_status_exposes_bounded_commander_fabric_summary(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime_root = tmp_path / "runtime"; runtime_root.mkdir()
    runtime = runtime_root / "runtime.json"
    now = datetime(2026, 9, 11, 0, 0, tzinfo=timezone.utc)
    telemetry = runner.initial_runtime(); telemetry["heartbeat_at"] = now.isoformat()
    runner.save_runtime(runtime, telemetry)
    root = runtime_root / "memory/commander-fabric"; root.mkdir(parents=True)
    project_scope = runner.commander.project_scope_id({}, project)
    (root / "current.json").write_text(json.dumps({
        "schema":"minitz.commander_fabric/v1","authority":"NONE","project_scope":project_scope,"task_id":"D01-30","total_lanes":30,
        "lanes":[
            {"lane_id":"CMD-01","role":"requirements","status":"ACTIVE","activity":"USEFUL","provider":"groq","summary":"PRIVATE","result_path":"/private/a"},
            {"lane_id":"CMD-02","role":"tests","status":"OUT_OF_CREDIT","activity":"REJECTED","provider":"mistral","result_path":"/private/b"},
        ],
    }))
    monkeypatch.setattr(runner, "service_active", lambda: True)
    payload=runner.production_status(repo, project, runtime, now=now)
    assert payload["commanders"]["total_lanes"] == 30
    assert payload["commanders"]["useful"] == 1
    assert "PRIVATE" not in json.dumps(payload["commanders"])
    assert "/private/" not in json.dumps(payload["commanders"])


def test_production_status_rejects_commander_index_without_exact_current_task_identity(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime_root=tmp_path/"runtime"; runtime_root.mkdir(); runtime=runtime_root/"runtime.json"
    now=datetime(2026,9,11,tzinfo=timezone.utc); telemetry=runner.initial_runtime(); telemetry["heartbeat_at"]=now.isoformat(); runner.save_runtime(runtime,telemetry)
    root=runtime_root/"memory/commander-fabric"; root.mkdir(parents=True)
    (root/"current.json").write_text(json.dumps({"authority":"NONE","task_id":"","total_lanes":30,"lanes":[{"lane_id":"CMD-01","role":"requirements","status":"ACTIVE","activity":"USEFUL","provider":"groq","summary":"STALE"}]}))
    monkeypatch.setattr(runner,"service_active",lambda:True)
    public=runner.production_status(repo,project,runtime,now=now)["commanders"]
    assert public["task_id"] == "D01-30"
    assert public["useful"] == 0 and public["active"] == 0
    assert "STALE" not in json.dumps(public)


def test_production_status_rejects_commander_index_from_other_project_scope(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    runtime_root = tmp_path / "runtime"; runtime_root.mkdir()
    runtime = runtime_root / "runtime.json"
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    telemetry = runner.initial_runtime(); telemetry["heartbeat_at"] = now.isoformat()
    runner.save_runtime(runtime, telemetry)
    root = runtime_root / "memory/commander-fabric"; root.mkdir(parents=True)
    (root / "current.json").write_text(json.dumps({
        "schema": "minitz.commander_fabric/v1", "authority": "NONE",
        "project_scope": "other-project", "task_id": "D01-30", "total_lanes": 30,
        "lanes": [{"lane_id": "CMD-01", "role": "requirements", "status": "ACTIVE",
                   "activity": "USEFUL", "provider": "groq", "summary": "CROSS_PROJECT"}],
    }))
    monkeypatch.setattr(runner, "service_active", lambda: True)
    public = runner.production_status(repo, project, runtime, now=now)["commanders"]
    assert public["task_id"] == "D01-30"
    assert public["useful"] == 0 and public["active"] == 0
    assert "CROSS_PROJECT" not in json.dumps(public)


def test_task_heartbeat_collects_then_refills_commander_assists(tmp_path: Path, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "_collect_commander_assists_nonblocking", lambda *a, **k: calls.append("collect"))
    monkeypatch.setattr(runner, "_prepare_commander_assists_nonblocking", lambda *a, **k: calls.append("prepare") or (tmp_path / "index.json"))

    result = runner._refresh_commander_assists_during_task(
        tmp_path, tmp_path, tmp_path, object(), "a" * 64, tmp_path / "capsule.json",
        tmp_path / "projection.json", {}, None,
    )

    assert calls == ["collect", "prepare"]
    assert result == tmp_path / "index.json"


def test_booster_autosync_launches_nonblocking_once_for_exact_program_revision(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    script = repo / "ops/local-ai/minitz_booster_sync.py"
    script.parent.mkdir(parents=True); script.write_text("print('ok')\n")
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MINITZ_BOOSTER_AUTOSYNC", "1")
    monkeypatch.setattr(runner.minitz, "program_identity", lambda: {"sha256": "a" * 64, "revision": 53})
    launches = []
    class Proc:
        pid = 12345
        returncode = None
        def poll(self): return None
    def popen(command, **kwargs):
        launches.append((command, kwargs))
        return Proc()
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    class Journal:
        def __init__(self): self.events=[]
        def emit(self, *args, **kwargs): self.events.append((args, kwargs))
    journal = Journal()

    handle = runner._maybe_start_booster_autosync(repo, runtime, None, set(), {}, journal)
    again = runner._maybe_start_booster_autosync(repo, runtime, handle, set(), {}, journal)

    assert handle is again
    assert handle.program_sha256 == "a" * 64
    assert len(launches) == 1
    assert launches[0][0][-2:] == ["sync", "--with-local-ai"]
    assert launches[0][1]["start_new_session"] is False


def test_booster_autosync_escalates_and_suppresses_repeated_same_program_failure(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    script = repo / "ops/local-ai/minitz_booster_sync.py"
    script.parent.mkdir(parents=True); script.write_text("print('ok')\n")
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MINITZ_BOOSTER_AUTOSYNC", "1")
    sha = "a" * 64
    monkeypatch.setattr(runner.minitz, "program_identity", lambda: {"sha256": sha, "revision": 53})
    class Proc:
        pid = 12345
        def poll(self): return 1
    class Journal:
        def __init__(self): self.events=[]
        def emit(self, *args, **kwargs): self.events.append((args, kwargs))
    journal=Journal(); completed=set(); retry_after={}; failures={}
    stderr=tmp_path/"boost.err"; stderr.write_text("transport failed")
    stdout=tmp_path/"boost.out"; stdout.write_text("")
    times=iter((100.0, 100.0, 1000.0, 1000.0, 5000.0, 5000.0))
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(times))
    for expected in (1,2,3):
        handle=runner.BoosterSyncHandle(sha, Proc(), stdout, stderr)
        assert runner._maybe_start_booster_autosync(repo,runtime,handle,completed,retry_after,journal,failure_counts=failures) is None
        assert failures[sha] == expected
    assert retry_after[sha] == float("inf")
    assert any(kwargs.get("status") == "SUPPRESSED" for _args,kwargs in journal.events)


def test_commander_provider_pool_supplements_partial_direct_pool_from_safe_status(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    registry = {
        "providers": {
            "ollama-qwen": {"default_model": "qwen"},
            "groq": {"default_model": "qwen"},
            "cerebras": {"default_model": "qwen"},
            "mistral": {"default_model": "mistral-small-latest"},
            "gemini": {"default_model": "gemini"},
        },
        "routes": {"llm.fast": ["ollama-qwen", "groq", "cerebras", "mistral", "gemini"]},
    }
    registry_path = repo / "ops/workstation/provider-registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry))
    monkeypatch.setattr(runner.commander, "eligible_external_providers", lambda *_a, **_k: ("groq", "cerebras", "mistral"))
    class Completed:
        returncode = 0
        stdout = json.dumps({"providers": [
            {"id":"groq","state":"CONFIGURED"},
            {"id":"cerebras","state":"CONFIGURED"},
            {"id":"mistral","state":"CONFIGURED"},
            {"id":"gemini","state":"CONFIGURED"},
        ]})
        stderr = ""
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: Completed())

    providers = runner._commander_external_provider_pool(repo, registry, limit=30)

    assert providers == ("groq", "cerebras", "mistral", "gemini")


def test_commander_provider_pool_uses_safe_wrapper_status_when_runner_env_has_no_api_keys(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    registry = {
        "providers": {
            "ollama-qwen": {"default_model": "qwen"},
            "groq": {"default_model": "qwen"},
            "cerebras": {"default_model": "qwen"},
            "mistral": {"default_model": "mistral-small-latest"},
            "gemini": {"default_model": "gemini"},
        },
        "routes": {"llm.fast": ["ollama-qwen", "groq", "cerebras", "mistral", "gemini"]},
    }
    registry_path = repo / "ops/workstation/provider-registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry))
    monkeypatch.setattr(runner.commander, "eligible_external_providers", lambda *_a, **_k: ())
    calls = []
    class Completed:
        returncode = 0
        stdout = json.dumps({"providers": [
            {"id":"groq","state":"CONFIGURED"},
            {"id":"cerebras","state":"CONFIGURED"},
            {"id":"mistral","state":"CONFIGURED"},
            {"id":"gemini","state":"NEEDS_MODIFICATION"},
        ]})
        stderr = ""
    def run(command, **kwargs):
        calls.append(command)
        return Completed()
    monkeypatch.setattr(runner.subprocess, "run", run)

    providers = runner._commander_external_provider_pool(repo, registry)

    assert providers == ("groq", "cerebras", "mistral")
    assert calls and "--registry" in calls[0]
    assert str(registry_path) in calls[0]


def test_commander_rejected_cache_retries_only_after_bounded_retry_after(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    monkeypatch.setenv("MINITZ_COMMANDER_PROVIDER_MAX_INFLIGHT", "1")
    digest=_commander_projection_digest(capsule, projection); lane=runner.commander.commander_lanes()[0]
    key=runner.commander.commander_cache_key("minitz","T","a"*64,digest,lane.lane_id,lane.role,"groq")
    root=runtime/"memory/commander-fabric"; root.mkdir(parents=True,exist_ok=True); rejected=root/f"{key}.rejected.json"
    future=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
    rejected.write_text(json.dumps({"authority":"NONE","project_scope":"minitz","task_id":"T","task_state_digest":"a"*64,"projection_digest":digest,"lane_id":"CMD-01","role":"requirements","provider":"groq","status":"OUT_OF_CREDIT","retry_after":future}))
    monkeypatch.setattr(runner.subprocess,"Popen",lambda *_a,**_k:(_ for _ in ()).throw(AssertionError("must suppress before retry_after")))
    inflight={}; runner._launch_commander_assists(repo,project,runtime,task,"a"*64,capsule,projection,inflight)
    assert inflight == {} and rejected.exists()
    past=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(); payload=json.loads(rejected.read_text()); payload["retry_after"]=past; rejected.write_text(json.dumps(payload))
    spawned=[]
    def popen(command,stdin=None,text=None,stdout=None,stderr=None,env=None,cwd=None,umask=None):
        proc=_CommanderFakeProcess(); spawned.append(proc); return proc
    monkeypatch.setattr(runner.subprocess,"Popen",popen)
    runner._launch_commander_assists(repo,project,runtime,task,"a"*64,capsule,projection,inflight)
    assert len(inflight) == 1 and spawned and not rejected.exists()


def test_commander_provider_never_ramps_above_safe_single_inflight_after_canary(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    monkeypatch.setenv("MINITZ_COMMANDER_PROVIDER_MAX_INFLIGHT", "10")
    digest=_commander_projection_digest(capsule, projection); lane=runner.commander.commander_lanes()[0]
    key=runner.commander.commander_cache_key("minitz","T","a"*64,digest,lane.lane_id,lane.role,"groq")
    root=runtime/"memory/commander-fabric"; root.mkdir(parents=True,exist_ok=True); accepted=root/f"{key}.accepted.json"
    result={"lane_id":"CMD-01","status":"USEFUL","summary":"canary pass","findings":[],"evidence_refs":[],"candidate_actions":[],"uncertainties":[]}
    accepted.write_text(json.dumps({"authority":"NONE","project_scope":"minitz","task_id":"T","task_state_digest":"a"*64,"projection_digest":digest,"lane_id":"CMD-01","role":"requirements","requested_provider":"groq","provider":"groq","result":result}))
    (root/"current.json").write_text(json.dumps({"schema":"minitz.commander_fabric/v1","authority":"NONE","project_scope":"minitz","task_id":"T","task_state_digest":"a"*64,"projection_digest":digest,"total_lanes":30,"lanes":[{"lane_id":"CMD-01","role":"requirements","status":"ACTIVE","activity":"USEFUL","provider":"groq","result_path":str(accepted)}]}))
    spawned=[]
    def popen(command,stdin=None,text=None,stdout=None,stderr=None,env=None,cwd=None,umask=None):
        proc=_CommanderFakeProcess(); spawned.append(proc); return proc
    monkeypatch.setattr(runner.subprocess,"Popen",popen)
    inflight={}; index=runner._launch_commander_assists(repo,project,runtime,task,"a"*64,capsule,projection,inflight)
    assert len(inflight) == 1 and len(spawned) == 1
    rows=json.loads(index.read_text())["lanes"]
    assert rows[0]["activity"] == "USEFUL"
    assert sum(row["activity"] == "RUNNING" for row in rows) == 1
    assert sum(row["activity"] == "UNASSIGNED" for row in rows) == 28
    assert all(row["provider"] == "groq" for row in rows)


def test_commander_provider_failure_backs_off_other_lanes_for_same_provider(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    monkeypatch.setenv("MINITZ_COMMANDER_PROVIDER_MAX_INFLIGHT", "10")
    digest=_commander_projection_digest(capsule, projection); lane=runner.commander.commander_lanes()[0]
    key=runner.commander.commander_cache_key("minitz","T","a"*64,digest,lane.lane_id,lane.role,"groq")
    root=runtime/"memory/commander-fabric"; root.mkdir(parents=True,exist_ok=True); rejected=root/f"{key}.rejected.json"
    retry=(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()
    rejected.write_text(json.dumps({"authority":"NONE","project_scope":"minitz","task_id":"T","task_state_digest":"a"*64,"projection_digest":digest,"lane_id":"CMD-01","role":"requirements","provider":"groq","status":"OUT_OF_CREDIT","retry_after":retry}))
    (root/"current.json").write_text(json.dumps({"schema":"minitz.commander_fabric/v1","authority":"NONE","project_scope":"minitz","task_id":"T","task_state_digest":"a"*64,"projection_digest":digest,"total_lanes":30,"lanes":[{"lane_id":"CMD-01","role":"requirements","status":"OUT_OF_CREDIT","activity":"REJECTED","provider":"groq","result_path":str(rejected)}]}))
    monkeypatch.setattr(runner.subprocess,"Popen",lambda *_a,**_k:(_ for _ in ()).throw(AssertionError("blocked provider must not spawn")))
    inflight={}; index=runner._launch_commander_assists(repo,project,runtime,task,"a"*64,capsule,projection,inflight)
    assert inflight == {}
    rows=json.loads(index.read_text())["lanes"]
    assert rows[0]["activity"] == "REJECTED"
    assert all(row["status"] == "OUT_OF_CREDIT" for row in rows[:10])
    assert all(row["activity"] in {"REJECTED","PROVIDER_BACKOFF"} for row in rows[:10])


def test_commander_prepare_failure_is_nonblocking_and_returns_existing_index(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MINITZ_COMMANDER_AUTOLAUNCH", "1")
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    index=runtime/"memory/commander-fabric/current.json"; index.parent.mkdir(parents=True,exist_ok=True); index.write_text('{"authority":"NONE"}')
    monkeypatch.setattr(runner,"_launch_commander_assists",lambda *_a,**_k:(_ for _ in ()).throw(OSError("assist index unavailable")))
    class Journal:
        def __init__(self): self.rows=[]
        def emit(self,*args,**kwargs): self.rows.append((args,kwargs))
    journal=Journal()
    result=runner._prepare_commander_assists_nonblocking(repo,project,runtime,task,"a"*64,capsule,projection,{},journal)
    assert result == index
    assert journal.rows and journal.rows[-1][0][0] == "commander.fabric_failed"
    assert journal.rows[-1][1]["status"] == "NEEDS_MODIFICATION"


def test_commander_cleanup_index_failure_never_escapes_or_preserves_owned_child(tmp_path: Path, monkeypatch):
    lease=tmp_path/"lease.json"; lease.write_text('{}'); proc=_CommanderFakeProcess(rc=None)
    handle=runner.CommanderHandle(key="k",lane_id="CMD-01",role="requirements",requested_provider="groq",project_scope="minitz",task_id="T",task_state_digest="a"*64,projection_digest="b"*64,process=proc,stdout_path=tmp_path/"o",stderr_path=tmp_path/"e",lease_path=lease,accepted_path=tmp_path/"a",rejected_path=tmp_path/"r")
    monkeypatch.setattr(runner,"_update_commander_index_lane",lambda *_a,**_k:(_ for _ in ()).throw(OSError("index read-only")))
    inflight={"k":handle}
    runner._terminate_commander_assists(tmp_path,inflight)
    assert proc.terminated and inflight == {} and not lease.exists()


def test_commander_collect_io_failure_is_nonblocking_and_cleans_owned_handles(tmp_path: Path, monkeypatch):
    lease=tmp_path/"lease.json"; lease.write_text('{}'); proc=_CommanderFakeProcess(rc=0)
    handle=runner.CommanderHandle(key="k",lane_id="CMD-01",role="requirements",requested_provider="groq",project_scope="minitz",task_id="T",task_state_digest="a"*64,projection_digest="b"*64,process=proc,stdout_path=tmp_path/"missing-out",stderr_path=tmp_path/"missing-err",lease_path=lease,accepted_path=tmp_path/"a",rejected_path=tmp_path/"r")
    monkeypatch.setattr(runner,"_tail",lambda *_a,**_k:(_ for _ in ()).throw(OSError("output unreadable")))
    class Journal:
        def __init__(self): self.rows=[]
        def emit(self,*args,**kwargs): self.rows.append((args,kwargs))
    journal=Journal(); inflight={"k":handle}
    runner._collect_commander_assists_nonblocking(tmp_path,inflight,journal)
    assert inflight == {} and not lease.exists()
    assert journal.rows and journal.rows[-1][0][0] == "commander.fabric_failed"
    assert journal.rows[-1][1]["status"] == "NEEDS_MODIFICATION"


def test_refresh_boost_fabric_derives_five_worker_current_state(tmp_path, monkeypatch):
    task = {
        "task_id": "T-BOOST", "revision": 2, "task_record_sha256": "a" * 64,
        "status": "PENDING", "task_class": "hard", "title": "Boost test",
        "write_scope": {"authority": "TASK_OWNED_ONLY", "allowed_paths": ["src/a.py", "ops/a.py", "tests/test_a.py", "website/a.js"]},
    }
    program = {
        "program_id": "TEST", "revision": 7, "tasks": [task],
        "current_execution": {"task_id": "T-BOOST", "task_revision": 2, "task_sha256": "a" * 64},
    }
    monkeypatch.setattr(runner.minitz, "load", lambda: program)
    current_path = runner._refresh_boost_fabric(tmp_path)
    current = json.loads(current_path.read_text(encoding="utf-8"))
    assert current["current_task_id"] == "T-BOOST"
    assert current["desired_boost_workers"] == 5
    assert current["runtime_state"] == "ACTIVE"
    assert len(current["boosts"]) == 5


def test_production_status_exposes_five_boost_control_summary(tmp_path, monkeypatch):
    task = state.TaskRecord("T-BOOST", "hard", "Boost task", "PENDING", (), "minitz")
    production = state.ProductionState(tmp_path, "IN_PROGRESS", "minitz", "T-BOOST", [state.SectionRecord("minitz", "MiniTZ", "IN_PROGRESS", [task])], run_id="minitz-task-program", priority_policy="MINITZ_TASK_PROGRAM")
    monkeypatch.setattr(runner.state, "load_project_production", lambda _root: production)
    monkeypatch.setattr(runner.state, "completed_count", lambda _production: 0)
    monkeypatch.setattr(runner, "load_runtime", lambda _path: {})
    monkeypatch.setattr(runner, "service_active", lambda: False)
    monkeypatch.setattr(runner.commander, "read_json", lambda _path: {"authority":"NONE","task_id":"T-BOOST","total_lanes":30,"lanes":[]})
    monkeypatch.setattr(runner.commander, "public_summary", lambda _index: {"schema":"minitz.commander_public_summary/v1","authority":"NONE","task_id":"T-BOOST","total_lanes":30,"active":0,"inflight":0,"useful":0,"rejected":0,"lanes":[]})
    boost_root = tmp_path / "memory/boost-fabric"
    boost_root.mkdir(parents=True)
    (boost_root / "current.json").write_text(json.dumps({
        "schema":"minitz.boost_fabric/v1","authority":"NONE","progression_authority":False,
        "runtime_state":"ACTIVE","current_task_id":"T-BOOST","total_commanders":30,
        "boosts":[{"boost_id":f"BOOST-{i:02d}","name":f"B{i}","status":"READY","commander_lanes":[f"CMD-{i:02d}"]} for i in range(1,6)]
    }))
    status = runner.production_status(tmp_path, tmp_path, tmp_path / "runtime.json")
    assert status["boosts"]["total_boosts"] == 5
    assert status["boosts"]["runtime_state"] == "ACTIVE"
    assert status["boosts"]["current_task_id"] == "T-BOOST"


def test_production_status_forces_stale_commander_lanes_offline_when_service_stopped(tmp_path, monkeypatch):
    task = state.TaskRecord("T", "hard", "Task", "PENDING", (), "minitz")
    production = state.ProductionState(tmp_path, "IN_PROGRESS", "minitz", "T", [state.SectionRecord("minitz", "MiniTZ", "IN_PROGRESS", [task])], run_id="minitz-task-program", priority_policy="MINITZ_TASK_PROGRAM")
    monkeypatch.setattr(runner.state, "load_project_production", lambda _root: production)
    monkeypatch.setattr(runner.state, "completed_count", lambda _production: 0)
    monkeypatch.setattr(runner, "load_runtime", lambda _path: {})
    monkeypatch.setattr(runner, "service_active", lambda: False)
    project_scope = runner.commander.project_scope_id({}, tmp_path)
    monkeypatch.setattr(runner.commander, "read_json", lambda _path: {"authority":"NONE","project_scope":project_scope,"task_id":"T","total_lanes":30,"lanes":[{"lane_id":"CMD-01","role":"requirements","status":"ACTIVE","activity":"RUNNING","provider":"groq"}]})
    status = runner.production_status(tmp_path, tmp_path, tmp_path / "runtime.json")
    assert status["status"] == "STOPPED"
    assert status["commanders"]["status"] == "OFFLINE"
    assert status["commanders"]["active"] == 0
    assert status["commanders"]["inflight"] == 0
    assert status["commanders"]["lanes"][0]["status"] == "OFFLINE"


def test_main_coder_commander_prepare_is_booster_managed_by_default(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    called = []
    monkeypatch.delenv("MINITZ_COMMANDER_AUTOLAUNCH", raising=False)
    monkeypatch.setattr(runner, "_launch_commander_assists", lambda *_a, **_k: called.append(True))
    index = runtime / "memory/commander-fabric/current.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps({"authority": "NONE", "task_id": task.id, "lanes": []}))
    result = runner._prepare_commander_assists_nonblocking(repo, project, runtime, task, "a"*64, capsule, projection, {}, None)
    assert result == index
    assert called == []


def test_commander_provider_health_backoff_survives_task_state_change(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    root = runtime / "memory/commander-fabric"; root.mkdir(parents=True, exist_ok=True)
    future = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()
    (root / "provider-health.json").write_text(json.dumps({
        "schema":"minitz.commander_provider_health/v1", "authority":"NONE",
        "progression_authority":False, "providers":{"groq":{
            "status":"OUT_OF_CREDIT", "retry_after":future, "consecutive_failures":3,
        }},
    }))
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("provider backoff must survive task-state change")))
    inflight = {}; index = runner._launch_commander_assists(repo, project, runtime, task, "b"*64, capsule, projection, inflight)
    assert inflight == {}
    rows = json.loads(index.read_text())["lanes"]
    assert rows[0]["status"] == "OUT_OF_CREDIT"
    assert rows[0]["activity"] == "PROVIDER_BACKOFF"


def test_commander_provider_health_escalates_repeated_rate_limit_backoff(tmp_path: Path):
    first = runner._record_commander_provider_failure(tmp_path, "groq", "OUT_OF_CREDIT", "HTTP_429 rate limit")
    second = runner._record_commander_provider_failure(tmp_path, "groq", "OUT_OF_CREDIT", "HTTP_429 rate limit")
    assert first["consecutive_failures"] == 1
    assert second["consecutive_failures"] == 2
    t1 = datetime.fromisoformat(str(first["retry_after"]).replace("Z", "+00:00"))
    t2 = datetime.fromisoformat(str(second["retry_after"]).replace("Z", "+00:00"))
    assert (t2 - datetime.now(timezone.utc)).total_seconds() > 100
    assert t2 > t1
    payload = json.loads((tmp_path / "memory/commander-fabric/provider-health.json").read_text())
    assert payload["authority"] == "NONE"
    assert payload["progression_authority"] is False
    assert "detail" not in payload["providers"]["groq"]


def test_local_qwen_is_not_promoted_when_codex_is_unavailable(tmp_path: Path):
    repo, project = write_repo_fixture(tmp_path)
    task = state.find_task(state.load_project_production(project), "D01-030")
    telemetry = runner.initial_runtime()
    telemetry["cooldowns"] = {"gpt-reserve": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
    catalog = {"qwen3-coder-next:minitz": {"local"}}
    coder_id, route, packet, peer = runner._select_main_task_route(
        task, catalog, telemetry, datetime.now(timezone.utc), repo, project
    )
    assert coder_id is None
    assert route is None
    assert packet is None
    assert telemetry["coder_statuses"]["codex"] == "OUT_OF_CREDIT"
    assert peer is None


def test_minitz_bounded_fallback_completion_reaches_existing_validation_authority():
    complete = runner.evidence.TaskResult("T", "COMPLETE", "validated", ("{}",))
    route = routing.Route("qwen3-coder-next:minitz", "none", "ollama")
    kept = runner._normalize_result_for_route(complete, route, allow_minitz_validated_completion=True)
    blocked = runner._normalize_result_for_route(complete, route, allow_minitz_validated_completion=False)
    assert kept.status == "COMPLETE"
    assert blocked.status == "COMPLETE"


def test_booster_handoff_refs_are_exact_task_scoped(tmp_path: Path):
    root = tmp_path / "boost-work-program"
    root.mkdir()
    wanted = root / "evidence/BOOST-02/UNIFY-07-handoff.json"
    wanted.parent.mkdir(parents=True)
    wanted.write_text('{"task_id":"UNIFY-07"}\n')
    other = root / "evidence/BOOST-03/UNIFY-06-handoff.json"
    other.parent.mkdir(parents=True)
    other.write_text('{"task_id":"UNIFY-06"}\n')
    (root / "BOOSTER_TASK_LIST.json").write_text(json.dumps({"items": [
        {"boost_id":"BOOST-02","task_id":"UNIFY-07","status":"HANDOFF_READY","handoff_ref":str(wanted)},
        {"boost_id":"BOOST-03","task_id":"UNIFY-06","status":"HANDOFF_READY","handoff_ref":str(other)},
        {"boost_id":"BOOST-04","task_id":"UNIFY-07","status":"QUEUED","handoff_ref":str(other)},
    ]}))
    assert runner._booster_handoff_refs_for_task(root / "BOOSTER_TASK_LIST.json", "UNIFY-07") == (wanted,)


def test_local_qwen_prompt_receives_validation_contract_and_exact_booster_handoff(tmp_path: Path, monkeypatch):
    digest = "5" * 64
    task = state.TaskRecord("UNIFY-07", "hard", "Failure learning", "PENDING", (
        "MINITZ_TASK_REVISION:3", f"MINITZ_TASK_SHA256:{digest}",
    ), "minitz")
    production = state.ProductionState(tmp_path, "IN_PROGRESS", "minitz", task.id,
        [state.SectionRecord("minitz", "MiniTZ", "IN_PROGRESS", [task])],
        run_id="minitz-task-program", priority_policy="MINITZ_TASK_PROGRAM")
    runtime = tmp_path / "runtime"; capsule = runtime / "task-memory/UNIFY-07.json"; capsule.parent.mkdir(parents=True)
    capsule.write_text(json.dumps({"task_id":"UNIFY-07"}))
    boost = runtime / "boost-work-program"; boost.mkdir()
    handoff = boost / "handoffs/BOOST-02/UNIFY-07.json"; handoff.parent.mkdir(parents=True); handoff.write_text('{}')
    (boost / "BOOSTER_TASK_LIST.json").write_text(json.dumps({"items":[{
        "canonical_task_id":"UNIFY-07","canonical_task_revision":3,"canonical_task_sha256":digest,
        "work_status":"HANDOFF_READY","evidence_refs":[str(handoff)]}]}))
    monkeypatch.setattr(runner, "_minitz_owner_direction", lambda *_a: "")
    monkeypatch.setattr(runner, "_minitz_owner_wake_context", lambda *_a: "")
    monkeypatch.setattr(runner, "_task_guidance_for", lambda *_a: None)
    monkeypatch.setattr(runner.main_coder, "shared_policy_paths", lambda *_a: ())
    monkeypatch.setattr(runner.execution_map, "task_context", lambda *_a: "")
    prompt = runner._task_prompt(tmp_path, production, task, runner.initial_runtime(), capsule,
        route=routing.Route("qwen3-coder-next:minitz", "none", "ollama"), coder_id="local-qwen")
    assert "MINITZ_PROGRESS_COMPLETION" in prompt
    assert "BOOSTER_EXACT_TASK_HANDOFFS" in prompt and str(handoff) in prompt
    assert "When the authorized task work is finished, return COMPLETE" in prompt


def _single_authority_runner_fixture(tmp_path: Path, monkeypatch, *, writer_id: str | None = None):
    repo = tmp_path / "repo"
    project = repo / "project"
    (repo / "docs/project-state").mkdir(parents=True)
    project.mkdir(parents=True)
    path = tmp_path / "TASK_PROGRAM.json"
    tasks = []
    for index, task_id in enumerate(("CLAIM-01", "CLAIM-02")):
        row = {
            "task_id": task_id,
            "revision": 1,
            "status": "PENDING",
            "title": task_id,
            "active_task_survival": True,
            "review_state": "VALUE_GATE_PASSED",
            "dependencies": [] if index == 0 else [{"dependency_type": "HARD", "task_ref": "CLAIM-01"}],
            "write_scope": {"authority": "TASK_OWNED_ONLY", "execution_root": str(repo.resolve()), "allowed_paths": [str(repo.resolve())]},
            "acceptance": ["writer claim is exact"],
        }
        row["task_record_sha256"] = runner.minitz.task_digest(row)
        tasks.append(row)
    program = {
        "schema": "minitz.living_task_program/v1",
        "program_id": "MINITZ_REBORN_SINGLE_TASK_PROGRAM",
        "single_transformation_lineage": True,
        "intended_final_task_program_count": 1,
        "task_program_authority": True,
        "production_execution_authority": True,
        "production_order_status_authority": True,
        "current_live_production_authority": str(path.resolve()),
        "dependency_types": list(runner.minitz.DEPENDENCY_TYPES),
        "revision": 1,
        "status": "ACTIVE_MINITZ_TASK_PROGRAM",
        "task_count": len(tasks),
        "tasks": tasks,
    }
    path.write_text(json.dumps(program, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setenv("MINITZ_TASK_PROGRAM_PATH", str(path))
    if writer_id is not None:
        runner.minitz.claim_task(
            "CLAIM-01", worker_id=writer_id, worker_role="PRIMARY_WRITER",
            write_authority=True, evidence=["fixture writer claim"], path=path,
        )
    task = state.resolve_current_task(repo, project)
    assert task is not None
    return repo, project, path, task


def test_minitz_production_runner_claims_unclaimed_current_task_before_write(tmp_path: Path, monkeypatch):
    repo, project, path, task = _single_authority_runner_fixture(tmp_path, monkeypatch)
    before = runner.minitz.load(path)
    claimed = runner._ensure_minitz_writer_claim(repo, project, task)
    assert claimed is not None
    after = runner.minitz.load(path)
    current = runner.minitz.current_task(after)
    assert current is not None
    assert after["revision"] == before["revision"] + 1
    assert current["status"] == "WORKING"
    assert current["workers"] == [{
        "worker_id": runner.MINITZ_PRODUCTION_WRITER_ID,
        "role": "PRIMARY_WRITER",
        "write_authority": True,
        "status": "WORKING",
        "claimed_at": current["workers"][0]["claimed_at"],
        "evidence": ["MiniTZ production runner has a viable execution route and is claiming the current task before write execution"],
    }]
    assert claimed.id == "CLAIM-01"
    assert "current_execution" not in json.loads(path.read_text(encoding="utf-8"))


def test_minitz_production_runner_reuses_its_existing_writer_claim(tmp_path: Path, monkeypatch):
    repo, project, path, task = _single_authority_runner_fixture(
        tmp_path, monkeypatch, writer_id=runner.MINITZ_PRODUCTION_WRITER_ID,
    )
    before = runner.minitz.program_identity(runner.minitz.load(path))
    claimed = runner._ensure_minitz_writer_claim(repo, project, task)
    after = runner.minitz.program_identity(runner.minitz.load(path))
    assert claimed is not None
    assert after == before


def test_minitz_production_runner_does_not_wait_on_existing_external_writer_claim(tmp_path: Path, monkeypatch):
    repo, project, path, task = _single_authority_runner_fixture(
        tmp_path, monkeypatch, writer_id="chatgpt:gpt-5.6-sol",
    )
    before = path.read_bytes()
    active = runner._ensure_minitz_writer_claim(repo, project, task)
    assert active is not None and active.id == task.id
    assert path.read_bytes() == before
    current = runner.minitz.current_task(runner.minitz.load(path))
    assert current is not None
    writers = [row for row in current["workers"] if row["write_authority"]]
    assert [row["worker_id"] for row in writers] == ["chatgpt:gpt-5.6-sol"]
    assert "WAITING_FOR_WRITER" not in Path(runner.__file__).read_text(encoding="utf-8")

def test_commander_runtime_index_is_five_operational_boost_packs(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ())
    index = runner._launch_commander_assists(repo, project, runtime, task, "a" * 64, capsule, projection, {})
    payload = json.loads(index.read_text())
    assert [row["boost_id"] for row in payload["boosts"]] == [f"BOOST-{i:02d}" for i in range(1, 6)]
    for pack in payload["boosts"]:
        assert len(pack["lanes"]) == 6
        assert [lane["work_mode"] for lane in pack["lanes"]] == ["WRITER", "WRITER", "READER", "READER", "READER", "VALIDATOR"]
        assert all(lane["boost_id"] == pack["boost_id"] for lane in pack["lanes"])





def test_commander_expired_cooldown_preserves_failure_streak(tmp_path):
    first = runner._record_commander_provider_failure(tmp_path, "mistral", "OUT_OF_CREDIT", "HTTP_429")
    path = tmp_path / "memory/commander-fabric/provider-health.json"
    payload = json.loads(path.read_text())
    payload["providers"]["mistral"]["retry_after"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    path.write_text(json.dumps(payload))
    assert runner._active_commander_provider_health(tmp_path) == {}
    second = runner._record_commander_provider_failure(tmp_path, "mistral", "OUT_OF_CREDIT", "HTTP_429")
    assert second["consecutive_failures"] == first["consecutive_failures"] + 1


def test_commander_resident_local_model_uses_runtime_parallelism(tmp_path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    path = repo / "ops/workstation/provider-registry.json"
    registry = json.loads(path.read_text())
    registry["providers"]["ollama-qwen"] = {"default_model":"qwen", "cost_class":"local_compute"}
    registry["routes"]["llm.fast"].insert(0, "ollama-qwen")
    path.write_text(json.dumps(registry))
    monkeypatch.setattr(runner, "_local_qwen_resident", lambda: True)
    monkeypatch.setenv("MINITZ_LOCAL_QWEN_PARALLEL", "2")
    monkeypatch.setattr(runner.local_capacity, "observe_local_capacity", lambda: {"ram_available_mib": 40000, "gpu_free_mib": 6800, "memory_pressure_full_avg10": 0})
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_a, **_k: _CommanderFakeProcess())
    inflight = {}
    runner._launch_commander_assists(repo, project, runtime, task, "a"*64, capsule, projection, inflight)
    providers = [handle.requested_provider for handle in inflight.values()]
    assert providers.count("ollama-qwen") == 2
    assert providers.count("groq") == 0


def test_commander_timestamp_only_refresh_reuses_inflight_work(tmp_path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_a, **_k: _CommanderFakeProcess())
    inflight = {}
    index = runner._launch_commander_assists(repo, project, runtime, task, "a"*64, capsule, projection, inflight)
    before = json.loads(index.read_text())["projection_digest"]
    changed = json.loads(projection.read_text()); changed["generated_at"] = "2099-01-01T00:00:00Z"
    projection.write_text(json.dumps(changed))
    runner._launch_commander_assists(repo, project, runtime, task, "a"*64, capsule, projection, inflight)
    assert json.loads(index.read_text())["projection_digest"] == before
    assert len(inflight) == 1


def test_working_task_without_worker_claim_gets_claim_for_completion(tmp_path, monkeypatch):
    repo, project, path, task = _single_authority_runner_fixture(tmp_path, monkeypatch)
    program = runner.minitz.load(path)
    row = runner.minitz.current_task(program)
    row["status"] = "WORKING"
    row["task_record_sha256"] = runner.minitz.task_digest(row)
    runner.minitz._atomic_write(path, program)
    task = state.resolve_current_task(repo, project)
    runner._ensure_minitz_writer_claim(repo, project, task)
    current = runner.minitz.current_task(runner.minitz.load(path))
    assert any(w.get("write_authority") and w.get("status") == "WORKING" for w in current.get("workers", []))


def test_local_qwen_residency_uses_api_readback_not_container_pid_namespace(monkeypatch):
    desired = "d" * 64
    class Response:
        def __init__(self, payload): self.payload = payload
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self): return json.dumps(self.payload).encode()
    def fake_urlopen(url, timeout=0):
        if str(url).endswith("/api/tags"):
            return Response({"models":[{"name":"qwen3-coder-next:minitz","digest":desired}]})
        return Response({"models":[{"name":"qwen3-coder-next:minitz","digest":desired,"size_vram":40601712066}]})
    monkeypatch.setattr(runner.Path, "glob", lambda *_a, **_k: [])
    monkeypatch.setattr(runner.urllib.request, "urlopen", fake_urlopen)
    assert runner._local_qwen_resident() is True


def test_local_qwen_residency_matches_minitz_alias_by_digest(monkeypatch):
    desired = "d" * 64
    class Response:
        def __init__(self, payload): self.payload=payload
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self): return json.dumps(self.payload).encode()
    def fake_urlopen(url, timeout=0):
        if str(url).endswith("/api/tags"):
            return Response({"models":[{"name":"qwen3-coder-next:minitz","digest":desired}]})
        return Response({"models":[{"name":"legacy-tag","digest":desired,"size_vram":40601712066}]})
    monkeypatch.setattr(runner.urllib.request, "urlopen", fake_urlopen)
    assert runner._local_qwen_resident() is True


def test_commander_inflight_prior_context_remains_visible_as_running(tmp_path: Path, monkeypatch):
    repo, project, runtime, capsule, projection, task = _commander_fixture(tmp_path)
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
    monkeypatch.setattr(runner, "_local_qwen_resident", lambda: False)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("existing inflight should suppress duplicate spawn")))
    lane=runner.commander.commander_lanes()[0]
    proc=_CommanderFakeProcess(rc=None)
    root=runtime/"memory/commander-fabric"; root.mkdir(parents=True,exist_ok=True)
    lease=root/"old.lease.json"; lease.write_text('{}')
    handle=runner.CommanderHandle(key="old",lane_id=lane.lane_id,role=lane.role,requested_provider="groq",project_scope="minitz",task_id="T",task_state_digest="a"*64,projection_digest="old-context",process=proc,stdout_path=root/"old.stdout",stderr_path=root/"old.stderr",lease_path=lease,accepted_path=root/"old.accepted",rejected_path=root/"old.rejected")
    inflight={"old":handle}
    index=runner._launch_commander_assists(repo,project,runtime,task,"a"*64,capsule,projection,inflight)
    row=json.loads(index.read_text())["lanes"][0]
    assert row["status"]=="ACTIVE" and row["activity"]=="RUNNING"
    assert row["provider"]=="groq"


def test_attempt_telemetry_separates_global_sequence_from_per_task_count(tmp_path: Path):
    telemetry = runner.initial_runtime()
    telemetry["attempt"] = 4394
    first = runner._attempt_paths(tmp_path, telemetry, "TASK-A-model", task_id="TASK-A")
    assert telemetry["execution_sequence"] == 4395
    assert telemetry["attempt"] == 1
    assert telemetry["task_attempt"] == 1
    assert telemetry["attempt_task_id"] == "TASK-A"
    assert first[0].name.startswith("4395-")
    runner._attempt_paths(tmp_path, telemetry, "TASK-A-model", task_id="TASK-A")
    assert telemetry["execution_sequence"] == 4396
    assert telemetry["task_attempt"] == 2
    runner._attempt_paths(tmp_path, telemetry, "TASK-B-model", task_id="TASK-B")
    assert telemetry["execution_sequence"] == 4397
    assert telemetry["task_attempt"] == 1


def _external_continue_result() -> object:
    failed = json.dumps({
        "kind": "DIAGNOSTIC", "criterion": "owner-authorized GitHub repository",
        "evidence_ref": "github://taghdisilabs-digital/MiniTZ", "verdict": "FAIL",
    })
    return runner.evidence.TaskResult("MINITZ-GITHUB-MAIN-01", "CONTINUE", "repository unavailable", (failed,))


def test_unchanged_external_failure_enters_persisted_condition_wait(monkeypatch):
    monkeypatch.setenv("MINITZ_EXTERNAL_BLOCKER_BASE_SECONDS", "60")
    telemetry = runner.initial_runtime()
    now = datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc)
    assert runner._record_external_condition_wait(telemetry, _external_continue_result(), "head-a", now=now)
    blocker = telemetry["stable_blocker"]
    assert telemetry["status"] == "WAITING_FOR_CONDITION"
    assert blocker["task_id"] == "MINITZ-GITHUB-MAIN-01"
    assert blocker["repeat_count"] == 1
    assert runner._external_condition_wait_remaining(
        telemetry, "MINITZ-GITHUB-MAIN-01", "head-a", now=now + timedelta(seconds=10)
    ) == pytest.approx(50.0)


def test_external_condition_wait_invalidates_on_source_change(monkeypatch):
    monkeypatch.setenv("MINITZ_EXTERNAL_BLOCKER_BASE_SECONDS", "60")
    telemetry = runner.initial_runtime()
    now = datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc)
    runner._record_external_condition_wait(telemetry, _external_continue_result(), "head-a", now=now)
    assert runner._external_condition_wait_remaining(
        telemetry, "MINITZ-GITHUB-MAIN-01", "head-b", now=now + timedelta(seconds=1)
    ) == 0.0
    assert telemetry.get("stable_blocker") is None


def test_restart_seeds_wait_from_persisted_external_continue_without_new_attempt(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MINITZ_EXTERNAL_BLOCKER_BASE_SECONDS", "60")
    telemetry = runner.initial_runtime()
    failed = json.loads(_external_continue_result().evidence[0])
    failed.update({"task_revision": 2, "task_digest": "a" * 64, "scope_ref": "task://minitz/MINITZ-GITHUB-MAIN-01/2"})
    telemetry["last_result"] = {
        "task_id": "MINITZ-GITHUB-MAIN-01", "status": "CONTINUE",
        "summary": "same external blocker", "evidence": [json.dumps(failed)],
    }
    attempts = tmp_path / "attempts"; attempts.mkdir()
    for number in range(4364, 4395):
        (attempts / f"{number}-MINITZ-GITHUB-MAIN-01-gpt.stdout.log").write_text("")
    now = datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc)
    assert runner._seed_external_condition_wait_from_last_result(
        telemetry, "MINITZ-GITHUB-MAIN-01", "source-a", tmp_path, now=now
    )
    assert telemetry["stable_blocker"]["repeat_count"] == 31
    assert telemetry["status"] == "WAITING_FOR_CONDITION"
    assert telemetry["execution_sequence"] == 0


def test_graceful_stop_signal_exits_before_new_model_work(tmp_path: Path, monkeypatch):
    repo, project = write_repo_fixture(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    runtime_root = tmp_path / "runtime"; runtime_root.mkdir(parents=True)
    runner._shutdown_requested.clear(); runner._request_graceful_shutdown(None, None)
    monkeypatch.setattr(runner.routing, "discover_catalog", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("model must not run after stop signal")))
    try:
        assert runner.run_production(repo, project, runtime_root, heartbeat_interval=0.01) == 0
    finally:
        runner._shutdown_requested.clear()
    runtime = runner.load_runtime(runtime_root / "runtime.json")
    assert runtime["child_pid"] is None
    assert "PAUSED" not in str(runtime.get("status") or "")
    assert "MAINTENANCE" not in str(runtime.get("status") or "")
