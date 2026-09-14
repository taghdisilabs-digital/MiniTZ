from types import SimpleNamespace
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"ops/local-ai"))
import minitz_production_evidence as evidence
import minitz_codex_routing as routing

def test_working_complete_already_advances_as_complete(monkeypatch):
    calls=[]
    monkeypatch.setattr(evidence,"load_project_production",lambda _p:SimpleNamespace(run_id="minitz-task-program"))
    monkeypatch.setattr(evidence,"find_task",lambda *_a:SimpleNamespace(status="WORKING"))
    monkeypatch.setattr(evidence,"mark_task_complete",lambda *a:calls.append(a))
    result=evidence.TaskResult("T","COMPLETE_ALREADY","done",("current work",))
    evidence.apply_result(Path("/repo"),Path("/repo"),result,routing.Route("qwen3-coder-next:minitz","none","ollama"))
    assert calls and calls[0][3]=="COMPLETE"

def test_already_completed_task_is_idempotent(monkeypatch):
    monkeypatch.setattr(evidence,"load_project_production",lambda _p:SimpleNamespace(run_id="minitz-task-program"))
    monkeypatch.setattr(evidence,"find_task",lambda *_a:SimpleNamespace(status="COMPLETE"))
    monkeypatch.setattr(evidence,"mark_task_complete",lambda *_a:(_ for _ in ()).throw(AssertionError("must not rewrite completion")))
    evidence.apply_result(Path("/repo"),Path("/repo"),evidence.TaskResult("T","COMPLETE","done",()),routing.Route("gpt-6-astra","ultra"))

def test_continue_never_advances(monkeypatch):
    monkeypatch.setattr(evidence,"load_project_production",lambda _p:SimpleNamespace(run_id="minitz-task-program"))
    monkeypatch.setattr(evidence,"find_task",lambda *_a:SimpleNamespace(status="WORKING"))
    monkeypatch.setattr(evidence,"mark_task_complete",lambda *_a:(_ for _ in ()).throw(AssertionError("CONTINUE must not advance")))
    evidence.apply_result(Path("/repo"),Path("/repo"),evidence.TaskResult("T","CONTINUE","work remains",()),routing.Route("gpt-6-astra","ultra"))
