from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

_STAGE_CLASSES = {
    "RECEIPT_SCHEMA_VALIDATION", "PRIVATE_SECRET_LEAK_VALIDATION",
    "GIT_SOURCE_FINGERPRINT", "D17_CONTINUITY", "TASK_PROGRAM_VALIDATION",
    "SOURCE_HARVEST_VALIDATION", "SERVICE_READBACK", "PROCESS_READBACK",
    "GPU_READBACK", "TEST_SUITE_READBACK",
}


@dataclass(frozen=True)
class StageOutcome:
    result: str
    evidence_refs: tuple[str, ...] = ()
    exit_status: int = 0
    failure_type: str | None = None


@dataclass(frozen=True)
class AuditStage:
    stage_id: str
    run: Callable[[], StageOutcome]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _combined_result(results: Sequence[str]) -> str:
    if any(result == "FAIL" for result in results):
        return "FAIL"
    if any(result in {"PARTIAL", "UNKNOWN"} for result in results):
        return "PARTIAL"
    return "PASS"


def run_staged_audit(stages: Sequence[AuditStage]) -> dict[str, object]:
    records: list[dict[str, object]] = []
    for stage in stages:
        if stage.stage_id not in _STAGE_CLASSES:
            raise ValueError(f"unsupported audit stage: {stage.stage_id}")
        started_at = _now(); started = time.monotonic()
        try:
            outcome = stage.run()
            result = str(outcome.result).upper()
            if result not in {"PASS", "FAIL", "PARTIAL", "UNKNOWN"}:
                result = "UNKNOWN"
            exit_status = int(outcome.exit_status)
            evidence = [str(item) for item in outcome.evidence_refs]
            failure_type = outcome.failure_type
        except Exception as exc:
            result = "FAIL"; exit_status = 1; evidence = []
            failure_type = type(exc).__name__
        records.append({
            "stage_id": stage.stage_id, "started_at": started_at, "completed_at": _now(),
            "exit_status": exit_status, "result": result, "evidence_refs": evidence,
            "duration": max(0.0, time.monotonic() - started),
            "failure_type_if_any": failure_type,
        })
    receipt: dict[str, object] = {
        "schema": "minitz.staged_audit_receipt/v1", "authority": "NONE",
        "mutation_authority": False, "progression_authority": False,
        "contains_all_stage_results": True,
        "result": _combined_result([str(row["result"]) for row in records]), "stages": records,
    }
    receipt["receipt_digest"] = _digest(receipt)
    return receipt


def write_receipt(path: Path, receipt: dict[str, object]) -> None:
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") == encoded:
            return
        raise FileExistsError(f"immutable audit receipt already exists: {target}")
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
        try:
            os.link(tmp, target)
        except FileExistsError:
            if target.read_text(encoding="utf-8") == encoded:
                return
            raise FileExistsError(f"immutable audit receipt already exists: {target}")
    finally:
        tmp.unlink(missing_ok=True)
