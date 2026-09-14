#!/usr/bin/env python3
"""Qualify explicit reconstruction launch profiles in existing playable-world scenarios."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import re
from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import identities, monitor, reject_material_fallbacks, runtime_has_task_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', choices=('ProductionTSR', 'NativeTAA', 'InvalidFixture'), required=True)
    parser.add_argument('--scenario', choices=('surfaces', 'environment'), default='surfaces')
    parser.add_argument('--override-fxaa', action='store_true', help='Negative control: console overrides the selected AA')
    parser.add_argument('--feature-level', choices=('sm5', 'sm6'), help='Force an RHI feature level; omitted uses project preference')
    parser.add_argument('--verify-feature-level', choices=('sm5', 'sm6'), help='Require observed renderer capabilities')
    parser.add_argument('--timeout', type=int, default=250, help='Process timeout including initial shader compilation')
    parser.add_argument('--ground-control', choices=('visible','hidden'), help='Require cosmetic ground; hidden is a native negative control with captures')
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists(), 'Use a fresh output directory'
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(out, account)
    expected = 'ProductionTSR' if args.profile == 'ProductionTSR' else 'NativeTAA'
    surface = args.scenario == 'surfaces'
    assert not args.ground_control or surface, 'Ground control uses the surfaces scenario'
    native_test = 'BiellaGames.D03.Surfaces' if surface else 'BiellaGames.D02.Environment'
    output_arg = 'BiellaPresentationOutput' if surface else 'BiellaEnvironmentOutput'
    protected = [PROJECT.parents[1]/'docs/project-state/03_BIELLA_CURRENT_STATE.md',
                 PROJECT.parents[1]/'docs/project-state/04_BIELLA_ACTIVE_TASK.md', PROJECT/'docs/PRODUCTION.md']

    def inputs():
        return identities(DEFAULT_EDITOR) + [file_identity(path) for path in (
            Path(__file__), PROJECT/'tests/verify_d03_01_reconstruction.py', PROJECT/'tests/verify_d03_01_shader_platform.py',
            PROJECT/'tests/verify_d03_01_surfaces.py', PROJECT/'tests/verify_d02_04.py')]

    report = dict(task_id='D03-01', result='FAIL', revision=source_revision(), profile=args.profile,
                  expected_profile=expected, scenario=args.scenario, override_fxaa=args.override_fxaa,
                  feature_level=args.feature_level, verify_feature_level=args.verify_feature_level,
                  ground_control=args.ground_control,
                  capture_status='GENERATED_DRAFT', identities_before=inputs(),
                  protected_before=[file_identity(path) for path in protected],
                  cache_scope='Existing Development DDC; not cold-cache, PSO or package qualification')
    write_json(out/'validation.json', report)
    try:
        override = ',r.AntiAliasingMethod 1' if args.override_fxaa else ''
        cmd = ['runuser', '-u', account.pw_name, '--', 'env', 'SDL_AUDIODRIVER=dummy',
               'xvfb-run', '-a', '-s', '-screen 0 1280x720x24', str(DEFAULT_EDITOR),
               str(PROJECT/'BiellaGames.uproject'), '/Game/Maps/BiellaOpenWorldMap',
               '-game', '-vulkan', '-NoVSync', '-windowed', '-ResX=1280', '-ResY=720',
               '-unattended', '-AudioMixer', '-nosplash', '-stdout', '-FullStdOutLogOutput',
               f'-AbsLog={out/"runtime.engine.log"}', f'-{output_arg}={out}',
               f'-BiellaRenderProfile={args.profile}', f'-BiellaRenderReadback={out/"native-views.csv"}',
               f'-ExecCmds=t.MaxFPS {0 if surface else 60},r.VSync 0,r.MotionBlurQuality 0{override},Automation RunTests {native_test}; SoftQuit']
        if args.feature_level:
            cmd.append(f'-{args.feature_level}')
        if args.ground_control:
            cmd.append('-BiellaVerifyGroundSupport')
            if args.ground_control == 'hidden': cmd.append('-BiellaHideGroundSupport')
        write_json(out/'command.json', cmd)
        report['runtime'] = monitor(cmd, out, args.timeout)
        log = (out/'runtime.stdout.log').read_text(errors='replace')
        assert report['runtime']['returncode'] == 0 and not report['runtime']['timed_out'], 'Unreal process failed'
        assert report['runtime']['log_finalization']['closed'], 'Runtime log still open'
        assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log, 'Unreal completion missing'
        assert re.search(r'Result=\{Success\}.*Name=\{' + native_test.rsplit('.', 1)[-1] + r'\}', log), 'Native scenario failed'
        assert not runtime_has_task_error(log), 'Runtime error'
        reject_material_fallbacks(log)
        assert f'D03_RENDER_PROFILE version=1 requested={args.profile} selected={expected}' in log, 'Profile selection diagnostic missing'
        if args.profile == 'InvalidFixture':
            assert 'D03_RENDER_PROFILE_INVALID requested=InvalidFixture fallback=NativeTAA' in log, 'Invalid-profile fallback diagnostic missing'
        from verify_d03_01_reconstruction import verify as verify_views
        report['native_views'] = verify_views(out, expected)
        if args.verify_feature_level:
            from verify_d03_01_shader_platform import verify as verify_platform
            report['shader_platform'] = verify_platform(out, args.verify_feature_level, expected)
        if surface:
            from verify_d03_01_surfaces import verify
            report['verification'] = verify(out, 4 if expected == 'ProductionTSR' else 2, 100)
            if args.ground_control:
                ground=json.loads((out/'ground.json').read_text())
                assert ground['count']==1 and all(ground[k] for k in ('visible','no_collision','no_navigation','rays_ignore_ground','existing_floor_collision')), 'Ground runtime invariants failed'
                report['ground']=ground
        else:
            from verify_d02_04 import verify
            report['verification'] = verify(out)
        report['result'] = 'PASS'
    except (AssertionError, OSError, ValueError, KeyError) as error:
        report['error'] = str(error)
    finally:
        report['identities_after'] = inputs()
        report['protected_after'] = [file_identity(path) for path in protected]
        if report['identities_before'] != report['identities_after']:
            report.update(result='FAIL', error='Inputs changed during run')
        if report['protected_before'][-1] != report['protected_after'][-1]:
            report.update(result='FAIL', error='Project production authority changed')
    if report['result'] == 'FAIL':
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                        type='runtime_validation', status='CONTINUE', diagnostics=report['error'],
                                        evidence=str(out)))+'\n')
    write_json(out/'validation.json', report)
    print(json.dumps(dict(result=report['result'], output=str(out), error=report.get('error')), indent=2))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
