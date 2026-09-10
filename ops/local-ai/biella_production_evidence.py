from __future__ import annotations

import hashlib
import json
import os
import re
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
    task_revision: int | None = None
    task_digest: str | None = None
    scope_ref: str | None = None
    family_revision: str | None = None
    authority_ref: str | None = None
    accepted_criteria: tuple[str, ...] = ()

    @property
    def completion_evidence(self) -> tuple[object, ...]:
        """Decode only typed family records; legacy strings remain evidence text."""
        try:
            from biella.validation import ValidationCompletionEvidence
        except ImportError:
            return ()
        records: list[ValidationCompletionEvidence] = []
        for item in self.evidence:
            if not isinstance(item, str) or not item.lstrip().startswith("{"):
                continue
            try:
                raw = json.loads(item)
                if isinstance(raw, Mapping) and "kind" in raw:
                    records.append(ValidationCompletionEvidence.from_mapping(raw))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return tuple(records)


def result_schema() -> dict[str, Any]:
    typed_evidence = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "kind", "task_id", "task_revision", "task_digest", "scope_ref",
            "evidence_ref", "evidence_sha256", "implementation_ref", "verdict",
        ],
        "properties": {
            "kind": {"type": "string", "maxLength": 128},
            "task_id": {"type": "string", "maxLength": 128},
            "task_revision": {"type": ["integer", "null"], "minimum": 1},
            "task_digest": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
            "scope_ref": {"type": ["string", "null"], "maxLength": 2048},
            "evidence_ref": {"type": "string", "maxLength": 2048},
            "evidence_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "implementation_ref": {"type": "string", "maxLength": 2048},
            "verdict": {"type": "string", "enum": ["ERROR", "FAIL", "FAILED", "INCONCLUSIVE", "PASS"]},
            "criterion": {"type": ["string", "null"], "maxLength": 512},
            "evidence_state": {"type": "string", "enum": ["CURRENT", "HISTORICAL"]},
            "source_ref": {"type": ["string", "null"], "maxLength": 2048},
            "family_revision": {"type": ["string", "null"], "maxLength": 128},
            "authority_ref": {"type": ["string", "null"], "maxLength": 2048},
            "accepted_criteria": {"type": "array", "maxItems": 128, "items": {"type": "string", "maxLength": 512}},
            "implementation_refs": {"type": "array", "maxItems": 256, "items": {"type": "string", "maxLength": 2048}},
            "value_receipt_refs": {"type": "array", "maxItems": 256, "items": {"type": "string", "maxLength": 2048}},
            "record_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["task_id", "status", "summary", "evidence", "task_revision", "task_digest", "scope_ref", "family_revision", "authority_ref", "accepted_criteria"],
        "properties": {
            "task_id": {"type": "string", "minLength": 1, "maxLength": 128},
            "status": {"type": "string", "enum": sorted(_ALLOWED)},
            "summary": {"type": "string", "maxLength": 16384},
            "evidence": {
                "type": "array", "maxItems": 256,
                "items": {"type": "string", "minLength": 1, "maxLength": 16384, "description": "Typed MiniTZ completion evidence is serialized as canonical JSON text."},
            },
            "task_revision": {"type": "integer", "minimum": 1},
            "task_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "scope_ref": {"type": "string", "maxLength": 2048},
            "family_revision": {"type": ["string", "null"], "maxLength": 128},
            "authority_ref": {"type": ["string", "null"], "maxLength": 2048},
            "accepted_criteria": {"type": "array", "maxItems": 128, "items": {"type": "string", "maxLength": 512}},
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
    if not isinstance(status, str):
        raise ValueError("status must be text")
    if status not in _ALLOWED:
        raise ValueError(f"unsupported result status: {status}")
    summary = raw.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("summary must be text")
    summary = summary.strip()
    evidence_raw = raw.get("evidence", [])
    if not isinstance(evidence_raw, list):
        raise ValueError("evidence must be an array")
    if len(evidence_raw) > 256:
        raise ValueError("evidence is unbounded")
    evidence: list[str] = []
    evidence_is_completion = status in _COMPLETE
    for item in evidence_raw:
        if evidence_is_completion:
            if not isinstance(item, str):
                if not isinstance(item, Mapping):
                    raise ValueError("completion evidence entries must be typed JSON objects")
                try:
                    from biella.validation import ValidationCompletionEvidence
                    evidence.append(ValidationCompletionEvidence.from_mapping(item).to_json())
                    continue
                except (ImportError, TypeError, ValueError) as exc:
                    raise ValueError(f"invalid typed completion evidence: {exc}") from exc
            clean = item.strip()
            if not clean or len(clean.encode()) > 16384:
                raise ValueError("completion evidence text is empty or unbounded")
            if not clean.startswith("{"):
                raise ValueError("completion evidence must be serialized typed JSON")
            try:
                parsed = json.loads(clean)
            except json.JSONDecodeError as exc:
                raise ValueError(f"completion evidence must be serialized typed JSON: {exc}") from exc
            try:
                from biella.validation import ValidationCompletionEvidence
                evidence.append(ValidationCompletionEvidence.from_mapping(parsed).to_json())
            except (ImportError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid typed completion evidence: {exc}") from exc
            continue

        if isinstance(item, str):
            clean = item.strip()
            if not clean or len(clean.encode()) > 16384:
                raise ValueError("evidence text is empty or unbounded")
            evidence.append(clean)
            continue
        if not isinstance(item, Mapping):
            raise ValueError("evidence entries must be bounded text or typed objects")
        try:
            from biella.validation import ValidationCompletionEvidence
            evidence.append(ValidationCompletionEvidence.from_mapping(item).to_json())
        except (ImportError, TypeError, ValueError) as exc:
            # Preserve compatibility for non-completion outputs while still failing
            # when typed evidence is malformed.
            raise ValueError(f"invalid typed completion evidence: {exc}") from exc
    if evidence_is_completion and not evidence:
        raise ValueError("completion requires evidence")
    task_revision = raw.get("task_revision")
    if task_revision is not None and (isinstance(task_revision, bool) or not isinstance(task_revision, int) or task_revision < 1):
        raise ValueError("task_revision must be a positive integer")
    task_digest = raw.get("task_digest")
    if task_digest is not None and (not isinstance(task_digest, str) or re.fullmatch(r"[0-9a-f]{64}", task_digest) is None):
        raise ValueError("task_digest must be an exact SHA-256 digest")
    optional_text: dict[str, str | None] = {}
    for key, maximum in (("scope_ref", 2048), ("family_revision", 128), ("authority_ref", 2048)):
        value = raw.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum):
            raise ValueError(f"{key} is malformed or unbounded")
        optional_text[key] = value
    accepted_raw = raw.get("accepted_criteria", [])
    if not isinstance(accepted_raw, list) or len(accepted_raw) > 128 or any(not isinstance(item, str) or not item.strip() or len(item.encode()) > 512 for item in accepted_raw):
        raise ValueError("accepted_criteria is malformed or unbounded")
    accepted_criteria = tuple(item.strip() for item in accepted_raw)
    if len(set(accepted_criteria)) != len(accepted_criteria):
        raise ValueError("accepted_criteria contains duplicates")
    return TaskResult(
        task_id, status, summary, tuple(evidence), task_revision, task_digest,
        optional_text["scope_ref"], optional_text["family_revision"],
        optional_text["authority_ref"], accepted_criteria,
    )


def _minitz_completion_contract(task_id: str) -> tuple[dict[str, object], Mapping[str, object]]:
    """Resolve exact live MiniTZ identity from the sole Task Program authority."""
    import minitz_task_program as minitz

    program = minitz.load()
    row = minitz.task_by_id(program, task_id)
    completion = row.get("completion") if isinstance(row.get("completion"), Mapping) else {}
    required = completion.get("minimum_truth_required", ()) if isinstance(completion, Mapping) else ()
    if not isinstance(required, list):
        required = ()
    revision = int(row["revision"])
    digest = minitz.task_digest(row)
    return ({
        "task_id": str(row["task_id"]),
        "task_revision": revision,
        "task_digest": digest,
        "scope_ref": f"task://minitz/{row['task_id']}/{revision}",
        "required_criteria": tuple(str(item) for item in required),
    }, row)


def _admit_minitz_result(result: TaskResult, task: Any) -> None:
    from biella.validation import ValidationCompletionFamily, ValidationAuthorityError

    contract, row = _minitz_completion_contract(result.task_id)
    family = ValidationCompletionFamily()
    if result.task_revision != contract["task_revision"] or result.task_digest != contract["task_digest"]:
        raise ValidationAuthorityError("completion result is stale for the current MiniTZ Task revision")
    if result.scope_ref != contract["scope_ref"]:
        raise ValidationAuthorityError("completion result crossed the current MiniTZ scope")
    if task.status in _COMPLETE:
        completion = row.get("completion") if isinstance(row.get("completion"), Mapping) else {}
        persisted = completion.get("evidence", ()) if isinstance(completion, Mapping) else ()
        if not isinstance(persisted, list):
            raise ValidationAuthorityError("persisted MiniTZ completion evidence is not independently readable")
        prior_revision = int(row["revision"])
        if prior_revision < 2:
            raise ValidationAuthorityError("completed MiniTZ task has no prior acceptance revision")
        prior_scope = f"task://minitz/{result.task_id}/{prior_revision - 1}"
        decision = family.verify_prior_acceptance(
            result.task_id,
            prior_revision,
            prior_scope,
            persisted,
            expected_task_digest=contract["task_digest"],
            required_criteria=contract["required_criteria"],
        )
        if not decision.accepted:
            raise ValidationAuthorityError(decision.reason or "prior MiniTZ acceptance could not be independently proven")
        return
    if result.status == "COMPLETE_ALREADY":
        decision = family.verify_prior_acceptance(
            result.task_id,
            int(contract["task_revision"]),
            str(contract["scope_ref"]),
            row.get("completion", {}).get("evidence", ()) if isinstance(row.get("completion"), Mapping) else (),
            expected_task_digest=contract["task_digest"],
            required_criteria=contract["required_criteria"],
        )
        if not decision.accepted:
            raise ValidationAuthorityError(decision.reason or "prior MiniTZ acceptance could not be independently proven")
        return
    decision = family.admit(
        result.task_id,
        int(contract["task_revision"]),
        str(contract["task_digest"]),
        str(contract["scope_ref"]),
        result.status,
        result.completion_evidence,
        required_criteria=contract["required_criteria"],
        accepted_criteria=result.accepted_criteria,
        family_revision=result.family_revision,
        authority_ref=result.authority_ref,
    )
    if result.status in _COMPLETE and not decision.accepted:
        raise ValidationAuthorityError(decision.reason or "MiniTZ completion was not semantically admitted")


def apply_result(repo_root: Path, project_root: Path, result: TaskResult, route: Route) -> None:
    production = load_project_production(project_root)
    task = find_task(production, result.task_id)
    if production.run_id == "minitz-task-program":
        if result.status == "CONTINUE":
            return
        _admit_minitz_result(result, task)
        if task.status in _COMPLETE:
            return
        mark_task_complete(repo_root, project_root, result.task_id, result.status, result.evidence)
        return
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
            candidates = [raw] if raw.is_absolute() else [root / raw, root / "projects/biella-games" / raw]
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
    """Commit the executor's exact recorded output set without another model turn."""
    if result.status not in _COMPLETE:
        return result
    try:
        dirty = _dirty_paths(Path(repo_root)) - set(_CONTINUITY_PATHS)
        expected = dict(owned_files or {})
        proof = _referenced_task_proof(repo_root, result)
        for name, digest in proof.items():
            expected.setdefault(name, digest)
        tracked = set()
        if proof:
            raw = _git(repo_root, "ls-files", "-z", "--", *sorted(proof), text=False).stdout
            tracked = {os.fsdecode(name) for name in raw.split(b"\0") if name}
        owned = sorted((dirty & set(expected)) | (set(proof) - tracked))
        if not owned:
            return result
        for name in owned:
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts:
                raise ValueError(f"invalid task output path: {name}")
            if _path_digest(Path(repo_root) / name) != expected[name]:
                raise ValueError(f"task output changed after the recorded validation boundary: {name}")
        _git(repo_root, "add", "-f", "--", *owned)
        _git(repo_root, "commit", "--only", "-m", f"production: persist validated {result.task_id} output", "--", *owned)
        commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        return TaskResult(
            result.task_id, result.status, result.summary,
            result.evidence + (f"Task-owned output committed locally: {commit}",),
            result.task_revision, result.task_digest, result.scope_ref,
            result.family_revision, result.authority_ref, result.accepted_criteria,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return TaskResult(
            result.task_id, "CONTINUE",
            f"Repair only the exact output-persistence operation; preserve passed work: {exc}", result.evidence,
            result.task_revision, result.task_digest, result.scope_ref,
            result.family_revision, result.authority_ref, result.accepted_criteria,
        )


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
    )


def derived_drive_publications(repo_root: Path) -> tuple[tuple[str, str], ...]:
    del repo_root
    return ()



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
