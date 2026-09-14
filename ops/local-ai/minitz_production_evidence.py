from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

_active_repo_root = Path(os.environ.get("MINITZ_REPO_ROOT") or Path(__file__).resolve().parents[2]).resolve()
_active_src_root = _active_repo_root / "src"
if (_active_src_root / "minitz").is_dir() and str(_active_src_root) not in sys.path:
    sys.path.insert(0, str(_active_src_root))

from minitz_codex_routing import Route
import minitz_task_ids as task_ids
from minitz_production_state import mark_task_complete, sync_current_state, load_project_production, find_task

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


def result_schema(expected_task_id: str | None = None) -> dict[str, Any]:
    task_id_schema: dict[str, Any] = {"type": "string", "minLength": 1, "maxLength": 128}
    if expected_task_id is not None:
        task_id_schema = {"type": "string", "const": str(expected_task_id)}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["task_id", "status", "summary", "evidence"],
        "properties": {
            "task_id": task_id_schema,
            "status": {"type": "string", "enum": sorted(_ALLOWED)},
            "summary": {"type": "string", "maxLength": 16384},
            "evidence": {"type": "array", "maxItems": 256, "items": {"type": "string", "maxLength": 16384}},
        },
    }


def parse_result(path: Path, expected_task_id: str) -> TaskResult:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid structured result: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("structured result must be an object")
    raw_task_id = raw.get("task_id", "")
    if not isinstance(raw_task_id, str):
        raise ValueError("task_id must be text")
    task_id = task_ids.canonical_task_id(raw_task_id)
    expected_canonical = task_ids.canonical_task_id(expected_task_id)
    if task_id != expected_canonical:
        raise ValueError(f"task_id mismatch: expected {expected_canonical}, got {raw_task_id}")
    status = raw.get("status", "")
    if not isinstance(status, str) or status not in _ALLOWED:
        raise ValueError(f"unsupported result status: {status}")
    summary = raw.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("summary must be text")
    summary = summary.strip()
    evidence_raw = raw.get("evidence", [])
    if not isinstance(evidence_raw, list) or len(evidence_raw) > 256:
        raise ValueError("evidence must be a bounded array")
    evidence_items: list[str] = []
    for item in evidence_raw:
        if isinstance(item, str):
            clean = item.strip()
        elif isinstance(item, Mapping):
            clean = json.dumps(dict(item), sort_keys=True, separators=(",", ":"))
        else:
            raise ValueError("evidence entries must be text or objects")
        if len(clean.encode()) > 16384:
            raise ValueError("evidence entry is unbounded")
        if clean:
            evidence_items.append(clean)
    return TaskResult(task_id, status, summary, tuple(evidence_items))


def apply_result(repo_root: Path, project_root: Path, result: TaskResult, route: Route) -> None:
    del route
    production = load_project_production(project_root)
    task = find_task(production, result.task_id)
    if task.status in _COMPLETE:
        return
    if result.status == "CONTINUE":
        return
    if result.status in _COMPLETE:
        evidence_items = result.evidence or ((result.summary or "Task work completed."),)
        mark_task_complete(repo_root, project_root, result.task_id, "COMPLETE", evidence_items)
        return
    raise ValueError(f"unsupported result status: {result.status}")


_CONTINUITY_PATHS = (
    "docs/project-state/03_MINITZ_CURRENT_STATE.md",
    "docs/project-state/04_MINITZ_ACTIVE_TASK.md",
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


def _path_digest(path: Path) -> str | None:
    if path.is_symlink():
        return "symlink:" + hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def workspace_snapshot(repo_root: Path) -> dict[str, str | None]:
    """Exact dirty-byte boundary, not an ownership claim by directory name."""
    return {name: _path_digest(Path(repo_root) / name) for name in sorted(_dirty_paths(repo_root))}


def task_owned_outputs(repo_root: Path, baseline: Mapping[str, str | None],
                       previous: Mapping[str, str | None]) -> dict[str, str | None]:
    current = workspace_snapshot(repo_root)
    # Pre-existing unrelated dirty files are never absorbed, even if edited later.
    return {name: digest for name, digest in current.items()
            if name not in _CONTINUITY_PATHS and (name not in baseline or name in previous)}


def _referenced_task_proof(repo_root: Path, result: TaskResult) -> dict[str, str | None]:
    """Retain explicitly named task reports and their same-namespace raw inputs."""
    root = Path(repo_root).resolve()
    found: dict[str, str | None] = {}
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
    for text in result.evidence:
        for token in re.findall(r"(?:/|[A-Za-z0-9_.-]+/)[^\s`\"<>;,]*?\.json", text):
            raw = Path(token)
            candidates = [raw] if raw.is_absolute() else [root / raw, root / "projects/minitz-games" / raw]
            for report_path in candidates:
                try:
                    report_path = report_path.resolve()
                    report_path.relative_to(root)
                    report = json.loads(report_path.read_bytes())
                    if not isinstance(report, dict) or task_ids.canonical_task_id(str(report.get("task_id", ""))) != task_ids.canonical_task_id(result.task_id):
                        continue
                except (OSError, ValueError):
                    continue
                namespace = report_path.parent
                pending = [report_path]
                while pending:
                    path = pending.pop()
                    relative = path.relative_to(root).as_posix()
                    if relative in found:
                        continue
                    found[relative] = _path_digest(path)
                    if path.suffix != ".json":
                        continue
                    try:
                        payload = json.loads(path.read_bytes())
                    except (OSError, ValueError):
                        continue
                    for value in strings(payload):
                        if len(value) > 4096 or "\n" in value:
                            continue
                        ref = Path(value)
                        for candidate in ([ref] if ref.is_absolute() else [path.parent / ref, root / ref]):
                            try:
                                candidate = candidate.resolve()
                                candidate.relative_to(namespace)
                                if candidate.is_file() and candidate.relative_to(root).as_posix() not in found:
                                    pending.append(candidate)
                            except (OSError, ValueError):
                                continue
    return found


def enforce_clean_completion_boundary(repo_root: Path, result: TaskResult, *,
                                      owned_files: Mapping[str, str | None] | None = None) -> TaskResult:
    """Persist current task-owned bytes; validation receipts never gate progression."""
    if result.status not in _COMPLETE:
        return result
    try:
        dirty = _dirty_paths(Path(repo_root)) - set(_CONTINUITY_PATHS)
        owned = sorted(dirty & set(dict(owned_files or {})))
        if not owned:
            return result
        for name in owned:
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts:
                raise ValueError(f"invalid task output path: {name}")
            if not (Path(repo_root) / name).exists():
                raise ValueError(f"task-owned output is missing: {name}")
        _git(repo_root, "add", "-f", "--", *owned)
        _git(repo_root, "commit", "--only", "-m", f"production: persist {result.task_id} output", "--", *owned)
        commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        return TaskResult(result.task_id, result.status, result.summary,
                          result.evidence + (f"Task-owned output committed locally: {commit}",))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return TaskResult(result.task_id, "CONTINUE",
                          f"Persist the current task-owned output before advancing: {exc}", result.evidence)


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


def persist_continuity(repo_root: Path, task_id: str) -> dict[str, str]:
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


def publish_derived_task_ledger(repo_root: Path) -> None:
    """Compatibility hook: derived local projections have no remote publisher or progression authority."""
    del repo_root
    return None
