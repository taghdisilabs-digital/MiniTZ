from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/local-ai"))
import biella_customer_handoff as handoff
import biella_production_evidence as evidence
import biella_production_runner as runner
import biella_publication as publication
import biella_codex_routing as routing
from ops.control_gateway.biella_live_projection import LiveProjection


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def repo_fixture(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "source.txt").write_text("base\n")
    git(repo, "add", "."); git(repo, "commit", "-qm", "base")
    return repo


def test_optional_ai_failure_cannot_prevent_production_resume(tmp_path, monkeypatch):
    repo = repo_fixture(tmp_path)
    runtime = tmp_path / "runtime"; runtime.mkdir()
    (runtime / "runtime.json").write_text('{"task_id":"D05-01"}')
    manager = handoff.BiellaCustomerHandoff(repo, runtime, tmp_path / "handoff")
    monkeypatch.setattr(manager, "service_states", lambda: {n: {"active":True,"enabled":"enabled"} for n in handoff.PROTECTED_SERVICES})
    monkeypatch.setattr(manager, "cooperative_pause", lambda: None)
    monkeypatch.setattr(manager, "sleep_services", lambda: None)
    manager.checkpoint()
    monkeypatch.setattr(manager, "running_customer_count", lambda: 0)
    monkeypatch.setattr(manager, "verify_source_alignment", lambda: None)
    starts=[]
    monkeypatch.setattr(manager, "set_enabled_state", lambda *a: None)
    def active(name, enabled):
        starts.append(name)
        if name == "biella-qwen-residency.service":
            raise handoff.HandoffError("optional Qwen failed")
    monkeypatch.setattr(manager, "set_active_state", active)
    result=manager.resume()
    assert starts[0] == "biella-codex-production.service"
    assert result["status"] == "RESTORED"
    assert result["optional_resource_errors"]
    assert not manager.active_checkpoint_path.exists()


def test_autocommit_uses_exact_owned_digest_not_project_prefix(tmp_path):
    repo=repo_fixture(tmp_path)
    directory=repo/"projects/biella-games"; directory.mkdir(parents=True)
    task=directory/"task.txt"; task.write_text("validated\n")
    unrelated=directory/"unrelated.txt"; unrelated.write_text("other work\n")
    result=evidence.TaskResult("D05-01","COMPLETE","done",("test proof",))
    final=evidence.enforce_clean_completion_boundary(repo,result,owned_files={str(task.relative_to(repo)):hashlib.sha256(task.read_bytes()).hexdigest()})
    assert final.status == "COMPLETE"
    assert git(repo,"show","HEAD:projects/biella-games/task.txt") == "validated"
    assert "unrelated.txt" in git(repo,"status","--porcelain")
    assert not git(repo,"ls-files","projects/biella-games/unrelated.txt")


def test_autocommit_does_not_commit_changed_validation_bytes(tmp_path):
    repo=repo_fixture(tmp_path)
    p=repo/"source.txt"; p.write_text("changed since validation\n")
    result=evidence.TaskResult("D05-01","COMPLETE","done",("test proof",))
    old=git(repo,"rev-parse","HEAD")
    final=evidence.enforce_clean_completion_boundary(repo,result,owned_files={"source.txt":hashlib.sha256(b"validated\n").hexdigest()})
    assert final.status == "CONTINUE"
    assert git(repo,"rev-parse","HEAD") == old


def test_task_tracking_excludes_existing_unrelated_dirty_files(tmp_path):
    repo=repo_fixture(tmp_path)
    (repo/"unrelated.txt").write_text("preserve\n")
    before=evidence.workspace_snapshot(repo)
    (repo/"source.txt").write_text("task changed\n")
    owned=evidence.task_owned_outputs(repo,before,{})
    assert set(owned)=={"source.txt"}


def test_transport_outage_retains_known_conflict(tmp_path, monkeypatch):
    repo=repo_fixture(tmp_path)
    telemetry=runner.initial_runtime()
    telemetry["source_alignment"]={"state":"RECONCILIATION_REQUIRED","detail":"known overlap","remote_commit":"known"}
    monkeypatch.setattr(evidence,"assert_remote_source_current",lambda *a: (_ for _ in ()).throw(evidence.SourceTransportError("offline")))
    monkeypatch.setattr(runner,"_beat",lambda *a,**kw: None)
    class Journal:
        def emit(self,*a,**kw): pass
    assert runner._guard_source_alignment(repo,tmp_path/"runtime.json",telemetry,Journal())
    assert telemetry["source_alignment"]["state"]=="RECONCILIATION_REQUIRED"
    assert telemetry["source_alignment"]["detail"]=="known overlap"
    assert telemetry["source_alignment"]["transport_state"]=="UNAVAILABLE"


def test_github_readback_mismatch_never_publishes_drive(tmp_path, monkeypatch):
    repo=repo_fixture(tmp_path)
    identity={"commit":git(repo,"rev-parse","HEAD"),"tree":git(repo,"rev-parse","HEAD^{tree}")}
    publication.request_publication(repo,"D05-01",identity)
    called=[]
    monkeypatch.setattr(publication,"_remote",lambda args,**kw: subprocess.CompletedProcess(args,0,b"different refs/heads/main\n" if "ls-remote" in args else b"",b""))
    monkeypatch.setattr(publication,"publish_drive_revision",lambda *a,**kw: called.append(True) or {"verified":True})
    result=publication.drain_once(repo)
    assert not called
    assert result["last_receipt"]["source_state"]=="RECONCILIATION_REQUIRED"


def test_publication_conflict_survives_next_network_outage(tmp_path,monkeypatch):
    repo=repo_fixture(tmp_path)
    publication.request_publication(repo,"D05-01",{"commit":git(repo,"rev-parse","HEAD"),"tree":git(repo,"rev-parse","HEAD^{tree}")})
    p=publication._state_path(repo); d=json.loads(p.read_text()); d["last_receipt"]={"source_state":"RECONCILIATION_REQUIRED","commit":d["commit"]}; p.write_text(json.dumps(d))
    monkeypatch.setattr(publication,"_remote",lambda *a,**kw: (_ for _ in ()).throw(OSError("offline")))
    called=[]
    monkeypatch.setattr(publication,"publish_drive_revision",lambda *a,**kw: called.append(True) or {"verified":True})
    assert publication.drain_once(repo)["status"]=="PENDING"
    assert not called


def test_drive_retry_retains_verified_files(tmp_path,monkeypatch):
    repo=repo_fixture(tmp_path)
    (repo/"second.txt").write_text("second\n"); git(repo,"add","second.txt"); git(repo,"commit","-qm","second")
    commit=git(repo,"rev-parse","HEAD")
    publication.request_publication(repo,"D05-01",{"commit":commit,"tree":git(repo,"rev-parse","HEAD^{tree}")})
    monkeypatch.setattr(sys.modules["biella_production_evidence"],"drive_publications",lambda r: (("source.txt","gdrive:one"),("second.txt","gdrive:two")))
    monkeypatch.setattr(sys.modules["biella_production_evidence"],"derived_drive_publications",lambda r: ())
    monkeypatch.setattr(sys.modules["biella_production_evidence"],"control_drive_publications",lambda r: ())
    calls=[]; fail={"two":True}
    def remote(args,**kwargs):
        calls.append(args)
        if "gdrive:two" in args and fail["two"]:
            raise subprocess.CalledProcessError(1,args,stderr=b"rateLimitExceeded: actual provider diagnostic")
        if "cat" in args:
            return subprocess.CompletedProcess(args,0,b"base\n" if "gdrive:one" in args else b"second\n",b"")
        if "lsjson" in args:
            return subprocess.CompletedProcess(args,0,json.dumps({"ID":"file-one" if "gdrive:one" in args else "file-two"}).encode(),b"")
        return subprocess.CompletedProcess(args,0,b"",b"")
    monkeypatch.setattr(publication,"_remote",remote)
    first=publication.publish_drive_revision(repo,commit)
    assert not first["verified"]
    assert "rateLimitExceeded" in first["errors"][0]["error"]
    first_one=sum("gdrive:one" in c for c in calls)
    fail["two"]=False
    second=publication.publish_drive_revision(repo,commit)
    assert second["verified"]
    assert sum("gdrive:one" in c for c in calls)==first_one
    assert {f["path"] for f in second["files"]}=={"source.txt","second.txt"}


def test_snapshot_never_assigns_predecessor_completion_to_current(tmp_path,monkeypatch):
    repo=repo_fixture(tmp_path); rt=tmp_path/"runtime"; rt.mkdir()
    (rt/"runtime.json").write_text(json.dumps({"task_id":"D05-01","status":"RUNNING","heartbeat_at":datetime.now(timezone.utc).isoformat(),"last_result":{"task_id":"D04-01","status":"COMPLETE"}}))
    live=LiveProjection(repo=repo,runtime_root=rt,assets=None)
    monkeypatch.setattr(live,"_stage",lambda memory: {})
    monkeypatch.setattr(live,"_system_activity",lambda: {})
    monkeypatch.setattr(live,"_git_info",lambda: {})
    assert live.refresh()["production"]["task_status"]=="RUNNING"


def test_source_search_is_not_runtime_validation(tmp_path):
    live=LiveProjection(repo=tmp_path,runtime_root=tmp_path,assets=None)
    event={"task_id":"D05-01","type":"tool.completed","tool":"shell","status":"COMPLETED","exit_code":0,"text":"rg -n 'render capture validation.json' Source"}
    assert live._latest_validation("D05-01",[event]) is None


def test_only_digest_bound_validation_record_is_projected(tmp_path):
    live=LiveProjection(repo=tmp_path,runtime_root=tmp_path,assets=None)
    p=tmp_path/"validation.json"; p.write_text('{"task_id":"D05-01","result":"PASS"}')
    event={"task_id":"D05-01","type":"validation.completed","status":"PASS","evidence_path":str(p),"evidence_sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
    assert live._latest_validation("D05-01",[event]) is not None
    p.write_text('{"task_id":"D05-01","result":"FAIL"}')
    assert live._latest_validation("D05-01",[event]) is None


def test_preferred_reserve_uses_strong_alternative_without_lowering_reasoning(monkeypatch):
    monkeypatch.delenv("BIELLA_CODEX_FORCE_MODEL",raising=False)
    monkeypatch.setenv("BIELLA_CODEX_PREFER_MODEL","gpt-reserve")
    monkeypatch.setenv("BIELLA_CODEX_PREFER_REASONING","max")
    catalog={"gpt-reserve":{"max"},"gpt-6-astra":{"high","ultra"},"gpt-5.6-luna":{"high","max"}}
    now=datetime.now(timezone.utc)
    assert routing.select_route("medium",catalog,{},now).model=="gpt-reserve"
    route=routing.select_route("medium",catalog,{},now,excluded_models={"gpt-reserve"})
    assert (route.model,route.reasoning)==("gpt-6-astra","ultra")


def test_live_capsule_preserves_exact_task_output_ownership(tmp_path):
    repo=repo_fixture(tmp_path); project=repo/"projects/biella-games"; project.mkdir(parents=True)
    (project/"unrelated.txt").write_text("other work")
    baseline=evidence.workspace_snapshot(repo)
    task=runner.state.TaskRecord("D05-01","medium","UI","PENDING",(),"post_d01")
    telemetry=runner.initial_runtime(); telemetry.update({"task_id":"D05-01","session_task_id":"D05-01","task_session_id":"persistent","status":"RUNNING"})
    runtime=tmp_path/"runtime"; runtime.mkdir()
    (project/"owned.txt").write_text("current task")
    outputs=runner._checkpoint_task_activity(repo,project,runtime,task,telemetry,baseline,{})
    capsule=json.loads((runtime/"task-memory/D05-01.json").read_text())
    assert set(outputs)=={"projects/biella-games/owned.txt"}
    assert capsule["owned_files"]==outputs
    assert capsule["dirty_path_count"]==2
    runner._write_task_capsule(repo,project,runtime,task,telemetry)
    assert json.loads((runtime/"task-memory/D05-01.json").read_text())["owned_files"]==outputs


def test_ignored_proof_and_referenced_raw_evidence_are_preserved_not_scratch(tmp_path):
    repo=repo_fixture(tmp_path)
    (repo/".gitignore").write_text("Build/\n");git(repo,"add",".gitignore");git(repo,"commit","-qm","ignore scratch")
    proof=repo/"Build/D05-01";proof.mkdir(parents=True)
    (proof/"raw.json").write_text('{"measured":true}')
    (proof/"scratch.log").write_text("not required")
    report=proof/"validation.json"
    report.write_text(json.dumps({"task_id":"D05-01","result":"PASS","raw_evidence":str(proof/"raw.json")}))
    result=evidence.TaskResult("D05-01","COMPLETE","done",("Build/D05-01/validation.json",))
    final=evidence.enforce_clean_completion_boundary(repo,result,owned_files={})
    assert final.status=="COMPLETE"
    assert git(repo,"ls-files","Build/D05-01/validation.json")
    assert git(repo,"ls-files","Build/D05-01/raw.json")
    assert not git(repo,"ls-files","Build/D05-01/scratch.log")
