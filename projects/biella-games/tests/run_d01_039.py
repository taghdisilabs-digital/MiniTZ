#!/usr/bin/env python3
"""Run two or more independent real Unreal D01-39 playtests and compare telemetry.

Each invocation creates a new attempt directory, retaining failed evidence.
Requires the current Editor target to have been built before invocation.
"""

import argparse
import hashlib
import json
import os
import pwd
import re
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from verify_d01_039 import require, verify


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_EDITOR = Path("/opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealEditor")
AUTOMATION = "BiellaGames.Demo01.DeterministicPlaytest"


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def file_identity(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def identities(editor):
    paths = [PROJECT / "BiellaGames.uproject", PROJECT / "Content/Maps/BiellaGameplayMap.umap",
             PROJECT / "Content/Maps/BiellaGameplayMap_Recovered.umap",
             PROJECT / "Binaries/Linux/libUnrealEditor-BiellaGames.so",
             PROJECT / "Binaries/Linux/UnrealEditor.modules", PROJECT / "Binaries/Linux/BiellaGamesEditor.target",
             editor, editor.parents[2] / "Build/Build.version"]
    paths.extend(path for directory in ("Source", "Config") for path in (PROJECT / directory).rglob("*") if path.is_file())
    paths.extend((PROJECT / "tests/run_d01_039.py", PROJECT / "tests/verify_d01_039.py"))
    return [file_identity(path) for path in sorted(set(paths))]


def source_revision():
    result = subprocess.run(["git", "rev-parse", "HEAD", "HEAD^{tree}"], cwd=PROJECT,
                            text=True, capture_output=True, timeout=10, check=True)
    commit, tree = result.stdout.splitlines()
    dirty = subprocess.run(["git", "status", "--short", "--", "."], cwd=PROJECT,
                           text=True, capture_output=True, timeout=10, check=True)
    return {"head": commit, "head_tree": tree, "project_status": dirty.stdout.splitlines(),
            "note": "File hashes identify tested working bytes; HEAD may precede the task commit."}


def runtime_run(command, log_path, timeout):
    start = time.monotonic()
    timed_out = False
    with log_path.open("xb") as log:
        process = subprocess.Popen(command, cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            # This group contains only this launched test, including runuser's child.
            os.killpg(process.pid, signal.SIGKILL)
            returncode = process.wait(timeout=10)
    return {"command": command, "pid": process.pid, "returncode": returncode,
            "timed_out": timed_out, "timeout_seconds": timeout,
            "elapsed_seconds": round(time.monotonic() - start, 3), "log": file_identity(log_path)}


def validate_automation(run):
    require(not run["timed_out"], "Unreal playtest exceeded its process timeout")
    require(run["returncode"] == 0, f"Unreal exited {run['returncode']}")
    content = Path(run["log"]["path"]).read_text(encoding="utf-8", errors="replace")
    require("**** TEST COMPLETE. EXIT CODE: 0 ****" in content, "Unreal automation completion missing")
    require(re.search(r"Result=\{Success\}.*Name=\{DeterministicPlaytest\}", content),
            "DeterministicPlaytest did not report automation success")
    require(not re.search(r"Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:|D01_039_TEST FAIL", content),
            "Unreal reported a failed test, assertion, ensure or fatal error")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT / "Build/Demo01/D01-039-runs",
                        help="Root for a new unique attempt directory (existing captures are never overwritten)")
    parser.add_argument("--editor", type=Path, default=DEFAULT_EDITOR)
    parser.add_argument("--renderer", choices=("nullrhi", "vulkan"), default="nullrhi")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--timeout", type=float, default=150, help="Per-process deadline, maximum 150 seconds")
    parser.add_argument("--runtime-user", default="unreal" if os.geteuid() == 0 else None,
                        help="Root launches Unreal with runuser, default: unreal")
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs must be at least 2")
    if not 0 < args.timeout <= 150:
        parser.error("--timeout must be greater than zero and at most 150 seconds")
    if not 0 <= args.seed <= 2147483647:
        parser.error("--seed must be a nonnegative signed 32-bit integer")
    if os.geteuid() == 0 and not args.runtime_user:
        parser.error("Unreal must run as a non-root runtime user")
    args.output = args.output.resolve()
    args.editor = args.editor.resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    attempt = args.output / f"{stamp}-{args.renderer}-{uuid.uuid4().hex[:8]}"
    # Root's usual umask is 077. Grant traversal only on output directories
    # this invocation creates, leaving pre-existing ancestors untouched.
    missing_parents, parent = [], args.output
    while not parent.exists():
        missing_parents.append(parent)
        parent = parent.parent
    args.output.mkdir(parents=True, exist_ok=True)
    for parent in missing_parents:
        parent.chmod(0o755)
    attempt.mkdir(parents=True, exist_ok=False)
    report = {"task_id": "D01-39", "result": "FAIL", "attempt": str(attempt),
              "created_utc": stamp, "renderer": args.renderer, "seed": args.seed,
              "fixed_delta_seconds": 1 / 60, "requested_runs": args.runs, "runs": []}
    print(f"D01-39 attempt: {attempt}", flush=True)
    try:
        runtime_prefix = []
        if args.runtime_user:
            runtime_account = pwd.getpwnam(args.runtime_user)
            require(runtime_account.pw_uid != 0, "Unreal runtime user must not be root")
            if os.geteuid() == 0:
                os.chown(attempt, runtime_account.pw_uid, runtime_account.pw_gid)
                attempt.chmod(0o755)
                runtime_prefix = ["runuser", "-u", args.runtime_user, "--"]
            else:
                require(runtime_account.pw_uid == os.geteuid(), "Only root can select another runtime user")
        access = subprocess.run(runtime_prefix + ["test", "-w", str(attempt)], capture_output=True, timeout=10)
        require(access.returncode == 0, f"Runtime user cannot traverse/write attempt directory: {attempt}")
        report["revision"] = source_revision()
        report["identities_before"] = identities(args.editor)
        write_json(attempt / "validation.json", report)
        captures = []
        for index in range(1, args.runs + 1):
            capture = attempt / f"run-{index:02d}.telemetry.jsonl"
            log_path = attempt / f"run-{index:02d}.stdout.log"
            command = runtime_prefix + [str(args.editor), str(PROJECT / "BiellaGames.uproject"),
                       "/Game/Maps/BiellaGameplayMap", "-game"]
            command += ["-nullrhi"] if args.renderer == "nullrhi" else [
                "-vulkan", "-RenderOffscreen", "-NoVSync", "-windowed", "-ResX=1280", "-ResY=720"]
            command += ["-unattended", "-nosound", "-nosplash", "-NoAsyncLoadingThread", "-stdout", "-FullStdOutLogOutput",
                        f"-AbsLog={attempt / f'run-{index:02d}.engine.log'}",
                        f"-ExecCmds=Automation RunTests {AUTOMATION}; SoftQuit", f"-BiellaTelemetry={capture}",
                        f"-BiellaPlaytestSeed={args.seed}", "-UseFixedTimeStep", "-FPS=60"]
            run = {"index": index, "command": command, "capture_path": str(capture), "result": "FAIL"}
            report["runs"].append(run)
            write_json(attempt / f"run-{index:02d}.json", run)
            write_json(attempt / "validation.json", report)
            run.update(runtime_run(command, log_path, args.timeout))
            if capture.exists():
                run["capture"] = file_identity(capture)
            write_json(attempt / f"run-{index:02d}.json", run)
            validate_automation(run)
            require(capture.is_file(), "Unreal did not create telemetry capture")
            run["result"] = "AUTOMATION_PASS"
            captures.append(capture)
            write_json(attempt / f"run-{index:02d}.json", run)
            write_json(attempt / "validation.json", report)
            print(f"Run {index}/{args.runs}: automation passed; captured {capture.name}", flush=True)
        report["verification"] = verify(captures)
        require(all(run["seed"] == args.seed for run in report["verification"]["runs"]),
                "Telemetry seed differs from requested seed")
        report["identities_after"] = identities(args.editor)
        require(report["identities_before"] == report["identities_after"], "Tested source/config/map/build bytes changed during execution")
        report["result"] = "PASS"
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    finally:
        write_json(attempt / "validation.json", report)
    print(json.dumps({"task_id": "D01-39", "result": report["result"], "validation": str(attempt / "validation.json"),
                      "error": report.get("error")}, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
