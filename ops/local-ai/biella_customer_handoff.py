#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROTECTED_SERVICES = (
    "biella-ollama.service",
    "biella-qwen-residency.service",
    "biella-codex-production.service",
)
HANDOFF_OWNER_ID = "customer-handoff"
PAUSED_FOR_CUSTOMER = "PAUSED_FOR_CUSTOMER"
STOP_ORDER = tuple(reversed(PROTECTED_SERVICES))
MINITZ_TASK_PROGRAM_PATH = Path("/root/biella/analysis/live_audit/TASK_PROGRAM.json")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CREDENTIAL_FIELD = re.compile(
    r"(?:api[_-]?key|password|passwd|login[_-]?token|refresh[_-]?token|access[_-]?token|"
    r"auth(?:entication)?[_-]?secret|private[_-]?key|credential(?:s)?)\Z",
    re.IGNORECASE,
)
_OBVIOUS_SECRET = re.compile(
    r"(?:\bbearer\s+[A-Za-z0-9._~+/=-]{16,}|\b(?:sk|ghp|github_pat|xox[baprs]-)[A-Za-z0-9._-]{12,})",
    re.IGNORECASE,
)


class HandoffError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str | None:
    if not Path(path).is_file():
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assert_credential_free(value: object, *, _field: str | None = None) -> None:
    """Reject raw authentication material while permitting refs and digests."""
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if _CREDENTIAL_FIELD.fullmatch(key_text) and not key_text.lower().endswith(("_ref", "_refs", "_sha256")):
                if child not in (None, "", "UNKNOWN", "NONE"):
                    raise HandoffError("checkpoint contains a raw credential field")
            _assert_credential_free(child, _field=key_text)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            _assert_credential_free(child, _field=_field)
        return
    if isinstance(value, str) and _OBVIOUS_SECRET.search(value):
        raise HandoffError("checkpoint contains raw authentication material")


def _minitz_program_identity(task_id: str | None) -> dict[str, Any] | None:
    """Read the live MiniTZ program without copying task content into a checkpoint."""
    if not task_id:
        return None
    configured = os.environ.get("MINITZ_TASK_PROGRAM_PATH")
    program_path = Path(configured).expanduser().resolve() if configured else MINITZ_TASK_PROGRAM_PATH
    if not program_path.is_file():
        if configured:
            raise HandoffError("MiniTZ Task Program is missing")
        return None
    try:
        program = json.loads(program_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if configured or task_id.startswith(("UNIFY-", "SEMANTIC-", "OS-", "OWNER-", "DATA-", "BOOST-")):
            raise HandoffError("MiniTZ Task Program cannot be read") from exc
        return None
    if not isinstance(program, dict):
        raise HandoffError("MiniTZ Task Program is not an object")
    tasks = program.get("tasks")
    if not isinstance(tasks, list):
        raise HandoffError("MiniTZ Task Program tasks are invalid")
    row = next((item for item in tasks if isinstance(item, dict) and item.get("task_id") == task_id), None)
    if row is None:
        return None
    if program.get("schema") != "minitz.living_task_program/v1" or program.get("program_id") != "MINITZ_REBORN_SINGLE_TASK_PROGRAM":
        raise HandoffError("MiniTZ Task Program authority is invalid")
    volatile_task_fields = {"task_record_sha256", "workers", "worker_state_sha256"}
    task_digest = _canonical_digest({key: value for key, value in row.items() if key not in volatile_task_fields})
    if row.get("task_record_sha256") != task_digest:
        raise HandoffError("MiniTZ task digest is invalid")
    active_statuses = {"PENDING", "WORKING", "DEFERRED", "IN_PROGRESS", "REQUIRES_OTHER_RESOURCE"}
    active_rows = [item for item in tasks if isinstance(item, dict) and item.get("status") in active_statuses]
    working_rows = [item for item in active_rows if item.get("status") == "WORKING"]
    if len(working_rows) > 1:
        raise HandoffError("MiniTZ has multiple WORKING tasks")
    current = active_rows[0] if active_rows else None
    if (
        not isinstance(current, dict)
        or current.get("task_id") != task_id
        or current.get("revision") != row.get("revision")
        or row.get("task_record_sha256") != task_digest
        or (working_rows and working_rows[0].get("task_id") != task_id)
    ):
        raise HandoffError("MiniTZ current task identity is stale")
    return {
        "authority_path": str(program_path),
        "program_id": str(program["program_id"]),
        "program_revision": int(program["revision"]),
        "program_sha256": _sha256(program_path),
        "task_id": task_id,
        "task_revision": int(row["revision"]),
        "task_digest": task_digest,
        "scope_ref": f"task://minitz/{task_id}/{int(row['revision'])}",
        "progression_authority": "MINITZ_TASK_PROGRAM_ONLY",
    }


def _safe_resolved_path(value: object, *, base: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        candidate = Path(value).resolve()
    except OSError:
        return None
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate


def _safe_task_owned_path(repo_root: Path, raw_path: str) -> Path | None:
    relative = Path(raw_path)
    if relative.is_absolute() or not raw_path or relative.as_posix() != raw_path or ".." in relative.parts:
        return None
    candidate = repo_root / relative
    try:
        candidate.parent.resolve().relative_to(repo_root.resolve())
    except (OSError, ValueError):
        return None
    return candidate


def _task_workspace_paths(repo_root: Path, project_root: Path | None) -> list[str]:
    if project_root is None:
        return []
    try:
        relative_root = project_root.relative_to(repo_root).as_posix()
    except ValueError:
        return []
    prefix = "" if relative_root == "." else relative_root.rstrip("/") + "/"
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture_output=True, check=True,
    )
    paths = []
    for record in proc.stdout.split(b"\0"):
        if len(record) < 4:
            continue
        raw = record[3:].decode("utf-8", errors="surrogateescape")
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        if raw == relative_root:
            continue
        if relative_root == "." or raw.startswith(prefix):
            paths.append(raw[len(prefix):] if relative_root != "." else raw)
    return sorted(dict.fromkeys(paths))


def _scoped_task_state(repo_root: Path, project_root: Path | None) -> dict[str, str]:
    def file_digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    if project_root is None:
        return {}
    entries: dict[str, str] = {}
    for raw in _task_workspace_paths(repo_root, project_root):
        path = project_root / raw
        if not path.exists():
            entries[raw] = "MISSING"
        elif path.is_symlink():
            entries[raw] = f"SYMLINK:{os.readlink(path)}"
        elif path.is_file():
            try:
                digest = file_digest(path)
                entries[raw] = f"FILE:{path.stat().st_size}:{digest}"
            except OSError:
                entries[raw] = "UNREADABLE"
        else:
            entries[raw] = f"TYPE:{int(path.stat().st_mode)}"
    return entries


def _task_scope_fingerprint(state: dict[str, str | None]) -> str:
    digest = hashlib.sha256()
    for path in sorted(state):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        value = state[path]
        digest.update(("MISSING" if value is None else value).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _path_identity(path: Path) -> str | None:
    if path.is_symlink():
        return "symlink:" + hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
    if not path.exists():
        return None
    if not path.is_file():
        return f"type:{int(path.stat().st_mode)}"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _task_owned_scope(repo_root: Path, task_id: str | None, task_memory: dict[str, Any]) -> dict[str, Any] | None:
    raw_owned = task_memory.get("owned_files")
    if not task_id or not isinstance(raw_owned, dict) or not raw_owned:
        return None
    normalized: dict[str, str | None] = {}
    for raw_path, expected in raw_owned.items():
        if not isinstance(raw_path, str) or not raw_path or (expected is not None and not isinstance(expected, str)):
            raise HandoffError("task-owned checkpoint state is invalid")
        candidate = _safe_task_owned_path(repo_root, raw_path)
        if candidate is None:
            raise HandoffError("task-owned checkpoint path is not canonical MiniTZ repository state")
        actual = _path_identity(candidate)
        if actual != expected:
            raise HandoffError(f"task-owned memory is stale for {raw_path}")
        normalized[raw_path] = expected
    return {
        "schema": "minitz.task_owned_checkpoint_scope/v1",
        "task_id": task_id,
        "owned_files": normalized,
        "fingerprint": _task_scope_fingerprint(normalized),
    }


def _load_task_memory(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_runtime(payload: Path) -> dict[str, Any]:
    if not payload.is_file():
        return {}
    try:
        raw = json.loads(payload.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}

def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def dirty_workspace_fingerprint(repo_root: Path) -> str:
    repo_root = Path(repo_root)
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture_output=True, check=True,
    )
    digest = hashlib.sha256()
    digest.update(proc.stdout)
    for record in proc.stdout.split(b"\0"):
        if len(record) < 4:
            continue
        raw = record[3:].decode("utf-8", errors="surrogateescape")
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        path = repo_root / raw
        digest.update(raw.encode("utf-8", errors="surrogateescape"))
        if path.is_symlink():
            digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        elif path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


class BiellaCustomerHandoff:
    def __init__(self, repo_root: Path, runtime_root: Path, handoff_root: Path):
        self.repo_root = Path(repo_root).resolve()
        self.runtime_root = Path(runtime_root).resolve()
        self.handoff_root = Path(handoff_root).resolve()
        self.active_checkpoint_path = self.handoff_root / "active.json"
        self.history_root = self.handoff_root / "history"
        self.last_resume_path = self.handoff_root / "last-resume.json"
        self.pause_request_path = self.runtime_root / "customer-pause-request.json"
        self.pause_ack_path = self.runtime_root / "customer-pause-ack.json"
    def service_states(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for name in PROTECTED_SERVICES:
            active = subprocess.run(
                ["systemctl", "is-active", "--quiet", name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            ).returncode == 0
            enabled_proc = subprocess.run(
                ["systemctl", "is-enabled", name], text=True, capture_output=True, check=False,
            )
            enabled = (enabled_proc.stdout or enabled_proc.stderr or "unknown").strip().splitlines()[0]
            result[name] = {"active": active, "enabled": enabled}
        return result

    def guard_production(self) -> None:
        if self.running_customer_count() > 0:
            raise HandoffError("cannot start Biella while a customer container is running")

    def running_customer_count(self) -> int:
        proc = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"], text=True, capture_output=True, check=False,
        )
        if proc.returncode != 0:
            raise HandoffError((proc.stderr or proc.stdout or "docker ps failed").strip())
        return sum(1 for line in proc.stdout.splitlines() if line.strip().startswith("psb-"))

    def set_enabled_state(self, name: str, state: str) -> None:
        if state == "enabled":
            cmd = ["systemctl", "enable", name]
        elif state == "disabled":
            cmd = ["systemctl", "disable", name]
        elif state == "masked":
            cmd = ["systemctl", "mask", name]
        else:
            return
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            raise HandoffError((proc.stderr or proc.stdout or f"failed to set {name} {state}").strip())
    def set_active_state(self, name: str, active: bool) -> None:
        cmd = ["systemctl", "start" if active else "stop", name]
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            raise HandoffError((proc.stderr or proc.stdout or f"failed to {'start' if active else 'stop'} {name}").strip())

    def verify_source_alignment(self) -> None:
        script = self.repo_root / "ops/local-ai/biella-production-source-sync.sh"
        if not script.is_file():
            raise HandoffError(f"source alignment script missing: {script}")
        env = os.environ.copy()
        env["BIELLA_REPO_ROOT"] = str(self.repo_root)
        proc = subprocess.run([str(script)], text=True, capture_output=True, check=False, env=env)
        if proc.returncode != 0:
            raise HandoffError((proc.stderr or proc.stdout or "source alignment failed").strip())

    def _git_identity(self) -> dict[str, str]:
        def git(*args: str) -> str:
            return subprocess.check_output(["git", "-C", str(self.repo_root), *args], text=True).strip()
        return {"branch": git("branch", "--show-current"), "head": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}")}

    def _runtime_identity(self) -> tuple[str | None, dict[str, Any]]:
        runtime_path = self.runtime_root / "runtime.json"
        runtime = _load_runtime(runtime_path)
        task_id = str(runtime.get("task_id") or "") or None
        task_memory = self.runtime_root / "task-memory" / f"{task_id}.json" if task_id else Path("/")
        projection = self.runtime_root / "memory/current-task.json"
        memory = _load_task_memory(task_memory) if task_id else {}
        if task_id and memory.get("task_id") not in (None, task_id):
            raise HandoffError("MiniTZ task memory belongs to another task")
        runtime_session = str(runtime.get("task_session_id") or runtime.get("session_id") or "") or None
        memory_session = str(memory.get("session_id") or "") or None
        if runtime_session and memory_session and runtime_session != memory_session:
            raise HandoffError("MiniTZ task/session identity is inconsistent")
        session_id = runtime_session or memory_session
        task_identity = _minitz_program_identity(task_id)
        declared_identity = memory.get("task_identity") or memory.get("task_authority")
        if task_identity is not None and isinstance(declared_identity, dict):
            if declared_identity.get("task_id") not in (None, task_id):
                raise HandoffError("MiniTZ task memory identity belongs to another task")
            if declared_identity.get("task_revision") not in (None, task_identity["task_revision"]):
                raise HandoffError("MiniTZ task memory revision is stale")
            if declared_identity.get("task_digest") not in (None, task_identity["task_digest"]):
                raise HandoffError("MiniTZ task memory digest is stale")
        identity: dict[str, Any] = {
            "runtime_sha256": _sha256(runtime_path),
            "task_memory_sha256": _sha256(task_memory) if task_id else None,
            "projection_sha256": _sha256(projection),
        }
        if task_identity is not None:
            identity["task_identity"] = task_identity
        identity["session_identity"] = {
            "task_id": task_id,
            "session_id": session_id,
            "session_sha256": hashlib.sha256(session_id.encode("utf-8")).hexdigest() if session_id else None,
        }
        return task_id, identity

    def _owner_lifecycle(self, task_identity: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(task_identity, dict):
            return None
        wake_path = self.runtime_root / "recovery/owner-os-wake-current.json"
        wake = _load_runtime(wake_path)
        expected = {
            "current_task_id": task_identity.get("task_id"),
            "current_task_revision": task_identity.get("task_revision"),
            "current_task_sha256": task_identity.get("task_digest"),
            "program_revision": task_identity.get("program_revision"),
            "program_sha256": task_identity.get("program_sha256"),
        }
        if (
            wake.get("schema") == "minitz.owner_wake_receipt/v1"
            and all(wake.get(key) == value for key, value in expected.items())
            and wake.get("host_power_change_authorized") is False
            and wake.get("control_gateway_authorized") is False
        ):
            return {
                "state": "EXPLICIT_OWNER_WAKE_ACTIVE",
                "receipt_ref": str(wake_path),
                "receipt_sha256": _sha256(wake_path),
                "owner_instruction": str(wake.get("owner_instruction") or ""),
            }
        return {
            "state": "OWNER_SLEEP",
            "receipt_ref": str(wake_path),
            "receipt_sha256": _sha256(wake_path),
            "reason": "explicit_owner_wake_receipt_missing_or_stale",
        }

    @staticmethod
    def _validate_checkpoint_envelope(checkpoint: dict[str, Any]) -> None:
        _assert_credential_free(checkpoint)
        if checkpoint.get("schema") != "biella.customer_handoff_checkpoint/v1":
            raise HandoffError("checkpoint schema is invalid")
        owner_id = checkpoint.get("owner_id")
        if owner_id is not None and owner_id != HANDOFF_OWNER_ID:
            raise HandoffError("checkpoint owner is foreign")
        task_id = checkpoint.get("task_id")
        task_identity = checkpoint.get("task_identity")
        if task_identity is not None and owner_id != HANDOFF_OWNER_ID:
            raise HandoffError("MiniTZ checkpoint owner is missing or foreign")
        if task_identity is not None:
            if not isinstance(task_identity, dict) or task_identity.get("task_id") != task_id:
                raise HandoffError("checkpoint task identity is invalid")
            runtime = checkpoint.get("runtime")
            if not isinstance(runtime, dict) or runtime.get("task_identity") != task_identity:
                raise HandoffError("checkpoint task identity is not bound to runtime identity")
            for key in ("task_digest", "program_sha256"):
                if not isinstance(task_identity.get(key), str) or _SHA256.fullmatch(task_identity[key]) is None:
                    raise HandoffError("checkpoint task identity digest is invalid")
            for key in ("task_revision", "program_revision"):
                if isinstance(task_identity.get(key), bool) or not isinstance(task_identity.get(key), int) or task_identity[key] < 1:
                    raise HandoffError("checkpoint task identity revision is invalid")
            if task_identity.get("progression_authority") != "MINITZ_TASK_PROGRAM_ONLY":
                raise HandoffError("checkpoint task progression authority is invalid")
        session_identity = checkpoint.get("session_identity")
        if session_identity is not None:
            if not isinstance(session_identity, dict) or session_identity.get("task_id") != task_id:
                raise HandoffError("checkpoint session identity is invalid")
            session_id = session_identity.get("session_id")
            if session_id is not None and (not isinstance(session_id, str) or len(session_id) > 256 or "\x00" in session_id):
                raise HandoffError("checkpoint session identity is invalid")
            session_sha = session_identity.get("session_sha256")
            if session_sha is not None and (not isinstance(session_sha, str) or _SHA256.fullmatch(session_sha) is None):
                raise HandoffError("checkpoint session identity digest is invalid")
            if session_id is None and session_sha is not None:
                raise HandoffError("checkpoint session identity digest is invalid")
            if session_id is not None and session_sha != hashlib.sha256(session_id.encode("utf-8")).hexdigest():
                raise HandoffError("checkpoint session identity digest does not match session")
            runtime = checkpoint.get("runtime")
            if not isinstance(runtime, dict) or runtime.get("session_identity") != session_identity:
                raise HandoffError("checkpoint session identity is not bound to runtime identity")
        owner_lifecycle = checkpoint.get("owner_lifecycle")
        if owner_lifecycle is not None:
            if not isinstance(owner_lifecycle, dict) or owner_lifecycle.get("state") not in {"EXPLICIT_OWNER_WAKE_ACTIVE", "OWNER_SLEEP"}:
                raise HandoffError("checkpoint owner lifecycle is invalid")

    def _worktree_identity(self, workspace_fingerprint: str, task_scope: dict[str, Any] | None) -> dict[str, Any]:
        identity = self._git_identity()
        identity["workspace_fingerprint"] = workspace_fingerprint
        if task_scope is not None:
            identity["task_owned_overlap_fingerprint"] = task_scope["fingerprint"]
        return identity
    def cooperative_pause(self, timeout_seconds: float = 3600.0) -> None:
        _atomic_json(self.pause_request_path, {
            "schema": "biella.customer_pause_request/v1",
            "requested_at": _now(),
        })
        deadline = time.monotonic() + max(1.0, timeout_seconds)
        while time.monotonic() < deadline:
            inactive = subprocess.run(
                ["systemctl", "is-active", "--quiet", "biella-codex-production.service"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            ).returncode != 0
            if inactive and self.pause_ack_path.is_file():
                return
            time.sleep(0.25)
        raise HandoffError("production did not reach a cooperative customer checkpoint before timeout")

    def _assert_workspace_compatible(self, checkpoint: dict[str, Any]) -> None:
        self._validate_checkpoint_envelope(checkpoint)
        worktree = checkpoint.get("worktree_identity")
        if isinstance(worktree, dict):
            try:
                current_worktree = self._git_identity()
            except (OSError, subprocess.SubprocessError) as exc:
                raise HandoffError("current worktree identity is unavailable") from exc
            if worktree.get("branch") != current_worktree.get("branch"):
                raise HandoffError("MiniTZ worktree branch changed while customer checkpoint was held")
        task_scope = checkpoint.get("task_scope")
        if isinstance(task_scope, dict):
            if task_scope.get("task_id") != checkpoint.get("task_id"):
                raise HandoffError("task-owned checkpoint scope belongs to another task")
            owned = task_scope.get("owned_files")
            if not isinstance(owned, dict) or not owned:
                raise HandoffError("task-owned checkpoint scope is invalid")
            expected_fingerprint = task_scope.get("fingerprint")
            if not isinstance(expected_fingerprint, str) or expected_fingerprint != _task_scope_fingerprint(owned):
                raise HandoffError("task-owned checkpoint scope fingerprint is invalid")
            changed = []
            for raw_path, expected in owned.items():
                if not isinstance(raw_path, str) or (expected is not None and not isinstance(expected, str)):
                    raise HandoffError("task-owned checkpoint scope is invalid")
                candidate = _safe_task_owned_path(self.repo_root, raw_path)
                if candidate is None:
                    raise HandoffError("task-owned checkpoint scope path is invalid")
                actual = _path_identity(candidate)
                if actual != expected:
                    changed.append(
                        f"{raw_path} (expected={expected or 'MISSING'}, observed={actual or 'MISSING'})"
                    )
            if changed:
                sample = ", ".join(changed[:5])
                raise HandoffError(f"task-owned checkpoint overlap changed while checkpoint was held: {sample}")
            return
        expected = str(checkpoint.get("workspace_fingerprint") or "")
        current = dirty_workspace_fingerprint(self.repo_root)
        if not expected or current != expected:
            raise HandoffError("Biella dirty worktree changed while customer checkpoint was held")

    def checkpoint(self) -> dict[str, Any]:
        if self.active_checkpoint_path.is_file():
            try:
                current = json.loads(self.active_checkpoint_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise HandoffError("active checkpoint is invalid") from exc
            if not isinstance(current, dict):
                raise HandoffError("active checkpoint is invalid")
            self._assert_workspace_compatible(current)
            self.sleep_services()
            return current
        original_services = self.service_states()
        if original_services["biella-codex-production.service"]["active"]:
            self.cooperative_pause()
        task_id, runtime_identity = self._runtime_identity()
        task_memory_path = self.runtime_root / "task-memory" / f"{task_id}.json" if task_id else Path("/")
        task_memory = _load_task_memory(task_memory_path) if task_id else {}
        task_scope = _task_owned_scope(self.repo_root, task_id, task_memory)
        workspace_fingerprint = dirty_workspace_fingerprint(self.repo_root)
        task_identity = runtime_identity.get("task_identity")
        session_identity = runtime_identity.get("session_identity")
        checkpoint = {
            "schema": "biella.customer_handoff_checkpoint/v1",
            "created_at": _now(),
            "repo": self._git_identity(),
            "task_id": task_id,
            "runtime": runtime_identity,
            "workspace_fingerprint": workspace_fingerprint,
            "services": original_services,
            "owner_id": HANDOFF_OWNER_ID,
            "worktree_identity": self._worktree_identity(workspace_fingerprint, task_scope),
        }
        if task_identity is not None:
            checkpoint["task_identity"] = task_identity
        if session_identity is not None:
            checkpoint["session_identity"] = session_identity
        owner_lifecycle = self._owner_lifecycle(task_identity)
        if owner_lifecycle is not None:
            checkpoint["owner_lifecycle"] = owner_lifecycle
        if task_scope is not None:
            checkpoint["task_scope"] = task_scope
        _assert_credential_free(checkpoint)
        self.last_resume_path.unlink(missing_ok=True)
        _atomic_json(self.active_checkpoint_path, checkpoint)
        self.sleep_services()
        return checkpoint
    def sleep_services(self) -> None:
        for name in STOP_ORDER:
            self.set_active_state(name, False)
        for name in PROTECTED_SERVICES:
            self.set_enabled_state(name, "disabled")

    def resume(self) -> dict[str, Any]:
        receipt = _load_runtime(self.last_resume_path)
        if not self.active_checkpoint_path.is_file():
            if receipt.get("status") == "RESTORED" and isinstance(receipt.get("checkpoint_sha256"), str):
                return {**receipt, "status": "RESTORED_ALREADY"}
            return {"status": "NO_CHECKPOINT"}
        checkpoint_digest = hashlib.sha256(self.active_checkpoint_path.read_bytes()).hexdigest()
        if receipt.get("status") == "RESTORED" and receipt.get("checkpoint_sha256") == checkpoint_digest:
            self.active_checkpoint_path.unlink(missing_ok=True)
            return {**receipt, "status": "RESTORED_ALREADY"}
        try:
            checkpoint = json.loads(self.active_checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HandoffError("active checkpoint is invalid") from exc
        if not isinstance(checkpoint, dict):
            raise HandoffError("active checkpoint is invalid")
        self._validate_checkpoint_envelope(checkpoint)
        self._assert_workspace_compatible(checkpoint)
        current_task, current_runtime = self._runtime_identity()
        expected_runtime = checkpoint.get("runtime")
        if current_task != checkpoint.get("task_id") or not isinstance(expected_runtime, dict) or current_runtime != expected_runtime:
            raise HandoffError("Biella runtime continuity changed while customer checkpoint was held")
        task_identity = current_runtime.get("task_identity")
        current_owner_lifecycle = self._owner_lifecycle(task_identity)
        if isinstance(task_identity, dict) and (
            not isinstance(current_owner_lifecycle, dict)
            or current_owner_lifecycle.get("state") != "EXPLICIT_OWNER_WAKE_ACTIVE"
        ):
            return {
                "status": "OWNER_SLEEP_PRESERVED",
                "checkpoint_sha256": checkpoint_digest,
                "task_id": current_task,
                "task_identity": task_identity,
                "owner_id": checkpoint.get("owner_id"),
                "owner_lifecycle": current_owner_lifecycle,
                "reason": "explicit_owner_resume_is_required_before_service_restore",
            }
        if self.running_customer_count() != 0:
            raise HandoffError("cannot resume Biella while a customer container is still running")
        self.verify_source_alignment()
        self._assert_workspace_compatible(checkpoint)
        services = checkpoint.get("services")
        if not isinstance(services, dict):
            raise HandoffError("checkpoint service state is invalid")
        for name in PROTECTED_SERVICES:
            if not isinstance(services.get(name), dict):
                raise HandoffError(f"checkpoint missing service state for {name}")
        # Authoritative execution is restored before optional accelerators.
        production = "biella-codex-production.service"
        self.set_enabled_state(production, str(services[production].get("enabled") or "unknown"))
        self.pause_request_path.unlink(missing_ok=True)
        self.pause_ack_path.unlink(missing_ok=True)
        self.set_active_state(production, bool(services[production].get("active")))
        optional_errors = []
        for name in PROTECTED_SERVICES:
            if name == production:
                continue
            for operation, value in (("enabled", str(services[name].get("enabled") or "unknown")),
                                     ("active", bool(services[name].get("active")))):
                try:
                    if operation == "enabled":
                        self.set_enabled_state(name, value)
                    else:
                        self.set_active_state(name, value)
                except (HandoffError, OSError, subprocess.SubprocessError) as exc:
                    optional_errors.append({"service": name, "operation": operation, "error": str(exc)})
        if optional_errors:
            _atomic_json(self.handoff_root / "optional-resource-restore.json", {
                "observed_at": _now(), "errors": optional_errors,
                "production_restored": True, "execution_authority": False,
            })
        self.history_root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(self.active_checkpoint_path.read_bytes()).hexdigest()
        history = self.history_root / f"{digest}.json"
        shutil.copy2(self.active_checkpoint_path, history)
        result = {"status": "RESTORED", "checkpoint_sha256": digest, "history": str(history), "optional_resource_errors": optional_errors}
        _atomic_json(self.last_resume_path, {
            "schema": "minitz.customer_handoff_resume_receipt/v1",
            "status": "RESTORED",
            "restored_at": _now(),
            "checkpoint_sha256": digest,
            "history": str(history),
            "optional_resource_errors": optional_errors,
        })
        self.active_checkpoint_path.unlink()
        return result

    def import_lessons(self, source_path: Path, inbox_root: Path) -> dict[str, Any]:
        source_path = Path(source_path)
        if not source_path.is_file():
            return {"status": "NO_LESSONS"}
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema") != "project_sandbox.sanitized_lessons/v1":
            raise HandoffError("lesson is not project-neutral: invalid bundle schema")
        raw_lessons = payload.get("lessons")
        if not isinstance(raw_lessons, list) or len(raw_lessons) > 100:
            raise HandoffError("lesson is not project-neutral: invalid lesson list")
        lessons = [_validate_neutral_lesson(item) for item in raw_lessons]
        if not lessons:
            source_path.unlink(missing_ok=True)
            return {"status": "NO_LESSONS"}
        encoded = json.dumps(lessons, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        inbox_root = Path(inbox_root)
        inbox_root.mkdir(parents=True, exist_ok=True)
        target = inbox_root / f"{digest}.json"
        candidate = {
            "schema": "biella.external_lesson_candidate/v1",
            "sha256": digest, "imported_at": _now(), "lessons": lessons,
            "authority": "PROJECT_NEUTRAL_CANDIDATE_NOT_ACTIVE_AUTHORITY",
        }
        if not target.exists():
            _atomic_json(target, candidate)
        source_path.unlink(missing_ok=True)
        return {"status": "IMPORTED", "sha256": digest, "path": str(target)}


_LESSON_CATEGORIES = {
    "build_method", "test_method", "tool_compatibility", "failure_fix", "performance",
    "cache_efficiency", "deployment_mechanic", "container_ci", "coding_workflow",
}
_LESSON_EVIDENCE = {"test", "build", "runtime", "benchmark", "deployment", "tool_output"}
_LESSON_KEYS = {"category", "title", "problem", "method", "result", "evidence_type", "timestamp"}
_NEUTRAL_FORBIDDEN = re.compile(
    r"(?:https?://|git@|www\.|(?:^|\s)/(?:[A-Za-z0-9_.-]+/){1,}|\b[A-Za-z]:\\|"
    r"\b(?:customer|client|brand|logo|palette|typography|font|visual|screenshot|copywriting|"
    r"business data|product requirement|design language|style guide)\b|```)",
    re.I,
)


def _validate_neutral_lesson(record: Any) -> dict[str, str]:
    if not isinstance(record, dict) or set(record) != _LESSON_KEYS:
        raise HandoffError("lesson is not project-neutral: invalid schema")
    category = str(record["category"])
    evidence = str(record["evidence_type"])
    if category not in _LESSON_CATEGORIES or evidence not in _LESSON_EVIDENCE:
        raise HandoffError("lesson is not project-neutral: unsupported category or evidence")
    result = {key: str(record[key]).strip() for key in _LESSON_KEYS}
    for key in ("title", "problem", "method", "result"):
        value = result[key]
        if not value or _NEUTRAL_FORBIDDEN.search(value):
            raise HandoffError("lesson is not project-neutral: forbidden content")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biella-customer-handoff")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("checkpoint", "resume", "import-lessons", "status", "guard-production"):
        sub.add_parser(name)
    return parser


def _default_manager() -> BiellaCustomerHandoff:
    repo = Path(os.environ.get("BIELLA_REPO_ROOT", "/root/biella/repos/biella-engine"))
    runtime = Path(os.environ.get("BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT", "/mnt/biella-extra/biella-runtime/codex-production"))
    handoff_root = Path(os.environ.get("BIELLA_CUSTOMER_HANDOFF_ROOT", "/mnt/biella-extra/biella-runtime/customer-handoff"))
    return BiellaCustomerHandoff(repo, runtime, handoff_root)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manager = _default_manager()
    if args.command == "checkpoint":
        result = manager.checkpoint()
    elif args.command == "resume":
        result = manager.resume()
    elif args.command == "import-lessons":
        source = Path(os.environ.get("BIELLA_EXTERNAL_LESSON_SOURCE", "/run/project-sandbox-broker/biella-lessons.json"))
        inbox = Path(os.environ.get("BIELLA_EXTERNAL_LESSON_INBOX", "/root/biella/artifacts/external-lessons/inbox"))
        result = manager.import_lessons(source, inbox)
    elif args.command == "guard-production":
        manager.guard_production()
        result = {"status": "CLEAR"}
    else:
        result = {
            "checkpoint_held": manager.active_checkpoint_path.is_file(),
            "running_customer_count": manager.running_customer_count(),
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
