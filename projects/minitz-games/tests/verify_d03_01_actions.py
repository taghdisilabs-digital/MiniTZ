#!/usr/bin/env python3
"""Read back action/control and affected native regression evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from run_d01_039 import PROJECT, file_identity, write_json
from run_d01_042 import REQUIRED_PHASES, decode_audio
from run_d01_043 import finalize_log
from run_d02_01 import reject_material_fallbacks, runtime_has_task_error
from verify_d03_01_aim import rows, verify_run
from verify_d03_01_audio_mix import measure, qualify_mix


def exact(identity):
    current = file_identity(Path(identity['path']))
    assert all(identity[key] == value for key, value in current.items()), f'Changed bytes: {identity["path"]}'
    return current


def feedback_readback(directory):
    report = json.loads((directory / 'validation.json').read_text())
    assert report['result'] == 'PASS'
    runtime = report['runtime']
    assert runtime['returncode'] == 0 and not runtime['timed_out']
    assert report['identities_before'] == report['identities_after']
    for identity in report['identities_after'] + report['frames'] + report['audio']:
        exact(identity)
    log_path = Path(runtime['log']['path'])
    closed = finalize_log(log_path)
    assert closed['closed'], 'Feedback log has an open writer'
    raw = log_path.read_bytes()
    recorded = runtime['log']
    # The legacy runner records before the detached trace daemon closes stdout.
    # Preserve that receipt and prove its exact prefix before admitting a suffix.
    assert hashlib.sha256(raw[:recorded['bytes']]).hexdigest() == recorded['sha256']
    suffix = raw[recorded['bytes']:].decode(errors='strict')
    if suffix:
        assert 'Daemon is exiting without errors.' in suffix, 'Unrecognized late feedback log suffix'
    log = raw.decode(errors='replace')
    assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log
    assert not runtime_has_task_error(log)
    reject_material_fallbacks(log)
    assert REQUIRED_PHASES <= set(report['phases'])
    for audio in report['audio']:
        assert decode_audio(Path(audio['path'])) == audio
    return report, dict(log=file_identity(log_path), log_finalization=closed,
                        original_log_prefix=recorded, late_suffix_bytes=len(raw)-recorded['bytes'],
                        phases=report['phases'], audio=report['audio'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    names = ('positive', 'disabled', 'aim', 'animation', 'environment', 'audio')
    for name in (*names, 'feedback', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in (*names, 'feedback', 'output'):
        setattr(args, name, getattr(args, name).resolve())
    assert not args.output.exists(), 'Preserve prior receipts'
    receipt = dict(task_id='D03-01', task_status='CONTINUE', result='FAIL', time=datetime.now(timezone.utc).isoformat())
    try:
        reports, inputs, captures = [], [], []
        for name in names:
            directory = getattr(args, name)
            report, decoded = verify_run(directory, 'EXPECTED_NEGATIVE_CONTROL' if name == 'disabled' else 'PASS')
            reports.append(report)
            inputs.append(file_identity(directory / 'validation.json'))
            captures.extend(decoded)
        maps = [{item['path']: item for item in report['identities_after']} for report in reports]
        common = set.intersection(*(set(mapping) for mapping in maps))
        assert len(common) > 250, 'Incomplete common source/build/content lineage'
        assert all(all(mapping[key] == maps[0][key] for mapping in maps) for key in common), 'Regression lineage differs'
        assert reports[0]['identities_after'] == reports[1]['identities_after'], 'Control lineage differs'
        feedback, feedback_proof = feedback_readback(args.feedback)
        feedback_map = {item['path']: item for item in feedback['identities_after']}
        overlap = set(maps[0]) & set(feedback_map)
        required = {key for key in maps[0] if any(key.startswith(str(PROJECT / part)+'/') for part in ('Source', 'Config', 'Binaries'))}
        assert required <= overlap and all(maps[0][key] == feedback_map[key] for key in overlap), 'Feedback source/build lineage differs'
        inputs.append(file_identity(args.feedback / 'validation.json'))
        mix = measure(args.audio)
        qualify_mix(mix, False)
        assert mix == reports[-1]['mix'], 'Mixer measurements changed'
        checks, negative = rows(args.positive / 'checks.csv'), rows(args.disabled / 'checks.csv')
        assert {r['phase'] for r in checks} == {r['phase'] for r in negative} == {'fire', 'hit', 'overlap', 'rival_hit'}
        assert all(.25 < float(r['barrel_peak']) < 5 and float(r['foot_peak']) < .1 for r in checks)
        assert all(float(r['fire_peak']) == 0 and float(r['hit_peak']) == 0 and float(r['barrel_peak']) < .1 for r in negative)
        poses = [{k: float(v) for k, v in row.items()} for row in rows(args.positive / 'poses.csv')]
        windows = []
        for phase, end in ((3, .18), (6, .22), (8, .15), (17, .15)):
            samples = [row for row in poses if row['phase'] == phase and 0 < row['age'] < end]
            assert len(samples) >= 3, f'Insufficient native event samples: {phase}'
            pairs = [(a, b) for a, b in zip(samples, samples[1:]) if b['frame'] == a['frame']+1]
            assert pairs
            windows.append(dict(phase=phase, frames=len(samples),
                                max_barrel_angle_degrees=max(row['barrel_angle'] for row in samples),
                                max_consecutive_barrel_step_degrees=max(abs(a['barrel_angle']-b['barrel_angle']) for a, b in pairs),
                                max_foot_displacement_cm=max(row['foot_displacement'] for row in samples)))
        receipt.update(result='PASS', inputs=inputs, captures=captures, common_input_identities=len(common),
                       feedback_common_identities=len(overlap), feedback=feedback_proof, audio_mix=mix,
                       action_pose_frames=len(poses), reaction_windows=windows,
                       positive_checks=checks, disabled_checks=negative, capture_status='GENERATED_DRAFT',
                       limitations='Native integration fixtures and existing Manny/additive resources. Fixed audio fixtures are not hardware listening tests. Reaction-window steps are observed samples, not frame-time/platform qualification. Full D03 still requires defeat/vehicle/art/LOD and package/shader/PSO/fallback work.')
    except (AssertionError, OSError, ValueError, KeyError) as error:
        receipt.update(result='FAIL', error=str(error))
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=receipt['time'], type='actions_readback', status='CONTINUE', diagnostics=str(error), evidence=str(args.output)))+'\n')
    write_json(args.output, receipt)
    print(json.dumps({k: receipt[k] for k in ('task_id', 'task_status', 'result')} | {'error': receipt.get('error'), 'output': str(args.output)}))
    return 0 if receipt['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
