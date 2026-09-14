"""Verify durable P2-07 evidence in a separate installed-wheel process."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

from minitz_os.engine import (
    BrowserActionRef,
    BrowserSessionRef,
    BrowserSessionStatus,
    FilesystemObjectStorageBackend,
    ProjectAccess,
    ProjectRef,
    ReferenceBrowserAdapter,
    StdlibHttpAdapter,
)


def main() -> None:
    database = Path(os.environ["MINITZ_DATABASE"])
    objects = FilesystemObjectStorageBackend(Path(os.environ["MINITZ_OBJECT_ROOT"]))
    evidence = json.loads(Path(os.environ["MINITZ_EVIDENCE"]).read_text(encoding="utf-8"))
    project_ref = ProjectRef(cast(str, evidence["project_ref"]))
    access = ProjectAccess(project_ref, os.environ["MINITZ_TOKEN"])
    http = StdlibHttpAdapter(
        database,
        objects,
        supported_data_policy_refs=("policy://installed/browser-data",),
        supported_egress_policy_refs=("policy://installed/browser-egress",),
    )
    adapter = ReferenceBrowserAdapter(database, objects, http)
    state = adapter.inspect_session(access, BrowserSessionRef(project_ref, cast(str, evidence["session_id"])))
    result = adapter.get_result(access, BrowserActionRef(project_ref, cast(str, evidence["action_id"])))
    assert state.status is BrowserSessionStatus.ACTIVE
    assert result.succeeded and result.output_ref is not None and result.page_ref is not None
    assert result.output_ref.digest == evidence["output_digest"]
    assert result.page_ref.current_url == evidence["page_url"] == "http://installed.invalid/app"
    assert result.receipt_artifact_ref.value == evidence["receipt_artifact"]
    print(
        json.dumps(
            {
                "page_url": result.page_ref.current_url,
                "restart": "verified",
                "session_status": state.status.value,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
