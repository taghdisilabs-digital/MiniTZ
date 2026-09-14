from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from ops.control_gateway.minitz_control_state import WorkstationState


def make_repo(path: Path) -> str:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "MiniTZ Test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True)
    files = {
        "src/minitz_os/engine/kernel.py": "engine\n",
        "ops/workstation/minitz": "supervisor\n",
        "website/src/index.html": "public\n",
        "website/src/control/index.html": "control\n",
        "projects/minitz-games/Source/game.cpp": "game\n",
        "projects/minitz-games/docs/PRODUCTION.md": "# prod\nCurrent task: `D01-019`\n",
    }
    for name, value in files.items():
        target = path / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(value)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "unified main"], check=True)
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


class FakeCommands:
    def __call__(self, argv, cwd=None, timeout=15):
        command = " ".join(argv)
        if command == "/usr/local/bin/minitz-workstation providers": return 0, "Cloudflare CONNECTED HTTP=200\nGroq CONNECTED HTTP=200\n"
        if command.startswith("gh auth status"): return 0, "connected"
        if command == "rclone listremotes": return 0, "gdrive:\n"
        if command == "codex --version": return 0, "codex-cli 0.test"
        if command == "codex mcp list": return 0, "saturn enabled"
        if command.startswith("systemctl is-active minitz-ollama.service"): return 0, "active"
        if command.startswith("systemctl is-active minitz-control-tunnel.service"): return 3, "inactive"
        if command.startswith("pgrep -c -f"): return 0, "2"
        if command.startswith("nvidia-smi"): return 0, "NVIDIA L40S, 46068 MiB, 27000 MiB"
        return 1, ""


class WorkstationStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.repo = Path(self.tmp.name) / "minitz"
        self.commit = make_repo(self.repo)
        self.state = WorkstationState(
            repo=self.repo,
            commands=FakeCommands(),
            http_json=lambda path: {
                "/api/tags": {"models": [{"name": "qwen3-coder-next:minitz"}]},
                "/api/ps": {"models": [{"name": "qwen3-coder-next:minitz", "size_vram": 27702297886}]},
            }[path],
            meminfo=lambda: {"MemTotal": 90_000_000, "MemAvailable": 70_000_000},
        )

    def tearDown(self): self.tmp.cleanup()

    def test_all_project_contexts_use_same_head(self):
        commits = {lane: self.state.payload("overview", lane)["commit"] for lane in ("Website", "Engine", "Games")}
        self.assertEqual(set(commits.values()), {self.commit})

    def test_files_are_filtered_by_subtree_not_repository(self):
        website = {x["path"] for x in self.state.payload("files", "Website")["items"]}
        engine = {x["path"] for x in self.state.payload("files", "Engine")["items"]}
        games = {x["path"] for x in self.state.payload("files", "Games")["items"]}
        self.assertIn("website/src/control/index.html", website)
        self.assertIn("projects/minitz-games/Source/game.cpp", games)
        self.assertIn("src/minitz_os/engine/kernel.py", engine)
        self.assertFalse(any(p.startswith("website/") or p.startswith("projects/minitz-games/") for p in engine))
        self.assertTrue(all(p.startswith("projects/minitz-games/") for p in games))

    def test_milestones_resolve_monorepo_paths(self):
        self.assertEqual(self.state.payload("milestones", "Website")["items"][-1]["status"], "COMPLETE")
        self.assertEqual(self.state.payload("milestones", "Games")["items"][-1]["status"], "CURRENT")

    def test_services_hardware_and_workers_still_report_runtime(self):
        services = {x["name"] for x in self.state.payload("services", "Engine")["items"]}
        self.assertTrue({"GitHub", "Cloudflare", "Ollama", "Codex", "Saturn"}.issubset(services))
        self.assertIn("NVIDIA L40S", self.state.payload("hardware", "Engine")["gpu"])
        workers = {x["name"] for x in self.state.payload("workers", "Engine")["items"]}
        self.assertTrue({"Ollama", "Qwen", "Codex", "Saturn MCP", "Cloudflare tunnel"}.issubset(workers))

    def test_capabilities_remain_allowlisted(self):
        ids = {x["id"] for x in self.state.payload("capabilities", "Engine")["items"]}
        self.assertIn("git.status.current", ids); self.assertNotIn("shell.exec", ids)


if __name__ == "__main__": unittest.main()
