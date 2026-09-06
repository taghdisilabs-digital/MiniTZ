#!/usr/bin/env python3
"""Verify the bounded native engine-preloader increment, not full startup readiness."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from run_d01_039 import PROJECT, file_identity, write_json


def verify():
    root = PROJECT/'Build/Presentation'
    checked = {}

    def check(entry):
        if entry['path'] not in checked:
            assert file_identity(Path(entry['path'])) == entry, entry['path']
            checked[entry['path']] = entry
        else:
            assert checked[entry['path']] == entry, entry['path']

    def read(relative):
        path = root/relative
        check(file_identity(path))
        return json.loads(path.read_text())

    build = read('loading-build-03/result.json')
    assert build['result'] == 'PASS' and build['inputs_unchanged']
    check(build['binary'])
    check(build['receipt'])
    source = read('loading-build-03/inputs-after.json')
    assert source == read('loading-build-03/inputs-before.json')
    assert {x['path'] for x in source} == {str(f) for f in (PROJECT/'Source').rglob('*') if f.is_file()}
    for entry in source:
        check(entry)
    stage = read('loading-stage-05/validation.json')
    assert stage['result'] == 'PASS'
    for key in ('build', 'descriptor', 'archive', 'base_archive', 'repacked_pak'):
        check(stage[key])
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
    base_pak, candidate_pak = stage['base_pak_members'], stage['pak_readback_members']
    assert base_pak.keys() == candidate_pak.keys()
    assert [k for k in base_pak if (base_pak[k]['sha256'], base_pak[k]['bytes']) !=
            (candidate_pak[k]['sha256'], candidate_pak[k]['bytes'])] == stage['changed_pak_members']
    runs = []
    raw = {}
    cases = [('cold-05', 'cold', 'ProductionTSR', 'surfaces', 'enabled'),
             ('warm-01', 'warm', 'ProductionTSR', 'surfaces', 'enabled'),
             ('disabled-01', 'cold', 'ProductionTSR', 'surfaces', 'disabled'),
             ('sm5-01', 'cold', 'NativeTAA', 'surfaces', 'enabled'),
             ('environment-01', 'cold', 'ProductionTSR', 'environment', 'enabled')]
    for name, phase, profile, scenario, enabled in cases:
        folder = root/f'loading-runtime-{name}'
        data = read(f'{folder.name}/validation.json')
        raw[name] = data
        assert data['result'] == 'PASS', folder
        assert (data['phase'], data['profile'], data['scenario'], data['loading_screen']) == (phase, profile, scenario, enabled)
        assert data['archive'] == stage['archive']
        assert data['package_before'] == data['package_after'] == stage['readback_members']
        assert data['inputs_before'] == data['inputs_after']
        for entry in data['inputs_after']:
            # Cold05's original decoded classifier was tightened after visual
            # review. Its unchanged runtime is revalidated in a separate receipt.
            if name == 'cold-05' and Path(entry['path']).name == 'verify_d03_01_loading_display.py':
                continue
            check(entry)
        display = read(f'{folder.name}/loading-display-analysis-v2.json')
        assert display['schema'] == 'biella.loading_display/v2'
        assert display['world_frames'], 'No scene candidate'
        if enabled == 'enabled':
            assert data['loading']['pending_at_stop'] == 0
            assert display['loading_frames'] and display['indicator_samples']
        else:
            assert not display['loading_frames'] and 'loading' not in data
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                check(file_identity(path))
        runs.append(dict(name=name, frames=data['verification']['frames'],
                         loading=data.get('loading'), captured_frames=display['frames'],
                         first_scene_seconds=display['world_frames'][0]/10,
                         trailing_static_loading_seconds=display['trailing_static_loading_seconds'],
                         last_loading_to_scene_seconds=(display['world_frames'][0]-display['loading_frames'][-1])/10
                         if display['loading_frames'] else None))
    assert raw['cold-05']['state'] == raw['warm-01']['state']
    assert raw['cold-05']['state_after'] == raw['warm-01']['state_before']
    for name, data in raw.items():
        if data['phase'] == 'cold':
            assert not data['state_before'], name
    review = read('loading-cold05-display-revalidation-01.json')
    assert review['result'] == 'PASS' and review['hud_only_frame_rejected'] == 48
    assert review['scene_frame_accepted'] == 60
    reject = read('loading-static-marquee-rejection-01.json')
    assert reject['expected_rejection'] and 'No distinct activity segment' in reject['diagnostics']
    return dict(task_id='D03-01', result='PASS', task_status='CONTINUE',
                scope='Engine-preload lifecycle, moving indicator, runtime regression and exact candidate bytes; full startup readiness remains OPEN',
                archive=stage['archive'], runs=runs, checked_identities=list(checked.values()),
                time=datetime.now(timezone.utc).isoformat())


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
                                        type='loading_series_validation', status='CONTINUE', diagnostics=str(error)))+'\n')
    write_json(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if k != 'checked_identities'}))
    raise SystemExit(0 if report['result'] == 'PASS' else 1)
