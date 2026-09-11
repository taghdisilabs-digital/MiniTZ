from __future__ import annotations

import copy
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from .biella_live_projection import LiveProjection, _iso_time, _read_json
except ImportError:
    from biella_live_projection import LiveProjection, _iso_time, _read_json


class MiniTZLiveProjection(LiveProjection):
    """Read-only public projection of the current MiniTZ execution surfaces."""

    def __init__(self, *, repo: Path, runtime_root: Path, assets, analysis_root: Path):
        super().__init__(repo=repo, runtime_root=runtime_root, assets=assets)
        self.analysis_root = Path(analysis_root)
        self.execution_root = self.analysis_root / "minitz_execution"
        self.program_path = self.analysis_root / "TASK_PROGRAM.json"

    def _latest_stream(self) -> Path | None:
        try:
            candidates = [path for path in self.execution_root.glob("*/stdout.jsonl") if path.is_file()]
        except OSError:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime, default=None)

    def _task_record(self, task_id: str) -> tuple[dict[str, object], dict[str, object]]:
        program = _read_json(self.program_path)
        tasks = program.get("tasks") if isinstance(program.get("tasks"), list) else []
        task = next((item for item in tasks if isinstance(item, dict) and str(item.get("task_id") or "") == task_id), {})
        return program, task

    def _checkpoint(self, task_id: str) -> dict[str, object]:
        direct = self.execution_root / f"CHECKPOINT_{task_id}.json"
        if direct.is_file():
            return _read_json(direct)
        newest: tuple[float, dict[str, object]] | None = None
        for path in self.execution_root.glob("CHECKPOINT_*.json"):
            value = _read_json(path)
            if str(value.get("task_id") or "") != task_id:
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if newest is None or mtime > newest[0]:
                newest = (mtime, value)
        return newest[1] if newest else {}

    @staticmethod
    def _safe_message(text: object) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip()
        value = value.replace("/root/biella/", "workspace/")
        value = value.replace("/mnt/biella-extra/", "runtime/")
        return value[:420]

    @staticmethod
    def _command_category(command: str) -> str:
        lower = command.lower()
        if "pytest" in lower or "unittest" in lower or " test" in lower or "/test_" in lower or "/verify_" in lower:
            return "TEST"
        if "build" in lower or "cmake" in lower or "ninja" in lower:
            return "BUILD"
        if "git commit" in lower:
            return "COMMIT"
        return "TOOL"

    def _normalized_events(self, stream: Path | None, limit: int = 240) -> list[dict[str, object]]:
        if stream is None:
            return []
        try:
            lines = stream.read_text(encoding="utf-8", errors="replace").splitlines()
            when = datetime.fromtimestamp(stream.stat().st_mtime, tz=timezone.utc).isoformat()
            task_files = [path for path in stream.parent.iterdir() if path.is_file()]
            base_mtime_ns = min((path.stat().st_mtime_ns for path in task_files), default=stream.stat().st_mtime_ns)
            event_base = int(base_mtime_ns // 1_000_000) * 1000
        except OSError:
            return []
        task_id = stream.parent.name
        result: list[dict[str, object]] = []
        for index, line in enumerate(lines, 1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(raw, dict):
                continue
            raw_type = str(raw.get("type") or "")
            item = raw.get("item") if isinstance(raw.get("item"), dict) else {}
            item_type = str(item.get("type") or "")
            state = "RUNNING" if raw_type.endswith(".started") else "COMPLETED" if raw_type.endswith(".completed") else "INFO"
            category = "MINITZ"
            text = "MiniTZ task activity"
            if raw_type in {"turn.started", "turn.completed"}:
                text = "MiniTZ execution turn started" if raw_type.endswith("started") else "MiniTZ execution turn completed"
            elif item_type == "agent_message":
                text = self._safe_message(item.get("text")) or "MiniTZ task update"
            elif item_type == "command_execution":
                command = str(item.get("command") or "")
                category = self._command_category(command)
                exit_code = item.get("exit_code")
                if raw_type.endswith(".completed") and exit_code not in (None, 0):
                    state = "FAILED"
                labels = {"TEST": "Validation", "BUILD": "Build", "COMMIT": "Commit", "TOOL": "Tool"}
                text = f"{task_id} · {labels[category]} {state.lower()}"
            elif item_type == "file_change":
                category = "ARTIFACT"
                text = f"{task_id} · source/output changed"
            else:
                continue
            result.append({
                "event_id": event_base + index,
                "seq": event_base + index,
                "time": when,
                "task_id": task_id,
                "category": category,
                "state": state,
                "text": text,
                "operation_kind": category,
            })
        return result[-limit:]

    def events_since(self, after_id: int) -> list[dict[str, object]]:
        return [event for event in self._normalized_events(self._latest_stream()) if int(event.get("event_id") or 0) > after_id]

    @staticmethod
    def sanitize_event(event: dict[str, object]) -> dict[str, object] | None:
        return copy.deepcopy(event)

    def refresh(self, *, force_assets: bool = False, force_system: bool = False, force_git: bool = False) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        runtime = _read_json(self.runtime_path)
        production_status = self._production_status()
        raw_coder_statuses = runtime.get("coder_statuses") if isinstance(runtime.get("coder_statuses"), dict) else {}
        coder_statuses = {
            "codex": str(raw_coder_statuses.get("codex") or "NEEDS_MODIFICATION"),
            "agr": str(raw_coder_statuses.get("agr") or "NEEDS_MODIFICATION"),
        }
        raw_coder_detail = runtime.get("coder_status_detail") if isinstance(runtime.get("coder_status_detail"), dict) else {}
        coder_detail = {key: str(value)[:240] for key, value in raw_coder_detail.items() if key in {"codex", "agr"} and value}
        active_coder = str(runtime.get("active_coder") or "codex")
        stream = self._latest_stream()
        task_id = stream.parent.name if stream else "UNKNOWN"
        program, task = self._task_record(task_id)
        checkpoint = self._checkpoint(task_id)
        events = self._normalized_events(stream)
        current = events[-1] if events else None

        stopped_at = _iso_time(checkpoint.get("stopped_at"))
        stream_time = None
        if stream:
            try:
                stream_time = datetime.fromtimestamp(stream.stat().st_mtime, tz=timezone.utc)
            except OSError:
                pass
        preserved_stop = bool(stopped_at and (stream_time is None or stopped_at >= stream_time))
        production_state = "WAITING" if preserved_stop else ("WORKING" if current and current.get("state") == "RUNNING" else "READY")
        checkpoint_program = checkpoint.get("task_program") if isinstance(checkpoint.get("task_program"), dict) else {}
        task_status = str(checkpoint_program.get("task_status") or task.get("status") or "UNKNOWN")

        title = str(task.get("title") or task_id)
        if preserved_stop:
            summary = "MiniTZ task checkpoint is preserved and ready for continuation."
            current = {
                "event_id": 0, "seq": 0, "time": str(checkpoint.get("stopped_at") or ""),
                "task_id": task_id, "category": "MINITZ", "state": "WAITING",
                "text": f"{task_id} · preserved checkpoint", "operation_kind": "MINITZ",
            }
        else:
            objective = task.get("objective") if isinstance(task.get("objective"), dict) else {}
            summary = str(objective.get("desired_state") or "MiniTZ is executing the current task program objective.")

        tasks = program.get("tasks") if isinstance(program.get("tasks"), list) else []
        completed = sum(1 for item in tasks if isinstance(item, dict) and str(item.get("status") or "").upper() in {"COMPLETE", "COMPLETED", "PASS", "PASSED"})
        total = len(tasks)
        mono = time.monotonic()
        with self._cache_lock:
            asset_due = force_assets or self._stage_cache is None or mono - self._last_asset_refresh >= self._asset_refresh_seconds
            system_due = force_system or self._system_cache is None or mono - self._last_system_refresh >= self._system_refresh_seconds
            git_due = force_git or self._git_cache is None or mono - self._last_git_refresh >= self._git_refresh_seconds
            cached_stage = copy.deepcopy(self._stage_cache)
            cached_system = copy.deepcopy(self._system_cache)
            cached_git = copy.deepcopy(self._git_cache)
        stage = self._stage({}) if asset_due else cached_stage
        system = self._system_activity() if system_due else cached_system
        git = self._git_info() if git_due else cached_git
        payload: dict[str, object] = {
            "schema": "minitz.public_live_snapshot/v1",
            "mode": "READ_ONLY_OBSERVER",
            "generated_at": now.isoformat(),
            "connection": {"state": "LIVE", "stale_after_seconds": 75},
            "production": {
                "state": production_state,
                "task_id": task_id,
                "task_title": title,
                "task_summary": summary,
                "task_status": task_status,
                "current_operation": current,
                "commanders": self._commander_summary(task_id, force_offline=str(production_status.get("status") or "") == "STOPPED"),
                "boosts": self._boost_summary(task_id),
                "execution_mode": "MINITZ_TASK_PROGRAM",
                "active_coder": active_coder,
                "main_coders": coder_statuses,
                "main_coder_detail": coder_detail,
                "continuity_status": "PRESERVED" if checkpoint else "FRESH",
                "efficiency": {"state": "ACTIVE", "projection_bytes": self.program_path.stat().st_size if self.program_path.is_file() else None, "source_ref_count": 1, "capability_count": len(task.get("required_capabilities") or []) if isinstance(task.get("required_capabilities"), list) else 0},
                "heartbeat_at": now.isoformat(),
                "heartbeat_age_seconds": 0.0,
                "task_started_at": "",
                "elapsed_task_seconds": None,
                "progress": {"completed": completed, "total": total, "percent": round(completed * 100 / total, 1) if total else None},
                "latest_validation": None,
                "commit": git,
            },
            "stage": stage,
            "system": self._public_system(system),
            "public_identity": "MiniTZ",
        }
        with self._cache_lock:
            if asset_due:
                self._stage_cache = copy.deepcopy(stage)
                self._last_asset_refresh = mono
            if system_due:
                self._system_cache = copy.deepcopy(system)
                self._last_system_refresh = mono
            if git_due:
                self._git_cache = copy.deepcopy(git)
                self._last_git_refresh = mono
            self._snapshot_cache = copy.deepcopy(payload)
        return payload

    def heartbeat_event(self) -> dict[str, object]:
        snapshot = self.refresh()
        production = snapshot.get("production") if isinstance(snapshot.get("production"), dict) else {}
        return {
            "event_id": 0,
            "seq": 0,
            "time": datetime.now(timezone.utc).isoformat(),
            "task_id": str(production.get("task_id") or "UNKNOWN"),
            "category": "MINITZ",
            "state": "HEARTBEAT",
            "text": "MiniTZ observer heartbeat",
            "heartbeat_at": datetime.now(timezone.utc).isoformat(),
            "heartbeat_age_seconds": 0.0,
            "system": copy.deepcopy(snapshot.get("system") or {}),
        }
