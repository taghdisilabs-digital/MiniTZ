from pathlib import Path
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


events = _load("minitz_repair_events", "ops/local-ai/minitz_production_events.py")
memory = _load("minitz_repair_memory", "ops/local-ai/minitz_memory_compactor.py")
style = _load("minitz_repair_style", "ops/local-ai/minitz_execution_style.py")


def test_repetitive_failure_becomes_bounded_repair_signal_across_restart(tmp_path: Path):
    event_path = tmp_path / "events.jsonl"
    failure_path = tmp_path / "failures.jsonl"
    first = events.ProductionEventJournal(event_path, failure_path=failure_path)
    first.emit("tool.failed", task_id="T-1", status="FAILED", tool="build",
               failure_type="COMPILER_FAILURE", detail="compiler failed pid=123")
    restarted = events.ProductionEventJournal(event_path, failure_path=failure_path)
    restarted.emit("tool.failed", task_id="T-1", status="FAILED", tool="build",
                   failure_type="COMPILER_FAILURE", detail="compiler failed pid=456")

    rows = [json.loads(line) for line in failure_path.read_text().splitlines()]
    assert rows[0]["recurrence_window_count"] == 1
    assert rows[0]["repetitive_failure"] is False
    assert rows[1]["recurrence_window_count"] == 2
    assert rows[1]["repetitive_failure"] is True
    assert rows[1]["repair_signal"] == "ROOT_CAUSE_BOUNDED_REPAIR"
    assert rows[1]["preserve_working_capabilities"] is True
    assert rows[0]["failure_signature"] == rows[1]["failure_signature"]

    projected = list(events.project_operational_evidence(event_path, failure_path))
    repeated = [row for row in projected if row.get("record_kind") == "FAILURE"][-1]
    assert repeated["repetitive_failure"] is True
    assert repeated["recurrence_window_count"] == 2


def test_compaction_preserves_task_horizon_project_and_creation_awareness(tmp_path: Path):
    repo = tmp_path / "repo"
    runtime = tmp_path / "runtime"
    (repo / "ops/workstation").mkdir(parents=True)
    (runtime / "task-memory").mkdir(parents=True)
    program = tmp_path / "TASK_PROGRAM.json"
    registry = {
        "providers": {
            "local": {
                "capabilities": ["llm.code", "asset.render", "browser.automation", "storage.read"],
                "required_env": [], "locator_env": [],
            }
        }
    }
    (repo / "ops/workstation/provider-registry.json").write_text(json.dumps(registry))

    task = {
        "task_id": "T-1", "revision": 7, "task_record_sha256": "task-digest-7",
        "project_id": "P-1", "title": "Preserve exact creation continuity", "status": "PENDING",
        "objective": {"desired_state": "repair without losing detail or working creation functions"},
        "acceptance": ["working create path remains functional", "scoped horizon remains exact"],
        "required_capabilities": ["llm.code", "asset.render"],
        "write_scope": {"authority": "TASK_OWNED_ONLY", "allowed_paths": ["/work/project"]},
        "preserve": {"accepted_work": True, "continuity": True, "evidence": True},
    }
    program.write_text(json.dumps({"program_id": "MINITZ", "tasks": [task]}))
    task_memory = {
        "task_id": "T-1", "task_revision": 7, "task_digest": "task-digest-7",
        "task_class": "hard", "title": task["title"], "summary": "unique detail " * 500,
        "next_action": "repair only the affected compiler boundary", "project_id": "P-1",
        "project_root": "/work/project", "scope_ref": "task://minitz/T-1/7",
        "program_identity": {"path": str(program), "program_id": "MINITZ", "revision": 9, "sha256": "program-9"},
    }
    (runtime / "task-memory/T-1.json").write_text(json.dumps(task_memory))
    failures = [
        {"task_id": "T-1", "failure_type": "COMPILER_FAILURE", "status": "FAILED",
         "failure_signature": "failure-signature://same", "recurrence_window_count": 2,
         "text": "same compiler boundary"},
        {"task_id": "T-1", "failure_type": "COMPILER_FAILURE", "status": "FAILED",
         "failure_signature": "failure-signature://same", "recurrence_window_count": 3,
         "text": "same compiler boundary"},
    ]
    (runtime / "failures.jsonl").write_text("".join(json.dumps(row) + "\n" for row in failures))

    result = memory.refresh_compacted_memory(
        repo, repo, runtime, current_task_id="T-1", projection_max_chars=2048
    )
    projection = json.loads(result.projection_path.read_text())
    guard = projection["continuity_guard"]
    assert guard["scoped_horizon"]["identity_state"] == "VERIFIED_TASK_HORIZON"
    assert guard["scoped_horizon"]["task"]["acceptance"] == task["acceptance"]
    assert guard["scoped_horizon"]["task"]["objective"] == task["objective"]
    assert guard["project_awareness"]["project_id"] == "P-1"
    assert set(guard["capability_ids"]) == {"llm.code", "asset.render", "browser.automation", "storage.read"}
    assert set(guard["creation_capability_ids"]) == {"llm.code", "asset.render", "browser.automation"}
    assert guard["repair_contract"]["preserve_working_capabilities"] is True
    assert projection["recurring_failures"][0]["observed_count"] >= 3


def test_execution_style_makes_preservation_invariants_runtime_prompt_rules():
    profile = style.proven_execution_style()
    prompt = style.proven_execution_style_prompt()
    assert profile["repetitive_failure_recovery"] == "FINGERPRINT_ROOT_CAUSE_BOUNDED_REPAIR"
    assert profile["repair_regression_policy"] == "PRESERVE_WORKING_CAPABILITIES"
    assert profile["context_preservation"] == "DETAIL_SCOPED_HORIZON_PROJECT_AWARENESS"
    assert profile["creation_functions"] == "PRESERVE_CREATE_BUILD_MODIFY_EXECUTE"
    assert "REPETITIVE_FAILURE_IS_A_REPAIR_SIGNAL" in prompt
    assert "NEVER_BREAK_WORKING_CAPABILITIES_TO_FIX_ONE_ERROR" in prompt
    assert "PRESERVE_DETAIL_SCOPED_HORIZON_AND_PROJECT_AWARENESS" in prompt
    assert "PRESERVE_CREATION_FUNCTIONS" in prompt
