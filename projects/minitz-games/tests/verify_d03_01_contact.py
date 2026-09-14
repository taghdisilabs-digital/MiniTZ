#!/usr/bin/env python3
"""Read back contact evidence, source lineage and settled native pose stability."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from run_d01_039 import file_identity, write_json


def read_csv(path):
    with path.open(encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def verify_run(directory, expected):
    report = json.loads((directory / 'validation.json').read_text())
    assert report['result'] == expected, f'Unexpected validation: {directory}'
    assert report['runtime']['returncode'] == 0
    assert report['runtime']['log_finalization']['closed']
    assert report['identities_before'] == report['identities_after']
    assert json.loads((directory / 'result.json').read_text(encoding='utf-8-sig'))['success']
    for identity in report['identities_after'] + report.get('captures', []) + report.get('measurements', []) + [report['runtime']['log']]:
        assert file_identity(Path(identity['path'])) == identity, f'Changed bytes: {identity["path"]}'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('positive', 'disabled', 'regression', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve prior receipts; use a fresh output path'
    receipt = dict(task_id='D03-01', task_status='CONTINUE', result='FAIL',
                   time=datetime.now(timezone.utc).isoformat())
    try:
        positive = verify_run(args.positive, 'PASS')
        disabled = verify_run(args.disabled, 'EXPECTED_NEGATIVE_CONTROL')
        regression = verify_run(args.regression, 'PASS')
        assert positive['identities_after'] == disabled['identities_after'], 'Control lineage differs'
        maps = [{x['path']: x for x in r['identities_after']} for r in (positive, regression)]
        common = maps[0].keys() & maps[1].keys()
        assert all(maps[0][key] == maps[1][key] for key in common), 'Regression lineage differs'
        receipt['common_input_identities'] = len(common)
        receipt['inputs'] = [file_identity(p / 'validation.json') for p in (args.positive, args.disabled, args.regression)]
        rows = [{k: float(v) for k, v in x.items()} for x in read_csv(args.positive / 'poses.csv')]
        # These stationary windows start after acquisition and end before the
        # screenshot request. Retain all raw frames, including screenshot stalls.
        windows = {1: 1.2, 2: 1.2, 3: 1.2, 4: 1.2, 10: .6, 12: .6, 15: .6, 17: .7}
        settled = []
        for phase, end in windows.items():
            samples = [r for r in rows if r['phase'] == phase and .5 <= r['age'] < end]
            assert len(samples) >= 3, f'Insufficient settled evidence: phase {phase}'
            assert all(min(r['left_weight'], r['right_weight']) > .99 for r in samples), 'Contact lost on stable support'
            error = max(r['max_contact_error'] for r in samples)
            assert error < 2, 'Settled sole error exceeds 2 cm'
            assert all(abs(r['actor_z'] - 1088) < .1 for r in samples), 'Cosmetic correction moved capsule'
            pairs = [(a, b) for a, b in zip(samples, samples[1:]) if b['frame'] == a['frame'] + 1]
            assert pairs, 'Missing consecutive rendered pose frames'
            step = max(abs(a[side + '_z'] - b[side + '_z']) for a, b in pairs for side in ('left', 'right'))
            assert step < 1, 'Settled ankle height jumps by more than 1 cm per frame'
            settled.append(dict(phase=phase, frames=len(samples), max_sole_error_cm=error, max_ankle_step_cm=step))
        checks = read_csv(args.positive / 'checks.csv')
        qualified = [r for r in checks if r['phase'] not in ('steep_rejected', 'gap_rejected', 'missing_one_support')]
        assert all(abs(float(r['sole_error'])) < 2 and float(r['normal_angle']) < 8 for r in qualified)
        negative = read_csv(args.disabled / 'checks.csv')
        split = [abs(float(r['sole_error'])) for r in negative if r['phase'] == 'split_levels']
        assert len(split) == 2 and min(split) > 8, 'Disabled control must expose error in both feet'
        assert all(float(r['weight']) == 0 for r in negative)
        receipt.update(result='PASS', settled_windows=settled,
                       max_qualified_sole_error_cm=max(abs(float(r['sole_error'])) for r in qualified),
                       max_qualified_normal_error_degrees=max(float(r['normal_angle']) for r in qualified),
                       disabled_split_error_cm=split, contact_pose_frames=len(rows),
                       animation_regression_pose_frames=regression['pose_frames'],
                       capture_status='GENERATED_DRAFT',
                       limitations='Cosmetic integration fixture on the canonical gameplay map. Settled pose windows are not shipping frame-time qualification; raw screenshot stalls are retained. No final art or full D03 completion claim.')
    except (AssertionError, OSError, ValueError, KeyError) as error:
        receipt['result'] = 'FAIL'
        receipt['error'] = str(error)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=receipt['time'], type='contact_readback',
                                         status='CONTINUE', diagnostics=str(error), evidence=str(args.output))) + '\n')
    write_json(args.output, receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
