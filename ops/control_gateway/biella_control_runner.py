from __future__ import annotations

import os
import secrets
import subprocess
import threading
from pathlib import Path
from typing import Callable

ExecCommand = Callable[[list[str], Path, dict[str, str], int], tuple[int, str]]


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


class ProjectRunner:
    def __init__(self, *, lane_workdirs: dict[str, Path],
                 runtime_env_loader: Callable[[], dict[str, str]] = load_runtime_env,
                 exec_command: ExecCommand = exec_command,
                 background: Callable[[Callable[[], None]], None] = start_thread):
        self.lane_workdirs = {key: Path(value) for key, value in lane_workdirs.items()}
        self.runtime_env_loader = runtime_env_loader
        self.exec_command = exec_command
        self.background = background

    def _workdir(self, lane: str) -> Path:
        workdir = self.lane_workdirs.get(lane)
        if workdir is None or not workdir.is_dir():
            raise ValueError(f"lane workspace unavailable: {lane}")
        return workdir

    def start_dialog(self, lane: str, message: str, publish) -> str:
        workdir = self._workdir(lane)
        dialog_id = "dialog-" + secrets.token_hex(6)
        publish(lane, {"type": "dialog", "id": dialog_id, "text": f"Local agent started for {lane}."})

        def worker() -> None:
            self._dialog_worker(dialog_id, lane, workdir, message, publish)

        self.background(worker)
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
        argv = [
            "/usr/local/bin/biella-codex",
            "-C", str(workdir),
            "exec", prompt,
        ]
        rc, output = self.exec_command(argv, workdir, self.runtime_env_loader(), 900)
        if rc == 0:
            publish(lane, {"type": "dialog", "id": dialog_id, "status": "COMPLETE", "text": final_agent_text(output)})
        else:
            tail = output[-4000:] if output else "Codex failed without output."
            publish(lane, {"type": "dialog", "id": dialog_id, "status": "FAILED", "text": tail})

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
