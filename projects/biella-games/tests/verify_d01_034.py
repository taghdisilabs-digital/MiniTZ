#!/usr/bin/env python3
"""Validate live D01-034 objective-manager evidence emitted by Unreal."""
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
    require(re.search(r"Result=\{Success\}.*Name=\{ObjectiveManager\}", content),
            "ObjectiveManager did not report Unreal automation success")
    require(not re.search(r"D01_034_TEST FAIL|Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:", content),
            "Runtime reported an assertion, ensure, fatal error or failed test")
    phases = re.findall(r"D01_034_TEST PASS phase=(\w+)", content)
    require(phases == ["activation", "progress", "success"],
            f"Unexpected objective phases: {phases}")
    complete = re.search(
        r"D01_034_TEST COMPLETE id=(\w+) version=(\d+) condition=(\w+) target=(\d+) progress=(\d+) authority=server",
        content,
    )
    require(complete, "Missing complete authoritative objective scenario")
    objective_id, version, condition, target, progress = complete.groups()
    require(objective_id == "Demo01ClearArena" and version == "1" and
            condition == "infected_remaining_zero" and target == progress and int(target) >= 2,
            "Objective success did not satisfy the executable clear-arena condition")
    require("D01_SIGNAL OBJECTIVE_ACTIVATED" in content and
            "D01_SIGNAL OBJECTIVE_SUCCESS" in content,
            "Missing objective activation/success runtime signals")
    return {
        "log": str(path),
        "result": "PASS",
        "phases": phases,
        "objective_id": objective_id,
        "version": int(version),
        "condition": condition,
        "target_count": int(target),
        "progress_count": int(progress),
    }


if __name__ == "__main__":
    try:
        require(len(sys.argv) > 1, "usage: verify_d01_034.py LOG [LOG ...]")
        print(json.dumps({"task_id": "D01-034", "runs": [verify(Path(p)) for p in sys.argv[1:]]}, indent=2))
    except (AssertionError, OSError) as error:
        print(json.dumps({"task_id": "D01-034", "result": "FAIL", "error": str(error)}))
        sys.exit(1)
