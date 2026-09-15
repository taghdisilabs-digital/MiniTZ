from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping
_PROTECTED_CANONICAL_CONTROL_NAMES = frozenset({
    "TASK_PROGRAM.json",
    "TASK_PROGRAM_CHANGE_LEDGER.jsonl",
    "runtime.json",
    "current-task.json",
    "compacted-memory.json",
    "minitz-publication.json",
})


def _assert_noncanonical_control_write(path: Path) -> None:
    target = Path(path)
    name = target.name
    lowered = name.lower()
    if (
        name in _PROTECTED_CANONICAL_CONTROL_NAMES
        or ".sqlite" in lowered
        or lowered.endswith(".db")
        or lowered.endswith(".db-wal")
        or lowered.endswith(".db-shm")
    ):
        raise ValueError(f"Boost/Commander write rejected for canonical control state: {target}")


COMMANDER_STATUSES = ("OFFLINE", "ACTIVE", "OUT_OF_CREDIT", "NEEDS_MODIFICATION")
COMMANDER_LANE_COUNT = 30
DEFAULT_REMOTE_PROVIDER_MAX_INFLIGHT = 1
DEFAULT_RESULT_MAX_TOKENS = 512


@dataclass(frozen=True)
class CommanderLane:
    lane_id: str
    role: str
    instruction: str
    authority: str = "NONE"
    work_mode: str = "BOOST_READ_SUMMARY"


_ROLES: tuple[tuple[str, str], ...] = (
    ("requirements", "Find one missing, contradictory, or underspecified requirement that can change the implementation decision."),
    ("task-boundary", "Check task scope, authority boundaries, and whether proposed work belongs to the current task."),
    ("source-map", "Identify the smallest exact source/evidence set the writer should inspect next."),
    ("architecture", "Find one architecture issue or simplification that preserves current authority and continuity."),
    ("implementation", "Propose one concrete implementation improvement grounded in the supplied task context."),
    ("integration", "Find one integration seam likely to fail when the change meets existing runtime behavior."),
    ("tests", "Identify the highest-value focused test that would falsify an incorrect implementation."),
    ("regression", "Find one likely regression against already-accepted behavior and how to detect it."),
    ("validation", "Check whether current evidence can actually admit the desired state and name the missing validation."),
    ("failure-triage", "Classify the most important current failure and suggest the smallest recovery boundary."),
    ("checkpoint-continuity", "Check task/session/checkpoint identity survival and stale-owner risks."),
    ("memory-context", "Find missing or stale memory context that could cause task replay or wrong assumptions."),
    ("cache-reuse", "Find safe content-addressed reuse or duplicate work that can be suppressed."),
    ("provider-routing", "Find routing/provider selection improvements without creating authority or quota probes."),
    ("concurrency", "Find race, lease, duplicate-work, or writer-starvation risks in concurrent execution."),
    ("performance", "Find one measurable performance improvement that does not reduce correctness."),
    ("build", "Find the smallest build/compile check needed for this task state."),
    ("runtime", "Find one runtime-state or process-lifecycle issue that source-only review could miss."),
    ("api-contract", "Check interface/schema compatibility and identify one contract edge case."),
    ("dependency", "Find one dependency/precondition mismatch or unnecessary dependency."),
    ("data-flow", "Trace one critical data/state flow and identify where truth could diverge."),
    ("observability", "Find one missing bounded diagnostic needed to prove current behavior without becoming authority."),
    ("evidence", "Check provenance/material-input matching and identify weak or missing evidence."),
    ("publication", "Find publication/synchronization risk that must remain nonblocking to canonical progress."),
    ("portability", "Find one environment/platform assumption likely to break outside the current host."),
    ("resilience", "Find one recoverability issue and the smallest fail-safe behavior."),
    ("simplification", "Find one unnecessary mechanism or duplicated semantic family that can be removed or attached."),
    ("risk", "Find the highest-impact plausible failure that is not already covered by current evidence."),
    ("alternate-solution", "Offer one materially different solution only if it is simpler or more reliable than the apparent path."),
    ("independent-review", "Perform an independent overall review and return only the single most valuable new finding."),
)


def _owner_work_mode(index: int) -> str:
    if 1 <= index <= 5:
        return "DRAFTER"
    if 6 <= index <= 7:
        return "WRITER"
    if index == 8:
        return "VALIDATOR"
    return "BOOST_READ_SUMMARY"


def commander_lanes() -> tuple[CommanderLane, ...]:
    return tuple(
        CommanderLane(f"CMD-{index:02d}", role, instruction, work_mode=_owner_work_mode(index))
        for index, (role, instruction) in enumerate(_ROLES, start=1)
    )


def commander_result_schema() -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["lane_id", "status", "summary", "findings", "evidence_refs", "candidate_actions", "uncertainties"],
        "properties": {
            "lane_id": {"type": "string", "pattern": r"^CMD-(0[1-9]|[12][0-9]|30)$"},
            "status": {"type": "string", "enum": ["NO_FINDING", "USEFUL"]},
            "summary": {"type": "string", "maxLength": 1200},
            "findings": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 900}},
            "evidence_refs": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 700}},
            "candidate_actions": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 900}},
            "uncertainties": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 700}},
        },
    }


def project_scope_id(task_memory: Mapping[str, object], project_root: Path) -> str:
    scope_ref = str(task_memory.get("scope_ref") or "").strip()
    match = re.match(r"^task://([^/]+)/", scope_ref)
    if match and match.group(1):
        return match.group(1)
    resolved = str(Path(project_root).resolve())
    return "path-sha256:" + hashlib.sha256(resolved.encode("utf-8")).hexdigest()


def commander_cache_key(
    project_scope: str,
    task_id: str,
    task_state_digest: str,
    projection_digest: str,
    lane_id: str,
    role: str,
    provider: str,
) -> str:
    payload = {
        "project_scope": str(project_scope),
        "task_id": str(task_id),
        "task_state_digest": str(task_state_digest),
        "projection_digest": str(projection_digest),
        "lane_id": str(lane_id),
        "role": str(role),
        "provider": str(provider),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _credential_present(env: Mapping[str, str], key: str) -> bool:
    value = str(env.get(key, "")).strip()
    if not value:
        return False
    upper = key.upper()
    if any(marker in upper for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
        if len(value) < 8 or value.lower() in {"none", "null", "unset", "placeholder", "changeme"}:
            return False
    return True


def _model_env_name(provider_id: str) -> str:
    return "MINITZ_" + re.sub(r"[^A-Z0-9]+", "_", provider_id.upper()).strip("_") + "_MODEL"


def eligible_external_providers(registry: Mapping[str, object], env: Mapping[str, str]) -> tuple[str, ...]:
    providers = registry.get("providers") if isinstance(registry.get("providers"), Mapping) else {}
    routes = registry.get("routes") if isinstance(registry.get("routes"), Mapping) else {}
    route = routes.get("llm.fast") if isinstance(routes.get("llm.fast"), list) else []
    result: list[str] = []
    for raw_id in route:
        provider_id = str(raw_id)
        if provider_id == "ollama-qwen":
            continue
        definition = providers.get(provider_id) if isinstance(providers, Mapping) else None
        if not isinstance(definition, Mapping) or definition.get("enabled") is False:
            continue
        required = [str(item) for item in definition.get("required_env", [])]
        if any(not _credential_present(env, key) for key in required):
            continue
        default_model = definition.get("default_model")
        if not (isinstance(default_model, str) and default_model.strip()) and not str(env.get(_model_env_name(provider_id), "")).strip():
            continue
        result.append(provider_id)
    return tuple(result)


def eligible_external_providers_from_status(
    registry: Mapping[str, object],
    status_payload: Mapping[str, object],
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    """Resolve healthy API helpers from non-secret provider status metadata."""
    if limit < 1:
        return ()
    providers = registry.get("providers") if isinstance(registry.get("providers"), Mapping) else {}
    routes = registry.get("routes") if isinstance(registry.get("routes"), Mapping) else {}
    route = [str(item) for item in routes.get("llm.fast", [])] if isinstance(routes.get("llm.fast"), list) else []
    raw_statuses = status_payload.get("providers") if isinstance(status_payload.get("providers"), list) else []
    states = {
        str(item.get("id") or ""): str(item.get("state") or "")
        for item in raw_statuses if isinstance(item, Mapping)
    }
    selected: list[str] = []
    for provider_id in route:
        if provider_id == "ollama-qwen" or states.get(provider_id) != "CONFIGURED":
            continue
        definition = providers.get(provider_id) if isinstance(providers, Mapping) else None
        if not isinstance(definition, Mapping) or definition.get("enabled") is False:
            continue
        # The resource call must be executable without a hidden per-call model choice.
        default_model = definition.get("default_model")
        if not isinstance(default_model, str) or not default_model.strip():
            continue
        selected.append(provider_id)
        if len(selected) >= limit:
            break
    return tuple(selected)


def select_provider_pool(
    candidates: Iterable[str],
    blocked: Iterable[str] = (),
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    """Pick a small active pool without reusing providers under bounded backoff."""
    if limit < 1:
        return ()
    ordered: list[str] = []
    for raw in candidates:
        provider = str(raw).strip()
        if provider and provider not in ordered:
            ordered.append(provider)
    blocked_set = {str(item) for item in blocked if str(item)}
    available = [provider for provider in ordered if provider not in blocked_set]
    # If every configured provider is backed off, retain the original pool only
    # to expose its backoff state; callers still must not launch blocked work.
    selected = available if available else ordered
    return tuple(selected[:limit])


def provider_schedule(
    lanes: Iterable[CommanderLane],
    providers: Iterable[str],
    *,
    per_provider_limit: int = DEFAULT_REMOTE_PROVIDER_MAX_INFLIGHT,
) -> dict[str, str | None]:
    lane_list = list(lanes)
    provider_list = [str(item) for item in providers if str(item)]
    result: dict[str, str | None] = {lane.lane_id: None for lane in lane_list}
    if not provider_list or per_provider_limit < 1:
        return result
    counts = {provider: 0 for provider in provider_list}
    cursor = 0
    for lane in lane_list:
        assigned = None
        for _ in range(len(provider_list)):
            provider = provider_list[cursor % len(provider_list)]
            cursor += 1
            if counts[provider] < per_provider_limit:
                counts[provider] += 1
                assigned = provider
                break
        if assigned is None:
            break
        result[lane.lane_id] = assigned
    return result


def _clip(value: object, maximum: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= maximum else text[: maximum - 1] + "…"


def _clip_list(value: object, *, items: int, chars: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:items]:
        if isinstance(item, Mapping):
            result.append(_clip(json.dumps(dict(item), sort_keys=True, separators=(",", ":")), chars))
        else:
            result.append(_clip(item, chars))
    return [item for item in result if item]


def bounded_context(
    task_memory: Mapping[str, object],
    projection: Mapping[str, object],
    *,
    maximum_bytes: int = 6000,
) -> dict[str, object]:
    if maximum_bytes < 1200:
        raise ValueError("maximum_bytes is too small for Commander context")
    capabilities = projection.get("capabilities") if isinstance(projection.get("capabilities"), Mapping) else {}
    failures = projection.get("failures") if isinstance(projection.get("failures"), list) else []
    context: dict[str, object] = {
        "task_id": _clip(task_memory.get("task_id") or projection.get("task_id"), 120),
        "title": _clip(task_memory.get("title"), 320),
        "task_class": _clip(task_memory.get("task_class"), 80),
        "summary": _clip(task_memory.get("summary"), 1200),
        "next_action": _clip(task_memory.get("next_action"), 480),
        "evidence": _clip_list(task_memory.get("evidence"), items=6, chars=240),
        "dirty_paths": _clip_list(task_memory.get("dirty_paths"), items=12, chars=160),
        "failures": _clip_list(failures, items=4, chars=260),
        "source_refs": _clip_list(projection.get("source_refs"), items=8, chars=160),
        "capabilities": [str(key)[:100] for key in list(capabilities)[:12]],
    }
    def size() -> int:
        return len(json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    list_keys = ("dirty_paths", "source_refs", "evidence", "failures", "capabilities")
    while size() > maximum_bytes:
        changed = False
        for key in list_keys:
            values = context.get(key)
            if isinstance(values, list) and values:
                values.pop()
                changed = True
                if size() <= maximum_bytes:
                    break
        if size() <= maximum_bytes:
            break
        summary = str(context.get("summary") or "")
        if len(summary) > 300:
            context["summary"] = _clip(summary, max(300, len(summary) - 200))
            changed = True
        elif not changed:
            break
    if size() > maximum_bytes:
        raise ValueError("Commander context cannot be bounded within maximum_bytes")
    return context


def commander_packet(
    *,
    lane: CommanderLane,
    project_scope: str,
    task_id: str,
    task_state_digest: str,
    projection_digest: str,
    requested_provider: str,
    context: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema": "minitz.commander_packet/v1",
        "authority": "NONE",
        "lane_id": lane.lane_id,
        "role": lane.role,
        "work_mode": lane.work_mode,
        "instruction": lane.instruction,
        "project_scope": str(project_scope),
        "task_id": str(task_id),
        "task_state_digest": str(task_state_digest),
        "projection_digest": str(projection_digest),
        "requested_provider": str(requested_provider),
        "context": dict(context),
    }


def commander_prompt(packet: Mapping[str, object]) -> str:
    return (
        "MINITZ_COMMANDER_ASSIST\n"
        "AUTHORITY: NONE\n"
        "READ_ONLY_ASSIST_ONLY\n"
        "DO_NOT_MODIFY_FILES\n"
        "DO_NOT_RUN_MUTATING_COMMANDS\n"
        "DO_NOT_COMMIT_PUSH_PUBLISH\n"
        "DO_NOT_COMPLETE_OR_ADVANCE_TASK\n"
        "DO_NOT_CHANGE_TASK_STATUS_OR_ORDER\n"
        "STRICT_JSON_ONLY\n"
        f"LANE: {packet.get('lane_id')}\nROLE: {packet.get('role')}\nWORK_MODE: {packet.get('work_mode')}\n"
        "DRAFTER means draft a concrete candidate approach. WRITER means produce candidate implementation text or patch guidance for the canonical writer without mutating files. "
        "VALIDATOR means falsify/check the candidate against evidence. BOOST_READ_SUMMARY means read, compare, summarize, and surface only high-value deltas.\n"
        f"ROLE_INSTRUCTION: {packet.get('instruction')}\n"
        "Return exactly one JSON object with fields lane_id,status,summary,findings,evidence_refs,candidate_actions,uncertainties. "
        "Keep the entire JSON under 2200 characters: summary <= 500 characters; at most 2 findings, 4 evidence_refs, 2 candidate_actions, and 2 uncertainties. "
        "status must be NO_FINDING or USEFUL. Do not invent file contents, commands already run, test results, or evidence. "
        "Prefer one high-value grounded finding over broad advice.\n"
        "USEFUL requires nonempty findings, candidate_actions, and evidence_refs. Use exact supplied source_refs or context.FIELD / context.FIELD[index] as references. Never invent references. NO_FINDING is valid when no grounded new finding exists.\n"
        "PACKET_JSON:\n"
        + json.dumps(dict(packet), sort_keys=True, separators=(",", ":"))
    )


def build_resource_command(
    provider: str, *, max_tokens: int = DEFAULT_RESULT_MAX_TOKENS,
    minitz_bin: str | None = None, response_schema: Mapping[str, object] | None = None,
    disable_reasoning: bool = False,
) -> list[str]:
    executable = minitz_bin or os.environ.get("MINITZ_BIN", "/usr/local/bin/minitz-resource")
    command = [
        str(executable), "fast-llm", "--provider", str(provider),
        "--max-tokens", str(int(max_tokens)), "--max-failover-attempts", "1",
    ]
    if response_schema is not None:
        command.extend(["--response-schema-json", json.dumps(dict(response_schema), sort_keys=True, separators=(",", ":"))])
    if disable_reasoning:
        command.append("--disable-reasoning")
    return command


def _json_text(text: str) -> str:
    value = str(text or "").strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.I | re.S)
    return fence.group(1).strip() if fence else value


def parse_resource_result(stdout_text: str) -> tuple[dict[str, object], dict[str, object]]:
    payload = json.loads(str(stdout_text or ""))
    if not isinstance(payload, Mapping):
        raise ValueError("Commander resource result must be an object")
    body = json.loads(_json_text(str(payload.get("text") or "")))
    if not isinstance(body, Mapping):
        raise ValueError("Commander provider text must contain one JSON object")
    meta = {
        "provider": payload.get("provider"),
        "model": payload.get("model"),
        "latency_ms": payload.get("latency_ms"),
        "usage": dict(payload.get("usage") or {}) if isinstance(payload.get("usage"), Mapping) else {},
        "routing_evidence": dict(payload.get("routing_evidence") or {}) if isinstance(payload.get("routing_evidence"), Mapping) else {},
    }
    return dict(body), meta


def validate_commander_result(packet: Mapping[str, object], value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("Commander result must be an object")
    allowed = {"lane_id", "status", "summary", "findings", "evidence_refs", "candidate_actions", "uncertainties"}
    if set(value) != allowed:
        raise ValueError("Commander result fields do not match schema")
    if value.get("lane_id") != packet.get("lane_id"):
        raise ValueError("Commander lane_id mismatch")
    if value.get("status") not in {"NO_FINDING", "USEFUL"}:
        raise ValueError("Commander result status is invalid")
    summary = value.get("summary")
    if not isinstance(summary, str) or len(summary) > 1200:
        raise ValueError("Commander summary is invalid")
    limits = {
        "findings": (6, 900),
        "evidence_refs": (12, 700),
        "candidate_actions": (6, 900),
        "uncertainties": (6, 700),
    }
    result: dict[str, object] = {"lane_id": str(value["lane_id"]), "status": str(value["status"]), "summary": summary.strip()}
    for key, (count_limit, char_limit) in limits.items():
        raw = value.get(key)
        if not isinstance(raw, list) or len(raw) > count_limit:
            raise ValueError(f"Commander {key} is invalid")
        clean: list[str] = []
        for item in raw:
            if not isinstance(item, str) or len(item) > char_limit:
                raise ValueError(f"Commander {key} item is invalid")
            if item.strip():
                clean.append(item.strip())
        result[key] = clean
    return result


_QUOTA_RE = re.compile(r"(?:out\s+of\s+credit|usage\s+limit|rate\s+limit|quota[^\n]{0,80}(?:exhaust|reached|exceed)|resource\s+exhausted|payment\s+required|http[_ -]?(?:402|429))", re.I)
_OFFLINE_RE = re.compile(r"(?:command\s+not\s+found|no\s+such\s+file|connection\s+refused|network\s+is\s+unreachable|name\s+or\s+service\s+not\s+known)", re.I)


def execution_failure_detail(returncode: int, stdout_text: str, stderr_text: str) -> str:
    """Only execution diagnostics may affect provider health, never model text."""
    if int(returncode) == 0:
        return ""
    if str(stderr_text or "").strip():
        return str(stderr_text).strip()
    try:
        envelope = json.loads(stdout_text)
    except (ValueError, TypeError):
        envelope = None
    if isinstance(envelope, Mapping) and "text" not in envelope and envelope.get("status") == "ERROR":
        return str(envelope.get("error") or f"Commander exited {returncode}")
    return f"Commander exited {returncode}"


def result_scoped_failure(payload: Mapping[str, object]) -> bool:
    return payload.get("failure_scope") == "RESULT" or payload.get("failure_type") in {"INVALID_RESULT", "VALIDATION_REJECTED"}


def classify_failure(returncode: int, text: str) -> str:
    # Successful generated content is never execution-error evidence.
    if int(returncode) == 0:
        return "ACTIVE"
    value = str(text or "")
    if _QUOTA_RE.search(value):
        return "OUT_OF_CREDIT"
    if int(returncode) == 127 or _OFFLINE_RE.search(value):
        return "OFFLINE"
    if int(returncode) == 0:
        return "ACTIVE"
    return "NEEDS_MODIFICATION"


def failure_retry_after(
    status: str,
    *,
    now: datetime | None = None,
    detail: str = "",
) -> str | None:
    delays = {"OFFLINE": 300, "OUT_OF_CREDIT": 1800, "NEEDS_MODIFICATION": 900}
    delay = delays.get(str(status))
    if delay is None:
        return None
    if str(status) == "OUT_OF_CREDIT" and re.search(r"(?:http[_ -]?429|rate\s+limit|too\s+many\s+requests)", str(detail or ""), re.I):
        delay = 60
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return (observed + timedelta(seconds=delay)).isoformat()


def lease_record(
    cache_key: str,
    task_id: str,
    lane_id: str,
    provider: str,
    pid: int,
    *,
    now: datetime | None = None,
    ttl_seconds: int = 180,
) -> dict[str, object]:
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return {
        "schema": "minitz.commander_lease/v1",
        "authority": "NONE",
        "cache_key": str(cache_key),
        "task_id": str(task_id),
        "lane_id": str(lane_id),
        "provider": str(provider),
        "pid": int(pid),
        "started_at": observed.isoformat(),
        "expires_at": (observed + timedelta(seconds=max(1, int(ttl_seconds)))).isoformat(),
    }


def lease_is_stale(
    lease: Mapping[str, object],
    *,
    now: datetime | None = None,
    pid_alive: Callable[[int], bool] | None = None,
) -> bool:
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    try:
        expires = datetime.fromisoformat(str(lease.get("expires_at") or "").replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        pid = int(lease.get("pid") or 0)
    except (TypeError, ValueError):
        return True
    if observed >= expires:
        return True
    checker = pid_alive or (lambda value: value > 0 and Path(f"/proc/{value}").exists())
    return pid <= 0 or not checker(pid)


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    target = Path(path)
    _assert_noncanonical_control_write(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def public_summary(index: Mapping[str, object]) -> dict[str, object]:
    lanes = index.get("lanes") if isinstance(index.get("lanes"), list) else []
    safe_lanes: list[dict[str, object]] = []
    useful = rejected = inflight = active = 0
    for raw in lanes:
        if not isinstance(raw, Mapping):
            continue
        status = str(raw.get("status") or "OFFLINE")
        activity = str(raw.get("activity") or "UNASSIGNED")
        active += status == "ACTIVE"
        useful += activity == "USEFUL"
        rejected += activity == "REJECTED"
        inflight += activity == "RUNNING"
        safe_lanes.append({
            "lane_id": str(raw.get("lane_id") or ""),
            "role": str(raw.get("role") or ""),
            "status": status if status in COMMANDER_STATUSES else "NEEDS_MODIFICATION",
            "activity": activity,
            "provider": str(raw.get("provider") or "") or None,
        })
    statuses = {str(row.get("status") or "OFFLINE") for row in safe_lanes}
    if "ACTIVE" in statuses:
        aggregate_status = "ACTIVE"
    elif "OUT_OF_CREDIT" in statuses:
        aggregate_status = "OUT_OF_CREDIT"
    elif "NEEDS_MODIFICATION" in statuses:
        aggregate_status = "NEEDS_MODIFICATION"
    else:
        aggregate_status = "OFFLINE"
    return {
        "schema": "minitz.commander_public_summary/v1",
        "authority": "NONE",
        "task_id": str(index.get("task_id") or ""),
        "status": aggregate_status,
        "total_lanes": int(index.get("total_lanes") or COMMANDER_LANE_COUNT),
        "active": active,
        "inflight": inflight,
        "useful": useful,
        "rejected": rejected,
        "lanes": safe_lanes,
    }


def validate_result_quality(packet: Mapping[str, object], result: Mapping[str, object]) -> dict[str, object]:
    """Admit grounded assistance, never claim implementation correctness from prose."""
    context = packet.get("context")
    if not isinstance(context, Mapping):
        raise ValueError("Commander quality evidence context is unavailable")
    if not str(result.get("summary") or "").strip():
        raise ValueError("Commander quality summary is empty")
    if result.get("status") == "USEFUL":
        if not result.get("findings"):
            raise ValueError("Commander USEFUL requires concrete findings")
        if not result.get("candidate_actions"):
            raise ValueError("Commander USEFUL requires a candidate action")
        if not result.get("evidence_refs"):
            raise ValueError("Commander USEFUL requires grounded evidence")
    allowed: set[str] = set()
    for key, value in context.items():
        if value not in (None, "", [], {}):
            allowed.add(f"context.{key}")
        if isinstance(value, list):
            for index, item in enumerate(value):
                allowed.add(f"context.{key}[{index}]")
                if key in {"source_refs", "evidence", "dirty_paths"} and isinstance(item, str):
                    allowed.add(item)
    refs = result.get("evidence_refs") or []
    if any(ref not in allowed for ref in refs):
        raise ValueError("Commander evidence reference is not in the supplied task context")
    return {
        "schema": "minitz.commander_quality/v1", "status": "PASS",
        "evaluator": "grounded-candidate-v1", "evidence_refs_checked": len(refs),
        "task_completion_authority": False,
        "functional_acceptance": "REQUIRES_TASK_VALIDATION",
    }


def local_capacity_observation(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Expose local pressure as telemetry only; never gate a qualified resident resource."""
    return {
        "authority": "OBSERVATION_ONLY",
        "admitted": True,
        "reason": "OBSERVATION_ONLY",
        "observation": dict(snapshot),
    }
