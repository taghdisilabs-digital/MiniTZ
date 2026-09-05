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
    }


def test_registry_covers_approved_resource_pool_and_paid_policy():
    registry = resource.load_registry(REGISTRY)
    expected = {"cloudflare", "saturn", "groq", "cerebras", "openrouter", "mistral", "tavily", "exa",
                "pinecone", "qdrant", "deepgram", "assemblyai", "elevenlabs", "stabilityai", "supabase",
                "neon", "upstash", "cloudinary", "axiom", "pexels", "modal", "endpoint"}
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
    assert providers["endpoint"]["state"] == "NOT_CONFIGURED"


def test_capability_routing_prefers_specialized_configured_resources():
    registry = resource.load_registry(REGISTRY)
    env = configured_env()
    assert resource.route_capability(registry, "research.search", env=env)[:2] == ["tavily", "exa"]
    assert resource.route_capability(registry, "research.semantic", env=env)[0] == "exa"
    assert resource.route_capability(registry, "llm.fast", env=env)[:3] == ["groq", "cerebras", "mistral"]


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
    result = resource.run_fast_llm(registry, "classify this", env=configured_env(), transport=transport)
    assert result["provider"] == "groq"
    assert result["model"] == "qwen/qwen3.8-27b"
    assert result["text"] == "compact result"
    assert result["usage"]["total_tokens"] == 16
    assert calls[0][1] == "https://api.groq.com/openai/v1/chat/completions"
    assert "groq-secret" not in json.dumps(result)
