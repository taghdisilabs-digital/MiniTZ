from __future__ import annotations

import fcntl
import json
import os
import secrets
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

ExecCommand = Callable[[list[str], Path, dict[str, str], int], tuple[int, str]]


class DialogBusy(RuntimeError):
    pass


def load_runtime_env(path: Path = Path("/root/.config/biella-ai/runtime.env")) -> dict[str, str]:
    env = dict(os.environ)
    if not path.is_file():
        return env
    result = subprocess.run(
        ["bash", "-c", 'set -a; source "$1"; env -0', "biella-control", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if result.returncode != 0:
        return env
    for item in result.stdout.split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        env[key.decode(errors="ignore")] = value.decode(errors="surrogateescape")
    return env


def exec_command(argv: list[str], cwd: Path, env: dict[str, str], timeout: int) -> tuple[int, str]:
    try:
        result = subprocess.run(
            argv, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
            text=True, capture_output=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
    return result.returncode, output.strip()


def start_thread(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, daemon=True).start()


def production_service_active() -> bool:
    return subprocess.run(
        ["systemctl", "is-active", "--quiet", "biella-codex-production.service"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def final_agent_text(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return "Local agent completed without a text response."
    for index, line in enumerate(lines):
        if line.lower() == "tokens used" and index > 0:
            return lines[index - 1][:12000]
    lower = [line.lower() for line in lines]
    if "codex" in lower:
        index = max(i for i, line in enumerate(lower) if line == "codex")
        if index + 1 < len(lines):
            return lines[index + 1][:12000]
    return lines[-1][:12000]


class ProductionJournalTailer:
    def __init__(self, path: Path, publish, *, poll_seconds: float = 0.2, replay_bytes: int = 262144):
        self.path = Path(path)
        self.publish = publish
        self.poll_seconds = poll_seconds
        self.replay_bytes = replay_bytes
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="biella-production-journal", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        position: int | None = None
        while not self._stop.is_set():
            if not self.path.exists():
                self._stop.wait(self.poll_seconds)
                continue
            try:
                size = self.path.stat().st_size
                if position is not None and size < position:
                    position = 0
                if position is None:
                    position = max(0, size - self.replay_bytes)
                    with self.path.open("rb") as handle:
                        handle.seek(position)
                        if position:
                            handle.readline()
                            position = handle.tell()
                with self.path.open("r", encoding="utf-8", errors="replace") as handle:
                    handle.seek(position)
                    while not self._stop.is_set():
                        line = handle.readline()
                        if not line:
                            position = handle.tell()
                            break
                        position = handle.tell()
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(event, dict):
                            self.publish("Games", event)
            except OSError:
                position = None
            self._stop.wait(self.poll_seconds)


class ProjectRunner:
    def __init__(self, *, lane_workdirs: dict[str, Path],
                 runtime_env_loader: Callable[[], dict[str, str]] = load_runtime_env,
                 exec_command: ExecCommand = exec_command,
                 background: Callable[[Callable[[], None]], None] = start_thread,
                 production_runtime_path: Path = Path("/mnt/biella-extra/biella-runtime/codex-production/runtime.json"),
                 production_active: Callable[[], bool] = production_service_active):
        self.lane_workdirs = {key: Path(value) for key, value in lane_workdirs.items()}
        self.runtime_env_loader = runtime_env_loader
        self.exec_command = exec_command
        self.background = background
        self.production_runtime_path = Path(production_runtime_path)
        self.production_active = production_active
        self.production_lock_path = self.production_runtime_path.parent / "run.lock"
        self._dialog_locks = {lane: threading.Lock() for lane in self.lane_workdirs}

    def _workdir(self, lane: str) -> Path:
        workdir = self.lane_workdirs.get(lane)
        if workdir is None or not workdir.is_dir():
            raise ValueError(f"lane workspace unavailable: {lane}")
        return workdir

    def _production_target(self, lane: str) -> tuple[str, str] | None:
        if lane != "Games" or not self.production_active():
            return None
        try:
            runtime = json.loads(self.production_runtime_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DialogBusy("production session is active but runtime identity is unavailable") from exc
        task_id = str(runtime.get("task_id") or "")
        session_task = str(runtime.get("session_task_id") or "")
        session_id = str(runtime.get("task_session_id") or "")
        if not task_id or session_task != task_id or not session_id:
            raise DialogBusy("production session is active but not ready for steering")
        return task_id, session_id

    def start_dialog(self, lane: str, message: str, publish) -> str:
        workdir = self._workdir(lane)
        dialog_id = "dialog-" + secrets.token_hex(6)
        target = self._production_target(lane)
        if target:
            task_id, session_id = target
            publish(lane, {"type": "dialog.operator", "id": dialog_id, "task_id": task_id, "text": message})
            argv = [
                "/usr/local/bin/biella-codex", "-C", str(workdir),
                "queue", "--thread", session_id, "--message", message,
            ]
            rc, output = self.exec_command(argv, workdir, self.runtime_env_loader(), 30)
            if rc != 0:
                publish(lane, {"type": "dialog.failed", "id": dialog_id, "task_id": task_id, "status": "FAILED", "text": (output or "queue failed")[-2000:]})
                raise DialogBusy("active production session rejected steering message")
            publish(lane, {"type": "dialog.queued", "id": dialog_id, "task_id": task_id, "status": "QUEUED", "text": "Queued into the active production session."})
            return dialog_id

        lock = self._dialog_locks[lane]
        if not lock.acquire(blocking=False):
            raise DialogBusy(f"dialog already active for {lane}")
        production_handle = None
        if lane == "Games":
            self.production_lock_path.parent.mkdir(parents=True, exist_ok=True)
            production_handle = self.production_lock_path.open("a+")
            try:
                fcntl.flock(production_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                production_handle.close()
                lock.release()
                raise DialogBusy("production or dialog active for Games") from exc
        publish(lane, {"type": "dialog.started", "id": dialog_id, "text": f"Local agent started for {lane}."})

        def worker() -> None:
            try:
                self._dialog_worker(dialog_id, lane, workdir, message, publish)
            finally:
                if production_handle is not None:
                    fcntl.flock(production_handle.fileno(), fcntl.LOCK_UN)
                    production_handle.close()
                lock.release()

        try:
            self.background(worker)
        except Exception:
            if production_handle is not None:
                fcntl.flock(production_handle.fileno(), fcntl.LOCK_UN)
                production_handle.close()
            lock.release()
            raise
        return dialog_id

    def _dialog_worker(self, dialog_id: str, lane: str, workdir: Path, message: str, publish) -> None:
        prompt = (
            f"You are operating Biella {lane} through the private control console using the shared /root/.codex controller context. "
            "Use progressive context: begin with the selected lane AGENTS/current task/directly touched source, expand only for a required unresolved fact, "
            "prefer targeted search and bounded log tails, and checkpoint before context pressure. "
            "The lane is starting context, not an execution sandbox. Preserve valid existing work and task status. "
            "Codex may use any configured local model, API, GPU, repository, runtime, or production tool when materially useful. "
            "Do not create model-specific project memory or parallel controller workflows.\n\n"
            f"Operator message:\n{message}"
        )
        argv = ["/usr/local/bin/biella-codex", "-C", str(workdir), "exec", prompt]
        rc, output = self.exec_command(argv, workdir, self.runtime_env_loader(), 900)
        if rc == 0:
            publish(lane, {"type": "dialog.agent", "id": dialog_id, "status": "COMPLETE", "text": final_agent_text(output)})
        else:
            tail = output[-4000:] if output else "Codex failed without output."
            publish(lane, {"type": "dialog.failed", "id": dialog_id, "status": "FAILED", "text": tail})

    def run_capability(self, lane: str, capability_id: str, auto_run: bool, publish) -> dict[str, object]:
        workdir = self._workdir(lane)
        commands = {
            "workstation.status": ["/usr/local/bin/biella", "status"],
            "workstation.doctor": ["/usr/local/bin/biella", "doctor"],
            "providers.check": ["/usr/local/bin/biella", "providers"],
            "git.status.current": ["git", "-C", str(workdir), "status", "--short", "--branch"],
        }
        argv = commands.get(capability_id)
        if argv is None:
            raise ValueError("unapproved capability")
        run_id = "run-" + secrets.token_hex(6)
        rc, output = self.exec_command(argv, workdir, self.runtime_env_loader(), 120)
        status = "COMPLETE" if rc == 0 else "FAILED"
        text = (output or status)[-6000:]
        publish(lane, {"type": "run", "id": run_id, "status": status, "capability_id": capability_id, "text": text})
        return {"run_id": run_id, "status": status, "output": text, "auto_run": auto_run}
