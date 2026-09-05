#!/usr/bin/env python3
"""Validate live D01-036 deterministic restart/reset evidence emitted by Unreal."""
import json
import re
import sys
from pathlib import Path


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def verify(path: Path):
    content = path.read_text(encoding="utf-8", errors="replace")
    require("**** TEST COMPLETE. EXIT CODE: 0 ****" in content,
            "Unreal automation did not exit successfully")
    require(re.search(r"Result=\{Success\}.*Name=\{RestartReset\}", content),
            "RestartReset did not report Unreal automation success")
    require(not re.search(
        r"D01_036_TEST FAIL|Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:",
        content), "Runtime reported an assertion, ensure, fatal error or failed test")
    phases = re.findall(r"D01_036_TEST PASS phase=(\w+)", content)
    require(phases == ["terminal_failure", "restart_request", "clean_match"],
            f"Unexpected restart phases: {phases}")
    requested = re.findall(
        r"D01_SIGNAL RESTART_REQUESTED map=(\S+) previous_phase=(\d+) restart_count=(\d+) authority=server",
        content)
    require(requested, "Missing authoritative restart request signal")
    complete = re.search(
        r"D01_036_TEST COMPLETE restart_count=(\d+) phase=Active objective=Demo01ClearArena "
        r"target=(\d+) progress=(\d+) infected_remaining=(\d+) player_alive=true "
        r"player_health=([0-9.]+) rival_alive=true pressure=([0-9.]+) authority=server",
        content)
    require(complete, "Missing complete clean-match restart scenario")
    restart_count, target, progress, remaining, health, pressure = complete.groups()
    require((restart_count, target, progress, remaining) == (requested[-1][2], "2", "0", "2"),
            "Restarted objective or roster did not return to its clean baseline")
    require(float(health) == 100.0 and float(pressure) == 0.0,
            "Restarted player or arena pressure did not return to baseline")
    return {
        "log": str(path),
        "result": "PASS",
        "phases": phases,
        "restart_count": int(restart_count),
        "objective_target": int(target),
        "objective_progress": int(progress),
        "infected_remaining": int(remaining),
        "player_health": float(health),
        "arena_pressure": float(pressure),
        "game_phase": "Active",
        "authority": "server",
    }


if __name__ == "__main__":
    try:
        require(len(sys.argv) > 1, "usage: verify_d01_036.py LOG [LOG ...]")
        print(json.dumps({"task_id": "D01-036", "runs": [verify(Path(p)) for p in sys.argv[1:]]}, indent=2))
    except (AssertionError, OSError) as error:
        print(json.dumps({"task_id": "D01-036", "result": "FAIL", "error": str(error)}))
        sys.exit(1)
