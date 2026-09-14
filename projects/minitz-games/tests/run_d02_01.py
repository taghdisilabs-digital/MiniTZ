#!/usr/bin/env python3
"""Run the editable D02-01 world through real Vulkan streaming and verify evidence.

Build/map authoring must finish first. Retains failed attempts, captures exact
source/module/content identities and leaves canonical task metadata untouched.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import re
import signal
import subprocess
import time

from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d01_043 import finalize_log, process_members
from verify_d02_01 import require, verify


def runtime_has_task_error(log: str) -> bool:
    """Ignore only the observed engine diagnostic before D02 execution begins."""
    if re.search(r"Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:", log):
        return True
    markers = [position for token in ("D02_STREAM WORLD_READY", "D02_01_TEST event=")
               if (position := log.find(token)) >= 0]
    boundary = min(markers) if markers else 0
    known_startup_error = (
        "StructProperty FDataflowToolNodeSnapshot::Date is not initialized properly "
        "even though its struct probably has a custom default constructor. "
        "Non deterministic fields should use UPROPERTY(Meta = (IgnoreForMemberInitializationTest)) "
        "to avoid errors from this test. Module:DataflowNodes File:Public/Dataflow/DataflowToolNode.h"
    )
    offset = 0
    for line in log.splitlines(keepends=True):
        error = re.search(r"\bError:", line)
        if error:
            message = line[error.end():].strip()
            if message.startswith("LogClass: "):
                message = message[len("LogClass: "):]
            if offset >= boundary or message != known_startup_error:
                return True
        offset += len(line)
    return False


def reject_material_fallbacks(log):
    require(not re.search(
        r"missing(?: the)? usage flag (?:bUsedWith)?InstancedStaticMeshes|"
        r"Default Material will be used in game|will be used instead", log, re.I),
        "Runtime substituted a fallback material instead of authored world/HLOD presentation")


def identities(editor):
    paths = {PROJECT / "BiellaGames.uproject", editor,
             editor.parents[2] / "Build/Build.version",
             PROJECT / "Binaries/Linux/libUnrealEditor-BiellaGames.so",
             PROJECT / "Binaries/Linux/UnrealEditor.modules",
             PROJECT / "Binaries/Linux/BiellaGamesEditor.target"}
    for directory in ("Source", "Config", "Content", "Plugins"):
        paths.update(path for path in (PROJECT / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts)
    paths.update(PROJECT / "tests" / name for name in (
        "run_d02_01.py", "verify_d02_01.py", "run_d01_039.py", "run_d01_042.py", "run_d01_043.py"))
    return [file_identity(path) for path in sorted(paths)]


def monitor(command, output, timeout):
    start = time.monotonic()
    last_sample = 0.0
    timed_out = False
    observed = set()
    log_path = output / "runtime.stdout.log"
    with log_path.open("xb") as log, (output / "process-memory.jsonl").open("x") as samples:
        process = subprocess.Popen(command, cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                now = time.monotonic()
                if now - start > timeout:
                    timed_out = True
                    os.killpg(process.pid, signal.SIGTERM)
                    break
                if now - last_sample >= 1:
                    records = []
                    for member in process_members(process.pid):
                        if member["name"] != "UnrealEditor":
                            continue
                        try:
                            status = (Path("/proc") / str(member["pid"]) / "status").read_text()
                            rss = int(re.search(r"^VmRSS:\s+(\d+)", status, re.M)[1])
                            peak = int(re.search(r"^VmHWM:\s+(\d+)", status, re.M)[1])
                        except (OSError, TypeError):
                            continue
                        records.append({**member, "rss_kib": rss, "peak_rss_kib": peak})
                        observed.add((member["pid"], member["start_ticks"]))
                    samples.write(json.dumps({"utc": datetime.now(timezone.utc).isoformat(),
                                              "elapsed_seconds": now - start, "unreal": records}) + "\n")
                    samples.flush()
                    last_sample = now
                time.sleep(.1)
            try:
                rc = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                rc = process.wait(timeout=10)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
    finalization = finalize_log(log_path)
    return {"command": command, "returncode": rc, "timed_out": timed_out,
            "elapsed_seconds": time.monotonic() - start, "timeout_seconds": timeout,
            "log": file_identity(log_path), "log_finalization": finalization,
            "observed_engine_processes": [{"pid": pid, "start_ticks": ticks} for pid, ticks in sorted(observed)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Fresh exact attempt directory; never overwritten")
    parser.add_argument("--editor", type=Path, default=DEFAULT_EDITOR)
    parser.add_argument("--timeout", type=float, default=720)
    args = parser.parse_args()
    if not 0 < args.timeout <= 900:
        parser.error("--timeout must be positive and at most 900 wall seconds")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = (args.output or Path("/root/biella/artifacts/games/D02-01") / stamp).resolve()
    editor = args.editor.resolve()
    account = pwd.getpwnam("unreal") if os.geteuid() == 0 else pwd.getpwuid(os.geteuid())
    prefix = ["runuser", "-u", account.pw_name, "--"] if os.geteuid() == 0 else []
    ensure_runtime_output(output, account)
    protected = [PROJECT.parents[1] / "docs/project-state/03_BIELLA_CURRENT_STATE.md",
                 PROJECT.parents[1] / "docs/project-state/04_BIELLA_ACTIVE_TASK.md", PROJECT / "docs/PRODUCTION.md"]
    report = {"task_id": "D02-01", "result": "FAIL", "created_utc": stamp, "output": str(output),
              "scope": "Editable Unreal Linux Vulkan development-host runtime; no Windows shipping or target-FPS acceptance inferred.",
              "capture_status": "GENERATED_DRAFT"}
    report_path = output / "validation.json"
    print(f"D02-01 evidence: {report_path}", flush=True)
    try:
        report["source_revision"] = source_revision()
        report["protected_before"] = [file_identity(path) for path in protected]
        report["identities_before"] = identities(editor)
        write_json(report_path, report)
        settings = ["t.MaxFPS 0", "r.VSync 0", "r.ScreenPercentage 100", "r.DynamicRes.OperationMode 0"]
        command = prefix + ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", str(editor),
                            str(PROJECT / "BiellaGames.uproject"), "/Game/Maps/BiellaOpenWorldMap", "-game",
                            "-vulkan", "-NoVSync", "-windowed", "-ResX=1280", "-ResY=720", "-unattended",
                            "-AudioMixer", "-DeterministicAudio", "-nosplash", "-stdout", "-FullStdOutLogOutput",
                            f"-AbsLog={output / 'runtime.engine.log'}",
                            "-ExecCmds=" + ",".join(settings + ["Automation RunTests BiellaGames.D02.WorldStreaming; SoftQuit"]),
                            f"-BiellaStreamingOutput={output}"]
        report["runtime"] = monitor(command, output, args.timeout)
        write_json(report_path, report)
        runtime = report["runtime"]
        require(not runtime["timed_out"] and runtime["returncode"] == 0, "Unreal failed or exceeded process deadline")
        require(runtime["log_finalization"]["closed"], "Runtime log still has a writer; evidence not final")
        log = (output / "runtime.stdout.log").read_text(errors="replace")
        require("**** TEST COMPLETE. EXIT CODE: 0 ****" in log, "Unreal completion marker missing")
        require(re.search(r"Result=\{Success\}.*Name=\{WorldStreaming\}", log), "WorldStreaming automation did not pass")
        require(not runtime_has_task_error(log),
                "Unreal reported a task-window error, failed assertion, or ensure")
        reject_material_fallbacks(log)
        report["verification"] = verify(output)
        memory = [json.loads(line) for line in (output / "process-memory.jsonl").read_text().splitlines()]
        measurements = [process for sample in memory for process in sample["unreal"]]
        require(len(measurements) >= 10 and len(runtime["observed_engine_processes"]) == 1,
                "Missing independent memory samples or ambiguous Unreal process identity")
        report["independent_peak_rss_kib"] = max(sample["rss_kib"] for sample in measurements)
        report["process_memory"] = file_identity(output / "process-memory.jsonl")
        report["identities_after"] = identities(editor)
        report["protected_after"] = [file_identity(path) for path in protected]
        require(report["identities_before"] == report["identities_after"], "Tested source/module/content bytes changed during runtime")
        require(report["protected_before"] == report["protected_after"], "Canonical protected task metadata changed during runtime")
        report["result"] = "PASS"
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    finally:
        # Failed attempts also retain the exact finishing bytes for diagnosis.
        try:
            if "identities_before" in report and "identities_after" not in report:
                report["identities_after"] = identities(editor)
            if "protected_before" in report and "protected_after" not in report:
                report["protected_after"] = [file_identity(path) for path in protected]
        except OSError as error:
            report["identity_readback_error"] = str(error)
            report["result"] = "FAIL"
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(report_path, report)
    print(json.dumps({"task_id": "D02-01", "result": report["result"], "error": report.get("error"),
                      "validation": str(report_path)}), flush=True)
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
