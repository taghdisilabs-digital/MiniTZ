from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import TypedDict, cast

from biella import (
    CallLedgerService,
    EventRef,
    ModelCallRef,
    ProjectAccess,
    ProjectRef,
    RunMemoryService,
    RunRef,
    ToolCallRef,
)


class AttemptConfig(TypedDict):
    run_id: str


class ReaderConfig(TypedDict):
    access_token: str
    attempt: AttemptConfig
    database_path: str
    project_id: str


class Evidence(TypedDict):
    original: str
    original_event: str
    retry: str
    retry_event: str
    tool: str
    tool_event: str


def load_mapping(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("installed reader input is malformed")
    return cast(dict[str, object], raw)


def main() -> None:
    if len(sys.argv) != 3:
        raise ValueError("reader requires configuration and evidence paths")
    config = cast(ReaderConfig, load_mapping(Path(sys.argv[1])))
    evidence = cast(Evidence, load_mapping(Path(sys.argv[2])))
    project_ref = ProjectRef(config["project_id"])
    access = ProjectAccess(project_ref, config["access_token"])
    ledger = CallLedgerService(config["database_path"])
    original = ledger.get_model_call(
        access,
        ModelCallRef(project_ref, evidence["original"]),
    )
    retry = ledger.get_model_call(
        access,
        ModelCallRef(project_ref, evidence["retry"]),
    )
    tool = ledger.get_tool_call(
        access,
        ToolCallRef(project_ref, evidence["tool"]),
    )
    if original.status != "FAILED":
        raise AssertionError("installed original call status differs")
    if retry.status != "SUCCEEDED" or retry.retry_of != original.call_ref:
        raise AssertionError("installed retry lineage differs")
    if tool.status != "SUCCEEDED" or tool.parent_model_call_ref != retry.call_ref:
        raise AssertionError("installed nested ToolCall lineage differs")
    if ledger.get_model_call_for_event(
        access,
        EventRef(project_ref, evidence["original_event"]),
    ) != original:
        raise AssertionError("installed original Event mapping differs")
    if ledger.get_model_call_for_event(
        access,
        EventRef(project_ref, evidence["retry_event"]),
    ) != retry:
        raise AssertionError("installed retry Event mapping differs")
    if ledger.get_tool_call_for_event(
        access,
        EventRef(project_ref, evidence["tool_event"]),
    ) != tool:
        raise AssertionError("installed ToolCall Event mapping differs")
    memory = RunMemoryService(config["database_path"]).reconstruct(
        access,
        RunRef(project_ref, config["attempt"]["run_id"]),
    )
    call_refs = {item.call_ref for item in memory.extension_refs}
    if not {
        original.call_ref.value,
        retry.call_ref.value,
        tool.call_ref.value,
    }.issubset(call_refs):
        raise AssertionError("installed RunMemory call references differ")


if __name__ == "__main__":
    main()
