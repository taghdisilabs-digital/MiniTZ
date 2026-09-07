from __future__ import annotations

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


def cloud_models() -> tuple[str, ...]:
    routes = [route for profile in _ROUTE_PROFILES.values() for route in profile]
    routes.extend(_ACCOUNT_RECOVERY_ROUTES)
    return tuple(dict.fromkeys(route.model for route in routes if route.provider == "openai"))


def account_usage_cooldown_models(failed_model: str) -> tuple[str, ...]:
    reserved = {"gpt-5.6-luna", "gpt-5.3-codex-spark"}
    if failed_model == "gpt-5.6-luna":
        reserved = {"gpt-5.3-codex-spark"}
    elif failed_model == "gpt-5.3-codex-spark":
        reserved = set()
    return tuple(model for model in cloud_models() if model not in reserved)


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


def select_route(task_class: str, catalog: Mapping[str, set[str]], cooldowns: Mapping[str, str], now: datetime) -> Route:
    candidates = _ROUTE_PROFILES.get(task_class)
    if candidates is None:
        raise ValueError(f"unknown task class: {task_class}")
    for route in candidates:
        if _cooling_down(route.model, cooldowns, now):
            continue
        if route.model not in catalog or route.reasoning not in catalog[route.model]:
            continue
        if task_class in {"creation", "hard_creation"} and reasoning_rank(route.reasoning) < reasoning_rank("high"):
            continue
        return route
    for route in _ACCOUNT_RECOVERY_ROUTES:
        if _cooling_down(route.model, cooldowns, now):
            continue
        if route.model in catalog and route.reasoning in catalog[route.model]:
            return route
    local_model = os.environ.get("BIELLA_CODEX_LOCAL_MODEL", _LOCAL_OSS_MODEL)
    if not _cooling_down(local_model, cooldowns, now) and local_model in catalog and "local" in catalog[local_model]:
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


def discover_catalog() -> dict[str, set[str]]:
    codex_bin = os.environ.get("BIELLA_CODEX_BIN", "/usr/bin/codex")
    proc = subprocess.run([codex_bin, "debug", "models"], text=True, capture_output=True, check=False)
    result: dict[str, set[str]] = {}
    if proc.returncode == 0:
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
    if not result:
        result = fallback_catalog()
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
    args = [
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
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


def build_codex_resume_command(route: Route, schema_path: Path, output_path: Path, session_id: str, *, allow_helper: bool = False) -> list[str]:
    return [
        *_provider_prefix(route), "exec", "resume",
        *_production_exec_args(route, schema_path, output_path, allow_helper=allow_helper),
        session_id,
        "-",
    ]
