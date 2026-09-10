#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

REGISTRY_PATH = Path(__file__).with_name("provider-registry.json")
Transport = Callable[[str, str, Mapping[str, str], Mapping[str, Any] | None, float], Mapping[str, Any]]


class ResourceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        failure_code: str = "RESOURCE_ERROR",
        retryable: bool = False,
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_code = str(failure_code)
        self.retryable = bool(retryable)
        self.evidence = dict(evidence or {})


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "biella.provider_registry/v1" or not isinstance(data.get("providers"), dict):
        raise ResourceError("invalid provider registry")
    return data


def _present(env: Mapping[str, str], name: str) -> bool:
    return bool(str(env.get(name, "")).strip())


def provider_state(provider: Mapping[str, Any], *, env: Mapping[str, str], command_exists: Callable[[str], bool] | None = None) -> str:
    command_exists = command_exists or (lambda command: shutil.which(command) is not None)
    command = provider.get("command")
    if command and not command_exists(str(command)):
        return "NOT_CONFIGURED"
    required = [str(item) for item in provider.get("required_env", [])]
    if any(not _present(env, item) for item in required):
        return "NOT_CONFIGURED"
    locators = [str(item) for item in provider.get("locator_env", [])]
    if any(not _present(env, item) for item in locators):
        return "NEEDS_LOCATOR"
    return "CONFIGURED"


def status_payload(registry: Mapping[str, Any], *, env: Mapping[str, str] | None = None,
                   command_exists: Callable[[str], bool] | None = None) -> dict[str, Any]:
    env = env or os.environ
    items = []
    for provider_id, provider in registry["providers"].items():
        items.append({
            "id": provider_id,
            "display_name": provider.get("display_name", provider_id),
            "state": provider_state(provider, env=env, command_exists=command_exists),
            "capabilities": list(provider.get("capabilities", [])),
            "cost_class": provider.get("cost_class", "unknown"),
            "authority": provider.get("authority", "RESOURCE_IMPLEMENTATION"),
        })
    return {"schema": registry["schema"], "policy": dict(registry.get("policy", {})), "providers": items}


def route_capability(registry: Mapping[str, Any], capability: str, *, env: Mapping[str, str] | None = None,
                     command_exists: Callable[[str], bool] | None = None) -> list[str]:
    env = env or os.environ
    result = []
    for provider_id in registry.get("routes", {}).get(capability, []):
        provider = registry["providers"].get(provider_id)
        if provider and provider_state(provider, env=env, command_exists=command_exists) == "CONFIGURED":
            result.append(provider_id)
    return result


def _http_json(method: str, url: str, headers: Mapping[str, str], body: Mapping[str, Any] | None,
               timeout: float) -> Mapping[str, Any]:
    payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    req_headers = {"Accept": "application/json", "User-Agent": "Biella-Resource/1"}
    req_headers.update(headers)
    if payload is not None:
        req_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            parsed = json.load(response)
    except urllib.error.HTTPError as exc:
        retryable = exc.code == 404 or exc.code in {408, 425, 429} or 500 <= exc.code <= 599
        raise ResourceError(
            f"provider HTTP {exc.code}",
            failure_code=f"HTTP_{exc.code}",
            retryable=retryable,
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        failure_code = "PROTOCOL_ERROR" if isinstance(exc, json.JSONDecodeError) else "TRANSPORT_ERROR"
        raise ResourceError(
            f"provider request failed: {type(exc).__name__}",
            failure_code=failure_code,
            retryable=True,
        ) from None
    if not isinstance(parsed, dict):
        raise ResourceError("provider returned non-object JSON", failure_code="PROTOCOL_ERROR", retryable=True)
    return parsed


def _choose_provider(registry: Mapping[str, Any], capability: str, requested: str | None,
                     env: Mapping[str, str], command_exists: Callable[[str], bool] | None = None) -> str:
    eligible = route_capability(registry, capability, env=env, command_exists=command_exists)
    if requested:
        if requested not in registry["providers"]:
            raise ResourceError(f"unknown provider: {requested}")
        if requested not in eligible:
            state = provider_state(registry["providers"][requested], env=env, command_exists=command_exists)
            raise ResourceError(f"provider {requested} unavailable for {capability}: {state}")
        return requested
    if not eligible:
        raise ResourceError(f"no configured provider for {capability}")
    return eligible[0]


def _clip(value: Any, maximum: int = 900) -> str:
    text = str(value or "").strip().replace("\x00", "")
    return text if len(text) <= maximum else text[: maximum - 1] + "…"


def _compact_search(provider: str, payload: Mapping[str, Any], limit: int) -> list[dict[str, Any]]:
    raw = payload.get("results", [])
    if not isinstance(raw, list):
        return []
    results = []
    for item in raw[:limit]:
        if not isinstance(item, dict):
            continue
        text = item.get("content") or item.get("text") or item.get("highlights") or ""
        if isinstance(text, list):
            text = " ".join(str(x) for x in text)
        result = {
            "title": _clip(item.get("title"), 240),
            "url": _clip(item.get("url"), 600),
            "text": _clip(text, 900),
        }
        if isinstance(item.get("score"), (int, float)):
            result["score"] = item["score"]
        results.append(result)
    return results


def run_search(registry: Mapping[str, Any], query: str, *, env: Mapping[str, str] | None = None,
               provider: str | None = None, limit: int = 5, semantic: bool = False,
               transport: Transport = _http_json, timeout: float = 20.0) -> dict[str, Any]:
    env = env or os.environ
    capability = "research.semantic" if semantic else "research.search"
    selected = _choose_provider(registry, capability, provider, env)
    definition = registry["providers"][selected]
    started = time.monotonic()
    if selected == "tavily":
        body = {"api_key": env["TAVILY_API_KEY"], "query": query, "max_results": limit,
                "search_depth": "basic", "include_answer": False}
        payload = transport("POST", definition["search_url"], {}, body, timeout)
    elif selected == "exa":
        body = {"query": query, "numResults": limit, "type": "auto",
                "contents": {"text": {"maxCharacters": 900}}}
        payload = transport("POST", definition["search_url"], {"x-api-key": env["EXA_API_KEY"]}, body, timeout)
    else:
        raise ResourceError(f"search adapter unavailable for {selected}")
    return {
        "capability": capability,
        "provider": selected,
        "query": query,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "results": _compact_search(selected, payload, limit),
    }


def _model_for(provider_id: str, provider: Mapping[str, Any], env: Mapping[str, str], requested: str | None) -> str:
    if requested:
        return requested
    override = env.get(f"BIELLA_{provider_id.upper()}_MODEL", "").strip()
    if override:
        return override
    default = provider.get("default_model")
    if isinstance(default, str) and default:
        return default
    raise ResourceError(
        f"provider {provider_id} requires --model or BIELLA_{provider_id.upper()}_MODEL",
        failure_code="MODEL_CONFIGURATION",
        retryable=True,
    )


def _bearer_key(provider_id: str) -> str:
    return {
        "groq": "GROQ_API_KEY", "cerebras": "CEREBRAS_API_KEY", "mistral": "MISTRAL_API_KEY",
        "openrouter": "OPENROUTER_API_KEY", "gemini": "GEMINI_API_KEY",
    }[provider_id]


def _run_fast_llm_once(
    registry: Mapping[str, Any],
    prompt: str,
    *,
    provider_id: str,
    model: str | None,
    env: Mapping[str, str],
    max_tokens: int,
    transport: Transport,
    timeout: float,
    command_exists: Callable[[str], bool] | None,
) -> dict[str, Any]:
    definition = registry["providers"][provider_id]
    model_id = _model_for(provider_id, definition, env, model)
    body = {"model": model_id, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
    started = time.monotonic()
    if provider_id == "ollama-qwen":
        base = str(env.get("BIELLA_OLLAMA_URL", "")).strip().rstrip("/")
        url = f"{base}/v1/chat/completions" if base else str(definition["chat_url"])
        payload = transport("POST", url, {}, body, timeout)
    else:
        key_name = _bearer_key(provider_id)
        payload = transport("POST", definition["chat_url"], {"Authorization": f"Bearer {env[key_name]}"}, body, timeout)
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ResourceError("provider response missing assistant content", failure_code="PROTOCOL_ERROR", retryable=True) from None
    usage_raw = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    usage = {k: usage_raw[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens", "cost") if k in usage_raw}
    return {
        "capability": "llm.fast",
        "provider": provider_id,
        "model": str(payload.get("model") or model_id),
        "latency_ms": round((time.monotonic() - started) * 1000),
        "text": _clip(text, 16000),
        "usage": usage,
    }


def _route_failure_code(error: Exception) -> str:
    if isinstance(error, ResourceError):
        return error.failure_code
    return "ADAPTER_ERROR"


def _route_failure_retryable(error: Exception) -> bool:
    if isinstance(error, ResourceError):
        return error.retryable
    text = str(error or "").lower()
    return any(marker in text for marker in (
        "unavailable", "not found", "not available", "rate limit", "timed out",
        "timeout", "connection", "temporar", "provider http", "server error",
    ))


def run_fast_llm(registry: Mapping[str, Any], prompt: str, *, env: Mapping[str, str] | None = None,
                 provider: str | None = None, model: str | None = None, max_tokens: int = 512,
                 transport: Transport = _http_json, timeout: float = 30.0,
                 command_exists: Callable[[str], bool] | None = None,
                 max_failover_attempts: int | None = None) -> dict[str, Any]:
    env = env or os.environ
    selected = _choose_provider(registry, "llm.fast", provider, env, command_exists=command_exists)
    eligible = route_capability(registry, "llm.fast", env=env, command_exists=command_exists)
    candidates = [selected] + [item for item in eligible if item != selected]
    if max_failover_attempts is None:
        attempt_limit = min(len(candidates), 3)
    elif isinstance(max_failover_attempts, bool) or not isinstance(max_failover_attempts, int) or max_failover_attempts < 1:
        raise ResourceError("max_failover_attempts must be a positive integer", failure_code="INVALID_ROUTE_LIMIT")
    else:
        attempt_limit = min(len(candidates), max_failover_attempts, 4)
    attempts: list[dict[str, Any]] = []
    for index, provider_id in enumerate(candidates[:attempt_limit]):
        requested_model = model
        try:
            result = _run_fast_llm_once(
                registry,
                prompt,
                provider_id=provider_id,
                model=model,
                env=env,
                max_tokens=max_tokens,
                transport=transport,
                timeout=timeout,
                command_exists=command_exists,
            )
        except Exception as exc:
            failure = {
                "provider": provider_id,
                "model": requested_model,
                "status": "FAILED",
                "failure_code": _route_failure_code(exc),
            }
            attempts.append(failure)
            if index + 1 >= attempt_limit or not _route_failure_retryable(exc):
                break
            continue
        attempts.append({
            "provider": provider_id,
            "model": requested_model or result["model"],
            "status": "SUCCEEDED",
        })
        result["routing_evidence"] = {
            "authority": "RESOURCE_IMPLEMENTATION",
            "capability": "llm.fast",
            "attempt_limit": attempt_limit,
            "attempted": attempts,
            "fallback_used": index > 0,
            "selection": "ordered-capability-route",
        }
        return result
    evidence = {
        "authority": "RESOURCE_IMPLEMENTATION",
        "capability": "llm.fast",
        "attempt_limit": attempt_limit,
        "attempted": attempts,
        "fallback_used": len(attempts) > 1,
        "selection": "ordered-capability-route",
    }
    summary = ", ".join(f"{item['provider']}:{item.get('failure_code', 'OK')}" for item in attempts)
    raise ResourceError(
        f"llm.fast route exhausted after {len(attempts)} attempt(s): {summary}",
        failure_code="ROUTE_EXHAUSTED",
        evidence=evidence,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biella resource")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    route = sub.add_parser("route"); route.add_argument("capability")
    search = sub.add_parser("search"); search.add_argument("query"); search.add_argument("--provider"); search.add_argument("--limit", type=int, default=5); search.add_argument("--semantic", action="store_true")
    llm = sub.add_parser("fast-llm"); llm.add_argument("--prompt"); llm.add_argument("--provider"); llm.add_argument("--model"); llm.add_argument("--max-tokens", type=int, default=512)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    registry = load_registry(args.registry)
    try:
        if args.command == "status":
            result = status_payload(registry)
        elif args.command == "route":
            result = {"capability": args.capability, "providers": route_capability(registry, args.capability)}
        elif args.command == "search":
            result = run_search(registry, args.query, provider=args.provider, limit=max(1, min(args.limit, 20)), semantic=args.semantic)
        elif args.command == "fast-llm":
            prompt = args.prompt if args.prompt is not None else sys.stdin.read()
            if not prompt.strip():
                raise ResourceError("fast-llm prompt is empty")
            result = run_fast_llm(registry, prompt, provider=args.provider, model=args.model, max_tokens=max(16, min(args.max_tokens, 4096)))
        else:
            raise AssertionError(args.command)
    except ResourceError as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
