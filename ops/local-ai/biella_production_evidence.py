from __future__ import annotations

import hashlib
import json
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
    return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=text, check=check)


def _dirty_paths(repo_root: Path) -> set[str]:
    proc = _git(repo_root, "status", "--porcelain", "--untracked-files=all")
    paths: set[str] = set()
    for raw in proc.stdout.splitlines():
        if len(raw) < 4:
            continue
        name = raw[3:]
        if " -> " in name:
            name = name.split(" -> ", 1)[1]
        paths.add(name.strip('"'))
    return paths


def assert_remote_source_current(repo_root: Path) -> dict[str, str]:
    repo_root = Path(repo_root)
    branch = _git(repo_root, "branch", "--show-current").stdout.strip()
    if branch != "main":
        raise SourceAlignmentError(f"canonical checkout is on branch {branch or 'DETACHED'}, expected main")
    fetched = _git(repo_root, "fetch", "--quiet", "origin", "main", check=False)
    if fetched.returncode != 0:
        detail = (fetched.stderr or fetched.stdout or "fetch failed").strip()
        raise SourceAlignmentError(f"cannot refresh origin/main: {detail}")
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
        ("docs/task-program/D_TASK_LEDGER.json", "gdrive:Biella/D_TASK_PROGRAM/D_TASK_LEDGER.json"),
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
