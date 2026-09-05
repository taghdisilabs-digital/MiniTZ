#!/usr/bin/env python3
"""Verify D01-032's live authoritative arena-pressure state scenario."""
import re
import sys
from pathlib import Path


EXPECTED = [
    ("rising", "Rising", "20.0", "1"),
    ("elevated", "Elevated", "50.0", "2"),
    ("critical", "Critical", "85.0", "3"),
    ("reset", "Inactive", "0.0", "4"),
]


def verify(path: Path):
    content = path.read_text(encoding="utf-8", errors="replace")
    assert "D01_032_TEST" in content, "D01-032 runtime test emitted no evidence"
    assert "D01_032_TEST COMPLETE id=Demo01ArenaPressure transitions=4 revisions=1,2,3,4 authority=server" in content
    assert "**** TEST COMPLETE. EXIT CODE: 0 ****" in content, "automation did not exit successfully"
    assert "ARENA_PRESSURE_REJECTED reason=non_finite" in content, "invalid input guard was not exercised"

    states = re.findall(
        r"D01_032_TEST STATE phase=(\w+) id=(\w+) state=(\w+) level=([0-9.]+) revision=(\d+) authority=(\w+)",
        content,
    )
    assert [(phase, state, level, revision) for phase, _, state, level, revision, authority in states
            if authority == "server"] == EXPECTED, f"unexpected transitions: {states}"
    assert states and {identity for _, identity, *_ in states} == {"Demo01ArenaPressure"}
    return {"log": str(path), "result": "PASS", "transitions": len(states), "identity": "Demo01ArenaPressure"}


if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            raise AssertionError("usage: verify_d01_032.py LOG")
        print({"task": "D01-032", "runs": [verify(Path(arg)) for arg in sys.argv[1:]]})
    except (AssertionError, OSError) as error:
        print({"task": "D01-032", "result": "FAIL", "error": str(error)})
        sys.exit(1)
