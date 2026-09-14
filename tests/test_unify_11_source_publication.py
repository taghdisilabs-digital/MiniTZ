from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/local-ai"))
import minitz_publication as pub  # type: ignore[import-not-found]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _repo(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.name", "MiniTZ Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "source.txt").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-u", "origin", "main")
    monkeypatch.setattr(pub, "_completed_snapshot", lambda *_a, **_k: ([], False))
    return repo


def _identity(repo: Path) -> dict[str, str]:
    commit = _git(repo, "rev-parse", "HEAD")
    return {"commit": commit, "tree": _git(repo, "rev-parse", commit + "^{tree}")}


def test_cursor_recovers_exact_pending_intent_from_durable_recovery_snapshot(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    expected = pub.request_publication(repo, "UNIFY-11", _identity(repo))
    state = pub._state_path(repo)
    recovery = pub._recovery_path(repo)
    assert recovery.is_file()
    state.write_text("{broken", encoding="utf-8")

    restored = pub.read_publication(repo)

    assert restored["commit"] == expected["commit"]
    assert restored["tree"] == expected["tree"]
    assert restored["task_id"] == "UNIFY-11"
    assert restored["status"] == "PENDING"
    assert json.loads(state.read_text(encoding="utf-8"))["commit"] == expected["commit"]


def test_corrupt_cursor_and_recovery_fail_closed_instead_of_resetting(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    pub.request_publication(repo, "UNIFY-11", _identity(repo))
    pub._state_path(repo).write_text("{broken", encoding="utf-8")
    pub._recovery_path(repo).write_text("{also broken", encoding="utf-8")
    with pytest.raises(pub.PublicationStateError):
        pub.read_publication(repo)


def test_source_and_publication_identity_is_singular_per_repository_ref(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    first = pub.source_publication_identity(repo)
    cursor = pub.request_publication(repo, "UNIFY-11", _identity(repo))
    second = pub.source_publication_identity(repo)
    assert first == second
    assert cursor["source_identity"] == first
    assert cursor["publication_ref"] == first["publication_ref"]
    assert first["ref"] == "refs/heads/main"


def test_cursor_and_manifest_bindings_share_one_publication_semantic_identity(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    cursor = pub.request_publication(repo, "UNIFY-11", _identity(repo))
    git_binding = pub.attach_publication_binding(
        repo,
        implementation_ref="git-adapter://minitz/repository-main",
        object_ref="repository://minitz/project/repo",
    )
    manifest_binding = pub.attach_publication_binding(
        repo,
        implementation_ref="production-integration://minitz/manifest-service",
        object_ref="production-manifest://minitz/project/manifest-1",
    )
    restarted = pub.read_publication(repo)
    assert git_binding["publication_ref"] == cursor["publication_ref"]
    assert manifest_binding["publication_ref"] == cursor["publication_ref"]
    assert len(restarted["semantic_bindings"]) == 2
    assert restarted["execution_authority"] is False


def test_non_ancestor_canonical_drive_replacement_is_rejected_before_transport(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    base = _identity(repo)["commit"]
    (repo / "source.txt").write_text("main next\n", encoding="utf-8")
    _git(repo, "commit", "-am", "main next")
    current = _identity(repo)["commit"]
    pub.request_publication(repo, "UNIFY-11", _identity(repo))
    with pub._locked(repo) as path:
        state = pub._read_state_locked(repo, path)
        state.setdefault("verified_files", {})["gdrive:canonical/source.txt"] = {
            "path": "source.txt", "destination": "gdrive:canonical/source.txt",
            "sha256": "0" * 64, "file_id": "old", "status": "VERIFIED", "commit": current,
        }
        pub._write_state(repo, path, state)

    _git(repo, "checkout", "-q", "-b", "diverged", base)
    (repo / "source.txt").write_text("diverged\n", encoding="utf-8")
    _git(repo, "commit", "-am", "diverged")
    divergent = _identity(repo)["commit"]
    monkeypatch.setattr(pub, "_remote", lambda *_a, **_k: pytest.fail("transport must not run for non-ancestor replacement"))

    result = pub.publish_drive_revision(repo, divergent)
    assert result["verified"] is False
    assert result["source_state"] == "RECONCILIATION_REQUIRED"
    assert "non-ancestor" in result["errors"][0]["error"]


def test_transport_failure_leaves_local_pending_intent_durable(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    requested = pub.request_publication(repo, "UNIFY-11", _identity(repo))
    monkeypatch.setattr(pub, "_remote", lambda *_a, **_k: (_ for _ in ()).throw(subprocess.TimeoutExpired("remote", 1)))
    result = pub.drain_once(repo, drive=False)
    after = pub.read_publication(repo)
    assert result["status"] == "PENDING"
    assert after["commit"] == requested["commit"]
    assert after["publication_intent"]["commit"] == requested["commit"]
    assert after["execution_authority"] is False



def test_reconciliation_required_is_terminal_for_publication_retry_loop(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    pub.request_publication(repo, "UNIFY-11", _identity(repo))
    with pub._locked(repo) as path:
        current = pub._read_state_locked(repo, path)
        current["status"] = "RECONCILIATION_REQUIRED"
        current["last_receipt"] = {"commit":current["commit"],"github":"PENDING","drive":"BATCHING","source_state":"RECONCILIATION_REQUIRED"}
        pub._write_state(repo, path, current)
    assert pub.publication_retry_needed(pub.read_publication(repo)) is False


def test_non_fast_forward_cursor_is_reconciliation_required_not_pending_retry(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    requested = pub.request_publication(repo, "UNIFY-11", _identity(repo))
    def remote(args, **_kwargs):
        if args[:4] == ["git","-C",str(repo),"ls-remote"]:
            return subprocess.CompletedProcess(args,0,stdout=("f"*40+"\trefs/heads/main\n").encode(),stderr=b"")
        if "push" in args:
            raise subprocess.CalledProcessError(1,args,stderr=b"! [rejected] x -> main (non-fast-forward)\nerror: failed to push some refs")
        raise AssertionError(args)
    monkeypatch.setattr(pub,"_remote",remote)
    result=pub.drain_once(repo,drive=False)
    assert result["commit"] == requested["commit"]
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert result["last_receipt"]["source_state"] == "RECONCILIATION_REQUIRED"
    assert pub.publication_retry_needed(result) is False
