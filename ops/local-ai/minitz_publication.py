from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "minitz.source_publication/v2"
_WORKERS: dict[str, tuple[threading.Thread, threading.Event]] = {}
_WORKERS_LOCK = threading.Lock()


class PublicationStateError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args], text=True, timeout=30).strip()


def _remote(args: list[str], *, timeout: float = 45.0) -> subprocess.CompletedProcess:
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=timeout)


def _state_path(repo: Path) -> Path:
    return Path(repo) / ".git" / "minitz-publication.json"


def _recovery_path(repo: Path) -> Path:
    return Path(repo) / ".git" / "minitz-publication.recovery.json"


def source_publication_identity(repo: Path, ref: str = "refs/heads/main") -> dict[str, str]:
    repo = Path(repo).resolve()
    commit = _git(repo, "rev-parse", ref)
    tree = _git(repo, "rev-parse", commit + "^{tree}")
    material = f"{repo}|{ref}|{commit}|{tree}".encode()
    return {
        "ref": ref,
        "commit": commit,
        "tree": tree,
        "publication_ref": "source-publication://minitz/" + hashlib.sha256(material).hexdigest(),
    }


@contextmanager
def _locked(repo: Path):
    state = _state_path(repo)
    state.parent.mkdir(parents=True, exist_ok=True)
    lock_path = state.with_suffix(state.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield state
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _write(path: Path, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(tmp, path)
    recovery = _recovery_path(path.parent.parent)
    rtmp = recovery.with_suffix(recovery.suffix + ".tmp")
    with rtmp.open("w", encoding="utf-8") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(rtmp, recovery)


def _load_state_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationStateError(str(exc)) from exc
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise PublicationStateError("invalid MiniTZ publication state")
    return value


def _read_state_locked(repo: Path, path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            return _load_state_file(path)
        except PublicationStateError:
            recovery = _recovery_path(repo)
            if not recovery.is_file():
                raise
            recovered = _load_state_file(recovery)
            _write(path, recovered)
            return recovered
    recovery = _recovery_path(repo)
    if recovery.is_file():
        recovered = _load_state_file(recovery)
        _write(path, recovered)
        return recovered
    return {
        "schema": SCHEMA,
        "status": "IDLE",
        "commit": None,
        "tree": None,
        "task_id": None,
        "source_identity": None,
        "publication_ref": None,
        "publication_intent": None,
        "semantic_bindings": [],
        "execution_authority": False,
        "last_receipt": None,
    }


def _write_state(repo: Path, path: Path, payload: dict[str, Any]) -> None:
    del repo
    _write(path, payload)


def read_publication(repo: Path) -> dict[str, Any]:
    repo = Path(repo).resolve()
    with _locked(repo) as path:
        return dict(_read_state_locked(repo, path))


def _completed_snapshot(repo: Path, commit: str) -> tuple[list[str], bool]:
    del repo, commit
    return [], False


def request_publication(repo: Path, task_id: str, identity: dict[str, str]) -> dict[str, Any]:
    repo = Path(repo).resolve()
    commit = str(identity["commit"]); tree = str(identity["tree"])
    source_identity = source_publication_identity(repo)
    if source_identity["commit"] != commit or source_identity["tree"] != tree:
        source_identity = {
            "ref": "refs/heads/main", "commit": commit, "tree": tree,
            "publication_ref": "source-publication://minitz/" + hashlib.sha256(f"{repo}|refs/heads/main|{commit}|{tree}".encode()).hexdigest(),
        }
    with _locked(repo) as path:
        prior = _read_state_locked(repo, path)
        last = prior.get("last_receipt") if isinstance(prior.get("last_receipt"), dict) else None
        already = bool(last and last.get("commit") == commit and last.get("github") == "VERIFIED")
        payload = {
            "schema": SCHEMA,
            "status": "SYNCED" if already else "PENDING",
            "commit": commit,
            "tree": tree,
            "task_id": str(task_id),
            "source_identity": source_identity,
            "publication_ref": source_identity["publication_ref"],
            "publication_intent": {"commit": commit, "tree": tree, "task_id": str(task_id)},
            "semantic_bindings": list(prior.get("semantic_bindings") or []),
            "execution_authority": False,
            "last_receipt": last if already else None,
            "updated_at": _now(),
        }
        _write_state(repo, path, payload)
        return dict(payload)


def attach_publication_binding(repo: Path, *, implementation_ref: str, object_ref: str) -> dict[str, Any]:
    repo = Path(repo).resolve()
    with _locked(repo) as path:
        state = _read_state_locked(repo, path)
        publication_ref = state.get("publication_ref")
        if not publication_ref:
            raise PublicationStateError("publication identity is not established")
        binding = {
            "publication_ref": publication_ref,
            "implementation_ref": str(implementation_ref),
            "object_ref": str(object_ref),
            "execution_authority": False,
        }
        rows = list(state.get("semantic_bindings") or [])
        if binding not in rows:
            rows.append(binding)
        state["semantic_bindings"] = rows
        state["updated_at"] = _now()
        _write_state(repo, path, state)
        return binding


def publication_retry_needed(cursor: Mapping[str, Any]) -> bool:
    if cursor.get("status") == "RECONCILIATION_REQUIRED":
        return False
    receipt = cursor.get("last_receipt") if isinstance(cursor.get("last_receipt"), Mapping) else {}
    return not (receipt.get("commit") == cursor.get("commit") and receipt.get("github") == "VERIFIED")


def _error_detail(exc: Exception) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        raw = exc.stderr or exc.stdout or b""
        if isinstance(raw, bytes): raw = raw.decode(errors="replace")
        return str(raw or exc)
    return str(exc)


def drain_once(repo: Path) -> dict[str, Any]:
    repo = Path(repo).resolve()
    requested = read_publication(repo)
    commit = requested.get("commit")
    if not commit:
        return requested
    receipt: dict[str, Any] = {"commit": commit, "attempted_at": _now(), "github": "PENDING", "errors": []}
    status = "PENDING"
    try:
        remote = _remote(["git", "-C", str(repo), "ls-remote", "origin", "refs/heads/main"]).stdout.decode().split()
        if not remote or remote[0] != commit:
            _remote(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", "push", "origin", f"{commit}:refs/heads/main"])
            remote = _remote(["git", "-C", str(repo), "ls-remote", "origin", "refs/heads/main"]).stdout.decode().split()
        if not remote or remote[0] != commit:
            receipt["source_state"] = "RECONCILIATION_REQUIRED"
            receipt["remote_commit"] = remote[0] if remote else None
            status = "RECONCILIATION_REQUIRED"
        else:
            subprocess.run(["git", "-C", str(repo), "fetch", "--quiet", "origin", "main"], check=True, timeout=30)
            remote_tree = _git(repo, "rev-parse", "FETCH_HEAD^{tree}")
            if remote_tree != requested.get("tree"):
                receipt["source_state"] = "RECONCILIATION_REQUIRED"
                receipt["remote_tree"] = remote_tree
                status = "RECONCILIATION_REQUIRED"
            else:
                receipt.update(github="VERIFIED", remote_commit=remote[0], remote_tree=remote_tree)
                status = "SYNCED"
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        detail = _error_detail(exc)
        receipt["errors"].append({"target": "github", "error": detail})
        if any(marker in detail.lower() for marker in ("non-fast-forward", "fetch first", "stale info")):
            receipt["source_state"] = "RECONCILIATION_REQUIRED"
            status = "RECONCILIATION_REQUIRED"
    with _locked(repo) as path:
        current = _read_state_locked(repo, path)
        if current.get("commit") == commit:
            current["last_receipt"] = receipt
            current["status"] = status
            current["updated_at"] = _now()
            _write_state(repo, path, current)
            return dict(current)
    return read_publication(repo)


def _worker(repo: Path, stop: threading.Event, failure_path: Path | None) -> None:
    while not stop.wait(2.0):
        try:
            cursor = read_publication(repo)
            if publication_retry_needed(cursor):
                drain_once(repo)
        except Exception as exc:
            if failure_path is not None:
                failure_path.parent.mkdir(parents=True, exist_ok=True)
                with failure_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"time": _now(), "type": "SOURCE_PUBLICATION", "error": _error_detail(exc)[:1200]}, sort_keys=True) + "\n")
            time.sleep(3.0)


def start_worker(repo: Path, *, failure_path: Path | None = None) -> None:
    repo = Path(repo).resolve(); key = str(repo)
    with _WORKERS_LOCK:
        current = _WORKERS.get(key)
        if current and current[0].is_alive():
            return
        stop = threading.Event()
        thread = threading.Thread(target=_worker, args=(repo, stop, failure_path), name="minitz-source-publication", daemon=True)
        _WORKERS[key] = (thread, stop)
        thread.start()


def stop_worker(repo: Path) -> None:
    key = str(Path(repo).resolve())
    with _WORKERS_LOCK:
        item = _WORKERS.pop(key, None)
    if item:
        thread, stop = item
        stop.set(); thread.join(timeout=5)
