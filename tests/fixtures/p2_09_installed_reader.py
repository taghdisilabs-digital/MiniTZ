from __future__ import annotations

import json
import os
from pathlib import Path

from biella import (
    ArtifactRef,
    ArtifactService,
    FilesystemObjectStorageBackend,
    ProjectAccess,
    ProjectRef,
    ReplicaBackendClass,
    ReplicaBackendRegistration,
    ReplicaState,
    ReplicatedObjectStore,
    SQLiteObjectStorageBackend,
)


database = Path(os.environ["BIELLA_DATABASE"])
evidence = json.loads(Path(os.environ["BIELLA_EVIDENCE"]).read_text(encoding="utf-8"))
project_ref = ProjectRef(evidence["project_id"])
access = ProjectAccess(project_ref, evidence["token"])
artifact_ref = ArtifactRef(
    project_ref,
    evidence["artifact_id"],
    evidence["artifact_revision"],
)
artifacts = ArtifactService(database)
store = ReplicatedObjectStore(
    database,
    artifacts,
    (
        ReplicaBackendRegistration(
            "local-a",
            FilesystemObjectStorageBackend(os.environ["BIELLA_LOCAL_OBJECT_ROOT"]),
            ReplicaBackendClass.REAL,
            "biella.filesystem.v1",
            10,
        ),
        ReplicaBackendRegistration(
            "reference-b",
            SQLiteObjectStorageBackend(os.environ["BIELLA_REFERENCE_DATABASE"]),
            ReplicaBackendClass.REFERENCE,
            "biella.sqlite-reference.v1",
            20,
        ),
    ),
)
artifact = artifacts.get_artifact(access, artifact_ref)
locations = {item.backend_id: item for item in store.locations(access, artifact_ref)}
payload = store.readArtifact(access, artifact_ref)
assert artifact.record_sha256 == evidence["artifact_record_sha256"]
assert artifact.content_ref is not None
assert artifact.content_ref.digest == evidence["content_digest"]
assert locations["local-a"].state is ReplicaState.MISSING
assert locations["reference-b"].state is ReplicaState.AVAILABLE
print(
    json.dumps(
        {
            "content_digest": artifact.content_ref.digest,
            "payload": payload.decode("utf-8"),
            "restart": "verified",
            "served_backend": "reference-b",
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
