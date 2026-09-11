"""Controller-owned, coalescing publication cursor. Never owns task progression."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import threading
from typing import Any

import minitz_task_program as minitz

_WORKERS: dict[str, tuple[threading.Thread, threading.Event, threading.Event]] = {}
_DRIVE_WORKERS: dict[str, tuple[threading.Thread, threading.Event, threading.Event]] = {}
DRIVE_TASK_INTERVAL = 5
DRIVE_PART_MAX_BYTES = 3_800_000_000
DRIVE_PACKAGE_DESTINATION = "gdrive:Biella/D_TASK_PROGRAM"


class PublicationStateError(RuntimeError):
    """Publication continuity cannot be reconstructed without losing source intent."""


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, timeout=20).strip()


def _state_path(repo: Path) -> Path:
    return Path(_git(repo, "rev-parse", "--absolute-git-dir")) / "biella-publication.json"


def _recovery_path(repo: Path) -> Path:
    return _state_path(repo).with_name("biella-publication.recovery.json")


def source_publication_identity(repo: Path, ref: str = "refs/heads/main") -> dict[str, str]:
    repo = Path(repo).resolve()
    if not isinstance(ref, str) or not ref.startswith("refs/") or any(char.isspace() for char in ref):
        raise ValueError("publication source ref is malformed")
    git_dir = str(Path(_git(repo, "rev-parse", "--absolute-git-dir")).resolve())
    worktree = str(Path(_git(repo, "rev-parse", "--show-toplevel")).resolve())
    try:
        remote = _git(repo, "config", "--get", "remote.origin.url")
    except subprocess.CalledProcessError:
        remote = ""
    repository_payload = {"git_dir": git_dir, "remote": remote, "worktree": worktree}
    repository_digest = _sha(repository_payload)
    publication_payload = {"repository_digest": repository_digest, "ref": ref}
    return {
        "schema": "minitz.source_publication_identity/v1",
        "repository_ref": f"git-repository://sha256/{repository_digest}",
        "ref": ref,
        "publication_ref": f"source-publication://sha256/{_sha(publication_payload)}",
    }


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


def _load_state_file(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationStateError(f"publication state is unreadable: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PublicationStateError(f"publication state is not an object: {path}")
    return raw


def _read_state_locked(repo: Path, path: Path) -> dict[str, Any]:
    recovery = _recovery_path(repo)
    if path.is_file():
        try:
            return _load_state_file(path)
        except PublicationStateError as cursor_error:
            if not recovery.is_file():
                raise cursor_error
            try:
                restored = _load_state_file(recovery)
            except PublicationStateError as recovery_error:
                raise PublicationStateError(
                    f"publication cursor and recovery snapshot are unreadable: {cursor_error}; {recovery_error}"
                ) from recovery_error
            _write(path, restored)
            return restored
    if recovery.is_file():
        restored = _load_state_file(recovery)
        _write(path, restored)
        return restored
    return {}


def _write_state(repo: Path, path: Path, payload: dict[str, Any]) -> None:
    _write(path, payload)
    _write(_recovery_path(repo), payload)


def read_publication(repo: Path) -> dict[str, Any]:
    repo = Path(repo).resolve()
    with _locked(repo) as path:
        state = _read_state_locked(repo, path)
    return state if state else {"status": "NO_PENDING_PUBLICATION"}


def _completed_snapshot(repo: Path, commit: str) -> tuple[list[str], bool]:
    del repo, commit
    program = minitz.load()
    completed = [row["task_id"] for row in program["tasks"] if row.get("status") in minitz.COMPLETE_STATUSES]
    finished = not any(row.get("status") in minitz.ACTIVE_STATUSES for row in program["tasks"])
    return completed, finished


def _schedule_drive(payload: dict[str, Any]) -> None:
    state = payload["drive_batch"]
    if state.get("pending"):
        return
    baseline = set(state["baseline_completed_ids"])
    new = [item for item in payload.get("completed_ids", []) if item not in baseline]
    if len(new) < DRIVE_TASK_INTERVAL and not (new and payload.get("program_finished")):
        return
    state["pending"] = {
        "commit": payload["commit"], "tree": payload["tree"],
        "task_ids": new, "completed_ids": list(payload["completed_ids"]),
        "base_commit": state.get("package_base_commit"), "requested_at": _now(),
    }
    state["status"] = "PENDING"


def request_publication(repo: Path, task_id: str, identity: dict[str, str]) -> dict[str, Any]:
    repo = Path(repo)
    commit, tree = identity["commit"], identity["tree"]
    if _git(repo, "rev-parse", commit + "^{tree}") != tree:
        raise ValueError("publication commit/tree do not match local Git objects")
    completed, finished = _completed_snapshot(repo, commit)
    with _locked(repo) as path:
        prior = _read_state_locked(repo, path)
        batch = prior.get("drive_batch")
        if batch is None:
            baseline_commit = prior.get("commit") or commit
            baseline, _ = _completed_snapshot(repo, baseline_commit)
            batch = {
                "schema": "biella.drive_batch/v1", "every_completed_tasks": DRIVE_TASK_INTERVAL,
                "part_max_bytes": DRIVE_PART_MAX_BYTES, "baseline_commit": baseline_commit,
                "baseline_completed_ids": baseline, "package_base_commit": None,
                "pending": None, "status": "BATCHING", "previous_pending_commit": prior.get("commit") if prior.get("status") == "PENDING" else None,
            }
        payload = dict(prior)
        requested_at = _now()
        source_identity = source_publication_identity(repo)
        payload.update({
            "schema": "biella.publication_cursor/v3", "status": "PENDING",
            "commit": commit, "tree": tree, "task_id": task_id,
            "requested_at": requested_at, "execution_authority": False,
            "source_identity": source_identity,
            "publication_ref": source_identity["publication_ref"],
            "publication_intent": {
                "commit": commit, "tree": tree, "task_id": task_id,
                "requested_at": requested_at, "publication_ref": source_identity["publication_ref"],
            },
            "semantic_bindings": prior.get("semantic_bindings", {}),
            "completed_ids": completed, "program_finished": finished, "drive_batch": batch,
            "verified_files": prior.get("verified_files", {}),
            "drive_folder_ids": prior.get("drive_folder_ids", {}),
            "task_program": minitz.program_identity(minitz.load()),
        })
        _schedule_drive(payload)
        _write_state(repo, path, payload)
    for workers in (_WORKERS, _DRIVE_WORKERS):
        worker = workers.get(str(repo.resolve()))
        if worker:
            worker[1].set()
    return payload


def finish_drive_batch(repo: Path, batch: dict[str, Any], receipt: dict[str, Any]) -> None:
    with _locked(repo) as path:
        current = _read_state_locked(repo, path)
        state = current["drive_batch"]
        if (state.get("pending") or {}).get("commit") != batch["commit"]:
            return
        state["last_receipt"] = {**receipt, "commit": batch["commit"], "attempted_at": _now()}
        if receipt.get("verified"):
            state.update({"baseline_completed_ids": batch["completed_ids"], "baseline_commit": batch["commit"],
                          "package_base_commit": batch["commit"], "pending": None, "status": "BATCHING", "failures": 0})
            _schedule_drive(current)
            github = current.get("last_receipt") or {}
            if github.get("commit") == current.get("commit") and github.get("github") == "VERIFIED":
                same_revision = current.get("commit") == batch["commit"]
                current["status"] = "PENDING" if state.get("pending") else ("SYNCED" if same_revision else "BATCHING")
                github["drive"] = "PENDING" if state.get("pending") else ("VERIFIED" if same_revision else "BATCHING")
        else:
            state["status"] = "PENDING"
            state["failures"] = int(state.get("failures", 0)) + 1
        _write_state(repo, path, current)


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


def attach_publication_binding(
    repo: Path, *, implementation_ref: str, object_ref: str
) -> dict[str, str]:
    repo = Path(repo).resolve()
    for value, label in ((implementation_ref, "implementation_ref"), (object_ref, "object_ref")):
        if not isinstance(value, str) or "://" not in value or any(char.isspace() for char in value):
            raise ValueError(f"publication {label} is malformed")
    with _locked(repo) as path:
        state = _read_state_locked(repo, path)
        publication_ref = state.get("publication_ref")
        if not isinstance(publication_ref, str):
            raise PublicationStateError("publication semantic identity is not established")
        payload = {
            "publication_ref": publication_ref,
            "implementation_ref": implementation_ref,
            "object_ref": object_ref,
            "execution_authority": False,
        }
        binding_ref = f"publication-binding://sha256/{_sha(payload)}"
        binding = {**payload, "binding_ref": binding_ref}
        state.setdefault("semantic_bindings", {})[binding_ref] = binding
        _write_state(repo, path, state)
    return binding


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    if ancestor == descendant:
        return True
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True, timeout=20,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise PublicationStateError(
        "could not verify publication ancestry: " + result.stderr.decode(errors="replace")[-1200:]
    )


def _verified_publication_commits(cursor: dict[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()
    for record in (cursor.get("verified_files") or {}).values():
        if isinstance(record, dict) and isinstance(record.get("commit"), str):
            values.add(record["commit"])
    batch = cursor.get("drive_batch") or {}
    if isinstance(batch, dict):
        for key in ("baseline_commit", "package_base_commit"):
            value = batch.get(key)
            if isinstance(value, str) and value:
                values.add(value)
    return tuple(sorted(values))


def publish_drive_revision(repo: Path, commit: str) -> dict[str, Any]:
    import biella_production_evidence as evidence
    targets = evidence.drive_publications(repo) + evidence.derived_drive_publications(repo) + evidence.control_drive_publications(repo)
    files, errors = [], []
    cursor = read_publication(repo)
    for prior_commit in _verified_publication_commits(cursor):
        if prior_commit != commit and not _is_ancestor(repo, prior_commit, commit):
            return {
                "verified": False, "files": files,
                "errors": [{"error": f"non-ancestor canonical publication replacement rejected: {prior_commit} -> {commit}"}],
                "source_state": "RECONCILIATION_REQUIRED",
            }
    options = ["--retries", "1", "--low-level-retries", "1", "--contimeout", "5s", "--timeout", "15s"]
    for relative, destination in dict.fromkeys(targets):
        cursor = read_publication(repo)
        if (cursor.get("last_receipt") or {}).get("source_state") == "RECONCILIATION_REQUIRED":
            return {"verified": False, "files": files, "errors": [{"error": "known source conflict; canonical Drive update deferred"}]}
        if cursor.get("commit") != commit and ((cursor.get("drive_batch") or {}).get("pending") or {}).get("commit") != commit:
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
                latest = _read_state_locked(repo, path)
                latest.setdefault("verified_files", {})[destination] = record
                _write_state(repo, path, latest)
            files.append(record)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            errors.append({"path": relative, "destination": destination, "error": _error_detail(exc)})
    return {"verified": not errors, "files": files, "errors": errors}


def drain_once(repo: Path, *, drive: bool = True, force_drive: bool = False) -> dict[str, Any]:
    repo = Path(repo)
    requested = read_publication(repo)
    if not requested.get("commit"):
        return requested
    if not requested.get("drive_batch"):
        requested = request_publication(repo, requested.get("task_id", "RECONCILE"), requested)
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
    # GitHub is per-commit; routine Drive writes are deferred until five real closures.
    receipt["drive"] = "BATCHING"
    if force_drive and receipt.get("source_state") != "RECONCILIATION_REQUIRED":
        try:
            outcome = publish_drive_revision(repo, commit)
            receipt["drive"] = "VERIFIED" if outcome.get("verified") else "PENDING"
            receipt["drive_readback"] = outcome
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            receipt["drive"] = "PENDING"
            receipt["errors"].append({"target": "drive", "error": _error_detail(exc)})
    elif (requested.get("drive_batch") or {}).get("pending"):
        receipt["drive"] = "PENDING"
    with _locked(repo) as path:
        current = _read_state_locked(repo, path)
        if current.get("commit") == commit:
            current["last_receipt"] = receipt
            current["status"] = "BATCHING" if receipt["github"] == "VERIFIED" and receipt["drive"] == "BATCHING" else ("SYNCED" if receipt["github"] == receipt["drive"] == "VERIFIED" else "PENDING")
            current["consecutive_failures"] = 0 if receipt["github"] == "VERIFIED" else int(current.get("consecutive_failures", 0)) + 1
            _write_state(repo, path, current)
    if drive and not force_drive and (current.get("drive_batch") or {}).get("pending"):
        drain_drive_once(repo)
        current = read_publication(repo)
    return current


def _package_root(repo: Path) -> Path:
    runtime = os.environ.get("BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT")
    return (Path(runtime) if runtime else _state_path(repo).parent) / "drive-packages"


def _remote_package_digest(target: str) -> tuple[str, int]:
    # Stream remote bytes: a 3.8-GB part must never be buffered in RAM.
    digest, size = hashlib.sha256(), 0
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(["rclone", "cat", target, "--retries", "1", "--low-level-retries", "1", "--contimeout", "10s", "--timeout", "60s"], stdout=subprocess.PIPE, stderr=errors)
        try:
            assert proc.stdout is not None
            for block in iter(lambda: proc.stdout.read(1024 * 1024), b""):
                digest.update(block); size += len(block)
            if proc.wait() != 0:
                errors.seek(0)
                raise RuntimeError("Drive package readback failed: " + errors.read().decode(errors="replace")[-3000:])
        finally:
            if proc.stdout:
                proc.stdout.close()
            if proc.poll() is None:
                proc.terminate(); proc.wait()
    return digest.hexdigest(), size


def _publish_package_file(repo: Path, source: Path, destination: str, digest: str, commit: str) -> dict[str, Any]:
    size = source.stat().st_size
    if size > DRIVE_PART_MAX_BYTES:
        raise ValueError("refusing an oversized Drive package part")
    prior = (read_publication(repo).get("verified_files") or {}).get(destination, {})
    if prior.get("sha256") == digest and prior.get("bytes") == size and prior.get("file_id"):
        return prior
    target = _drive_target(repo, destination)
    options = ["--retries", "1", "--low-level-retries", "1", "--contimeout", "10s", "--timeout", "60s"]
    metadata = None
    try:
        metadata = json.loads(_remote(["rclone", "lsjson", target, "--stat", *options], timeout=75).stdout)
    except subprocess.CalledProcessError as exc:
        if exc.returncode not in (3, 4):
            raise
    matches = bool(metadata and metadata.get("Size") == size and _remote_package_digest(target) == (digest, size))
    if not matches:
        # Inactivity timeout belongs to rclone; productive large transfers have no short wall-clock deadline.
        subprocess.run(["rclone", "copyto", str(source), target, "--checksum", "--stats", "0", *options], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        if _remote_package_digest(target) != (digest, size):
            raise RuntimeError("Drive package size/SHA-256 readback mismatch")
        metadata = json.loads(_remote(["rclone", "lsjson", target, "--stat", *options], timeout=75).stdout)
    if not metadata or not metadata.get("ID"):
        raise RuntimeError("package bytes matched but Drive file identity is missing")
    record = {"destination": destination, "sha256": digest, "bytes": size, "file_id": metadata["ID"], "status": "VERIFIED", "commit": commit, "verified_at": _now()}
    with _locked(repo) as path:
        current = _read_state_locked(repo, path)
        current.setdefault("verified_files", {})[destination] = record
        _write_state(repo, path, current)
    return record


def drain_drive_once(repo: Path) -> dict[str, Any]:
    repo = Path(repo)
    requested = read_publication(repo)
    batch = (requested.get("drive_batch") or {}).get("pending")
    if not batch:
        return {"status": "BATCHING"}
    # Only serialize the Drive worker. This lock never covers task execution or GitHub publication.
    with _state_path(repo).with_name("biella-drive-worker.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "ALREADY_PUBLISHING"}
        try:
            requested = read_publication(repo)
            batch = (requested.get("drive_batch") or {}).get("pending")
            if not batch:
                return {"status": "BATCHING"}
            if (requested.get("last_receipt") or {}).get("source_state") == "RECONCILIATION_REQUIRED":
                raise RuntimeError("Known source conflict remains unresolved; Drive checkpoint not overwritten")
            remote = _remote(["git", "-C", str(repo), "ls-remote", "origin", "refs/heads/main"]).stdout.decode().split()
            current = read_publication(repo)
            if not remote or remote[0] not in {batch["commit"], current["commit"]}:
                raise RuntimeError("Drive checkpoint source differs from current remotely verified source")
            subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", batch["commit"], remote[0]], check=True, capture_output=True)
            import biella_drive_package as package
            root = _package_root(repo)
            manifest = package.build_package(repo, batch, root, max_bytes=DRIVE_PART_MAX_BYTES)
            folder = root / batch["commit"]
            records = []
            for part in manifest["parts"]:
                records.append(_publish_package_file(repo, folder / part["name"], DRIVE_PACKAGE_DESTINATION + "/" + part["name"], part["sha256"], batch["commit"]))
            record = _publish_package_file(repo, folder / "manifest.json", DRIVE_PACKAGE_DESTINATION + "/" + manifest["manifest_name"], package.file_digest(folder / "manifest.json"), batch["commit"])
            controls = publish_drive_revision(repo, batch["commit"])
            receipt = {"verified": controls.get("verified", False), "parts": records, "manifest": record, "controls": controls}
            finish_drive_batch(repo, batch, receipt)
            if receipt["verified"]:
                # Only transfer staging is removed; committed source/proof and remote parts remain.
                for part in manifest["parts"]:
                    (folder / part["name"]).unlink(missing_ok=True)
            return receipt
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            receipt = {"verified": False, "error": _error_detail(exc)}
            finish_drive_batch(repo, batch, receipt)
            return receipt
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


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
    # Reconcile the committed snapshot on startup without counting attempts/restarts.
    cursor = read_publication(repo)
    if cursor.get("commit"):
        head = _git(repo, "rev-parse", "HEAD")
        request_publication(repo, cursor.get("task_id", "RECONCILE"), {"commit": head, "tree": _git(repo, "rev-parse", head + "^{tree}")})
    def run_git() -> None:
        while not stop.is_set():
            try:
                cursor = read_publication(repo)
                prior = cursor.get("last_receipt") or {}
                if prior.get("commit") != cursor.get("commit") or prior.get("github") != "VERIFIED":
                    result = drain_once(repo, drive=False)
                    if (result.get("last_receipt") or {}).get("github") != "VERIFIED":
                        record_failure(json.dumps(result.get("last_receipt") or {}, sort_keys=True), result.get("task_id"))
            except Exception as exc:
                record_failure(str(exc))
            wake.wait(30.0); wake.clear()
    drive_wake, drive_stop = threading.Event(), threading.Event()
    def run_drive() -> None:
        while not drive_stop.is_set():
            try:
                result = drain_drive_once(repo)
                if result.get("verified") is False:
                    record_failure(json.dumps(result, sort_keys=True))
            except Exception as exc:
                record_failure(str(exc))
            batch = read_publication(repo).get("drive_batch") or {}
            failures = int(batch.get("failures", 0))
            drive_wake.wait(min(300.0, 30.0 * 2 ** min(failures, 4))); drive_wake.clear()
    thread = threading.Thread(target=run_git, name="biella-publication", daemon=True)
    drive_thread = threading.Thread(target=run_drive, name="biella-drive-publication", daemon=True)
    _WORKERS[key] = (thread, wake, stop)
    _DRIVE_WORKERS[key] = (drive_thread, drive_wake, drive_stop)
    thread.start(); drive_thread.start()


def stop_worker(repo: Path) -> None:
    for workers in (_WORKERS, _DRIVE_WORKERS):
        entry = workers.pop(str(Path(repo).resolve()), None)
        if entry:
            entry[2].set(); entry[1].set()
