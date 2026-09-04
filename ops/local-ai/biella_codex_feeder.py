#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


_REASONING_ORDER = ("low", "medium", "high", "xhigh", "max", "ultra")




@dataclass(frozen=True)
class Task:
    id: str
    task_class: str
    title: str


class AlreadyRunning(RuntimeError):
    pass


class RunLock:
    def __init__(self, path: Path):
        self.path = path
        self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise AlreadyRunning(str(self.path)) from exc
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None


@dataclass(frozen=True)
class Route:
    model: str
    reasoning: str


_ROUTE_PROFILES: dict[str, tuple[Route, ...]] = {
    "simple": (
        Route("gpt-5.6-luna", "medium"),
        Route("gpt-5.6-terra", "medium"),
        Route("gpt-5.6-sol", "medium"),
        Route("gpt-5.5", "medium"),
        Route("gpt-6-astra", "high"),
    ),
    "medium": (
        Route("gpt-5.6-luna", "high"),
        Route("gpt-5.6-terra", "high"),
        Route("gpt-5.6-sol", "high"),
        Route("gpt-5.5", "high"),
        Route("gpt-6-astra", "xhigh"),
    ),
    "creation": (
        Route("gpt-5.6-luna", "max"),
        Route("gpt-5.6-sol", "xhigh"),
        Route("gpt-5.6-terra", "xhigh"),
        Route("gpt-6-astra", "xhigh"),
    ),
    "hard": (
        Route("gpt-6-astra", "ultra"),
        Route("gpt-5.6-terra", "ultra"),
        Route("gpt-5.6-sol", "ultra"),
        Route("gpt-5.6-luna", "max"),
    ),
    "deep_memory": (
        Route("gpt-6-astra", "ultra"),
        Route("gpt-5.6-terra", "ultra"),
        Route("gpt-5.6-sol", "ultra"),
    ),
    "hard_creation": (
        Route("gpt-6-astra", "ultra"),
        Route("gpt-5.6-terra", "ultra"),
        Route("gpt-5.6-sol", "ultra"),
        Route("gpt-5.6-luna", "max"),
    ),
}


def reasoning_rank(effort: str) -> int:
    return _REASONING_ORDER.index(effort)


def _cooling_down(model: str, cooldowns: Mapping[str, str], now: datetime) -> bool:
    raw = cooldowns.get(model)
    if not raw:
        return False
    try:
        until = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return until > now


def select_route(
    task_class: str,
    catalog: Mapping[str, set[str]],
    cooldowns: Mapping[str, str],
    now: datetime,
) -> Route:
    candidates = _ROUTE_PROFILES.get(task_class)
    if candidates is None:
        raise ValueError(f"unknown task class: {task_class}")
    for route in candidates:
        if _cooling_down(route.model, cooldowns, now):
            continue
        if route.model not in catalog:
            continue
        if route.reasoning not in catalog[route.model]:
            continue
        if task_class in {"creation", "hard_creation"} and reasoning_rank(route.reasoning) < reasoning_rank("high"):
            continue
        return route
    raise RuntimeError(f"no eligible Codex model for {task_class}")


_LIMIT_RE = re.compile(r"(?:usage_limit_exceeded|rate_limit_exceeded|usage limit|rate limit)", re.I)
_RETRY_RE = re.compile(
    r"(?:try again at|retry at|available at)\s+([A-Za-z]{3}\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M(?:\s+UTC)?)",
    re.I,
)


def limit_retry_at(text: str, observed_at: datetime) -> datetime:
    if not _LIMIT_RE.search(text):
        raise ValueError("not a usage/rate-limit response")
    match = _RETRY_RE.search(text)
    if match:
        raw = match.group(1)
        is_utc = raw.upper().endswith(" UTC")
        if is_utc:
            raw = raw[:-4]
        parsed = datetime.strptime(raw, "%b %d, %Y %I:%M %p")
        if is_utc:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.replace(tzinfo=observed_at.tzinfo or timezone.utc)
    return observed_at + timedelta(minutes=30)


def build_codex_command(route: Route, schema_path: Path, output_path: Path, cwd: Path) -> list[str]:
    codex_bin = os.environ.get("BIELLA_CODEX_BIN", "/usr/bin/codex")
    return [
        codex_bin,
        "--search",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
        "-c",
        'shell_environment_policy.inherit="all"',
        "-c",
        f'model_reasoning_effort="{route.reasoning}"',
        "-m",
        route.model,
        "-C",
        str(cwd),
        "--output-schema",
        str(schema_path),
        "-o",
        str(output_path),
        "-",
    ]


















def result_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["task_id", "status", "summary", "evidence"],
        "properties": {
            "task_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["COMPLETE", "COMPLETE_ALREADY", "CONTINUE", "EXTERNAL_DEPENDENCY", "OWNER_DECISION"],
            },
            "summary": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
    }

_DEMO01_TASKS: tuple[tuple[str, str], ...] = (
    ("deep_memory", "Resolve canonical Games truth, active workers, Git/Drive/runtime state"),
    ("deep_memory", "Reconcile Demo-01 requirements with current verified evidence"),
    ("deep_memory", "Classify reusable recovery source/content without promoting old authority"),
    ("simple", "Verify installed Unreal Engine 5.8.2 tooling and exact build paths"),
    ("simple", "Compare current uproject, modules and Config against reusable recovery pieces"),
    ("medium", "Recover only valid missing Unreal bootstrap pieces into canonical Games source"),
    ("simple", "Build the current canonical Unreal editor/project target"),
    ("simple", "Launch the canonical project and capture real startup/world evidence"),
    ("medium", "Repair startup, map or module errors until runtime is clean"),
    ("medium", "Establish Demo-01 GameMode, GameState and controller ownership chain"),
    ("medium", "Establish one canonical Demo-01 gameplay map and startup world"),
    ("simple", "Recover or implement the third-person player character"),
    ("simple", "Implement current movement/look input mappings"),
    ("simple", "Prove player spawn and possession"),
    ("simple", "Implement and prove third-person camera behavior"),
    ("simple", "Implement and prove continuous locomotion"),
    ("simple", "Implement collision-safe traversal over real world geometry"),
    ("simple", "Implement player health, damage, death and restart lifecycle"),
    ("hard_creation", "Create one compact gameplay arena layout with valid scale and routes"),
    ("simple", "Establish arena collision, traversal surfaces and navigation bounds"),
    ("creation", "Establish runtime lighting and material readability for the arena"),
    ("hard_creation", "Recover/use relevant environment assets without visual-family contamination"),
    ("simple", "Implement or recover weapon ownership and equip state"),
    ("simple", "Implement aim/fire input and authoritative weapon action"),
    ("simple", "Implement projectile/trace hit resolution"),
    ("simple", "Implement target damage and gameplay state consequence"),
    ("creation", "Add readable combat feedback, VFX/audio hooks and death feedback"),
    ("simple", "Implement or recover infected runtime actor foundation"),
    ("simple", "Implement infected navigation over the arena"),
    ("simple", "Implement infected perception and target acquisition"),
    ("simple", "Implement infected chase and attack behavior"),
    ("simple", "Implement infected damage reaction and death"),
    ("medium", "Verify player-versus-infected gameplay chain end to end"),
    ("simple", "Implement or recover one rival contestant actor"),
    ("simple", "Implement rival navigation and world awareness"),
    ("medium", "Implement rival perception and target-selection transitions"),
    ("medium", "Implement rival combat, damage, death and survival response"),
    ("hard", "Verify simultaneous PLAYER + RIVAL + INFECTED interaction"),
    ("deep_memory", "Resolve the currently approved arena-pressure behavior from authority"),
    ("medium", "Implement one authoritative arena-pressure state transition"),
    ("hard", "Make arena pressure affect at least two live systems and verify reactions"),
    ("creation", "Implement minimum Demo-01 HUD and gameplay readability"),
    ("medium", "Implement one executable Demo-01 objective/mission state chain"),
    ("simple", "Implement success, failure and clean retry/restart behavior"),
    ("hard_creation", "Perform gameplay/visual readability pass against approved references"),
    ("medium", "Run stability pass and repair material runtime defects"),
    ("medium", "Measure representative performance/resources and repair material issues"),
    ("medium", "Build/package the most appropriate real Demo-01 executable artifact"),
    ("hard", "Run full end-to-end Demo-01 acceptance in real packaged/current runtime"),
    ("deep_memory", "Close GitHub/Drive evidence durably and record exact next dependency"),
)





_COMPLETE_STATUSES = {"COMPLETE", "COMPLETE_ALREADY"}
_DEMO_LINE_RE = re.compile(r"^- \[(?P<done>[xX ])\] (?P<id>D01-\d{3}) \| (?P<title>[^|]+?) \| (?P<status>[^|]+?) \| (?P<evidence>.*)$")
_STAGE_RE = re.compile(r"^## Stage (?P<number>[2-8]) — (?P<title>.+)$")


def _demo_task_class(task_id: str) -> str:
    number = int(task_id.rsplit("-", 1)[1])
    if 1 <= number <= len(_DEMO01_TASKS):
        return _DEMO01_TASKS[number - 1][0]
    return "medium"


def _read_demo_authority(project_root: Path) -> list[dict[str, Any]]:
    path = project_root / "docs" / "DEMO_01_QUEUE.md"
    tasks: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = _DEMO_LINE_RE.match(raw.strip())
        if not match:
            continue
        status = match.group("status").strip()
        if match.group("done").lower() == "x" and status not in _COMPLETE_STATUSES:
            status = "COMPLETE"
        if status not in _COMPLETE_STATUSES:
            status = "PENDING"
        evidence = match.group("evidence").strip()
        tasks.append({
            "id": match.group("id"),
            "class": _demo_task_class(match.group("id")),
            "title": match.group("title").strip(),
            "status": status,
            "evidence": [evidence] if evidence else [],
        })
    if not tasks:
        raise ValueError(f"no Demo 01 tasks found in {path}")
    return tasks


def _read_stage_sections(project_root: Path) -> list[dict[str, Any]]:
    path = project_root / "docs" / "IMPLEMENTATION_SEQUENCE.md"
    sections: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = _STAGE_RE.match(raw.strip())
        if not match:
            continue
        number = match.group("number")
        sections.append({
            "id": f"stage{number}",
            "title": match.group("title").strip(),
            "source": "docs/IMPLEMENTATION_SEQUENCE.md",
            "status": "PENDING",
            "tasks": [],
            "evidence": [],
        })
    expected = [f"stage{i}" for i in range(2, 9)]
    if [section["id"] for section in sections] != expected:
        raise ValueError("implementation sequence must expose Stage 2 through Stage 8 in order")
    return sections


def _refresh_current(production: dict[str, Any]) -> None:
    for section in production["sections"]:
        if section.get("status") in _COMPLETE_STATUSES:
            continue
        for task in section["tasks"]:
            if task.get("status") not in _COMPLETE_STATUSES:
                production["current_section"] = section["id"]
                production["current_task"] = task["id"]
                return
        production["current_section"] = section["id"]
        production["current_task"] = None
        return
    production["current_section"] = None
    production["current_task"] = None


def demo_handoff_waiting(production: Mapping[str, Any]) -> bool:
    if production.get("demo_execution") != "external_until_complete":
        return False
    demo = next(section for section in production["sections"] if section["id"] == "demo01")
    if demo.get("status") in _COMPLETE_STATUSES:
        return False
    return any(task.get("status") not in _COMPLETE_STATUSES for task in demo.get("tasks", []))


def write_games_production(path: Path, *, project_root: Path = Path("/root/biella/repos/biella-games")) -> Path:
    demo_tasks = _read_demo_authority(project_root)
    sections = [{
        "id": "demo01",
        "title": "Demo 01 — first playable vertical slice",
        "source": "docs/DEMO_01_QUEUE.md",
        "status": "IN_PROGRESS",
        "tasks": demo_tasks,
        "evidence": [],
    }, *_read_stage_sections(project_root)]
    production: dict[str, Any] = {
        "schema_version": 2,
        "run_id": "biella-games-production",
        "goal": "Complete Biella Games through the current accepted production sequence and release-candidate evidence",
        "project_root": str(project_root.resolve()),
        "status": "READY",
        "demo_execution": "external_until_complete",
        "current_section": None,
        "current_task": None,
        "active_model": None,
        "active_reasoning": None,
        "cooldowns": {},
        "attempt_seq": 0,
        "last_result": None,
        "sections": sections,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _refresh_current(production)
    save_production(path, production)
    return path


def load_production(path: Path) -> dict[str, Any]:
    production = json.loads(path.read_text(encoding="utf-8"))
    if production.get("schema_version") != 2:
        raise ValueError("unsupported production schema")
    if not isinstance(production.get("sections"), list) or not production["sections"]:
        raise ValueError("production requires sections")
    seen: set[str] = set()
    for section in production["sections"]:
        if not isinstance(section.get("tasks"), list):
            raise ValueError("section tasks must be a list")
        for task in section["tasks"]:
            task_id = str(task["id"])
            if task_id in seen:
                raise ValueError(f"duplicate task id: {task_id}")
            if task.get("class") not in _ROUTE_PROFILES:
                raise ValueError(f"unknown task class: {task.get('class')}")
            seen.add(task_id)
    return production


def save_production(path: Path, production: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(production, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def find_task(production: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    for section in production["sections"]:
        for task in section["tasks"]:
            if task["id"] == task_id:
                return task
    raise KeyError(task_id)


def next_production_task(production: Mapping[str, Any]) -> Task | None:
    for section in production["sections"]:
        for item in section["tasks"]:
            if item.get("status") not in _COMPLETE_STATUSES:
                return Task(str(item["id"]), str(item["class"]), str(item["title"]))
        if section.get("status") not in _COMPLETE_STATUSES and not section["tasks"]:
            return None
    return None


def mark_production_complete(
    production: dict[str, Any], task_id: str, status: str, model: str, reasoning: str, evidence: Sequence[str]
) -> None:
    if status not in _COMPLETE_STATUSES:
        raise ValueError("completion status required")
    task = find_task(production, task_id)
    task["status"] = status
    task["model"] = model
    task["reasoning"] = reasoning
    task["evidence"] = list(evidence)
    task["completed_at"] = datetime.now(timezone.utc).isoformat()
    production["last_result"] = {"task_id": task_id, "status": status, "model": model, "reasoning": reasoning, "evidence": list(evidence)}
    production["updated_at"] = datetime.now(timezone.utc).isoformat()
    _refresh_current(production)


def sync_demo_progress(path: Path) -> None:
    production = load_production(path)
    project_root = Path(str(production["project_root"]))
    source_tasks = _read_demo_authority(project_root)
    demo = next(section for section in production["sections"] if section["id"] == "demo01")
    existing = {task["id"]: task for task in demo["tasks"]}
    for source in source_tasks:
        task = existing.get(source["id"])
        if task is None:
            demo["tasks"].append(source)
            continue
        task["title"] = source["title"]
        task["class"] = source["class"]
        if task.get("status") not in _COMPLETE_STATUSES and source["status"] in _COMPLETE_STATUSES:
            task["status"] = source["status"]
            task["evidence"] = source["evidence"]
    if all(task.get("status") in _COMPLETE_STATUSES for task in demo["tasks"]):
        demo["status"] = "COMPLETE"
    _refresh_current(production)
    production["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_production(path, production)


def apply_section_plan(production: dict[str, Any], section_id: str, plan: Mapping[str, Any]) -> None:
    if plan.get("section_id") != section_id:
        raise ValueError("section plan id mismatch")
    section = next(section for section in production["sections"] if section["id"] == section_id)
    if bool(plan.get("complete")):
        section["status"] = "COMPLETE_ALREADY" if not section["tasks"] else "COMPLETE"
        section["evidence"] = list(plan.get("evidence", []))
        section["summary"] = str(plan.get("summary", ""))
        _refresh_current(production)
        return
    existing_titles = {re.sub(r"\s+", " ", str(task["title"]).strip().lower()) for task in section["tasks"]}
    prefix_match = re.search(r"(\d+)$", section_id)
    prefix = f"S{prefix_match.group(1)}" if prefix_match else section_id.upper()
    next_number = len(section["tasks"]) + 1
    for raw in plan.get("tasks", []):
        task_class = str(raw["class"])
        if task_class not in _ROUTE_PROFILES:
            raise ValueError(f"unknown task class: {task_class}")
        title = str(raw["title"]).strip()
        normalized = re.sub(r"\s+", " ", title.lower())
        if not title or normalized in existing_titles:
            continue
        section["tasks"].append({
            "id": f"{prefix}-{next_number:03d}",
            "class": task_class,
            "title": title,
            "status": "PENDING",
            "evidence": [],
        })
        existing_titles.add(normalized)
        next_number += 1
    section["status"] = "IN_PROGRESS"
    section["summary"] = str(plan.get("summary", ""))
    section["evidence"] = list(plan.get("evidence", []))
    _refresh_current(production)


def _section_record(production: Mapping[str, Any], section_id: str) -> dict[str, Any]:
    for section in production["sections"]:
        if section["id"] == section_id:
            return section
    raise KeyError(section_id)


def _section_for_task(production: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    for section in production["sections"]:
        if any(task["id"] == task_id for task in section["tasks"]):
            return section
    raise KeyError(task_id)


def section_plan_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["section_id", "complete", "summary", "evidence", "tasks"],
        "properties": {
            "section_id": {"type": "string"},
            "complete": {"type": "boolean"},
            "summary": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "tasks": {
                "type": "array",
                "maxItems": 50,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["class", "title"],
                    "properties": {
                        "class": {"type": "string", "enum": sorted(_ROUTE_PROFILES)},
                        "title": {"type": "string", "minLength": 1, "maxLength": 240},
                    },
                },
            },
        },
    }


def build_section_prompt(production: Mapping[str, Any], section: Mapping[str, Any], *, audit: bool) -> str:
    existing = [
        f"{task['id']} [{task.get('status','PENDING')}] {task['title']}"
        for task in section.get("tasks", [])[-50:]
    ]
    existing_text = "\n".join(existing) if existing else "none"
    mode = (
        "Audit this section after execution. If every accepted requirement in this section is now satisfied by current source and real evidence, return complete=true. Otherwise return only the remaining missing tasks."
        if audit
        else "Plan the currently incomplete work for this section. Return 20 to 50 bounded tasks unless materially fewer are required by current accepted scope."
    )
    return (
        "Biella Games production section refresh. Work from current canonical GitHub/Drive/runtime authority and directly relevant source only.\n"
        f"RUN: {production['run_id']}\nGOAL: {production['goal']}\n"
        f"PROJECT: {production['project_root']}\nSECTION: {section['id']} | {section['title']}\nSOURCE: {section.get('source','')}\n"
        f"MODE: {mode}\nEXISTING SECTION TASKS:\n{existing_text}\n"
        "Tasks must be non-overlapping, dependency-aware, execution-sized, and limited to this section. Preserve completed work. "
        "Do not derive work from stale TODOs or historical files unless current authority requires it. Do not invent product scope. "
        "Use deep inspection only for named missing facts. Creation tasks must be classified creation/hard_creation and never rely on low reasoning. "
        "Set complete=true only with current implementation/runtime evidence supporting the whole section."
    )


def build_production_task_prompt(production: Mapping[str, Any], task: Task) -> str:
    section = _section_for_task(production, task.id)
    record = find_task(production, task.id)
    previous = production.get("last_result")
    previous_text = "none"
    if isinstance(previous, dict) and previous.get("task_id") == task.id:
        previous_text = json.dumps(previous, sort_keys=True, separators=(",", ":"))
    return (
        "Biella Games production task. Work autonomously from /root and follow current AGENTS/current GitHub/Drive/runtime authority.\n"
        f"RUN: {production['run_id']}\nGOAL: {production['goal']}\n"
        f"SECTION: {section['id']} | {section['title']}\nTASK: {task.id} [{task.task_class}] {task.title}\n"
        f"PROJECT: {production['project_root']}\nPREVIOUS_ATTEMPT: {previous_text}\n"
        "Execute only this task boundary. Verify current work before editing and preserve valid completed work. "
        "Do not reopen earlier section tasks. Internal tool/build/provider failures are repair/routing work. "
        "Codex may use configured local Qwen, APIs, GPU, Unreal, GitHub, Drive and production tools when useful. "
        "Do not manage Codex account quota or usage resets. Creation output must be real/editable and visually inspectable when applicable. "
        "Return COMPLETE_ALREADY when current evidence already satisfies the task."
    )


def _invoke_structured(
    prompt: str,
    route: Route,
    runtime_root: Path,
    schema_path: Path,
    output_path: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> tuple[int, Mapping[str, Any] | None, str]:
    cmd = build_codex_command(route, schema_path, output_path, Path("/root"))
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.run(cmd, input=prompt, text=True, stdout=stdout, stderr=stderr, check=False, env=os.environ.copy())
    error_text = _tail_text(stderr_path) + "\n" + _tail_text(stdout_path)
    if proc.returncode != 0:
        return proc.returncode, None, error_text
    if not output_path.exists():
        return 1, None, "Codex completed without structured result"
    try:
        return 0, json.loads(output_path.read_text(encoding="utf-8")), error_text
    except json.JSONDecodeError as exc:
        return 1, None, f"invalid structured result: {exc}"


def _record_production_failure(
    production: dict[str, Any], route: Route, detail: str, observed: datetime, *, task_id: str | None = None, limited: bool = False
) -> None:
    retry_at = limit_retry_at(detail, observed) if limited else observed + timedelta(minutes=2)
    production.setdefault("cooldowns", {})[route.model] = retry_at.isoformat()
    production["last_result"] = {
        "task_id": task_id,
        "status": "MODEL_COOLDOWN" if limited else "MODEL_RUNTIME_COOLDOWN",
        "model": route.model,
        "reasoning": route.reasoning,
        "retry_at": retry_at.isoformat(),
        "summary": detail[-2000:],
        "evidence": [],
    }
    production["updated_at"] = observed.isoformat()


def _invoke_production_task(
    production: dict[str, Any], task: Task, route: Route, runtime_root: Path, schema_path: Path
) -> tuple[int, Mapping[str, Any] | None, str]:
    seq = int(production.get("attempt_seq", 0)) + 1
    production["attempt_seq"] = seq
    attempts = runtime_root / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    stem = f"{seq:04d}-{task.id}-{route.model}"
    return _invoke_structured(
        build_production_task_prompt(production, task), route, runtime_root, schema_path,
        attempts / f"{stem}.result.json", attempts / f"{stem}.stdout.log", attempts / f"{stem}.stderr.log"
    )


def _invoke_section_plan(
    production: dict[str, Any], section: Mapping[str, Any], route: Route, runtime_root: Path, schema_path: Path, *, audit: bool
) -> tuple[int, Mapping[str, Any] | None, str]:
    seq = int(production.get("attempt_seq", 0)) + 1
    production["attempt_seq"] = seq
    attempts = runtime_root / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    stem = f"{seq:04d}-PLAN-{section['id']}-{route.model}"
    return _invoke_structured(
        build_section_prompt(production, section, audit=audit), route, runtime_root, schema_path,
        attempts / f"{stem}.result.json", attempts / f"{stem}.stdout.log", attempts / f"{stem}.stderr.log"
    )


def _apply_production_task_result(
    production: dict[str, Any], task: Task, route: Route, result: Mapping[str, Any], observed: datetime
) -> str:
    if result.get("task_id") != task.id:
        raise ValueError("agent result task_id mismatch")
    status = str(result.get("status"))
    summary = str(result.get("summary", ""))
    evidence = list(result.get("evidence", []))
    record = find_task(production, task.id)
    if status in _COMPLETE_STATUSES:
        record["status"] = status
        record["summary"] = summary
        record["evidence"] = evidence
        record["model"] = route.model
        record["reasoning"] = route.reasoning
        record["completed_at"] = observed.isoformat()
        production["last_result"] = {"task_id": task.id, "status": status, "summary": summary, "evidence": evidence, "model": route.model, "reasoning": route.reasoning}
        production["status"] = "RUNNING"
        production["updated_at"] = observed.isoformat()
        _refresh_current(production)
        return "ADVANCE"
    production["last_result"] = {"task_id": task.id, "status": status, "summary": summary, "evidence": evidence, "model": route.model, "reasoning": route.reasoning}
    production["updated_at"] = observed.isoformat()
    if status == "CONTINUE":
        record["status"] = "PENDING"
        production["status"] = "RUNNING"
        production["current_task"] = task.id
        return "RETRY_TASK"
    if status in {"EXTERNAL_DEPENDENCY", "OWNER_DECISION"}:
        production["status"] = status
        production["current_task"] = task.id
        return "PAUSE"
    raise ValueError(f"unsupported agent status: {status}")


def run_production(production_path: Path, *, runtime_root: Path | None = None) -> int:
    production = load_production(production_path)
    if _section_record(production, "demo01").get("status") not in _COMPLETE_STATUSES:
        try:
            sync_demo_progress(production_path)
            production = load_production(production_path)
        except (FileNotFoundError, ValueError):
            pass
    runtime_root = runtime_root or Path("/mnt/biella-extra/biella-runtime/codex-feeder") / str(production["run_id"])
    runtime_root.mkdir(parents=True, exist_ok=True)
    task_schema_path = runtime_root / "result-schema.json"
    section_schema_path = runtime_root / "section-plan-schema.json"
    task_schema_path.write_text(json.dumps(result_schema(), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    section_schema_path.write_text(json.dumps(section_plan_schema(), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    lock = RunLock(runtime_root / "run.lock")
    lock.acquire()
    try:
        production["status"] = "RUNNING"
        save_production(production_path, production)
        catalog = discover_catalog()
        while True:
            if demo_handoff_waiting(production):
                try:
                    sync_demo_progress(production_path)
                    production = load_production(production_path)
                except (FileNotFoundError, ValueError):
                    pass
                if demo_handoff_waiting(production):
                    production["status"] = "WAITING_DEMO_HANDOFF"
                    production["active_model"] = None
                    production["active_reasoning"] = None
                    production["updated_at"] = datetime.now(timezone.utc).isoformat()
                    save_production(production_path, production)
                    time.sleep(max(1.0, float(os.environ.get("BIELLA_DEMO_HANDOFF_POLL_SECONDS", "30"))))
                    continue
                production["status"] = "RUNNING"
                save_production(production_path, production)
            _refresh_current(production)
            section_id = production.get("current_section")
            if not section_id:
                production["status"] = "COMPLETE"
                production["current_task"] = None
                production["active_model"] = None
                production["active_reasoning"] = None
                production["updated_at"] = datetime.now(timezone.utc).isoformat()
                save_production(production_path, production)
                return 0
            section = _section_record(production, str(section_id))
            task = next_production_task(production)
            if task is None or _section_for_task(production, task.id)["id"] != section_id:
                if section_id == "demo01":
                    section["status"] = "COMPLETE"
                    _refresh_current(production)
                    save_production(production_path, production)
                    continue
                audit = bool(section.get("tasks"))
                now = datetime.now(timezone.utc)
                try:
                    route = select_route("deep_memory", catalog, production.get("cooldowns", {}), now)
                except RuntimeError:
                    production["status"] = "WAITING_MODEL_AVAILABILITY"
                    save_production(production_path, production)
                    time.sleep(min(60.0, max(1.0, _earliest_cooldown_delay(production.get("cooldowns", {}), now))))
                    catalog = discover_catalog()
                    continue
                production["active_model"] = route.model
                production["active_reasoning"] = route.reasoning
                save_production(production_path, production)
                rc, plan, error_text = _invoke_section_plan(production, section, route, runtime_root, section_schema_path, audit=audit)
                observed = datetime.now(timezone.utc)
                if rc != 0:
                    _record_production_failure(production, route, error_text, observed, limited=bool(_LIMIT_RE.search(error_text)))
                    save_production(production_path, production)
                    continue
                before = len(section["tasks"])
                try:
                    apply_section_plan(production, str(section_id), plan or {})
                except (ValueError, TypeError, KeyError) as exc:
                    _record_production_failure(production, route, f"invalid section plan: {exc}", observed)
                    save_production(production_path, production)
                    continue
                if not bool((plan or {}).get("complete")) and len(section["tasks"]) == before:
                    _record_production_failure(production, route, "section planner returned no new tasks and did not complete section", observed)
                save_production(production_path, production)
                continue
            now = datetime.now(timezone.utc)
            try:
                route = select_route(task.task_class, catalog, production.get("cooldowns", {}), now)
            except RuntimeError:
                production["status"] = "WAITING_MODEL_AVAILABILITY"
                save_production(production_path, production)
                time.sleep(min(60.0, max(1.0, _earliest_cooldown_delay(production.get("cooldowns", {}), now))))
                catalog = discover_catalog()
                continue
            production["active_model"] = route.model
            production["active_reasoning"] = route.reasoning
            production["current_task"] = task.id
            save_production(production_path, production)
            rc, result, error_text = _invoke_production_task(production, task, route, runtime_root, task_schema_path)
            observed = datetime.now(timezone.utc)
            if rc != 0:
                _record_production_failure(production, route, error_text, observed, task_id=task.id, limited=bool(_LIMIT_RE.search(error_text)))
                save_production(production_path, production)
                continue
            try:
                action = _apply_production_task_result(production, task, route, result or {}, observed)
            except (ValueError, TypeError, KeyError) as exc:
                _record_production_failure(production, route, f"invalid agent result: {exc}", observed, task_id=task.id)
                save_production(production_path, production)
                continue
            save_production(production_path, production)
            if action == "PAUSE":
                return 2
    finally:
        lock.release()




def discover_catalog() -> dict[str, set[str]]:
    codex_bin = os.environ.get("BIELLA_CODEX_BIN", "/usr/bin/codex")
    proc = subprocess.run(
        [codex_bin, "debug", "models"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return _fallback_catalog()
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _fallback_catalog()
    result: dict[str, set[str]] = {}
    models = data.get("models", []) if isinstance(data, dict) else []
    for item in models:
        if not isinstance(item, dict):
            continue
        slug = item.get("slug")
        if not isinstance(slug, str):
            continue
        levels = {
            str(level.get("effort"))
            for level in item.get("supported_reasoning_levels", [])
            if isinstance(level, dict) and level.get("effort")
        }
        if levels:
            result[slug] = levels
    return result or _fallback_catalog()


def _fallback_catalog() -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for routes in _ROUTE_PROFILES.values():
        for route in routes:
            result.setdefault(route.model, set()).add(route.reasoning)
    return result


def _tail_text(path: Path, maximum_bytes: int = 65536) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    return data[-maximum_bytes:].decode("utf-8", errors="replace")




def _earliest_cooldown_delay(cooldowns: Mapping[str, str], now: datetime) -> float:
    waits: list[float] = []
    for raw in cooldowns.values():
        try:
            target = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        delta = (target - now).total_seconds()
        if delta > 0:
            waits.append(delta)
    return min(waits) if waits else 60.0









def _unit_name(run_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id).strip("-.") or "run"
    return f"biella-codex-feed-{safe}"







def _production_path() -> Path:
    return Path(os.environ.get("BIELLA_GAMES_PRODUCTION_FILE", "/root/biella/work/games-production.json"))


def _project_root() -> Path:
    return Path(os.environ.get("BIELLA_GAMES_PROJECT_ROOT", "/root/biella/repos/biella-games"))


def init_production(path: Path, *, project_root: Path) -> Path:
    if path.exists():
        sync_demo_progress(path)
        production = load_production(path)
        if "demo_execution" not in production:
            production["demo_execution"] = "external_until_complete"
            save_production(path, production)
        return path
    return write_games_production(path, project_root=project_root)


def production_status_payload(path: Path) -> dict[str, Any]:
    production = load_production(path)
    total = 0
    completed = 0
    section_summary: list[dict[str, Any]] = []
    for section in production["sections"]:
        section_total = len(section["tasks"])
        section_completed = sum(1 for task in section["tasks"] if task.get("status") in _COMPLETE_STATUSES)
        total += section_total
        completed += section_completed
        section_summary.append({
            "id": section["id"],
            "status": section["status"],
            "completed": section_completed,
            "total": section_total,
        })
    return {
        "run_id": production["run_id"],
        "status": production.get("status", "READY"),
        "current_section": production.get("current_section"),
        "current_task": production.get("current_task"),
        "completed": completed,
        "total": total,
        "active_model": production.get("active_model"),
        "active_reasoning": production.get("active_reasoning"),
        "cooldowns": production.get("cooldowns", {}),
        "sections": section_summary,
        "last_result": production.get("last_result"),
    }


def start_production(path: Path) -> int:
    init_production(path, project_root=_project_root())
    production = load_production(path)
    unit = _unit_name(production["run_id"])
    active = subprocess.run(["systemctl", "is-active", "--quiet", unit], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if active.returncode == 0:
        print(json.dumps({"unit": unit, "status": "ALREADY_RUNNING"}, sort_keys=True))
        return 0
    entrypoint = os.environ.get("BIELLA_CODEX_ENTRYPOINT", "/usr/local/bin/biella-codex")
    cmd = [
        "systemd-run",
        f"--unit={unit}",
        "--collect",
        "--property=Type=exec",
        "--property=Restart=no",
        f"--setenv=BIELLA_GAMES_PRODUCTION_FILE={path.resolve()}",
        f"--setenv=BIELLA_GAMES_PROJECT_ROOT={_project_root().resolve()}",
        entrypoint,
        "feed",
        "run",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr, end="")
        return proc.returncode
    print(json.dumps({"unit": unit, "status": "STARTED"}, sort_keys=True))
    return 0


def stop_production(path: Path) -> int:
    production = load_production(path)
    return subprocess.run(["systemctl", "stop", _unit_name(production["run_id"])], check=False).returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biella-codex feed")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("sync")
    sub.add_parser("run")
    sub.add_parser("start")
    sub.add_parser("status")
    sub.add_parser("stop")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    os.umask(0o077)
    args = _parser().parse_args(argv)
    production_path = _production_path()
    if args.command == "init":
        init_production(production_path, project_root=_project_root())
        payload = production_status_payload(production_path)
        payload["production"] = str(production_path.resolve())
        print(json.dumps(payload, sort_keys=True))
        return 0
    if args.command == "sync":
        sync_demo_progress(production_path)
        print(json.dumps(production_status_payload(production_path), sort_keys=True))
        return 0
    if args.command == "run":
        return run_production(production_path)
    if args.command == "start":
        return start_production(production_path)
    if args.command == "status":
        print(json.dumps(production_status_payload(production_path), sort_keys=True))
        return 0
    if args.command == "stop":
        return stop_production(production_path)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
