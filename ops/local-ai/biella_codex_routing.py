from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

_REASONING_ORDER = ("low", "medium", "high", "xhigh", "max", "ultra")


@dataclass(frozen=True)
class Route:
    model: str
    reasoning: str
    provider: str = "openai"


@dataclass(frozen=True)
class SimpleResourceDecision:
    kind: str
    command: str | None = None


def simple_resource_plan(task_class: str, *, deterministic_command: str | None,
                         grounded_context: bool, local_qwen_resident: bool,
                         spark_available: bool, read_only_microanalysis: bool) -> tuple[SimpleResourceDecision, ...]:
    if str(task_class) != "simple":
        return (SimpleResourceDecision("GENERAL_CODEX"),)
    exact_command = str(deterministic_command or "").strip()
    if exact_command:
        return (SimpleResourceDecision("DETERMINISTIC", exact_command),)
    plan: list[SimpleResourceDecision] = []
    if grounded_context and local_qwen_resident:
        plan.append(SimpleResourceDecision("LOCAL_QWEN"))
    if grounded_context and read_only_microanalysis and spark_available:
        plan.append(SimpleResourceDecision("SPARK"))
    plan.append(SimpleResourceDecision("GENERAL_CODEX"))
    return tuple(plan)


def classify_simple_operation(task_class: str, *, deterministic_command: str | None,
                              grounded_context: bool, local_qwen_resident: bool,
                              spark_available: bool, read_only_microanalysis: bool) -> SimpleResourceDecision:
    return simple_resource_plan(
        task_class, deterministic_command=deterministic_command, grounded_context=grounded_context,
        local_qwen_resident=local_qwen_resident, spark_available=spark_available,
        read_only_microanalysis=read_only_microanalysis,
    )[0]


_ROUTE_PROFILES: dict[str, tuple[Route, ...]] = {
    "simple": (Route("gpt-5.6-luna", "medium"), Route("gpt-5.6-terra", "medium"), Route("gpt-5.6-sol", "medium"), Route("gpt-5.5", "medium"), Route("gpt-6-astra", "high")),
    "medium": (Route("gpt-5.6-luna", "high"), Route("gpt-5.6-terra", "high"), Route("gpt-5.6-sol", "high"), Route("gpt-5.5", "high"), Route("gpt-6-astra", "xhigh")),
    "creation": (Route("gpt-5.6-luna", "max"), Route("gpt-5.6-sol", "xhigh"), Route("gpt-5.6-terra", "xhigh"), Route("gpt-6-astra", "xhigh")),
    "hard": (Route("gpt-6-astra", "ultra"), Route("gpt-5.6-terra", "ultra"), Route("gpt-5.6-sol", "ultra"), Route("gpt-5.6-luna", "max")),
    "deep_memory": (Route("gpt-6-astra", "ultra"), Route("gpt-5.6-terra", "ultra"), Route("gpt-5.6-sol", "ultra")),
    "hard_creation": (Route("gpt-6-astra", "ultra"), Route("gpt-5.6-terra", "ultra"), Route("gpt-5.6-sol", "ultra"), Route("gpt-5.6-luna", "max")),
}

_LOCAL_OSS_MODEL = "qwen3-coder-next:biella"
_ACCOUNT_RECOVERY_ROUTES = (
    Route("gpt-5.6-luna", "max"),
    Route("gpt-5.3-codex-spark", "xhigh"),
)
_DISCOVERED_STRONG_RECOVERY_ROUTES = (Route("gpt-reserve", "max"),)
_BOUNDED_FALLBACK_MODELS = {"gpt-5.3-codex-spark", _LOCAL_OSS_MODEL}


def is_bounded_fallback(route: Route) -> bool:
    return route.model in _BOUNDED_FALLBACK_MODELS


def bounded_fallback_models() -> tuple[str, ...]:
    return tuple(sorted(_BOUNDED_FALLBACK_MODELS))


def cloud_models() -> tuple[str, ...]:
    routes = [route for profile in _ROUTE_PROFILES.values() for route in profile]
    routes.extend(_ACCOUNT_RECOVERY_ROUTES)
    routes.extend(_DISCOVERED_STRONG_RECOVERY_ROUTES)
    return tuple(dict.fromkeys(route.model for route in routes if route.provider == "openai"))


def account_usage_cooldown_models(failed_model: str) -> tuple[str, ...]:
    return (str(failed_model),)


def reconcile_legacy_account_cooldowns(cooldowns: Mapping[str, str]) -> dict[str, str]:
    current = {str(model): str(until) for model, until in cooldowns.items()}
    known = [model for model in current if model in set(cloud_models())]
    values = {current[model] for model in known}
    if len(known) >= 4 and len(values) == 1:
        return {model: until for model, until in current.items() if model not in set(known)}
    return current


def reasoning_rank(effort: str) -> int:
    return _REASONING_ORDER.index(effort)


def _cooling_down(model: str, cooldowns: Mapping[str, str], now: datetime) -> bool:
    raw = cooldowns.get(model)
    if not raw:
        return False
    try:
        until = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return until > now


def select_route(task_class: str, catalog: Mapping[str, set[str]], cooldowns: Mapping[str, str], now: datetime, *, excluded_models: set[str] | None = None) -> Route:
    candidates = _ROUTE_PROFILES.get(task_class)
    if candidates is None:
        raise ValueError(f"unknown task class: {task_class}")
    excluded = excluded_models or set()
    forced_model = os.environ.get("BIELLA_CODEX_FORCE_MODEL", "").strip()
    forced_reasoning = os.environ.get("BIELLA_CODEX_FORCE_REASONING", "").strip()
    if forced_model:
        if forced_model in excluded or _cooling_down(forced_model, cooldowns, now):
            raise RuntimeError(f"forced Codex route unavailable: {forced_model}")
        levels = catalog.get(forced_model)
        if not levels:
            raise RuntimeError(f"forced Codex route unavailable: {forced_model}")
        if forced_reasoning:
            if forced_reasoning not in levels:
                raise RuntimeError(f"forced Codex route unsupported: {forced_model}:{forced_reasoning}")
            reasoning = forced_reasoning
        else:
            supported = [level for level in _REASONING_ORDER if level in levels]
            if not supported:
                raise RuntimeError(f"forced Codex route has no supported reasoning level: {forced_model}")
            reasoning = supported[-1]
        if task_class in {"creation", "hard_creation"} and reasoning_rank(reasoning) < reasoning_rank("high"):
            raise RuntimeError(f"forced Codex route reasoning is below creation minimum: {forced_model}:{reasoning}")
        return Route(forced_model, reasoning)
    preferred = os.environ.get("BIELLA_CODEX_PREFER_MODEL", "").strip()
    if preferred:
        # Prefer Reserve, but an observed outage is not a permanent route pin.
        strong = (preferred, *(item.model for item in _ROUTE_PROFILES["hard_creation"]),
                  *(item.model for item in _DISCOVERED_STRONG_RECOVERY_ROUTES))
        for model in dict.fromkeys(strong):
            if model in excluded or model in _BOUNDED_FALLBACK_MODELS or _cooling_down(model, cooldowns, now):
                continue
            levels = catalog.get(model, set())
            eligible = [level for level in _REASONING_ORDER if level in levels and reasoning_rank(level) >= reasoning_rank("high")]
            if eligible:
                return Route(model, eligible[-1])
    for route in candidates:
        if route.model in excluded or _cooling_down(route.model, cooldowns, now):
            continue
        if route.model not in catalog or route.reasoning not in catalog[route.model]:
            continue
        if task_class in {"creation", "hard_creation"} and reasoning_rank(route.reasoning) < reasoning_rank("high"):
            continue
        return route
    recovery_routes = (
        _ACCOUNT_RECOVERY_ROUTES[0],
        *_DISCOVERED_STRONG_RECOVERY_ROUTES,
        *_ACCOUNT_RECOVERY_ROUTES[1:],
    )
    for route in recovery_routes:
        if route.model in excluded or _cooling_down(route.model, cooldowns, now):
            continue
        if route.model in catalog and route.reasoning in catalog[route.model]:
            return route
    local_model = os.environ.get("BIELLA_CODEX_LOCAL_MODEL", _LOCAL_OSS_MODEL)
    if local_model not in excluded and not _cooling_down(local_model, cooldowns, now) and local_model in catalog and "local" in catalog[local_model]:
        return Route(local_model, "none", "ollama")
    raise RuntimeError(f"no eligible Codex model for {task_class}")


_LIMIT_RE = re.compile(r"(?:usage_limit_exceeded|rate_limit_exceeded|usage limit|rate limit)", re.I)
_ACCOUNT_USAGE_RE = re.compile(r"(?:you(?:'|’)?ve hit your usage limit|chatgpt\.com/codex/settings/usage)", re.I)
_LOCAL_COMPAT_RE = re.compile(r"(?:does not support thinking|failed to decode models response.*missing field [`']?models)", re.I | re.S)
_RETRY_RE = re.compile(r"(?:try again at|retry at|available at)\s+([A-Za-z]{3}\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M(?:\s+UTC)?)", re.I)


def is_limit_error(text: str) -> bool:
    return bool(_LIMIT_RE.search(text))


def is_account_usage_limit_error(text: str) -> bool:
    return bool(_ACCOUNT_USAGE_RE.search(text))


def is_local_provider_compatibility_error(text: str) -> bool:
    return bool(_LOCAL_COMPAT_RE.search(text))


def limit_retry_at(text: str, observed_at: datetime) -> datetime:
    if not is_limit_error(text):
        raise ValueError("not a usage/rate-limit response")
    match = _RETRY_RE.search(text)
    if not match:
        return observed_at + timedelta(minutes=30)
    raw = match.group(1); is_utc = raw.upper().endswith(" UTC")
    if is_utc:
        raw = raw[:-4]
    raw = re.sub(r"(?<=\d)(?:st|nd|rd|th)(?=,)", "", raw, flags=re.I)
    parsed = datetime.strptime(raw, "%b %d, %Y %I:%M %p")
    return parsed.replace(tzinfo=timezone.utc if is_utc else observed_at.tzinfo or timezone.utc)


def fallback_catalog() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for routes in (*_ROUTE_PROFILES.values(), _ACCOUNT_RECOVERY_ROUTES):
        for route in routes:
            result.setdefault(route.model, set()).add(route.reasoning)
    return result


def _discover_local_ollama_models() -> set[str]:
    ollama_bin = os.environ.get("BIELLA_OLLAMA_BIN", "/usr/local/bin/ollama")
    try:
        proc = subprocess.run([ollama_bin, "list"], text=True, capture_output=True, check=False, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if proc.returncode != 0:
        return set()
    models: set[str] = set()
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            models.add(parts[0])
    return models


_CATALOG_CACHE_SCHEMA = "minitz.model_catalog_cache/v1"


def _catalog_digest(catalog: Mapping[str, set[str]]) -> str:
    normalized = {str(model): sorted(str(level) for level in levels) for model, levels in sorted(catalog.items())}
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def persist_catalog_cache(path: Path, catalog: Mapping[str, set[str]], *, state: str,
                          source: str = "codex_debug_models", observed_at: datetime | None = None,
                          probe_state: str | None = None) -> None:
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    normalized = {str(model): sorted(str(level) for level in levels) for model, levels in sorted(catalog.items())}
    effective_probe_state = probe_state or ("LIVE_DISCOVERED" if state == "LIVE_DISCOVERED" else "DISCOVERY_UNAVAILABLE")
    payload = {
        "schema": _CATALOG_CACHE_SCHEMA, "state": str(state), "probe_state": effective_probe_state,
        "source": str(source), "observed_at": (observed_at or datetime.now(timezone.utc)).isoformat(),
        "catalog": normalized, "catalog_digest": _catalog_digest({k: set(v) for k, v in normalized.items()}),
    }
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def _load_catalog_cache(path: Path) -> dict[str, set[str]] | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema") != _CATALOG_CACHE_SCHEMA:
        return None
    if payload.get("state") not in {"LIVE_DISCOVERED", "LAST_KNOWN_GOOD"}:
        return None
    raw_catalog = payload.get("catalog")
    if not isinstance(raw_catalog, dict):
        return None
    result: dict[str, set[str]] = {}
    for model, levels in raw_catalog.items():
        if not isinstance(model, str) or not isinstance(levels, list) or not levels:
            return None
        parsed = {str(level) for level in levels if isinstance(level, str) and level}
        if not parsed:
            return None
        result[model] = parsed
    if payload.get("catalog_digest") != _catalog_digest(result):
        return None
    return result


def discover_catalog(*, cache_path: Path | None = None, timeout_seconds: float = 2.0) -> dict[str, set[str]]:
    codex_bin = os.environ.get("BIELLA_CODEX_BIN", "/usr/bin/codex")
    result: dict[str, set[str]] = {}
    try:
        proc = subprocess.run(
            [codex_bin, "debug", "models"], text=True, capture_output=True, check=False,
            timeout=max(0.05, float(timeout_seconds)),
        )
    except (OSError, subprocess.TimeoutExpired):
        proc = None
    if proc is not None and proc.returncode == 0:
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            data = {}
        for item in data.get("models", []) if isinstance(data, dict) else []:
            if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
                continue
            levels = {str(level.get("effort")) for level in item.get("supported_reasoning_levels", []) if isinstance(level, dict) and level.get("effort")}
            if levels:
                result[item["slug"]] = levels
    if result and cache_path is not None:
        persist_catalog_cache(cache_path, result, state="LIVE_DISCOVERED")
    if not result and cache_path is not None:
        cached = _load_catalog_cache(cache_path)
        if cached:
            result = cached
            persist_catalog_cache(cache_path, result, state="LAST_KNOWN_GOOD", source="cached_codex_debug_models")
    if not result:
        result = fallback_catalog()
        if cache_path is not None:
            persist_catalog_cache(
                cache_path, result, state="STATIC_FALLBACK", source="builtin_route_profiles",
                probe_state="DISCOVERY_UNAVAILABLE",
            )
    local_model = os.environ.get("BIELLA_CODEX_LOCAL_MODEL", _LOCAL_OSS_MODEL)
    if local_model in _discover_local_ollama_models():
        result[local_model] = {"local"}
    return result


def earliest_cooldown_delay(cooldowns: Mapping[str, str], now: datetime) -> float:
    waits: list[float] = []
    for raw in cooldowns.values():
        try:
            target = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        if (delta := (target - now).total_seconds()) > 0:
            waits.append(delta)
    return min(waits) if waits else 60.0


def local_model_catalog_path() -> Path:
    configured = os.environ.get("BIELLA_CODEX_LOCAL_MODEL_CATALOG")
    return Path(configured) if configured else Path(__file__).with_name("biella-qwen-codex-model-catalog.json")


def _production_exec_args(route: Route, schema_path: Path, output_path: Path, *, allow_helper: bool = False) -> list[str]:
    fanout = ["--enable", "multi_agent", "--disable", "multi_agent_v2"] if allow_helper else ["--disable", "multi_agent", "--disable", "multi_agent_v2"]
    local = route.provider == "ollama"
    execution_safety = ["--sandbox", "workspace-write"] if is_bounded_fallback(route) else ["--dangerously-bypass-approvals-and-sandbox", "--dangerously-bypass-hook-trust"]
    args = [
        *execution_safety,
        "--disable", "plugins",
        *fanout,
        "-c", 'shell_environment_policy.inherit="all"',
        "-c", f'model_auto_compact_token_limit={12000 if local else 96000}',
        "-c", f'tool_output_token_limit={4000 if local else 12000}',
        "-c", 'max_concurrent_threads_per_session=2',
        "-c", 'max_depth=1',
    ]
    if route.provider == "openai":
        args += ["-c", f'model_reasoning_effort="{route.reasoning}"']
    elif route.provider == "ollama":
        args += ["-c", 'model_reasoning_effort="none"']
    else:
        raise ValueError(f"unsupported Codex provider: {route.provider}")
    args += [
        "-m", route.model,
        "--json",
        "--output-schema", str(schema_path),
        "-o", str(output_path),
    ]
    return args


def _provider_prefix(route: Route) -> list[str]:
    codex_bin = os.environ.get("BIELLA_CODEX_BIN", "/usr/bin/codex")
    if route.provider == "openai":
        return [codex_bin, "--search"]
    if route.provider == "ollama":
        catalog = local_model_catalog_path()
        return [codex_bin, "--oss", "--local-provider", "ollama", "-c", f'model_catalog_json="{catalog}"']
    raise ValueError(f"unsupported Codex provider: {route.provider}")


def build_codex_command(route: Route, schema_path: Path, output_path: Path, cwd: Path, *, allow_helper: bool = False) -> list[str]:
    return [
        *_provider_prefix(route), "exec",
        *_production_exec_args(route, schema_path, output_path, allow_helper=allow_helper),
        "-C", str(cwd),
        "-",
    ]


def build_taskbooster_command(route: Route, schema_path: Path, output_path: Path, cwd: Path) -> list[str]:
    if route.provider != "openai" or route.model != "gpt-5.3-codex-spark":
        raise ValueError("TaskBooster requires the Spark OpenAI route")
    codex_bin = os.environ.get("BIELLA_CODEX_BIN", "/usr/bin/codex")
    return [
        codex_bin, "exec",
        "--sandbox", "read-only",
        "--disable", "plugins",
        "--disable", "multi_agent",
        "--disable", "multi_agent_v2",
        "-c", 'shell_environment_policy.inherit="all"',
        "-c", 'model_auto_compact_token_limit=12000',
        "-c", 'tool_output_token_limit=4000',
        "-c", 'max_concurrent_threads_per_session=1',
        "-c", 'max_depth=1',
        "-c", f'model_reasoning_effort="{route.reasoning}"',
        "-m", route.model,
        "--json",
        "--output-schema", str(schema_path),
        "-o", str(output_path),
        "-C", str(cwd),
        "-",
    ]


def build_codex_resume_command(route: Route, schema_path: Path, output_path: Path, session_id: str, *, allow_helper: bool = False) -> list[str]:
    return [
        *_provider_prefix(route), "exec", "resume",
        *_production_exec_args(route, schema_path, output_path, allow_helper=allow_helper),
        session_id,
        "-",
    ]
