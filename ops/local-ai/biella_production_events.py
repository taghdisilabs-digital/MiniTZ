from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_MAX_TEXT = 4000


def _bounded(value: object, limit: int = _MAX_TEXT) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _last_seq(path: Path) -> int:
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
            previous.unlink(missing_ok=True)
            os.replace(self.path, previous)
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
            "lane": "Games",
            "type": str(event_type),
        }
        if task_id:
            event["task_id"] = str(task_id)
        if text:
            event["text"] = _bounded(text)
        if status:
            event["status"] = str(status)
        for key, value in fields.items():
            if value is None:
                continue
            if isinstance(value, str):
                event[key] = _bounded(value)
            else:
                event[key] = value
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        status_key = str(event.get("status") or "").upper()
        type_key = str(event.get("type") or "").lower()
        is_failure = status_key in {"FAILED", "ERROR", "RETRY"} or any(token in type_key for token in ("error", "failed", "retry", "recovery"))
        if is_failure and self.failure_path is not None:
            failure = {
                "schema": "biella.failure_event/v1",
                "seq": event["seq"], "time": event["time"], "lane": event["lane"],
                "failure_type": event["type"], "status": event.get("status") or "FAILED",
            }
            for key in ("task_id", "text", "tool", "detail", "exit_code", "model", "reasoning"):
                if key in event:
                    failure[key] = event[key]
            with self.failure_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(failure, sort_keys=True, separators=(",", ":")) + "\n")
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
