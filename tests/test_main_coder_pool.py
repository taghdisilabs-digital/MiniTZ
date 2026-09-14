import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/biella_main_coder.py"


def load_pool():
    assert MODULE.exists(), "main coder pool module is not implemented"
    spec = importlib.util.spec_from_file_location("biella_main_coder", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_universal_coder_status_is_exactly_four_states():
    pool = load_pool()
    assert pool.CODER_STATUSES == ("OFFLINE", "ACTIVE", "OUT_OF_CREDIT", "NEEDS_MODIFICATION")


def test_parse_agr_models_uses_real_cli_shape():
    pool = load_pool()
    raw = """Fetching available models...\ngemini-3.8-flash-high\tGemini 3.8 Flash (High)\nclaude-opus-4-6-thinking\tClaude Opus 4.6 (Thinking)\n"""
    assert pool.parse_agr_models(raw) == ("gemini-3.8-flash-high", "claude-opus-4-6-thinking")


def test_agr_status_classifies_real_observations_without_quota_probe():
    pool = load_pool()
    assert pool.classify_agr_observation(127, "agy: command not found") == "OFFLINE"
    assert pool.classify_agr_observation(1, "Eligibility check failed: account is not eligible in your location") == "NEEDS_MODIFICATION"
    assert pool.classify_agr_observation(1, "quota exhausted; weekly limit remaining 0%") == "OUT_OF_CREDIT"
    assert pool.classify_agr_observation(0, '{"status":"SUCCESS"}') == "ACTIVE"


def test_owner_excluded_agr_stream_command_is_not_constructible(tmp_path: Path):
    pool = load_pool()
    import pytest
    with pytest.raises(RuntimeError, match="disabled by the MiniTZ owner"):
        pool.build_agr_stream_command(
            "gemini-3.8-flash-high", "high", tmp_path / "schema.json", read_only=True
        )


def test_owner_excluded_agr_writer_command_is_not_constructible(tmp_path: Path):
    pool = load_pool()
    import pytest
    with pytest.raises(RuntimeError, match="disabled by the MiniTZ owner"):
        pool.build_agr_stream_command(
            "claude-opus-4-6-thinking", "high", tmp_path / "schema.json", read_only=False
        )


def test_agr_stream_user_event_is_exact_bounded_protocol():
    pool = load_pool()
    payload = json.loads(pool.agr_user_event("continue current task"))
    assert payload == {"event": "user", "message": {"content": "continue current task"}}


def test_parse_agr_stream_result_extracts_conversation_and_structured_output():
    pool = load_pool()
    lines = [
        '{"event":"system","message":"started"}',
        '{"event":"result","result":{"conversation_id":"conv-123","status":"SUCCESS","response":"ok","structured_output":{"task_id":"D01","status":"CONTINUE"},"usage":{"input_tokens":10,"cache_read_tokens":8}}}',
    ]
    result = pool.parse_agr_stream_result(lines)
    assert result["conversation_id"] == "conv-123"
    assert result["status"] == "SUCCESS"
    assert result["structured_output"]["task_id"] == "D01"
    assert result["usage"]["cache_read_tokens"] == 8


def test_coder_selection_preserves_codex_and_never_routes_owner_excluded_agr():
    pool = load_pool()
    selection = pool.select_coder_roles(
        {"codex": "ACTIVE", "agr": "ACTIVE"}, current_writer="codex"
    )
    assert selection.primary == "codex"
    assert selection.peer is None


def test_coder_selection_does_not_handoff_to_owner_excluded_agr():
    pool = load_pool()
    selection = pool.select_coder_roles(
        {"codex": "OUT_OF_CREDIT", "agr": "ACTIVE"}, current_writer="codex"
    )
    assert selection.primary is None
    assert selection.peer is None


def test_needs_modification_backend_is_not_routable():
    pool = load_pool()
    selection = pool.select_coder_roles(
        {"codex": "ACTIVE", "agr": "NEEDS_MODIFICATION"}, current_writer="codex"
    )
    assert selection.primary == "codex"
    assert selection.peer is None


def test_agr_task_model_preferences_are_quality_first_but_bounded():
    pool = load_pool()
    available = {
        "gemini-3.8-flash-high", "gemini-3.1-pro-high",
        "claude-sonnet-4-6", "claude-opus-4-6-thinking",
    }
    assert pool.select_agr_model("simple", available) == "gemini-3.8-flash-high"
    assert pool.select_agr_model("medium", available) == "claude-sonnet-4-6"
    assert pool.select_agr_model("hard", available) == "claude-opus-4-6-thinking"
    assert pool.select_agr_model("deep_memory", available) == "claude-opus-4-6-thinking"


def test_shared_policy_paths_use_same_engine_and_project_agents(tmp_path: Path):
    pool = load_pool()
    repo = tmp_path / "repo"
    project = repo / "projects" / "game"
    (repo / "ops/workstation").mkdir(parents=True)
    project.mkdir(parents=True)
    (repo / "ops/workstation/AGENTS.md").write_text("engine")
    (project / "AGENTS.md").write_text("project")
    assert pool.shared_policy_paths(repo, project) == (
        repo / "ops/workstation/AGENTS.md", project / "AGENTS.md"
    )


def test_owner_excluded_agr_discovery_returns_empty_without_cli_probe(monkeypatch):
    pool = load_pool()
    def forbidden(*_args, **_kwargs):
        raise AssertionError("owner-excluded AGY must not be probed")
    monkeypatch.setattr(pool.subprocess, "run", forbidden)
    assert pool.discover_agr_models(timeout_seconds=0.1) == set()


def test_peer_assist_schema_has_no_completion_authority():
    pool = load_pool()
    schema = pool.peer_assist_schema()
    assert schema["properties"]["status"]["enum"] == ["NO_FINDING", "USEFUL"]
    assert "task_status" not in schema["properties"]
    assert "complete" not in schema["properties"]


def test_peer_assist_key_is_project_scoped_content_addressed_and_backend_specific():
    pool = load_pool()
    a = pool.peer_assist_key("minitz", "UNIFY-04", "a" * 64, "agr", "claude-opus-4-6-thinking", "b" * 64, "c" * 64)
    b = pool.peer_assist_key("minitz", "UNIFY-04", "a" * 64, "agr", "claude-opus-4-6-thinking", "b" * 64, "c" * 64)
    c = pool.peer_assist_key("minitz", "UNIFY-04", "a" * 64, "codex", "gpt-6-astra", "b" * 64, "c" * 64)
    other_project = pool.peer_assist_key("customer-a", "UNIFY-04", "a" * 64, "agr", "claude-opus-4-6-thinking", "b" * 64, "c" * 64)
    assert a == b
    assert a != c
    assert a != other_project
    assert len(a) == 64


def test_peer_prompt_is_explicitly_read_only_and_shared_state_bound(tmp_path: Path):
    pool = load_pool()
    prompt = pool.peer_assist_prompt(
        task_id="UNIFY-04", title="Continuity", task_state_digest="d" * 64,
        capsule_path=tmp_path / "task.json", projection_path=tmp_path / "projection.json",
        policy_paths=(tmp_path / "AGENTS.md",), primary_coder="codex", peer_coder="agr",
    )
    assert "READ_ONLY_PEER_ASSIST" in prompt
    assert "AUTHORITY: NONE" in prompt
    assert "DO_NOT_MODIFY_FILES" in prompt
    assert "DO_NOT_COMPLETE_OR_ADVANCE_TASK" in prompt
    assert "PRIMARY_CODER: codex" in prompt
    assert "PEER_CODER: agr" in prompt
    assert "d" * 64 in prompt


def test_owner_excluded_agr_discovery_never_starts_process(monkeypatch):
    pool = load_pool()
    def forbidden(*args, **kwargs):
        raise AssertionError("AGY discovery must not execute")
    monkeypatch.setattr(pool.subprocess, "run", forbidden)
    assert pool.discover_agr_models() == set()


def test_owner_excluded_agr_never_selected_from_stale_active_status():
    pool = load_pool()
    selected = pool.select_coder_roles({"codex":"ACTIVE", "agr":"ACTIVE"}, current_writer="agr")
    assert selected.primary == "codex"
    assert selected.peer is None
