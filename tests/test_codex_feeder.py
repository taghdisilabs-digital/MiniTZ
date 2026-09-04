from __future__ import annotations

import importlib.util
import json
import os
import subprocess
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


def _write_games_authority(root: Path) -> None:
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "DEMO_01_QUEUE.md").write_text(
        "# Demo\nCurrent task: D01-008\nLast checkpoint: D01-007 COMPLETE\n\n"
        "- [x] D01-001 | Resolve truth | COMPLETE_ALREADY | observed\n"
        "- [x] D01-002 | Verify authority | COMPLETE | observed\n"
        "- [ ] D01-003 | Build project | PENDING | build\n"
        "- [ ] D01-008 | Current build task | PENDING | build\n",
        encoding="utf-8",
    )
    (docs / "IMPLEMENTATION_SEQUENCE.md").write_text(
        "## Stage 1 — First playable vertical slice\n"
        "## Stage 2 — Open-world and systemic expansion\n"
        "## Stage 3 — Production rendering, animation, VFX and audio quality\n"
        "## Stage 4 — Content system multiplication\n"
        "## Stage 5 — UI, settings, localization and accessibility\n"
        "## Stage 6 — Cinematic and presentation integration\n"
        "## Stage 7 — Performance, stability and scalability qualification\n"
        "## Stage 8 — Delivery, update and release-candidate qualification\n",
        encoding="utf-8",
    )


def _single_stage_production(tmp_path: Path, *, task: bool = False) -> Path:
    path = tmp_path / "production.json"
    tasks = [{"id": "S2-001", "class": "simple", "title": "Implement streaming continuity", "status": "PENDING", "evidence": []}] if task else []
    feeder.save_production(path, {
        "schema_version": 2,
        "run_id": "game",
        "goal": "complete game",
        "project_root": str(tmp_path / "games"),
        "status": "READY",
        "current_section": "stage2",
        "current_task": "S2-001" if task else None,
        "active_model": None,
        "active_reasoning": None,
        "cooldowns": {},
        "attempt_seq": 0,
        "last_result": None,
        "sections": [
            {"id": "demo01", "title": "Demo", "source": "demo", "status": "COMPLETE", "tasks": [], "evidence": []},
            {"id": "stage2", "title": "Open-world expansion", "source": "docs/IMPLEMENTATION_SEQUENCE.md", "status": "IN_PROGRESS" if task else "PENDING", "tasks": tasks, "evidence": []},
            {"id": "stage3", "title": "Rendering", "source": "docs/IMPLEMENTATION_SEQUENCE.md", "status": "COMPLETE_ALREADY", "tasks": [], "evidence": []},
        ],
        "updated_at": "2026-09-04T00:00:00+00:00",
    })
    return path


def test_hard_and_deep_memory_use_astra_ultra():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    for task_class in ("hard", "deep_memory", "hard_creation"):
        assert feeder.select_route(task_class, catalog(), {}, now) == feeder.Route("gpt-6-astra", "ultra")


def test_creation_never_routes_low_reasoning():
    route = feeder.select_route("creation", catalog(), {}, datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc))
    assert feeder.reasoning_rank(route.reasoning) >= feeder.reasoning_rank("high")


def test_simple_prefers_luna_and_cooldown_falls_back():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    assert feeder.select_route("simple", catalog(), {}, now).model == "gpt-5.6-luna"
    route = feeder.select_route("simple", catalog(), {"gpt-5.6-luna": "2026-09-04T13:00:00+00:00"}, now)
    assert route.model != "gpt-5.6-luna"


def test_codex_command_never_contains_usage_or_reset_actions(tmp_path: Path):
    cmd = feeder.build_codex_command(feeder.Route("gpt-5.6-luna", "medium"), tmp_path / "schema.json", tmp_path / "out.json", Path("/root"))
    joined = " ".join(cmd).lower()
    assert "/usage" not in joined and "reset" not in joined
    assert cmd.index("--search") < cmd.index("exec")
    assert 'model_reasoning_effort="medium"' in cmd


def test_usage_limit_parser_uses_observed_retry():
    observed = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    retry = feeder.limit_retry_at("usage_limit_exceeded: try again at Sep 7, 2026 5:05 PM UTC", observed)
    assert retry > observed


def test_one_production_file_contains_sections_and_imports_demo_progress(tmp_path: Path):
    project = tmp_path / "games"
    _write_games_authority(project)
    production_path = tmp_path / "production.json"
    feeder.write_games_production(production_path, project_root=project)
    production = feeder.load_production(production_path)
    assert [s["id"] for s in production["sections"]] == ["demo01", "stage2", "stage3", "stage4", "stage5", "stage6", "stage7", "stage8"]
    assert feeder.find_task(production, "D01-001")["status"] == "COMPLETE_ALREADY"
    assert feeder.find_task(production, "D01-002")["status"] == "COMPLETE"
    assert production["current_section"] == "demo01"
    assert production["current_task"] == "D01-003"
    assert not (tmp_path / "state.json").exists()


def test_completed_task_is_embedded_and_not_requeued(tmp_path: Path):
    project = tmp_path / "games"
    _write_games_authority(project)
    path = tmp_path / "production.json"
    feeder.write_games_production(path, project_root=project)
    production = feeder.load_production(path)
    feeder.mark_production_complete(production, "D01-003", "COMPLETE", "gpt-5.6-luna", "medium", ["build pass"])
    feeder.save_production(path, production)
    restored = feeder.load_production(path)
    assert feeder.find_task(restored, "D01-003")["status"] == "COMPLETE"
    assert feeder.next_production_task(restored).id == "D01-008"


def test_sync_demo_progress_never_downgrades_completed_work(tmp_path: Path):
    project = tmp_path / "games"
    _write_games_authority(project)
    path = tmp_path / "production.json"
    feeder.write_games_production(path, project_root=project)
    production = feeder.load_production(path)
    feeder.find_task(production, "D01-003")["status"] = "COMPLETE"
    feeder.save_production(path, production)
    feeder.sync_demo_progress(path)
    assert feeder.find_task(feeder.load_production(path), "D01-003")["status"] == "COMPLETE"


def test_section_plan_appends_inside_same_section_without_duplicates(tmp_path: Path):
    path = _single_stage_production(tmp_path)
    production = feeder.load_production(path)
    plan = {"section_id": "stage2", "complete": False, "summary": "planned", "evidence": ["sequence"], "tasks": [
        {"class": "hard", "title": "Implement world streaming continuity"},
        {"class": "creation", "title": "Create readable streamed-region transition"},
    ]}
    feeder.apply_section_plan(production, "stage2", plan)
    feeder.apply_section_plan(production, "stage2", {**plan, "tasks": [plan["tasks"][0]]})
    stage2 = next(s for s in production["sections"] if s["id"] == "stage2")
    assert [t["id"] for t in stage2["tasks"]] == ["S2-001", "S2-002"]
    assert all(t["status"] == "PENDING" for t in stage2["tasks"])


def test_section_prompt_is_bounded_and_non_overlapping(tmp_path: Path):
    production = feeder.load_production(_single_stage_production(tmp_path))
    section = next(s for s in production["sections"] if s["id"] == "stage2")
    prompt = feeder.build_section_prompt(production, section, audit=False)
    assert "20 to 50" in prompt and "non-overlapping" in prompt
    assert "stage2" in prompt and "stage3" not in prompt
    assert len(prompt.encode()) < 6000


def test_section_plan_schema_bounds_tasks_and_classes():
    schema = feeder.section_plan_schema()
    tasks = schema["properties"]["tasks"]
    assert tasks["maxItems"] == 50
    assert set(tasks["items"]["properties"]["class"]["enum"]) == set(feeder._ROUTE_PROFILES)


def test_task_prompt_contains_only_current_task(tmp_path: Path):
    production = feeder.load_production(_single_stage_production(tmp_path, task=True))
    task = feeder.next_production_task(production)
    prompt = feeder.build_production_task_prompt(production, task)
    assert "S2-001" in prompt
    assert "stage3" not in prompt
    assert len(prompt.encode()) < 5000


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
            raise AssertionError("second feeder acquired active run lock")
    finally:
        first.release()


def test_result_schema_only_allows_progress_or_real_stop_states():
    assert feeder.result_schema()["properties"]["status"]["enum"] == ["COMPLETE", "COMPLETE_ALREADY", "CONTINUE", "EXTERNAL_DEPENDENCY", "OWNER_DECISION"]


def test_run_production_plans_executes_and_audits_same_section(tmp_path: Path, monkeypatch):
    production_path = _single_stage_production(tmp_path)
    fake = tmp_path / "codex"
    counter = tmp_path / "plan-count"
    fake.write_text(
        "#!/usr/bin/env python3\nimport json,os,pathlib,sys\na=sys.argv[1:]\n"
        "if a[:2]==['debug','models']:\n print(json.dumps({'models':[{'slug':'gpt-6-astra','supported_reasoning_levels':[{'effort':'ultra'}]},{'slug':'gpt-5.6-luna','supported_reasoning_levels':[{'effort':'medium'},{'effort':'high'},{'effort':'max'}]}]}));sys.exit(0)\n"
        "out=pathlib.Path(a[a.index('-o')+1]);schema=pathlib.Path(a[a.index('--output-schema')+1]).name\n"
        "if schema=='section-plan-schema.json':\n p=pathlib.Path(os.environ['PLAN_COUNT']);n=int(p.read_text()) if p.exists() else 0;p.write_text(str(n+1));result={'section_id':'stage2','complete':False,'summary':'planned','evidence':['sequence'],'tasks':[{'class':'simple','title':'Implement streaming continuity'}]} if n==0 else {'section_id':'stage2','complete':True,'summary':'verified','evidence':['runtime evidence'],'tasks':[]}\n"
        "else: result={'task_id':'S2-001','status':'COMPLETE','summary':'done','evidence':['test pass']}\n"
        "out.write_text(json.dumps(result));sys.exit(0)\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setenv("BIELLA_CODEX_BIN", str(fake))
    monkeypatch.setenv("PLAN_COUNT", str(counter))
    assert feeder.run_production(production_path, runtime_root=tmp_path / "runtime") == 0
    production = feeder.load_production(production_path)
    stage2 = next(s for s in production["sections"] if s["id"] == "stage2")
    assert stage2["status"] == "COMPLETE"
    assert stage2["tasks"][0]["status"] == "COMPLETE"
    assert production["status"] == "COMPLETE"
    assert not (tmp_path / "state.json").exists()


def test_run_production_falls_back_after_observed_luna_limit(tmp_path: Path, monkeypatch):
    production_path = _single_stage_production(tmp_path, task=True)
    fake = tmp_path / "codex"
    marker = tmp_path / "luna-hit"
    fake.write_text(
        "#!/usr/bin/env python3\nimport json,os,pathlib,sys\na=sys.argv[1:]\n"
        "if a[:2]==['debug','models']:\n print(json.dumps({'models':[{'slug':'gpt-5.6-luna','supported_reasoning_levels':[{'effort':'medium'}]},{'slug':'gpt-5.6-terra','supported_reasoning_levels':[{'effort':'medium'},{'effort':'ultra'}]}]}));sys.exit(0)\n"
        "out=pathlib.Path(a[a.index('-o')+1]);schema=pathlib.Path(a[a.index('--output-schema')+1]).name;model=a[a.index('-m')+1]\n"
        "marker=pathlib.Path(os.environ['FAKE_MARKER'])\n"
        "if schema!='section-plan-schema.json' and model=='gpt-5.6-luna' and not marker.exists(): marker.write_text('1');print('usage_limit_exceeded',file=sys.stderr);sys.exit(1)\n"
        "result={'section_id':'stage2','complete':True,'summary':'verified','evidence':['runtime'],'tasks':[]} if schema=='section-plan-schema.json' else {'task_id':'S2-001','status':'COMPLETE','summary':'done','evidence':['build pass']}\n"
        "out.write_text(json.dumps(result));sys.exit(0)\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setenv("BIELLA_CODEX_BIN", str(fake))
    monkeypatch.setenv("FAKE_MARKER", str(marker))
    assert feeder.run_production(production_path, runtime_root=tmp_path / "runtime") == 0
    production = feeder.load_production(production_path)
    task = feeder.find_task(production, "S2-001")
    assert task["status"] == "COMPLETE"
    assert task["model"] == "gpt-5.6-terra"
    assert "gpt-5.6-luna" in production["cooldowns"]


def test_cli_uses_one_canonical_production_file_and_no_queue_surface(tmp_path: Path):
    project = tmp_path / "games"
    _write_games_authority(project)
    production = tmp_path / "games-production.json"
    env = os.environ.copy()
    env["BIELLA_GAMES_PRODUCTION_FILE"] = str(production)
    env["BIELLA_GAMES_PROJECT_ROOT"] = str(project)
    init = subprocess.run([sys.executable, str(MODULE_PATH), "init"], env=env, text=True, capture_output=True, check=False)
    assert init.returncode == 0, init.stderr
    status = subprocess.run([sys.executable, str(MODULE_PATH), "status"], env=env, text=True, capture_output=True, check=False)
    payload = json.loads(status.stdout)
    assert payload["run_id"] == "biella-games-production"
    assert payload["current_section"] == "demo01"
    help_result = subprocess.run([sys.executable, str(MODULE_PATH), "--help"], env=env, text=True, capture_output=True, check=False)
    assert "init-demo01" not in help_result.stdout and "--queue" not in help_result.stdout
    assert "init" in help_result.stdout and "sync" in help_result.stdout


def test_init_existing_production_preserves_completed_work(tmp_path: Path):
    project = tmp_path / "games"
    _write_games_authority(project)
    path = tmp_path / "games-production.json"
    feeder.write_games_production(path, project_root=project)
    production = feeder.load_production(path)
    feeder.find_task(production, "D01-003")["status"] = "COMPLETE"
    feeder.save_production(path, production)
    feeder.init_production(path, project_root=project)
    assert feeder.find_task(feeder.load_production(path), "D01-003")["status"] == "COMPLETE"
