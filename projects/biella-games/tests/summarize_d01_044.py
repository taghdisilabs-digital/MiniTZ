#!/usr/bin/env python3
"""Replay three retained D01-44 measurements and persist a compact evidence index.

This derives evidence only. Project task status and publication belong to the
canonical production controller, not this measurement tool.
"""
import argparse
import json
from pathlib import Path
import subprocess

from run_d01_039 import PROJECT, file_identity, write_json
from run_d01_043 import PROTECTED
from run_d01_044 import verify_resources
from verify_d01_039 import require
from verify_d01_044 import verify_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs=3, type=Path, help="720p, 1080p, 720p repeat run directories in order")
    args = parser.parse_args()
    rows, inputs, protected = [], None, None
    for label, directory, width, height in zip(("720p A", "1080p", "720p B"), args.runs,
                                               (1280, 1920, 1280), (720, 1080, 720)):
        directory = directory.resolve()
        report = json.loads((directory / "validation.json").read_text())
        perf = json.loads((directory / "perf.json").read_text())
        require(report["result"] == "PASS" and report["mode"] == "MEASUREMENT", "Run is not an accepted measurement")
        require(perf["requested_seconds"] >= 120 and perf["warmup_seconds"] >= 10, "Measurement floor not met")
        require(report["identities_before"] == report["identities_after"], "Run inputs changed")
        require(report["protected_before"] == report["protected_after"], "Protected bytes changed during run")
        if inputs is None:
            inputs, protected = report["identities_before"], report["protected_before"]
            for identity in inputs + protected:
                require(file_identity(Path(identity["path"])) == identity, "Tested input no longer matches current bytes")
        require(report["identities_before"] == inputs and report["protected_before"] == protected,
                "Runs do not share the same tested inputs/protected metadata")
        for identity in report["evidence"] + report["capture_copies"]:
            require(file_identity(Path(identity["path"])) == identity, "Retained evidence digest changed")
        runtime = report["runtime"]
        require(runtime["returncode"] == 0 and not runtime["watchdog_failure"] and not runtime["survivors"] and
                runtime["log_finalization"]["closed"], "Runtime/exit/log finalization not complete")
        require(len(runtime["unreal_process_identities"]) == 1 and
                runtime["unreal_process_identities"][0]["pid"] == perf["process_id"], "Process attribution differs")
        verification = verify_run(directory, perf["requested_seconds"], width, height, perf["warmup_seconds"])
        resources = verify_resources(directory, perf)
        require(verification == report["verification"] and resources == report["resources"], "Fresh replay differs from retained result")
        require(resources["start_ticks"] == runtime["unreal_process_identities"][0]["start_ticks"], "PID start identity differs")
        frames = verification["frame_time"]["all_measurement"]
        rows.append({"label": label, "validation": file_identity(directory / "validation.json"),
                     "resolution": [width, height], "frames": frames,
                     "simulation_delta": verification["simulation_delta"],
                     "thread_mean_ms": {key: value.get("mean_ms") for key, value in verification["thread_timings"].items()},
                     "resources": resources, "cycles": perf["cycles"], "restarts": perf["restarts"],
                     "measured_gameplay_events": verification["telemetry"],
                     "top_hitches": verification["top_hitches"],
                     "fresh_replay": "PASS"})
    for path in PROTECTED:
        relative = path.relative_to(PROJECT.parents[1])
        require(path.read_bytes() == subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=PROJECT),
                "Protected authority differs from current HEAD")
    build = PROJECT / "Build/Demo01/D01-044-editor-build.log"
    tests = PROJECT / "Build/Demo01/D01-044-verifier-tests-final.log"
    require("Result: Succeeded" in build.read_text(), "Build success missing")
    require("Ran 40 tests" in tests.read_text() and tests.read_text().rstrip().endswith("OK"), "Verifier tests not green")
    regressions = list((PROJECT / "Build/Demo01/D01-044-predecessor-regression").glob("*/validation.json"))
    require(len(regressions) == 1, "Ambiguous predecessor evidence")
    regression = json.loads(regressions[0].read_text())
    require(regression["result"] == "PASS" and len(regression["runs"]) == 2, "Predecessor regression not complete")
    a, b = rows[0]["frames"]["observed_fps"], rows[2]["frames"]["observed_fps"]
    result = {"task_id": "D01-44", "result": "PASS", "scope": "BOUNDED_NATIVE_LINUX_DEVELOPMENT_HOST_MEASUREMENT",
              "total_measured_frames": sum(row["frames"]["count"] for row in rows),
              "total_measured_seconds": sum(row["frames"]["duration_seconds"] for row in rows),
              "720p_repeat_fps_difference_percent_of_pair_mean": abs(a - b) / ((a + b) / 2) * 100,
              "measurements": rows, "tested_inputs": inputs, "protected": protected,
              "build": file_identity(build), "verifier_tests": file_identity(tests),
              "predecessor_regression": file_identity(regressions[0]),
              "analysis_source": file_identity(Path(__file__)),
              "acceptance": file_identity(PROJECT / "Build/Demo01/D01-044-acceptance.md"),
              "validation": {"raw_evidence_replayed": "PASS", "retained_evidence_digests": "PASS",
                             "same_source_content_build_across_runs": "PASS", "current_tested_bytes": "PASS",
                             "protected_metadata_matches_HEAD": "PASS", "adversarial_tests": 40,
                             "predecessor_fresh_processes": 2},
              "canonical_metadata_changed": False, "publication_owner": "Auto Feeder",
              "limitations": ["Linux UnrealEditor -game Development on L40S/Xvfb; no Windows/DX12/package target qualification.",
                              "No FPS/memory budget invented; existing target-tier decisions remain UNKNOWN.",
                              "Asynchronous thread/GPU timings support a limiting-stage inference, not traced pass-level diagnosis.",
                              "One-second OS/device samples can miss subsecond resource peaks; buffer/cache/editor overhead remains included.",
                              "No leak-free, physical latency/scanout, production-scale content or final visual acceptance claim."]}
    output = PROJECT / "Build/Demo01/D01-044-validation.json"
    write_json(output, result)
    print(json.dumps({"result": "PASS", "frames": result["total_measured_frames"],
                      "seconds": result["total_measured_seconds"], "validation": str(output)}, indent=2))


if __name__ == "__main__":
    main()
