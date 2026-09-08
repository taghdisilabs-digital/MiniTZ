"""Controller-owned, coalescing publication cursor. Never owns task progression."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from typing import Any

_WORKERS: dict[str, tuple[threading.Thread, threading.Event, threading.Event]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, timeout=20).strip()


def _state_path(repo: Path) -> Path:
    return Path(_git(repo, "rev-parse", "--absolute-git-dir")) / "biella-publication.json"


@contextmanager
def _locked(repo: Path):
    path = _state_path(repo)
    with path.with_suffix(".lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield path
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _write(path: Path, payload: dict[str, Any]) -> None:
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, indent=2)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def read_publication(repo: Path) -> dict[str, Any]:
    path = _state_path(Path(repo))
    return json.loads(path.read_text()) if path.is_file() else {"status": "NO_PENDING_PUBLICATION"}


def request_publication(repo: Path, task_id: str, identity: dict[str, str]) -> dict[str, Any]:
    repo = Path(repo)
    commit, tree = identity["commit"], identity["tree"]
    if _git(repo, "rev-parse", commit + "^{tree}") != tree:
        raise ValueError("publication commit/tree do not match local Git objects")
    with _locked(repo) as path:
        prior = json.loads(path.read_text()) if path.is_file() else {}
        if prior.get("commit") == commit and prior.get("status") == "SYNCED":
            return prior
        payload = {
            "schema": "biella.publication_cursor/v1", "status": "PENDING",
            "commit": commit, "tree": tree, "task_id": task_id,
            "requested_at": _now(), "last_receipt": prior.get("last_receipt"),
            "execution_authority": False,
            "verified_files": prior.get("verified_files", {}),
            "drive_folder_ids": prior.get("drive_folder_ids", {}),
        }
        _write(path, payload)
    worker = _WORKERS.get(str(repo.resolve()))
    if worker:
        worker[1].set()
    return payload


def _remote(args: list[str], *, timeout: float = 45.0) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=timeout, check=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def _error_detail(exc: Exception) -> str:
    parts = [str(exc)]
    for attribute in ("stdout", "stderr"):
        value = getattr(exc, attribute, None)
        if value:
            parts.append(value.decode(errors="replace") if isinstance(value, bytes) else str(value))
    return "\n".join(parts)[-3000:]


def _drive_target(repo: Path, destination: str) -> str:
    parent, separator, name = destination.rpartition("/")
    folder_id = (read_publication(repo).get("drive_folder_ids") or {}).get(parent)
    if separator and folder_id and destination.startswith("gdrive:"):
        return f"gdrive,root_folder_id={folder_id}:{name}"
    return destination


def publish_drive_revision(repo: Path, commit: str) -> dict[str, Any]:
    import biella_production_evidence as evidence
    targets = evidence.drive_publications(repo) + evidence.derived_drive_publications(repo) + evidence.control_drive_publications(repo)
    files, errors = [], []
    options = ["--retries", "1", "--low-level-retries", "1", "--contimeout", "5s", "--timeout", "15s"]
    for relative, destination in dict.fromkeys(targets):
        cursor = read_publication(repo)
        if cursor.get("commit") != commit:
            return {"verified": False, "files": files, "errors": errors, "superseded": True}
        exists = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{commit}:{relative}"], capture_output=True)
        if exists.returncode:
            if (relative, destination) in evidence.drive_publications(repo):
                errors.append({"path": relative, "error": "required canonical file absent from publication revision"})
            continue
        data = subprocess.check_output(["git", "-C", str(repo), "show", f"{commit}:{relative}"])
        digest = hashlib.sha256(data).hexdigest()
        prior = (cursor.get("verified_files") or {}).get(destination, {})
        if prior.get("sha256") == digest and prior.get("file_id") and prior.get("status") == "VERIFIED":
            files.append(prior)
            continue
        target = _drive_target(repo, destination)
        try:
            # Read first: an interrupted receipt does not require another upload.
            try:
                remote = _remote(["rclone", "cat", target, *options]).stdout
            except subprocess.CalledProcessError as exc:
                if exc.returncode not in (3, 4):
                    raise
                remote = None
            if remote is None or hashlib.sha256(remote).hexdigest() != digest:
                with tempfile.NamedTemporaryFile(dir=_state_path(repo).parent) as local:
                    local.write(data); local.flush(); os.fsync(local.fileno())
                    _remote(["rclone", "copyto", local.name, target, "--checksum", *options])
                remote = _remote(["rclone", "cat", target, *options]).stdout
            if hashlib.sha256(remote).hexdigest() != digest:
                raise RuntimeError("exact Drive content readback mismatch")
            metadata = json.loads(_remote(["rclone", "lsjson", target, "--stat", *options]).stdout)
            file_id = metadata.get("ID")
            if not file_id:
                raise RuntimeError("Drive content matched but file identity was not returned")
            record = {"path": relative, "destination": destination, "sha256": digest,
                      "file_id": file_id, "status": "VERIFIED", "verified_at": _now(), "commit": commit}
            with _locked(repo) as path:
                latest = json.loads(path.read_text())
                latest.setdefault("verified_files", {})[destination] = record
                _write(path, latest)
            files.append(record)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            errors.append({"path": relative, "destination": destination, "error": _error_detail(exc)})
    return {"verified": not errors, "files": files, "errors": errors}


def drain_once(repo: Path) -> dict[str, Any]:
    repo = Path(repo)
    requested = read_publication(repo)
    if requested.get("status") != "PENDING":
        return requested
    commit = requested["commit"]
    receipt: dict[str, Any] = {"commit": commit, "attempted_at": _now(), "github": "PENDING", "drive": "PENDING", "errors": []}
    previous = requested.get("last_receipt") or {}
    if previous.get("source_state") == "RECONCILIATION_REQUIRED":
        receipt["source_state"] = "RECONCILIATION_REQUIRED"
    try:
        remote = _remote(["git", "-C", str(repo), "ls-remote", "origin", "refs/heads/main"]).stdout.decode().split()
        if not remote or remote[0] != commit:
            _remote(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", "push", "origin", f"{commit}:refs/heads/main"])
            remote = _remote(["git", "-C", str(repo), "ls-remote", "origin", "refs/heads/main"]).stdout.decode().split()
        if not remote or remote[0] != commit:
            receipt["source_state"] = "RECONCILIATION_REQUIRED"
            receipt["remote_commit"] = remote[0] if remote else None
            raise RuntimeError("GitHub exact revision readback mismatch")
        receipt["github"] = "VERIFIED"
        receipt["remote_commit"] = remote[0]
        receipt.pop("source_state", None)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        detail = _error_detail(exc)
        receipt["errors"].append({"target": "github", "error": detail})
        if any(marker in detail.lower() for marker in ("non-fast-forward", "fetch first", "stale info")):
            receipt["source_state"] = "RECONCILIATION_REQUIRED"
    # A known conflict survives transport loss; no stale canonical Drive overwrite.
    if receipt.get("source_state") != "RECONCILIATION_REQUIRED":
        try:
            drive = publish_drive_revision(repo, commit)
            receipt["drive"] = "VERIFIED" if drive.get("verified") else "PENDING"
            receipt["drive_readback"] = drive
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            receipt["errors"].append({"target": "drive", "error": _error_detail(exc)})
    with _locked(repo) as path:
        current = json.loads(path.read_text())
        if current.get("commit") == commit:
            current["last_receipt"] = receipt
            if receipt["github"] == receipt["drive"] == "VERIFIED":
                current["status"] = "SYNCED"
                current["verified_at"] = _now()
                current["consecutive_failures"] = 0
            else:
                current["consecutive_failures"] = int(current.get("consecutive_failures", 0)) + 1
            _write(path, current)
    return current


def start_worker(repo: Path, *, failure_path: Path | None = None) -> None:
    """One deterministic helper thread inside the controller; no service or scheduler."""
    repo = Path(repo).resolve()
    key = str(repo)
    if key in _WORKERS and _WORKERS[key][0].is_alive():
        return
    if not (repo / ".git").exists():
        return
    wake, stop = threading.Event(), threading.Event()
    def record_failure(detail: str, task_id: str | None = None) -> None:
        if failure_path is None:
            return
        try:
            event = {"time": _now(), "task_id": task_id, "type": "publication.retry", "status": "PENDING_RETRY", "diagnostics": detail[:1800]}
            with Path(failure_path).open("a", encoding="utf-8") as output:
                output.write(json.dumps(event, sort_keys=True) + "\n")
                output.flush()
        except OSError:
            pass  # The pending cursor remains authoritative for retry, never for task status.
    def run() -> None:
        while not stop.is_set():
            try:
                result = drain_once(repo)
                if result.get("status") == "PENDING":
                    record_failure(json.dumps(result.get("last_receipt") or {}, sort_keys=True), result.get("task_id"))
            except Exception as exc:
                record_failure(str(exc))
            cursor = read_publication(repo)
            failures = int(cursor.get("consecutive_failures", 0))
            # Publication-only backoff; never sleeps or rotates the executor.
            wake.wait(min(300.0, 30.0 * (2 ** min(failures, 3)))); wake.clear()
    thread = threading.Thread(target=run, name="biella-publication", daemon=True)
    _WORKERS[key] = (thread, wake, stop)
    thread.start()


def stop_worker(repo: Path) -> None:
    entry = _WORKERS.pop(str(Path(repo).resolve()), None)
    if entry:
        entry[2].set(); entry[1].set()
