"""Streaming, exact-revision Drive transfer packages; no execution authority."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any

MAX_PART_BYTES = 3_800_000_000
READ_BYTES = 1024 * 1024


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(READ_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


class _SplitWriter:
    def __init__(self, directory: Path, prefix: str, limit: int):
        self.directory, self.prefix, self.limit = directory, prefix, limit
        self.parts: list[dict[str, Any]] = []
        self.handle = None
        self.size = self.total = 0
        self.digest = hashlib.sha256()
        self.partial: Path | None = None

    def write(self, data: bytes) -> int:
        view = memoryview(data)
        length = len(view)
        while view:
            if self.handle is None:
                self.partial = self.directory / f"{self.prefix}.part{len(self.parts)+1:06d}.partial"
                self.handle = self.partial.open("wb")
                self.size = 0
                self.digest = hashlib.sha256()
            count = min(len(view), self.limit - self.size)
            self.handle.write(view[:count]); self.digest.update(view[:count])
            self.size += count; self.total += count; view = view[count:]
            if self.size == self.limit:
                self._finish_part()
        return length

    def _finish_part(self) -> None:
        if self.handle is None:
            return
        self.handle.flush(); os.fsync(self.handle.fileno()); self.handle.close()
        self.handle = None
        assert self.partial is not None
        final = self.partial.with_suffix("")
        os.replace(self.partial, final)
        self.parts.append({"name": final.name, "bytes": self.size, "sha256": self.digest.hexdigest()})

    def flush(self) -> None:
        if self.handle is not None:
            self.handle.flush()

    def tell(self) -> int:
        return self.total

    def close(self) -> None:
        self._finish_part()


def build_package(repo: Path, batch: dict[str, Any], directory: Path, *, max_bytes: int = MAX_PART_BYTES) -> dict[str, Any]:
    """Export a snapshot once, then committed deltas. Never read dirty task bytes."""
    if not 0 < max_bytes <= MAX_PART_BYTES:
        raise ValueError("package part limit must be positive and no larger than 3.8 GB")
    repo, directory = Path(repo), Path(directory)
    commit = _git(repo, "rev-parse", batch["commit"] + "^{commit}").decode().strip()
    tree = _git(repo, "rev-parse", commit + "^{tree}").decode().strip()
    if tree != batch["tree"]:
        raise ValueError("package source commit/tree mismatch")
    base = batch.get("base_commit")
    target = directory / commit
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = target / "manifest.json"
    if manifest_path.is_file():
        saved = json.loads(manifest_path.read_text())
        if saved.get("commit") == commit and saved.get("base_commit") == base and saved.get("part_max_bytes") == max_bytes:
            if all((target / part["name"]).is_file() and (target / part["name"]).stat().st_size == part["bytes"] and file_digest(target / part["name"]) == part["sha256"] for part in saved["parts"]):
                return saved
    deleted: list[str] = []
    selected: list[str] = []
    if base:
        subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", base, commit], check=True)
        selected = [os.fsdecode(p) for p in _git(repo, "diff", "--name-only", "--no-renames", "--diff-filter=ACMT", "-z", base, commit).split(b"\0") if p]
        deleted = [os.fsdecode(p) for p in _git(repo, "diff", "--name-only", "--no-renames", "--diff-filter=D", "-z", base, commit).split(b"\0") if p]
        import biella_production_evidence as evidence
        for relative, _ in evidence.drive_publications(repo) + evidence.derived_drive_publications(repo) + evidence.control_drive_publications(repo):
            if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{commit}:{relative}"], capture_output=True).returncode == 0:
                selected.append(relative)
        selected = sorted(set(selected))
        if not selected or sum(len(os.fsencode(p)) + 1 for p in selected) > 65536:
            # A full exact snapshot is preferable to argument truncation or an empty delta.
            base = None; selected = []; deleted = []
    first, last = batch["task_ids"][0], batch["task_ids"][-1]
    prefix = f"BIELLA_PRODUCTION_{first}_{last}_{commit[:12]}.tar.gz"
    writer = _SplitWriter(target, prefix, max_bytes)
    args = ["git", "-C", str(repo), "archive", "--format=tar", commit]
    if base:
        args += ["--", *selected]
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errors)
        try:
            assert proc.stdout is not None
            with gzip.GzipFile(filename="", mode="wb", fileobj=writer, compresslevel=1, mtime=0) as compressed:
                for chunk in iter(lambda: proc.stdout.read(READ_BYTES), b""):
                    compressed.write(chunk)
            proc.stdout.close()
            if proc.wait() != 0:
                errors.seek(0)
                raise RuntimeError("git archive failed: " + errors.read().decode(errors="replace")[-2000:])
            writer.close()
        finally:
            if proc.poll() is None:
                proc.terminate(); proc.wait()
            writer.close()
    manifest = {
        "schema": "biella.drive_transfer_package/v1", "kind": "DELTA" if base else "SNAPSHOT",
        "commit": commit, "tree": tree, "base_commit": base,
        "task_ids": list(batch["task_ids"]), "part_max_bytes": max_bytes,
        "format": "git-archive tar, gzip compressed, split in listed order",
        "manifest_name": prefix.removesuffix(".tar.gz") + ".manifest.json",
        "parts": writer.parts, "deleted_paths": deleted,
        "restore_order": "Verify SHA-256 for every listed part, concatenate in manifest order, decompress gzip, then extract tar. DELTA requires base_commit and applies deleted_paths after extraction.",
        "authority": "TRANSFER_ARTIFACT_NOT_EXECUTION_STATE",
    }
    raw = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    temporary = manifest_path.with_suffix(".tmp")
    with temporary.open("w") as handle:
        handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, manifest_path)
    return manifest
