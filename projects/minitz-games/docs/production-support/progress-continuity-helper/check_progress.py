#!/usr/bin/env python3
"""Read-only liveness and forward-progress view over the canonical production runner."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve()
PROJECT = HERE.parents[3]
REPO = HERE.parents[5]
RUNTIME_ROOT = Path('/mnt/biella-extra/biella-runtime/codex-production')
RUNTIME = RUNTIME_ROOT / 'runtime.json'
UNIT = 'biella-codex-production.service'
sys.path.insert(0, str(REPO / 'ops/local-ai'))
import biella_production_runner as production_runner


def file_identity(path):
    path = Path(path)
    if not path.is_file():
        return None
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    stat = path.stat()
    return {'path': str(path), 'sha256': digest, 'bytes': stat.st_size,
            'mtime_ns': stat.st_mtime_ns}


def command(*args):
    return subprocess.run(args, cwd=REPO, text=True, capture_output=True, check=False)


def service_state():
    proc = command('systemctl', 'show', UNIT, '-p', 'ActiveState', '-p', 'SubState',
                   '-p', 'MainPID', '-p', 'NRestarts')
    values = {}
    for line in proc.stdout.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            values[key] = value
    return values


def pid_alive(value):
    try:
        pid = int(value or 0)
    except (TypeError, ValueError):
        return False
    return pid > 0 and (Path('/proc') / str(pid)).exists()


def latest_activity(task_id):
    candidates = [
        PROJECT / 'Build/AAA' / task_id,
        PROJECT / 'Build/Release' / task_id,
        PROJECT / 'Build/Qualification' / task_id,
    ]
    files = []
    for root in candidates:
        if root.is_dir():
            files.extend(path for path in root.rglob('*') if path.is_file())
    if not files:
        return None
    newest = max(files, key=lambda path: path.stat().st_mtime_ns)
    return file_identity(newest)


def latest_result(task_id):
    attempts = RUNTIME_ROOT / 'attempts'
    matches = sorted(attempts.glob(f'*-{task_id}-*.result.json')) if attempts.is_dir() else []
    return file_identity(matches[-1]) if matches else None


def worktree_fingerprint():
    proc = command('git', 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    return hashlib.sha256(proc.stdout.encode('utf-8', errors='surrogateescape')).hexdigest()


def snapshot():
    runtime = json.loads(RUNTIME.read_text(encoding='utf-8'))
    canonical = production_runner.production_status(REPO, PROJECT, RUNTIME)
    task_id = canonical.get('current_task') or runtime.get('task_id')
    task_memory = RUNTIME_ROOT / 'task-memory' / f'{task_id}.json' if task_id else None
    return {
        'schema': 'biella.games.progress_snapshot/v1',
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'canonical_status': canonical,
        'service': service_state(),
        'runtime': {key: runtime.get(key) for key in (
            'status', 'task_id', 'attempt', 'pid', 'child_pid', 'task_session_id',
            'active_model', 'active_reasoning', 'heartbeat_at', 'updated_at')},
        'head': command('git', 'rev-parse', 'HEAD').stdout.strip(),
        'tree': command('git', 'rev-parse', 'HEAD^{tree}').stdout.strip(),
        'worktree_fingerprint': worktree_fingerprint(),
        'task_memory': file_identity(task_memory) if task_memory else None,
        'latest_task_activity': latest_activity(task_id) if task_id else None,
        'latest_completed_attempt': latest_result(task_id) if task_id else None,
    }


def progress_markers(before, after):
    markers = []
    if before.get('head') != after.get('head'):
        markers.append('git_head_changed')
    if before.get('tree') != after.get('tree'):
        markers.append('git_tree_changed')
    if before.get('runtime', {}).get('attempt') != after.get('runtime', {}).get('attempt'):
        markers.append('attempt_changed')
    if (before.get('task_memory') or {}).get('sha256') != (after.get('task_memory') or {}).get('sha256'):
        markers.append('task_memory_changed')
    before_activity = (before.get('latest_task_activity') or {}).get('mtime_ns', 0)
    after_activity = (after.get('latest_task_activity') or {}).get('mtime_ns', 0)
    if after_activity > before_activity:
        markers.append('task_evidence_activity_advanced')
    if (before.get('latest_completed_attempt') or {}).get('sha256') != (after.get('latest_completed_attempt') or {}).get('sha256'):
        markers.append('completed_attempt_changed')
    return markers


def heartbeat_age_seconds(runtime):
    raw = runtime.get('heartbeat_at')
    if not raw:
        return None
    observed = datetime.fromisoformat(raw)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - observed).total_seconds()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    snap = sub.add_parser('snapshot')
    snap.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('check')
    check.add_argument('--baseline', type=Path)
    check.add_argument('--require-forward', action='store_true')
    check.add_argument('--require-material', action='store_true')
    args = parser.parse_args()
    current = snapshot()
    if args.operation == 'snapshot':
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(current, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(json.dumps({'result': 'PASS', 'output': str(args.output),
                          'task_id': current['runtime'].get('task_id')}, sort_keys=True))
        return 0

    runtime = current['runtime']
    service = current['service']
    age = heartbeat_age_seconds(runtime)
    active = service.get('ActiveState') == 'active' and service.get('SubState') == 'running'
    canonical_active = current['canonical_status'].get('status') == 'ACTIVE'
    task_id = current['canonical_status'].get('current_task')
    checks = {
        'canonical_liveness_active': canonical_active,
        'service_active': active,
        'runtime_task_matches_canonical': runtime.get('task_id') == task_id,
        'runtime_pid_matches_service': str(runtime.get('pid')) == service.get('MainPID'),
        'runner_process_alive': pid_alive(runtime.get('pid')),
        'child_process_consistent': not runtime.get('child_pid') or pid_alive(runtime.get('child_pid')),
        'heartbeat_fresh_under_canonical_90s_rule': age is not None and age <= 90,
    }
    baseline = json.loads(args.baseline.read_text(encoding='utf-8')) if args.baseline else None
    markers = progress_markers(baseline, current) if baseline else []
    material_names = {'git_head_changed', 'git_tree_changed', 'task_evidence_activity_advanced', 'completed_attempt_changed'}
    material_markers = [marker for marker in markers if marker in material_names]
    continuity_markers = [marker for marker in markers if marker not in material_names]
    if material_markers:
        progress_state = 'MATERIAL_FORWARD_PROGRESS_OBSERVED'
    elif continuity_markers:
        progress_state = 'EXECUTION_CONTINUITY_ADVANCED'
    else:
        progress_state = 'RUNNING_NO_MATERIAL_DELTA_YET'
    if args.require_forward:
        checks['forward_progress_since_baseline'] = bool(markers)
    if args.require_material:
        checks['material_project_progress_since_baseline'] = bool(material_markers)
    same_session = None
    if baseline:
        before_session = baseline.get('runtime', {}).get('task_session_id')
        after_session = runtime.get('task_session_id')
        same_session = bool(before_session and before_session == after_session)
    report = {
        'schema': 'biella.games.progress_check/v1',
        'result': 'PASS' if all(checks.values()) else 'FAIL',
        'task_id': task_id,
        'progress_state': progress_state,
        'progress_markers': markers,
        'material_progress_markers': material_markers,
        'continuity_progress_markers': continuity_markers,
        'same_task_session_as_baseline': same_session,
        'heartbeat_age_seconds': age,
        'checks': checks,
        'current': current,
        'baseline': str(args.baseline) if args.baseline else None,
        'interpretation': (
            'Fresh canonical heartbeat/process state proves liveness. Only explicit markers prove '
            'material forward progress; absence of a marker is not called a stall while canonical liveness is ACTIVE.'
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
