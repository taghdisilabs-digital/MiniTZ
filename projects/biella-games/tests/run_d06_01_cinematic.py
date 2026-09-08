#!/usr/bin/env python3
"""Build, author, read back and exercise D06-01's real runtime sequence handoff."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import uuid

from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, runtime_run, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import monitor


ENGINE = Path("/opt/unreal/UE_5.8.2")
BUILD = ENGINE / "Engine/Build/BatchFiles/Linux/Build.sh"
SEQUENCE = PROJECT / "Content/Cinematics/LS_Demo01_RuntimeHandoff.uasset"
PROTECTED = [PROJECT.parents[1] / "docs/project-state/03_BIELLA_CURRENT_STATE.md",
             PROJECT.parents[1] / "docs/project-state/04_BIELLA_ACTIVE_TASK.md",
             PROJECT / "docs/PRODUCTION.md"]


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def task_inputs(editor):
    paths = {PROJECT / "BiellaGames.uproject", editor, ENGINE / "Engine/Build/Build.version",
             PROJECT / "Binaries/Linux/libUnrealEditor-BiellaGames.so",
             PROJECT / "Binaries/Linux/UnrealEditor.modules",
             PROJECT / "Binaries/Linux/BiellaGamesEditor.target",
             PROJECT / "Content/Python/author_d06_01_cinematic.py",
             PROJECT / "Source/BiellaGames/Private/BiellaCinematicDirector.cpp",
             PROJECT / "Source/BiellaGames/Public/BiellaCinematicDirector.h",
             PROJECT / "Source/BiellaGames/Private/Tests/BiellaCinematicTest.cpp",
             PROJECT / "tests/run_d06_01_cinematic.py"}
    for directory in ("Source", "Config", "Content", "Plugins"):
        paths.update(path for path in (PROJECT / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts)
    return [file_identity(path) for path in sorted(paths, key=str) if path.is_file()]


def prefix_for(account):
    return ["runuser", "-u", account.pw_name, "--"] if os.geteuid() == 0 else []


def commandlet(editor, account, report, engine_log, verify_mode):
    command = prefix_for(account) + [
        "xvfb-run", "-a", "-s", "-screen 0 1280x720x24", str(editor),
        str(PROJECT / "BiellaGames.uproject"), "-run=pythonscript",
        f"-script={PROJECT / 'Content/Python/author_d06_01_cinematic.py'}",
        "-EnablePlugins=PythonScriptPlugin", "-unattended", "-nullrhi", "-nosound", "-nop4",
        "-stdout", "-FullStdOutLogOutput", f"-AbsLog={engine_log}",
        f"-BiellaD06CinematicOutput={report}"]
    if verify_mode:
        command.append("-D06VerifyCinematic")
    return command


def build_editor(output):
    command = [str(BUILD), "BiellaGamesEditor", "Linux", "Development",
               f"-Project={PROJECT / 'BiellaGames.uproject'}", "-WaitMutex"]
    log = output / "build.log"
    with log.open("x", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=PROJECT, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=900, check=False)
    require(result.returncode == 0, f"Unreal editor build failed with exit code {result.returncode}")
    for binary in (PROJECT / "Binaries/Linux").glob("libUnrealEditor-Biella*.so"):
        os.chmod(binary, binary.stat().st_mode | 0o444)
    return {"command": command, "returncode": result.returncode, "log": file_identity(log)}


def validate_commandlet(run, report_path, mode, source_sha):
    require(not run["timed_out"] and run["returncode"] == 0,
            f"D06 {mode} commandlet failed or exceeded its deadline")
    log = Path(run["log"]["path"]).read_text(encoding="utf-8", errors="replace")
    require(f"D06_CINEMATIC_AUTHORING COMPLETE mode={mode}" in log,
            f"D06 {mode} commandlet completion marker is missing")
    require("Traceback" not in log and "D06_CINEMATIC AUTHORING FAIL" not in log,
            f"D06 {mode} commandlet reported a Python failure")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    require(data.get("task_id") == "D06-01" and data.get("mode") == mode and data.get("result") == "PASS",
            f"D06 {mode} report is not PASS")
    require(data.get("source_sha256") == source_sha, f"D06 {mode} source SHA does not match authoring source")
    sequence = data.get("sequence", {})
    require(sequence.get("binding_count") == 1 and sequence.get("camera_cut_track_count") == 1,
            f"D06 {mode} report does not prove one camera binding and one camera-cut track")
    require(sequence.get("playback_start") == 0 and sequence.get("playback_end", 0) > 0,
            f"D06 {mode} report has an invalid editable playback range")
    return data


def validate_runtime(run, output):
    require(not run["timed_out"] and run["returncode"] == 0,
            "D06 Unreal runtime failed or exceeded its process deadline")
    require(run["log_finalization"]["closed"], "D06 runtime log still has a writer")
    log = (output / "runtime.stdout.log").read_text(encoding="utf-8", errors="replace")
    require("**** TEST COMPLETE. EXIT CODE: 0 ****" in log,
            "D06 automation completion marker is missing")
    require(re.search(r"Result=\{Success\}.*Name=\{Cinematic\}", log),
            "D06 Cinematic automation did not report success")
    require("D06_01_TEST COMPLETE" in log, "D06 native handoff completion marker is missing")
    require(log.count("D06_SIGNAL CINEMATIC_HANDOFF path=watched") == 1 and
            log.count("D06_SIGNAL CINEMATIC_HANDOFF path=skipped") == 1,
            "D06 watched and skipped handoff markers are incomplete")
    require(not re.search(
        r"Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:|"
        r"D06_01_TEST FAIL|D06_SIGNAL CINEMATIC_REJECTED", log),
        "D06 runtime reported a failed test, ensure, fatal, or rejected handoff")

    telemetry = output / "cinematic.telemetry.jsonl"
    require(telemetry.is_file(), "D06 runtime did not produce opt-in telemetry")
    records = [json.loads(line) for line in telemetry.read_text(encoding="utf-8").splitlines() if line.strip()]
    events = [record.get("event") for record in records]
    require(events.count("cinematic_enter") == 2 and events.count("cinematic_handoff") == 2,
            "D06 telemetry does not contain both sequence entries and both handoffs")
    paths = sorted(record.get("fields", {}).get("path") for record in records
                   if record.get("event") == "cinematic_handoff")
    require(paths == ["skipped", "watched"], "D06 telemetry handoff paths are not watched and skipped")
    return {"log": file_identity(output / "runtime.stdout.log"),
            "telemetry": file_identity(telemetry), "handoff_paths": paths,
            "signals": {"watched": log.count("D06_SIGNAL CINEMATIC_HANDOFF path=watched"),
                        "skipped": log.count("D06_SIGNAL CINEMATIC_HANDOFF path=skipped")}}


def record_failure(error, output):
    event = {"task_id": "D06-01", "time": datetime.now(timezone.utc).isoformat(),
             "type": "cinematic_runtime_validation", "status": "CONTINUE",
             "diagnostics": str(error)[:2000], "evidence": str(output)}
    try:
        with Path("/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Fresh D06 evidence directory")
    parser.add_argument("--editor", type=Path, default=DEFAULT_EDITOR)
    parser.add_argument("--timeout", type=float, default=240)
    args = parser.parse_args()
    if not 30 < args.timeout <= 900:
        parser.error("--timeout must be greater than 30 and at most 900 seconds")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = (args.output or Path("/root/biella/artifacts/games/D06-01") /
              f"{stamp}-vulkan-{uuid.uuid4().hex[:8]}").resolve()
    require(not output.exists(), f"Evidence directory already exists: {output}")
    editor = args.editor.resolve()
    account = pwd.getpwnam("unreal") if os.geteuid() == 0 else pwd.getpwuid(os.geteuid())
    ensure_runtime_output(output, account)
    report_path = output / "validation.json"
    source_sha = hashlib.sha256((PROJECT / "Content/Python/author_d06_01_cinematic.py").read_bytes()).hexdigest()
    report = {"task_id": "D06-01", "result": "FAIL", "created_utc": stamp,
              "output": str(output), "renderer": "vulkan", "capture_status": "GENERATED_DRAFT",
              "source_sha256": source_sha}

    def save():
        write_json(report_path, report)

    print(f"D06-01 evidence: {report_path}", flush=True)
    try:
        require(editor.is_file(), f"Unreal editor not found: {editor}")
        require(BUILD.is_file(), f"Unreal build tool not found: {BUILD}")
        report["source_revision_before"] = source_revision()
        report["protected_before"] = [file_identity(path) for path in PROTECTED]
        save()

        report["build"] = build_editor(output)
        save()

        author_report_path = output / "authoring.json"
        author_run = runtime_run(
            commandlet(editor, account, author_report_path, output / "authoring.engine.log", False),
            output / "authoring.stdout.log", 240)
        report["authoring"] = author_run
        report["authoring_report"] = validate_commandlet(author_run, author_report_path, "author", source_sha)
        require(SEQUENCE.is_file(), f"Editable sequence package is missing: {SEQUENCE}")
        require(SEQUENCE.read_bytes()[:4] == bytes.fromhex("c1832a9e"),
                "Editable sequence is not an Unreal package asset")
        report["sequence_asset"] = {**file_identity(SEQUENCE), "format": "UnrealPackage", "magic": "c1832a9e"}
        save()

        verify_report_path = output / "readback.json"
        verify_run = runtime_run(
            commandlet(editor, account, verify_report_path, output / "readback.engine.log", True),
            output / "readback.stdout.log", 240)
        report["readback"] = verify_run
        report["readback_report"] = validate_commandlet(verify_run, verify_report_path, "verify", source_sha)
        save()

        report["runtime_inputs_before"] = task_inputs(editor)
        runtime_output = output / "runtime"
        ensure_runtime_output(runtime_output, account)
        runtime_command = prefix_for(account) + [
            "xvfb-run", "-a", "-s", "-screen 0 1280x720x24", str(editor),
            str(PROJECT / "BiellaGames.uproject"), "/Game/Maps/BiellaGameplayMap", "-game",
            "-vulkan", "-RenderOffscreen", "-NoVSync", "-windowed", "-ResX=1280", "-ResY=720",
            "-unattended", "-nosound", "-nosplash", "-NoAsyncLoadingThread", "-stdout",
            "-FullStdOutLogOutput", f"-AbsLog={runtime_output / 'runtime.engine.log'}",
            "-BiellaD06Cinematic",
            f"-BiellaTelemetry={runtime_output / 'cinematic.telemetry.jsonl'}",
            "-ExecCmds=Automation RunTests BiellaGames.D06.Cinematic; SoftQuit"]
        report["runtime"] = monitor(runtime_command, runtime_output, args.timeout)
        report["runtime_validation"] = validate_runtime(report["runtime"], runtime_output)
        report["runtime_inputs_after"] = task_inputs(editor)
        report["protected_after"] = [file_identity(path) for path in PROTECTED]
        require(report["runtime_inputs_before"] == report["runtime_inputs_after"],
                "Tested source/config/content/module bytes changed during runtime")
        require(report["protected_before"] == report["protected_after"],
                "Canonical protected task metadata changed during runtime")
        report["result"] = "PASS"
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
        record_failure(error, output)
    finally:
        save()
    print(json.dumps({"task_id": report["task_id"], "result": report["result"],
                      "output": str(output), "error": report.get("error")}))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
