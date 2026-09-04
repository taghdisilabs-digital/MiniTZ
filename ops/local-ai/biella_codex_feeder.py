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


@dataclass(frozen=True)
class QueueSpec:
    run_id: str
    goal: str
    project_root: Path
    tasks: tuple[Task, ...]
    source_path: Path


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
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
        "--search",
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


def load_queue(path: Path) -> QueueSpec:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported queue schema")
    raw_tasks = data.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("queue requires tasks")
    tasks: list[Task] = []
    seen: set[str] = set()
    for item in raw_tasks:
        task = Task(str(item["id"]), str(item["class"]), str(item["title"]))
        if task.id in seen:
            raise ValueError(f"duplicate task id: {task.id}")
        if task.task_class not in _ROUTE_PROFILES:
            raise ValueError(f"unknown task class: {task.task_class}")
        seen.add(task.id)
        tasks.append(task)
    return QueueSpec(
        run_id=str(data["run_id"]),
        goal=str(data["goal"]),
        project_root=Path(str(data["project_root"])),
        tasks=tuple(tasks),
        source_path=path.resolve(),
    )


def initial_state(queue: QueueSpec) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": queue.run_id,
        "queue_path": str(queue.source_path),
        "status": "READY",
        "current_task": queue.tasks[0].id if queue.tasks else None,
        "completed": [],
        "cooldowns": {},
        "last_result": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_state(path: Path, state: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_state(path: Path, queue: QueueSpec) -> dict[str, Any]:
    if not path.exists():
        return initial_state(queue)
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("run_id") != queue.run_id:
        raise ValueError("state run_id does not match queue")
    known = {task.id for task in queue.tasks}
    completed = state.get("completed", [])
    if not isinstance(completed, list) or any(item not in known for item in completed):
        raise ValueError("state contains unknown completed task")
    return state


def next_task(queue: QueueSpec, state: Mapping[str, Any]) -> Task | None:
    completed = set(state.get("completed", []))
    for task in queue.tasks:
        if task.id not in completed:
            return task
    return None


def mark_complete(state: dict[str, Any], task_id: str, status: str, model: str, reasoning: str) -> None:
    completed = state.setdefault("completed", [])
    if task_id not in completed:
        completed.append(task_id)
    state["last_result"] = {"task_id": task_id, "status": status, "model": model, "reasoning": reasoning}
    state["current_task"] = None
    state["updated_at"] = datetime.now(timezone.utc).isoformat()


def record_limit_failure(
    state: dict[str, Any],
    task: Task,
    route: Route,
    error_text: str,
    observed_at: datetime,
) -> None:
    retry_at = limit_retry_at(error_text, observed_at)
    state.setdefault("cooldowns", {})[route.model] = retry_at.isoformat()
    state["current_task"] = task.id
    state["last_result"] = {
        "task_id": task.id,
        "status": "MODEL_COOLDOWN",
        "model": route.model,
        "reasoning": route.reasoning,
        "retry_at": retry_at.isoformat(),
    }
    state["updated_at"] = observed_at.isoformat()


def build_task_prompt(queue: QueueSpec, task: Task, state: Mapping[str, Any]) -> str:
    previous = state.get("last_result")
    previous_text = "none"
    if isinstance(previous, dict) and previous.get("task_id") == task.id:
        previous_text = json.dumps(previous, sort_keys=True, separators=(",", ":"))
    return (
        "Biella production task. Work autonomously from /root and follow current AGENTS/current GitHub/Drive/runtime authority.\n"
        f"RUN: {queue.run_id}\nGOAL: {queue.goal}\n"
        f"TASK: {task.id} [{task.task_class}] {task.title}\n"
        f"PROJECT: {queue.project_root}\n"
        f"PREVIOUS_ATTEMPT: {previous_text}\n"
        "Preserve valid newer work; verify before redoing. Internal tool/build/provider failures are repair/routing work. "
        "Codex may use configured local Qwen, APIs, GPU, Unreal, GitHub, Drive and production tools when useful. "
        "Do not manage Codex account quota or usage resets. Creation output must be real/editable and visually inspectable when applicable. "
        "Finish this task or return only a genuine external dependency/owner decision. Keep final summary compact."
    )


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


def write_demo01_queue(path: Path) -> Path:
    tasks = [
        {"id": f"D01-{index:03d}", "class": task_class, "title": title}
        for index, (task_class, title) in enumerate(_DEMO01_TASKS, start=1)
    ]
    payload = {
        "schema_version": 1,
        "run_id": "demo01-50",
        "goal": "Finish the first real playable packaged Biella Games Demo 01 vertical slice",
        "project_root": "/root/biella/repos/biella-games",
        "tasks": tasks,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return path


def apply_agent_result(
    state: dict[str, Any],
    task: Task,
    route: Route,
    result: Mapping[str, Any],
    observed_at: datetime,
) -> str:
    if result.get("task_id") != task.id:
        raise ValueError("agent result task_id mismatch")
    status = str(result.get("status"))
    summary = str(result.get("summary", ""))
    evidence = list(result.get("evidence", []))
    if status in {"COMPLETE", "COMPLETE_ALREADY"}:
        mark_complete(state, task.id, status, route.model, route.reasoning)
        state["last_result"].update({"summary": summary, "evidence": evidence})
        state["status"] = "RUNNING"
        state["updated_at"] = observed_at.isoformat()
        return "ADVANCE"
    checkpoint = {
        "task_id": task.id,
        "status": status,
        "model": route.model,
        "reasoning": route.reasoning,
        "summary": summary,
        "evidence": evidence,
    }
    state["current_task"] = task.id
    state["last_result"] = checkpoint
    state["updated_at"] = observed_at.isoformat()
    if status == "CONTINUE":
        state["status"] = "RUNNING"
        return "RETRY_TASK"
    if status in {"EXTERNAL_DEPENDENCY", "OWNER_DECISION"}:
        state["status"] = status
        return "PAUSE"
    raise ValueError(f"unsupported agent status: {status}")



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


def _record_runtime_failure(
    state: dict[str, Any], task: Task, route: Route, observed_at: datetime, detail: str
) -> None:
    until = observed_at + timedelta(minutes=2)
    state.setdefault("cooldowns", {})[route.model] = until.isoformat()
    state["current_task"] = task.id
    state["last_result"] = {
        "task_id": task.id,
        "status": "MODEL_RUNTIME_COOLDOWN",
        "model": route.model,
        "reasoning": route.reasoning,
        "retry_at": until.isoformat(),
        "summary": detail[-2000:],
        "evidence": [],
    }
    state["updated_at"] = observed_at.isoformat()


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


def _invoke_task(
    queue: QueueSpec,
    task: Task,
    state: dict[str, Any],
    route: Route,
    runtime_root: Path,
    schema_path: Path,
) -> tuple[int, Mapping[str, Any] | None, str]:
    seq = int(state.get("attempt_seq", 0)) + 1
    state["attempt_seq"] = seq
    attempts = runtime_root / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    stem = f"{seq:04d}-{task.id}-{route.model}"
    stdout_path = attempts / f"{stem}.stdout.log"
    stderr_path = attempts / f"{stem}.stderr.log"
    output_path = attempts / f"{stem}.result.json"
    prompt = build_task_prompt(queue, task, state)
    cmd = build_codex_command(route, schema_path, output_path, Path("/root"))
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            stdout=stdout,
            stderr=stderr,
            check=False,
            env=os.environ.copy(),
        )
    error_text = _tail_text(stderr_path) + "\n" + _tail_text(stdout_path)
    if proc.returncode != 0:
        return proc.returncode, None, error_text
    if not output_path.exists():
        return 1, None, "Codex completed without structured result"
    try:
        result = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return 1, None, f"invalid structured result: {exc}"
    return 0, result, error_text


def run_queue(queue_path: Path, *, runtime_root: Path | None = None) -> int:
    queue = load_queue(queue_path)
    state_path = queue.source_path.parent / "state.json"
    runtime_root = runtime_root or Path("/mnt/biella-extra/biella-runtime/codex-feeder") / queue.run_id
    runtime_root.mkdir(parents=True, exist_ok=True)
    schema_path = runtime_root / "result-schema.json"
    schema_path.write_text(json.dumps(result_schema(), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    lock = RunLock(runtime_root / "run.lock")
    lock.acquire()
    try:
        state = load_state(state_path, queue)
        state["status"] = "RUNNING"
        save_state(state_path, state)
        catalog = discover_catalog()
        while True:
            task = next_task(queue, state)
            if task is None:
                state["status"] = "COMPLETE"
                state["current_task"] = None
                state["updated_at"] = datetime.now(timezone.utc).isoformat()
                save_state(state_path, state)
                return 0
            state["current_task"] = task.id
            now = datetime.now(timezone.utc)
            try:
                route = select_route(task.task_class, catalog, state.get("cooldowns", {}), now)
            except RuntimeError:
                state["status"] = "WAITING_MODEL_AVAILABILITY"
                state["updated_at"] = now.isoformat()
                save_state(state_path, state)
                time.sleep(min(60.0, max(1.0, _earliest_cooldown_delay(state.get("cooldowns", {}), now))))
                catalog = discover_catalog()
                continue
            state["active_model"] = route.model
            state["active_reasoning"] = route.reasoning
            state["updated_at"] = now.isoformat()
            save_state(state_path, state)
            returncode, result, error_text = _invoke_task(queue, task, state, route, runtime_root, schema_path)
            observed = datetime.now(timezone.utc)
            if returncode != 0:
                if _LIMIT_RE.search(error_text):
                    record_limit_failure(state, task, route, error_text, observed)
                else:
                    _record_runtime_failure(state, task, route, observed, error_text)
                save_state(state_path, state)
                continue
            try:
                action = apply_agent_result(state, task, route, result or {}, observed)
            except (ValueError, TypeError) as exc:
                _record_runtime_failure(state, task, route, observed, f"invalid agent result: {exc}")
                save_state(state_path, state)
                continue
            if action == "ADVANCE":
                next_item = next_task(queue, state)
                state["current_task"] = next_item.id if next_item else None
                save_state(state_path, state)
                continue
            save_state(state_path, state)
            if action == "PAUSE":
                return 2
    finally:
        lock.release()



def status_payload(queue_path: Path) -> dict[str, Any]:
    queue = load_queue(queue_path)
    state = load_state(queue.source_path.parent / "state.json", queue)
    current = next_task(queue, state)
    return {
        "run_id": queue.run_id,
        "status": state.get("status", "READY"),
        "current_task": state.get("current_task") or (current.id if current else None),
        "completed": len(state.get("completed", [])),
        "total": len(queue.tasks),
        "active_model": state.get("active_model"),
        "active_reasoning": state.get("active_reasoning"),
        "cooldowns": state.get("cooldowns", {}),
        "last_result": state.get("last_result"),
    }


def _unit_name(run_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id).strip("-.") or "run"
    return f"biella-codex-feed-{safe}"


def start_detached(queue_path: Path) -> int:
    queue = load_queue(queue_path)
    unit = _unit_name(queue.run_id)
    active = subprocess.run(
        ["systemctl", "is-active", "--quiet", unit],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
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
        entrypoint,
        "feed",
        "run",
        "--queue",
        str(queue.source_path),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr, end="")
        return proc.returncode
    print(json.dumps({"unit": unit, "status": "STARTED"}, sort_keys=True))
    return 0


def stop_detached(queue_path: Path) -> int:
    queue = load_queue(queue_path)
    unit = _unit_name(queue.run_id)
    proc = subprocess.run(["systemctl", "stop", unit], check=False)
    return proc.returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biella-codex feed")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-demo01")
    init.add_argument("--queue", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--queue", type=Path, required=True)
    start = sub.add_parser("start")
    start.add_argument("--queue", type=Path, required=True)
    status = sub.add_parser("status")
    status.add_argument("--queue", type=Path, required=True)
    stop = sub.add_parser("stop")
    stop.add_argument("--queue", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    os.umask(0o077)
    args = _parser().parse_args(argv)
    if args.command == "init-demo01":
        write_demo01_queue(args.queue)
        print(json.dumps({"queue": str(args.queue.resolve()), "tasks": 50}, sort_keys=True))
        return 0
    if args.command == "run":
        return run_queue(args.queue)
    if args.command == "start":
        return start_detached(args.queue)
    if args.command == "status":
        print(json.dumps(status_payload(args.queue), sort_keys=True))
        return 0
    if args.command == "stop":
        return stop_detached(args.queue)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
