from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

PREVIEWABLE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm", ".mov"}
PUBLIC_ROOT_LANES = {
    "games-presentation": "Games",
    "games-generated": "Games",
    "games-visual-output": "Games",
    "website-generated": "Website",
}
STALE_AFTER_SECONDS = 75


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _iso_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class LiveProjection:
    def __init__(self, *, repo: Path, runtime_root: Path, assets):
        self.repo = Path(repo)
        self.runtime_root = Path(runtime_root)
        self.assets = assets
        self.games_project = self.repo / "projects" / "biella-games"
        self.journal_path = self.runtime_root / "events.jsonl"
        self.runtime_path = self.runtime_root / "runtime.json"
        self.memory_root = self.runtime_root / "task-memory"
        self._cache_lock = threading.RLock()
        self._snapshot_cache: dict[str, object] | None = None
        self._stage_cache: dict[str, object] | None = None
        self._system_cache: dict[str, object] | None = None
        self._git_cache: dict[str, str] | None = None
        self._last_asset_refresh = 0.0
        self._last_system_refresh = 0.0
        self._last_git_refresh = 0.0
        self._asset_dirty = True
        self._refresh_seconds = 1.0
        self._asset_refresh_seconds = 30.0
        self._system_refresh_seconds = 2.0
        self._git_refresh_seconds = 5.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def _run(argv: list[str], timeout: int = 8) -> tuple[int, str]:
        try:
            result = subprocess.run(argv, text=True, capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return 1, ""
        return result.returncode, (result.stdout or result.stderr or "").strip()

    def _production_status(self) -> dict[str, object]:
        # Public live observation must never invoke or message the production controller.
        # Read only the controller's already-written runtime file plus canonical Project state.
        runtime = _read_json(self.runtime_path)
        production_path = self.games_project / "docs" / "PRODUCTION.md"
        current_section = None
        current_task = None
        completed = 0
        total = 0
        try:
            lines = production_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for raw in lines:
            line = raw.strip()
            if line.startswith("Current section:"):
                current_section = line.split(":", 1)[1].strip().strip("`") or None
            elif line.startswith("Current task:"):
                value = line.split(":", 1)[1].strip().strip("`")
                current_task = value if value and value != "NONE" else None
            elif line.startswith("- [") and " | " in line:
                total += 1
                if line.startswith("- [x]"):
                    completed += 1
        if not runtime and not lines:
            return {"status": "ERROR", "current_task": None, "completed": 0, "total": 0}
        result = dict(runtime)
        result["current_section"] = current_section
        result["current_task"] = str(runtime.get("task_id") or current_task or "UNKNOWN")
        result["completed"] = completed
        result["total"] = total
        return result

    def _git_info(self) -> dict[str, str]:
        rc_commit, commit = self._run(["git", "-C", str(self.repo), "rev-parse", "HEAD"])
        rc_tree, tree = self._run(["git", "-C", str(self.repo), "rev-parse", "HEAD^{tree}"])
        rc_message, message = self._run(["git", "-C", str(self.repo), "log", "-1", "--format=%s", "HEAD", "--"])
        rc_time, committed_at = self._run(["git", "-C", str(self.repo), "log", "-1", "--format=%cI", "HEAD", "--"])
        if any(rc != 0 for rc in (rc_commit, rc_tree, rc_message, rc_time)):
            return {"commit": "UNAVAILABLE", "tree": "UNAVAILABLE", "message": "source unavailable", "committed_at": ""}
        return {"commit": commit, "tree": tree, "message": message, "committed_at": committed_at}

    def _task_memory(self, task_id: str) -> dict[str, object]:
        if not task_id or task_id == "UNKNOWN":
            return {}
        return _read_json(self.memory_root / f"{task_id}.json")

    def _child_process_state(self, runtime: dict[str, object]) -> str:
        try:
            pid = int(runtime.get("child_pid") or 0)
        except (TypeError, ValueError):
            return "UNKNOWN"
        if pid <= 0:
            return "UNKNOWN"
        try:
            fields = (Path("/proc") / str(pid) / "stat").read_text().split()
        except OSError:
            return "MISSING"
        return fields[2] if len(fields) > 2 else "UNKNOWN"

    def _tail_events(self, max_bytes: int = 768 * 1024, limit: int = 600) -> list[dict[str, object]]:
        try:
            size = self.journal_path.stat().st_size
            with self.journal_path.open("rb") as handle:
                start = max(0, size - max_bytes)
                handle.seek(start)
                if start:
                    handle.readline()
                lines = handle.read().decode("utf-8", errors="replace").splitlines()
        except OSError:
            return []
        result: list[dict[str, object]] = []
        for line in lines[-limit:]:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    @staticmethod
    def _category(event: dict[str, object]) -> str:
        event_type = str(event.get("type") or "")
        tool = str(event.get("tool") or "")
        raw = f"{tool} {event.get('text') or ''}".lower()
        if event_type.startswith("validation."):
            return "TEST"
        if event_type == "agent.message" or event_type.startswith("task.") or event_type in {"turn.completed", "dialog.queued", "dialog.started"}:
            return "BIELLA"
        if "git commit" in raw or event_type.startswith("commit."):
            return "COMMIT"
        if any(token in raw for token in ("verify_", "pytest", "unittest", "tests/run_", " tests/", "validation.json")):
            return "TEST"
        if any(token in raw for token in ("build.sh", "cmake --build", "ninja ", "compile", "build completed")):
            return "BUILD"
        if any(token in raw for token in ("capture", "render", "unrealeditor", "ffmpeg")):
            return "RENDER"
        if tool == "file_change" or event_type == "artifact.created":
            return "ARTIFACT"
        return "TOOL"

    @staticmethod
    def _state_word(event: dict[str, object]) -> str:
        status = str(event.get("status") or "").upper()
        event_type = str(event.get("type") or "")
        if event.get("exit_code") not in (None, 0) or status in {"FAILED", "ERROR"}:
            return "FAILED"
        if status in {"COMPLETED", "COMPLETE", "PASS", "PASSED"} or event_type in {"turn.completed"}:
            return "COMPLETED"
        if status in {"STARTED", "IN_PROGRESS", "RUNNING", "ACTIVE"} or event_type.endswith(".started"):
            return "RUNNING"
        return status or "INFO"

    @classmethod
    def sanitize_event(cls, event: dict[str, object]) -> dict[str, object] | None:
        category = cls._category(event)
        state = cls._state_word(event)
        event_type = str(event.get("type") or "")
        task_id = str(event.get("task_id") or "")
        when = str(event.get("time") or "")
        if event_type == "agent.message":
            text = str(event.get("text") or "Biella updated production state").strip()
            try:
                structured = json.loads(text)
            except json.JSONDecodeError:
                structured = None
            if isinstance(structured, dict) and isinstance(structured.get("summary"), str):
                text = structured["summary"].strip()
            text = text.replace("/root/biella/repos/biella-engine/", "")
            text = text.replace("/mnt/biella-extra/biella-runtime/", "runtime/")
            text = re.sub(r"\s+", " ", text)[:520]
        else:
            raw = str(event.get("text") or "")
            detail = ""
            match = re.search(r"(?:tests/|Build/Presentation/)([A-Za-z0-9_.\-/]+)", raw)
            if match:
                detail = Path(match.group(1)).name
            verbs = {"RUNNING": "running", "COMPLETED": "completed", "FAILED": "failed", "INFO": "updated"}
            verb = verbs.get(state, state.lower())
            labels = {
                "BIELLA": "Production update",
                "TOOL": str(event.get("tool") or "Tool").replace("_", " ").title(),
                "BUILD": "Build",
                "TEST": "Validation",
                "RENDER": "Runtime / render",
                "COMMIT": "Commit",
                "ARTIFACT": "Artifact",
            }
            text = f"{labels[category]} {verb}"
            if detail:
                text += f" · {detail}"
        return {
            "event_id": int(event.get("event_id") or event.get("seq") or 0),
            "seq": int(event.get("seq") or 0),
            "time": when,
            "task_id": task_id,
            "category": category,
            "state": state,
            "text": text,
        }

    def _task_started_at(self, task_id: str, events: list[dict[str, object]]) -> str:
        matches = [str(item.get("time") or "") for item in events if str(item.get("task_id") or "") == task_id and item.get("time")]
        if matches:
            return matches[0]
        try:
            with self.journal_path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(item, dict) and str(item.get("task_id") or "") == task_id and item.get("time"):
                        return str(item["time"])
        except OSError:
            pass
        return ""

    def _local_ai_status(self) -> dict[str, object]:
        result: dict[str, object] = {
            "state": "OFFLINE",
            "model": None,
            "context_length": None,
            "vram_mib": None,
        }
        try:
            with urlopen("http://127.0.0.1:11434/api/ps", timeout=0.75) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return result
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            return result
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("model") or "")
            if name != "qwen3-coder-next:biella":
                continue
            result.update({
                "state": "RESIDENT" if int(item.get("size_vram") or 0) > 0 else "LOADED",
                "model": name,
                "context_length": int(item.get("context_length") or 0) or None,
                "vram_mib": round(int(item.get("size_vram") or 0) / (1024 * 1024), 1),
            })
            break
        return result

    def _efficiency_status(self, task_id: str) -> dict[str, object]:
        path = self.runtime_root / "memory" / "current-task.json"
        projection = _read_json(path)
        active = (
            projection.get("schema") == "biella.compacted_task_projection/v1"
            and str(projection.get("task_id") or "") == task_id
        )
        try:
            size = path.stat().st_size if active else None
        except OSError:
            size = None
        capabilities = projection.get("capabilities") if isinstance(projection.get("capabilities"), dict) else {}
        source_refs = projection.get("source_refs") if isinstance(projection.get("source_refs"), list) else []
        return {
            "state": "ACTIVE" if active else "UNAVAILABLE",
            "projection_bytes": size,
            "generated_at": str(projection.get("generated_at") or "") if active else "",
            "source_ref_count": len(source_refs) if active else 0,
            "capability_count": len(capabilities) if active else 0,
        }

    def _system_activity(self) -> dict[str, object]:
        gpu = {"name": "Unavailable", "utilization_percent": None, "memory_used_mib": None, "memory_total_mib": None, "temperature_c": None, "power_w": None}
        rc, output = self._run([
            "nvidia-smi",
            "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ], 5)
        if rc == 0 and output:
            parts = [part.strip() for part in output.splitlines()[0].split(",")]
            if len(parts) >= 6:
                try:
                    gpu = {
                        "name": parts[0],
                        "utilization_percent": float(parts[1]),
                        "memory_used_mib": float(parts[2]),
                        "memory_total_mib": float(parts[3]),
                        "temperature_c": float(parts[4]),
                        "power_w": float(parts[5]),
                    }
                except ValueError:
                    pass
        total_kib = available_kib = 0
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    total_kib = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    available_kib = int(line.split()[1])
        except (OSError, ValueError):
            pass
        try:
            load_1m = float(Path("/proc/loadavg").read_text().split()[0])
        except (OSError, ValueError, IndexError):
            load_1m = None
        return {
            "gpu": gpu,
            "local_ai": self._local_ai_status(),
            "host": {
                "load_1m": load_1m,
                "cpu_count": os.cpu_count() or 0,
                "ram_used_mib": round(max(0, total_kib - available_kib) / 1024, 1) if total_kib else None,
                "ram_total_mib": round(total_kib / 1024, 1) if total_kib else None,
            },
        }

    @staticmethod
    def _collect_preview_strings(value: object, out: list[str]) -> None:
        if isinstance(value, str):
            if Path(value).suffix.lower() in PREVIEWABLE_SUFFIXES:
                out.append(value)
            return
        if isinstance(value, list):
            for item in value:
                LiveProjection._collect_preview_strings(item, out)
            return
        if isinstance(value, dict):
            for item in value.values():
                LiveProjection._collect_preview_strings(item, out)

    def _asset_item_for_path(self, candidate: Path) -> dict[str, object] | None:
        try:
            candidate = candidate.resolve()
        except OSError:
            return None
        if not candidate.is_file() or candidate.suffix.lower() not in PREVIEWABLE_SUFFIXES:
            return None
        for lane, roots in self.assets.roots.items():
            for root in roots:
                if root.root_id not in PUBLIC_ROOT_LANES or PUBLIC_ROOT_LANES[root.root_id] != lane:
                    continue
                try:
                    candidate.relative_to(root.path)
                except ValueError:
                    continue
                try:
                    return self.assets._item(lane, root, candidate, include_digest=False)
                except OSError:
                    return None
        return None

    def _preferred_assets(self, memory: dict[str, object]) -> list[dict[str, object]]:
        strings: list[str] = []
        self._collect_preview_strings(memory, strings)
        referenced_json: list[Path] = []
        for raw in self._flatten_strings(memory):
            if not raw.lower().endswith(".json"):
                continue
            path = Path(raw)
            if not path.is_absolute():
                path = self.games_project / path
            if path.is_file():
                referenced_json.append(path)
        for path in referenced_json[:30]:
            self._collect_preview_strings(_read_json(path), strings)
        result: list[dict[str, object]] = []
        seen: set[str] = set()
        for raw in reversed(strings):
            path = Path(raw)
            if not path.is_absolute():
                path = self.games_project / path
            item = self._asset_item_for_path(path)
            if not item:
                continue
            key = f"{item['root_id']}:{item['path']}"
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        result.sort(key=lambda item: (str(item.get("modified_at") or ""), str(item.get("path") or "")), reverse=True)
        return result

    @staticmethod
    def _flatten_strings(value: object) -> list[str]:
        result: list[str] = []
        if isinstance(value, str):
            result.append(value)
        elif isinstance(value, list):
            for item in value:
                result.extend(LiveProjection._flatten_strings(item))
        elif isinstance(value, dict):
            for item in value.values():
                result.extend(LiveProjection._flatten_strings(item))
        return result

    def _recent_public_assets(self, limit: int = 24) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for lane, roots in self.assets.roots.items():
            for root in roots:
                if root.root_id not in PUBLIC_ROOT_LANES or PUBLIC_ROOT_LANES[root.root_id] != lane or not root.path.is_dir():
                    continue
                scanned = 0
                for path in root.path.rglob("*"):
                    if scanned >= 12000:
                        break
                    if not path.is_file():
                        continue
                    scanned += 1
                    if path.suffix.lower() not in PREVIEWABLE_SUFFIXES:
                        continue
                    try:
                        items.append(self.assets._item(lane, root, path, include_digest=False))
                    except OSError:
                        continue
        items.sort(key=lambda item: (str(item.get("modified_at") or ""), str(item.get("name") or "")), reverse=True)
        return items[:limit]

    @staticmethod
    def _public_asset(item: dict[str, object]) -> dict[str, object]:
        root_id = str(item["root_id"])
        path = str(item["path"])
        return {
            "name": str(item.get("name") or Path(path).name),
            "kind": str(item.get("kind") or "image"),
            "source_class": str(item.get("source_class") or "CURRENT"),
            "modified_at": str(item.get("modified_at") or ""),
            "url": f"/live-api/asset?root_id={quote(root_id, safe='')}&path={quote(path, safe='/')}",
        }

    def _stage(self, memory: dict[str, object]) -> dict[str, object]:
        preferred = self._preferred_assets(memory)
        recent = self._recent_public_assets(30)
        merged: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in preferred + recent:
            key = f"{item['root_id']}:{item['path']}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        public = [self._public_asset(item) for item in merged[:12]]
        return {
            "primary": public[0] if public else None,
            "showcase": public[1:10] if len(public) > 1 else [],
            "mode": "CURRENT_TASK_EVIDENCE_THEN_RECENT_VPS_OUTPUTS",
        }

    def resolve_public_asset(self, root_id: str, relative_path: str) -> tuple[str, Path]:
        lane = PUBLIC_ROOT_LANES.get(root_id)
        if not lane:
            raise ValueError("public asset root unavailable")
        candidate = self.assets.resolve_asset(lane, root_id, relative_path)
        if candidate.suffix.lower() not in PREVIEWABLE_SUFFIXES:
            raise ValueError("public asset is not previewable")
        return lane, candidate

    def _latest_validation(self, task_id: str, events: list[dict[str, object]]) -> dict[str, object] | None:
        for event in reversed(events):
            if str(event.get("task_id") or "") != task_id or event.get("type") != "validation.completed":
                continue
            try:
                path = Path(str(event["evidence_path"]))
                if not path.is_absolute():
                    path = self.repo / path
                path.resolve().relative_to(self.repo.resolve())
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != event.get("evidence_sha256"):
                    continue
                report = json.loads(data)
                if report.get("task_id") != task_id or report.get("result") not in {"PASS", "FAIL", "FAILED"}:
                    continue
                verified_event = dict(event)
                verified_event["status"] = "PASS" if report["result"] == "PASS" else "FAILED"
                verified_event["text"] = "Task validation evidence"
                return self.sanitize_event(verified_event)
            except (KeyError, OSError, ValueError, TypeError):
                continue
        return None

    @staticmethod
    def _task_status(task_id: str, runtime: dict, status: dict, memory: dict) -> str:
        if str(runtime.get("task_id") or "") == task_id:
            observed = str(runtime.get("status") or "UNKNOWN")
            if observed in {"RUNNING", "ACTIVE"}:
                return "RUNNING"
            return observed
        result = status.get("last_result") or {}
        if result.get("task_id") == task_id:
            return str(result.get("status") or "UNKNOWN")
        if memory.get("task_id") == task_id and memory.get("last_status"):
            return str(memory["last_status"])
        return str(status.get("status") or "UNKNOWN")

    def _production_state(self, *, status: dict[str, object], runtime: dict[str, object], current: dict[str, object] | None, heartbeat_age: float | None) -> str:
        if str(status.get("status") or "").upper() == "ERROR":
            return "ERROR"
        if heartbeat_age is None or heartbeat_age > STALE_AFTER_SECONDS:
            return "STALE"
        child_state = self._child_process_state(runtime)
        if child_state == "T" or str(runtime.get("status") or "").upper() in {"PAUSED", "WAITING"}:
            return "WAITING"
        if current and current.get("state") == "RUNNING":
            if current.get("category") == "COMMIT":
                return "COMMITTING"
            if current.get("category") in {"TEST", "BUILD"}:
                return "VALIDATING"
        if str(status.get("status") or runtime.get("status") or "").upper() in {"ACTIVE", "RUNNING"}:
            return "WORKING"
        return "WAITING"

    def observe_event(self, event: dict[str, object]) -> None:
        category = self._category(event)
        raw = str(event.get("text") or "").lower()
        if category in {"ARTIFACT", "RENDER"} or any(suffix in raw for suffix in PREVIEWABLE_SUFFIXES):
            with self._cache_lock:
                self._asset_dirty = True

    def start(
        self, *, refresh_seconds: float = 1.0, asset_refresh_seconds: float = 30.0,
        system_refresh_seconds: float = 2.0, git_refresh_seconds: float = 5.0,
    ) -> None:
        self._refresh_seconds = max(0.2, float(refresh_seconds))
        self._asset_refresh_seconds = max(2.0, float(asset_refresh_seconds))
        self._system_refresh_seconds = max(1.0, float(system_refresh_seconds))
        self._git_refresh_seconds = max(1.0, float(git_refresh_seconds))
        self.refresh(force_assets=True, force_system=True, force_git=True)
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._refresh_loop, name="biella-live-projection", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=max(2.0, self._refresh_seconds * 3))

    def _refresh_loop(self) -> None:
        while not self._stop.wait(self._refresh_seconds):
            try:
                self.refresh()
            except Exception:
                # The observer never owns production. Keep serving the last valid projection.
                continue

    def refresh(
        self, *, force_assets: bool = False, force_system: bool = False, force_git: bool = False,
    ) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        mono = time.monotonic()
        status = self._production_status()
        runtime = _read_json(self.runtime_path)
        task_id = str(status.get("current_task") or status.get("task_id") or runtime.get("task_id") or "UNKNOWN")
        memory = self._task_memory(task_id)
        heartbeat_at = str(status.get("heartbeat_at") or runtime.get("heartbeat_at") or "")
        heartbeat_time = _iso_time(heartbeat_at)
        heartbeat_age = max(0.0, (now - heartbeat_time).total_seconds()) if heartbeat_time else None
        events = self._tail_events()
        task_events = [item for item in events if str(item.get("task_id") or "") == task_id]
        current = self.sanitize_event(task_events[-1]) if task_events else None
        started_at = self._task_started_at(task_id, events)
        started = _iso_time(started_at)
        elapsed = max(0, int((now - started).total_seconds())) if started else None
        with self._cache_lock:
            asset_dirty_due = self._asset_dirty and mono - self._last_asset_refresh >= min(5.0, self._asset_refresh_seconds)
            asset_due = force_assets or self._stage_cache is None or asset_dirty_due or mono - self._last_asset_refresh >= self._asset_refresh_seconds
            system_due = force_system or self._system_cache is None or mono - self._last_system_refresh >= self._system_refresh_seconds
            git_due = force_git or self._git_cache is None or mono - self._last_git_refresh >= self._git_refresh_seconds
        if asset_due:
            stage = self._stage(memory)
        else:
            with self._cache_lock:
                stage = copy.deepcopy(self._stage_cache)
        if system_due:
            system = self._system_activity()
        else:
            with self._cache_lock:
                system = copy.deepcopy(self._system_cache)
        if git_due:
            git = self._git_info()
        else:
            with self._cache_lock:
                git = copy.deepcopy(self._git_cache)
        completed = int(status.get("completed") or 0)
        total = int(status.get("total") or 0)
        title = str(memory.get("title") or task_id)
        summary = str(memory.get("summary") or "").strip()
        if not summary or summary.lower().startswith(("invalid structured result", "missing structured result")):
            summary = str((current or {}).get("text") or (status.get("last_result") or {}).get("summary") or "").strip()
        production_state = self._production_state(status=status, runtime=runtime, current=current, heartbeat_age=heartbeat_age)
        payload: dict[str, object] = {
            "schema": "biella.public_live_snapshot/v1",
            "mode": "READ_ONLY_OBSERVER",
            "generated_at": now.isoformat(),
            "connection": {
                "state": "LIVE" if heartbeat_age is not None and heartbeat_age <= STALE_AFTER_SECONDS else "STALE",
                "stale_after_seconds": STALE_AFTER_SECONDS,
            },
            "production": {
                "state": production_state,
                "task_id": task_id,
                "task_title": title,
                "task_summary": summary,
                "task_status": self._task_status(task_id, runtime, status, memory),
                "current_operation": current,
                "model": str(status.get("active_model") or runtime.get("active_model") or "UNKNOWN"),
                "reasoning": str(status.get("active_reasoning") or runtime.get("active_reasoning") or "UNKNOWN"),
                "attempt": int(runtime.get("attempt") or 0) or None,
                "continuity": {
                    "session_state": "PERSISTENT" if runtime.get("task_session_id") and str(runtime.get("session_task_id") or task_id) == task_id else "FRESH",
                },
                "efficiency": self._efficiency_status(task_id),
                "heartbeat_at": heartbeat_at,
                "heartbeat_age_seconds": round(heartbeat_age, 1) if heartbeat_age is not None else None,
                "task_started_at": started_at,
                "elapsed_task_seconds": elapsed,
                "progress": {"completed": completed, "total": total, "percent": round(completed * 100 / total, 1) if total else None},
                "latest_validation": self._latest_validation(task_id, events),
                "commit": git,
            },
            "stage": stage,
            "system": system,
        }
        with self._cache_lock:
            if asset_due:
                self._stage_cache = copy.deepcopy(stage); self._last_asset_refresh = mono; self._asset_dirty = False
            if system_due:
                self._system_cache = copy.deepcopy(system); self._last_system_refresh = mono
            if git_due:
                self._git_cache = copy.deepcopy(git); self._last_git_refresh = mono
            self._snapshot_cache = copy.deepcopy(payload)
        return payload

    def snapshot(self) -> dict[str, object]:
        with self._cache_lock:
            if self._snapshot_cache is not None:
                return copy.deepcopy(self._snapshot_cache)
        return self.refresh(force_assets=True, force_system=True, force_git=True)

    def heartbeat_event(self) -> dict[str, object]:
        snapshot = self.snapshot()
        production = snapshot.get("production") if isinstance(snapshot.get("production"), dict) else {}
        heartbeat_at = str(production.get("heartbeat_at") or "")
        heartbeat_time = _iso_time(heartbeat_at)
        age = max(0.0, (datetime.now(timezone.utc) - heartbeat_time).total_seconds()) if heartbeat_time else None
        return {
            "event_id": 0,
            "seq": 0,
            "time": datetime.now(timezone.utc).isoformat(),
            "task_id": str(production.get("task_id") or "UNKNOWN"),
            "category": "BIELLA",
            "state": "HEARTBEAT",
            "text": "Live production heartbeat",
            "heartbeat_at": heartbeat_at,
            "heartbeat_age_seconds": round(age, 1) if age is not None else None,
            "system": copy.deepcopy(snapshot.get("system") or {}),
        }
