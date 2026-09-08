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
