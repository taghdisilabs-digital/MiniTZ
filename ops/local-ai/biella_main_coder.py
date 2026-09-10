from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
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


def discover_agr_models(*, timeout_seconds: float = 2.0) -> set[str]:
    agy_bin = os.environ.get("BIELLA_AGR_BIN", "/root/.local/bin/agy")
    try:
        result = subprocess.run(
            [agy_bin, "models"], text=True, capture_output=True, check=False, timeout=timeout_seconds
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()
    return set(parse_agr_models(result.stdout))


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
    model: str,
    effort: str,
    schema_path: Path,
    *,
    read_only: bool,
    conversation_id: str | None = None,
) -> list[str]:
    agy_bin = os.environ.get("BIELLA_AGR_BIN", "/root/.local/bin/agy")
    command = [
        agy_bin,
        "--model", str(model),
        "--effort", str(effort),
        "--mode", "plan" if read_only else "accept-edits",
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--json-schema", str(Path(schema_path)),
        "--disable-slash-commands",
    ]
    if conversation_id:
        command.extend(["--conversation", str(conversation_id)])
    if not read_only:
        command.append("--dangerously-skip-permissions")
    return command


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
    active = [name for name in ("codex", "agr") if statuses.get(name) == "ACTIVE"]
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
    task_id: str,
    task_state_digest: str,
    peer_coder: str,
    model: str,
    capsule_digest: str,
    projection_digest: str,
) -> str:
    payload = {
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
        "Do not duplicate obvious work already present in current evidence. Return only grounded findings and exact evidence references."
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
