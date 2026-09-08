#!/usr/bin/env python3
"""Read-only integrity check for canonical Biella Games source and continuity."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve()
PROJECT = HERE.parents[3]
REPO = HERE.parents[5]
RUNTIME_ROOT = Path('/mnt/biella-extra/biella-runtime/codex-production')
RUNTIME = RUNTIME_ROOT / 'runtime.json'
TASK_MEMORY = RUNTIME_ROOT / 'task-memory/D17-01.json'
STATE03 = REPO / 'docs/project-state/03_BIELLA_CURRENT_STATE.md'
STATE04 = REPO / 'docs/project-state/04_BIELLA_ACTIVE_TASK.md'
PRODUCTION = PROJECT / 'docs/PRODUCTION.md'
UNIT = 'biella-codex-production.service'


def run(*args):
    return subprocess.run(args, cwd=REPO, text=True, capture_output=True, check=False)


def sha256(path):
    path = Path(path)
    if not path.is_file():
        return None
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extract_task(path, pattern):
    text = Path(path).read_text(encoding='utf-8')
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else None


def first_unfinished():
    text = PRODUCTION.read_text(encoding='utf-8')
    for match in re.finditer(r'^-\s+\[([ xX])\]\s+([A-Z]\d{2}-\d{2})\s+\|', text, re.MULTILINE):
        if match.group(1) == ' ':
            return match.group(2)
    return None


def service_state():
    proc = run('systemctl', 'show', UNIT, '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID', '-p', 'NRestarts')
    values = {}
    for line in proc.stdout.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            values[key] = value
    values['query_returncode'] = proc.returncode
    return values


def pid_alive(value):
    try:
        return int(value or 0) > 0 and Path('/proc') .joinpath(str(int(value))).exists()
    except (TypeError, ValueError):
        return False


def dirty_paths():
    proc = run('git', 'status', '--porcelain=v1', '--untracked-files=all')
    paths = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        value = line[3:]
        if ' -> ' in value:
            value = value.split(' -> ', 1)[1]
        paths.append(value)
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expect-service', choices=('active', 'stopped', 'either'), default='either')
    args = parser.parse_args()

    branch = run('git', 'branch', '--show-current').stdout.strip()
    head = run('git', 'rev-parse', 'HEAD').stdout.strip()
    tree = run('git', 'rev-parse', 'HEAD^{tree}').stdout.strip()
    task03 = extract_task(STATE03, r'^active_execution:\s*\n.*?^  id:\s*([A-Z0-9-]+)\s*$')
    task04 = extract_task(STATE04, r'^task:\s*\n.*?^  id:\s*([A-Z0-9-]+)\s*$')
    production_task = first_unfinished()
    runtime = json.loads(RUNTIME.read_text(encoding='utf-8'))
    service = service_state()
    task_memory = RUNTIME_ROOT / 'task-memory' / f'{task03}.json'
    dirty = dirty_paths()
    continuity_allowed = {
        'docs/project-state/03_BIELLA_CURRENT_STATE.md',
        'docs/project-state/04_BIELLA_ACTIVE_TASK.md',
        'docs/task-program/D_TASK_LEDGER.json',
    }
    unexpected_dirty = [p for p in dirty if not (
        p.startswith('projects/biella-games/') or p in continuity_allowed)]
    git_dir_raw = run('git', 'rev-parse', '--git-dir').stdout.strip()
    git_dir = (REPO / git_dir_raw).resolve() if not Path(git_dir_raw).is_absolute() else Path(git_dir_raw)
    operations = [name for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD') if (git_dir / name).exists()]
    operations += [name for name in ('rebase-merge', 'rebase-apply') if (git_dir / name).exists()]
    active = service.get('ActiveState') == 'active' and service.get('SubState') == 'running'

    checks = {
        'branch_is_main': branch == 'main',
        'git_identity_resolved': bool(head and tree),
        'no_active_git_operation': not operations,
        'task_alignment_03_04_production': bool(task03) and task03 == task04 == production_task,
        'runtime_task_alignment': runtime.get('task_id') == task03,
        'task_memory_present': task_memory.is_file() and task_memory.stat().st_size > 0,
        'no_unexpected_non_project_dirty_paths': not unexpected_dirty,
        'helper_excluded_from_cook_inputs': HERE.relative_to(PROJECT).parts[0] == 'docs',
    }
    if args.expect_service == 'active':
        checks['service_active'] = active
    elif args.expect_service == 'stopped':
        checks['service_stopped'] = not active and service.get('MainPID') in ('0', None)
    if active:
        checks['runtime_pid_matches_service'] = str(runtime.get('pid')) == service.get('MainPID')
        checks['runtime_process_alive'] = pid_alive(runtime.get('pid'))
        checks['child_process_consistent'] = not runtime.get('child_pid') or pid_alive(runtime.get('child_pid'))
    elif args.expect_service == 'stopped':
        checks['previous_runtime_process_not_alive'] = not pid_alive(runtime.get('pid'))

    report = {
        'schema': 'biella.games.source_integrity_helper/v1',
        'result': 'PASS' if all(checks.values()) else 'FAIL',
        'branch': branch,
        'head': head,
        'tree': tree,
        'task': {'state03': task03, 'state04': task04, 'production': production_task,
                 'runtime': runtime.get('task_id')},
        'service': service,
        'runtime': {key: runtime.get(key) for key in (
            'status', 'task_id', 'attempt', 'pid', 'child_pid', 'task_session_id',
            'active_model', 'active_reasoning', 'heartbeat_at', 'updated_at')},
        'task_memory': {'path': str(task_memory), 'sha256': sha256(task_memory),
                        'bytes': task_memory.stat().st_size if task_memory.is_file() else None},
        'dirty_paths': dirty,
        'unexpected_dirty_paths': unexpected_dirty,
        'git_operations': operations,
        'checks': checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
