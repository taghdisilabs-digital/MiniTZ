#!/usr/bin/env python3
"""Run the exact D03 archive under isolated source/cache/network namespaces.

Cold means a new empty task user/cache directory; warm reuses that same directory.
Host source, editor, original home, cook workspace and network DDC are inaccessible.
Native engine timings measure gameplay; optional syscall tracing is reported separately.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import re
import subprocess
from run_d01_039 import PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d01_048 import launch
from run_d02_01 import reject_material_fallbacks, runtime_has_task_error


def members(root):
    return [file_identity(f) for f in sorted(root.rglob('*')) if f.is_file()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--phase', choices=('cold', 'warm'), required=True)
    parser.add_argument('--profile', choices=('ProductionTSR', 'NativeTAA'), required=True)
    parser.add_argument('--scenario', choices=('surfaces', 'environment'), default='surfaces')
    parser.add_argument('--feature-level', choices=('sm5', 'sm6'), help='Force a Vulkan feature level; omitted uses project preference')
    parser.add_argument('--verify-feature-level', choices=('sm5', 'sm6'), help='Require observed native renderer capabilities')
    parser.add_argument('--verify-architecture', action='store_true', help='Require all six authored street meshes and their platform-specific proxies')
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--loading-screen', choices=('enabled', 'disabled'), help='Verify native startup lifecycle and independently capture the X11 display')
    args = parser.parse_args()
    if args.verify_architecture and (args.scenario != 'surfaces' or not args.verify_feature_level):
        parser.error('--verify-architecture requires surfaces and --verify-feature-level')
    out, state = args.output.resolve(), args.state.resolve()
    assert not out.exists(), 'Fresh evidence required'
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(out, account)
    if args.phase == 'cold':
        assert not state.exists(), 'Cold state must be newly created, not cleared'
        ensure_runtime_output(state, account)
        for name in ('home', 'user', 'xdg-cache', 'xdg-config'):
            ensure_runtime_output(state/name, account)
    else:
        assert state.is_dir() and members(state), 'Warm state requires previous run files'
    stage = json.loads((args.stage/'validation.json').read_text())
    assert stage['result'] == 'PASS', 'Stage/archive not qualified'
    extraction = Path(stage['archive_readback'])
    binary = extraction/'Linux/BiellaGames/Binaries/Linux/BiellaGames'
    original = [Path('/opt/unreal/UE_5.8.2'), PROJECT, Path('/home/unreal'), Path(stage['destination']).parent]
    inputs = [PROJECT/'tests'/name for name in ('run_d03_01_package.py', 'd03_01_package_isolation_probe.py',
              'verify_d03_01_reconstruction.py', 'verify_d03_01_surfaces.py', 'verify_d02_04.py',
              'run_d01_048.py', 'run_d02_01.py', 'run_d01_039.py', 'run_d01_042.py',
              'verify_d03_01_shader_platform.py', 'verify_d03_01_architecture.py')]
    if args.loading_screen:
        inputs.extend(PROJECT/'tests'/name for name in ('d03_01_loading_display.py', 'verify_d03_01_loading_display.py'))
    report = dict(task_id='D03-01', result='FAIL', revision=source_revision(),
                  stage=file_identity(args.stage.resolve()/'validation.json'), profile=args.profile,
                  scenario=args.scenario, phase=args.phase, state=str(state), trace=args.trace,
                  loading_screen=args.loading_screen,
                  feature_level_request=args.feature_level,
                  feature_level_expected=args.verify_feature_level,
                  architecture_required=args.verify_architecture,
                  capture_status='GENERATED_DRAFT', state_before=members(state),
                  inaccessible_host_roots=[str(p) for p in original],
                  inputs_before=[file_identity(f) for f in inputs], archive=stage['archive'],
                  scope='Linux Development packaged Vulkan, task-isolated user caches; OS page cache is not flushed; no generated frames or cross-hardware claim')
    write_json(out/'validation.json', report)
    try:
        assert file_identity(Path(stage['archive']['path'])) == stage['archive'], 'Canonical archive changed'
        assert members(extraction) == stage['readback_members'], 'Archive extraction differs'
        report['package_before'] = members(extraction)
        assert file_identity(binary)['sha256'], 'Missing packaged binary'
        surface = args.scenario == 'surfaces'
        native = 'BiellaGames.D03.Surfaces' if surface else 'BiellaGames.D02.Environment'
        output_arg = 'BiellaPresentationOutput' if surface else 'BiellaEnvironmentOutput'
        command = ['bwrap', '--die-with-parent', '--ro-bind', '/', '/', '--dev-bind', '/dev', '/dev',
                   '--tmpfs', '/root', '--tmpfs', '/opt', '--tmpfs', '/home', '--tmpfs', '/mnt',
                   '--tmpfs', '/tmp', '--chmod', '1777', '/tmp', '--tmpfs', '/var/tmp',
                   '--chmod', '1777', '/var/tmp', '--tmpfs', '/var/cache', '--tmpfs', '/run',
                   '--unshare-pid', '--proc', '/proc', '--unshare-net', '--unshare-ipc',
                   '--ro-bind', str(extraction/'Linux'), '/tmp/package', '--bind', str(state), '/tmp/state',
                   '--bind', str(state/'home'), '/home/unreal', '--bind', str(out), '/tmp/evidence',
                   '--ro-bind', str(PROJECT/'tests/d03_01_package_isolation_probe.py'), '/tmp/probe.py',
                   '--chdir', '/tmp/package', '--', 'runuser', '-u', account.pw_name, '--',
                   'env', 'SDL_AUDIODRIVER=dummy', 'XDG_CACHE_HOME=/tmp/state/xdg-cache',
                   'XDG_CONFIG_HOME=/tmp/state/xdg-config', 'python3', '/tmp/probe.py',
                   'xvfb-run', '-a', '-s', '-screen 0 1280x720x24']
        if args.trace:
            command += ['strace', '-f', '-qq', '-e', 'trace=file', '-o', '/tmp/evidence/file-access.log']
        if args.loading_screen:
            # Bind before bwrap's command delimiter, then run capture inside Xvfb.
            delimiter = command.index('--')
            command[delimiter:delimiter] = ['--ro-bind', str(PROJECT/'tests/d03_01_loading_display.py'), '/tmp/loading-display.py']
            command += ['python3', '/tmp/loading-display.py']
        command += ['/tmp/package/BiellaGames.sh', '/Game/Maps/BiellaOpenWorldMap', '-vulkan', '-NoVSync',
                    '-windowed', '-ResX=1280', '-ResY=720', '-unattended', '-AudioMixer', '-nosplash',
                    '-stdout', '-FullStdOutLogOutput', '-UserDir=/tmp/state/user/',
                    '-AbsLog=/tmp/evidence/runtime.engine.log', f'-{output_arg}=/tmp/evidence',
                    f'-BiellaRenderProfile={args.profile}', '-BiellaRenderReadback=/tmp/evidence/native-views.csv',
                    '-LogCmds=LogPSOHitching Verbose,LogShaderLibrary Verbose,LogVulkanRHI Verbose',
                    f'-ExecCmds=t.MaxFPS {0 if surface else 60},r.VSync 0,r.MotionBlurQuality 0,Automation RunTests {native}; SoftQuit']
        if args.feature_level:
            command.append(f'-{args.feature_level}')
        if args.loading_screen:
            command.append('-BiellaLoadingOutput=/tmp/evidence')
            if args.loading_screen == 'disabled':
                command.append('-NoLoadingScreen')
        write_json(out/'command.json', command)
        report['runtime'] = launch(command, extraction, out/'runtime.stdout.log', 360)
        log = (out/'runtime.stdout.log').read_text(errors='replace')
        assert report['runtime']['returncode'] == 0 and not report['runtime']['timed_out'], 'Packaged process failed'
        assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log, 'Native completion missing'
        assert re.search(r'Result=\{Success\}.*Name=\{' + native.rsplit('.', 1)[-1] + r'\}', log), 'Native scenario failed'
        assert not runtime_has_task_error(log), 'Runtime error'
        if args.loading_screen == 'enabled':
            assert log.count('D03_LOADING_START version=1') == 1, 'Exactly one loading screen must play'
            stops = re.findall(r'D03_LOADING_STOP version=1 engine_finished=(\d+) ready=(\d+) exit=(\d+) pending=(\d+) render_ticks=(\d+) elapsed_s=([\d.]+) max_render_gap_s=([\d.]+)', log)
            assert len(stops) == 1 and stops[0][:4] == ('1', '1', '0', '0'), 'Invalid loading handoff'
            assert int(stops[0][4]) >= 3, 'No sustained native loading rendering'
            assert log.index('D03_LOADING_STOP') < log.index('Result={Success}'), 'Gameplay did not follow startup'
            report['loading'] = dict(render_ticks=int(stops[0][4]), elapsed_seconds=float(stops[0][5]),
                                     max_render_gap_seconds=float(stops[0][6]), pending_at_stop=0)
            assert (out/'loading-render-ticks.csv').is_file(), 'Missing native loading telemetry'
        elif args.loading_screen == 'disabled':
            assert 'D03_LOADING_DISABLED version=1' in log and 'D03_LOADING_START' not in log and 'D03_LOADING_STOP' not in log, 'Disabled control still played screen'
            assert not (out/'loading-render-ticks.csv').exists(), 'Disabled control has loading telemetry'
        if args.loading_screen:
            from verify_d03_01_loading_display import verify as verify_display
            report['loading_display'] = verify_display(out, args.loading_screen == 'enabled')
        reject_material_fallbacks(log)
        assert f'D03_RENDER_PROFILE version=1 requested={args.profile} selected={args.profile}' in log, 'Profile diagnostic missing'
        probe = json.loads((out/'isolation-probe.json').read_text())
        assert probe['uid'] == account.pw_uid and not any(probe['hidden_path_exists'].values()), 'Namespace isolation failed'
        assert not probe['package_writable'] and probe['state_writable'], 'Package/tmp/state mount policy differs'
        from verify_d03_01_reconstruction import verify as verify_views
        report['native_views'] = verify_views(out, args.profile)
        if surface:
            from verify_d03_01_surfaces import verify
            report['verification'] = verify(out, 4 if args.profile == 'ProductionTSR' else 2, 100)
            # The reused verifier's original editor-DDC prose is not a cache assertion.
            report['verification']['scope'] = report['scope'] + '; gross pixel-delta screening only; engine whole-frame GPU timings'
        else:
            from verify_d02_04 import verify
            report['verification'] = verify(out)
        if args.verify_feature_level:
            from verify_d03_01_shader_platform import verify as verify_platform
            report['shader_platform'] = verify_platform(out, args.verify_feature_level, args.profile)
        if args.verify_architecture:
            from verify_d03_01_architecture import verify as verify_architecture
            report['architecture'] = verify_architecture(out, args.verify_feature_level)
        report['pso_hitches'] = [dict(kind=m[0], milliseconds=float(m[1]), diagnostic=m[2]) for m in re.findall(
            r'Runtime (graphics|compute) PSO creation hitch \(([\d.]+) msec\)([^\n]*)', log)]
        report['pso_observations'] = [line for line in log.splitlines() if re.search(
            r'LogPSOHitching:|pipeline cache|PipelineCache|PSOPrecach|ShaderLibrary|Engine Initialization', line, re.I)]
        report['pso_measurement_scope'] = 'Engine LogPSOHitching Verbose records runtime PSO creations exceeding its 20ms threshold; not all pipeline creation costs'
        report['result'] = 'PASS'
    except (AssertionError, OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
    finally:
        report['state_after'] = members(state)
        report['package_after'] = members(extraction)
        report['inputs_after'] = [file_identity(f) for f in inputs]
        if report.get('package_before') != report['package_after'] or report['inputs_before'] != report['inputs_after']:
            report.update(result='FAIL', error='Package or verification source changed')
        write_json(out/'validation.json', report)
        if report['result'] != 'PASS':
            with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                            type='packaged_runtime', status='CONTINUE', diagnostics=report.get('error'),
                                            evidence=str(out)))+'\n')
    print(json.dumps(dict(result=report['result'], output=str(out), error=report.get('error'))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
