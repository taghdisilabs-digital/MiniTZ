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
        assert snapshot["connection"]["state"] == "STALE"
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
            "runtime_state":"ACTIVE","current_task_id":"T","total_commanders":30,
            "boosts":[{"boost_id":f"BOOST-{i:02d}","name":f"B{i}","status":"READY","commander_lanes":[f"CMD-{i:02d}"],"assignment_path":"/private/a"} for i in range(1,6)]
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
        assert boosts["runtime_state"] == "ACTIVE"
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


def test_minitz_projection_prefers_canonical_current_execution_over_newer_old_stream():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp); repo=base/'repo'; repo.mkdir(); runtime=base/'runtime'; runtime.mkdir()
        analysis=base/'audit'; execution=analysis/'minitz_execution'
        old=execution/'OLD'; old.mkdir(parents=True); (old/'stdout.jsonl').write_text(json.dumps({'type':'turn.started'})+'\n')
        current=execution/'UNIFY-07'; current.mkdir(); (current/'stdout.jsonl').write_text(json.dumps({'type':'turn.started'})+'\n')
        os.utime(old/'stdout.jsonl',(2000,2000)); os.utime(current/'stdout.jsonl',(1000,1000))
        (analysis/'TASK_PROGRAM.json').write_text(json.dumps({'revision':55,'current_execution':{
            'task_id':'UNIFY-07','task_revision':3,'task_sha256':'5'*64},'tasks':[
            {'task_id':'OLD','status':'PENDING','title':'Old'},{'task_id':'UNIFY-07','status':'PENDING','title':'Current'}]}))
        (runtime/'runtime.json').write_text(json.dumps({'task_id':'UNIFY-07','status':'RUNNING','heartbeat_at':'2026-09-11T19:00:00+00:00'}))
        live=MiniTZLiveProjection(repo=repo,runtime_root=runtime,assets=AssetCatalog({'Games':[],'Website':[]}),analysis_root=analysis)
        live._stage=lambda memory:{'primary':None,'showcase':[],'mode':'NONE','unreal_live':False}; live._system_activity=lambda:{'gpu':{},'host':{},'local_ai':{'state':'RESIDENT'}}; live._git_info=lambda:{'commit':'TEST'}
        live._production_status=lambda:{'status':'RUNNING'}
        assert live.refresh(force_assets=True,force_system=True,force_git=True)['production']['task_id']=='UNIFY-07'


def test_minitz_projection_does_not_synthesize_liveness_when_runner_stopped():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp); repo=base/'repo'; repo.mkdir(); runtime=base/'runtime'; runtime.mkdir(); analysis=base/'audit'
        stream=analysis/'minitz_execution'/'T'; stream.mkdir(parents=True); (stream/'stdout.jsonl').write_text(json.dumps({'type':'turn.started'})+'\n')
        (analysis/'TASK_PROGRAM.json').write_text(json.dumps({'revision':1,'current_execution':{'task_id':'T'},'tasks':[{'task_id':'T','status':'PENDING','title':'Task'}]}))
        heartbeat='2026-09-11T18:00:00+00:00'; (runtime/'runtime.json').write_text(json.dumps({'task_id':'T','status':'RUNNING','heartbeat_at':heartbeat,'coder_statuses':{'codex':'ACTIVE','agr':'NEEDS_MODIFICATION'}}))
        live=MiniTZLiveProjection(repo=repo,runtime_root=runtime,assets=AssetCatalog({'Games':[],'Website':[]}),analysis_root=analysis)
        live._stage=lambda memory:{'primary':None,'showcase':[],'mode':'NONE','unreal_live':False}; live._system_activity=lambda:{'gpu':{},'host':{},'local_ai':{'state':'RESIDENT'}}; live._git_info=lambda:{'commit':'TEST'}
        live._production_status=lambda:{'status':'STOPPED'}
        snapshot=live.refresh(force_assets=True,force_system=True,force_git=True)
        assert snapshot['connection']['state']=='STOPPED'
        assert snapshot['production']['state']=='STOPPED'
        assert snapshot['production']['heartbeat_at']==heartbeat
        event=live.heartbeat_event(); assert event['heartbeat_at']==heartbeat


def test_minitz_projection_reports_local_qwen_fallback_without_fake_codex_active():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp); repo=base/'repo'; repo.mkdir(); runtime=base/'runtime'; runtime.mkdir(); analysis=base/'audit'
        stream=analysis/'minitz_execution'/'T'; stream.mkdir(parents=True); (stream/'stdout.jsonl').write_text(json.dumps({'type':'turn.started'})+'\n')
        (analysis/'TASK_PROGRAM.json').write_text(json.dumps({'revision':1,'current_execution':{'task_id':'T'},'tasks':[{'task_id':'T','status':'PENDING','title':'Task'}]}))
        future='2099-01-01T00:00:00+00:00'; (runtime/'runtime.json').write_text(json.dumps({
            'task_id':'T','status':'RUNNING','heartbeat_at':future,'active_model':'qwen3-coder-next:biella','active_coder':'codex',
            'coder_statuses':{'codex':'ACTIVE','agr':'NEEDS_MODIFICATION'},'cooldowns':{'gpt-reserve':future}}))
        live=MiniTZLiveProjection(repo=repo,runtime_root=runtime,assets=AssetCatalog({'Games':[],'Website':[]}),analysis_root=analysis)
        live._stage=lambda memory:{'primary':None,'showcase':[],'mode':'NONE','unreal_live':False}; live._system_activity=lambda:{'gpu':{},'host':{},'local_ai':{'state':'RESIDENT'}}; live._git_info=lambda:{'commit':'TEST'}
        live._production_status=lambda:{'status':'RUNNING'}
        p=live.refresh(force_assets=True,force_system=True,force_git=True)['production']
        assert p['active_coder']=='local-qwen'
        assert p['main_coders']['codex']=='OUT_OF_CREDIT'


def test_host_memory_metrics_expose_active_cache_and_available_ram():
    from ops.control_gateway.biella_live_projection import _host_memory_metrics
    metrics = _host_memory_metrics("""MemTotal:       90501512 kB
MemAvailable:   86251972 kB
Buffers:         2577760 kB
Cached:         78563912 kB
SReclaimable:    4020904 kB
Shmem:             50096 kB
""")
    assert metrics["ram_used_mib"] == round((90501512 - 86251972) / 1024, 1)
    assert metrics["ram_cache_mib"] == round((2577760 + 78563912 + 4020904 - 50096) / 1024, 1)
    assert metrics["ram_available_mib"] == round(86251972 / 1024, 1)


def test_live_ui_distinguishes_active_ram_from_cache():
    text = (Path(__file__).resolve().parents[1] / "website/src/live/app.js").read_text(encoding="utf-8")
    assert "ram_cache_mib" in text
    assert "active +" in text


def test_minitz_projection_exposes_current_quality_and_pressure_validation(tmp_path):
    repo=tmp_path/'repo'; repo.mkdir(); runtime=tmp_path/'runtime'; runtime.mkdir(); analysis=tmp_path/'audit'
    stream=analysis/'minitz_execution'/'T'; stream.mkdir(parents=True); (stream/'stdout.jsonl').write_text(json.dumps({'type':'turn.started'})+'\n')
    digest='a'*64
    (analysis/'TASK_PROGRAM.json').write_text(json.dumps({'revision':2,'current_execution':{'task_id':'T','task_revision':2,'task_sha256':digest},'tasks':[{'task_id':'T','revision':2,'task_record_sha256':digest,'status':'WORKING','title':'Task'}]}))
    (runtime/'runtime.json').write_text(json.dumps({'task_id':'T','status':'RUNNING','heartbeat_at':'2099-01-01T00:00:00+00:00'}))
    qualification=tmp_path/'qualification.json'
    qualification.write_text(json.dumps({'observed_at_epoch':1000,'task':{'task_id':'T','task_sha256':digest},'qualification':{'current_capacity':{'allowed':True,'reasons':[]},'results':[{'case':'quality-a','quality':{'verdict':'PASS','score':1.0}},{'case':'quality-b','quality':{'verdict':'PASS','score':0.95}}]}}))
    live=MiniTZLiveProjection(repo=repo,runtime_root=runtime,assets=AssetCatalog({'Games':[],'Website':[]}),analysis_root=analysis,qualification_path=qualification)
    live._stage=lambda memory:{'primary':None,'showcase':[],'mode':'NONE','unreal_live':False}; live._system_activity=lambda:{'gpu':{},'host':{},'local_ai':{'state':'RESIDENT'}}; live._git_info=lambda:{'commit':'TEST'}; live._production_status=lambda:{'status':'RUNNING'}
    validation=live.refresh(force_assets=True,force_system=True,force_git=True)['production']['latest_validation']
    assert validation['state']=='PASS' and validation['passed']==2 and validation['total']==2
    assert validation['capacity_allowed'] is True and validation['task_digest_match'] is True


def test_minitz_projection_quality_fails_when_evaluator_or_pressure_rejects(tmp_path):
    repo=tmp_path/'repo'; repo.mkdir(); runtime=tmp_path/'runtime'; runtime.mkdir(); analysis=tmp_path/'audit'
    stream=analysis/'minitz_execution'/'T'; stream.mkdir(parents=True); (stream/'stdout.jsonl').write_text(json.dumps({'type':'turn.started'})+'\n')
    digest='b'*64; (analysis/'TASK_PROGRAM.json').write_text(json.dumps({'current_execution':{'task_id':'T','task_sha256':digest},'tasks':[{'task_id':'T','task_record_sha256':digest,'status':'WORKING'}]})); (runtime/'runtime.json').write_text(json.dumps({'task_id':'T','status':'RUNNING','heartbeat_at':'2099-01-01T00:00:00+00:00'}))
    q=tmp_path/'q.json'; q.write_text(json.dumps({'task':{'task_id':'T','task_sha256':digest},'qualification':{'current_capacity':{'allowed':False,'reasons':['MEMORY_PRESSURE']},'results':[{'case':'x','quality':{'verdict':'FAIL','score':0.2}}]}}))
    live=MiniTZLiveProjection(repo=repo,runtime_root=runtime,assets=AssetCatalog({}),analysis_root=analysis,qualification_path=q); live._stage=lambda m:{}; live._system_activity=lambda:{}; live._git_info=lambda:{}; live._production_status=lambda:{'status':'RUNNING'}
    validation=live.refresh(force_assets=True,force_system=True,force_git=True)['production']['latest_validation']
    assert validation['state']=='FAILED' and validation['capacity_allowed'] is False and validation['pressure_reasons']==['MEMORY_PRESSURE']
