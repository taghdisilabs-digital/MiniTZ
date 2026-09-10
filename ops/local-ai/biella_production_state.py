from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import biella_task_ids as task_ids
import biella_task_ledger as task_ledger
import minitz_task_program as minitz

_COMPLETE = {"COMPLETE", "COMPLETE_ALREADY"}
_SECTION_RE = re.compile(r"^## Section: (?P<id>[A-Za-z0-9_-]+) \| (?P<title>.+?) \| (?P<status>[A-Z_]+)$")
_TASK_RE = re.compile(r"^- \[(?P<done>[xX ])\] (?P<id>[A-Z0-9-]+) \| (?P<class>[a-z_]+) \| (?P<title>.+?) \| (?P<status>[A-Z_]+) \|\s*(?P<evidence>.*)$")
_CANONICAL_REPO_ROOT = Path("/root/biella/repos/biella-engine")
_CANONICAL_PROJECT_ROOT = _CANONICAL_REPO_ROOT / "projects/biella-games"


def _use_minitz_project(project_root: Path) -> bool:
    return bool(os.environ.get("MINITZ_TASK_PROGRAM_PATH")) or Path(project_root).resolve() == _CANONICAL_PROJECT_ROOT


def _use_minitz_repo(repo_root: Path) -> bool:
    return bool(os.environ.get("MINITZ_TASK_PROGRAM_PATH")) or Path(repo_root).resolve() == _CANONICAL_REPO_ROOT


@dataclass(frozen=True)
class TaskRecord:
    id: str
    task_class: str
    title: str
    status: str
    evidence: tuple[str, ...] = ()
    section_id: str = ""


@dataclass
class SectionRecord:
    id: str
    title: str
    status: str
    tasks: list[TaskRecord] = field(default_factory=list)


@dataclass
class ProductionState:
    project_root: Path
    status: str
    current_section: str | None
    current_task: str | None
    sections: list[SectionRecord]
    run_id: str = "biella-games-production"
    priority_policy: str = "CANONICAL_ORDER"


@dataclass(frozen=True)
class ActiveTask:
    id: str
    project: str
    section: str
    task_class: str
    title: str
    status: str


def _minitz_current_row(program: dict) -> dict | None:
    execution = program.get("current_execution")
    if isinstance(execution, dict) and execution.get("task_id"):
        current = minitz.task_by_id(program, str(execution["task_id"]))
        if minitz.runnable(program, current):
            return current
    current = next((row for row in program["tasks"] if minitz.runnable(program, row)), None)
    if current is not None:
        return current
    active = [row["task_id"] for row in program["tasks"] if row.get("status") in minitz.ACTIVE_STATUSES]
    if active:
        raise ValueError("MiniTZ active tasks exist but none is dependency-runnable: " + ",".join(active))
    return None


def _minitz_production(project_root: Path) -> ProductionState:
    program = minitz.load()
    current = _minitz_current_row(program)
    tasks: list[TaskRecord] = []
    for row in program["tasks"]:
        completion = row.get("completion") if isinstance(row.get("completion"), dict) else {}
        completion_evidence = completion.get("evidence") if isinstance(completion, dict) else []
        evidence = tuple(str(item) for item in completion_evidence or ()) + (
            f"MINITZ_TASK_REVISION:{row['revision']}",
            f"MINITZ_TASK_SHA256:{row['task_record_sha256']}",
        )
        tasks.append(TaskRecord(
            str(row["task_id"]), minitz.task_class(program, row), str(row["title"]),
            str(row["status"]), evidence, "minitz",
        ))
    active = any(row.get("status") in minitz.ACTIVE_STATUSES for row in program["tasks"])
    section = SectionRecord("minitz", "MiniTZ Tasks", "IN_PROGRESS" if active else "COMPLETE", tasks)
    return ProductionState(
        Path(project_root), "IN_PROGRESS" if active else "COMPLETE",
        "minitz" if current is not None else None, current["task_id"] if current else None,
        [section], run_id="minitz-task-program", priority_policy="MINITZ_TASK_PROGRAM",
    )


def _live_repository_identity(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(Path(repo_root)), "remote", "get-url", "origin"],
            text=True, capture_output=True, check=False, timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "UNKNOWN"
    if proc.returncode != 0 or not proc.stdout.strip():
        return "UNKNOWN"
    remote = proc.stdout.strip()
    match = re.match(r"^(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?$", remote)
    return match.group(1) if match else remote


def _unquote(value: str) -> str:
    value = value.strip()
    return value[1:-1] if value.startswith("`") and value.endswith("`") else value


def production_path(project_root: Path) -> Path:
    return Path(project_root) / "docs" / "PRODUCTION.md"


def load_project_production(project_root: Path) -> ProductionState:
    project_root = Path(project_root)
    if _use_minitz_project(project_root):
        return _minitz_production(project_root)
    lines = production_path(project_root).read_text(encoding="utf-8").splitlines()
    status = "IN_PROGRESS"; current_section = current_task = None
    priority_policy = "CANONICAL_ORDER"
    sections: list[SectionRecord] = []; section: SectionRecord | None = None
    for raw in lines:
        line = raw.strip()
        if line.startswith("Status:") and not sections:
            status = _unquote(line.split(":", 1)[1])
            continue
        if line.startswith("Priority:") and not sections:
            priority_policy = _unquote(line.split(":", 1)[1])
            continue
        if line.startswith("Current section:"):
            value = _unquote(line.split(":", 1)[1]); current_section = None if value in {"", "NONE", "null"} else value
            continue
        if line.startswith("Current task:"):
            value = _unquote(line.split(":", 1)[1]); current_task = None if value in {"", "NONE", "null"} else task_ids.canonical_task_id(value)
            continue
        match = _SECTION_RE.match(line)
        if match:
            section = SectionRecord(match.group("id"), match.group("title").strip(), match.group("status"))
            sections.append(section)
            continue
        match = _TASK_RE.match(line)
        if match and section is not None:
            task_status = match.group("status")
            if match.group("done").lower() == "x" and task_status not in _COMPLETE:
                task_status = "COMPLETE"
            evidence = match.group("evidence").strip()
            section.tasks.append(TaskRecord(
                task_ids.canonical_task_id(match.group("id")), match.group("class"), match.group("title").strip(),
                task_status, (evidence,) if evidence else (), section.id,
            ))
    if not sections:
        raise ValueError(f"no production sections found in {production_path(project_root)}")
    return ProductionState(project_root, status, current_section, current_task, sections, priority_policy=priority_policy)


def find_task(production: ProductionState, task_id: str) -> TaskRecord:
    canonical = task_ids.canonical_task_id(task_id)
    for section in production.sections:
        for task in section.tasks:
            if task.id == canonical:
                return task
    raise KeyError(task_id)


def next_task(production: ProductionState) -> TaskRecord | None:
    if production.run_id == "minitz-task-program":
        if production.current_task is None:
            active = [task.id for section in production.sections for task in section.tasks if task.status in minitz.ACTIVE_STATUSES]
            if active:
                raise ValueError("MiniTZ active tasks exist but no executable current task: " + ",".join(active))
            return None
        return next(task for section in production.sections for task in section.tasks if task.id == production.current_task)
    for section in production.sections:
        if section.status in _COMPLETE:
            continue
        for task in section.tasks:
            if task.status not in _COMPLETE:
                return task
        return None
    return None


def completed_count(production: ProductionState) -> int:
    return sum(task.status in _COMPLETE for section in production.sections for task in section.tasks)


def completed_demo_count(production: ProductionState) -> int:
    if production.run_id == "minitz-task-program":
        return 0
    demo = next((section for section in production.sections if section.id == "demo01"), None)
    if demo is None:
        return 0
    return sum(task.status in _COMPLETE for task in demo.tasks)


def _replace_meta(lines: list[str], prefix: str, value: str | None) -> None:
    rendered = f"{prefix} `{value if value is not None else 'NONE'}`"
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = rendered
            return
    raise ValueError(f"missing metadata line {prefix}")


def sync_project_metadata(project_root: Path) -> ProductionState:
    if _use_minitz_project(project_root):
        return load_project_production(project_root)
    path = production_path(project_root)
    production = load_project_production(project_root)
    task = next_task(production)
    section = task.section_id if task else None
    if task is None:
        for candidate in production.sections:
            if candidate.status not in _COMPLETE:
                section = candidate.id
                break
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, raw in enumerate(lines):
        match = _TASK_RE.match(raw.strip())
        if match:
            canonical = task_ids.canonical_task_id(match.group("id"))
            if canonical != match.group("id"):
                lines[index] = raw.replace(match.group("id"), canonical, 1)
    _replace_meta(lines, "Current section:", section)
    _replace_meta(lines, "Current task:", task.id if task else None)
    demo = next((candidate for candidate in production.sections if candidate.id == "demo01"), None)
    if demo is not None:
        complete = sum(item.status in _COMPLETE for item in demo.tasks)
        rendered = f"Progress: `{complete}/{len(demo.tasks)}` Demo tasks complete"
        for index, line in enumerate(lines):
            if line.startswith("Progress:"):
                lines[index] = rendered
                break
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return load_project_production(project_root)


def active_task_path(repo_root: Path) -> Path:
    return Path(repo_root) / "docs/project-state/04_BIELLA_ACTIVE_TASK.md"


def current_state_path(repo_root: Path) -> Path:
    return Path(repo_root) / "docs/project-state/03_BIELLA_CURRENT_STATE.md"


def load_active_task(repo_root: Path) -> ActiveTask:
    values: dict[str, str] = {}
    in_task = False
    for raw in active_task_path(repo_root).read_text(encoding="utf-8").splitlines():
        if raw.strip() == "task:": in_task = True; continue
        if not in_task: continue
        match = re.match(r"^  (id|project|section|class|title|status):\s*(.+?)\s*$", raw)
        if match: values[match.group(1)] = _unquote(match.group(2))
        elif raw and not raw.startswith("  ") and raw.strip() not in {"```", ""}: break
    required = ("id", "project", "section", "class", "title", "status")
    missing = [key for key in required if key not in values]
    if missing: raise ValueError(f"active task missing fields: {','.join(missing)}")
    return ActiveTask(task_ids.canonical_task_id(values["id"]), values["project"], values["section"], values["class"], values["title"], values["status"])


def write_active_task(repo_root: Path, task: TaskRecord | None, *, project: str = "Biella Games", predecessor: str | None = None) -> None:
    if _use_minitz_repo(repo_root):
        path = active_task_path(repo_root)
        program = minitz.load(); ident = minitz.program_identity(program)
        if task is None:
            text = (
                "# 04 - MINITZ ACTIVE TASK PROJECTION\n\n```yaml\n"
                "schema: minitz.active_task_projection/v1\n"
                "projection_authority: false\n"
                f"task_program: {ident['path']}\nprogram_revision: {ident['revision']}\nprogram_sha256: {ident['sha256']}\n\n"
                "task:\n  id: NONE\n  project: MiniTZ\n  section: NONE\n  class: NONE\n"
                "  title: No active MiniTZ task\n  status: COMPLETE\n  runner: STOPPED\n```\n"
            )
        else:
            row = minitz.task_by_id(program, task.id); lane = minitz.task_lane(program, row)
            text = (
                "# 04 - MINITZ ACTIVE TASK PROJECTION\n\n```yaml\n"
                "schema: minitz.active_task_projection/v1\nprojection_authority: false\n"
                f"task_program: {ident['path']}\nprogram_id: {ident['program_id']}\nprogram_revision: {ident['revision']}\nprogram_sha256: {ident['sha256']}\n\n"
                f"task:\n  id: {task.id}\n  project: MiniTZ\n  section: minitz\n  class: {task.task_class}\n"
                f"  title: {task.title}\n  status: {task.status}\n  runner: READY\n  lane: {lane}\n"
                f"  revision: {row['revision']}\n  task_sha256: {row['task_record_sha256']}\n\n"
                "authority:\n  progression: MINITZ_TASK_PROGRAM_ONLY\n  derived_ledgers: NON_AUTHORITATIVE\n"
                "  runner_and_auto_feeder: CONSUME_MINITZ_TASK_PROGRAM\n\n"
                f"stop: Execute only the current MiniTZ task {task.id}; validate and persist before advancing.\n```\n"
            )
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
        return
    from biella_execution_map import task_entry
    mapped = task_entry(repo_root, task.id) if task else None
    if mapped:
        project = {"Games": "Biella Games", "Website": "Biella Website", "Engine": "Biella Engine", "Cross-project": "Biella cross-project proof"}.get(mapped["lane"], project)
    path = active_task_path(repo_root)
    source_root = Path(repo_root) / "projects/biella-games"
    priority = load_project_production(source_root).priority_policy if production_path(source_root).is_file() else "CANONICAL_ORDER"
    if task is None:
        text = (
            "# 04 - BIELLA ACTIVE TASK\n\n```yaml\nschema: biella.active_task/v9\n\n"
            "task:\n  id: NONE\n  project: Biella Games\n  section: NONE\n  class: NONE\n"
            "  title: No active Project task\n  status: COMPLETE\n  runner: STOPPED\n```\n"
        )
    else:
        pred = predecessor or "NONE"
        text = (
            "# 04 - BIELLA ACTIVE TASK\n\n```yaml\nschema: biella.active_task/v9\n\n"
            f"task:\n  id: {task.id}\n  project: {project}\n  section: {task.section_id}\n"
            f"  class: {task.task_class}\n  title: {task.title}\n  status: PENDING\n"
            f"  runner: READY\n  priority: {priority}\n\n"
            "  authority:\n    - Mahdi Taghdisi current product/execution authority\n"
            "    - docs/project-state/03_BIELLA_CURRENT_STATE.md\n"
            "    - projects/biella-games/docs/PRODUCTION.md\n"
            "    - docs/project-state/07_BIELLA_PRODUCTION_SYSTEM.md\n"
            "    - docs/task-program/D_NEXT_100_TASKS.json (active entry only; not a queue)\n\n"
            f"  continuity:\n    completed_predecessor: {pred}\n"
            "    production_source: projects/biella-games/docs/PRODUCTION.md\n\n"
            "  preserve:\n    - all completed predecessor tasks and their evidence\n"
            "    - Engine P4-06 as INCOMPLETE_DEFERRED\n"
            "    - one-repository/one-controller/one-Project-production-source architecture\n\n"
            f"  stop: Execute only {task.id}; validate and persist it before advancing.\n```\n"
        )
    path.write_text(text, encoding="utf-8")


def _update_yaml_block(lines: list[str], block: str, fields: dict[str, str]) -> None:
    start = next((i for i, line in enumerate(lines) if line == f"{block}:"), None)
    if start is None:
        return
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line and not line.startswith(" ") and line != "```":
            end = i
            break
        if line == "```":
            end = i
            break
    seen: set[str] = set()
    for i in range(start + 1, end):
        match = re.match(r"^  ([A-Za-z0-9_-]+):", lines[i])
        if match and match.group(1) in fields:
            key = match.group(1); lines[i] = f"  {key}: {fields[key]}"; seen.add(key)
    insert_at = end
    additions = [f"  {key}: {value}" for key, value in fields.items() if key not in seen]
    if additions:
        lines[insert_at:insert_at] = additions


def sync_current_state(repo_root: Path, production: ProductionState, task: TaskRecord | None, *, state: str = "PENDING") -> None:
    path = current_state_path(repo_root)
    if _use_minitz_repo(repo_root):
        program = minitz.load(); ident = minitz.program_identity(program); current = _minitz_current_row(program)
        completed = sum(row.get("status") in minitz.COMPLETE_STATUSES for row in program["tasks"])
        active_count = sum(row.get("status") in minitz.ACTIVE_STATUSES for row in program["tasks"])
        execution = program.get("current_execution") if isinstance(program.get("current_execution"), dict) else {}
        if current is None:
            active_text = "  id: NONE\n  state: COMPLETE\n  runner: STOPPED\n"
        else:
            active_text = (
                f"  id: {current['task_id']}\n  task_revision: {current['revision']}\n"
                f"  task_sha256: {current['task_record_sha256']}\n  lane: {minitz.task_lane(program, current)}\n"
                f"  state: {current['status']}\n  runner: READY\n"
            )
        continuity = ""
        if execution.get("run_ref"):
            continuity += f"  run_ref: {execution['run_ref']}\n"
        if execution.get("session_ref"):
            continuity += f"  session_ref: {execution['session_ref']}\n"
        repository_identity = _live_repository_identity(repo_root)
        text = (
            "# 03 - MINITZ CURRENT STATE PROJECTION\n\n```yaml\n"
            "schema: minitz.current_state_projection/v1\nstate_class: VOLATILE_CURRENT\nprojection_authority: false\n\n"
            "authority:\n  progression_source: MINITZ_TASK_PROGRAM_ONLY\n"
            f"  task_program_path: {ident['path']}\n  program_id: {ident['program_id']}\n"
            f"  program_revision: {ident['revision']}\n  program_sha256: {ident['sha256']}\n"
            "  task_program_authority: true\n  production_execution_authority: true\n  production_order_status_authority: true\n\n"
            f"repository:\n  repository: {repository_identity}\n  branch: main\n"
            "  canonical_checkout: /root/biella/repos/biella-engine\n  source_identity_source: LIVE_GIT_READ_REQUIRED\n\n"
            "active_execution:\n" + active_text + continuity +
            "  runtime_state_source: /mnt/biella-extra/biella-runtime/codex-production/runtime.json\n\n"
            f"progress:\n  completed_tasks: {completed}\n  active_tasks: {active_count}\n  total_tasks: {len(program['tasks'])}\n\n"
            "execution_invariants:\n  one_task_program: true\n  derived_ledgers_authority: false\n"
            "  runner_and_auto_feeder_source: MINITZ_TASK_PROGRAM_ONLY\n  hidden_task_queue_allowed: false\n"
            "  publication_cursor_authority: false\n  local_qwen_authority: false\n```\n"
        )
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
        return
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    for field in ("feeder", "execution_started", "controller_service_state", "runner_process_state",
                  "codex_child_process_state", "authoritative_persistent_task_session_id",
                  "latest_attempt", "active_model", "active_reasoning", "current_increment",
                  "predecessor", "predecessor_status"):
        _remove_yaml_block_field(lines, "active_execution", field)
    for field in ("source_alignment_commit", "source_alignment_tree"):
        _remove_yaml_block_field(lines, "repository", field)
    for field in ("running_customer_count", "current_state"):
        _remove_yaml_block_field(lines, "customer_execution", field)
    for field in ("current_frontier", "D03_01"):
        _remove_yaml_block_field(lines, "games", field)
    task_id = task.id if task else "NONE"
    _update_yaml_block(lines, "execution_invariants", {"priority_policy": production.priority_policy})
    completed = completed_count(production)
    total = sum(len(section.tasks) for section in production.sections)
    _update_yaml_block(lines, "repository", {
        "source_identity_source": "LIVE_GIT_PLUS_RUNTIME",
    })
    _update_yaml_block(lines, "active_execution", {
        "id": task_id, "project": "Biella Games", "section": task.section_id if task else "NONE",
        "state": state, "runner": "READY" if task else "STOPPED",
        "runtime_state_source": "/mnt/biella-extra/biella-runtime/codex-production/runtime.json",
    })
    _update_yaml_block(lines, "customer_execution", {
        "runtime_state_source": "DOCKER_PLUS_CUSTOMER_HANDOFF_RUNTIME",
    })
    _update_yaml_block(lines, "games", {
        "current_section": task.section_id if task else "NONE",
        "current_task": task_id,
        "completed_tasks": str(completed),
        "total_tasks": str(total),
        "completed_demo_tasks": str(completed_demo_count(production)),
        "queued_successor": task_id,
        "task_boundary": f"{task_id}_{state}",
    })
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    task_ledger.sync_task_ledger(repo_root, production)


def _block_field(text: str, block: str, field: str) -> str | None:
    in_block = False
    prefix = f"  {field}:"
    for raw in text.splitlines():
        if raw == f"{block}:":
            in_block = True
            continue
        if not in_block:
            continue
        if raw and not raw.startswith(" "):
            break
        if raw.startswith(prefix):
            return _unquote(raw.split(":", 1)[1])
    return None



def resolve_current_task(repo_root: Path, project_root: Path) -> TaskRecord | None:
    if _use_minitz_project(project_root):
        production = load_project_production(project_root); current = next_task(production)
        write_active_task(repo_root, current, predecessor=_previous_completed_task(production, current.id) if current else None)
        sync_current_state(repo_root, production, current, state=current.status if current else "COMPLETE")
        return current
    production = sync_project_metadata(project_root)
    task_ledger.sync_task_ledger(repo_root, production)
    current = next_task(production)
    active = load_active_task(repo_root)
    if current is None:
        if active.id != "NONE":
            write_active_task(repo_root, None)
            sync_current_state(repo_root, production, None, state="COMPLETE")
        return None
    if active.id == current.id:
        active_text = active_task_path(repo_root).read_text(encoding="utf-8")
        state_text = current_state_path(repo_root).read_text(encoding="utf-8") if current_state_path(repo_root).exists() else ""
        legacy_active = "feeder:" in active_text or "execution_started:" in active_text
        legacy_state = "feeder:" in state_text or "execution_started:" in state_text
        raw_active_id = _block_field(active_text, "task", "id")
        raw_state_id = _block_field(state_text, "active_execution", "id")
        alias_active = bool(raw_active_id and task_ids.canonical_task_id(raw_active_id) != raw_active_id)
        alias_state = bool(raw_state_id and task_ids.canonical_task_id(raw_state_id) != raw_state_id)
        if legacy_active or legacy_state or alias_active or alias_state:
            write_active_task(repo_root, current, predecessor=_previous_completed_task(production, current.id))
            sync_current_state(repo_root, production, current)
        return current
    if active.id == "NONE":
        write_active_task(repo_root, current, predecessor=_previous_completed_task(production, current.id))
        sync_current_state(repo_root, production, current)
        return current
    try:
        previous = find_task(production, active.id)
    except KeyError as exc:
        raise ValueError(f"active task {active.id} is not in Project production state") from exc
    if previous.status not in _COMPLETE:
        raise ValueError(f"active task mismatch: {active.id} is not complete while Project current is {current.id}")
    write_active_task(repo_root, current, predecessor=previous.id)
    sync_current_state(repo_root, production, current)
    return current


def defer_pending_task_after(project_root: Path, task_id: str, after_task_id: str) -> ProductionState:
    """Move one active task later without changing its completion evidence."""
    if _use_minitz_project(project_root):
        minitz.defer_task_after(task_id, after_task_id, reason=f"Controller resource deferral: {task_id} after {after_task_id}")
        return load_project_production(project_root)
    canonical = task_ids.canonical_task_id(task_id)
    after = task_ids.canonical_task_id(after_task_id)
    production = load_project_production(project_root)
    task = find_task(production, canonical); anchor = find_task(production, after)
    if task.status in _COMPLETE or anchor.status in _COMPLETE:
        raise ValueError("resource deferral requires pending task rows")
    if task.section_id != anchor.section_id:
        raise ValueError("resource deferral cannot cross canonical sections")
    ordered = [item.id for section in production.sections for item in section.tasks]
    if ordered.index(after) <= ordered.index(canonical):
        raise ValueError("resource deferral anchor must follow the blocked task")
    path = production_path(project_root); lines = path.read_text(encoding="utf-8").splitlines()
    task_index = anchor_index = None
    for index, raw in enumerate(lines):
        match = _TASK_RE.match(raw.strip())
        if not match:
            continue
        current = task_ids.canonical_task_id(match.group("id"))
        if current == canonical: task_index = index
        if current == after: anchor_index = index
    if task_index is None or anchor_index is None:
        raise KeyError(f"missing task row for deferral: {canonical}/{after}")
    row = lines.pop(task_index)
    if task_index < anchor_index: anchor_index -= 1
    lines.insert(anchor_index + 1, row)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sync_project_metadata(project_root)


def activate_project_frontier(repo_root: Path, project_root: Path) -> tuple[ProductionState, TaskRecord | None]:
    """Refresh derived 03/04 from the canonical MiniTZ order after an explicit order change."""
    if _use_minitz_project(project_root):
        production = load_project_production(project_root); task = next_task(production)
        write_active_task(repo_root, task, predecessor=_previous_completed_task(production, task.id) if task else None)
        sync_current_state(repo_root, production, task, state=task.status if task else "COMPLETE")
        return production, task
    production = sync_project_metadata(project_root); task = next_task(production)
    predecessor = _previous_completed_task(production, task.id) if task else None
    write_active_task(repo_root, task, predecessor=predecessor)
    sync_current_state(repo_root, production, task, state="PENDING" if task else "COMPLETE")
    return production, task


def mark_task_complete(repo_root: Path, project_root: Path, task_id: str, status: str, evidence: Sequence[str]) -> ProductionState:
    if status not in _COMPLETE:
        raise ValueError("completion status required")
    if _use_minitz_project(project_root):
        minitz.complete_task(task_id, status, evidence)
        production = load_project_production(project_root); successor = next_task(production)
        write_active_task(repo_root, successor, predecessor=task_id)
        sync_current_state(repo_root, production, successor, state=successor.status if successor else "COMPLETE")
        return production
    canonical_id = task_ids.canonical_task_id(task_id)
    path = production_path(project_root)
    lines = path.read_text(encoding="utf-8").splitlines()
    found = False
    for index, raw in enumerate(lines):
        match = _TASK_RE.match(raw.strip())
        if not match or task_ids.canonical_task_id(match.group("id")) != canonical_id:
            continue
        rendered = "; ".join(str(item).strip() for item in evidence if str(item).strip())
        lines[index] = f"- [x] {canonical_id} | {match.group('class')} | {match.group('title').strip()} | {status} | {rendered}"
        found = True
        break
    if not found:
        raise KeyError(task_id)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    production = sync_project_metadata(project_root)
    successor = next_task(production)
    write_active_task(repo_root, successor, predecessor=canonical_id)
    sync_current_state(repo_root, production, successor, state="PENDING" if successor else "COMPLETE")
    return production


def mark_section_status(project_root: Path, section_id: str, status: str) -> ProductionState:
    if _use_minitz_project(project_root):
        raise ValueError("MiniTZ Task Program has no independently mutable section status")
    path = production_path(project_root)
    lines = path.read_text(encoding="utf-8").splitlines()
    found = False
    for index, raw in enumerate(lines):
        match = _SECTION_RE.match(raw.strip())
        if match and match.group("id") == section_id:
            lines[index] = f"## Section: {section_id} | {match.group('title').strip()} | {status}"
            found = True
            break
    if not found:
        raise KeyError(section_id)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sync_project_metadata(project_root)


_ALLOWED_TASK_CLASSES = {"simple", "medium", "creation", "hard", "deep_memory", "hard_creation"}


def apply_section_plan(repo_root: Path, project_root: Path, section_id: str, plan: dict) -> ProductionState:
    if _use_minitz_project(project_root):
        raise ValueError("MiniTZ forbids section planning as a second task queue")
    if plan.get("section_id") != section_id:
        raise ValueError("section plan id mismatch")
    production = load_project_production(project_root)
    section = next((item for item in production.sections if item.id == section_id), None)
    if section is None:
        raise KeyError(section_id)
    if bool(plan.get("complete")):
        production = mark_section_status(project_root, section_id, "COMPLETE_ALREADY" if not section.tasks else "COMPLETE")
        successor = next_task(production)
        write_active_task(repo_root, successor, predecessor=section.tasks[-1].id if section.tasks else section_id)
        sync_current_state(repo_root, production, successor, state="PENDING" if successor else "COMPLETE")
        return production

    existing_titles = {re.sub(r"\s+", " ", task.title.strip().lower()) for task in section.tasks}
    existing_ids = [task.id for item in production.sections for task in item.tasks]
    additions: list[str] = []
    for raw in plan.get("tasks", []):
        if not isinstance(raw, dict):
            raise ValueError("section task must be an object")
        task_class = str(raw.get("class", "")); title = str(raw.get("title", "")).strip()
        if task_class not in _ALLOWED_TASK_CLASSES:
            raise ValueError(f"unknown task class: {task_class}")
        normalized = re.sub(r"\s+", " ", title.lower())
        if not title or normalized in existing_titles:
            continue
        task_id = task_ids.next_task_id(section_id, existing_ids)
        additions.append(f"- [ ] {task_id} | {task_class} | {title} | PENDING | ")
        existing_ids.append(task_id)
        existing_titles.add(normalized)
    if not additions:
        raise ValueError("section plan returned no unique tasks")

    path = production_path(project_root); lines = path.read_text(encoding="utf-8").splitlines()
    for index, raw in enumerate(lines):
        match = _SECTION_RE.match(raw.strip())
        if match and match.group("id") == section_id:
            lines[index] = f"## Section: {section_id} | {match.group('title').strip()} | IN_PROGRESS"
            start = index; break
    else:
        raise KeyError(section_id)
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _SECTION_RE.match(lines[index].strip()): end = index; break
    while end > start + 1 and lines[end - 1] == "": end -= 1
    lines[end:end] = ["", *additions, ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    production = sync_project_metadata(project_root); successor = next_task(production)
    write_active_task(repo_root, successor, predecessor=section.tasks[-1].id if section.tasks else section_id)
    sync_current_state(repo_root, production, successor, state="PENDING")
    return production


def _remove_yaml_block_field(lines: list[str], block: str, field_name: str) -> None:
    start = next((i for i, line in enumerate(lines) if line == f"{block}:"), None)
    if start is None:
        return
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i] == "```" or (lines[i] and not lines[i].startswith(" ")):
            end = i; break
    for i in range(end - 1, start, -1):
        if lines[i].startswith(f"  {field_name}:"):
            del lines[i]


def _previous_completed_task(production: ProductionState, task_id: str) -> str | None:
    previous = None
    for section in production.sections:
        for task in section.tasks:
            if task.id == task_id:
                return previous
            if task.status in _COMPLETE:
                previous = task.id
    return previous
