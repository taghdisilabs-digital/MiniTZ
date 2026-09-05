from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import biella_codex_routing as routing
import biella_production_evidence as evidence
import biella_production_state as state
import biella_task_packet as packets

UNIT_NAME = "biella-codex-production"
_RUNTIME_KEYS = {
    "status", "project", "task_id", "attempt", "pid", "child_pid",
    "active_model", "active_reasoning", "cooldowns", "last_result",
    "heartbeat_at", "updated_at",
}


class AlreadyRunning(RuntimeError):
    pass


class ProductionLock:
    def __init__(self, path: Path):
        self.path = Path(path); self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close(); raise AlreadyRunning(str(self.path)) from exc
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close(); self._handle = None


def initial_runtime() -> dict[str, Any]:
    return {
        "status": "STOPPED", "project": None, "task_id": None, "attempt": 0,
        "pid": None, "child_pid": None, "active_model": None,
        "active_reasoning": None, "cooldowns": {}, "last_result": None,
        "heartbeat_at": None, "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_runtime(path: Path, runtime: Mapping[str, Any]) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: runtime.get(key) for key in _RUNTIME_KEYS}
    payload["cooldowns"] = dict(payload.get("cooldowns") or {})
    payload["attempt"] = int(payload.get("attempt") or 0)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_runtime(path: Path) -> dict[str, Any]:
    if not Path(path).exists():
        return initial_runtime()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    result = initial_runtime()
    for key in _RUNTIME_KEYS:
        if key in raw:
            result[key] = raw[key]
    return result


def _beat(runtime_path: Path, telemetry: dict[str, Any], *, at: datetime | None = None) -> datetime:
    observed = at or datetime.now(timezone.utc)
    telemetry["heartbeat_at"] = observed.isoformat()
    telemetry["updated_at"] = observed.isoformat()
    save_runtime(runtime_path, telemetry)
    return observed


def _tail(path: Path, maximum_bytes: int = 65536) -> str:
    if not path.exists():
        return ""
    return path.read_bytes()[-maximum_bytes:].decode("utf-8", errors="replace")


def invoke_structured(prompt: str, route: routing.Route, schema_path: Path, output_path: Path,
                      stdout_path: Path, stderr_path: Path, runtime_path: Path,
                      telemetry: dict[str, Any], *, heartbeat_interval: float = 30.0,
                      on_heartbeat: Callable[[datetime], None] | None = None) -> tuple[int, str]:
    cmd = routing.build_codex_command(route, schema_path, output_path, Path("/root"))
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True, stdout=stdout, stderr=stderr, env=os.environ.copy())
        telemetry["child_pid"] = proc.pid
        _beat(runtime_path, telemetry)
        assert proc.stdin is not None
        proc.stdin.write(prompt); proc.stdin.close()
        next_beat = time.monotonic()
        while proc.poll() is None:
            now_mono = time.monotonic()
            if now_mono >= next_beat:
                observed = _beat(runtime_path, telemetry)
                if on_heartbeat:
                    on_heartbeat(observed)
                next_beat = now_mono + heartbeat_interval
            time.sleep(min(0.05, max(0.005, heartbeat_interval / 4)))
        rc = int(proc.returncode or 0)
    telemetry["child_pid"] = None
    observed = _beat(runtime_path, telemetry)
    if on_heartbeat:
        on_heartbeat(observed)
    return rc, _tail(stderr_path) + "\n" + _tail(stdout_path)


def _attempt_paths(runtime_root: Path, telemetry: dict[str, Any], stem: str) -> tuple[Path, Path, Path]:
    telemetry["attempt"] = int(telemetry.get("attempt") or 0) + 1
    attempts = runtime_root / "attempts"; attempts.mkdir(parents=True, exist_ok=True)
    base = f"{telemetry['attempt']:04d}-{stem}"
    return attempts / f"{base}.result.json", attempts / f"{base}.stdout.log", attempts / f"{base}.stderr.log"


def _set_failure(telemetry: dict[str, Any], route: routing.Route, detail: str, task_id: str) -> None:
    observed = datetime.now(timezone.utc)
    limited = routing.is_limit_error(detail)
    retry_at = routing.limit_retry_at(detail, observed) if limited else observed + timedelta(minutes=2)
    telemetry.setdefault("cooldowns", {})[route.model] = retry_at.isoformat()
    telemetry["status"] = "WAITING_MODEL_AVAILABILITY" if limited else "ERROR"
    telemetry["last_result"] = {"task_id": task_id, "status": "MODEL_COOLDOWN" if limited else "MODEL_RUNTIME_COOLDOWN", "summary": detail[-2000:], "evidence": [], "model": route.model, "reasoning": route.reasoning, "retry_at": retry_at.isoformat()}


def service_active() -> bool:
    return subprocess.run(["systemctl", "is-active", "--quiet", UNIT_NAME], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def production_status(repo_root: Path, project_root: Path, runtime_path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    production = state.load_project_production(project_root)
    telemetry = load_runtime(runtime_path)
    now = now or datetime.now(timezone.utc)
    if not service_active():
        liveness = "STOPPED"
    else:
        heartbeat = None
        raw = telemetry.get("heartbeat_at")
        if isinstance(raw, str) and raw:
            try:
                heartbeat = datetime.fromisoformat(raw)
                if heartbeat.tzinfo is None: heartbeat = heartbeat.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if heartbeat is None or (now - heartbeat).total_seconds() > 90:
            liveness = "STALE"
        elif telemetry.get("status") in {"WAITING", "WAITING_MODEL_AVAILABILITY", "EXTERNAL_DEPENDENCY", "OWNER_DECISION"}:
            liveness = "WAITING"
        elif telemetry.get("status") in {"ERROR", "FAILED"}:
            liveness = "ERROR"
        else:
            liveness = "ACTIVE"
    sections = []
    for section in production.sections:
        sections.append({"id": section.id, "status": section.status, "completed": sum(t.status in {"COMPLETE", "COMPLETE_ALREADY"} for t in section.tasks), "total": len(section.tasks)})
    return {
        "run_id": "biella-production", "status": liveness,
        "current_section": production.current_section, "current_task": production.current_task,
        "completed": state.completed_count(production), "total": sum(len(s.tasks) for s in production.sections),
        "active_model": telemetry.get("active_model"), "active_reasoning": telemetry.get("active_reasoning"),
        "cooldowns": telemetry.get("cooldowns") or {}, "heartbeat_at": telemetry.get("heartbeat_at"),
        "last_result": telemetry.get("last_result"), "sections": sections,
    }


def _first_incomplete_section(production: state.ProductionState) -> state.SectionRecord | None:
    for section in production.sections:
        if section.status not in {"COMPLETE", "COMPLETE_ALREADY"}:
            return section
    return None


def run_production(repo_root: Path, project_root: Path, runtime_root: Path, *, heartbeat_interval: float = 30.0) -> int:
    repo_root = Path(repo_root); project_root = Path(project_root); runtime_root = Path(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_path = runtime_root / "runtime.json"
    schema_path = runtime_root / "result-schema.json"
    section_schema_path = runtime_root / "section-plan-schema.json"
    schema_path.write_text(json.dumps(evidence.result_schema(), sort_keys=True) + "\n", encoding="utf-8")
    section_schema_path.write_text(json.dumps(packets.section_plan_schema(), sort_keys=True) + "\n", encoding="utf-8")
    lock = ProductionLock(runtime_root / "run.lock"); lock.acquire()
    try:
        telemetry = load_runtime(runtime_path)
        telemetry.update({"status": "RUNNING", "project": "biella-games", "pid": os.getpid()})
        _beat(runtime_path, telemetry)
        catalog = routing.discover_catalog()
        while True:
            production = state.sync_project_metadata(project_root)
            task = state.resolve_current_task(repo_root, project_root)
            if task is None:
                production = state.load_project_production(project_root)
                section = _first_incomplete_section(production)
                if section is None:
                    telemetry.update({"status": "COMPLETE", "task_id": None, "child_pid": None, "active_model": None, "active_reasoning": None})
                    _beat(runtime_path, telemetry); return 0
                if section.id == "demo01" and section.tasks and all(t.status in {"COMPLETE", "COMPLETE_ALREADY"} for t in section.tasks):
                    state.mark_section_status(project_root, section.id, "COMPLETE")
                    continue
                now = datetime.now(timezone.utc)
                try:
                    route = routing.select_route("deep_memory", catalog, telemetry.get("cooldowns", {}), now)
                except RuntimeError:
                    telemetry.update({"status": "WAITING_MODEL_AVAILABILITY", "task_id": f"PLAN:{section.id}", "active_model": None, "active_reasoning": None})
                    _beat(runtime_path, telemetry); time.sleep(min(60.0, max(1.0, routing.earliest_cooldown_delay(telemetry.get("cooldowns", {}), now)))); catalog = routing.discover_catalog(); continue
                telemetry.update({"status": "RUNNING", "task_id": f"PLAN:{section.id}", "active_model": route.model, "active_reasoning": route.reasoning})
                _beat(runtime_path, telemetry)
                output, stdout, stderr = _attempt_paths(runtime_root, telemetry, f"PLAN-{section.id}-{route.model}")
                rc, error_text = invoke_structured(packets.compile_section_packet(production, section, audit=bool(section.tasks)), route, section_schema_path, output, stdout, stderr, runtime_path, telemetry, heartbeat_interval=heartbeat_interval)
                if rc != 0:
                    _set_failure(telemetry, route, error_text, f"PLAN:{section.id}"); _beat(runtime_path, telemetry); continue
                try:
                    plan = json.loads(output.read_text(encoding="utf-8"))
                    state.apply_section_plan(repo_root, project_root, section.id, plan)
                except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
                    _set_failure(telemetry, route, f"invalid section plan: {exc}", f"PLAN:{section.id}"); _beat(runtime_path, telemetry); continue
                telemetry["last_result"] = {"task_id": None, "status": "SECTION_REFRESH", "summary": str(plan.get("summary", "")), "evidence": list(plan.get("evidence", [])), "model": route.model, "reasoning": route.reasoning}
                _beat(runtime_path, telemetry); continue
            now = datetime.now(timezone.utc)
            try:
                route = routing.select_route(task.task_class, catalog, telemetry.get("cooldowns", {}), now)
            except RuntimeError:
                telemetry.update({"status": "WAITING_MODEL_AVAILABILITY", "task_id": task.id, "active_model": None, "active_reasoning": None})
                _beat(runtime_path, telemetry)
                time.sleep(min(60.0, max(1.0, routing.earliest_cooldown_delay(telemetry.get("cooldowns", {}), now))))
                catalog = routing.discover_catalog(); continue
            telemetry.update({"status": "RUNNING", "task_id": task.id, "active_model": route.model, "active_reasoning": route.reasoning})
            state.sync_current_state(repo_root, production, task, state="IN_PROGRESS", execution_started=True)
            _beat(runtime_path, telemetry)
            output, stdout, stderr = _attempt_paths(runtime_root, telemetry, f"{task.id}-{route.model}")
            prompt = packets.compile_task_packet(repo_root, production, task)
            rc, error_text = invoke_structured(prompt, route, schema_path, output, stdout, stderr, runtime_path, telemetry, heartbeat_interval=heartbeat_interval)
            if rc != 0:
                _set_failure(telemetry, route, error_text, task.id); _beat(runtime_path, telemetry); continue
            try:
                result = evidence.parse_result(output, task.id)
            except ValueError as exc:
                _set_failure(telemetry, route, str(exc), task.id); _beat(runtime_path, telemetry); continue
            telemetry["last_result"] = {
                "task_id": result.task_id, "status": result.status, "summary": result.summary,
                "evidence": list(result.evidence), "model": route.model, "reasoning": route.reasoning,
            }
            evidence.apply_result(repo_root, project_root, result, route)
            _beat(runtime_path, telemetry)
            if result.status in {"COMPLETE", "COMPLETE_ALREADY", "CONTINUE"}:
                continue
            telemetry["status"] = result.status
            telemetry["active_model"] = None; telemetry["active_reasoning"] = None
            _beat(runtime_path, telemetry); return 2
    finally:
        lock.release()


def default_repo_root() -> Path:
    return Path(os.environ.get("BIELLA_REPO_ROOT", "/root/biella/repos/biella-engine"))


def default_project_root(repo_root: Path | None = None) -> Path:
    repo = repo_root or default_repo_root()
    return Path(os.environ.get("BIELLA_PROJECT_ROOT", str(repo / "projects/biella-games")))


def default_runtime_root() -> Path:
    return Path(os.environ.get("BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT", "/mnt/biella-extra/biella-runtime/codex-production"))


def start_production(repo_root: Path, project_root: Path, runtime_root: Path) -> int:
    if service_active():
        print(json.dumps({"unit": UNIT_NAME, "status": "ALREADY_RUNNING"}, sort_keys=True)); return 0
    state.resolve_current_task(repo_root, project_root)
    entrypoint = os.environ.get("BIELLA_CODEX_ENTRYPOINT", "/usr/local/bin/biella-codex")
    cmd = [
        "systemd-run", f"--unit={UNIT_NAME}", "--collect", "--property=Type=exec", "--property=Restart=no",
        f"--setenv=BIELLA_REPO_ROOT={Path(repo_root).resolve()}",
        f"--setenv=BIELLA_PROJECT_ROOT={Path(project_root).resolve()}",
        f"--setenv=BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT={Path(runtime_root).resolve()}",
        entrypoint, "production", "run",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr, end=""); return proc.returncode
    print(json.dumps({"unit": UNIT_NAME, "status": "STARTED"}, sort_keys=True)); return 0


def stop_production(runtime_root: Path) -> int:
    rc = subprocess.run(["systemctl", "stop", UNIT_NAME], check=False).returncode
    runtime_path = Path(runtime_root) / "runtime.json"
    telemetry = load_runtime(runtime_path)
    telemetry.update({"status": "STOPPED", "pid": None, "child_pid": None, "active_model": None, "active_reasoning": None})
    _beat(runtime_path, telemetry)
    return rc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biella-codex production")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sync", "run", "start", "status", "stop"):
        sub.add_parser(name)
    return parser


def main(argv=None) -> int:
    os.umask(0o077)
    args = _parser().parse_args(argv)
    repo_root = default_repo_root(); project_root = default_project_root(repo_root); runtime_root = default_runtime_root()
    if args.command == "run":
        return run_production(repo_root, project_root, runtime_root)
    if args.command == "start":
        return start_production(repo_root, project_root, runtime_root)
    if args.command == "status":
        print(json.dumps(production_status(repo_root, project_root, runtime_root / "runtime.json"), sort_keys=True)); return 0
    if args.command == "sync":
        state.resolve_current_task(repo_root, project_root)
        print(json.dumps(production_status(repo_root, project_root, runtime_root / "runtime.json"), sort_keys=True)); return 0
    if args.command == "stop":
        return stop_production(runtime_root)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
