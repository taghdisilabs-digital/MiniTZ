"""Verify durable P2-06 evidence in a separate installed-wheel process."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

from biella import (
    FilesystemObjectStorageBackend,
    InferResult,
    ModelDeploymentRef,
    ModelExecutionRef,
    ProjectAccess,
    ProjectRef,
    ReferenceModelAdapter,
)


def main() -> None:
    database = Path(os.environ["BIELLA_DATABASE"])
    evidence = json.loads(Path(os.environ["BIELLA_EVIDENCE"]).read_text(encoding="utf-8"))
    project_ref = ProjectRef(cast(str, evidence["project_ref"]))
    access = ProjectAccess(project_ref, os.environ["BIELLA_TOKEN"])
    adapter = ReferenceModelAdapter(database, FilesystemObjectStorageBackend(Path(os.environ["BIELLA_OBJECT_ROOT"])))
    deployment = adapter.get_deployment(access, ModelDeploymentRef(project_ref, cast(str, evidence["deployment_id"])))
    result = adapter.get_result(access, ModelExecutionRef(project_ref, cast(str, evidence["execution_id"])))
    assert isinstance(result, InferResult)
    assert deployment.runtime_identity.reality == "REFERENCE"
    assert deployment.runtime_identity.model_revision == "installed-reference-v1"
    assert result.text == evidence["text"] == "installed restart exact"
    assert result.evidence.model_call_ref.call_id == evidence["model_call_id"]
    assert result.evidence.receipt_artifact_ref.value == evidence["receipt_artifact"]
    assert result.evidence.output_ref is not None
    assert result.evidence.output_ref.digest == evidence["output_digest"]
    print(json.dumps({"restart": "verified", "text": result.text}, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
