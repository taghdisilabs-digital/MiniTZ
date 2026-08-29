"""Read P2-04 isolated-runtime evidence after an installed-wheel restart."""

from __future__ import annotations

import json
import os
from pathlib import Path

from biella import (
    ArtifactService,
    DockerIsolatedRuntimeAdapter,
    FilesystemObjectStorageBackend,
    ProjectAccess,
    ProjectRef,
    RuntimeCollectionReceipt,
    RuntimeRef,
    RuntimeStatus,
    ToolCallRef,
)


expected = json.loads(os.environ["BIELLA_EXPECTED"])
database = Path(os.environ["BIELLA_DATABASE"])
objects = FilesystemObjectStorageBackend(Path(os.environ["BIELLA_OBJECT_ROOT"]))
project_ref = ProjectRef(expected["project_id"])
access = ProjectAccess(project_ref, expected["token"])
adapter = DockerIsolatedRuntimeAdapter(database, objects, runtime_root=Path(os.environ["BIELLA_RUNTIME_ROOT"]))
collection = adapter.get_receipt(access, ToolCallRef(project_ref, expected["collection_call_id"]))
cleanup = adapter.get_receipt(access, ToolCallRef(project_ref, expected["cleanup_call_id"]))
state = adapter.get_state(
    access,
    RuntimeRef(project_ref, expected["runtime_id"], expected["runtime_generation"]),
)
assert isinstance(collection, RuntimeCollectionReceipt)
assert collection.record_sha256 == expected["collection_record_sha256"]
assert cleanup.record_sha256 == expected["cleanup_record_sha256"]
assert state.status is RuntimeStatus.CLEANED
assert state == cleanup.state
assert collection.output_artifact_refs[0].value == expected["output_artifact_ref"]
artifact = ArtifactService(database).get_artifact(access, collection.output_artifact_refs[0])
assert artifact.content_ref is not None
assert objects.read(artifact.content_ref) == b"installed isolated output\n"
print(
    json.dumps(
        {
            "cleanup_record_sha256": cleanup.record_sha256,
            "collection_record_sha256": collection.record_sha256,
            "output_artifact_ref": collection.output_artifact_refs[0].value,
            "runtime_ref": state.runtime_ref.value,
            "status": state.status.value,
        },
        sort_keys=True,
    )
)
