from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA = "biella.compacted_memory/v1"
_TASK_RE = re.compile(r"^- \[(?P<done>[xX ])\] (?P<id>[A-Z0-9-]+) \| (?P<class>[a-z_]+) \| (?P<title>.+?) \| (?P<status>[A-Z_]+) \|\s*(?P<evidence>.*)$")
_COMPLETE = {"COMPLETE", "COMPLETE_ALREADY"}


@dataclass(frozen=True)
class MemoryRecord:
    category: str
    text: str
    source_ref: str
    task_id: str | None = None
    task_class: str | None = None
    verified: bool = False
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompactionResult:
    index_path: Path
    gzip_path: Path
    projection_path: Path


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _content_ref(text: str) -> str:
    return "sha256:" + _sha(text.encode("utf-8"))


def _equivalence_ref(text: str) -> str:
    normalized = " ".join(str(text).split()).casefold()
    return "sha256:" + _sha(normalized.encode("utf-8"))


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _source_identity(path: Path, repo_root: Path) -> dict[str, Any]:
    data = path.read_bytes()
    try:
        display = path.relative_to(repo_root).as_posix()
    except ValueError:
        display = str(path)
    return {"path": display, "sha256": _sha(data), "bytes": len(data)}


def merge_records(records: Iterable[MemoryRecord]) -> dict[str, Any]:
    content: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    categories: dict[str, list[str]] = {}
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    task_ids: dict[str, list[str]] = {}
    task_classes: dict[str, list[str]] = {}

    for record in records:
        text = str(record.text)
        ref = _content_ref(text)
        eq_ref = _equivalence_ref(text)
        content.setdefault(ref, {"text": text, "bytes": len(text.encode("utf-8"))})
        row: dict[str, Any] = {
            "category": record.category,
            "content_ref": ref,
            "equivalence_ref": eq_ref,
            "source_ref": record.source_ref,
            "verified": bool(record.verified),
        }
        if record.task_id:
            row["task_id"] = record.task_id
            task_ids.setdefault(record.task_id, [])
            if ref not in task_ids[record.task_id]:
                task_ids[record.task_id].append(ref)
        if record.task_class:
            row["task_class"] = record.task_class
            task_classes.setdefault(record.task_class, [])
            if ref not in task_classes[record.task_class]:
                task_classes[record.task_class].append(ref)
        if record.capabilities:
            row["capabilities"] = sorted(set(record.capabilities))
        rows.append(row)
        categories.setdefault(record.category, [])
        if ref not in categories[record.category]:
            categories[record.category].append(ref)

        key = (record.category, eq_ref)
        group = groups.setdefault(key, {
            "category": record.category,
            "equivalence_ref": eq_ref,
            "content_refs": [], "source_refs": [], "task_ids": [],
            "task_classes": [], "verified_values": [], "capabilities": [],
        })
        for field, value in (("content_refs", ref), ("source_refs", record.source_ref),
                             ("task_ids", record.task_id), ("task_classes", record.task_class)):
            if value and value not in group[field]:
                group[field].append(value)
        if bool(record.verified) not in group["verified_values"]:
            group["verified_values"].append(bool(record.verified))
        for capability in record.capabilities:
            if capability not in group["capabilities"]:
                group["capabilities"].append(capability)

    equivalence_groups = []
    for group in groups.values():
        for field in ("content_refs", "source_refs", "task_ids", "task_classes", "capabilities"):
            group[field] = sorted(group[field])
        group["verified_values"] = sorted(group["verified_values"])
        group["variant_count"] = len(group["content_refs"])
        group["source_count"] = len(group["source_refs"])
        # Preferred ref is only a compact projection hint. No variant is deleted.
        group["preferred_ref"] = min(
            group["content_refs"],
            key=lambda item: (content[item]["bytes"], item),
        )
        equivalence_groups.append(group)

    return {
        "content": dict(sorted(content.items())),
        "records": rows,
        "categories": {key: sorted(value) for key, value in sorted(categories.items())},
        "equivalence_groups": sorted(equivalence_groups, key=lambda item: (item["category"], item["equivalence_ref"])),
        "task_ids": {key: sorted(value) for key, value in sorted(task_ids.items())},
        "task_classes": {key: sorted(value) for key, value in sorted(task_classes.items())},
    }


def _policy_records(path: Path) -> list[MemoryRecord]:
    text = path.read_text(encoding="utf-8")
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
    return [MemoryRecord("instruction", chunk, f"{path}:chunk:{index}") for index, chunk in enumerate(chunks)]


def _production_records(path: Path) -> list[MemoryRecord]:
    result: list[MemoryRecord] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = _TASK_RE.match(raw.strip())
        if not match:
            continue
        task_id = match.group("id")
        task_class = match.group("class")
        status = match.group("status")
        verified = status in _COMPLETE or match.group("done").lower() == "x"
        title = match.group("title").strip()
        result.append(MemoryRecord(
            "task", f"{task_id} | {task_class} | {title} | {status}",
            f"{path}:task:{task_id}", task_id, task_class, verified,
        ))
        evidence = match.group("evidence").strip()
        if evidence:
            for index, item in enumerate(part.strip() for part in evidence.split(";") if part.strip()):
                result.append(MemoryRecord(
                    "verified_action" if verified else "task_evidence", item,
                    f"{path}:task:{task_id}:evidence:{index}", task_id, task_class, verified,
                ))
    return result


def _task_memory_records(path: Path) -> list[MemoryRecord]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, Mapping):
        return []
    task_id = str(payload.get("task_id") or "") or None
    task_class = str(payload.get("task_class") or "") or None
    records: list[MemoryRecord] = []
    summary = str(payload.get("summary") or "").strip()
    if summary:
        records.append(MemoryRecord("task_memory", summary, f"{path}:summary", task_id, task_class, False))
    next_action = str(payload.get("next_action") or "").strip()
    if next_action:
        records.append(MemoryRecord("task_memory", next_action, f"{path}:next_action", task_id, task_class, False))
    for index, item in enumerate(payload.get("evidence") or []):
        text = str(item).strip()
        if text:
            records.append(MemoryRecord("task_evidence", text, f"{path}:evidence:{index}", task_id, task_class, False))
    return records


def _failure_records(path: Path) -> list[MemoryRecord]:
    if not path.exists():
        return []
    records: list[MemoryRecord] = []
    for index, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw, "status": "UNPARSEABLE"}
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        task_id = str(payload.get("task_id") or "") or None if isinstance(payload, Mapping) else None
        records.append(MemoryRecord("failure", text, f"{path}:line:{index+1}", task_id, None, False))
    return records


def _capability_records(path: Path) -> tuple[list[MemoryRecord], dict[str, list[str]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], {}
    providers = payload.get("providers") if isinstance(payload, Mapping) else None
    if not isinstance(providers, Mapping):
        return [], {}
    records: list[MemoryRecord] = []
    capabilities: dict[str, list[str]] = {}
    for provider_id, provider in sorted(providers.items()):
        if not isinstance(provider, Mapping):
            continue
        caps = tuple(sorted(str(item) for item in provider.get("capabilities", []) if str(item)))
        for capability in caps:
            capabilities.setdefault(capability, []).append(str(provider_id))
        summary = json.dumps({
            "provider": provider_id,
            "display_name": provider.get("display_name", provider_id),
            "capabilities": list(caps),
            "cost_class": provider.get("cost_class"),
        }, sort_keys=True, separators=(",", ":"))
        records.append(MemoryRecord("capability", summary, f"{path}:provider:{provider_id}", capabilities=caps))
    return records, {key: sorted(set(value)) for key, value in sorted(capabilities.items())}


def _source_files(repo_root: Path, project_root: Path, runtime_root: Path) -> list[Path]:
    candidates = [
        repo_root / "docs/project-state/00_BIELLA_PROJECT_OPERATING_CONTRACT.md",
        repo_root / "docs/project-state/BIELLA_PROJECT_INSTRUCTIONS.md",
        repo_root / "docs/project-state/BIELLA_DURABLE_SOURCE_AND_SYNC_RULES.md",
        repo_root / "ops/workstation/AGENTS.md",
        repo_root / "ops/workstation/provider-registry.json",
        project_root / "AGENTS.md",
        project_root / "docs/PRODUCTION.md",
        runtime_root / "failures.jsonl",
    ]
    candidates.extend(sorted((runtime_root / "task-memory").glob("*.json")))
    return [path for path in candidates if path.is_file()]


_RESOLVED_FAILURE_STATUSES = {"RECOVERED", "REPAIRED", "RESOLVED", "PASS", "COMPLETED"}
_TRANSIENT_PROVIDER_FAILURE_RE = re.compile(
    r"(?:you(?:'|’)?ve hit your usage limit|chatgpt\.com/codex/settings/usage|does not support thinking|failed to decode models response.*missing field [`']?models)",
    re.I | re.S,
)


def _active_failure_projection(failures: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Project semantic blockers only; preserve raw tool exits in lossless history.

    ``tool.completed`` failures remain in failures.jsonl and the full compacted index,
    but never compete for bounded active-prompt space. A meaningful build/runtime/tool
    problem is carried by the task capsule and/or an explicit semantic failure record.
    Recovery checkpoints clear prior semantic blockers without deleting raw history.
    """
    semantic: list[Mapping[str, Any]] = []
    for row in failures:
        status = str(row.get("status") or "").upper()
        if status in _RESOLVED_FAILURE_STATUSES:
            if bool(row.get("resolve_prior")):
                semantic.clear()
            continue
        failure_type = str(row.get("failure_type") or row.get("type") or "")
        if failure_type == "tool.completed":
            continue
        provider_text = "\n".join(str(row.get(key) or "") for key in ("text", "detail", "diagnostic", "message"))
        if _TRANSIENT_PROVIDER_FAILURE_RE.search(provider_text):
            continue
        semantic.append(row)
    return semantic[-20:]


def _projection(index: Mapping[str, Any], *, current_task_id: str | None,
                task_memory: Mapping[str, Any] | None, failures: list[Mapping[str, Any]],
                maximum_chars: int) -> dict[str, Any]:
    content = index.get("content", {})
    categories = index.get("categories", {})
    task_classes = index.get("task_classes", {})
    current_class = str((task_memory or {}).get("task_class") or "")

    verified_refs: list[str] = []
    for row in index.get("records", []):
        if not isinstance(row, Mapping) or row.get("category") != "verified_action" or not row.get("verified"):
            continue
        if row.get("task_id") == current_task_id or (current_class and row.get("task_class") == current_class):
            verified_refs.append(str(row.get("content_ref")))
    if len(verified_refs) < 20:
        for ref in categories.get("verified_action", []):
            if ref not in verified_refs:
                verified_refs.append(ref)
            if len(verified_refs) >= 20:
                break

    projection: dict[str, Any] = {
        "schema": "biella.compacted_task_projection/v1",
        "task_id": current_task_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_memory": dict(task_memory or {}),
        "failures": _active_failure_projection(failures),
        "capabilities": dict(index.get("capabilities", {})),
        "instruction_refs": list(categories.get("instruction", [])),
        "verified_actions": [
            {"content_ref": ref, "text": content.get(ref, {}).get("text", "")}
            for ref in verified_refs[:20]
        ],
        "task_class_refs": list(task_classes.get(current_class, [])) if current_class else [],
        "source_refs": [source.get("path") for source in index.get("sources", [])],
        "full_index": "memory/compacted-memory.json",
    }
    encoded = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded) <= maximum_chars:
        return projection

    # Reduce only derivative display fields; exact records remain in the full index/raw sources.
    projection["verified_actions"] = projection["verified_actions"][:8]
    projection["failures"] = projection["failures"][-8:]
    projection["instruction_refs"] = projection["instruction_refs"][:64]
    projection["task_class_refs"] = projection["task_class_refs"][:64]
    projection["task_memory"] = {
        key: value for key, value in (task_memory or {}).items()
        if key in {"task_id", "task_class", "title", "session_id", "summary", "next_action", "last_status", "dirty_path_count"}
    }
    def encoded_bytes() -> int:
        return len(json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))

    if encoded_bytes() > maximum_chars:
        projection["verified_actions"] = [item["content_ref"] for item in projection["verified_actions"]]
        projection["failures"] = [
            {key: row.get(key) for key in ("seq", "time", "task_id", "failure_type", "status", "text", "detail") if row.get(key) is not None}
            for row in projection["failures"][-4:]
        ]
    for key in ("task_class_refs", "instruction_refs"):
        while encoded_bytes() > maximum_chars and len(projection.get(key, [])) > 8:
            projection[key] = projection[key][: max(8, len(projection[key]) // 2)]
    while encoded_bytes() > maximum_chars and len(projection.get("verified_actions", [])) > 4:
        projection["verified_actions"] = projection["verified_actions"][: len(projection["verified_actions"]) // 2]
    while encoded_bytes() > maximum_chars and len(projection.get("failures", [])) > 2:
        projection["failures"] = projection["failures"][-max(2, len(projection["failures"]) // 2):]
    if encoded_bytes() > maximum_chars:
        preferred = {"llm.fast", "llm.code", "llm.reasoning", "unreal.assist", "code", "reasoning", "unreal"}
        projection["capabilities"] = {
            key: value for key, value in projection.get("capabilities", {}).items()
            if key in preferred
        }
    if encoded_bytes() > maximum_chars:
        projection["source_refs"] = projection.get("source_refs", [])[:8]
        memory = projection.get("task_memory", {})
        if isinstance(memory, dict):
            for key, limit in (("summary", 1800), ("next_action", 900)):
                value = memory.get(key)
                if isinstance(value, str) and len(value) > limit:
                    memory[key] = value[:limit - 1] + "…"
    # Last-resort derivative trimming preserves exact data in full_index/raw source refs.
    while encoded_bytes() > maximum_chars and projection.get("instruction_refs"):
        projection["instruction_refs"] = projection["instruction_refs"][:-1]
    while encoded_bytes() > maximum_chars and projection.get("task_class_refs"):
        projection["task_class_refs"] = projection["task_class_refs"][:-1]
    return projection


def refresh_compacted_memory(repo_root: Path, project_root: Path, runtime_root: Path, *,
                             current_task_id: str | None = None,
                             projection_max_chars: int = 12000) -> CompactionResult:
    repo_root = Path(repo_root).resolve()
    project_root = Path(project_root).resolve()
    runtime_root = Path(runtime_root).resolve()
    records: list[MemoryRecord] = []
    sources: list[dict[str, Any]] = []
    capabilities: dict[str, list[str]] = {}

    policy_paths = {
        repo_root / "docs/project-state/00_BIELLA_PROJECT_OPERATING_CONTRACT.md",
        repo_root / "docs/project-state/BIELLA_PROJECT_INSTRUCTIONS.md",
        repo_root / "docs/project-state/BIELLA_DURABLE_SOURCE_AND_SYNC_RULES.md",
        repo_root / "ops/workstation/AGENTS.md",
        project_root / "AGENTS.md",
    }
    production_path = project_root / "docs/PRODUCTION.md"
    registry_path = repo_root / "ops/workstation/provider-registry.json"
    failures_path = runtime_root / "failures.jsonl"

    for path in _source_files(repo_root, project_root, runtime_root):
        sources.append(_source_identity(path, repo_root))
        if path in policy_paths:
            records.extend(_policy_records(path))
        elif path == production_path:
            records.extend(_production_records(path))
        elif path == registry_path:
            cap_records, capabilities = _capability_records(path)
            records.extend(cap_records)
        elif path == failures_path:
            records.extend(_failure_records(path))
        elif path.parent == runtime_root / "task-memory":
            records.extend(_task_memory_records(path))

    merged = merge_records(records)
    index: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "project_root": str(project_root),
        "sources": sorted(sources, key=lambda item: item["path"]),
        "capabilities": capabilities,
        **merged,
    }

    task_memory: Mapping[str, Any] | None = None
    if current_task_id:
        task_path = runtime_root / "task-memory" / f"{current_task_id}.json"
        if task_path.exists():
            try:
                loaded = json.loads(task_path.read_text(encoding="utf-8"))
                if isinstance(loaded, Mapping):
                    task_memory = loaded
            except json.JSONDecodeError:
                pass
    failures: list[Mapping[str, Any]] = []
    if failures_path.exists():
        for raw in failures_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, Mapping):
                continue
            failure_task_id = row.get("task_id") or row.get("task")
            if not current_task_id or failure_task_id == current_task_id:
                failures.append(row)

    projection = _projection(
        index, current_task_id=current_task_id, task_memory=task_memory,
        failures=failures, maximum_chars=max(2048, int(projection_max_chars)),
    )
    memory_root = runtime_root / "memory"
    index_path = memory_root / "compacted-memory.json"
    gzip_path = memory_root / "compacted-memory.json.gz"
    projection_path = memory_root / "current-task.json"
    encoded = (json.dumps(index, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    _atomic_write(index_path, encoded)
    _atomic_write(gzip_path, gzip.compress(encoded, compresslevel=9, mtime=0))
    _atomic_write(projection_path, (json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8"))
    return CompactionResult(index_path, gzip_path, projection_path)
