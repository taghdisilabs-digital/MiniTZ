from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/workstation/minitz-resource.py"
REGISTRY = ROOT / "ops/workstation/provider-registry.json"
spec = importlib.util.spec_from_file_location("minitz_resource", MODULE)
assert spec and spec.loader
resource = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = resource
spec.loader.exec_module(resource)


def configured_env() -> dict[str, str]:
    return {
        "TAVILY_API_KEY": "tavily-secret",
        "EXA_API_KEY": "exa-secret",
        "GROQ_API_KEY": "groq-secret",
        "CEREBRAS_API_KEY": "cerebras-secret",
        "MISTRAL_API_KEY": "mistral-secret",
        "OPENROUTER_API_KEY": "openrouter-secret",
        "SUPABASE_PUBLISHABLE_KEY": "supabase-secret",
        "GEMINI_API_KEY": "gemini-secret",
        "MINITZ_RESOURCE_LOOP_STATE_PATH": f"/tmp/minitz-test-resource-loop-{uuid4().hex}.json",
    }


def test_registry_covers_approved_resource_pool_and_paid_policy():
    registry = resource.load_registry(REGISTRY)
    expected = {"cloudflare", "saturn", "groq", "cerebras", "openrouter", "mistral", "tavily", "exa",
                "pinecone", "qdrant", "deepgram", "assemblyai", "elevenlabs", "stabilityai", "supabase",
                "neon", "upstash", "cloudinary", "axiom", "pexels", "modal"}
    assert expected <= set(registry["providers"])
    assert registry["policy"]["paid_allowed"] is True
    assert registry["policy"]["free_credit_preferred"] is True


def test_status_never_emits_secret_values_and_missing_locator_is_explicit():
    registry = resource.load_registry(REGISTRY)
    env = configured_env()
    payload = resource.status_payload(registry, env=env, command_exists=lambda _: True)
    encoded = json.dumps(payload, sort_keys=True)
    for secret in env.values():
        assert secret not in encoded
    providers = {item["id"]: item for item in payload["providers"]}
    assert providers["groq"]["state"] == "CONFIGURED"
    assert providers["supabase"]["state"] == "NEEDS_LOCATOR"
    assert "endpoint" not in providers


def test_capability_routing_prefers_specialized_configured_resources():
    registry = resource.load_registry(REGISTRY)
    env = configured_env()
    assert resource.route_capability(registry, "research.search", env=env)[:2] == ["tavily", "exa"]
    assert resource.route_capability(registry, "research.semantic", env=env)[0] == "exa"
    assert resource.route_capability(registry, "llm.fast", env=env, command_exists=lambda _: True)[:4] == ["ollama-qwen", "groq", "cerebras", "mistral"]


def test_search_uses_tavily_and_compacts_provider_response():
    registry = resource.load_registry(REGISTRY)
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        return {"results": [
            {"title": "One", "url": "https://example.test/1", "content": "A" * 2000, "score": 0.9},
            {"title": "Two", "url": "https://example.test/2", "content": "B", "score": 0.8},
        ]}
    result = resource.run_search(registry, "unreal build", env=configured_env(), limit=2, transport=transport)
    assert result["provider"] == "tavily"
    assert result["capability"] == "research.search"
    assert len(result["results"]) == 2
    assert len(result["results"][0]["text"]) <= 900
    assert calls[0][1] == "https://api.tavily.com/search"
    assert "tavily-secret" not in json.dumps(result)


def test_fast_llm_uses_observed_default_and_returns_compact_usage():
    registry = resource.load_registry(REGISTRY)
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        return {
            "choices": [{"message": {"content": "compact result"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
            "model": body["model"],
        }
    result = resource.run_fast_llm(registry, "classify this", env=configured_env(), provider="groq", transport=transport)
    assert result["provider"] == "groq"
    assert result["model"] == "qwen/qwen3.8-27b"
    assert result["text"] == "compact result"
    assert result["usage"]["total_tokens"] == 16
    assert calls[0][1] == "https://api.groq.com/openai/v1/chat/completions"
    assert "groq-secret" not in json.dumps(result)


def test_owner_excluded_gemini_is_not_routable_even_with_key():
    registry = resource.load_registry(REGISTRY)
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        return {"choices": [{"message": {"content": "gemini result"}}], "model": body["model"], "usage": {"total_tokens": 7}}
    try:
        resource.run_fast_llm(registry, "summarize", env=configured_env(), provider="gemini", model="observed-test-model", transport=transport)
    except resource.ResourceError as exc:
        assert exc.failure_code == "RESOURCE_ERROR"
    else:
        raise AssertionError("Google Gemini executed despite owner exclusion")
    assert calls == []





def test_fast_llm_structured_output_controls_are_forwarded_to_provider():
    registry = resource.load_registry(REGISTRY)
    env = configured_env() | {
        "CLOUDFLARE_ACCOUNT_ID": "fixture-account",
        "CLOUDFLARE_API_TOKEN": "cloudflare-secret",
    }
    schema = {"type": "object", "required": ["status"], "properties": {"status": {"type": "string"}}}
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        return {"choices": [{"message": {"content": '{"status":"ok"}'}}], "model": body["model"], "usage": {"total_tokens": 9}}
    result = resource.run_fast_llm(
        registry, "return structured output", env=env, provider="cloudflare",
        command_exists=lambda _command: False, transport=transport,
        response_schema=schema, disable_reasoning=True,
    )
    assert result["text"] == '{"status":"ok"}'
    body = calls[0][3]
    assert body["response_format"] == {"type": "json_schema", "json_schema": {"name": "minitz_response", "strict": True, "schema": schema}}
    assert body["chat_template_kwargs"] == {"thinking": False}


def test_fast_llm_cli_forwards_structured_output_controls(monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(resource, "load_registry", lambda _path=REGISTRY: {"providers": {}, "routes": {}})
    def fake_run(registry, prompt, **kwargs):
        seen.update(kwargs)
        return {"provider":"cloudflare","model":"test","text":"{}","usage":{},"routing_evidence":{}}
    monkeypatch.setattr(resource, "run_fast_llm", fake_run)
    schema = '{"type":"object"}'
    assert resource.main([
        "fast-llm", "--prompt", "structured", "--provider", "cloudflare",
        "--response-schema-json", schema, "--disable-reasoning",
    ]) == 0
    assert seen["response_schema"] == {"type":"object"}
    assert seen["disable_reasoning"] is True
    assert json.loads(capsys.readouterr().out)["provider"] == "cloudflare"

def test_fast_llm_cli_forwards_explicit_timeout_seconds(monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(resource, "load_registry", lambda _path=REGISTRY: {"providers": {}, "routes": {}})
    def fake_run(registry, prompt, **kwargs):
        seen.update(kwargs)
        return {"provider":"ollama-qwen","model":"qwen","text":"ok","usage":{},"routing_evidence":{}}
    monkeypatch.setattr(resource, "run_fast_llm", fake_run)
    assert resource.main(["fast-llm", "--prompt", "bounded", "--provider", "ollama-qwen", "--timeout-seconds", "80"]) == 0
    assert seen["timeout"] == 80.0
    assert json.loads(capsys.readouterr().out)["provider"] == "ollama-qwen"


def test_fast_llm_rejects_empty_assistant_content_as_retryable_protocol_failure():
    registry = resource.load_registry(REGISTRY)
    env = configured_env()
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append(url)
        return {"choices": [{"message": {"content": ""}}], "model": body["model"], "usage": {"total_tokens": 512}}
    try:
        resource.run_fast_llm(
            registry, "structured output", env=env, provider="groq",
            command_exists=lambda _command: False, transport=transport,
            max_failover_attempts=1,
        )
    except resource.ResourceError as exc:
        assert exc.failure_code == "ROUTE_EXHAUSTED"
        assert exc.evidence["attempted"][0]["failure_code"] == "PROTOCOL_ERROR"
    else:
        raise AssertionError("empty assistant content must not count as success")
    assert len(calls) == 1


def test_cloudflare_default_model_is_qualified_structured_work_model():
    registry = resource.load_registry(REGISTRY)
    assert registry["providers"]["cloudflare"]["default_model"] == "@cf/moonshotai/kimi-k2.7-code"

def test_cloudflare_workers_ai_is_routed_as_paid_fast_code_and_reasoning_resource(tmp_path):
    registry = resource.load_registry(REGISTRY)
    env = configured_env() | {
        "CLOUDFLARE_ACCOUNT_ID": "fixture-account",
        "CLOUDFLARE_API_TOKEN": "cloudflare-secret",
        "MINITZ_RESOURCE_LOOP_STATE_PATH": str(tmp_path / "rotation.json"),
    }
    for capability in ("llm.fast", "llm.code", "llm.reasoning"):
        routed = resource.route_capability(
            registry, capability, env=env, command_exists=lambda command: command == "ollama"
        )
        assert routed[:2] == ["ollama-qwen", "cloudflare"]
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        return {
            "choices": [{"message": {"content": "cloud result"}}],
            "model": body["model"],
            "usage": {"total_tokens": 13},
        }
    result = resource.run_fast_llm(
        registry, "analyze bounded task", env=env, provider="cloudflare",
        command_exists=lambda command: command == "ollama", transport=transport,
    )
    assert result["provider"] == "cloudflare"
    assert result["text"] == "cloud result"
    assert calls[0][1] == "https://api.cloudflare.com/client/v4/accounts/fixture-account/ai/v1/chat/completions"
    assert calls[0][2]["Authorization"] == "Bearer cloudflare-secret"
    assert "cloudflare-secret" not in json.dumps(result)


def test_external_resource_policy_strings_do_not_disable_configured_resources():
    registry = resource.load_registry(REGISTRY)
    env = configured_env() | {
        "CLOUDFLARE_ACCOUNT_ID": "fixture-account",
        "CLOUDFLARE_API_TOKEN": "cloudflare-secret",
        "MINITZ_EXTERNAL_RESOURCE_POLICY": "BLOCKED",
    }
    routed = resource.route_capability(
        registry, "llm.fast", env=env, command_exists=lambda command: command == "ollama"
    )
    assert "cloudflare" in routed
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append(url)
        return {"choices": [{"message": {"content": "ok"}}], "model": body["model"], "usage": {}}
    result = resource.run_fast_llm(
        registry, "configured resource stays eligible", env=env, provider="cloudflare",
        command_exists=lambda command: command == "ollama", transport=transport,
        max_failover_attempts=1,
    )
    assert result["provider"] == "cloudflare"
    assert len(calls) == 1

def test_local_qwen_is_first_class_preferred_compute_resource():
    registry = resource.load_registry(REGISTRY)
    provider = registry["providers"]["ollama-qwen"]
    assert provider["cost_class"] == "local_compute"
    assert provider["default_model"] == "qwen3-coder-next:minitz"
    for capability in ("llm.fast", "llm.code", "llm.reasoning", "unreal.assist"):
        assert resource.route_capability(registry, capability, env={}, command_exists=lambda command: command == "ollama")[0] == "ollama-qwen"


def test_local_qwen_fast_llm_uses_local_openai_endpoint_without_secret():
    registry = resource.load_registry(REGISTRY)
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        return {"choices": [{"message": {"content": "local result"}}], "model": body["model"], "usage": {"total_tokens": 9}}
    result = resource.run_fast_llm(
        registry, "review this bounded code", env={}, provider="ollama-qwen",
        command_exists=lambda command: command == "ollama", transport=transport,
        local_admission=lambda: {"allowed": True, "reason": "UNIT_TRANSPORT_TEST"},
    )
    assert result["provider"] == "ollama-qwen"
    assert result["model"] == "qwen3-coder-next:minitz"
    assert result["text"] == "local result"
    assert calls[0][1] == "http://127.0.0.1:11434/v1/chat/completions"
    assert calls[0][2] == {}


def test_fast_llm_uses_bounded_capability_equivalent_failover_with_evidence():
    registry = resource.load_registry(REGISTRY)
    calls = []

    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        if "api.groq.com" in url:
            raise resource.ResourceError("provider unavailable", failure_code="TRANSPORT_ERROR", retryable=True)
        return {
            "choices": [{"message": {"content": "fallback result"}}],
            "usage": {"total_tokens": 11},
            "model": body["model"],
        }

    result = resource.run_fast_llm(
        registry,
        "bounded failover",
        env=configured_env(),
        provider="groq",
        command_exists=lambda _command: False,
        transport=transport,
        max_failover_attempts=2,
    )

    assert result["provider"] == "cerebras"
    assert [call[1] for call in calls] == [
        "https://api.groq.com/openai/v1/chat/completions",
        "https://api.cerebras.ai/v1/chat/completions",
    ]
    evidence = result["routing_evidence"]
    assert evidence["authority"] == "RESOURCE_IMPLEMENTATION"
    assert evidence["capability"] == "llm.fast"
    assert evidence["attempt_limit"] == 2
    assert evidence["fallback_used"] is True
    assert evidence["attempted"] == [
        {"provider": "groq", "model": None, "status": "FAILED", "failure_code": "TRANSPORT_ERROR"},
        {"provider": "cerebras", "model": "qwen-3.8-27b", "status": "SUCCEEDED"},
    ]
    assert "groq-secret" not in json.dumps(result)
    assert "cerebras-secret" not in json.dumps(result)


def test_fast_llm_does_not_fan_out_for_unclassified_adapter_failure():
    registry = resource.load_registry(REGISTRY)
    calls = []

    def transport(method, url, headers, body, timeout):
        calls.append(url)
        raise resource.ResourceError("adapter invariant failed")

    try:
        resource.run_fast_llm(
            registry,
            "no retry",
            env=configured_env(),
            provider="groq",
            transport=transport,
            max_failover_attempts=3,
        )
    except resource.ResourceError as exc:
        assert exc.failure_code == "ROUTE_EXHAUSTED"
        assert len(exc.evidence["attempted"]) == 1
    else:
        raise AssertionError("expected bounded route failure")
    assert calls == ["https://api.groq.com/openai/v1/chat/completions"]


def test_fast_llm_respects_explicit_non_retryable_resource_failure():
    registry = resource.load_registry(REGISTRY)
    calls = []

    def transport(method, url, headers, body, timeout):
        calls.append(url)
        raise resource.ResourceError("provider unavailable", failure_code="AUTHORIZATION", retryable=False)

    try:
        resource.run_fast_llm(
            registry,
            "no auth retry",
            env=configured_env(),
            provider="groq",
            transport=transport,
            max_failover_attempts=3,
        )
    except resource.ResourceError as exc:
        assert exc.failure_code == "ROUTE_EXHAUSTED"
        assert exc.evidence["attempted"] == [
            {"provider": "groq", "model": None, "status": "FAILED", "failure_code": "AUTHORIZATION"},
        ]
    else:
        raise AssertionError("expected bounded route failure")
    assert calls == ["https://api.groq.com/openai/v1/chat/completions"]


def test_fast_llm_cli_forwards_explicit_single_provider_attempt(monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(resource, "load_registry", lambda _path=REGISTRY: {"providers": {}, "routes": {}})
    def fake_run(registry, prompt, **kwargs):
        seen.update(kwargs)
        return {"provider":"groq","model":"test","text":"ok","usage":{},"routing_evidence":{}}
    monkeypatch.setattr(resource, "run_fast_llm", fake_run)
    assert resource.main(["fast-llm", "--prompt", "bounded", "--provider", "groq", "--max-failover-attempts", "1"]) == 0
    assert seen["provider"] == "groq"
    assert seen["max_failover_attempts"] == 1
    assert json.loads(capsys.readouterr().out)["provider"] == "groq"


def test_resource_loop_owner_authorized_state_rotates_equivalent_providers(tmp_path):
    registry = resource.load_registry(REGISTRY)
    loop = registry["policy"]["resource_loop"]
    assert loop["state"] == "ACTIVE_OWNER_AUTHORIZED"
    assert loop["automatic_dispatch"] is True
    assert loop["explicit_owner_start_required"] is False
    env = configured_env() | {"MINITZ_RESOURCE_LOOP_STATE_PATH": str(tmp_path / "rotation.json")}
    assert resource.route_capability(registry, "research.search", env=env) == ["tavily", "exa"]
    assert resource.route_capability(registry, "research.search", env=env) == ["exa", "tavily"]
    assert resource.route_capability(registry, "research.search", env=env) == ["tavily", "exa"]
    assert (tmp_path / "rotation.json").is_file()


def test_active_resource_loop_rotates_equivalent_providers_before_reuse(tmp_path):
    registry = resource.load_registry(REGISTRY)
    registry = json.loads(json.dumps(registry))
    registry["policy"]["resource_loop"]["state"] = "ACTIVE"
    registry["policy"]["resource_loop"]["automatic_dispatch"] = True
    env = configured_env() | {"MINITZ_RESOURCE_LOOP_STATE_PATH": str(tmp_path / "rotation.json")}
    assert resource.route_capability(registry, "research.search", env=env) == ["tavily", "exa"]
    assert resource.route_capability(registry, "research.search", env=env) == ["exa", "tavily"]
    assert resource.route_capability(registry, "research.search", env=env) == ["tavily", "exa"]


def test_resource_loop_declares_equivalent_pools_and_passive_quota_policy():
    registry = resource.load_registry(REGISTRY)
    policy = registry["policy"]
    assert policy["quota_probe_forbidden"] is True
    assert policy["generation_probe_forbidden"] is True
    assert policy["quota_observation"] == "PASSIVE_RECEIPTS_OR_NON_BILLABLE_METADATA_ONLY"
    pools = registry["equivalent_provider_pools"]
    assert pools["research.search"] == ["tavily", "exa"]
    assert set(pools["compute.remote"]) == {"saturn", "modal"}
    assert set(pools["vector.search"]) == {"qdrant", "pinecone"}

def test_nvidia_provider_is_openai_compatible_and_uses_protected_api_key():
    registry = json.loads((ROOT / "ops/workstation/provider-registry.json").read_text())
    provider = registry["providers"]["nvidia"]
    assert provider["chat_url"] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert provider["required_env"] == ["NVIDIA_API_KEY"]
    assert "llm.code" in provider["capabilities"]
    assert "nvidia" in registry["routes"]["llm.code"]
    assert "nvidia" in registry["routes"]["llm.fast"]
    assert resource._bearer_key("nvidia") == "NVIDIA_API_KEY"


def test_nvidia_api_key_is_configured_only_through_secret_prompt():
    configure = (ROOT / "ops/workstation/minitz-provider-configure.sh").read_text()
    assert "ask_secret NVIDIA_API_KEY 'NVIDIA API key'" in configure


def test_local_priority_survives_repeated_resource_rotation(tmp_path):
    registry = resource.load_registry(REGISTRY)
    env = configured_env() | {"MINITZ_RESOURCE_LOOP_STATE_PATH": str(tmp_path / "rotation.json")}
    orders = [resource.route_capability(registry, "llm.fast", env=env, command_exists=lambda c: c == "ollama") for _ in range(8)]
    assert all(order[0] == "ollama-qwen" for order in orders)
    assert len({order[1] for order in orders}) > 1


def test_resource_default_registry_does_not_reactivate_donor_source():
    assert resource._CANONICAL_REGISTRY == Path("/root/attached-storage/minitz-os-sandbox/workspace/repo/ops/workstation/provider-registry.json")


def test_fast_llm_selects_equivalent_order_only_once(monkeypatch):
    registry = resource.load_registry(REGISTRY)
    calls = []
    def route(*args, **kwargs):
        calls.append(1)
        return ["groq", "mistral"]
    def transport(method, url, headers, body, timeout):
        return {"choices":[{"message":{"content":"useful"}}],"model":body["model"]}
    monkeypatch.setattr(resource, "route_capability", route)
    result = resource.run_fast_llm(registry, "bounded", env=configured_env(), transport=transport)
    assert result["provider"] == "groq"
    assert len(calls) == 1




def test_removed_google_model_family_cannot_use_another_provider():
    registry = resource.load_registry(REGISTRY)
    calls = []
    def transport(*args):
        calls.append(args)
        return {"choices":[{"message":{"content":"wrong route"}}],"model":"google/removed-model"}
    try:
        resource.run_fast_llm(registry, "bounded", env=configured_env(), provider="openrouter", model="google/removed-model", transport=transport)
    except resource.ResourceError as exc:
        assert exc.failure_code == "OWNER_DISABLED"
    else:
        raise AssertionError("Removed Google model executed through a proxy")
    assert calls == []
