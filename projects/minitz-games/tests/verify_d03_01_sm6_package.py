#!/usr/bin/env python3
"""Read back current SM6/default and explicit SM5 packaged-world qualification.

This is a D03 increment receipt, not acceptance of production stutter or final art.
Prior SM5 package receipts remain historical and are never rewritten here.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from run_d01_039 import PROJECT, file_identity, write_json
from run_d03_01_package import members
from verify_d03_01_shader_platform import verify as verify_platform
from verify_d03_01_architecture import verify as verify_architecture
from verify_d03_01_reconstruction import verify as verify_views


def verify(root):
    checked = {}

    def check(item):
        assert file_identity(Path(item['path'])) == item, f'Identity changed: {item["path"]}'
        checked[item['path']] = item

    def read(path):
        path = root/path
        check(file_identity(path))
        return json.loads(path.read_text())

    build = read('package-sm6-build-01/result.json')
    assert build['result'] == 'PASS' and build['inputs_unchanged'], 'Native build unqualified'
    sources = read('package-sm6-build-01/inputs-after.json')
    assert sources == read('package-sm6-build-01/inputs-before.json'), 'Build source changed'
    for item in sources + [build['binary'], build['receipt'], build['marker_after']]:
        check(item)
    cook = read('package-sm6-cook-01/validation.json')
    assert cook['result'] == 'PASS' and cook['cache_before'] == [], 'Cold cook unqualified'
    assert cook['inputs_before'] == cook['inputs_after'], 'Cook changed canonical inputs'
    for key in ('inputs_after', 'snapshot_inputs', 'snapshot_binaries', 'cooked_files'):
        for item in cook[key]:
            check(item)
    check(cook['editor'])
    check(cook['editor_module'])
    stage_path = root/'package-sm6-stage-01/validation.json'
    stage = read(stage_path)
    assert stage['result'] == 'PASS', 'Stage unqualified'
    assert stage['cook'] == file_identity(root/'package-sm6-cook-01/validation.json'), 'Cook/stage lineage differs'
    for item in [stage['cook'], stage['dependencies'], stage['archive']] + stage['members'] + stage['readback_members']:
        check(item)
    assert members(Path(stage['archive_readback'])) == stage['readback_members'], 'Archive extraction changed'
    binary = next(x for x in stage['readback_members'] if x['path'].endswith('/Binaries/Linux/BiellaGames'))
    assert binary['sha256'] == build['binary']['sha256'], 'Packaged binary differs from native build'
    snapshot_binary = next(x for x in cook['snapshot_binaries'] if x['path'].endswith('/BiellaGames'))
    assert snapshot_binary['sha256'] == binary['sha256'], 'Cook binary lineage differs'
    runs, negative_checks, tool_inputs = {}, [], None
    for level, short, profile in [('sm6', 'tsr', 'ProductionTSR'), ('sm5', 'fallback-taa', 'NativeTAA')]:
        previous = None
        for phase in ('cold', 'warm', 'environment'):
            name = f'package-{level}-{short}-{phase}-01'
            out = root/name
            run = read(out/'validation.json')
            assert run['result'] == 'PASS' and run['profile'] == profile, f'Unqualified {name}'
            assert run['feature_level_expected'] == level, 'Feature expectation differs'
            assert run['feature_level_request'] == (None if level == 'sm6' else 'sm5'), 'Default/forced selection differs'
            assert run['scenario'] == ('environment' if phase == 'environment' else 'surfaces'), 'Scenario differs'
            assert run['phase'] == ('cold' if phase == 'cold' else 'warm'), 'Cache phase differs'
            assert run['archive'] == stage['archive'] and run['stage'] == file_identity(stage_path), 'Archive lineage differs'
            assert run['package_before'] == run['package_after'] == stage['readback_members'], 'Runtime package changed'
            assert run['inputs_before'] == run['inputs_after'], 'Verification sources changed during run'
            if tool_inputs is None:
                tool_inputs = run['inputs_after']
            assert run['inputs_after'] == tool_inputs, 'Series verification sources differ'
            for item in tool_inputs:
                check(item)
            assert run['state_before'] == (previous['state_after'] if previous else []), 'Cold/warm cache continuity differs'
            probe = read(out/'isolation-probe.json')
            assert probe['network_interfaces'] == ['lo'] and not any(probe['hidden_path_exists'].values()), 'Host isolation not proven'
            assert not probe['package_writable'] and probe['state_writable'], 'Mount access differs'
            check(run['runtime']['log'])
            assert verify_views(out, profile) == run['native_views'], 'Native view/scenario join differs'
            assert verify_platform(out, level, profile) == run['shader_platform'], 'Native platform proof no longer reproduces'
            opposite = 'sm5' if level == 'sm6' else 'sm6'
            try:
                verify_platform(out, opposite, profile)
            except AssertionError as error:
                negative_checks.append(dict(run=name, control='opposite_native_feature_level', rejected=str(error)))
            else:
                raise AssertionError('Wrong native feature level accepted')
            if phase != 'environment':
                assert run['architecture_required'], 'Facade gate was not enabled'
                assert verify_architecture(out, level) == run['architecture'], 'Facade proof differs'
                from verify_d03_01_surfaces import verify as verify_scenario
                actual = verify_scenario(out, 4 if level == 'sm6' else 2, 100)
                actual['scope'] = run['verification']['scope']
            else:
                from verify_d02_04 import verify as verify_scenario
                actual = verify_scenario(out)
            assert actual == run['verification'], 'Scenario proof no longer reproduces'
            log = (out/'runtime.stdout.log').read_text()
            libraries = {name: int(count) for name, count in re.findall(
                r'Using IoDispatcher for shader code library (\w+). Total (\d+) unique shaders.', log)}
            assert libraries.get('Global', 0) > 0 and libraries.get('BiellaGames', 0) > 0, 'Packaged shader libraries missing'
            init = re.search(r'\(Engine Initialization\) Total time: ([\d.]+) seconds', log)
            assert init, 'Native initialization timing missing'
            hitches = run['pso_hitches']
            runs[name] = dict(receipt=file_identity(out/'validation.json'), feature_level=level, profile=profile,
                frames=actual['frames'], captures=len(actual['captures']),
                native_views=run['native_views']['joined_scenario_frames'], shader_libraries=libraries,
                engine_initialization_seconds=float(init[1]), pso_hitches_over_20ms=len(hitches),
                pso_max_creation_ms=max((x['milliseconds'] for x in hitches), default=0),
                pso_by_kind={kind: sum(x['kind'] == kind for x in hitches) for kind in ('graphics', 'compute')},
                driver_cache_files=[x for x in run['state_after'] if '/xdg-cache/' in x['path']],
                costs=actual.get('costs'), facade=run.get('architecture'),
                native_pso_observations=[line for line in run['pso_observations']
                    if 'Binary pipeline cache' in line or 'Vulkan PSO Precaching' in line])
            previous = run
    negative = read('package-sm6-missing-shader-01/validation.json')
    assert negative['result'] == 'PASS' and negative['feature_level'] == 'sm6', 'SM6 missing-cache control unqualified'
    assert negative['positive'] == runs['package-sm6-tsr-cold-01']['receipt'], 'Control positive lineage differs'
    assert negative['archive'] == negative['archive_after'] == stage['archive'], 'Control archive differs'
    assert negative['canonical_before'] == negative['canonical_after'] == stage['readback_members'], 'Control mutated canonical extraction'
    assert negative['failure_diagnostics'] and negative['runtime']['returncode'] != 0 and not negative['runtime']['timed_out'], 'Control rejection missing'
    for item in [negative['input'], negative['positive'], negative['runtime']['log']]:
        check(item)
    mutation = negative['mutation']
    for item in [mutation['original_pak'], mutation['mutated_pak'], mutation['withheld'], mutation['engine_source']] + mutation['logical_files_after']:
        check(item)
    workspace = Path(mutation['withheld']['path']).parent.parent
    before = {Path(x['path']).relative_to(workspace/'extracted').as_posix(): x for x in mutation['logical_files_before']}
    assert before.pop('Engine/GlobalShaderCache-VULKAN_SM6.bin')['sha256'] == mutation['withheld']['sha256'], 'Wrong cache withheld'
    after = {Path(x['path']).relative_to(workspace/'repacked-readback').as_posix(): x['sha256'] for x in mutation['logical_files_after']}
    assert {name: item['sha256'] for name, item in before.items()} == after, 'Other logical pak files changed'
    return dict(task_id='D03-01', result='PASS', input=file_identity(Path(__file__).resolve()),
        build_source_files=len(sources), canonical_cook_inputs=len(cook['inputs_after']),
        archive=stage['archive'], archive_members=len(stage['readback_members']), native_binary=binary,
        runs=runs, positive_frames=sum(x['frames'] for x in runs.values()),
        captures=sum(x['captures'] for x in runs.values()), negative_feature_checks=negative_checks,
        negative_preserved_logical_files=len(after), identities=sorted(checked.values(), key=lambda x: x['path']),
        scope='Linux Development Vulkan default SM6/TSR and forced SM5/TAA; same exact archive; isolated cold/warm user/driver caches; no generated frames',
        limitations=['PSO creation events may overlap and are not additive wall-frame stalls; functional PASS does not accept cold stutter.',
                     'OS page cache was not flushed. One host, no Shipping or cross-hardware qualification.',
                     'Gross pixel deltas do not establish fine temporal, ghosting or disocclusion quality.',
                     'SDL dummy audio; no new audible-mix qualification. Final art and complete D03 acceptance remain.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve earlier readbacks'
    try:
        result = verify(PROJECT/'Build/Presentation')
    except (AssertionError, OSError, ValueError, KeyError) as error:
        result = dict(task_id='D03-01', result='FAIL', error=str(error))
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                type='sm6_package_readback', status='CONTINUE', diagnostics=str(error), evidence=str(args.output)))+'\n')
    write_json(args.output, result)
    print(json.dumps({key: result.get(key) for key in ('result', 'positive_frames', 'captures', 'error')}))
    return 0 if result['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
