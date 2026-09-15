"""Read-only material readback for the owner-authorized frozen closure cycle.

Run in the Ubuntu 26.04 sandbox with the exact inputs mounted read-only.
This records observations; it never updates Task Program status or receipts.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
SANDBOX = REPO.parents[1]
PROGRAM = SANDBOX / "state/task-program/TASK_PROGRAM.json"
TASK = "MINITZ-FINAL-CLOSURE-01"
TASK_SHA = "d5fff2506163cd5389093153513d6a9bda5eb7ad1077faf7b343c227804495b8"
PROGRAM_SHA = "5e35ce190dddeed89ad6f4045c55ee061ee7ae5a2af87c9a87a3100adf376a57"
SOURCE_SHA = "07fc3844ab80c41d8bc6e4825386a3491a8de0347428b56eeabb2cc838d781e9"
IMAGE_SHA = "2353fbe2c932c43120938bcd27ca103f231825f2f978741078e9ce12f73a1080"
QUAL = REPO / "docs/evidence/MINITZ-SYSTEM-QUALIFY-01-r7"
sys.path[:0] = [str(REPO / "src"), str(REPO / "ops/local-ai")]

import minitz_task_program as task_program
from minitz_completion_truth import (
    owner_acceptance_matches_current, runtime_boot_proof_matches_current,
)
from minitz_os.boot_artifact import inspect_current_boot_artifact
from minitz_os.source import source_manifest, verify_source


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ref(path):
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    require(sha(PROGRAM) == PROGRAM_SHA, "Task Program changed; refresh exact task boundary")
    program = task_program.load(PROGRAM)
    final = task_program.task_by_id(program, TASK)
    require(program["revision"] == 127, "Program revision mismatch")
    require(final["revision"] == 8 and final["task_record_sha256"] == TASK_SHA
            and task_program.task_digest(final) == TASK_SHA, "Task identity mismatch")
    require(final["status"] == "WORKING", "Unexpected task status")
    require(program["tasks"][-1]["task_id"] == TASK, "Task is not final boundary")
    predecessors = program["tasks"][:-1]
    require(len(predecessors) == 35 and all(t["status"] in task_program.COMPLETE_STATUSES
            for t in predecessors), "Incomplete predecessor")
    require(task_program.current_task(program)["task_id"] == TASK, "Wrong current task")
    require(program["intended_final_task_program_count"] == 1
            and program["task_program_authority"] is True, "Task authority mismatch")

    direction = program["owner_direction"]["latest_explicit_instruction"]
    require(direction["revision"] == 2 and direction["recorded_at"] ==
            "2026-09-15T21:31:46.120143+00:00", "Owner instruction changed")
    require(SOURCE_SHA in direction["authorized_operation"] and
            IMAGE_SHA in direction["authorized_operation"], "Frozen pair not owner-authorized")

    live = source_manifest(REPO)
    require(verify_source(REPO, live)["source_sha256"] == live["source_sha256"], "Live source failed verification")
    artifact = inspect_current_boot_artifact(REPO, SANDBOX)
    require(artifact["state"] == "CURRENT_VERIFIED", "Current artifact verification failed")
    require((artifact["source_sha256"], artifact["image_sha256"]) ==
            (SOURCE_SHA, IMAGE_SHA), "Artifact differs from owner-authorized pair")
    with Path(artifact["image_path"]).open("rb") as stream:
        stream.seek(510)
        require(stream.read(2) == b"\x55\xaa" and stream.read(8) == b"EFI PART",
                "Raw image MBR/GPT magic mismatch")
    installed_manifest_path = SANDBOX / "system/current/etc/minitz/source.json"
    installed_manifest = read(installed_manifest_path)
    installed_path = SANDBOX / "system/current/opt/minitz/source"
    installed = verify_source(installed_path, installed_manifest)
    frozen = read(QUAL / "current-source.json")
    require(installed["source_sha256"] == frozen["source_sha256"] == SOURCE_SHA,
            "Installed or qualified source differs from frozen release")
    require(installed_manifest["files"] == frozen["files"] and len(frozen["files"]) == 195,
            "Installed source files differ from qualified release")
    require(frozen["source_authority"] == "source-library://minitz/main" and
            frozen["base_os"] == "Ubuntu 26.04" and
            frozen["private_state_included"] is False and
            frozen["credential_values_included"] is False, "Release source contract mismatch")

    runtime_path = SANDBOX / "state/image-build/runtime-boot.json"
    runtime = read(runtime_path)
    require(runtime_boot_proof_matches_current(SANDBOX, artifact), "Runtime proof mismatch")
    require(owner_acceptance_matches_current(program, artifact), "Owner receipt mismatch")
    owner = task_program.task_by_id(program, "MINITZ-OWNER-ACCEPTANCE-01")
    require(any(e.startswith("OWNER_EXPLICIT_ACCEPTANCE:") and "passed" in e
                for e in owner["completion"]["evidence"]), "Explicit owner acceptance absent")

    qualification = read(REPO / "docs/evidence/MINITZ-SYSTEM-QUALIFY-01.validation.json")
    index_path = QUAL / "evidence-index.json"
    require(sha(index_path) == qualification["evidence_index_sha256"], "Qualification index changed")
    require(qualification["quality_verdict"] == "PASS" and not qualification["remaining_work"],
            "Qualification has unfinished work")
    require(qualification["boot_artifact"]["image_sha256"] == IMAGE_SHA,
            "Qualification binds a different image")
    reused = []
    for entry in read(index_path)["files"]:
        if entry["classification"] != "CURRENT_NONBOOT_QUALIFICATION_EVIDENCE":
            continue
        path = QUAL / entry["path"]
        require(sha(path) == entry["sha256"] and path.stat().st_size == entry["bytes"],
                f"Qualification evidence changed: {entry['path']}")
        reused.append(ref(path))
        if path.name.endswith("-run.json"):
            require(read(path)["returncode"] == 0, f"Cited qualification run failed: {path.name}")
    failures = read(QUAL / "failure-dispositions.json")
    require(all(d["state"] in {"REPAIRED", "HISTORICAL_ONLY"} for d in failures["dispositions"]),
            "Unresolved qualification defect")
    observations = read(QUAL / "nonboot-observations.json")
    require(observations["image_payload"]["state"] == "PASS" and
            observations["image_payload"]["source_sha256"] == SOURCE_SHA,
            "Embedded source qualification mismatch")

    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip()
    remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=REPO, text=True).strip()
    require(branch == "main" and remote == "https://github.com/taghdisilabs-digital/MiniTZ.git",
            "Canonical Git identity mismatch")
    os_release = Path("/etc/os-release").read_text()
    require('VERSION_ID="26.04"' in os_release, "Readback must run in Ubuntu 26.04")
    require(sha(PROGRAM) == PROGRAM_SHA, "Task Program changed during readback")
    require(source_manifest(REPO)["source_sha256"] == live["source_sha256"], "Source changed during readback")
    report = {
        "schema": "minitz.final_closure_material_readback/v1", "authority": "NONE",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "task_id": TASK, "task_revision": 8, "task_sha256": TASK_SHA,
        "task_status_observed": final["status"], "program_revision": 127, "program": ref(PROGRAM),
        "predecessors": [{"task_id": t["task_id"], "status": t["status"],
                          "task_sha256": t["task_record_sha256"]} for t in predecessors],
        "owner_frozen_release_instruction": direction, "single_os_contract": program["single_os_contract"],
        "artifact": artifact, "raw_image_format": "MBR_SIGNATURE_AND_GPT_MAGIC_VERIFIED",
        "live_source_sha256": live["source_sha256"], "frozen_release_source_sha256": SOURCE_SHA,
        "newer_source_disposition": "NEXT_CYCLE_PER_EXPLICIT_OWNER_INSTRUCTION",
        "installed": {**installed, "source_path": str(installed_path), "manifest": ref(installed_manifest_path)},
        "runtime_boot": {"record": runtime, "record_ref": ref(runtime_path),
                         "log_ref": ref(Path(runtime["log_path"])), "exact_match": True},
        "owner_acceptance": {"task_id": owner["task_id"], "task_revision": owner["revision"],
                             "task_sha256": owner["task_record_sha256"], "completion": owner["completion"],
                             "exact_match": True},
        "qualification": {"report": ref(REPO / "docs/evidence/MINITZ-SYSTEM-QUALIFY-01.validation.json"),
                          "index": ref(index_path), "reused_evidence_readback": reused,
                          "image_payload": observations["image_payload"],
                          "capability_scope": observations["capability_readiness_scope"],
                          "failure_dispositions": failures},
        "git": {"branch": branch, "origin": remote}, "verification_os": os_release,
        "material_conditions": {"predecessors_complete": True, "current_artifact_verified": True,
                                "runtime_boot_exact": True, "explicit_owner_acceptance_exact": True,
                                "installed_source_exact": True},
        "unresolved_critical_gaps": [], "scope": "Owner-authorized frozen release cycle",
        "image_boot_executed": False, "task_program_mutated": False,
        "quality_verdict": "PASS",
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
