from __future__ import annotations
import copy, json, sys
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ops/local-ai'))
import minitz_task_program as program
import minitz_production_evidence as evidence
import minitz_production_runner as runner
import minitz_codex_routing as routing


def test_task_program_does_not_require_value_gate(tmp_path: Path):
    source=Path('/root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json')
    raw=json.loads(source.read_text())
    for row in raw['tasks']:
        if row.get('status') in program.ACTIVE_STATUSES:
            row.pop('review_state',None)
            row['task_record_sha256']=program.task_digest(row)
    target=tmp_path/'TASK_PROGRAM.json'
    raw['current_live_production_authority']=str(target.resolve())
    target.write_text(json.dumps(raw,indent=2)+'\n')
    loaded=program.load(target)
    expected=next(row['task_id'] for row in raw['tasks'] if row.get('status') in program.ACTIVE_STATUSES)
    assert program.current_task(loaded)['task_id']==expected


def test_minitz_complete_advances_without_validation_family(monkeypatch):
    production=SimpleNamespace(run_id='minitz-task-program')
    task=SimpleNamespace(status='WORKING')
    calls=[]
    monkeypatch.setattr(evidence,'load_project_production',lambda _root: production)
    monkeypatch.setattr(evidence,'find_task',lambda _prod,_id: task)
    monkeypatch.setattr(evidence,'mark_task_complete',lambda *args: calls.append(args))
    result=evidence.TaskResult('MINITZ-X','COMPLETE','work finished',('current implementation committed',))
    evidence.apply_result(Path('/repo'),Path('/repo'),result,routing.Route('qwen3-coder-next:minitz','none','ollama'))
    assert calls and calls[0][3]=='COMPLETE'


def test_task_bound_result_schema_has_no_validation_admission_fields(monkeypatch):
    schema=evidence.result_schema('T')
    assert schema['required']==['task_id','status','summary','evidence']
    assert set(schema['properties'])=={'task_id','status','summary','evidence'}


def test_bounded_local_helper_has_no_progression_authority():
    result=evidence.TaskResult('T','COMPLETE','done',('evidence',))
    route=routing.Route('qwen3-coder-next:minitz','none','ollama')
    assert runner._normalize_result_for_route(result,route).status=='CONTINUE'


def test_completion_boundary_commits_current_owned_bytes_without_validation_digest(tmp_path: Path, monkeypatch):
    owned={'src/a.txt':'old-digest'}
    (tmp_path/'src').mkdir(); (tmp_path/'src/a.txt').write_text('new current bytes')
    monkeypatch.setattr(evidence,'_dirty_paths',lambda _root:{'src/a.txt'})
    monkeypatch.setattr(evidence,'_git',lambda *_a,**_k: SimpleNamespace(stdout='abc\n'))
    result=evidence.TaskResult('T','COMPLETE','done',('evidence',))
    out=evidence.enforce_clean_completion_boundary(tmp_path,result,owned_files=owned)
    assert out.status=='COMPLETE'
