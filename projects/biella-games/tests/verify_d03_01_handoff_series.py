#!/usr/bin/env python3
"""Read back the bounded first-world handoff candidate and its runtime evidence.

This verifies exact source/package lineage and the sampled startup boundary.
It does not accept final art, continuous display readiness or D03 as a whole.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from run_d01_039 import PROJECT, file_identity, write_json
from verify_d03_01_handoff import check_display, verify as verify_handoff


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

    build = read('handoff-build-01/result.json')
    assert build['result'] == 'PASS' and build['inputs_unchanged']
    assert build['marker_before'] == build['marker_after']
    for key in ('binary', 'receipt'):
        check(build[key])
    source = read('handoff-build-01/inputs-after.json')
    assert source == read('handoff-build-01/inputs-before.json')
    assert {x['path'] for x in source} == {str(f) for f in (PROJECT/'Source').rglob('*') if f.is_file()}
    for entry in source:
        check(entry)

    stage = read('handoff-stage-01/validation.json')
    assert stage['result'] == 'PASS'
    for key in ('build', 'descriptor', 'archive', 'base_archive', 'repacked_pak'):
        check(stage[key])
    assert stage['build'] == file_identity(root/'handoff-build-01/result.json')
    assert stage['changed_members'] == ['Linux/BiellaGames/Binaries/Linux/BiellaGames',
                                        'Linux/BiellaGames/Content/Paks/BiellaGames-Linux.pak']
    assert stage['changed_pak_members'] == ['BiellaGames/BiellaGames.uproject']
    for key in ('reused_cook_inputs', 'readback_members'):
        for entry in stage[key]:
            check(entry)
    for key in ('base_pak_members', 'pak_readback_members'):
        assert len(stage[key]) == 1732
        for entry in stage[key].values():
            check(entry)
    before, after = stage['base_pak_members'], stage['pak_readback_members']
    assert before.keys() == after.keys()
    assert [k for k in before if (before[k]['sha256'], before[k]['bytes']) !=
            (after[k]['sha256'], after[k]['bytes'])] == stage['changed_pak_members']

    runs, raw = [], {}
    cases = [('cold-01', 'cold', 'ProductionTSR', 'surfaces', 'sm6', 'enabled'),
             ('warm-02', 'warm', 'ProductionTSR', 'surfaces', 'sm6', 'enabled'),
             ('disabled-01', 'cold', 'ProductionTSR', 'surfaces', 'sm6', 'disabled'),
             ('sm5-01', 'cold', 'NativeTAA', 'surfaces', 'sm5', 'enabled'),
             ('environment-01', 'cold', 'ProductionTSR', 'environment', 'sm6', 'enabled')]
    for name, phase, profile, scenario, feature, enabled in cases:
        folder = root/f'handoff-runtime-{name}'
        data = read(f'{folder.name}/validation.json')
        raw[name] = data
        assert data['result'] == 'PASS', folder
        assert (data['phase'], data['profile'], data['scenario'], data['feature_level_expected'],
                data['startup_handoff']) == (phase, profile, scenario, feature, enabled)
        assert data['loading_screen'] == 'enabled'
        assert data['archive'] == stage['archive']
        assert data['stage'] == file_identity(root/'handoff-stage-01/validation.json')
        assert data['package_before'] == data['package_after'] == stage['readback_members']
        assert data['inputs_before'] == data['inputs_after']
        for entry in data['inputs_after']:
            check(entry)
        assert data['runtime']['returncode'] == 0 and not data['runtime']['timed_out']
        if phase == 'cold':
            assert not data['state_before'], name
        display = read(f'{folder.name}/loading-display-analysis-v2.json')
        assert display['schema'] == 'biella.loading_display/v2'
        assert display['world_frames'] and display['loading_frames'] and display['indicator_samples']
        handoff = None
        if enabled == 'enabled':
            handoff = verify_handoff(folder)
            assert handoff == data['startup_handoff_verification']
        else:
            log = (folder/'runtime.engine.log').read_text(errors='replace')
            assert 'D03_HANDOFF_DISABLED version=1' in log
            assert 'D03_HANDOFF_START' not in log and 'D03_HANDOFF_END' not in log
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                check(file_identity(path))
        runs.append(dict(name=name, scenario_frames=data['verification']['frames'],
                         captured_frames=display['frames'], handoff=handoff,
                         first_loading_frame=min(display['loading_frames']),
                         last_loading_frame=max(display['loading_frames']),
                         first_scene_frame=min(display['world_frames']),
                         trailing_static_loading_seconds=display['trailing_static_loading_seconds']))

    recovery = read('handoff-warm-recovery-01.json')
    interrupted = read('handoff-runtime-warm-01/validation.json')
    assert interrupted['result'] != 'PASS' and 'state_after' not in interrupted
    assert recovery['returncode'] == 143 and recovery['process_match_count'] == 0
    assert recovery['cold_after_equals_interrupted_before']
    assert raw['cold-01']['state'] == interrupted['state'] == recovery['state'] == raw['warm-02']['state']
    assert raw['cold-01']['state_after'] == interrupted['state_before']
    assert recovery['state_at_recovery'] == raw['warm-02']['state_before']
    for entry in recovery['interrupted_evidence']:
        check(entry)
    # Cache snapshots are historical identities; a warm run may update them.
    # Verify the chain, not their equality to the final current cache bytes.
    negatives = []
    for report_name, runtime, expected in [
            ('handoff-negative-before-01.json', 'loading-runtime-cold-05', list(range(48, 57))),
            ('handoff-negative-disabled-01.json', 'handoff-runtime-disabled-01', list(range(50, 60)))]:
        report = read(report_name)
        assert report['result'] == 'FAIL'
        display = read(f'{runtime}/loading-display-analysis-v2.json')
        missing = sorted(set(range(min(display['loading_frames']), min(display['world_frames']))) -
                         set(display['loading_frames']))
        assert missing == expected
        try:
            check_display(display)
        except AssertionError as error:
            assert str(error) == report['error']
        else:
            raise AssertionError(f'Negative control accepted: {runtime}')
        negatives.append(dict(runtime=runtime, rejected_frames=missing))

    return dict(task_id='D03-01', result='PASS', task_status='CONTINUE',
                scope='Exact handoff build/package lineage and independent 10 Hz display/native scenarios; full production presentation remains OPEN',
                archive=stage['archive'], runs=runs, negatives=negatives,
                warm_recovery='cold-01 -> interrupted warm-01 -> preserved recovery snapshot -> warm-02',
                checked_identities=list(checked.values()), time=datetime.now(timezone.utc).isoformat())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve prior evidence'
    try:
        report = verify()
    except (AssertionError, OSError, KeyError, ValueError) as error:
        report = dict(task_id='D03-01', result='FAIL', error=str(error))
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                        type='handoff_series_validation', status='CONTINUE', diagnostics=str(error)))+'\n')
    write_json(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if k != 'checked_identities'}))
    raise SystemExit(0 if report['result'] == 'PASS' else 1)
