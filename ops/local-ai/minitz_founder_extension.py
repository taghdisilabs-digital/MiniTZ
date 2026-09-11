from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import minitz_task_program as minitz

_TASK_IDS = (
    "HAL-LINUX-01", "HAL-FOUNDER-01", "TRUST-NODE-01",
    "GPU-RESIDENCY-01", "BOOST-FABRIC-01", "BROWSER-SWARM-01",
    "SYSTEM-QUALIFY-01",
)

def extension_tasks(*, path: Path | None = None) -> list[dict[str, Any]]:
    """Return the canonical OS-native records for the historical founder extension IDs.

    The old insertion extension is retired. These tasks now live directly in the one
    MiniTZ OS Task Program and this module is compatibility/readback only.
    """
    program = minitz.load(path)
    missing = [task_id for task_id in _TASK_IDS if not any(row["task_id"] == task_id for row in program["tasks"])]
    if missing:
        raise ValueError("MiniTZ OS canonical founder tasks are missing: " + ",".join(missing))
    return [deepcopy(minitz.task_by_id(program, task_id)) for task_id in _TASK_IDS]

def apply_extension(*, path: Path | None = None) -> dict[str, Any]:
    """Compatibility no-op. Never reinsert or reorder canonical OS tasks."""
    program = minitz.load(path)
    extension_tasks(path=path)
    return minitz.program_identity(program)
