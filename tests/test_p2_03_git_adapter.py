"""P2-03 exact-revision Git repository adapter acceptance tests."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

import pytest
import biella
from biella import (
    ArtifactService,
    CapabilityRef,
    FilesystemAdapter,
    FilesystemMode,
    FilesystemObjectStorageBackend,
    FilesystemRoot,
    FilesystemScope,
    GitAdapter,
    GitAuthorityError,
    GitConflictError,
    GitIntegrityError,
    GitScopeError,
    GraphRef,
    GraphService,
    Node,
    NodeExecutionAttempt,
    NodeExecutionService,
    NodeRef,
    ProjectAccess,
    ProjectRef,
    ProjectStore,
    RepositoryCommitReceipt,
    RepositoryDiffReceipt,
    RepositoryInspectionReceipt,
    RepositoryPushReceipt,
    RepositoryRef,
    RepositoryWorkspaceRef,
    RunService,
    TaskRevisionService,
)


def test_t01_public_exact_repository_interfaces_are_active_runtime_exports() -> None:
    expected = {
        "GitAdapter",
        "RepositoryCommitReceipt",
        "RepositoryDiffReceipt",
        "RepositoryInspectionReceipt",
        "RepositoryPushReceipt",
        "RepositoryRef",
        "RepositoryWorkspaceRef",
    }
    assert expected.issubset(set(biella.__all__))


def _run_git(path: Path, *argv: str) -> str:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_AUTHOR_NAME": "Fixture Author",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture Author",
        }
    )
    result = subprocess.run(
        ("/usr/bin/git", *argv),
        cwd=path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


@dataclass(frozen=True)
class _Environment:
    database: Path
    access: ProjectAccess
    project_ref: ProjectRef
    objects: FilesystemObjectStorageBackend
    filesystem: FilesystemAdapter
    git: GitAdapter
    source_root: FilesystemRoot
    candidate_root: FilesystemRoot
    source_root_path: Path
    source_repo_path: Path
    candidate_root_path: Path
    remote_path: Path
    base_commit: str
    base_tree: str
    attempt: NodeExecutionAttempt


def _environment(
    tmp_path: Path,
    *,
    namespace: str = "git-adapter",
    side_effect_authority: str = "EXTERNAL_SIDE_EFFECT",
) -> _Environment:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_root_path = tmp_path / "source-root"
    source_repo_path = source_root_path / "source"
    candidate_root_path = tmp_path / "candidate-root"
    remote_path = tmp_path / "publish.git"
    source_repo_path.mkdir(parents=True)
    candidate_root_path.mkdir()
    remote_path.mkdir()
    _run_git(source_repo_path, "init", "--initial-branch=main")
    (source_repo_path / "tracked.txt").write_text("base tracked\n", encoding="utf-8")
    (source_repo_path / "staged.txt").write_text("base staged\n", encoding="utf-8")
    (source_repo_path / "link.txt").symlink_to("tracked.txt")
    _run_git(source_repo_path, "add", "--all")
    _run_git(source_repo_path, "commit", "-m", "fixture base")
    first_commit = _run_git(source_repo_path, "rev-parse", "HEAD^{commit}")
    _run_git(
        source_repo_path,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{first_commit},vendor/submodule",
    )
    _run_git(source_repo_path, "commit", "-m", "record exact submodule identity")
    base_commit = _run_git(source_repo_path, "rev-parse", "HEAD^{commit}")
    base_tree = _run_git(source_repo_path, "rev-parse", "HEAD^{tree}")
    (source_repo_path / "tracked.txt").write_text("dirty unstaged source\n", encoding="utf-8")
    (source_repo_path / "staged.txt").write_text("dirty staged source\n", encoding="utf-8")
    _run_git(source_repo_path, "add", "staged.txt")
    (source_repo_path / "source-untracked.txt").write_text("unrelated source work\n", encoding="utf-8")
    _run_git(remote_path, "init", "--bare", "--initial-branch=main")

    database = tmp_path / f"{namespace}.sqlite3"
    registration = ProjectStore(database).create_project(namespace=namespace, display_name=namespace.title())
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    filesystem = FilesystemAdapter(database, objects)
    filesystem_capabilities = filesystem.register_capabilities(registration.access)
    git = GitAdapter(database, objects)
    process_capabilities = git.process.register_capabilities(registration.access)
    git_capabilities = git.register_capabilities(registration.access)
    capabilities = tuple(sorted((*filesystem_capabilities, *process_capabilities, *git_capabilities)))
    task = TaskRevisionService(database).create_task(
        registration.access,
        project_ref=registration.project.project_ref,
        idempotency_key="git-adapter-task",
        task_type="git.adapter",
        objective="Verify exact-revision candidate-safe Git operations",
        required_capabilities=capabilities,
        input_refs=(),
        output_contract={"result": "schema://biella/git-receipt/1"},
        constraints={},
        side_effect_authority=side_effect_authority,
        data_policy_ref=None,
        egress_policy_ref=None,
        evidence_requirements=("tool-call", "artifact", "content-ref"),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(registration.access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        registration.access,
        run.run_ref,
        owner_ref="controller://git-adapter-tests",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(registration.project.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "TOOL",
        capabilities,
        (),
        (),
        {"result": "schema://biella/git-receipt/1"},
        None,
        side_effect_authority,
        {},
        ("tool-call", "artifact", "content-ref"),
    )
    GraphService(database).create_graph(
        registration.access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(node,),
        compiler_identity=None,
        compiler_version=None,
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    executions.prepare_run(registration.access, run.run_ref)
    attempt = executions.lease_node(
        registration.access,
        node.node_ref,
        authority_attempt=run_attempt,
        owner_ref="executor://git-adapter-tests",
        lease_seconds=1800,
        idempotency_key="git-adapter-node-lease",
    )
    executions.start_node(registration.access, attempt, idempotency_key="git-adapter-node-start")
    source_root = filesystem.register_root(
        registration.access,
        path=source_root_path,
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_WRITE,
        allow_remove=False,
        idempotency_key="git-source-root",
    )
    candidate_root = filesystem.register_root(
        registration.access,
        path=candidate_root_path,
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_WRITE,
        allow_remove=True,
        idempotency_key="git-candidate-root",
    )
    return _Environment(
        database,
        registration.access,
        registration.project.project_ref,
        objects,
        filesystem,
        git,
        source_root,
        candidate_root,
        source_root_path,
        source_repo_path,
        candidate_root_path,
        remote_path,
        base_commit,
        base_tree,
        attempt,
    )


def _repository(env: _Environment) -> RepositoryRef:
    return env.git.register_repository(
        env.access,
        env.attempt,
        root_ref=env.source_root.root_ref,
        relative_path="source",
        expected_commit_sha=env.base_commit,
        expected_tree_sha=env.base_tree,
        idempotency_key="register-exact-source",
    )


def _workspace(env: _Environment, repository: RepositoryRef | None = None) -> RepositoryWorkspaceRef:
    return env.git.create_workspace(
        env.access,
        env.attempt,
        _repository(env) if repository is None else repository,
        candidate_root_ref=env.candidate_root.root_ref,
        relative_path="candidate",
        require_source_head=True,
        idempotency_key="create-isolated-candidate",
    )


def test_t02_registers_nine_git_capabilities(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    implementations = env.git.register_capabilities(env.access)
    assert set(implementations) == {
        CapabilityRef(f"git.{operation}", "1.0.0")
        for operation in ("inspect", "status", "diff", "read", "workspace", "apply", "commit", "fetch", "push")
    }


def test_t03_exact_repository_inspection_preserves_dirty_source(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    before_status = _run_git(env.source_repo_path, "status", "--porcelain=v2", "--untracked-files=all")
    before_files = {
        path.name: path.read_bytes()
        for path in env.source_repo_path.iterdir()
        if path.is_file() and path.name != ".git"
    }
    repository = _repository(env)
    inspection = env.git.inspect(env.access, env.attempt, repository, idempotency_key="inspect-dirty-source")
    assert repository.commit_sha == env.base_commit
    assert repository.tree_sha == env.base_tree
    assert inspection.head_commit_sha == env.base_commit
    assert inspection.head_tree_sha == env.base_tree
    assert inspection.staged_paths == ("staged.txt",)
    assert inspection.unstaged_paths == ("tracked.txt", "vendor/submodule")
    assert inspection.untracked_paths == ("source-untracked.txt",)
    assert inspection.dirty
    assert _run_git(env.source_repo_path, "status", "--porcelain=v2", "--untracked-files=all") == before_status
    assert before_files == {
        path.name: path.read_bytes()
        for path in env.source_repo_path.iterdir()
        if path.is_file() and path.name != ".git"
    }
    assert ArtifactService(env.database).get_artifact(env.access, inspection.artifact_ref).project_ref == env.project_ref


def test_t04_isolated_candidate_materializes_exact_clean_base(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    repository = _repository(env)
    source_status = _run_git(env.source_repo_path, "status", "--porcelain=v2", "--untracked-files=all")
    workspace = _workspace(env, repository)
    candidate = env.candidate_root_path / "candidate"
    assert _run_git(candidate, "rev-parse", "HEAD^{commit}") == env.base_commit
    assert _run_git(candidate, "rev-parse", "HEAD^{tree}") == env.base_tree
    assert _run_git(candidate, "status", "--porcelain") == ""
    assert _run_git(candidate, "remote") == ""
    assert (candidate / "tracked.txt").read_text(encoding="utf-8") == "base tracked\n"
    assert (candidate / "link.txt").is_symlink()
    assert os.readlink(candidate / "link.txt") == "tracked.txt"
    assert _run_git(env.source_repo_path, "status", "--porcelain=v2", "--untracked-files=all") == source_status
    assert workspace.base_commit_sha == workspace.current_commit_sha == env.base_commit
    assert workspace.base_tree_sha == workspace.current_tree_sha == env.base_tree


def _candidate_patch() -> bytes:
    return b"""diff --git a/tracked.txt b/tracked.txt
--- a/tracked.txt
+++ b/tracked.txt
@@ -1 +1 @@
-base tracked
+candidate tracked
diff --git a/new.txt b/new.txt
new file mode 100644
--- /dev/null
+++ b/new.txt
@@ -0,0 +1 @@
+candidate untracked
"""


def test_t05_patch_is_base_bound_and_diff_captures_untracked_artifact(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    repository = _repository(env)
    workspace = _workspace(env, repository)
    patch_ref = env.objects.put(_candidate_patch(), media_type="text/x-diff")
    receipt = env.git.apply_patch(
        env.access,
        env.attempt,
        workspace,
        patch_ref=patch_ref,
        expected_commit_sha=workspace.current_commit_sha,
        idempotency_key="apply-base-bound-patch",
    )
    candidate = env.candidate_root_path / "candidate"
    assert (candidate / "tracked.txt").read_text(encoding="utf-8") == "candidate tracked\n"
    assert (candidate / "new.txt").read_text(encoding="utf-8") == "candidate untracked\n"
    assert receipt.untracked_paths == ("new.txt",)
    assert b"candidate tracked" in env.objects.read(receipt.unstaged_diff_ref)
    manifest = json.loads(env.objects.read(receipt.untracked_manifest_ref))
    assert tuple(manifest) == ("new.txt",)
    assert manifest["new.txt"]["digest"] == biella.ContentRef.from_bytes(
        b"candidate untracked\n",
        media_type="application/octet-stream",
    ).digest
    artifact = ArtifactService(env.database).get_artifact(env.access, receipt.artifact_ref)
    assert receipt.unstaged_diff_ref in artifact.source_content_refs
    assert receipt.untracked_manifest_ref in artifact.source_content_refs
    with pytest.raises(GitConflictError, match="stale"):
        env.git.apply_patch(
            env.access,
            env.attempt,
            workspace,
            patch_ref=patch_ref,
            expected_commit_sha="0" * 40,
            idempotency_key="reject-stale-patch-base",
        )
    assert _run_git(env.source_repo_path, "status", "--porcelain=v2", "--untracked-files=all")


def test_t06_commit_records_exact_parent_tree_and_never_executes_hooks(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    workspace = _workspace(env)
    patch_ref = env.objects.put(_candidate_patch(), media_type="text/x-diff")
    env.git.apply_patch(
        env.access,
        env.attempt,
        workspace,
        patch_ref=patch_ref,
        expected_commit_sha=workspace.current_commit_sha,
        idempotency_key="apply-before-commit",
    )
    candidate = env.candidate_root_path / "candidate"
    marker = tmp_path / "hook-must-not-run"
    hook = candidate / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n", encoding="utf-8")
    hook.chmod(0o755)
    receipt = env.git.commit(
        env.access,
        env.attempt,
        workspace,
        expected_parent_commit_sha=workspace.current_commit_sha,
        message="Coherent candidate commit",
        author_name="Biella Test",
        author_email="biella@example.invalid",
        idempotency_key="commit-exact-candidate",
    )
    assert not marker.exists()
    assert receipt.parent_commit_sha == env.base_commit
    assert receipt.parent_tree_sha == env.base_tree
    assert receipt.commit_sha == _run_git(candidate, "rev-parse", "HEAD^{commit}")
    assert receipt.tree_sha == _run_git(candidate, "rev-parse", "HEAD^{tree}")
    assert receipt.tree_sha != env.base_tree
    assert receipt.workspace_ref.current_commit_sha == receipt.commit_sha
    assert receipt.workspace_ref.current_tree_sha == receipt.tree_sha
    assert _run_git(candidate, "status", "--porcelain") == ""
    with pytest.raises(GitConflictError, match="stale"):
        env.git.get_workspace(env.access, workspace)


def test_t07_push_is_separate_explicit_non_force_external_side_effect(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    workspace = _workspace(env)
    patch_ref = env.objects.put(_candidate_patch(), media_type="text/x-diff")
    env.git.apply_patch(
        env.access,
        env.attempt,
        workspace,
        patch_ref=patch_ref,
        expected_commit_sha=workspace.current_commit_sha,
        idempotency_key="apply-before-push",
    )
    commit = env.git.commit(
        env.access,
        env.attempt,
        workspace,
        expected_parent_commit_sha=workspace.current_commit_sha,
        message="Push candidate",
        author_name="Biella Test",
        author_email="biella@example.invalid",
        idempotency_key="commit-before-push",
    )
    with pytest.raises(GitAuthorityError, match="explicit"):
        env.git.push(
            env.access,
            env.attempt,
            commit.workspace_ref,
            destination_url=str(env.remote_path),
            destination_ref="refs/heads/candidate",
            expected_remote_commit_sha=None,
            explicit_authorization=False,
            allow_network=False,
            idempotency_key="implicit-push-denied",
        )
    absent = subprocess.run(
        ("/usr/bin/git", "rev-parse", "--verify", "refs/heads/candidate"),
        cwd=env.remote_path,
        check=False,
        capture_output=True,
    )
    assert absent.returncode != 0
    receipt = env.git.push(
        env.access,
        env.attempt,
        commit.workspace_ref,
        destination_url=str(env.remote_path),
        destination_ref="refs/heads/candidate",
        expected_remote_commit_sha=None,
        explicit_authorization=True,
        allow_network=False,
        idempotency_key="explicit-safe-test-push",
    )
    assert not receipt.forced
    assert receipt.before_commit_sha is None
    assert receipt.pushed_commit_sha == commit.commit_sha
    assert _run_git(env.remote_path, "rev-parse", "refs/heads/candidate^{commit}") == commit.commit_sha
    with pytest.raises(GitAuthorityError, match="force push"):
        env.git.push(
            env.access,
            env.attempt,
            commit.workspace_ref,
            destination_url=str(env.remote_path),
            destination_ref="refs/heads/forced",
            expected_remote_commit_sha=None,
            explicit_authorization=True,
            allow_network=False,
            allow_force=True,
            idempotency_key="force-push-denied",
        )


def test_t08_unsafe_config_attributes_and_metadata_patch_fail_closed(tmp_path: Path) -> None:
    configured = _environment(tmp_path / "configured", namespace="git-configured")
    _run_git(configured.source_repo_path, "config", "filter.evil.clean", "/bin/false")
    with pytest.raises(GitAuthorityError, match="unsafe repository Git config"):
        _repository(configured)

    env = _environment(tmp_path / "patch", namespace="git-policy-patch")
    workspace = _workspace(env)
    policy_patch = b"""diff --git a/.gitattributes b/.gitattributes
new file mode 100644
--- /dev/null
+++ b/.gitattributes
@@ -0,0 +1 @@
+*.bin filter=evil
"""
    with pytest.raises(GitAuthorityError, match="policy"):
        env.git.apply_patch(
            env.access,
            env.attempt,
            workspace,
            patch_ref=env.objects.put(policy_patch, media_type="text/x-diff"),
            expected_commit_sha=workspace.current_commit_sha,
            idempotency_key="reject-attribute-policy-patch",
        )
    metadata_patch = b"""diff --git a/.git/config b/.git/config
new file mode 100644
--- /dev/null
+++ b/.git/config
@@ -0,0 +1 @@
+[core]
"""
    with pytest.raises((GitAuthorityError, GitConflictError)):
        env.git.apply_patch(
            env.access,
            env.attempt,
            workspace,
            patch_ref=env.objects.put(metadata_patch, media_type="text/x-diff"),
            expected_commit_sha=workspace.current_commit_sha,
            idempotency_key="reject-dot-git-patch",
        )


def test_t09_submodule_symlink_project_scope_and_restart_are_exact(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    repository = _repository(env)
    assert tuple(repository.submodules) == ("vendor/submodule",)
    assert len(repository.submodules["vendor/submodule"]) == 40
    assert env.objects.read(
        env.git.read_exact(
            env.access,
            env.attempt,
            repository,
            path="link.txt",
            idempotency_key="read-exact-symlink-blob",
        )
    ) == b"tracked.txt"
    workspace = _workspace(env, repository)
    beta = ProjectStore(env.database).create_project(namespace="git-beta", display_name="Git Beta")
    with pytest.raises(GitScopeError):
        env.git.get_repository(beta.access, repository)
    restarted = GitAdapter(env.database, FilesystemObjectStorageBackend(tmp_path / "objects"))
    assert restarted.get_repository(env.access, repository) == repository
    assert restarted.get_workspace(env.access, workspace) == workspace


def test_t10_replays_survive_workspace_advance_and_process_restart(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    repository = _repository(env)
    workspace = _workspace(env, repository)
    assert _workspace(env, repository) == workspace
    patch_ref = env.objects.put(_candidate_patch(), media_type="text/x-diff")
    applied = env.git.apply_patch(
        env.access,
        env.attempt,
        workspace,
        patch_ref=patch_ref,
        expected_commit_sha=workspace.current_commit_sha,
        idempotency_key="durable-replay-apply",
    )
    assert env.git.apply_patch(
        env.access,
        env.attempt,
        workspace,
        patch_ref=patch_ref,
        expected_commit_sha=workspace.current_commit_sha,
        idempotency_key="durable-replay-apply",
    ) == applied
    committed = env.git.commit(
        env.access,
        env.attempt,
        workspace,
        expected_parent_commit_sha=workspace.current_commit_sha,
        message="Durable replay candidate",
        author_name="Biella Test",
        author_email="biella@example.invalid",
        idempotency_key="durable-replay-commit",
    )
    assert env.git.apply_patch(
        env.access,
        env.attempt,
        workspace,
        patch_ref=patch_ref,
        expected_commit_sha=workspace.current_commit_sha,
        idempotency_key="durable-replay-apply",
    ) == applied
    assert env.git.commit(
        env.access,
        env.attempt,
        workspace,
        expected_parent_commit_sha=workspace.current_commit_sha,
        message="Durable replay candidate",
        author_name="Biella Test",
        author_email="biella@example.invalid",
        idempotency_key="durable-replay-commit",
    ) == committed
    assert _workspace(env, repository) == workspace
    restarted = GitAdapter(env.database, FilesystemObjectStorageBackend(tmp_path / "objects"))
    assert restarted.get_receipt(env.access, applied.tool_call_ref) == applied
    assert restarted.get_receipt(env.access, committed.tool_call_ref) == committed


def test_t11_stale_source_context_mismatch_and_path_escape_fail_closed(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    repository = _repository(env)
    _run_git(env.source_repo_path, "add", "--all")
    _run_git(env.source_repo_path, "commit", "-m", "advance source after registration")
    (env.source_repo_path / "later-untracked.txt").write_text("preserve me\n", encoding="utf-8")
    before = _run_git(env.source_repo_path, "status", "--porcelain=v2", "--untracked-files=all")
    with pytest.raises(GitConflictError, match="source HEAD is stale"):
        env.git.create_workspace(
            env.access,
            env.attempt,
            repository,
            candidate_root_ref=env.candidate_root.root_ref,
            relative_path="stale-rejected",
            require_source_head=True,
            idempotency_key="stale-source-rejected",
        )
    historical = env.git.create_workspace(
        env.access,
        env.attempt,
        repository,
        candidate_root_ref=env.candidate_root.root_ref,
        relative_path="historical-exact",
        require_source_head=False,
        idempotency_key="historical-source-accepted",
    )
    assert historical.current_commit_sha == env.base_commit
    assert _run_git(env.source_repo_path, "status", "--porcelain=v2", "--untracked-files=all") == before
    mismatch = b"""diff --git a/tracked.txt b/tracked.txt
--- a/tracked.txt
+++ b/tracked.txt
@@ -1 +1 @@
-context that is not present
+must never apply
"""
    candidate = env.candidate_root_path / "historical-exact" / "tracked.txt"
    original = candidate.read_bytes()
    with pytest.raises(GitConflictError, match="Git command failed"):
        env.git.apply_patch(
            env.access,
            env.attempt,
            historical,
            patch_ref=env.objects.put(mismatch, media_type="text/x-diff"),
            expected_commit_sha=historical.current_commit_sha,
            idempotency_key="context-mismatch-rejected",
        )
    assert candidate.read_bytes() == original
    with pytest.raises((GitConflictError, ValueError)):
        env.git.create_workspace(
            env.access,
            env.attempt,
            repository,
            candidate_root_ref=env.candidate_root.root_ref,
            relative_path="../escape",
            require_source_head=False,
            idempotency_key="path-escape-rejected",
        )


def test_t12_lfs_fetch_and_push_policy_are_explicit(tmp_path: Path) -> None:
    lfs = _environment(tmp_path / "lfs", namespace="git-lfs-policy")
    (lfs.source_repo_path / ".gitattributes").write_text("*.bin filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8")
    (lfs.source_repo_path / "pointer.bin").write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:0000000000000000000000000000000000000000000000000000000000000000\n"
        "size 0\n",
        encoding="utf-8",
    )
    _run_git(lfs.source_repo_path, "add", ".gitattributes", "pointer.bin")
    _run_git(lfs.source_repo_path, "commit", "-m", "exact LFS pointer fixture")
    lfs_commit = _run_git(lfs.source_repo_path, "rev-parse", "HEAD^{commit}")
    lfs_tree = _run_git(lfs.source_repo_path, "rev-parse", "HEAD^{tree}")
    with pytest.raises(GitAuthorityError, match="unsafe Git attributes"):
        lfs.git.register_repository(
            lfs.access,
            lfs.attempt,
            root_ref=lfs.source_root.root_ref,
            relative_path="source",
            expected_commit_sha=lfs_commit,
            expected_tree_sha=lfs_tree,
            idempotency_key="reject-unavailable-lfs-filter",
        )

    env = _environment(tmp_path / "network", namespace="git-network-policy")
    workspace = _workspace(env)
    with pytest.raises(GitAuthorityError, match="network fetch"):
        env.git.fetch(
            env.access,
            env.attempt,
            workspace,
            source_url="https://example.invalid/repository.git",
            source_ref="refs/heads/main",
            allow_network=False,
            idempotency_key="network-fetch-denied",
        )
    env.git.fetch(
        env.access,
        env.attempt,
        workspace,
        source_url=str(env.source_repo_path),
        source_ref="refs/heads/main",
        allow_network=False,
        idempotency_key="local-fetch-governed",
    )

    read_only = _environment(
        tmp_path / "read-only",
        namespace="git-read-only-push",
        side_effect_authority="PROJECT_WRITE",
    )
    read_only_workspace = _workspace(read_only)
    with pytest.raises(GitAuthorityError, match="side-effect authority"):
        read_only.git.push(
            read_only.access,
            read_only.attempt,
            read_only_workspace,
            destination_url=str(read_only.remote_path),
            destination_ref="refs/heads/denied",
            expected_remote_commit_sha=None,
            explicit_authorization=True,
            allow_network=False,
            idempotency_key="read-only-task-push-denied",
        )


def test_t13_receipt_tamper_and_content_erasure_fail_closed(tmp_path: Path) -> None:
    tamper = _environment(tmp_path / "tamper", namespace="git-tamper")
    workspace = _workspace(tamper)
    receipt = tamper.git.apply_patch(
        tamper.access,
        tamper.attempt,
        workspace,
        patch_ref=tamper.objects.put(_candidate_patch(), media_type="text/x-diff"),
        expected_commit_sha=workspace.current_commit_sha,
        idempotency_key="tamper-evidence-source",
    )
    forged = RepositoryDiffReceipt(
        receipt.workspace_ref,
        receipt.staged_diff_ref,
        receipt.unstaged_diff_ref,
        receipt.untracked_manifest_ref,
        ("forged.txt",),
        receipt.process_call_refs,
        receipt.tool_call_ref,
        receipt.artifact_ref,
        receipt.completed_at,
    )
    with sqlite3.connect(tamper.database) as connection:
        connection.execute("DROP TRIGGER git_operation_results_no_update")
        connection.execute(
            "UPDATE git_operation_results SET receipt_json=?,record_sha256=? WHERE project_id=? AND call_id=?",
            (
                json.dumps(forged.payload(), sort_keys=True, separators=(",", ":")),
                forged.record_sha256,
                tamper.project_ref.value,
                receipt.tool_call_ref.call_id,
            ),
        )
    with pytest.raises(GitIntegrityError, match="Artifact manifest differ"):
        tamper.git.get_receipt(tamper.access, receipt.tool_call_ref)

    erased = _environment(tmp_path / "erased", namespace="git-erased")
    erased_receipt = erased.git.inspect(
        erased.access,
        erased.attempt,
        _repository(erased),
        idempotency_key="erased-content-inspection",
    )
    digest = erased_receipt.status_ref.digest
    object_path = tmp_path / "erased" / "objects" / "objects" / "sha256" / digest[:2] / digest[2:4] / digest / "content"
    object_path.unlink()
    with pytest.raises(GitIntegrityError, match="ContentRef failed verification"):
        erased.git.get_receipt(erased.access, erased_receipt.tool_call_ref)


def test_t14_type_build_exact_wheel_and_separate_installed_restart() -> None:
    root = Path(__file__).resolve().parents[1]
    source_paths = (
        root / "src/biella/__init__.py",
        root / "src/biella/git_adapter.py",
        root / "src/biella/process.py",
        root / "tests/test_p2_03_git_adapter.py",
        root / "tests/fixtures/p2_03_installed_writer.py",
        root / "tests/fixtures/p2_03_installed_reader.py",
    )
    prohibited = (
        "TO" "DO",
        "FIX" "ME",
        "place" "holder",
        "pytest.mark." "skip",
        "@unittest." "skip",
        "Not" "Implemented",
    )
    for path in source_paths:
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        assert all(marker not in source for marker in prohibited)
    active_runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "src/biella").glob("*.py"))
        if path.name != "migration.py"
    )
    assert "QuarantineRef" not in active_runtime
    typecheck = subprocess.run(
        (sys.executable, "-m", "mypy", "--strict", "src"),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert typecheck.returncode == 0, f"{typecheck.stdout}\n{typecheck.stderr}"
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary = Path(temporary_directory)
        wheel_root = temporary / "wheel"
        wheel_root.mkdir()
        build = subprocess.run(
            (
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(wheel_root),
            ),
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert build.returncode == 0, f"{build.stdout}\n{build.stderr}"
        wheels = tuple(wheel_root.glob("biella_engine-*.whl"))
        assert len(wheels) == 1
        wheel = wheels[0]
        package_paths = tuple(sorted((root / "src/biella").glob("*.py")))
        with zipfile.ZipFile(wheel) as archive:
            wheel_names = {
                name
                for name in archive.namelist()
                if name.startswith("biella/") and name.endswith(".py")
            }
            assert wheel_names == {f"biella/{path.name}" for path in package_paths}
            for path in package_paths:
                assert hashlib.sha256(archive.read(f"biella/{path.name}")).hexdigest() == hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        installed = temporary / "installed"
        install = subprocess.run(
            (
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(installed),
                str(wheel),
            ),
            cwd=temporary,
            check=False,
            capture_output=True,
            text=True,
        )
        assert install.returncode == 0, f"{install.stdout}\n{install.stderr}"
        environment = os.environ.copy()
        environment.update(
            {
                "BIELLA_CANDIDATE_ROOT": str(temporary / "candidate-root"),
                "BIELLA_DATABASE": str(temporary / "restart.sqlite3"),
                "BIELLA_OBJECT_ROOT": str(temporary / "objects"),
                "BIELLA_SOURCE_ROOT": str(temporary / "source-root"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(installed),
            }
        )
        writer = subprocess.run(
            (sys.executable, str(root / "tests/fixtures/p2_03_installed_writer.py")),
            cwd=temporary,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert writer.returncode == 0, f"{writer.stdout}\n{writer.stderr}"
        identity = json.loads(writer.stdout)
        environment["BIELLA_EXPECTED"] = json.dumps(identity, sort_keys=True)
        reader = subprocess.run(
            (sys.executable, str(root / "tests/fixtures/p2_03_installed_reader.py")),
            cwd=temporary,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert reader.returncode == 0, f"{reader.stdout}\n{reader.stderr}"
        observed = json.loads(reader.stdout)
        assert observed["commit_artifact_ref"] == identity["commit_artifact_ref"]
        assert observed["commit_record_sha256"] == identity["commit_record_sha256"]
        assert observed["commit_sha"] == identity["commit_sha"]
        assert observed["diff_artifact_ref"] == identity["diff_artifact_ref"]
        assert observed["diff_record_sha256"] == identity["diff_record_sha256"]
        assert observed["tree_sha"] == identity["tree_sha"]
