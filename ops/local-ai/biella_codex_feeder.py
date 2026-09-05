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









_COMPLETE_STATUSES = {"COMPLETE", "COMPLETE_ALREADY"}
_PROJECT_SECTION_RE = re.compile(r"^## Section: (?P<id>[a-zA-Z0-9_-]+) \| (?P<title>.+?) \| (?P<status>[A-Z_]+)$")
_PROJECT_TASK_RE = re.compile(r"^- \[(?P<done>[xX ])\] (?P<id>[A-Z0-9-]+) \| (?P<class>[a-z_]+) \| (?P<title>.+?) \| (?P<status>[A-Z_]+) \|\s*(?P<evidence>.*)$")
_RUNTIME_STATE_KEYS = {
    "status", "active_model", "active_reasoning", "cooldowns", "attempt_seq",
    "last_result", "heartbeat_at", "updated_at",
}


def _production_markdown_path(project_root: Path) -> Path:
    return project_root / "docs" / "PRODUCTION.md"


def _unquote_meta(value: str) -> str:
    value = value.strip()
    return value[1:-1] if value.startswith("`") and value.endswith("`") and len(value) >= 2 else value


def load_project_production(project_root: Path) -> dict[str, Any]:
    path = _production_markdown_path(project_root)
    lines = path.read_text(encoding="utf-8").splitlines()
    state: dict[str, Any] = {
        "run_id": "biella-games-production",
        "goal": "Complete Biella Games through the accepted production sequence",
        "project_root": str(project_root.resolve()),
        "status": "IN_PROGRESS",
        "current_section": None,
        "current_task": None,
        "sections": [],
    }
    current_section: dict[str, Any] | None = None
    for raw in lines:
        line = raw.strip()
        if line.startswith("Status:") and not state["sections"]:
            state["status"] = _unquote_meta(line.split(":", 1)[1])
            continue
        if line.startswith("Current section:"):
            value = _unquote_meta(line.split(":", 1)[1]); state["current_section"] = None if value in {"", "NONE", "null"} else value
            continue
        if line.startswith("Current task:"):
            value = _unquote_meta(line.split(":", 1)[1])
            state["current_task"] = None if value in {"", "NONE", "null"} else value
            continue
        match = _PROJECT_SECTION_RE.match(line)
        if match:
            current_section = {
                "id": match.group("id"), "title": match.group("title").strip(),
                "status": match.group("status"), "source": "docs/PRODUCTION.md",
                "tasks": [], "evidence": [],
            }
            state["sections"].append(current_section)
            continue
        match = _PROJECT_TASK_RE.match(line)
        if match and current_section is not None:
            status = match.group("status")
            if match.group("done").lower() == "x" and status not in _COMPLETE_STATUSES:
                status = "COMPLETE"
            evidence = match.group("evidence").strip()
            task_class = match.group("class")
            if task_class not in _ROUTE_PROFILES:
                raise ValueError(f"unknown task class: {task_class}")
            current_section["tasks"].append({
                "id": match.group("id"), "class": task_class,
                "title": match.group("title").strip(), "status": status,
                "evidence": [evidence] if evidence else [],
            })
    if not state["sections"]:
        raise ValueError(f"no production sections found in {path}")
    return state


def find_task(production: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    for section in production["sections"]:
        for task in section["tasks"]:
            if task["id"] == task_id:
                return task
    raise KeyError(task_id)


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


def next_production_task(production: Mapping[str, Any]) -> Task | None:
    for section in production["sections"]:
        if section.get("status") in _COMPLETE_STATUSES:
            continue
        for item in section["tasks"]:
            if item.get("status") not in _COMPLETE_STATUSES:
                return Task(str(item["id"]), str(item["class"]), str(item["title"]))
        return None
    return None


def _desired_current(production: Mapping[str, Any]) -> tuple[str | None, str | None]:
    for section in production["sections"]:
        if section.get("status") in _COMPLETE_STATUSES:
            continue
        for task in section["tasks"]:
            if task.get("status") not in _COMPLETE_STATUSES:
                return str(section["id"]), str(task["id"])
        return str(section["id"]), None
    return None, None


def _replace_meta_line(lines: list[str], prefix: str, value: str | None) -> None:
    rendered = f"{prefix} `{value if value is not None else 'NONE'}`"
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = rendered
            return
    raise ValueError(f"missing production metadata line: {prefix}")


def sync_project_metadata(project_root: Path) -> None:
    path = _production_markdown_path(project_root)
    state = load_project_production(project_root)
    section, task = _desired_current(state)
    lines = path.read_text(encoding="utf-8").splitlines()
    _replace_meta_line(lines, "Current section:", section)
    _replace_meta_line(lines, "Current task:", task)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mark_project_task_complete(project_root: Path, task_id: str, status: str, evidence: Sequence[str]) -> None:
    if status not in _COMPLETE_STATUSES:
        raise ValueError("completion status required")
    path = _production_markdown_path(project_root)
    lines = path.read_text(encoding="utf-8").splitlines()
    found = False
    for index, raw in enumerate(lines):
        match = _PROJECT_TASK_RE.match(raw.strip())
        if not match or match.group("id") != task_id:
            continue
        evidence_text = "; ".join(str(item) for item in evidence)
        lines[index] = f"- [x] {task_id} | {match.group('class')} | {match.group('title').strip()} | {status} | {evidence_text}"
        found = True
        break
    if not found:
        raise KeyError(task_id)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    state = load_project_production(project_root)
    section = _section_for_task(state, task_id)
    if section["id"] == "demo01" and section["tasks"] and all(t.get("status") in _COMPLETE_STATUSES for t in section["tasks"]):
        lines = path.read_text(encoding="utf-8").splitlines()
        _replace_section_status(lines, "demo01", "COMPLETE")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sync_project_metadata(project_root)


def _replace_section_status(lines: list[str], section_id: str, status: str) -> None:
    for index, raw in enumerate(lines):
        match = _PROJECT_SECTION_RE.match(raw.strip())
        if match and match.group("id") == section_id:
            lines[index] = f"## Section: {section_id} | {match.group('title').strip()} | {status}"
            return
    raise KeyError(section_id)


def apply_section_plan_to_project(project_root: Path, section_id: str, plan: Mapping[str, Any]) -> None:
    if plan.get("section_id") != section_id:
        raise ValueError("section plan id mismatch")
    path = _production_markdown_path(project_root)
    state = load_project_production(project_root)
    section = _section_record(state, section_id)
    lines = path.read_text(encoding="utf-8").splitlines()
    if bool(plan.get("complete")):
        _replace_section_status(lines, section_id, "COMPLETE_ALREADY" if not section["tasks"] else "COMPLETE")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        sync_project_metadata(project_root)
        return
    existing_titles = {re.sub(r"\s+", " ", str(t["title"]).strip().lower()) for t in section["tasks"]}
    prefix_match = re.search(r"(\d+)$", section_id)
    prefix = f"S{prefix_match.group(1)}" if prefix_match else section_id.upper()
    next_number = 1
    for task in section["tasks"]:
        m = re.match(re.escape(prefix) + r"-(\d+)$", str(task["id"]))
        if m:
            next_number = max(next_number, int(m.group(1)) + 1)
    additions: list[str] = []
    for raw in plan.get("tasks", []):
        task_class = str(raw["class"])
        if task_class not in _ROUTE_PROFILES:
            raise ValueError(f"unknown task class: {task_class}")
        title = str(raw["title"]).strip()
        normalized = re.sub(r"\s+", " ", title.lower())
        if not title or normalized in existing_titles:
            continue
        additions.append(f"- [ ] {prefix}-{next_number:03d} | {task_class} | {title} | PENDING | ")
        existing_titles.add(normalized)
        next_number += 1
    if not additions:
        raise ValueError("section plan returned no unique tasks")
    _replace_section_status(lines, section_id, "IN_PROGRESS")
    start = next(i for i, raw in enumerate(lines) if (_PROJECT_SECTION_RE.match(raw.strip()) and _PROJECT_SECTION_RE.match(raw.strip()).group("id") == section_id))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if _PROJECT_SECTION_RE.match(lines[i].strip()):
            end = i
            break
    while end > start + 1 and lines[end - 1] == "":
        end -= 1
    lines[end:end] = ["", *additions, ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sync_project_metadata(project_root)


def section_plan_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False,
        "required": ["section_id", "complete", "summary", "evidence", "tasks"],
        "properties": {
            "section_id": {"type": "string"}, "complete": {"type": "boolean"}, "summary": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "tasks": {"type": "array", "maxItems": 50, "items": {"type": "object", "additionalProperties": False,
                "required": ["class", "title"], "properties": {"class": {"type": "string", "enum": sorted(_ROUTE_PROFILES)},
                "title": {"type": "string", "minLength": 1, "maxLength": 240}}}},
        },
    }


def build_section_prompt(production: Mapping[str, Any], section: Mapping[str, Any], *, audit: bool) -> str:
    existing = "\n".join(f"{t['id']} [{t.get('status','PENDING')}] {t['title']}" for t in section.get("tasks", [])[-50:]) or "none"
    mode = "Audit this section. Return complete=true only if current source and real evidence satisfy the accepted section; otherwise return only missing delta tasks." if audit else "Plan the incomplete work. Return 20 to 50 bounded tasks unless materially fewer are required by accepted scope."
    return (
        "Biella production section task. Use current canonical repo/Drive/runtime truth and only directly relevant source.\n"
        f"PROJECT: {production['project_root']}\nSECTION: {section['id']} | {section['title']}\nMODE: {mode}\nEXISTING:\n{existing}\n"
        "Tasks must be non-overlapping, dependency-aware, execution-sized, and limited to this section. Preserve completed work. "
        "Use `biella resource route <capability>` for specialized research/preprocessing where it saves model work; free/trial/prepaid and paid external Resources are authorized when useful, without quota probing. "
        "Do not invent scope or reopen completed tasks without material invalidation evidence."
    )


def build_production_task_prompt(production: Mapping[str, Any], task: Task) -> str:
    section = _section_for_task(production, task.id)
    return (
        "Biella production task. Follow current scoped AGENTS, canonical Git/Drive/runtime authority, and preserve completed work.\n"
        f"PROJECT: {production['project_root']}\nSECTION: {section['id']} | {section['title']}\nTASK: {task.id} [{task.task_class}] {task.title}\n"
        "Execute only this task boundary. Use real editable outputs and task-derived validation. Return COMPLETE_ALREADY when current evidence already satisfies it. "
        "Before expensive general-model work, use `biella resource route <capability>` and specialized configured Resources when they materially reduce time/tokens or improve quality; free/trial/prepaid and paid external Resource use is authorized. "
        "Use one provider by default, validate provider outputs against the task, and do not probe quota/balance. Do not manage Codex usage/reset/credits."
    )


def initial_runtime_state() -> dict[str, Any]:
    return {"status": "STOPPED", "active_model": None, "active_reasoning": None, "cooldowns": {}, "attempt_seq": 0,
            "last_result": None, "heartbeat_at": None, "updated_at": datetime.now(timezone.utc).isoformat()}


def save_runtime_state(path: Path, runtime: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: runtime.get(key) for key in _RUNTIME_STATE_KEYS}
    payload["cooldowns"] = dict(payload.get("cooldowns") or {})
    payload["attempt_seq"] = int(payload.get("attempt_seq") or 0)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_runtime_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return initial_runtime_state()
    raw = json.loads(path.read_text(encoding="utf-8"))
    base = initial_runtime_state()
    for key in _RUNTIME_STATE_KEYS:
        if key in raw:
            base[key] = raw[key]
    return base


def _runtime_root() -> Path:
    return Path(os.environ.get("BIELLA_CODEX_FEED_RUNTIME_ROOT", "/mnt/biella-extra/biella-runtime/codex-feeder/biella-games-production"))


def _project_root() -> Path:
    return Path(os.environ.get("BIELLA_GAMES_PROJECT_ROOT", "/root/biella/repos/biella-engine/projects/biella-games"))


def _service_active(unit: str) -> bool:
    return subprocess.run(["systemctl", "is-active", "--quiet", unit], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def production_status_payload(project_root: Path, *, runtime_root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    production = load_project_production(project_root)
    runtime_root = runtime_root or _runtime_root(); runtime = load_runtime_state(runtime_root / "runtime.json")
    now = now or datetime.now(timezone.utc); active = _service_active(_unit_name(production["run_id"]))
    if not active:
        liveness = "STOPPED"
    else:
        heartbeat = None
        raw = runtime.get("heartbeat_at")
        if isinstance(raw, str) and raw:
            try:
                heartbeat = datetime.fromisoformat(raw)
                if heartbeat.tzinfo is None: heartbeat = heartbeat.replace(tzinfo=timezone.utc)
            except ValueError: pass
        if heartbeat is None or (now - heartbeat).total_seconds() > 90:
            liveness = "STALE"
        elif str(runtime.get("status")) in {"EXTERNAL_DEPENDENCY", "OWNER_DECISION", "WAITING_MODEL_AVAILABILITY", "WAITING"}:
            liveness = "WAITING"
        elif str(runtime.get("status")) in {"ERROR", "FAILED"}:
            liveness = "ERROR"
        else:
            liveness = "ACTIVE"
    sections=[]; total=completed=0
    for section in production["sections"]:
        st=len(section["tasks"]); sc=sum(1 for t in section["tasks"] if t.get("status") in _COMPLETE_STATUSES)
        total += st; completed += sc; sections.append({"id": section["id"], "status": section["status"], "completed": sc, "total": st})
    return {"run_id": production["run_id"], "status": liveness, "current_section": production.get("current_section"),
            "current_task": production.get("current_task"), "completed": completed, "total": total,
            "active_model": runtime.get("active_model"), "active_reasoning": runtime.get("active_reasoning"),
            "cooldowns": runtime.get("cooldowns") or {}, "heartbeat_at": runtime.get("heartbeat_at"),
            "last_result": runtime.get("last_result"), "sections": sections}


def _invoke_structured(prompt: str, route: Route, schema_path: Path, output_path: Path, stdout_path: Path, stderr_path: Path) -> tuple[int, Mapping[str, Any] | None, str]:
    cmd = build_codex_command(route, schema_path, output_path, Path("/root"))
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.run(cmd, input=prompt, text=True, stdout=stdout, stderr=stderr, check=False, env=os.environ.copy())
    error_text = _tail_text(stderr_path) + "\n" + _tail_text(stdout_path)
    if proc.returncode != 0: return proc.returncode, None, error_text
    if not output_path.exists(): return 1, None, "Codex completed without structured result"
    try: return 0, json.loads(output_path.read_text(encoding="utf-8")), error_text
    except json.JSONDecodeError as exc: return 1, None, f"invalid structured result: {exc}"


def _record_runtime_failure(runtime: dict[str, Any], route: Route, detail: str, observed: datetime, *, task_id: str | None = None, limited: bool = False) -> None:
    retry_at = limit_retry_at(detail, observed) if limited else observed + timedelta(minutes=2)
    runtime.setdefault("cooldowns", {})[route.model] = retry_at.isoformat()
    runtime["status"] = "WAITING_MODEL_AVAILABILITY" if limited else "ERROR"
    runtime["last_result"] = {"task_id": task_id, "status": "MODEL_COOLDOWN" if limited else "MODEL_RUNTIME_COOLDOWN",
                              "model": route.model, "reasoning": route.reasoning, "retry_at": retry_at.isoformat(), "summary": detail[-2000:], "evidence": []}
    runtime["heartbeat_at"] = observed.isoformat(); runtime["updated_at"] = observed.isoformat()


def _attempt_paths(runtime: dict[str, Any], runtime_root: Path, stem: str) -> tuple[Path, Path, Path]:
    runtime["attempt_seq"] = int(runtime.get("attempt_seq") or 0) + 1
    attempts = runtime_root / "attempts"; attempts.mkdir(parents=True, exist_ok=True)
    base = f"{runtime['attempt_seq']:04d}-{stem}"
    return attempts / f"{base}.result.json", attempts / f"{base}.stdout.log", attempts / f"{base}.stderr.log"


def run_production(project_root: Path, *, runtime_root: Path | None = None) -> int:
    runtime_root = runtime_root or _runtime_root(); runtime_root.mkdir(parents=True, exist_ok=True)
    task_schema = runtime_root / "result-schema.json"; section_schema = runtime_root / "section-plan-schema.json"
    task_schema.write_text(json.dumps(result_schema(), sort_keys=True) + "\n", encoding="utf-8")
    section_schema.write_text(json.dumps(section_plan_schema(), sort_keys=True) + "\n", encoding="utf-8")
    lock = RunLock(runtime_root / "run.lock"); lock.acquire()
    try:
        runtime = load_runtime_state(runtime_root / "runtime.json"); runtime["status"] = "RUNNING"; runtime["heartbeat_at"] = datetime.now(timezone.utc).isoformat(); save_runtime_state(runtime_root / "runtime.json", runtime)
        catalog = discover_catalog()
        while True:
            sync_project_metadata(project_root); production = load_project_production(project_root)
            section_id = production.get("current_section")
            if not section_id:
                runtime.update({"status": "COMPLETE", "active_model": None, "active_reasoning": None, "heartbeat_at": datetime.now(timezone.utc).isoformat()}); save_runtime_state(runtime_root / "runtime.json", runtime); return 0
            section = _section_record(production, str(section_id)); task = next_production_task(production); now = datetime.now(timezone.utc)
            if task is not None and _section_for_task(production, task.id)["id"] == section_id:
                try: route = select_route(task.task_class, catalog, runtime.get("cooldowns", {}), now)
                except RuntimeError:
                    runtime.update({"status": "WAITING_MODEL_AVAILABILITY", "heartbeat_at": now.isoformat()}); save_runtime_state(runtime_root / "runtime.json", runtime); time.sleep(min(60.0, max(1.0, _earliest_cooldown_delay(runtime.get("cooldowns", {}), now)))); catalog = discover_catalog(); continue
                runtime.update({"status": "RUNNING", "active_model": route.model, "active_reasoning": route.reasoning, "heartbeat_at": now.isoformat()}); save_runtime_state(runtime_root / "runtime.json", runtime)
                out, stdout, stderr = _attempt_paths(runtime, runtime_root, f"{task.id}-{route.model}")
                rc, result, error = _invoke_structured(build_production_task_prompt(production, task), route, task_schema, out, stdout, stderr); observed = datetime.now(timezone.utc)
                if rc != 0:
                    _record_runtime_failure(runtime, route, error, observed, task_id=task.id, limited=bool(_LIMIT_RE.search(error))); save_runtime_state(runtime_root / "runtime.json", runtime); continue
                if result.get("task_id") != task.id: _record_runtime_failure(runtime, route, "agent result task_id mismatch", observed, task_id=task.id); save_runtime_state(runtime_root / "runtime.json", runtime); continue
                status = str(result.get("status")); evidence = list(result.get("evidence", [])); summary = str(result.get("summary", ""))
                runtime["last_result"] = {"task_id": task.id, "status": status, "summary": summary, "evidence": evidence, "model": route.model, "reasoning": route.reasoning}; runtime["heartbeat_at"] = observed.isoformat(); runtime["updated_at"] = observed.isoformat()
                if status in _COMPLETE_STATUSES: mark_project_task_complete(project_root, task.id, status, evidence); save_runtime_state(runtime_root / "runtime.json", runtime); continue
                if status == "CONTINUE": save_runtime_state(runtime_root / "runtime.json", runtime); continue
                if status in {"EXTERNAL_DEPENDENCY", "OWNER_DECISION"}: runtime["status"] = status; save_runtime_state(runtime_root / "runtime.json", runtime); return 2
                _record_runtime_failure(runtime, route, f"unsupported agent status: {status}", observed, task_id=task.id); save_runtime_state(runtime_root / "runtime.json", runtime); continue
            # No incomplete task in current section: Demo closes automatically after its explicit D01-050 closure task; later sections are audited/planned.
            if section_id == "demo01" and section["tasks"] and all(t.get("status") in _COMPLETE_STATUSES for t in section["tasks"]):
                lines=_production_markdown_path(project_root).read_text(encoding="utf-8").splitlines(); _replace_section_status(lines, "demo01", "COMPLETE"); _production_markdown_path(project_root).write_text("\n".join(lines)+"\n", encoding="utf-8"); sync_project_metadata(project_root); continue
            try: route = select_route("deep_memory", catalog, runtime.get("cooldowns", {}), now)
            except RuntimeError:
                runtime.update({"status": "WAITING_MODEL_AVAILABILITY", "heartbeat_at": now.isoformat()}); save_runtime_state(runtime_root / "runtime.json", runtime); time.sleep(min(60.0, max(1.0, _earliest_cooldown_delay(runtime.get("cooldowns", {}), now)))); catalog = discover_catalog(); continue
            runtime.update({"status": "RUNNING", "active_model": route.model, "active_reasoning": route.reasoning, "heartbeat_at": now.isoformat()}); save_runtime_state(runtime_root / "runtime.json", runtime)
            out, stdout, stderr = _attempt_paths(runtime, runtime_root, f"PLAN-{section_id}-{route.model}")
            rc, plan, error = _invoke_structured(build_section_prompt(production, section, audit=bool(section["tasks"])), route, section_schema, out, stdout, stderr); observed=datetime.now(timezone.utc)
            if rc != 0: _record_runtime_failure(runtime, route, error, observed, limited=bool(_LIMIT_RE.search(error))); save_runtime_state(runtime_root / "runtime.json", runtime); continue
            try: apply_section_plan_to_project(project_root, str(section_id), plan or {})
            except (ValueError, TypeError, KeyError) as exc: _record_runtime_failure(runtime, route, f"invalid section plan: {exc}", observed); save_runtime_state(runtime_root / "runtime.json", runtime); continue
            runtime["last_result"] = {"task_id": None, "status": "SECTION_REFRESH", "summary": str((plan or {}).get("summary", "")), "evidence": list((plan or {}).get("evidence", [])), "model": route.model, "reasoning": route.reasoning}; runtime["heartbeat_at"] = observed.isoformat(); save_runtime_state(runtime_root / "runtime.json", runtime)
    finally:
        lock.release()


def start_production(project_root: Path) -> int:
    sync_project_metadata(project_root); production = load_project_production(project_root); unit = _unit_name(production["run_id"])
    if _service_active(unit): print(json.dumps({"unit": unit, "status": "ALREADY_RUNNING"}, sort_keys=True)); return 0
    entrypoint=os.environ.get("BIELLA_CODEX_ENTRYPOINT", "/usr/local/bin/biella-codex")
    cmd=["systemd-run", f"--unit={unit}", "--collect", "--property=Type=exec", "--property=Restart=no", f"--setenv=BIELLA_GAMES_PROJECT_ROOT={project_root.resolve()}", entrypoint, "feed", "run"]
    proc=subprocess.run(cmd,text=True,capture_output=True,check=False)
    if proc.returncode != 0: print(proc.stderr or proc.stdout,file=sys.stderr,end=""); return proc.returncode
    print(json.dumps({"unit":unit,"status":"STARTED"},sort_keys=True)); return 0


def stop_production(project_root: Path) -> int:
    production=load_project_production(project_root); unit=_unit_name(production["run_id"]); rc=subprocess.run(["systemctl","stop",unit],check=False).returncode
    runtime=load_runtime_state(_runtime_root()/"runtime.json"); runtime.update({"status":"STOPPED","active_model":None,"active_reasoning":None,"heartbeat_at":datetime.now(timezone.utc).isoformat()}); save_runtime_state(_runtime_root()/"runtime.json",runtime); return rc


def _parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(prog="biella-codex feed"); sub=parser.add_subparsers(dest="command",required=True)
    for name in ("sync","run","start","status","stop"): sub.add_parser(name)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    os.umask(0o077); args=_parser().parse_args(argv); project_root=_project_root()
    if args.command=="sync": sync_project_metadata(project_root); print(json.dumps(production_status_payload(project_root),sort_keys=True)); return 0
    if args.command=="run": return run_production(project_root)
    if args.command=="start": return start_production(project_root)
    if args.command=="status": print(json.dumps(production_status_payload(project_root),sort_keys=True)); return 0
    if args.command=="stop": return stop_production(project_root)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
