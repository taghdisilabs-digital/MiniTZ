#!/usr/bin/env python3
"""Verify the one-variable native PSO scheduling comparison and timing boundaries."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import re

from run_d01_039 import PROJECT, file_identity, write_json
from run_d02_01 import reject_material_fallbacks, runtime_has_task_error
from run_d03_01_package import members
from verify_d03_01_pso_capture import (
    STAMP, measurements, normalized_command, stamp, verify_architecture,
    verify_platform, verify_surfaces, verify_views,
)


RUNS = {'pso-scheduling-legacy-cold-01': 0, 'pso-scheduling-pool-cold-01': 1}
SETTING = 'r.ShaderPipelineCache.UsePrecachingThreadPool'


def callback_timings(log):
    """Report observed boundaries; the last interval includes waits/merge, not just driver work."""
    patterns = {
        'callback': r'LogVulkanRHI: FVulkanPipelineStateCacheManager::OnShaderPipelineCachePrecompilationComplete',
        'saved': r'LogVulkanRHI: Display: FVulkanPipelineStateCacheManager: Saved device pipeline cache file',
        'finished': r'LogRHI: FShaderPipelineCache::BeginNextPrecompileCacheTask\(\) - Finished, no jobs remaining\.',
    }
    events = {}
    for name, pattern in patterns.items():
        found = re.findall(STAMP + r'.*' + pattern, log)
        assert len(found) == 1, f'Expected one native {name} boundary'
        events[name] = found[0]
    start, saved, finished = (stamp(events[k]) for k in ('callback', 'saved', 'finished'))
    assert start <= saved <= finished
    return dict(timestamps=events, callback_to_saved_seconds=(saved-start).total_seconds(),
                saved_to_finished_seconds=(finished-saved).total_seconds(),
                callback_to_finished_seconds=(finished-start).total_seconds(),
                scope='Observed wall intervals, not isolated driver/lock costs; do not sum worker creation durations.')


def verify(root):
    checked, results, commands = {}, {}, {}

    def check(item):
        assert file_identity(Path(item['path'])) == item, f'Identity changed: {item["path"]}'
        checked[item['path']] = item
        return item

    def read(path):
        check(file_identity(path))
        return json.loads(path.read_text())

    stage = read(root/'package-sm6-stage-01/validation.json')
    assert stage['result'] == 'PASS'
    check(stage['archive'])
    assert members(Path(stage['archive_readback'])) == stage['readback_members']
    for item in stage['readback_members']:
        check(item)
    build = read(root/'package-sm6-build-01/result.json')
    assert build['result'] == 'PASS' and build['inputs_unchanged']
    check(build['binary'])
    assert next(x for x in stage['readback_members'] if x['path'].endswith('/Binaries/Linux/BiellaGames'))['sha256'] == build['binary']['sha256']
    for item in read(root/'package-sm6-build-01/inputs-after.json'):
        check(item)

    predecessor = read(root/'pso-seeded-cold-03/validation.json')
    reference = normalized_command(read(root/'pso-seeded-cold-03/command.json'), predecessor, root/'pso-seeded-cold-03')
    seed = check(predecessor['seed']['source'])
    for name, pool in RUNS.items():
        out = root/name
        run = read(out/'validation.json')
        assert run['result'] == 'PASS' and run['scenario'] == 'surfaces' and run['precache_thread_pool'] == pool
        assert run['stage'] == file_identity(root/'package-sm6-stage-01/validation.json')
        assert run['archive'] == stage['archive']
        assert run['package_before'] == run['package_after'] == stage['readback_members']
        baseline = read(Path(run['baseline']['path']))
        check(run['baseline'])
        assert baseline['result'] == 'PASS' and run['inputs_before'] == run['inputs_after']
        assert run['inputs_before'][:-1] == baseline['inputs_after']
        for item in run['inputs_before'][:-1]:
            check(item)
        snapshot = check(file_identity(out/'runner.py'))
        assert all(snapshot[k] == run['inputs_before'][-1][k] for k in ('sha256', 'bytes'))
        assert run['state_before'] == [] and run['state_at_launch'] == [run['seed']['copied']]
        check(run['seed']['source'])
        assert all(seed[k] == run['seed']['source'][k] == run['seed']['copied'][k] for k in ('sha256', 'bytes'))
        assert run['seed']['copied']['path'] == run['state']+'/user/Saved/BiellaGames_SF_VULKAN_SM6.upipelinecache'
        for item in run['recordings']:
            check(item)
        probe = read(out/'isolation-probe.json')
        assert probe['uid'] == pwd.getpwnam('unreal').pw_uid and probe['network_interfaces'] == ['lo']
        assert not any(probe['hidden_path_exists'].values()) and not probe['package_writable'] and probe['state_writable']
        check(run['runtime']['log'])
        assert run['runtime']['returncode'] == 0 and not run['runtime']['timed_out']
        command = read(out/'command.json')
        assert command == run['runtime']['command']
        commands[name] = normalized_command(command, run, out)
        expected = [arg + f',{SETTING}={pool}' if arg.startswith('-DPCVars=') else arg for arg in reference]
        assert commands[name] == expected, 'Launch differs beyond the one scheduling setting'
        log = (out/'runtime.stdout.log').read_text()
        assert f'LogConfig: Set CVar [[{SETTING}:{pool}]]' in log
        assert 'Vulkan PSO Precaching = 1, PipelineFileCache = 1' in log
        assert re.search(r'Opened FPipelineCacheFile:.*BiellaGames_SF_VULKAN_SM6.upipelinecache', log)
        assert re.search(r'Result=\{Success\}.*Name=\{Surfaces\}', log)
        assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log and not runtime_has_task_error(log)
        reject_material_fallbacks(log)
        assert verify_views(out, 'ProductionTSR') == run['native_views']
        assert verify_platform(out, 'sm6', 'ProductionTSR') == run['shader_platform']
        assert verify_architecture(out, 'sm6') == run['architecture']
        actual = verify_surfaces(out, 4, 100)
        actual['scope'] = run['verification']['scope']
        assert actual == run['verification']
        results[name] = dict(pool=pool, frames=actual['frames'], captures=len(actual['captures']),
                             costs=actual['costs'], measurements=measurements(log, 'surfaces'),
                             callback=callback_timings(log))
        for path in sorted(out.rglob('*')):
            if path.is_file():
                check(file_identity(path))

    preservation = read(root/'pso-scheduling-recordings-01/preservation.json')
    assert {x['run'] for x in preservation['copies']} == set(RUNS)
    for item in preservation['copies']:
        check(item['source'])
        check(item['canonical'])
        assert all(item['source'][k] == item['canonical'][k] for k in ('sha256', 'bytes'))
    check(file_identity(Path(__file__).resolve()))
    return dict(task_id='D03-01', result='PASS', classification='GENERATED_DRAFT', runs=results,
                archive=stage['archive'], seed=seed, matched_variable=SETTING,
                checked_identities=list(checked.values()),
                scope='Native isolated scheduling experiment only. No game configuration change, production cache acceptance or remote publication. OS page cache not flushed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=PROJECT/'Build/Presentation')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve previous verification receipts'
    try:
        result = verify(args.root.resolve())
    except (AssertionError, OSError, KeyError, ValueError) as error:
        result = dict(task_id='D03-01', result='FAIL', error=str(error))
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                type='pso_scheduling_verification', status='CONTINUE', diagnostics=str(error), evidence=str(args.output)))+'\n')
    write_json(args.output, result)
    print(json.dumps(dict(result=result['result'], error=result.get('error'), checked=len(result.get('checked_identities', [])))))
    return 0 if result['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
