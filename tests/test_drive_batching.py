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


def _fixture_completed_snapshot(repo, commit):
    text = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{commit}:projects/biella-games/docs/PRODUCTION.md"],
        text=True,
    )
    completed = []
    active = False
    for line in text.splitlines():
        if line.startswith("- [x] "):
            completed.append(line.split("|", 1)[0].split()[-1])
        elif line.startswith("- [ ] "):
            active = True
    return completed, not active


@pytest.fixture(autouse=True)
def _batching_fixture_owns_completion_source(monkeypatch):
    monkeypatch.setattr(pub, "_completed_snapshot", _fixture_completed_snapshot)


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
    monkeypatch.setattr(pub, "publish_drive_revision", lambda *a, **kw: pytest.fail("automatic publication called Drive"))
    for i in range(1, 5):
        complete(repo, i)
        result = pub.drain_once(repo)
        assert result["last_receipt"]["github"] == "VERIFIED"
        assert result["last_receipt"]["drive"] == "EXPLICIT_ONLY"
        assert result["drive_batch"]["pending"] is None
        assert result["drive_batch"]["status"] == "EXPLICIT_ONLY"
    assert git(repo, "ls-remote", "origin", "refs/heads/main").split()[0] == identity(repo)["commit"]

def test_completions_never_schedule_drive_batch(tmp_path):
    repo = project(tmp_path)
    for i in range(1, 13):
        result = complete(repo, i)
        assert result["drive_batch"]["pending"] is None
        assert result["drive_batch"]["status"] == "EXPLICIT_ONLY"
        assert result["drive_batch"]["automatic_publication"] is False

def test_legacy_pending_drive_batch_is_retired_without_transport(tmp_path):
    repo = project(tmp_path)
    state = pub.read_publication(repo)
    legacy_pending = {
        "commit": state["commit"], "tree": state["tree"], "task_ids": ["D01-01"],
        "completed_ids": ["D01-01"], "base_commit": None, "requested_at": "legacy",
    }
    with pub._locked(repo) as path:
        current = pub._read_state_locked(repo, path)
        current["drive_batch"]["pending"] = legacy_pending
        current["drive_batch"]["status"] = "PENDING"
        pub._write_state(repo, path, current)
    complete(repo, 1)
    migrated = pub.read_publication(repo)["drive_batch"]
    assert migrated["pending"] is None
    assert migrated["retired_pending"] == legacy_pending
    assert migrated["status"] == "EXPLICIT_ONLY"
    assert migrated["automatic_publication"] is False

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


def test_explicit_only_drive_state_never_blocks_new_git_request(tmp_path):
    repo = project(tmp_path)
    for i in range(1, 6):
        complete(repo, i)
    result = pub.drain_once(repo)
    assert result["status"] == "SYNCED"
    assert result["last_receipt"]["github"] == "VERIFIED"
    assert result["last_receipt"]["drive"] == "EXPLICIT_ONLY"
    assert result["drive_batch"]["pending"] is None

def test_automatic_drain_never_builds_or_mirrors_drive_packages(tmp_path, monkeypatch):
    repo = project(tmp_path)
    for i in range(1, 6):
        complete(repo, i)
    monkeypatch.setattr(pub, "_publish_package_file", lambda *a, **kw: pytest.fail("automatic package upload called"))
    monkeypatch.setattr(pub, "publish_drive_revision", lambda *a, **kw: pytest.fail("automatic Drive mirror called"))
    result = pub.drain_once(repo)
    assert result["status"] == "SYNCED"
    assert result["drive_batch"]["pending"] is None
    assert result["last_receipt"]["drive"] == "EXPLICIT_ONLY"

def test_program_exhaustion_does_not_schedule_drive(tmp_path):
    repo = project(tmp_path)
    for i in range(1, 13):
        result = complete(repo, i)
    assert result["program_finished"] is True
    assert result["drive_batch"]["pending"] is None
    assert result["drive_batch"]["status"] == "EXPLICIT_ONLY"

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


def test_background_worker_has_only_source_publication_thread(tmp_path):
    repo = project(tmp_path)
    pub.start_worker(repo)
    key = str(repo.resolve())
    try:
        assert key in pub._WORKERS
        assert key not in pub._DRIVE_WORKERS
        assert pub._WORKERS[key][0].name == "biella-publication"
    finally:
        pub.stop_worker(repo)

def test_background_publication_never_calls_drive_transport(tmp_path, monkeypatch):
    repo = project(tmp_path)
    calls = []
    original = pub._remote
    def remote(args, **kwargs):
        if args and args[0] == "rclone":
            calls.append(args)
            raise AssertionError("automatic publication must not call rclone")
        return original(args, **kwargs)
    monkeypatch.setattr(pub, "_remote", remote)
    result = pub.drain_once(repo)
    assert result["last_receipt"]["drive"] == "EXPLICIT_ONLY"
    assert calls == []


def test_background_worker_has_no_drive_thread(tmp_path):
    repo = project(tmp_path)
    pub.start_worker(repo)
    try:
        key = str(repo.resolve())
        assert key in pub._WORKERS
        assert key not in pub._DRIVE_WORKERS
    finally:
        pub.stop_worker(repo)
