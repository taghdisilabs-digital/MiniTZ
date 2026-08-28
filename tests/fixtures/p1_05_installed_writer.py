from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import TypedDict, cast

from biella import (
    CapabilityRef,
    CallLedgerService,
    ContentRef,
    GraphRef,
    NodeExecutionAttempt,
    NodeRef,
    ProjectAccess,
    ProjectRef,
    RunRef,
    TaskRef,
)


class AttemptConfig(TypedDict):
    attempt_id: str
    attempt_number: int
    fence: int
    graph_id: str
    graph_revision: int
    lease_acquired_at: str
    lease_expires_at: str
    node_id: str
    owner_ref: str
    run_attempt_id: str
    run_fence: int
    run_id: str
    task_digest: str
    task_id: str
    task_revision: int


class RequestConfig(TypedDict):
    algorithm: str
    digest: str
    media_type: str
    size_bytes: int


class WriterConfig(TypedDict):
    access_token: str
    attempt: AttemptConfig
    capability_id: str
    capability_version: str
    database_path: str
    project_id: str
    request: RequestConfig


def load_config(path: Path) -> WriterConfig:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("installed writer configuration is malformed")
    return cast(WriterConfig, raw)


def main() -> None:
    if len(sys.argv) != 3:
        raise ValueError("writer requires configuration and evidence paths")
    config = load_config(Path(sys.argv[1]))
    values = config["attempt"]
    project_ref = ProjectRef(config["project_id"])
    access = ProjectAccess(project_ref, config["access_token"])
    attempt = NodeExecutionAttempt(
        values["attempt_id"],
        NodeRef(
            GraphRef(
                project_ref,
                values["graph_id"],
                values["graph_revision"],
            ),
            values["node_id"],
        ),
        RunRef(project_ref, values["run_id"]),
        TaskRef(project_ref, values["task_id"], values["task_revision"]),
        values["task_digest"],
        values["attempt_number"],
        values["fence"],
        values["owner_ref"],
        values["run_attempt_id"],
        values["run_fence"],
        values["lease_acquired_at"],
        values["lease_expires_at"],
    )
    capability_ref = CapabilityRef(
        config["capability_id"],
        config["capability_version"],
    )
    request = config["request"]
    request_ref = ContentRef(
        request["algorithm"],
        request["digest"],
        request["size_bytes"],
        request["media_type"],
    )
    ledger = CallLedgerService(config["database_path"])
    original = ledger.start_model_call(
        access,
        attempt,
        idempotency_key="wheel-model-original",
        capability_ref=capability_ref,
        purpose="INITIAL",
        retry_of=None,
        provider_id="provider://wheel/reference",
        model_id="model://wheel/reference-v1",
        deployment_id="deployment://wheel/cpu",
        runtime_id="runtime://wheel/python",
        input_refs=(request_ref,),
        provider_trace_id=None,
    )
    original = ledger.finish_model_call(
        access,
        attempt,
        original.call_ref,
        idempotency_key="wheel-model-original-finish",
        status="FAILED",
        output_refs=(),
        usage=None,
        cost=None,
        failure_category="TRANSPORT",
        failure_reason="durable wheel transport failure",
        failure_evidence_refs=(),
    )
    retry = ledger.start_model_call(
        access,
        attempt,
        idempotency_key="wheel-model-retry",
        capability_ref=capability_ref,
        purpose="INFRASTRUCTURE_RETRY",
        retry_of=original.call_ref,
        provider_id="provider://wheel/reference",
        model_id="model://wheel/reference-v1",
        deployment_id="deployment://wheel/cpu",
        runtime_id="runtime://wheel/python",
        input_refs=(request_ref,),
        provider_trace_id=None,
    )
    tool = ledger.start_tool_call(
        access,
        attempt,
        idempotency_key="wheel-tool-nested",
        capability_ref=capability_ref,
        purpose="INITIAL",
        retry_of=None,
        parent_model_call_ref=retry.call_ref,
        tool_id="tool://wheel/reference",
        implementation_id="implementation://wheel/reference-v1",
        runtime_id="runtime://wheel/python",
        input_refs=(),
        provider_trace_id=None,
    )
    tool = ledger.finish_tool_call(
        access,
        attempt,
        tool.call_ref,
        idempotency_key="wheel-tool-nested-finish",
        status="SUCCEEDED",
        output_refs=(),
        usage=None,
        cost=None,
        failure_category=None,
        failure_reason=None,
        failure_evidence_refs=(),
    )
    retry = ledger.finish_model_call(
        access,
        attempt,
        retry.call_ref,
        idempotency_key="wheel-model-retry-finish",
        status="SUCCEEDED",
        output_refs=(),
        usage=None,
        cost=None,
        failure_category=None,
        failure_reason=None,
        failure_evidence_refs=(),
    )
    Path(sys.argv[2]).write_text(
        json.dumps(
            {
                "original": original.call_ref.call_id,
                "original_event": original.event_ref.event_id,
                "retry": retry.call_ref.call_id,
                "retry_event": retry.event_ref.event_id,
                "tool": tool.call_ref.call_id,
                "tool_event": tool.event_ref.event_id,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
