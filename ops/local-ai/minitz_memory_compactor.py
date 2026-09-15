from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from minitz_os.engine.failure_repair_learning import FailureLearningError, FailureLearningService
from minitz_os.engine.project import ProjectError

try:
    from minitz_policy import build_policy_projection
except ModuleNotFoundError:  # Loaded directly by tests or another controller.
    _POLICY_MODULE_PATH = Path(__file__).with_name("minitz_policy.py")
    _POLICY_SPEC = importlib.util.spec_from_file_location("_minitz_minitz_policy", _POLICY_MODULE_PATH)
    if not _POLICY_SPEC or not _POLICY_SPEC.loader:
        raise
    _POLICY_MODULE = importlib.util.module_from_spec(_POLICY_SPEC)
    sys.modules[_POLICY_SPEC.name] = _POLICY_MODULE
    _POLICY_SPEC.loader.exec_module(_POLICY_MODULE)
    build_policy_projection = _POLICY_MODULE.build_policy_projection

try:
    import minitz_data_residency as data_residency
except ModuleNotFoundError:  # Loaded directly by tests or another controller.
    _RESIDENCY_MODULE_PATH = Path(__file__).with_name("minitz_data_residency.py")
    _RESIDENCY_SPEC = importlib.util.spec_from_file_location("_minitz_minitz_data_residency", _RESIDENCY_MODULE_PATH)
    if not _RESIDENCY_SPEC or not _RESIDENCY_SPEC.loader:
        raise
    data_residency = importlib.util.module_from_spec(_RESIDENCY_SPEC)
    sys.modules[_RESIDENCY_SPEC.name] = data_residency
    _RESIDENCY_SPEC.loader.exec_module(data_residency)

try:
    import minitz_production_events as production_events
except ModuleNotFoundError:
    _EVENTS_MODULE_PATH = Path(__file__).with_name("minitz_production_events.py")
    _EVENTS_SPEC = importlib.util.spec_from_file_location("_minitz_production_events", _EVENTS_MODULE_PATH)
    if not _EVENTS_SPEC or not _EVENTS_SPEC.loader:
        raise
    production_events = importlib.util.module_from_spec(_EVENTS_SPEC)
    sys.modules[_EVENTS_SPEC.name] = production_events
    _EVENTS_SPEC.loader.exec_module(production_events)

SCHEMA = "minitz.compacted_memory/v1"
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
    scope_ref: str | None = None
    rule_identity: str | None = None
    policy_digest: str | None = None
    authority: str | None = None
    origin_kind: str | None = None
    semantic_status: str | None = None
    replacement_rule_ids: tuple[str, ...] = ()


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
        for field in (
            "scope_ref", "rule_identity", "policy_digest", "authority", "origin_kind",
            "semantic_status",
        ):
            value = getattr(record, field)
            if value:
                row[field] = value
        if record.replacement_rule_ids:
            row["replacement_rule_ids"] = sorted(set(record.replacement_rule_ids))
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
            "scope_refs": [], "rule_identities": [], "policy_digests": [],
            "authorities": [], "origin_kinds": [], "semantic_statuses": [],
            "replacement_rule_ids": [],
        })
        for field, value in (
            ("content_refs", ref), ("source_refs", record.source_ref),
            ("task_ids", record.task_id), ("task_classes", record.task_class),
            ("scope_refs", record.scope_ref), ("rule_identities", record.rule_identity),
            ("policy_digests", record.policy_digest), ("authorities", record.authority),
            ("origin_kinds", record.origin_kind), ("semantic_statuses", record.semantic_status),
        ):
            if value and value not in group[field]:
                group[field].append(value)
        for replacement_rule_id in record.replacement_rule_ids:
            if replacement_rule_id not in group["replacement_rule_ids"]:
                group["replacement_rule_ids"].append(replacement_rule_id)
        if bool(record.verified) not in group["verified_values"]:
            group["verified_values"].append(bool(record.verified))
        for capability in record.capabilities:
            if capability not in group["capabilities"]:
                group["capabilities"].append(capability)

    equivalence_groups = []
    for group in groups.values():
        for field in (
            "content_refs", "source_refs", "task_ids", "task_classes", "capabilities",
            "scope_refs", "rule_identities", "policy_digests", "authorities", "origin_kinds",
            "semantic_statuses", "replacement_rule_ids",
        ):
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


def _policy_records(path: Path, policy_projection: Mapping[str, Any] | None = None) -> list[MemoryRecord]:
    if policy_projection is not None:
        prefix = f"{path}:chunk:"
        projected = [
            item for item in policy_projection.get("records", [])
            if isinstance(item, Mapping) and str(item.get("source_ref", "")).startswith(prefix)
        ]
        return [
            MemoryRecord(
                str(item.get("category") or "instruction"),
                str(item.get("text") or ""),
                str(item.get("source_ref") or ""),
                scope_ref=str(item.get("scope_ref") or "") or None,
                rule_identity=str(item.get("rule_identity") or "") or None,
                policy_digest=str(item.get("policy_digest") or "") or None,
                authority=str(item.get("authority") or "") or None,
                origin_kind=str(item.get("origin_kind") or "") or None,
                semantic_status=str(item.get("semantic_status") or "") or None,
                replacement_rule_ids=tuple(str(value) for value in item.get("replacement_rule_ids", []) if str(value)),
            )
            for item in projected
        ]
    text = path.read_text(encoding="utf-8")
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
    return [MemoryRecord("instruction", chunk, f"{path}:chunk:{index}") for index, chunk in enumerate(chunks)]


def _policy_projection_records(policy_projection: Mapping[str, Any]) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for item in policy_projection.get("records", []):
        if not isinstance(item, Mapping):
            continue
        records.append(
            MemoryRecord(
                str(item.get("category") or "instruction"),
                str(item.get("text") or ""),
                str(item.get("source_ref") or ""),
                scope_ref=str(item.get("scope_ref") or "") or None,
                rule_identity=str(item.get("rule_identity") or "") or None,
                policy_digest=str(item.get("policy_digest") or "") or None,
                authority=str(item.get("authority") or "") or None,
                origin_kind=str(item.get("origin_kind") or "") or None,
                semantic_status=str(item.get("semantic_status") or "") or None,
                replacement_rule_ids=tuple(str(value) for value in item.get("replacement_rule_ids", []) if str(value)),
            )
        )
    return records


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


def _source_files(
    repo_root: Path,
    project_root: Path,
    runtime_root: Path,
    *,
    active_policy_paths: Iterable[Path] | None = None,
) -> list[Path]:
    policy_candidates = list(active_policy_paths) if active_policy_paths is not None else [
        repo_root / "docs/project-state/00_MINITZ_PROJECT_OPERATING_CONTRACT.md",
        repo_root / "docs/project-state/MINITZ_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml",
        repo_root / "docs/project-state/MINITZ_DURABLE_SOURCE_AND_SYNC_RULES.md",
        repo_root / "ops/workstation/AGENTS.md",
        project_root / "AGENTS.md",
    ]
    candidates = [
        *policy_candidates,
        repo_root / "ops/workstation/provider-registry.json",
        project_root / "docs/PRODUCTION.md",
        runtime_root / "failures.jsonl",
    ]
    candidates.extend(sorted((runtime_root / "task-memory").glob("*.json")))
    return [path for path in candidates if path.is_file()]


_RESOLVED_FAILURE_STATUSES = {"RECOVERED", "REPAIRED", "RESOLVED", "PASS", "COMPLETED"}
_TRANSIENT_PROVIDER_FAILURE_RE = re.compile(
    r"(?:you(?:'|’)?ve hit your usage limit|chatgpt\.com/codex/settings/usage|does not support thinking|failed to decode models response.*missing field [`']?models|unknown input item type:\s*[^A-Za-z0-9]{0,32}compaction|use the minitz os command surface\.?)",
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
        event_type = str(row.get("event_type") or row.get("type") or "")
        if failure_type == "tool.completed":
            continue
        if event_type == "commander.assist_failed" and failure_type in {"VALIDATION_REJECTED", "INVALID_RESULT"}:
            continue
        provider_text = "\n".join(str(row.get(key) or "") for key in ("text", "detail", "diagnostic", "message"))
        if _TRANSIENT_PROVIDER_FAILURE_RE.search(provider_text):
            continue
        semantic.append(row)
    return semantic[-20:]


def _active_working_set(current_task_id: str | None, task_memory: Mapping[str, Any] | None) -> dict[str, Any]:
    memory = task_memory if isinstance(task_memory, Mapping) else {}
    owned = memory.get("owned_files") if isinstance(memory.get("owned_files"), Mapping) else {}
    baseline = memory.get("workspace_baseline") if isinstance(memory.get("workspace_baseline"), Mapping) else {}
    dirty_raw = memory.get("dirty_paths") if isinstance(memory.get("dirty_paths"), list) else []
    owned_paths = sorted(str(path)[:240] for path in owned if str(path).strip())
    dirty_paths = sorted({str(path)[:240] for path in dirty_raw if str(path).strip()})
    root_counts: dict[str, int] = {}
    for raw_path in baseline:
        path = str(raw_path).strip().replace("\\", "/")
        if not path:
            continue
        root = path.split("/", 1)[0]
        root_counts[root] = root_counts.get(root, 0) + 1
    program = memory.get("program_identity") if isinstance(memory.get("program_identity"), Mapping) else {}
    return {
        "authority": "NONE_DERIVED_READING_HINT",
        "task_id": current_task_id,
        "task_revision": memory.get("task_revision"),
        "task_digest": memory.get("task_digest"),
        "canonical_task_program_ref": str(program.get("path") or "") or None,
        "owned_path_count": len(owned_paths),
        "owned_paths": owned_paths[:32],
        "dirty_path_count": len(dirty_paths),
        "dirty_paths": dirty_paths[:32],
        "workspace_path_count": len(baseline),
        "workspace_roots": [
            {"root": root, "path_count": count}
            for root, count in sorted(root_counts.items(), key=lambda item: (-item[1], item[0]))[:24]
        ],
        "read_policy": "READ_EXACT_CURRENT_SOURCE_ON_DEMAND",
    }


_TASK_HORIZON_FIELDS = (
    "task_id", "revision", "task_record_sha256", "project", "project_id", "title", "status",
    "objective", "acceptance", "required_capabilities", "dependencies", "write_scope",
    "deliverables", "constraints", "side_effects", "preserve", "completion",
    "negative_controls", "unresolved", "validation",
)
_CREATION_CAPABILITY_TOKENS = (
    "create", "build", "generate", "write", "edit", "modify", "render", "compile",
    "package", "code", "execute", "shell", "browser", "asset", "media", "test",
)


def _task_horizon_projection(task_memory: Mapping[str, Any] | None) -> dict[str, Any]:
    memory = dict(task_memory or {})
    fallback = {
        key: memory[key] for key in (
            "task_id", "task_revision", "task_digest", "title", "summary", "next_action",
            "scope_ref", "project_root", "project_id", "project_ref", "run_id", "run_ref",
            "objective", "acceptance", "required_capabilities", "write_scope", "constraints",
            "output_contract", "creation_functions", "remaining_work", "preserve",
        ) if key in memory
    }
    program_identity = memory.get("program_identity") if isinstance(memory.get("program_identity"), Mapping) else {}
    source = program_identity.get("path")
    result: dict[str, Any] = {
        "identity_state": "TASK_MEMORY_ONLY",
        "source_ref": str(source) if source else None,
        "task": fallback,
    }
    if not source:
        return result
    path = Path(str(source))
    if not path.is_file():
        result["identity_state"] = "PROGRAM_SOURCE_UNAVAILABLE"
        return result
    try:
        program = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        result["identity_state"] = "PROGRAM_SOURCE_UNREADABLE"
        return result
    task_id = str(memory.get("task_id") or "")
    task = next((row for row in program.get("tasks", []) if isinstance(row, Mapping) and str(row.get("task_id") or "") == task_id), None)
    if not isinstance(task, Mapping):
        result["identity_state"] = "TASK_NOT_FOUND_IN_PROGRAM"
        return result
    memory_revision = memory.get("task_revision")
    memory_digest = str(memory.get("task_digest") or "")
    revision_ok = memory_revision in (None, "") or task.get("revision") == memory_revision
    digest_ok = not memory_digest or str(task.get("task_record_sha256") or "") == memory_digest
    result["program_identity"] = {
        "path": str(path),
        "program_id": program_identity.get("program_id"),
        "revision": program_identity.get("revision"),
        "sha256": program_identity.get("sha256"),
    }
    if not (revision_ok and digest_ok):
        result["identity_state"] = "TASK_IDENTITY_MISMATCH"
        return result
    result["identity_state"] = "VERIFIED_TASK_HORIZON"
    result["task"] = {key: task[key] for key in _TASK_HORIZON_FIELDS if key in task}
    return result


def _creation_capability_ids(capabilities: Mapping[str, Any]) -> list[str]:
    return sorted(
        str(capability_id) for capability_id in capabilities
        if any(token in str(capability_id).casefold() for token in _CREATION_CAPABILITY_TOKENS)
    )


def _recurring_failure_projection(active_failures: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in active_failures:
        signature = str(row.get("failure_signature") or "")
        if not signature:
            structural = {
                "task": row.get("task_id") or row.get("task"),
                "failure_type": row.get("failure_type") or row.get("type"),
                "tool": row.get("tool"),
                "provider": row.get("provider"),
            }
            signature = "derived://" + _sha(json.dumps(structural, sort_keys=True, default=str).encode("utf-8"))
        group = groups.setdefault(signature, {
            "failure_signature": signature, "observed_count": 0, "rows_seen": 0, "latest": {},
        })
        group["rows_seen"] += 1
        observed = int(group["rows_seen"])
        try:
            observed = max(observed, int(row.get("recurrence_window_count") or 0))
        except (TypeError, ValueError):
            pass
        group["observed_count"] = max(int(group["observed_count"]), observed)
        group["latest"] = {
            key: row.get(key) for key in ("time", "task_id", "failure_type", "status", "text", "detail", "tool", "provider")
            if row.get(key) is not None
        }
    recurring = [
        {**{key: value for key, value in group.items() if key != "rows_seen"}, "repair_signal": "ROOT_CAUSE_BOUNDED_REPAIR", "preserve_working_capabilities": True}
        for group in groups.values() if int(group["observed_count"]) >= 2
    ]
    return sorted(recurring, key=lambda item: (-int(item["observed_count"]), str(item["failure_signature"])))[:8]

def _projection(index: Mapping[str, Any], *, current_task_id: str | None,
                task_memory: Mapping[str, Any] | None, failures: list[Mapping[str, Any]],
                maximum_chars: int) -> dict[str, Any]:
    content = index.get("content", {})
    categories = index.get("categories", {})
    task_classes = index.get("task_classes", {})
    current_class = str((task_memory or {}).get("task_class") or "")
    policy = index.get("policy", {})
    capabilities = dict(index.get("capabilities", {}))
    active_failures = _active_failure_projection(failures)
    horizon = _task_horizon_projection(task_memory)
    continuity_guard = {
        "schema": "minitz.continuity_guard/v1",
        "detail_preservation": "PRESERVE_UNIQUE_AUTHORITY_EVIDENCE_AND_IMPLEMENTATION_DETAIL",
        "scoped_horizon": horizon,
        "project_awareness": {
            key: (task_memory or {}).get(key) for key in ("project_root", "project_id", "project_ref", "scope_ref")
            if (task_memory or {}).get(key) is not None
        },
        "capability_ids": sorted(str(key) for key in capabilities),
        "creation_capability_ids": _creation_capability_ids(capabilities),
        "creation_functions": "PRESERVE_WORKING_CREATE_BUILD_MODIFY_EXECUTE_PATHS",
        "repair_contract": {
            "scope": "SMALLEST_AFFECTED_BOUNDARY",
            "preserve_verified_work": True,
            "preserve_working_capabilities": True,
            "rerun": "AFFECTED_VALIDATION_PLUS_TARGETED_REGRESSION",
            "repetitive_failure": "ROOT_CAUSE_AND_ANTI_REGRESSION_TEST",
        },
    }

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
        "active_working_set": _active_working_set(current_task_id, task_memory),
        "schema": "minitz.compacted_task_projection/v1",
        "task_id": current_task_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_memory": dict(task_memory or {}),
        "failures": active_failures,
        "recurring_failures": _recurring_failure_projection(active_failures),
        "capabilities": capabilities,
        "continuity_guard": continuity_guard,
        "data_residency": dict(index.get("data_residency", {})),
        "instruction_refs": list(categories.get("instruction", [])),
        "verified_actions": [
            {"content_ref": ref, "text": content.get(ref, {}).get("text", "")}
            for ref in verified_refs[:20]
        ],
        "task_class_refs": list(task_classes.get(current_class, [])) if current_class else [],
        "source_refs": [
            source.get("path") for source in index.get("sources", [])
            if not (
                "/task-memory/" in str(source.get("path") or "")
                and not (current_task_id and str(source.get("path") or "").endswith(f"/task-memory/{current_task_id}.json"))
            )
        ],
        "policy": {
            "schema": policy.get("schema"),
            "authority": policy.get("authority"),
            "active_historical_steering_target": policy.get("active_historical_steering_target"),
            "legacy_policy_active_input": policy.get("legacy_policy_active_input"),
            "execution_inputs": policy.get("execution_inputs", {}),
            "semantic_replacement_rule_ids": [
                str(rule.get("rule_id"))
                for rule in policy.get("semantic_replacements", [])
                if isinstance(rule, Mapping)
            ],
            "active_authority_conflicts": policy.get("active_authority_conflicts", []),
        },
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
        if key in {
            "task_id", "task_class", "title", "session_id", "summary", "next_action", "last_status",
            "dirty_path_count", "task_revision", "task_digest", "scope_ref", "progression_authority",
            "provider_session_authority", "task_identity", "session_identity", "program_identity",
            "worktree_identity", "owner_lifecycle", "bootstrap", "checkpoint_identity", "continuity",
        }
    }
    def encoded_bytes() -> int:
        return len(json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))

    if encoded_bytes() > maximum_chars:
        projection["verified_actions"] = [item["content_ref"] for item in projection["verified_actions"]]
        projection["failures"] = [
            {key: row.get(key) for key in ("seq", "time", "task_id", "failure_type", "status", "text", "detail", "failure_signature", "recurrence_window_count", "repetitive_failure", "repair_signal") if row.get(key) is not None}
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


def refresh_failure_learning_projection(
    runtime_root: Path, *, current_task_id: str | None = None
) -> dict[str, Any]:
    """Attach unified failure evidence to scoped learning without owning progression."""

    runtime_root = Path(runtime_root).resolve()
    failures_path = runtime_root / "failures.jsonl"
    learning_db = runtime_root / "memory" / "failure-learning.sqlite3"
    learning_db.parent.mkdir(parents=True, exist_ok=True)
    service = FailureLearningService(learning_db)
    recorded = unavailable = rejected = 0
    if failures_path.exists():
        for row in production_events.project_failure_evidence(failures_path):
            if not isinstance(row, Mapping):
                rejected += 1
                continue
            if row.get("parse_state") != "JSON":
                rejected += 1
                continue
            provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
            if current_task_id and provenance.get("task_id") != current_task_id:
                continue
            resource_context = {
                key: str(value)
                for key, value in (
                    ("provider", row.get("provider")),
                    ("model", row.get("model")),
                    ("provider_state", row.get("status")),
                )
                if value not in (None, "")
            }
            try:
                binding = service.record_unified_failure_evidence(row, resource_context=resource_context)
            except (FailureLearningError, ProjectError, TypeError, ValueError):
                rejected += 1
                continue
            if binding.learning_state == "RECORDED":
                recorded += 1
            else:
                unavailable += 1
    return {
        "schema": "minitz.failure_learning_projection/v1",
        "authority": "NONE_DERIVED_LEARNING",
        "progression_authority": False,
        "blocking": False,
        "current_task_id": current_task_id,
        "recorded": recorded,
        "unavailable_scope": unavailable,
        "rejected": rejected,
        "database": str(learning_db),
    }


def refresh_compacted_memory(repo_root: Path, project_root: Path, runtime_root: Path, *,
                             current_task_id: str | None = None,
                             projection_max_chars: int = 12000) -> CompactionResult:
    repo_root = Path(repo_root).resolve()
    project_root = Path(project_root).resolve()
    runtime_root = Path(runtime_root).resolve()
    records: list[MemoryRecord] = []
    sources: list[dict[str, Any]] = []
    capabilities: dict[str, list[str]] = {}

    policy_projection = build_policy_projection(repo_root, project_root)
    active_policy_paths = {
        repo_root / str(row["path"])
        for row in policy_projection.get("active_sources", [])
        if isinstance(row, Mapping)
    }
    records.extend(_policy_projection_records(policy_projection))

    policy_paths = set(active_policy_paths)
    production_path = project_root / "docs/PRODUCTION.md"
    registry_path = repo_root / "ops/workstation/provider-registry.json"
    failures_path = runtime_root / "failures.jsonl"

    for path in _source_files(
        repo_root, project_root, runtime_root, active_policy_paths=active_policy_paths,
    ):
        sources.append(_source_identity(path, repo_root))
        if path in policy_paths:
            # The semantic policy projection above is the only active policy
            # record source.  This branch is intentionally a no-op so a raw
            # source cannot create a second authority or duplicate records.
            continue
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
        "policy": {
            key: value for key, value in policy_projection.items() if key != "records"
        },
        "capabilities": capabilities,
        "data_residency": data_residency.semantic_memory_policy(),
        **merged,
    }
    try:
        failure_learning_projection = refresh_failure_learning_projection(
            runtime_root, current_task_id=current_task_id
        )
    except Exception as exc:
        failure_learning_projection = {
            "schema": "minitz.failure_learning_projection/v1",
            "authority": "NONE_DERIVED_LEARNING",
            "progression_authority": False,
            "blocking": False,
            "current_task_id": current_task_id,
            "state": "UNAVAILABLE",
            "error_class": type(exc).__name__,
        }
    index["failure_learning"] = failure_learning_projection

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
    projection["failure_learning"] = failure_learning_projection
    memory_root = runtime_root / "memory"
    index_path = memory_root / "compacted-memory.json"
    gzip_path = memory_root / "compacted-memory.json.gz"
    projection_path = memory_root / "current-task.json"
    encoded = (json.dumps(index, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    projection_encoded = (json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    encoded = data_residency.redact_raw_auth_credentials(encoded)
    projection_encoded = data_residency.redact_raw_auth_credentials(projection_encoded)
    _atomic_write(index_path, encoded)
    _atomic_write(gzip_path, gzip.compress(encoded, compresslevel=9, mtime=0))
    _atomic_write(projection_path, projection_encoded)
    return CompactionResult(index_path, gzip_path, projection_path)
