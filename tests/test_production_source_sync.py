from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops/local-ai/biella-production-source-sync.sh"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=False)


def _pair(tmp_path: Path) -> tuple[Path, Path, Path]:
    remote = tmp_path / "remote.git"
    local = tmp_path / "local"
    other = tmp_path / "other"
    assert _run("git", "init", "-q", "--bare", str(remote)).returncode == 0
    assert _run("git", "init", "-q", "-b", "main", str(local)).returncode == 0
    for repo in (local,):
        assert _run("git", "config", "user.name", "Biella Test", cwd=repo).returncode == 0
        assert _run("git", "config", "user.email", "test@example.invalid", cwd=repo).returncode == 0
    (local / "authority.txt").write_text("base\n", encoding="utf-8")
    assert _run("git", "add", ".", cwd=local).returncode == 0
    assert _run("git", "commit", "-qm", "base", cwd=local).returncode == 0
    assert _run("git", "remote", "add", "origin", str(remote), cwd=local).returncode == 0
    assert _run("git", "push", "-q", "-u", "origin", "main", cwd=local).returncode == 0
    assert _run("git", "clone", "-q", "-b", "main", str(remote), str(other)).returncode == 0
    assert _run("git", "config", "user.name", "Biella Test", cwd=other).returncode == 0
    assert _run("git", "config", "user.email", "test@example.invalid", cwd=other).returncode == 0
    return local, remote, other


def _sync(repo: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["BIELLA_REPO_ROOT"] = str(repo)
    return subprocess.run([str(SCRIPT)], text=True, capture_output=True, check=False, env=env)


def test_source_sync_fast_forwards_remote_without_touching_nonoverlap_dirty_work(tmp_path: Path):
    local, remote, other = _pair(tmp_path)
    dirty = local / "projects/biella-games/partial.cpp"
    dirty.parent.mkdir(parents=True)
    dirty.write_text("preserve me\n", encoding="utf-8")
    (other / "authority.txt").write_text("new authority\n", encoding="utf-8")
    assert _run("git", "add", "authority.txt", cwd=other).returncode == 0
    assert _run("git", "commit", "-qm", "authority update", cwd=other).returncode == 0
    assert _run("git", "push", "-q", "origin", "main", cwd=other).returncode == 0

    completed = _sync(local)
    assert completed.returncode == 0, completed.stderr
    local_head = _run("git", "rev-parse", "HEAD", cwd=local).stdout.strip()
    remote_head = _run("git", "--git-dir", str(remote), "rev-parse", "refs/heads/main").stdout.strip()
    assert local_head == remote_head
    assert dirty.read_text(encoding="utf-8") == "preserve me\n"


def test_source_sync_refuses_remote_overlap_and_preserves_local_bytes(tmp_path: Path):
    local, _remote, other = _pair(tmp_path)
    before = _run("git", "rev-parse", "HEAD", cwd=local).stdout.strip()
    (local / "authority.txt").write_text("local uncommitted\n", encoding="utf-8")
    (other / "authority.txt").write_text("remote authority\n", encoding="utf-8")
    assert _run("git", "add", "authority.txt", cwd=other).returncode == 0
    assert _run("git", "commit", "-qm", "remote overlap", cwd=other).returncode == 0
    assert _run("git", "push", "-q", "origin", "main", cwd=other).returncode == 0

    completed = _sync(local)
    assert completed.returncode != 0
    assert "overlap" in completed.stderr.lower()
    assert _run("git", "rev-parse", "HEAD", cwd=local).stdout.strip() == before
    assert (local / "authority.txt").read_text(encoding="utf-8") == "local uncommitted\n"


def test_source_sync_allows_local_ahead_without_rewriting_history(tmp_path: Path):
    local, _remote, _other = _pair(tmp_path)
    (local / "local-progress.txt").write_text("verified local progress\n", encoding="utf-8")
    assert _run("git", "add", "local-progress.txt", cwd=local).returncode == 0
    assert _run("git", "commit", "-qm", "local progress", cwd=local).returncode == 0
    before = _run("git", "rev-parse", "HEAD", cwd=local).stdout.strip()
    completed = _sync(local)
    assert completed.returncode == 0, completed.stderr
    assert _run("git", "rev-parse", "HEAD", cwd=local).stdout.strip() == before
