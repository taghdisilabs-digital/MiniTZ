"""Bounded revision-10 qualification. Never boots the disk image."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
SANDBOX = REPO.parents[1]
sys.path.insert(0, str(REPO / "src"))
from minitz_os.source import source_manifest

TESTS = [
    "tests/test_minitz_accessibility_capabilities.py",
    "tests/test_minitz_capability_surface.py",
    "tests/test_minitz_source_release.py",
    "tests/test_minitz_boot_image.py",
    "tests/test_minitz_progressive_truth.py::test_current_boot_artifact_is_exact_source_bound_and_never_falls_back_to_old_output",
    "tests/test_minitz_progressive_truth.py::test_model_completion_for_system_qualification_requires_current_material_artifact",
    "tests/test_minitz_progressive_truth.py::test_system_qualification_does_not_wait_for_runtime_boot_proof",
    "tests/test_production_runner.py::test_local_qwen_parallelism_defaults_to_one_without_explicit_runtime_capacity",
    "tests/test_production_runner.py::test_commander_resident_local_model_uses_runtime_parallelism",
]

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def container(image, entrypoint="python3"):
    return ["docker", "run", "--rm", "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,exec,nosuid,nodev", "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "PYTHONPATH=/workspace/repo/src:/workspace/repo/ops/local-ai",
        "--mount", f"type=bind,src={REPO},dst=/workspace/repo,readonly",
        "--mount", f"type=bind,src={SANDBOX}/state/image-build/validation,dst=/image,readonly",
        "--mount", f"type=bind,src={SANDBOX}/state/validation/startup-foundation-venv,dst=/state/validation/startup-foundation-venv,readonly",
        "--mount", f"type=bind,src={SANDBOX}/state/task-program/TASK_PROGRAM.json,dst=/state/task-program/TASK_PROGRAM.json,readonly",
        "--workdir", "/workspace/repo", "--entrypoint", entrypoint, image]

def run(name, label=None):
    before = source_manifest(REPO)
    tag = (SANDBOX / "state/image-build/rootfs-image-tag").read_text().strip()
    if name == "build":
        command = ["bash", str(REPO / "ops/workstation/minitz-os-sandbox/build-image.sh")]
    elif name == "structural":
        candidate = json.loads((SANDBOX / "state/image-build/candidate.json").read_text())
        assert candidate["source_sha256"] == before["source_sha256"]
        command = ["bash", str(REPO / "ops/workstation/minitz-os-sandbox/validate-image.sh"), candidate["image_path"]]
    elif name == "affected":
        command = container("minitz-os-lab:ubuntu26.04", "/state/validation/startup-foundation-venv/bin/python")
        command += ["-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *TESTS]
    else:
        script = {"clean-target": "MINITZ-SYSTEM-QUALIFY-01-r10/clean_target.py",
            "payload": "MINITZ-SYSTEM-QUALIFY-01-r6/image_payload.py",
            "preinstall": "MINITZ-SYSTEM-QUALIFY-01-r10/preinstall.py"}[name]
        command = container(tag) + ["-B", "/workspace/repo/docs/evidence/" + script]
    label = label or name
    log = OUT / (label + ".log")
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with log.open("x") as stream:
        completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    record = {"task_ref": "task://minitz/MINITZ-SYSTEM-QUALIFY-01/10", "command": command,
        "started_at": started, "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "returncode": completed.returncode, "source_sha256": before["source_sha256"],
        "source_unchanged": source_manifest(REPO)["source_sha256"] == before["source_sha256"],
        "log": str(log.relative_to(REPO)), "log_sha256": digest(log), "image_boot_executed": False}
    if name == "affected":
        record["test_files_sha256"] = {p: digest(REPO / p) for p in sorted({t.split("::")[0] for t in TESTS})}
    (OUT / (label + "-run.json")).write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    print(log.read_text()[-2000:])
    return completed.returncode

if __name__ == "__main__":
    raise SystemExit(run(*sys.argv[1:]))
