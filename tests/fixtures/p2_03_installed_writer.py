"""Create P2-03 Git evidence using only an installed wheel."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from minitz_os.engine import (
    FilesystemAdapter,
    FilesystemMode,
    FilesystemObjectStorageBackend,
    FilesystemScope,
    GitAdapter,
    GraphRef,
    GraphService,
    Node,
    NodeExecutionService,
    NodeRef,
    ProjectStore,
    RunService,
    TaskRevisionService,
)


def run_git(path: Path, *argv: str) -> str:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_EMAIL": "installed@example.invalid",
            "GIT_AUTHOR_NAME": "Installed Fixture",
            "GIT_COMMITTER_EMAIL": "installed@example.invalid",
            "GIT_COMMITTER_NAME": "Installed Fixture",
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


database = Path(os.environ["MINITZ_DATABASE"])
source_root_path = Path(os.environ["MINITZ_SOURCE_ROOT"])
candidate_root_path = Path(os.environ["MINITZ_CANDIDATE_ROOT"])
object_root = Path(os.environ["MINITZ_OBJECT_ROOT"])
source_repo = source_root_path / "source"
source_repo.mkdir(parents=True)
candidate_root_path.mkdir()
run_git(source_repo, "init", "--initial-branch=main")
(source_repo / "tracked.txt").write_text("installed base\n", encoding="utf-8")
run_git(source_repo, "add", "tracked.txt")
run_git(source_repo, "commit", "-m", "installed exact base")
base_commit = run_git(source_repo, "rev-parse", "HEAD^{commit}")
base_tree = run_git(source_repo, "rev-parse", "HEAD^{tree}")

registration = ProjectStore(database).create_project(
    namespace="installed-git",
    display_name="Installed Git",
)
objects = FilesystemObjectStorageBackend(object_root)
filesystem = FilesystemAdapter(database, objects)
filesystem_capabilities = filesystem.register_capabilities(registration.access)
git = GitAdapter(database, objects)
process_capabilities = git.process.register_capabilities(registration.access)
git_capabilities = git.register_capabilities(registration.access)
capabilities = tuple(sorted((*filesystem_capabilities, *process_capabilities, *git_capabilities)))
task = TaskRevisionService(database).create_task(
    registration.access,
    project_ref=registration.project.project_ref,
    idempotency_key="installed-git-task",
    task_type="git.installed",
    objective="Verify installed exact-revision Git restart",
    required_capabilities=capabilities,
    input_refs=(),
    output_contract={"result": "schema://minitz/git-receipt/1"},
    constraints={},
    side_effect_authority="EXTERNAL_SIDE_EFFECT",
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
    owner_ref="controller://installed-git",
    lease_seconds=600,
)
graph_ref = GraphRef.new(registration.project.project_ref)
node = Node(
    NodeRef.new(graph_ref),
    "TOOL",
    capabilities,
    (),
    (),
    {"result": "schema://minitz/git-receipt/1"},
    None,
    "EXTERNAL_SIDE_EFFECT",
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
    owner_ref="executor://installed-git",
    lease_seconds=600,
    idempotency_key="installed-git-node-lease",
)
executions.start_node(registration.access, attempt, idempotency_key="installed-git-node-start")
source_root = filesystem.register_root(
    registration.access,
    path=source_root_path,
    scope=FilesystemScope.PROJECT,
    mode=FilesystemMode.READ_WRITE,
    allow_remove=False,
    idempotency_key="installed-git-source-root",
)
candidate_root = filesystem.register_root(
    registration.access,
    path=candidate_root_path,
    scope=FilesystemScope.PROJECT,
    mode=FilesystemMode.READ_WRITE,
    allow_remove=True,
    idempotency_key="installed-git-candidate-root",
)
repository = git.register_repository(
    registration.access,
    attempt,
    root_ref=source_root.root_ref,
    relative_path="source",
    expected_commit_sha=base_commit,
    expected_tree_sha=base_tree,
    idempotency_key="installed-git-register",
)
workspace = git.create_workspace(
    registration.access,
    attempt,
    repository,
    candidate_root_ref=candidate_root.root_ref,
    relative_path="candidate",
    require_source_head=True,
    idempotency_key="installed-git-workspace",
)
patch = b"""diff --git a/tracked.txt b/tracked.txt
--- a/tracked.txt
+++ b/tracked.txt
@@ -1 +1 @@
-installed base
+installed candidate
"""
diff = git.apply_patch(
    registration.access,
    attempt,
    workspace,
    patch_ref=objects.put(patch, media_type="text/x-diff"),
    expected_commit_sha=workspace.current_commit_sha,
    idempotency_key="installed-git-apply",
)
commit = git.commit(
    registration.access,
    attempt,
    workspace,
    expected_parent_commit_sha=workspace.current_commit_sha,
    message="Installed exact candidate",
    author_name="MiniTZ Installed",
    author_email="installed@example.invalid",
    idempotency_key="installed-git-commit",
)
print(
    json.dumps(
        {
            "commit_artifact_ref": commit.artifact_ref.value,
            "commit_call_id": commit.tool_call_ref.call_id,
            "commit_record_sha256": commit.record_sha256,
            "commit_sha": commit.commit_sha,
            "diff_artifact_ref": diff.artifact_ref.value,
            "diff_call_id": diff.tool_call_ref.call_id,
            "diff_record_sha256": diff.record_sha256,
            "project_id": registration.project.project_ref.value,
            "token": registration.access.token,
            "tree_sha": commit.tree_sha,
        },
        sort_keys=True,
    )
)
