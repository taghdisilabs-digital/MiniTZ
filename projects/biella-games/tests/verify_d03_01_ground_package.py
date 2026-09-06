#!/usr/bin/env python3
"""Read back the ground package lineage and compare matched native ground controls."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image
from run_d01_039 import PROJECT, file_identity, write_json
from run_d03_01_package import members


def verify(args):
    checked = {}

    def check(item):
        assert file_identity(Path(item['path'])) == item, f'Identity changed: {item["path"]}'
        checked[item['path']] = item

    def read(path):
        check(file_identity(path))
        return json.loads(path.read_text())

    build = read(args.game_build/'result.json')
    source = read(args.game_build/'inputs-after.json')
    assert build['result'] == 'PASS' and build['returncode'] == 0 and build['inputs_unchanged']
    assert source == read(args.game_build/'inputs-before.json')
    assert source == [file_identity(p) for p in sorted((PROJECT/'Source').rglob('*')) if p.is_file()]
    for item in source + [build['binary'], build['receipt']]:
        check(item)
    stage = read(args.stage/'validation.json')
    assert stage['result'] == 'PASS' and stage['returncode'] == 0
    check(stage['cook'])
    cook = read(Path(stage['cook']['path']))
    assert cook['result'] == 'PASS' and cook['returncode'] == 0 and cook['cache_before'] == []
    repair = read(args.cook_config_repair/'validation.json')
    assert repair['result'] == 'PASS' and repair['cook'] == stage['cook']
    assert repair['generated_token_value_recorded'] is False
    assert repair['appended_section'] == '/Script/AndroidFileServerEditor.AndroidFileServerRuntimeSettings'
    assert repair['after'] in cook['snapshot_inputs']
    assert (repair['before']['sha256'], repair['before']['bytes']) == (
        repair['private_backup']['sha256'], repair['private_backup']['bytes'])
    for item in (repair['after'], repair['private_backup'], repair['engine_source']):
        check(item)
    assert cook['inputs_before'] == cook['inputs_after']
    assert [i for i in cook['inputs_after'] if '/Source/' in i['path']] == source
    for key in ('inputs_after', 'snapshot_inputs', 'snapshot_binaries', 'cooked_files', 'editor_modules'):
        for item in cook[key]:
            check(item)
    editor = read(Path(cook['editor_build']['path']))
    check(cook['editor_build'])
    check(cook['editor'])
    assert editor['result'] == 'PASS' and editor['returncode'] == 0
    assert editor['inputs_before'] == editor['inputs_after']
    assert [i for i in editor['inputs_after'] if '/Source/' in i['path']] == source
    assert {i['path']: i for i in cook['editor_modules']} == {
        i['path']: i for i in editor['binaries'] if Path(i['path']).suffix == '.so'}
    original = {str(Path(i['path']).relative_to(PROJECT)): (i['sha256'], i['bytes']) for i in cook['inputs_after']}
    copied = {str(Path(i['path']).relative_to(cook['snapshot'])): (i['sha256'], i['bytes']) for i in cook['snapshot_inputs']}
    assert original == copied, 'Cook snapshot differs from canonical project'
    check(stage['dependencies'])
    dependency = read(Path(stage['dependencies']['path']))
    assert dependency['result'] == 'PASS'
    for item in dependency['licenses']:
        check(item)
    check(stage['archive'])
    assert members(Path(stage['archive_readback'])) == stage['readback_members']
    for item in stage['members'] + stage['readback_members']:
        check(item)
    staged = [(str(Path(i['path']).relative_to(stage['destination'])), i['sha256'], i['bytes']) for i in stage['members']]
    extracted = [(str(Path(i['path']).relative_to(stage['archive_readback'])), i['sha256'], i['bytes']) for i in stage['readback_members']]
    assert staged == extracted
    binary = next(i for i in stage['readback_members'] if i['path'].endswith('/Binaries/Linux/BiellaGames'))
    assert (binary['sha256'], binary['bytes']) == (build['binary']['sha256'], build['binary']['bytes'])

    paths = dict(tsr=args.tsr, taa=args.taa, hidden=args.hidden, environment=args.environment)
    reports, poses = {}, {}
    for name, path in paths.items():
        run = read(path/'validation.json')
        reports[name] = run
        hidden = name == 'hidden'
        assert run['result'] == ('FAIL' if hidden else 'PASS'), name
        assert run.get('error') == ('Ground runtime invariants failed' if hidden else None), name
        assert run['stage'] == file_identity(args.stage/'validation.json') and run['archive'] == stage['archive']
        assert run['package_before'] == run['package_after'] == stage['readback_members']
        assert run['inputs_before'] == run['inputs_after']
        for item in run['inputs_after'] + [run['runtime']['log']]:
            check(item)
        assert run['runtime']['returncode'] == 0 and not run['runtime']['timed_out']
        assert run['phase'] == 'cold' and run['trace'] is False
        assert run['state_before'] == [], 'Cold user state contains files'
        expected_profile = 'NativeTAA' if name == 'taa' else 'ProductionTSR'
        assert run['profile'] == expected_profile
        assert run['feature_level_expected'] == ('sm5' if name == 'taa' else 'sm6')
        assert run['feature_level_request'] == run['feature_level_expected']
        assert run['shader_platform']['result'] == 'PASS'
        probe = read(path/'isolation-probe.json')
        assert not any(probe['hidden_path_exists'].values())
        assert not probe['package_writable'] and probe['state_writable']
        for filename in ('runtime.engine.log', 'command.json', 'native-views.csv', 'frames.csv'):
            check(file_identity(path/filename))
        native = read(path/'result.json')
        assert native['success'] and native['rhi'] == 'Vulkan' and not native['error']
        assert not native['fixed_timestep'] and not native['benchmark']
        if name == 'environment':
            assert run['scenario'] == 'environment'
            from verify_d02_04 import verify as verify_environment
            assert verify_environment(path) == run['verification']
            check(file_identity(path/'events.log'))
            for capture in run['verification']['captures']:
                check(file_identity(Path(capture)))
            continue
        assert run['scenario'] == 'surfaces' and run['ground_control'] == ('hidden' if hidden else 'visible')
        ground = read(path/'ground.json')
        assert ground == run['ground'] and ground['count'] == 1 and ground['visible'] is (not hidden)
        assert all(ground[k] is True for k in ('no_collision', 'no_navigation', 'rays_ignore_ground', 'existing_floor_collision'))
        assert ground['material'] == '/Game/OpenWorld/Materials/MI_GroundSupport.MI_GroundSupport'
        assert ground['center_cm'] == [10000, 0, -58] and ground['extent_cm'] == [60000, 50000, 50]
        assert len(run['verification']['captures']) == 43
        for shot in run['verification']['captures']:
            item = file_identity(path/'captures'/f"{shot['name']}.png")
            assert (item['sha256'], item['bytes']) == (shot['sha256'], shot['bytes'])
            check(item)
        check(file_identity(path/'frames.csv'))
        check(file_identity(path/'captures.csv'))
        with (path/'frames.csv').open() as stream:
            frames = {int(r['frame']): r for r in csv.DictReader(stream)}
        with (path/'captures.csv').open() as stream:
            poses[name] = {r['name']: [float(frames[int(r['frame'])][k]) for k in ('x', 'y', 'z', 'yaw')]
                           for r in csv.DictReader(stream) if r['name'].startswith('static_')}
        assert len(poses[name]) == 10
    assert len({r['state'] for r in reports.values()}) == 4, 'Cold runs must use independent new state'
    assert poses['tsr'] == poses['taa'] == poses['hidden'], 'Static camera poses differ'

    # Reuse the two world-only margin regions already established by editor review.
    regions = dict(left_margin=[10, 282, 130, 316], far_margin=[840, 169, 930, 179])
    metrics = []
    for index in range(10):
        shot = f'static_{index:03d}'
        arrays = {}
        for name in ('tsr', 'taa', 'hidden'):
            with Image.open(paths[name]/'captures'/f'{shot}.png') as im:
                assert im.size == (1280, 720)
                arrays[name] = np.asarray(im.convert('RGB'), dtype=np.float32)
        hidden = arrays['hidden']
        for name in ('tsr', 'taa'):
            visible = arrays[name]
            street_mad = float(np.abs(visible[420:560, 700:900] - hidden[420:560, 700:900]).mean())
            assert street_mad < 2, (name, shot, 'Existing street changed substantially')
            for region, (x1, y1, x2, y2) in regions.items():
                a, b = visible[y1:y2, x1:x2], hidden[y1:y2, x1:x2]
                black_a, black_b = float((a.max(axis=2) <= 5).mean()), float((b.max(axis=2) <= 5).mean())
                gain = float(a.mean() - b.mean())
                assert black_b > .90 and black_a < .01 and gain > 30, (name, shot, region)
                metrics.append(dict(run=name, capture=shot, region=region, black_visible=black_a,
                                    black_hidden=black_b, mean_rgb_gain_255=gain, street_mad_255=street_mad))
    return dict(task_id='D03-01', result='PASS', status='GENERATED_DRAFT', archive=stage['archive'],
                source_files=len(source), editor_modules=cook['editor_modules'], native_binary=binary,
                archive_members=len(extracted), matched_static_poses=10, pixel_checks=metrics,
                costs={n: reports[n]['verification']['costs'] for n in ('tsr', 'taa')},
                runtime_receipts={n: file_identity(p/'validation.json') for n, p in paths.items()},
                identities=sorted(checked.values(), key=lambda i: i['path']),
                limitations=['Linux Development Vulkan at 1280x720, native variable timing, no generated frames; one workstation.',
                             'Fresh cook DDC and task-isolated runtime caches; OS page cache is not flushed.',
                             'Two ground margin regions at matched static poses; finite distant horizon and sparse world art remain.',
                             'Does not establish fine temporal quality, acceptable startup motion, final frame-time budget, or D03 completion.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output', 'stage', 'game-build', 'cook-config-repair', 'tsr', 'taa', 'hidden', 'environment', 'visual-output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for key, value in vars(args).items():
        setattr(args, key, value.resolve())
    assert not args.output.exists(), 'Preserve previous verification'
    try:
        report = verify(args)
        assert not args.visual_output.exists(), 'Preserve previous visual evidence'
        args.visual_output.mkdir(parents=True)
        copies = []
        for name in ('tsr', 'taa', 'hidden', 'environment'):
            path = getattr(args, name)
            shots = ('hazard_active', 'stream_return') if name == 'environment' else ('static_009', 'pan_015', 'walk_end')
            for shot in shots:
                source = path/'captures'/f'{shot}.png'
                target = args.visual_output/f'ground-package-{name}-{shot}.png'
                shutil.copyfile(source, target)
                original, canonical = file_identity(source), file_identity(target)
                assert (original['sha256'], original['bytes']) == (canonical['sha256'], canonical['bytes'])
                copies.append(dict(source=original, canonical_local=canonical))
        manifest = args.visual_output/'manifest.json'
        write_json(manifest, dict(task_id='D03-01', status='GENERATED_DRAFT', copies=copies,
                                 publication='Auto Feeder owns GitHub/Drive publication; no remote publication claimed.'))
        report['canonical_visual_manifest'] = file_identity(manifest)
    except (AssertionError, KeyError, OSError, ValueError) as error:
        report = dict(task_id='D03-01', result='FAIL', error=str(error))
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                        type='ground_package_verification', status='CONTINUE',
                                        diagnostics=str(error), evidence=str(args.output)))+'\n')
    report['input'] = file_identity(Path(__file__).resolve())
    write_json(args.output, report)
    print(json.dumps(dict(result=report['result'], error=report.get('error'), output=str(args.output))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
