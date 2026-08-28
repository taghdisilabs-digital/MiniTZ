from __future__ import annotations

import os
from pathlib import Path

import biella
from biella import (
    ArtifactService,
    CheckpointService,
    ContentRef,
    FilesystemObjectStorageBackend,
    ProjectAccess,
    ProjectRef,
    RunCheckpointRef,
    RunMemoryService,
    RunRef,
)


installed = Path(os.environ["BIELLA_INSTALLED"]).resolve()
assert Path(biella.__file__).resolve().is_relative_to(installed)
database = Path(os.environ["BIELLA_DATABASE"])
project_ref = ProjectRef(os.environ["BIELLA_PROJECT_ID"])
access = ProjectAccess(project_ref, os.environ["BIELLA_TOKEN"])
run_ref = RunRef(project_ref, os.environ["BIELLA_RUN_ID"])
memory = RunMemoryService(database).reconstruct(access, run_ref)
authority = memory.run_attempts[-1]
service = CheckpointService(
    database,
    FilesystemObjectStorageBackend(Path(os.environ["BIELLA_OBJECT_ROOT"])),
)
checkpoint_ref = RunCheckpointRef(project_ref, os.environ["BIELLA_CHECKPOINT_ID"])
result = service.resume_run(
    access,
    run_ref,
    checkpoint_ref=checkpoint_ref,
    authority_attempt=authority,
    idempotency_key="wheel-resume-b",
)
by_value = {item.node_ref.value: item for item in result.memory.graphs[-1].nodes}
a = by_value[os.environ["BIELLA_A_REF"]]
b = by_value[os.environ["BIELLA_B_REF"]]
assert a.latest is not None and a.latest.status == "SUCCEEDED"
assert a.latest.outputs["result"] == os.environ["BIELLA_OUTPUT_REF"]
assert b.latest is not None and b.latest.status == "READY"
new_attempt = service.executions.lease_node(
    access,
    b.node_ref,
    authority_attempt=authority,
    owner_ref="executor://wheel-b-new",
    lease_seconds=60,
    idempotency_key="wheel-b-new-lease",
)
assert new_attempt.fence == int(os.environ["BIELLA_OLD_FENCE"]) + 1
service.executions.start_node(
    access,
    new_attempt,
    idempotency_key="wheel-b-new-start",
)
b_output = ArtifactService(database).publish_from_run(
    access,
    producer_attempt=authority,
    expected_task_ref=memory.task.task_ref,
    expected_task_digest=memory.task.canonical_digest,
    role="wheel.checkpoint-b-output",
    content_ref=ContentRef.from_bytes(b"wheel-b-output", media_type="text/plain"),
    source_refs=(),
    source_artifact_refs=(),
    source_content_refs=(),
    derivation_type="wheel.checkpoint.continuation",
    metadata={},
)
service.executions.finalize_node(
    access,
    new_attempt,
    outputs={"result": b_output.artifact_ref},
    evidence={},
    acceptance_criteria=(),
    idempotency_key="wheel-b-new-finalize",
)
completed = RunMemoryService(database).reconstruct(access, run_ref)
completed_nodes = {
    item.node_ref.value: item for item in completed.graphs[-1].nodes
}
completed_b = completed_nodes[os.environ["BIELLA_B_REF"]]
assert completed_b.latest is not None and completed_b.latest.status == "SUCCEEDED"
assert completed.run.status == "SUCCEEDED"
