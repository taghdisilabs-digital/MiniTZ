"""Verify durable P2-08 evidence in a separate installed-wheel process."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

from minitz_os.engine import (
    DatabaseOperationRef,
    FilesystemObjectStorageBackend,
    LibpqPostgreSQLAdapter,
    ProjectAccess,
    ProjectRef,
)


def main() -> None:
    database = Path(os.environ["MINITZ_DATABASE"])
    objects = FilesystemObjectStorageBackend(Path(os.environ["MINITZ_OBJECT_ROOT"]))
    evidence = json.loads(Path(os.environ["MINITZ_EVIDENCE"]).read_text(encoding="utf-8"))
    project_ref = ProjectRef(cast(str, evidence["project_ref"]))
    access = ProjectAccess(project_ref, os.environ["MINITZ_TOKEN"])
    adapter = LibpqPostgreSQLAdapter(database, objects)
    result = adapter.get_query_result(
        access,
        DatabaseOperationRef(project_ref, cast(str, evidence["operation_id"])),
    )
    assert result.success and result.result_ref is not None
    assert result.result_ref.digest == evidence["result_digest"]
    assert result.receipt_ref.digest == evidence["receipt_digest"]
    rows = objects.read(result.result_ref).splitlines()
    assert json.loads(rows[1]) == {"row": ["installed-restart"]}
    print(
        json.dumps(
            {
                "restart": "verified",
                "row_count": result.row_count,
                "tool_status": "SUCCEEDED",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    adapter.close()


if __name__ == "__main__":
    main()
