from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from biella_codex_routing import Route
import biella_task_ids as task_ids
from biella_production_state import mark_task_complete, sync_current_state, load_project_production, find_task

_ALLOWED = {"COMPLETE", "COMPLETE_ALREADY", "CONTINUE"}
_COMPLETE = {"COMPLETE", "COMPLETE_ALREADY"}


class SourceAlignmentError(RuntimeError):
    pass


class SourceTransportError(RuntimeError):
    """Remote freshness is unavailable; this is not evidence of divergent source."""



@dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: str
    summary: str
    evidence: tuple[str, ...]


def result_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["task_id", "status", "summary", "evidence"],
        "properties": {
            "task_id": {"type": "string"},
            "status": {"type": "string", "enum": sorted(_ALLOWED)},
            "summary": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
    }


def parse_result(path: Path, expected_task_id: str) -> TaskResult:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid structured result: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("structured result must be an object")
    raw_task_id = str(raw.get("task_id", ""))
    task_id = task_ids.canonical_task_id(raw_task_id)
    expected_canonical = task_ids.canonical_task_id(expected_task_id)
    if task_id != expected_canonical:
        raise ValueError(f"task_id mismatch: expected {expected_canonical}, got {raw_task_id}")
    status = str(raw.get("status", ""))
    if status not in _ALLOWED:
        raise ValueError(f"unsupported result status: {status}")
    summary = str(raw.get("summary", "")).strip()
    evidence_raw = raw.get("evidence", [])
    if not isinstance(evidence_raw, list):
        raise ValueError("evidence must be an array")
    evidence = tuple(str(item).strip() for item in evidence_raw if str(item).strip())
    if status in _COMPLETE and not evidence:
        raise ValueError("completion requires evidence")
    return TaskResult(task_id, status, summary, evidence)


def apply_result(repo_root: Path, project_root: Path, result: TaskResult, route: Route) -> None:
    production = load_project_production(project_root)
    task = find_task(production, result.task_id)
    if task.status in _COMPLETE:
        return
    if result.status in _COMPLETE:
        mark_task_complete(repo_root, project_root, result.task_id, result.status, result.evidence)
        return
    if result.status == "CONTINUE":
        return
    raise ValueError(f"unsupported result status: {result.status}")


_CONTINUITY_PATHS = (
    "docs/project-state/03_BIELLA_CURRENT_STATE.md",
    "docs/project-state/04_BIELLA_ACTIVE_TASK.md",
    "projects/biella-games/docs/PRODUCTION.md",
    "docs/task-program/D_TASK_LEDGER.json",
)


def _git(repo_root: Path, *args: str, check: bool = True, text: bool = True):
    return subprocess.run(["git", "-C", str(repo_root), "-c", "core.hooksPath=/dev/null", *args], capture_output=True, text=text, check=check, timeout=25, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def _dirty_paths(repo_root: Path) -> set[str]:
    proc = _git(repo_root, "status", "--porcelain=v1", "-z", "--untracked-files=all", text=False)
    records = iter(proc.stdout.split(b"\0"))
    paths: set[str] = set()
    for raw in records:
        if len(raw) < 4:
            continue
        paths.add(os.fsdecode(raw[3:]))
        if raw[:1] in (b"R", b"C") or raw[1:2] in (b"R", b"C"):
            original = next(records, b"")
            if original:
                paths.add(os.fsdecode(original))
    return paths


def completion_boundary_dirty_paths(repo_root: Path) -> tuple[str, ...]:
    try:
        dirty = _dirty_paths(Path(repo_root))
    except subprocess.CalledProcessError:
        return ()
    allowed = {path for path in _CONTINUITY_PATHS if (Path(repo_root) / path).exists()}
    return tuple(sorted(dirty - allowed))


def enforce_clean_completion_boundary(repo_root: Path, result: TaskResult) -> TaskResult:
    """Finalize validated task-owned bytes directly; never replay work just to commit."""
    if result.status not in _COMPLETE:
        return result
    from biella_execution_map import task_entry
    try:
        dirty = _dirty_paths(Path(repo_root)) - set(_CONTINUITY_PATHS)
        entry = task_entry(repo_root, result.task_id)
        root = entry["execution_root"] if entry else "projects/biella-games"
        if root == ".":
            prefixes = ("src/", "ops/", "tests/", "docs/", "website/")
        elif root == "website":
            prefixes = ("website/", "ops/control_gateway/", ".github/workflows/")
        else:
            prefixes = (root.rstrip("/") + "/",)
        owned = sorted(path for path in dirty if path.startswith(prefixes))
        if not owned:
            return result
        _git(repo_root, "add", "--", *owned)
        _git(repo_root, "commit", "--only", "-m", f"production: persist validated {result.task_id} output", "--", *owned)
        commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        return TaskResult(result.task_id, result.status, result.summary,
                          result.evidence + (f"Task-owned output committed locally: {commit}",))
    except (OSError, subprocess.SubprocessError) as exc:
        return TaskResult(result.task_id, "CONTINUE",
            f"Repair only the local output-persistence operation; reuse completed validation and do not repeat the task: {exc}",
            result.evidence)


def assert_remote_source_current(repo_root: Path) -> dict[str, str]:
    repo_root = Path(repo_root)
    branch = _git(repo_root, "branch", "--show-current").stdout.strip()
    if branch != "main":
        raise SourceAlignmentError(f"canonical checkout is on branch {branch or 'DETACHED'}, expected main")
    try:
        fetched = _git(repo_root, "fetch", "--quiet", "origin", "main", check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SourceTransportError(f"remote freshness temporarily unavailable: {exc}") from exc
    if fetched.returncode != 0:
        detail = (fetched.stderr or fetched.stdout or "fetch failed").strip()
        raise SourceTransportError(f"cannot refresh origin/main: {detail}")
    head = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    tree = _git(repo_root, "rev-parse", "HEAD^{tree}").stdout.strip()
    remote = _git(repo_root, "rev-parse", "refs/remotes/origin/main").stdout.strip()
    if head == remote:
        return {"state": "ALIGNED", "commit": head, "tree": tree, "remote_commit": remote}
    remote_is_ancestor = _git(repo_root, "merge-base", "--is-ancestor", remote, head, check=False)
    if remote_is_ancestor.returncode == 0:
        return {"state": "LOCAL_AHEAD", "commit": head, "tree": tree, "remote_commit": remote}
    local_is_ancestor = _git(repo_root, "merge-base", "--is-ancestor", head, remote, check=False)
    if local_is_ancestor.returncode == 0:
        raise SourceAlignmentError(f"VPS source behind origin/main: local {head}, remote {remote}")
    raise SourceAlignmentError(f"local main diverged from origin/main: local {head}, remote {remote}")


def drive_publications(repo_root: Path) -> tuple[tuple[str, str], ...]:
    del repo_root
    return (
        ("docs/project-state/03_BIELLA_CURRENT_STATE.md", "gdrive:Biella/CURRENT/03_BIELLA_CURRENT_STATE.md"),
        ("docs/project-state/04_BIELLA_ACTIVE_TASK.md", "gdrive:Biella/CURRENT/04_BIELLA_ACTIVE_TASK.md"),
        ("projects/biella-games/docs/PRODUCTION.md", "gdrive:Biella/PROJECTS/GAMES/PRODUCTION.md"),
    )


def derived_drive_publications(repo_root: Path) -> tuple[tuple[str, str], ...]:
    del repo_root
    return (
        ("docs/task-program/D_TASK_MANIFEST.json", "gdrive:Biella/D_TASK_PROGRAM/D_TASK_MANIFEST.json"),
        ("docs/task-program/D_NEXT_100_TASKS.json", "gdrive:Biella/D_TASK_PROGRAM/D_NEXT_100_TASKS.json"),
        ("docs/task-program/D_NEXT_100_TASKS.md", "gdrive:Biella/D_TASK_PROGRAM/D_NEXT_100_TASKS.md"),
        ("docs/task-program/D_TASK_LEDGER.json", "gdrive:Biella/D_TASK_PROGRAM/D_TASK_LEDGER.json"),
    )



def control_drive_publications(repo_root: Path) -> tuple[tuple[str, str], ...]:
    """Current control files; preserve existing identities and the canonical folder layout."""
    del repo_root
    return (
        ("docs/project-state/07_BIELLA_PRODUCTION_SYSTEM.md", "gdrive:Biella/CURRENT/07_BIELLA_PRODUCTION_SYSTEM.md"),
        ("docs/project-state/00_BIELLA_PROJECT_OPERATING_CONTRACT.md", "gdrive:Biella/CURRENT/00_START_HERE/00_BIELLA_PROJECT_OPERATING_CONTRACT.md"),
        ("docs/project-state/BIELLA_PROJECT_INSTRUCTIONS.md", "gdrive:Biella/CURRENT/00_START_HERE/BIELLA_CHATGPT_PROJECT_INSTRUCTIONS.md"),
    )


def _publish_exact_files(repo_root: Path, publications: tuple[tuple[str, str], ...]) -> None:
    for relative, target in publications:
        local = Path(repo_root) / relative
        if not local.exists():
            continue
        subprocess.run(["rclone", "copyto", str(local), target], check=True, stdout=subprocess.DEVNULL)
        remote = subprocess.run(["rclone", "cat", target], check=True, capture_output=True).stdout
        if hashlib.sha256(local.read_bytes()).hexdigest() != hashlib.sha256(remote).hexdigest():
            raise RuntimeError(f"Drive readback digest mismatch for {local.name}")


def publish_drive_continuity(repo_root: Path) -> None:
    _publish_exact_files(Path(repo_root), drive_publications(Path(repo_root)))


def publish_derived_task_ledger(repo_root: Path) -> None:
    _publish_exact_files(Path(repo_root), derived_drive_publications(Path(repo_root)))


def persist_local_continuity(repo_root: Path, task_id: str) -> dict[str, str]:
    """Commit only current continuity. Remote transport is a separate operation."""
    repo_root = Path(repo_root)
    if _git(repo_root, "branch", "--show-current").stdout.strip() != "main":
        raise SourceAlignmentError("canonical local continuity requires main")
    dirty = _dirty_paths(repo_root)
    paths = sorted(dirty & set(_CONTINUITY_PATHS))
    if paths:
        _git(repo_root, "add", "--", *paths)
        staged = _git(repo_root, "diff", "--cached", "--quiet", "--", *paths, check=False)
        if staged.returncode == 1:
            _git(repo_root, "commit", "--only", "-m", f"production: advance after {task_id}", "--", *paths)
        elif staged.returncode != 0:
            raise RuntimeError("cannot inspect local continuity changes")
    return {"commit": _git(repo_root, "rev-parse", "HEAD").stdout.strip(),
            "tree": _git(repo_root, "rev-parse", "HEAD^{tree}").stdout.strip()}


def persist_continuity(repo_root: Path, task_id: str, *, publish_drive: bool = True) -> dict[str, str]:
    repo_root = Path(repo_root)
    assert_remote_source_current(repo_root)
    dirty = _dirty_paths(repo_root)
    allowed = {path for path in _CONTINUITY_PATHS if (repo_root / path).exists()}
    unexpected = dirty - allowed
    if unexpected:
        raise RuntimeError("unexpected uncommitted task output: " + ", ".join(sorted(unexpected)))
    if dirty:
        _git(repo_root, "add", *sorted(allowed))
        staged = _git(repo_root, "diff", "--cached", "--quiet", check=False)
        if staged.returncode == 1:
            _git(repo_root, "commit", "-m", f"production: advance after {task_id}")
        elif staged.returncode != 0:
            raise RuntimeError("failed to inspect staged continuity changes")
    head = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    tree = _git(repo_root, "rev-parse", "HEAD^{tree}").stdout.strip()
    _git(repo_root, "push", "origin", "HEAD:main")
    remote = subprocess.run(["git", "-C", str(repo_root), "ls-remote", "origin", "refs/heads/main"], capture_output=True, text=True, check=True).stdout.split()
    if not remote or remote[0] != head:
        raise RuntimeError("GitHub main readback mismatch")
    if publish_drive:
        publish_drive_continuity(repo_root)
    return {"commit": head, "tree": tree}


def continuity_changes(repo_root: Path) -> bool:
    try:
        dirty = _dirty_paths(Path(repo_root))
    except subprocess.CalledProcessError:
        return False
    return bool(dirty & set(_CONTINUITY_PATHS))


def assert_clean_task_workspace(repo_root: Path) -> None:
    try:
        dirty = _dirty_paths(Path(repo_root))
    except subprocess.CalledProcessError:
        return
    if dirty:
        raise RuntimeError("production task requires a clean canonical worktree: " + ", ".join(sorted(dirty)))


def unexpected_dirty_paths(repo_root: Path) -> set[str]:
    try:
        dirty = _dirty_paths(Path(repo_root))
    except subprocess.CalledProcessError:
        return set()
    allowed = {path for path in _CONTINUITY_PATHS if (Path(repo_root) / path).exists()}
    return dirty - allowed
