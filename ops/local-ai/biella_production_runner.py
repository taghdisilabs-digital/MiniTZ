#!/usr/bin/env python3
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
    "heartbeat_at", "updated_at", "task_session_id", "session_task_id",
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
        "task_session_id": None, "session_task_id": None,
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


def _extract_codex_session_id(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("thread_id"), str) and item.get("thread_id"):
            return str(item["thread_id"])
        payload = item.get("payload")
        if isinstance(payload, dict):
            for key in ("thread_id", "session_id"):
                if isinstance(payload.get(key), str) and payload.get(key):
                    return str(payload[key])
    return None


def _resume_session_for(telemetry: Mapping[str, Any], task_id: str) -> str | None:
    if telemetry.get("session_task_id") != task_id:
        return None
    raw = telemetry.get("task_session_id")
    return str(raw) if isinstance(raw, str) and raw else None


def _clear_task_session(telemetry: dict[str, Any]) -> None:
    telemetry["task_session_id"] = None
    telemetry["session_task_id"] = None


def _task_capsule_path(runtime_root: Path, task_id: str) -> Path:
    safe_id = str(task_id).replace("/", "_")
    return Path(runtime_root) / "task-memory" / f"{safe_id}.json"


def _project_dirty_paths(repo_root: Path, project_root: Path) -> list[str]:
    repo_root = Path(repo_root).resolve(); project_root = Path(project_root).resolve()
    try:
        prefix = project_root.relative_to(repo_root).as_posix().rstrip("/") + "/"
    except ValueError:
        return []
    proc = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return []
    result: list[str] = []
    for raw in proc.stdout.splitlines():
        if len(raw) < 4:
            continue
        name = raw[3:].strip('"')
        if " -> " in name:
            name = name.split(" -> ", 1)[1].strip('"')
        if name.startswith(prefix):
            result.append(name[len(prefix):])
    return sorted(dict.fromkeys(result))


def _write_task_capsule(repo_root: Path, project_root: Path, runtime_root: Path, task: state.TaskRecord, telemetry: Mapping[str, Any]) -> Path:
    path = _task_capsule_path(runtime_root, task.id)
    existing: Mapping[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("task_id") == task.id:
                existing = loaded
        except (OSError, json.JSONDecodeError):
            pass
    previous = telemetry.get("last_result") if isinstance(telemetry.get("last_result"), dict) else {}
    if previous.get("task_id") != task.id:
        previous = existing
    capsule = packets.build_task_memory_capsule(
        task, project_root, session_id=_resume_session_for(telemetry, task.id),
        summary=str(previous.get("summary", "")), evidence=previous.get("evidence", ()),
        dirty_paths=_project_dirty_paths(repo_root, project_root),
    )
    capsule["last_status"] = previous.get("status")
    capsule["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(capsule, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def _task_prompt(repo_root: Path, production: state.ProductionState, task: state.TaskRecord, telemetry: Mapping[str, Any], capsule_path: Path) -> str:
    if _resume_session_for(telemetry, task.id):
        return packets.compile_resume_packet(task, capsule_path)
    initial = packets.compile_task_packet(repo_root, production, task)
    if capsule_path.exists():
        initial += f"\nTASK_MEMORY: {capsule_path}\nRead this bounded recovery capsule before redoing any existing work.\n"
    return initial


def _helper_allowed(task_id: str) -> bool:
    configured = {item.strip() for item in os.environ.get("BIELLA_CODEX_ONE_HELPER_TASKS", "").split(",") if item.strip()}
    return "*" in configured or task_id in configured


def invoke_structured(prompt: str, route: routing.Route, schema_path: Path, output_path: Path,
                      stdout_path: Path, stderr_path: Path, runtime_path: Path,
                      telemetry: dict[str, Any], *, heartbeat_interval: float = 30.0,
                      on_heartbeat: Callable[[datetime], None] | None = None,
                      cwd: Path | None = None, resume_session_id: str | None = None,
                      session_task_id: str | None = None, allow_helper: bool = False) -> tuple[int, str]:
    if resume_session_id:
        cmd = routing.build_codex_resume_command(route, schema_path, output_path, resume_session_id, allow_helper=True) if allow_helper else routing.build_codex_resume_command(route, schema_path, output_path, resume_session_id)
    else:
        cmd = routing.build_codex_command(route, schema_path, output_path, cwd or Path("/root"), allow_helper=True) if allow_helper else routing.build_codex_command(route, schema_path, output_path, cwd or Path("/root"))
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
    observed_session = resume_session_id or _extract_codex_session_id(stdout_path)
    if observed_session and session_task_id:
        telemetry["task_session_id"] = observed_session
        telemetry["session_task_id"] = session_task_id
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
    telemetry["status"] = "RECOVERING_MODEL" if limited else "RECOVERING_RUNTIME"
    telemetry["last_result"] = {"task_id": task_id, "status": "MODEL_RECOVERY" if limited else "RUNTIME_RECOVERY", "summary": detail[-2000:], "evidence": [], "model": route.model, "reasoning": route.reasoning, "retry_at": retry_at.isoformat()}


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


def _persist_until_success(repo_root: Path, task_id: str, runtime_path: Path, telemetry: dict[str, Any], *, retry_seconds: float = 5.0) -> dict[str, str]:
    previous = telemetry.get("last_result") if isinstance(telemetry.get("last_result"), dict) else {}
    while True:
        try:
            identity = evidence.persist_continuity(repo_root, task_id)
        except Exception as exc:
            telemetry["status"] = "RECOVERING_PERSISTENCE"
            telemetry["last_result"] = {
                "task_id": task_id, "status": "RECOVERING_PERSISTENCE",
                "summary": str(exc), "evidence": list(previous.get("evidence", [])),
            }
            _beat(runtime_path, telemetry)
            time.sleep(max(0.05, retry_seconds))
            continue
        derived = {"status": "SYNCED"}
        try:
            evidence.publish_derived_task_ledger(repo_root)
        except Exception as exc:
            derived = {"status": "PENDING_RETRY", "error": str(exc)}
        telemetry["status"] = "RUNNING"
        telemetry["last_result"] = {
            "task_id": task_id, "status": "RECOVERED_PERSISTENCE",
            "summary": "Canonical Git/Drive publication recovered.",
            "evidence": list(previous.get("evidence", [])), "continuity": identity,
            "derived_ledger": derived,
        }
        _beat(runtime_path, telemetry)
        return identity


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
        telemetry.update({"status": "RUNNING", "project": "biella-games", "pid": os.getpid(), "child_pid": None})
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
                    _persist_until_success(repo_root, f"SECTION-{section.id}", runtime_path, telemetry)
                    continue
                now = datetime.now(timezone.utc)
                try:
                    route = routing.select_route("deep_memory", catalog, telemetry.get("cooldowns", {}), now)
                except RuntimeError:
                    telemetry.update({"status": "RECOVERING_MODEL", "task_id": f"PLAN:{section.id}", "active_model": None, "active_reasoning": None})
                    _beat(runtime_path, telemetry); time.sleep(min(60.0, max(1.0, routing.earliest_cooldown_delay(telemetry.get("cooldowns", {}), now)))); catalog = routing.discover_catalog(); continue
                telemetry.update({"status": "RUNNING", "task_id": f"PLAN:{section.id}", "active_model": route.model, "active_reasoning": route.reasoning})
                _beat(runtime_path, telemetry)
                output, stdout, stderr = _attempt_paths(runtime_root, telemetry, f"PLAN-{section.id}-{route.model}")
                rc, error_text = invoke_structured(packets.compile_section_packet(production, section, audit=bool(section.tasks)), route, section_schema_path, output, stdout, stderr, runtime_path, telemetry, heartbeat_interval=heartbeat_interval, cwd=project_root, session_task_id=f"PLAN:{section.id}")
                if rc != 0:
                    _set_failure(telemetry, route, error_text, f"PLAN:{section.id}"); _beat(runtime_path, telemetry); continue
                try:
                    plan = json.loads(output.read_text(encoding="utf-8"))
                    state.apply_section_plan(repo_root, project_root, section.id, plan)
                    _persist_until_success(repo_root, f"PLAN-{section.id}", runtime_path, telemetry)
                except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
                    _set_failure(telemetry, route, f"invalid section plan: {exc}", f"PLAN:{section.id}"); _beat(runtime_path, telemetry); continue
                telemetry["last_result"] = {"task_id": None, "status": "SECTION_REFRESH", "summary": str(plan.get("summary", "")), "evidence": list(plan.get("evidence", [])), "model": route.model, "reasoning": route.reasoning}
                _beat(runtime_path, telemetry); continue
            now = datetime.now(timezone.utc)
            try:
                route = routing.select_route(task.task_class, catalog, telemetry.get("cooldowns", {}), now)
            except RuntimeError:
                telemetry.update({"status": "RECOVERING_MODEL", "task_id": task.id, "active_model": None, "active_reasoning": None})
                _beat(runtime_path, telemetry)
                time.sleep(min(60.0, max(1.0, routing.earliest_cooldown_delay(telemetry.get("cooldowns", {}), now))))
                catalog = routing.discover_catalog(); continue
            telemetry.update({"status": "RUNNING", "task_id": task.id, "active_model": route.model, "active_reasoning": route.reasoning})
            if evidence.continuity_changes(repo_root):
                unexpected = evidence.unexpected_dirty_paths(repo_root)
                if unexpected:
                    telemetry["last_result"] = {
                        "task_id": task.id, "status": "RECONCILE_DEFERRED",
                        "summary": "Continuity reconciliation deferred until current task output is committed.",
                        "evidence": sorted(unexpected),
                    }
                else:
                    _persist_until_success(repo_root, f"RECONCILE-{task.id}", runtime_path, telemetry)
            _beat(runtime_path, telemetry)
            output, stdout, stderr = _attempt_paths(runtime_root, telemetry, f"{task.id}-{route.model}")
            capsule_path = _write_task_capsule(repo_root, project_root, runtime_root, task, telemetry)
            prompt = _task_prompt(repo_root, production, task, telemetry, capsule_path)
            resume_session_id = _resume_session_for(telemetry, task.id)
            rc, error_text = invoke_structured(
                prompt, route, schema_path, output, stdout, stderr, runtime_path, telemetry,
                heartbeat_interval=heartbeat_interval, cwd=project_root,
                resume_session_id=resume_session_id, session_task_id=task.id,
                allow_helper=_helper_allowed(task.id),
            )
            if rc != 0:
                _set_failure(telemetry, route, error_text, task.id)
                _write_task_capsule(repo_root, project_root, runtime_root, task, telemetry)
                _beat(runtime_path, telemetry); continue
            try:
                result = evidence.parse_result(output, task.id)
            except ValueError as exc:
                _set_failure(telemetry, route, str(exc), task.id); _beat(runtime_path, telemetry); continue
            telemetry["last_result"] = {
                "task_id": result.task_id, "status": result.status, "summary": result.summary,
                "evidence": list(result.evidence), "model": route.model, "reasoning": route.reasoning,
            }
            _write_task_capsule(repo_root, project_root, runtime_root, task, telemetry)
            try:
                evidence.apply_result(repo_root, project_root, result, route)
            except Exception as exc:
                telemetry["status"] = "RECOVERING_INTERNAL"
                telemetry["last_result"] = {"task_id": task.id, "status": "RECOVERING_INTERNAL", "summary": str(exc), "evidence": list(result.evidence), "model": route.model, "reasoning": route.reasoning}
                _beat(runtime_path, telemetry); time.sleep(1.0); continue
            if result.status in {"COMPLETE", "COMPLETE_ALREADY"}:
                _clear_task_session(telemetry)
                _persist_until_success(repo_root, result.task_id, runtime_path, telemetry)
            _beat(runtime_path, telemetry)
            continue
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
    proc = subprocess.run(["systemctl", "start", f"{UNIT_NAME}.service"], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr, end=""); return proc.returncode
    print(json.dumps({"unit": UNIT_NAME, "status": "STARTED"}, sort_keys=True)); return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biella-codex production")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sync", "run", "start", "status"):
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
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
