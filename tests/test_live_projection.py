from __future__ import annotations

import json
import os
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

    def test_production_status_reads_runtime_and_project_file_without_controller_call(self):
        (self.game / "docs").mkdir(parents=True)
        (self.game / "docs" / "PRODUCTION.md").write_text(
            "Current section: `post_d01`\nCurrent task: `D03-01`\n"
            "- [x] D02-04 | hard | done | COMPLETE | evidence\n"
            "- [ ] D03-01 | hard_creation | live | PENDING | registry_status=PENDING\n"
        )
        (self.runtime / "runtime.json").write_text(json.dumps({
            "status": "RUNNING", "task_id": "D03-01", "active_model": "model-a",
            "active_reasoning": "high", "heartbeat_at": "2026-09-06T07:00:00+00:00"
        }))
        self.live._run = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("controller/process command must not be invoked"))
        status = self.live._production_status()
        self.assertEqual(status["current_task"], "D03-01")
        self.assertEqual(status["current_section"], "post_d01")
        self.assertEqual(status["completed"], 1)
        self.assertEqual(status["total"], 2)
        self.assertEqual(status["active_model"], "model-a")

    def test_current_task_evidence_resolves_to_public_stage_asset(self):
        newer = self.capture.parent / "newer.png"
        newer.write_bytes(b"\x89PNG\r\nnewer-frame")
        os.utime(self.capture, (1000, 1000))
        os.utime(newer, (2000, 2000))
        validation = self.presentation / "current" / "validation.json"
        validation.write_text(json.dumps({"result": "PASS", "captures": [{"path": str(self.capture)}, {"path": str(newer)}]}))
        memory = {
            "task_id": "D03-01",
            "current_increment": {"validation": "Build/Presentation/current/validation.json"},
        }
        stage = self.live._stage(memory)
        self.assertIsNotNone(stage["primary"])
        self.assertEqual(stage["primary"]["name"], "newer.png")
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
