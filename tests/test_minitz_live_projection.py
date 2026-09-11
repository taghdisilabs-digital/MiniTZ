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


def test_minitz_projection_exposes_main_coder_pool_from_runtime():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp); repo = base / "repo"; repo.mkdir()
        runtime = base / "runtime"; runtime.mkdir()
        (runtime / "runtime.json").write_text(json.dumps({
            "active_coder": "codex",
            "coder_statuses": {"codex": "ACTIVE", "agr": "NEEDS_MODIFICATION"},
            "coder_status_detail": {"agr": "eligibility check failed"},
        }))
        analysis = base / "live_audit"; execution = analysis / "minitz_execution"
        stream_dir = execution / "T-1"; stream_dir.mkdir(parents=True)
        (analysis / "TASK_PROGRAM.json").write_text(json.dumps({
            "revision": 1, "tasks": [{"task_id": "T-1", "status": "PENDING", "title": "Task"}]
        }))
        (stream_dir / "stdout.jsonl").write_text(json.dumps({"type": "turn.started"}) + "\n")
        live = MiniTZLiveProjection(repo=repo, runtime_root=runtime, assets=AssetCatalog({"Games": [], "Website": []}), analysis_root=analysis)
        live._stage = lambda memory: {"primary": None, "showcase": [], "mode": "NONE", "unreal_live": False}
        live._system_activity = lambda: {"gpu": {}, "host": {}, "local_ai": {"state": "OFFLINE"}}
        live._git_info = lambda: {"commit": "TEST", "tree": "TEST", "message": "test", "committed_at": ""}
        snapshot = live.refresh(force_assets=True, force_system=True, force_git=True)
        assert snapshot["production"]["active_coder"] == "codex"
        assert snapshot["production"]["main_coders"] == {"codex": "ACTIVE", "agr": "NEEDS_MODIFICATION"}
        assert snapshot["production"]["main_coder_detail"]["agr"] == "eligibility check failed"


def test_minitz_live_snapshot_exposes_same_bounded_commander_summary():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp); repo=base/"repo"; repo.mkdir(); runtime=base/"runtime"; runtime.mkdir()
        (runtime/"runtime.json").write_text(json.dumps({"task_id":"T"}))
        fabric=runtime/"memory/commander-fabric"; fabric.mkdir(parents=True)
        (fabric/"current.json").write_text(json.dumps({"schema":"minitz.commander_fabric/v1","authority":"NONE","task_id":"T","total_lanes":30,"lanes":[{"lane_id":"CMD-01","role":"requirements","status":"ACTIVE","activity":"USEFUL","provider":"groq","summary":"PRIVATE"}]}))
        analysis=base/"audit"; execution=analysis/"minitz_execution"; stream=execution/"T"; stream.mkdir(parents=True)
        (stream/"stdout.jsonl").write_text(json.dumps({"type":"turn.started"})+"\n")
        (analysis/"TASK_PROGRAM.json").write_text(json.dumps({"revision":1,"tasks":[{"task_id":"T","status":"PENDING","title":"Task"}]}))
        live=MiniTZLiveProjection(repo=repo,runtime_root=runtime,assets=AssetCatalog({"Games":[],"Website":[]}),analysis_root=analysis)
        live._stage=lambda memory:{"primary":None,"showcase":[],"mode":"NONE","unreal_live":False}
        live._system_activity=lambda:{"gpu":{},"host":{},"local_ai":{"state":"OFFLINE"}}
        live._git_info=lambda:{"commit":"TEST","tree":"TEST","message":"test","committed_at":""}
        commanders=live.refresh(force_assets=True,force_system=True,force_git=True)["production"]["commanders"]
        assert commanders["total_lanes"] == 30 and commanders["useful"] == 1
        assert "lanes" not in commanders and "provider" not in json.dumps(commanders)
        assert "PRIVATE" not in json.dumps(commanders)


def test_minitz_live_snapshot_exposes_sanitized_five_boost_summary():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp); repo=base/"repo"; repo.mkdir(); runtime=base/"runtime"; runtime.mkdir()
        (runtime/"runtime.json").write_text(json.dumps({"task_id":"T"}))
        boost=runtime/"memory/boost-fabric"; boost.mkdir(parents=True)
        (boost/"current.json").write_text(json.dumps({
            "schema":"minitz.boost_fabric/v1","authority":"NONE","progression_authority":False,
            "runtime_state":"ARMED_NOT_STARTED","current_task_id":"T","total_commanders":30,
            "boosts":[{"boost_id":f"BOOST-{i:02d}","name":f"B{i}","status":"WAITING_FOR_OWNER_RESUME","commander_lanes":[f"CMD-{i:02d}"],"assignment_path":"/private/a"} for i in range(1,6)]
        }))
        analysis=base/"audit"; stream=analysis/"minitz_execution"/"T"; stream.mkdir(parents=True)
        (stream/"stdout.jsonl").write_text(json.dumps({"type":"turn.started"})+"\n")
        (analysis/"TASK_PROGRAM.json").write_text(json.dumps({"revision":1,"tasks":[{"task_id":"T","status":"PENDING","title":"Task"}]}))
        live=MiniTZLiveProjection(repo=repo,runtime_root=runtime,assets=AssetCatalog({"Games":[],"Website":[]}),analysis_root=analysis)
        live._stage=lambda memory:{"primary":None,"showcase":[],"mode":"NONE","unreal_live":False}
        live._system_activity=lambda:{"gpu":{},"host":{},"local_ai":{"state":"OFFLINE"}}
        live._git_info=lambda:{"commit":"TEST","tree":"TEST","message":"test","committed_at":""}
        boosts=live.refresh(force_assets=True,force_system=True,force_git=True)["production"]["boosts"]
        assert boosts["total_boosts"] == 5
        assert boosts["runtime_state"] == "ARMED_NOT_STARTED"
        assert "/private/" not in json.dumps(boosts)


def test_minitz_public_snapshot_forces_commander_offline_when_production_stopped():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp); repo=base/"repo"; repo.mkdir(); runtime=base/"runtime"; runtime.mkdir()
        (runtime/"runtime.json").write_text(json.dumps({"task_id":"T"}))
        fabric=runtime/"memory/commander-fabric"; fabric.mkdir(parents=True)
        (fabric/"current.json").write_text(json.dumps({"schema":"minitz.commander_fabric/v1","authority":"NONE","task_id":"T","total_lanes":30,"lanes":[{"lane_id":"CMD-01","role":"requirements","status":"ACTIVE","activity":"RUNNING","provider":"groq"}]}))
        analysis=base/"audit"; stream=analysis/"minitz_execution"/"T"; stream.mkdir(parents=True)
        (stream/"stdout.jsonl").write_text(json.dumps({"type":"turn.started"})+"\n")
        (analysis/"TASK_PROGRAM.json").write_text(json.dumps({"revision":1,"tasks":[{"task_id":"T","status":"PENDING","title":"Task"}]}))
        live=MiniTZLiveProjection(repo=repo,runtime_root=runtime,assets=AssetCatalog({"Games":[],"Website":[]}),analysis_root=analysis)
        live._stage=lambda memory:{"primary":None,"showcase":[],"mode":"NONE","unreal_live":False}
        live._system_activity=lambda:{"gpu":{},"host":{},"local_ai":{"state":"OFFLINE"}}
        live._git_info=lambda:{"commit":"TEST","tree":"TEST","message":"test","committed_at":""}
        live._production_status=lambda:{"status":"STOPPED"}
        commanders=live.refresh(force_assets=True,force_system=True,force_git=True)["production"]["commanders"]
        assert commanders["status"] == "OFFLINE"
        assert commanders["active"] == 0 and commanders["inflight"] == 0
