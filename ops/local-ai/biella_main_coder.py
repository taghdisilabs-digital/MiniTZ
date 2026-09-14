from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

CODER_STATUSES = ("OFFLINE", "ACTIVE", "OUT_OF_CREDIT", "NEEDS_MODIFICATION")

_AGR_LIMIT_RE = re.compile(
    r"(?:out\s+of\s+credit|usage\s+limit|rate\s+limit|quota[^\n]{0,80}(?:exhaust|reached|exceed|0%)|"
    r"resource\s+exhausted|weekly\s+limit\s+remaining[^\n]{0,20}0(?:\.0+)?%|"
    r"five\s+hour\s+limit\s+remaining[^\n]{0,20}0(?:\.0+)?%)",
    re.I,
)
_AGR_OFFLINE_RE = re.compile(
    r"(?:command\s+not\s+found|no\s+such\s+file|connection\s+refused|network\s+is\s+unreachable|"
    r"temporary\s+failure\s+in\s+name\s+resolution|name\s+or\s+service\s+not\s+known)",
    re.I,
)

_COPILOT_PROVIDER_ENV_KEYS = (
    "COPILOT_PROVIDER_BASE_URL", "COPILOT_PROVIDER_TYPE", "COPILOT_PROVIDER_API_KEY",
    "COPILOT_PROVIDER_BEARER_TOKEN", "COPILOT_PROVIDER_WIRE_API",
    "COPILOT_PROVIDER_TRANSPORT", "COPILOT_PROVIDER_MODEL_ID",
    "COPILOT_PROVIDER_WIRE_MODEL", "COPILOT_PROVIDER_HEADERS",
    "COPILOT_PROVIDER_MAX_PROMPT_TOKENS", "COPILOT_PROVIDER_MAX_OUTPUT_TOKENS",
    "COPILOT_MODEL",
)
_COPILOT_SAFE_ENV_KEYS = (
    "PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE",
    "TERM", "TMPDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS", "NO_COLOR",
)

_AGR_MODEL_PREFERENCES: dict[str, tuple[str, ...]] = {
    "simple": (
        "gemini-3.8-flash-high", "gemini-3.7-flash-high", "gemini-3.6-flash-high",
        "claude-sonnet-4-6", "gemini-3.1-pro-high", "claude-opus-4-6-thinking",
    ),
    "medium": (
        "claude-sonnet-4-6", "gemini-3.1-pro-high", "claude-opus-4-6-thinking",
        "gemini-3.8-flash-high",
    ),
    "creation": (
        "claude-sonnet-4-6", "claude-opus-4-6-thinking", "gemini-3.1-pro-high",
        "gemini-3.8-flash-high",
    ),
    "hard": (
        "claude-opus-4-6-thinking", "gemini-3.1-pro-high", "claude-sonnet-4-6",
        "gemini-3.8-flash-high",
    ),
    "deep_memory": (
        "claude-opus-4-6-thinking", "gemini-3.1-pro-high", "claude-sonnet-4-6",
    ),
    "hard_creation": (
        "claude-opus-4-6-thinking", "gemini-3.1-pro-high", "claude-sonnet-4-6",
    ),
}


@dataclass(frozen=True)
class CoderSelection:
    primary: str | None
    peer: str | None


def parse_agr_models(text: str) -> tuple[str, ...]:
    models: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or "\t" not in line:
            continue
        slug = line.split("\t", 1)[0].strip()
        if slug and re.fullmatch(r"[a-z0-9][a-z0-9._-]*", slug):
            models.append(slug)
    return tuple(dict.fromkeys(models))


def copilot_candidate_available() -> bool:
    path = Path(os.environ.get("BIELLA_COPILOT_BIN", "/usr/local/bin/copilot"))
    return path.is_file() and os.access(path, os.X_OK)


def copilot_session_id(project_scope: str, task_id: str, task_state_digest: str, profile: str) -> str:
    identity = f"minitz-ai-peer://{project_scope}/{task_id}/{task_state_digest}/{profile}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def build_copilot_peer_command(
    prompt: str, session_id: str, working_root: Path, *, read_dirs: Iterable[Path] = (),
) -> list[str]:
    copilot_bin = os.environ.get("BIELLA_COPILOT_BIN", "/usr/local/bin/copilot")
    command = [
        copilot_bin, "-p", str(prompt), "--session-id", str(session_id),
        "-C", str(Path(working_root).resolve()), "--no-ask-user", "--silent",
        "--allow-all-tools", "--deny-tool=write", "--deny-tool=shell",
    ]
    for path in read_dirs:
        command.extend(["--add-dir", str(Path(path).resolve())])
    return command


def _copilot_minimal_env(base_env: Mapping[str, str]) -> dict[str, str]:
    return {key: str(base_env[key]) for key in _COPILOT_SAFE_ENV_KEYS if str(base_env.get(key) or "").strip()}


def _protected_runtime_values(keys: Iterable[str], base_env: Mapping[str, str]) -> dict[str, str]:
    wanted = {str(key) for key in keys}
    result = {key: str(base_env[key]) for key in wanted if str(base_env.get(key) or "").strip()}
    missing = wanted.difference(result)
    if not missing:
        return result
    source_path = Path(
        str(base_env.get("MINITZ_CREDENTIAL_SOURCE") or base_env.get("BIELLA_AI_RUNTIME_ENV") or "/root/.config/biella-ai/runtime.env")
    )
    try:
        lines = source_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in missing:
            continue
        value = value.strip()
        if len(value) >= 2 and value[:1] == value[-1:] and value[0] in {"\"", "'"}:
            value = value[1:-1]
        if value:
            result[key] = value
            missing.discard(key)
        if not missing:
            break
    return result


def copilot_cloudflare_candidate_available(base_env: Mapping[str, str] | None = None) -> bool:
    source = dict(os.environ if base_env is None else base_env)
    values = _protected_runtime_values(("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"), source)
    return bool(
        copilot_candidate_available()
        and str(values.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
        and str(values.get("CLOUDFLARE_API_TOKEN") or "").strip()
    )


def copilot_local_qwen_candidate_available(base_env: Mapping[str, str] | None = None, *, timeout_seconds: float = 2.0) -> bool:
    source = dict(os.environ if base_env is None else base_env)
    if not copilot_candidate_available():
        return False
    model = str(source.get("BIELLA_CODEX_LOCAL_MODEL") or "qwen3-coder-next:biella").strip()
    desired_gpu = str(source.get("BIELLA_QWEN_NUM_GPU") or "42").strip()
    desired_ctx = str(source.get("BIELLA_QWEN_NUM_CTX") or "16384").strip()
    ollama_bin = str(source.get("BIELLA_OLLAMA_BIN") or "/usr/local/bin/ollama")
    try:
        proc = subprocess.run(
            [ollama_bin, "show", model, "--modelfile"], text=True, capture_output=True,
            check=False, timeout=max(0.1, float(timeout_seconds)),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    params: dict[str, str] = {}
    for raw in proc.stdout.splitlines():
        match = re.fullmatch(r"PARAMETER\s+(num_gpu|num_ctx)\s+(\S+)", raw.strip())
        if match:
            params[match.group(1)] = match.group(2)
    return params.get("num_gpu") == desired_gpu and params.get("num_ctx") == desired_ctx


def copilot_peer_env(profile: str, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = dict(os.environ if base_env is None else base_env)
    env = _copilot_minimal_env(source)
    for key in _COPILOT_PROVIDER_ENV_KEYS:
        env.pop(key, None)
    if profile == "native":
        # Explicit non-Google model: provider auto-selection may choose Gemini.
        model = str(source.get("MINITZ_COPILOT_MODEL") or "gpt-5.4").strip()
        if model.lower() == "auto" or "gemini" in model.lower():
            raise ValueError("MiniTZ native peer requires an explicit non-Gemini model")
        env["COPILOT_MODEL"] = model
        return env
    if profile == "local-qwen":
        env.update({
            "COPILOT_PROVIDER_BASE_URL": "http://127.0.0.1:11434/v1",
            "COPILOT_PROVIDER_TYPE": "openai",
            "COPILOT_MODEL": str(source.get("BIELLA_CODEX_LOCAL_MODEL") or "qwen3-coder-next:biella"),
        })
        return env
    if profile == "cloudflare":
        values = _protected_runtime_values(("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"), source)
        account = str(values.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
        token = str(values.get("CLOUDFLARE_API_TOKEN") or "").strip()
        if not account or not token:
            raise ValueError("Cloudflare credential reference is not available to this peer process")
        env.update({
            "COPILOT_PROVIDER_BASE_URL": f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1",
            "COPILOT_PROVIDER_TYPE": "openai",
            "COPILOT_PROVIDER_API_KEY": token,
            "COPILOT_MODEL": "@cf/moonshotai/kimi-k2.7-code",
            "COPILOT_PROVIDER_MAX_PROMPT_TOKENS": "32768",
            "COPILOT_PROVIDER_MAX_OUTPUT_TOKENS": "4096",
        })
        return env
    raise ValueError(f"unknown Copilot peer profile: {profile}")


def classify_copilot_observation(returncode: int, output: str) -> str:
    text = str(output or "")
    if agr_is_usage_limited(text):
        return "OUT_OF_CREDIT"
    if int(returncode) == 127 or _AGR_OFFLINE_RE.search(text):
        return "OFFLINE"
    if int(returncode) == 0:
        return "ACTIVE"
    return "NEEDS_MODIFICATION"


def discover_agr_models(*, timeout_seconds: float = 2.0) -> set[str]:
    """AGY/Antigravity is owner-disabled; never probe it during execution."""
    return set()


def agr_is_usage_limited(text: str) -> bool:
    return bool(_AGR_LIMIT_RE.search(str(text or "")))


def classify_agr_observation(returncode: int, output: str) -> str:
    text = str(output or "")
    if agr_is_usage_limited(text):
        return "OUT_OF_CREDIT"
    if int(returncode) == 127 or _AGR_OFFLINE_RE.search(text):
        return "OFFLINE"
    if int(returncode) == 0:
        try:
            payload = json.loads(text.splitlines()[-1]) if text.strip() else {}
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, Mapping) and str(payload.get("status", "")).upper() in {"ERROR", "INVALID", "CANCELED", "INTERRUPTED"}:
            return "NEEDS_MODIFICATION"
        return "ACTIVE"
    return "NEEDS_MODIFICATION"


def select_agr_model(task_class: str, available: Iterable[str]) -> str:
    available_set = {str(item) for item in available}
    preferred = _AGR_MODEL_PREFERENCES.get(str(task_class))
    if preferred is None:
        raise ValueError(f"unknown task class: {task_class}")
    for model in preferred:
        if model in available_set:
            return model
    raise RuntimeError(f"no eligible AGR model for {task_class}")


def agr_effort(task_class: str) -> str:
    if task_class == "simple":
        return "low"
    if task_class in {"medium", "creation"}:
        return "medium"
    if task_class in {"hard", "deep_memory", "hard_creation"}:
        return "high"
    raise ValueError(f"unknown task class: {task_class}")


def build_agr_stream_command(
    model: str, effort: str, schema_path: Path, *, read_only: bool,
    conversation_id: str | None = None,
) -> list[str]:
    raise RuntimeError("AGY/Antigravity is disabled by the MiniTZ owner")


def agr_user_event(prompt: str) -> str:
    return json.dumps(
        {"event": "user", "message": {"content": str(prompt)}},
        sort_keys=True,
        separators=(",", ":"),
    )


def parse_agr_stream_result(lines: Iterable[str]) -> dict[str, object]:
    latest: dict[str, object] | None = None
    for raw in lines:
        try:
            item = json.loads(str(raw))
        except json.JSONDecodeError:
            continue
        if not isinstance(item, Mapping):
            continue
        if item.get("event") == "result" and isinstance(item.get("result"), Mapping):
            latest = dict(item["result"])
        elif "conversation_id" in item and "status" in item:
            latest = dict(item)
    if latest is None:
        raise ValueError("AGR stream produced no result event")
    return latest


def select_coder_roles(statuses: Mapping[str, str], *, current_writer: str | None) -> CoderSelection:
    active = [name for name in ("codex", "copilot") if statuses.get(name) == "ACTIVE"]
    if not active:
        return CoderSelection(None, None)
    if current_writer in active:
        primary = str(current_writer)
    elif "codex" in active:
        primary = "codex"
    else:
        primary = active[0]
    peer = next((name for name in active if name != primary), None)
    return CoderSelection(primary, peer)


def shared_policy_paths(repo_root: Path, working_root: Path) -> tuple[Path, ...]:
    repo = Path(repo_root).resolve()
    current = Path(working_root).resolve()
    engine_policy = repo / "ops" / "workstation" / "AGENTS.md"
    result: list[Path] = []
    if engine_policy.is_file():
        result.append(engine_policy)
    try:
        current.relative_to(repo)
    except ValueError:
        return tuple(result)
    for directory in (current, *current.parents):
        candidate = directory / "AGENTS.md"
        if candidate.is_file() and candidate != engine_policy:
            result.append(candidate)
            break
        if directory == repo:
            break
    return tuple(result)


def peer_assist_schema() -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "summary", "findings", "evidence_refs", "candidate_actions"],
        "properties": {
            "status": {"type": "string", "enum": ["NO_FINDING", "USEFUL"]},
            "summary": {"type": "string", "maxLength": 6000},
            "findings": {"type": "array", "maxItems": 24, "items": {"type": "string", "maxLength": 2000}},
            "evidence_refs": {"type": "array", "maxItems": 48, "items": {"type": "string", "maxLength": 2048}},
            "candidate_actions": {"type": "array", "maxItems": 24, "items": {"type": "string", "maxLength": 2000}},
        },
    }


def peer_assist_key(
    project_scope: str,
    task_id: str,
    task_state_digest: str,
    peer_coder: str,
    model: str,
    capsule_digest: str,
    projection_digest: str,
) -> str:
    payload = {
        "project_scope": str(project_scope),
        "task_id": str(task_id), "task_state_digest": str(task_state_digest),
        "peer_coder": str(peer_coder), "model": str(model),
        "capsule_digest": str(capsule_digest), "projection_digest": str(projection_digest),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def peer_assist_prompt(
    *, task_id: str, title: str, task_state_digest: str,
    capsule_path: Path, projection_path: Path | None,
    policy_paths: Iterable[Path], primary_coder: str, peer_coder: str,
) -> str:
    policies = "\n".join(f"POLICY: {Path(path)}" for path in policy_paths)
    projection = str(Path(projection_path)) if projection_path else "NONE"
    return (
        "READ_ONLY_PEER_ASSIST\n"
        "AUTHORITY: NONE\n"
        "DO_NOT_MODIFY_FILES\n"
        "DO_NOT_COMMIT_PUSH_PUBLISH_OR_CHANGE_TASK_STATE\n"
        "DO_NOT_COMPLETE_OR_ADVANCE_TASK\n"
        f"PRIMARY_CODER: {primary_coder}\nPEER_CODER: {peer_coder}\n"
        f"TASK: {task_id} | {title}\nTASK_STATE_DIGEST: {task_state_digest}\n"
        f"TASK_MEMORY: {Path(capsule_path)}\nMEMORY_PROJECTION: {projection}\n{policies}\n"
        "Read the shared MiniTZ task memory/projection and exact current source needed for one independent high-value assist. "
        "Prioritize finding a concrete blocker, missing validation, risky assumption, exact implementation improvement, reusable material, or test that can accelerate the canonical writer. "
        "Do not duplicate obvious work already present in current evidence. "
        "STRICT_JSON_ONLY. Return exactly one JSON object and no markdown/prose outside it: "
        '{"status":"NO_FINDING|USEFUL","summary":"string","findings":[],"evidence_refs":[],"candidate_actions":[]}. '
        "status must be exactly NO_FINDING or USEFUL; every finding/action/evidence item must be a non-empty string."
    )



def validate_peer_assist(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("peer assist result must be an object")
    allowed = {"status", "summary", "findings", "evidence_refs", "candidate_actions"}
    if set(value) != allowed:
        raise ValueError("peer assist result fields do not match schema")
    status = value.get("status")
    if status not in {"NO_FINDING", "USEFUL"}:
        raise ValueError("peer assist status is invalid")
    summary = value.get("summary")
    if not isinstance(summary, str) or len(summary.encode()) > 6000:
        raise ValueError("peer assist summary is invalid")
    result: dict[str, object] = {"status": status, "summary": summary.strip()}
    for key, limit, item_limit in (("findings", 24, 2000), ("evidence_refs", 48, 2048), ("candidate_actions", 24, 2000)):
        raw = value.get(key)
        if not isinstance(raw, list) or len(raw) > limit:
            raise ValueError(f"peer assist {key} is invalid")
        clean: list[str] = []
        for item in raw:
            if not isinstance(item, str) or not item.strip() or len(item.encode()) > item_limit:
                raise ValueError(f"peer assist {key} item is invalid")
            clean.append(item.strip())
        result[key] = clean
    return result
