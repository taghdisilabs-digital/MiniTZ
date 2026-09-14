#!/usr/bin/env python3
"""Replay the SM6/default and SM5/fallback matrix from one native editor build."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from run_d01_039 import file_identity, write_json
from verify_d03_01_shader_platform import verify
from verify_d03_01_surfaces import verify as verify_surfaces
from verify_d02_04 import verify as verify_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--runs', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve previous series receipts'
    report = dict(task_id='D03-01', result='FAIL', runs=[], controls=[])
    try:
        build = json.loads((args.build/'result.json').read_text())
        assert build['result'] == 'PASS' and build['inputs_unchanged'], 'Native build failed'
        build_inputs = json.loads((args.build/'inputs-before.json').read_text())
        assert build_inputs == json.loads((args.build/'inputs-after.json').read_text()), 'Build inputs changed'
        reference = None
        matrix = set()
        for out in args.runs:
            out = out.resolve()
            validation = json.loads((out/'validation.json').read_text())
            assert validation['result'] == 'PASS', f'Native run failed: {out}'
            assert validation['identities_before'] == validation['identities_after'], 'Run inputs changed'
            if reference is None:
                reference = validation['identities_before']
            assert reference == validation['identities_before'], 'Different runtime input lineage'
            scenario = validation['scenario']
            level = validation['verify_feature_level']
            profile = validation['expected_profile']
            assert validation['feature_level'] == (None if level == 'sm6' else 'sm5'), 'Default/fallback launch not exercised'
            assert validation['runtime']['returncode'] == 0 and not validation['runtime']['timed_out'], 'Native process failed'
            assert validation['runtime']['log_finalization']['closed'], 'Native log not finalized'
            observed = verify(out, level, profile)
            assert observed == validation['shader_platform'], 'Shader readback drift'
            replay = verify_surfaces(out, 4 if profile == 'ProductionTSR' else 2, 100) if scenario == 'surfaces' else verify_environment(out)
            assert replay == validation['verification'], 'Scenario readback drift'
            key = (level, profile, scenario)
            assert key not in matrix, 'Duplicate matrix run'
            matrix.add(key)
            report['runs'].append(dict(output=str(out.resolve()), feature_level=level, profile=profile,
                                       scenario=scenario, frames=observed['reconstruction']['joined_scenario_frames'],
                                       captures=len(replay['captures']), primitives=observed.get('primitives'),
                                       costs=replay.get('costs')))
            # Unmodified real observations must reject the opposite platform claim.
            opposite = 'sm5' if level == 'sm6' else 'sm6'
            try:
                verify(out, opposite, profile)
            except AssertionError as error:
                report['controls'].append(dict(output=str(out.resolve()), claimed_level=opposite,
                                               result='EXPECTED_REJECTION', diagnostic=str(error)))
            else:
                raise AssertionError('Opposite platform claim accepted')
        required = {(level, profile, 'surfaces') for level in ('sm5', 'sm6') for profile in ('ProductionTSR', 'NativeTAA')}
        required |= {('sm6', 'ProductionTSR', 'environment'), ('sm5', 'NativeTAA', 'environment')}
        assert matrix == required, 'Incomplete shader-platform/profile matrix'
        by_path = {entry['path']: entry for entry in reference}
        assert all(by_path.get(entry['path']) == entry for entry in build_inputs), 'Runtime differs from native build source'
        assert by_path.get(build['module']['path']) == build['module'], 'Runtime module differs from build'
        for entry in reference:
            assert file_identity(Path(entry['path'])) == entry, f'Current input drift: {entry["path"]}'
        report.update(result='PASS', current_inputs=len(reference), build_inputs=len(build_inputs),
                      total_frames=sum(run['frames'] for run in report['runs']),
                      total_captures=sum(run['captures'] for run in report['runs']),
                      scope='One Linux Vulkan Development editor build, native runtime; no SM6 package or cold-cache qualification')
    except (AssertionError, OSError, ValueError, KeyError) as error:
        report['error'] = str(error)
    write_json(args.output, report)
    with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
        for item in report['controls']:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                        type='validation_negative_control', status=item['result'],
                                        diagnostics=item['diagnostic'], evidence=item['output']))+'\n')
        if report['result'] == 'FAIL':
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                        type='shader_series_validation', status='CONTINUE',
                                        diagnostics=report['error'], evidence=str(args.output.resolve())))+'\n')
    print(json.dumps({key: report[key] for key in ('result', 'total_frames', 'total_captures', 'error') if key in report}))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
