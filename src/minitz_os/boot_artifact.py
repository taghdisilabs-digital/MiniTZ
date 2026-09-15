"""Exact current boot-artifact authority for MiniTZ OS.

Historical image bytes may remain for provenance, but only the atomically
published current record can represent the current boot artifact.  The record
is source-bound and is never reconstructed by scanning output directories.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .source import source_manifest

CURRENT_SCHEMA = "minitz.current-boot-artifact/v1"
CANDIDATE_SCHEMA = "minitz.boot-artifact-candidate/v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"unreadable MiniTZ artifact record: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"invalid MiniTZ artifact record: {path}")
    return value


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
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


def _state_root(sandbox_root: Path) -> Path:
    return Path(sandbox_root).resolve() / "state" / "image-build"


def _current_source_sha(repo_root: Path) -> str:
    return str(source_manifest(Path(repo_root).resolve())["source_sha256"])


def _validate_build(build: Mapping[str, Any], *, source_sha: str, image: Path) -> None:
    if build.get("schema") != "minitz.boot_image_build/v1" or build.get("product") != "MiniTZ OS":
        raise ValueError("boot build record contract mismatch")
    if build.get("source_sha256") != source_sha:
        raise ValueError("boot build source does not match exact current source")
    if build.get("bootable_disk_image") is not True:
        raise ValueError("boot build is not a bootable disk image")
    if not image.is_file():
        raise ValueError("boot image is unavailable")
    digest = _sha256(image)
    if build.get("image_sha256") != digest:
        raise ValueError("boot build image digest mismatch")
    if int(build.get("image_bytes") or -1) != image.stat().st_size:
        raise ValueError("boot build image size mismatch")


def stage_boot_artifact_candidate(repo_root: Path, sandbox_root: Path, image_path: Path, build_path: Path) -> dict[str, Any]:
    """Stage exact built bytes for validation without making them current."""
    repo_root = Path(repo_root).resolve()
    sandbox_root = Path(sandbox_root).resolve()
    image = Path(image_path).resolve()
    build_path = Path(build_path).resolve()
    source_sha = _current_source_sha(repo_root)
    build = _load_json(build_path)
    _validate_build(build, source_sha=source_sha, image=image)
    record = {
        "schema": CANDIDATE_SCHEMA,
        "product": "MiniTZ OS",
        "state": "CANDIDATE_UNVALIDATED",
        "source_sha256": source_sha,
        "image_path": str(image),
        "image_sha256": str(build["image_sha256"]),
        "image_bytes": image.stat().st_size,
        "build_record_path": str(build_path),
        "build_record_sha256": _sha256(build_path),
    }
    state = _state_root(sandbox_root)
    _atomic_json(state / "candidate.json", record)

    # A record bound to a different source is no longer current.  Historical
    # image bytes remain provenance, but stale current authority is removed.
    current_path = state / "current.json"
    if current_path.is_file():
        try:
            current = _load_json(current_path)
        except ValueError:
            current = {}
        if current.get("source_sha256") != source_sha:
            current_path.unlink(missing_ok=True)
    return record


def publish_validated_boot_artifact(
    repo_root: Path,
    sandbox_root: Path,
    image_path: Path,
    build_path: Path,
    validation_path: Path,
) -> dict[str, Any]:
    """Atomically publish one exact validated current image.

    No directory scan, timestamp choice, filename fallback, or older build may
    become current through this function.
    """
    repo_root = Path(repo_root).resolve()
    sandbox_root = Path(sandbox_root).resolve()
    image = Path(image_path).resolve()
    build_path = Path(build_path).resolve()
    validation_path = Path(validation_path).resolve()
    source_sha = _current_source_sha(repo_root)
    build = _load_json(build_path)
    _validate_build(build, source_sha=source_sha, image=image)

    state = _state_root(sandbox_root)
    candidate = _load_json(state / "candidate.json")
    if candidate.get("schema") != CANDIDATE_SCHEMA or candidate.get("source_sha256") != source_sha:
        raise ValueError("boot artifact candidate is not bound to exact current source")
    if candidate.get("image_path") != str(image) or candidate.get("image_sha256") != build.get("image_sha256"):
        raise ValueError("boot artifact candidate image mismatch")

    validation = _load_json(validation_path)
    if validation.get("schema") != "minitz.boot_image_validation/v1" or validation.get("product") != "MiniTZ OS":
        raise ValueError("boot validation contract mismatch")
    if validation.get("source_sha256") != source_sha:
        raise ValueError("boot validation source mismatch")
    if validation.get("image_sha256") != build.get("image_sha256"):
        raise ValueError("boot validation image mismatch")
    if int(validation.get("image_bytes") or -1) != image.stat().st_size:
        raise ValueError("boot validation image size mismatch")
    if validation.get("quality_verdict") != "PASS":
        raise ValueError("boot validation did not pass")
    for field, expected in (
        ("partition_table", "GPT"),
        ("efi_system_partition", "PASS"),
        ("root_filesystem", "EXT4_PASS"),
        ("kernel_present", "PASS"),
        ("source_identity_embedded", "PASS"),
    ):
        if validation.get(field) != expected:
            raise ValueError(f"boot validation missing required check: {field}")
    if _sha256(image) != validation.get("image_sha256"):
        raise ValueError("boot validation image digest does not match current bytes")

    record = {
        "schema": CURRENT_SCHEMA,
        "product": "MiniTZ OS",
        "state": "CURRENT_VERIFIED",
        "source_sha256": source_sha,
        "image_path": str(image),
        "image_sha256": str(validation["image_sha256"]),
        "image_bytes": image.stat().st_size,
        "build_record_path": str(build_path),
        "build_record_sha256": _sha256(build_path),
        "validation_record_path": str(validation_path),
        "validation_record_sha256": _sha256(validation_path),
    }
    _atomic_json(state / "current.json", record)
    return record


def inspect_current_boot_artifact(repo_root: Path, sandbox_root: Path) -> dict[str, Any]:
    """Read current artifact truth without falling back to older files."""
    repo_root = Path(repo_root).resolve()
    sandbox_root = Path(sandbox_root).resolve()
    source_sha = _current_source_sha(repo_root)
    current_path = _state_root(sandbox_root) / "current.json"
    if not current_path.is_file():
        return {"state": "NEEDS_BUILD_OR_VALIDATION", "source_sha256": source_sha, "current_record_path": str(current_path)}
    try:
        current = _load_json(current_path)
    except ValueError as exc:
        return {"state": "CORRUPT_CURRENT_RECORD", "source_sha256": source_sha, "detail": str(exc), "current_record_path": str(current_path)}
    if current.get("schema") != CURRENT_SCHEMA or current.get("state") != "CURRENT_VERIFIED":
        return {**current, "state": "CORRUPT_CURRENT_RECORD", "current_record_path": str(current_path)}
    if current.get("source_sha256") != source_sha:
        return {**current, "state": "STALE_SOURCE", "expected_source_sha256": source_sha, "current_record_path": str(current_path)}

    try:
        image = Path(str(current["image_path"])).resolve()
        build_path = Path(str(current["build_record_path"])).resolve()
        validation_path = Path(str(current["validation_record_path"])).resolve()
        if not image.is_file() or not build_path.is_file() or not validation_path.is_file():
            return {**current, "state": "MISSING_CURRENT_BYTES", "current_record_path": str(current_path)}
        if _sha256(image) != current.get("image_sha256") or image.stat().st_size != int(current.get("image_bytes") or -1):
            return {**current, "state": "CURRENT_IMAGE_MISMATCH", "current_record_path": str(current_path)}
        if _sha256(build_path) != current.get("build_record_sha256") or _sha256(validation_path) != current.get("validation_record_sha256"):
            return {**current, "state": "CURRENT_RECORD_MISMATCH", "current_record_path": str(current_path)}
        build = _load_json(build_path)
        validation = _load_json(validation_path)
        _validate_build(build, source_sha=source_sha, image=image)
        if validation.get("source_sha256") != source_sha or validation.get("image_sha256") != current.get("image_sha256") or validation.get("quality_verdict") != "PASS":
            return {**current, "state": "CURRENT_VALIDATION_MISMATCH", "current_record_path": str(current_path)}
    except (KeyError, TypeError, ValueError) as exc:
        return {**current, "state": "CURRENT_RECORD_MISMATCH", "detail": str(exc), "current_record_path": str(current_path)}
    return {**current, "state": "CURRENT_VERIFIED", "current_record_path": str(current_path)}
