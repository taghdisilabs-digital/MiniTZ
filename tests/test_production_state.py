from pathlib import Path
import importlib.util
import json
import sys

import pytest

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


def _write_minitz_program(path: Path, task_ids=("UNIFY-01", "UNIFY-02")) -> Path:
    import json
    tasks = []
    for task_id in task_ids:
        row = {
            "task_id": task_id,
            "revision": 1,
            "status": "PENDING",
            "title": f"Execute {task_id}",
            "active_task_survival": True,
            "review_state": "VALUE_GATE_PASSED",
            "dependencies": [],
            "scope": {"system": "MiniTZ"},
            "source_refs": [],
            "acceptance": ["validated current-task completion"],
        }
        row["task_record_sha256"] = state.minitz.task_digest(row)
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
        "dependency_types": list(state.minitz.DEPENDENCY_TYPES),
        "revision": 1,
        "status": "ACTIVE_MINITZ_TASK_PROGRAM",
        "task_count": len(tasks),
        "tasks": tasks,
        "current_execution": {
            "task_id": tasks[0]["task_id"],
            "task_revision": tasks[0]["revision"],
            "task_sha256": tasks[0]["task_record_sha256"],
        },
    }
    path.write_text(json.dumps(program, indent=2) + "\n", encoding="utf-8")
    return path


def _write_minitz_projection_fixture(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    project = repo / "project"
    (repo / "docs/project-state").mkdir(parents=True)
    project.mkdir()
    (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").write_text("stale\n")
    (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").write_text("stale\n")
    program = _write_minitz_program(tmp_path / "TASK_PROGRAM.json")
    monkeypatch.setenv("MINITZ_TASK_PROGRAM_PATH", str(program))
    return repo, project, program


def test_minitz_resolution_does_not_require_precompiled_write_scope(tmp_path: Path, monkeypatch):
    repo, project, _program = _write_minitz_projection_fixture(tmp_path, monkeypatch)
    resolved = state.resolve_current_task(repo, project)
    assert resolved is not None
    assert resolved.id == "UNIFY-01"
    assert "MINITZ ACTIVE TASK PROJECTION" in (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").read_text()
    assert "MINITZ CURRENT STATE PROJECTION" in (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").read_text()


def test_minitz_completion_advances_to_successor_without_precompiled_write_scope(tmp_path: Path, monkeypatch):
    repo, project, _program = _write_minitz_projection_fixture(tmp_path, monkeypatch)
    state.mark_task_complete(repo, project, "UNIFY-01", "COMPLETE", ["validator pass"])
    production = state.load_project_production(project)
    assert state.find_task(production, "UNIFY-01").status == "COMPLETE"
    assert production.current_task == "UNIFY-02"
    assert state.resolve_current_task(repo, project).id == "UNIFY-02"


def test_minitz_runner_falls_back_to_canonical_repo_when_scope_is_not_precompiled(tmp_path: Path, monkeypatch):
    repo, project, _program = _write_minitz_projection_fixture(tmp_path, monkeypatch)
    import biella_production_runner as runner
    assert runner._task_working_directory(repo, project, "UNIFY-01") == repo.resolve()


def test_runner_reads_live_minitz_owner_direction(tmp_path: Path, monkeypatch):
    repo, project, program_path = _write_minitz_projection_fixture(tmp_path, monkeypatch)
    import json
    program = json.loads(program_path.read_text())
    program["owner_direction"] = {
        "identity": "MiniTZ",
        "owner": "Mahdi Taghdisi Neghab",
        "organization": "TaghdisiLabs.Digital",
        "contact": "Solo@taghdisilabs.digital",
        "project_brand_injection": "FORBIDDEN_UNLESS_PROJECT_EXPLICITLY_REQUIRES_IT",
        "automatic_task_progression": "MANDATORY",
        "validator_creation": "AUTOMATIC_WHEN_REQUIRED",
    }
    program_path.write_text(json.dumps(program, indent=2) + "\n")
    import biella_production_runner as runner
    rendered = runner._minitz_owner_direction(project)
    assert "Mahdi Taghdisi Neghab" in rendered
    assert "TaghdisiLabs.Digital" in rendered
    assert "Solo@taghdisilabs.digital" in rendered
    assert "FORBIDDEN_UNLESS_PROJECT_EXPLICITLY_REQUIRES_IT" in rendered
    assert "AUTOMATIC_WHEN_REQUIRED" in rendered


def test_minitz_state_projection_uses_live_git_remote_identity(tmp_path: Path, monkeypatch):
    repo, project, _program = _write_minitz_projection_fixture(tmp_path, monkeypatch)
    import subprocess
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run([
        "git", "-C", str(repo), "remote", "add", "origin",
        "https://github.com/taghdisilabs-digital/MiniTZ.git",
    ], check=True)
    state.resolve_current_task(repo, project)
    rendered = (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").read_text()
    assert "repository: taghdisilabs-digital/MiniTZ" in rendered
    assert "patrickminitz-web" not in rendered


def test_minitz_completion_persists_family_and_transition_receipt(tmp_path: Path, monkeypatch):
    repo, project, program_path = _write_minitz_projection_fixture(tmp_path, monkeypatch)
    program = json.loads(program_path.read_text(encoding="utf-8"))
    program["current_execution"].update({
        "run_ref": "commander-run://run-1",
        "session_ref": "commander-session://session-1",
        "run_state_ref": {"path": "/tmp/run-state.json", "sha256": "state-digest"},
    })
    program_path.write_text(json.dumps(program, indent=2) + "\n", encoding="utf-8")

    state.resolve_current_task(repo, project)
    state.mark_task_complete(repo, project, "UNIFY-01", "COMPLETE", ["validator pass"])

    program = json.loads(program_path.read_text(encoding="utf-8"))
    evidence = program["tasks"][0]["completion"]["evidence"]
    assert "MINITZ_TRANSITION_PREDECESSOR_TASK_ID:UNIFY-01" in evidence
    assert "MINITZ_TRANSITION_RUN_REF:commander-run://run-1" in evidence
    assert "MINITZ_TRANSITION_SESSION_REF:commander-session://session-1" in evidence
    assert "MINITZ_TRANSITION_RUN_STATE_REF:{\"path\":\"/tmp/run-state.json\",\"sha256\":\"state-digest\"}" in evidence

    active = (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").read_text(encoding="utf-8")
    current = (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").read_text(encoding="utf-8")
    for rendered in (active, current):
        assert "id: MINITZ_PROGRESSION_FAMILY" in rendered
        assert "scheduler_mechanism: GENERIC_SCHEDULER_PLAN_ONLY" in rendered
        assert "progression_mutation: false" in rendered
        assert "predecessor_task_id: UNIFY-01" in rendered
        assert "run_ref: commander-run://run-1" in rendered
        assert "session_ref: commander-session://session-1" in rendered


def test_minitz_resolution_repairs_stale_projection_from_canonical_receipt(tmp_path: Path, monkeypatch):
    repo, project, program_path = _write_minitz_projection_fixture(tmp_path, monkeypatch)
    state.mark_task_complete(repo, project, "UNIFY-01", "COMPLETE", ["validator pass"])
    active_path = repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md"
    current_path = repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md"
    active_path.write_text("stale active projection\n", encoding="utf-8")
    current_path.unlink()

    resolved = state.resolve_current_task(repo, project)
    identity = state.minitz.program_identity(state.minitz.load(program_path))
    assert resolved.id == "UNIFY-02"
    for path in (active_path, current_path):
        rendered = path.read_text(encoding="utf-8")
        assert f"program_revision: {identity['revision']}" in rendered
        assert f"program_sha256: {identity['sha256']}" in rendered
        assert "predecessor_task_id: UNIFY-01" in rendered


def test_normal_active_projection_fails_closed_when_production_source_is_missing(tmp_path: Path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    production_path = project / "docs/PRODUCTION.md"
    task = state.find_task(state.load_project_production(project), "D01-030")
    production_path.unlink()
    with pytest.raises(FileNotFoundError):
        state.write_active_task(repo, task)


def test_normal_progression_priority_rejects_malformed_authority(tmp_path: Path):
    _repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    path = project / "docs/PRODUCTION.md"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "Status: `IN_PROGRESS`\n", "Status: `IN_PROGRESS`\nPriority: `NOT_A_POLICY`\n", 1
    ), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported progression priority policy"):
        state.load_project_production(project)


def test_scheduler_family_attachment_is_explicitly_plan_only():
    sys.path.insert(0, str(ROOT / "src"))
    from biella.scheduler import SchedulerContractError, SchedulerFamilyAttachment

    attachment = SchedulerFamilyAttachment.minitz()
    assert attachment.progression_authority == "MINITZ_TASK_PROGRAM_ONLY"
    assert attachment.progression_mutation is False
    with pytest.raises(SchedulerContractError):
        SchedulerFamilyAttachment(
            family_id="MINITZ_PROGRESSION_FAMILY",
            progression_authority="MINITZ_TASK_PROGRAM_ONLY",
            progression_mutation=True,
        )
