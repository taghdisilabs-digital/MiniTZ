from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Callable

try:
    from .biella_control_gateway import APPROVED_CAPABILITIES
except ImportError:
    from biella_control_gateway import APPROVED_CAPABILITIES

CommandRunner = Callable[[list[str], Path | None, int], tuple[int, str]]


def run_command(argv: list[str], cwd: Path | None = None, timeout: int = 15) -> tuple[int, str]:
    try:
        result = subprocess.run(
            argv, cwd=str(cwd) if cwd else None,
            text=True, capture_output=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    output = (result.stdout or result.stderr or "").strip()
    return result.returncode, output


def ollama_json(path: str) -> dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434" + path, timeout=5) as response:
            value = json.load(response)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0])
    except (OSError, ValueError):
        pass
    return values


class WorkstationState:
    def __init__(self, *, repo: Path,
                 commands: CommandRunner = run_command,
                 http_json: Callable[[str], dict] = ollama_json,
                 meminfo: Callable[[], dict[str, int]] = read_meminfo):
        self.repo = Path(repo)
        self.games_project = self.repo / "projects" / "biella-games"
        self.commands = commands
        self.http_json = http_json
        self.meminfo = meminfo

    def payload(self, route: str, lane: str) -> dict[str, object]:
        if route == "projection":
            return self.projection(lane)
        if route == "overview":
            return self.overview(lane)
        if route == "capabilities":
            return self.capabilities(lane)
        if route == "services":
            return self.services(lane)
        if route == "milestones":
            return self.milestones(lane)
        if route == "hardware":
            return self.hardware(lane)
        if route == "workers":
            return self.workers(lane)
        if route == "files":
            return self.files(lane)
        raise KeyError(route)

    def _repo_ref(self, lane: str) -> tuple[Path, str]:
        if lane not in {"Website", "Engine", "Games"}:
            raise ValueError(f"unknown project context: {lane}")
        return self.repo, "HEAD"

    def _commit_info(self, lane: str) -> dict[str, str]:
        repo, ref = self._repo_ref(lane)
        if not repo.exists():
            return {"commit": "UNAVAILABLE", "message": "source unavailable", "updated_at": ""}
        rc_commit, commit = run_command(["git", "-C", str(repo), "rev-parse", ref])
        rc_message, message = run_command(["git", "-C", str(repo), "log", "-1", "--format=%s", ref, "--"])
        rc_time, updated_at = run_command(["git", "-C", str(repo), "log", "-1", "--format=%cI", ref, "--"])
        if rc_commit != 0 or rc_message != 0 or rc_time != 0:
            return {"commit": "UNAVAILABLE", "message": "source unavailable", "updated_at": ""}
        return {"commit": commit.strip(), "message": message.strip(), "updated_at": updated_at.strip()}

    def _git_files(self, lane: str, limit: int = 80) -> list[str]:
        repo, ref = self._repo_ref(lane)
        if not repo.exists():
            return []
        rc, output = run_command(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", ref], timeout=20)
        if rc != 0:
            return []
        paths = [line for line in output.splitlines() if line]
        if lane == "Website":
            paths = [path for path in paths if path.startswith("website/")]
        elif lane == "Games":
            paths = [path for path in paths if path.startswith("projects/biella-games/")]
        elif lane == "Engine":
            paths = [
                path for path in paths
                if not path.startswith("website/")
                and not path.startswith("projects/biella-games/")
                and not path.startswith(".github/workflows/website")
                and not path.startswith(".github/workflows/control-console")
            ]
        return paths[:limit]

    def overview(self, lane: str) -> dict[str, object]:
        info = self._commit_info(lane)
        return {
            "lane": lane,
            "goal": f"Operate the current {lane} lane from its verified source and live Biella runtime.",
            "active_task": info["message"],
            "status": "CURRENT" if info["commit"] != "UNAVAILABLE" else "DEGRADED",
            "commit": info["commit"],
            "updated_at": info["updated_at"],
        }

    def _production_status(self) -> dict[str, object]:
        rc, output = self.commands(["/usr/local/bin/biella-codex", "production", "status"], None, 15)
        if rc != 0:
            return {"status": "ERROR", "current_task": None, "completed": 0, "total": 0}
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return {"status": "ERROR", "current_task": None, "completed": 0, "total": 0}
        return payload if isinstance(payload, dict) else {"status": "ERROR", "current_task": None, "completed": 0, "total": 0}

    def work(self, lane: str) -> dict[str, object]:
        if lane != "Games":
            return {"lane": lane, "current_task": None, "sections": [], "tasks": []}
        path = self.games_project / "docs" / "PRODUCTION.md"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {"lane": lane, "current_task": None, "sections": [], "tasks": []}
        current_task = None
        sections: list[dict[str, object]] = []
        tasks: list[dict[str, object]] = []
        current_section: str | None = None
        for raw in lines:
            line = raw.strip()
            if line.startswith("Current task:"):
                value = line.split(":", 1)[1].strip().strip("`")
                current_task = None if value in {"NONE", ""} else value
                continue
            if line.startswith("## Section:"):
                parts = [part.strip() for part in line[len("## Section:"):].split("|")]
                if len(parts) >= 3:
                    current_section = parts[0]
                    sections.append({"id": parts[0], "title": parts[1], "status": parts[2]})
                continue
            if line.startswith("- [") and " | " in line and current_section:
                parts = [part.strip() for part in line.split("|")]
                if len(parts) >= 5:
                    head = parts[0]
                    task_id = head.split()[-1]
                    tasks.append({
                        "id": task_id, "section": current_section, "class": parts[1],
                        "title": parts[2], "status": parts[3], "evidence": parts[4],
                    })
        return {"lane": lane, "current_task": current_task, "sections": sections, "tasks": tasks}

    def projection(self, lane: str) -> dict[str, object]:
        info = self._commit_info(lane)
        production_status = self._production_status()
        control = {
            "project": lane,
            "status": production_status.get("status", "ERROR"),
            "current_section": production_status.get("current_section"),
            "current_task": production_status.get("current_task"),
            "completed": production_status.get("completed", 0),
            "total": production_status.get("total", 0),
            "active_coder": production_status.get("active_coder"),
            "main_coders": production_status.get("main_coders", {}),
            "main_coder_detail": production_status.get("main_coder_detail", {}),
            "commanders": production_status.get("commanders", {}),
            "boosts": production_status.get("boosts", {}),
            "active_model": production_status.get("active_model"),
            "active_reasoning": production_status.get("active_reasoning"),
            "heartbeat_at": production_status.get("heartbeat_at"),
            "sections": production_status.get("sections", []),
            "commit": info["commit"],
            "updated_at": info["updated_at"],
        }
        return {
            "lane": lane,
            "control": control,
            "work": self.work(lane),
            "outputs": self.files(lane),
            "system": {
                "services": self.services(lane).get("items", []),
                "resources": self.resources(),
                "hardware": self.hardware(lane),
                "workers": self.workers(lane).get("items", []),
            },
        }


    def resources(self) -> list[dict[str, object]]:
        rc, output = self.commands(["/usr/local/bin/biella", "resource", "status"], None, 20)
        if rc != 0:
            return []
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return []
        items = payload.get("providers", []) if isinstance(payload, dict) else []
        return [item for item in items if isinstance(item, dict)]

    def capabilities(self, lane: str) -> dict[str, object]:
        descriptions = {
            "workstation.status": "Read compact Biella workstation status.",
            "workstation.doctor": "Run the bounded Biella workstation diagnostic suite.",
            "providers.check": "Read configured provider health without response bodies or secrets.",
            "git.status.current": "Read the selected lane working-tree status only.",
        }
        items = [{"id": item, "title": item.replace(".", " ").title(), "description": descriptions[item], "status": "APPROVED"}
                 for item in sorted(APPROVED_CAPABILITIES)]
        return {"lane": lane, "items": items}

    def _provider_items(self) -> list[dict[str, str]]:
        rc, output = self.commands(["/usr/local/bin/biella", "providers"], None, 30)
        if rc != 0:
            return []
        items: list[dict[str, str]] = []
        for line in output.splitlines():
            parts = line.split(None, 2)
            if len(parts) < 2:
                continue
            name, status = parts[0], parts[1]
            detail = parts[2] if len(parts) > 2 else ""
            items.append({"name": name, "status": status, "detail": detail})
        return items

    def services(self, lane: str) -> dict[str, object]:
        items = {item["name"]: item for item in self._provider_items()}
        rc, detail = self.commands(["gh", "auth", "status"], None, 10)
        items["GitHub"] = {"name": "GitHub", "status": "CONNECTED" if rc == 0 else "DEGRADED", "detail": "authenticated CLI" if rc == 0 else "authentication unavailable"}
        rc, remotes = self.commands(["rclone", "listremotes"], None, 10)
        drive_ok = rc == 0 and any(x in remotes.splitlines() for x in ("drive:", "gdrive:"))
        items["Drive"] = {"name": "Drive", "status": "CONNECTED" if drive_ok else "DEGRADED", "detail": "configured rclone remote" if drive_ok else "remote unavailable"}
        tags = self.http_json("/api/tags")
        ollama_ok = isinstance(tags.get("models"), list)
        items["Ollama"] = {"name": "Ollama", "status": "CONNECTED" if ollama_ok else "DEGRADED", "detail": "localhost:11434"}
        rc, version = self.commands(["codex", "--version"], None, 10)
        items["Codex"] = {"name": "Codex", "status": "CONNECTED" if rc == 0 else "DEGRADED", "detail": version if rc == 0 else "CLI unavailable"}
        rc, mcp = self.commands(["codex", "mcp", "list"], None, 15)
        saturn_ok = rc == 0 and "saturn" in mcp.lower() and "enabled" in mcp.lower()
        items["Saturn"] = {"name": "Saturn", "status": "CONNECTED" if saturn_ok else "DEGRADED", "detail": "Codex MCP enabled" if saturn_ok else "MCP unavailable"}
        return {"lane": lane, "items": list(items.values())}

    def hardware(self, lane: str) -> dict[str, object]:
        rc, gpu = self.commands([
            "nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader"
        ], None, 10)
        ps = self.http_json("/api/ps")
        qwen = next((item for item in ps.get("models", []) if item.get("name") == "qwen3-coder-next:biella" or item.get("model") == "qwen3-coder-next:biella"), {})
        vram = qwen.get("size_vram")
        mem = self.meminfo()
        total = int(mem.get("MemTotal", 0))
        available = int(mem.get("MemAvailable", 0))
        used = max(0, total - available)
        usage = [
            {"name": "Host RAM", "value": f"{used // 1024} MiB", "detail": f"{total // 1024} MiB total"},
            {"name": "Qwen VRAM", "value": f"{vram or 0} bytes", "detail": "qwen3-coder-next:biella"},
            {"name": "Context mode", "value": os.environ.get("BIELLA_CONTEXT_MODE", "progressive"), "detail": "context loading policy"},
            {"name": "Context file budget", "value": os.environ.get("BIELLA_CONTEXT_MAX_FILES", "8"), "detail": "soft files per expansion"},
            {"name": "Context byte budget", "value": os.environ.get("BIELLA_CONTEXT_MAX_BYTES", "65536"), "detail": "soft bytes per expansion"},
            {"name": "Context log tail", "value": os.environ.get("BIELLA_CONTEXT_LOG_TAIL_LINES", "120"), "detail": "maximum routine log tail lines"},
            {"name": "Context search results", "value": os.environ.get("BIELLA_CONTEXT_SEARCH_RESULTS", "20"), "detail": "maximum routine targeted results"},
        ]
        return {
            "lane": lane,
            "gpu": gpu if rc == 0 else "unavailable",
            "vram_used": f"{vram} bytes" if isinstance(vram, int) else "Not reported",
            "ram_used": f"{used // 1024} MiB" if total else "Not reported",
            "api_calls": "Not tracked",
            "usage": usage,
        }

    def workers(self, lane: str) -> dict[str, object]:
        rc, state = self.commands(["systemctl", "is-active", "biella-ollama.service"], None, 10)
        ollama_status = "READY" if rc == 0 and state.strip() == "active" else "DEGRADED"
        ps = self.http_json("/api/ps")
        qwen_ok = any(item.get("name") == "qwen3-coder-next:biella" or item.get("model") == "qwen3-coder-next:biella" for item in ps.get("models", []))
        rc, count = self.commands(["pgrep", "-c", "-f", "codex"], None, 10)
        rc_mcp, mcp = self.commands(["codex", "mcp", "list"], None, 15)
        saturn_ok = rc_mcp == 0 and "saturn" in mcp.lower() and "enabled" in mcp.lower()
        rc_tunnel, tunnel = self.commands(["systemctl", "is-active", "biella-control-tunnel.service"], None, 10)
        items = [
            {"name": "Ollama", "status": ollama_status, "detail": "biella-ollama.service"},
            {"name": "Qwen", "status": "READY" if qwen_ok else "DEGRADED", "detail": "qwen3-coder-next:biella"},
            {"name": "Codex", "status": "RUNNING" if rc == 0 and count.strip() not in {"", "0"} else "AVAILABLE", "detail": f"{count.strip() or '0'} processes"},
            {"name": "Saturn MCP", "status": "CONNECTED" if saturn_ok else "DEGRADED", "detail": "official stdio MCP"},
            {"name": "Cloudflare tunnel", "status": "CONNECTED" if rc_tunnel == 0 and tunnel.strip() == "active" else "OFFLINE", "detail": "control.biellagames.dev ingress"},
        ]
        return {"lane": lane, "items": items}

    def _ref_has_path(self, lane: str, path: str) -> bool:
        repo, ref = self._repo_ref(lane)
        if not repo.exists():
            return False
        rc, _ = run_command(["git", "-C", str(repo), "cat-file", "-e", f"{ref}:{path}"])
        return rc == 0

    def milestones(self, lane: str) -> dict[str, object]:
        info = self._commit_info(lane)
        items = [{
            "title": "Current source",
            "status": "CURRENT" if info["commit"] != "UNAVAILABLE" else "DEGRADED",
            "detail": f"{info['commit'][:12]} {info['message']}" if info["commit"] != "UNAVAILABLE" else "source unavailable",
        }]
        if lane == "Website":
            ready = self._ref_has_path(lane, "website/src/control/index.html")
            items.append({"title": "Private control console source", "status": "COMPLETE" if ready else "BLOCKED", "detail": "/control/ source in current Website branch"})
        elif lane == "Engine":
            ready = self._ref_has_path(lane, "ops/workstation/biella")
            items.append({"title": "Unified workstation supervisor", "status": "COMPLETE" if ready else "BLOCKED", "detail": "current Engine main"})
        else:
            items.append({"title": "Games current main", "status": "CURRENT" if info["commit"] != "UNAVAILABLE" else "BLOCKED", "detail": info["message"]})
        return {"lane": lane, "items": items}

    def files(self, lane: str) -> dict[str, object]:
        info = self._commit_info(lane)
        items = [
            {"path": path, "lane": lane, "commit": info["commit"], "updated_at": info["updated_at"]}
            for path in self._git_files(lane)
        ]
        return {"lane": lane, "items": items}
