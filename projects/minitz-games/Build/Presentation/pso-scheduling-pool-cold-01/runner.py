#!/usr/bin/env python3
"""Measure a portable PSO recording in fresh driver state using the qualified archive.

This experiment does not modify the game or qualify production loading smoothness.
The only optional seed is one exact recorded PSO description file, never a driver cache.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import re
import shutil

from run_d01_039 import PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d01_048 import launch
from run_d02_01 import reject_material_fallbacks, runtime_has_task_error
from run_d03_01_package import members
from verify_d03_01_architecture import verify as verify_architecture
from verify_d03_01_reconstruction import verify as verify_views
from verify_d03_01_shader_platform import verify as verify_platform
from verify_d03_01_surfaces import verify as verify_surfaces
from verify_d02_04 import verify as verify_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, default=PROJECT/'Build/Presentation/package-sm6-tsr-cold-01')
    parser.add_argument('--seed', type=Path, help='Recorded SM6 PSO descriptions to load as a user cache')
    parser.add_argument('--file-cache-with-precaching', action='store_true', help='Enable the Vulkan compatibility gate at startup')
    parser.add_argument('--preserve-user-cache', action='store_true', help='Use logging CVars instead of -logpso, which deletes the user cache at startup')
    parser.add_argument('--precache-thread-pool', type=int, choices=(0, 1), help='Experimental bundled-cache scheduling override; omitted preserves the native default')
    args = parser.parse_args()
    out, state, baseline = args.output.resolve(), args.state.resolve(), args.baseline.resolve()
    assert not out.exists() and not state.exists(), 'Evidence and state must both be fresh'
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(out, account)
    shutil.copyfile(Path(__file__), out/'runner.py')
    ensure_runtime_output(state, account)
    for name in ('home', 'user', 'xdg-cache', 'xdg-config'):
        ensure_runtime_output(state/name, account)
    positive = json.loads((baseline/'validation.json').read_text())
    scenario = positive['scenario']
    assert scenario in ('surfaces', 'environment'), 'Unsupported qualified scenario'
    stage_path = Path(positive['stage']['path'])
    stage = json.loads(stage_path.read_text())
    extraction = Path(stage['archive_readback'])
    inputs = [Path(item['path']) for item in positive['inputs_after']] + [Path(__file__).resolve()]
    report = dict(task_id='D03-01', result='FAIL', revision=source_revision(), scenario=scenario,
                  baseline=file_identity(baseline/'validation.json'), stage=file_identity(stage_path),
                  archive=stage['archive'], state=str(state), state_before=members(state),
                  inputs_before=[file_identity(p) for p in inputs], capture_status='GENERATED_DRAFT',
                  scope='Same Linux Development SM6/TSR archive, fresh isolated user/driver caches; PSO descriptions only may be seeded. OS page cache not flushed; no production stutter acceptance.')
    write_json(out/'validation.json', report)
    try:
        assert positive['result'] == stage['result'] == 'PASS'
        assert report['stage'] == positive['stage']
        assert report['inputs_before'][:-1] == positive['inputs_after'], 'Qualified verifier inputs changed'
        assert positive['feature_level_expected'] == 'sm6' and positive['profile'] == 'ProductionTSR'
        assert file_identity(Path(stage['archive']['path'])) == stage['archive']
        report['package_before'] = members(extraction)
        assert report['package_before'] == stage['readback_members']
        if args.seed:
            seed = args.seed.resolve()
            assert seed.name.endswith('.rec.upipelinecache') and '_VULKAN_SM6_' in seed.name
            assert seed.stat().st_size > 64, 'Empty PSO seed'
            destination = state/'user/Saved/BiellaGames_SF_VULKAN_SM6.upipelinecache'
            ensure_runtime_output(destination.parent, account)
            shutil.copyfile(seed, destination)
            shutil.chown(destination, user=account.pw_uid, group=account.pw_gid)
            report['seed'] = dict(source=file_identity(seed), copied=file_identity(destination))
            assert report['seed']['source']['sha256'] == report['seed']['copied']['sha256']
        report['state_at_launch'] = members(state)
        assert len(report['state_at_launch']) == (1 if args.seed else 0), 'Unexpected driver/user seed'
        command_path = baseline/'command.json'
        command = json.loads(command_path.read_text())
        assert command == positive['runtime']['command'], 'Baseline command differs'
        report['baseline_command'] = file_identity(command_path)
        replacements = {positive['state']: str(state), positive['state']+'/home': str(state/'home'), str(baseline): str(out)}
        command = [replacements.get(arg, arg) for arg in command]
        command.append('-psocache')
        overrides = []
        if args.preserve_user_cache:
            overrides += ['r.ShaderPipelineCache.LogPSO=1', 'r.ShaderPipelineCache.SaveBoundPSOLog=1']
        else:
            command.append('-logpso')
        if args.file_cache_with_precaching:
            overrides.append('r.Vulkan.EnablePSOFileCacheWhenPrecachingActive=1')
        if args.precache_thread_pool is not None:
            overrides.append(f'r.ShaderPipelineCache.UsePrecachingThreadPool={args.precache_thread_pool}')
        if overrides:
            command.append('-DPCVars='+','.join(overrides))
        write_json(out/'command.json', command)
        report['runtime'] = launch(command, extraction, out/'runtime.stdout.log', 360)
        log = (out/'runtime.stdout.log').read_text(errors='replace')
        assert report['runtime']['returncode'] == 0 and not report['runtime']['timed_out'], 'Native process failed'
        assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log
        native_name = 'Surfaces' if scenario == 'surfaces' else 'Environment'
        assert re.search(r'Result=\{Success\}.*Name=\{' + native_name + r'\}', log), 'Native scenario failed'
        assert not runtime_has_task_error(log), 'Native error'
        reject_material_fallbacks(log)
        probe = json.loads((out/'isolation-probe.json').read_text())
        assert probe['uid'] == account.pw_uid and not any(probe['hidden_path_exists'].values())
        assert probe['network_interfaces'] == ['lo'] and not probe['package_writable'] and probe['state_writable']
        report['native_views'] = verify_views(out, 'ProductionTSR')
        report['shader_platform'] = verify_platform(out, 'sm6', 'ProductionTSR')
        if scenario == 'surfaces':
            report['architecture'] = verify_architecture(out, 'sm6')
            report['verification'] = verify_surfaces(out, 4, 100)
            report['verification']['scope'] = report['scope'] + '; gross pixel-delta screening only'
        else:
            report['verification'] = verify_environment(out)
        report['pso_hitches'] = [dict(kind=m[0], milliseconds=float(m[1]), diagnostic=m[2]) for m in re.findall(
            r'Runtime (graphics|compute) PSO creation hitch \(([\d.]+) msec\)([^\n]*)', log)]
        report['pso_observations'] = [line for line in log.splitlines() if re.search(
            r'LogPSOHitching:|pipeline cache|PipelineCache|PSOPrecach|record PSOs|Engine Initialization', line, re.I)]
        recordings = sorted((state/'user/Saved/CollectedPSOs').glob('*.rec.upipelinecache'))
        assert len(recordings) == 1 and recordings[0].stat().st_size > 64, 'One nonempty native PSO recording required'
        assert 'Forcing PSO cache from command line' in log
        if not args.preserve_user_cache:
            assert 'Forcing logging of PSOs from command line' in log
        if args.file_cache_with_precaching:
            assert 'Vulkan PSO Precaching = 1, PipelineFileCache = 1' in log, 'Vulkan compatibility gate not applied'
        if args.precache_thread_pool is not None:
            diagnostic = f'LogConfig: Set CVar [[r.ShaderPipelineCache.UsePrecachingThreadPool:{args.precache_thread_pool}]]'
            assert diagnostic in log, 'Bundled-cache scheduling override not applied'
            report['precache_thread_pool'] = args.precache_thread_pool
        report['recordings'] = [file_identity(p) for p in recordings]
        if args.seed:
            assert re.search(r'Opened FPipelineCacheFile:.*BiellaGames_SF_VULKAN_SM6.upipelinecache', log), 'Seed not opened natively'
        report['result'] = 'PASS'
    except (AssertionError, OSError, KeyError, ValueError) as error:
        report['error'] = str(error)
    finally:
        report['state_after'] = members(state)
        report['package_after'] = members(extraction)
        report['inputs_after'] = [file_identity(p) for p in inputs]
        if report.get('package_before') != report['package_after'] or report['inputs_before'] != report['inputs_after']:
            report.update(result='FAIL', error='Package or verifier inputs changed')
        write_json(out/'validation.json', report)
        if report['result'] != 'PASS':
            with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                    type='pso_capture_experiment', status='CONTINUE', diagnostics=report.get('error'), evidence=str(out)))+'\n')
    print(json.dumps(dict(result=report['result'], output=str(out), error=report.get('error'))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
