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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import biella_codex_routing as routing
import biella_execution_style as execution_style
import biella_memory_compactor as memory_compactor
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
    "task_sessions", "source_alignment",
}


class AlreadyRunning(RuntimeError):
    pass


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
        "source_alignment": None,
    }


def save_runtime(path: Path, runtime: Mapping[str, Any]) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: runtime.get(key) for key in _RUNTIME_KEYS}
    payload["cooldowns"] = dict(payload.get("cooldowns") or {})
    payload["task_sessions"] = dict(payload.get("task_sessions") or {})
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
    current_task = result.get("session_task_id"); current_session = result.get("task_session_id")
    if isinstance(current_task, str) and current_task and isinstance(current_session, str) and current_session:
        result["task_sessions"].setdefault(current_task, current_session)
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


def _resume_session_for(telemetry: Mapping[str, Any], task_id: str) -> str | None:
    if telemetry.get("session_task_id") == task_id:
        raw = telemetry.get("task_session_id")
        if isinstance(raw, str) and raw:
            return str(raw)
    sessions = telemetry.get("task_sessions")
    if isinstance(sessions, Mapping):
        raw = sessions.get(task_id)
        if isinstance(raw, str) and raw:
            return str(raw)
    return None


def _record_task_session(telemetry: dict[str, Any], task_id: str, session_id: str) -> None:
    sessions = dict(telemetry.get("task_sessions") or {})
    sessions[task_id] = session_id
    telemetry["task_sessions"] = sessions
    telemetry["task_session_id"] = session_id
    telemetry["session_task_id"] = task_id


def _resume_session_for_route(telemetry: Mapping[str, Any], task_id: str, route: routing.Route) -> str | None:
    if routing.is_bounded_fallback(route):
        return None
    return _resume_session_for(telemetry, task_id)


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
    )


def _clear_task_session(telemetry: dict[str, Any]) -> None:
    task_id = telemetry.get("session_task_id")
    sessions = dict(telemetry.get("task_sessions") or {})
    current_session = telemetry.get("task_session_id")
    if isinstance(task_id, str) and task_id and isinstance(current_session, str) and current_session:
        # Keep the completed task's session in the continuity map while clearing
        # the live slot.  The Task Program transition receipt carries the same
        # value for crash recovery and cross-projection repair.
        sessions[task_id] = current_session
    telemetry["task_sessions"] = sessions
    telemetry["task_session_id"] = None
    telemetry["session_task_id"] = None


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
    capsule = packets.build_task_memory_capsule(
        task, project_root, session_id=_resume_session_for(telemetry, task.id),
        summary=str(previous.get("summary", "")), evidence=previous.get("evidence", ()),
        dirty_paths=_project_dirty_paths(repo_root, project_root),
    )
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


def _task_prompt(repo_root: Path, production: state.ProductionState, task: state.TaskRecord, telemetry: Mapping[str, Any], capsule_path: Path, projection_path: Path | None = None, local_assist_path: Path | None = None, taskbooster_path: Path | None = None, route: routing.Route | None = None) -> str:
    guide_path = Path(production.project_root) / "docs" / "task-guides" / f"{task.id}.md"
    priority_context = f"\nMINITZ_TASK_PROGRAM: {production.priority_policy}. Follow the exact living MiniTZ Task Program order/status and current Task/Run continuity. No ledger, map, helper, or session may advance it independently. Preserve accepted output and required quality.\n"
    owner_context = _minitz_owner_direction(production.project_root)
    if route is not None and routing.is_bounded_fallback(route):
        return priority_context + owner_context + packets.compile_bounded_fallback_packet(task, capsule_path, projection_path, guide_path if guide_path.exists() else None) + execution_map.task_context(repo_root, task.id)
    if _resume_session_for(telemetry, task.id):
        prompt = packets.compile_resume_packet(task, capsule_path)
    else:
        prompt = packets.compile_task_packet(repo_root, production, task)
        if capsule_path.exists():
            prompt += f"\nTASK_MEMORY: {capsule_path}\nRead this bounded recovery capsule before redoing any existing work.\n"
    prompt = priority_context + owner_context + prompt
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


_QWEN_HELPER_BUDGET_SECONDS = 90.0
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
            journal.emit("resource.local_assist_recovery", task_id=task_id, status="RECOVERED", text=recovery_text, provider="ollama-qwen")
        return None
    task_class = str((meaningful.get("task_memory") or {}).get("task_class") or "")
    prompt = (
        "You are Biella's bounded local Qwen execution assistant. Do not decide authority or completion. "
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
        "--provider", "ollama-qwen", "--max-tokens", "320", "--prompt", prompt,
    ]
    if journal is not None:
        journal.emit("resource.local_assist_started", task_id=task_id, status="RUNNING", text=digest[:20], provider="ollama-qwen")
    helper_started = time.monotonic()
    try:
        proc = subprocess.run(argv, text=True, capture_output=True, timeout=_QWEN_HELPER_BUDGET_SECONDS, check=False)
    except subprocess.TimeoutExpired as exc:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        partial = exc.output.decode("utf-8", errors="replace") if isinstance(exc.output, bytes) else str(exc.output or "")
        raw_path.write_text(partial, encoding="utf-8")
        _emit_helper_failure(journal, "resource.local_assist_failed", task_id=task_id,
            failure_type="HELPER_DEADLINE_EXCEEDED", budget_seconds=_QWEN_HELPER_BUDGET_SECONDS, started=helper_started,
            text="Local Qwen helper deadline exceeded", provider="ollama-qwen", raw_result_path=raw_path)
        return None
    except OSError as exc:
        _emit_helper_failure(journal, "resource.local_assist_failed", task_id=task_id,
            failure_type="PROVIDER_UNAVAILABLE", budget_seconds=_QWEN_HELPER_BUDGET_SECONDS, started=helper_started,
            text=str(exc), provider="ollama-qwen")
        return None
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(proc.stdout or "", encoding="utf-8")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "local assist failed")[-1600:]
        _emit_helper_failure(journal, "resource.local_assist_failed", task_id=task_id,
            failure_type=_helper_process_failure_type(detail), budget_seconds=_QWEN_HELPER_BUDGET_SECONDS, started=helper_started,
            text=detail, provider="ollama-qwen", raw_result_path=raw_path, exit_code=proc.returncode)
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        _emit_helper_failure(journal, "resource.local_assist_failed", task_id=task_id,
            failure_type="INVALID_RESULT", budget_seconds=_QWEN_HELPER_BUDGET_SECONDS, started=helper_started,
            text="Local assist returned invalid JSON", provider="ollama-qwen", raw_result_path=raw_path)
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
            failure_type="VALIDATION_REJECTED", budget_seconds=_QWEN_HELPER_BUDGET_SECONDS, started=helper_started,
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
        "raw_result_path": str(raw_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "authority": "NON_AUTHORITATIVE_RESOURCE_ASSIST",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    if journal is not None:
        journal.emit("resource.local_assist_completed", task_id=task_id, status="COMPLETE", text=str(path), provider=str(result.get("provider") or "ollama-qwen"), model=str(result.get("model") or ""))
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
    if not qwen_resident:
        return None, None
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
    return {
        "run_id": "biella-production", "status": liveness,
        "current_section": production.current_section, "current_task": production.current_task,
        "completed": state.completed_count(production), "total": sum(len(s.tasks) for s in production.sections),
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
        while True:
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
                try:
                    route = routing.select_route(
                        "deep_memory", catalog, telemetry.get("cooldowns", {}), now,
                        excluded_models=set(routing.bounded_fallback_models()),
                    )
                except RuntimeError:
                    telemetry.update({"status": "RECOVERING_MODEL", "task_id": f"PLAN:{section.id}", "active_model": None, "active_reasoning": None})
                    _beat(runtime_path, telemetry); time.sleep(min(5.0, max(0.5, routing.earliest_cooldown_delay(telemetry.get("cooldowns", {}), now)))); catalog = _discover_runtime_catalog(runtime_root); continue
                telemetry.update({"status": "RUNNING", "task_id": f"PLAN:{section.id}", "active_model": route.model, "active_reasoning": route.reasoning})
                _beat(runtime_path, telemetry)
                output, stdout, stderr = _attempt_paths(runtime_root, telemetry, f"PLAN-{section.id}-{route.model}")
                rc, error_text = invoke_structured(packets.compile_section_packet(production, section, audit=bool(section.tasks)), route, section_schema_path, output, stdout, stderr, runtime_path, telemetry, heartbeat_interval=heartbeat_interval, cwd=project_root, session_task_id=f"PLAN:{section.id}", event_journal=journal)
                if rc != 0:
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
                telemetry["last_result"] = {"task_id": None, "status": "SECTION_REFRESH", "summary": str(plan.get("summary", "")), "evidence": list(plan.get("evidence", [])), "model": route.model, "reasoning": route.reasoning}
                _beat(runtime_path, telemetry); continue
            if _defer_resource_blocker(repo_root, project_root, production, task, telemetry, journal, runtime_path):
                continue
            now = datetime.now(timezone.utc)
            route, bounded_packet_id = _select_task_route(
                task, catalog, telemetry.get("cooldowns", {}), now, telemetry, repo_root, project_root
            )
            if route is None:
                telemetry.update({"status": "RECOVERING_MODEL", "task_id": task.id, "active_model": None, "active_reasoning": None})
                _beat(runtime_path, telemetry)
                time.sleep(2.0)
                catalog = _discover_runtime_catalog(runtime_root); continue
            if task.task_class == "simple" and bounded_packet_id and routing.is_bounded_fallback(route):
                _record_simple_helper_attempt(telemetry, task.id, bounded_packet_id, route)
            telemetry.update({"status": "RUNNING", "task_id": task.id, "active_model": route.model, "active_reasoning": route.reasoning})
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
            bounded_fallback = routing.is_bounded_fallback(route)
            local_assist_path, taskbooster_path = _prepare_optional_task_assists(
                repo_root, project_root, runtime_root, task, route, catalog, projection_path, journal
            )
            prompt = _task_prompt(
                repo_root, production, task, telemetry, capsule_path, projection_path,
                local_assist_path, taskbooster_path, route=route
            )
            resume_session_id = _resume_session_for_route(telemetry, task.id, route)
            event_type = "task.bounded_fallback_started" if bounded_fallback else ("task.continued" if resume_session_id else "task.started")
            journal.emit(event_type, task_id=task.id, status="RUNNING", text=task.title, model=route.model, reasoning=route.reasoning, bounded_packet_id=bounded_packet_id)
            rc, error_text = invoke_structured(
                prompt, route, schema_path, output, stdout, stderr, runtime_path, telemetry,
                heartbeat_interval=heartbeat_interval, on_heartbeat=observe_activity, cwd=_task_working_directory(repo_root, project_root, task.id),
                resume_session_id=resume_session_id, session_task_id=task.id,
                allow_helper=False if bounded_fallback else _helper_allowed(task.id),
                persist_session_identity=not bounded_fallback,
                event_journal=journal,
            )
            if rc != 0:
                stale_resume = resume_session_id and _is_stale_resume_error(error_text)
                incompatible_resume = resume_session_id and _is_resume_protocol_incompatible(error_text)
                if stale_resume or incompatible_resume:
                    stale_session_id = resume_session_id
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
                _set_failure(telemetry, route, str(exc), task.id); _beat(runtime_path, telemetry); continue
            result = _normalize_result_for_route(result, route)
            if result.status in {"COMPLETE", "COMPLETE_ALREADY"} and (telemetry.get("source_alignment") or {}).get("state") == "RECONCILIATION_REQUIRED":
                result = evidence.TaskResult(result.task_id, "CONTINUE",
                    "Preserve passed task evidence; reconcile only the observed source revision difference before closure: " + str(telemetry["source_alignment"].get("detail", "")), result.evidence)
            observe_activity()
            result = evidence.enforce_clean_completion_boundary(repo_root, result, owned_files=current_owned)
            _emit_validation_evidence(repo_root, project_root, result, journal)
            telemetry["last_result"] = {
                "task_id": result.task_id, "status": result.status, "summary": result.summary,
                "evidence": list(result.evidence), "model": route.model, "reasoning": route.reasoning,
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
