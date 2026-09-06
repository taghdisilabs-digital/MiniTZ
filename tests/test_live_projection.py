from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ops.control_gateway.biella_control_assets import AssetCatalog, AssetRoot
from ops.control_gateway.biella_live_projection import LiveProjection


class LiveProjectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        self.game = self.repo / "projects" / "biella-games"
        self.presentation = self.game / "Build" / "Presentation"
        self.presentation.mkdir(parents=True)
        self.runtime = base / "runtime"
        (self.runtime / "task-memory").mkdir(parents=True)
        self.capture = self.presentation / "current" / "captures" / "frame.png"
        self.capture.parent.mkdir(parents=True)
        self.capture.write_bytes(b"\x89PNG\r\ncurrent-frame")
        self.assets = AssetCatalog({
            "Games": [AssetRoot("games-presentation", self.presentation, "TASK_EVIDENCE")],
            "Website": [],
        })
        self.live = LiveProjection(repo=self.repo, runtime_root=self.runtime, assets=self.assets)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sanitizes_agent_dialog_and_classifies_tool_activity(self):
        message = self.live.sanitize_event({
            "type": "agent.message", "seq": 7, "task_id": "D03-01", "time": "2026-09-06T07:00:00+00:00",
            "text": "Built /root/biella/repos/biella-engine/projects/biella-games/Build/Presentation/current/frame.png",
        })
        self.assertEqual(message["category"], "BIELLA")
        self.assertNotIn("/root/biella/repos/biella-engine", message["text"])
        test_event = self.live.sanitize_event({
            "type": "tool.started", "tool": "shell", "status": "IN_PROGRESS", "seq": 8,
            "task_id": "D03-01", "text": "python3 tests/verify_d03_01_shadow.py",
        })
        self.assertEqual(test_event["category"], "TEST")
        self.assertEqual(test_event["state"], "RUNNING")
        self.assertNotIn("python3", test_event["text"])

    def test_current_task_evidence_resolves_to_public_stage_asset(self):
        validation = self.presentation / "current" / "validation.json"
        validation.write_text(json.dumps({"result": "PASS", "captures": [{"path": str(self.capture)}]}))
        memory = {
            "task_id": "D03-01",
            "current_increment": {"validation": "Build/Presentation/current/validation.json"},
        }
        stage = self.live._stage(memory)
        self.assertIsNotNone(stage["primary"])
        self.assertEqual(stage["primary"]["name"], "frame.png")
        self.assertTrue(stage["primary"]["url"].startswith("/live-api/asset?"))

    def test_public_asset_resolution_is_preview_only_and_root_bounded(self):
        lane, path = self.live.resolve_public_asset("games-presentation", "current/captures/frame.png")
        self.assertEqual(lane, "Games")
        self.assertEqual(path, self.capture)
        with self.assertRaises(ValueError):
            self.live.resolve_public_asset("games-presentation", "../secret.png")
        with self.assertRaises(ValueError):
            self.live.resolve_public_asset("games-content", "anything.png")


if __name__ == "__main__":
    unittest.main()
