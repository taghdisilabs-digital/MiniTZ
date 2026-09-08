from __future__ import annotations
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/local-ai"))
import biella_publication as pub


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def project(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "projects/biella-games/docs").mkdir(parents=True)
    write_tasks(repo, 0)
    (repo / "source.txt").write_text("retained source\n")
    git(repo, "add", "."); git(repo, "commit", "-qm", "base")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-qu", "origin", "main")
    request(repo, "RECONCILE")
    return repo


def write_tasks(repo, count):
    rows = [f"- [{'x' if i <= count else ' '}] D01-{i:02d} | medium | task {i} | {'COMPLETE' if i <= count else 'PENDING'} | proof" for i in range(1, 13)]
    (repo / "projects/biella-games/docs/PRODUCTION.md").write_text("\n".join(rows) + "\n")


def identity(repo):
    return {"commit": git(repo, "rev-parse", "HEAD"), "tree": git(repo, "rev-parse", "HEAD^{tree}")}


def request(repo, task):
    return pub.request_publication(repo, task, identity(repo))


def complete(repo, count):
    write_tasks(repo, count)
    git(repo, "add", "."); git(repo, "commit", "-qm", f"completed {count}")
    return request(repo, f"D01-{count:02d}")


def test_four_closures_have_no_drive_calls_and_git_still_publishes(tmp_path, monkeypatch):
    repo = project(tmp_path)
    monkeypatch.setattr(pub, "publish_drive_revision", lambda *a, **kw: pytest.fail("Drive called before fifth completion"))
    for i in range(1, 5):
        complete(repo, i)
        result = pub.drain_once(repo)
        assert result["last_receipt"]["github"] == "VERIFIED"
        assert result["last_receipt"]["drive"] == "BATCHING"
        assert result["drive_batch"]["pending"] is None
    assert git(repo, "ls-remote", "origin", "refs/heads/main").split()[0] == identity(repo)["commit"]


def test_fifth_completion_schedules_once_and_retries_do_not_count(tmp_path):
    repo = project(tmp_path)
    for i in range(1, 6):
        result = complete(repo, i)
    pending = result["drive_batch"]["pending"]
    assert pending["task_ids"] == [f"D01-{i:02d}" for i in range(1, 6)]
    assert result["drive_batch"]["part_max_bytes"] == 3_800_000_000
    for _ in range(3):
        assert request(repo, "D01-05")["drive_batch"]["pending"] == pending
    complete(repo, 6)
    assert pub.read_publication(repo)["drive_batch"]["pending"] == pending


def test_next_five_only_after_successful_batch_receipt(tmp_path):
    repo = project(tmp_path)
    for i in range(1, 6): complete(repo, i)
    pending = pub.read_publication(repo)["drive_batch"]["pending"]
    complete(repo, 6)
    pub.finish_drive_batch(repo, pending, {"verified": True, "parts": []})
    assert pub.read_publication(repo)["drive_batch"]["pending"] is None
    for i in range(7, 11): complete(repo, i)
    assert pub.read_publication(repo)["drive_batch"]["pending"]["task_ids"] == [f"D01-{i:02d}" for i in range(6, 11)]


def test_migration_keeps_existing_completion_as_baseline(tmp_path):
    repo = project(tmp_path)
    write_tasks(repo, 7); git(repo, "add", "."); git(repo, "commit", "-qm", "existing progress")
    path = pub._state_path(repo)
    legacy = {**identity(repo), "task_id": "D01-08", "status": "PENDING", "verified_files": {"old": {"sha256": "preserved"}}}
    path.write_text(json.dumps(legacy))
    result = request(repo, "RECONCILE")
    assert len(result["drive_batch"]["baseline_completed_ids"]) == 7
    assert result["drive_batch"]["pending"] is None
    assert result["verified_files"] == legacy["verified_files"]


def test_package_size_cap_roundtrip_and_dirty_files_excluded(tmp_path):
    import biella_drive_package as package
    repo = project(tmp_path)
    (repo / "large.bin").write_bytes(bytes(range(256)) * 300)
    git(repo, "add", "large.bin"); git(repo, "commit", "-qm", "source")
    revision = identity(repo)
    (repo / "source.txt").write_text("uncommitted change")
    (repo / "untracked.txt").write_text("not accepted")
    manifest = package.build_package(repo, {**revision, "task_ids": ["D01-01"], "base_commit": None}, tmp_path / "packages", max_bytes=512)
    parts = [tmp_path / "packages" / revision["commit"] / part["name"] for part in manifest["parts"]]
    assert len(parts) > 1
    assert all(p.stat().st_size <= 512 for p in parts)
    for p, info in zip(parts, manifest["parts"]):
        assert hashlib.sha256(p.read_bytes()).hexdigest() == info["sha256"]
    stream = gzip.decompress(b"".join(p.read_bytes() for p in parts))
    with tarfile.open(fileobj=io.BytesIO(stream)) as archive:
        assert archive.extractfile("source.txt").read() == b"retained source\n"
        assert "untracked.txt" not in archive.getnames()
        assert archive.extractfile("large.bin").read() == bytes(range(256)) * 300
    assert package.build_package(repo, {**revision, "task_ids": ["D01-01"], "base_commit": None}, tmp_path / "packages", max_bytes=512) == manifest


def test_delta_records_deletions_and_does_not_repack_unchanged_source(tmp_path):
    import biella_drive_package as package
    repo = project(tmp_path); base = identity(repo)["commit"]
    (repo / "source.txt").unlink(); (repo / "new.txt").write_text("new")
    git(repo, "add", "."); git(repo, "commit", "-qm", "delta")
    result = package.build_package(repo, {**identity(repo), "base_commit": base, "task_ids": ["D01-06"]}, tmp_path / "packages", max_bytes=4096)
    assert result["kind"] == "DELTA"
    assert result["deleted_paths"] == ["source.txt"]
    assert result["base_commit"] == base


def test_failed_batch_does_not_clear_pending_or_block_new_git_request(tmp_path):
    repo = project(tmp_path)
    for i in range(1, 6): complete(repo, i)
    pending = pub.read_publication(repo)["drive_batch"]["pending"]
    pub.finish_drive_batch(repo, pending, {"verified": False, "error": "Drive unavailable"})
    result = complete(repo, 6)
    assert result["drive_batch"]["pending"] == pending
    assert result["commit"] == identity(repo)["commit"]


def test_complete_batch_packages_then_mirrors_without_task_replay(tmp_path, monkeypatch):
    repo = project(tmp_path)
    for i in range(1, 6): complete(repo, i)
    observed = []
    def publish_file(root, source, destination, digest, commit):
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        assert source.stat().st_size <= 3_800_000_000
        observed.append(destination)
        return {"file_id": "fixture-file", "sha256": digest, "destination": destination}
    monkeypatch.setattr(pub, "_publish_package_file", publish_file)
    monkeypatch.setattr(pub, "publish_drive_revision", lambda *a: {"verified": True, "files": []})
    result = pub.drain_once(repo)
    assert result["status"] == "SYNCED"
    assert result["drive_batch"]["pending"] is None
    assert len(result["drive_batch"]["baseline_completed_ids"]) == 5
    assert any(name.endswith(".manifest.json") for name in observed)
    assert not list(pub._package_root(repo).rglob("*.part*"))
    assert git(repo, "status", "--porcelain") == ""


def test_final_partial_batch_flushes_at_program_exhaustion(tmp_path):
    repo = project(tmp_path)
    for i in range(1, 6): complete(repo, i)
    batch = pub.read_publication(repo)["drive_batch"]["pending"]
    pub.finish_drive_batch(repo, batch, {"verified": True})
    for i in range(6, 11): complete(repo, i)
    batch = pub.read_publication(repo)["drive_batch"]["pending"]
    pub.finish_drive_batch(repo, batch, {"verified": True})
    complete(repo, 11)
    assert pub.read_publication(repo)["drive_batch"]["pending"] is None
    complete(repo, 12)
    assert pub.read_publication(repo)["drive_batch"]["pending"]["task_ids"] == ["D01-11", "D01-12"]


def test_corrupt_staging_is_rebuilt_from_committed_bytes(tmp_path):
    import biella_drive_package as package
    repo = project(tmp_path)
    batch = {**identity(repo), "base_commit": None, "task_ids": ["D01-01"]}
    manifest = package.build_package(repo, batch, tmp_path / "packages", max_bytes=512)
    part = tmp_path / "packages" / batch["commit"] / manifest["parts"][0]["name"]
    part.write_bytes(b"corrupt")
    rebuilt = package.build_package(repo, batch, tmp_path / "packages", max_bytes=512)
    assert rebuilt == manifest
    assert package.file_digest(part) == manifest["parts"][0]["sha256"]


def test_slow_drive_worker_cannot_delay_new_github_commit(tmp_path, monkeypatch):
    import threading
    import time
    repo = project(tmp_path)
    entered, release = threading.Event(), threading.Event()
    def slow_drive(*args):
        entered.set(); release.wait(5)
        return {"status": "BATCHING"}
    monkeypatch.setattr(pub, "drain_drive_once", slow_drive)
    pub.start_worker(repo)
    threads = [workers[str(repo.resolve())][0] for workers in (pub._WORKERS, pub._DRIVE_WORKERS)]
    try:
        assert entered.wait(2)
        complete(repo, 1)
        target = identity(repo)["commit"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if git(repo, "ls-remote", "origin", "refs/heads/main").split()[0] == target:
                break
            time.sleep(0.02)
        assert not release.is_set()
        assert git(repo, "ls-remote", "origin", "refs/heads/main").split()[0] == target
    finally:
        release.set(); pub.stop_worker(repo)
        for thread in threads: thread.join(timeout=2)
