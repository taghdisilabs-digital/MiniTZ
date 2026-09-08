from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))
MODULE = LOCAL_AI / "biella_production_state.py"
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
    assert resolved.id == "D01-30"
    assert resolved.task_class == "hard"


def test_completed_project_task_repairs_stale_active_pointer(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-029", project_id="D01-030")
    resolved = state.resolve_current_task(repo, project)
    assert resolved.id == "D01-30"
    active = state.load_active_task(repo)
    assert active.id == "D01-30"


def test_mark_complete_advances_project_and_active_task(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    state.mark_task_complete(repo, project, "D01-030", "COMPLETE", ["runtime pass"])
    production = state.load_project_production(project)
    assert state.find_task(production, "D01-030").status == "COMPLETE"
    assert production.current_task == "D01-31"
    assert state.load_active_task(repo).id == "D01-31"


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
    assert resolved.id == "D01-30"
    assert "feeder:" not in p03.read_text()
    assert "feeder:" not in p04.read_text()
    assert "runner:" in p03.read_text()
    assert "runner:" in p04.read_text()


def test_active_task_durable_state_has_no_execution_started(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    task = state.resolve_current_task(repo, project)
    state.write_active_task(repo, task, predecessor="D01-029")
    assert "execution_started:" not in (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").read_text()


def test_resolve_migrates_execution_started_out_of_durable_state(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    p03 = repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md"
    p04 = repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md"
    p03.write_text(p03.read_text().replace("  state: READY\n", "  state: READY\n  execution_started: false\n"))
    p04.write_text(p04.read_text().replace("  status: PENDING\n", "  status: PENDING\n  execution_started: false\n"))
    resolved = state.resolve_current_task(repo, project)
    assert resolved.id == "D01-30"
    assert "execution_started:" not in p03.read_text()
    assert "execution_started:" not in p04.read_text()


def test_sync_project_metadata_updates_demo_progress_from_task_rows(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    path = project / "docs/PRODUCTION.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("Current task: `D01-030`\n", "Current task: `D01-030`\nProgress: `0/99` Demo tasks complete\n")
    path.write_text(text, encoding="utf-8")
    state.sync_project_metadata(project)
    updated = path.read_text(encoding="utf-8")
    assert "Progress: `1/3` Demo tasks complete" in updated


def test_legacy_d01_ids_resolve_to_canonical_two_digit_identity(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    production = state.load_project_production(project)
    assert production.current_task == "D01-30"
    assert state.find_task(production, "D01-030").id == "D01-30"
    assert state.find_task(production, "D01-30").id == "D01-30"
    assert state.load_active_task(repo).id == "D01-30"


def test_mark_complete_accepts_canonical_id_for_legacy_d01_row(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    state.mark_task_complete(repo, project, "D01-30", "COMPLETE", ["runtime pass"])
    text = (project / "docs/PRODUCTION.md").read_text(encoding="utf-8")
    assert "- [x] D01-30 | hard | Current task | COMPLETE | runtime pass" in text
    assert state.load_active_task(repo).id == "D01-31"


def test_sync_project_metadata_normalizes_legacy_task_rows_in_place(tmp_path: Path):
    _repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    state.sync_project_metadata(project)
    text = (project / "docs/PRODUCTION.md").read_text(encoding="utf-8")
    assert "Current task: `D01-30`" in text
    assert "- [x] D01-29 | hard | Prior task | COMPLETE | prior evidence" in text
    assert "- [ ] D01-30 | hard | Current task | PENDING | current evidence" in text
    assert "D01-029" not in text
    assert "D01-030" not in text


def test_resolve_current_task_refreshes_derived_task_ledger(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    resolved = state.resolve_current_task(repo, project)
    ledger_path = repo / "docs/task-program/D_TASK_LEDGER.json"
    assert resolved.id == "D01-30"
    assert ledger_path.exists()
    text = ledger_path.read_text(encoding="utf-8")
    assert '"current_task": "D01-30"' in text
    assert '"registry_is_queue": false' in text


def test_resolve_rewrites_legacy_active_and_state_ids_immediately(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    state.resolve_current_task(repo, project)
    active_text = (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").read_text(encoding="utf-8")
    state_text = (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").read_text(encoding="utf-8")
    assert "  id: D01-30" in active_text
    assert "  id: D01-030" not in active_text
    assert "  id: D01-30" in state_text
    assert "  id: D01-030" not in state_text


def test_resolve_none_active_pointer_advances_to_project_successor(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="NONE", project_id="D02-01")
    path = project / "docs/PRODUCTION.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("- [ ] D01-030 | hard | Current task | PENDING | current evidence", "- [x] D01-030 | hard | Current task | COMPLETE | current evidence")
    text = text.replace("- [ ] D01-031 | hard | Next task | PENDING | next evidence", "- [x] D01-031 | hard | Next task | COMPLETE | next evidence")
    text = text.replace("## Section: demo01 | Demo | IN_PROGRESS", "## Section: demo01 | Demo | COMPLETE")
    text += "\n## Section: post_d01 | Continuation | PENDING\n\n- [ ] D02-01 | hard_creation | Open-world streaming and continuity | PENDING | ready\n"
    path.write_text(text, encoding="utf-8")

    resolved = state.resolve_current_task(repo, project)

    assert resolved.id == "D02-01"
    assert state.load_active_task(repo).id == "D02-01"


def test_sync_current_state_demo_count_excludes_completed_post_d01_tasks(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D02-01")
    production_path = project / "docs/PRODUCTION.md"
    text = production_path.read_text(encoding="utf-8")
    text = text.replace("- [ ] D01-030 | hard | Current task | PENDING | current evidence", "- [x] D01-030 | hard | Current task | COMPLETE | current evidence")
    text = text.replace("- [ ] D01-031 | hard | Next task | PENDING | next evidence", "- [x] D01-031 | hard | Next task | COMPLETE | next evidence")
    text = text.replace("## Section: demo01 | Demo | IN_PROGRESS", "## Section: demo01 | Demo | COMPLETE")
    text += "\n## Section: post_d01 | Continuation | IN_PROGRESS\n\n- [x] D02-01 | hard | Post task | COMPLETE | pass\n- [ ] D02-02 | hard | Current post task | PENDING |\n"
    production_path.write_text(text, encoding="utf-8")
    state_path = repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md"
    state_path.write_text(state_path.read_text() + "games:\n  completed_demo_tasks: 0\n  total_demo_tasks: 3\n  queued_successor: D02-02\n")
    production = state.load_project_production(project)
    current = state.find_task(production, "D02-02")
    state.sync_current_state(repo, production, current)
    current_text = state_path.read_text(encoding="utf-8")
    assert "completed_demo_tasks: 3" in current_text
    assert "completed_demo_tasks: 4" not in current_text


def test_sync_current_state_removes_volatile_runtime_snapshots_and_updates_program_progress(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    state_path = repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md"
    state_path.write_text(
        "repository:\n  source_alignment_commit: old\n  source_alignment_tree: oldtree\n"
        "active_execution:\n  id: D01-030\n  state: RUNNING\n  latest_attempt: 99\n  active_model: stale\n"
        "  active_reasoning: stale\n  controller_service_state: ACTIVE\n  runner_process_state: RUNNING\n"
        "  codex_child_process_state: RUNNING\n  authoritative_persistent_task_session_id: stale-session\n"
        "  current_increment: old\n  predecessor: OLD\n  predecessor_status: OLD\n"
        "customer_execution:\n  running_customer_count: 99\n  current_state: OLD\n"
        "games:\n  current_task: OLD\n  current_section: OLD\n  completed_tasks: 0\n  total_tasks: 0\n",
        encoding="utf-8",
    )
    production = state.load_project_production(project)
    current = state.find_task(production, "D01-030")
    state.sync_current_state(repo, production, current)
    updated = state_path.read_text()
    for stale in ("source_alignment_commit:", "source_alignment_tree:", "latest_attempt:", "active_model:",
                  "active_reasoning:", "controller_service_state:", "runner_process_state:",
                  "codex_child_process_state:", "authoritative_persistent_task_session_id:",
                  "current_increment:", "predecessor:", "predecessor_status:"):
        assert stale not in updated
    assert "runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json" in updated
    assert "source_identity_source: LIVE_GIT_PLUS_RUNTIME" in updated
    assert "runtime_state_source: DOCKER_PLUS_CUSTOMER_HANDOFF_RUNTIME" in updated
    assert "running_customer_count:" not in updated
    assert "current_state:" not in updated
    assert "current_task: D01-30" in updated
    assert "current_section: demo01" in updated
    assert "completed_tasks: 1" in updated
    assert "total_tasks: 3" in updated
