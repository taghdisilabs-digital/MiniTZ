"""Single authoritative MiniTZ Task Program adapter.

The living JSON at TASK_PROGRAM_PATH is the only task-order/status/progression
source used by the production runner.  All other ledgers/maps are derived
in-memory projections and have no mutation authority.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_TASK_PROGRAM_PATH = Path("/root/biella/analysis/live_audit/TASK_PROGRAM.json")
ACTIVE_STATUSES = {"PENDING", "DEFERRED", "IN_PROGRESS", "REQUIRES_OTHER_RESOURCE"}
COMPLETE_STATUSES = {"COMPLETE", "COMPLETE_ALREADY", "COMPLETED", "DUPLICATE", "OBSOLETE", "RETIRED", "SUPERSEDED"}
DEPENDENCY_TYPES = (
    "HARD", "FAMILY_LOCAL", "RECOMMENDED_ORDER", "NONBLOCKING_INPUT",
    "OPTIONAL_EVIDENCE", "CONFLICTS_WITH", "TOUCHES_SAME_AUTHORITY",
    "SUPERSEDES", "DERIVES_FROM",
)


def program_path() -> Path:
    raw = os.environ.get("MINITZ_TASK_PROGRAM_PATH")
    return Path(raw).expanduser().resolve() if raw else DEFAULT_TASK_PROGRAM_PATH


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def task_digest(task: Mapping[str, Any]) -> str:
    return digest({key: value for key, value in task.items() if key != "task_record_sha256"})


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(path: Path | None = None) -> dict[str, Any]:
    path = Path(path or program_path()).resolve()
    raw = path.read_bytes()
    program = json.loads(raw)
    _need(isinstance(program, dict), "MiniTZ Task Program must be an object")
    _need(program.get("schema") == "minitz.living_task_program/v1", "unexpected MiniTZ Task Program schema")
    _need(program.get("program_id") == "MINITZ_REBORN_SINGLE_TASK_PROGRAM", "unexpected MiniTZ program identity")
    _need(program.get("single_transformation_lineage") is True, "competing task-program lineage")
    _need(program.get("intended_final_task_program_count") == 1, "MiniTZ requires exactly one task program")
    _need(program.get("task_program_authority") is True, "MiniTZ task-program authority is not active")
    _need(program.get("production_execution_authority") is True, "MiniTZ execution authority is not active")
    _need(program.get("production_order_status_authority") is True, "MiniTZ order/status authority is not active")
    _need(str(program.get("current_live_production_authority")) == str(path), "MiniTZ live authority path mismatch")
    _need(program.get("dependency_types") == list(DEPENDENCY_TYPES), "MiniTZ dependency enum mismatch")
    tasks = program.get("tasks")
    _need(isinstance(tasks, list) and program.get("task_count") == len(tasks), "MiniTZ task count mismatch")
    ids = [task.get("task_id") for task in tasks if isinstance(task, dict)]
    _need(len(ids) == len(tasks) and len(ids) == len(set(ids)) and all(isinstance(x, str) and x for x in ids), "invalid MiniTZ task identities")
    valid_statuses = ACTIVE_STATUSES | COMPLETE_STATUSES
    for task in tasks:
        _need(task.get("status") in valid_statuses, f"unsupported MiniTZ task status: {task.get('status')}")
        _need(task.get("task_record_sha256") == task_digest(task), f"MiniTZ task digest mismatch: {task.get('task_id')}")
        deps = task.get("dependencies")
        _need(isinstance(deps, list), f"MiniTZ task dependencies missing: {task.get('task_id')}")
        for dep in deps:
            _need(isinstance(dep, dict) and dep.get("dependency_type") in DEPENDENCY_TYPES and dep.get("task_ref") in ids and dep.get("task_ref") != task.get("task_id"), f"invalid MiniTZ dependency: {task.get('task_id')}")
        if task.get("status") in ACTIVE_STATUSES:
            _need(task.get("active_task_survival") is True, f"active MiniTZ task lacks survival gate: {task.get('task_id')}")
            _need(task.get("review_state") == "VALUE_GATE_PASSED", f"active MiniTZ task lacks value gate: {task.get('task_id')}")
    execution = program.get("current_execution")
    if isinstance(execution, dict) and execution.get("task_id"):
        matches = [task for task in tasks if task["task_id"] == execution["task_id"]]
        _need(len(matches) == 1, "current MiniTZ task is absent")
        task = matches[0]
        _need(execution.get("task_revision") == task.get("revision"), "current MiniTZ task revision mismatch")
        _need(execution.get("task_sha256") == task_digest(task), "current MiniTZ task digest mismatch")
    program["_observed_sha256"] = hashlib.sha256(raw).hexdigest()
    program["_observed_path"] = str(path)
    return program


def public_program(program: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in program.items() if not key.startswith("_observed_")}


def program_identity(program: Mapping[str, Any] | None = None) -> dict[str, Any]:
    program = dict(program or load())
    return {
        "path": str(program.get("_observed_path") or program_path()),
        "program_id": program["program_id"],
        "revision": program["revision"],
        "task_count": program["task_count"],
        "sha256": str(program.get("_observed_sha256") or file_sha256(program_path())),
    }


def task_by_id(program: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    for task in program["tasks"]:
        if task["task_id"] == task_id:
            return task
    raise KeyError(task_id)


def hard_dependencies(task: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(dep["task_ref"] for dep in task.get("dependencies", []) if dep.get("dependency_type") == "HARD")


def runnable(program: Mapping[str, Any], task: Mapping[str, Any]) -> bool:
    if task.get("status") not in ACTIVE_STATUSES:
        return False
    completed = {row["task_id"] for row in program["tasks"] if row.get("status") in COMPLETE_STATUSES}
    return set(hard_dependencies(task)).issubset(completed)


def executable_scope(task: Mapping[str, Any]) -> Mapping[str, Any]:
    scope = task.get("write_scope")
    _need(isinstance(scope, dict), f"current MiniTZ task lacks explicit write scope: {task.get('task_id')}")
    _need(scope.get("authority") in {"TASK_OWNED_ONLY", "READ_ONLY"}, f"current MiniTZ task lacks bounded authority: {task.get('task_id')}")
    paths = scope.get("allowed_paths")
    _need(isinstance(paths, list), f"current MiniTZ task lacks bounded paths: {task.get('task_id')}")
    _need(bool(paths) or scope.get("authority") == "READ_ONLY", f"current MiniTZ task lacks bounded paths: {task.get('task_id')}")
    return scope


def current_task(program: Mapping[str, Any]) -> dict[str, Any] | None:
    execution = program.get("current_execution")
    if isinstance(execution, dict) and execution.get("task_id"):
        task = task_by_id(program, execution["task_id"])
        if runnable(program, task):
            executable_scope(task)
            return task
    task = next((task for task in program["tasks"] if runnable(program, task)), None)
    if task is not None:
        executable_scope(task)
        return task
    active = [row["task_id"] for row in program["tasks"] if row.get("status") in ACTIVE_STATUSES]
    _need(not active, "active MiniTZ tasks exist but none is runnable: " + ",".join(active))
    return None


def task_class(program: Mapping[str, Any], task: Mapping[str, Any]) -> str:
    plan = (program.get("logic_first_execution_plan") or {}).get(task["task_id"], {})
    profile = str(plan.get("resource_profile", "")).upper()
    kind = str(plan.get("work_kind", "")).upper()
    combined = profile + " " + kind + " " + str(task.get("scope", "")).upper()
    if "CREATION" in combined or "GRAPHICAL" in combined or "UNREAL" in combined:
        return "hard_creation"
    if "VERY_HIGH" in profile or "DEEP" in combined:
        return "deep_memory"
    if "HIGH" in profile or "GPU" in profile:
        return "hard"
    return "medium"


def task_lane(program: Mapping[str, Any], task: Mapping[str, Any]) -> str:
    root = str((task.get("write_scope") or {}).get("execution_root", ""))
    if "/projects/biella-games" in root:
        return "Games"
    if root.endswith("/website") or "/website/" in root:
        return "Website"
    if root.startswith("/root/biella/analysis"):
        return "Analysis"
    return "Engine"


def execution_root(task: Mapping[str, Any]) -> Path:
    scope = executable_scope(task)
    root = Path(str(scope.get("execution_root", "")))
    _need(root.is_absolute(), f"MiniTZ task has no absolute execution root: {task.get('task_id')}")
    return root.resolve()


def _execution_pointer(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "task_revision": task["revision"],
        "task_sha256": task_digest(task),
        "run_ref": None,
        "session_ref": None,
        "run_state_ref": None,
    }


@contextmanager
def _locked(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, program: Mapping[str, Any]) -> str:
    data = json.dumps(public_program(program), indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        tmp.unlink(missing_ok=True)
    return hashlib.sha256(data.encode()).hexdigest()


def _transaction(program: dict[str, Any], *, prior_revision: int, prior_sha: str, action: str, evidence: Sequence[str]) -> None:
    fact = {"action": action, "evidence": list(evidence), "previous_program_revision": prior_revision, "previous_program_sha256": prior_sha}
    program["transaction"] = {
        "previous_program_revision": prior_revision,
        "previous_program_sha256": prior_sha,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "transaction_id": f"MINITZ::{action}::{digest(fact)}",
        "validation_receipt_sha256": digest(fact),
    }



def _normalized_insert_task(raw: Mapping[str, Any]) -> dict[str, Any]:
    task = dict(raw)
    task_id = str(task.get("task_id") or "").strip()
    _need(bool(task_id), "inserted MiniTZ task requires task_id")
    task["task_id"] = task_id
    task["revision"] = int(task.get("revision") or 1)
    _need(task["revision"] >= 1, "inserted MiniTZ task revision must be positive")
    task["status"] = str(task.get("status") or "PENDING")
    _need(task["status"] in ACTIVE_STATUSES, "inserted MiniTZ task must be active")
    _need(task.get("active_task_survival") is True, "inserted MiniTZ task requires survival gate")
    _need(task.get("review_state") == "VALUE_GATE_PASSED", "inserted MiniTZ task requires value gate")
    _need(isinstance(task.get("dependencies"), list), "inserted MiniTZ task requires dependencies")
    executable_scope(task)
    task["task_record_sha256"] = task_digest(task)
    return task


def insert_tasks_after(after_task_id: str, tasks: Sequence[Mapping[str, Any]], *, evidence: Sequence[str], path: Path | None = None) -> dict[str, Any]:
    clean_evidence = [str(item).strip() for item in evidence if str(item).strip()]
    _need(bool(clean_evidence), "MiniTZ task-program evolution requires evidence")
    normalized = [_normalized_insert_task(task) for task in tasks]
    _need(bool(normalized), "MiniTZ task-program evolution requires tasks")
    new_ids = [task["task_id"] for task in normalized]
    _need(len(new_ids) == len(set(new_ids)), "duplicate inserted MiniTZ task identity")
    path = Path(path or program_path()).resolve()
    with _locked(path):
        program = load(path)
        prior_sha = program["_observed_sha256"]
        prior_revision = int(program["revision"])
        existing = {row["task_id"]: row for row in program["tasks"]}
        overlap = [task_id for task_id in new_ids if task_id in existing]
        if overlap:
            _need(set(overlap) == set(new_ids), "partial MiniTZ task-program extension already exists")
            for task in normalized:
                _need(existing[task["task_id"]] == task, f"conflicting existing MiniTZ task: {task['task_id']}")
            return program_identity(program)
        _need(after_task_id in existing, "MiniTZ task-program insertion anchor is absent")
        combined_ids = set(existing) | set(new_ids)
        for task in normalized:
            for dep in task["dependencies"]:
                _need(isinstance(dep, dict) and dep.get("dependency_type") in DEPENDENCY_TYPES, f"invalid inserted MiniTZ dependency: {task['task_id']}")
                ref = str(dep.get("task_ref") or "")
                _need(ref in combined_ids and ref != task["task_id"], f"invalid inserted MiniTZ dependency: {task['task_id']}")
        rows = list(program["tasks"])
        anchor = next(index for index, row in enumerate(rows) if row["task_id"] == after_task_id)
        rows[anchor + 1:anchor + 1] = normalized
        program["tasks"] = rows
        program["task_count"] = len(rows)
        program["revision"] = prior_revision + 1
        _transaction(program, prior_revision=prior_revision, prior_sha=prior_sha, action="EVOLVE::INSERT::" + ",".join(new_ids), evidence=clean_evidence)
        new_sha = _atomic_write(path, program)
    observed = load(path)
    _need(observed["_observed_sha256"] == new_sha, "MiniTZ task-program evolution readback mismatch")
    return program_identity(observed)

def complete_task(task_id: str, status: str, evidence: Sequence[str], *, path: Path | None = None) -> dict[str, Any]:
    _need(status in {"COMPLETE", "COMPLETE_ALREADY"}, "completion status required")
    clean_evidence = [str(item).strip() for item in evidence if str(item).strip()]
    _need(bool(clean_evidence), "MiniTZ completion requires evidence")
    path = Path(path or program_path()).resolve()
    with _locked(path):
        program = load(path); prior_sha = program["_observed_sha256"]; prior_revision = int(program["revision"])
        task = task_by_id(program, task_id)
        if task.get("status") in COMPLETE_STATUSES:
            return program_identity(program)
        _need(task.get("status") in ACTIVE_STATUSES, "MiniTZ task is not active")
        task["revision"] = int(task["revision"]) + 1
        task["status"] = status
        task["active_task_survival"] = False
        task["completion"] = {
            "status": status,
            "evidence": clean_evidence,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        task["task_record_sha256"] = task_digest(task)
        program["revision"] = prior_revision + 1
        successor = next((row for row in program["tasks"] if runnable(program, row)), None)
        program["current_execution"] = _execution_pointer(successor) if successor else None
        _transaction(program, prior_revision=prior_revision, prior_sha=prior_sha, action=f"COMPLETE::{task_id}", evidence=clean_evidence)
        new_sha = _atomic_write(path, program)
    observed = load(path)
    _need(observed["_observed_sha256"] == new_sha, "MiniTZ completion readback mismatch")
    return program_identity(observed)


def defer_task_after(task_id: str, after_task_id: str, *, reason: str, path: Path | None = None) -> dict[str, Any]:
    _need(bool(str(reason).strip()), "deferral reason required")
    path = Path(path or program_path()).resolve()
    with _locked(path):
        program = load(path); prior_sha = program["_observed_sha256"]; prior_revision = int(program["revision"])
        tasks = list(program["tasks"])
        ids = [row["task_id"] for row in tasks]
        _need(task_id in ids and after_task_id in ids and task_id != after_task_id, "invalid MiniTZ deferral identities")
        moving = tasks.pop(ids.index(task_id))
        _need(moving.get("status") in ACTIVE_STATUSES, "only an active MiniTZ task can be deferred")
        index = next(i for i, row in enumerate(tasks) if row["task_id"] == after_task_id)
        tasks.insert(index + 1, moving)
        program["tasks"] = tasks
        program["revision"] = prior_revision + 1
        successor = next((row for row in tasks if runnable(program, row)), None)
        program["current_execution"] = _execution_pointer(successor) if successor else None
        _transaction(program, prior_revision=prior_revision, prior_sha=prior_sha, action=f"DEFER::{task_id}::AFTER::{after_task_id}", evidence=[reason])
        new_sha = _atomic_write(path, program)
    observed = load(path)
    _need(observed["_observed_sha256"] == new_sha, "MiniTZ deferral readback mismatch")
    return program_identity(observed)
