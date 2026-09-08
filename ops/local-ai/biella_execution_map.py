"""Read one normalized task packet from the owner-requested 100-task map."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAP_PATH = "docs/task-program/D_NEXT_100_TASKS.json"


def load_map(repo: Path) -> dict[str, Any]:
    path = Path(repo) / MAP_PATH
    if not path.is_file():
        return {"tasks": [], "registry_is_queue": False}
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("registry_is_queue") is not False:
        raise ValueError("execution map must not become a second queue")
    return result


def task_entry(repo: Path, task_id: str) -> dict[str, Any] | None:
    return next((item for item in load_map(repo)["tasks"] if item["task_id"] == task_id), None)


def task_working_directory(repo: Path, default: Path, task_id: str) -> Path:
    entry = task_entry(repo, task_id)
    if entry is None:
        return Path(default)
    root = Path(repo).resolve()
    target = (root / entry["execution_root"]).resolve()
    target.relative_to(root)
    if not target.is_dir():
        raise FileNotFoundError(f"mapped execution directory is missing: {target}")
    return target


def task_context(repo: Path, task_id: str) -> str:
    entry = task_entry(repo, task_id)
    if entry is None:
        return ""
    return (
        "\nCURRENT_TASK_EXECUTION_MAP\n"
        "Only this task is loaded. PRODUCTION.md owns status/order; this map supplies scoped work and evidence, not another queue.\n"
        + json.dumps(entry, ensure_ascii=False, sort_keys=True, indent=2)
        + "\nEND_CURRENT_TASK_EXECUTION_MAP\n"
        "Reuse material-input-matching evidence. Implement only unmet requirements. No repeated approvals, invented scope, full-program context preload, or completion from a self-report. "
        "Git/Drive transport retries belong to the controller publication cursor; they must not trigger a task replay. "
        "A task whose deliverable is actual external publication/player evidence still requires that real evidence; never replace it with a claim.\n"
    )

def _render_human_readable(data: dict[str, Any]) -> str:
    def bullets(value: Any) -> str:
        if isinstance(value, list):
            return "\n".join(f"- {item}" for item in value) if value else "- None"
        return str(value or "")
    lines = [
        "# Biella — next 100 canonical tasks", "",
        "Priority: **GAME_FIRST — game delivery is NUMBER 1.**", "",
        "This map is not a queue. Physical Project PRODUCTION.md order is authoritative; task IDs and accepted work are preserved.", "",
        "Only task objectives, deliverables, validation, evidence and canonical dependency edges are extracted. Historical repository/controller paths, FUTURE_BLOCKED flags and raw activation/control instructions are not active.", "",
        "## Shared execution rules", "",
        "One authoritative task/session per active task; parked resource-blocked tasks retain their task/session identity. Reuse valid work; execute only missing outputs and required validation. No website/business prerequisite for game delivery. Real external evidence remains required where promised. Local/GitHub per-task; Drive every five completed tasks in <=3.8 GB parts.", "",
    ]
    for item in data.get("tasks", []):
        deps = ", ".join(item.get("depends_on") or []) or "None"
        lines.extend([
            f"## {int(item['ordinal']):03d}. {item['task_id']} — {item['title']}", "",
            f"Lane: **{item['lane']}** · Priority: **{item.get('priority', 1)}** · Execution root: `{item['execution_root']}` · Dependencies: {deps}", "",
            f"**Objective.** {item.get('objective', '')}", "",
            "**Deliverable.** " + bullets(item.get("deliverable", [])), "",
            "**Validation.** " + bullets(item.get("validation", [])), "",
            "**Required evidence.** " + bullets(item.get("required_evidence", [])), "",
        ])
        refs = [f"`{ref['path']}` (SHA-256 `{ref['sha256']}`)" for ref in item.get("source_refs", [])]
        lines.extend(["**Source records.** " + ("; ".join(refs) if refs else "None"), ""])
    return "\n".join(lines).rstrip() + "\n"


def sync_production_order(repo: Path, production: Any) -> dict[str, Any]:
    """Keep the non-authoritative task map's order metadata aligned to canonical PRODUCTION.md."""
    repo = Path(repo); data = load_map(repo)
    order = [task.id for section in production.sections for task in section.tasks]
    positions = {task_id: index for index, task_id in enumerate(order, 1)}
    tasks = list(data.get("tasks", []))
    tasks.sort(key=lambda item: positions.get(item["task_id"], len(order) + int(item.get("ordinal", 0))))
    for ordinal, item in enumerate(tasks, 1):
        item["ordinal"] = ordinal
        if item["task_id"] in positions:
            item["production_ordinal"] = positions[item["task_id"]]
    data["tasks"] = tasks
    path = repo / MAP_PATH
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    readable = repo / "docs/task-program/D_NEXT_100_TASKS.md"
    if readable.exists():
        readable.write_text(_render_human_readable(data), encoding="utf-8")
    return data
