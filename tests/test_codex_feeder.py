from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ops" / "local-ai" / "biella_codex_feeder.py"
spec = importlib.util.spec_from_file_location("biella_codex_feeder", MODULE_PATH)
assert spec and spec.loader
feeder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = feeder
spec.loader.exec_module(feeder)


def catalog():
    return {
        "gpt-6-astra": {"low", "medium", "high", "xhigh", "max", "ultra"},
        "gpt-5.6-luna": {"low", "medium", "high", "xhigh", "max"},
        "gpt-5.6-sol": {"low", "medium", "high", "xhigh", "max", "ultra"},
        "gpt-5.6-terra": {"low", "medium", "high", "xhigh", "max", "ultra"},
        "gpt-5.5": {"low", "medium", "high", "xhigh"},
    }


def test_hard_and_deep_memory_use_astra_ultra():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    for task_class in ("hard", "deep_memory", "hard_creation"):
        route = feeder.select_route(task_class, catalog(), {}, now)
        assert route.model == "gpt-6-astra"
        assert route.reasoning == "ultra"


def test_creation_never_routes_low_reasoning():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    route = feeder.select_route("creation", catalog(), {}, now)
    assert feeder.reasoning_rank(route.reasoning) >= feeder.reasoning_rank("high")


def test_simple_prefers_luna_and_observed_cooldown_falls_back():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    first = feeder.select_route("simple", catalog(), {}, now)
    assert first.model == "gpt-5.6-luna"
    assert first.reasoning == "medium"
    cooldowns = {"gpt-5.6-luna": "2026-09-04T13:00:00+00:00"}
    second = feeder.select_route("simple", catalog(), cooldowns, now)
    assert second.model != "gpt-5.6-luna"


def test_usage_limit_parser_marks_only_observed_model():
    observed = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    retry = feeder.limit_retry_at(
        "usage_limit_exceeded: try again at Sep 7, 2026 5:05 PM UTC", observed
    )
    assert retry > observed


def test_codex_command_never_contains_usage_or_reset_actions(tmp_path: Path):
    route = feeder.Route("gpt-5.6-luna", "medium")
    cmd = feeder.build_codex_command(route, tmp_path / "schema.json", tmp_path / "out.json", Path("/root"))
    joined = " ".join(cmd).lower()
    assert "/usage" not in joined
    assert "reset" not in joined
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    assert 'model_reasoning_effort="medium"' in cmd


def sample_queue(tmp_path: Path):
    path = tmp_path / "queue.json"
    path.write_text(
        '{"schema_version":1,"run_id":"demo","goal":"finish demo","project_root":"/root/biella/repos/biella-games","tasks":['
        '{"id":"D01-001","class":"deep_memory","title":"resolve truth"},'
        '{"id":"D01-002","class":"simple","title":"build project"},'
        '{"id":"D01-003","class":"creation","title":"create arena"}'
        ']}',
        encoding="utf-8",
    )
    return feeder.load_queue(path)


def test_resume_skips_completed_task(tmp_path: Path):
    queue = sample_queue(tmp_path)
    state_path = tmp_path / "state.json"
    state = feeder.initial_state(queue)
    feeder.mark_complete(state, "D01-001", "COMPLETE", "gpt-6-astra", "ultra")
    feeder.save_state(state_path, state)
    restored = feeder.load_state(state_path, queue)
    assert feeder.next_task(queue, restored).id == "D01-002"
    assert restored["completed"] == ["D01-001"]


def test_limit_failure_cools_only_rejected_model_and_keeps_task(tmp_path: Path):
    queue = sample_queue(tmp_path)
    state = feeder.initial_state(queue)
    task = feeder.next_task(queue, state)
    observed = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    feeder.record_limit_failure(
        state,
        task,
        feeder.Route("gpt-6-astra", "ultra"),
        "usage_limit_exceeded",
        observed,
    )
    assert state["current_task"] == "D01-001"
    assert "gpt-6-astra" in state["cooldowns"]
    assert "gpt-5.6-luna" not in state["cooldowns"]
    assert state["completed"] == []


def test_single_flight_lock_rejects_second_holder(tmp_path: Path):
    lock_path = tmp_path / "run.lock"
    first = feeder.RunLock(lock_path)
    first.acquire()
    try:
        second = feeder.RunLock(lock_path)
        try:
            second.acquire()
        except feeder.AlreadyRunning:
            pass
        else:
            raise AssertionError("second feeder acquired active run lock")
    finally:
        first.release()


def test_task_prompt_contains_only_current_task_not_full_queue(tmp_path: Path):
    queue = sample_queue(tmp_path)
    state = feeder.initial_state(queue)
    task = feeder.next_task(queue, state)
    prompt = feeder.build_task_prompt(queue, task, state)
    assert "D01-001" in prompt
    assert "resolve truth" in prompt
    assert "D01-002" not in prompt
    assert "D01-003" not in prompt
    assert len(prompt.encode()) < 5000


def test_result_schema_only_allows_progress_or_real_stop_states():
    schema = feeder.result_schema()
    statuses = schema["properties"]["status"]["enum"]
    assert statuses == ["COMPLETE", "COMPLETE_ALREADY", "CONTINUE", "EXTERNAL_DEPENDENCY", "OWNER_DECISION"]


def test_demo01_queue_is_exactly_50_compact_contiguous_tasks(tmp_path: Path):
    path = tmp_path / "queue.json"
    feeder.write_demo01_queue(path)
    queue = feeder.load_queue(path)
    assert len(queue.tasks) == 50
    assert [task.id for task in queue.tasks] == [f"D01-{i:03d}" for i in range(1, 51)]
    assert path.stat().st_size < 12000


def test_demo01_hard_memory_and_creation_classes_obey_reasoning_policy(tmp_path: Path):
    path = tmp_path / "queue.json"
    feeder.write_demo01_queue(path)
    queue = feeder.load_queue(path)
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    for task in queue.tasks:
        route = feeder.select_route(task.task_class, catalog(), {}, now)
        if task.task_class in {"hard", "deep_memory", "hard_creation"}:
            assert route == feeder.Route("gpt-6-astra", "ultra")
        if task.task_class in {"creation", "hard_creation"}:
            assert feeder.reasoning_rank(route.reasoning) >= feeder.reasoning_rank("high")


def test_complete_result_advances_state(tmp_path: Path):
    queue = sample_queue(tmp_path)
    state = feeder.initial_state(queue)
    task = feeder.next_task(queue, state)
    action = feeder.apply_agent_result(
        state,
        task,
        feeder.Route("gpt-6-astra", "ultra"),
        {"task_id": task.id, "status": "COMPLETE", "summary": "done", "evidence": ["runtime pass"]},
        datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc),
    )
    assert action == "ADVANCE"
    assert state["completed"] == [task.id]


def test_continue_result_preserves_same_task_and_checkpoint(tmp_path: Path):
    queue = sample_queue(tmp_path)
    state = feeder.initial_state(queue)
    task = feeder.next_task(queue, state)
    action = feeder.apply_agent_result(
        state,
        task,
        feeder.Route("gpt-6-astra", "ultra"),
        {"task_id": task.id, "status": "CONTINUE", "summary": "repaired build", "evidence": ["compile progressed"]},
        datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc),
    )
    assert action == "RETRY_TASK"
    assert state["current_task"] == task.id
    assert state["completed"] == []
    assert state["last_result"]["summary"] == "repaired build"


def test_real_external_dependency_pauses_without_marking_complete(tmp_path: Path):
    queue = sample_queue(tmp_path)
    state = feeder.initial_state(queue)
    task = feeder.next_task(queue, state)
    action = feeder.apply_agent_result(
        state,
        task,
        feeder.Route("gpt-6-astra", "ultra"),
        {"task_id": task.id, "status": "EXTERNAL_DEPENDENCY", "summary": "external dependency", "evidence": []},
        datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc),
    )
    assert action == "PAUSE"
    assert state["status"] == "EXTERNAL_DEPENDENCY"
    assert state["completed"] == []


def test_run_queue_falls_back_after_observed_usage_limit(tmp_path: Path, monkeypatch):
    queue_path = tmp_path / "queue.json"
    queue_path.write_text(
        '{"schema_version":1,"run_id":"demo","goal":"finish demo","project_root":"/root/biella/repos/biella-games","tasks":['
        '{"id":"D01-001","class":"simple","title":"build project"}]}'
    )
    fake = tmp_path / "codex"
    marker = tmp_path / "luna-hit"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2]==['debug','models']:\n"
        " print(json.dumps({'models':["
        "{'slug':'gpt-5.6-luna','supported_reasoning_levels':[{'effort':'medium'},{'effort':'high'},{'effort':'max'}]},"
        "{'slug':'gpt-5.6-terra','supported_reasoning_levels':[{'effort':'medium'},{'effort':'high'},{'effort':'xhigh'},{'effort':'ultra'}]}]})); sys.exit(0)\n"
        "model=a[a.index('-m')+1]; out=pathlib.Path(a[a.index('-o')+1])\n"
        "marker=pathlib.Path(os.environ['FAKE_MARKER'])\n"
        "if model=='gpt-5.6-luna' and not marker.exists():\n"
        " marker.write_text('1'); print('usage_limit_exceeded', file=sys.stderr); sys.exit(1)\n"
        "out.write_text(json.dumps({'task_id':'D01-001','status':'COMPLETE','summary':'done','evidence':['build pass']})); sys.exit(0)\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("BIELLA_CODEX_BIN", str(fake))
    monkeypatch.setenv("FAKE_MARKER", str(marker))
    runtime = tmp_path / "runtime"
    rc = feeder.run_queue(queue_path, runtime_root=runtime)
    assert rc == 0
    queue = feeder.load_queue(queue_path)
    state = feeder.load_state(queue_path.parent / "state.json", queue)
    assert state["status"] == "COMPLETE"
    assert state["completed"] == ["D01-001"]
    assert "gpt-5.6-luna" in state["cooldowns"]
    assert state["last_result"]["model"] == "gpt-5.6-terra"


def test_cli_init_demo01_and_status(tmp_path: Path):
    import subprocess
    import sys

    queue_path = tmp_path / "run" / "queue.json"
    init = subprocess.run(
        [sys.executable, str(MODULE_PATH), "init-demo01", "--queue", str(queue_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    assert queue_path.exists()
    status = subprocess.run(
        [sys.executable, str(MODULE_PATH), "status", "--queue", str(queue_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    payload = __import__("json").loads(status.stdout)
    assert payload["run_id"] == "demo01-50"
    assert payload["completed"] == 0
    assert payload["total"] == 50
    assert payload["status"] == "READY"
