#!/usr/bin/env python3
"""Read back defeat poses, disabled control and affected native evidence."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from run_d01_039 import PROJECT, file_identity, write_json
from verify_d03_01_aim import rows, verify_run
from verify_d03_01_actions import exact, feedback_readback


def provenance(path):
    value = json.loads(path.read_text())
    entries = value if isinstance(value, list) else value['files']
    for entry in entries:
        for candidate in (Path(entry['source']), PROJECT / entry['local']):
            current = file_identity(candidate)
            assert all(current[key] == entry[key] for key in ('sha256', 'bytes')), f'Asset differs: {candidate}'
    return dict(provenance=file_identity(path), exact_source_and_local_entries=len(entries))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    names = ('positive', 'disabled', 'action', 'animation', 'environment')
    for name in (*names, 'feedback', 'build', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in (*names, 'feedback', 'build', 'output'):
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
        assert reports[0]['identities_after'] == reports[1]['identities_after'], 'Disabled control lineage differs'
        feedback, feedback_proof = feedback_readback(args.feedback)
        feedback_map = {item['path']: item for item in feedback['identities_after']}
        overlap = set(maps[0]) & set(feedback_map)
        required = {key for key in maps[0] if any(key.startswith(str(PROJECT / part)+'/') for part in ('Source', 'Config', 'Binaries'))}
        assert required <= overlap and all(maps[0][key] == feedback_map[key] for key in overlap), 'Feedback source/build lineage differs'
        inputs.append(file_identity(args.feedback / 'validation.json'))

        build = json.loads(args.build.read_text())
        assert build['result'] == 'PASS' and build['returncode'] == 0
        assert build['identities_before'] == build['identities_after'], 'Build changed tested inputs'
        build_map = {item['path']: item for item in build['identities_after']}
        assert required <= set(build_map) and all(maps[0][key] == build_map[key] for key in required), 'Build lineage differs'
        for identity in build['identities_after'] + [build['log']]:
            exact(identity)
        inputs.append(file_identity(args.build))

        positive = json.loads((args.positive / 'result.json').read_text(encoding='utf-8-sig'))
        negative = json.loads((args.disabled / 'result.json').read_text(encoding='utf-8-sig'))
        assert positive['success'] and negative['success'] and not positive['error'] and not negative['error']
        poses = [{key: float(value) for key, value in row.items()} for row in rows(args.positive / 'poses.csv')]
        disabled = [{key: float(value) for key, value in row.items()} for row in rows(args.disabled / 'poses.csv')]
        for data in (poses, disabled):
            assert {row['phase'] for row in data} == {4, 5, 6}
            assert all(row['root_drift'] < .1 for row in data), 'Cosmetic moved gameplay capsule'
        falling = [row for row in poses if row['phase'] == 4 and row['cosmetic'] == 1]
        assert len(falling) == positive['falling_frames'] and len(falling) >= 8
        for field in ('head_drop', 'pelvis_drop'):
            assert abs(max(row[field] for row in falling)-positive[field]) <= .000002, f'Changed {field} measurement'
        assert positive['head_drop'] > 60 and positive['pelvis_drop'] > 30
        assert positive['initial_pose_error'] < .1 and positive['root_drift'] < .1
        assert positive['hold_head_drift'] < 3 and positive['hold_pelvis_drift'] < 3
        assert all(positive['floor_z'] < positive[key] < positive['floor_z']+50 for key in ('settled_head_z', 'settled_pelvis_z'))
        assert all(row['cosmetic'] == 0 for row in disabled)
        expired = [row for row in poses if row['age'] > 3.15]
        assert expired and all(row['cosmetic'] == 0 for row in expired), 'Cosmetic outlived its bounded timer'
        assert any(row['cosmetic'] == 1 and row['age'] > 2 for row in poses)

        assets = [provenance(PROJECT / path) for path in (
            'SourceAssets/Characters/UE58Defeat.provenance.json',
            'SourceAssets/Characters/UE58DefeatPhysics.provenance.json',
            'Build/Presentation/defeat-candidates-01/candidate-provenance.json')]
        receipt.update(result='PASS', inputs=inputs, captures=captures,
                       common_input_identities=len(common), feedback_common_identities=len(overlap),
                       feedback=feedback_proof, positive=positive, disabled=negative,
                       pose_frames=len(poses), disabled_pose_frames=len(disabled), assets=assets,
                       capture_status='GENERATED_DRAFT',
                       limitations='Native on-foot Manny integration and representative static road contact. Other directional/seated/vehicle actions, final art, crowd/LOD/platform costs, native frame-time, shader/PSO, supported renderer fallback and packaged play remain D03 work. The cvar control qualifies this cosmetic layer only.')
    except (AssertionError, OSError, ValueError, KeyError) as error:
        receipt.update(result='FAIL', error=str(error))
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=receipt['time'], type='defeat_readback',
                                         status='CONTINUE', diagnostics=str(error), evidence=str(args.output)))+'\n')
    write_json(args.output, receipt)
    print(json.dumps({key: receipt[key] for key in ('task_id', 'task_status', 'result')} | {'error': receipt.get('error'), 'output': str(args.output)}))
    return 0 if receipt['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
