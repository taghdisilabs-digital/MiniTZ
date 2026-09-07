from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/biella_memory_compactor.py"
spec = importlib.util.spec_from_file_location("biella_memory_compactor", MODULE)
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
    project = repo / "projects/biella-games"
    (repo / "docs/project-state").mkdir(parents=True)
    (repo / "ops/workstation").mkdir(parents=True)
    (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/00_BIELLA_PROJECT_OPERATING_CONTRACT.md").write_text("# Law\n\nKeep verified work.\n")
    (repo / "docs/project-state/BIELLA_PROJECT_INSTRUCTIONS.md").write_text("# Rules\n\nUse Resources.\n")
    (repo / "docs/project-state/BIELLA_DURABLE_SOURCE_AND_SYNC_RULES.md").write_text("# Durable\n\nPublish exact bytes.\n")
    (repo / "ops/workstation/AGENTS.md").write_text("# Agent\n\nLocal first.\n")
    (project / "AGENTS.md").write_text("# Games\n\nPreserve gameplay truth.\n")
    (project / "docs/PRODUCTION.md").write_text(
        "Status: `IN_PROGRESS`\nCurrent section: `s1`\nCurrent task: `T2`\n\n"
        "## Section: s1 | Work | IN_PROGRESS\n"
        "- [x] T1 | hard | Done task | COMPLETE | build pass; runtime pass\n"
        "- [ ] T2 | hard_creation | Current task | PENDING | \n"
    )
    registry = {
        "schema":"biella.provider_registry/v1", "policy":{},
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
        {"schema":"biella.failure_event/v1","seq":1,"time":"now","failure_type":"tool.completed",
         "status":"FAILED","task_id":"T2","tool":"shell","exit_code":1,"text":"rg optional path","detail":"no match"},
        {"schema":"biella.failure_event/v1","seq":2,"time":"later","failure_type":"bounded_search",
         "status":"RECOVERED","task_id":"T2","detail":"bounded search recovered"},
        {"schema":"biella.failure_event/v1","seq":3,"time":"latest","failure_type":"runtime_validation",
         "status":"CONTINUE","task_id":"T2","detail":"nav failed"},
    ]
    (runtime / "failures.jsonl").write_text("".join(json.dumps(row)+"\n" for row in failures))
    return repo, project, runtime


def test_refresh_categorizes_verified_actions_failures_capabilities_and_sources(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    data = json.loads(result.index_path.read_text())
    assert data["schema"] == "biella.compacted_memory/v1"
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


def test_recovery_checkpoint_clears_prior_active_failures_without_deleting_raw_history(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    with (runtime / "failures.jsonl").open("a") as handle:
        handle.write(json.dumps({
            "schema":"biella.failure_event/v1","seq":4,"time":"resolved","failure_type":"task.recovery",
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
            "schema":"biella.failure_event/v1","seq":4,"time":"resolved","failure_type":"task.recovery",
            "status":"RECOVERED","task_id":"T2","resolve_prior":True
        })+"\n")
        handle.write(json.dumps({
            "schema":"biella.failure_event/v1","seq":5,"time":"after","failure_type":"runtime_validation",
            "status":"CONTINUE","task_id":"T2","detail":"new blocker"
        })+"\n")
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    projection = json.loads(result.projection_path.read_text())
    assert len(projection["failures"]) == 1
    assert projection["failures"][0]["detail"] == "new blocker"


def test_raw_tool_failure_alone_remains_lossless_but_never_becomes_active_prompt_blocker(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    raw = {"schema":"biella.failure_event/v1","seq":9,"time":"now","failure_type":"tool.completed",
           "status":"FAILED","task_id":"T2","tool":"shell","exit_code":1,"detail":"rg no match"}
    (runtime / "failures.jsonl").write_text(json.dumps(raw)+"\n")
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    index = json.loads(result.index_path.read_text())
    projection = json.loads(result.projection_path.read_text())
    assert projection["failures"] == []
    failure_texts = [index["content"][ref]["text"] for ref in index["categories"]["failure"]]
    assert any('"failure_type":"tool.completed"' in text and 'rg no match' in text for text in failure_texts)


def test_projection_excludes_transient_provider_recovery_noise_but_keeps_raw_history(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    with (runtime / "failures.jsonl").open("a") as handle:
        handle.write(json.dumps({
            "seq":10,"time":"provider","failure_type":"agent.error","status":"FAILED","task_id":"T2",
            "text":"You've hit your usage limit. Visit chatgpt.com/codex/settings/usage"
        })+"\n")
        handle.write(json.dumps({
            "seq":11,"time":"local","failure_type":"task.runtime_recovery","status":"RECOVERING_RUNTIME","task_id":"T2",
            "text":"qwen3-coder-next:biella does not support thinking"
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


def test_bridge_contract_is_a_compacted_policy_source(tmp_path: Path):
    repo, project, runtime = fixture(tmp_path)
    bridge = repo / "docs/project-state/BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml"
    bridge.write_text(
        'document:\n  id: "BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE"\n'
        'execution_model:\n  model: "isolated_project_cell"\n'
        'absolute_invariants:\n  - "BIELLA_OWNS_EXECUTION_STATE"\n',
        encoding="utf-8",
    )
    result = memory.refresh_compacted_memory(repo, project, runtime, current_task_id="T2")
    index = json.loads(result.index_path.read_text())
    source_paths = {str(item["path"]) for item in index["sources"]}
    assert any("BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml" in item for item in source_paths)
    instructions = [index["content"][ref]["text"] for ref in index["categories"]["instruction"]]
    assert any("isolated_project_cell" in item for item in instructions)
