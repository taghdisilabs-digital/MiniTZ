import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/minitz_codex_account_pool.py"


def pool():
    assert MODULE.is_file(), "MiniTZ Codex account pool is not implemented"
    spec = importlib.util.spec_from_file_location("minitz_codex_account_pool", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_account_pool_supports_arbitrary_account_count_and_shared_assets(tmp_path):
    mod = pool()
    shared = tmp_path / "shared"
    shared.mkdir()
    for name in ("cache", "tmp", "plugins", "skills"):
        (shared / name).mkdir()
    for name in ("AGENTS.md", "models_cache.json", "config.toml"):
        (shared / name).write_text(name + "\n", encoding="utf-8")
    registry = tmp_path / "accounts.json"
    for account_id in ("a1", "a2", "a3", "a4"):
        home = tmp_path / "accounts" / account_id
        mod.add_account(registry, account_id, home, shared_root=shared)
        (home / "auth.json").write_text("{}\n", encoding="utf-8")
    data = json.loads(registry.read_text(encoding="utf-8"))
    assert [row["account_id"] for row in data["accounts"]] == ["a1", "a2", "a3", "a4"]
    for row in data["accounts"]:
        home = Path(row["home"])
        assert (home / "AGENTS.md").resolve() == (shared / "AGENTS.md").resolve()
        assert (home / "cache").resolve() == (shared / "cache").resolve()
        assert (home / "config.toml").resolve() == (shared / "config.toml").resolve()


def test_select_next_account_skips_disabled_and_cooling_accounts(tmp_path):
    mod = pool()
    now = datetime(2026, 9, 12, 1, 0, tzinfo=timezone.utc)
    registry = {
        "accounts": [
            {"account_id": "a", "home": str(tmp_path / "a"), "enabled": True},
            {"account_id": "b", "home": str(tmp_path / "b"), "enabled": False},
            {"account_id": "c", "home": str(tmp_path / "c"), "enabled": True},
        ]
    }
    for account in ("a", "b", "c"):
        home = tmp_path / account; home.mkdir(); (home / "auth.json").write_text("{}")
    state = {"active_account": "a", "cooldowns": {"c": "2026-09-12T02:00:00+00:00"}}
    assert mod.select_next_account(registry, state, "a", now=now) is None
    state["cooldowns"] = {}
    assert mod.select_next_account(registry, state, "a", now=now)["account_id"] == "c"


def test_resume_command_becomes_fresh_exec_after_account_switch():
    mod = pool()
    args = ["--search", "exec", "resume", "--json", "-o", "/tmp/result.json", "session-123", "-"]
    converted = mod.fresh_exec_args(args)
    assert converted == ["--search", "exec", "--json", "-o", "/tmp/result.json", "-"]


def test_passive_low_remaining_signal_is_detected_without_quota_probe():
    mod = pool()
    assert mod.passive_low_remaining("weekly limit remaining 8%", threshold=10)
    assert mod.passive_low_remaining("8% remaining in weekly limit", threshold=10)
    assert not mod.passive_low_remaining("weekly limit remaining 42%", threshold=10)
    assert mod.passive_low_remaining("You are approaching your usage limit", threshold=10)


def test_switch_checkpoint_binds_shared_minitz_state(tmp_path, monkeypatch):
    mod = pool()
    runtime = tmp_path / "runtime"; runtime.mkdir()
    (runtime / "runtime.json").write_text(json.dumps({"task_id": "TASK-1", "attempt": 7, "task_session_id": "native-old"}) + "\n")
    (runtime / "task-memory").mkdir(); (runtime / "memory").mkdir(); (runtime / "recovery").mkdir()
    (runtime / "task-memory/TASK-1.json").write_text('{"task_id":"TASK-1","summary":"shared"}\n')
    (runtime / "memory/current-task.json").write_text('{"task_id":"TASK-1"}\n')
    (runtime / "memory/compacted-memory.json").write_text('{"schema":"memory"}\n')
    program = tmp_path / "TASK_PROGRAM.json"
    program.write_text(json.dumps({"revision": 12, "tasks": [{"task_id":"TASK-1","status":"WORKING"}]}) + "\n")
    monkeypatch.setenv("MINITZ_TASK_PROGRAM_PATH", str(program))
    receipt = mod.write_switch_checkpoint(runtime, "a", "b", reason="USAGE_LIMIT")
    assert receipt["task_id"] == "TASK-1"
    assert receipt["from_account"] == "a" and receipt["to_account"] == "b"
    assert receipt["resume_strategy"] == "FRESH_CODEX_SESSION_FROM_SHARED_MINITZ_CHECKPOINT"
    assert receipt["task_capsule_sha256"]
    assert receipt["current_task_projection_sha256"]
    assert receipt["compacted_memory_sha256"]
    assert receipt["task_program_sha256"]
    assert (runtime / "recovery/codex-account-switch-current.json").is_file()


def test_production_service_and_installer_use_account_pool_router():
    unit = (ROOT / "ops/local-ai/minitz-production.service").read_text(encoding="utf-8")
    installer = (ROOT / "ops/local-ai/install-minitz-ai.sh").read_text(encoding="utf-8")
    assert "Environment=MINITZ_CODEX_BIN=/usr/local/bin/minitz-codex-router" in unit
    assert '"$SOURCE_DIR/minitz_codex_account_pool.py"' in installer
    assert '/usr/local/bin/minitz-codex-router' in installer
    assert '/usr/local/bin/minitz-codex-account' in installer


def test_router_rotates_accounts_checkpoints_and_drops_foreign_native_resume(tmp_path):
    import os
    import subprocess
    mod = pool()
    runtime = tmp_path / "runtime"; (runtime / "task-memory").mkdir(parents=True); (runtime / "memory").mkdir()
    (runtime / "runtime.json").write_text(json.dumps({"task_id":"TASK-1","attempt":9,"task_session_id":"old-native"}) + "\n")
    (runtime / "task-memory/TASK-1.json").write_text('{"task_id":"TASK-1"}\n')
    (runtime / "memory/current-task.json").write_text('{"task_id":"TASK-1"}\n')
    (runtime / "memory/compacted-memory.json").write_text('{"schema":"memory"}\n')
    program = tmp_path / "TASK_PROGRAM.json"
    program.write_text(json.dumps({"revision":3,"tasks":[{"task_id":"TASK-1","status":"WORKING"}]}) + "\n")
    registry = tmp_path / "accounts.json"; state = tmp_path / "state.json"
    shared = tmp_path / "shared"; shared.mkdir()
    for name in ("cache", "tmp", "plugins", "skills"): (shared / name).mkdir()
    for name in ("AGENTS.md", "models_cache.json", "config.toml"): (shared / name).write_text("shared\n")
    for account_id in ("a", "b"):
        home = tmp_path / "accounts" / account_id
        mod.add_account(registry, account_id, home, shared_root=shared)
        (home / "auth.json").write_text("{}\n")
    state.write_text(json.dumps({"schema":mod.STATE_SCHEMA,"active_account":"a","cooldowns":{}}) + "\n")
    fake = tmp_path / "fake-codex.py"
    log = tmp_path / "fake.log"
    fake.write_text(
        "#!/usr/bin/env python3\nimport json,os,sys\n"
        "home=os.environ['CODEX_HOME']; args=sys.argv[1:]\n"
        "open(os.environ['FAKE_LOG'],'a').write(json.dumps({'home':home,'args':args})+'\\n')\n"
        "if home.endswith('/a'):\n print(\"You've hit your usage limit. try again at Sep 12, 2026 9:41 PM UTC\", file=sys.stderr); sys.exit(1)\n"
        "print(json.dumps({'type':'thread.started','thread_id':'new-thread'}))\n"
        "sys.exit(0)\n"
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env.update({
        "MINITZ_CODEX_PRODUCTION_RUNTIME_ROOT": str(runtime),
        "MINITZ_CODEX_ACCOUNT_REGISTRY": str(registry),
        "MINITZ_CODEX_ACCOUNT_STATE": str(state),
        "MINITZ_CODEX_REAL_BIN": str(fake),
        "MINITZ_TASK_PROGRAM_PATH": str(program),
        "FAKE_LOG": str(log),
    })
    router = ROOT / "ops/local-ai/minitz-codex-router"
    completed = subprocess.run(
        [str(router), "--search", "exec", "resume", "--json", "-o", str(runtime / "attempt.result.json"), "old-session", "-"],
        input="RESUME_EXISTING_TASK_SESSION\n", text=True, capture_output=True, env=env, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows[0]["home"].endswith("/a") and "resume" in rows[0]["args"]
    assert rows[1]["home"].endswith("/b")
    assert "resume" not in rows[1]["args"] and "old-session" not in rows[1]["args"]
    checkpoint = json.loads((runtime / "recovery/codex-account-switch-current.json").read_text())
    assert (checkpoint["from_account"], checkpoint["to_account"], checkpoint["task_id"]) == ("a", "b", "TASK-1")
    assert json.loads(state.read_text())["active_account"] == "b"



def test_router_reports_cooling_capacity_separately_from_missing_auth(tmp_path, monkeypatch, capsys):
    mod = pool()
    home = tmp_path / "accounts" / "mahdi"; home.mkdir(parents=True)
    (home / "auth.json").write_text("{}\n", encoding="utf-8")
    registry = tmp_path / "accounts.json"
    registry.write_text(json.dumps({"schema":mod.SCHEMA,"accounts":[{"account_id":"mahdi","home":str(home),"enabled":True}]}) + "\n")
    state = tmp_path / "pool-state.json"
    retry_at = "2026-09-15T08:40:00+00:00"
    state.write_text(json.dumps({"schema":mod.STATE_SCHEMA,"active_account":"mahdi","cooldowns":{"mahdi":retry_at}}) + "\n")
    monkeypatch.setenv("MINITZ_CODEX_ACCOUNT_REGISTRY", str(registry))
    monkeypatch.setenv("MINITZ_CODEX_ACCOUNT_STATE", str(state))
    monkeypatch.setattr(mod, "_now", lambda: datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc))
    assert mod.router_main(["exec"]) == 78
    err = capsys.readouterr().err
    assert "CAPACITY_UNAVAILABLE" in err
    assert retry_at in err
    assert "no enabled logged-in account" not in err


def test_account_exec_streams_before_process_exit(tmp_path, monkeypatch):
    import io
    import threading
    import types
    mod = pool()
    ready = threading.Event()
    release = tmp_path / "release"

    class Probe(io.BytesIO):
        def write(self, value):
            size = super().write(value)
            if b"thread.started" in self.getvalue():
                ready.set()
            return size

    out, err = Probe(), io.BytesIO()
    monkeypatch.setattr(mod, "sys", types.SimpleNamespace(
        stdout=types.SimpleNamespace(buffer=out),
        stderr=types.SimpleNamespace(buffer=err),
    ))
    fake = tmp_path / "fake-codex"
    fake.write_text(
        "#!/usr/bin/env python3\nimport os,sys,time\n"
        "sys.stdin.buffer.read()\n"
        "print('{\"type\":\"thread.started\",\"thread_id\":\"live-session\"}', flush=True)\n"
        "print('live stderr', file=sys.stderr, flush=True)\n"
        f"end=time.monotonic()+5\nwhile not os.path.exists({str(release)!r}) and time.monotonic()<end: time.sleep(0.01)\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("MINITZ_CODEX_REAL_BIN", str(fake))
    results, failures = [], []
    def invoke():
        try:
            results.append(mod._run_account({"home": str(tmp_path)}, ["exec", "--json"], b"bounded task\n"))
        except BaseException as exc:
            failures.append(exc)
    worker = threading.Thread(target=invoke)
    worker.start()
    try:
        assert ready.wait(2), "Codex events were buffered instead of streamed while the task was running"
        assert worker.is_alive(), "test must observe streaming before process exit"
    finally:
        release.touch()
        worker.join(7)
    assert not worker.is_alive() and not failures
    assert results[0].returncode == 0
    assert out.getvalue().count(b"thread.started") == 1
    assert b"live stderr" in err.getvalue()
    mod._forward_account_output(results[0])
    assert out.getvalue().count(b"thread.started") == 1, "router replayed an already streamed event"
