"""Read P2-02 managed-process evidence after an installed-wheel restart."""

from __future__ import annotations

import json
import os
from pathlib import Path

from biella import (
    FilesystemObjectStorageBackend,
    ManagedProcessAdapter,
    ProjectAccess,
    ProjectRef,
    ToolCallRef,
)


database = Path(os.environ["BIELLA_DATABASE"])
object_root = Path(os.environ["BIELLA_OBJECT_ROOT"])
expected = json.loads(os.environ["BIELLA_EXPECTED"])
project_ref = ProjectRef(expected["project_id"])
access = ProjectAccess(project_ref, expected["token"])
objects = FilesystemObjectStorageBackend(object_root)
adapter = ManagedProcessAdapter(database, objects, inherited_environment={"LANG": "C.UTF-8"})
result = adapter.get_result(access, ToolCallRef(project_ref, expected["call_id"]))
assert result.artifact_ref.value == expected["artifact_ref"]
assert result.result_ref.value == expected["result_ref"]
assert result.stdout_ref.value == expected["stdout_ref"]
assert result.record_sha256 == expected["record_sha256"]
assert result.process_identity is not None
assert result.process_identity.record_sha256 == expected["process_record_sha256"]
assert not adapter._identity_is_current(result.process_identity)
assert objects.read(result.stdout_ref) == b"INSTALLED PROCESS STDIN"
print(
    json.dumps(
        {
            "artifact_ref": result.artifact_ref.value,
            "process_record_sha256": result.process_identity.record_sha256,
            "record_sha256": result.record_sha256,
            "result_ref": result.result_ref.value,
            "stdout_ref": result.stdout_ref.value,
        },
        sort_keys=True,
    )
)
