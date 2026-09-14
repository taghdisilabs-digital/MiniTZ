"""Start the existing canonical executor, without another task authority."""
from __future__ import annotations
import fcntl
import os
import subprocess
import sys
from pathlib import Path


def production_command(source_root, runtime_root, environ):
    source, runtime = Path(source_root).resolve(), Path(runtime_root).resolve()
    runner = source / "ops/local-ai/biella_production_runner.py"
    if not runner.is_file():
        raise RuntimeError("Canonical production runner is missing")
    env = dict(environ)
    env.update(MINITZ_SOURCE_ROOT=str(source), BIELLA_REPO_ROOT=str(source),
               BIELLA_PROJECT_ROOT=str(source),
               BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT=str(runtime))
    env["PYTHONPATH"] = str(source / "src") + os.pathsep + env.get("PYTHONPATH", "")
    executable = env.get("MINITZ_PRODUCTION_PYTHON", sys.executable)
    return [executable, str(runner), "run"], env


def launch_production(source_root, runtime_root, log, *, env=None, popen=subprocess.Popen):
    runtime = Path(runtime_root).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    # Probe the existing runner lock; never erase a lock or create a new queue.
    with (runtime / "run.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None, {"state": "ALREADY_RUNNING", "runtime_ref": str(runtime),
                          "functional_acceptance": "NOT_YET_OBSERVED"}
        fcntl.flock(lock, fcntl.LOCK_UN)
    command, environment = production_command(
        source_root, runtime, dict(os.environ) if env is None else env)
    child = popen(command, cwd=str(Path(source_root).resolve()), env=environment,
                  stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    return child, {"state": "START_REQUESTED", "pid": child.pid,
                   "runtime_ref": str(runtime), "runner_ref": command[-2],
                   "functional_acceptance": "NOT_YET_OBSERVED"}
