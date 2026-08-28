"""Read P2-01 filesystem evidence after an installed-process restart."""

from __future__ import annotations

import json
import os
from pathlib import Path

from biella import (
    FilesystemAdapter,
    FilesystemObjectStorageBackend,
    FilesystemRootRef,
    ProjectAccess,
    ProjectRef,
    ToolCallRef,
)


database = Path(os.environ["BIELLA_DATABASE"])
object_root = Path(os.environ["BIELLA_OBJECT_ROOT"])
expected = json.loads(os.environ["BIELLA_EXPECTED"])
project_ref = ProjectRef(expected["project_id"])
access = ProjectAccess(project_ref, expected["token"])
adapter = FilesystemAdapter(database, FilesystemObjectStorageBackend(object_root))
root = adapter.get_root(access, FilesystemRootRef(project_ref, expected["root_id"]))
operation = adapter.get_operation(access, ToolCallRef(project_ref, expected["call_id"]))
assert root.project_ref == project_ref
assert operation.artifact_ref.value == expected["artifact_ref"]
assert operation.output_ref.value == expected["content_ref"]
assert operation.record_sha256 == expected["record_sha256"]
print(
    json.dumps(
        {
            "artifact_ref": operation.artifact_ref.value,
            "content_ref": operation.output_ref.value,
            "record_sha256": operation.record_sha256,
            "root_record_sha256": root.record_sha256,
        },
        sort_keys=True,
    )
)
