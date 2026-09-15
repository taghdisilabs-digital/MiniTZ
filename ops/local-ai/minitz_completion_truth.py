"""Material completion truth for the final MiniTZ OS horizon.

This module does not make tests into a generic progression gate.  It enforces
only material facts already required by the final OS tasks: exact current boot
artifact identity and explicit owner acceptance of that exact artifact.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO_ROOT = Path(os.environ.get("MINITZ_REPO_ROOT") or Path(__file__).resolve().parents[2]).resolve()
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from minitz_os.boot_artifact import inspect_current_boot_artifact
from minitz_os.source import source_manifest, verify_source
import minitz_task_program as minitz

SYSTEM_QUALIFY = "MINITZ-SYSTEM-QUALIFY-01"
OWNER_ACCEPTANCE = "MINITZ-OWNER-ACCEPTANCE-01"
FINAL_CLOSURE = "MINITZ-FINAL-CLOSURE-01"
_MATERIAL_ARTIFACT_TASKS = {SYSTEM_QUALIFY, FINAL_CLOSURE}


def _sandbox_root(repo_root: Path) -> Path:
    configured = os.environ.get("MINITZ_OS_SANDBOX_ROOT")
    if configured:
        return Path(configured).resolve()
    root = Path(repo_root).resolve()
    # canonical checkout: <sandbox>/workspace/repo
    try:
        return root.parents[1]
    except IndexError:
        return Path("/root/attached-storage/minitz-os-sandbox")


def _condition(criterion: str, ref: str) -> str:
    return json.dumps({
        "kind": "CONDITION",
        "criterion": criterion,
        "evidence_ref": ref,
        "verdict": "FAIL",
    }, sort_keys=True, separators=(",", ":"))




def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = json.dumps(dict(value), sort_keys=True, indent=2) + "\n"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _runtime_boot_path(sandbox_root: Path) -> Path:
    return Path(sandbox_root).resolve() / "state/image-build/runtime-boot.json"


def runtime_boot_proof_matches_current(sandbox_root: Path, artifact: Mapping[str, Any]) -> bool:
    path = _runtime_boot_path(sandbox_root)
    if artifact.get("state") != "CURRENT_VERIFIED" or not path.is_file():
        return False
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        log = Path(str(record["log_path"])).resolve()
        marker = f"MINITZ_BOOT_OK source_sha256={artifact['source_sha256']}"
        if not log.is_file():
            return False
        return (
            record.get("schema") == "minitz.runtime-boot-proof/v1"
            and record.get("product") == "MiniTZ OS"
            and record.get("result") == "PASS"
            and record.get("source_sha256") == artifact.get("source_sha256")
            and record.get("image_sha256") == artifact.get("image_sha256")
            and record.get("image_path") == artifact.get("image_path")
            and record.get("marker") == marker
            and record.get("log_sha256") == _file_sha256(log)
            and marker in log.read_text(encoding="utf-8", errors="replace")
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def record_runtime_boot_proof(
    repo_root: Path, sandbox_root: Path, log_path: Path, *, method: str,
) -> dict[str, Any]:
    """Record proof from an already owner-authorized boot; this function never boots an image."""
    allowed_methods = {
        "QEMU_UEFI_OWNER_AUTHORIZED",
        "PHYSICAL_OWNER_BOOT",
        "EXTERNAL_CLEAN_TARGET_OWNER_AUTHORIZED",
    }
    if method not in allowed_methods:
        raise ValueError("runtime boot proof method must be explicitly owner-authorized")
    artifact = inspect_current_boot_artifact(repo_root, sandbox_root)
    if artifact.get("state") != "CURRENT_VERIFIED":
        raise ValueError("runtime boot proof requires exact current verified artifact")
    log = Path(log_path).resolve()
    if not log.is_file():
        raise ValueError("runtime boot proof log is unavailable")
    marker = f"MINITZ_BOOT_OK source_sha256={artifact['source_sha256']}"
    if marker not in log.read_text(encoding="utf-8", errors="replace"):
        raise ValueError("runtime boot proof does not contain the exact current source marker")
    record = {
        "schema": "minitz.runtime-boot-proof/v1",
        "product": "MiniTZ OS",
        "method": method,
        "result": "PASS",
        "source_sha256": artifact["source_sha256"],
        "image_sha256": artifact["image_sha256"],
        "image_path": artifact["image_path"],
        "marker": marker,
        "log_path": str(log),
        "log_sha256": _file_sha256(log),
    }
    _atomic_json(_runtime_boot_path(sandbox_root), record)
    return record


def _owner_markers(evidence: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in evidence:
        text = str(raw)
        for name in ("SOURCE_SHA256", "IMAGE_SHA256", "IMAGE_PATH"):
            prefix = f"OWNER_ACCEPTED_{name}:"
            if text.startswith(prefix):
                result[name] = text[len(prefix):]
    return result


def owner_acceptance_matches_current(program: Mapping[str, Any], artifact: Mapping[str, Any]) -> bool:
    try:
        task = minitz.task_by_id(program, OWNER_ACCEPTANCE)
    except KeyError:
        return False
    if task.get("status") not in minitz.COMPLETE_STATUSES:
        return False
    completion = task.get("completion") if isinstance(task.get("completion"), Mapping) else {}
    evidence = completion.get("evidence") if isinstance(completion.get("evidence"), list) else []
    markers = _owner_markers(tuple(str(item) for item in evidence))
    return (
        markers.get("SOURCE_SHA256") == artifact.get("source_sha256")
        and markers.get("IMAGE_SHA256") == artifact.get("image_sha256")
        and markers.get("IMAGE_PATH") == artifact.get("image_path")
    )


def installed_source_matches_current(repo_root: Path, sandbox_root: Path) -> bool:
    current = Path(sandbox_root).resolve() / "system" / "current"
    source = current / "opt/minitz/source"
    manifest_path = current / "etc/minitz/source.json"
    if not source.is_dir() or not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        installed = verify_source(source, manifest)
    except (OSError, ValueError):
        return False
    return installed.get("source_sha256") == source_manifest(Path(repo_root).resolve())["source_sha256"]


def admit_model_result(
    repo_root: Path,
    sandbox_root: Path,
    task_id: str,
    status: str,
    summary: str,
    evidence: Sequence[str],
    *,
    program_path: Path | None = None,
) -> dict[str, Any]:
    """Admit only materially true model completion; owner acceptance is never model-owned."""
    clean_evidence = tuple(str(item) for item in evidence)
    if status not in {"COMPLETE", "COMPLETE_ALREADY"}:
        return {"status": status, "summary": summary, "evidence": clean_evidence}

    if task_id not in _MATERIAL_ARTIFACT_TASKS | {OWNER_ACCEPTANCE}:
        return {"status": status, "summary": summary, "evidence": clean_evidence}

    if task_id == OWNER_ACCEPTANCE:
        condition = _condition(
            "explicit owner acceptance of the exact current MiniTZ boot artifact",
            "owner://minitz/exact-artifact-acceptance",
        )
        return {
            "status": "CONTINUE",
            "summary": "REQUIRES_OWNER_ACCEPTANCE: exact current artifact must be accepted by the owner, not by a model.",
            "evidence": clean_evidence + (condition,),
        }

    artifact = inspect_current_boot_artifact(repo_root, sandbox_root)
    if task_id in _MATERIAL_ARTIFACT_TASKS and artifact.get("state") != "CURRENT_VERIFIED":
        condition = _condition(
            "exact current source-bound boot artifact is materially present and structurally verified",
            "artifact://minitz/current-boot-image",
        )
        return {
            "status": "CONTINUE",
            "summary": f"MATERIAL_PROOF_REQUIRED: current boot artifact state is {artifact.get('state')}",
            "evidence": clean_evidence + (condition,),
        }

    if task_id == FINAL_CLOSURE and not runtime_boot_proof_matches_current(sandbox_root, artifact):
        condition = _condition(
            "runtime boot proof for the exact current MiniTZ image is required before final closure",
            "artifact://minitz/current-runtime-boot-proof",
        )
        return {
            "status": "CONTINUE",
            "summary": "MATERIAL_PROOF_REQUIRED: exact current runtime boot proof is absent or stale.",
            "evidence": clean_evidence + (condition,),
        }

    if task_id == FINAL_CLOSURE:
        program = minitz.load(program_path)
        if not owner_acceptance_matches_current(program, artifact):
            condition = _condition(
                "owner acceptance is bound to the exact current MiniTZ artifact",
                "owner://minitz/exact-artifact-acceptance",
            )
            return {
                "status": "CONTINUE",
                "summary": "REQUIRES_OWNER_ACCEPTANCE: final closure cannot replace or infer owner acceptance.",
                "evidence": clean_evidence + (condition,),
            }
        if not installed_source_matches_current(repo_root, sandbox_root):
            condition = _condition(
                "installed MiniTZ source is the exact current canonical source",
                "artifact://minitz/installed-source",
            )
            return {
                "status": "CONTINUE",
                "summary": "MATERIAL_PROOF_REQUIRED: installed source does not match current canonical source.",
                "evidence": clean_evidence + (condition,),
            }
    return {"status": status, "summary": summary, "evidence": clean_evidence}


def owner_acceptance_evidence(repo_root: Path, sandbox_root: Path, owner_evidence: Sequence[str]) -> tuple[str, ...]:
    artifact = inspect_current_boot_artifact(repo_root, sandbox_root)
    if artifact.get("state") != "CURRENT_VERIFIED":
        raise ValueError(f"owner acceptance requires exact current verified artifact, got {artifact.get('state')}")
    clean = tuple(str(item).strip() for item in owner_evidence if str(item).strip())
    if not clean:
        raise ValueError("owner acceptance requires explicit owner evidence")
    return clean + (
        f"OWNER_ACCEPTED_SOURCE_SHA256:{artifact['source_sha256']}",
        f"OWNER_ACCEPTED_IMAGE_SHA256:{artifact['image_sha256']}",
        f"OWNER_ACCEPTED_IMAGE_PATH:{artifact['image_path']}",
    )


def reconcile_material_truth(
    repo_root: Path,
    sandbox_root: Path | None = None,
    *,
    program_path: Path | None = None,
) -> dict[str, Any]:
    """Reopen only the invalid final suffix; preserve the valid boot-build history."""
    repo_root = Path(repo_root).resolve()
    sandbox_root = Path(sandbox_root).resolve() if sandbox_root is not None else _sandbox_root(repo_root)
    program_path = Path(program_path or minitz.program_path()).resolve()
    program = minitz.load(program_path)
    artifact = inspect_current_boot_artifact(repo_root, sandbox_root)

    system = minitz.task_by_id(program, SYSTEM_QUALIFY)
    if artifact.get("state") != "CURRENT_VERIFIED":
        evidence = [
            f"Material truth reconciliation: current artifact state={artifact.get('state')}",
            "Historical MINITZ-BOOTABLE-IMAGE-01 completion remains preserved; only the invalid later suffix is reopened.",
        ]
        before_revision = int(program["revision"])
        identity = minitz.reopen_from(SYSTEM_QUALIFY, evidence=evidence, path=program_path)
        changed = int(identity["revision"]) != before_revision
        return {"changed": changed, "reopened_from": SYSTEM_QUALIFY if changed else None, "artifact_state": artifact.get("state")}

    owner = minitz.task_by_id(program, OWNER_ACCEPTANCE)
    if owner.get("status") in minitz.COMPLETE_STATUSES and not owner_acceptance_matches_current(program, artifact):
        minitz.reopen_from(
            OWNER_ACCEPTANCE,
            evidence=["Material truth reconciliation: no explicit owner receipt is bound to the exact current artifact."],
            path=program_path,
        )
        return {"changed": True, "reopened_from": OWNER_ACCEPTANCE, "artifact_state": artifact.get("state")}

    final = minitz.task_by_id(program, FINAL_CLOSURE)
    if final.get("status") in minitz.COMPLETE_STATUSES and (
        artifact.get("state") != "CURRENT_VERIFIED" or not installed_source_matches_current(repo_root, sandbox_root)
    ):
        minitz.reopen_from(
            FINAL_CLOSURE,
            evidence=["Material truth reconciliation: final installed/artifact identity is no longer current."],
            path=program_path,
        )
        return {"changed": True, "reopened_from": FINAL_CLOSURE, "artifact_state": artifact.get("state")}

    return {"changed": False, "reopened_from": None, "artifact_state": artifact.get("state")}
