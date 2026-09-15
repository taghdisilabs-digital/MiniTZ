"""Full sealed-source non-boot installation and fresh-process recovery probe."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from minitz_os.source import source_manifest, build_signed_update, apply_signed_update, provision_first_boot, verify_source

source = Path("/workspace/repo")
before = source_manifest(source)
result = {"source_sha256": before["source_sha256"], "source_files": len(before["files"]),
    "base_os": Path("/etc/os-release").read_text(), "image_boot_executed": False,
    "scope": "Disposable full-source signed installation and process recovery; no machine boot or service restart",
    "commands": [], "timings_seconds": {}}
with tempfile.TemporaryDirectory(prefix="minitz-qualification-") as temporary:
    work = Path(temporary)
    system = work / "system"
    key = os.urandom(32)
    continuity = provision_first_boot(system,
        task_state={"current_task_ref": "task://minitz/MINITZ-SYSTEM-QUALIFY-01/6"},
        memory_state={"os_index_ref": "memory://minitz/os-index"},
        resource_state={"registry_ref": "resource://minitz/registry"})
    started = time.monotonic()
    release = build_signed_update(source, work / "payload", key)
    assert release["source_sha256"] == before["source_sha256"]
    receipt = Path(release["update_path"])
    first = apply_signed_update(receipt, system, key)
    second = apply_signed_update(receipt, system, key)
    assert first["signed_update"] and second["cache_hit"]
    result["timings_seconds"]["signed_install_and_idempotent_reapply"] = time.monotonic() - started
    result["signed_install"] = result["idempotent_signed_reapply"] = "PASS"
    result["payload_sha256"] = release["artifact_sha256"]
    active = system / "current"
    installed = active / "opt/minitz/source"
    manifest_path = active / "etc/minitz/source.json"
    assert verify_source(installed, json.loads(manifest_path.read_text()))["verified"]
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8", "PYTHONPATH": str(installed / "src"),
        "PYTHONDONTWRITEBYTECODE": "1", "MINITZ_SOURCE_ROOT": str(installed),
        "MINITZ_SOURCE_MANIFEST": str(manifest_path),
        "MINITZ_PROVIDER_REGISTRY": str(installed / "ops/workstation/provider-registry.json"),
        "MINITZ_STATE_ROOT": str(system / "state"),
        "MINITZ_TASK_PROGRAM_PATH": str(work / "absent-task-program.json")}
    def cli(*args):
        started = time.monotonic()
        completed = subprocess.run([sys.executable, "-B", "-S", "-m", "minitz_os", *args],
            cwd=work, env=env, capture_output=True, text=True, timeout=60)
        entry = {"arguments": list(args), "returncode": completed.returncode,
            "elapsed_seconds": time.monotonic() - started,
            "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest()}
        result["commands"].append(entry)
        if completed.returncode:
            raise RuntimeError(json.dumps({**entry, "stderr": completed.stderr}))
        return json.loads(completed.stdout)
    assert cli("source")["source_sha256"] == before["source_sha256"]
    resources = cli("resource", "status")
    result["resource_observation"] = resources
    result["dashboard_observation"] = cli("dashboard", "--json")
    result["doctor_observation"] = cli("doctor", "--json")
    for _ in range(2):
        recovered = cli("recover", "--system-root", str(system))
        assert recovered["recovered"]
        assert recovered["source"]["source_sha256"] == before["source_sha256"]
        assert recovered["continuity"]["continuity_sha256"] == continuity["continuity_sha256"]
    result["fresh_process_recovery"] = "PASS"
    subprocess.run([str(installed / "ops/project-cell/minitz-project-cell"), "--help"],
        cwd=work, env=env, capture_output=True, timeout=30, check=True)
    result["project_cell_entrypoint"] = "PASS"
    compiled = 0
    for relative in before["files"]:
        if relative.endswith(".py"):
            compile((installed / relative).read_bytes(), relative, "exec")
            compiled += 1
    result["python_files_compiled"] = compiled
    assert source_manifest(source)["source_sha256"] == before["source_sha256"]
    result["source_unchanged"] = True
print(json.dumps(result, indent=2))
