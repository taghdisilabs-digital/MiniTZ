"""Read P2-05 HTTP evidence after an installed-wheel process restart."""

from __future__ import annotations

import json
import os
from pathlib import Path

from biella import (
    FilesystemObjectStorageBackend,
    HttpExecutionRef,
    ProjectAccess,
    ProjectRef,
    StdlibHttpAdapter,
)


expected = json.loads(os.environ["BIELLA_EXPECTED"])
database = Path(os.environ["BIELLA_DATABASE"])
objects = FilesystemObjectStorageBackend(Path(os.environ["BIELLA_OBJECT_ROOT"]))
project_ref = ProjectRef(expected["project_id"])
access = ProjectAccess(project_ref, expected["token"])
adapter = StdlibHttpAdapter(database, objects)
result = adapter.get_result(access, HttpExecutionRef(project_ref, expected["execution_id"]))
assert result.record_sha256 == expected["record_sha256"]
assert result.response_ref is not None
assert result.response_ref.digest == expected["response_digest"]
assert result.response_artifact_ref is not None
assert result.response_artifact_ref.value == expected["response_artifact_ref"]
assert result.tool_call_ref.call_id == expected["tool_call_id"]
assert objects.read(result.response_ref) == b"installed-http-binary\x00response"
print(
    json.dumps(
        {
            "record_sha256": result.record_sha256,
            "response_artifact_ref": result.response_artifact_ref.value,
            "response_digest": result.response_ref.digest,
            "tool_call_id": result.tool_call_ref.call_id,
        },
        sort_keys=True,
    )
)
