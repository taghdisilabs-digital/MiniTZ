from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from ops.control_gateway.biella_control_state import WorkstationState


def make_repo(path: Path) -> str:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Biella Test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True)
    files = {
        "src/biella/kernel.py": "engine\n",
        "website/src/control/index.html": "control\n",
        "projects/biella-games/Source/game.cpp": "game\n",
        "projects/biella-games/docs/PRODUCTION.md": (
            "# Production\nStatus: `IN_PROGRESS`\nCurrent section: `demo01`\nCurrent task: `D01-019`\n\n"
            "## Section: demo01 | Demo | IN_PROGRESS\n\n"
            "- [x] D01-018 | medium | Health | COMPLETE | pass\n"
            "- [ ] D01-019 | medium | Weapon | PENDING | hit evidence\n"
        ),
    }
    for name, value in files.items():
        target = path / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(value)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "unified main"], check=True)
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


class FakeCommands:
    def __call__(self, argv, cwd=None, timeout=15):
        command = " ".join(argv)
        if command == "/usr/local/bin/biella-codex feed status":
            return 0, json.dumps({
                "status": "STOPPED", "current_section": "demo01", "current_task": "D01-019",
                "completed": 18, "total": 50, "active_model": None, "active_reasoning": None,
                "heartbeat_at": "2026-09-05T00:00:00+00:00", "sections": [{"id": "demo01", "status": "IN_PROGRESS", "completed": 18, "total": 50}],
            })
        if command == "/usr/local/bin/biella providers":
            return 0, "Cloudflare CONNECTED HTTP=200\n"
        if command == "/usr/local/bin/biella resource status":
            return 0, json.dumps({"providers": [{"id": "groq", "state": "CONFIGURED", "capabilities": ["llm.fast"]}]})
        if command.startswith("gh auth status"): return 0, "connected"
        if command == "rclone listremotes": return 0, "gdrive:\n"
        if command == "codex --version": return 0, "codex-cli"
        if command == "codex mcp list": return 0, "saturn enabled"
        if command.startswith("systemctl is-active biella-ollama.service"): return 0, "active"
        if command.startswith("systemctl is-active biella-control-tunnel.service"): return 0, "active"
        if command.startswith("pgrep -c -f"): return 0, "1"
        if command.startswith("nvidia-smi"): return 0, "NVIDIA L40S, 46068 MiB, 1000 MiB"
        return 1, ""


class MonorepoProjectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.repo = Path(self.tmp.name) / "biella-engine"
        self.commit = make_repo(self.repo)
        self.state = WorkstationState(
            repo=self.repo, commands=FakeCommands(),
            http_json=lambda path: {"models": [{"name": "qwen3-coder-next:biella", "size_vram": 1}]},
            meminfo=lambda: {"MemTotal": 1000, "MemAvailable": 500},
        )

    def tearDown(self): self.tmp.cleanup()

    def test_all_project_contexts_share_one_git_identity(self):
        commits = {self.state.payload("overview", lane)["commit"] for lane in ("Website", "Engine", "Games")}
        self.assertEqual(commits, {self.commit})

    def test_files_are_directory_scoped_inside_one_repo(self):
        website = {x["path"] for x in self.state.payload("files", "Website")["items"]}
        engine = {x["path"] for x in self.state.payload("files", "Engine")["items"]}
        games = {x["path"] for x in self.state.payload("files", "Games")["items"]}
        self.assertEqual(website, {"website/src/control/index.html"})
        self.assertIn("src/biella/kernel.py", engine)
        self.assertNotIn("projects/biella-games/Source/game.cpp", engine)
        self.assertIn("projects/biella-games/Source/game.cpp", games)

    def test_projection_exposes_one_live_control_and_work_graph(self):
        payload = self.state.payload("projection", "Games")
        self.assertEqual(payload["control"]["status"], "STOPPED")
        self.assertEqual(payload["control"]["current_task"], "D01-019")
        self.assertEqual(payload["control"]["completed"], 18)
        self.assertEqual(payload["work"]["current_task"], "D01-019")
        self.assertEqual(payload["work"]["tasks"][0]["id"], "D01-018")
        self.assertEqual(payload["work"]["tasks"][1]["id"], "D01-019")
        self.assertIn("resources", payload["system"])
        self.assertTrue(any(item.get("id") == "groq" for item in payload["system"]["resources"]))


if __name__ == "__main__": unittest.main()
