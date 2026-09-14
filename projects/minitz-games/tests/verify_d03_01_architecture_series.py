#!/usr/bin/env python3
"""Replay the bounded facade increment against raw native evidence and current bytes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from run_d01_039 import PROJECT, file_identity, write_json
from run_d02_01 import reject_material_fallbacks, runtime_has_task_error
from verify_d02_04 import verify as environment
from verify_d03_01_architecture import verify as architecture
from verify_d03_01_reconstruction import verify as reconstruction
from verify_d03_01_shader_platform import verify as platform
from verify_d03_01_surfaces import verify as surfaces


RUNS = (
    ('architecture-sm6-tsr-02', 'sm6', 'ProductionTSR', 'surfaces'),
    ('architecture-sm5-taa-01', 'sm5', 'NativeTAA', 'surfaces'),
    ('architecture-environment-sm6-01', 'sm6', 'ProductionTSR', 'environment'),
    ('architecture-environment-sm5-01', 'sm5', 'NativeTAA', 'environment'),
)


def read(path):
    return json.loads(path.read_text())


def unchanged(items):
    for item in items:
        assert file_identity(Path(item['path'])) == item, 'Changed file: ' + item['path']


def verify():
    root = PROJECT / 'Build/Presentation'
    common = None
    runs, controls = [], []
    for name, feature, profile, scenario in RUNS:
        out = root / name
        saved = read(out / 'validation.json')
        assert saved['result'] == 'PASS', name
        assert saved['profile'] == profile and saved['scenario'] == scenario
        assert saved['identities_before'] == saved['identities_after'], 'Runtime input mutation'
        if common is None:
            common = saved['identities_after']
            unchanged(common)
        assert common == saved['identities_after'], 'Different runtime lineage'
        runtime = saved['runtime']
        assert runtime['returncode'] == 0 and not runtime['timed_out']
        assert runtime['log_finalization']['closed']
        log = (out / 'runtime.stdout.log').read_text(errors='replace')
        assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log
        assert not runtime_has_task_error(log)
        reject_material_fallbacks(log)
        native = reconstruction(out, profile)
        shader = platform(out, feature, profile)
        replay = surfaces(out, 4 if profile == 'ProductionTSR' else 2, 100) if scenario == 'surfaces' else environment(out)
        assert replay == saved['verification'], 'Scenario replay differs'
        assert native == saved['native_views'] and shader == saved['shader_platform']
        meshes = architecture(out, feature) if scenario == 'surfaces' else None
        captures = [file_identity(p) for p in sorted((out / 'captures').glob('*.png'))]
        assert len(captures) == (43 if scenario == 'surfaces' else 5)
        runs.append(dict(name=name, feature_level=feature, profile=profile, scenario=scenario,
            validation=file_identity(out / 'validation.json'), frames=replay['frames'],
            captures=captures, measurements={k:v for k,v in replay.items() if k != 'captures'},
            native_views=native, shader_platform=shader, architecture=meshes,
            raw=[file_identity(out / n) for n in ('result.json', 'frames.csv', 'native-views.csv', 'runtime.stdout.log')]))
        opposite = 'sm5' if feature == 'sm6' else 'sm6'
        try:
            platform(out, opposite, profile)
        except AssertionError as error:
            assert 'Runtime capability mismatch: feature_sm6=' in str(error), str(error)
            controls.append(dict(run=name, claimed_feature_level=opposite,
                                 result='EXPECTED_REJECTION', diagnostic=str(error)))
        else:
            raise AssertionError('Opposite platform accepted: ' + name)

    build = read(root / 'architecture-build-lineage-01.json')
    assert build['result'] == 'PASS' and len(build['inputs']) == 90
    unchanged(build['inputs'])
    module = file_identity(PROJECT / 'Binaries/Linux/libUnrealEditor-BiellaGames.so')
    assert module in common
    assert module['sha256'] == '5354cd383cdf65e46c761e839e311d6003fa5a0a42cef82fb007e5055345b3a5'
    author = read(root / 'architecture-author-07/validation.json')
    hlod = read(root / 'architecture-hlod-02/validation.json')
    assert author['result'] == hlod['result'] == 'PASS'
    unchanged(author['sources'])
    unchanged(hlod['after'])
    unchanged(hlod['scripts'])
    authored = read(root / 'architecture-author-07/author.json')
    readback = read(root / 'architecture-author-07/readback.json')
    assert authored['meshes'] == readback['meshes'] and len(readback['meshes']) == 6
    for before, after in zip(authored['actors'], readback['actors']):
        assert before['label'] == after['label']
        assert before['before'] == before['after'] == after['before'] == after['after']
        assert before['mesh'] == after['mesh']
    world = read(root / 'architecture-hlod-02/world.json')
    assert world['result'] == 'PASS' and world['read_only']
    h = world['built_hlod_geometry']
    assert len(h) == 13 and sum(row['instances'] for row in h) == 58
    facade_hlods = sum(any('/MIC_Facade' in mat for mat in row['materials']) for row in h)
    assert facade_hlods == 6
    return dict(task_id='D03-01', result='PASS', time=datetime.now(timezone.utc).isoformat(),
        runs=runs, opposite_platform_controls=controls, runtime_input_count=len(common),
        unchanged_build_input_count=len(build['inputs']), current_content_assets=len(hlod['after']),
        native_module=module, authored_meshes=len(readback['meshes']), facade_hlods=facade_hlods,
        frames=sum(run['frames'] for run in runs), captures=sum(len(run['captures']) for run in runs),
        scope='Native Linux Vulkan Development editor, existing caches, same source/module/content. '
              'Representative facade integration and forced SM5 fallback; no cold package or final art acceptance.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve existing evidence; use a fresh output'
    try:
        report = verify()
    except (OSError, AssertionError, ValueError, KeyError) as error:
        report = dict(task_id='D03-01', result='FAIL', error=str(error))
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                type='architecture_series', status='CONTINUE', diagnostics=str(error), evidence=str(args.output)))+'\n')
    write_json(args.output, report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('runs', 'opposite_platform_controls')}))
    raise SystemExit(0 if report['result'] == 'PASS' else 1)
