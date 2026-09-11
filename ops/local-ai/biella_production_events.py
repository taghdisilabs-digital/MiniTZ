from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_MAX_TEXT = 4000
_EVENT_STREAM_ID = "minitz-production-events-v1"
_FAILURE_STREAM_ID = "minitz-production-failures-v1"
_SEMANTIC_GRAPH = "MiniTZ"
_EVIDENCE_FAMILY_REF = "semantic-family://minitz/event-evidence/v1"
_EVIDENCE_FAMILY_REVISION = 1
_EVIDENCE_AUTHORITY = "NONE_DERIVED_EVIDENCE"
_RESERVED_EVENT_FIELDS = frozenset({
    "seq", "time", "lane", "type", "authority", "journal_event_ref",
    "record_kind", "semantic_graph", "semantic_family_ref", "family_revision",
    "projection_authority", "progression_authority", "evidence_authority",
})
_PROVENANCE_FIELDS = (
    "project_ref", "project_id", "task_ref", "task_id", "session_id",
    "run_ref", "run_id", "run_attempt_id", "attempt_id", "node_attempt_id",
    "event_ref", "call_ref", "model_call_ref", "tool_call_ref",
    "bounded_packet_id", "lane_id", "role",
)


def _family_fields(record_kind: str) -> dict[str, Any]:
    """Return non-authoritative identity fields for one journal realization."""

    return {
        "record_kind": record_kind,
        "semantic_graph": _SEMANTIC_GRAPH,
        "semantic_family_ref": _EVIDENCE_FAMILY_REF,
        "family_revision": _EVIDENCE_FAMILY_REVISION,
        "authority": _EVIDENCE_AUTHORITY,
        "evidence_authority": _EVIDENCE_AUTHORITY,
        "projection_authority": False,
        "progression_authority": False,
    }


def _journal_event_ref(seq: object) -> str | None:
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
        return None
    return f"journal-event://{_EVENT_STREAM_ID}/{seq}"


def _occurrence_ref(
    stream_id: str, source_kind: str, line_number: int, raw_sha256: str,
    journal_event_ref: str | None,
) -> str:
    anchor = journal_event_ref or f"line:{line_number}"
    identity = f"{stream_id}\0{source_kind}\0{anchor}\0{raw_sha256}".encode("utf-8")
    return "journal-evidence://sha256/" + hashlib.sha256(identity).hexdigest()


def _project_stream(path: Path, *, source_kind: str, stream_id: str):
    path = Path(path)
    if not path.exists():
        return
    with path.open("rb") as handle:
        for line_number, raw in enumerate(handle, 1):
            raw_sha256 = hashlib.sha256(raw).hexdigest()
            evidence = {
                "schema": "minitz.operational_evidence_projection/v1",
                **_family_fields(source_kind),
                "evidence_ref": None,
                "source_kind": source_kind,
                "source_stream": stream_id,
                "source_line": line_number,
                "raw_sha256": raw_sha256,
                "parse_state": "JSON",
                "journal_event_ref": None,
                "legacy_event_identity": None,
                "event_type": None,
                "failure_type": None,
                "failure_classification": None,
                "status": None,
                "recorded_at": None,
                "source_schema": None,
                "provenance": {},
            }
            try:
                item = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                evidence["parse_state"] = "OPAQUE_INVALID_JSON"
                evidence["evidence_ref"] = _occurrence_ref(
                    stream_id, source_kind, line_number, raw_sha256, None
                )
                yield evidence
                continue
            if not isinstance(item, Mapping):
                evidence["parse_state"] = "OPAQUE_NON_OBJECT_JSON"
                evidence["evidence_ref"] = _occurrence_ref(
                    stream_id, source_kind, line_number, raw_sha256, None
                )
                yield evidence
                continue
            explicit_ref = item.get("journal_event_ref")
            if source_kind == "FAILURE":
                explicit_ref = item.get("origin_event_ref") or explicit_ref
            if isinstance(explicit_ref, str) and explicit_ref:
                event_ref = explicit_ref
            elif source_kind == "EVENT":
                event_ref = _journal_event_ref(item.get("seq"))
            elif item.get("schema") == "biella.failure_event/v1":
                event_ref = _journal_event_ref(item.get("seq"))
            else:
                event_ref = None
            evidence["journal_event_ref"] = event_ref
            evidence["legacy_event_identity"] = event_ref
            evidence["evidence_ref"] = _occurrence_ref(
                stream_id, source_kind, line_number, raw_sha256, event_ref
            )
            evidence["event_type"] = item.get("event_type") if source_kind == "FAILURE" else item.get("type")
            evidence["failure_type"] = item.get("failure_type")
            evidence["failure_classification"] = item.get("failure_type")
            evidence["status"] = item.get("status")
            evidence["recorded_at"] = item.get("time")
            evidence["source_schema"] = item.get("schema")
            evidence["provenance"] = {
                key: item[key] for key in _PROVENANCE_FIELDS
                if key in item and item[key] not in (None, "")
            }
            yield evidence


def _journal_segment_paths(path: Path) -> tuple[Path, ...]:
    path = Path(path)
    previous = path.with_name(path.stem + ".previous" + path.suffix)
    archives = tuple(sorted(path.parent.glob(path.stem + ".archive.*" + path.suffix)))
    candidates = ([previous] if previous.exists() else []) + list(archives) + ([path] if path.exists() else [])
    return tuple(candidates)


def project_operational_evidence(events_path: Path, failures_path: Path):
    """Yield a rebuildable, authority-free view over raw operational journals.

    Raw JSONL bytes remain the evidence. This projection only binds exact source
    occurrences, preserves legacy event/failure identity where it is explicit or
    safely derivable from the event stream, and never allocates EventLedger IDs.
    Rotated event segments are included without becoming a second truth store.
    """

    event_segments = sorted(
        _journal_segment_paths(Path(events_path)),
        key=lambda candidate: (_last_seq_in_file(candidate), candidate.name),
    )
    for segment in event_segments:
        yield from _project_stream(segment, source_kind="EVENT", stream_id=_EVENT_STREAM_ID)
    yield from _project_stream(Path(failures_path), source_kind="FAILURE", stream_id=_FAILURE_STREAM_ID)


def _bounded(value: object, limit: int = _MAX_TEXT) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _last_seq_in_file(path: Path) -> int:
    path = Path(path)
    if not path.exists():
        return 0
    try:
        tail = path.read_bytes()[-131072:].decode("utf-8", errors="ignore")
    except OSError:
        return 0
    for raw in reversed(tail.splitlines()):
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(item, Mapping):
            try:
                return int(item.get("seq") or 0)
            except (TypeError, ValueError):
                continue
    return 0


def _last_seq(path: Path) -> int:
    return max((_last_seq_in_file(item) for item in _journal_segment_paths(path)), default=0)


class ProductionEventJournal:
    def __init__(self, path: Path, *, max_bytes: int = 32 * 1024 * 1024, failure_path: Path | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max(1024, int(max_bytes)) if max_bytes >= 1024 else int(max_bytes)
        self._seq = _last_seq(self.path)
        self.failure_path = Path(failure_path) if failure_path is not None else None
        if self.failure_path is not None:
            self.failure_path.parent.mkdir(parents=True, exist_ok=True)

    def _rotate_if_needed(self) -> None:
        try:
            if not self.path.exists() or self.path.stat().st_size < self.max_bytes:
                return
        except OSError:
            return
        previous = self.path.with_name(self.path.stem + ".previous" + self.path.suffix)
        try:
            if not previous.exists():
                destination = previous
            else:
                raw = self.path.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()[:20]
                destination = self.path.with_name(
                    f"{self.path.stem}.archive.{digest}{self.path.suffix}"
                )
                duplicate_index = 2
                while destination.exists():
                    destination = self.path.with_name(
                        f"{self.path.stem}.archive.{digest}.{duplicate_index}{self.path.suffix}"
                    )
                    duplicate_index += 1
            os.replace(self.path, destination)
        except OSError:
            return

    def emit(self, event_type: str, *, task_id: str | None = None,
             text: str | None = None, status: str | None = None,
             **fields: Any) -> dict[str, Any]:
        self._rotate_if_needed()
        self._seq += 1
        event: dict[str, Any] = {
            "seq": self._seq,
            "time": datetime.now(timezone.utc).isoformat(),
            "lane": "MiniTZ OS",
            "type": str(event_type),
            "journal_event_ref": _journal_event_ref(self._seq),
            **_family_fields("EVENT"),
        }
        if task_id:
            event["task_id"] = str(task_id)
        if text:
            event["text"] = _bounded(text)
        if status:
            event["status"] = str(status)
        for key, value in fields.items():
            if key in _RESERVED_EVENT_FIELDS or value is None:
                continue
            if isinstance(value, str):
                event[key] = _bounded(value)
            else:
                event[key] = value
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        status_key = str(event.get("status") or "").upper()
        type_key = str(event.get("type") or "").lower()
        is_failure = status_key in {"FAILED", "ERROR", "RETRY"} or any(token in type_key for token in ("error", "failed", "retry", "recovery"))
        if is_failure and self.failure_path is not None:
            failure = {
                "schema": "biella.failure_event/v1",
                "seq": event["seq"], "time": event["time"], "lane": event["lane"],
                "failure_type": event.get("failure_type") or event["type"],
                "failure_classification": event.get("failure_type") or event["type"],
                "event_type": event["type"], "status": event.get("status") or "FAILED",
                "origin_event_ref": event["journal_event_ref"],
                "legacy_event_identity": event["journal_event_ref"],
                **_family_fields("FAILURE"),
            }
            for key in _PROVENANCE_FIELDS + (
                "text", "tool", "detail", "exit_code", "model", "reasoning",
                "helper_budget_seconds", "elapsed_seconds", "raw_result_path",
                "raw_result_sha256", "raw_result_bytes", "evidence_ref", "provider",
            ):
                if key in event:
                    failure[key] = event[key]
            with self.failure_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(failure, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return event

    def emit_codex(self, raw: Mapping[str, Any], task_id: str) -> dict[str, Any] | None:
        projected = project_codex_event(raw, task_id)
        if not projected:
            return None
        event_type = str(projected.pop("type"))
        text = projected.pop("text", None)
        status = projected.pop("status", None)
        return self.emit(event_type, task_id=task_id, text=text, status=status, **projected)


def _summary_text(value: object) -> str:
    if isinstance(value, str):
        return _bounded(value)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                candidate = item.get("text") or item.get("summary_text")
                if candidate:
                    parts.append(str(candidate))
        return _bounded(" ".join(parts))
    if isinstance(value, Mapping):
        return _summary_text(value.get("text") or value.get("summary_text"))
    return ""


def _item_text(item: Mapping[str, Any]) -> str:
    for key in ("text", "message", "output_text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return _bounded(value)
    content = item.get("content")
    if isinstance(content, list):
        return _summary_text(content)
    return ""


def project_codex_event(raw: Mapping[str, Any], task_id: str) -> dict[str, Any] | None:
    del task_id
    event_type = str(raw.get("type") or "")
    if event_type in {"thread.started", "turn.started"}:
        result: dict[str, Any] = {"type": event_type}
        if raw.get("thread_id"):
            result["session_id"] = str(raw["thread_id"])
        return result
    if event_type == "turn.completed":
        usage = raw.get("usage")
        result = {"type": "turn.completed"}
        if isinstance(usage, Mapping):
            result["usage"] = {
                key: int(usage[key])
                for key in ("input_tokens", "cached_input_tokens", "output_tokens")
                if isinstance(usage.get(key), (int, float))
            }
        return result
    if event_type in {"error", "turn.failed"}:
        return {"type": "agent.error", "status": "FAILED", "text": _bounded(raw.get("message") or raw.get("error") or event_type)}
    if event_type not in {"item.started", "item.completed"}:
        return None
    item = raw.get("item")
    if not isinstance(item, Mapping):
        return None
    item_type = str(item.get("type") or "")
    phase = "started" if event_type.endswith("started") else "completed"
    if item_type in {"agent_message", "message"}:
        text = _item_text(item)
        return {"type": "agent.message", "text": text} if text else None
    if item_type == "reasoning":
        summary = _summary_text(item.get("summary"))
        return {"type": "agent.reasoning_summary", "text": summary} if summary else None
    if item_type in {"command_execution", "local_shell_call"}:
        command = item.get("command") or item.get("cmd") or "command"
        if isinstance(command, list):
            command = " ".join(str(part) for part in command)
        result = {
            "type": f"tool.{phase}",
            "tool": "shell",
            "text": _bounded(command, 1200),
            "status": str(item.get("status") or phase).upper(),
        }
        if isinstance(item.get("exit_code"), int):
            result["exit_code"] = int(item["exit_code"])
        if result["status"] in {"FAILED", "ERROR"}:
            detail = item.get("aggregated_output") or item.get("output") or item.get("stderr")
            if detail:
                result["detail"] = _bounded(detail, 2000)
        return result
    if item_type in {"mcp_tool_call", "function_call", "custom_tool_call"}:
        name = item.get("name") or item.get("tool") or item.get("tool_name") or item_type
        return {
            "type": f"tool.{phase}",
            "tool": _bounded(name, 200),
            "text": _bounded(name, 200),
            "status": str(item.get("status") or phase).upper(),
        }
    if item_type in {"file_change", "patch_apply"}:
        return {"type": f"tool.{phase}", "tool": "file_change", "text": "file change", "status": phase.upper()}
    return None
