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
