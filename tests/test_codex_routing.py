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
