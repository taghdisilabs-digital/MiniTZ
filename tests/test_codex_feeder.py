from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ops/local-ai/biella_codex_feeder.py"
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


def write_project(root: Path, *, stage2_task: bool = False) -> Path:
    docs = root / "docs"
    docs.mkdir(parents=True)
    stage2_status = "IN_PROGRESS" if stage2_task else "PENDING_UNPLANNED"
    stage2_line = "- [ ] S2-001 | simple | Implement streaming continuity | PENDING | runtime evidence\n" if stage2_task else ""
    (docs / "PRODUCTION.md").write_text(
        "# Biella Games Production\n\nStatus: `IN_PROGRESS`\nCurrent section: `stage2`\nCurrent task: `S2-001`\n\n"
        "## Section: demo01 | Demo | COMPLETE\n\n"
        "- [x] D01-001 | deep_memory | Resolve truth | COMPLETE | observed\n\n"
        f"## Section: stage2 | Open world | {stage2_status}\n\n{stage2_line}\n"
        "## Section: stage3 | Rendering | COMPLETE_ALREADY\n",
        encoding="utf-8",
    )
    feeder.sync_project_metadata(root)
    return root


def test_hard_and_deep_memory_use_astra_ultra():
    now = datetime(2026, 9, 5, tzinfo=timezone.utc)
    for task_class in ("hard", "deep_memory", "hard_creation"):
        assert feeder.select_route(task_class, catalog(), {}, now) == feeder.Route("gpt-6-astra", "ultra")


def test_creation_never_routes_low_reasoning():
    route = feeder.select_route("creation", catalog(), {}, datetime(2026, 9, 5, tzinfo=timezone.utc))
    assert feeder.reasoning_rank(route.reasoning) >= feeder.reasoning_rank("high")


def test_simple_prefers_luna_and_cooldown_falls_back():
    now = datetime(2026, 9, 5, tzinfo=timezone.utc)
    assert feeder.select_route("simple", catalog(), {}, now).model == "gpt-5.6-luna"
    route = feeder.select_route("simple", catalog(), {"gpt-5.6-luna": "2026-09-05T01:00:00+00:00"}, now)
    assert route.model != "gpt-5.6-luna"


def test_codex_command_never_contains_usage_or_reset(tmp_path: Path):
    cmd = feeder.build_codex_command(feeder.Route("gpt-5.6-luna", "medium"), tmp_path / "schema", tmp_path / "out", Path("/root"))
    joined = " ".join(cmd).lower()
    assert "/usage" not in joined and "reset" not in joined
    assert cmd.index("--search") < cmd.index("exec")


def test_usage_limit_parser_uses_observed_retry():
    observed = datetime(2026, 9, 5, tzinfo=timezone.utc)
    assert feeder.limit_retry_at("usage_limit_exceeded: try again at Sep 7, 2026 5:05 PM UTC", observed) > observed


def test_section_plan_appends_into_same_project_file(tmp_path: Path):
    project = write_project(tmp_path / "games")
    feeder.apply_section_plan_to_project(project, "stage2", {
        "section_id": "stage2", "complete": False, "summary": "planned", "evidence": ["sequence"],
        "tasks": [{"class": "hard", "title": "Implement world streaming"}, {"class": "creation", "title": "Create readable transition"}],
    })
    state = feeder.load_project_production(project)
    section = next(s for s in state["sections"] if s["id"] == "stage2")
    assert [t["id"] for t in section["tasks"]] == ["S2-001", "S2-002"]
    assert state["current_task"] == "S2-001"
    assert not list(tmp_path.rglob("games-production.json"))


def test_task_completion_updates_markdown_and_advances(tmp_path: Path):
    project = write_project(tmp_path / "games", stage2_task=True)
    feeder.mark_project_task_complete(project, "S2-001", "COMPLETE", ["runtime pass"])
    state = feeder.load_project_production(project)
    assert feeder.find_task(state, "S2-001")["status"] == "COMPLETE"
    assert state["current_section"] == "stage2" and state["current_task"] is None


def test_single_flight_lock_rejects_second_holder(tmp_path: Path):
    first = feeder.RunLock(tmp_path / "run.lock")
    first.acquire()
    try:
        second = feeder.RunLock(tmp_path / "run.lock")
        try:
            second.acquire()
        except feeder.AlreadyRunning:
            pass
        else:
            raise AssertionError("second feeder acquired lock")
    finally:
        first.release()


def test_run_plans_executes_and_audits_same_markdown_section(tmp_path: Path, monkeypatch):
    project = write_project(tmp_path / "games")
    fake = tmp_path / "codex"
    count = tmp_path / "plan-count"
    fake.write_text(
        "#!/usr/bin/env python3\nimport json,os,pathlib,sys\na=sys.argv[1:]\n"
        "if a[:2]==['debug','models']:\n print(json.dumps({'models':[{'slug':'gpt-6-astra','supported_reasoning_levels':[{'effort':'ultra'}]},{'slug':'gpt-5.6-luna','supported_reasoning_levels':[{'effort':'medium'}]}]}));sys.exit(0)\n"
        "out=pathlib.Path(a[a.index('-o')+1]);schema=pathlib.Path(a[a.index('--output-schema')+1]).name\n"
        "if schema=='section-plan-schema.json':\n p=pathlib.Path(os.environ['PLAN_COUNT']);n=int(p.read_text()) if p.exists() else 0;p.write_text(str(n+1));result={'section_id':'stage2','complete':False,'summary':'planned','evidence':['sequence'],'tasks':[{'class':'simple','title':'Implement streaming continuity'}]} if n==0 else {'section_id':'stage2','complete':True,'summary':'verified','evidence':['runtime'],'tasks':[]}\n"
        "else: result={'task_id':'S2-001','status':'COMPLETE','summary':'done','evidence':['pass']}\n"
        "out.write_text(json.dumps(result));sys.exit(0)\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("BIELLA_CODEX_BIN", str(fake)); monkeypatch.setenv("PLAN_COUNT", str(count))
    assert feeder.run_production(project, runtime_root=tmp_path / "runtime") == 0
    state = feeder.load_project_production(project)
    assert next(s for s in state["sections"] if s["id"] == "stage2")["status"] == "COMPLETE"
    assert feeder.find_task(state, "S2-001")["status"] == "COMPLETE"


def test_run_falls_back_after_observed_luna_limit(tmp_path: Path, monkeypatch):
    project = write_project(tmp_path / "games", stage2_task=True)
    fake = tmp_path / "codex"; marker = tmp_path / "luna-hit"
    fake.write_text(
        "#!/usr/bin/env python3\nimport json,os,pathlib,sys\na=sys.argv[1:]\n"
        "if a[:2]==['debug','models']:\n print(json.dumps({'models':[{'slug':'gpt-5.6-luna','supported_reasoning_levels':[{'effort':'medium'}]},{'slug':'gpt-5.6-terra','supported_reasoning_levels':[{'effort':'medium'},{'effort':'ultra'}]},{'slug':'gpt-6-astra','supported_reasoning_levels':[{'effort':'ultra'}]}]}));sys.exit(0)\n"
        "out=pathlib.Path(a[a.index('-o')+1]);schema=pathlib.Path(a[a.index('--output-schema')+1]).name;model=a[a.index('-m')+1];marker=pathlib.Path(os.environ['FAKE_MARKER'])\n"
        "if schema!='section-plan-schema.json' and model=='gpt-5.6-luna' and not marker.exists(): marker.write_text('1');print('usage_limit_exceeded',file=sys.stderr);sys.exit(1)\n"
        "result={'section_id':'stage2','complete':True,'summary':'verified','evidence':['runtime'],'tasks':[]} if schema=='section-plan-schema.json' else {'task_id':'S2-001','status':'COMPLETE','summary':'done','evidence':['pass']}\n"
        "out.write_text(json.dumps(result));sys.exit(0)\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("BIELLA_CODEX_BIN", str(fake)); monkeypatch.setenv("FAKE_MARKER", str(marker))
    runtime = tmp_path / "runtime"
    assert feeder.run_production(project, runtime_root=runtime) == 0
    state = feeder.load_project_production(project)
    assert feeder.find_task(state, "S2-001")["status"] == "COMPLETE"
    telemetry = feeder.load_runtime_state(runtime / "runtime.json")
    assert "gpt-5.6-luna" in telemetry["cooldowns"]


def test_cli_has_no_queue_or_production_file_surface(tmp_path: Path):
    project = write_project(tmp_path / "games", stage2_task=True)
    env = os.environ.copy(); env["BIELLA_GAMES_PROJECT_ROOT"] = str(project); env["BIELLA_CODEX_FEED_RUNTIME_ROOT"] = str(tmp_path / "runtime")
    status = subprocess.run([sys.executable, str(MODULE_PATH), "status"], env=env, text=True, capture_output=True, check=False)
    assert status.returncode == 0, status.stderr
    payload = json.loads(status.stdout)
    assert payload["current_task"] == "S2-001"
    help_result = subprocess.run([sys.executable, str(MODULE_PATH), "--help"], env=env, text=True, capture_output=True)
    assert "--queue" not in help_result.stdout and "games-production.json" not in help_result.stdout
