from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from biella_codex_routing import Route
from biella_production_state import mark_task_complete, sync_current_state, load_project_production, find_task

_ALLOWED = {"COMPLETE", "COMPLETE_ALREADY", "CONTINUE", "EXTERNAL_DEPENDENCY", "OWNER_DECISION"}
_COMPLETE = {"COMPLETE", "COMPLETE_ALREADY"}


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
    task_id = str(raw.get("task_id", ""))
    if task_id != expected_task_id:
        raise ValueError(f"task_id mismatch: expected {expected_task_id}, got {task_id}")
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
        sync_current_state(repo_root, production, task, state="IN_PROGRESS", execution_started=True)
        return
    if result.status in {"EXTERNAL_DEPENDENCY", "OWNER_DECISION"}:
        sync_current_state(repo_root, production, task, state=result.status, execution_started=False)
        return
    raise ValueError(f"unsupported result status: {result.status}")
