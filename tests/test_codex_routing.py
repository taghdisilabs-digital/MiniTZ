from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/biella_codex_routing.py"
spec = importlib.util.spec_from_file_location("biella_codex_routing", MODULE)
assert spec and spec.loader
routing = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = routing
spec.loader.exec_module(routing)
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def catalog():
    return {
        "gpt-6-astra": {"high", "xhigh", "ultra"},
        "gpt-5.6-luna": {"medium", "high", "max"},
        "gpt-5.6-terra": {"medium", "high", "ultra"},
        "gpt-5.6-sol": {"medium", "high", "ultra"},
        "gpt-5.3-codex-spark": {"high", "xhigh"},
    }


def test_hard_and_deep_memory_route_astra_ultra():
    for task_class in ("hard", "deep_memory", "hard_creation"):
        assert routing.select_route(task_class, catalog(), {}, NOW) == routing.Route("gpt-6-astra", "ultra")


def test_creation_never_routes_below_high():
    route = routing.select_route("creation", catalog(), {}, NOW)
    assert routing.reasoning_rank(route.reasoning) >= routing.reasoning_rank("high")


def test_cooldown_skips_observed_model():
    route = routing.select_route("simple", catalog(), {"gpt-5.6-luna": "2026-09-05T03:00:00+00:00"}, NOW)
    assert route.model != "gpt-5.6-luna"


def test_command_has_no_usage_or_reset(tmp_path: Path):
    cmd = routing.build_codex_command(routing.Route("gpt-6-astra", "ultra"), tmp_path / "schema.json", tmp_path / "out.json", Path("/root"))
    joined = " ".join(cmd).lower()
    assert "/usage" not in joined
    assert "reset" not in joined
    assert cmd[1:3] == ["--search", "exec"]


def test_limit_retry_parser_uses_observed_provider_error():
    observed = datetime(2026, 9, 5, tzinfo=timezone.utc)
    retry = routing.limit_retry_at("usage_limit_exceeded: try again at Sep 7, 2026 5:05 PM UTC", observed)
    assert retry > observed


def test_production_command_disables_fanout_and_compacts_early(tmp_path: Path):
    project = tmp_path / "projects" / "biella-games"
    cmd = routing.build_codex_command(
        routing.Route("gpt-6-astra", "ultra"),
        tmp_path / "schema.json",
        tmp_path / "out.json",
        project,
    )
    joined = " ".join(cmd)
    assert "--json" in cmd
    assert "--disable multi_agent" in joined
    assert "--disable multi_agent_v2" in joined
    assert 'model_auto_compact_token_limit=96000' in joined
    assert cmd[cmd.index("-C") + 1] == str(project)


def test_resume_command_reuses_existing_task_session(tmp_path: Path):
    cmd = routing.build_codex_resume_command(
        routing.Route("gpt-6-astra", "ultra"),
        tmp_path / "schema.json",
        tmp_path / "out.json",
        "01a07348-9c1c-7760-9f52-76718655365a",
    )
    joined = " ".join(cmd)
    assert "exec resume" in joined
    assert "01a07348-9c1c-7760-9f52-76718655365a" in cmd
    assert "--disable multi_agent" in joined
    assert 'model_auto_compact_token_limit=96000' in joined
    assert "--json" in cmd


def test_single_agent_default_keeps_full_model_and_tool_access(tmp_path: Path):
    route = routing.Route("gpt-6-astra", "ultra")
    cmd = routing.build_codex_command(route, tmp_path / "schema.json", tmp_path / "out.json", tmp_path / "project")
    joined = " ".join(cmd)
    assert "-m gpt-6-astra" in joined
    assert 'model_reasoning_effort="ultra"' in joined
    assert "--search" in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    assert "--disable multi_agent" in joined
    assert "tool_output_token_limit=12000" in joined


def test_one_helper_mode_is_explicit_and_capped(tmp_path: Path):
    route = routing.Route("gpt-6-astra", "ultra")
    cmd = routing.build_codex_command(route, tmp_path / "schema.json", tmp_path / "out.json", tmp_path / "project", allow_helper=True)
    joined = " ".join(cmd)
    pairs = list(zip(cmd, cmd[1:]))
    assert ("--enable", "multi_agent") in pairs
    assert ("--disable", "multi_agent") not in pairs
    assert "max_concurrent_threads_per_session=2" in joined
    assert "max_depth=1" in joined


def test_bounded_fallback_routes_are_explicit_and_strong_routes_are_not():
    assert routing.is_bounded_fallback(routing.Route("gpt-5.3-codex-spark", "xhigh"))
    assert routing.is_bounded_fallback(routing.Route("qwen3-coder-next:biella", "none", "ollama"))
    assert not routing.is_bounded_fallback(routing.Route("gpt-5.6-luna", "max"))
    assert not routing.is_bounded_fallback(routing.Route("gpt-6-astra", "ultra"))


def test_bounded_fallback_models_can_be_excluded_from_broad_planning():
    current = {
        "gpt-5.3-codex-spark": {"xhigh"},
        "qwen3-coder-next:biella": {"local"},
    }
    with __import__("pytest").raises(RuntimeError):
        routing.select_route(
            "deep_memory", current, {}, NOW,
            excluded_models=set(routing.bounded_fallback_models()),
        )


def test_local_provider_compatibility_error_parser_is_bounded_to_local_protocol_faults():
    assert routing.is_local_provider_compatibility_error('"qwen3-coder-next:biella" does not support thinking')
    assert routing.is_local_provider_compatibility_error("failed to decode models response: missing field `models`")
    assert not routing.is_local_provider_compatibility_error("ordinary native process failed")


def test_model_availability_and_stale_catalog_signals_are_distinct_from_runtime_errors():
    assert routing.is_model_unavailable_error("provider says model unavailable")
    assert routing.is_model_unavailable_error("model qwen3-coder-next:biella not found")
    assert routing.is_catalog_stale_error("model catalog is stale and must refresh")
    assert routing.requires_catalog_refresh("the model catalog does not contain this revision")
    assert not routing.requires_catalog_refresh("ordinary native process failed")


def test_account_usage_retry_parser_accepts_ordinal_provider_date():
    observed = datetime(2026, 9, 6, 23, 40, tzinfo=timezone.utc)
    retry = routing.limit_retry_at(
        "You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at Sep 12th, 2026 9:41 PM.",
        observed,
    )
    assert retry == datetime(2026, 9, 12, 21, 41, tzinfo=timezone.utc)
    assert routing.is_account_usage_limit_error("You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage")


def test_all_cloud_cooldowns_route_to_local_ollama_continuity():
    current = catalog()
    current["qwen3-coder-next:biella"] = {"local"}
    cooldowns = {model: "2026-09-12T21:41:00+00:00" for model in routing.cloud_models()}
    route = routing.select_route("hard_creation", current, cooldowns, NOW)
    assert route.model == "qwen3-coder-next:biella"
    assert route.provider == "ollama"
    assert route.reasoning == "none"


def test_account_recovery_routes_luna_then_spark_then_local_even_for_deep_memory():
    current = catalog()
    current["qwen3-coder-next:biella"] = {"local"}
    until = "2026-09-12T21:41:00+00:00"
    cooldowns = {model: until for model in routing.cloud_models() if model not in {"gpt-5.6-luna", "gpt-5.3-codex-spark"}}
    assert routing.select_route("deep_memory", current, cooldowns, NOW) == routing.Route("gpt-5.6-luna", "max")
    cooldowns["gpt-5.6-luna"] = until
    assert routing.select_route("deep_memory", current, cooldowns, NOW) == routing.Route("gpt-5.3-codex-spark", "xhigh")
    cooldowns["gpt-5.3-codex-spark"] = until
    assert routing.select_route("deep_memory", current, cooldowns, NOW) == routing.Route("qwen3-coder-next:biella", "none", "ollama")


def test_local_oss_command_uses_non_reasoning_qwen_catalog_without_web_search_and_disables_plugins(tmp_path: Path, monkeypatch):
    catalog_path = tmp_path / "qwen-codex-model-catalog.json"
    monkeypatch.setenv("BIELLA_CODEX_LOCAL_MODEL_CATALOG", str(catalog_path))
    route = routing.Route("qwen3-coder-next:biella", "none", "ollama")
    cmd = routing.build_codex_command(route, tmp_path / "schema.json", tmp_path / "out.json", tmp_path / "project")
    joined = " ".join(cmd)
    assert cmd[1:4] == ["--oss", "--local-provider", "ollama"]
    assert "--search" not in cmd
    assert "--disable plugins" in joined
    assert 'model_auto_compact_token_limit=12000' in joined
    assert 'tool_output_token_limit=4000' in joined
    assert 'model_reasoning_effort="none"' in joined
    assert f'model_catalog_json="{catalog_path}"' in joined
    assert "--sandbox workspace-write" in joined
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd


def test_spark_bounded_fallback_uses_workspace_write_without_approval_bypass(tmp_path: Path):
    cmd = routing.build_codex_command(
        routing.Route("gpt-5.3-codex-spark", "xhigh"),
        tmp_path / "schema.json", tmp_path / "out.json", tmp_path / "project",
    )
    joined = " ".join(cmd)
    assert "--sandbox workspace-write" in joined
    assert "--skip-git-repo-check" in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd


def test_cloud_production_command_disables_plugins(tmp_path: Path):
    cmd = routing.build_codex_command(
        routing.Route("gpt-6-astra", "ultra"),
        tmp_path / "schema.json",
        tmp_path / "out.json",
        tmp_path / "project",
    )
    assert "--disable plugins" in " ".join(cmd)


def test_discover_catalog_includes_ready_local_ollama_model(monkeypatch):
    class Completed:
        def __init__(self, returncode, stdout):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""
    def fake_run(cmd, **_kwargs):
        if cmd[-2:] == ["debug", "models"]:
            return Completed(0, '{"models":[{"slug":"gpt-6-astra","supported_reasoning_levels":[{"effort":"ultra"}]}]}')
        if cmd[-1:] == ["list"]:
            return Completed(0, "NAME ID SIZE MODIFIED\nqwen3-coder-next:biella abc 52GB now\n")
        raise AssertionError(cmd)
    monkeypatch.setattr(routing.subprocess, "run", fake_run)
    current = routing.discover_catalog()
    assert current["gpt-6-astra"] == {"ultra"}
    assert current["qwen3-coder-next:biella"] == {"local"}


def test_local_resume_command_preserves_session_with_ollama_and_no_plugins(tmp_path: Path):
    route = routing.Route("qwen3-coder-next:biella", "none", "ollama")
    session_id = "01a07480-2c40-7d03-b649-d3f72807cc3e"
    cmd = routing.build_codex_resume_command(route, tmp_path / "schema.json", tmp_path / "out.json", session_id)
    joined = " ".join(cmd)
    assert cmd[1:4] == ["--oss", "--local-provider", "ollama"]
    assert "exec resume" in joined
    assert session_id in cmd
    assert "--disable plugins" in joined
    assert "--search" not in cmd


def test_catalog_discovered_reserve_is_strong_recovery_before_bounded_fallback():
    current = catalog()
    current["gpt-reserve"] = {"low", "medium", "high", "xhigh", "max"}
    until = "2026-09-12T21:41:00+00:00"
    cooldowns = {model: until for model in catalog()}
    route = routing.select_route("hard_creation", current, cooldowns, NOW)
    assert route == routing.Route("gpt-reserve", "max")
    assert not routing.is_bounded_fallback(route)


def test_account_usage_cooldown_is_scoped_to_observed_failed_model():
    assert routing.account_usage_cooldown_models("gpt-6-astra") == ("gpt-6-astra",)
    assert routing.account_usage_cooldown_models("gpt-5.6-luna") == ("gpt-5.6-luna",)
    assert routing.account_usage_cooldown_models("gpt-5.3-codex-spark") == ("gpt-5.3-codex-spark",)


def test_legacy_blanket_cooldowns_are_dropped_but_individual_cooldowns_survive():
    until = "2026-09-12T21:41:00+00:00"
    blanket = {model: until for model in catalog()}
    assert routing.reconcile_legacy_account_cooldowns(blanket) == {}
    individual = {"gpt-6-astra": until, "gpt-5.6-luna": "2026-09-11T10:00:00+00:00"}
    assert routing.reconcile_legacy_account_cooldowns(individual) == individual

def test_owner_forced_reserve_max_is_used_when_catalog_supports_it(monkeypatch):
    current = catalog()
    current["gpt-reserve"] = {"low", "medium", "high", "xhigh", "max"}
    monkeypatch.setenv("BIELLA_CODEX_FORCE_MODEL", "gpt-reserve")
    monkeypatch.setenv("BIELLA_CODEX_FORCE_REASONING", "max")
    assert routing.select_route("hard_creation", current, {}, NOW) == routing.Route("gpt-reserve", "max")


def test_owner_forced_reasoning_fails_closed_when_model_does_not_support_it(monkeypatch):
    current = catalog()
    current["gpt-reserve"] = {"low", "medium", "high", "xhigh", "max"}
    monkeypatch.setenv("BIELLA_CODEX_FORCE_MODEL", "gpt-reserve")
    monkeypatch.setenv("BIELLA_CODEX_FORCE_REASONING", "ultra")
    with __import__("pytest").raises(RuntimeError, match="forced Codex route"):
        routing.select_route("hard_creation", current, {}, NOW)


def test_owner_forced_model_respects_observed_cooldown(monkeypatch):
    current = catalog()
    current["gpt-reserve"] = {"max"}
    monkeypatch.setenv("BIELLA_CODEX_FORCE_MODEL", "gpt-reserve")
    monkeypatch.setenv("BIELLA_CODEX_FORCE_REASONING", "max")
    with __import__("pytest").raises(RuntimeError, match="forced Codex route"):
        routing.select_route("hard_creation", current, {"gpt-reserve": "2026-09-12T21:41:00+00:00"}, NOW)


def test_taskbooster_spark_command_is_read_only_and_schema_bound(tmp_path: Path):
    route = routing.Route("gpt-5.3-codex-spark", "xhigh")
    schema = tmp_path / "booster.schema.json"
    output = tmp_path / "booster.json"
    cmd = routing.build_taskbooster_command(route, schema, output, tmp_path)
    assert cmd[0].endswith("codex")
    assert "--sandbox" in cmd and cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert "workspace-write" not in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
    assert "--dangerously-bypass-hook-trust" not in cmd
    assert "--output-schema" in cmd and cmd[cmd.index("--output-schema") + 1] == str(schema)
    assert "-o" in cmd and cmd[cmd.index("-o") + 1] == str(output)
    assert "--disable" in cmd
    assert "multi_agent" in cmd and "multi_agent_v2" in cmd and "plugins" in cmd
    assert "-m" in cmd and cmd[cmd.index("-m") + 1] == "gpt-5.3-codex-spark"


def test_taskbooster_command_rejects_non_spark_route(tmp_path: Path):
    import pytest
    with pytest.raises(ValueError, match="Spark"):
        routing.build_taskbooster_command(
            routing.Route("gpt-6-astra", "ultra"),
            tmp_path / "schema.json", tmp_path / "out.json", tmp_path,
        )


def test_codex_peer_command_is_read_only_and_single_agent(tmp_path: Path):
    command = routing.build_codex_peer_command(
        routing.Route("gpt-6-astra", "ultra"),
        tmp_path / "peer.schema.json", tmp_path / "peer.result.json", tmp_path,
    )
    joined = " ".join(command)
    assert "--sandbox read-only" in joined
    assert "--disable multi_agent" in joined
    assert "--disable multi_agent_v2" in joined
    assert "--output-schema" in command
    assert command[-1] == "-"
