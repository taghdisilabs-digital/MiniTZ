"""Read-only material readback for owner acceptance revision 6; never boots."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
SANDBOX = REPO.parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "ops/local-ai")]
from minitz_os.boot_artifact import inspect_current_boot_artifact
from minitz_os.source import source_manifest
from minitz_completion_truth import owner_acceptance_matches_current, runtime_boot_proof_matches_current


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    program_path = SANDBOX / "state/task-program/TASK_PROGRAM.json"
    program_sha = sha(program_path)
    program = json.loads(program_path.read_text())
    assert program["revision"] == 111
    assert program_sha == "6e4058865ad8a240c55a43f4be9964b20a8ce62cdee70369dda67ddeace71ca6"
    task = next(t for t in program["tasks"] if t["task_id"] == "MINITZ-OWNER-ACCEPTANCE-01")
    assert (task["revision"], task["task_record_sha256"], task["status"]) == (
        6, "21dd149a0495522c194507c4e047725bb1526e909a2973926f91a8fc0b34b8e5", "WORKING")
    predecessor = next(t for t in program["tasks"] if t["task_id"] == "MINITZ-SYSTEM-QUALIFY-01")
    assert predecessor["status"] == "COMPLETE"
    qualification_path = REPO / "docs/evidence/MINITZ-SYSTEM-QUALIFY-01.validation.json"
    qualification = json.loads(qualification_path.read_text())
    evidence_dir = REPO / qualification["evidence_directory"]
    manifest = source_manifest(REPO)
    assert manifest == json.loads((evidence_dir / "current-source.json").read_text())
    artifact = inspect_current_boot_artifact(REPO, SANDBOX)
    assert artifact["state"] == "CURRENT_VERIFIED"
    assert {k: v for k, v in artifact.items() if k != "current_record_path"} == qualification["boot_artifact"]
    with Path(artifact["image_path"]).open("rb") as stream:
        stream.seek(510)
        assert stream.read(2) == b"\x55\xaa"
        assert stream.read(8) == b"EFI PART"
    index_path = evidence_dir / "evidence-index.json"
    assert sha(index_path) == qualification["evidence_index_sha256"]
    index = {item["path"]: item for item in json.loads(index_path.read_text())["files"]}
    selected = ["current-source.json", "current-artifact.json", "structural-validation.json",
        "structural-restored-run.json", "structural-restored.log", "payload-run.json", "payload.log",
        "affected-r7-run.json", "affected-r7.log", "clean-target-configured-run.json",
        "clean-target-configured.log", "preinstall-run.json", "preinstall.log",
        "nonboot-observations.json", "reuse-bindings.json"]
    verified = []
    for name in selected:
        path = evidence_dir / name
        assert path.stat().st_size == index[name]["bytes"] and sha(path) == index[name]["sha256"], name
        if name.endswith("-run.json"):
            assert json.loads(path.read_text())["returncode"] == 0, name
        verified.append({"path": str(path.relative_to(REPO)), "sha256": sha(path)})
    reuse = json.loads((evidence_dir / "reuse-bindings.json").read_text())
    assert reuse["current_source_sha256"] == manifest["source_sha256"]
    for name, expected in reuse["unchanged_engine_and_gateway_files"].items():
        assert manifest["files"][name] == expected, name
    reused_refs = []

    def verify_refs(value):
        if isinstance(value, dict):
            if {"path", "sha256", "bytes"} <= value.keys():
                path = REPO / value["path"]
                assert sha(path) == value["sha256"] and path.stat().st_size == value["bytes"], str(path)
                reused_refs.append(value["path"])
            for child in value.values():
                verify_refs(child)
        elif isinstance(value, list):
            for child in value:
                verify_refs(child)

    verify_refs(reuse)
    checks_path = Path(__file__).with_name("checks.json")
    checks = json.loads(checks_path.read_text())
    assert checks["returncode"] == 0
    assert (checks["task_id"], checks["task_revision"], checks["task_sha256"], checks["source_sha256"]) == (
        task["task_id"], task["revision"], task["task_record_sha256"], manifest["source_sha256"])
    assert sha(REPO / checks["log"]) == checks["log_sha256"]
    assert sha(REPO / "tests/test_minitz_progressive_truth.py") == checks["test_file_sha256"]
    boot_path = SANDBOX / "state/image-build/runtime-boot.json"
    boot_matches = runtime_boot_proof_matches_current(SANDBOX, artifact)
    boot = None
    if boot_matches:
        record = json.loads(boot_path.read_text())
        assert record["method"] == "EXTERNAL_CLEAN_TARGET_OWNER_AUTHORIZED"
        log = Path(record["log_path"])
        boot = {"record_path": str(boot_path), "record_sha256": sha(boot_path),
            "record": record, "log_bytes": log.stat().st_size,
            "observed_markers": [line for line in log.read_text(errors="replace").splitlines()
                if "MINITZ_BOOT_" in line],
            "scope": "External receipt and log prove boot plus source/resource-registry/dashboard/doctor checks. Registry counts do not prove provider execution or daily-use workflows.",
            "owner_authorization_provenance": "Receipt labels the method EXTERNAL_CLEAN_TARGET_OWNER_AUTHORIZED; this readback did not witness or issue that authorization and grants no new control authority."}
    assert sha(program_path) == program_sha
    print(json.dumps({
        "schema": "minitz.owner_acceptance_input_readback/v1", "authority": "NONE",
        "collector_sha256": sha(Path(__file__)),
        "progression_authority": False, "recorded_at": datetime.now(timezone.utc).isoformat(),
        "task_id": task["task_id"], "task_revision": task["revision"],
        "task_sha256": task["task_record_sha256"], "task_status": task["status"],
        "program_revision": program["revision"], "program_sha256": program_sha,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "source_sha256": manifest["source_sha256"], "source_files_verified": len(manifest["files"]),
        "artifact": artifact, "format_magic": "MBR_SIGNATURE_AND_GPT_EFI_PART_VERIFIED",
        "predecessor": {"task_id": predecessor["task_id"], "revision": predecessor["revision"],
            "task_sha256": predecessor["task_record_sha256"], "status": predecessor["status"],
            "qualification_report": str(qualification_path.relative_to(REPO)),
            "qualification_report_sha256": sha(qualification_path)},
        "verified_evidence": verified, "verified_reuse_refs": sorted(set(reused_refs)),
        "unchanged_reused_engine_gateway_files": len(reuse["unchanged_engine_and_gateway_files"]),
        "focused_checks": {"path": str(checks_path.relative_to(REPO)), "sha256": sha(checks_path),
            "scope": checks["scope"], "returncode": checks["returncode"],
            "log": checks["log"], "log_sha256": checks["log_sha256"]},
        "image_boot_executed_by_this_readback": False,
        "runtime_boot_record_present": boot_path.is_file(),
        "runtime_boot_proof_matches_current": boot_matches, "external_boot_evidence": boot,
        "owner_acceptance_matches_current": owner_acceptance_matches_current(program, artifact),
        "owner_acceptance_receipt": None,
        "predecessor_limitations_at_qualification_time": qualification["limitations"],
        "unmet_criterion": "Clean-target daily operation, actual AI/resource and browser/computer execution, durable memory and update/recovery observations plus explicit owner acceptance remain outstanding; startup proof alone does not establish them.",
        "smallest_next_action": ("Obtain a connection/reference for the external Linux target that produced the boot log, or its existing workflow evidence, to finish the remaining observations and request the owner's artifact-bound decision. Current target availability is unproven. Do not repeat the verified boot."
            if boot_matches else "Obtain explicit owner command to boot this exact raw image in an isolated local target; then collect runtime observations and request the owner's artifact-bound decision."),
        "task_program_unchanged": True,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
