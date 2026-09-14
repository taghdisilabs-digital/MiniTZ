#!/usr/bin/env python3
"""Read back native aim/control/regression bytes and evaluated pose stability."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from run_d01_039 import file_identity, write_json
from run_d02_01 import reject_material_fallbacks, runtime_has_task_error


def rows(path):
    with path.open(encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def verify_run(directory, expected):
    report = json.loads((directory / 'validation.json').read_text())
    assert report['result'] == expected, f'Unexpected result: {directory}'
    runtime = report['runtime']
    assert runtime['returncode'] == 0 and not runtime['timed_out']
    assert runtime['log_finalization']['closed']
    assert report['identities_before'] == report['identities_after']
    for identity in report['identities_after'] + report.get('captures', []) + report.get('measurements', []) + [runtime['log']]:
        assert file_identity(Path(identity['path'])) == identity, f'Changed bytes: {identity["path"]}'
    log = Path(runtime['log']['path']).read_text(errors='replace')
    assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log
    assert not runtime_has_task_error(log)
    reject_material_fallbacks(log)
    from PIL import Image
    captures = sorted(directory.rglob('*.png'))
    assert captures, f'No native captures: {directory}'
    for path in captures:
        with Image.open(path) as im:
            im.load()
            assert im.size == (1280, 720)
    return report, [file_identity(path) for path in captures]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('positive', 'disabled', 'contact', 'animation', 'environment', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve prior receipts; use a fresh output path'
    receipt = dict(task_id='D03-01', task_status='CONTINUE', result='FAIL',
                   time=datetime.now(timezone.utc).isoformat())
    try:
        reports, inputs, captures = [], [], []
        for name in ('positive', 'disabled', 'contact', 'animation', 'environment'):
            directory = getattr(args, name)
            report, decoded = verify_run(directory, 'EXPECTED_NEGATIVE_CONTROL' if name == 'disabled' else 'PASS')
            reports.append(report)
            inputs.append(file_identity(directory / 'validation.json'))
            captures.extend(decoded)
        maps = [{item['path']: item for item in report['identities_after']} for report in reports]
        common = set.intersection(*(set(mapping) for mapping in maps))
        assert len(common) > 250, 'Incomplete common source/build/content lineage'
        assert all(all(mapping[key] == maps[0][key] for mapping in maps) for key in common), 'Regression lineage differs'
        assert reports[0]['identities_after'] == reports[1]['identities_after'], 'Disabled control lineage differs'
        checks = rows(args.positive / 'checks.csv')
        assert len(checks) == 7
        assert all(float(row['pitch_error']) < 2 and float(row['ray_angle']) < 5 and float(row['weight']) > .99 for row in checks)
        negative = rows(args.disabled / 'checks.csv')
        assert len(negative) == 3 and all(float(row['weight']) == 0 for row in negative)
        assert max(float(row['pitch_error']) for row in negative) > 15
        poses = [{key: float(value) for key, value in row.items()} for row in rows(args.positive / 'poses.csv')]
        settled = []
        for phase, end in ((2, 1.3), (3, 1.3), (4, 1.3), (5, 1.4)):
            samples = [row for row in poses if row['phase'] == phase and .8 <= row['age'] < end]
            assert len(samples) >= 3, f'Insufficient settled pose evidence: {phase}'
            error = max(abs(row['barrel_pitch'] - row['camera_pitch']) for row in samples)
            assert error < 2 and all(row['aim_weight'] > .99 for row in samples)
            pairs = [(a, b) for a, b in zip(samples, samples[1:]) if b['frame'] == a['frame'] + 1]
            assert pairs, 'No consecutive rendered poses'
            step = max(abs(a['barrel_pitch'] - b['barrel_pitch']) for a, b in pairs)
            assert step < 1, 'Settled barrel jumps by more than 1 degree per frame'
            settled.append(dict(phase=phase, frames=len(samples), max_pitch_error_degrees=error, max_barrel_step_degrees=step))
        receipt.update(result='PASS', inputs=inputs, common_input_identities=len(common),
                       captures=captures, aim_pose_frames=len(poses), settled_windows=settled,
                       max_check_pitch_error_degrees=max(float(row['pitch_error']) for row in checks),
                       max_check_ray_angle_degrees=max(float(row['ray_angle']) for row in checks),
                       disabled_max_pitch_error_degrees=max(float(row['pitch_error']) for row in negative),
                       capture_status='GENERATED_DRAFT',
                       limitations='Native integration fixtures with population frozen, existing Manny rig and blockout weapon/world. Settled pose stability is not shipping frame-time, package, PSO, final art, or full D03 qualification.')
    except (AssertionError, OSError, ValueError, KeyError) as error:
        receipt['result'] = 'FAIL'
        receipt['error'] = str(error)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=receipt['time'], type='aim_readback',
                                         status='CONTINUE', diagnostics=str(error), evidence=str(args.output))) + '\n')
    write_json(args.output, receipt)
    print(json.dumps({key: value for key, value in receipt.items() if key not in ('captures', 'inputs')}, indent=2))
    return 0 if receipt['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
