"""Reproduce bounded non-boot checks in the Ubuntu 26.04 sandbox."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
SANDBOX = REPO.parents[1]
OUT = Path(__file__).resolve().parent
SUITES = {
    "attachments": [
        "tests/test_sandbox_startup_attachments.py", "tests/test_sandbox_production_handoff.py",
        "tests/test_control_gateway.py", "tests/test_minitz_live_projection.py",
    ],
    "core": [
        "tests/test_minitz_source_release.py", "tests/test_minitz_capability_surface.py",
        "tests/test_minitz_boot_image.py", "tests/test_minitz_os_sandbox.py",
        "tests/test_minitz_operator_surface.py", "tests/test_security_privacy.py",
        "tests/test_minitz_secret_boundary.py", "tests/test_minitz_data_residency.py",
        "tests/test_minitz_removed_legacy_authority.py", "tests/test_resource_router.py",
        "tests/test_resource_quality_pressure.py", "tests/test_minitz_workstation_unification.py",
        "tests/test_minitz_connectors_source.py", "tests/test_project_cell_bridge.py",
    ],
    "integration": [
        "tests/test_p2_05_http_adapter.py", "tests/test_p2_06_model_adapter.py",
        "tests/test_p2_07_browser_adapter.py", "tests/test_p3_13_human_browser.py",
        "tests/test_p0_10_p0_integration_qualification.py", "tests/test_p1_06_checkpoint_resume.py",
    ],
}

def run(name):
    suite = name.split("-", 1)[0]
    files = SUITES[suite]
    command = ["docker", "run", "--rm", "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,exec,nosuid,nodev", "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "PYTHONPATH=/workspace/repo/src:/workspace/repo/ops/local-ai",
        "--mount", f"type=bind,src={REPO},dst=/workspace/repo,readonly",
        "--mount", f"type=bind,src={SANDBOX}/state/validation/startup-foundation-venv,dst=/state/validation/startup-foundation-venv,readonly",
        "--mount", f"type=bind,src={SANDBOX}/state/task-program/TASK_PROGRAM.json,dst=/state/task-program/TASK_PROGRAM.json,readonly",
        "--workdir", "/workspace/repo", "--entrypoint", "/state/validation/startup-foundation-venv/bin/python",
        "minitz-os-lab:ubuntu26.04", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *files]
    if suite == "integration":
        command += ["-k", "not type_build_exact_wheel and not real_pinned_chromium and not test_t15 and not test_t16"]
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    sys.path.insert(0, str(REPO / "src"))
    from minitz_os.source import source_manifest
    source = source_manifest(REPO)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log = OUT / (name + ".log")
    if log.exists():
        raise SystemExit("Preserve existing evidence; choose a new attempt name for reruns")
    with log.open("w") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    record = {"command": command, "started_at": started,
        "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "returncode": result.returncode, "source_sha256": source["source_sha256"],
        "source_unchanged": source_manifest(REPO)["source_sha256"] == source["source_sha256"],
        "test_files_sha256": {file: digest(REPO / file) for file in files},
        "log_sha256": digest(log), "log": str(log.relative_to(REPO)),
        "scope": "Non-boot, no external network; reference/model protocol fixtures are not live capability observations"}
    (OUT / (name + "-run.json")).write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))
    print(log.read_text()[-16000:])
    return result.returncode

if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1]))
