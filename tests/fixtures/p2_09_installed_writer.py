from __future__ import annotations

import json
import os
from pathlib import Path

from biella import (
    ArtifactService,
    FilesystemObjectStorageBackend,
    ProjectStore,
    ReplicaBackendClass,
    ReplicaBackendRegistration,
    ReplicatedObjectStore,
    SQLiteObjectStorageBackend,
)


database = Path(os.environ["BIELLA_DATABASE"])
local_root = Path(os.environ["BIELLA_LOCAL_OBJECT_ROOT"])
reference_database = Path(os.environ["BIELLA_REFERENCE_DATABASE"])
evidence_path = Path(os.environ["BIELLA_EVIDENCE"])
projects = ProjectStore(database)
artifacts = ArtifactService(database)
registration = projects.create_project(
    namespace="installed-replica",
    display_name="Installed Replica",
)
local = FilesystemObjectStorageBackend(local_root)
reference = SQLiteObjectStorageBackend(reference_database)
payload = b"installed restart exact replica"
content_ref = local.put(payload, media_type="application/octet-stream")
artifact = artifacts.create_artifact(
    registration.access,
    project_ref=registration.project.project_ref,
    role="document.source",
    content_ref=content_ref,
    source_refs=(),
    source_artifact_refs=(),
    source_content_refs=(),
    derivation_type="artifact.imported",
    metadata={},
)
store = ReplicatedObjectStore(
    database,
    artifacts,
    (
        ReplicaBackendRegistration(
            "local-a",
            local,
            ReplicaBackendClass.REAL,
            "biella.filesystem.v1",
            10,
        ),
        ReplicaBackendRegistration(
            "reference-b",
            reference,
            ReplicaBackendClass.REFERENCE,
            "biella.sqlite-reference.v1",
            20,
        ),
    ),
)
store.registerArtifactReplica(
    registration.access,
    artifact.artifact_ref,
    "local-a",
)
store.replicateContent(
    registration.access,
    artifact.artifact_ref,
    "reference-b",
)
store.deleteReplica(
    registration.access,
    artifact.artifact_ref,
    "local-a",
)
evidence_path.write_text(
    json.dumps(
        {
            "artifact_id": artifact.artifact_id,
            "artifact_record_sha256": artifact.record_sha256,
            "artifact_revision": artifact.revision,
            "content_digest": content_ref.digest,
            "project_id": artifact.project_ref.value,
            "token": registration.access.token,
        },
        separators=(",", ":"),
        sort_keys=True,
    ),
    encoding="utf-8",
)
print("writer-complete")
