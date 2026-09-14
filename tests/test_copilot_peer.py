from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))

import biella_production_runner as runner
import biella_production_state as state


def load_main_coder():
    path = LOCAL_AI / "biella_main_coder.py"
    spec = importlib.util.spec_from_file_location("copilot_peer_main_coder", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_copilot_session_id_is_stable_and_task_digest_bound():
    main = load_main_coder()
    a = main.copilot_session_id("minitz", "CODEX-L40-BRIDGE-01", "a" * 64, "native")
    b = main.copilot_session_id("minitz", "CODEX-L40-BRIDGE-01", "a" * 64, "native")
    changed = main.copilot_session_id("minitz", "CODEX-L40-BRIDGE-01", "b" * 64, "native")
    qwen = main.copilot_session_id("minitz", "CODEX-L40-BRIDGE-01", "a" * 64, "local-qwen")
    assert a == b
    assert a != changed
    assert a != qwen
    assert len(a) == 36


def test_copilot_peer_command_is_noninteractive_and_denies_mutation(tmp_path: Path):
    main = load_main_coder()
    command = main.build_copilot_peer_command(
        "return strict json", "00000000-0000-0000-0000-000000000001", tmp_path,
        read_dirs=(tmp_path / "memory", tmp_path / "projection"),
    )
    joined = " ".join(command)
    assert command[0].endswith("copilot")
    assert "-p return strict json" in joined
    assert "--session-id 00000000-0000-0000-0000-000000000001" in joined
    assert "--no-ask-user" in command
    assert "--silent" in command
    assert "--allow-all-tools" in command
    assert "--deny-tool=write" in command
    assert "--deny-tool=shell" in command
    assert command.count("--add-dir") == 2


def test_copilot_local_qwen_env_is_keyless_and_drops_other_provider_secrets():
    main = load_main_coder()
    env = main.copilot_peer_env(
        "local-qwen",
        {"PATH": os.environ.get("PATH", ""), "COPILOT_PROVIDER_API_KEY": "must-not-survive", "COPILOT_PROVIDER_BEARER_TOKEN": "must-not-survive"},
    )
    assert env["COPILOT_PROVIDER_BASE_URL"] == "http://127.0.0.1:11434/v1"
    assert env["COPILOT_PROVIDER_TYPE"] == "openai"
    assert env["COPILOT_MODEL"] == "qwen3-coder-next:biella"
    assert "COPILOT_PROVIDER_API_KEY" not in env
    assert "COPILOT_PROVIDER_BEARER_TOKEN" not in env


def test_copilot_observation_classifies_without_quota_probe():
    main = load_main_coder()
    assert main.classify_copilot_observation(0, '{"status":"USEFUL"}') == "ACTIVE"
    assert main.classify_copilot_observation(1, "You've hit your usage limit") == "OUT_OF_CREDIT"
    assert main.classify_copilot_observation(127, "copilot: command not found") == "OFFLINE"
    assert main.classify_copilot_observation(1, "authentication required") == "NEEDS_MODIFICATION"


def test_coder_selection_prefers_copilot_as_codex_peer():
    main = load_main_coder()
    selection = main.select_coder_roles(
        {"codex": "ACTIVE", "copilot": "ACTIVE", "agr": "ACTIVE"}, current_writer="codex"
    )
    assert selection.primary == "codex"
    assert selection.peer == "copilot"


def test_runner_selects_copilot_peer_before_agr(monkeypatch, tmp_path: Path):
    task = state.TaskRecord("T-PEER", "medium", "Peer task", "WORKING", (), "minitz")
    monkeypatch.setattr(runner, "_select_task_route", lambda *_a, **_k: (runner.routing.Route("gpt-5.5", "high", "openai"), None))
    monkeypatch.setattr(runner.main_coder, "copilot_candidate_available", lambda: True)
    telemetry = {"active_coder": "codex", "coder_statuses": {"copilot": "ACTIVE", "agr": "ACTIVE"}, "cooldowns": {}}
    coder, route, packet, peer = runner._select_main_task_route(
        task, {"gpt-5.5": {"high"}}, {"claude-sonnet-4-6"}, telemetry,
        datetime.now(timezone.utc), tmp_path, tmp_path,
    )
    assert coder == "codex"
    assert route and route.provider == "openai"
    assert packet is None
    assert peer == "copilot"


def test_runner_does_not_auto_route_copilot_qwen_when_profile_is_unqualified(monkeypatch, tmp_path: Path):
    task = state.TaskRecord("T-PEER", "medium", "Peer task", "WORKING", (), "minitz")
    monkeypatch.setattr(runner.main_coder, "copilot_local_qwen_candidate_available", lambda _env=None: False)
    route = runner._select_main_coder_peer_route(
        "copilot-qwen", task, {}, set(), {"coder_statuses": {}},
        datetime.now(timezone.utc), tmp_path, tmp_path,
    )
    assert route is None


def test_runner_builds_copilot_peer_routes(monkeypatch, tmp_path: Path):
    task = state.TaskRecord("T-PEER", "medium", "Peer task", "WORKING", (), "minitz")
    telemetry = {"coder_statuses": {"copilot": "ACTIVE", "copilot-qwen": "ACTIVE"}, "cooldowns": {}}
    native = runner._select_main_coder_peer_route(
        "copilot", task, {}, set(), telemetry, datetime.now(timezone.utc), tmp_path, tmp_path
    )
    assert native and native.provider == "copilot" and native.model == "github-copilot-auto"


def test_launch_copilot_peer_uses_read_only_command_and_native_env(monkeypatch, tmp_path: Path):
    task = state.TaskRecord("T-PEER", "medium", "Peer task", "WORKING", (), "minitz")
    runtime = tmp_path / "runtime"
    capsule = runtime / "task-memory/T-PEER.json"
    projection = runtime / "memory/current-task.json"
    capsule.parent.mkdir(parents=True); projection.parent.mkdir(parents=True)
    capsule.write_text('{"task_id":"T-PEER","scope_ref":"task://minitz/T-PEER/1"}\n')
    projection.write_text('{"task_id":"T-PEER"}\n')
    captured = {}

    class FakeProcess:
        stdin = None
        def poll(self): return None

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs.get("env") or {}
        captured["cwd"] = kwargs.get("cwd")
        return FakeProcess()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner.main_coder, "shared_policy_paths", lambda *_a: ())
    inflight = {}
    launched = runner._launch_main_coder_peer_assist(
        tmp_path, tmp_path, runtime, task, "a" * 64,
        primary_coder="codex", peer_coder="copilot",
        peer_route=runner.routing.Route("github-copilot-auto", "none", "copilot"),
        capsule_path=capsule, projection_path=projection, inflight=inflight,
    )
    assert launched is True
    joined = " ".join(captured["command"])
    assert "--deny-tool=write" in captured["command"]
    assert "--deny-tool=shell" in captured["command"]
    assert "READ_ONLY_PEER_ASSIST" in joined
    assert "COPILOT_PROVIDER_BASE_URL" not in captured["env"]
    assert len(inflight) == 1


def test_collect_copilot_peer_accepts_silent_schema_json(tmp_path: Path):
    root = tmp_path / "peer"
    root.mkdir()
    stdout = root / "x.stdout.log"
    stderr = root / "x.stderr.log"
    output = root / "x.result.json"
    accepted = root / "x.accepted.json"
    stdout.write_text('{"status":"USEFUL","summary":"ok","findings":["f"],"evidence_refs":["e"],"candidate_actions":["a"]}\n')
    stderr.write_text("")

    class Done:
        def poll(self): return 0

    handle = runner.MainCoderPeerHandle(
        "k", "copilot", "github-copilot-auto", "minitz", "T-PEER", "a" * 64,
        Done(), output, stdout, stderr, accepted,
    )
    inflight = {"k": handle}
    telemetry = {"coder_statuses": {}}
    runner._collect_main_coder_peer_assists(inflight, telemetry)
    assert accepted.is_file()
    payload = __import__("json").loads(accepted.read_text())
    assert payload["peer_coder"] == "copilot"
    assert payload["result"]["status"] == "USEFUL"
    assert telemetry["coder_statuses"]["copilot"] == "ACTIVE"
    assert inflight == {}


def test_collect_copilot_peer_classifies_usage_limit(tmp_path: Path):
    root = tmp_path / "peer"
    root.mkdir()
    stdout = root / "x.stdout.log"; stdout.write_text("")
    stderr = root / "x.stderr.log"; stderr.write_text("You've hit your usage limit\n")
    output = root / "x.result.json"
    accepted = root / "x.accepted.json"

    class Done:
        def poll(self): return 1

    handle = runner.MainCoderPeerHandle(
        "k", "copilot", "github-copilot-auto", "minitz", "T-PEER", "a" * 64,
        Done(), output, stdout, stderr, accepted,
    )
    inflight = {"k": handle}
    telemetry = {"coder_statuses": {}}
    runner._collect_main_coder_peer_assists(inflight, telemetry)
    assert telemetry["coder_statuses"]["copilot"] == "OUT_OF_CREDIT"
    assert accepted.with_name("x.rejected.json").is_file()


def test_minitz_task_packet_exposes_ai_peer_resource_without_authority(tmp_path: Path):
    import biella_task_packet as packets
    task = state.TaskRecord(
        "T-PEER", "medium", "Peer task", "WORKING",
        ("MINITZ_TASK_REVISION:2", "MINITZ_TASK_SHA256:" + "a" * 64), "minitz",
    )
    production = state.ProductionState(
        tmp_path, "IN_PROGRESS", "minitz", task.id,
        [state.SectionRecord("minitz", "MiniTZ", "IN_PROGRESS", [task])],
        run_id="minitz-task-program", priority_policy="MINITZ_TASK_PROGRAM",
    )
    packet = packets.compile_task_packet(tmp_path, production, task)
    assert "AI peer" in packet
    assert "Copilot+Cloudflare" in packet
    assert "direct local Qwen" in packet
    assert "authority NONE" in packet
    assert "cannot complete or advance" in packet


def test_peer_prompt_contains_strict_json_contract_for_copilot(tmp_path: Path):
    main = load_main_coder()
    prompt = main.peer_assist_prompt(
        task_id="T-PEER", title="Peer task", task_state_digest="a" * 64,
        capsule_path=tmp_path / "task.json", projection_path=tmp_path / "projection.json",
        policy_paths=(), primary_coder="codex", peer_coder="copilot",
    )
    assert "STRICT_JSON_ONLY" in prompt
    assert '"status"' in prompt
    assert '"summary"' in prompt
    assert '"findings"' in prompt
    assert '"evidence_refs"' in prompt
    assert '"candidate_actions"' in prompt
    assert "NO_FINDING" in prompt and "USEFUL" in prompt


def test_copilot_cloudflare_env_scopes_existing_credential_to_peer():
    main = load_main_coder()
    env = main.copilot_peer_env(
        "cloudflare",
        {
            "PATH": os.environ.get("PATH", ""),
            "CLOUDFLARE_ACCOUNT_ID": "acct-safe-id",
            "CLOUDFLARE_API_TOKEN": "protected-token-value",
            "COPILOT_PROVIDER_API_KEY": "stale-value",
        },
    )
    assert env["COPILOT_PROVIDER_BASE_URL"] == "https://api.cloudflare.com/client/v4/accounts/acct-safe-id/ai/v1"
    assert env["COPILOT_PROVIDER_TYPE"] == "openai"
    assert env["COPILOT_PROVIDER_API_KEY"] == "protected-token-value"
    assert env["COPILOT_MODEL"] == "@cf/moonshotai/kimi-k2.7-code"
    assert "CLOUDFLARE_API_TOKEN" not in env


def test_copilot_cloudflare_env_requires_existing_protected_credential():
    main = load_main_coder()
    import pytest
    with pytest.raises(ValueError, match="Cloudflare credential"):
        main.copilot_peer_env(
            "cloudflare",
            {"PATH": os.environ.get("PATH", ""), "BIELLA_AI_RUNTIME_ENV": "/definitely/missing/minitz-runtime.env"},
        )


def test_runner_uses_cloudflare_copilot_after_native_failure_not_qwen(monkeypatch, tmp_path: Path):
    task = state.TaskRecord("T-PEER", "medium", "Peer task", "WORKING", (), "minitz")
    monkeypatch.setattr(runner, "_select_task_route", lambda *_a, **_k: (runner.routing.Route("gpt-5.5", "high", "openai"), None))
    monkeypatch.setattr(runner.main_coder, "copilot_candidate_available", lambda: True)
    monkeypatch.setattr(runner.main_coder, "copilot_cloudflare_candidate_available", lambda _env=None: True)
    telemetry = {
        "active_coder": "codex",
        "coder_statuses": {"copilot": "OUT_OF_CREDIT", "agr": "NEEDS_MODIFICATION"},
        "cooldowns": {},
    }
    coder, _route, _packet, peer = runner._select_main_task_route(
        task, {"gpt-5.5": {"high"}}, set(), telemetry,
        datetime.now(timezone.utc), tmp_path, tmp_path,
    )
    assert coder == "codex"
    assert peer == "copilot-cloudflare"


def test_runner_builds_cloudflare_copilot_peer_route(monkeypatch, tmp_path: Path):
    task = state.TaskRecord("T-PEER", "medium", "Peer task", "WORKING", (), "minitz")
    monkeypatch.setattr(runner.main_coder, "copilot_cloudflare_candidate_available", lambda _env=None: True)
    telemetry = {"coder_statuses": {"copilot-cloudflare": "ACTIVE"}, "cooldowns": {}}
    route = runner._select_main_coder_peer_route(
        "copilot-cloudflare", task, {}, set(), telemetry, datetime.now(timezone.utc), tmp_path, tmp_path
    )
    assert route and route.provider == "copilot-cloudflare"
    assert route.model == "@cf/moonshotai/kimi-k2.7-code"


def test_cloudflare_peer_reads_only_required_values_from_protected_backend(tmp_path: Path):
    main = load_main_coder()
    protected = tmp_path / "runtime.env"
    protected.write_text(
        "CLOUDFLARE_ACCOUNT_ID=acct-from-store\n"
        "CLOUDFLARE_API_TOKEN=protected-store-token\n"
        "GROQ_API_KEY=must-not-enter-peer\n",
        encoding="utf-8",
    )
    base = {"PATH": os.environ.get("PATH", ""), "BIELLA_AI_RUNTIME_ENV": str(protected)}
    assert main.copilot_cloudflare_candidate_available(base) is True
    env = main.copilot_peer_env("cloudflare", base)
    assert env["COPILOT_PROVIDER_BASE_URL"].endswith("/acct-from-store/ai/v1")
    assert env["COPILOT_PROVIDER_API_KEY"] == "protected-store-token"
    assert "CLOUDFLARE_API_TOKEN" not in env
    assert "GROQ_API_KEY" not in env
    assert "BIELLA_AI_RUNTIME_ENV" not in env
