#!/usr/bin/env python3
"""Validate live D01-035 player failure-state evidence emitted by Unreal."""
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
    require(re.search(r"Result=\{Success\}.*Name=\{FailureState\}", content),
            "FailureState did not report Unreal automation success")
    require(not re.search(
        r"D01_035_TEST FAIL|Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:",
        content), "Runtime reported an assertion, ensure, fatal error or failed test")
    phases = re.findall(r"D01_035_TEST PASS phase=(\w+)", content)
    require(phases == ["health_zero", "failure"], f"Unexpected failure phases: {phases}")
    complete = re.search(
        r"D01_035_TEST COMPLETE player=(\S+) health=([0-9.]+) phase=Failure "
        r"player_alive=false objective=You_were_defeated objective_success=false authority=server",
        content,
    )
    require(complete, "Missing complete authoritative player failure scenario")
    _, health = complete.groups()
    require(float(health) == 0.0, "Failure scenario did not end at zero player health")
    require("D01_SIGNAL DEFEAT" in content and "D01_SIGNAL PLAYER_FAILURE" in content,
            "Missing player defeat and authoritative failure runtime signals")
    return {
        "log": str(path),
        "result": "PASS",
        "phases": phases,
        "player_health": float(health),
        "game_phase": "Failure",
        "player_alive": False,
        "objective_success": False,
        "authority": "server",
    }


if __name__ == "__main__":
    try:
        require(len(sys.argv) > 1, "usage: verify_d01_035.py LOG [LOG ...]")
        import json
        print(json.dumps({"task_id": "D01-035", "runs": [verify(Path(p)) for p in sys.argv[1:]]}, indent=2))
    except (AssertionError, OSError) as error:
        print(json.dumps({"task_id": "D01-035", "result": "FAIL", "error": str(error)}))
        sys.exit(1)
