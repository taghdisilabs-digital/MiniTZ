#!/usr/bin/env python3
"""Recheck D01 shared combat against D02-01's current editable Editor build.

Uses the existing runtime scenario and detailed D01-031 verifier. Each output is
fresh; neither the completed release package nor canonical metadata is written.
This Vulkan run uses normal world ticks and makes no performance claim.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys

from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import identities, monitor
from verify_d01_031 import verify as verify_shared
from verify_d01_039 import require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh exact attempt directory")
    args = parser.parse_args()
    output = args.output.resolve()
    require(not output.exists(), f"Output already exists: {output}")
    account = pwd.getpwnam("unreal") if os.geteuid() == 0 else pwd.getpwuid(os.geteuid())
    ensure_runtime_output(output, account)
    prefix = ["runuser", "-u", account.pw_name, "--"] if os.geteuid() == 0 else []
    protected = [PROJECT.parents[1] / "docs/project-state/03_BIELLA_CURRENT_STATE.md",
                 PROJECT.parents[1] / "docs/project-state/04_BIELLA_ACTIVE_TASK.md",
                 PROJECT / "docs/PRODUCTION.md"]
    tooling = [Path(__file__), PROJECT / "tests/verify_d01_031.py", PROJECT / "tests/verify_d01_039.py"]
    report = {"task_id": "D02-01", "suite": "BiellaGames.Demo01.SharedInteraction", "result": "FAIL",
              "created_utc": datetime.now(timezone.utc).isoformat(), "revision": source_revision(),
              "scope": "Current Linux Development Editor shared-combat regression; normal world ticks; no FPS or package qualification claim",
              "identities_before": identities(DEFAULT_EDITOR),
              "protected_before": [file_identity(path) for path in protected],
              "tooling_before": [file_identity(path) for path in tooling]}
    report_path = output / "validation.json"
    write_json(report_path, report)
    try:
        command = prefix + ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24",
                            str(DEFAULT_EDITOR), str(PROJECT / "BiellaGames.uproject"),
                            "/Game/Maps/BiellaGameplayMap", "-game", "-vulkan", "-NoVSync", "-windowed",
                            "-ResX=1280", "-ResY=720", "-unattended", "-nosound", "-nosplash",
                            "-NoAsyncLoadingThread", "-stdout", "-FullStdOutLogOutput",
                            f"-AbsLog={output / 'runtime.engine.log'}",
                            f"-ExecCmds=Automation RunTests {report['suite']}; SoftQuit"]
        report["runtime"] = monitor(command, output, 180)
        runtime = report["runtime"]
        require(runtime["timed_out"] is False, "SharedInteraction exceeded its process timeout")
        require(type(runtime["returncode"]) is int and runtime["returncode"] == 0,
                f"Unreal exited {runtime['returncode']}")
        require(runtime["log_finalization"]["closed"], "Runtime log was not finalized")
        log_path = Path(runtime["log"]["path"])
        content = log_path.read_text(encoding="utf-8", errors="replace")
        require(not re.search(r"\bLog\w+:\s*(?:Error|Fatal):|Fatal error:|Assertion failed:|Ensure condition failed:|"
                              r"Result=\{Fail\}|Segmentation fault|Unhandled Exception|D01_\d+_TEST FAIL", content, re.I),
                "Runtime reported an error, failure, assertion or ensure")
        for marker in ("GAME_INSTANCE_READY", "WORLD_READY", "HUD_READY", "CONTROLLER_READY"):
            require(f"D01_SIGNAL {marker}" in content, f"Missing live-world signal: {marker}")
        complete = content.find("D01_031_TEST COMPLETE")
        success = content.find("Result={Success} Name={SharedInteraction} Path={BiellaGames.Demo01.SharedInteraction}")
        exit_marker = content.find("**** TEST COMPLETE. EXIT CODE: 0 ****")
        clean_exit = content.rfind("LogExit: Exiting.")
        require(0 <= complete < success < exit_marker < clean_exit,
                "Scenario, automation and clean exit did not complete in order")
        require("LogVulkanRHI:" in content and "swapchain" in content.lower(), "Missing real Vulkan swapchain")
        report["verification"] = verify_shared(log_path)
        report["identities_after"] = identities(DEFAULT_EDITOR)
        report["protected_after"] = [file_identity(path) for path in protected]
        report["tooling_after"] = [file_identity(path) for path in tooling]
        for group in ("identities", "protected", "tooling"):
            require(report[f"{group}_before"] == report[f"{group}_after"], f"{group} changed during regression")
        report["result"] = "PASS"
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    finally:
        write_json(report_path, report)
    print(json.dumps({"task_id": "D02-01", "suite": report["suite"], "result": report["result"],
                      "validation": str(report_path), "error": report.get("error")}, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
