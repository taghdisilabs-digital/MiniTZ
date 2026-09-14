#!/usr/bin/env python3
"""Verify the ground increment from matched native renders and exact source lineage."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image
from run_d01_039 import PROJECT, file_identity, write_json


def read(path):
    return json.loads(path.read_text())


def current(records):
    for record in records:
        assert file_identity(Path(record['path'])) == record, record['path']


def verify(root):
    names = ['ground-tsr-01', 'ground-taa-01', 'ground-hidden-01', 'ground-environment-01']
    reports = {name: read(root/name/'validation.json') for name in names}
    baseline = reports[names[0]]['identities_before']
    current(baseline)
    ground_fields = ('no_collision', 'no_navigation', 'rays_ignore_ground', 'existing_floor_collision')
    inputs = []
    for name, report in reports.items():
        folder = root/name
        hidden = name == 'ground-hidden-01'
        assert report['result'] == ('FAIL' if hidden else 'PASS')
        assert report.get('error') == ('Ground runtime invariants failed' if hidden else None)
        assert report['identities_before'] == report['identities_after'] == baseline
        runtime = report['runtime']
        assert runtime['returncode'] == 0 and not runtime['timed_out'] and runtime['log_finalization']['closed']
        current([runtime['log']])
        native = read(folder/'result.json')
        assert native['success'] and native['rhi'] == 'Vulkan' and not native['error']
        assert not native['fixed_timestep'] and not native['benchmark']
        inputs += [file_identity(folder/'validation.json'), file_identity(folder/'result.json')]
        if name != 'ground-environment-01':
            ground = read(folder/'ground.json')
            assert ground['count'] == 1 and all(ground[key] is True for key in ground_fields)
            assert ground['visible'] is (not hidden)
            assert ground['material'] == '/Game/OpenWorld/Materials/MI_GroundSupport.MI_GroundSupport'
            assert ground['center_cm'] == [10000, 0, -58] and ground['extent_cm'] == [60000, 50000, 50]
            inputs.append(file_identity(folder/'ground.json'))
            assert len(report['verification']['captures']) == 43
            for capture in report['verification']['captures']:
                identity = file_identity(folder/'captures'/f"{capture['name']}.png")
                assert identity['sha256'] == capture['sha256'] and identity['bytes'] == capture['bytes']

    build = read(root/'ground-build-04/validation.json')
    assert build['result'] == 'PASS' and build['returncode'] == 0 and build['inputs_before'] == build['inputs_after']
    current(build['inputs_after'] + build['binaries'])
    runtime_map = {r['path']: r for r in baseline}
    # Authoring/verifier scripts and standalone game outputs are not editor-loaded inputs.
    native_source = [r for r in build['inputs_after'] if '/Source/' in r['path']]
    loaded_binaries = [r for r in build['binaries'] if Path(r['path']).suffix == '.so' and r['path'] in runtime_map]
    build_only_binaries = [r for r in build['binaries'] if Path(r['path']).suffix == '.so' and r['path'] not in runtime_map]
    assert native_source and loaded_binaries
    assert all(runtime_map[r['path']] == r for r in native_source + loaded_binaries)
    assert [Path(r['path']).name for r in build_only_binaries] == ['libUnrealEditor-BiellaLoadingScreen.so']
    for name in names:
        log = (root/name/'runtime.stdout.log').read_text()
        assert "InternalLoadLibrary: 'BiellaLoadingScreen'" in log and 'D03_LOADING_REGISTERED version=1' in log
    readback = read(root/'ground-readback-02/validation.json')
    assert readback['result'] == 'PASS' and readback['before'] == readback['after']
    current(list(readback['after'].values()))
    from verify_d03_01_ground_map import verify as verify_map
    audit = verify_map(root/'ground-map-audit-01', root/'ground-author-01')
    inputs += [file_identity(root/'ground-build-04/validation.json'),
               file_identity(root/'ground-readback-02/validation.json'),
               file_identity(root/'ground-map-audit-01/verification.json')]

    poses = {}
    for name in names[:3]:
        folder = root/name
        frames = {int(r['frame']): r for r in csv.DictReader((folder/'frames.csv').open())}
        shots = list(csv.DictReader((folder/'captures.csv').open()))
        poses[name] = {r['name']: [float(frames[int(r['frame'])][k]) for k in ('x', 'y', 'z', 'yaw')]
                       for r in shots if r['name'].startswith('static_')}
        assert len(poses[name]) == 10
        inputs += [file_identity(folder/'frames.csv'), file_identity(folder/'captures.csv')]
    assert poses[names[0]] == poses[names[1]] == poses[names[2]], 'Static camera poses differ'

    # Small world-only rectangles, chosen after direct review of static_009.
    # Tests cover these margins, not the distant horizon or entire scene.
    regions = {'left_margin': [10, 282, 130, 316], 'far_margin': [840, 169, 930, 179]}
    metrics = []
    for index in range(10):
        capture = f'static_{index:03d}'
        arrays = {}
        for name in names[:3]:
            path = root/name/'captures'/f'{capture}.png'
            with Image.open(path) as im:
                assert im.size == (1280, 720)
                arrays[name] = np.asarray(im.convert('RGB'), dtype=np.float32)
            inputs.append(file_identity(path))
        hidden = arrays[names[2]]
        for name in names[:2]:
            visible = arrays[name]
            street_mad = float(np.abs(visible[420:560, 700:900] - hidden[420:560, 700:900]).mean())
            assert street_mad < 2, 'Existing street changed substantially'
            for label, (x1, y1, x2, y2) in regions.items():
                a, b = visible[y1:y2, x1:x2], hidden[y1:y2, x1:x2]
                black_visible = float((a.max(axis=2) <= 5).mean())
                black_hidden = float((b.max(axis=2) <= 5).mean())
                gain = float(a.mean() - b.mean())
                assert black_hidden > .90 and black_visible < .01 and gain > 30, (name, capture, label)
                metrics.append(dict(run=name, capture=capture, region=label, black_fraction_hidden=black_hidden,
                                    black_fraction_visible=black_visible, mean_rgb_gain_255=gain, street_mad_255=street_mad))
    return dict(task_id='D03-01', result='PASS', capture_status='GENERATED_DRAFT', inputs=inputs,
                native_source_files=len(native_source), loaded_editor_binaries=len(loaded_binaries),
                build_and_current_only_binaries=build_only_binaries,
                matched_static_poses=10, regions_xyxy=regions, unchanged_street_region_xyxy=[700,420,900,560],
                pixel_checks=metrics, map_audit=audit,
                negative_control='Hidden ground: expected native visibility assertion consumed, process exits 0; external ground gate rejects solely visibility. Matched images reproduce black margins.',
                costs={n:reports[n]['verification']['costs'] for n in names[:3]},
                environment=reports[names[3]]['verification'],
                limitations=['Two margin regions at one fixed camera; finite ground edge remains visible at the distant horizon.',
                             'Loading module exact bytes verified at build and now, and runtime loading confirmed in logs; older runtime harness did not hash that module before/after each run.',
                             'Existing DDC/editor Development Vulkan, 1280x720, native variable timing, no generated frames. Not a cold cook/package or performance qualification.',
                             'Gross stability and direct visual inspection do not establish fine temporal quality or final art acceptance.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--visual-output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists() and not args.visual_output.exists(), 'Use fresh outputs'
    try:
        report = verify(PROJECT/'Build/Presentation')
        args.visual_output.mkdir(parents=True)
        copies = []
        for name in ['ground-tsr-01', 'ground-taa-01', 'ground-hidden-01']:
            for shot in ['static_009', 'pan_015', 'walk_end']:
                source = PROJECT/'Build/Presentation'/name/'captures'/f'{shot}.png'
                target = args.visual_output/f'{name}-{shot}.png'
                shutil.copyfile(source, target)
                a, b = file_identity(source), file_identity(target)
                assert a['sha256'] == b['sha256'] and a['bytes'] == b['bytes']
                copies.append(dict(source=a, canonical_local=b))
        manifest = args.visual_output/'manifest.json'
        write_json(manifest, dict(task_id='D03-01', status='GENERATED_DRAFT', copies=copies,
                                 publication='Auto Feeder owns GitHub/Drive publication; no remote publication claimed.'))
        report['canonical_visual_manifest'] = file_identity(manifest)
        report['verifier'] = file_identity(Path(__file__))
        write_json(args.output, report)
        print(json.dumps(dict(result='PASS', matched_static_poses=10, pixel_checks=len(report['pixel_checks']), canonical_captures=len(copies))))
    except (AssertionError, OSError, ValueError, KeyError) as error:
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                        type='ground_verification', status='CONTINUE', diagnostics=str(error)))+'\n')
        raise


if __name__ == '__main__':
    main()
