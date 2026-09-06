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
