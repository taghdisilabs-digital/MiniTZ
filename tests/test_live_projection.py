from __future__ import annotations

import json
from datetime import datetime, timezone
import os
import tempfile
import unittest
from pathlib import Path

from ops.control_gateway.minitz_control_assets import AssetCatalog, AssetRoot
from ops.control_gateway.minitz_live_projection import LiveProjection


class LiveProjectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        self.game = self.repo / "projects" / "minitz-games"
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
            "text": "Built /root/minitz/repos/minitz-engine/projects/minitz-games/Build/Presentation/current/frame.png",
        })
        self.assertEqual(message["category"], "MINITZ")
        self.assertNotIn("/root/minitz/repos/minitz-engine", message["text"])
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

    def test_apex_public_projection_exposes_main_coder_pool_with_safe_defaults(self):
        (self.game / "docs").mkdir(parents=True)
        (self.game / "docs" / "PRODUCTION.md").write_text("Current task: `D03-01`\n- [ ] D03-01 | hard | live | PENDING | evidence\n")
        (self.runtime / "runtime.json").write_text(json.dumps({
            "status": "RUNNING", "task_id": "D03-01",
            "active_coder": "agr",
            "coder_statuses": {"codex": "ACTIVE", "agr": "NEEDS_MODIFICATION"},
            "coder_status_detail": {"agr": "eligibility check failed"},
            "heartbeat_at": "2026-09-10T22:00:00+00:00",
        }))
        self.live._system_activity = lambda: {"gpu": {}, "host": {}, "local_ai": {"state": "OFFLINE"}}
        payload = self.live.refresh(force_system=True)
        production = payload["production"]
        self.assertEqual(production["active_coder"], "agr")
        self.assertEqual(production["main_coders"], {"codex": "ACTIVE", "agr": "NEEDS_MODIFICATION"})
        self.assertEqual(production["main_coder_detail"]["agr"], "eligibility check failed")

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


    def test_json_agent_message_projects_summary_not_raw_payload(self):
        event = self.live.sanitize_event({
            "type": "agent.message", "seq": 9, "task_id": "D03-01", "time": "2026-09-07T22:00:00+00:00",
            "text": json.dumps({"status": "CONTINUE", "summary": "Stable-key cook is progressing normally.", "evidence": ["private/path"]}),
        })
        self.assertEqual(event["text"], "Stable-key cook is progressing normally.")
        self.assertNotIn("evidence", event["text"])

    def test_cached_snapshot_avoids_request_time_asset_scan_and_system_probe(self):
        (self.game / "docs").mkdir(parents=True, exist_ok=True)
        (self.game / "docs" / "PRODUCTION.md").write_text("Current section: `post_d01`\nCurrent task: `D03-01`\n- [ ] D03-01 | hard_creation | live | PENDING | evidence\n")
        (self.runtime / "runtime.json").write_text(json.dumps({"status":"RUNNING","task_id":"D03-01","heartbeat_at":"2026-09-07T23:00:00+00:00"}))
        (self.runtime / "task-memory" / "D03-01.json").write_text(json.dumps({"title":"Live task","summary":"Current work"}))
        calls={"stage":0,"system":0}
        original_stage=self.live._stage
        self.live._stage=lambda memory: (calls.__setitem__("stage",calls["stage"]+1) or original_stage(memory))
        self.live._system_activity=lambda: (calls.__setitem__("system",calls["system"]+1) or {"gpu":{},"host":{}})
        self.live.refresh(force_assets=True, force_system=True)
        before=dict(calls)
        first=self.live.snapshot()
        second=self.live.snapshot()
        self.assertEqual(calls,before)
        self.assertEqual(first,second)

    def test_snapshot_surfaces_runtime_continuity_efficiency_and_local_ai(self):
        (self.game / "docs").mkdir(parents=True, exist_ok=True)
        (self.game / "docs" / "PRODUCTION.md").write_text(
            "Current section: `post_d01`\nCurrent task: `D04-01`\n"
            "- [x] D03-01 | hard_creation | done | COMPLETE | evidence\n"
            "- [ ] D04-01 | hard_creation | live | PENDING | evidence\n"
        )
        (self.runtime / "runtime.json").write_text(json.dumps({
            "status": "RUNNING", "task_id": "D04-01", "attempt": 306,
            "task_session_id": "session-abc", "session_task_id": "D04-01",
            "active_model": "gpt-reserve", "active_reasoning": "max",
            "heartbeat_at": "2026-09-08T02:20:00+00:00",
        }))
        (self.runtime / "task-memory" / "D04-01.json").write_text(json.dumps({"title": "Data-driven content"}))
        memory_dir = self.runtime / "memory"
        memory_dir.mkdir()
        (memory_dir / "current-task.json").write_text(json.dumps({
            "schema": "minitz.compacted_task_projection/v1", "task_id": "D04-01",
            "generated_at": "2026-09-08T02:19:00+00:00",
            "source_refs": ["a", "b"], "capabilities": {"llm.fast": ["ollama-qwen"]},
        }))
        self.live._system_activity = lambda: {
            "gpu": {}, "host": {},
            "local_ai": {"state": "RESIDENT", "model": "qwen3-coder-next:minitz", "context_length": 16384},
        }
        payload = self.live.refresh(force_system=True)
        production = payload["production"]
        self.assertEqual(production["execution_mode"], "AI_ACCELERATED_BUILD")
        self.assertEqual(production["continuity_status"], "PRESERVED")
        self.assertEqual(production["efficiency"]["state"], "ACTIVE")
        self.assertEqual(production["efficiency"]["source_ref_count"], 2)
        self.assertEqual(production["efficiency"]["capability_count"], 1)
        self.assertEqual(payload["system"]["local_ai"]["state"], "RESIDENT")
        self.assertNotIn("model", payload["system"]["local_ai"])

    def test_aaa_task_evidence_can_drive_public_stage(self):
        aaa = self.game / "Build" / "AAA"
        frame = aaa / "D17-02" / "raw" / "route-720-02" / "service-approach.png"
        frame.parent.mkdir(parents=True)
        frame.write_bytes(b"\x89PNG\r\nlatest-d17-frame")
        assets = AssetCatalog({
            "Games": [AssetRoot("games-aaa", aaa, "TASK_EVIDENCE")],
            "Website": [],
        })
        live = LiveProjection(repo=self.repo, runtime_root=self.runtime, assets=assets)
        stage = live._stage({})
        self.assertIsNotNone(stage["primary"])
        self.assertEqual(stage["primary"]["name"], "service-approach.png")
        self.assertIn("root_id=games-aaa", stage["primary"]["url"])
        lane, resolved = live.resolve_public_asset(
            "games-aaa", "D17-02/raw/route-720-02/service-approach.png")
        self.assertEqual(lane, "Games")
        self.assertEqual(resolved, frame)

    def test_latest_unreal_capture_preempts_older_preferred_evidence(self):
        aaa = self.game / "Build" / "AAA"
        latest = aaa / "D17-02" / "raw" / "live-1080" / "latest-frame.png"
        latest.parent.mkdir(parents=True)
        latest.write_bytes(b"\x89PNG\r\nlatest-unreal-frame")
        os.utime(self.capture, (1000, 1000))
        os.utime(latest, (3000, 3000))
        assets = AssetCatalog({
            "Games": [
                AssetRoot("games-presentation", self.presentation, "TASK_EVIDENCE"),
                AssetRoot("games-aaa", aaa, "TASK_EVIDENCE"),
            ],
            "Website": [],
        })
        live = LiveProjection(repo=self.repo, runtime_root=self.runtime, assets=assets)
        stage = live._stage({"capture": str(self.capture)})
        self.assertEqual(stage["mode"], "LATEST_UNREAL_CAPTURE_FIRST")
        self.assertEqual(stage["primary"]["name"], "latest-frame.png")
        self.assertEqual(stage["primary"]["stream_role"], "UNREAL_LIVE_FRAME")
        self.assertIn("root_id=games-aaa", stage["primary"]["url"])

    def test_public_snapshot_redacts_executor_and_model_identity(self):
        (self.game / "docs").mkdir(parents=True, exist_ok=True)
        (self.game / "docs" / "PRODUCTION.md").write_text(
            "Current section: `live`\nCurrent task: `D17-02`\n- [ ] D17-02 | hard | live | PENDING | evidence\n"
        )
        (self.runtime / "runtime.json").write_text(json.dumps({
            "status": "RUNNING", "task_id": "D17-02", "attempt": 356,
            "task_session_id": "secret-session", "session_task_id": "D17-02",
            "active_model": "internal-model-name", "active_reasoning": "ultra",
            "heartbeat_at": "2026-09-09T19:00:00+00:00",
        }))
        (self.runtime / "task-memory" / "D17-02.json").write_text(json.dumps({"title": "World build"}))
        self.live._system_activity = lambda: {
            "gpu": {}, "host": {},
            "local_ai": {"state": "RESIDENT", "model": "private-local-model", "context_length": 16384, "vram_mib": 12000},
        }
        payload = self.live.refresh(force_system=True)
        production = payload["production"]
        self.assertNotIn("model", production)
        self.assertNotIn("reasoning", production)
        self.assertNotIn("attempt", production)
        self.assertNotIn("continuity", production)
        self.assertEqual(production["execution_mode"], "AI_ACCELERATED_BUILD")
        local_ai = payload["system"]["local_ai"]
        self.assertEqual(local_ai["state"], "RESIDENT")
        self.assertNotIn("model", local_ai)
        self.assertNotIn("context_length", local_ai)

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


def test_public_live_snapshot_exposes_bounded_commander_fabric_summary():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp); repo=base/"repo"; game=repo/"projects/minitz-games"; (game/"docs").mkdir(parents=True)
        (game/"docs/PRODUCTION.md").write_text("Current task: `T`\n- [ ] T | hard | live | PENDING | evidence\n")
        runtime=base/"runtime"; (runtime/"task-memory").mkdir(parents=True)
        (runtime/"runtime.json").write_text(json.dumps({"status":"RUNNING","task_id":"T","heartbeat_at":datetime.now(timezone.utc).isoformat()}))
        fabric=runtime/"memory/commander-fabric"; fabric.mkdir(parents=True)
        (fabric/"current.json").write_text(json.dumps({
            "schema":"minitz.commander_fabric/v1","authority":"NONE","task_id":"T","total_lanes":30,
            "lanes":[{"lane_id":"CMD-01","role":"requirements","status":"ACTIVE","activity":"RUNNING","provider":"groq","result_path":"/private/result","summary":"PRIVATE"}],
        }))
        live=LiveProjection(repo=repo,runtime_root=runtime,assets=AssetCatalog({"Games":[],"Website":[]}))
        live._stage=lambda memory:{"primary":None,"showcase":[],"mode":"NONE","unreal_live":False}
        live._system_activity=lambda:{"gpu":{},"host":{},"local_ai":{"state":"OFFLINE"}}
        live._git_info=lambda:{"commit":"TEST","tree":"TEST","message":"test","committed_at":""}
        snapshot=live.refresh(force_assets=True,force_system=True,force_git=True)
        commanders=snapshot["production"]["commanders"]
        assert commanders["total_lanes"] == 30 and commanders["inflight"] == 1
        assert "lanes" not in commanders
        assert "provider" not in json.dumps(commanders)
        assert "PRIVATE" not in json.dumps(commanders) and "/private/" not in json.dumps(commanders)
