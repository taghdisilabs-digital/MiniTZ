from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/minitz_memory_compactor.py"
spec = importlib.util.spec_from_file_location("minitz_memory_compactor", MODULE)
assert spec and spec.loader
memory = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = memory
spec.loader.exec_module(memory)


def test_merge_is_content_addressed_and_preserves_equivalent_variants():
    records = [
        memory.MemoryRecord("instruction", "A   B", "p1", "D1", "hard", True),
        memory.MemoryRecord("instruction", "A B", "p2", "D2", "hard", True),
        memory.MemoryRecord("instruction", "unique", "p3", "D3", "simple", True),
    ]
    merged = memory.merge_records(records)
    assert len(merged["content"]) == 3
    groups = [g for g in merged["equivalence_groups"] if len(g["content_refs"]) == 2]
    assert len(groups) == 1
    assert set(groups[0]["source_refs"]) == {"p1", "p2"}
    assert any(item["text"] == "unique" for item in merged["content"].values())


def fixture(tmp_path: Path):
    repo = tmp_path / "repo"
    project = repo / "projects/minitz-games"
    (repo / "docs/project-state").mkdir(parents=True)
    (repo / "ops/workstation").mkdir(parents=True)
    (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/00_MINITZ_PROJECT_OPERATING_CONTRACT.md").write_text("# Law\n\nKeep verified work.\n")
    (repo / "docs/project-state/MINITZ_PROJECT_INSTRUCTIONS.md").write_text("# Rules\n\nUse Resources.\n")
    (repo / "docs/project-state/MINITZ_DURABLE_SOURCE_AND_SYNC_RULES.md").write_text("# Durable\n\nPublish exact bytes.\n")
    (repo / "ops/workstation/AGENTS.md").write_text("# Agent\n\nLocal first.\n")
    (project / "AGENTS.md").write_text("# Games\n\nPreserve gameplay truth.\n")
    (project / "docs/PRODUCTION.md").write_text(
        "Status: `IN_PROGRESS`\nCurrent section: `s1`\nCurrent task: `T2`\n\n"
        "## Section: s1 | Work | IN_PROGRESS\n"
        "- [x] T1 | hard | Done task | COMPLETE | build pass; runtime pass\n"
        "- [ ] T2 | hard_creation | Current task | PENDING | \n"
    )
    registry = {
        "schema":"minitz.provider_registry/v1", "policy":{},
        "providers":{"local":{"capabilities":["llm.code","llm.reasoning"],"required_env":[],"locator_env":[]}},
        "routes":{"llm.code":["local"],"llm.reasoning":["local"]},
    }
    (repo / "ops/workstation/provider-registry.json").write_text(json.dumps(registry))
    runtime = tmp_path / "runtime"; (runtime / "task-memory").mkdir(parents=True)
    (runtime / "task-memory/T2.json").write_text(json.dumps({
        "task_id":"T2","task_class":"hard_creation","summary":"partial world work",
        "evidence":["editor build pass"],"session_id":"sess","dirty_paths":["a.cpp"]
    }))
    failures = [
        {"schema":"minitz.failure_event/v1","seq":1,"time":"now","failure_type":"tool.completed",
         "status":"FAILED","task_id":"T2","tool":"shell","exit_code":1,"text":"rg optional path","detail":"no match"},
        {"schema":"minitz.failure_event/v1","seq":2,"time":"later","failure_type":"bounded_search",
         "status":"RECOVERED","task_id":"T2","detail":"bounded search recovered"},
        {"schema":"minitz.failure_event/v1","seq":3,"time":"latest","failure_type":"runtime_validation",
         "status":"CONTINUE","task_id":"T2","detail":"nav failed"},
    ]
    (runtime / "failures.jsonl").write_text("".join(json.dumps(row)+"\n" for row in failures))
    return repo, project, runtime


def test_refresh_categorizes_verified_actions_failures_capabilities_and_sources(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    data = json.loads(result.index_path.read_text())
    assert data["schema"] == "minitz.compacted_memory/v1"
    cats = data["categories"]
    assert cats["verified_action"]
    texts = [data["content"][r]["text"] for r in cats["verified_action"]]
    assert "build pass" in texts and "runtime pass" in texts
    assert cats["failure"]
    assert data["capabilities"]["llm.code"] == ["local"]
    assert data["capabilities"]["llm.reasoning"] == ["local"]
    assert all(src["sha256"] and src["bytes"] >= 0 for src in data["sources"])
    with gzip.open(result.gzip_path, "rb") as handle:
        assert handle.read() == result.index_path.read_bytes()


def test_projection_is_bounded_project_aware_and_preserves_refs(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2", projection_max_chars=12000)
    projection = json.loads(result.projection_path.read_text())
    assert projection["task_id"] == "T2"
    assert projection["task_memory"]["summary"] == "partial world work"
    assert [row["failure_type"] for row in projection["failures"]] == ["runtime_validation"]
    assert projection["failures"][0]["detail"] == "nav failed"
    assert projection["capabilities"]["llm.code"] == ["local"]
    assert projection["source_refs"]
    assert result.projection_path.stat().st_size <= 12000


def test_projection_exposes_bounded_active_working_set_for_exact_source_reading(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    task_path = runtime / "task-memory/T2.json"
    task = json.loads(task_path.read_text())
    task["owned_files"] = {
        "ops/local-ai/worker.py": "a" * 64,
        "tests/test_worker.py": "b" * 64,
    }
    task["dirty_paths"] = ["ops/local-ai/worker.py"]
    task["workspace_baseline"] = {
        **{f"src/module_{index:02d}.py": "c" * 64 for index in range(70)},
        "ops/local-ai/worker.py": "a" * 64,
        "tests/test_worker.py": "b" * 64,
    }
    task["task_revision"] = 3
    task["task_digest"] = "d" * 64
    task["program_identity"] = {
        "path": "/canonical/TASK_PROGRAM.json",
        "revision": 9,
        "sha256": "e" * 64,
    }
    task_path.write_text(json.dumps(task))

    result = memory.refresh_compacted_memory(
        repo, project, runtime, current_task_id="T2", projection_max_chars=12000
    )
    projection = json.loads(result.projection_path.read_text())
    working = projection["active_working_set"]
    assert working["authority"] == "NONE_DERIVED_READING_HINT"
    assert working["task_id"] == "T2"
    assert working["task_revision"] == 3
    assert working["task_digest"] == "d" * 64
    assert working["canonical_task_program_ref"] == "/canonical/TASK_PROGRAM.json"
    assert working["owned_paths"] == ["ops/local-ai/worker.py", "tests/test_worker.py"]
    assert working["dirty_paths"] == ["ops/local-ai/worker.py"]
    assert working["workspace_path_count"] == 72
    assert {row["root"] for row in working["workspace_roots"]} == {"ops", "src", "tests"}
    assert working["read_policy"] == "READ_EXACT_CURRENT_SOURCE_ON_DEMAND"
    assert result.projection_path.stat().st_size <= 12000


def test_projection_keeps_raw_tool_failures_in_full_index_but_not_active_prompt(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    index = json.loads(result.index_path.read_text())
    projection = json.loads(result.projection_path.read_text())
    failure_texts = [index["content"][ref]["text"] for ref in index["categories"]["failure"]]
    assert any('"failure_type":"tool.completed"' in text for text in failure_texts)
    assert any('"status":"RECOVERED"' in text for text in failure_texts)
    assert all(row.get("failure_type") != "tool.completed" for row in projection["failures"])
    assert all(str(row.get("status", "")).upper() not in {"RECOVERED", "REPAIRED", "RESOLVED", "PASS", "COMPLETED"} for row in projection["failures"])


def test_commander_result_rejection_stays_in_raw_history_but_not_active_task_failures(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    row = {
        "schema":"minitz.failure_event/v1", "seq":4, "time":"now",
        "failure_type":"VALIDATION_REJECTED", "event_type":"commander.assist_failed",
        "status":"NEEDS_MODIFICATION", "task_id":"T2",
        "authority":"NONE_DERIVED_EVIDENCE", "progression_authority":False,
        "text":"Commander evidence reference is not in the supplied task context",
    }
    with (runtime / "failures.jsonl").open("a") as handle:
        handle.write(json.dumps(row)+"\n")
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    projection = json.loads(result.projection_path.read_text())
    assert all(item.get("event_type") != "commander.assist_failed" for item in projection["failures"])
    index = json.loads(result.index_path.read_text())
    failure_texts = [index["content"][ref]["text"] for ref in index["categories"]["failure"]]
    assert any("Commander evidence reference" in text for text in failure_texts)


def test_commander_provider_failure_remains_active_task_failure(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    row = {
        "schema":"minitz.failure_event/v1", "seq":5, "time":"now",
        "failure_type":"OUT_OF_CREDIT", "event_type":"commander.assist_failed",
        "status":"FAILED", "task_id":"T2", "provider":"groq",
        "authority":"NONE_DERIVED_EVIDENCE", "progression_authority":False,
        "text":"provider quota exhausted",
    }
    with (runtime / "failures.jsonl").open("a") as handle:
        handle.write(json.dumps(row)+"\n")
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    projection = json.loads(result.projection_path.read_text())
    assert any(item.get("failure_type") == "OUT_OF_CREDIT" for item in projection["failures"])


def test_recovery_checkpoint_clears_prior_active_failures_without_deleting_raw_history(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    with (runtime / "failures.jsonl").open("a") as handle:
        handle.write(json.dumps({
            "schema":"minitz.failure_event/v1","seq":4,"time":"resolved","failure_type":"task.recovery",
            "status":"RECOVERED","task_id":"T2","resolve_prior":True,"detail":"root cause fixed"
        })+"\n")
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    index = json.loads(result.index_path.read_text())
    projection = json.loads(result.projection_path.read_text())
    assert projection["failures"] == []
    failure_texts = [index["content"][ref]["text"] for ref in index["categories"]["failure"]]
    assert any('"detail":"nav failed"' in text for text in failure_texts)
    assert any('"resolve_prior":true' in text for text in failure_texts)


def test_failure_after_recovery_checkpoint_becomes_active_again(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    with (runtime / "failures.jsonl").open("a") as handle:
        handle.write(json.dumps({
            "schema":"minitz.failure_event/v1","seq":4,"time":"resolved","failure_type":"task.recovery",
            "status":"RECOVERED","task_id":"T2","resolve_prior":True
        })+"\n")
        handle.write(json.dumps({
            "schema":"minitz.failure_event/v1","seq":5,"time":"after","failure_type":"runtime_validation",
            "status":"CONTINUE","task_id":"T2","detail":"new blocker"
        })+"\n")
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    projection = json.loads(result.projection_path.read_text())
    assert len(projection["failures"]) == 1
    assert projection["failures"][0]["detail"] == "new blocker"


def test_raw_tool_failure_alone_remains_lossless_but_never_becomes_active_prompt_blocker(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    raw = {"schema":"minitz.failure_event/v1","seq":9,"time":"now","failure_type":"tool.completed",
           "status":"FAILED","task_id":"T2","tool":"shell","exit_code":1,"detail":"rg no match"}
    (runtime / "failures.jsonl").write_text(json.dumps(raw)+"\n")
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    index = json.loads(result.index_path.read_text())
    projection = json.loads(result.projection_path.read_text())
    assert projection["failures"] == []
    failure_texts = [index["content"][ref]["text"] for ref in index["categories"]["failure"]]
    assert any('"failure_type":"tool.completed"' in text and 'rg no match' in text for text in failure_texts)


def test_projection_excludes_retired_command_surface_process_noise_but_keeps_raw_history(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    with (runtime / "failures.jsonl").open("a") as handle:
        handle.write(json.dumps({
            "schema":"minitz.failure_event/v1", "seq":99, "time":"old",
            "failure_type":"PROCESS_FAILED", "status":"ERROR", "task_id":"T2",
            "provider":"fast-llm-pool", "text":"Use the MiniTZ OS command surface."
        }) + "\n")
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    projection = json.loads(result.projection_path.read_text())
    assert all(
        "Use the MiniTZ OS command surface." not in json.dumps(row)
        for row in projection["failures"]
    )
    index = json.loads(result.index_path.read_text())
    failure_texts = [index["content"][ref]["text"] for ref in index["categories"]["failure"]]
    assert any("Use the MiniTZ OS command surface." in text for text in failure_texts)


def test_projection_excludes_transient_provider_recovery_noise_but_keeps_raw_history(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    with (runtime / "failures.jsonl").open("a") as handle:
        handle.write(json.dumps({
            "seq":10,"time":"provider","failure_type":"agent.error","status":"FAILED","task_id":"T2",
            "text":"You've hit your usage limit. Visit chatgpt.com/codex/settings/usage"
        })+"\n")
        handle.write(json.dumps({
            "seq":11,"time":"local","failure_type":"task.runtime_recovery","status":"RECOVERING_RUNTIME","task_id":"T2",
            "text":"qwen3-coder-next:minitz does not support thinking"
        })+"\n")
        handle.write(json.dumps({
            "seq":12,"time":"resume","failure_type":"agent.error","status":"FAILED","task_id":"T2",
            "text":r"Reconnecting... ({\\\"error\\\":{\\\"message\\\":\\\"input[42]: unknown input item type: \\\\\\\"compaction\\\\\\\"\\\"}})"
        })+"\n")
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    index = json.loads(result.index_path.read_text())
    projection = json.loads(result.projection_path.read_text())
    projected = json.dumps(projection["failures"]).lower()
    assert "usage limit" not in projected
    assert "does not support thinking" not in projected
    assert "unknown input item type" not in projected
    assert "nav failed" in projected
    failure_texts = [index["content"][ref]["text"].lower() for ref in index["categories"]["failure"]]
    assert any("usage limit" in text for text in failure_texts)
    assert any("does not support thinking" in text for text in failure_texts)
    assert any("unknown input item type" in text for text in failure_texts)


def test_projection_excludes_cross_task_legacy_task_key_failures(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    with (runtime / "failures.jsonl").open("a") as handle:
        handle.write(json.dumps({
            "time":"old","type":"build","status":"repairing","task":"OTHER-01",
            "diagnostic":"old task failure must not enter current prompt"
        })+"\n")
        handle.write(json.dumps({
            "time":"current","type":"runtime_validation","status":"CONTINUE","task":"T2",
            "diagnostics":"current task blocker"
        })+"\n")
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    projection = json.loads(result.projection_path.read_text())
    details = json.dumps(projection["failures"])
    assert "old task failure" not in details
    assert "current task blocker" in details


def test_bridge_contract_is_provenance_only_not_active_policy(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    bridge = repo / "docs/project-state/MINITZ_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml"
    bridge.write_text(
        'document:\n  id: "MINITZ_ISOLATED_PROJECT_EXECUTION_BRIDGE"\n'
        'execution_model:\n  model: "isolated_project_cell"\n'
        'absolute_invariants:\n  - "MINITZ_OWNS_EXECUTION_STATE"\n',
        encoding="utf-8",
    )
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    index = json.loads(result.index_path.read_text())
    source_paths = {str(item["path"]) for item in index["sources"]}
    assert not any("MINITZ_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml" in item for item in source_paths)
    provenance = index["policy"]["provenance_sources"]
    assert any(item["path"] == "docs/project-state/MINITZ_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml" and item["provenance_only"] for item in provenance)
    instructions = [index["content"][ref]["text"] for ref in index["categories"]["instruction"]]
    assert not any("isolated_project_cell" in item for item in instructions)


def test_minitz_policy_excludes_legacy_steering_but_preserves_exact_provenance(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    legacy = repo / "docs/project-state/MINITZ_PROJECT_INSTRUCTIONS.md"
    legacy_bytes = legacy.read_bytes()
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    index = json.loads(result.index_path.read_text())
    policy = index["policy"]

    assert policy["active_historical_steering_target"] == 0
    assert policy["legacy_policy_active_input"] is False
    assert all(item["path"] != "docs/project-state/MINITZ_PROJECT_INSTRUCTIONS.md" for item in index["sources"])
    assert all(
        "Use Resources." not in item["text"]
        for item in index["content"].values()
    )
    legacy_rows = [
        item for item in policy["provenance_sources"]
        if item["path"] == "docs/project-state/MINITZ_PROJECT_INSTRUCTIONS.md"
    ]
    assert len(legacy_rows) == 1
    assert legacy_rows[0]["sha256"] == memory._sha(legacy_bytes)
    assert legacy_rows[0]["active_input"] is False
    assert legacy_rows[0]["provenance_only"] is True

    replacement_ids = {item["rule_id"] for item in policy["semantic_replacements"]}
    assert "p4-06-scoped-acceptance" in replacement_ids
    semantic_ids = {item["rule_id"] for item in policy["semantic_rules"]}
    assert "minitz-memory-residency" in semantic_ids
    semantic_text = " ".join(item["statement"] for item in policy["semantic_rules"])
    assert "current task-specific acceptance" in semantic_text
    assert "raw API/login authentication credential values" in semantic_text
    assert "memory, experience, learning, caches" in semantic_text


def test_minitz_policy_has_one_candidate_projection_per_rule_and_scope(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    policy = json.loads(result.index_path.read_text())["policy"]
    active_keys = [
        (item["scope_ref"], item["rule_identity"])
        for item in policy["active_rule_index"]
        if item["active_projection_count"] == 1
    ]

    assert active_keys
    assert len(active_keys) == len(set(active_keys))
    assert policy["active_authority_conflicts"] == []
    assert policy["authority"] == "NONE_CANDIDATE_ANALYSIS"
    assert set(policy["execution_inputs"]) == {"scope://minitz/system"}
    assert policy["execution_inputs"]["scope://minitz/system"]["agents_policy_digest"]


def test_scoped_policy_digest_changes_invalidate_only_dependent_scope(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    first = memory.build_policy_projection(repo, project)
    first_inputs = first["execution_inputs"]

    project_agents = project / "AGENTS.md"
    project_agents.write_text(project_agents.read_text() + "\nHistorical project-only change.\n")
    second = memory.build_policy_projection(repo, project)
    second_inputs = second["execution_inputs"]

    system_scope = "scope://minitz/system"
    assert second_inputs[system_scope]["effective_policy_digest"] == first_inputs[system_scope]["effective_policy_digest"]

    os_agents = repo / "ops/workstation/AGENTS.md"
    os_agents.write_text(os_agents.read_text() + "\nOS policy change.\n")
    third = memory.build_policy_projection(repo, project)
    assert third["execution_inputs"][system_scope]["effective_policy_digest"] != second_inputs[system_scope]["effective_policy_digest"]

    legacy = repo / "docs/project-state/MINITZ_PROJECT_INSTRUCTIONS.md"
    legacy.write_text(legacy.read_text() + "\nHistorical-only change.\n")
    fourth = memory.build_policy_projection(repo, project)
    assert fourth["execution_inputs"] == third["execution_inputs"]


def test_compactor_preserves_nonsecret_experience_but_redacts_raw_auth_credentials(tmp_path: Path, monkeypatch):
    repo, project, runtime = fixture(tmp_path)
    credentials = tmp_path / "runtime.env"
    credentials.write_text(
        "API_TOKEN=api-secret-value-123456789\n"
        "LOGIN_PASSWORD=login-secret-value-987654321\n"
        "MODEL=qwen3-coder-next:minitz\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MINITZ_AI_RUNTIME_ENV", str(credentials))
    with (runtime / "failures.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "schema":"minitz.failure_event/v1", "seq":99, "time":"now",
            "failure_type":"provider_recovery", "status":"CONTINUE", "task_id":"T2",
            "detail":"provider used api-secret-value-123456789 then recovered useful state",
            "text":"login login-secret-value-987654321 retry preserved",
        }) + "\n")
    task_path = runtime / "task-memory/T2.json"
    task = json.loads(task_path.read_text())
    task["summary"] = "keep engineering context; login-secret-value-987654321 must not persist"
    task_path.write_text(json.dumps(task), encoding="utf-8")

    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    index_bytes = result.index_path.read_bytes()
    projection_bytes = result.projection_path.read_bytes()
    for raw in (b"api-secret-value-123456789", b"login-secret-value-987654321"):
        assert raw not in index_bytes
        assert raw not in projection_bytes
    combined = index_bytes + projection_bytes
    assert b"then recovered useful state" in combined
    assert b"keep engineering context" in combined
    assert b"[MINITZ_AUTH_CREDENTIAL_REDACTED]" in combined
    data = json.loads(index_bytes)
    assert "memory" in data["data_residency"]["retained_inside_minitz"]
    assert "experience" in data["data_residency"]["retained_inside_minitz"]
    assert "cache" in data["data_residency"]["retained_inside_minitz"]
