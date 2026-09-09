from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ops.control_gateway.biella_control_assets import AssetCatalog
from ops.control_gateway.minitz_live_projection import MiniTZLiveProjection


def test_minitz_projection_uses_current_task_checkpoint_not_legacy_runtime():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo = base / "repo"
        repo.mkdir()
        runtime = base / "runtime"
        runtime.mkdir()
        analysis = base / "live_audit"
        execution = analysis / "minitz_execution"
        stream_dir = execution / "TASKPROG-F01"
        stream_dir.mkdir(parents=True)

        (analysis / "TASK_PROGRAM.json").write_text(json.dumps({
            "schema": "minitz.living_task_program/v1",
            "revision": 14,
            "tasks": [{
                "task_id": "TASKPROG-F01",
                "status": "PENDING",
                "title": "Living MiniTZ task program",
                "required_capabilities": ["task_program.compile"],
            }],
        }))
        stream = stream_dir / "stdout.jsonl"
        stream.write_text("\n".join([
            json.dumps({"type": "turn.started"}),
            json.dumps({"type": "item.completed", "item": {
                "type": "agent_message",
                "text": "MiniTZ update from /root/biella/private/path",
            }}),
        ]) + "\n")
        os.utime(stream, (1000, 1000))
        (execution / "CHECKPOINT_TASKPROG-F01.json").write_text(json.dumps({
            "schema": "minitz.task_session_checkpoint/v1",
            "task_id": "TASKPROG-F01",
            "stopped_at": "2026-09-09T21:08:02+00:00",
            "task_program": {"task_status": "PENDING"},
        }))

        live = MiniTZLiveProjection(
            repo=repo,
            runtime_root=runtime,
            assets=AssetCatalog({"Games": [], "Website": []}),
            analysis_root=analysis,
        )
        live._stage = lambda memory: {"primary": None, "showcase": [], "mode": "NONE", "unreal_live": False}
        live._system_activity = lambda: {"gpu": {}, "host": {}, "local_ai": {"state": "OFFLINE"}}
        live._git_info = lambda: {"commit": "TEST", "tree": "TEST", "message": "test", "committed_at": ""}

        snapshot = live.refresh(force_assets=True, force_system=True, force_git=True)
        assert snapshot["schema"] == "minitz.public_live_snapshot/v1"
        assert snapshot["public_identity"] == "MiniTZ"
        assert snapshot["connection"]["state"] == "LIVE"
        assert snapshot["production"]["task_id"] == "TASKPROG-F01"
        assert snapshot["production"]["state"] == "WAITING"
        assert snapshot["production"]["current_operation"]["text"] == "TASKPROG-F01 · preserved checkpoint"

        events = live.events_since(0)
        assert events
        assert any("MiniTZ update" in event["text"] for event in events)
        assert all("/root/biella/" not in event["text"] for event in events)
