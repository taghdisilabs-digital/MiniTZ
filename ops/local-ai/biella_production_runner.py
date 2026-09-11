#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import biella_codex_routing as routing
import biella_execution_style as execution_style
import biella_memory_compactor as memory_compactor
import biella_main_coder as main_coder
import minitz_commander_fabric as commander
import minitz_taskbooster as taskbooster
import minitz_task_program as minitz
import biella_production_evidence as evidence
import biella_production_events as production_events
import biella_production_state as state
import biella_task_packet as packets
import biella_publication as publication
import biella_execution_map as execution_map

UNIT_NAME = "biella-codex-production"
SOURCE_REFRESH_EXIT = 75
_RUNTIME_KEYS = {
    "status", "project", "task_id", "attempt", "pid", "child_pid",
    "active_model", "active_reasoning", "cooldowns", "last_result",
    "heartbeat_at", "updated_at", "task_session_id", "session_task_id",
    "task_sessions", "coder_sessions", "coder_statuses", "coder_status_detail", "last_coder_usage", "active_coder", "source_alignment",
}


class AlreadyRunning(RuntimeError):
    pass


@dataclass
class MainCoderPeerHandle:
    key: str
    peer_coder: str
    model: str
    task_id: str
    task_state_digest: str
    process: subprocess.Popen
    output_path: Path
    stdout_path: Path
    stderr_path: Path
    accepted_path: Path


@dataclass
class CommanderHandle:
    key: str
    lane_id: str
    role: str
    requested_provider: str
    task_id: str
    task_state_digest: str
    projection_digest: str
    process: subprocess.Popen
    stdout_path: Path
    stderr_path: Path
    lease_path: Path
    accepted_path: Path
    rejected_path: Path


class ProductionLock:
    def __init__(self, path: Path):
        self.path = Path(path); self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close(); raise AlreadyRunning(str(self.path)) from exc
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close(); self._handle = None


def initial_runtime() -> dict[str, Any]:
    return {
        "status": "STOPPED", "project": None, "task_id": None, "attempt": 0,
        "pid": None, "child_pid": None, "active_model": None,
        "active_reasoning": None, "cooldowns": {}, "last_result": None,
        "heartbeat_at": None, "updated_at": datetime.now(timezone.utc).isoformat(),
        "task_session_id": None, "session_task_id": None, "task_sessions": {},
        "coder_sessions": {}, "coder_statuses": {"codex": "NEEDS_MODIFICATION", "agr": "NEEDS_MODIFICATION"},
        "coder_status_detail": {}, "last_coder_usage": {},
        "active_coder": "codex", "source_alignment": None,
    }


def save_runtime(path: Path, runtime: Mapping[str, Any]) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: runtime.get(key) for key in _RUNTIME_KEYS}
    payload["cooldowns"] = dict(payload.get("cooldowns") or {})
    payload["task_sessions"] = dict(payload.get("task_sessions") or {})
    payload["coder_sessions"] = {str(task): dict(sessions) for task, sessions in dict(payload.get("coder_sessions") or {}).items() if isinstance(sessions, Mapping)}
    payload["coder_statuses"] = dict(payload.get("coder_statuses") or {})
    payload["coder_status_detail"] = dict(payload.get("coder_status_detail") or {})
    payload["last_coder_usage"] = dict(payload.get("last_coder_usage") or {})
    payload["attempt"] = int(payload.get("attempt") or 0)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_runtime(path: Path) -> dict[str, Any]:
    if not Path(path).exists():
        return initial_runtime()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    result = initial_runtime()
    for key in _RUNTIME_KEYS:
        if key in raw:
            result[key] = raw[key]
    result["task_sessions"] = dict(result.get("task_sessions") or {})
    result["coder_sessions"] = {str(task): dict(sessions) for task, sessions in dict(result.get("coder_sessions") or {}).items() if isinstance(sessions, Mapping)}
    result["coder_statuses"] = dict(result.get("coder_statuses") or {})
    result["coder_status_detail"] = dict(result.get("coder_status_detail") or {})
    result["last_coder_usage"] = dict(result.get("last_coder_usage") or {})
    result["coder_statuses"].setdefault("codex", "NEEDS_MODIFICATION")
    result["coder_statuses"].setdefault("agr", "NEEDS_MODIFICATION")
    current_task = result.get("session_task_id"); current_session = result.get("task_session_id")
    if isinstance(current_task, str) and current_task and isinstance(current_session, str) and current_session:
        result["task_sessions"].setdefault(current_task, current_session)
    # Old runtime files had only one Codex-native session map. Migrate it once into
    # the provider-scoped map without changing the legacy compatibility fields.
    if "coder_sessions" not in raw:
        for task_id, session_id in result["task_sessions"].items():
            if isinstance(session_id, str) and session_id:
                result["coder_sessions"].setdefault(str(task_id), {})["codex"] = session_id
    return result



def _beat(runtime_path: Path, telemetry: dict[str, Any], *, at: datetime | None = None) -> datetime:
    observed = at or datetime.now(timezone.utc)
    telemetry["heartbeat_at"] = observed.isoformat()
    telemetry["updated_at"] = observed.isoformat()
    save_runtime(runtime_path, telemetry)
    return observed


def _tail(path: Path, maximum_bytes: int = 65536) -> str:
    if not path.exists():
        return ""
    return path.read_bytes()[-maximum_bytes:].decode("utf-8", errors="replace")


def _extract_codex_session_id(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("thread_id"), str) and item.get("thread_id"):
            return str(item["thread_id"])
        payload = item.get("payload")
        if isinstance(payload, dict):
            for key in ("thread_id", "session_id"):
                if isinstance(payload.get(key), str) and payload.get(key):
                    return str(payload[key])
    return None


def _resume_session_for(telemetry: Mapping[str, Any], task_id: str, *, coder_id: str = "codex") -> str | None:
    coder_sessions = telemetry.get("coder_sessions")
    if isinstance(coder_sessions, Mapping):
        sessions = coder_sessions.get(task_id)
        if isinstance(sessions, Mapping):
            raw = sessions.get(coder_id)
            if isinstance(raw, str) and raw:
                return raw
    if coder_id != "codex":
        return None
    if telemetry.get("active_coder") in {None, "codex"} and telemetry.get("session_task_id") == task_id:
        raw = telemetry.get("task_session_id")
        if isinstance(raw, str) and raw:
            return str(raw)
    sessions = telemetry.get("task_sessions")
    if isinstance(sessions, Mapping):
        raw = sessions.get(task_id)
        if isinstance(raw, str) and raw:
            return str(raw)
    return None


def _record_task_session(telemetry: dict[str, Any], task_id: str, session_id: str, *, coder_id: str = "codex") -> None:
    all_sessions = {str(task): dict(sessions) for task, sessions in dict(telemetry.get("coder_sessions") or {}).items() if isinstance(sessions, Mapping)}
    all_sessions.setdefault(task_id, {})[coder_id] = session_id
    telemetry["coder_sessions"] = all_sessions
    if coder_id == "codex":
        legacy = dict(telemetry.get("task_sessions") or {})
        legacy[task_id] = session_id
        telemetry["task_sessions"] = legacy
    if telemetry.get("active_coder", "codex") == coder_id:
        telemetry["task_session_id"] = session_id
        telemetry["session_task_id"] = task_id


def _resume_session_for_route(telemetry: Mapping[str, Any], task_id: str, route: routing.Route, *, coder_id: str = "codex") -> str | None:
    if coder_id == "codex" and routing.is_bounded_fallback(route):
        return None
    return _resume_session_for(telemetry, task_id, coder_id=coder_id)


def _task_has_shared_continuity(telemetry: Mapping[str, Any], task_id: str, capsule_path: Path | None = None) -> bool:
    coder_sessions = telemetry.get("coder_sessions")
    if isinstance(coder_sessions, Mapping):
        sessions = coder_sessions.get(task_id)
        if isinstance(sessions, Mapping) and any(isinstance(value, str) and value for value in sessions.values()):
            return True
    if _resume_session_for(telemetry, task_id, coder_id="codex"):
        return True
    if capsule_path and Path(capsule_path).is_file():
        try:
            capsule = json.loads(Path(capsule_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if isinstance(capsule, Mapping) and capsule.get("task_id") == task_id:
            if str(capsule.get("summary") or "").strip() or capsule.get("evidence") or capsule.get("owned_files") or int(capsule.get("dirty_path_count") or 0) > 0:
                return True
    return False

def _resource_blocker_deferral_tail(production: state.ProductionState, blocked_task_id: str, dependencies: Mapping[str, Sequence[str]]) -> str | None:
    """Return the last contiguous later pending task runnable without the blocked task."""
    ordered = [task for section in production.sections for task in section.tasks]
    completed = {task.id for task in ordered if task.status in state._COMPLETE}
    try:
        start = next(index for index, task in enumerate(ordered) if task.id == blocked_task_id)
    except StopIteration:
        return None
    available = set(completed); tail = None
    for task in ordered[start + 1:]:
        if task.status in state._COMPLETE:
            available.add(task.id); continue
        required = set(dependencies.get(task.id, ()))
        if blocked_task_id in required or not required.issubset(available):
            break
        tail = task.id; available.add(task.id)
    return tail


def _resource_blocker_summary(telemetry: Mapping[str, Any], task_id: str) -> str | None:
    previous = telemetry.get("last_result")
    if not isinstance(previous, Mapping) or previous.get("task_id") != task_id or previous.get("status") != "CONTINUE":
        return None
    summary = str(previous.get("summary", "")).strip()
    return summary if summary.startswith("REQUIRES_OTHER_RESOURCE:") else None


def _defer_resource_blocker(repo_root: Path, project_root: Path, production: state.ProductionState, task: state.TaskRecord, telemetry: dict[str, Any], journal: production_events.ProductionEventJournal, runtime_path: Path) -> bool:
    summary = _resource_blocker_summary(telemetry, task.id)
    if not summary:
        return False
    dependencies = {item["task_id"]: tuple(item.get("depends_on") or ()) for item in execution_map.load_map(repo_root).get("tasks", [])}
    tail = _resource_blocker_deferral_tail(production, task.id, dependencies)
    if not tail:
        return False
    # Seed legacy single-session runtime into the per-task registry before switching frontier.
    current_session = _resume_session_for(telemetry, task.id)
    if current_session:
        _record_task_session(telemetry, task.id, current_session)
    production = state.defer_pending_task_after(project_root, task.id, tail)
    execution_map.sync_production_order(repo_root, production)
    production, successor = state.activate_project_frontier(repo_root, project_root)
    telemetry.update({"task_id": successor.id if successor else None, "last_result": {
        "task_id": task.id, "status": "RESOURCE_DEFERRED", "summary": summary,
        "evidence": [f"Canonical task row moved after {tail}; status/evidence unchanged."],
    }})
    journal.emit("task.resource_deferred", task_id=task.id, status="RESOURCE_DEFERRED", text=f"{summary} Independent work continues through {tail}.")
    _beat(runtime_path, telemetry)
    return True


def _normalize_result_for_route(result: evidence.TaskResult, route: routing.Route) -> evidence.TaskResult:
    if not routing.is_bounded_fallback(route) or result.status == "CONTINUE":
        return result
    return evidence.TaskResult(
        result.task_id,
        "CONTINUE",
        f"Bounded fallback completed its bounded work but cannot close the whole task. {result.summary}".strip(),
        result.evidence,
        result.task_revision,
        result.task_digest,
        result.scope_ref,
        result.family_revision,
        result.authority_ref,
        result.accepted_criteria,
    )


def _clear_task_session(telemetry: dict[str, Any]) -> None:
    # Native provider sessions are already stored in coder_sessions. Clearing the
    # live slot must never reinterpret one provider's conversation as another's.
    telemetry["task_session_id"] = None
    telemetry["session_task_id"] = None


def _drop_coder_task_session(telemetry: dict[str, Any], task_id: str, coder_id: str) -> None:
    sessions_by_task = {str(task): dict(values) for task, values in dict(telemetry.get("coder_sessions") or {}).items() if isinstance(values, Mapping)}
    task_sessions = sessions_by_task.get(task_id)
    if isinstance(task_sessions, dict):
        task_sessions.pop(coder_id, None)
        if task_sessions:
            sessions_by_task[task_id] = task_sessions
        else:
            sessions_by_task.pop(task_id, None)
    telemetry["coder_sessions"] = sessions_by_task
    if coder_id == "codex":
        legacy = dict(telemetry.get("task_sessions") or {})
        legacy.pop(task_id, None)
        telemetry["task_sessions"] = legacy
    if telemetry.get("active_coder") == coder_id and telemetry.get("session_task_id") == task_id:
        _clear_task_session(telemetry)


def _task_capsule_path(runtime_root: Path, task_id: str) -> Path:
    safe_id = str(task_id).replace("/", "_")
    return Path(runtime_root) / "task-memory" / f"{safe_id}.json"


def _project_dirty_paths(repo_root: Path, project_root: Path) -> list[str]:
    repo_root = Path(repo_root).resolve(); project_root = Path(project_root).resolve()
    try:
        relative_root = project_root.relative_to(repo_root).as_posix()
        prefix = "" if relative_root == "." else relative_root.rstrip("/") + "/"
    except ValueError:
        return []
    proc = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return []
    result: list[str] = []
    for raw in proc.stdout.splitlines():
        if len(raw) < 4:
            continue
        name = raw[3:].strip('"')
        if " -> " in name:
            name = name.split(" -> ", 1)[1].strip('"')
        if name.startswith(prefix):
            result.append(name[len(prefix):])
    return sorted(dict.fromkeys(result))


def _task_workspace_fingerprint(repo_root: Path, project_root: Path) -> str:
    repo_root = Path(repo_root).resolve(); project_root = Path(project_root).resolve()
    digest = hashlib.sha256()
    tree = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "HEAD^{tree}"], text=True, capture_output=True, check=False)
    digest.update((tree.stdout.strip() if tree.returncode == 0 else "UNKNOWN_TREE").encode())
    for relative in _project_dirty_paths(repo_root, project_root):
        digest.update(relative.encode()); digest.update(b"\0")
        path = project_root / relative
        if not path.exists():
            digest.update(b"MISSING\0"); continue
        if not path.is_file():
            digest.update(b"NONFILE\0"); continue
        digest.update(str(path.stat().st_size).encode()); digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _bounded_packet_id(repo_root: Path, project_root: Path, task: state.TaskRecord) -> str:
    digest = hashlib.sha256()
    digest.update(task.id.encode()); digest.update(b"\0")
    digest.update(task.task_class.encode()); digest.update(b"\0")
    digest.update(_task_workspace_fingerprint(repo_root, project_root).encode())
    guide = Path(project_root) / "docs" / "task-guides" / f"{task.id}.md"
    if guide.exists():
        digest.update(hashlib.sha256(guide.read_bytes()).digest())
    return digest.hexdigest()


def _task_working_directory(repo_root: Path, project_root: Path, task_id: str) -> Path:
    if state._use_minitz_project(Path(project_root)):
        program = minitz.load()
        row = minitz.task_by_id(program, task_id)
        scope = row.get("write_scope")
        if isinstance(scope, dict):
            return minitz.execution_root(row)
        return Path(repo_root).resolve()
    return execution_map.task_working_directory(repo_root, project_root, task_id)


def _simple_task_resource_context(repo_root: Path, project_root: Path, task: state.TaskRecord) -> tuple[bool, bool]:
    working_root = _task_working_directory(repo_root, project_root, task.id)
    parts = [task.title, *task.evidence]
    guide = Path(project_root) / "docs" / "task-guides" / f"{task.id}.md"
    if guide.is_file():
        parts.append(guide.read_text(encoding="utf-8", errors="replace")[:12000])
    context = "\n".join(str(part) for part in parts if str(part).strip())
    grounded = bool(taskbooster.extract_grounded_targets(context, working_root))
    read_only = grounded and bool(re.search(r"\b(?:read[- ]?only|inspect|audit|verify|review|analy(?:se|ze)|diagnos(?:e|tic))\b", context, re.I))
    return grounded, read_only


def _simple_helper_attempted_models(telemetry: Mapping[str, Any], task_id: str, packet_id: str) -> set[str]:
    current = telemetry.get("simple_resource_attempts")
    if not isinstance(current, Mapping) or current.get("task_id") != task_id or current.get("task_state_digest") != packet_id:
        return set()
    models = current.get("models")
    return {str(model) for model in models} if isinstance(models, list) else set()


def _record_simple_helper_attempt(telemetry: dict[str, Any], task_id: str, packet_id: str, route: routing.Route) -> None:
    if not routing.is_bounded_fallback(route):
        return
    attempted = _simple_helper_attempted_models(telemetry, task_id, packet_id)
    attempted.add(route.model)
    telemetry["simple_resource_attempts"] = {
        "task_id": task_id, "task_state_digest": packet_id, "models": sorted(attempted),
        "authority": "NONE",
    }


def _select_task_route(task: state.TaskRecord, catalog: Mapping[str, set[str]], cooldowns: Mapping[str, str], now: datetime, telemetry: Mapping[str, Any], repo_root: Path, project_root: Path) -> tuple[routing.Route | None, str | None]:
    packet_id = _bounded_packet_id(repo_root, project_root, task)
    if task.task_class == "simple":
        grounded, read_only = _simple_task_resource_context(repo_root, project_root, task)
        local_model = os.environ.get("BIELLA_CODEX_LOCAL_MODEL", "qwen3-coder-next:biella")
        qwen_available = _local_qwen_resident() and local_model in catalog and "local" in catalog.get(local_model, set())
        spark_available = "xhigh" in catalog.get("gpt-5.3-codex-spark", set())
        attempted = _simple_helper_attempted_models(telemetry, task.id, packet_id)
        for decision in routing.simple_resource_plan(
            task.task_class, deterministic_command=None, grounded_context=grounded,
            local_qwen_resident=qwen_available, spark_available=spark_available,
            read_only_microanalysis=read_only,
        ):
            if decision.kind == "LOCAL_QWEN" and local_model not in attempted:
                return routing.Route(local_model, "none", "ollama"), packet_id
            if decision.kind == "SPARK" and "gpt-5.3-codex-spark" not in attempted:
                return routing.Route("gpt-5.3-codex-spark", "xhigh"), packet_id
            if decision.kind == "GENERAL_CODEX":
                break
    try:
        route = routing.select_route(task.task_class, catalog, cooldowns, now)
    except RuntimeError:
        return None, None
    return route, packet_id if routing.is_bounded_fallback(route) else None


def _select_main_task_route(
    task: state.TaskRecord,
    codex_catalog: Mapping[str, set[str]],
    agr_models: set[str],
    telemetry: dict[str, Any],
    now: datetime,
    repo_root: Path,
    project_root: Path,
) -> tuple[str | None, routing.Route | None, str | None, str | None]:
    codex_route, packet_id = _select_task_route(
        task, codex_catalog, telemetry.get("cooldowns", {}), now, telemetry, repo_root, project_root
    )
    statuses = dict(telemetry.get("coder_statuses") or {})
    codex_full = bool(
        codex_route is not None
        and codex_route.provider == "openai"
        and not routing.is_bounded_fallback(codex_route)
    )
    if codex_full:
        statuses["codex"] = "ACTIVE"
    elif codex_route is None and statuses.get("codex") == "ACTIVE":
        statuses["codex"] = "OUT_OF_CREDIT" if telemetry.get("cooldowns") else "NEEDS_MODIFICATION"
    telemetry["coder_statuses"] = statuses

    agr_usable = statuses.get("agr") == "ACTIVE" and bool(agr_models)
    current = str(telemetry.get("active_coder") or "codex")
    if current == "agr" and agr_usable:
        model = main_coder.select_agr_model(task.task_class, agr_models)
        peer = "codex" if codex_full else None
        return "agr", routing.Route(model, main_coder.agr_effort(task.task_class), "antigravity"), None, peer
    if codex_full:
        peer = "agr" if agr_usable else None
        return "codex", codex_route, packet_id, peer
    if agr_usable:
        model = main_coder.select_agr_model(task.task_class, agr_models)
        return "agr", routing.Route(model, main_coder.agr_effort(task.task_class), "antigravity"), None, None
    if codex_route is not None:
        return "codex", codex_route, packet_id, None
    return None, None, None, None

def _select_main_coder_class_route(
    task_class: str,
    codex_catalog: Mapping[str, set[str]],
    agr_models: set[str],
    telemetry: dict[str, Any],
    now: datetime,
) -> tuple[str | None, routing.Route | None]:
    try:
        codex_route = routing.select_route(
            task_class, codex_catalog, telemetry.get("cooldowns", {}), now,
            excluded_models=set(routing.bounded_fallback_models()),
        )
    except RuntimeError:
        codex_route = None
    statuses = dict(telemetry.get("coder_statuses") or {})
    if codex_route is not None and codex_route.provider == "openai":
        statuses["codex"] = "ACTIVE"
    elif statuses.get("codex") == "ACTIVE":
        statuses["codex"] = "OUT_OF_CREDIT" if telemetry.get("cooldowns") else "NEEDS_MODIFICATION"
    telemetry["coder_statuses"] = statuses
    agr_usable = statuses.get("agr") == "ACTIVE" and bool(agr_models)
    current = str(telemetry.get("active_coder") or "codex")
    if current == "agr" and agr_usable:
        try:
            model = main_coder.select_agr_model(task_class, agr_models)
        except RuntimeError:
            pass
        else:
            return "agr", routing.Route(model, main_coder.agr_effort(task_class), "antigravity")
    if codex_route is not None and codex_route.provider == "openai":
        return "codex", codex_route
    if agr_usable:
        try:
            model = main_coder.select_agr_model(task_class, agr_models)
        except RuntimeError:
            return None, None
        return "agr", routing.Route(model, main_coder.agr_effort(task_class), "antigravity")
    return None, None


def _select_main_coder_peer_route(
    peer_coder: str | None,
    task: state.TaskRecord,
    codex_catalog: Mapping[str, set[str]],
    agr_models: set[str],
    telemetry: dict[str, Any],
    now: datetime,
    repo_root: Path,
    project_root: Path,
) -> routing.Route | None:
    if peer_coder == "agr" and telemetry.get("coder_statuses", {}).get("agr") == "ACTIVE":
        try:
            model = main_coder.select_agr_model(task.task_class, agr_models)
        except RuntimeError:
            return None
        return routing.Route(model, main_coder.agr_effort(task.task_class), "antigravity")
    if peer_coder == "codex":
        route, _packet = _select_task_route(
            task, codex_catalog, telemetry.get("cooldowns", {}), now, telemetry, repo_root, project_root
        )
        if route is not None and route.provider == "openai" and not routing.is_bounded_fallback(route):
            return route
    return None


def _write_task_capsule(repo_root: Path, project_root: Path, runtime_root: Path, task: state.TaskRecord, telemetry: Mapping[str, Any]) -> Path:
    project_root = _task_working_directory(repo_root, project_root, task.id)
    path = _task_capsule_path(runtime_root, task.id)
    existing: Mapping[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("task_id") == task.id:
                existing = loaded
        except (OSError, json.JSONDecodeError):
            pass
    previous = telemetry.get("last_result") if isinstance(telemetry.get("last_result"), dict) else {}
    if previous.get("task_id") != task.id:
        previous = existing
    active_coder = str(telemetry.get("active_coder") or "codex")
    capsule = packets.build_task_memory_capsule(
        task, project_root, session_id=_resume_session_for(telemetry, task.id, coder_id=active_coder),
        summary=str(previous.get("summary", "")), evidence=previous.get("evidence", ()),
        dirty_paths=_project_dirty_paths(repo_root, project_root),
    )
    task_coder_sessions = (telemetry.get("coder_sessions") or {}).get(task.id, {}) if isinstance(telemetry.get("coder_sessions"), Mapping) else {}
    capsule["coder_sessions"] = dict(task_coder_sessions) if isinstance(task_coder_sessions, Mapping) else {}
    for name in ("workspace_baseline", "owned_files", "live_observation"):
        if name in existing:
            capsule[name] = existing[name]
    capsule["last_status"] = previous.get("status")
    capsule["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(capsule, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def _checkpoint_task_activity(repo_root: Path, project_root: Path, runtime_root: Path,
                              task: state.TaskRecord, telemetry: Mapping[str, Any],
                              baseline: Mapping[str, Any], previous_owned: Mapping[str, Any]) -> dict[str, Any]:
    """Refresh recoverable bytes from actual activity; never changes task authority."""
    owned = evidence.task_owned_outputs(repo_root, baseline, previous_owned)
    path = _write_task_capsule(repo_root, project_root, runtime_root, task, telemetry)
    capsule = json.loads(path.read_text(encoding="utf-8"))
    capsule["workspace_baseline"] = dict(baseline)
    capsule["owned_files"] = owned
    events = Path(runtime_root) / "events.jsonl"
    if events.is_file():
        with events.open("rb") as stream:
            stream.seek(max(0, events.stat().st_size - 32768))
            lines = stream.read().decode("utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("task_id") == task.id and event.get("type") in {"agent.message", "tool.completed"}:
                capsule["live_observation"] = {"time": event.get("time"), "type": event.get("type"),
                    "seq": event.get("seq"), "text": str(event.get("text", ""))[:1200]}
                break
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(capsule, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    os.replace(tmp, path)
    return owned


def _emit_validation_evidence(repo_root: Path, project_root: Path, result: evidence.TaskResult,
                              journal: production_events.ProductionEventJournal) -> None:
    # Only explicit result evidence references are considered, never command keywords.
    seen = set()
    # Typed family records are independently observable diagnostics.  Emitting a
    # FAIL record never mutates or advances the task; the completion adapter is
    # the only place that can make the final semantic admission decision.
    for record in result.completion_evidence:
        try:
            journal.emit(
                "validation.completed", task_id=result.task_id,
                status=record.verdict, evidence_path=record.evidence_ref,
                evidence_sha256=record.evidence_sha256,
                implementation_ref=record.implementation_ref,
                family_revision=record.family_revision,
                authority_ref=record.authority_ref,
                text="Typed MiniTZ validation-family evidence",
            )
        except Exception:
            # Staged diagnostics are optional observability; one malformed or
            # failed emission must not suppress unrelated evidence.
            continue
    for text in result.evidence:
        for token in re.findall(r"(?:/|[A-Za-z0-9_.-]+/)[^\s`\"<>]*?\.json", text):
            path = Path(token)
            candidates = [path] if path.is_absolute() else [Path(repo_root) / path, Path(project_root) / path]
            for candidate in candidates:
                try:
                    candidate = candidate.resolve()
                    candidate.relative_to(Path(repo_root).resolve())
                    if candidate in seen or not candidate.is_file():
                        continue
                    raw = candidate.read_bytes(); report = json.loads(raw)
                    if not isinstance(report, dict) or report.get("task_id") != result.task_id or report.get("result") not in {"PASS", "FAIL", "FAILED"}:
                        continue
                    seen.add(candidate)
                    journal.emit("validation.completed", task_id=result.task_id,
                        status=report["result"], evidence_path=str(candidate),
                        evidence_sha256=hashlib.sha256(raw).hexdigest(), text="Task validation evidence")
                except (OSError, ValueError, TypeError):
                    continue


def _minitz_owner_direction(project_root: Path) -> str:
    if not state._use_minitz_project(Path(project_root)):
        return ""
    program = minitz.load()
    direction = program.get("owner_direction")
    if not isinstance(direction, Mapping) or not direction:
        return ""
    return (
        "\nMINITZ_OWNER_DIRECTION\n"
        + json.dumps(dict(direction), ensure_ascii=False, sort_keys=True, indent=2)
        + "\nEND_MINITZ_OWNER_DIRECTION\n"
    )


def _main_coder_peer_key(
    task: state.TaskRecord,
    task_state_digest: str,
    peer_coder: str,
    model: str,
    capsule_path: Path,
    projection_path: Path | None,
) -> str:
    capsule_digest = hashlib.sha256(Path(capsule_path).read_bytes()).hexdigest()
    projection_digest = "NONE"
    if projection_path is not None and Path(projection_path).is_file():
        projection_digest = hashlib.sha256(Path(projection_path).read_bytes()).hexdigest()
    return main_coder.peer_assist_key(
        task.id, task_state_digest, peer_coder, model, capsule_digest, projection_digest
    )


def _peer_root(runtime_root: Path) -> Path:
    root = Path(runtime_root) / "memory" / "main-coder-peer"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _launch_main_coder_peer_assist(
    repo_root: Path,
    project_root: Path,
    runtime_root: Path,
    task: state.TaskRecord,
    task_state_digest: str,
    *,
    primary_coder: str,
    peer_coder: str,
    peer_route: routing.Route,
    capsule_path: Path,
    projection_path: Path | None,
    inflight: dict[str, MainCoderPeerHandle],
) -> bool:
    key = _main_coder_peer_key(task, task_state_digest, peer_coder, peer_route.model, capsule_path, projection_path)
    if key in inflight:
        return False
    root = _peer_root(runtime_root)
    safe_task = re.sub(r"[^A-Za-z0-9_.-]+", "_", task.id)
    base = root / f"{safe_task}-{key}"
    accepted_path = base.with_suffix(".accepted.json")
    rejected_path = base.with_suffix(".rejected.json")
    if accepted_path.is_file() or rejected_path.is_file():
        return False
    schema_path = root / "peer-assist.schema.json"
    if not schema_path.is_file():
        schema_path.write_text(json.dumps(main_coder.peer_assist_schema(), sort_keys=True) + "\n", encoding="utf-8")
    output_path = base.with_suffix(".result.json")
    stdout_path = base.with_suffix(".stdout.log")
    stderr_path = base.with_suffix(".stderr.log")
    working_root = _task_working_directory(repo_root, project_root, task.id)
    prompt = main_coder.peer_assist_prompt(
        task_id=task.id, title=task.title, task_state_digest=task_state_digest,
        capsule_path=capsule_path, projection_path=projection_path,
        policy_paths=main_coder.shared_policy_paths(repo_root, working_root),
        primary_coder=primary_coder, peer_coder=peer_coder,
    )
    if peer_coder == "agr":
        command = main_coder.build_agr_stream_command(
            peer_route.model, peer_route.reasoning, schema_path, read_only=True
        )
        stdin_text = main_coder.agr_user_event(prompt) + "\n"
    elif peer_coder == "codex":
        command = routing.build_codex_peer_command(peer_route, schema_path, output_path, working_root)
        stdin_text = prompt
    else:
        raise ValueError(f"unsupported main coder peer: {peer_coder}")
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, text=True, stdout=stdout, stderr=stderr,
            env=os.environ.copy(), cwd=working_root, umask=0o022,
        )
        assert process.stdin is not None
        process.stdin.write(stdin_text)
        process.stdin.close()
    inflight[key] = MainCoderPeerHandle(
        key, peer_coder, peer_route.model, task.id, task_state_digest,
        process, output_path, stdout_path, stderr_path, accepted_path,
    )
    return True


def _collect_main_coder_peer_assists(
    inflight: dict[str, MainCoderPeerHandle],
    telemetry: dict[str, Any],
    journal: production_events.ProductionEventJournal | None = None,
) -> None:
    for key, handle in list(inflight.items()):
        rc = handle.process.poll()
        if rc is None:
            continue
        stdout_text = _tail(handle.stdout_path)
        stderr_text = _tail(handle.stderr_path)
        detail = (stderr_text + "\n" + stdout_text).strip()
        try:
            if rc != 0:
                raise ValueError(detail or f"peer exited {rc}")
            if handle.peer_coder == "agr":
                envelope = main_coder.parse_agr_stream_result(stdout_text.splitlines())
                if str(envelope.get("status") or "").upper() != "SUCCESS":
                    raise ValueError(str(envelope.get("error") or envelope.get("status") or "AGR peer failed"))
                raw_result = envelope.get("structured_output")
                if not isinstance(raw_result, Mapping):
                    response = str(envelope.get("response") or "")
                    raw_result = json.loads(response) if response.strip() else None
            else:
                raw_result = json.loads(handle.output_path.read_text(encoding="utf-8"))
            result = main_coder.validate_peer_assist(raw_result)  # type: ignore[arg-type]
            wrapper = {
                "schema": "minitz.main_coder_peer_assist/v1",
                "authority": "NONE",
                "task_id": handle.task_id,
                "task_state_digest": handle.task_state_digest,
                "peer_key": handle.key,
                "peer_coder": handle.peer_coder,
                "model": handle.model,
                "result": result,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            tmp = handle.accepted_path.with_suffix(handle.accepted_path.suffix + ".tmp")
            tmp.write_text(json.dumps(wrapper, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            os.replace(tmp, handle.accepted_path)
            telemetry.setdefault("coder_statuses", {})[handle.peer_coder] = "ACTIVE"
            if journal is not None:
                journal.emit("coder.peer_assist_completed", task_id=handle.task_id, status="ACTIVE", text=str(handle.accepted_path), coder=handle.peer_coder, model=handle.model)
        except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
            telemetry.setdefault("coder_status_detail", {})[handle.peer_coder] = str(exc)[-1200:]
            if handle.peer_coder == "agr":
                telemetry.setdefault("coder_statuses", {})["agr"] = main_coder.classify_agr_observation(int(rc), detail + "\n" + str(exc))
            rejected_path = handle.accepted_path.with_name(handle.accepted_path.name.replace(".accepted.json", ".rejected.json"))
            rejected = {
                "schema": "minitz.main_coder_peer_rejection/v1", "authority": "NONE",
                "task_id": handle.task_id, "task_state_digest": handle.task_state_digest,
                "peer_key": handle.key, "peer_coder": handle.peer_coder, "model": handle.model,
                "status": telemetry.get("coder_statuses", {}).get(handle.peer_coder),
                "detail": str(exc)[-1200:], "created_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                tmp = rejected_path.with_suffix(rejected_path.suffix + ".tmp")
                tmp.write_text(json.dumps(rejected, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
                os.replace(tmp, rejected_path)
            except OSError:
                pass
            if journal is not None:
                journal.emit("coder.peer_assist_failed", task_id=handle.task_id, status=telemetry.get("coder_statuses", {}).get(handle.peer_coder), text=str(exc)[-1200:], coder=handle.peer_coder, model=handle.model)
        finally:
            inflight.pop(key, None)


def _latest_main_coder_peer_assist(runtime_root: Path, task_id: str, task_state_digest: str) -> Path | None:
    root = Path(runtime_root) / "memory" / "main-coder-peer"
    if not root.is_dir():
        return None
    safe_task = re.sub(r"[^A-Za-z0-9_.-]+", "_", task_id)
    matches: list[tuple[str, Path]] = []
    for path in root.glob(f"{safe_task}-*.accepted.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping) or payload.get("authority") != "NONE":
            continue
        if payload.get("task_id") != task_id or payload.get("task_state_digest") != task_state_digest:
            continue
        matches.append((str(payload.get("created_at") or ""), path))
    return max(matches, default=("", None), key=lambda item: item[0])[1]


def _terminate_main_coder_peers(inflight: dict[str, MainCoderPeerHandle]) -> None:
    for handle in list(inflight.values()):
        if handle.process.poll() is None:
            try:
                handle.process.terminate()
            except OSError:
                pass
    inflight.clear()


def _commander_root(runtime_root: Path) -> Path:
    return Path(runtime_root) / "memory" / "commander-fabric"


def _commander_index_path(runtime_root: Path) -> Path:
    return _commander_root(runtime_root) / "current.json"


def _commander_paths(runtime_root: Path, key: str) -> tuple[Path, Path, Path, Path, Path]:
    root = _commander_root(runtime_root)
    return (
        root / f"{key}.stdout.json",
        root / f"{key}.stderr.log",
        root / f"{key}.lease.json",
        root / f"{key}.accepted.json",
        root / f"{key}.rejected.json",
    )


def _commander_provider_limit() -> int:
    try:
        value = int(os.environ.get("BIELLA_COMMANDER_PROVIDER_MAX_INFLIGHT", str(commander.DEFAULT_PROVIDER_MAX_INFLIGHT)))
    except ValueError:
        value = commander.DEFAULT_PROVIDER_MAX_INFLIGHT
    return max(1, min(commander.COMMANDER_LANE_COUNT, value))


def _commander_result_tokens() -> int:
    try:
        value = int(os.environ.get("BIELLA_COMMANDER_RESULT_MAX_TOKENS", str(commander.DEFAULT_RESULT_MAX_TOKENS)))
    except ValueError:
        value = commander.DEFAULT_RESULT_MAX_TOKENS
    return max(64, min(1024, value))


def _commander_index_row(
    lane: commander.CommanderLane,
    *,
    provider: str | None,
    key: str | None,
    status: str,
    activity: str,
    result_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "role": lane.role,
        "status": status if status in commander.COMMANDER_STATUSES else "NEEDS_MODIFICATION",
        "activity": activity,
        "provider": provider,
        "cache_key": key,
        "result_path": str(result_path) if result_path is not None else None,
    }


def _commander_cached_row(
    lane: commander.CommanderLane,
    *,
    task_id: str,
    task_state_digest: str,
    projection_digest: str,
    provider: str,
    key: str,
    accepted_path: Path,
    rejected_path: Path,
) -> dict[str, Any] | None:
    if accepted_path.is_file():
        payload = commander.read_json(accepted_path)
        result = payload.get("result") if isinstance(payload.get("result"), Mapping) else {}
        if (
            payload.get("authority") == "NONE"
            and payload.get("task_id") == task_id
            and payload.get("task_state_digest") == task_state_digest
            and payload.get("projection_digest") == projection_digest
            and payload.get("lane_id") == lane.lane_id
        ):
            activity = str(result.get("status") or "NO_FINDING")
            return _commander_index_row(
                lane, provider=str(payload.get("provider") or provider), key=key,
                status="ACTIVE", activity=activity, result_path=accepted_path,
            )
    if rejected_path.is_file():
        payload = commander.read_json(rejected_path)
        if (
            payload.get("authority") == "NONE"
            and payload.get("task_id") == task_id
            and payload.get("task_state_digest") == task_state_digest
            and payload.get("projection_digest") == projection_digest
            and payload.get("lane_id") == lane.lane_id
        ):
            retry_after = str(payload.get("retry_after") or "")
            if retry_after:
                try:
                    retry_at = datetime.fromisoformat(retry_after.replace("Z", "+00:00"))
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    retry_at = datetime.now(timezone.utc)
                if datetime.now(timezone.utc) >= retry_at:
                    rejected_path.unlink(missing_ok=True)
                    return None
            status = str(payload.get("status") or "NEEDS_MODIFICATION")
            return _commander_index_row(
                lane, provider=str(payload.get("provider") or provider), key=key,
                status=status, activity="REJECTED", result_path=rejected_path,
            )
    return None


def _update_commander_index_lane(
    runtime_root: Path,
    handle: CommanderHandle,
    *,
    status: str,
    activity: str,
    provider: str | None,
    result_path: Path | None,
) -> None:
    path = _commander_index_path(runtime_root)
    index = commander.read_json(path)
    if (
        index.get("task_id") != handle.task_id
        or index.get("task_state_digest") != handle.task_state_digest
        or index.get("projection_digest") != handle.projection_digest
    ):
        return
    rows = index.get("lanes") if isinstance(index.get("lanes"), list) else []
    updated = []
    for raw in rows:
        if not isinstance(raw, Mapping) or raw.get("lane_id") != handle.lane_id:
            updated.append(dict(raw) if isinstance(raw, Mapping) else raw)
            continue
        row = dict(raw)
        row.update({
            "status": status if status in commander.COMMANDER_STATUSES else "NEEDS_MODIFICATION",
            "activity": activity,
            "provider": provider or handle.requested_provider,
            "result_path": str(result_path) if result_path is not None else None,
        })
        updated.append(row)
    index["lanes"] = updated
    index["updated_at"] = datetime.now(timezone.utc).isoformat()
    commander.atomic_json(path, index)


def _launch_commander_assists(
    repo_root: Path,
    project_root: Path,
    runtime_root: Path,
    task: state.TaskRecord,
    task_state_digest: str,
    capsule_path: Path,
    projection_path: Path | None,
    inflight: dict[str, CommanderHandle],
    journal: production_events.ProductionEventJournal | None = None,
) -> Path:
    root = _commander_root(runtime_root)
    root.mkdir(parents=True, exist_ok=True)
    index_path = _commander_index_path(runtime_root)
    projection_digest = "NONE"
    projection: dict[str, object] = {}
    if projection_path is not None and Path(projection_path).is_file():
        projection_digest = hashlib.sha256(Path(projection_path).read_bytes()).hexdigest()
        projection = commander.read_json(Path(projection_path))
    capsule = commander.read_json(Path(capsule_path)) if Path(capsule_path).is_file() else {}
    context = commander.bounded_context(capsule, projection)
    try:
        registry = json.loads((Path(repo_root) / "ops/workstation/provider-registry.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        registry = {"providers": {}, "routes": {"llm.fast": []}}
    providers = commander.eligible_external_providers(registry, os.environ)
    provider_limit = _commander_provider_limit()
    schedule = commander.provider_schedule(commander.commander_lanes(), providers, per_provider_limit=provider_limit)
    prior_index = commander.read_json(index_path)
    same_index = (
        prior_index.get("authority") == "NONE"
        and prior_index.get("task_id") == task.id
        and prior_index.get("task_state_digest") == task_state_digest
        and prior_index.get("projection_digest") == projection_digest
    )
    provider_proven_active: set[str] = set()
    provider_backoff: dict[str, tuple[str, str]] = {}
    if same_index:
        for raw in prior_index.get("lanes", []) if isinstance(prior_index.get("lanes"), list) else []:
            if not isinstance(raw, Mapping):
                continue
            provider = str(raw.get("provider") or "")
            result_path = Path(str(raw.get("result_path") or "")) if raw.get("result_path") else None
            if not provider or result_path is None or not result_path.is_file():
                continue
            payload = commander.read_json(result_path)
            if (
                payload.get("authority") != "NONE"
                or payload.get("task_id") != task.id
                or payload.get("task_state_digest") != task_state_digest
                or payload.get("projection_digest") != projection_digest
            ):
                continue
            if str(raw.get("status") or "") == "ACTIVE" and str(raw.get("activity") or "") in {"USEFUL", "NO_FINDING"}:
                provider_proven_active.add(provider)
                continue
            if str(raw.get("activity") or "") == "REJECTED":
                retry_after = str(payload.get("retry_after") or "")
                if not retry_after:
                    continue
                try:
                    retry_at = datetime.fromisoformat(retry_after.replace("Z", "+00:00"))
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if datetime.now(timezone.utc) < retry_at:
                    status = str(payload.get("status") or "NEEDS_MODIFICATION")
                    provider_backoff[provider] = (status, retry_after)
    provider_inflight: dict[str, int] = {}
    for existing in inflight.values():
        provider_inflight[existing.requested_provider] = provider_inflight.get(existing.requested_provider, 0) + 1
    rows: list[dict[str, Any]] = []
    launched = 0
    for lane in commander.commander_lanes():
        provider = schedule.get(lane.lane_id)
        if not provider:
            rows.append(_commander_index_row(lane, provider=None, key=None, status="OFFLINE", activity="UNASSIGNED"))
            continue
        key = commander.commander_cache_key(
            task.id, task_state_digest, projection_digest, lane.lane_id, lane.role, provider
        )
        stdout_path, stderr_path, lease_path, accepted_path, rejected_path = _commander_paths(runtime_root, key)
        cached = _commander_cached_row(
            lane, task_id=task.id, task_state_digest=task_state_digest,
            projection_digest=projection_digest, provider=provider, key=key,
            accepted_path=accepted_path, rejected_path=rejected_path,
        )
        if cached is not None:
            rows.append(cached)
            continue
        blocked = provider_backoff.get(provider)
        if blocked is not None:
            rows.append(_commander_index_row(
                lane, provider=provider, key=key, status=blocked[0], activity="PROVIDER_BACKOFF"
            ))
            continue
        existing = inflight.get(key)
        if existing is not None and existing.process.poll() is None:
            rows.append(_commander_index_row(lane, provider=provider, key=key, status="ACTIVE", activity="RUNNING"))
            continue
        lease = commander.read_json(lease_path) if lease_path.is_file() else {}
        if lease:
            if commander.lease_is_stale(lease):
                lease_path.unlink(missing_ok=True)
            else:
                rows.append(_commander_index_row(lane, provider=provider, key=key, status="ACTIVE", activity="RUNNING"))
                continue
        effective_provider_limit = provider_limit if provider in provider_proven_active else 1
        if len(inflight) >= commander.COMMANDER_LANE_COUNT or provider_inflight.get(provider, 0) >= effective_provider_limit:
            rows.append(_commander_index_row(lane, provider=provider, key=key, status="OFFLINE", activity="UNASSIGNED"))
            continue
        packet = commander.commander_packet(
            lane=lane, task_id=task.id, task_state_digest=task_state_digest,
            projection_digest=projection_digest, requested_provider=provider, context=context,
        )
        prompt = commander.commander_prompt(packet)
        command = commander.build_resource_command(provider, max_tokens=_commander_result_tokens())
        try:
            with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
                process = subprocess.Popen(
                    command, stdin=subprocess.PIPE, text=True, stdout=stdout, stderr=stderr,
                    env=os.environ.copy(), cwd=Path(repo_root), umask=0o022,
                )
                assert process.stdin is not None
                process.stdin.write(prompt)
                process.stdin.close()
            commander.atomic_json(
                lease_path,
                commander.lease_record(key, task.id, lane.lane_id, provider, int(process.pid)),
            )
            inflight[key] = CommanderHandle(
                key=key, lane_id=lane.lane_id, role=lane.role, requested_provider=provider,
                task_id=task.id, task_state_digest=task_state_digest, projection_digest=projection_digest,
                process=process, stdout_path=stdout_path, stderr_path=stderr_path,
                lease_path=lease_path, accepted_path=accepted_path, rejected_path=rejected_path,
            )
            provider_inflight[provider] = provider_inflight.get(provider, 0) + 1
            launched += 1
            rows.append(_commander_index_row(lane, provider=provider, key=key, status="ACTIVE", activity="RUNNING"))
            if journal is not None:
                journal.emit(
                    "commander.assist_started", task_id=task.id, status="ACTIVE",
                    text=f"{lane.lane_id} {lane.role}", lane_id=lane.lane_id,
                    role=lane.role, provider=provider, authority="NONE",
                )
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            status = commander.classify_failure(getattr(exc, "returncode", 1) or 1, str(exc))
            rejected = {
                "schema": "minitz.commander_rejection/v1", "authority": "NONE",
                "task_id": task.id, "task_state_digest": task_state_digest,
                "projection_digest": projection_digest, "lane_id": lane.lane_id,
                "role": lane.role, "provider": provider, "cache_key": key,
                "status": status, "detail": str(exc)[-1200:],
                "retry_after": commander.failure_retry_after(status),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            commander.atomic_json(rejected_path, rejected)
            rows.append(_commander_index_row(lane, provider=provider, key=key, status=status, activity="REJECTED", result_path=rejected_path))
            if journal is not None:
                journal.emit(
                    "commander.assist_failed", task_id=task.id, status=status,
                    text=str(exc)[-1200:], lane_id=lane.lane_id, role=lane.role,
                    provider=provider, authority="NONE",
                )
    index = {
        "schema": "minitz.commander_fabric/v1",
        "authority": "NONE",
        "progression_authority": False,
        "task_id": task.id,
        "task_state_digest": task_state_digest,
        "projection_digest": projection_digest,
        "total_lanes": commander.COMMANDER_LANE_COUNT,
        "provider_limit": provider_limit,
        "provider_canary_first": True,
        "provider_proven_active": sorted(provider_proven_active),
        "provider_backoff": {provider: {"status": value[0], "retry_after": value[1]} for provider, value in sorted(provider_backoff.items())},
        "eligible_providers": list(providers),
        "launched_this_pass": launched,
        "lanes": rows,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    commander.atomic_json(index_path, index)
    return index_path


def _prepare_commander_assists_nonblocking(
    repo_root: Path,
    project_root: Path,
    runtime_root: Path,
    task: state.TaskRecord,
    task_state_digest: str,
    capsule_path: Path,
    projection_path: Path | None,
    inflight: dict[str, CommanderHandle],
    journal: production_events.ProductionEventJournal | None = None,
) -> Path | None:
    try:
        return _launch_commander_assists(
            repo_root, project_root, runtime_root, task, task_state_digest,
            capsule_path, projection_path, inflight, journal,
        )
    except Exception as exc:
        if journal is not None:
            journal.emit(
                "commander.fabric_failed", task_id=task.id, status="NEEDS_MODIFICATION",
                text=str(exc)[-1200:], authority="NONE",
            )
        existing = _commander_index_path(runtime_root)
        return existing if existing.is_file() else None


def _collect_commander_assists(
    runtime_root: Path,
    inflight: dict[str, CommanderHandle],
    journal: production_events.ProductionEventJournal | None = None,
) -> None:
    for key, handle in list(inflight.items()):
        rc = handle.process.poll()
        if rc is None:
            continue
        stdout_text = _tail(handle.stdout_path)
        stderr_text = _tail(handle.stderr_path)
        detail = (stderr_text + "\n" + stdout_text).strip()
        try:
            if rc != 0:
                raise ValueError(detail or f"Commander exited {rc}")
            raw_result, meta = commander.parse_resource_result(stdout_text)
            packet = {
                "lane_id": handle.lane_id,
                "task_id": handle.task_id,
                "task_state_digest": handle.task_state_digest,
                "projection_digest": handle.projection_digest,
            }
            result = commander.validate_commander_result(packet, raw_result)
            wrapper = {
                "schema": "minitz.commander_assist/v1",
                "authority": "NONE",
                "progression_authority": False,
                "task_id": handle.task_id,
                "task_state_digest": handle.task_state_digest,
                "projection_digest": handle.projection_digest,
                "lane_id": handle.lane_id,
                "role": handle.role,
                "requested_provider": handle.requested_provider,
                "provider": meta.get("provider") or handle.requested_provider,
                "model": meta.get("model"),
                "routing_evidence": meta.get("routing_evidence") or {},
                "usage": meta.get("usage") or {},
                "result": result,
                "cache_key": handle.key,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            commander.atomic_json(handle.accepted_path, wrapper)
            _update_commander_index_lane(
                runtime_root, handle, status="ACTIVE", activity=str(result.get("status") or "NO_FINDING"),
                provider=str(wrapper.get("provider") or handle.requested_provider), result_path=handle.accepted_path,
            )
            if journal is not None:
                journal.emit(
                    "commander.assist_completed", task_id=handle.task_id, status="ACTIVE",
                    text=str(handle.accepted_path), lane_id=handle.lane_id, role=handle.role,
                    provider=wrapper.get("provider"), authority="NONE",
                )
        except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
            status = commander.classify_failure(int(rc), detail + "\n" + str(exc))
            rejected = {
                "schema": "minitz.commander_rejection/v1", "authority": "NONE",
                "progression_authority": False,
                "task_id": handle.task_id, "task_state_digest": handle.task_state_digest,
                "projection_digest": handle.projection_digest, "lane_id": handle.lane_id,
                "role": handle.role, "provider": handle.requested_provider,
                "cache_key": handle.key, "status": status, "detail": str(exc)[-1200:],
                "retry_after": commander.failure_retry_after(status),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            commander.atomic_json(handle.rejected_path, rejected)
            _update_commander_index_lane(
                runtime_root, handle, status=status, activity="REJECTED",
                provider=handle.requested_provider, result_path=handle.rejected_path,
            )
            if journal is not None:
                journal.emit(
                    "commander.assist_failed", task_id=handle.task_id, status=status,
                    text=str(exc)[-1200:], lane_id=handle.lane_id, role=handle.role,
                    provider=handle.requested_provider, authority="NONE",
                )
        finally:
            handle.lease_path.unlink(missing_ok=True)
            inflight.pop(key, None)


def _collect_commander_assists_nonblocking(
    runtime_root: Path,
    inflight: dict[str, CommanderHandle],
    journal: production_events.ProductionEventJournal | None = None,
) -> None:
    try:
        _collect_commander_assists(runtime_root, inflight, journal)
    except Exception as exc:
        if journal is not None:
            journal.emit(
                "commander.fabric_failed", status="NEEDS_MODIFICATION",
                text=str(exc)[-1200:], authority="NONE",
            )
        _terminate_commander_assists(runtime_root, inflight)


def _terminate_commander_assists(runtime_root: Path, inflight: dict[str, CommanderHandle]) -> None:
    for key, handle in list(inflight.items()):
        try:
            if handle.process.poll() is None:
                try:
                    handle.process.terminate()
                except OSError:
                    pass
            try:
                handle.lease_path.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                _update_commander_index_lane(
                    runtime_root, handle, status="OFFLINE", activity="TERMINATED",
                    provider=handle.requested_provider, result_path=None,
                )
            except OSError:
                pass
        finally:
            inflight.pop(key, None)


def _task_prompt(repo_root: Path, production: state.ProductionState, task: state.TaskRecord, telemetry: Mapping[str, Any], capsule_path: Path, projection_path: Path | None = None, local_assist_path: Path | None = None, taskbooster_path: Path | None = None, route: routing.Route | None = None, peer_assist_path: Path | None = None, commander_index_path: Path | None = None, *, coder_id: str = "codex") -> str:
    guide_path = Path(production.project_root) / "docs" / "task-guides" / f"{task.id}.md"
    priority_context = f"\nMINITZ_TASK_PROGRAM: {production.priority_policy}. Follow the exact living MiniTZ Task Program order/status and current Task/Run continuity. No ledger, map, helper, or session may advance it independently. Preserve accepted output and required quality.\n"
    owner_context = _minitz_owner_direction(production.project_root)
    working_root = _task_working_directory(repo_root, Path(production.project_root), task.id)
    policies = main_coder.shared_policy_paths(repo_root, working_root)
    policy_context = f"\nMAIN_CODER_BACKEND: {coder_id}\n"
    if policies:
        policy_context += f"SHARED_MINITZ_POLICY: {policies[0]}\n"
        if len(policies) > 1:
            policy_context += f"PROJECT_AGENTS_POLICY: {policies[1]}\n"
        policy_context += "Apply these same MiniTZ/Project instructions regardless of coder backend; backend change never changes authority, acceptance, memory, cache, or task scope.\n"
    if route is not None and routing.is_bounded_fallback(route):
        return priority_context + owner_context + policy_context + packets.compile_bounded_fallback_packet(task, capsule_path, projection_path, guide_path if guide_path.exists() else None) + execution_map.task_context(repo_root, task.id)
    if _task_has_shared_continuity(telemetry, task.id, capsule_path):
        prompt = packets.compile_resume_packet(task, capsule_path)
    else:
        prompt = packets.compile_task_packet(repo_root, production, task)
        if capsule_path.exists():
            prompt += f"\nTASK_MEMORY: {capsule_path}\nRead this bounded recovery capsule before redoing any existing work.\n"
    prompt = priority_context + owner_context + policy_context + prompt
    if production.run_id == "minitz-task-program":
        prompt += (
            "\nMINITZ_VALIDATION_COMPLETION_FAMILY\n"
            "For COMPLETE or COMPLETE_ALREADY, use the exact current MiniTZ Task Program task revision and task_record digest. "
            "Return task_revision, task_digest, scope_ref, family_revision, authority_ref, and accepted_criteria. "
            "Every completion evidence entry must be a bounded typed JSON validation-family record with exact task identity, "
            "evidence digest, evidence reference, implementation reference, verdict, and current provenance. Include exactly one "
            "FAMILY_RECEIPT binding all useful implementation refs and required criteria. Cited FAIL or FAILED evidence vetoes "
            "completion. Helpers, audits, and diagnostics never progress the Task; invalid or stale records yield no assist and "
            "the strong route continues.\nEND_MINITZ_VALIDATION_COMPLETION_FAMILY\n"
        )
    if guide_path.exists():
        guide_text = guide_path.read_text(encoding="utf-8")[:12000]
        prompt += (
            f"\nTASK_GUIDE: {guide_path}\n"
            "Read TASK_GUIDE before broad source search. The complete bounded guide content is embedded below so no extra lookup is required. "
            "Use it to avoid naming/discovery stalls. It does not override current source, exact runtime evidence, or Project authority.\n"
            "--- TASK GUIDE CONTENT ---\n" + guide_text + "\n--- END TASK GUIDE CONTENT ---\n"
        )
    if projection_path and Path(projection_path).exists():
        prompt += (
            f"\nMEMORY_PROJECTION: {projection_path}\n"
            "This is a rebuildable compact derivative of current authority, verified actions, failures, and capabilities. "
            "Use it to avoid redundant rereads; follow its source refs back to raw authority/evidence when exact detail is required. "
            "It never overrides current source or task authority.\n"
        )
    if local_assist_path and Path(local_assist_path).exists():
        prompt += (
            f"\nLOCAL_RESOURCE_ASSIST: {local_assist_path}\n"
            "This local-Qwen output is non-authoritative bounded assistance. Reuse useful analysis, validate it against current source/evidence, "
            "and do not repeat its work with Codex unless validation or missing detail requires it.\n"
        )
    if taskbooster_path and Path(taskbooster_path).exists():
        prompt += (
            f"\nTASKBOOSTER_ASSIST: {taskbooster_path}\n"
            "This Spark TaskBooster result is non-authoritative, read-only, evidence-grounded assistance produced for one exact microtask. "
            "Validate it against current source/evidence before reuse. It cannot complete, advance, reorder, commit, publish, or mutate the task. "
            "Do not repeat its analysis unless validation or missing detail requires it.\n"
        )
    if peer_assist_path and Path(peer_assist_path).exists():
        prompt += (
            f"\nMAIN_CODER_PEER_ASSIST: {peer_assist_path}\n"
            "This is non-authoritative read-only assistance from the other main coder using the same MiniTZ task state. "
            "Reuse grounded findings when useful and validate them against current source/evidence. It cannot complete, advance, reorder, commit, publish, or mutate the task. "
            "Do not repeat equivalent analysis unless the current source changed or validation requires it.\n"
        )
    if commander_index_path and Path(commander_index_path).exists():
        prompt += (
            f"\nCOMMANDER_FABRIC_INDEX: {commander_index_path}\n"
            "AUTHORITY: NONE. This index represents exactly 30 non-authoritative read-only Commander assist lanes sharing this MiniTZ task state. "
            "Read accepted result paths only when useful, validate every finding against current source/evidence, and never wait for unfinished lanes. "
            "Commander lanes cannot complete, advance, reorder, commit, publish, or mutate the task. They are optional acceleration only.\n"
        )
    alignment = telemetry.get("source_alignment") or {}
    if alignment.get("state") == "RECONCILIATION_REQUIRED":
        prompt += (
            "\nSOURCE_REPAIR_WITHIN_CURRENT_TASK: " + str(alignment.get("detail", "")) + "\n"
            "Inspect the exact local and remote revisions and affected paths. Reconcile compatible changes with a normal merge or fast-forward, preserving current work. "
            "No reset, clean, stash, force-push, history rewrite or whole-task replay. Reuse unaffected validation. "
            "This is an executable repair in the existing task/session, not a request for another approval or a reason to sleep.\n"
        )
    prompt += execution_map.task_context(repo_root, task.id)
    prompt += "\n" + execution_style.proven_execution_style_prompt()
    return prompt


def _refresh_memory_projection(repo_root: Path, project_root: Path, runtime_root: Path, task_id: str, journal: production_events.ProductionEventJournal | None = None) -> Path | None:
    try:
        result = memory_compactor.refresh_compacted_memory(
            repo_root, project_root, runtime_root, current_task_id=task_id
        )
    except Exception as exc:
        if journal is not None:
            journal.emit(
                "memory.compaction_failed", task_id=task_id, status="ERROR",
                text=f"Compacted memory refresh failed; continuing from raw task memory: {exc}",
            )
        return None
    if journal is not None:
        journal.emit(
            "memory.compacted", task_id=task_id, status="COMPLETE",
            text=str(result.projection_path), full_index=str(result.index_path),
        )
    return result.projection_path


def _assist_projection_payload(projection: Mapping[str, Any]) -> dict[str, Any]:
    memory = projection.get("task_memory") if isinstance(projection.get("task_memory"), Mapping) else {}
    memory_keep = {
        key: memory.get(key) for key in (
            "task_id", "task_class", "title", "summary", "next_action",
            "last_status", "evidence", "dirty_path_count"
        ) if memory.get(key) is not None
    }
    failures = []
    for row in projection.get("failures", []) if isinstance(projection.get("failures"), list) else []:
        if not isinstance(row, Mapping):
            continue
        failures.append({
            key: row.get(key) for key in (
                "task_id", "failure_type", "type", "status", "text",
                "detail", "diagnostic", "tool", "exit_code", "evidence",
                "helper_budget_seconds", "elapsed_seconds", "provider", "model", "event_type"
            ) if row.get(key) is not None
        })
    return {
        "task_id": projection.get("task_id"),
        "task_memory": memory_keep,
        "failures": failures[-8:],
        "capabilities": projection.get("capabilities") or {},
        "verified_actions": projection.get("verified_actions") or [],
    }


_ASSIST_FILE_SUFFIXES = (".cpp", ".cc", ".c", ".h", ".hpp", ".py", ".md", ".json", ".ini", ".yaml", ".yml", ".uasset", ".umap", ".wav", ".png")


def _assist_unresolved_paths(text: str, project_root: Path | None) -> list[str]:
    if project_root is None:
        return []
    project_root = Path(project_root)
    repo_root = project_root.parents[1] if len(project_root.parents) > 1 else project_root
    missing: list[str] = []
    for token in re.findall(r"`([^`\n]+)`", str(text or "")):
        candidate = token.strip().strip('"\'')
        if not candidate or "://" in candidate or any(ch in candidate for ch in "*?{}"):
            continue
        # Ignore command snippets/symbols; validate only path-like spans.
        if " " in candidate or not ("/" in candidate or candidate.lower().endswith(_ASSIST_FILE_SUFFIXES)):
            continue
        candidate = candidate.split("::", 1)[0]
        if candidate.startswith("/Game/"):
            rel = candidate[len("/Game/"):].strip("/")
            base = project_root / "Content" / rel
            if base.exists() or any(Path(str(base) + ext).exists() for ext in (".uasset", ".umap")):
                continue
            missing.append(candidate); continue
        path = Path(candidate)
        if path.is_absolute():
            if not path.exists(): missing.append(candidate)
            continue
        if not (project_root / path).exists() and not (repo_root / path).exists():
            missing.append(candidate)
    return sorted(set(missing))


def _assist_clean_task_out_of_scope_paths(text: str, meaningful: Mapping[str, Any], project_root: Path | None) -> list[str]:
    """Reject path suggestions not already present in a clean task's bounded input."""
    if meaningful.get("failures") or project_root is None:
        return []
    project_root = Path(project_root)
    supported = json.dumps(meaningful, sort_keys=True, ensure_ascii=False)
    unsupported: list[str] = []
    for token in re.findall(r"`([^`\n]+)`", str(text or "")):
        candidate = token.strip().strip('"\'')
        if not candidate or "://" in candidate or any(ch in candidate for ch in "*?{}"):
            continue
        if " " in candidate or not ("/" in candidate or candidate.lower().endswith(_ASSIST_FILE_SUFFIXES)):
            continue
        candidate = candidate.split("::", 1)[0]
        variants = {candidate}
        path = Path(candidate)
        if path.is_absolute():
            try:
                variants.add(str(path.relative_to(project_root)))
            except ValueError:
                pass
        if not any(variant and variant in supported for variant in variants):
            unsupported.append(candidate)
    return sorted(set(unsupported))


def _hydrate_assist_verified_actions(projection: Mapping[str, Any], runtime_root: Path) -> list[dict[str, str]]:
    actions = projection.get("verified_actions")
    if not isinstance(actions, list):
        return []
    content: Mapping[str, Any] = {}
    full_index = str(projection.get("full_index") or "").strip()
    if full_index:
        path = Path(full_index)
        if not path.is_absolute():
            path = Path(runtime_root) / path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping) and isinstance(payload.get("content"), Mapping):
                content = payload["content"]
        except (OSError, json.JSONDecodeError):
            content = {}
    hydrated: list[dict[str, str]] = []
    for item in actions:
        ref = ""
        text = ""
        if isinstance(item, str):
            ref = item
        elif isinstance(item, Mapping):
            ref = str(item.get("content_ref") or "")
            text = str(item.get("text") or "").strip()
        if ref and not text:
            row = content.get(ref) if isinstance(content, Mapping) else None
            if isinstance(row, Mapping):
                text = str(row.get("text") or "").strip()
        if ref and text:
            hydrated.append({"content_ref": ref, "text": text})
    return hydrated


def _assist_ungrounded_verified_action_claim(text: str, verified_actions: list[Mapping[str, Any]]) -> str | None:
    exact = {str(row.get("content_ref") or ""): str(row.get("text") or "") for row in verified_actions if isinstance(row, Mapping)}
    for line in str(text or "").splitlines():
        refs = re.findall(r"sha256:[0-9a-fA-F]{64}", line)
        for ref in refs:
            expected = exact.get(ref)
            if not expected or expected not in line:
                return line.strip()
    return None


def _assist_invented_failure_claim(text: str, failures: list[Mapping[str, Any]]) -> str | None:
    """Return the unsupported failure claim when a clean projection is made negative."""
    if failures:
        return None
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if re.search(r"\bretry\s+(?:the\s+)?(?:failing|failed)\b", lower):
            return line
        match = re.search(r"likely\s+failure\s+cause(?:\s+if\s+any)?\s*:\s*(.+)$", line, re.IGNORECASE)
        if not match:
            match = re.search(r"(?:^|[()0-9. -])failure(?:\s+cause)?\s*:\s*(.+)$", line, re.IGNORECASE)
        if match:
            claim = match.group(1).strip()
            if not re.match(r"^(?:none|n/?a|not applicable|no (?:unresolved )?failure|no failure)(?:\b|\s|[.;,-])", claim, re.IGNORECASE):
                return line
    return None


_FAST_LLM_HELPER_BUDGET_SECONDS = 110.0
_SPARK_HELPER_BUDGET_SECONDS = 180.0


def _helper_failure_cools_model(failure_type: str) -> bool:
    del failure_type
    return False


def _helper_process_failure_type(detail: str) -> str:
    text = str(detail or "").lower()
    unavailable = ("connection refused", "failed to connect", "service unavailable", "no route to host", "provider unavailable")
    return "PROVIDER_UNAVAILABLE" if any(token in text for token in unavailable) else "PROCESS_FAILED"


def _emit_helper_failure(journal: production_events.ProductionEventJournal | None, event_type: str, *,
                         task_id: str, failure_type: str, budget_seconds: float, started: float,
                         text: str, provider: str, model: str | None = None, raw_result_path: Path | None = None,
                         detail: str | None = None, exit_code: int | None = None, status: str = "ERROR") -> None:
    if journal is None:
        return
    journal.emit(
        event_type, task_id=task_id, status=status, text=text, provider=provider, model=model,
        failure_type=failure_type, helper_budget_seconds=budget_seconds,
        elapsed_seconds=max(0.0, time.monotonic() - started),
        raw_result_path=str(raw_result_path) if raw_result_path else None, detail=detail, exit_code=exit_code,
    )


def _ensure_local_resource_assist(runtime_root: Path, task_id: str, projection_path: Path, journal: production_events.ProductionEventJournal | None = None, *, project_root: Path | None = None) -> Path | None:
    try:
        projection = json.loads(Path(projection_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if journal is not None:
            journal.emit("resource.local_assist_failed", task_id=task_id, status="ERROR", text=f"Projection unavailable for local assist: {exc}")
        return None
    if not isinstance(projection, Mapping):
        return None
    meaningful = _assist_projection_payload(projection)
    hydrated_actions = _hydrate_assist_verified_actions(projection, Path(runtime_root))
    # Cross-task verified patterns are useful for diagnosing an actual semantic
    # blocker, but on a clean task they can anchor local Qwen on unrelated work.
    meaningful["verified_actions"] = hydrated_actions if meaningful.get("failures") else []
    canonical = json.dumps(meaningful, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    safe_task = str(task_id).replace("/", "_")
    path = Path(runtime_root) / "memory" / "local-assist" / f"{safe_task}-{digest[:20]}.json"
    rejected_path = path.with_suffix(path.suffix + ".rejected")
    raw_path = path.with_suffix(path.suffix + ".raw.json")
    if rejected_path.exists():
        return None
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            cached_text = str(cached.get("text") or "")
            missing = _assist_unresolved_paths(cached_text, project_root)
            out_of_scope = _assist_clean_task_out_of_scope_paths(cached_text, meaningful, project_root)
            invented = _assist_invented_failure_claim(cached_text, list(meaningful.get("failures") or []))
            verified_claim = _assist_ungrounded_verified_action_claim(cached_text, list(meaningful.get("verified_actions") or []))
        except (OSError, json.JSONDecodeError):
            missing = ["invalid cached assist"]
            out_of_scope = []
            invented = None
            verified_claim = None
        if not missing and not out_of_scope and not invented and not verified_claim:
            return path
        if verified_claim:
            rejection = {"reason":"ungrounded_verified_action_claim","claim":verified_claim}
            recovery_text = "Rejected cached local assist with ungrounded verified-action claim: " + verified_claim
        elif invented:
            rejection = {"reason":"ungrounded_failure_claim","claim":invented}
            recovery_text = "Rejected cached local assist with invented failure claim: " + invented
        elif out_of_scope:
            rejection = {"reason":"out_of_scope_paths","paths":out_of_scope}
            recovery_text = "Rejected cached local assist with paths outside current clean-task input: " + ", ".join(out_of_scope)
        else:
            rejection = {"reason":"ungrounded_paths","paths":missing}
            recovery_text = "Rejected cached local assist with ungrounded paths: " + ", ".join(missing)
        rejected_path.write_text(json.dumps(rejection, sort_keys=True) + "\n", encoding="utf-8")
        if journal is not None:
            journal.emit("resource.local_assist_recovery", task_id=task_id, status="RECOVERED", text=recovery_text, provider="fast-llm-pool")
        return None
    task_class = str((meaningful.get("task_memory") or {}).get("task_class") or "")
    prompt = (
        "You are MiniTZ's bounded fast-LLM execution assistant. Do not decide authority or completion. "
        "Use the compact task state below to reduce general Codex reasoning. Return a concise technical assist: "
        "(1) next smallest action, (2) likely failure cause if any, (3) exact files/tests/tools to inspect or run, "
        "(4) reusable verified pattern if supported. Mention only file/asset paths literally supported by the input; never invent a path, API, symbol, test, or command target. "
        "If the failures list is empty, section (2) MUST be exactly 'Likely failure cause if any: NONE' and section (1) must not imply retry/repair of a failure. "
        "If citing a verified_action content_ref, include its exact corresponding text verbatim on the same line; do not paraphrase or assign additional meaning to a hash. "
        "Do not manufacture failure state, stale-cache/race claims, or negative status from absent evidence. Do not repeat the whole input and do not propose task advancement.\n\n"
        + canonical[:12000]
    )
    argv = [
        "/usr/local/bin/biella", "resource", "fast-llm",
        "--max-tokens", "320", "--prompt", prompt,
    ]
    if journal is not None:
        journal.emit("resource.local_assist_started", task_id=task_id, status="RUNNING", text=digest[:20], provider="fast-llm-pool")
    helper_started = time.monotonic()
    try:
        proc = subprocess.run(argv, text=True, capture_output=True, timeout=_FAST_LLM_HELPER_BUDGET_SECONDS, check=False)
    except subprocess.TimeoutExpired as exc:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        partial = exc.output.decode("utf-8", errors="replace") if isinstance(exc.output, bytes) else str(exc.output or "")
        raw_path.write_text(partial, encoding="utf-8")
        _emit_helper_failure(journal, "resource.local_assist_failed", task_id=task_id,
            failure_type="HELPER_DEADLINE_EXCEEDED", budget_seconds=_FAST_LLM_HELPER_BUDGET_SECONDS, started=helper_started,
            text="Fast-LLM helper deadline exceeded", provider="fast-llm-pool", raw_result_path=raw_path)
        return None
    except OSError as exc:
        _emit_helper_failure(journal, "resource.local_assist_failed", task_id=task_id,
            failure_type="PROVIDER_UNAVAILABLE", budget_seconds=_FAST_LLM_HELPER_BUDGET_SECONDS, started=helper_started,
            text=str(exc), provider="fast-llm-pool")
        return None
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(proc.stdout or "", encoding="utf-8")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "local assist failed")[-1600:]
        _emit_helper_failure(journal, "resource.local_assist_failed", task_id=task_id,
            failure_type=_helper_process_failure_type(detail), budget_seconds=_FAST_LLM_HELPER_BUDGET_SECONDS, started=helper_started,
            text=detail, provider="fast-llm-pool", raw_result_path=raw_path, exit_code=proc.returncode)
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        _emit_helper_failure(journal, "resource.local_assist_failed", task_id=task_id,
            failure_type="INVALID_RESULT", budget_seconds=_FAST_LLM_HELPER_BUDGET_SECONDS, started=helper_started,
            text="Fast-LLM assist returned invalid JSON", provider="fast-llm-pool", raw_result_path=raw_path)
        return None
    assist_text = str(payload.get("text") or "")
    missing_paths = _assist_unresolved_paths(assist_text, project_root)
    out_of_scope_paths = _assist_clean_task_out_of_scope_paths(assist_text, meaningful, project_root)
    invented_failure = _assist_invented_failure_claim(assist_text, list(meaningful.get("failures") or []))
    verified_claim = _assist_ungrounded_verified_action_claim(assist_text, list(meaningful.get("verified_actions") or []))
    if missing_paths or out_of_scope_paths or invented_failure or verified_claim:
        rejected_path.parent.mkdir(parents=True, exist_ok=True)
        if verified_claim:
            rejection = {"reason":"ungrounded_verified_action_claim","claim":verified_claim}
            recovery_text = "Rejected local assist with ungrounded verified-action claim: " + verified_claim
        elif invented_failure:
            rejection = {"reason":"ungrounded_failure_claim","claim":invented_failure}
            recovery_text = "Rejected local assist with invented failure claim: " + invented_failure
        elif out_of_scope_paths:
            rejection = {"reason":"out_of_scope_paths","paths":out_of_scope_paths}
            recovery_text = "Rejected local assist with paths outside current clean-task input: " + ", ".join(out_of_scope_paths)
        else:
            rejection = {"reason":"ungrounded_paths","paths":missing_paths}
            recovery_text = "Rejected local assist with ungrounded paths: " + ", ".join(missing_paths)
        rejection["raw_result_path"] = str(raw_path)
        rejection["raw_sha256"] = hashlib.sha256((proc.stdout or "").encode("utf-8")).hexdigest()
        rejected_path.write_text(json.dumps(rejection, sort_keys=True) + "\n", encoding="utf-8")
        _emit_helper_failure(journal, "resource.local_assist_recovery", task_id=task_id,
            failure_type="VALIDATION_REJECTED", budget_seconds=_FAST_LLM_HELPER_BUDGET_SECONDS, started=helper_started,
            text=recovery_text, provider="ollama-qwen", raw_result_path=raw_path, detail=str(rejected_path), status="RECOVERED")
        return None
    result = {
        "schema": "biella.local_resource_assist/v1",
        "task_id": task_id,
        "projection_content_sha256": digest,
        "provider": payload.get("provider"),
        "model": payload.get("model"),
        "text": assist_text,
        "usage": payload.get("usage") or {},
        "latency_ms": payload.get("latency_ms"),
        "routing_evidence": payload.get("routing_evidence") or {},
        "raw_result_path": str(raw_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "authority": "NON_AUTHORITATIVE_RESOURCE_ASSIST",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    if journal is not None:
        journal.emit("resource.local_assist_completed", task_id=task_id, status="COMPLETE", text=str(path), provider=str(result.get("provider") or "fast-llm-pool"), model=str(result.get("model") or ""))
    return path



def _taskbooster_atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _taskbooster_prompt(packet: Mapping[str, Any]) -> str:
    return (
        "You are MiniTZ Spark TaskBooster, a non-authoritative read-only microtask assistant. "
        "Work only on the exact objective and allowed_reads in the packet. Do not inspect other paths, do not use web search, "
        "do not mutate files, do not advance/complete/reorder tasks, and do not invent symbols, failures, commands, paths, or evidence. "
        "A USEFUL finding requires exact current evidence_refs with path, SHA-256, line range, and exact quote. "
        "candidate_patch is text only and may mention only allowlisted paths. recommended_commands must be empty unless the packet explicitly allows the exact command. "
        "Return only the requested structured result.\n\nTASKBOOSTER_PACKET_JSON:\n"
        + json.dumps(dict(packet), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )


def _taskbooster_reject(base: Path, task_id: str, packet: Mapping[str, Any], reason: str,
                        raw_text: str, journal: production_events.ProductionEventJournal | None,
                        *, raw_result_path: Path | None = None, evidence_items: Sequence[str] = (),
                        failure_type: str = "VALIDATION_REJECTED", helper_started: float | None = None,
                        exit_code: int | None = None) -> Path:
    short = str(packet.get("booster_id") or "TB").replace(":", "_")
    rejected = Path(base) / f"{str(task_id).replace('/', '_')}-{short}.rejected.json"
    payload = taskbooster.failure_evidence(reason, raw_text)
    payload.update({
        "task_id": task_id, "booster_id": packet.get("booster_id"),
        "raw_result_path": str(raw_result_path) if raw_result_path else None,
        "evidence": list(evidence_items),
    })
    _taskbooster_atomic_json(rejected, payload)
    event_type = "resource.taskbooster_failed" if failure_type in {"HELPER_DEADLINE_EXCEEDED", "PROVIDER_UNAVAILABLE", "PROCESS_FAILED"} else "resource.taskbooster_rejected"
    _emit_helper_failure(
        journal, event_type, task_id=task_id, failure_type=failure_type,
        budget_seconds=_SPARK_HELPER_BUDGET_SECONDS, started=helper_started if helper_started is not None else time.monotonic(),
        text=reason, provider="openai", model="gpt-5.3-codex-spark", raw_result_path=raw_result_path,
        detail="; ".join(evidence_items), exit_code=exit_code,
    )
    return rejected


def _ensure_taskbooster_assist(repo_root: Path, project_root: Path, runtime_root: Path,
                               task: state.TaskRecord, strong_route: routing.Route,
                               catalog: Mapping[str, set[str]], local_assist_path: Path | None,
                               journal: production_events.ProductionEventJournal | None = None) -> Path | None:
    if routing.is_bounded_fallback(strong_route):
        return None
    levels = catalog.get("gpt-5.3-codex-spark", set())
    if "xhigh" not in levels or local_assist_path is None or not Path(local_assist_path).is_file():
        return None
    try:
        local_assist = json.loads(Path(local_assist_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if journal is not None:
            journal.emit("resource.taskbooster_rejected", task_id=task.id, status="ERROR", text="INVALID_LOCAL_ASSIST", detail=str(exc))
        return None
    working_root = _task_working_directory(repo_root, project_root, task.id)
    task_state_digest = _bounded_packet_id(repo_root, project_root, task)
    packet = taskbooster.compile_packet(
        task_id=task.id, task_state_digest=task_state_digest,
        objective=f"{task.id}: {task.title}. Produce one exact evidence-grounded technical micro-analysis for the authoritative strong turn.",
        acceptance=("Every USEFUL finding cites exact allowlisted current-source lines.",
                    "Do not mutate files, execute unapproved commands, or decide task completion/advancement."),
        scope_root=working_root, local_assist=local_assist,
    )
    if not packet.get("allowed_reads"):
        return None
    base = Path(runtime_root) / "memory" / "taskbooster"
    base.mkdir(parents=True, exist_ok=True)
    safe = str(task.id).replace("/", "_")
    short = str(packet["booster_id"]).replace(":", "_")
    accepted_path = base / f"{safe}-{short}.json"
    rejected_path = base / f"{safe}-{short}.rejected.json"
    raw_path = base / f"{safe}-{short}.raw.json"
    trace_path = base / f"{safe}-{short}.trace.json"
    schema_path = base / "taskbooster-result.schema.json"
    if rejected_path.exists():
        return None
    if accepted_path.exists():
        try:
            cached = json.loads(accepted_path.read_text(encoding="utf-8"))
            cached_result = cached.get("result") if isinstance(cached, Mapping) else None
            if isinstance(cached_result, Mapping):
                checked = taskbooster.validate_result(packet, cached_result, working_root,
                                                      current_task_state_digest=_bounded_packet_id(repo_root, project_root, task))
                if checked.accepted:
                    return accepted_path
        except (OSError, json.JSONDecodeError):
            pass
    schema_payload = taskbooster.booster_result_schema()
    expected_schema = json.dumps(schema_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    if not schema_path.exists() or schema_path.read_text(encoding="utf-8", errors="replace") != expected_schema:
        schema_path.write_text(expected_schema, encoding="utf-8")
    spark_route = routing.Route("gpt-5.3-codex-spark", "xhigh")
    command = routing.build_taskbooster_command(spark_route, schema_path, raw_path, working_root)
    prompt = _taskbooster_prompt(packet)
    if journal is not None:
        journal.emit("resource.taskbooster_started", task_id=task.id, status="RUNNING",
                     text=str(packet["booster_id"]), model=spark_route.model, reasoning=spark_route.reasoning)
    helper_started = time.monotonic()
    try:
        proc = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=_SPARK_HELPER_BUDGET_SECONDS, check=False)
    except subprocess.TimeoutExpired as exc:
        partial = exc.output.decode("utf-8", errors="replace") if isinstance(exc.output, bytes) else str(exc.output or "")
        raw = json.dumps({"partial_output": partial}, sort_keys=True)
        _taskbooster_reject(base, task.id, packet, "HELPER_DEADLINE_EXCEEDED", raw, journal,
                            failure_type="HELPER_DEADLINE_EXCEEDED", helper_started=helper_started)
        return None
    except OSError as exc:
        raw = json.dumps({"exception_type": type(exc).__name__}, sort_keys=True)
        _taskbooster_reject(base, task.id, packet, "PROVIDER_UNAVAILABLE", raw, journal,
                            failure_type="PROVIDER_UNAVAILABLE", helper_started=helper_started)
        return None
    trace = {"returncode": proc.returncode, "stdout": proc.stdout or "", "stderr": proc.stderr or ""}
    _taskbooster_atomic_json(trace_path, trace)
    if proc.returncode != 0:
        detail = proc.stderr or proc.stdout or "Spark helper process failed"
        failure_type = _helper_process_failure_type(detail)
        _taskbooster_reject(base, task.id, packet, failure_type, json.dumps(trace, sort_keys=True), journal,
                            raw_result_path=raw_path if raw_path.exists() else None, failure_type=failure_type,
                            helper_started=helper_started, exit_code=proc.returncode)
        return None
    try:
        raw_text = raw_path.read_text(encoding="utf-8")
        result = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as exc:
        raw_text = raw_path.read_text(encoding="utf-8", errors="replace") if raw_path.exists() else json.dumps(trace, sort_keys=True)
        _taskbooster_reject(base, task.id, packet, "INVALID_RESULT", raw_text, journal,
                            raw_result_path=raw_path if raw_path.exists() else None, evidence_items=(str(exc),),
                            failure_type="INVALID_RESULT", helper_started=helper_started)
        return None
    checked = taskbooster.validate_result(
        packet, result, working_root,
        current_task_state_digest=_bounded_packet_id(repo_root, project_root, task),
    )
    if not checked.accepted:
        failure_type = "STALE_INPUT" if checked.reason == "STALE_INPUT_DIGEST" else "VALIDATION_REJECTED"
        _taskbooster_reject(base, task.id, packet, checked.reason, raw_text, journal,
                            raw_result_path=raw_path, evidence_items=checked.evidence,
                            failure_type=failure_type, helper_started=helper_started)
        return None
    wrapper = {
        "schema": "minitz.taskbooster_assist/v1", "authority": "NONE",
        "task_id": task.id, "booster_id": packet["booster_id"],
        "provider": "openai", "model": spark_route.model,
        "task_state_digest": task_state_digest,
        "packet": packet, "result": result,
        "raw_result_path": str(raw_path), "trace_path": str(trace_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _taskbooster_atomic_json(accepted_path, wrapper)
    if journal is not None:
        journal.emit("resource.taskbooster_completed", task_id=task.id, status="COMPLETE",
                     text=str(accepted_path), model=spark_route.model, reasoning=spark_route.reasoning)
    return accepted_path


def _local_qwen_resident() -> bool:
    try:
        found = False
        for comm in Path("/proc").glob("[0-9]*/comm"):
            try:
                if comm.read_text(encoding="utf-8", errors="ignore").strip() == "ollama":
                    found = True; break
            except OSError:
                continue
        if not found:
            return False
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return any(
            item.get("name") == "qwen3-coder-next:biella" or item.get("model") == "qwen3-coder-next:biella"
            for item in payload.get("models", []) if isinstance(item, Mapping)
        )
    except Exception:
        return False

def _deterministic_projection_context(runtime_root: Path, task: state.TaskRecord, projection_path: Path,
                                      working_root: Path) -> Path | None:
    try:
        projection = json.loads(Path(projection_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(projection, Mapping):
        return None
    meaningful = _assist_projection_payload(projection)
    memory = meaningful.get("task_memory") if isinstance(meaningful.get("task_memory"), Mapping) else {}
    pieces = [str(memory.get(key) or "") for key in ("title", "summary", "next_action")]
    evidence_items = memory.get("evidence") if isinstance(memory.get("evidence"), list) else []
    pieces.extend(str(item) for item in evidence_items)
    text = "\n".join(piece for piece in pieces if piece.strip())
    if not taskbooster.extract_grounded_targets(text, working_root):
        return None
    payload = {
        "schema": "minitz.deterministic_context_assist/v1", "authority": "NON_AUTHORITATIVE_DETERMINISTIC_CONTEXT",
        "task_id": task.id, "text": text[:6000],
        "projection_sha256": hashlib.sha256(Path(projection_path).read_bytes()).hexdigest(),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    path = Path(runtime_root) / "memory" / "taskbooster" / f"{str(task.id).replace('/', '_')}-projection-{digest[:20]}.json"
    _taskbooster_atomic_json(path, payload)
    return path


def _prepare_optional_task_assists(repo_root: Path, project_root: Path, runtime_root: Path,
                                   task: state.TaskRecord, route: routing.Route,
                                   catalog: Mapping[str, set[str]], projection_path: Path | None,
                                   journal: production_events.ProductionEventJournal | None = None) -> tuple[Path | None, Path | None]:
    if routing.is_bounded_fallback(route) or projection_path is None or not Path(projection_path).is_file():
        return None, None
    if task.task_class == "simple":
        return None, None
    working_root = _task_working_directory(repo_root, project_root, task.id)
    qwen_resident = _local_qwen_resident()
    if task.task_class == "simple":
        deterministic_context = _deterministic_projection_context(runtime_root, task, Path(projection_path), working_root)
        decision = routing.classify_simple_operation(
            "simple", deterministic_command=None, grounded_context=deterministic_context is not None,
            local_qwen_resident=qwen_resident,
            spark_available="xhigh" in catalog.get("gpt-5.3-codex-spark", set()),
            read_only_microanalysis=deterministic_context is not None,
        )
        if decision.kind == "LOCAL_QWEN":
            local_assist = _ensure_local_resource_assist(runtime_root, task.id, projection_path, journal, project_root=working_root)
            if local_assist is None:
                local_assist = deterministic_context
        elif decision.kind == "SPARK":
            local_assist = deterministic_context
        else:
            return None, None
        if local_assist is None:
            return None, None
        boosted = _ensure_taskbooster_assist(repo_root, project_root, runtime_root, task, route, catalog, local_assist, journal)
        return local_assist, boosted
    local_assist = _ensure_local_resource_assist(runtime_root, task.id, projection_path, journal, project_root=working_root)
    if local_assist is None:
        return None, None
    boosted = _ensure_taskbooster_assist(repo_root, project_root, runtime_root, task, route, catalog, local_assist, journal)
    return local_assist, boosted



def _helper_allowed(task_id: str) -> bool:
    del task_id
    return False


def _drain_codex_events(path: Path, offset: int, journal: production_events.ProductionEventJournal | None, task_id: str | None, *, final: bool = False) -> tuple[int, str | None]:
    if not path.exists():
        return offset, None
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read()
    except OSError:
        return offset, None
    if not data:
        return offset, None
    chunks = data.split(b"\n")
    complete = chunks if final and chunks[-1] else chunks[:-1]
    consumed = 0
    session_id: str | None = None
    for raw in complete:
        consumed += len(raw) + 1
        if not raw.strip():
            continue
        try:
            item = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            if item.get("type") == "thread.started" and isinstance(item.get("thread_id"), str):
                session_id = str(item["thread_id"])
            if journal is not None and task_id:
                journal.emit_codex(item, task_id)
    if final and chunks[-1]:
        consumed -= 1
    return offset + consumed, session_id


def invoke_structured(prompt: str, route: routing.Route, schema_path: Path, output_path: Path,
                      stdout_path: Path, stderr_path: Path, runtime_path: Path,
                      telemetry: dict[str, Any], *, heartbeat_interval: float = 30.0,
                      on_heartbeat: Callable[[datetime], None] | None = None,
                      cwd: Path | None = None, resume_session_id: str | None = None,
                      session_task_id: str | None = None, allow_helper: bool = False,
                      persist_session_identity: bool = True,
                      event_journal: production_events.ProductionEventJournal | None = None) -> tuple[int, str]:
    if resume_session_id:
        cmd = routing.build_codex_resume_command(route, schema_path, output_path, resume_session_id, allow_helper=True) if allow_helper else routing.build_codex_resume_command(route, schema_path, output_path, resume_session_id)
    else:
        cmd = routing.build_codex_command(route, schema_path, output_path, cwd or Path("/root"), allow_helper=True) if allow_helper else routing.build_codex_command(route, schema_path, output_path, cwd or Path("/root"))
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True, stdout=stdout, stderr=stderr, env=os.environ.copy(), cwd=cwd, umask=0o022)
        telemetry["child_pid"] = proc.pid
        _beat(runtime_path, telemetry)
        assert proc.stdin is not None
        proc.stdin.write(prompt); proc.stdin.close()
        next_beat = time.monotonic()
        event_offset = 0
        while proc.poll() is None:
            event_offset, live_session = _drain_codex_events(stdout_path, event_offset, event_journal, session_task_id)
            if persist_session_identity and live_session and session_task_id and telemetry.get("task_session_id") != live_session:
                _record_task_session(telemetry, session_task_id, live_session)
                _beat(runtime_path, telemetry)
            now_mono = time.monotonic()
            if now_mono >= next_beat:
                observed = _beat(runtime_path, telemetry)
                if on_heartbeat:
                    on_heartbeat(observed)
                next_beat = now_mono + heartbeat_interval
            time.sleep(min(0.05, max(0.005, heartbeat_interval / 4)))
        rc = int(proc.returncode or 0)
        event_offset, final_session = _drain_codex_events(stdout_path, event_offset, event_journal, session_task_id, final=True)
        if persist_session_identity and final_session and session_task_id:
            _record_task_session(telemetry, session_task_id, final_session)
    telemetry["child_pid"] = None
    observed_session = resume_session_id or _extract_codex_session_id(stdout_path)
    if persist_session_identity and observed_session and session_task_id:
        _record_task_session(telemetry, session_task_id, observed_session)
    observed = _beat(runtime_path, telemetry)
    if on_heartbeat:
        on_heartbeat(observed)
    return rc, _tail(stderr_path) + "\n" + _tail(stdout_path)


def invoke_agr_structured(
    prompt: str,
    model: str,
    effort: str,
    schema_path: Path,
    output_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    runtime_path: Path,
    telemetry: dict[str, Any],
    *,
    heartbeat_interval: float = 30.0,
    on_heartbeat: Callable[[datetime], None] | None = None,
    cwd: Path | None = None,
    resume_session_id: str | None = None,
    session_task_id: str | None = None,
    read_only: bool = False,
    persist_session_identity: bool = True,
    event_journal: production_events.ProductionEventJournal | None = None,
) -> tuple[int, str]:
    cmd = main_coder.build_agr_stream_command(
        model, effort, schema_path, read_only=read_only, conversation_id=resume_session_id
    )
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, text=True, stdout=stdout, stderr=stderr,
            env=os.environ.copy(), cwd=cwd, umask=0o022,
        )
        telemetry["child_pid"] = proc.pid
        _beat(runtime_path, telemetry)
        assert proc.stdin is not None
        proc.stdin.write(main_coder.agr_user_event(prompt) + "\n")
        proc.stdin.flush()
        proc.stdin.close()
        next_beat = time.monotonic()
        while proc.poll() is None:
            now_mono = time.monotonic()
            if now_mono >= next_beat:
                observed = _beat(runtime_path, telemetry)
                if on_heartbeat:
                    on_heartbeat(observed)
                next_beat = now_mono + heartbeat_interval
            time.sleep(min(0.05, max(0.005, heartbeat_interval / 4)))
        rc = int(proc.returncode or 0)
    telemetry["child_pid"] = None
    stdout_text = _tail(stdout_path)
    stderr_text = _tail(stderr_path)
    detail = (stderr_text + "\n" + stdout_text).strip()
    result: dict[str, object] | None = None
    try:
        result = main_coder.parse_agr_stream_result(stdout_text.splitlines())
    except ValueError:
        result = None
    status_text = detail
    if result is not None and result.get("error"):
        status_text += "\n" + str(result.get("error"))
    observed_status = main_coder.classify_agr_observation(rc, status_text)
    if result is not None and str(result.get("status") or "").upper() == "SUCCESS" and rc == 0:
        observed_status = "ACTIVE"
    telemetry.setdefault("coder_statuses", {})["agr"] = observed_status
    telemetry.setdefault("coder_status_detail", {})["agr"] = str(result.get("error") if result else detail)[-1200:]
    if result is not None and isinstance(result.get("usage"), Mapping):
        telemetry.setdefault("last_coder_usage", {})["agr"] = dict(result["usage"])
    if result is not None and persist_session_identity and session_task_id:
        conversation_id = result.get("conversation_id")
        if isinstance(conversation_id, str) and conversation_id:
            _record_task_session(telemetry, session_task_id, conversation_id, coder_id="agr")
    if rc == 0 and result is not None and str(result.get("status") or "").upper() == "SUCCESS":
        structured = result.get("structured_output")
        if not isinstance(structured, Mapping):
            response = str(result.get("response") or "").strip()
            try:
                candidate = json.loads(response)
            except json.JSONDecodeError:
                candidate = None
            structured = candidate if isinstance(candidate, Mapping) else None
        if not isinstance(structured, Mapping):
            rc = 1
            detail = (detail + "\nAGR SUCCESS response did not contain structured output").strip()
            telemetry["coder_statuses"]["agr"] = "NEEDS_MODIFICATION"
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = output_path.with_suffix(output_path.suffix + ".tmp")
            tmp.write_text(json.dumps(dict(structured), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            os.replace(tmp, output_path)
    if event_journal is not None and session_task_id:
        event_journal.emit(
            "coder.agr.completed" if rc == 0 else "coder.agr.failed",
            task_id=session_task_id, status=telemetry["coder_statuses"]["agr"],
            text=str(result.get("error") if result else detail)[-1200:], model=model, reasoning=effort,
        )
    observed = _beat(runtime_path, telemetry)
    if on_heartbeat:
        on_heartbeat(observed)
    return rc, detail


def _attempt_paths(runtime_root: Path, telemetry: dict[str, Any], stem: str) -> tuple[Path, Path, Path]:
    telemetry["attempt"] = int(telemetry.get("attempt") or 0) + 1
    attempts = runtime_root / "attempts"; attempts.mkdir(parents=True, exist_ok=True)
    base = f"{telemetry['attempt']:04d}-{stem}"
    return attempts / f"{base}.result.json", attempts / f"{base}.stdout.log", attempts / f"{base}.stderr.log"


def _is_stale_resume_error(detail: str) -> bool:
    text = str(detail or "")
    return any(marker in text for marker in (
        "ActiveTurnOutputSchemaMismatch",
        "ActiveTurnInputMismatch",
        "session not found",
        "thread not found",
    ))


def _is_resume_protocol_incompatible(detail: str) -> bool:
    text = str(detail or "").lower()
    return "unknown input item type" in text and "compaction" in text


def _set_failure(telemetry: dict[str, Any], route: routing.Route, detail: str, task_id: str) -> None:
    observed = datetime.now(timezone.utc)
    limited = routing.is_limit_error(detail)
    local_compat = route.provider == "ollama" and routing.is_local_provider_compatibility_error(detail)
    catalog_refresh = routing.requires_catalog_refresh(detail)
    model_recovery = limited or local_compat or catalog_refresh
    result = {
        "task_id": task_id,
        "status": "MODEL_RECOVERY" if model_recovery else "RUNTIME_RECOVERY",
        "summary": detail[-2000:], "evidence": [],
        "model": route.model, "reasoning": route.reasoning,
    }
    if limited:
        retry_at = routing.limit_retry_at(detail, observed)
        cooldowns = telemetry.setdefault("cooldowns", {})
        if routing.is_account_usage_limit_error(detail):
            for model in routing.account_usage_cooldown_models(route.model):
                cooldowns[model] = retry_at.isoformat()
        else:
            cooldowns[route.model] = retry_at.isoformat()
        result["retry_at"] = retry_at.isoformat()
        telemetry["status"] = "RECOVERING_MODEL"
    elif local_compat:
        retry_at = observed + timedelta(seconds=60)
        telemetry.setdefault("cooldowns", {})[route.model] = retry_at.isoformat()
        result["retry_at"] = retry_at.isoformat()
        telemetry["status"] = "RECOVERING_MODEL"
    elif catalog_refresh:
        retry_at = observed + timedelta(seconds=60)
        telemetry.setdefault("cooldowns", {})[route.model] = retry_at.isoformat()
        result["retry_at"] = retry_at.isoformat()
        result["catalog_refresh_required"] = True
        telemetry["status"] = "RECOVERING_MODEL"
    else:
        # Runtime/session/tooling failure is not evidence that the model is unavailable.
        # Keep the preferred authority route eligible instead of silently falling back.
        telemetry["status"] = "RECOVERING_RUNTIME"
    telemetry["last_result"] = result


def service_active() -> bool:
    return subprocess.run(["systemctl", "is-active", "--quiet", UNIT_NAME], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def production_status(repo_root: Path, project_root: Path, runtime_path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    production = state.load_project_production(project_root)
    telemetry = load_runtime(runtime_path)
    now = now or datetime.now(timezone.utc)
    if not service_active():
        liveness = "STOPPED"
    else:
        heartbeat = None
        raw = telemetry.get("heartbeat_at")
        if isinstance(raw, str) and raw:
            try:
                heartbeat = datetime.fromisoformat(raw)
                if heartbeat.tzinfo is None: heartbeat = heartbeat.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if heartbeat is None or (now - heartbeat).total_seconds() > 90:
            liveness = "STALE"
        else:
            liveness = "ACTIVE"
    sections = []
    for section in production.sections:
        sections.append({"id": section.id, "status": section.status, "completed": sum(t.status in {"COMPLETE", "COMPLETE_ALREADY"} for t in section.tasks), "total": len(section.tasks)})
    commander_index = commander.read_json(Path(runtime_path).parent / "memory" / "commander-fabric" / "current.json")
    current_task_id = str(production.current_task or telemetry.get("task_id") or "")
    if commander_index.get("authority") != "NONE" or str(commander_index.get("task_id") or "") != current_task_id:
        commander_index = {"authority": "NONE", "task_id": current_task_id, "total_lanes": commander.COMMANDER_LANE_COUNT, "lanes": []}
    commander_summary = commander.public_summary(commander_index)
    return {
        "run_id": "biella-production", "status": liveness,
        "current_section": production.current_section, "current_task": production.current_task,
        "completed": state.completed_count(production), "total": sum(len(s.tasks) for s in production.sections),
        "active_coder": telemetry.get("active_coder"),
        "main_coders": telemetry.get("coder_statuses") or {},
        "main_coder_detail": telemetry.get("coder_status_detail") or {},
        "commanders": commander_summary,
        "active_model": telemetry.get("active_model"), "active_reasoning": telemetry.get("active_reasoning"),
        "cooldowns": telemetry.get("cooldowns") or {}, "heartbeat_at": telemetry.get("heartbeat_at"),
        "last_result": telemetry.get("last_result"), "source_alignment": telemetry.get("source_alignment"),
        "sections": sections,
    }


def _first_incomplete_section(production: state.ProductionState) -> state.SectionRecord | None:
    for section in production.sections:
        if section.status not in {"COMPLETE", "COMPLETE_ALREADY"}:
            return section
    return None


def _guard_source_alignment(
    repo_root: Path, runtime_path: Path, telemetry: dict[str, Any],
    journal: production_events.ProductionEventJournal, *, task_id: str | None = None,
) -> bool:
    try:
        identity = evidence.assert_remote_source_current(repo_root)
    except evidence.SourceTransportError as exc:
        head = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True).strip()
        tree = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD^{tree}"], text=True).strip()
        previous_alignment = dict(telemetry.get("source_alignment") or {})
        if previous_alignment.get("state") == "RECONCILIATION_REQUIRED":
            previous_alignment.update({"transport_state": "UNAVAILABLE", "transport_error": str(exc),
                                       "commit": head, "tree": tree})
            telemetry["source_alignment"] = previous_alignment
        else:
            telemetry["source_alignment"] = {"state": "REMOTE_UNAVAILABLE_LOCAL_CONTINUATION",
                                             "commit": head, "tree": tree, "detail": str(exc)}
        journal.emit("source.transport_deferred", task_id=task_id or telemetry.get("task_id"), status="RETRY_INDEPENDENT", text=str(exc))
        _beat(runtime_path, telemetry)
        return True
    except evidence.SourceAlignmentError as exc:
        detail = str(exc)
        telemetry["source_alignment"] = {"state": "RECONCILIATION_REQUIRED", "detail": detail}
        journal.emit("source.reconciliation_required", task_id=task_id or telemetry.get("task_id"),
                     status="REPAIR_INLINE", text=detail)
        _beat(runtime_path, telemetry)
        return True
    telemetry["source_alignment"] = identity
    return True


def _persist_until_success(repo_root: Path, task_id: str, runtime_path: Path, telemetry: dict[str, Any], *, retry_seconds: float = 5.0, event_journal: production_events.ProductionEventJournal | None = None) -> dict[str, str]:
    del retry_seconds
    previous = telemetry.get("last_result") if isinstance(telemetry.get("last_result"), dict) else {}
    identity = evidence.persist_local_continuity(repo_root, task_id)
    publication.request_publication(repo_root, task_id, identity)
    telemetry["status"] = "RUNNING"
    telemetry["last_result"] = {
        "task_id": task_id, "status": "LOCAL_PERSISTED_PUBLICATION_PENDING",
        "summary": "Canonical local continuity committed; remote publication is independently retryable.",
        "evidence": list(previous.get("evidence", [])), "continuity": identity,
    }
    if event_journal:
        event_journal.emit("persistence.local_completed", task_id=task_id, status="LOCAL_PERSISTED",
                           commit=identity["commit"], tree=identity["tree"], publication="PENDING")
    _beat(runtime_path, telemetry)
    return identity


def _customer_pause_requested(runtime_root: Path) -> bool:
    return (Path(runtime_root) / "customer-pause-request.json").is_file()


def _acknowledge_customer_pause(repo_root: Path, project_root: Path, runtime_root: Path, runtime_path: Path, telemetry: dict[str, Any], journal: production_events.ProductionEventJournal) -> None:
    production = state.load_project_production(project_root)
    current = state.next_task(production)
    task_id = current.id if current is not None else None
    telemetry.update({
        "status": "PAUSED_FOR_CUSTOMER", "task_id": task_id, "child_pid": None,
        "active_model": None, "active_reasoning": None,
    })
    head = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD^{tree}"], text=True).strip()
    ack = {
        "schema": "biella.customer_pause_ack/v1", "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id, "attempt": int(telemetry.get("attempt") or 0), "child_pid": None,
        "task_session_id": telemetry.get("task_session_id"), "repo_head": head, "repo_tree": tree,
    }
    path = Path(runtime_root) / "customer-pause-ack.json"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(ack, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    journal.emit("production.customer_pause", task_id=task_id, status="PAUSED", text="Safe customer-resource checkpoint acknowledged")
    _beat(runtime_path, telemetry)


_MODEL_CATALOG_DISCOVERY_DEADLINE_SECONDS = 1.0


def _discover_runtime_catalog(runtime_root: Path) -> dict[str, set[str]]:
    return routing.discover_catalog(
        cache_path=Path(runtime_root) / "model-catalog-cache.json",
        timeout_seconds=_MODEL_CATALOG_DISCOVERY_DEADLINE_SECONDS,
    )


def _refresh_catalog_after_route_failure(
    runtime_root: Path,
    telemetry: dict[str, Any],
    detail: str,
) -> dict[str, set[str]] | None:
    """Refresh only for an explicit model/catalog invalidation signal."""
    if not routing.requires_catalog_refresh(detail):
        return None
    try:
        catalog = _discover_runtime_catalog(runtime_root)
    except Exception as exc:  # pragma: no cover - discovery implementations vary by host
        result = telemetry.setdefault("last_result", {})
        if isinstance(result, dict):
            result["catalog_refresh"] = {
                "status": "FAILED",
                "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            }
        return None
    result = telemetry.setdefault("last_result", {})
    if isinstance(result, dict):
        result["catalog_refresh"] = {
            "status": "REFRESHED",
            "models": sorted(catalog),
        }
    return catalog


def run_production(repo_root: Path, project_root: Path, runtime_root: Path, *, heartbeat_interval: float = 30.0) -> int:
    repo_root = Path(repo_root); project_root = Path(project_root); runtime_root = Path(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_path = runtime_root / "runtime.json"
    schema_path = runtime_root / "result-schema.json"
    section_schema_path = runtime_root / "section-plan-schema.json"
    schema_path.write_text(json.dumps(evidence.result_schema(), sort_keys=True) + "\n", encoding="utf-8")
    section_schema_path.write_text(json.dumps(packets.section_plan_schema(), sort_keys=True) + "\n", encoding="utf-8")
    journal = production_events.ProductionEventJournal(runtime_root / "events.jsonl", failure_path=runtime_root / "failures.jsonl")
    lock = ProductionLock(runtime_root / "run.lock"); lock.acquire()
    try:
        publication.start_worker(repo_root, failure_path=runtime_root / "failures.jsonl")
        telemetry = load_runtime(runtime_path)
        reconciled_cooldowns = routing.reconcile_legacy_account_cooldowns(telemetry.get("cooldowns", {}))
        if reconciled_cooldowns != dict(telemetry.get("cooldowns", {}) or {}):
            telemetry["cooldowns"] = reconciled_cooldowns
        telemetry.update({"status": "RUNNING", "project": "minitz", "pid": os.getpid(), "child_pid": None})
        journal.emit("production.started", task_id=telemetry.get("task_id"), status="RUNNING", text="Biella production runner active")
        _beat(runtime_path, telemetry)
        catalog: Mapping[str, set[str]] | None = None
        agr_models: set[str] = main_coder.discover_agr_models(timeout_seconds=2.0)
        peer_inflight: dict[str, MainCoderPeerHandle] = {}
        commander_inflight: dict[str, CommanderHandle] = {}
        while True:
            _collect_main_coder_peer_assists(peer_inflight, telemetry, journal)
            _collect_commander_assists_nonblocking(runtime_root, commander_inflight, journal)
            if _customer_pause_requested(runtime_root):
                _acknowledge_customer_pause(repo_root, project_root, runtime_root, runtime_path, telemetry, journal)
                return 0
            if not _guard_source_alignment(repo_root, runtime_path, telemetry, journal):
                return SOURCE_REFRESH_EXIT
            if catalog is None:
                catalog = _discover_runtime_catalog(runtime_root)
            production = state.sync_project_metadata(project_root)
            telemetry["priority_policy"] = production.priority_policy
            task = state.resolve_current_task(repo_root, project_root)
            if task is None:
                production = state.load_project_production(project_root)
                section = _first_incomplete_section(production)
                if section is None:
                    if os.environ.get("BIELLA_CONTINUOUS_IDLE", "0") != "1":
                        telemetry.update({"status": "COMPLETE", "task_id": None, "child_pid": None, "active_model": None, "active_reasoning": None})
                        journal.emit("production.completed", status="COMPLETE", text="All current production tasks complete")
                        _beat(runtime_path, telemetry); return 0
                    projects_dir = repo_root / "projects"
                    projects = sorted(p.name for p in projects_dir.iterdir() if p.is_dir()) if projects_dir.exists() else []
                    registry_path = repo_root / "ops/workstation/provider-registry.json"
                    capabilities = []
                    try:
                        registry = json.loads(registry_path.read_text(encoding="utf-8"))
                        capabilities = sorted((registry.get("routes") or {}).keys())
                    except (OSError, json.JSONDecodeError):
                        pass
                    discovery = {
                        "schema": "biella.opportunity_discovery/v1",
                        "status": "REQUEST_NEW_TASK",
                        "projects": projects,
                        "registered_capabilities": capabilities,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "authority": "READ_ONLY_DISCOVERY_NO_TASK_INVENTION",
                    }
                    discovery_path = runtime_root / "opportunity-discovery.json"
                    discovery_path.write_text(json.dumps(discovery, sort_keys=True) + "\n", encoding="utf-8")
                    prior = telemetry.get("status")
                    telemetry.update({"status": "WAITING_FOR_TASK", "task_id": None, "child_pid": None, "active_model": None, "active_reasoning": None, "last_result": discovery})
                    if prior != "WAITING_FOR_TASK":
                        journal.emit("production.awaiting_task", status="WAITING_FOR_TASK", text="Canonical task list exhausted; owner task requested and current projects/capabilities inventoried read-only.")
                    _beat(runtime_path, telemetry); time.sleep(5.0); catalog = _discover_runtime_catalog(runtime_root); continue
                if section.id == "demo01" and section.tasks and all(t.status in {"COMPLETE", "COMPLETE_ALREADY"} for t in section.tasks):
                    state.mark_section_status(project_root, section.id, "COMPLETE")
                    _persist_until_success(repo_root, f"SECTION-{section.id}", runtime_path, telemetry, event_journal=journal)
                    continue
                now = datetime.now(timezone.utc)
                planner_coder, route = _select_main_coder_class_route(
                    "deep_memory", catalog, agr_models, telemetry, now
                )
                if route is None or planner_coder is None:
                    telemetry.update({"status": "RECOVERING_MODEL", "task_id": f"PLAN:{section.id}", "active_model": None, "active_reasoning": None})
                    _beat(runtime_path, telemetry)
                    time.sleep(min(5.0, max(0.5, routing.earliest_cooldown_delay(telemetry.get("cooldowns", {}), now))))
                    catalog = _discover_runtime_catalog(runtime_root)
                    agr_models = main_coder.discover_agr_models(timeout_seconds=2.0)
                    continue
                telemetry.update({
                    "status": "RUNNING", "task_id": f"PLAN:{section.id}", "active_coder": planner_coder,
                    "active_model": route.model, "active_reasoning": route.reasoning,
                })
                _beat(runtime_path, telemetry)
                output, stdout, stderr = _attempt_paths(runtime_root, telemetry, f"PLAN-{section.id}-{route.model}")
                section_prompt = packets.compile_section_packet(production, section, audit=bool(section.tasks))
                policies = main_coder.shared_policy_paths(repo_root, project_root)
                section_prompt = (
                    f"MAIN_CODER_BACKEND: {planner_coder}\n"
                    + "".join(f"SHARED_POLICY: {policy}\n" for policy in policies)
                    + "Same MiniTZ authority, memory, cache, validation and no-replay rules apply regardless of backend.\n"
                    + section_prompt
                )
                planner_session = _resume_session_for(telemetry, f"PLAN:{section.id}", coder_id=planner_coder)
                if planner_coder == "agr":
                    rc, error_text = invoke_agr_structured(
                        section_prompt, route.model, route.reasoning, section_schema_path, output, stdout, stderr, runtime_path, telemetry,
                        heartbeat_interval=heartbeat_interval, cwd=project_root, resume_session_id=planner_session,
                        session_task_id=f"PLAN:{section.id}", read_only=False, persist_session_identity=True, event_journal=journal,
                    )
                else:
                    rc, error_text = invoke_structured(
                        section_prompt, route, section_schema_path, output, stdout, stderr, runtime_path, telemetry,
                        heartbeat_interval=heartbeat_interval, cwd=project_root, resume_session_id=planner_session,
                        session_task_id=f"PLAN:{section.id}", event_journal=journal,
                    )
                    if rc == 0:
                        telemetry.setdefault("coder_statuses", {})["codex"] = "ACTIVE"
                if rc != 0:
                    if planner_coder == "agr":
                        telemetry.setdefault("coder_statuses", {})["agr"] = main_coder.classify_agr_observation(rc, error_text)
                        telemetry["last_result"] = {"task_id": f"PLAN:{section.id}", "status": "CODER_FAILOVER", "summary": error_text[-2000:], "evidence": [], "coder": "agr", "model": route.model, "reasoning": route.reasoning}
                    else:
                        _set_failure(telemetry, route, error_text, f"PLAN:{section.id}")
                        refreshed_catalog = _refresh_catalog_after_route_failure(runtime_root, telemetry, error_text)
                        if refreshed_catalog is not None:
                            catalog = refreshed_catalog
                    _beat(runtime_path, telemetry); continue
                if not _guard_source_alignment(repo_root, runtime_path, telemetry, journal, task_id=f"PLAN:{section.id}"):
                    return SOURCE_REFRESH_EXIT
                try:
                    plan = json.loads(output.read_text(encoding="utf-8"))
                    state.apply_section_plan(repo_root, project_root, section.id, plan)
                    _persist_until_success(repo_root, f"PLAN-{section.id}", runtime_path, telemetry, event_journal=journal)
                except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
                    _set_failure(telemetry, route, f"invalid section plan: {exc}", f"PLAN:{section.id}"); _beat(runtime_path, telemetry); continue
                telemetry["last_result"] = {"task_id": None, "status": "SECTION_REFRESH", "summary": str(plan.get("summary", "")), "evidence": list(plan.get("evidence", [])), "coder": planner_coder, "model": route.model, "reasoning": route.reasoning}
                _beat(runtime_path, telemetry); continue
            if _defer_resource_blocker(repo_root, project_root, production, task, telemetry, journal, runtime_path):
                continue
            now = datetime.now(timezone.utc)
            coder_id, route, bounded_packet_id, peer_coder = _select_main_task_route(
                task, catalog, agr_models, telemetry, now, repo_root, project_root
            )
            if route is None or coder_id is None:
                telemetry.update({"status": "RECOVERING_MODEL", "task_id": task.id, "active_model": None, "active_reasoning": None})
                _beat(runtime_path, telemetry)
                time.sleep(2.0)
                catalog = _discover_runtime_catalog(runtime_root)
                agr_models = main_coder.discover_agr_models(timeout_seconds=2.0)
                continue
            bounded_fallback = coder_id == "codex" and routing.is_bounded_fallback(route)
            if task.task_class == "simple" and bounded_packet_id and bounded_fallback:
                _record_simple_helper_attempt(telemetry, task.id, bounded_packet_id, route)
            telemetry.update({
                "status": "RUNNING", "task_id": task.id, "active_coder": coder_id,
                "active_model": route.model, "active_reasoning": route.reasoning,
            })
            if evidence.continuity_changes(repo_root):
                unexpected = evidence.unexpected_dirty_paths(repo_root)
                if unexpected:
                    telemetry["last_result"] = {
                        "task_id": task.id, "status": "RECONCILE_DEFERRED",
                        "summary": "Continuity reconciliation deferred until current task output is committed.",
                        "evidence": sorted(unexpected),
                    }
                else:
                    _persist_until_success(repo_root, f"RECONCILE-{task.id}", runtime_path, telemetry, event_journal=journal)
            _beat(runtime_path, telemetry)
            output, stdout, stderr = _attempt_paths(runtime_root, telemetry, f"{task.id}-{route.model}")
            capsule_path = _write_task_capsule(repo_root, project_root, runtime_root, task, telemetry)
            capsule_data = json.loads(capsule_path.read_text(encoding="utf-8"))
            previous_owned = dict(capsule_data.get("owned_files") or {})
            try:
                ownership_baseline = evidence.workspace_snapshot(repo_root)
            except (OSError, subprocess.SubprocessError) as exc:
                ownership_baseline = dict(capsule_data.get("workspace_baseline") or {})
                journal.emit("memory.observation_failed", task_id=task.id, status="ERROR", text=str(exc))
            current_owned = dict(previous_owned)
            def observe_activity(_at=None):
                nonlocal current_owned
                try:
                    current_owned = _checkpoint_task_activity(repo_root, project_root, runtime_root,
                        task, telemetry, ownership_baseline, previous_owned)
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    journal.emit("memory.observation_failed", task_id=task.id, status="ERROR", text=str(exc))
            observe_activity()
            projection_path = _refresh_memory_projection(repo_root, project_root, runtime_root, task.id, journal)
            task_state_digest = _bounded_packet_id(repo_root, project_root, task)
            commander_index_path = _prepare_commander_assists_nonblocking(
                repo_root, project_root, runtime_root, task, task_state_digest,
                capsule_path, projection_path, commander_inflight, journal,
            )
            peer_assist_path = _latest_main_coder_peer_assist(runtime_root, task.id, task_state_digest)
            dispatch_peer = peer_coder
            peer_route = _select_main_coder_peer_route(
                dispatch_peer, task, catalog, agr_models, telemetry, now, repo_root, project_root
            )
            # A configured AGR backend that is present but not yet usable gets one
            # useful read-only recovery attempt per exact task-state digest. It runs
            # beside Codex and can never stall the canonical writer. Rejection is
            # content-addressed so an unchanged broken state is not hammered.
            if (
                peer_route is None and dispatch_peer is None and coder_id == "codex"
                and telemetry.get("coder_statuses", {}).get("agr") == "NEEDS_MODIFICATION"
                and agr_models
            ):
                try:
                    recovery_model = main_coder.select_agr_model(task.task_class, agr_models)
                except RuntimeError:
                    recovery_model = None
                if recovery_model:
                    dispatch_peer = "agr"
                    peer_route = routing.Route(recovery_model, main_coder.agr_effort(task.task_class), "antigravity")
            if dispatch_peer and peer_route is not None:
                try:
                    launched = _launch_main_coder_peer_assist(
                        repo_root, project_root, runtime_root, task, task_state_digest,
                        primary_coder=coder_id, peer_coder=dispatch_peer, peer_route=peer_route,
                        capsule_path=capsule_path, projection_path=projection_path, inflight=peer_inflight,
                    )
                    if launched:
                        journal.emit(
                            "coder.peer_assist_started", task_id=task.id, status=telemetry.get("coder_statuses", {}).get(dispatch_peer),
                            text="Independent read-only main-coder peer assist launched",
                            coder=dispatch_peer, primary_coder=coder_id, model=peer_route.model,
                        )
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    telemetry.setdefault("coder_status_detail", {})[dispatch_peer] = str(exc)[-1200:]
                    journal.emit(
                        "coder.peer_assist_failed", task_id=task.id, status=telemetry.get("coder_statuses", {}).get(dispatch_peer),
                        text=str(exc)[-1200:], coder=dispatch_peer, model=peer_route.model,
                    )
            local_assist_path, taskbooster_path = _prepare_optional_task_assists(
                repo_root, project_root, runtime_root, task, route, catalog, projection_path, journal
            )
            prompt = _task_prompt(
                repo_root, production, task, telemetry, capsule_path, projection_path,
                local_assist_path, taskbooster_path, route=route, peer_assist_path=peer_assist_path,
                commander_index_path=commander_index_path, coder_id=coder_id
            )
            resume_session_id = _resume_session_for_route(telemetry, task.id, route, coder_id=coder_id)
            event_type = "task.bounded_fallback_started" if bounded_fallback else ("task.continued" if _task_has_shared_continuity(telemetry, task.id, capsule_path) else "task.started")
            journal.emit(
                event_type, task_id=task.id, status="RUNNING", text=task.title,
                model=route.model, reasoning=route.reasoning, coder=coder_id,
                peer_coder=peer_coder, bounded_packet_id=bounded_packet_id,
            )
            if coder_id == "agr":
                rc, error_text = invoke_agr_structured(
                    prompt, route.model, route.reasoning, schema_path, output, stdout, stderr, runtime_path, telemetry,
                    heartbeat_interval=heartbeat_interval, on_heartbeat=observe_activity, cwd=_task_working_directory(repo_root, project_root, task.id),
                    resume_session_id=resume_session_id, session_task_id=task.id, read_only=False,
                    persist_session_identity=True, event_journal=journal,
                )
            else:
                rc, error_text = invoke_structured(
                    prompt, route, schema_path, output, stdout, stderr, runtime_path, telemetry,
                    heartbeat_interval=heartbeat_interval, on_heartbeat=observe_activity, cwd=_task_working_directory(repo_root, project_root, task.id),
                    resume_session_id=resume_session_id, session_task_id=task.id,
                    allow_helper=False if bounded_fallback else _helper_allowed(task.id),
                    persist_session_identity=not bounded_fallback,
                    event_journal=journal,
                )
                if rc == 0:
                    telemetry.setdefault("coder_statuses", {})["codex"] = "ACTIVE"
            if rc != 0:
                if coder_id == "agr":
                    telemetry.setdefault("coder_statuses", {})["agr"] = main_coder.classify_agr_observation(rc, error_text)
                    telemetry["last_result"] = {
                        "task_id": task.id, "status": "CODER_FAILOVER",
                        "summary": error_text[-2000:], "evidence": [],
                        "coder": "agr", "model": route.model, "reasoning": route.reasoning,
                    }
                    journal.emit(
                        "task.coder_failover", task_id=task.id, status=telemetry["coder_statuses"]["agr"],
                        text=error_text[-1200:], coder="agr", model=route.model, reasoning=route.reasoning,
                    )
                    _write_task_capsule(repo_root, project_root, runtime_root, task, telemetry)
                    _beat(runtime_path, telemetry)
                    continue
                stale_resume = resume_session_id and _is_stale_resume_error(error_text)
                incompatible_resume = resume_session_id and _is_resume_protocol_incompatible(error_text)
                if stale_resume or incompatible_resume:
                    stale_session_id = resume_session_id
                    _drop_coder_task_session(telemetry, task.id, "codex")
                    _clear_task_session(telemetry)
                    telemetry["status"] = "RECOVERING_SESSION"
                    # Rotate only the executor-session boundary. The canonical Task,
                    # worktree, task-memory capsule, raw evidence, and failure history
                    # remain untouched and drive the next fresh Codex session.
                    telemetry["last_result"] = {
                        "task_id": f"SESSION:{task.id}", "status": "SESSION_RECOVERY",
                        "summary": error_text[-1200:], "evidence": [],
                        "model": route.model, "reasoning": route.reasoning,
                    }
                    recovery_text = (
                        "Provider-incompatible Codex session rotated; task identity, worktree, task memory, and evidence preserved."
                        if incompatible_resume else
                        "Stale interrupted Codex session rotated; task bytes and compact memory preserved."
                    )
                    journal.emit(
                        "task.session_recovery", task_id=task.id, status="RECOVERED",
                        text=recovery_text, stale_session_id=stale_session_id,
                        model=route.model, reasoning=route.reasoning,
                    )
                    _beat(runtime_path, telemetry)
                    continue
                _set_failure(telemetry, route, error_text, task.id)
                refreshed_catalog = _refresh_catalog_after_route_failure(runtime_root, telemetry, error_text)
                if refreshed_catalog is not None:
                    catalog = refreshed_catalog
                journal.emit("task.runtime_recovery", task_id=task.id, status=telemetry.get("status"), text=error_text[-1200:])
                _write_task_capsule(repo_root, project_root, runtime_root, task, telemetry)
                _beat(runtime_path, telemetry); continue
            if not _guard_source_alignment(repo_root, runtime_path, telemetry, journal, task_id=task.id):
                return SOURCE_REFRESH_EXIT
            try:
                result = evidence.parse_result(output, task.id)
            except ValueError as exc:
                if coder_id == "agr":
                    telemetry.setdefault("coder_statuses", {})["agr"] = "NEEDS_MODIFICATION"
                    telemetry.setdefault("coder_status_detail", {})["agr"] = str(exc)[-1200:]
                    telemetry["last_result"] = {"task_id": task.id, "status": "CODER_FAILOVER", "summary": str(exc), "evidence": [], "coder": "agr", "model": route.model, "reasoning": route.reasoning}
                else:
                    _set_failure(telemetry, route, str(exc), task.id)
                _beat(runtime_path, telemetry); continue
            result = _normalize_result_for_route(result, route)
            if result.status in {"COMPLETE", "COMPLETE_ALREADY"} and (telemetry.get("source_alignment") or {}).get("state") == "RECONCILIATION_REQUIRED":
                result = evidence.TaskResult(result.task_id, "CONTINUE",
                    "Preserve passed task evidence; reconcile only the observed source revision difference before closure: " + str(telemetry["source_alignment"].get("detail", "")), result.evidence,
                    result.task_revision, result.task_digest, result.scope_ref,
                    result.family_revision, result.authority_ref, result.accepted_criteria)
            observe_activity()
            result = evidence.enforce_clean_completion_boundary(repo_root, result, owned_files=current_owned)
            _emit_validation_evidence(repo_root, project_root, result, journal)
            telemetry["last_result"] = {
                "task_id": result.task_id, "status": result.status, "summary": result.summary,
                "evidence": list(result.evidence), "coder": coder_id, "model": route.model, "reasoning": route.reasoning,
            }
            _write_task_capsule(repo_root, project_root, runtime_root, task, telemetry)
            _refresh_memory_projection(repo_root, project_root, runtime_root, task.id, journal)
            try:
                evidence.apply_result(repo_root, project_root, result, route)
            except Exception as exc:
                telemetry["status"] = "RECOVERING_INTERNAL"
                telemetry["last_result"] = {"task_id": task.id, "status": "RECOVERING_INTERNAL", "summary": str(exc), "evidence": list(result.evidence), "model": route.model, "reasoning": route.reasoning}
                _beat(runtime_path, telemetry); time.sleep(1.0); continue
            if result.status in {"COMPLETE", "COMPLETE_ALREADY"}:
                _clear_task_session(telemetry)
                _refresh_memory_projection(repo_root, project_root, runtime_root, result.task_id, journal)
                _persist_until_success(repo_root, result.task_id, runtime_path, telemetry, event_journal=journal)
            journal.emit("task.completed" if result.status in {"COMPLETE", "COMPLETE_ALREADY"} else "task.continue", task_id=result.task_id, status=result.status, text=result.summary)
            _beat(runtime_path, telemetry)
            continue
    except evidence.SourceAlignmentError:
        return SOURCE_REFRESH_EXIT
    finally:
        if "peer_inflight" in locals():
            _collect_main_coder_peer_assists(peer_inflight, telemetry if "telemetry" in locals() else initial_runtime(), journal if "journal" in locals() else None)
            _terminate_main_coder_peers(peer_inflight)
        if "commander_inflight" in locals():
            _collect_commander_assists_nonblocking(runtime_root, commander_inflight, journal if "journal" in locals() else None)
            _terminate_commander_assists(runtime_root, commander_inflight)
        publication.stop_worker(repo_root)
        lock.release()


def default_repo_root() -> Path:
    return Path(os.environ.get("BIELLA_REPO_ROOT", "/root/biella/repos/biella-engine"))


def default_project_root(repo_root: Path | None = None) -> Path:
    repo = repo_root or default_repo_root()
    return Path(os.environ.get("BIELLA_PROJECT_ROOT", str(repo / "projects/biella-games")))


def default_runtime_root() -> Path:
    return Path(os.environ.get("BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT", "/mnt/biella-extra/biella-runtime/codex-production"))


def start_production(repo_root: Path, project_root: Path, runtime_root: Path) -> int:
    if service_active():
        print(json.dumps({"unit": UNIT_NAME, "status": "ALREADY_RUNNING"}, sort_keys=True)); return 0
    state.resolve_current_task(repo_root, project_root)
    proc = subprocess.run(["systemctl", "enable", "--now", f"{UNIT_NAME}.service"], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr, end=""); return proc.returncode
    print(json.dumps({"unit": UNIT_NAME, "status": "STARTED"}, sort_keys=True)); return 0


def accept_current_task(repo_root: Path, project_root: Path, runtime_root: Path, task_id: str, owner_evidence: Sequence[str]) -> dict[str, Any]:
    repo_root = Path(repo_root); project_root = Path(project_root); runtime_root = Path(runtime_root)
    evidence_items = tuple(str(item).strip() for item in owner_evidence if str(item).strip())
    if not evidence_items:
        raise ValueError("owner acceptance requires evidence")
    production = state.load_project_production(project_root)
    current = state.next_task(production)
    canonical = state.task_ids.canonical_task_id(task_id)
    if current is None or current.id != canonical:
        raise ValueError(f"owner acceptance task mismatch: current={current.id if current else 'NONE'} requested={canonical}")
    dirty = _project_dirty_paths(repo_root, project_root)
    if dirty:
        raise RuntimeError("owner acceptance requires committed or deliberately discarded current-task work: " + ", ".join(dirty))
    state.mark_task_complete(repo_root, project_root, canonical, "COMPLETE", evidence_items)
    updated = state.load_project_production(project_root)
    successor = state.next_task(updated)
    runtime_path = runtime_root / "runtime.json"
    telemetry = load_runtime(runtime_path)
    _clear_task_session(telemetry)
    telemetry.update({
        "status": "READY_TO_START" if successor else "COMPLETE",
        "task_id": successor.id if successor else None,
        "pid": None, "child_pid": None, "active_model": None, "active_reasoning": None,
        "last_result": {
            "task_id": canonical, "status": "COMPLETE", "summary": "Owner-accepted task completion applied immediately.",
            "evidence": list(evidence_items),
        },
    })
    _beat(runtime_path, telemetry)
    identity = evidence.persist_local_continuity(repo_root, canonical)
    publication.request_publication(repo_root, canonical, identity)
    return {"accepted_task": canonical, "next_task": successor.id if successor else None, "continuity": identity}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biella-codex production")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sync", "run", "start", "status"):
        sub.add_parser(name)
    accept = sub.add_parser("accept")
    accept.add_argument("--task", required=True)
    accept.add_argument("--evidence", action="append", required=True)
    accept.add_argument("--no-resume", action="store_true")
    return parser


def main(argv=None) -> int:
    os.umask(0o077)
    args = _parser().parse_args(argv)
    repo_root = default_repo_root(); project_root = default_project_root(repo_root); runtime_root = default_runtime_root()
    if args.command == "run":
        return run_production(repo_root, project_root, runtime_root)
    if args.command == "start":
        return start_production(repo_root, project_root, runtime_root)
    if args.command == "status":
        print(json.dumps(production_status(repo_root, project_root, runtime_root / "runtime.json"), sort_keys=True)); return 0
    if args.command == "sync":
        state.resolve_current_task(repo_root, project_root)
        print(json.dumps(production_status(repo_root, project_root, runtime_root / "runtime.json"), sort_keys=True)); return 0
    if args.command == "accept":
        if service_active():
            stopped = subprocess.run(["systemctl", "stop", f"{UNIT_NAME}.service"], text=True, capture_output=True, check=False)
            if stopped.returncode != 0:
                print(stopped.stderr or stopped.stdout, file=sys.stderr, end="")
                return stopped.returncode
        result = accept_current_task(repo_root, project_root, runtime_root, args.task, args.evidence)
        if result.get("next_task") and not args.no_resume:
            rc = start_production(repo_root, project_root, runtime_root)
            if rc != 0:
                return rc
        print(json.dumps(result, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
