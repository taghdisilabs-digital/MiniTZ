from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from ops.control_gateway.biella_control_state import WorkstationState


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def make_repo(path: Path, files: dict[str, str]) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Biella Test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True)
    for name, value in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "current main"], check=True)


class FakeCommands:
    def __call__(self, argv, cwd=None, timeout=15):
        command = " ".join(argv)
        if command == "/usr/local/bin/biella providers":
            return 0, "Cloudflare CONNECTED HTTP=200\nGroq CONNECTED HTTP=200\nSaturn CONNECTED\nModal CONNECTED\n"
        if command.startswith("gh auth status"):
            return 0, "connected"
        if command == "rclone listremotes":
            return 0, "drive:\ngdrive:\n"
        if command == "codex --version":
            return 0, "codex-cli 0.test"
        if command == "codex mcp list":
            return 0, "saturn /wrapper enabled"
        if command.startswith("systemctl is-active biella-ollama.service"):
            return 0, "active"
        if command.startswith("systemctl is-active biella-control-tunnel.service"):
            return 3, "inactive"
        if command.startswith("pgrep -c -f"):
            return 0, "2"
        if command.startswith("nvidia-smi"):
            return 0, "NVIDIA L40S, 46068 MiB, 27000 MiB"
        return 1, ""


class WorkstationStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.engine = root / "engine"
        self.games = root / "games"
        make_repo(self.engine, {
            "src/engine.py": "engine\n",
            "ops/workstation/biella": "supervisor\n",
            "website/src/index.html": "public\n",
        })
        subprocess.run(["git", "-C", str(self.engine), "branch", "website"], check=True)
        subprocess.run(["git", "-C", str(self.engine), "checkout", "-q", "website"], check=True)
        (self.engine / "website/src/control").mkdir(parents=True)
        (self.engine / "website/src/control/index.html").write_text("control\n")
        subprocess.run(["git", "-C", str(self.engine), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.engine), "commit", "-qm", "current website"], check=True)
        subprocess.run(["git", "-C", str(self.engine), "checkout", "-q", "main"], check=True)
        make_repo(self.games, {"Source/game.cpp": "game\n"})
        self.state = WorkstationState(
            engine_repo=self.engine,
            games_repo=self.games,
            website_ref="website",
            commands=FakeCommands(),
            http_json=lambda path: {
                "/api/tags": {"models": [{"name": "qwen3-coder-next:biella"}]},
                "/api/ps": {"models": [{"name": "qwen3-coder-next:biella", "size_vram": 27702297886}]},
            }[path],
            meminfo=lambda: {"MemTotal": 90_000_000, "MemAvailable": 70_000_000},
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_overview_uses_lane_current_commit(self):
        website = self.state.payload("overview", "Website")
        engine = self.state.payload("overview", "Engine")
        self.assertEqual(website["lane"], "Website")
        self.assertEqual(website["active_task"], "current website")
        self.assertEqual(engine["active_task"], "current main")
        self.assertEqual(website["status"], "CURRENT")

    def test_capabilities_are_approved_and_no_shell_capability_exists(self):
        payload = self.state.payload("capabilities", "Engine")
        ids = {item["id"] for item in payload["items"]}
        self.assertIn("workstation.status", ids)
        self.assertIn("git.status.current", ids)
        self.assertNotIn("shell.exec", ids)
        self.assertTrue(all(item["status"] == "APPROVED" for item in payload["items"]))

    def test_services_hardware_workers_have_required_current_fields(self):
        services = self.state.payload("services", "Engine")
        names = {item["name"] for item in services["items"]}
        for required in {"GitHub", "Drive", "Cloudflare", "Ollama", "Codex", "Saturn"}:
            self.assertIn(required, names)
        hardware = self.state.payload("hardware", "Engine")
        self.assertIn("NVIDIA L40S", hardware["gpu"])
        self.assertEqual(hardware["vram_used"], "27702297886 bytes")
        self.assertIn("ram_used", hardware)
        usage_names = {item["name"] for item in hardware["usage"]}
        self.assertIn("Context mode", usage_names)
        self.assertIn("Context file budget", usage_names)
        self.assertIn("Context byte budget", usage_names)
        self.assertIn("Context log tail", usage_names)
        self.assertIn("Context search results", usage_names)
        workers = self.state.payload("workers", "Engine")
        worker_names = {item["name"] for item in workers["items"]}
        for required in {"Ollama", "Qwen", "Codex", "Saturn MCP", "Cloudflare tunnel"}:
            self.assertIn(required, worker_names)

    def test_files_are_separated_by_lane(self):
        website = self.state.payload("files", "Website")["items"]
        engine = self.state.payload("files", "Engine")["items"]
        games = self.state.payload("files", "Games")["items"]
        website_paths = {item["path"] for item in website}
        engine_paths = {item["path"] for item in engine}
        games_paths = {item["path"] for item in games}
        self.assertIn("website/src/control/index.html", website_paths)
        self.assertNotIn("website/src/control/index.html", engine_paths)
        self.assertIn("src/engine.py", engine_paths)
        self.assertEqual(games_paths, {"Source/game.cpp"})

    def test_milestones_only_describe_current_runtime_evidence(self):
        payload = self.state.payload("milestones", "Website")
        text = json_text = str(payload).lower()
        self.assertNotIn("superseded", text)
        self.assertNotIn("historical", text)
        self.assertTrue(any(item["status"] in {"COMPLETE", "CURRENT", "READY"} for item in payload["items"]))


if __name__ == "__main__":
    unittest.main()
