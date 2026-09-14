from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

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


@dataclass(frozen=True)
class BoostGroup:
    boost_id: str
    name: str
    responsibility: str
    commander_lanes: tuple[str, ...]
    context_profile: str


_GROUPS = (
    BoostGroup(
        "BOOST-01", "Contract/Authority",
        "Authority, requirements, source truth, dependency graph, exact scope.",
        ("CMD-01", "CMD-02", "CMD-03", "CMD-12", "CMD-20", "CMD-28"),
        "DEEPEST_CROSS_PROJECT",
    ),
    BoostGroup(
        "BOOST-02", "Core Engineering",
        "Core semantic/kernel implementation and focused simplification.",
        ("CMD-04", "CMD-05", "CMD-13", "CMD-16", "CMD-27", "CMD-29"),
        "DEEP_CURRENT_TASK_CORE",
    ),
    BoostGroup(
        "BOOST-03", "Runtime/Integration",
        "Runtime attachment, adapters, providers, concurrency, APIs, and data flow.",
        ("CMD-06", "CMD-14", "CMD-15", "CMD-18", "CMD-19", "CMD-21"),
        "DEEP_RUNTIME_INTEGRATION",
    ),
    BoostGroup(
        "BOOST-04", "Qualification",
        "Tests, regression, build, validation, failure triage, and resilience.",
        ("CMD-07", "CMD-08", "CMD-09", "CMD-10", "CMD-17", "CMD-26"),
        "ACCEPTANCE_AND_FALSIFICATION",
    ),
    BoostGroup(
        "BOOST-05", "Continuity/Delivery",
        "Checkpoint continuity, evidence, observability, publication, portability, and review.",
        ("CMD-11", "CMD-22", "CMD-23", "CMD-24", "CMD-25", "CMD-30"),
        "DEEP_CONTINUITY_DELIVERY",
    ),
)


def boost_groups() -> tuple[BoostGroup, ...]:
    lanes = [lane for group in _GROUPS for lane in group.commander_lanes]
    expected = [f"CMD-{index:02d}" for index in range(1, 31)]
    if sorted(lanes) != expected or len(set(lanes)) != 30:
        raise ValueError("five-Boost Commander partition must cover CMD-01..CMD-30 exactly once")
    return _GROUPS


def _canonical_program_digest(program: Mapping[str, Any]) -> str:
    value = {str(k): v for k, v in program.items() if not str(k).startswith("_observed_")}
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _path_owner(path: str) -> str:
    value = str(path).strip()
    if value.startswith("tests/") or value.startswith(".github/"):
        return "BOOST-04"
    if value.startswith("website/") or value.startswith("docs/") or "/docs/" in value:
        return "BOOST-05"
    if value.startswith("ops/") or value.startswith("/mnt/") or value.startswith("/var/") or value.startswith("/run/"):
        return "BOOST-03"
    return "BOOST-02"


def _task_paths(task: Mapping[str, Any]) -> tuple[str, ...]:
    scope = task.get("write_scope") if isinstance(task.get("write_scope"), Mapping) else {}
    raw = scope.get("allowed_paths") if isinstance(scope.get("allowed_paths"), list) else []
    return tuple(dict.fromkeys(str(item).strip() for item in raw if str(item).strip()))


def _section_status(task: Mapping[str, Any], current_task_id: str | None) -> str:
    status = str(task.get("status") or "UNKNOWN")
    if status in {"COMPLETE", "COMPLETE_ALREADY", "COMPLETED", "DUPLICATE", "OBSOLETE", "RETIRED"}:
        return "COMPLETE"
    if str(task.get("task_id") or "") == str(current_task_id or ""):
        return "READY"
    return "QUEUED_BY_CANONICAL_ORDER"


def _section(task: Mapping[str, Any], group: BoostGroup, current_task_id: str | None) -> dict[str, Any]:
    task_id = str(task.get("task_id") or "")
    all_paths = _task_paths(task)
    owned = [] if group.boost_id == "BOOST-01" else [path for path in all_paths if _path_owner(path) == group.boost_id]
    write_authority = "ISOLATED_TASK_OWNED_ONLY" if owned else "READ_ONLY"
    return {
        "section_id": f"{task_id}::{group.boost_id}",
        "canonical_task_id": task_id,
        "task_revision": task.get("revision"),
        "task_record_sha256": task.get("task_record_sha256"),
        "canonical_status": str(task.get("status") or "UNKNOWN"),
        "boost_status": _section_status(task, current_task_id),
        "task_class": str(task.get("task_class") or "medium"),
        "title": str(task.get("title") or task_id),
        "boost_id": group.boost_id,
        "responsibility": group.responsibility,
        "context_profile": group.context_profile,
        "commander_lanes": list(group.commander_lanes),
        "write_authority": write_authority,
        "allowed_write_paths": owned,
        "progression_authority": False,
    }


def build_task_plan(program: Mapping[str, Any]) -> dict[str, Any]:
    tasks = program.get("tasks") if isinstance(program.get("tasks"), list) else []
    active_statuses = {"PENDING", "WORKING", "DEFERRED", "IN_PROGRESS", "REQUIRES_OTHER_RESOURCE"}
    current_task_id = next(
        (str(task.get("task_id") or "") for task in tasks
         if isinstance(task, Mapping) and task.get("status") in active_statuses),
        None,
    )
    groups = boost_groups()
    task_lists = {
        group.boost_id: [_section(task, group, current_task_id) for task in tasks if isinstance(task, Mapping)]
        for group in groups
    }
    return {
        "schema": "minitz.five_boost_task_plan/v1",
        "authority": "NONE",
        "progression_authority": False,
        "source_program_id": str(program.get("program_id") or ""),
        "source_program_revision": int(program.get("revision") or 0),
        "source_program_sha256": str(program.get("_observed_sha256") or _canonical_program_digest(program)),
        "canonical_task_count": len(tasks),
        "current_task_id": current_task_id,
        "desired_boost_workers": 5,
        "start_policy": "WITH_ACTIVE_CANONICAL_TASK",
        "runtime_state": "ACTIVE",
        "reserved_usage_policy": {
            "preferred_model": "gpt-reserve",
            "catalog_eligibility_required": True,
            "quota_probe_forbidden": True,
            "fallback_to_task_class_routes": True,
        },
        "qualification_prerequisites": {
            "hal": {
                "state": "QUALIFICATION_REQUIRED",
                "driver_domain": "LINUX_ONLY",
                "kernel_substrate": "LINUX",
                "founder_mode_target": True,
                "host_kernel_bypass_claimed": False,
                "required_evidence": ["driver_binding", "gpu_functional_readback", "io_isolation_readback"],
            },
            "trust": {
                "state": "QUALIFICATION_REQUIRED",
                "root_or_cloud_anchor_required_for_strict_mode": True,
                "raw_secret_values_allowed": False,
                "required_evidence": ["boot_integrity", "node_identity", "credential_binding", "attestation_or_root_anchor"],
            },
            "swarm": {
                "state": "ACTIVE",
                "runtime_state": "ACTIVE",
                "desired_boost_workers": 5,
                "desired_commander_lanes": 30,
                "desired_browser_automation_slots": 30,
                "browser_slots_are_authority": False,
            },
            "validation": {
                "state": "QUALIFICATION_REQUIRED",
                "digest": "SHA-256",
                "cache_efficiency_target": 0.98,
                "observed_cache_efficiency": None,
                "dynamic_anomaly_resolution_requires_evidence": True,
            },
        },
        "groups": [
            {
                "boost_id": group.boost_id,
                "name": group.name,
                "responsibility": group.responsibility,
                "context_profile": group.context_profile,
                "commander_lanes": list(group.commander_lanes),
            }
            for group in groups
        ],
        "boost_task_lists": task_lists,
    }


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path = Path(path)
    _assert_noncanonical_control_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def _current_assignment(plan: Mapping[str, Any], boost_id: str) -> dict[str, Any]:
    current_task_id = str(plan.get("current_task_id") or "")
    task_lists = plan.get("boost_task_lists") if isinstance(plan.get("boost_task_lists"), Mapping) else {}
    rows = task_lists.get(boost_id) if isinstance(task_lists.get(boost_id), list) else []
    row = next((dict(item) for item in rows if isinstance(item, Mapping) and str(item.get("canonical_task_id") or "") == current_task_id), None)
    return row or {
        "section_id": f"{current_task_id}::{boost_id}" if current_task_id else f"IDLE::{boost_id}",
        "canonical_task_id": current_task_id or None,
        "boost_id": boost_id,
        "boost_status": "NO_CURRENT_TASK",
        "allowed_write_paths": [],
        "progression_authority": False,
    }



_WORKER_STATUSES = {"READY", "ACTIVE", "WAITING", "COMPLETE", "FAILED", "NEEDS_REBASE", "STOPPED"}

def record_worker_report(runtime_root: Path, boost_id: str, *, task_id: str, task_record_sha256: str, status: str, source_program_sha256: str, summary: str = "", commit: str | None = None) -> Path:
    root = Path(runtime_root) / "memory" / "boost-fabric"
    current = read_json(root / "current.json")
    valid_boosts = {group.boost_id for group in boost_groups()}
    if boost_id not in valid_boosts:
        raise ValueError("unknown Boost worker")
    if status not in _WORKER_STATUSES:
        raise ValueError("invalid Boost worker status")
    if str(current.get("source_program_sha256") or "") != str(source_program_sha256):
        raise ValueError("stale Boost source program")
    if str(current.get("current_task_id") or "") != str(task_id):
        raise ValueError("foreign Boost task identity")
    assignment = read_json(root / "assignments" / str(task_id) / f"{boost_id}.json")
    if str(assignment.get("task_record_sha256") or "") != str(task_record_sha256):
        raise ValueError("stale Boost task record")
    report = {
        "schema": "minitz.boost_worker_report/v1",
        "authority": "NONE",
        "progression_authority": False,
        "boost_id": boost_id,
        "task_id": str(task_id),
        "task_record_sha256": str(task_record_sha256),
        "source_program_sha256": str(source_program_sha256),
        "status": status,
        "summary": str(summary)[:1200],
        "commit": str(commit) if commit else None,
    }
    return _atomic_json(root / "workers" / f"{boost_id}.json", report)

def refresh_runtime(runtime_root: Path, program: Mapping[str, Any]) -> tuple[Path, Path]:
    root = Path(runtime_root) / "memory" / "boost-fabric"
    plan = build_task_plan(program)
    plan_path = root / "task-plan.json"
    current_path = root / "current.json"
    existing = {}
    if plan_path.is_file():
        try:
            existing = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    if existing != plan:
        _atomic_json(plan_path, plan)
    assignment_dir = root / "assignments" / str(plan.get("current_task_id") or "IDLE")
    boost_rows = []
    for group in boost_groups():
        assignment = _current_assignment(plan, group.boost_id)
        assignment_path = _atomic_json(assignment_dir / f"{group.boost_id}.json", assignment)
        report_path = root / "workers" / f"{group.boost_id}.json"
        report = read_json(report_path)
        report_valid = (
            report.get("authority") == "NONE" and report.get("progression_authority") is False
            and str(report.get("boost_id") or "") == group.boost_id
            and str(report.get("task_id") or "") == str(assignment.get("canonical_task_id") or "")
            and str(report.get("task_record_sha256") or "") == str(assignment.get("task_record_sha256") or "")
            and str(report.get("source_program_sha256") or "") == str(plan.get("source_program_sha256") or "")
            and str(report.get("status") or "") in _WORKER_STATUSES
        )
        boost_rows.append({
            "boost_id": group.boost_id,
            "name": group.name,
            "status": str(report.get("status") if report_valid else assignment.get("boost_status") or "UNKNOWN"),
            "commander_lanes": list(group.commander_lanes),
            "assignment_path": str(assignment_path),
            "worker_report_path": str(report_path) if report_valid else None,
        })
    current = {
        "schema": "minitz.boost_fabric/v1",
        "authority": "NONE",
        "progression_authority": False,
        "runtime_state": str(plan.get("runtime_state") or "ACTIVE"),
        "start_policy": str(plan.get("start_policy") or "WITH_ACTIVE_CANONICAL_TASK"),
        "source_program_id": plan.get("source_program_id"),
        "source_program_revision": plan.get("source_program_revision"),
        "source_program_sha256": plan.get("source_program_sha256"),
        "current_task_id": plan.get("current_task_id"),
        "desired_boost_workers": 5,
        "total_commanders": 30,
        "reserved_usage_policy": dict(plan.get("reserved_usage_policy") or {}),
        "qualification_prerequisites": dict(plan.get("qualification_prerequisites") or {}),
        "task_plan_path": str(plan_path),
        "boosts": boost_rows,
    }
    _atomic_json(current_path, current)
    return plan_path, current_path



def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def control_summary(current: Mapping[str, Any], *, preview_limit: int = 16) -> dict[str, Any]:
    if current.get("authority") != "NONE" or current.get("progression_authority") is not False:
        current = {"authority": "NONE", "progression_authority": False, "boosts": []}
    plan = read_json(Path(str(current.get("task_plan_path") or ""))) if current.get("task_plan_path") else {}
    task_lists = plan.get("boost_task_lists") if isinstance(plan.get("boost_task_lists"), Mapping) else {}
    safe_boosts: list[dict[str, Any]] = []
    for raw in current.get("boosts", []) if isinstance(current.get("boosts"), list) else []:
        if not isinstance(raw, Mapping):
            continue
        boost_id = str(raw.get("boost_id") or "")
        rows = task_lists.get(boost_id) if isinstance(task_lists.get(boost_id), list) else []
        preview = []
        for item in rows:
            if not isinstance(item, Mapping) or str(item.get("boost_status") or "") == "COMPLETE":
                continue
            preview.append({
                "section_id": str(item.get("section_id") or ""),
                "canonical_task_id": str(item.get("canonical_task_id") or ""),
                "title": str(item.get("title") or ""),
                "task_class": str(item.get("task_class") or ""),
                "canonical_status": str(item.get("canonical_status") or "UNKNOWN"),
                "boost_status": str(item.get("boost_status") or "UNKNOWN"),
                "write_authority": str(item.get("write_authority") or "READ_ONLY"),
            })
            if len(preview) >= max(1, int(preview_limit)):
                break
        safe_boosts.append({
            "boost_id": boost_id,
            "name": str(raw.get("name") or ""),
            "status": str(raw.get("status") or "UNKNOWN"),
            "commander_lanes": [str(item) for item in raw.get("commander_lanes", [])],
            "task_preview": preview,
        })
    reserved = current.get("reserved_usage_policy") if isinstance(current.get("reserved_usage_policy"), Mapping) else {}
    return {
        "schema": "minitz.boost_control_summary/v1",
        "authority": "NONE",
        "progression_authority": False,
        "current_task_id": current.get("current_task_id"),
        "runtime_state": str(current.get("runtime_state") or "UNKNOWN"),
        "start_policy": str(current.get("start_policy") or ""),
        "total_boosts": len(safe_boosts),
        "total_commanders": int(current.get("total_commanders") or 30),
        "reserved_usage_policy": {
            "preferred_model": str(reserved.get("preferred_model") or "gpt-reserve"),
            "catalog_eligibility_required": bool(reserved.get("catalog_eligibility_required", True)),
            "quota_probe_forbidden": bool(reserved.get("quota_probe_forbidden", True)),
            "fallback_to_task_class_routes": bool(reserved.get("fallback_to_task_class_routes", True)),
        },
        "qualification_prerequisites": dict(current.get("qualification_prerequisites") or {}),
        "boost_task_lists": safe_boosts,
        "boosts": safe_boosts,
    }

def public_summary(current: Mapping[str, Any]) -> dict[str, Any]:
    control = control_summary(current, preview_limit=1)
    safe = [{
        "boost_id": row["boost_id"],
        "name": row["name"],
        "status": row["status"],
        "commander_lanes": list(row["commander_lanes"]),
    } for row in control["boosts"]]
    return {
        "schema": "minitz.boost_public_summary/v1",
        "authority": "NONE",
        "current_task_id": control.get("current_task_id"),
        "runtime_state": control.get("runtime_state"),
        "start_policy": control.get("start_policy"),
        "total_boosts": len(safe),
        "total_commanders": control.get("total_commanders", 30),
        "boosts": safe,
    }
