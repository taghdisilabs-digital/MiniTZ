from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/workstation/biella-resource.py"
REGISTRY = ROOT / "ops/workstation/provider-registry.json"
spec = importlib.util.spec_from_file_location("biella_resource", MODULE)
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
    }


def test_registry_covers_approved_resource_pool_and_paid_policy():
    registry = resource.load_registry(REGISTRY)
    expected = {"cloudflare", "saturn", "groq", "cerebras", "openrouter", "mistral", "tavily", "exa",
                "pinecone", "qdrant", "deepgram", "assemblyai", "elevenlabs", "stabilityai", "supabase",
                "neon", "upstash", "cloudinary", "axiom", "pexels", "modal", "gemini"}
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
    assert providers["gemini"]["state"] == "CONFIGURED"
    assert "endpoint" not in providers


def test_capability_routing_prefers_specialized_configured_resources():
    registry = resource.load_registry(REGISTRY)
    env = configured_env()
    assert resource.route_capability(registry, "research.search", env=env)[:2] == ["tavily", "exa"]
    assert resource.route_capability(registry, "research.semantic", env=env)[0] == "exa"
    assert resource.route_capability(registry, "llm.fast", env=env)[:4] == ["ollama-qwen", "groq", "cerebras", "mistral"]


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


def test_gemini_is_routable_as_fast_llm_without_leaking_key():
    registry = resource.load_registry(REGISTRY)
    calls = []
    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        return {"choices": [{"message": {"content": "gemini result"}}], "model": body["model"], "usage": {"total_tokens": 7}}
    result = resource.run_fast_llm(registry, "summarize", env=configured_env(), provider="gemini", model="observed-test-model", transport=transport)
    assert result["provider"] == "gemini"
    assert result["text"] == "gemini result"
    assert calls[0][1].endswith("/v1beta/openai/chat/completions")
    assert calls[0][2]["Authorization"] == "Bearer gemini-secret"
    assert "gemini-secret" not in json.dumps(result)


def test_local_qwen_is_first_class_preferred_compute_resource():
    registry = resource.load_registry(REGISTRY)
    provider = registry["providers"]["ollama-qwen"]
    assert provider["cost_class"] == "local_compute"
    assert provider["default_model"] == "qwen3-coder-next:biella"
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
    )
    assert result["provider"] == "ollama-qwen"
    assert result["model"] == "qwen3-coder-next:biella"
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
