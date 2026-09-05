#!/usr/bin/env python3
"""Run one sustained Vulkan/audio Demo01 process; preserve every attempt locally."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import time

from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, identities, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from verify_d01_039 import require
from verify_d01_043 import classify_log, qualification_mode, verify_capture

REFERENCE = PROJECT / "Build/Demo01/D01-042-qualified-predecessor/20260905T084808.360613Z-nullrhi-02df4931/run-01.telemetry.jsonl"
BASELINE_LOG = PROJECT / "Build/Demo01/D01-042-runs/20260905T084808.324250Z/feedback.stdout.log"
PROTECTED = [PROJECT.parents[1] / "docs/project-state/03_BIELLA_CURRENT_STATE.md",
             PROJECT.parents[1] / "docs/project-state/04_BIELLA_ACTIVE_TASK.md", PROJECT / "docs/PRODUCTION.md"]


def task_identities(editor):
    paths = list((PROJECT / "Content").rglob("*.uasset"))
    paths += [Path(__file__), PROJECT / "tests/verify_d01_043.py", PROJECT / "tests/test_d01_043.py",
              PROJECT / "tests/run_d01_042.py", REFERENCE, BASELINE_LOG]
    return identities(editor) + [file_identity(p) for p in sorted(paths)]


def process_members(group):
    members = []
    for directory in Path("/proc").glob("[0-9]*"):
        try:
            raw = (directory / "stat").read_text()
            fields = raw[raw.rfind(")") + 2:].split()
            if int(fields[2]) == group:
                members.append({"pid": int(directory.name), "name": raw[raw.find("(") + 1:raw.rfind(")")],
                                "state": fields[0], "start_ticks": int(fields[19])})
        except (OSError, ValueError, IndexError):
            continue
    return members


def monitored_run(command, directory, timeout):
    start = time.monotonic()
    capture = directory / "soak.telemetry.jsonl"
    log_path = directory / "soak.stdout.log"
    monitor_path = directory / "process-monitor.jsonl"
    identities_seen = set()
    failure = None
    last_event_at, last_seq = start, 0
    last_sample = 0
    last_event = None
    with log_path.open("xb") as output, monitor_path.open("x") as monitor:
        process = subprocess.Popen(command, cwd=PROJECT, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                now = time.monotonic()
                if now - start > timeout:
                    failure = "overall process deadline"
                    break
                if capture.exists():
                    with capture.open("rb") as stream:
                        stream.seek(max(0, capture.stat().st_size - 16384))
                        lines = stream.read().splitlines()
                    for line in reversed(lines):
                        try:
                            event = json.loads(line)
                            if event["seq"] > last_seq:
                                last_seq, last_event_at, last_event = event["seq"], now, event
                            break
                        except (ValueError, KeyError):
                            continue
                if now - last_event_at > (30 if last_seq else 120):
                    failure = "telemetry progress watchdog"
                    break
                if now - last_sample >= 5:
                    members = process_members(process.pid)
                    for item in members:
                        if item["name"] == "UnrealEditor":
                            identities_seen.add((item["pid"], item["start_ticks"]))
                    monitor.write(json.dumps({"elapsed_seconds": now - start, "process_group": process.pid,
                                              "members": members, "last_event": last_event}) + "\n")
                    monitor.flush()
                    last_sample = now
                time.sleep(0.25)
            if failure:
                # Capture identity and wait channels before terminating only this invocation's group.
                diagnostics = {"reason": failure, "members": process_members(process.pid), "last_event": last_event}
                for member in diagnostics["members"]:
                    try:
                        member["wait_channel"] = Path(f"/proc/{member['pid']}/wchan").read_text().strip()
                    except OSError:
                        pass
                write_json(directory / "watchdog.json", diagnostics)
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
            returncode = process.wait(timeout=15)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
    survivors = process_members(process.pid)
    if survivors:
        os.killpg(process.pid, signal.SIGKILL)
    return {"command": command, "launcher_pid": process.pid, "returncode": returncode,
            "watchdog_failure": failure, "timeout_seconds": timeout, "elapsed_seconds": time.monotonic() - start,
            "unreal_process_identities": [{"pid": pid, "start_ticks": ticks} for pid, ticks in sorted(identities_seen)],
            "surviving_processes_after_exit": survivors, "log": file_identity(log_path),
            "process_monitor": file_identity(monitor_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=900)
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--editor", type=Path, default=DEFAULT_EDITOR)
    args = parser.parse_args()
    if not 10 <= args.seconds <= 3600 or not 1 <= args.cycles <= 100:
        parser.error("seconds must be 10..3600 and cycles 1..100")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = PROJECT / "Build/Demo01/D01-043-runs" / stamp
    account = pwd.getpwnam("unreal") if os.geteuid() == 0 else pwd.getpwuid(os.geteuid())
    ensure_runtime_output(directory, account)
    report_path = directory / "validation.json"
    report = {"task_id": "D01-43", "result": "FAIL", "mode": qualification_mode(args.seconds, args.cycles),
              "created_utc": stamp, "requested_seconds": args.seconds, "minimum_cycles": args.cycles,
              "revision": source_revision(), "identities_before": task_identities(args.editor),
              "protected_before": [file_identity(p) for p in PROTECTED],
              "scope": "One Linux development-host Vulkan/audio process; fixed60 simulation; no shipping FPS, leak-free, Windows or package qualification."}
    write_json(report_path, report)
    print(f"D01-43 evidence: {report_path}", flush=True)
    try:
        prefix = ["runuser", "-u", account.pw_name, "--"] if os.geteuid() == 0 else []
        command = prefix + ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", str(args.editor),
                  str(PROJECT / "BiellaGames.uproject"), "/Game/Maps/BiellaGameplayMap", "-game", "-vulkan",
                  "-NoVSync", "-windowed", "-ResX=1280", "-ResY=720", "-unattended", "-AudioMixer",
                  "-DeterministicAudio", "-UseFixedTimeStep", "-FPS=60", "-nosplash", "-NoAsyncLoadingThread",
                  "-stdout", "-FullStdOutLogOutput", f"-AbsLog={directory / 'soak.engine.log'}",
                  "-ExecCmds=t.MaxFPS 60,Automation RunTests BiellaGames.Demo01.StabilitySoak; SoftQuit",
                  f"-BiellaTelemetry={directory / 'soak.telemetry.jsonl'}", "-BiellaPlaytestSeed=1337",
                  f"-BiellaSoakSeconds={args.seconds}", f"-BiellaSoakCycles={args.cycles}"]
        report["command"] = command
        write_json(report_path, report)
        report["runtime"] = monitored_run(command, directory, args.seconds + 240)
        write_json(report_path, report)
        runtime = report["runtime"]
        require(runtime["returncode"] == 0 and not runtime["watchdog_failure"], "Runtime exit/watchdog failure")
        require(len(runtime["unreal_process_identities"]) == 1, "Expected one uninterrupted Unreal PID/start identity")
        require(not runtime["surviving_processes_after_exit"], "Test process group did not exit cleanly")
        report["logs"] = classify_log((directory / "soak.stdout.log").read_text(errors="replace"), BASELINE_LOG.read_text())
        report["telemetry"] = file_identity(directory / "soak.telemetry.jsonl")
        report["verification"] = verify_capture(directory / "soak.telemetry.jsonl", args.seconds, args.cycles, REFERENCE)
        report["identities_after"] = task_identities(args.editor)
        report["protected_after"] = [file_identity(p) for p in PROTECTED]
        require(report["identities_before"] == report["identities_after"], "Tested bytes changed during run")
        require(report["protected_before"] == report["protected_after"], "Protected task metadata changed")
        report["result"] = "PASS"
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    finally:
        write_json(report_path, report)
    print(json.dumps({"result": report["result"], "mode": report["mode"], "validation": str(report_path),
                      "error": report.get("error")}, indent=2), flush=True)
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
