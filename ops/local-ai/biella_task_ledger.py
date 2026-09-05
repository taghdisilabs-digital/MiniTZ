from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import biella_task_ids as task_ids

CANONICAL_ID_RE = re.compile(r"^D\d{2}-\d{2}$")
_ROW_RE = re.compile(
    r"^\|\s*`(?P<id>D\d{2}-\d{2})`\s*\|\s*(?P<title>.*?)\s*\|\s*`(?P<status>[A-Z_]+)`\s*\|\s*(?P<depends>.*?)\s*\|\s*(?P<aliases>.*?)\s*\|$"
)
_REGISTRY_FILES = (
    "docs/task-program/D00_D08_ENGINE_GAMES.md",
    "docs/task-program/D09_D14_WEBSITE.md",
    "docs/task-program/D15_D24_AAA_CHALLENGER.md",
)
_LIVE_SOURCE = "projects/biella-games/docs/PRODUCTION.md"


def ledger_path(repo_root: Path) -> Path:
    return Path(repo_root) / "docs/task-program/D_TASK_LEDGER.json"


def _split_refs(value: str) -> list[str]:
    if not value or value.strip() in {"—", "-"}:
        return []
    return [item.strip().strip("`") for item in value.split(",") if item.strip()]


def _registry_rows(repo_root: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for relative in _REGISTRY_FILES:
        path = Path(repo_root) / relative
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            match = _ROW_RE.match(raw.strip())
            if not match:
                continue
            task_id = task_ids.canonical_task_id(match.group("id"))
            rows[task_id] = {
                "task_id": task_id,
                "program": task_id.split("-", 1)[0],
                "title": match.group("title").strip(),
                "status": match.group("status"),
                "depends_on": _split_refs(match.group("depends")),
                "legacy_aliases": _split_refs(match.group("aliases")),
                "status_source": relative,
            }
    return rows


def _sort_key(task_id: str) -> tuple[int, int]:
    group, number = task_id[1:].split("-", 1)
    return int(group), int(number)


def build_task_ledger(repo_root: Path, production) -> dict[str, Any]:
    rows = _registry_rows(Path(repo_root))
    for section in production.sections:
        for task in section.tasks:
            task_id = task_ids.canonical_task_id(task.id)
            row = rows.setdefault(task_id, {
                "task_id": task_id,
                "program": task_id.split("-", 1)[0],
                "title": task.title,
                "status": task.status,
                "depends_on": [],
                "legacy_aliases": [],
                "status_source": _LIVE_SOURCE,
            })
            row["title"] = task.title
            row["status"] = task.status
            row["status_source"] = _LIVE_SOURCE
    return {
        "schema": "biella.d_task_ledger/v1",
        "registry_is_queue": False,
        "execution_authority": "current 03/04 + Project PRODUCTION.md",
        "current_task": task_ids.canonical_task_id(production.current_task) if production.current_task else None,
        "tasks": [rows[key] for key in sorted(rows, key=_sort_key)],
    }


def sync_task_ledger(repo_root: Path, production) -> dict[str, Any]:
    payload = build_task_ledger(Path(repo_root), production)
    path = ledger_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != rendered:
        path.write_text(rendered, encoding="utf-8")
    return payload
