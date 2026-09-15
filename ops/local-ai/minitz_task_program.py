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

DEFAULT_TASK_PROGRAM_PATH = Path("/root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json")
ACTIVE_STATUSES = {"PENDING", "WORKING", "DEFERRED", "IN_PROGRESS", "REQUIRES_OTHER_RESOURCE"}
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


VOLATILE_TASK_FIELDS = {"task_record_sha256", "workers", "worker_state_sha256", "worker_history"}


def task_digest(task: Mapping[str, Any]) -> str:
    return digest({key: value for key, value in task.items() if key not in VOLATILE_TASK_FIELDS})


def _first_active_row(program: Mapping[str, Any]) -> dict[str, Any] | None:
    tasks = program.get("tasks") if isinstance(program.get("tasks"), list) else []
    active = [row for row in tasks if isinstance(row, dict) and row.get("status") in ACTIVE_STATUSES]
    working = [row for row in active if row.get("status") == "WORKING"]
    _need(len(working) <= 1, "MiniTZ permits at most one WORKING task")
    if not active:
        return None
    first = active[0]
    if working and working[0].get("task_id") != first.get("task_id"):
        raise ValueError("MiniTZ WORKING task is not the first active task")
    return first


def _derived_execution_pointer(task: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if task is None:
        return None
    return {
        "task_id": task["task_id"],
        "task_revision": task["revision"],
        "task_sha256": task_digest(task),
        "run_ref": None,
        "session_ref": None,
        "run_state_ref": None,
    }


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
    # Persisted current-task pointers are legacy compatibility only.  Array order
    # plus tasks[].status is the sole task/order/status authority.
    first_active = _first_active_row(program)
    program["current_execution"] = _derived_execution_pointer(first_active)
    program["_observed_sha256"] = hashlib.sha256(raw).hexdigest()
    program["_observed_path"] = str(path)
    return program


def public_program(program: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in program.items()
        if not key.startswith("_observed_") and key not in {"current_execution", "frozen_current_task"}
    }


def program_identity(program: Mapping[str, Any] | None = None) -> dict[str, Any]:
    program = dict(program or load())
    return {
        "path": str(program.get("_observed_path") or program_path()),
        "program_id": program["program_id"],
        "revision": program["revision"],
        "task_count": program["task_count"],
        "sha256": str(program.get("_observed_sha256") or file_sha256(program_path())),
    }


def task_context_payload(task: Mapping[str, Any]) -> dict[str, Any]:
    policy = task.get("context_policy") if isinstance(task.get("context_policy"), Mapping) else {}
    mode = str(policy.get("mode") or "TASK_LOCAL_MINIMUM")
    _need(mode == "TASK_LOCAL_MINIMUM", f"unsupported MiniTZ task context mode: {mode}")
    fields = policy.get("default_fields")
    if not isinstance(fields, list) or not fields:
        fields = [
            "task_id", "revision", "status", "title", "scope", "objective", "dependencies",
            "procedure", "inputs", "source_refs", "deliverables", "required_capabilities",
            "resource_requirements", "write_scope", "validation", "acceptance",
            "negative_controls", "required_evidence", "workers", "completion",
        ]
    payload = {str(key): task[key] for key in fields if isinstance(key, str) and key in task}
    payload["context_policy"] = dict(policy) if policy else {
        "mode": "TASK_LOCAL_MINIMUM",
        "target_token_budget": 12000,
        "hard_token_limit": 32000,
    }
    hard_limit = payload["context_policy"].get("hard_token_limit", 32000)
    _need(isinstance(hard_limit, int) and not isinstance(hard_limit, bool) and hard_limit > 0,
          "MiniTZ task context hard_token_limit must be a positive integer")
    # Conservative UTF-8/JSON bound: four encoded characters per requested token.
    _need(len(encoded(payload)) <= hard_limit * 4, f"MiniTZ task context exceeds hard token budget: {task.get('task_id')}")
    return payload


def task_by_id(program: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    for task in program["tasks"]:
        if task["task_id"] == task_id:
            return task
    raise KeyError(task_id)


def hard_dependencies(task: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(dep["task_ref"] for dep in task.get("dependencies", []) if dep.get("dependency_type") == "HARD")


def runnable(program: Mapping[str, Any], task: Mapping[str, Any]) -> bool:
    first = _first_active_row(program)
    if first is None or task.get("task_id") != first.get("task_id"):
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
    task = _first_active_row(program)
    if task is None:
        return None
    completed = {row["task_id"] for row in program["tasks"] if row.get("status") in COMPLETE_STATUSES}
    missing = [dep for dep in hard_dependencies(task) if dep not in completed]
    if missing:
        raise ValueError(
            "first active MiniTZ task is blocked: " + str(task.get("task_id"))
            + " missing=" + ",".join(missing)
        )
    executable_scope(task)
    return task


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
    if "/projects/minitz-games" in root:
        return "Games"
    if root.endswith("/website") or "/website/" in root:
        return "Website"
    return "Engine"


def execution_root(task: Mapping[str, Any]) -> Path:
    scope = executable_scope(task)
    root = Path(str(scope.get("execution_root", "")))
    _need(root.is_absolute(), f"MiniTZ task has no absolute execution root: {task.get('task_id')}")
    return root.resolve()


def _execution_pointer(task: Mapping[str, Any]) -> dict[str, Any]:
    return dict(_derived_execution_pointer(task) or {})


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
        "transaction_sha256": digest(fact),
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

def rewrite_future_horizon(
    after_task_id: str, future_tasks: Sequence[Mapping[str, Any]], *,
    program_updates: Mapping[str, Any] | None, evidence: Sequence[str],
    path: Path | None = None,
) -> dict[str, Any]:
    clean_evidence = [str(item).strip() for item in evidence if str(item).strip()]
    _need(bool(clean_evidence), "MiniTZ future-horizon rewrite requires evidence")
    path = Path(path or program_path()).resolve()
    with _locked(path):
        program = load(path)
        prior_sha = program["_observed_sha256"]; prior_revision = int(program["revision"])
        rows = list(program["tasks"])
        ids = [row["task_id"] for row in rows]
        _need(after_task_id in ids, "MiniTZ future-horizon anchor is absent")
        anchor = ids.index(after_task_id)
        prefix = rows[: anchor + 1]
        anchor_before = dict(prefix[-1])
        prefix_ids = {row["task_id"] for row in prefix}
        rewritten: list[dict[str, Any]] = []
        seen = set(prefix_ids)
        valid_statuses = ACTIVE_STATUSES | COMPLETE_STATUSES
        for raw in future_tasks:
            task = dict(raw)
            task_id = str(task.get("task_id") or "").strip()
            _need(bool(task_id) and task_id not in seen, f"invalid/duplicate future MiniTZ task: {task_id}")
            seen.add(task_id); task["task_id"] = task_id
            _need(task.get("status") in valid_statuses, f"unsupported future MiniTZ task status: {task_id}")
            _need(isinstance(task.get("dependencies"), list), f"future MiniTZ task dependencies missing: {task_id}")
            if task.get("status") in ACTIVE_STATUSES:
                _need(task.get("active_task_survival") is True, f"future MiniTZ task lacks survival gate: {task_id}")
                executable_scope(task)
            task["task_record_sha256"] = task_digest(task)
            rewritten.append(task)
        combined = prefix + rewritten
        combined_ids = {row["task_id"] for row in combined}
        for task in combined:
            for dep in task.get("dependencies", []):
                _need(
                    isinstance(dep, dict)
                    and dep.get("dependency_type") in DEPENDENCY_TYPES
                    and dep.get("task_ref") in combined_ids
                    and dep.get("task_ref") != task.get("task_id"),
                    f"invalid MiniTZ dependency after future rewrite: {task.get('task_id')}",
                )
        protected = {
            "schema", "program_id", "tasks", "task_count", "revision",
            "current_execution", "single_transformation_lineage",
            "task_program_authority", "production_execution_authority",
            "production_order_status_authority", "current_live_production_authority",
        }
        for key, value in dict(program_updates or {}).items():
            _need(key not in protected, f"protected MiniTZ program field cannot be rewritten: {key}")
            program[key] = value
        program["tasks"] = combined
        program["task_count"] = len(combined)
        program["revision"] = prior_revision + 1
        _transaction(
            program, prior_revision=prior_revision, prior_sha=prior_sha,
            action=f"EVOLVE::FUTURE_HORIZON_AFTER::{after_task_id}", evidence=clean_evidence,
        )
        new_sha = _atomic_write(path, program)
    observed = load(path)
    _need(observed["_observed_sha256"] == new_sha, "MiniTZ future-horizon rewrite readback mismatch")
    _need(task_by_id(observed, after_task_id) == anchor_before, "MiniTZ future-horizon rewrite changed the preserved anchor")
    return program_identity(observed)


def claim_task(
    task_id: str, *, worker_id: str, worker_role: str, write_authority: bool,
    evidence: Sequence[str], path: Path | None = None,
) -> dict[str, Any]:
    clean_evidence = [str(item).strip() for item in evidence if str(item).strip()]
    _need(bool(clean_evidence), "MiniTZ task claim requires evidence")
    worker_id = str(worker_id).strip(); worker_role = str(worker_role).strip()
    _need(bool(worker_id), "MiniTZ task claim requires worker_id")
    _need(bool(worker_role), "MiniTZ task claim requires worker_role")
    _need(isinstance(write_authority, bool), "MiniTZ task claim write_authority must be boolean")
    path = Path(path or program_path()).resolve()
    with _locked(path):
        program = load(path)
        prior_sha = program["_observed_sha256"]; prior_revision = int(program["revision"])
        current = current_task(program)
        _need(current is not None and current["task_id"] == task_id, "MiniTZ claim must target the first active task")
        task = task_by_id(program, task_id)
        workers = list(task.get("workers") or [])
        existing = next((row for row in workers if str(row.get("worker_id")) == worker_id), None)
        if existing is not None:
            _need(bool(existing.get("write_authority")) == write_authority, "MiniTZ worker claim authority conflict")
            _need(str(existing.get("role")) == worker_role, "MiniTZ worker claim role conflict")
            if existing.get("status") == "WORKING":
                return program_identity(program)
        writers = [row for row in workers if row.get("status") == "WORKING" and row.get("write_authority") is True]
        if write_authority:
            _need(not writers, "MiniTZ task already has a WORKING writer")
        elif task.get("status") != "WORKING":
            raise ValueError("first MiniTZ task claim must be a writer")
        now = datetime.now(timezone.utc).isoformat()
        if task.get("status") != "WORKING":
            _need(task.get("status") in ACTIVE_STATUSES, "MiniTZ task is not active")
            task["revision"] = int(task["revision"]) + 1
            task["status"] = "WORKING"
        workers.append({
            "worker_id": worker_id,
            "role": worker_role,
            "write_authority": write_authority,
            "status": "WORKING",
            "claimed_at": now,
            "evidence": clean_evidence,
        })
        task["workers"] = workers
        task["worker_state_sha256"] = digest(workers)
        task["task_record_sha256"] = task_digest(task)
        program["revision"] = prior_revision + 1
        _transaction(
            program, prior_revision=prior_revision, prior_sha=prior_sha,
            action=f"CLAIM::{task_id}::{worker_id}", evidence=clean_evidence,
        )
        new_sha = _atomic_write(path, program)
    observed = load(path)
    _need(observed["_observed_sha256"] == new_sha, "MiniTZ task claim readback mismatch")
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
        _need(task.get("status") == "WORKING", "MiniTZ task must be WORKING before completion")
        now = datetime.now(timezone.utc).isoformat()
        workers = list(task.get("workers") or [])
        _need(any(row.get("write_authority") is True and row.get("status") == "WORKING" for row in workers),
              "MiniTZ completion requires a WORKING writer claim")
        for worker in workers:
            if worker.get("status") == "WORKING":
                worker["status"] = "COMPLETE"
                worker["completed_at"] = now
        task["workers"] = workers
        task["worker_state_sha256"] = digest(workers)
        task["revision"] = int(task["revision"]) + 1
        task["status"] = status
        task["active_task_survival"] = False
        task["completion"] = {
            "status": status,
            "evidence": clean_evidence,
            "recorded_at": now,
        }
        task["task_record_sha256"] = task_digest(task)
        program["revision"] = prior_revision + 1
        _transaction(program, prior_revision=prior_revision, prior_sha=prior_sha, action=f"COMPLETE::{task_id}", evidence=clean_evidence)
        new_sha = _atomic_write(path, program)
    observed = load(path)
    _need(observed["_observed_sha256"] == new_sha, "MiniTZ completion readback mismatch")
    return program_identity(observed)


def reopen_from(task_id: str, *, evidence: Sequence[str], path: Path | None = None) -> dict[str, Any]:
    """Reopen an invalidated task and its completed suffix without erasing history.

    This is deterministic repair of current truth, not owner rollback: completed
    prefix tasks remain byte-for-byte unchanged while former completions in the
    invalid suffix become non-authoritative provenance in completion_history.
    """
    clean_evidence = [str(item).strip() for item in evidence if str(item).strip()]
    _need(bool(clean_evidence), "MiniTZ reopen requires material invalidation evidence")
    path = Path(path or program_path()).resolve()
    with _locked(path):
        program = load(path)
        prior_sha = program["_observed_sha256"]
        prior_revision = int(program["revision"])
        rows = list(program["tasks"])
        ids = [row["task_id"] for row in rows]
        _need(task_id in ids, "MiniTZ reopen anchor is absent")
        anchor = ids.index(task_id)
        now = datetime.now(timezone.utc).isoformat()
        changed = False
        for row in rows[anchor:]:
            if row.get("status") not in COMPLETE_STATUSES:
                prior_workers = row.get("workers")
                if (
                    row.get("status") in ACTIVE_STATUSES
                    and row.get("completion_history")
                    and isinstance(prior_workers, list)
                    and prior_workers
                    and all(str(worker.get("status") or "") != "WORKING" for worker in prior_workers if isinstance(worker, Mapping))
                ):
                    row.pop("workers", None)
                    row.pop("worker_state_sha256", None)
                    worker_history = list(row.get("worker_history") or [])
                    worker_history.append({
                        "workers": prior_workers,
                        "invalidated_at": now,
                        "invalidation_evidence": list(clean_evidence),
                    })
                    row["worker_history"] = worker_history
                    row["task_record_sha256"] = task_digest(row)
                    changed = True
                continue
            prior_completion = row.pop("completion", None)
            if isinstance(prior_completion, Mapping):
                history = list(row.get("completion_history") or [])
                history.append({
                    "completion": dict(prior_completion),
                    "invalidated_at": now,
                    "invalidation_evidence": list(clean_evidence),
                })
                row["completion_history"] = history
            prior_workers = row.pop("workers", None)
            if isinstance(prior_workers, list) and prior_workers:
                worker_history = list(row.get("worker_history") or [])
                worker_history.append({
                    "workers": prior_workers,
                    "invalidated_at": now,
                    "invalidation_evidence": list(clean_evidence),
                })
                row["worker_history"] = worker_history
            row.pop("worker_state_sha256", None)
            row["revision"] = int(row["revision"]) + 1
            row["status"] = "PENDING"
            row["active_task_survival"] = True
            row["task_record_sha256"] = task_digest(row)
            changed = True
        obsolete_present = "frozen_current_task" in program
        program.pop("frozen_current_task", None)
        if not changed and not obsolete_present:
            return program_identity(program)
        program["tasks"] = rows
        program["revision"] = prior_revision + 1
        _transaction(
            program, prior_revision=prior_revision, prior_sha=prior_sha,
            action=f"MATERIAL_TRUTH_REOPEN::{task_id}", evidence=clean_evidence,
        )
        new_sha = _atomic_write(path, program)
    observed = load(path)
    _need(observed["_observed_sha256"] == new_sha, "MiniTZ material-truth reopen readback mismatch")
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


def resolve_effective_action(
    active_task: Mapping[str, Any] | None, *, active_mode: str | None,
    disposition: str = "CONTINUE", requested_mode: str | None = None,
) -> dict[str, Any]:
    """Project a current owner-authorized action; never ask a model for authority.

    Callers supply the existing authorization, not a model-inferred permission.
    A policy update has no replacement mode and therefore retains that mode.
    This pure resolver does not mutate tasks, create queues, or grant access.
    """
    modes = {"READ_ONLY", "MUTATING_EXECUTION"}
    _need(disposition in {"CONTINUE", "CANCEL", "STOP", "PAUSE", "DO_NOT_CONTINUE", "REPLACE", "SWITCH"},
          "unknown explicit task disposition")
    _need(requested_mode is None or requested_mode in modes, "invalid explicit replacement mode")
    selected = requested_mode if requested_mode is not None else active_mode
    valid = isinstance(active_task, Mapping) and bool(active_task.get("task_id"))
    resume = valid and disposition == "CONTINUE" and selected in modes and active_task.get("status") in ACTIVE_STATUSES
    return {"authority": "DERIVED_FROM_OWNER_AND_CANONICAL_TASK", "progression_mutation": False,
            "task_id": active_task.get("task_id") if valid else None,
            "task_revision": active_task.get("revision") if valid else None,
            "action_mode": selected if resume else "UNKNOWN", "should_resume": bool(resume),
            "disposition": disposition,
            "write_scope": dict(active_task.get("write_scope") or {}) if resume else {}}
