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
import threading
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_REPO_ROOT = Path(os.environ.get("MINITZ_REPO_ROOT") or Path(__file__).resolve().parents[2]).resolve()
_SRC_ROOT = _REPO_ROOT / "src"
if _SRC_ROOT.is_dir() and str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import minitz_codex_routing as routing
import minitz_execution_style as execution_style
import minitz_memory_compactor as memory_compactor
import minitz_main_coder as main_coder
import minitz_commander_fabric as commander
import minitz_local_capacity as local_capacity
import minitz_boost_fabric as boost_fabric
import minitz_taskbooster as taskbooster
import minitz_task_program as minitz
import minitz_task_guidance as task_guidance
import minitz_production_evidence as evidence
import minitz_production_events as production_events
import minitz_production_state as state
import minitz_task_packet as packets
import minitz_publication as publication
import minitz_execution_map as execution_map
import minitz_completion_truth as completion_truth

UNIT_NAME = "minitz-production"
SOURCE_REFRESH_EXIT = 75

_shutdown_requested = threading.Event()
_local_qwen_recovery_lock = threading.Lock()

def _request_graceful_shutdown(signum, frame) -> None:
    del signum, frame
    _shutdown_requested.set()

_RUNTIME_KEYS = {
    "status", "project", "task_id", "attempt", "execution_sequence", "task_attempt", "attempt_task_id", "stable_blocker", "pid", "child_pid",
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
    project_scope: str
    task_id: str
    task_state_digest: str
    process: subprocess.Popen
    output_path: Path
    stdout_path: Path
    stderr_path: Path
    accepted_path: Path


@dataclass
class BoosterSyncHandle:
    program_sha256: str
    process: subprocess.Popen
    stdout_path: Path
    stderr_path: Path


@dataclass
class CommanderHandle:
    key: str
    lane_id: str
    role: str
    requested_provider: str
    project_scope: str
    task_id: str
    task_state_digest: str
    projection_digest: str
    process: subprocess.Popen
    stdout_path: Path
    stderr_path: Path
    lease_path: Path
    accepted_path: Path
    rejected_path: Path
    quality_context: Mapping[str, object] | None = None


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
        "execution_sequence": 0, "task_attempt": 0, "attempt_task_id": None, "stable_blocker": None,
        "pid": None, "child_pid": None, "active_model": None,
        "active_reasoning": None, "cooldowns": {}, "last_result": None,
        "heartbeat_at": None, "updated_at": datetime.now(timezone.utc).isoformat(),
        "task_session_id": None, "session_task_id": None, "task_sessions": {},
        "coder_sessions": {}, "coder_statuses": {"codex": "NEEDS_MODIFICATION"},
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
    payload["execution_sequence"] = int(payload.get("execution_sequence") or 0)
    payload["task_attempt"] = int(payload.get("task_attempt") or payload.get("attempt") or 0)
    payload["attempt"] = payload["task_attempt"]  # public/runtime meaning: current canonical task attempt
    payload["stable_blocker"] = dict(payload["stable_blocker"]) if isinstance(payload.get("stable_blocker"), Mapping) else None
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
    result["execution_sequence"] = int(raw.get("execution_sequence") or raw.get("attempt") or 0)
    result["task_attempt"] = int(raw.get("task_attempt") or (raw.get("attempt") if "execution_sequence" in raw else 0) or 0)
    result["attempt"] = result["task_attempt"]
    result["stable_blocker"] = dict(raw["stable_blocker"]) if isinstance(raw.get("stable_blocker"), Mapping) else None
    result["coder_statuses"].setdefault("codex", "NEEDS_MODIFICATION")
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


def _commander_output_evidence(path: Path, *, prefix: str) -> dict[str, Any]:
    """Capture one completed Commander stream without embedding provider bytes."""

    source_path = Path(path)
    result: dict[str, Any] = {f"{prefix}_capture_path": str(source_path)}
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        result.update({
            f"{prefix}_path": str(source_path),
            f"{prefix}_available": False,
            f"{prefix}_read_error": type(exc).__name__,
        })
        return result

    digest = hashlib.sha256(raw).hexdigest()
    evidence_path = source_path.with_name(
        f"{source_path.stem}.{digest}.evidence{source_path.suffix}"
    )
    try:
        file_descriptor = os.open(evidence_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    except OSError:
        evidence_path = source_path
    else:
        try:
            with os.fdopen(file_descriptor, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            evidence_path = source_path

    result.update({
        f"{prefix}_path": str(evidence_path),
        f"{prefix}_sha256": digest,
        f"{prefix}_bytes": len(raw),
        f"{prefix}_available": True,
    })
    return result


def _commander_file_identity(path: Path, *, prefix: str) -> dict[str, Any]:
    source_path = Path(path)
    result: dict[str, Any] = {f"{prefix}_path": str(source_path)}
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        result.update({
            f"{prefix}_available": False,
            f"{prefix}_read_error": type(exc).__name__,
        })
        return result
    result.update({
        f"{prefix}_sha256": hashlib.sha256(raw).hexdigest(),
        f"{prefix}_bytes": len(raw),
        f"{prefix}_available": True,
    })
    return result


def _commander_immutable_json(path: Path, payload: Mapping[str, Any]) -> bool:
    """Create one metadata sidecar without rewriting an existing evidence record."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    try:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        existing = commander.read_json(target)
        if (
            existing.get("schema") != payload.get("schema")
            or existing.get("rejection_sha256") != payload.get("rejection_sha256")
            or existing.get("raw_result_sha256") != payload.get("raw_result_sha256")
        ):
            raise ValueError(f"immutable Commander evidence link conflict: {target}")
        return False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return True


def _commander_link_path(rejected_path: Path) -> Path:
    name = Path(rejected_path).name
    if name.endswith(".rejected.json"):
        name = name[:-len(".rejected.json")] + ".evidence-link.json"
    else:
        name += ".evidence-link.json"
    return Path(rejected_path).with_name(name)


def _journal_commander_link_refs(
    journal: production_events.ProductionEventJournal,
) -> set[str]:
    refs: set[str] = set()
    for segment in production_events._journal_segment_paths(journal.path):
        for _line_number, _raw, item in production_events._iter_jsonl_objects(segment):
            if (
                item.get("type") == "commander.assist_evidence_linked"
                and isinstance(item.get("evidence_link_ref"), str)
            ):
                refs.add(str(item["evidence_link_ref"]))
    return refs


def _existing_commander_failure_type(payload: Mapping[str, Any], stdout_path: Path) -> str:
    existing = str(payload.get("failure_type") or "").strip()
    if existing:
        return existing
    try:
        commander.parse_resource_result(stdout_path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return _commander_rejection_type(0, exc)
    return "VALIDATION_REJECTED"


def reconcile_commander_rejection_evidence(
    runtime_root: Path,
    journal: production_events.ProductionEventJournal | None = None,
) -> tuple[Path, ...]:
    """Attach old Commander rejection artifacts to raw output and journal identity.

    This is deliberately append-only: original rejection/stdout/stderr/journal
    bytes are never rewritten. A content-addressed raw capture and an immutable
    sidecar bind the existing records; an optional distinct journal event records
    that relation without re-emitting the original failure.
    """

    root = _commander_root(runtime_root)
    if not root.is_dir():
        return ()
    events_path = Path(runtime_root) / "events.jsonl"
    failures_path = Path(runtime_root) / "failures.jsonl"
    occurrence_index = production_events.build_commander_failure_occurrence_index(
        events_path, failures_path,
    )
    existing_link_refs = _journal_commander_link_refs(journal) if journal is not None else set()
    linked: list[Path] = []
    for rejected_path in sorted(root.glob("*.rejected.json")):
        payload = commander.read_json(rejected_path)
        if (
            payload.get("schema") != "minitz.commander_rejection/v1"
            or payload.get("authority") != "NONE"
            or not payload.get("cache_key")
        ):
            continue
        key = str(payload.get("cache_key"))
        if rejected_path.name != f"{key}.rejected.json":
            continue
        stdout_path, stderr_path, _lease_path, _accepted_path, _rejected_path = _commander_paths(runtime_root, key)
        raw_result = _commander_output_evidence(stdout_path, prefix="raw_result")
        if not raw_result.get("raw_result_available"):
            continue
        raw_error = _commander_output_evidence(stderr_path, prefix="raw_error")
        rejection_identity = _commander_file_identity(rejected_path, prefix="rejection")
        occurrence = production_events.find_commander_failure_occurrence(
            events_path, failures_path, payload, occurrence_index=occurrence_index,
        )
        event = occurrence.get("event") if isinstance(occurrence.get("event"), Mapping) else {}
        failure = occurrence.get("failure") if isinstance(occurrence.get("failure"), Mapping) else {}
        failure_type = _existing_commander_failure_type(payload, stdout_path)
        legacy_failure_type = str(
            failure.get("failure_type")
            or event.get("failure_type")
            or event.get("event_type")
            or "commander.assist_failed"
        )
        if event and failure:
            link_status = "LINKED"
        elif event:
            link_status = "EVENT_LINKED_FAILURE_UNRESOLVED"
        else:
            link_status = "RAW_LINKED_JOURNAL_UNRESOLVED"
        link_path = _commander_link_path(rejected_path)
        link: dict[str, Any] = {
            "schema": "minitz.commander_evidence_link/v1",
            "record_kind": "EVIDENCE_LINK",
            "semantic_graph": "MiniTZ",
            "semantic_family_ref": production_events._EVIDENCE_FAMILY_REF,
            "family_revision": production_events._EVIDENCE_FAMILY_REVISION,
            "authority": "NONE_DERIVED_EVIDENCE",
            "evidence_authority": "NONE_DERIVED_EVIDENCE",
            "projection_authority": False,
            "progression_authority": False,
            "task_id": payload.get("task_id"),
            "task_state_digest": payload.get("task_state_digest"),
            "projection_digest": payload.get("projection_digest"),
            "lane_id": payload.get("lane_id"),
            "role": payload.get("role"),
            "provider": payload.get("provider"),
            "cache_key": key,
            "status": payload.get("status"),
            "failure_type": failure_type,
            "legacy_failure_type": legacy_failure_type,
            "event_type": "commander.assist_failed",
            "created_at": payload.get("created_at"),
            "rejection_ref": str(rejected_path),
            **rejection_identity,
            **raw_result,
            **raw_error,
            "evidence_ref": raw_result.get("raw_result_path"),
            "evidence_link_ref": str(link_path),
            "source_event_ref": event.get("ref"),
            "source_failure_ref": failure.get("ref"),
            "source_event_line": event.get("source_line"),
            "source_failure_line": failure.get("source_line"),
            "source_event_raw_sha256": event.get("raw_sha256"),
            "source_failure_raw_sha256": failure.get("raw_sha256"),
            "legacy_event_identity": event.get("ref"),
            "source_status": payload.get("status"),
            "link_status": link_status,
        }
        _commander_immutable_json(link_path, link)
        if journal is not None and str(link_path) not in existing_link_refs:
            journal.emit(
                "commander.assist_evidence_linked",
                task_id=str(payload.get("task_id") or "") or None,
                status="LINKED",
                text=str(link_path),
                lane_id=payload.get("lane_id"),
                role=payload.get("role"),
                provider=payload.get("provider"),
                cache_key=key,
                source_status=payload.get("status"),
                failure_type=failure_type,
                legacy_failure_type=legacy_failure_type,
                rejection_ref=str(rejected_path),
                rejection_sha256=rejection_identity.get("rejection_sha256"),
                rejection_bytes=rejection_identity.get("rejection_bytes"),
                raw_result_capture_path=raw_result.get("raw_result_capture_path"),
                raw_result_path=raw_result.get("raw_result_path"),
                raw_result_sha256=raw_result.get("raw_result_sha256"),
                raw_result_bytes=raw_result.get("raw_result_bytes"),
                evidence_ref=raw_result.get("raw_result_path"),
                evidence_link_ref=str(link_path),
                source_event_ref=event.get("ref"),
                source_failure_ref=failure.get("ref"),
                legacy_event_identity=event.get("ref"),
                link_status=link_status,
                authority="NONE",
            )
            existing_link_refs.add(str(link_path))
        linked.append(link_path)
    return tuple(linked)


def _commander_rejection_type(returncode: int, error: BaseException) -> str:
    if int(returncode) != 0:
        return "PROCESS_FAILED"
    if isinstance(error, json.JSONDecodeError):
        return "INVALID_RESULT"
    message = str(error).lower()
    if "provider text" in message or "resource result" in message:
        return "INVALID_RESULT"
    return "VALIDATION_REJECTED"


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


def _task_bound_mapping_matches(task: state.TaskRecord, payload: Mapping[str, Any] | None) -> bool:
    if not isinstance(payload, Mapping) or payload.get("task_id") != task.id:
        return False
    authority = packets._task_authority(task)
    if authority is None:
        return True
    return (
        payload.get("task_revision") == authority["task_revision"]
        and str(payload.get("task_digest") or "") == str(authority["task_digest"])
    )


def _bind_task_identity(task: state.TaskRecord, payload: Mapping[str, Any]) -> dict[str, Any]:
    bound = dict(payload)
    authority = packets._task_authority(task)
    if authority is not None:
        bound.update({
            "task_revision": authority["task_revision"],
            "task_digest": authority["task_digest"],
            "scope_ref": authority["scope_ref"],
        })
    return bound


def _task_bound_runtime_result(task: state.TaskRecord, result: evidence.TaskResult, **metadata: Any) -> dict[str, Any]:
    return _bind_task_identity(task, {
        "task_id": result.task_id, "status": result.status, "summary": result.summary,
        "evidence": list(result.evidence), **metadata,
    })


def _resource_blocker_summary(telemetry: Mapping[str, Any], task: state.TaskRecord | str) -> str | None:
    previous = telemetry.get("last_result")
    if isinstance(task, state.TaskRecord):
        if not _task_bound_mapping_matches(task, previous):
            return None
    elif not isinstance(previous, Mapping) or previous.get("task_id") != task:
        return None
    if not isinstance(previous, Mapping) or previous.get("status") != "CONTINUE":
        return None
    summary = str(previous.get("summary", "")).strip()
    return summary if summary.startswith("REQUIRES_OTHER_RESOURCE:") else None


def _defer_resource_blocker(repo_root: Path, project_root: Path, production: state.ProductionState, task: state.TaskRecord, telemetry: dict[str, Any], journal: production_events.ProductionEventJournal, runtime_path: Path) -> bool:
    summary = _resource_blocker_summary(telemetry, task)
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


def _normalize_result_for_route(
    result: evidence.TaskResult, route: routing.Route, *, allow_minitz_validated_completion: bool = False,
    repo_root: Path | None = None, sandbox_root: Path | None = None,
) -> evidence.TaskResult:
    del allow_minitz_validated_completion
    if result.status in {"COMPLETE", "COMPLETE_ALREADY"} and routing.is_bounded_fallback(route):
        return evidence.TaskResult(
            result.task_id, "CONTINUE",
            "BOUNDED_ASSIST_ONLY: bounded/local helper result cannot close the canonical task.",
            result.evidence,
        )
    if repo_root is None:
        return result
    repo = Path(repo_root).resolve()
    sandbox = Path(sandbox_root).resolve() if sandbox_root is not None else Path(os.environ.get(
        "MINITZ_OS_SANDBOX_ROOT", str(repo.parents[1])
    )).resolve()
    decision = completion_truth.admit_model_result(
        repo, sandbox, result.task_id, result.status, result.summary, result.evidence
    )
    return evidence.TaskResult(
        result.task_id, str(decision["status"]), str(decision["summary"]),
        tuple(str(item) for item in decision["evidence"]),
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


def _task_guidance_for(task_id: str) -> dict[str, Any] | None:
    try:
        program = minitz.load()
        program_file = Path(str(program.get("_observed_path") or minitz.program_path())).resolve()
        root = program_file.parent / "task_guidance"
        if not task_guidance.task_is_in_guided_range(program, task_id, root, start_offset=6):
            return None
        document = task_guidance.load_task_guidance(program, task_id, root)
        if document is not None:
            return document
        task_guidance.write_guidance_documents(program_file, output_root=root, start_offset=6)
        return task_guidance.load_task_guidance(program, task_id, root)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


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


MINITZ_PRODUCTION_WRITER_ID = "minitz:production-runner"


def _ensure_minitz_writer_claim(
    repo_root: Path, project_root: Path, task: state.TaskRecord,
    journal: production_events.ProductionEventJournal | None = None,
) -> state.TaskRecord:
    """Ensure the canonical task is active without blocking on worker ownership metadata."""
    if not state._use_minitz_project(Path(project_root)):
        return task
    program = minitz.load()
    current = minitz.current_task(program)
    if current is None or str(current.get("task_id") or "") != task.id:
        raise ValueError("MiniTZ writer claim target is not the first active task")
    writers = [w for w in current.get("workers") or [] if w.get("write_authority") is True and w.get("status") == "WORKING"]
    if current.get("status") != "WORKING" or not writers:
        minitz.claim_task(
            task.id, worker_id=MINITZ_PRODUCTION_WRITER_ID, worker_role="PRIMARY_WRITER",
            write_authority=True,
            evidence=["MiniTZ production runner has a viable execution route and is claiming the current task before write execution"],
        )
        if journal is not None:
            journal.emit(
                "task.writer_claimed", task_id=task.id, status="WORKING",
                text="MiniTZ production runner claimed the current task before write execution.",
            )
    refreshed = state.resolve_current_task(repo_root, project_root)
    if refreshed is None or refreshed.id != task.id:
        raise ValueError("MiniTZ writer claim changed current task identity")
    return refreshed


def _task_working_directory(repo_root: Path, project_root: Path, task_id: str) -> Path:
    if state._use_minitz_project(Path(project_root)):
        program = minitz.load()
        row = minitz.task_by_id(program, task_id)
        scope = row.get("write_scope")
        if isinstance(scope, dict):
            return minitz.execution_root(row)
        return Path(repo_root).resolve()
    return execution_map.task_working_directory(repo_root, project_root, task_id)


def _minitz_capsule_continuity(repo_root: Path, runtime_root: Path, task: state.TaskRecord) -> dict[str, Any]:
    """Capture bounded current identity for a MiniTZ task-memory capsule.

    The capsule is a recovery projection, not a progression authority.  It records
    only digests and identity metadata so a fresh provider session can re-bootstrap
    from the live Task Program, OS policy, and durable task memory.
    """
    authority = packets._task_authority(task)
    if authority is None:
        return {}
    program = minitz.load()
    row = minitz.task_by_id(program, task.id)
    if (
        int(row.get("revision", 0)) != int(authority["task_revision"])
        or str(row.get("task_record_sha256") or "") != str(authority["task_digest"])
    ):
        raise ValueError("MiniTZ task capsule identity is stale")
    program_identity = minitz.program_identity(program)

    def git_value(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(Path(repo_root).resolve()), *args],
            text=True, capture_output=True, check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError("MiniTZ task capsule worktree identity is unavailable")
        return result.stdout.strip()

    try:
        worktree_identity = {
            "branch": git_value("branch", "--show-current"),
            "head": git_value("rev-parse", "HEAD"),
            "tree": git_value("rev-parse", "HEAD^{tree}"),
            "workspace_fingerprint": _task_workspace_fingerprint(repo_root, repo_root),
        }
    except RuntimeError:
        # Legacy/unit-test fixtures may be plain directories.  Preserve the
        # exact MiniTZ task/session authority while omitting this optional
        # worktree representation; the canonical MiniTZ repository is a Git
        # worktree and records it there.
        worktree_identity = None

    return {
        "task_revision": authority["task_revision"],
        "task_digest": authority["task_digest"],
        "program_identity": program_identity,
        "worktree_identity": worktree_identity,
        "policy_ref": str(Path(repo_root).resolve() / "ops" / "workstation" / "AGENTS.md"),
    }


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
        local_model = os.environ.get("MINITZ_LOCAL_MODEL", "qwen3-coder-next:minitz")
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
    elif codex_route is None or routing.is_bounded_fallback(codex_route):
        statuses["codex"] = "OUT_OF_CREDIT" if telemetry.get("cooldowns") else "NEEDS_MODIFICATION"
    telemetry["coder_statuses"] = statuses
    telemetry["active_coder"] = "codex"
    if not codex_full:
        return None, None, None, None
    copilot_status = statuses.get("copilot")
    copilot_candidate = main_coder.copilot_candidate_available() and copilot_status not in {"OFFLINE", "OUT_OF_CREDIT", "NEEDS_MODIFICATION"}
    cloud_status = statuses.get("copilot-cloudflare")
    cloud_candidate = (
        main_coder.copilot_cloudflare_candidate_available()
        and cloud_status not in {"OFFLINE", "OUT_OF_CREDIT", "NEEDS_MODIFICATION"}
    )
    if copilot_status == "ACTIVE" and main_coder.copilot_candidate_available():
        peer = "copilot"
    elif copilot_candidate:
        peer = "copilot"
    elif cloud_candidate:
        peer = "copilot-cloudflare"
    else:
        peer = None
    return "codex", codex_route, packet_id, peer


def _select_main_coder_class_route(
    task_class: str, codex_catalog: Mapping[str, set[str]], telemetry: dict[str, Any], now: datetime,
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
    telemetry["active_coder"] = "codex"
    if codex_route is not None and codex_route.provider == "openai":
        return "codex", codex_route
    return None, None


def _select_main_coder_peer_route(
    peer_coder: str | None, task: state.TaskRecord, codex_catalog: Mapping[str, set[str]],
    telemetry: dict[str, Any], now: datetime, repo_root: Path, project_root: Path,
) -> routing.Route | None:
    statuses = telemetry.get("coder_statuses", {}) if isinstance(telemetry.get("coder_statuses"), Mapping) else {}
    if peer_coder == "copilot" and main_coder.copilot_candidate_available():
        if statuses.get("copilot") not in {"OFFLINE", "OUT_OF_CREDIT", "NEEDS_MODIFICATION"}:
            return routing.Route(str(os.environ.get("MINITZ_COPILOT_MODEL") or "gpt-5.4"), "none", "copilot")
    if peer_coder == "copilot-cloudflare" and main_coder.copilot_cloudflare_candidate_available():
        if statuses.get("copilot-cloudflare") not in {"OFFLINE", "OUT_OF_CREDIT", "NEEDS_MODIFICATION"}:
            return routing.Route("@cf/moonshotai/kimi-k2.7-code", "none", "copilot-cloudflare")
    if peer_coder == "copilot-qwen" and main_coder.copilot_local_qwen_candidate_available():
        if statuses.get("copilot-qwen") not in {"OFFLINE", "OUT_OF_CREDIT", "NEEDS_MODIFICATION"}:
            model = os.environ.get("MINITZ_LOCAL_MODEL", "qwen3-coder-next:minitz")
            return routing.Route(model, "none", "copilot-qwen")
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
    continuity = _minitz_capsule_continuity(repo_root, runtime_root, task)
    existing_progress = existing if _task_bound_mapping_matches(task, existing) else {}
    runtime_result = telemetry.get("last_result") if isinstance(telemetry.get("last_result"), dict) else {}
    previous = runtime_result if _task_bound_mapping_matches(task, runtime_result) else existing_progress
    active_coder = str(telemetry.get("active_coder") or "codex")
    capsule = packets.build_task_memory_capsule(
        task, project_root, session_id=_resume_session_for(telemetry, task.id, coder_id=active_coder),
        summary=str(previous.get("summary", "")), evidence=previous.get("evidence", ()),
        dirty_paths=_project_dirty_paths(repo_root, project_root),
        **continuity,
    )
    task_coder_sessions = (telemetry.get("coder_sessions") or {}).get(task.id, {}) if isinstance(telemetry.get("coder_sessions"), Mapping) else {}
    capsule["coder_sessions"] = dict(task_coder_sessions) if isinstance(task_coder_sessions, Mapping) else {}
    for name in ("workspace_baseline", "owned_files"):
        if name in existing:
            capsule[name] = existing[name]
    if "live_observation" in existing_progress:
        capsule["live_observation"] = existing_progress["live_observation"]
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


def _minitz_owner_wake_context(capsule_path: Path, task_id: str) -> str:
    return ""


def _main_coder_peer_key(
    project_root: Path,
    task: state.TaskRecord,
    task_state_digest: str,
    peer_coder: str,
    model: str,
    capsule_path: Path,
    projection_path: Path | None,
) -> str:
    capsule_data = commander.read_json(Path(capsule_path))
    project_scope = commander.project_scope_id(capsule_data, project_root)
    capsule_digest = hashlib.sha256(Path(capsule_path).read_bytes()).hexdigest()
    projection_digest = "NONE"
    if projection_path is not None and Path(projection_path).is_file():
        projection_digest = hashlib.sha256(Path(projection_path).read_bytes()).hexdigest()
    return main_coder.peer_assist_key(
        project_scope, task.id, task_state_digest, peer_coder, model, capsule_digest, projection_digest
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
    capsule_data = commander.read_json(Path(capsule_path))
    project_scope = commander.project_scope_id(capsule_data, project_root)
    key = _main_coder_peer_key(project_root, task, task_state_digest, peer_coder, peer_route.model, capsule_path, projection_path)
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
    child_env = os.environ.copy()
    if peer_coder == "codex":
        command = routing.build_codex_peer_command(peer_route, schema_path, output_path, working_root)
        stdin_text = prompt
    elif peer_coder in {"copilot", "copilot-qwen", "copilot-cloudflare"}:
        profile = {"copilot": "native", "copilot-qwen": "local-qwen", "copilot-cloudflare": "cloudflare"}[peer_coder]
        session_id = main_coder.copilot_session_id(project_scope, task.id, task_state_digest, profile)
        read_dirs = [Path(capsule_path).parent]
        if projection_path is not None:
            read_dirs.append(Path(projection_path).parent)
        command = main_coder.build_copilot_peer_command(
            prompt, session_id, working_root, read_dirs=read_dirs
        )
        child_env = main_coder.copilot_peer_env(profile, child_env)
        stdin_text = None
    else:
        raise ValueError(f"unsupported main coder peer: {peer_coder}")
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            text=True, stdout=stdout, stderr=stderr,
            env=child_env, cwd=working_root, umask=0o022,
        )
        if stdin_text is not None:
            assert process.stdin is not None
            process.stdin.write(stdin_text)
            process.stdin.close()
    inflight[key] = MainCoderPeerHandle(
        key, peer_coder, peer_route.model, project_scope, task.id, task_state_digest,
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
            if handle.peer_coder in {"copilot", "copilot-qwen", "copilot-cloudflare"}:
                raw_result = json.loads(stdout_text.strip())
            else:
                raw_result = json.loads(handle.output_path.read_text(encoding="utf-8"))
            result = main_coder.validate_peer_assist(raw_result)  # type: ignore[arg-type]
            wrapper = {
                "schema": "minitz.main_coder_peer_assist/v1",
                "authority": "NONE",
                "project_scope": handle.project_scope,
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
            if handle.peer_coder in {"copilot", "copilot-qwen", "copilot-cloudflare"}:
                telemetry.setdefault("coder_statuses", {})[handle.peer_coder] = main_coder.classify_copilot_observation(
                    int(rc), detail + "\n" + str(exc)
                )
            rejected_path = handle.accepted_path.with_name(handle.accepted_path.name.replace(".accepted.json", ".rejected.json"))
            rejected = {
                "schema": "minitz.main_coder_peer_rejection/v1", "authority": "NONE",
                "project_scope": handle.project_scope,
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


def _latest_main_coder_peer_assist(runtime_root: Path, project_scope: str, task_id: str, task_state_digest: str) -> Path | None:
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
        if payload.get("project_scope") != project_scope:
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


def _commander_resource_command(registry: Mapping[str, Any], provider: str) -> list[str]:
    providers = registry.get("providers") if isinstance(registry.get("providers"), Mapping) else {}
    definition = providers.get(provider) if isinstance(providers.get(provider), Mapping) else {}
    structured = bool(definition.get("commander_structured_output"))
    command = commander.build_resource_command(
        provider,
        max_tokens=max(64, min(1024, int(definition.get("commander_result_max_tokens") or _commander_result_tokens()))),
        response_schema=commander.commander_result_schema() if structured else None,
        disable_reasoning=bool(definition.get("commander_disable_reasoning")) if structured else False,
    )
    if definition.get("commander_timeout_seconds"):
        command.extend(["--timeout-seconds", str(float(definition["commander_timeout_seconds"]))])
    return command


def _remote_commander_provider_limit() -> int:
    """Keep paid/remote helper fanout separate from local GPU parallelism."""
    try:
        value = int(os.environ.get("MINITZ_REMOTE_COMMANDER_PROVIDER_MAX_INFLIGHT", "1"))
    except ValueError:
        value = 1
    return max(1, min(commander.COMMANDER_LANE_COUNT, value))


def _local_qwen_parallelism() -> int:
    """Use the local runtime's supplied parallel capability; MiniTZ adds no one-call cap."""
    raw = str(os.environ.get("MINITZ_LOCAL_QWEN_PARALLEL") or "").strip()
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return min(commander.COMMANDER_LANE_COUNT, value)
        except ValueError:
            pass
    return commander.COMMANDER_LANE_COUNT


def _commander_external_provider_pool(
    repo_root: Path,
    registry: Mapping[str, object],
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    """Select configured external LLM candidates without importing secrets into the runner."""
    maximum = max(0, int(limit))
    if maximum == 0:
        return ()
    selected = list(commander.eligible_external_providers(registry, os.environ)[:maximum])
    if len(selected) >= maximum:
        return tuple(selected)
    registry_path = Path(repo_root) / "ops/workstation/provider-registry.json"
    try:
        completed = subprocess.run(
            ["/usr/local/bin/minitz-resource", "--registry", str(registry_path), "status"],
            text=True, capture_output=True, timeout=12, check=False,
        )
        if completed.returncode != 0:
            return tuple(selected)
        payload = json.loads(completed.stdout)
        if not isinstance(payload, Mapping):
            return tuple(selected)
        status_candidates = commander.eligible_external_providers_from_status(registry, payload, limit=maximum)
        for provider in status_candidates:
            if provider not in selected:
                selected.append(provider)
            if len(selected) >= maximum:
                break
        return tuple(selected)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
        return tuple(selected)


def _maybe_start_booster_autosync(
    repo_root: Path,
    runtime_root: Path,
    current: BoosterSyncHandle | None,
    completed_programs: set[str],
    retry_after: dict[str, float],
    journal: production_events.ProductionEventJournal,
    *,
    failure_counts: dict[str, int] | None = None,
) -> BoosterSyncHandle | None:
    """Refresh all five bounded Qwen Booster contexts once per exact Task Program revision."""
    enabled = str(os.environ.get("MINITZ_BOOSTER_AUTOSYNC") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return current
    failures = failure_counts if failure_counts is not None else {}
    if current is not None:
        rc = current.process.poll()
        if rc is None:
            return current
        if rc == 0:
            completed_programs.add(current.program_sha256)
            failures.pop(current.program_sha256, None)
            retry_after.pop(current.program_sha256, None)
            journal.emit(
                "resource.booster_sync_completed", status="COMPLETE",
                text=current.program_sha256, authority="NONE", provider="ollama-qwen",
            )
        else:
            count = int(failures.get(current.program_sha256, 0)) + 1
            failures[current.program_sha256] = count
            if count >= 3:
                retry_after[current.program_sha256] = float("inf")
                failure_status = "SUPPRESSED"
            else:
                retry_after[current.program_sha256] = time.monotonic() + (60.0 * (5 ** (count - 1)))
                failure_status = "ERROR"
            journal.emit(
                "resource.booster_sync_failed", status=failure_status,
                text=_tail(current.stderr_path, 1200), authority="NONE", provider="ollama-qwen",
                consecutive_failures=count,
            )
        current = None
    try:
        identity = minitz.program_identity()
        program_sha = str(identity.get("sha256") or "")
    except Exception as exc:
        journal.emit("resource.booster_sync_failed", status="ERROR", text=str(exc)[:1200], authority="NONE")
        return None
    if not program_sha or program_sha in completed_programs or time.monotonic() < retry_after.get(program_sha, 0.0):
        return None
    script = Path(repo_root) / "ops/local-ai/minitz_booster_sync.py"
    if not script.is_file():
        retry_after[program_sha] = time.monotonic() + 60.0
        journal.emit("resource.booster_sync_failed", status="ERROR", text=f"missing {script}", authority="NONE")
        return None
    root = Path(runtime_root) / "memory/boost-work-program/autosync"
    root.mkdir(parents=True, exist_ok=True)
    stdout_path = root / f"{program_sha}.stdout.json"
    stderr_path = root / f"{program_sha}.stderr.log"
    env = dict(os.environ)
    env.update({
        "MINITZ_SANDBOX_REPO": str(Path(repo_root).resolve()),
        "MINITZ_RUNTIME_ROOT": str(Path(runtime_root).resolve()),
        "MINITZ_PROVIDER_REGISTRY": str(Path(repo_root).resolve() / "ops/workstation/provider-registry.json"),
    })
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                [sys.executable, str(script), "sync", "--with-local-ai"],
                cwd=str(Path(repo_root).resolve()), env=env, stdout=stdout, stderr=stderr,
                start_new_session=False,
            )
    except OSError as exc:
        retry_after[program_sha] = time.monotonic() + 60.0
        journal.emit("resource.booster_sync_failed", status="ERROR", text=str(exc)[:1200], authority="NONE")
        return None
    journal.emit(
        "resource.booster_sync_started", status="RUNNING", text=program_sha,
        authority="NONE", provider="ollama-qwen", pid=int(process.pid),
    )
    return BoosterSyncHandle(program_sha, process, stdout_path, stderr_path)


def _commander_result_tokens() -> int:
    try:
        value = int(os.environ.get("MINITZ_COMMANDER_RESULT_MAX_TOKENS", str(commander.DEFAULT_RESULT_MAX_TOKENS)))
    except ValueError:
        value = commander.DEFAULT_RESULT_MAX_TOKENS
    return max(64, min(1024, value))


def _commander_provider_health_path(runtime_root: Path) -> Path:
    return _commander_root(runtime_root) / "provider-health.json"


def _active_commander_provider_health(runtime_root: Path) -> dict[str, dict[str, Any]]:
    path = _commander_provider_health_path(runtime_root)
    payload = commander.read_json(path)
    if payload.get("schema") != "minitz.commander_provider_health/v1":
        return {}
    providers = payload.get("providers") if isinstance(payload.get("providers"), Mapping) else {}
    now = datetime.now(timezone.utc)
    active: dict[str, dict[str, Any]] = {}
    for provider, raw in providers.items():
        if not isinstance(raw, Mapping):
            continue
        retry_after = str(raw.get("retry_after") or "")
        try:
            retry_at = datetime.fromisoformat(retry_after.replace("Z", "+00:00"))
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if retry_at <= now:
            continue
        active[str(provider)] = dict(raw)
    # Expiry permits another attempt; only a validated success resets the
    # failure streak. Preserve it across cooldown/task/session changes.
    return active


def _record_commander_provider_failure(runtime_root: Path, provider: str, status: str, detail: str) -> dict[str, Any]:
    path = _commander_provider_health_path(runtime_root)
    payload = commander.read_json(path)
    providers = dict(payload.get("providers") or {}) if payload.get("schema") == "minitz.commander_provider_health/v1" else {}
    prior = providers.get(provider) if isinstance(providers.get(provider), Mapping) else {}
    count = int(prior.get("consecutive_failures") or 0) + 1
    observed = datetime.now(timezone.utc)
    base = commander.failure_retry_after(status, now=observed, detail=detail)
    try:
        retry_at = datetime.fromisoformat(str(base or observed.isoformat()).replace("Z", "+00:00"))
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
    except ValueError:
        retry_at = observed
    lowered = str(detail or "").lower()
    if status == "OUT_OF_CREDIT" and ("429" in lowered or "rate limit" in lowered or "too many requests" in lowered):
        retry_at = max(retry_at, observed + timedelta(seconds=min(1800, 60 * (2 ** min(count - 1, 5)))))
    elif status == "OUT_OF_CREDIT":
        retry_at = max(retry_at, observed + timedelta(seconds=min(21600, 1800 * (2 ** min(count - 1, 4)))))
    row = {
        "status": status, "retry_after": retry_at.isoformat(), "consecutive_failures": count,
        "detail_sha256": hashlib.sha256(str(detail or "").encode("utf-8", errors="replace")).hexdigest(),
        "updated_at": observed.isoformat(),
    }
    providers[provider] = row
    commander.atomic_json(path, {
        "schema": "minitz.commander_provider_health/v1", "authority": "NONE",
        "progression_authority": False, "providers": providers, "updated_at": observed.isoformat(),
    })
    return row


def _clear_commander_provider_failure(runtime_root: Path, provider: str) -> None:
    path = _commander_provider_health_path(runtime_root)
    payload = commander.read_json(path)
    if payload.get("schema") != "minitz.commander_provider_health/v1":
        return
    providers = dict(payload.get("providers") or {})
    if provider not in providers:
        return
    providers.pop(provider, None)
    commander.atomic_json(path, {
        "schema": "minitz.commander_provider_health/v1", "authority": "NONE",
        "progression_authority": False, "providers": providers,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


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
        "work_mode": lane.work_mode,
        "status": status if status in commander.COMMANDER_STATUSES else "NEEDS_MODIFICATION",
        "activity": activity,
        "provider": provider,
        "cache_key": key,
        "result_path": str(result_path) if result_path is not None else None,
    }


_BOOST_PACK_WORK_MODES = ("WRITER", "WRITER", "READER", "READER", "READER", "VALIDATOR")


def _commander_boost_packs(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_lane = {str(row.get("lane_id")): dict(row) for row in rows if isinstance(row, Mapping)}
    packs: list[dict[str, Any]] = []
    for group in boost_fabric.boost_groups():
        lanes: list[dict[str, Any]] = []
        for lane_id, work_mode in zip(group.commander_lanes, _BOOST_PACK_WORK_MODES, strict=True):
            row = dict(by_lane.get(lane_id, {"lane_id": lane_id, "status": "OFFLINE", "activity": "UNASSIGNED"}))
            row["boost_id"] = group.boost_id
            row["work_mode"] = work_mode
            lanes.append(row)
        packs.append({"boost_id": group.boost_id, "lanes": lanes})
    return packs


def _commander_cached_row(
    lane: commander.CommanderLane,
    *,
    project_scope: str,
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
            and payload.get("project_scope") == project_scope
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
            and payload.get("project_scope") == project_scope
            and payload.get("task_id") == task_id
            and payload.get("task_state_digest") == task_state_digest
            and payload.get("projection_digest") == projection_digest
            and payload.get("lane_id") == lane.lane_id
        ):
            retry_after = str(payload.get("retry_after") or "")
            created_at = str(payload.get("created_at") or "")
            detail = str(payload.get("detail") or "")
            status = str(payload.get("status") or "NEEDS_MODIFICATION")
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at else None
                if created is not None and created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
            except ValueError:
                created = None
            normalized_retry = commander.failure_retry_after(status, now=created, detail=detail) if created is not None else None
            if normalized_retry and (not retry_after or normalized_retry < retry_after):
                retry_after = normalized_retry
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
        index.get("project_scope") != handle.project_scope
        or index.get("task_id") != handle.task_id
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
    index["boosts"] = _commander_boost_packs(updated)
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
    project_scope = commander.project_scope_id(capsule, project_root)
    context = commander.bounded_context(capsule, projection)
    # Hash the actual bounded input, not refreshed timestamps or unused fields.
    projection_digest = hashlib.sha256(json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()
    try:
        registry = json.loads((Path(repo_root) / "ops/workstation/provider-registry.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        registry = {"providers": {}, "routes": {"llm.fast": []}}
    external_candidates = _commander_external_provider_pool(
        Path(repo_root), registry, limit=commander.COMMANDER_LANE_COUNT
    )
    local_provider = "ollama-qwen"
    local_resident = (
        local_provider in registry.get("providers", {})
        and local_provider in registry.get("routes", {}).get("llm.fast", [])
        and _local_qwen_resident()
    )
    capacity_snapshot: dict[str, Any] = {}
    if local_resident:
        try:
            capacity_snapshot = local_capacity.observe_local_capacity()
        except Exception as exc:
            capacity_snapshot = {"observation_error": type(exc).__name__}
    local_admission: dict[str, Any] = commander.local_capacity_observation(capacity_snapshot)
    if not local_resident:
        local_admission.update({"admitted": False, "reason": "NOT_RESIDENT"})
    provider_candidates = (local_provider,) if local_resident else tuple(external_candidates)
    remote_provider_limit = _remote_commander_provider_limit()
    local_provider_limit = _local_qwen_parallelism() if local_resident else 0
    prior_index = commander.read_json(index_path)
    same_index = (
        prior_index.get("authority") == "NONE"
        and prior_index.get("project_scope") == project_scope
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
                or payload.get("project_scope") != project_scope
                or payload.get("task_id") != task.id
                or payload.get("task_state_digest") != task_state_digest
                or payload.get("projection_digest") != projection_digest
            ):
                continue
            if str(raw.get("status") or "") == "ACTIVE" and str(raw.get("activity") or "") in {"USEFUL", "NO_FINDING"}:
                provider_proven_active.add(provider)
                continue
            if str(raw.get("activity") or "") == "REJECTED" and not commander.result_scoped_failure(payload):
                retry_after = str(payload.get("retry_after") or "")
                status = str(payload.get("status") or "NEEDS_MODIFICATION")
                detail = str(payload.get("detail") or "")
                created_at = str(payload.get("created_at") or "")
                try:
                    created = datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at else None
                    if created is not None and created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                except ValueError:
                    created = None
                normalized_retry = commander.failure_retry_after(status, now=created, detail=detail) if created is not None else None
                if normalized_retry and (not retry_after or normalized_retry < retry_after):
                    retry_after = normalized_retry
                if not retry_after:
                    continue
                try:
                    retry_at = datetime.fromisoformat(retry_after.replace("Z", "+00:00"))
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if datetime.now(timezone.utc) < retry_at:
                    provider_backoff[provider] = (status, retry_after)
    for provider, health in _active_commander_provider_health(runtime_root).items():
        provider_backoff[provider] = (
            str(health.get("status") or "NEEDS_MODIFICATION"),
            str(health.get("retry_after") or ""),
        )
    # Healthy resident Qwen suppresses paid remote helpers. If it becomes unavailable
    # or enters real provider backoff, remote candidates take over on the same task.
    if local_resident and local_provider in provider_backoff:
        provider_candidates = tuple(external_candidates)
    providers = commander.select_provider_pool(provider_candidates, provider_backoff, limit=3)
    schedule = commander.provider_schedule(
        commander.commander_lanes(), providers, per_provider_limit=commander.COMMANDER_LANE_COUNT
    )
    provider_inflight: dict[str, int] = {}
    for existing in inflight.values():
        provider_inflight[existing.requested_provider] = provider_inflight.get(existing.requested_provider, 0) + 1
    rows: list[dict[str, Any]] = []
    launched = 0
    for lane in commander.commander_lanes():
        reused = None
        for cached_provider in provider_candidates:
            cached_key = commander.commander_cache_key(
                project_scope, task.id, task_state_digest, projection_digest, lane.lane_id, lane.role, cached_provider
            )
            cached_stdout, cached_stderr, cached_lease, cached_accepted, cached_rejected = _commander_paths(runtime_root, cached_key)
            if not cached_accepted.is_file():
                continue
            reused = _commander_cached_row(
                lane, project_scope=project_scope, task_id=task.id, task_state_digest=task_state_digest,
                projection_digest=projection_digest, provider=cached_provider, key=cached_key,
                accepted_path=cached_accepted, rejected_path=cached_rejected,
            )
            if reused is not None and reused.get("activity") in {"USEFUL", "NO_FINDING"}:
                break
            reused = None
        if reused is not None:
            rows.append(reused)
            continue
        existing_lane = next((handle for handle in inflight.values() if handle.project_scope == project_scope and handle.task_id == task.id and handle.task_state_digest == task_state_digest and handle.projection_digest == projection_digest and handle.lane_id == lane.lane_id and handle.process.poll() is None), None)
        if existing_lane is not None:
            rows.append(_commander_index_row(lane, provider=existing_lane.requested_provider, key=existing_lane.key, status="ACTIVE", activity="RUNNING"))
            continue
        prior_context_lane = next((handle for handle in inflight.values()
            if handle.project_scope == project_scope and handle.task_id == task.id
            and handle.task_state_digest == task_state_digest and handle.lane_id == lane.lane_id
            and handle.process.poll() is None), None)
        if prior_context_lane is not None:
            rows.append(_commander_index_row(lane, provider=prior_context_lane.requested_provider, key=prior_context_lane.key, status="ACTIVE", activity="RUNNING"))
            continue
        provider = schedule.get(lane.lane_id)
        if local_provider in providers and provider_inflight.get(local_provider, 0) < local_provider_limit:
            local_key = commander.commander_cache_key(project_scope, task.id, task_state_digest, projection_digest, lane.lane_id, lane.role, local_provider)
            local_paths = _commander_paths(runtime_root, local_key)
            local_rejection = commander.read_json(local_paths[4])
            if not local_rejection:
                provider = local_provider
        if not provider:
            rows.append(_commander_index_row(lane, provider=None, key=None, status="OFFLINE", activity="UNASSIGNED"))
            continue
        key = commander.commander_cache_key(
            project_scope, task.id, task_state_digest, projection_digest, lane.lane_id, lane.role, provider
        )
        stdout_path, stderr_path, lease_path, accepted_path, rejected_path = _commander_paths(runtime_root, key)
        cached = _commander_cached_row(
            lane, project_scope=project_scope, task_id=task.id, task_state_digest=task_state_digest,
            projection_digest=projection_digest, provider=provider, key=key,
            accepted_path=accepted_path, rejected_path=rejected_path,
        )
        if cached is not None:
            rows.append(cached)
            if cached.get("activity") == "REJECTED" and rejected_path.is_file():
                rejected_payload = commander.read_json(rejected_path)
                retry_after = str(rejected_payload.get("retry_after") or "")
                status = str(rejected_payload.get("status") or "NEEDS_MODIFICATION")
                detail = str(rejected_payload.get("detail") or "")
                created_at = str(rejected_payload.get("created_at") or "")
                try:
                    created = datetime.fromisoformat(created_at.replace("Z", "+00:00")) if created_at else None
                    if created is not None and created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                except ValueError:
                    created = None
                normalized_retry = commander.failure_retry_after(status, now=created, detail=detail) if created is not None else None
                if normalized_retry and (not retry_after or normalized_retry < retry_after):
                    retry_after = normalized_retry
                if retry_after and not commander.result_scoped_failure(rejected_payload):
                    try:
                        retry_at = datetime.fromisoformat(retry_after.replace("Z", "+00:00"))
                        if retry_at.tzinfo is None:
                            retry_at = retry_at.replace(tzinfo=timezone.utc)
                    except ValueError:
                        retry_at = datetime.now(timezone.utc)
                    if datetime.now(timezone.utc) < retry_at:
                        provider_backoff[provider] = (status, retry_after)
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
        effective_provider_limit = local_provider_limit if provider == local_provider else (remote_provider_limit if provider in provider_proven_active else 1)
        if len(inflight) >= commander.COMMANDER_LANE_COUNT or provider_inflight.get(provider, 0) >= effective_provider_limit:
            rows.append(_commander_index_row(lane, provider=provider, key=key, status="OFFLINE", activity="UNASSIGNED"))
            continue
        packet = commander.commander_packet(
            lane=lane, project_scope=project_scope, task_id=task.id, task_state_digest=task_state_digest,
            projection_digest=projection_digest, requested_provider=provider, context=context,
        )
        prompt = commander.commander_prompt(packet)
        command = _commander_resource_command(registry, provider)
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
                project_scope=project_scope, task_id=task.id, task_state_digest=task_state_digest, projection_digest=projection_digest,
                process=process, stdout_path=stdout_path, stderr_path=stderr_path,
                lease_path=lease_path, accepted_path=accepted_path, rejected_path=rejected_path,
                quality_context=context,
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
            provider_health = _record_commander_provider_failure(
                runtime_root, provider, status, str(exc)
            )
            raw_result_evidence = _commander_output_evidence(stdout_path, prefix="raw_result")
            raw_error_evidence = _commander_output_evidence(stderr_path, prefix="raw_error")
            rejected = {
                "schema": "minitz.commander_rejection/v1", "authority": "NONE",
                "project_scope": project_scope,
                "task_id": task.id, "task_state_digest": task_state_digest,
                "projection_digest": projection_digest, "lane_id": lane.lane_id,
                "role": lane.role, "provider": provider, "cache_key": key,
                "status": status, "detail": str(exc)[-1200:],
                **raw_result_evidence, **raw_error_evidence,
                "evidence_ref": raw_result_evidence.get("raw_result_path"),
                "retry_after": provider_health.get("retry_after"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            commander.atomic_json(rejected_path, rejected)
            rows.append(_commander_index_row(lane, provider=provider, key=key, status=status, activity="REJECTED", result_path=rejected_path))
            if journal is not None:
                journal.emit(
                    "commander.assist_failed", task_id=task.id, status=status,
                    text=str(exc)[-1200:], lane_id=lane.lane_id, role=lane.role,
                    provider=provider, authority="NONE",
                    raw_result_capture_path=raw_result_evidence.get("raw_result_capture_path"),
                    raw_result_path=raw_result_evidence.get("raw_result_path"),
                    raw_result_sha256=raw_result_evidence.get("raw_result_sha256"),
                    raw_result_bytes=raw_result_evidence.get("raw_result_bytes"),
                    evidence_ref=raw_result_evidence.get("raw_result_path"),
                )
    for row in rows:
        if row.get("activity") != "RUNNING":
            continue
        if row.get("provider") == local_provider:
            row["route_reason"] = "LOCAL_FIRST_WITH_CAPACITY"
        elif not local_admission.get("admitted"):
            row["route_reason"] = str(local_admission.get("reason") or "CAPACITY_UNKNOWN")
        elif local_provider in provider_backoff:
            row["route_reason"] = "LOCAL_PROVIDER_RESTRICTION"
        elif provider_inflight.get(local_provider, 0) >= local_provider_limit:
            row["route_reason"] = "LOCAL_CAPACITY_BUSY"
        else:
            row["route_reason"] = "LOCAL_RESULT_RETRY_BOUNDARY"
    index = {
        "schema": "minitz.commander_fabric/v1",
        "authority": "NONE",
        "progression_authority": False,
        "project_scope": project_scope,
        "task_id": task.id,
        "task_state_digest": task_state_digest,
        "projection_digest": projection_digest,
        "total_lanes": commander.COMMANDER_LANE_COUNT,
        "remote_provider_limit": remote_provider_limit,
        "local_parallelism": local_provider_limit,
        "provider_canary_first": True,
        "local_capacity": local_admission,
        "local_inflight": provider_inflight.get(local_provider, 0),
        "uncached_pending_lanes": sum(row.get("activity") in {"UNASSIGNED", "PROVIDER_BACKOFF"} for row in rows),
        "quality_policy": "grounded-candidate-v1; functional acceptance requires task validation",
        "provider_proven_active": sorted(provider_proven_active),
        "provider_backoff": {provider: {"status": value[0], "retry_after": value[1]} for provider, value in sorted(provider_backoff.items())},
        "candidate_providers": list(provider_candidates),
        "eligible_providers": list(providers),
        "launched_this_pass": launched,
        "lanes": rows,
        "boosts": _commander_boost_packs(rows),
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
    # Commander lanes are Booster-managed by default. The canonical main coder only
    # consumes their durable index/results; it does not launch or supervise them.
    # Explicit legacy/test opt-in remains available for bounded compatibility.
    if str(os.environ.get("MINITZ_COMMANDER_AUTOLAUNCH") or "").strip().lower() not in {"1", "true", "yes", "on"}:
        existing = _commander_index_path(runtime_root)
        return existing if existing.is_file() else None
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
        raw_result_evidence = _commander_output_evidence(handle.stdout_path, prefix="raw_result")
        raw_error_evidence = _commander_output_evidence(handle.stderr_path, prefix="raw_error")
        detail = commander.execution_failure_detail(int(rc), stdout_text, stderr_text)
        try:
            if rc != 0:
                raise ValueError(detail or f"Commander exited {rc}")
            raw_result, meta = commander.parse_resource_result(stdout_text)
            packet = {
                "lane_id": handle.lane_id,
                "project_scope": handle.project_scope,
                "task_id": handle.task_id,
                "task_state_digest": handle.task_state_digest,
                "projection_digest": handle.projection_digest,
            }
            result = commander.validate_commander_result(packet, raw_result)
            quality = commander.validate_result_quality({**packet, "context": handle.quality_context}, result) if handle.quality_context is not None else {"status": "UNKNOWN", "reason": "LEGACY_HANDLE_WITHOUT_QUALITY_CONTEXT"}
            wrapper = {
                "quality_validation": quality,
                "schema": "minitz.commander_assist/v1",
                "authority": "NONE",
                "progression_authority": False,
                "project_scope": handle.project_scope,
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
                **raw_result_evidence,
                **raw_error_evidence,
                "evidence_ref": raw_result_evidence.get("raw_result_path"),
                "cache_key": handle.key,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            commander.atomic_json(handle.accepted_path, wrapper)
            _clear_commander_provider_failure(
                runtime_root, str(wrapper.get("provider") or handle.requested_provider)
            )
            _update_commander_index_lane(
                runtime_root, handle, status="ACTIVE", activity=str(result.get("status") or "NO_FINDING"),
                provider=str(wrapper.get("provider") or handle.requested_provider), result_path=handle.accepted_path,
            )
            if journal is not None:
                journal.emit(
                    "commander.assist_completed", task_id=handle.task_id, status="ACTIVE",
                    text=str(handle.accepted_path), lane_id=handle.lane_id, role=handle.role,
                    provider=wrapper.get("provider"), authority="NONE",
                    raw_result_capture_path=wrapper.get("raw_result_capture_path"),
                    raw_result_path=wrapper.get("raw_result_path"),
                    raw_result_sha256=wrapper.get("raw_result_sha256"),
                    raw_result_bytes=wrapper.get("raw_result_bytes"),
                    evidence_ref=wrapper.get("evidence_ref"),
                )
        except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
            failure_type = _commander_rejection_type(int(rc), exc)
            if int(rc) != 0:
                status = commander.classify_failure(int(rc), detail)
                provider_health = _record_commander_provider_failure(
                    runtime_root, handle.requested_provider, status, detail
                )
            else:
                status = "NEEDS_MODIFICATION"
                provider_health = {"retry_after": commander.failure_retry_after(status)}
            rejected = {
                "schema": "minitz.commander_rejection/v1", "authority": "NONE",
                "progression_authority": False,
                "project_scope": handle.project_scope,
                "task_id": handle.task_id, "task_state_digest": handle.task_state_digest,
                "projection_digest": handle.projection_digest, "lane_id": handle.lane_id,
                "role": handle.role, "provider": handle.requested_provider,
                "cache_key": handle.key, "status": status, "failure_type": failure_type,
                "failure_scope": "PROVIDER" if int(rc) != 0 else "RESULT",
                "detail": str(exc)[-1200:],
                **raw_result_evidence,
                **raw_error_evidence,
                "evidence_ref": raw_result_evidence.get("raw_result_path"),
                "retry_after": provider_health.get("retry_after"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            commander.atomic_json(handle.rejected_path, rejected)
            _update_commander_index_lane(
                runtime_root, handle, status=status, activity="REJECTED",
                provider=handle.requested_provider, result_path=handle.rejected_path,
            )
            if journal is not None and int(rc) != 0:
                journal.emit(
                    "commander.assist_failed", task_id=handle.task_id, status=status,
                    text=str(exc)[-1200:], lane_id=handle.lane_id, role=handle.role,
                    provider=handle.requested_provider, authority="NONE",
                    failure_type=failure_type,
                    raw_result_capture_path=raw_result_evidence.get("raw_result_capture_path"),
                    raw_result_path=raw_result_evidence.get("raw_result_path"),
                    raw_result_sha256=raw_result_evidence.get("raw_result_sha256"),
                    raw_result_bytes=raw_result_evidence.get("raw_result_bytes"),
                    evidence_ref=raw_result_evidence.get("raw_result_path"),
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


def _refresh_commander_assists_during_task(
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
    """Collect finished lanes and refill bounded Commander capacity during a long writer call."""
    _collect_commander_assists_nonblocking(runtime_root, inflight, journal)
    return _prepare_commander_assists_nonblocking(
        repo_root, project_root, runtime_root, task, task_state_digest,
        capsule_path, projection_path, inflight, journal,
    )


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


def _booster_handoff_refs_for_task(
    ledger_path: Path, task_id: str, task_revision: int | None = None, task_digest: str | None = None,
) -> tuple[Path, ...]:
    ledger = commander.read_json(Path(ledger_path))
    refs: list[Path] = []
    for raw in ledger.get("items", []) if isinstance(ledger.get("items"), list) else []:
        if not isinstance(raw, Mapping):
            continue
        row_task = str(raw.get("canonical_task_id") or raw.get("task_id") or "")
        status = str(raw.get("work_status") or raw.get("status") or "")
        if row_task != task_id or status not in {"HANDOFF_READY", "DONE_LOCAL"}:
            continue
        if task_revision is not None and int(raw.get("canonical_task_revision") or task_revision) != int(task_revision):
            continue
        if task_digest is not None and str(raw.get("canonical_task_sha256") or task_digest) != str(task_digest):
            continue
        candidates = list(raw.get("evidence_refs") or []) if isinstance(raw.get("evidence_refs"), list) else []
        if raw.get("handoff_ref"):
            candidates.append(raw.get("handoff_ref"))
        for value in candidates:
            candidate = Path(str(value))
            try:
                candidate.resolve().relative_to(Path(ledger_path).resolve().parent)
            except (OSError, ValueError):
                continue
            if candidate.is_file() and candidate not in refs:
                refs.append(candidate)
    return tuple(refs)


def _task_prompt(repo_root: Path, production: state.ProductionState, task: state.TaskRecord, telemetry: Mapping[str, Any], capsule_path: Path, projection_path: Path | None = None, local_assist_path: Path | None = None, taskbooster_path: Path | None = None, route: routing.Route | None = None, peer_assist_path: Path | None = None, commander_index_path: Path | None = None, *, coder_id: str = "codex") -> str:
    guide_path = Path(production.project_root) / "docs" / "task-guides" / f"{task.id}.md"
    if production.run_id == "minitz-task-program":
        priority_context = f"\nMINITZ_TASK_PROGRAM: {production.priority_policy}. Follow the exact living MiniTZ Task Program order/status and current Task/Run continuity. No ledger, map, helper, or session may advance it independently. Preserve accepted output and required quality.\n"
    else:
        priority_context = f"\nPRODUCTION_PRIORITY: {production.priority_policy}. Preserve the current project production order and accepted task continuity.\n"
    owner_context = _minitz_owner_direction(production.project_root)
    wake_context = _minitz_owner_wake_context(capsule_path, task.id)
    working_root = _task_working_directory(repo_root, Path(production.project_root), task.id)
    policies = main_coder.shared_policy_paths(repo_root, working_root)
    policy_context = f"\nMAIN_CODER_BACKEND: {coder_id}\n"
    if policies:
        policy_context += f"SHARED_MINITZ_POLICY: {policies[0]}\n"
        if len(policies) > 1:
            policy_context += f"PROJECT_AGENTS_POLICY: {policies[1]}\n"
        policy_context += "Apply these same MiniTZ/Project instructions regardless of coder backend; backend change never changes authority, acceptance, memory, cache, or task scope.\n"
    bounded_fallback = route is not None and routing.is_bounded_fallback(route)
    if bounded_fallback:
        prompt = packets.compile_bounded_fallback_packet(
            task, capsule_path, projection_path, guide_path if guide_path.exists() else None,
            allow_validated_completion=production.run_id == "minitz-task-program",
        )
    elif _task_has_shared_continuity(telemetry, task.id, capsule_path):
        prompt = packets.compile_resume_packet(task, capsule_path)
    else:
        prompt = packets.compile_task_packet(repo_root, production, task)
        if capsule_path.exists():
            prompt += f"\nTASK_MEMORY: {capsule_path}\nRead this bounded recovery capsule before redoing any existing work.\n"
    prompt = priority_context + owner_context + wake_context + policy_context + prompt
    if production.run_id == "minitz-task-program":
        prompt += (
            "\nMINITZ_PROGRESS_COMPLETION\n"
            "When the authorized task work is finished, return COMPLETE. Validation/tests may be recorded as evidence, "
            "but no validation family, reviewer, receipt, accepted-criteria ceremony, or provider/model may veto task progression. "
            "Return CONTINUE only when real task work remains.\nEND_MINITZ_PROGRESS_COMPLETION\n"
        )
    guidance_document = _task_guidance_for(task.id) if production.run_id == "minitz-task-program" else None
    if guidance_document is not None:
        helper_guidance = task_guidance.helper_view(guidance_document)
        prompt += (
            "\nMINITZ_TASK_GUIDANCE\n"
            + json.dumps(helper_guidance, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\nThis derived task guidance is digest-bound, non-authoritative execution context. Use its data, acceptance, evidence and capability context to reduce rediscovery. "
            + "It cannot advance, complete, or become capability authority. Required/candidate capabilities may improve execution and may produce validated capability candidates, "
            + "but durable System/Engine promotion requires current MiniTZ validation and canonical admission.\nEND_MINITZ_TASK_GUIDANCE\n"
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
        os_memory_index = Path(projection_path).parent / "compacted-memory.json"
        if os_memory_index.is_file():
            prompt += (
                f"\nMINITZ_OS_MEMORY_INDEX: {os_memory_index}\n"
                "This is the primary MiniTZ OS-wide memory/experience/evidence index. It serves the MiniTZ OS system, not one task. "
                "Use it when system-wide prior decisions, verified mechanisms, failures, capabilities, provenance, or reusable experience materially affect the current task. "
                "Historical material remains provenance unless current MiniTZ OS policy promotes it; raw secrets remain excluded.\n"
            )
        prompt += (
            f"\nMEMORY_PROJECTION: {projection_path}\n"
            "This is a rebuildable bounded current-task derivative of the MiniTZ OS-wide memory index. "
            "Use it for efficient current-task context, but do not treat the current task as the owner or scope of MiniTZ memory. "
            "Follow its source refs or the OS memory index when exact system-wide detail is required. It never overrides current source or task authority.\n"
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
    booster_root = Path(capsule_path).parent.parent / "boost-work-program"
    booster_ledger = booster_root / "BOOSTER_TASK_LIST.json"
    booster_handoff = booster_root / "context" / "main-coder-context.json"
    if booster_ledger.is_file():
        prompt += (
            f"\nBOOSTER_SHARED_LEDGER: {booster_ledger}\n"
            "This is non-authoritative persistent work coordination for five owner-launched Boosters. "
            "Use it to avoid redoing DONE_LOCAL/HANDOFF_READY work, but never let it advance or reorder the canonical Task Program.\n"
        )
    if booster_ledger.is_file():
        authority = packets._task_authority(task)
        handoff_refs = _booster_handoff_refs_for_task(
            booster_ledger, task.id,
            int(authority["task_revision"]) if authority else None,
            str(authority["task_digest"]) if authority else None,
        )
        if handoff_refs:
            prompt += "\nBOOSTER_EXACT_TASK_HANDOFFS\n" + "\n".join(str(ref) for ref in handoff_refs) + (
                "\nThese refs are exact-task, revision/digest-matched, non-authoritative Booster implementation/evidence. "
                "Read and validate them before rediscovery; reuse valid bytes/tests/commits, but canonical completion remains MiniTZ validation authority.\n"
                "END_BOOSTER_EXACT_TASK_HANDOFFS\n"
            )
    if booster_handoff.is_file():
        prompt += (
            f"\nBOOSTER_MAIN_CODER_HANDOFF: {booster_handoff}\n"
            "Read exact-task Booster results, validate them against current source/evidence, and reuse valid implementation/evidence instead of replaying work. "
            "Booster results are assistance only and never completion/progression authority.\n"
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
        memory_project_root = repo_root if state._use_minitz_project(Path(project_root)) else project_root
        result = memory_compactor.refresh_compacted_memory(
            repo_root, memory_project_root, runtime_root, current_task_id=task_id
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


def _ensure_local_resource_assist(runtime_root: Path, task_id: str, projection_path: Path, journal: production_events.ProductionEventJournal | None = None, *, project_root: Path | None = None, guidance_document: Mapping[str, Any] | None = None) -> Path | None:
    try:
        projection = json.loads(Path(projection_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if journal is not None:
            journal.emit("resource.local_assist_failed", task_id=task_id, status="ERROR", text=f"Projection unavailable for local assist: {exc}")
        return None
    if not isinstance(projection, Mapping):
        return None
    meaningful = _assist_projection_payload(projection)
    if isinstance(guidance_document, Mapping):
        meaningful["task_guidance"] = task_guidance.helper_view(guidance_document)
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
        "/usr/local/bin/minitz-resource", "fast-llm",
        "--provider", "ollama-qwen", "--max-failover-attempts", "1",
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
        "schema": "minitz.local_resource_assist/v1",
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
        # Resolve the MiniTZ alias once, then prove residency by immutable model
        # digest so an older equivalent tag cannot hide already-resident bytes.
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.0) as response:
            tags = json.loads(response.read().decode("utf-8"))
        desired = next(
            (str(item.get("digest") or "") for item in tags.get("models", [])
             if isinstance(item, Mapping) and str(item.get("name") or "") == "qwen3-coder-next:minitz"),
            "",
        )
        if not desired:
            return False
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return any(
            str(item.get("digest") or "") == desired and int(item.get("size_vram") or 0) > 0
            for item in payload.get("models", []) if isinstance(item, Mapping)
        )
    except Exception:
        return False


def _warm_local_qwen() -> bool:
    """Warm the canonical MiniTZ Qwen alias locally; never fall through to a paid provider."""
    with _local_qwen_recovery_lock:
        if _local_qwen_resident():
            return True
        base = str(os.environ.get("MINITZ_OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
        model = str(os.environ.get("MINITZ_LOCAL_MODEL") or "qwen3-coder-next:minitz").strip()
        payload = json.dumps({"model": model, "prompt": "", "stream": False, "keep_alive": -1}, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            base + "/api/generate", data=payload, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            timeout = float(os.environ.get("MINITZ_LOCAL_QWEN_WARM_TIMEOUT_SECONDS", "120"))
        except ValueError:
            timeout = 120.0
        with urllib.request.urlopen(request, timeout=max(5.0, min(timeout, 600.0))) as response:
            response.read()
        return _local_qwen_resident()


def _ensure_local_qwen_ready(telemetry: dict[str, Any], journal: production_events.ProductionEventJournal | None = None,
                             task_id: str | None = None, *, blocking: bool = True) -> bool:
    """Keep local Qwen resident. Remote writer work may begin only after a successful blocking check."""
    if _local_qwen_resident():
        previous = telemetry.get("local_qwen_state")
        telemetry["local_qwen_state"] = "RESIDENT"
        telemetry.pop("local_qwen_recovery_detail", None)
        if previous == "RECOVERING" and journal is not None:
            journal.emit("resource.local_qwen_recovered", task_id=task_id, status="ACTIVE", text="Local Qwen residency restored")
        return True
    telemetry["local_qwen_state"] = "RECOVERING"
    telemetry["local_qwen_recovery_attempts"] = int(telemetry.get("local_qwen_recovery_attempts") or 0) + 1
    if journal is not None and telemetry.get("local_qwen_recovery_announced") is not True:
        journal.emit("resource.local_qwen_recovery_started", task_id=task_id, status="RECOVERING", text="Recovering local Qwen before additional remote writer spend")
        telemetry["local_qwen_recovery_announced"] = True
    if not blocking:
        if not _local_qwen_recovery_lock.locked():
            thread = threading.Thread(target=_warm_local_qwen, name="minitz-local-qwen-recovery", daemon=True)
            thread.start()
        return False
    try:
        ready = _warm_local_qwen()
    except Exception as exc:
        telemetry["local_qwen_recovery_detail"] = f"{type(exc).__name__}: {exc}"[-1200:]
        return False
    if ready:
        telemetry["local_qwen_state"] = "RESIDENT"
        telemetry["local_qwen_recovery_announced"] = False
        telemetry.pop("local_qwen_recovery_detail", None)
        if journal is not None:
            journal.emit("resource.local_qwen_recovered", task_id=task_id, status="ACTIVE", text="Local Qwen residency restored")
    return ready


def _remote_writer_requires_local_qwen(coder_id: str | None, route: routing.Route | None) -> bool:
    return bool(
        coder_id == "codex" and route is not None
        and route.provider != "ollama"
        and not routing.is_bounded_fallback(route)
    )


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
    guidance_document = _task_guidance_for(task.id)
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
            local_assist = _ensure_local_resource_assist(runtime_root, task.id, projection_path, journal, project_root=working_root, guidance_document=guidance_document)
            if local_assist is None:
                local_assist = deterministic_context
        elif decision.kind == "SPARK":
            local_assist = deterministic_context
        else:
            return None, None
        if local_assist is None:
            return None, None
        boosted = None  # retired legacy TaskBooster; use five-Boost fabric
        return local_assist, boosted
    local_assist = _ensure_local_resource_assist(runtime_root, task.id, projection_path, journal, project_root=working_root, guidance_document=guidance_document)
    if local_assist is None:
        return None, None
    boosted = None  # retired legacy TaskBooster; use five-Boost fabric
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


def _historical_task_attempt_count(attempts: Path, task_id: str) -> int:
    prefixes: set[int] = set()
    marker = f"-{task_id}-"
    if not attempts.is_dir():
        return 0
    for path in attempts.glob("*.stdout.log"):
        name = path.name
        if marker not in name:
            continue
        prefix = name.split("-", 1)[0]
        if prefix.isdigit():
            prefixes.add(int(prefix))
    return len(prefixes)


def _attempt_paths(runtime_root: Path, telemetry: dict[str, Any], stem: str, *, task_id: str | None = None) -> tuple[Path, Path, Path]:
    attempts = runtime_root / "attempts"; attempts.mkdir(parents=True, exist_ok=True)
    sequence = int(telemetry.get("execution_sequence") or telemetry.get("attempt") or 0) + 1
    telemetry["execution_sequence"] = sequence
    if task_id:
        if telemetry.get("attempt_task_id") == task_id and int(telemetry.get("task_attempt") or 0) > 0:
            task_attempt = int(telemetry["task_attempt"]) + 1
        else:
            task_attempt = _historical_task_attempt_count(attempts, task_id) + 1
        telemetry["attempt_task_id"] = task_id
        telemetry["task_attempt"] = task_attempt
        telemetry["attempt"] = task_attempt
    base = f"{sequence:04d}-{stem}"
    return attempts / f"{base}.result.json", attempts / f"{base}.stdout.log", attempts / f"{base}.stderr.log"


_EXTERNAL_CONDITION_SCHEMES = ("github://", "remote://", "http://", "https://", "owner://")

def _external_failure_rows(evidence_items: Sequence[str]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for item in evidence_items:
        if not isinstance(item, str) or not item.lstrip().startswith("{"):
            continue
        try:
            record = json.loads(item)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, Mapping) or str(record.get("verdict", "")).upper() not in {"FAIL", "FAILED", "ERROR"}:
            continue
        refs = [str(record.get(key) or "") for key in ("evidence_ref", "source_ref")]
        external_ref = next((ref for ref in refs if ref.startswith(_EXTERNAL_CONDITION_SCHEMES)), "")
        if not external_ref:
            continue
        rows.append({
            "criterion": str(record.get("criterion") or ""),
            "evidence_ref": external_ref,
            "verdict": str(record.get("verdict") or "").upper(),
        })
    return tuple(sorted(rows, key=lambda row: (row["evidence_ref"], row["criterion"], row["verdict"])))


def _external_condition_fingerprint(result: evidence.TaskResult) -> str | None:
    if result.status != "CONTINUE":
        return None
    rows = _external_failure_rows(result.evidence)
    if not rows:
        return None
    payload = {"task_id": result.task_id, "failures": rows}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _external_blocker_delay_seconds(repeat_count: int) -> float:
    try:
        base = max(5.0, float(os.environ.get("MINITZ_EXTERNAL_BLOCKER_BASE_SECONDS", "60")))
    except ValueError:
        base = 60.0
    try:
        maximum = max(base, float(os.environ.get("MINITZ_EXTERNAL_BLOCKER_MAX_SECONDS", "3600")))
    except ValueError:
        maximum = 3600.0
    return min(maximum, base * (2 ** max(0, min(int(repeat_count) - 1, 10))))


def _record_external_condition_wait(
    telemetry: dict[str, Any], result: evidence.TaskResult, source_identity: str, *,
    now: datetime | None = None, repeat_floor: int = 1, task: state.TaskRecord | None = None,
) -> bool:
    fingerprint = _external_condition_fingerprint(result)
    if fingerprint is None:
        telemetry["stable_blocker"] = None
        return False
    observed = now or datetime.now(timezone.utc)
    previous = telemetry.get("stable_blocker") if isinstance(telemetry.get("stable_blocker"), Mapping) else {}
    same = previous.get("fingerprint") == fingerprint and previous.get("source_identity") == source_identity
    repeat_count = max(int(repeat_floor), int(previous.get("repeat_count") or 0) + 1 if same else 1)
    delay = _external_blocker_delay_seconds(repeat_count)
    blocker: dict[str, Any] = {
        "schema": "minitz.stable_external_blocker/v1", "task_id": result.task_id,
        "fingerprint": fingerprint, "source_identity": source_identity,
        "repeat_count": repeat_count, "observed_at": observed.isoformat(),
        "retry_at": (observed + timedelta(seconds=delay)).isoformat(),
        "delay_seconds": delay, "reason": "UNCHANGED_EXTERNAL_CONDITION",
    }
    if task is not None:
        blocker = _bind_task_identity(task, blocker)
    telemetry["stable_blocker"] = blocker
    telemetry.update({"status": "WAITING_FOR_CONDITION", "task_id": result.task_id, "child_pid": None, "active_model": None, "active_reasoning": None})
    return True


def _seed_external_condition_wait_from_last_result(
    telemetry: dict[str, Any], task: state.TaskRecord | str, source_identity: str,
    runtime_root: Path, *, now: datetime | None = None,
) -> bool:
    if isinstance(telemetry.get("stable_blocker"), Mapping):
        return False
    last = telemetry.get("last_result") if isinstance(telemetry.get("last_result"), Mapping) else None
    if isinstance(task, state.TaskRecord):
        if not _task_bound_mapping_matches(task, last):
            return False
        task_id = task.id
    else:
        task_id = task
        if not last or last.get("task_id") != task_id:
            return False
    if not last or last.get("status") != "CONTINUE":
        return False
    raw_evidence = last.get("evidence")
    if not isinstance(raw_evidence, list):
        return False
    evidence_items = tuple(item for item in raw_evidence if isinstance(item, str))
    rows = _external_failure_rows(evidence_items)
    if not rows:
        return False
    recovered = evidence.TaskResult(
        task_id, "CONTINUE", str(last.get("summary") or "persisted external blocker"), evidence_items,
    )
    repeat_floor = max(1, _historical_task_attempt_count(Path(runtime_root) / "attempts", task_id))
    telemetry["attempt_task_id"] = task_id
    telemetry["task_attempt"] = repeat_floor
    telemetry["attempt"] = repeat_floor
    return _record_external_condition_wait(
        telemetry, recovered, source_identity, now=now, repeat_floor=repeat_floor,
        task=task if isinstance(task, state.TaskRecord) else None,
    )


def _external_condition_wait_remaining(
    telemetry: dict[str, Any], task: state.TaskRecord | str, source_identity: str, *,
    now: datetime | None = None,
) -> float:
    blocker = telemetry.get("stable_blocker") if isinstance(telemetry.get("stable_blocker"), Mapping) else None
    task_id = task.id if isinstance(task, state.TaskRecord) else task
    if not blocker or blocker.get("task_id") != task_id:
        return 0.0
    if isinstance(task, state.TaskRecord) and not _task_bound_mapping_matches(task, blocker):
        telemetry["stable_blocker"] = None
        return 0.0
    if blocker.get("source_identity") != source_identity:
        telemetry["stable_blocker"] = None
        return 0.0
    try:
        retry_at = datetime.fromisoformat(str(blocker.get("retry_at")))
    except (TypeError, ValueError):
        telemetry["stable_blocker"] = None
        return 0.0
    observed = now or datetime.now(timezone.utc)
    return max(0.0, (retry_at - observed).total_seconds())

def _repo_condition_identity(repo_root: Path) -> str:
    head_probe = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True, capture_output=True, check=False
    )
    head = head_probe.stdout.strip() if head_probe.returncode == 0 else "NO_GIT_IDENTITY"
    remote_probe = subprocess.run(
        ["git", "-C", str(repo_root), "remote"], text=True, capture_output=True, check=False
    )
    remotes = remote_probe.stdout.splitlines() if remote_probe.returncode == 0 else []
    # Remote names are enough to invalidate the current no-origin blocker without persisting credential-bearing URLs.
    payload = {"head": head, "remote_names": sorted(name.strip() for name in remotes if name.strip())}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _is_stale_resume_error(detail: str) -> bool:
    text = str(detail or "")
    return any(marker in text for marker in (
        "ActiveTurnOutputSchemaMismatch",
        "ActiveTurnInputMismatch",
        "session not found",
        "thread not found",
        "no rollout found for thread id",
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


def _codex_pool_capacity_retry_at(returncode: int, detail: str, *, now: datetime | None = None) -> datetime | None:
    if int(returncode) != 78 or "minitz codex account pool" not in str(detail or "").lower():
        return None
    now = now or datetime.now(timezone.utc)
    state_path = Path(os.environ.get("MINITZ_CODEX_ACCOUNT_STATE", "/root/attached-storage/minitz-os-sandbox/state/credentials/codex-accounts/pool-state.json"))
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    candidates: list[datetime] = []
    for raw in (payload.get("cooldowns") or {}).values():
        try:
            target = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        if target > now:
            candidates.append(target)
    return min(candidates) if candidates else None


def _set_codex_pool_capacity_failure(telemetry: dict[str, Any], route: routing.Route, detail: str, task_id: str, retry_at: datetime) -> None:
    cooldowns = telemetry.setdefault("cooldowns", {})
    for model in routing.account_usage_cooldown_models(route.model):
        cooldowns[model] = retry_at.isoformat()
    telemetry["status"] = "RECOVERING_MODEL"
    telemetry.setdefault("coder_statuses", {})["codex"] = "CAPACITY_UNAVAILABLE"
    telemetry["last_result"] = {
        "task_id": task_id, "status": "MODEL_RECOVERY",
        "summary": str(detail)[-2000:], "evidence": [],
        "model": route.model, "reasoning": route.reasoning,
        "reason": "CODEX_ACCOUNT_POOL_CAPACITY_UNAVAILABLE",
        "retry_at": retry_at.isoformat(),
    }


def service_active() -> bool:
    return subprocess.run(["systemctl", "is-active", "--quiet", UNIT_NAME], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def _refresh_boost_fabric(runtime_root: Path) -> Path:
    current_path = Path(runtime_root) / "memory" / "boost-fabric" / "current.json"
    current = boost_fabric.read_json(current_path)
    program_path = minitz.program_path()
    if current_path.is_file() and program_path.is_file():
        try:
            observed_sha = minitz.file_sha256(program_path)
        except OSError:
            observed_sha = ""
        if observed_sha and str(current.get("source_program_sha256") or "") == observed_sha:
            return current_path
    program = minitz.load()
    _, current_path = boost_fabric.refresh_runtime(Path(runtime_root), program)
    return current_path


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
    runtime_root = Path(runtime_path).parent
    commander_index = commander.read_json(runtime_root / "memory" / "commander-fabric" / "current.json")
    current_task_id = str(production.current_task or telemetry.get("task_id") or "")
    task_capsule = commander.read_json(runtime_root / "task-memory" / f"{current_task_id}.json") if current_task_id else {}
    current_project_scope = commander.project_scope_id(task_capsule, project_root)
    if (
        commander_index.get("authority") != "NONE"
        or str(commander_index.get("project_scope") or "") != current_project_scope
        or str(commander_index.get("task_id") or "") != current_task_id
    ):
        commander_index = {
            "authority": "NONE", "project_scope": current_project_scope, "task_id": current_task_id,
            "total_lanes": commander.COMMANDER_LANE_COUNT, "lanes": [],
        }
    commander_summary = commander.public_summary(commander_index)
    if liveness == "STOPPED":
        stopped_lanes = []
        for raw in commander_summary.get("lanes", []):
            row = dict(raw)
            row["status"] = "OFFLINE"
            if row.get("activity") == "RUNNING":
                row["activity"] = "STOPPED"
            stopped_lanes.append(row)
        commander_summary = {**commander_summary, "status": "OFFLINE", "active": 0, "inflight": 0, "lanes": stopped_lanes}
    boost_index = boost_fabric.read_json(Path(runtime_path).parent / "memory" / "boost-fabric" / "current.json")
    if boost_index.get("authority") != "NONE" or boost_index.get("progression_authority") is not False or str(boost_index.get("current_task_id") or "") != current_task_id:
        boost_index = {"authority":"NONE","progression_authority":False,"current_task_id":current_task_id,"runtime_state":"ACTIVE","total_commanders":30,"boosts":[]}
    boost_summary = boost_fabric.control_summary(boost_index)
    return {
        "run_id": "minitz-production", "status": liveness,
        "current_section": production.current_section, "current_task": production.current_task,
        "completed": state.completed_count(production), "total": sum(len(s.tasks) for s in production.sections),
        "active_coder": telemetry.get("active_coder"),
        "main_coders": telemetry.get("coder_statuses") or {},
        "main_coder_detail": telemetry.get("coder_status_detail") or {},
        "commanders": commander_summary,
        "boosts": boost_summary,
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


def _observed_conflict_included(repo_root: Path, alignment: Mapping[str, Any], head: str) -> bool:
    """Resolve only an observed conflict whose two histories are in current HEAD.

    A transport outage is not remote freshness evidence. Unknown or unresolved
    conflicts remain blocking; resolved observations remain as provenance.
    """
    match = re.fullmatch(
        r"(?:local main diverged from origin/main|VPS source behind origin/main): "
        r"local ([0-9a-f]{40}), remote ([0-9a-f]{40})",
        str(alignment.get("detail", "")),
    )
    if match is None:
        return False
    try:
        return all(subprocess.run(
            ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", commit, head],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False,
        ).returncode == 0 for commit in match.groups())
    except (OSError, subprocess.TimeoutExpired):
        return False


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
            if _observed_conflict_included(repo_root, previous_alignment, head):
                telemetry["source_alignment"] = {
                    "state": "REMOTE_UNAVAILABLE_LOCAL_CONTINUATION", "commit": head, "tree": tree,
                    "detail": str(exc), "transport_state": "UNAVAILABLE",
                    "resolution": "BOTH_OBSERVED_COMMITS_INCLUDED_IN_CURRENT_HEAD",
                    "resolved_previous_alignment": previous_alignment,
                }
            else:
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
        reconcile_commander_rejection_evidence(runtime_root, journal)
        publication.start_worker(repo_root, failure_path=runtime_root / "failures.jsonl")
        telemetry = load_runtime(runtime_path)
        reconciled_cooldowns = routing.reconcile_legacy_account_cooldowns(telemetry.get("cooldowns", {}))
        if reconciled_cooldowns != dict(telemetry.get("cooldowns", {}) or {}):
            telemetry["cooldowns"] = reconciled_cooldowns
        telemetry.update({"status": "RUNNING", "project": "minitz", "pid": os.getpid(), "child_pid": None})
        journal.emit("production.started", task_id=telemetry.get("task_id"), status="RUNNING", text="MiniTZ production runner active")
        _beat(runtime_path, telemetry)
        catalog: Mapping[str, set[str]] | None = None
        peer_inflight: dict[str, MainCoderPeerHandle] = {}
        commander_inflight: dict[str, CommanderHandle] = {}
        booster_sync_handle: BoosterSyncHandle | None = None
        booster_sync_completed: set[str] = set()
        booster_sync_retry_after: dict[str, float] = {}
        booster_sync_failures: dict[str, int] = {}
        while True:
            _collect_main_coder_peer_assists(peer_inflight, telemetry, journal)
            _collect_commander_assists_nonblocking(runtime_root, commander_inflight, journal)
            _ensure_local_qwen_ready(telemetry, journal, telemetry.get("task_id"), blocking=False)
            if _shutdown_requested.is_set():
                return 0
            if not _guard_source_alignment(repo_root, runtime_path, telemetry, journal):
                return SOURCE_REFRESH_EXIT
            if state._use_minitz_project(Path(project_root)):
                material = completion_truth.reconcile_material_truth(
                    repo_root, Path(os.environ.get("MINITZ_OS_SANDBOX_ROOT", str(Path(repo_root).resolve().parents[1])))
                )
                if material.get("changed"):
                    telemetry["stable_blocker"] = None
                    journal.emit(
                        "task.material_truth_reconciled", task_id=material.get("reopened_from"), status="REOPENED",
                        text=f"Invalid final-horizon material truth reopened from {material.get('reopened_from')}; valid prefix preserved.",
                        artifact_state=material.get("artifact_state"),
                    )
                booster_sync_handle = _maybe_start_booster_autosync(
                    repo_root, runtime_root, booster_sync_handle, booster_sync_completed, booster_sync_retry_after, journal,
                    failure_counts=booster_sync_failures,
                )
            if catalog is None:
                catalog = _discover_runtime_catalog(runtime_root)
            production = state.sync_project_metadata(project_root)
            telemetry["priority_policy"] = production.priority_policy
            task = state.resolve_current_task(repo_root, project_root)
            if production.run_id == "minitz-task-program":
                _refresh_boost_fabric(runtime_root)
            if task is None:
                production = state.load_project_production(project_root)
                section = _first_incomplete_section(production)
                if section is None:
                    if os.environ.get("MINITZ_CONTINUOUS_IDLE", "0") != "1":
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
                        "schema": "minitz.opportunity_discovery/v1",
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
                planner_coder, route = _select_main_coder_class_route("deep_memory", catalog, telemetry, now)
                if route is None or planner_coder is None:
                    telemetry.update({"status": "RECOVERING_MODEL", "task_id": f"PLAN:{section.id}", "active_model": None, "active_reasoning": None})
                    _beat(runtime_path, telemetry)
                    time.sleep(min(5.0, max(0.5, routing.earliest_cooldown_delay(telemetry.get("cooldowns", {}), now))))
                    catalog = _discover_runtime_catalog(runtime_root)
                    continue
                if _remote_writer_requires_local_qwen(planner_coder, route) and not _ensure_local_qwen_ready(telemetry, journal, f"PLAN:{section.id}"):
                    telemetry.update({
                        "status": "RECOVERING_LOCAL_QWEN", "task_id": f"PLAN:{section.id}",
                        "child_pid": None, "active_model": None, "active_reasoning": None,
                    })
                    _beat(runtime_path, telemetry)
                    time.sleep(1.0)
                    continue
                telemetry.update({
                    "status": "RUNNING", "task_id": f"PLAN:{section.id}", "active_coder": planner_coder,
                    "active_model": route.model, "active_reasoning": route.reasoning,
                })
                _beat(runtime_path, telemetry)
                output, stdout, stderr = _attempt_paths(runtime_root, telemetry, f"PLAN-{section.id}-{route.model}", task_id=f"PLAN:{section.id}")
                section_prompt = packets.compile_section_packet(production, section, audit=bool(section.tasks))
                policy_root = repo_root if state._use_minitz_project(Path(project_root)) else project_root
                policies = main_coder.shared_policy_paths(repo_root, policy_root)
                section_prompt = (
                    f"MAIN_CODER_BACKEND: {planner_coder}\n"
                    + "".join(f"SHARED_POLICY: {policy}\n" for policy in policies)
                    + "Same MiniTZ authority, memory, cache, validation and no-replay rules apply regardless of backend.\n"
                    + section_prompt
                )
                planner_session = _resume_session_for(telemetry, f"PLAN:{section.id}", coder_id=planner_coder)
                rc, error_text = invoke_structured(
                    section_prompt, route, section_schema_path, output, stdout, stderr, runtime_path, telemetry,
                    heartbeat_interval=heartbeat_interval, cwd=project_root, resume_session_id=planner_session,
                    session_task_id=f"PLAN:{section.id}", event_journal=journal,
                )
                if rc == 0:
                    telemetry.setdefault("coder_statuses", {})["codex"] = "ACTIVE"
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
                telemetry["last_result"] = {"task_id": None, "status": "SECTION_REFRESH", "summary": str(plan.get("summary", "")), "evidence": list(plan.get("evidence", [])), "coder": planner_coder, "model": route.model, "reasoning": route.reasoning}
                _beat(runtime_path, telemetry); continue
            source_condition_identity = _repo_condition_identity(repo_root)
            _seed_external_condition_wait_from_last_result(
                telemetry, task, source_condition_identity, runtime_root
            )
            wait_remaining = _external_condition_wait_remaining(telemetry, task, source_condition_identity)
            if wait_remaining > 0:
                telemetry.update({
                    "status": "WAITING_FOR_CONDITION", "task_id": task.id, "child_pid": None,
                    "active_model": None, "active_reasoning": None,
                })
                _beat(runtime_path, telemetry)
                time.sleep(min(5.0, wait_remaining))
                continue
            if _defer_resource_blocker(repo_root, project_root, production, task, telemetry, journal, runtime_path):
                continue
            now = datetime.now(timezone.utc)
            coder_id, route, bounded_packet_id, peer_coder = _select_main_task_route(
                task, catalog, telemetry, now, repo_root, project_root
            )
            if route is None or coder_id is None:
                telemetry.update({"status": "RECOVERING_MODEL", "task_id": task.id, "active_model": None, "active_reasoning": None})
                _beat(runtime_path, telemetry)
                time.sleep(2.0)
                catalog = _discover_runtime_catalog(runtime_root)
                continue
            remote_qwen_guard = _remote_writer_requires_local_qwen(coder_id, route)
            if remote_qwen_guard and not _ensure_local_qwen_ready(telemetry, journal, task.id):
                telemetry.update({
                    "status": "RECOVERING_LOCAL_QWEN", "task_id": task.id, "child_pid": None,
                    "active_model": None, "active_reasoning": None,
                })
                _beat(runtime_path, telemetry)
                time.sleep(1.0)
                continue
            if production.run_id == "minitz-task-program":
                task = _ensure_minitz_writer_claim(repo_root, project_root, task, journal)
                production = state.load_project_production(project_root)
                _refresh_boost_fabric(runtime_root)
            bounded_fallback = coder_id == "codex" and routing.is_bounded_fallback(route)
            execution_coder = "local-qwen" if bounded_fallback else coder_id
            if task.task_class == "simple" and bounded_packet_id and bounded_fallback:
                _record_simple_helper_attempt(telemetry, task.id, bounded_packet_id, route)
            telemetry.update({
                "status": "RUNNING", "task_id": task.id, "active_coder": execution_coder,
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
            output, stdout, stderr = _attempt_paths(runtime_root, telemetry, f"{task.id}-{route.model}", task_id=task.id)
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

            def observe_task_and_helpers(_at=None):
                nonlocal current_owned, commander_index_path
                observe_activity(_at)
                if remote_qwen_guard:
                    _ensure_local_qwen_ready(telemetry, journal, task.id, blocking=False)
                commander_index_path = _refresh_commander_assists_during_task(
                    repo_root, project_root, runtime_root, task, task_state_digest,
                    capsule_path, projection_path, commander_inflight, journal,
                )

            project_scope = commander.project_scope_id(capsule_data, project_root)
            peer_assist_path = _latest_main_coder_peer_assist(runtime_root, project_scope, task.id, task_state_digest)
            dispatch_peer = peer_coder
            peer_route = _select_main_coder_peer_route(
                dispatch_peer, task, catalog, telemetry, now, repo_root, project_root
            )
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
                commander_index_path=commander_index_path, coder_id=execution_coder
            )
            resume_session_id = _resume_session_for_route(telemetry, task.id, route, coder_id=coder_id)
            event_type = "task.bounded_fallback_started" if bounded_fallback else ("task.continued" if _task_has_shared_continuity(telemetry, task.id, capsule_path) else "task.started")
            journal.emit(
                event_type, task_id=task.id, status="RUNNING", text=task.title,
                model=route.model, reasoning=route.reasoning, coder=execution_coder,
                peer_coder=peer_coder, bounded_packet_id=bounded_packet_id,
            )
            if production.run_id == "minitz-task-program":
                schema_path.write_text(json.dumps(evidence.result_schema(task.id), sort_keys=True) + "\n", encoding="utf-8")
            rc, error_text = invoke_structured(
                prompt, route, schema_path, output, stdout, stderr, runtime_path, telemetry,
                heartbeat_interval=heartbeat_interval, on_heartbeat=observe_task_and_helpers, cwd=_task_working_directory(repo_root, project_root, task.id),
                resume_session_id=resume_session_id, session_task_id=task.id,
                allow_helper=False if bounded_fallback else _helper_allowed(task.id),
                persist_session_identity=not bounded_fallback,
                event_journal=journal,
            )
            if rc == 0 and not bounded_fallback:
                telemetry.setdefault("coder_statuses", {})["codex"] = "ACTIVE"
            if rc != 0:
                pool_retry_at = _codex_pool_capacity_retry_at(rc, error_text)
                if pool_retry_at is not None:
                    _set_codex_pool_capacity_failure(telemetry, route, error_text, task.id, pool_retry_at)
                    journal.emit(
                        "resource.codex_capacity_unavailable", task_id=task.id, status="DEFERRED_TO_ALTERNATE",
                        text=error_text[-1200:], coder="codex", model=route.model, retry_at=pool_retry_at.isoformat(),
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
                _set_failure(telemetry, route, str(exc), task.id)
                _beat(runtime_path, telemetry); continue
            result = _normalize_result_for_route(
                result, route, allow_minitz_validated_completion=production.run_id == "minitz-task-program",
                repo_root=repo_root,
                sandbox_root=Path(os.environ.get("MINITZ_OS_SANDBOX_ROOT", str(Path(repo_root).resolve().parents[1]))),
            )
            observe_activity()
            result = evidence.enforce_clean_completion_boundary(repo_root, result, owned_files=current_owned)
            telemetry["last_result"] = _task_bound_runtime_result(
                task, result, coder=execution_coder, model=route.model, reasoning=route.reasoning,
            )
            _write_task_capsule(repo_root, project_root, runtime_root, task, telemetry)
            _refresh_memory_projection(repo_root, project_root, runtime_root, task.id, journal)
            try:
                evidence.apply_result(repo_root, project_root, result, route)
            except Exception as exc:
                telemetry["status"] = "RECOVERING_INTERNAL"
                telemetry["last_result"] = _bind_task_identity(task, {
                    "task_id": task.id, "status": "RECOVERING_INTERNAL", "summary": str(exc),
                    "evidence": list(result.evidence), "model": route.model, "reasoning": route.reasoning,
                })
                _beat(runtime_path, telemetry); time.sleep(1.0); continue
            if result.status in {"COMPLETE", "COMPLETE_ALREADY"}:
                telemetry["stable_blocker"] = None
                _clear_task_session(telemetry)
                _refresh_memory_projection(repo_root, project_root, runtime_root, result.task_id, journal)
                _persist_until_success(repo_root, result.task_id, runtime_path, telemetry, event_journal=journal)
            elif _record_external_condition_wait(
                telemetry, result, _repo_condition_identity(repo_root),
                repeat_floor=max(1, _historical_task_attempt_count(runtime_root / "attempts", task.id)), task=task,
            ):
                blocker = telemetry.get("stable_blocker") or {}
                journal.emit(
                    "task.external_condition_wait", task_id=result.task_id, status="WAITING_FOR_CONDITION",
                    text="Unchanged external blocker persisted; equivalent model execution suppressed until retry/change.",
                    retry_at=blocker.get("retry_at"), repeat_count=blocker.get("repeat_count"),
                )
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
    return Path(os.environ.get("MINITZ_SOURCE_ROOT") or os.environ.get("MINITZ_REPO_ROOT") or _REPO_ROOT)


def default_project_root(repo_root: Path | None = None) -> Path:
    repo = repo_root or default_repo_root()
    return Path(os.environ.get("MINITZ_PROJECT_ROOT", str(repo)))


def default_runtime_root() -> Path:
    return Path(os.environ.get("MINITZ_RUNTIME_ROOT", "/root/attached-storage/minitz-os-sandbox/state/production"))


def start_production(repo_root: Path, project_root: Path, runtime_root: Path) -> int:
    if service_active():
        print(json.dumps({"unit": UNIT_NAME, "status": "ALREADY_RUNNING"}, sort_keys=True)); return 0
    if state._use_minitz_project(Path(project_root)):
        completion_truth.reconcile_material_truth(
            repo_root, Path(os.environ.get("MINITZ_OS_SANDBOX_ROOT", str(Path(repo_root).resolve().parents[1])))
        )
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
    if canonical == completion_truth.OWNER_ACCEPTANCE:
        evidence_items = completion_truth.owner_acceptance_evidence(
            repo_root, Path(os.environ.get("MINITZ_OS_SANDBOX_ROOT", str(repo_root.resolve().parents[1]))), evidence_items
        )
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
    parser = argparse.ArgumentParser(prog="minitz-codex production")
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
        _shutdown_requested.clear()
        import signal
        signal.signal(signal.SIGTERM, _request_graceful_shutdown)
        signal.signal(signal.SIGINT, _request_graceful_shutdown)
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
