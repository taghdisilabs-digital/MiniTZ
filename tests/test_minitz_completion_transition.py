from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))
import biella_codex_routing as routing
import biella_production_state as state

spec = importlib.util.spec_from_file_location(
    "minitz_completion_transition_evidence",
    LOCAL_AI / "biella_production_evidence.py",
)
assert spec and spec.loader
evidence = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evidence
spec.loader.exec_module(evidence)
def _contract():
    return {
        "task_id": "T",
        "task_revision": 2,
        "task_digest": "a" * 64,
        "scope_ref": "task://minitz/T/2",
        "required_criteria": (),
        "allowed_criteria": ("done",),
    }


def _result(status="COMPLETE_ALREADY"):
    return evidence.TaskResult(
        "T", status, "validated", (), 2, "a" * 64,
        "task://minitz/T/2", None, None, ("done",),
    )


def test_working_complete_already_is_admitted_as_fresh_complete(monkeypatch):
    calls = []
    monkeypatch.setattr(evidence, "_minitz_completion_contract", lambda _task: (_contract(), {"status": "WORKING"}))
    import biella.validation as validation

    def admit(self, *args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(accepted=True, reason="")
    def no_prior(*_args, **_kwargs):
        raise AssertionError("WORKING task must not require prior acceptance")

    monkeypatch.setattr(validation.ValidationCompletionFamily, "admit", admit)
    monkeypatch.setattr(validation.ValidationCompletionFamily, "verify_prior_acceptance", no_prior)
    status = evidence._admit_minitz_result(_result(), SimpleNamespace(status="WORKING"))
    assert status == "COMPLETE"
    assert calls and calls[0][0][4] == "COMPLETE"


def test_completed_task_still_requires_prior_acceptance(monkeypatch):
    row = {"status": "COMPLETE", "revision": 3, "completion": {"evidence": ["persisted"]}}
    contract = {**_contract(), "task_revision": 3, "scope_ref": "task://minitz/T/3"}
    monkeypatch.setattr(evidence, "_minitz_completion_contract", lambda _task: (contract, row))
    import biella.validation as validation
    calls = []

    def prior(self, *args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(accepted=True, reason="")

    monkeypatch.setattr(validation.ValidationCompletionFamily, "verify_prior_acceptance", prior)
    result = evidence.TaskResult("T", "COMPLETE_ALREADY", "done", (), 3, "a" * 64, "task://minitz/T/3")
    assert evidence._admit_minitz_result(result, SimpleNamespace(status="COMPLETE")) == "COMPLETE_ALREADY"
    assert calls


def test_apply_result_uses_normalized_completion_status(monkeypatch, tmp_path):
    task = state.TaskRecord("T", "hard", "task", "WORKING", (), "minitz")
    production = state.ProductionState(tmp_path, "IN_PROGRESS", "minitz", "T", [
        state.SectionRecord("minitz", "MiniTZ", "IN_PROGRESS", [task])
    ], run_id="minitz-task-program")
    monkeypatch.setattr(evidence, "load_project_production", lambda _root: production)
    monkeypatch.setattr(evidence, "find_task", lambda _production, _task: task)
    monkeypatch.setattr(evidence, "_admit_minitz_result", lambda _result, _task: "COMPLETE")
    applied = []
    monkeypatch.setattr(evidence, "mark_task_complete", lambda *_args: applied.append(_args))
    evidence.apply_result(tmp_path, tmp_path, _result(), routing.Route("gpt-5.6-luna", "high"))
    assert applied
    assert applied[0][3] == "COMPLETE"
