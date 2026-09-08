from pathlib import Path
import json, hashlib

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / 'projects/biella-games/docs/PRODUCTION.md'
MAP = ROOT / 'docs/task-program/D_NEXT_100_TASKS.json'
REG = ROOT / 'docs/task-program/D15_D24_AAA_CHALLENGER.md'
GUIDES = ROOT / 'projects/biella-games/docs/task-guides'


def order():
    rows=[]
    for line in PROD.read_text().splitlines():
        if line.startswith('- ['):
            parts=[x.strip() for x in line.split('|')]
            if len(parts)>1: rows.append(parts[0].split()[-1])
    return rows


def test_visual_last_layer_runs_immediately_after_d08_before_binding_reproducibility():
    ids=order(); pos={x:i for i,x in enumerate(ids)}
    assert pos['D08-01'] < pos['D17-01'] < pos['D17-08'] < pos['D15-01'] < pos['D16-01'] < pos['D19-01']


def test_dependencies_follow_visual_first_chain():
    rows={x['task_id']:x for x in json.loads(MAP.read_text())['tasks']}
    assert rows['D17-01']['depends_on']==['D08-01']
    assert rows['D15-01']['depends_on']==['D17-08']
    for i in range(2,9):
        assert rows[f'D17-{i:02d}']['depends_on']==[f'D17-{i-1:02d}']


def test_final_visual_layer_is_creation_not_a_review_only_gate():
    for tid in ('D17-05','D17-06','D17-07'):
        text=(GUIDES/f'{tid}.md').read_text()
        assert 'FINAL_VISUAL_LAYER' in text
        assert 'create/fix' in text.lower()
        assert 'owner visual direction' in text.lower()
        assert 'no review-only loop' in text.lower()


def test_d17_map_uses_current_guides_and_matching_digests():
    rows={x['task_id']:x for x in json.loads(MAP.read_text())['tasks']}
    for i in range(1,9):
        tid=f'D17-{i:02d}'; rel=f'projects/biella-games/docs/task-guides/{tid}.md'
        ref=next(x for x in rows[tid]['source_refs'] if x['path']==rel)
        assert ref['sha256']==hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
        assert not any('/future/' in x['path'] for x in rows[tid]['source_refs'])


def test_registry_dependency_matches_visual_first_chain():
    text=REG.read_text()
    assert '| `D17-01` | Select canonical AAA challenger slice | `PENDING` | D08-01 |' in text
    assert '| `D15-01` | Lock authoritative predecessor closure set | `PENDING` | D17-08 |' in text
