#!/usr/bin/env python3
"""Validate live D01-033 response evidence; assertions execute in Unreal."""
import json
import math
import re
import sys
from pathlib import Path


EXPECTED_PHASES = [
    "baseline_chase", "rising_no_spawn", "blocked_spawn",
    "downgrade_cancels_retry", "unblocked_retry", "elevated_chase",
    "critical_two_slots", "late_consumers", "reset_restores_baseline",
    "defeated_stays_stopped", "no_duplicates_or_refill",
]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def verify(path: Path):
    content = path.read_text(encoding="utf-8", errors="replace")
    require("**** TEST COMPLETE. EXIT CODE: 0 ****" in content,
            "Unreal automation did not exit successfully")
    require(re.search(r"Result=\{Success\}.*Name=\{PressureResponses\}", content),
            "PressureResponses did not report Unreal automation success")
    require(not re.search(r"D01_033_TEST FAIL|Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:", content),
            "Runtime reported an assertion, ensure, fatal error or failed test")
    phases = re.findall(r"D01_033_TEST PASS phase=(\w+)", content)
    require(phases == EXPECTED_PHASES, f"Unexpected acceptance phases: {phases}")
    require("D01_033_TEST COMPLETE id=Demo01ArenaPressure" in content,
            "Missing complete canonical pressure scenario")
    require("D01_033_TEST RECONSTRUCTION navigation=true floor_collision=true" in content,
            "Reload did not restore real floor collision and navigation")
    require("D01_033_TEST ENCLOSED_CAPSULE simple_blocked=true" in content,
            "Solid containment placement guard was not exercised")

    measurement = re.search(
        r"D01_033_TEST MOVEMENT baseline_cm=([\d.]+) baseline_s=([\d.]+) "
        r"elevated_cm=([\d.]+) elevated_s=([\d.]+) velocity_ratio=([\d.]+) base_speed=([\d.]+)",
        content,
    )
    require(measurement, "Missing measured world-tick displacement")
    baseline, baseline_s, elevated, elevated_s, ratio, base_speed = map(float, measurement.groups())
    require(all(math.isfinite(v) and v > 0 for v in (baseline, baseline_s, elevated, elevated_s, ratio)),
            "Invalid displacement measurement")
    actual_ratio = (elevated / elevated_s) / (baseline / baseline_s)
    require(baseline > 100 and elevated > 100 and base_speed == 210.0,
            "Movement samples lack real baseline movement or changed base tuning")
    require(1.15 < actual_ratio < 1.35 and abs(actual_ratio - ratio) < 0.005,
            "Elevated pressure did not increase measured movement consistently")

    transitions = re.findall(
        r"D01_SIGNAL ARENA_PRESSURE_TRANSITION id=(\w+) previous=\w+ state=\w+ "
        r"level=([\d.]+) revision=(\d+).*authority=server", content,
    )
    require(transitions, "No authoritative transitions")
    lights = re.findall(r"D01_SIGNAL PRESSURE_LIGHT id=(\w+) revision=(\d+) level=([\d.]+) intensity=([\d.]+)", content)
    movement = re.findall(r"D01_SIGNAL PRESSURE_MOVEMENT id=(\w+) revision=(\d+) actor=\S+ level=([\d.]+)", content)
    for identity, level, revision in transitions:
        require(identity == "Demo01ArenaPressure", "Multiple pressure authorities")
        require(any(i == identity and r == revision and value == level and
                    abs(float(intensity) - (900 + 17 * float(level))) < 0.1
                    for i, r, value, intensity in lights),
                f"Transition {revision} did not reach the actual light")
        require((identity, revision, level) in movement,
                f"Transition {revision} did not reach infected movement")

    spawns = re.findall(
        r"D01_SIGNAL PRESSURE_SPAWN id=(\w+) revision=(\d+) level=([\d.]+) "
        r"slot=(\d+) actor=(\S+) count=(\d+).*authority=server", content,
    )
    require(len(spawns) == 2 and [s[3] for s in spawns] == ["0", "1"] and
            [s[5] for s in spawns] == ["1", "2"] and len({s[4] for s in spawns}) == 2,
            f"Spawns were not two distinct, once-only slots: {spawns}")
    for identity, revision, level, *_ in spawns:
        require((identity, level, revision) in transitions,
                "Spawn did not derive from an authoritative transition")
    require(re.search(r"PRESSURE_SPAWN_DEFERRED .*slot=0 reason=collision", content),
            "Occupied spawn collision safety was not exercised")
    return {
        "log": str(path), "result": "PASS", "phases": phases,
        "identity": "Demo01ArenaPressure", "transitions": len(transitions),
        "spawn_count": len(spawns), "baseline_cm": baseline,
        "baseline_seconds": baseline_s, "elevated_cm": elevated,
        "elevated_seconds": elevated_s, "velocity_ratio": ratio,
    }


if __name__ == "__main__":
    try:
        require(len(sys.argv) > 1, "usage: verify_d01_033.py LOG [LOG ...]")
        print(json.dumps({"task_id": "D01-033", "runs": [verify(Path(p)) for p in sys.argv[1:]]}, indent=2))
    except (AssertionError, OSError) as error:
        print(json.dumps({"task_id": "D01-033", "result": "FAIL", "error": str(error)}))
        sys.exit(1)
