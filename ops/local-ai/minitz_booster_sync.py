from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping
from datetime import datetime, timezone

import minitz_task_guidance as task_guidance
import minitz_boost_fabric as boost_fabric

try:
    import minitz_secret_boundary as secret_boundary
except ModuleNotFoundError:
    _SECRET_BOUNDARY_PATH = Path(__file__).with_name("minitz_secret_boundary.py")
    _SECRET_BOUNDARY_SPEC = __import__("importlib.util").util.spec_from_file_location("_minitz_secret_boundary", _SECRET_BOUNDARY_PATH)
    if not _SECRET_BOUNDARY_SPEC or not _SECRET_BOUNDARY_SPEC.loader:
        raise
    secret_boundary = __import__("importlib.util").util.module_from_spec(_SECRET_BOUNDARY_SPEC)
    _SECRET_BOUNDARY_SPEC.loader.exec_module(secret_boundary)

try:
    import minitz_private_secret_verifier as privacy_verifier
except ModuleNotFoundError:
    _PRIVACY_VERIFIER_PATH = Path(__file__).with_name("minitz_private_secret_verifier.py")
    _PRIVACY_VERIFIER_SPEC = __import__("importlib.util").util.spec_from_file_location("_minitz_private_secret_verifier", _PRIVACY_VERIFIER_PATH)
    if not _PRIVACY_VERIFIER_SPEC or not _PRIVACY_VERIFIER_SPEC.loader:
        raise
    privacy_verifier = __import__("importlib.util").util.module_from_spec(_PRIVACY_VERIFIER_SPEC)
    _PRIVACY_VERIFIER_SPEC.loader.exec_module(privacy_verifier)
_PROTECTED_CANONICAL_CONTROL_NAMES = frozenset({
    "TASK_PROGRAM.json",
    "TASK_PROGRAM_CHANGE_LEDGER.jsonl",
    "runtime.json",
    "current-task.json",
    "compacted-memory.json",
    "biella-publication.json",
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


_COMPLETE = {"COMPLETE", "COMPLETE_ALREADY", "COMPLETED", "RETIRED", "OBSOLETE", "DUPLICATE"}

BOOSTER_CHANNELS: dict[str, tuple[tuple[str, str], ...]] = {
    "BOOST-01": (("CMD-01", "requirements"), ("CMD-02", "task-boundary"), ("CMD-03", "source-map"), ("CMD-12", "memory-context"), ("CMD-20", "dependency"), ("CMD-28", "risk")),
    "BOOST-02": (("CMD-04", "architecture"), ("CMD-05", "implementation"), ("CMD-13", "cache-reuse"), ("CMD-16", "performance"), ("CMD-27", "simplification"), ("CMD-29", "alternate-solution")),
    "BOOST-03": (("CMD-06", "integration"), ("CMD-14", "provider-routing"), ("CMD-15", "concurrency"), ("CMD-18", "runtime"), ("CMD-19", "api-contract"), ("CMD-21", "data-flow")),
    "BOOST-04": (("CMD-07", "tests"), ("CMD-08", "regression"), ("CMD-09", "validation"), ("CMD-10", "failure-triage"), ("CMD-17", "build"), ("CMD-26", "resilience")),
    "BOOST-05": (("CMD-11", "checkpoint-continuity"), ("CMD-22", "observability"), ("CMD-23", "evidence"), ("CMD-24", "publication"), ("CMD-25", "portability"), ("CMD-30", "independent-review")),
}

BOOSTER_DOMAINS = {
    "BOOST-01": "Contract / Authority",
    "BOOST-02": "Core Engineering",
    "BOOST-03": "Runtime / Integration",
    "BOOST-04": "Qualification / Tests / Regression / Validation / Failure Triage / Resilience",
    "BOOST-05": "Continuity / Delivery",
}

_SERVICE_CAPABILITIES = {
    "BOOST-01": ("llm.code", "compute.remote"),
    "BOOST-02": ("llm.reasoning", "observability.query"),
    "BOOST-03": ("llm.code", "compute.remote"),
    "BOOST-04": ("llm.reasoning", "research.search", "browser.actions"),
    "BOOST-05": ("llm.reasoning", "vector.search"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_status(value: object) -> str:
    return str(value or "UNKNOWN").upper()


def _hard_dependencies(task: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    raw = task.get("dependencies") if isinstance(task.get("dependencies"), list) else []
    for dep in raw:
        if not isinstance(dep, Mapping):
            continue
        if str(dep.get("dependency_type") or "").upper() != "HARD":
            continue
        ref = str(dep.get("task_ref") or dep.get("task_id") or "").strip()
        if ref and ref not in result:
            result.append(ref)
    raw_depends = task.get("depends_on") if isinstance(task.get("depends_on"), list) else []
    for dep in raw_depends:
        ref = str(dep).strip()
        if ref and ref not in result:
            result.append(ref)
    return result


def reconcile_ledger(program: Mapping[str, Any], ledger: Mapping[str, Any], *, program_sha256: str | None = None) -> dict[str, Any]:
    result = json.loads(json.dumps(dict(ledger)))
    allowed = [str(x) for x in result.get("allowed_work_status", [])]
    if "NEEDS_REBASE" not in allowed:
        allowed.append("NEEDS_REBASE")
    result["allowed_work_status"] = allowed
    result["canonical_program_revision"] = int(program.get("revision") or 0)
    result["canonical_program_sha256"] = str(program_sha256 or program.get("_observed_sha256") or "")
    result["last_reconciled_at"] = _now()
    tasks = {str(t.get("task_id")): t for t in program.get("tasks", []) if isinstance(t, Mapping) and t.get("task_id")}
    status_by_id = {task_id: _canonical_status(task.get("status")) for task_id, task in tasks.items()}
    items = result.get("items") if isinstance(result.get("items"), list) else []
    for row in items:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("canonical_task_id") or "")
        task = tasks.get(task_id)
        if task is None:
            row["canonical_status"] = "MISSING"
            if row.get("work_status") not in {"DONE_LOCAL", "HANDOFF_READY", "SUPERSEDED"}:
                row["work_status"] = "SUPERSEDED"
            continue
        previous_revision = row.get("canonical_task_revision")
        previous_sha = str(row.get("canonical_task_sha256") or "")
        revision = task.get("revision")
        digest = str(task.get("task_record_sha256") or "")
        identity_changed = (previous_revision is not None and previous_revision != revision) or (previous_sha and digest and previous_sha != digest)
        row["canonical_task_revision"] = revision
        row["canonical_task_sha256"] = digest
        row["canonical_status"] = _canonical_status(task.get("status"))
        row["title"] = str(task.get("title") or task_id)
        objective = task.get("objective") if isinstance(task.get("objective"), Mapping) else {}
        row["task_description"] = str(objective.get("desired_state") or objective.get("reason") or task.get("title") or task_id)[:2400]
        primary_paths: list[str] = []
        for source in task.get("inputs", []) if isinstance(task.get("inputs"), list) else []:
            if isinstance(source, Mapping) and source.get("path"):
                path_value = str(source.get("path"))
                if path_value not in primary_paths:
                    primary_paths.append(path_value)
        scope = task.get("write_scope") if isinstance(task.get("write_scope"), Mapping) else {}
        for raw_path in scope.get("allowed_paths", []) if isinstance(scope.get("allowed_paths"), list) else []:
            path_value = str(raw_path)
            if path_value and path_value not in primary_paths:
                primary_paths.append(path_value)
        row["primary_files_or_scopes"] = primary_paths[:64]
        hard = _hard_dependencies(task)
        unmet = [dep for dep in hard if status_by_id.get(dep, "UNKNOWN") not in _COMPLETE]
        row["hard_dependencies"] = hard
        row["unmet_hard_dependencies"] = unmet
        current = str(row.get("work_status") or "QUEUED")
        if row["canonical_status"] in _COMPLETE:
            if current not in {"DONE_LOCAL", "HANDOFF_READY", "SUPERSEDED"}:
                row["work_status"] = "SUPERSEDED"
        elif unmet:
            if current not in {"DONE_LOCAL", "HANDOFF_READY", "SUPERSEDED"}:
                row["work_status"] = "BLOCKED_CANONICAL_DEPENDENCY"
        elif identity_changed:
            if current not in {"SUPERSEDED"}:
                row["work_status"] = "NEEDS_REBASE"
                row["rebase_reason"] = "canonical task revision/digest changed; validate prior Booster evidence against current task identity"
        elif current == "BLOCKED_CANONICAL_DEPENDENCY":
            row["work_status"] = "QUEUED"
    return result


def _current_task_row(program: Mapping[str, Any]) -> dict[str, Any]:
    current = program.get("current_execution") if isinstance(program.get("current_execution"), Mapping) else {}
    task_id = str(current.get("task_id") or "")
    if not task_id:
        task_id = str(boost_fabric.build_task_plan(program).get("current_task_id") or "")
    if not task_id:
        return {}
    task = next((dict(item) for item in program.get("tasks", []) if isinstance(item, Mapping) and str(item.get("task_id") or "") == task_id), None)
    if task is None or _canonical_status(task.get("status")) in _COMPLETE:
        return {}
    revision = current.get("task_revision")
    digest = str(current.get("task_sha256") or "")
    if revision is not None and int(task.get("revision") or 0) != int(revision):
        raise ValueError("current Task Program revision does not match current_execution")
    if digest and str(task.get("task_record_sha256") or "") != digest:
        raise ValueError("current Task Program digest does not match current_execution")
    return task


def select_next_work(ledger: Mapping[str, Any], booster_id: str) -> dict[str, Any] | None:
    candidates = []
    priority = {"IN_PROGRESS": 0, "NEEDS_REBASE": 1, "QUEUED": 2}
    for row in ledger.get("items", []) if isinstance(ledger.get("items"), list) else []:
        if not isinstance(row, Mapping) or str(row.get("booster") or "") != booster_id:
            continue
        if _canonical_status(row.get("canonical_status")) in _COMPLETE:
            continue
        status = str(row.get("work_status") or "QUEUED")
        if status not in priority:
            continue
        if row.get("unmet_hard_dependencies"):
            continue
        candidates.append((priority[status], int(row.get("queue_order") or 10**9), row))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]  # live mutable row when caller owns ledger dict


def _content_text(memory_index: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    ref = str(row.get("content_ref") or "")
    raw = memory_index.get("content", {}).get(ref) if isinstance(memory_index.get("content"), Mapping) else None
    if isinstance(raw, Mapping):
        for key in ("text", "content", "summary", "value"):
            if raw.get(key) is not None:
                return str(raw.get(key))
        return json.dumps(dict(raw), sort_keys=True, separators=(",", ":"))
    return str(raw or "")


def _relevant_memory(memory_index: Mapping[str, Any], task: Mapping[str, Any], *, limit: int = 14) -> list[dict[str, Any]]:
    task_id = str(task.get("task_id") or "")
    title = str(task.get("title") or "").lower()
    title_tokens = [tok for tok in title.replace("/", " ").replace("-", " ").split() if len(tok) >= 5][:8]
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for idx, raw in enumerate(memory_index.get("records", []) if isinstance(memory_index.get("records"), list) else []):
        if not isinstance(raw, Mapping):
            continue
        text = _content_text(memory_index, raw)
        score = 0
        if str(raw.get("task_id") or "") == task_id:
            score += 100
        lower = text.lower()
        if task_id and task_id.lower() in lower:
            score += 40
        score += sum(3 for tok in title_tokens if tok in lower)
        if str(raw.get("scope_ref") or "") == "scope://minitz/system" and str(raw.get("category") or "") == "instruction":
            score += 5
        if score <= 0:
            continue
        row = {
            "category": str(raw.get("category") or ""),
            "task_id": raw.get("task_id"),
            "task_revision": raw.get("task_revision"),
            "task_sha256": raw.get("task_sha256") or raw.get("task_record_sha256"),
            "scope_ref": raw.get("scope_ref"),
            "source_ref": str(raw.get("source_ref") or ""),
            "content_ref": str(raw.get("content_ref") or ""),
            "text": text[:900],
        }
        scored.append((score, -idx, row))
    scored.sort(reverse=True, key=lambda x: (x[0], x[1]))
    ordered = [row for _, _, row in scored]
    return secret_boundary.filter_booster_memory(
        ordered,
        task_id=task_id,
        task_revision=int(task.get("revision") or 0),
        task_sha256=str(task.get("task_record_sha256") or ""),
    )[:limit]


def _incoming_handoffs(ledger: Mapping[str, Any], booster_id: str) -> list[dict[str, Any]]:
    out = []
    for raw in ledger.get("items", []) if isinstance(ledger.get("items"), list) else []:
        if not isinstance(raw, Mapping) or str(raw.get("work_status") or "") != "HANDOFF_READY":
            continue
        if str(raw.get("handoff_to") or "") != booster_id:
            continue
        out.append({
            "from_booster": str(raw.get("booster") or ""),
            "task_id": str(raw.get("canonical_task_id") or ""),
            "summary": str(raw.get("summary") or "")[:1200],
            "files_changed": [str(x) for x in raw.get("files_changed", [])][:20],
            "evidence_refs": [str(x) for x in raw.get("evidence_refs", [])][:20],
        })
    return out[:8]


def _service_recommendations(provider_registry: Mapping[str, Any], booster_id: str) -> dict[str, Any]:
    policy = provider_registry.get("policy") if isinstance(provider_registry.get("policy"), Mapping) else {}
    loop = policy.get("resource_loop") if isinstance(policy.get("resource_loop"), Mapping) else {}
    routes = provider_registry.get("routes") if isinstance(provider_registry.get("routes"), Mapping) else {}
    recommendations = []
    for capability in _SERVICE_CAPABILITIES.get(booster_id, ("llm.code",)):
        providers = [str(x) for x in routes.get(capability, [])] if isinstance(routes.get(capability), list) else []
        recommendations.append({"capability": capability, "providers": providers[:6], "dispatch": "RECOMMEND_ONLY"})
    return {
        "primary_local": "ollama-qwen",
        "dispatch_allowed": False,
        "external_loop_state": str(loop.get("state") or "RESERVED_NOT_STARTED"),
        "selection_law": "task-fit capability pool; rotate equivalents before reuse when later authorized",
        "recommendations": recommendations,
    }


def _project_scope_id(
    program: Mapping[str, Any],
    memory_index: Mapping[str, Any],
    projection: Mapping[str, Any] | None,
) -> str:
    if isinstance(projection, Mapping):
        task_memory = projection.get("task_memory") if isinstance(projection.get("task_memory"), Mapping) else {}
        scope_ref = str(task_memory.get("scope_ref") or "")
        match = re.match(r"^task://([^/]+)/", scope_ref)
        if match and match.group(1):
            return match.group(1)
    project_id = str(program.get("project_id") or "").strip()
    if project_id:
        return project_id
    project_root = str(memory_index.get("project_root") or "").strip()
    if project_root:
        return "path-sha256:" + hashlib.sha256(str(Path(project_root).resolve()).encode("utf-8")).hexdigest()
    program_id = str(program.get("program_id") or "").strip()
    if program_id:
        return "program:" + program_id
    raise ValueError("Booster cache requires a Project scope identity")


def build_context_pack(
    program: Mapping[str, Any],
    ledger: Mapping[str, Any],
    booster_id: str,
    *,
    memory_index: Mapping[str, Any],
    projection: Mapping[str, Any] | None,
    provider_registry: Mapping[str, Any],
    maximum_bytes: int = 32000,
    guidance_root: Path | None = None,
) -> dict[str, Any]:
    if booster_id not in BOOSTER_CHANNELS:
        raise ValueError("unknown Booster")
    selected = select_next_work(ledger, booster_id)
    task_index = {str(t.get("task_id")): t for t in program.get("tasks", []) if isinstance(t, Mapping)}
    task = task_index.get(str((selected or {}).get("canonical_task_id") or ""), {})
    idle_capacity = selected is None
    if idle_capacity:
        task = _current_task_row(program)
    guidance_doc = None
    if guidance_root is not None and task.get("task_id"):
        guidance_doc = task_guidance.load_task_guidance(program, str(task.get("task_id")), Path(guidance_root))
    pack: dict[str, Any] = {
        "schema": "minitz.booster_context/v1",
        "authority": "NONE",
        "project_scope": _project_scope_id(program, memory_index, projection),
        "progression_authority": False,
        "booster_id": booster_id,
        "idle_capacity": bool(idle_capacity and task),
        "domain": BOOSTER_DOMAINS[booster_id],
        "channels": [{"lane_id": lane, "role": role} for lane, role in BOOSTER_CHANNELS[booster_id]],
        "selected_task": {
            "task_id": task.get("task_id"), "revision": task.get("revision"), "task_record_sha256": task.get("task_record_sha256"),
            "status": task.get("status"), "title": task.get("title"), "objective": task.get("objective"),
            "acceptance": list(task.get("acceptance") or [])[:20], "inputs": list(task.get("inputs") or [])[:20],
            "required_capabilities": list(task.get("required_capabilities") or [])[:20], "write_scope": task.get("write_scope") or {},
        },
        "task_guidance": task_guidance.helper_view(guidance_doc) if isinstance(guidance_doc, Mapping) else None,
        "ledger_entry": dict(selected) if isinstance(selected, Mapping) else None,
        "incoming_handoffs": _incoming_handoffs(ledger, booster_id),
        "memory": {"records": _relevant_memory(memory_index, task)},
        "projection": dict(projection) if isinstance(projection, Mapping) and str(projection.get("task_id") or "") == str(task.get("task_id") or "") else None,
        "services": _service_recommendations(provider_registry, booster_id),
        "context_limits": {"maximum_bytes": maximum_bytes, "load_full_os_memory": False, "load_full_logs": False, "prefer_refs_and_digests": True},
    }
    # Bounded degradation: remove lower-value memory/handoff/projection detail until within budget.
    while len(json.dumps(pack, sort_keys=True, separators=(",", ":")).encode("utf-8")) > maximum_bytes:
        records = pack["memory"]["records"]
        if records:
            records.pop()
            continue
        handoffs = pack["incoming_handoffs"]
        if handoffs:
            handoffs.pop()
            continue
        if pack.get("projection") is not None:
            proj = pack["projection"]
            pack["projection"] = {k: proj.get(k) for k in ("schema", "task_id", "source_refs", "failures") if k in proj}
            if len(json.dumps(pack, sort_keys=True, separators=(",", ":")).encode("utf-8")) <= maximum_bytes:
                break
            pack["projection"] = None
            continue
        raise ValueError("Booster task contract exceeds context budget")
    return secret_boundary.validate_privacy_safe_payload(pack)


def _legacy_context_digest(pack: Mapping[str, Any]) -> str:
    value = json.loads(json.dumps(dict(pack)))
    ledger_entry = value.get("ledger_entry")
    if isinstance(ledger_entry, dict):
        for key in ("cycle_count", "work_status", "started_at", "finished_at", "last_claimed_at", "updated_at", "last_worker"):
            ledger_entry.pop(key, None)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _canonical_list(value: object) -> object:
    if not isinstance(value, list):
        return value
    return sorted(value, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


def context_digest(pack: Mapping[str, Any]) -> str:
    value = json.loads(json.dumps(dict(pack)))
    material: dict[str, Any] = {}
    for key in ("schema", "project_scope", "booster_id", "domain", "selected_task"):
        if key in value:
            material[key] = value[key]
    memory = value.get("memory")
    if isinstance(memory, dict):
        memory = dict(memory)
        if isinstance(memory.get("records"), list):
            memory["records"] = _canonical_list(memory["records"])
        material["memory"] = memory
    projection = value.get("projection")
    if isinstance(projection, dict):
        projection = dict(projection)
        projection.pop("generated_at", None)
        for key, item in list(projection.items()):
            if isinstance(item, list):
                projection[key] = _canonical_list(item)
        material["projection"] = projection
    elif projection is not None:
        material["projection"] = projection

    handoffs = value.get("incoming_handoffs")
    if handoffs is not None:
        material["incoming_handoffs"] = _canonical_list(handoffs)
    ledger = value.get("ledger_entry")
    if isinstance(ledger, dict):
        keep = ("canonical_status", "canonical_task_id", "canonical_task_revision",
                "canonical_task_sha256", "hard_dependencies", "unmet_hard_dependencies",
                "primary_files_or_scopes", "summary", "files_changed", "evidence_refs",
                "next_action", "task_description", "title")
        semantic = {key: ledger[key] for key in keep if key in ledger}
        for key in ("hard_dependencies", "unmet_hard_dependencies", "primary_files_or_scopes",
                    "files_changed", "evidence_refs"):
            if key in semantic:
                semantic[key] = _canonical_list(semantic[key])
        material["ledger_entry"] = semantic
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path = Path(path)
    _assert_noncanonical_control_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def ensure_local_ai_assist(pack: Mapping[str, Any], cache_root: Path, invoke: Callable[[str], Mapping[str, Any]]) -> Path:
    project_scope = str(pack.get("project_scope") or "").strip()
    if not project_scope:
        raise ValueError("Booster cache requires an explicit Project scope")
    digest = context_digest(pack)
    booster = str(pack.get("booster_id") or "BOOST")
    task_id = str((pack.get("selected_task") or {}).get("task_id") or "IDLE") if isinstance(pack.get("selected_task"), Mapping) else "IDLE"
    path = Path(cache_root) / booster / f"{task_id}-{digest[:20]}.json"
    if path.is_file():
        return path
    legacy_digest = _legacy_context_digest(pack)
    legacy_path = Path(cache_root) / booster / f"{task_id}-{legacy_digest[:20]}.json"
    if legacy_path != path and legacy_path.is_file():
        legacy = _read_json(legacy_path)
        if (str(legacy.get("booster_id") or "") == booster and str(legacy.get("task_id") or "") == task_id
                and str(legacy.get("project_scope") or "") == project_scope
                and str(legacy.get("context_digest") or "") == legacy_digest
                and str(legacy.get("provider") or "") == "ollama-qwen"
                and legacy.get("authority") == "NONE" and legacy.get("progression_authority") is False):
            promoted = dict(legacy)
            promoted.update({"context_digest": digest, "material_digest": digest,
                             "cache_key_version": "task-material-v2",
                             "reused_from_context_digest": legacy_digest})
            secret_boundary.validate_privacy_safe_payload(promoted)
            return _atomic_json(path, promoted)
    prompt = (
        "You are local MiniTZ bounded assist. Use only this context. Return concise implementation guidance, likely risks, exact source/test refs, reuse/cache opportunities, and next action. "
        "Do not claim progression/completion and do not request external providers.\nCONTEXT\n" +
        json.dumps(dict(pack), sort_keys=True, separators=(",", ":"))[:14000]
    )
    raw = invoke(prompt)
    payload = {
        "schema": "minitz.booster_local_ai_assist/v1", "authority": "NONE", "progression_authority": False,
        "booster_id": booster, "project_scope": project_scope,
        "task_id": task_id, "context_digest": digest,
        "material_digest": digest, "cache_key_version": "task-material-v2",
        "provider": str(raw.get("provider") or "ollama-qwen"), "model": str(raw.get("model") or ""),
        "text": str(raw.get("text") or "")[:12000], "usage": dict(raw.get("usage") or {}) if isinstance(raw.get("usage"), Mapping) else {},
        "created_at": _now(),
    }
    return _atomic_json(path, payload)


def _bounded_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    text = value.strip()
    if not text or len(text.encode("utf-8")) > maximum:
        raise ValueError(f"{label} is empty or unbounded")
    return text


def _json_object_from_model_text(value: object) -> dict[str, Any]:
    text = _bounded_text(value, "Qwen idle-work result", 24000)
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Qwen idle-work result is not a JSON object")
    value = json.loads(text[start:end + 1])
    if not isinstance(value, Mapping):
        raise ValueError("Qwen idle-work result must be an object")
    return dict(value)


def _normalize_idle_qwen_plan(pack: Mapping[str, Any], raw: Mapping[str, Any]) -> dict[str, Any]:
    if pack.get("idle_capacity") is not True:
        raise ValueError("Qwen idle-work generation requires an idle Booster")
    booster_id = str(pack.get("booster_id") or "")
    if booster_id not in BOOSTER_CHANNELS:
        raise ValueError("unknown Booster")
    task = pack.get("selected_task") if isinstance(pack.get("selected_task"), Mapping) else {}
    task_id = _bounded_text(task.get("task_id"), "Qwen idle-work task_id", 128)
    revision = task.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValueError("Qwen idle-work task revision is invalid")
    task_sha = _bounded_text(task.get("task_record_sha256"), "Qwen idle-work task digest", 64)
    if len(task_sha) != 64 or any(ch not in "0123456789abcdef" for ch in task_sha):
        raise ValueError("Qwen idle-work task digest is not SHA-256")
    canonical = pack.get("canonical_program") if isinstance(pack.get("canonical_program"), Mapping) else {}
    program_revision = canonical.get("revision")
    if isinstance(program_revision, bool) or not isinstance(program_revision, int) or program_revision < 1:
        raise ValueError("Qwen idle-work program revision is invalid")
    program_sha = _bounded_text(canonical.get("sha256"), "Qwen idle-work program digest", 64)
    if len(program_sha) != 64 or any(ch not in "0123456789abcdef" for ch in program_sha):
        raise ValueError("Qwen idle-work program digest is not SHA-256")
    body = _json_object_from_model_text(raw.get("text"))
    summary = _bounded_text(body.get("summary"), "Qwen idle-work summary", 1200)
    units = body.get("work_units")
    if not isinstance(units, list) or not 1 <= len(units) <= 3:
        raise ValueError("Qwen idle-work plan must contain one to three work units")
    allowed_lanes = {lane for lane, _role in BOOSTER_CHANNELS[booster_id]}
    normalized: list[dict[str, Any]] = []
    seen_lanes: set[str] = set()
    for raw_unit in units:
        if not isinstance(raw_unit, Mapping):
            raise ValueError("Qwen idle-work unit must be an object")
        lane_id = _bounded_text(raw_unit.get("lane_id"), "Qwen idle-work lane", 16)
        if lane_id not in allowed_lanes:
            raise ValueError(f"Qwen idle-work lane {lane_id} does not belong to {booster_id}")
        if lane_id in seen_lanes:
            raise ValueError("Qwen idle-work lanes must be distinct")
        seen_lanes.add(lane_id)
        mode = _bounded_text(raw_unit.get("mode"), "Qwen idle-work mode", 32)
        if mode != "READ_ONLY":
            raise ValueError("Qwen idle-generated work is read-only unless a separate isolated write boundary is explicitly proven")
        unit = {
            "title": _bounded_text(raw_unit.get("title"), "Qwen idle-work title", 180),
            "objective": _bounded_text(raw_unit.get("objective"), "Qwen idle-work objective", 900),
            "lane_id": lane_id,
            "evidence_goal": _bounded_text(raw_unit.get("evidence_goal"), "Qwen idle-work evidence goal", 900),
            "mode": mode,
        }
        unit_digest = hashlib.sha256(json.dumps(unit, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        normalized.append({"work_unit_id": "QWEN-" + unit_digest[:16], **unit})
    context_sha = context_digest(pack)
    identity = {
        "booster_id": booster_id, "task_id": task_id, "task_revision": revision,
        "task_sha256": task_sha, "program_revision": program_revision,
        "program_sha256": program_sha, "context_digest": context_sha,
        "summary": summary, "work_units": normalized,
    }
    plan_digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": "minitz.qwen_idle_boost_plan/v1",
        "authority": "NONE_NON_CANONICAL_WORK_COORDINATION",
        "progression_authority": False,
        **identity,
        "plan_digest": plan_digest,
        "provider": str(raw.get("provider") or "ollama-qwen"),
        "model": str(raw.get("model") or ""),
        "usage": dict(raw.get("usage") or {}) if isinstance(raw.get("usage"), Mapping) else {},
        "created_at": _now(),
    }


def ensure_idle_qwen_plan(pack: Mapping[str, Any], cache_root: Path, invoke: Callable[[str], Mapping[str, Any]]) -> Path:
    if pack.get("idle_capacity") is not True:
        raise ValueError("Booster has dependency-ready work; Qwen idle decomposition is not applicable")
    booster_id = str(pack.get("booster_id") or "")
    task = pack.get("selected_task") if isinstance(pack.get("selected_task"), Mapping) else {}
    task_id = _bounded_text(task.get("task_id"), "Qwen idle-work task_id", 128)
    digest = context_digest(pack)
    path = Path(cache_root) / booster_id / f"{task_id}-idle-work-{digest[:20]}.json"
    if path.is_file():
        return path
    lanes = [{"lane_id": lane, "role": role} for lane, role in BOOSTER_CHANNELS[booster_id]]
    prompt = (
        "You are local MiniTZ Qwen decomposing unused Booster capacity for the exact current canonical task. "
        "Return ONLY one JSON object with keys summary and work_units. work_units must contain 1-3 distinct useful non-overlapping entries. "
        "Each entry must contain title, objective, lane_id, evidence_goal, and mode=READ_ONLY. Use only the supplied Booster lanes. "
        "Do not create a new canonical task, change task order/status, claim completion, request external providers, invent paths, or repeat already-finished work. "
        "Prefer work that materially reduces the current writer's remaining uncertainty or validation burden.\n"
        "BOOSTER_LANES=" + json.dumps(lanes, sort_keys=True, separators=(",", ":")) + "\nCONTEXT\n" +
        json.dumps(dict(pack), sort_keys=True, separators=(",", ":"))[:14000]
    )
    plan = _normalize_idle_qwen_plan(pack, invoke(prompt))
    return _atomic_json(path, plan)


def prepare_idle_qwen_plan_for_booster(context_root: Path, cache_root: Path, booster_id: str, *, command: str = "/usr/local/bin/biella") -> Path:
    if booster_id not in BOOSTER_CHANNELS:
        raise ValueError("unknown Booster")
    context_path = Path(context_root) / f"{booster_id}.json"
    if not context_path.is_file():
        raise FileNotFoundError(context_path)
    _require_privacy_qualification(context_path)
    pack = _read_json(context_path)
    secret_boundary.validate_privacy_safe_payload(pack)
    return ensure_idle_qwen_plan(pack, cache_root, lambda prompt: _invoke_local_qwen(prompt, command=command))


def seed_qwen_idle_work(program_path: Path, ledger_path: Path, plan_path: Path) -> dict[str, Any]:
    raw_program = Path(program_path).read_bytes()
    program_sha = hashlib.sha256(raw_program).hexdigest()
    program = json.loads(raw_program)
    if not isinstance(program, Mapping):
        raise ValueError("canonical Task Program must be an object")
    plan = _read_json(Path(plan_path))
    booster_id = str(plan.get("booster_id") or "")
    if booster_id not in BOOSTER_CHANNELS:
        raise ValueError("unknown Booster")
    current_task = _current_task_row(program)
    if not current_task:
        raise ValueError("no current canonical task for Qwen idle work")
    current = program.get("current_execution") if isinstance(program.get("current_execution"), Mapping) else {}
    identity_ok = (
        str(plan.get("task_id") or "") == str(current.get("task_id") or "")
        and int(plan.get("task_revision") or 0) == int(current.get("task_revision") or 0)
        and str(plan.get("task_sha256") or "") == str(current.get("task_sha256") or "")
        and int(plan.get("program_revision") or 0) == int(program.get("revision") or 0)
        and str(plan.get("program_sha256") or "") == program_sha
    )
    if not identity_ok:
        raise ValueError("stale Qwen idle plan cannot enter the Booster ledger")
    units = plan.get("work_units") if isinstance(plan.get("work_units"), list) else []
    if not units:
        raise ValueError("Qwen idle plan contains no work")
    work_id = f"{booster_id}:{current['task_id']}:QWEN:{str(plan.get('plan_digest') or '')[:16]}"
    with _with_ledger_lock(Path(ledger_path)) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        ledger = _read_json(Path(ledger_path))
        reconciled = reconcile_ledger(program, ledger, program_sha256=program_sha)
        existing = next((row for row in reconciled.get("items", []) if isinstance(row, dict) and str(row.get("work_id") or "") == work_id), None)
        if existing is not None:
            _atomic_json(Path(ledger_path), reconciled)
            result = dict(existing)
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            return result
        if select_next_work(reconciled, booster_id) is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            raise ValueError("Booster gained dependency-ready work before Qwen idle plan was seeded")
        items = reconciled.get("items") if isinstance(reconciled.get("items"), list) else []
        order = max((int(row.get("queue_order") or 0) for row in items if isinstance(row, Mapping) and str(row.get("booster") or "") == booster_id), default=0) + 1
        objective = current_task.get("objective") if isinstance(current_task.get("objective"), Mapping) else {}
        primary: list[str] = []
        for source in current_task.get("inputs", []) if isinstance(current_task.get("inputs"), list) else []:
            if isinstance(source, Mapping) and source.get("path") and str(source.get("path")) not in primary:
                primary.append(str(source.get("path")))
        scope = current_task.get("write_scope") if isinstance(current_task.get("write_scope"), Mapping) else {}
        for value in scope.get("allowed_paths", []) if isinstance(scope.get("allowed_paths"), list) else []:
            if str(value) and str(value) not in primary:
                primary.append(str(value))
        row = {
            "work_id": work_id, "booster": booster_id,
            "canonical_task_id": str(current_task.get("task_id") or ""),
            "canonical_task_revision": int(current_task.get("revision") or 0),
            "canonical_task_sha256": str(current_task.get("task_record_sha256") or ""),
            "canonical_status": _canonical_status(current_task.get("status")),
            "title": str(current_task.get("title") or current_task.get("task_id") or "")[:500],
            "task_description": str(objective.get("desired_state") or objective.get("reason") or current_task.get("title") or "")[:2400],
            "hard_dependencies": _hard_dependencies(current_task), "unmet_hard_dependencies": [],
            "primary_files_or_scopes": primary[:64], "queue_order": order,
            "work_status": "QUEUED", "cycle_count": 0, "started_at": None, "finished_at": None,
            "last_claimed_at": None, "last_worker": None, "summary": "", "files_changed": [],
            "evidence_refs": [], "next_action": "", "handoff_to": None,
            "origin": "LOCAL_QWEN_CURRENT_TASK_DECOMPOSITION",
            "progression_authority": False, "write_authority": "READ_ONLY",
            "qwen_plan_ref": str(Path(plan_path)), "qwen_plan_sha256": hashlib.sha256(Path(plan_path).read_bytes()).hexdigest(),
            "qwen_context_digest": str(plan.get("context_digest") or ""), "qwen_work_units": units,
        }
        items.append(row)
        reconciled["items"] = items
        _atomic_json(Path(ledger_path), reconciled)
        result = dict(row)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return result


def collect_current_local_ai_assists(context_root: Path, local_ai_root: Path) -> list[dict[str, Any]]:
    """Collect only Qwen assists bound to the exact current semantic Booster contexts."""
    rows: list[dict[str, Any]] = []
    context_root = Path(context_root); local_ai_root = Path(local_ai_root)
    for booster_id in BOOSTER_CHANNELS:
        context_path = context_root / f"{booster_id}.json"
        if not context_path.is_file():
            continue
        pack = json.loads(context_path.read_text(encoding="utf-8"))
        if not isinstance(pack, Mapping):
            continue
        project_scope = str(pack.get("project_scope") or "").strip()
        if not project_scope:
            continue
        selected = pack.get("selected_task") if isinstance(pack.get("selected_task"), Mapping) else {}
        task_id = str(selected.get("task_id") or "IDLE")
        digest = context_digest(pack)
        path = local_ai_root / booster_id / f"{task_id}-{digest[:20]}.json"
        if not path.is_file():
            continue
        try:
            assist = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(assist, Mapping):
            continue
        if (
            assist.get("schema") != "minitz.booster_local_ai_assist/v1"
            or str(assist.get("project_scope") or "") != project_scope
            or str(assist.get("booster_id") or "") != booster_id
            or str(assist.get("task_id") or "") != task_id
            or str(assist.get("context_digest") or "") != digest
            or assist.get("progression_authority") is not False
        ):
            continue
        row = {
            "booster": booster_id,
            "project_scope": project_scope,
            "task_id": task_id,
            "context_digest": digest,
            "assist_ref": str(path),
            "assist_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "provider": str(assist.get("provider") or "ollama-qwen"),
            "model": str(assist.get("model") or ""),
            "text": str(assist.get("text") or "")[:2400],
            "authority": "NONE",
            "progression_authority": False,
            "purpose": "ACTIVE_OR_UPCOMING_BOOSTER_ASSIST",
        }
        secret_boundary.validate_privacy_safe_payload(row)
        rows.append(row)
    return rows


def build_main_coder_handoff(
    program: Mapping[str, Any],
    ledger: Mapping[str, Any],
    *,
    local_ai_assists: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    current = program.get("current_execution") if isinstance(program.get("current_execution"), Mapping) else {}
    task_id = str(current.get("task_id") or "")
    revision = current.get("task_revision")
    digest = str(current.get("task_sha256") or "")
    rows = []
    for raw in ledger.get("items", []) if isinstance(ledger.get("items"), list) else []:
        if not isinstance(raw, Mapping) or str(raw.get("canonical_task_id") or "") != task_id:
            continue
        if str(raw.get("work_status") or "") not in {"DONE_LOCAL", "HANDOFF_READY"}:
            continue
        if revision is not None and raw.get("canonical_task_revision") != revision:
            continue
        if digest and str(raw.get("canonical_task_sha256") or "") != digest:
            continue
        rows.append({
            "booster": str(raw.get("booster") or ""), "work_status": str(raw.get("work_status") or ""),
            "summary": str(raw.get("summary") or "")[:1600], "files_changed": [str(x) for x in raw.get("files_changed", [])][:30],
            "evidence_refs": [str(x) for x in raw.get("evidence_refs", [])][:30], "next_action": str(raw.get("next_action") or "")[:900],
        })
    payload = {
        "schema": "minitz.main_coder_booster_handoff/v1", "authority": "NONE", "progression_authority": False,
        "task_id": task_id, "task_revision": revision, "task_sha256": digest, "booster_results": rows,
        "local_qwen_assists": [dict(row) for row in local_ai_assists][:5],
        "privacy_qualification_required_before_ingestion": True,
    }
    return secret_boundary.validate_privacy_safe_payload(payload)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected JSON object: {path}")
    return dict(value)


def _ledger_lock_path(path: Path) -> Path:
    return Path(str(path) + ".lock")


def _with_ledger_lock(path: Path):
    lock_path = _ledger_lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    return lock_path.open("a+", encoding="utf-8")


def sync_files(
    program_path: Path,
    ledger_path: Path,
    memory_path: Path,
    projection_path: Path,
    registry_path: Path,
    *,
    context_root: Path,
    maximum_bytes: int = 32000,
) -> dict[str, Any]:
    program_path = Path(program_path); ledger_path = Path(ledger_path)
    try:
        task_guidance.write_guidance_documents(
            program_path, output_root=program_path.parent / "task_guidance", start_offset=6,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    raw_program = program_path.read_bytes()
    program = json.loads(raw_program)
    program_sha = hashlib.sha256(raw_program).hexdigest()
    if not isinstance(program, Mapping):
        raise ValueError("canonical Task Program must be an object")
    with _with_ledger_lock(ledger_path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        ledger = _read_json(ledger_path)
        reconciled = reconcile_ledger(program, ledger, program_sha256=program_sha)
        _atomic_json(ledger_path, reconciled)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    memory = _read_json(memory_path)
    projection = _read_json(projection_path) if Path(projection_path).is_file() else {}
    registry = _read_json(registry_path)
    context_root = Path(context_root); context_root.mkdir(parents=True, exist_ok=True)
    contexts: dict[str, str] = {}
    for booster_id in BOOSTER_CHANNELS:
        pack = build_context_pack(
            program, reconciled, booster_id,
            memory_index=memory, projection=projection, provider_registry=registry,
            maximum_bytes=maximum_bytes, guidance_root=program_path.parent / "task_guidance",
        )
        pack["canonical_program"] = {
            "revision": int(program.get("revision") or 0),
            "sha256": program_sha,
            "current_execution": dict(program.get("current_execution") or {}) if isinstance(program.get("current_execution"), Mapping) else {},
        }
        pack["sandbox"] = {
            "host_workspace": f"/mnt/biella-extra/minitz-os-sandbox/workspace/boosts/{booster_id}",
            "container_workspace": "/workspace/repo",
            "host_os_reference": "/host-vps",
            "host_os_mutation_allowed": False,
            "normal_network": "AVAILABLE",
            "exec_wrapper": "/mnt/biella-extra/minitz-os-sandbox/exec-booster.sh",
        }
        path = _atomic_json(context_root / f"{booster_id}.json", pack)
        contexts[booster_id] = str(path)
    local_ai_root = Path(os.environ.get("MINITZ_BOOSTER_LOCAL_AI_ROOT", str(context_root.parent / "local-ai")))
    handoff = build_main_coder_handoff(
        program, reconciled,
        local_ai_assists=collect_current_local_ai_assists(context_root, local_ai_root),
    )
    handoff_path = _atomic_json(context_root / "main-coder-context.json", handoff)
    return {
        "schema": "minitz.booster_sync_result/v1",
        "program_revision": int(program.get("revision") or 0),
        "program_sha256": program_sha,
        "ledger": str(ledger_path),
        "contexts": contexts,
        "main_coder_handoff": str(handoff_path),
    }


def claim_work(ledger_path: Path, booster_id: str) -> dict[str, Any]:
    if booster_id not in BOOSTER_CHANNELS:
        raise ValueError("unknown Booster")
    ledger_path = Path(ledger_path)
    with _with_ledger_lock(ledger_path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        ledger = _read_json(ledger_path)
        selected = select_next_work(ledger, booster_id)
        if selected is None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            raise ValueError(f"no dependency-ready work for {booster_id}")
        selected["work_status"] = "IN_PROGRESS"
        selected["cycle_count"] = int(selected.get("cycle_count") or 0) + 1
        selected.setdefault("started_at", _now())
        if not selected.get("started_at"):
            selected["started_at"] = _now()
        selected["last_claimed_at"] = _now()
        selected["last_worker"] = booster_id
        _atomic_json(ledger_path, ledger)
        result = dict(selected)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return result


def report_work(
    ledger_path: Path,
    booster_id: str,
    task_id: str,
    *,
    status: str,
    summary: str = "",
    files_changed: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    next_action: str = "",
    handoff_to: str | None = None,
) -> dict[str, Any]:
    allowed = {"IN_PROGRESS", "DONE_LOCAL", "BLOCKED_CANONICAL_DEPENDENCY", "BLOCKED_TECHNICAL", "HANDOFF_READY", "SUPERSEDED", "NEEDS_REBASE"}
    if status not in allowed:
        raise ValueError("invalid Booster work status")
    if booster_id not in BOOSTER_CHANNELS:
        raise ValueError("unknown Booster")
    if handoff_to is not None and handoff_to not in BOOSTER_CHANNELS:
        raise ValueError("unknown handoff Booster")
    ledger_path = Path(ledger_path)
    with _with_ledger_lock(ledger_path) as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        ledger = _read_json(ledger_path)
        matches = [item for item in ledger.get("items", []) if isinstance(item, dict) and str(item.get("booster") or "") == booster_id and str(item.get("canonical_task_id") or "") == task_id]
        active = [item for item in matches if str(item.get("work_status") or "") in {"QUEUED", "IN_PROGRESS", "NEEDS_REBASE"}]
        if len(active) == 1:
            row = active[0]
        elif len(matches) == 1:
            row = matches[0]
        elif not matches:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            raise ValueError("Booster task entry not found")
        else:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            raise ValueError("Booster task entry is ambiguous; finish or supersede the active child work first")
        row["work_status"] = status
        row["summary"] = str(summary)[:3000]
        row["files_changed"] = [str(x) for x in (files_changed or [])][:100]
        row["evidence_refs"] = [str(x) for x in (evidence_refs or [])][:100]
        row["next_action"] = str(next_action)[:1800]
        row["handoff_to"] = handoff_to
        row["updated_at"] = _now()
        if status in {"DONE_LOCAL", "HANDOFF_READY", "SUPERSEDED"}:
            row["finished_at"] = _now()
        _atomic_json(ledger_path, ledger)
        result = dict(row)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return result


def _invoke_local_qwen(prompt: str, *, command: str = "/usr/local/bin/biella") -> Mapping[str, Any]:
    bounded_prompt = str(prompt)[:7000]
    completed = subprocess.run(
        [command, "resource", "fast-llm", "--provider", "ollama-qwen", "--max-tokens", "320", "--max-failover-attempts", "1", "--timeout-seconds", "80", "--prompt", bounded_prompt],
        text=True, capture_output=True, timeout=90, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout)[-1600:])
    value = json.loads(completed.stdout)
    if not isinstance(value, Mapping):
        raise RuntimeError("local Qwen returned malformed result")
    return value


def refresh_context_privacy_receipts(
    context_root: Path,
    protected_config_source: Path,
    *,
    booster_ids: list[str] | tuple[str, ...] | None = None,
) -> dict[str, str]:
    """Bind privacy receipts to the exact current Booster context bytes."""
    context_root = Path(context_root)
    source = Path(protected_config_source)
    selected = tuple(booster_ids or BOOSTER_CHANNELS.keys())
    receipts: dict[str, str] = {}
    for booster_id in selected:
        if booster_id not in BOOSTER_CHANNELS:
            raise ValueError("unknown Booster")
        target = context_root / f"{booster_id}.json"
        if not target.is_file():
            continue
        receipt = privacy_verifier.verify_secret_leaks(source, [target])
        if (
            receipt.get("result") != "PASS"
            or receipt.get("exact_value_hit_count") != 0
            or int(receipt.get("unknown_entry_count") or 0) != 0
        ):
            raise ValueError(f"privacy qualification failed for {booster_id}")
        receipt_path = context_root / "privacy" / f"{booster_id}.json"
        privacy_verifier.write_receipt(receipt_path, receipt)
        receipts[booster_id] = str(receipt_path)
    return receipts


def _protected_config_source() -> Path:
    return Path(os.environ.get("MINITZ_PROTECTED_CONFIG_SOURCE", "/root/.config/biella-ai/runtime.env"))


def _require_privacy_qualification(context_path: Path) -> Path:
    context_path = Path(context_path)
    receipt_path = context_path.parent / "privacy" / f"{context_path.stem}.json"
    if not receipt_path.is_file():
        raise ValueError("privacy qualification receipt missing for Booster context")
    receipt = _read_json(receipt_path)
    context_sha = hashlib.sha256(context_path.read_bytes()).hexdigest()
    identities = receipt.get("target_identity_digests") if isinstance(receipt.get("target_identity_digests"), list) else []
    qualified = any(isinstance(row, Mapping) and str(row.get("content_sha256") or "") == context_sha for row in identities)
    if (
        receipt.get("schema") != "minitz.private_secret_leak_receipt/v3"
        or receipt.get("result") != "PASS"
        or receipt.get("exact_value_hit_count") != 0
        or int(receipt.get("unknown_entry_count") or 0) != 0
        or not qualified
    ):
        raise ValueError("privacy qualification receipt does not match Booster context")
    return receipt_path


def prepare_local_ai_for_booster(context_root: Path, cache_root: Path, booster_id: str, *, command: str = "/usr/local/bin/biella") -> Path:
    if booster_id not in BOOSTER_CHANNELS:
        raise ValueError("unknown Booster")
    path = Path(context_root) / f"{booster_id}.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    _require_privacy_qualification(path)
    pack = _read_json(path)
    secret_boundary.validate_privacy_safe_payload(pack)
    return ensure_local_ai_assist(pack, cache_root, lambda prompt: _invoke_local_qwen(prompt, command=command))


def prepare_local_ai_for_contexts(context_root: Path, cache_root: Path, *, command: str = "/usr/local/bin/biella") -> dict[str, str]:
    result: dict[str, str] = {}
    for booster_id in BOOSTER_CHANNELS:
        path = Path(context_root) / f"{booster_id}.json"
        if not path.is_file():
            continue
        assist = prepare_local_ai_for_booster(context_root, cache_root, booster_id, command=command)
        result[booster_id] = str(assist)
    return result


def _default_paths() -> dict[str, Path]:
    runtime = Path(os.environ.get("MINITZ_RUNTIME_ROOT", "/mnt/biella-extra/biella-runtime/codex-production"))
    repo = Path(os.environ.get("MINITZ_SANDBOX_REPO", "/mnt/biella-extra/minitz-os-sandbox/workspace/repo"))
    return {
        "program": Path(os.environ.get("MINITZ_TASK_PROGRAM_PATH", "/root/biella/analysis/live_audit/TASK_PROGRAM.json")),
        "ledger": Path(os.environ.get("MINITZ_BOOSTER_LEDGER", "/mnt/biella-extra/biella-runtime/boost-work-program/BOOSTER_TASK_LIST.json")),
        "memory": Path(os.environ.get("MINITZ_OS_MEMORY_INDEX", str(runtime / "memory/compacted-memory.json"))),
        "projection": Path(os.environ.get("MINITZ_CURRENT_TASK_PROJECTION", str(runtime / "memory/current-task.json"))),
        "registry": Path(os.environ.get("MINITZ_PROVIDER_REGISTRY", str(repo / "ops/workstation/provider-registry.json"))),
        "contexts": Path(os.environ.get("MINITZ_BOOSTER_CONTEXT_ROOT", "/mnt/biella-extra/biella-runtime/boost-work-program/context")),
        "local_ai": Path(os.environ.get("MINITZ_BOOSTER_LOCAL_AI_ROOT", "/mnt/biella-extra/biella-runtime/boost-work-program/local-ai")),
    }


def _cli(argv: list[str] | None = None) -> int:
    paths = _default_paths()
    parser = argparse.ArgumentParser(prog="minitz-booster-sync")
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync"); sync.add_argument("--with-local-ai", action="store_true")
    claim = sub.add_parser("claim"); claim.add_argument("booster", choices=sorted(BOOSTER_CHANNELS))
    report = sub.add_parser("report"); report.add_argument("booster", choices=sorted(BOOSTER_CHANNELS)); report.add_argument("task_id"); report.add_argument("--status", required=True); report.add_argument("--summary", default=""); report.add_argument("--file", action="append", default=[]); report.add_argument("--evidence", action="append", default=[]); report.add_argument("--next-action", default=""); report.add_argument("--handoff-to", choices=sorted(BOOSTER_CHANNELS))
    args = parser.parse_args(argv)
    if args.command == "sync":
        result = sync_files(paths["program"], paths["ledger"], paths["memory"], paths["projection"], paths["registry"], context_root=paths["contexts"])
        if args.with_local_ai:
            privacy_receipts = refresh_context_privacy_receipts(paths["contexts"], _protected_config_source())
            local_ai = prepare_local_ai_for_contexts(paths["contexts"], paths["local_ai"])
            result = sync_files(paths["program"], paths["ledger"], paths["memory"], paths["projection"], paths["registry"], context_root=paths["contexts"])
            result["privacy_receipts"] = privacy_receipts
            result["local_ai"] = local_ai
        print(json.dumps(result, sort_keys=True))
        return 0
    if args.command == "claim":
        # Always reconcile before claim so a selected chat cannot claim stale/completed work.
        sync_files(paths["program"], paths["ledger"], paths["memory"], paths["projection"], paths["registry"], context_root=paths["contexts"])
        idle_qwen_plan = None
        try:
            row = claim_work(paths["ledger"], args.booster)
        except ValueError as exc:
            if "no dependency-ready work" not in str(exc):
                raise
            refresh_context_privacy_receipts(paths["contexts"], _protected_config_source(), booster_ids=(args.booster,))
            idle_qwen_plan = prepare_idle_qwen_plan_for_booster(paths["contexts"], paths["local_ai"], args.booster)
            seed_qwen_idle_work(paths["program"], paths["ledger"], idle_qwen_plan)
            sync_files(paths["program"], paths["ledger"], paths["memory"], paths["projection"], paths["registry"], context_root=paths["contexts"])
            row = claim_work(paths["ledger"], args.booster)
        # Refresh after claim so the context reflects the live ledger entry.
        sync_files(paths["program"], paths["ledger"], paths["memory"], paths["projection"], paths["registry"], context_root=paths["contexts"])
        local_ai_path = None
        local_ai_error = None
        try:
            refresh_context_privacy_receipts(paths["contexts"], _protected_config_source(), booster_ids=(args.booster,))
            local_ai_path = str(prepare_local_ai_for_booster(paths["contexts"], paths["local_ai"], args.booster))
        except Exception as exc:
            local_ai_error = str(exc)[-1200:]
        print(json.dumps({
            "claimed": row,
            "context": str(paths["contexts"] / f"{args.booster}.json"),
            "local_ai": local_ai_path,
            "local_ai_error": local_ai_error,
            "idle_qwen_plan": str(idle_qwen_plan) if idle_qwen_plan else None,
        }, sort_keys=True))
        return 0
    if args.command == "report":
        row = report_work(paths["ledger"], args.booster, args.task_id, status=args.status, summary=args.summary, files_changed=args.file, evidence_refs=args.evidence, next_action=args.next_action, handoff_to=args.handoff_to)
        sync_files(paths["program"], paths["ledger"], paths["memory"], paths["projection"], paths["registry"], context_root=paths["contexts"])
        print(json.dumps(row, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
