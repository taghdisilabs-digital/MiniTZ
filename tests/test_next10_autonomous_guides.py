from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / 'projects/minitz-games/docs/task-guides'
MAP = ROOT / 'docs/task-program/D_NEXT_100_TASKS.json'
TASKS = ['D17-01','D17-02','D17-03','D17-04','D17-05','D17-06','D17-07','D17-08','D19-01','D19-02']


def test_next_ten_have_current_autonomous_guides():
    for task in TASKS:
        text = (GUIDES / f'{task}.md').read_text()
        assert 'EXECUTOR_OWNS_ROUTINE_BLOCKER_RESOLUTION' in text
        assert 'NO_UNCHANGED_BLOCKER_RETRY' in text
        assert 'NO_REVIEW_OR_APPROVAL_WAIT' in text
        assert 'PRESERVE_REAL_ACCEPTANCE' in text


def test_next_ten_map_to_current_guides_with_exact_digests():
    rows = {x['task_id']: x for x in json.loads(MAP.read_text())['tasks']}
    for task in TASKS:
        rel = f'projects/minitz-games/docs/task-guides/{task}.md'
        refs = rows[task]['source_refs']
        ref = next(x for x in refs if x['path'] == rel)
        assert ref['sha256'] == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert not any('/future/' in x['path'] for x in refs)
