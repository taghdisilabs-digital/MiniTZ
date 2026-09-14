"""Read P2-03 Git evidence after an installed-wheel process restart."""

from __future__ import annotations

import json
import os
from pathlib import Path

from minitz_os.engine import (
    FilesystemObjectStorageBackend,
    GitAdapter,
    ProjectAccess,
    ProjectRef,
    RepositoryCommitReceipt,
    RepositoryDiffReceipt,
    ToolCallRef,
)


database = Path(os.environ["MINITZ_DATABASE"])
object_root = Path(os.environ["MINITZ_OBJECT_ROOT"])
expected = json.loads(os.environ["MINITZ_EXPECTED"])
project_ref = ProjectRef(expected["project_id"])
access = ProjectAccess(project_ref, expected["token"])
objects = FilesystemObjectStorageBackend(object_root)
adapter = GitAdapter(database, objects)
diff = adapter.get_receipt(access, ToolCallRef(project_ref, expected["diff_call_id"]))
commit = adapter.get_receipt(access, ToolCallRef(project_ref, expected["commit_call_id"]))
assert isinstance(diff, RepositoryDiffReceipt)
assert isinstance(commit, RepositoryCommitReceipt)
assert diff.artifact_ref.value == expected["diff_artifact_ref"]
assert diff.record_sha256 == expected["diff_record_sha256"]
assert b"installed candidate" in objects.read(diff.unstaged_diff_ref)
assert commit.artifact_ref.value == expected["commit_artifact_ref"]
assert commit.record_sha256 == expected["commit_record_sha256"]
assert commit.commit_sha == expected["commit_sha"]
assert commit.tree_sha == expected["tree_sha"]
print(
    json.dumps(
        {
            "commit_artifact_ref": commit.artifact_ref.value,
            "commit_record_sha256": commit.record_sha256,
            "commit_sha": commit.commit_sha,
            "diff_artifact_ref": diff.artifact_ref.value,
            "diff_record_sha256": diff.record_sha256,
            "tree_sha": commit.tree_sha,
        },
        sort_keys=True,
    )
)
