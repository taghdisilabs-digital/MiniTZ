#!/usr/bin/env python3
"""Author, read back and exercise D04-01's versioned population content."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
import time
import uuid

from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, runtime_run, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import monitor, reject_material_fallbacks
from verify_d04_01 import require, verify


CONTENT_SOURCE = PROJECT / "Content/Data/D04/D04-01-content.json"
CONTENT_ASSET_NAMES = (
    "DA_ActorVariant_InfectedStandard.uasset",
    "DA_ActorVariant_RivalStandard.uasset",
    "DA_Encounter_StreetPopulation.uasset",
    "DA_Tuning_PopulationDevelopment.uasset",
)
PROTECTED = [PROJECT.parents[1] / "docs/project-state/03_BIELLA_CURRENT_STATE.md",
             PROJECT.parents[1] / "docs/project-state/04_BIELLA_ACTIVE_TASK.md", PROJECT / "docs/PRODUCTION.md"]


def source_inputs(editor):
    paths = [
        PROJECT / "BiellaGames.uproject",
        PROJECT / "Config/DefaultGame.ini",
        PROJECT / "Content/Maps/BiellaOpenWorldMap.umap",
        CONTENT_SOURCE,
        PROJECT / "Content/Python/author_d04_01_content.py",
        PROJECT / "Source/BiellaGames/Public/BiellaContentDefinitions.h",
        PROJECT / "Source/BiellaGames/Private/BiellaContentDefinitions.cpp",
        PROJECT / "Source/BiellaGames/Public/BiellaPopulation.h",
        PROJECT / "Source/BiellaGames/Private/BiellaPopulation.cpp",
        PROJECT / "Source/BiellaGames/Private/Tests/BiellaContentRegistryTest.cpp",
        PROJECT / "tests/run_d04_01.py",
        PROJECT / "tests/verify_d04_01.py",
        PROJECT / "tests/run_d02_02.py",
        PROJECT / "tests/verify_d02_02.py",
        PROJECT / "tests/run_d02_04.py",
        PROJECT / "tests/verify_d02_04.py",
        PROJECT / "tests/run_d02_01_shared_regression.py",
        PROJECT / "tests/verify_d01_031.py",
        PROJECT / "tests/verify_d01_039.py",
        PROJECT / "tests/run_d02_01.py",
        PROJECT / "tests/run_d01_039.py",
        PROJECT / "tests/run_d01_042.py",
        PROJECT / "Binaries/Linux/libUnrealEditor-BiellaGames.so",
        PROJECT / "Binaries/Linux/libUnrealEditor-BiellaLoadingScreen.so",
        PROJECT / "Binaries/Linux/UnrealEditor.modules",
        PROJECT / "Binaries/Linux/BiellaGamesEditor.target",
        editor,
        editor.parents[2] / "Build/Build.version",
    ]
    return [file_identity(path) for path in sorted(set(paths))]


def content_assets():
    folder = PROJECT / "Content/Data/D04"
    assets = []
    for name in CONTENT_ASSET_NAMES:
        path = folder / name
        require(path.is_file(), f"Missing native runtime asset: {path}")
        raw = path.read_bytes()
        require(raw[:4] == bytes.fromhex("c1832a9e"), f"{path} is not an Unreal package asset")
        assets.append({**file_identity(path), "format": "UnrealPackage", "magic": raw[:4].hex()})
    return assets


def _prefix(account):
    return ["runuser", "-u", account.pw_name, "--"] if os.geteuid() == 0 else []


def commandlet_command(editor, account, report, engine_log, verify_mode):
    command = _prefix(account) + ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", str(editor),
              str(PROJECT / "BiellaGames.uproject"), "-run=pythonscript",
              f"-script={PROJECT / 'Content/Python/author_d04_01_content.py'}",
              "-EnablePlugins=PythonScriptPlugin", "-unattended", "-nullrhi", "-nosound", "-nop4",
              "-stdout", "-FullStdOutLogOutput", f"-AbsLog={engine_log}",
              f"-BiellaContentAuthoringOutput={report}"]
    if verify_mode:
        command.append("-D04VerifyContent")
    return command


def run_child(command, log_path, timeout):
    start = time.monotonic()
    timed_out = False
    with log_path.open("xb") as log:
        process = subprocess.Popen(command, cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                returncode = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                returncode = process.wait(timeout=10)
    return {"command": command, "pid": process.pid, "returncode": returncode, "timed_out": timed_out,
            "timeout_seconds": timeout, "elapsed_seconds": round(time.monotonic() - start, 3),
            "log": file_identity(log_path)}


def commandlet_report(run, report_path, mode, source_sha):
    require(not run["timed_out"] and run["returncode"] == 0,
            f"D04 {mode} commandlet failed or exceeded its deadline: {run['returncode']}")
    log = Path(run["log"]["path"]).read_text(encoding="utf-8", errors="replace")
    require("D04_CONTENT AUTHORING COMPLETE mode=" + mode in log,
            f"D04 {mode} commandlet completion marker is missing")
    require("Traceback" not in log and "D04_CONTENT AUTHORING FAIL" not in log,
            f"D04 {mode} commandlet reported a Python failure")
    data = json.loads(report_path.read_text(encoding="utf-8"))
    require(data.get("task_id") == "D04-01" and data.get("mode") == mode and data.get("result") == "PASS",
            f"D04 {mode} report is not PASS")
    require(data.get("source_sha256") == source_sha, f"D04 {mode} source SHA does not match editable content")
    return data


def record_failure(error, output):
    event = {"task_id": "D04-01", "time": datetime.now(timezone.utc).isoformat(),
             "type": "runtime_validation", "status": "CONTINUE", "diagnostics": str(error)[:2000],
             "evidence": str(output)}
    try:
        with Path("/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Fresh D04 evidence directory; never overwritten")
    parser.add_argument("--editor", type=Path, default=DEFAULT_EDITOR)
    parser.add_argument("--renderer", choices=("vulkan", "nullrhi"), default="vulkan")
    parser.add_argument("--timeout", type=float, default=300, help="D04 Unreal process deadline")
    parser.add_argument("--population-timeout", type=float, default=300, help="D02 regression process deadline")
    args = parser.parse_args()
    if not 30 < args.timeout <= 900 or not 30 < args.population_timeout <= 900:
        parser.error("timeouts must be greater than 30 and at most 900 seconds")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = (args.output or PROJECT / "Build/D04-01/runs" / f"{stamp}-{args.renderer}-{uuid.uuid4().hex[:8]}").resolve()
    require(not output.exists(), f"Evidence directory already exists: {output}")
    editor = args.editor.resolve()
    account = pwd.getpwnam("unreal") if os.geteuid() == 0 else pwd.getpwuid(os.geteuid())
    ensure_runtime_output(output, account)
    report_path = output / "validation.json"
    source_sha = hashlib.sha256(CONTENT_SOURCE.read_bytes()).hexdigest()
    report = {"task_id": "D04-01", "result": "FAIL", "created_utc": stamp, "output": str(output),
              "renderer": args.renderer, "capture_status": "GENERATED_DRAFT", "source_sha256": source_sha}
    write_json(report_path, report)
    print(f"D04-01 evidence: {report_path}", flush=True)
    try:
        require(editor.is_file(), f"Unreal editor not found: {editor}")
        report["revision"] = source_revision()
        report["source_inputs_before"] = source_inputs(editor)
        report["protected_before"] = [file_identity(path) for path in PROTECTED]
        report["assets_before"] = content_assets()
        write_json(report_path, report)

        author_report_path = output / "authoring.json"
        author_run = runtime_run(
            commandlet_command(editor, account, author_report_path, output / "authoring.engine.log", False),
            output / "authoring.stdout.log", 180)
        report["authoring"] = author_run
        report["authoring_report"] = commandlet_report(author_run, author_report_path, "author", source_sha)
        report["assets_after_author"] = content_assets()
        write_json(report_path, report)

        readback_report_path = output / "readback.json"
        readback_run = runtime_run(
            commandlet_command(editor, account, readback_report_path, output / "readback.engine.log", True),
            output / "readback.stdout.log", 180)
        report["readback"] = readback_run
        report["readback_report"] = commandlet_report(readback_run, readback_report_path, "verify", source_sha)
        report["assets_after_readback"] = content_assets()
        require(report["assets_after_author"] == report["assets_after_readback"],
                "Read-only content readback changed native asset bytes")
        write_json(report_path, report)

        runtime_output = output / "runtime"
        ensure_runtime_output(runtime_output, account)
        runtime_command = _prefix(account) + ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", str(editor),
            str(PROJECT / "BiellaGames.uproject"), "/Game/Maps/BiellaOpenWorldMap", "-game"]
        if args.renderer == "vulkan":
            runtime_command += ["-vulkan", "-NoVSync", "-windowed", "-ResX=1280", "-ResY=720"]
        else:
            runtime_command.append("-nullrhi")
        runtime_command += ["-unattended", "-nosound", "-nosplash", "-stdout", "-FullStdOutLogOutput",
                            f"-AbsLog={runtime_output / 'runtime.engine.log'}",
                            "-ExecCmds=t.MaxFPS 0,r.VSync 0,r.ScreenPercentage 100,r.DynamicRes.OperationMode 0,"
                            "Automation RunTests BiellaGames.D04.ContentRegistry; SoftQuit",
                            f"-BiellaContentOutput={runtime_output}"]
        report["runtime"] = monitor(runtime_command, runtime_output, args.timeout)
        write_json(report_path, report)
        runtime = report["runtime"]
        require(not runtime["timed_out"] and runtime["returncode"] == 0,
                "D04 Unreal runtime failed or exceeded its process deadline")
        require(runtime["log_finalization"]["closed"], "D04 runtime log still has a writer")
        runtime_log = (runtime_output / "runtime.stdout.log").read_text(encoding="utf-8", errors="replace")
        require("**** TEST COMPLETE. EXIT CODE: 0 ****" in runtime_log and
                "Result={Success}" in runtime_log and "Name={ContentRegistry}" in runtime_log,
                "D04 ContentRegistry automation did not complete successfully")
        require(not any(marker in runtime_log for marker in (
            "Result={Fail}", "Fatal error:", "Assertion failed:", "Ensure condition failed:",
            "D04_CONTENT VALIDATION", "D04_CONTENT REGISTRY_REJECTED", "D04_CONTENT POPULATION_REJECTED",
            "D04_CONTENT SPAWN_REJECTED")), "D04 runtime reported a hard content/test failure")
        reject_material_fallbacks(runtime_log)

        population_output = output / "population"
        population_command = [sys.executable, str(PROJECT / "tests/run_d02_02.py"), "--output", str(population_output),
                              "--count", "4", "--renderer", args.renderer]
        report["population_runner"] = run_child(population_command, output / "population.runner.log",
                                                 args.population_timeout)
        population_run = report["population_runner"]
        require(not population_run["timed_out"] and population_run["returncode"] == 0,
                "Preserved D02 population regression failed")

        environment_output = output / "environment"
        environment_command = [sys.executable, str(PROJECT / "tests/run_d02_04.py"),
                               "--output", str(environment_output)]
        report["environment_runner"] = run_child(environment_command, output / "environment.runner.log",
                                                   args.timeout)
        environment_run = report["environment_runner"]
        require(not environment_run["timed_out"] and environment_run["returncode"] == 0,
                "Preserved D02 environment regression failed")
        report["environment_validation"] = json.loads(
            (environment_output / "validation.json").read_text(encoding="utf-8"))
        require(report["environment_validation"].get("result") == "PASS",
                "D02 environment regression report is not PASS")

        shared_output = output / "shared"
        shared_command = [sys.executable, str(PROJECT / "tests/run_d02_01_shared_regression.py"),
                          "--output", str(shared_output)]
        report["shared_runner"] = run_child(shared_command, output / "shared.runner.log", args.timeout)
        shared_run = report["shared_runner"]
        require(not shared_run["timed_out"] and shared_run["returncode"] == 0,
                "Preserved shared-gameplay regression failed")
        report["shared_validation"] = json.loads(
            (shared_output / "validation.json").read_text(encoding="utf-8"))
        require(report["shared_validation"].get("result") == "PASS",
                "Shared-gameplay regression report is not PASS")
        report["verification"] = verify(runtime_output, population_output, args.renderer)
        report["assets_after_runtime"] = content_assets()
        report["source_inputs_after"] = source_inputs(editor)
        report["protected_after"] = [file_identity(path) for path in PROTECTED]
        require(report["source_inputs_before"] == report["source_inputs_after"],
                "D04 source/module/map inputs changed during validation")
        require(report["assets_after_readback"] == report["assets_after_runtime"],
                "Runtime changed authored D04 asset bytes")
        require(report["protected_before"] == report["protected_after"],
                "Canonical protected task metadata changed during validation")
        report["result"] = "PASS"
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
        record_failure(error, output)
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(report_path, report)
    print(json.dumps({"task_id": "D04-01", "result": report["result"], "validation": str(report_path),
                      "error": report.get("error")}, indent=2), flush=True)
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
