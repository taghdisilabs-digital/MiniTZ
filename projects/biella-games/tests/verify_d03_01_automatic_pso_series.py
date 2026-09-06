#!/usr/bin/env python3
"""Read back separate startup PSO telemetry and preserve the rejected wait trial.

PASS here qualifies telemetry, flag behavior and the existing packaged scenarios.
It does not mean that waiting for automatic PSOs fixes startup motion.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from run_d01_039 import PROJECT, file_identity, write_json
from verify_d03_01_automatic_pso import observe, verify as verify_wait
from verify_d03_01_handoff import verify as verify_handoff


def verify():
    root = PROJECT/'Build/Presentation'
    checked = {}

    def check(entry):
        path = entry['path']
        if path not in checked:
            assert file_identity(Path(path)) == entry, path
            checked[path] = entry
        else:
            assert checked[path] == entry, path

    def read(relative):
        path = root/relative
        check(file_identity(path))
        return json.loads(path.read_text())

    build = read('automatic-pso-build-02/result.json')
    assert build['result'] == 'PASS' and build['inputs_unchanged']
    assert build['marker_before'] == build['marker_after']
    for key in ('binary', 'receipt'):
        check(build[key])
    source = read('automatic-pso-build-02/inputs-after.json')
    assert source == read('automatic-pso-build-02/inputs-before.json')
    assert {x['path'] for x in source} == {str(f) for f in (PROJECT/'Source').rglob('*') if f.is_file()}
    for entry in source:
        check(entry)

    stages = {}
    for number in ('01', '02'):
        stage = read(f'automatic-pso-stage-{number}/validation.json')
        stages[number] = stage
        assert stage['result'] == 'PASS'
        assert stage['build'] == file_identity(root/f'automatic-pso-build-{number}/result.json')
        # Stage 01 is the preserved experiment. Its old live build output/source
        # were superseded; verify the immutable package and recorded source pair.
        old_build = read(f'automatic-pso-build-{number}/result.json')
        assert old_build['result'] == 'PASS' and old_build['inputs_unchanged']
        assert read(f'automatic-pso-build-{number}/inputs-before.json') == read(f'automatic-pso-build-{number}/inputs-after.json')
        for key in ('build', 'descriptor', 'archive', 'base_archive', 'repacked_pak'):
            check(stage[key])
        assert stage['changed_members'] == ['Linux/BiellaGames/Binaries/Linux/BiellaGames',
                                            'Linux/BiellaGames/Content/Paks/BiellaGames-Linux.pak']
        assert stage['changed_pak_members'] == ['BiellaGames/BiellaGames.uproject']
        for key in ('reused_cook_inputs', 'readback_members'):
            for entry in stage[key]:
                check(entry)
        binaries = [e for e in stage['readback_members'] if e['path'].endswith('/Binaries/Linux/BiellaGames')]
        assert len(binaries) == 1
        assert all(binaries[0][k] == old_build['binary'][k] for k in ('sha256', 'bytes'))
        for key in ('base_pak_members', 'pak_readback_members'):
            assert len(stage[key]) == 1732
            for entry in stage[key].values():
                check(entry)
        before, after = stage['base_pak_members'], stage['pak_readback_members']
        assert before.keys() == after.keys()
        assert [k for k in before if (before[k]['sha256'], before[k]['bytes']) !=
                (after[k]['sha256'], after[k]['bytes'])] == stage['changed_pak_members']

    cases = [
        ('default-01', '02', 'cold', 'ProductionTSR', 'surfaces', 'sm6', 'default', 0),
        ('warm-01', '02', 'warm', 'ProductionTSR', 'surfaces', 'sm6', 'default', 0),
        ('sm5-01', '02', 'cold', 'NativeTAA', 'surfaces', 'sm5', 'default', 0),
        ('environment-01', '02', 'cold', 'ProductionTSR', 'environment', 'sm6', 'default', 0),
        ('optin-01', '02', 'cold', 'ProductionTSR', 'surfaces', 'sm6', 'enabled', 1),
        ('cold-01', '01', 'cold', 'ProductionTSR', 'surfaces', 'sm6', 'enabled', 1),
        ('disabled-01', '01', 'cold', 'ProductionTSR', 'surfaces', 'sm6', 'disabled', 0),
    ]
    runs, raw = [], {}
    for name, number, phase, profile, scenario, feature, mode, wait in cases:
        folder = root/f'automatic-pso-runtime-{name}'
        data = read(f'{folder.name}/validation.json')
        raw[name] = data
        assert data['result'] == 'PASS', folder
        assert (data['phase'], data['profile'], data['scenario'], data['feature_level_expected'],
                data['automatic_pso_wait']) == (phase, profile, scenario, feature, mode)
        assert data['loading_screen'] == data['startup_handoff'] == 'enabled'
        stage = stages[number]
        assert data['archive'] == stage['archive']
        assert data['stage'] == file_identity(root/f'automatic-pso-stage-{number}/validation.json')
        assert data['package_before'] == data['package_after'] == stage['readback_members']
        assert data['inputs_before'] == data['inputs_after']
        if number == '02':
            for entry in data['inputs_after']:
                check(entry)
        assert data['runtime']['returncode'] == 0 and not data['runtime']['timed_out']
        if phase == 'cold':
            assert not data['state_before'], name
        command = read(f'{folder.name}/command.json')
        if number == '02':
            assert ('-BiellaWaitForAutomaticPSOs' in command) == (mode == 'enabled')
            assert '-BiellaSkipAutomaticPSOWait' not in command
        elif mode == 'disabled':
            assert '-BiellaSkipAutomaticPSOWait' in command
        observed = observe(folder)
        native = observed['native']
        assert all(len(native[k]) == 1 for k in ('start', 'stop', 'handoff'))
        start, stop, handoff = (native[k][0] for k in ('start', 'stop', 'handoff'))
        assert start[0] == stop[0] == handoff[0] == wait
        assert start[3:] == [1, 0, 0], 'Automatic precaching disabled or priority-filtered'
        assert stop[1] == handoff[1] == 0
        if wait:
            assert stop[2] == handoff[2] == 0, 'Opt-in released with observed automatic work'
        if phase == 'cold':
            assert max(start[2], observed['sampled_max_automatic']) > 0
        with (folder/'loading-render-ticks.csv').open() as stream:
            render_samples = list(csv.DictReader(stream))
        with (folder/'loading-pso-samples.csv').open() as stream:
            pipeline_samples = list(csv.DictReader(stream))
        assert len(render_samples) == len(pipeline_samples) == data['loading']['render_ticks'] >= 3
        for render, pipeline in zip(render_samples, pipeline_samples):
            assert all(render[k] == pipeline[k] for k in ('render_tick', 'elapsed_seconds'))
            assert int(pipeline['file_cache']) >= 0 and int(pipeline['automatic']) >= 0
        handoff_report = verify_handoff(folder)
        assert handoff_report == data['startup_handoff_verification']
        strict = verify_wait(folder, require_observed_work=phase == 'cold')
        # The separate strict gate is intentionally retained. A telemetry PASS
        # cannot promote a failed or bypassed full-wait/motion gate into success.
        motion = 'PASS' if not observed['unmeasured_loading_frames'] and observed['longest_static_seconds'] < 1 else 'FAIL'
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                check(file_identity(path))
        runs.append(dict(name=name, candidate=number, mode=mode,
                         loading=data['loading'], handoff=handoff_report,
                         observations=observed, strict_wait_and_motion=strict,
                         sampled_one_second_motion_gate=motion,
                         native_frames=data['verification']['frames'],
                         display_frames=read(f'{folder.name}/loading-display-analysis-v2.json')['frames']))
    assert raw['default-01']['state'] == raw['warm-01']['state']
    assert raw['default-01']['state_after'] == raw['warm-01']['state_before']
    trial, bypass = (next(r for r in runs if r['name'] == n) for n in ('cold-01', 'disabled-01'))
    assert trial['loading']['elapsed_seconds'] > bypass['loading']['elapsed_seconds'] + 20
    assert trial['sampled_one_second_motion_gate'] == bypass['sampled_one_second_motion_gate'] == 'FAIL'
    assert bypass['observations']['native']['stop'][0][2] > 0
    baseline = read('automatic-pso-negative-before-02.json')
    assert baseline['result'] == 'FAIL' and 'telemetry' in baseline['error']
    return dict(task_id='D03-01', result='PASS', task_status='CONTINUE',
                scope='Separate PSO counter telemetry, opt-in flag, exact build/package lineage and affected native scenarios; full automatic waiting rejected as production default',
                automatic_wait_default='disabled; explicit diagnostic opt-in only',
                continuous_motion='OPEN; >=1s observed static indicator remains',
                archive=stages['02']['archive'], runs=runs,
                warm_chain='default-01 state-after equals warm-01 state-before',
                checked_identities=list(checked.values()), time=datetime.now(timezone.utc).isoformat())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve evidence'
    try:
        report = verify()
    except (AssertionError, OSError, KeyError, ValueError) as error:
        report = dict(task_id='D03-01', result='FAIL', error=str(error))
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                        type='automatic_pso_series_validation', status='CONTINUE', diagnostics=str(error)))+'\n')
    write_json(args.output, report)
    print(json.dumps(dict(result=report['result'], error=report.get('error'),
                          checked_identities=len(report.get('checked_identities', [])), output=str(args.output))))
    raise SystemExit(0 if report['result'] == 'PASS' else 1)
