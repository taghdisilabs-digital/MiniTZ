from __future__ import annotations

import os
from pathlib import Path

from minitz_os.capabilities import CapabilitySurface
from minitz_os.operator import OperatorSurface
from minitz_os.source import (
    build_release,
    install_release,
    provision_first_boot,
    recover_installation,
    source_manifest,
)
from minitz_task_program import file_sha256, load, task_by_id, task_digest


ROOT = Path(__file__).resolve().parents[1]
_MOUNTED_TASK_PROGRAM = Path("/state/task-program/TASK_PROGRAM.json")
TASK_PROGRAM = Path(os.environ["MINITZ_TASK_PROGRAM_PATH"]) if "MINITZ_TASK_PROGRAM_PATH" in os.environ else (
    _MOUNTED_TASK_PROGRAM if _MOUNTED_TASK_PROGRAM.is_file() else Path("/root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json")
)
TASK_ID = "MINITZ-OWNER-ACCEPTANCE-01"


def test_owner_acceptance_clean_target_is_usable_capable_recoverable_and_controlled(
    tmp_path: Path,
) -> None:
    program_before = file_sha256(TASK_PROGRAM)
    program = load(TASK_PROGRAM)
    task = task_by_id(program, TASK_ID)
    task_revision = int(task["revision"])
    task_sha256 = task_digest(task)
    assert task["task_record_sha256"] == task_sha256

    manifest = source_manifest(ROOT)
    release = build_release(ROOT, tmp_path / "release")
    assert release["source_sha256"] == manifest["source_sha256"]
    assert release["source_files"] == len(manifest["files"])

    system = tmp_path / "clean-target"
    provision_first_boot(
        system,
        task_state={
            "task_id": TASK_ID,
            "task_revision": task_revision,
            "task_sha256": task_sha256,
            "task_program_sha256": program["_observed_sha256"],
        },
        memory_state={"current_task_ref": f"task://minitz/{TASK_ID}"},
        resource_state={"registry_ref": "resource://minitz/registry"},
    )
    installed = install_release(
        Path(release["artifact_path"]), system, release["artifact_sha256"]
    )
    recovered = recover_installation(system)
    assert installed["source_sha256"] == manifest["source_sha256"]
    assert recovered["recovered"] is True
    assert recovered["source"]["source_sha256"] == manifest["source_sha256"]
    assert recovered["continuity"]["task_state"]["task_id"] == TASK_ID
    assert recovered["continuity"]["memory_state"]["current_task_ref"] == f"task://minitz/{TASK_ID}"

    operator = OperatorSurface(ROOT, tmp_path / "operator-state", TASK_PROGRAM).snapshot()
    assert operator["discoverable_command"] == "minitz dashboard"
    assert {section["key"] for section in operator["sections"]} == {
        "tasks",
        "resources",
        "files",
        "apps",
        "browser/computer",
        "memory",
        "health",
        "updates",
        "recovery",
        "evidence",
    }
    capabilities = CapabilitySurface().snapshot()
    namespaces = {item["capability_ref"].split(".", 1)[0] for item in capabilities["capabilities"]}
    assert {"model", "web", "filesystem", "process", "storage", "system"} <= namespaces
    assert file_sha256(TASK_PROGRAM) == program_before
