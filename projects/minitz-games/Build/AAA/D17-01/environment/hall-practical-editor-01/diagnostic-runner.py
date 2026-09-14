#!/usr/bin/env python3
"""Inspect real editor G-buffer channels using the existing environment fixture.

This is material diagnosis, not ordinary gameplay or slice acceptance. It does
not modify assets, native code, or the fixture's input/state behavior.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import re
from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import identities, monitor, reject_material_fallbacks, runtime_has_task_error
from verify_d02_04 import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--buffer', required=True, choices=('BaseColor', 'Roughness', 'WorldNormal', 'Lit'))
    parser.add_argument('--disable-point-lights', action='store_true',
                        help='Diagnostic isolation only; disables the renderer point-light show flag without saving assets.')
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists(), 'Preserve previous diagnostics; use a fresh output'
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(out, account)
    report = dict(task_id='D17-01', result='FAIL', buffer=args.buffer,
                  point_lights_disabled=args.disable_point_lights,
                  scope='EDITOR_FIXTURE_MATERIAL_DIAGNOSIS_NOT_SLICE_ACCEPTANCE',
                  runner=file_identity(Path(__file__)), identities_before=identities(DEFAULT_EDITOR))
    controls = 't.MaxFPS 60,r.VSync 0,r.ScreenPercentage 100,r.DynamicRes.OperationMode 0'
    if args.disable_point_lights:
        assert args.buffer == 'Lit', 'Light isolation requires the Lit buffer'
        controls += ',ShowFlag.PointLights 0'
    if args.buffer != 'Lit':
        controls += f',viewmode VisualizeBuffer,r.BufferVisualizationTarget {args.buffer}'
    cmd = ['runuser', '-u', account.pw_name, '--', 'env', 'SDL_AUDIODRIVER=dummy',
           'xvfb-run', '-a', '-s', '-screen 0 1280x720x24', str(DEFAULT_EDITOR),
           str(PROJECT / 'BiellaGames.uproject'), '/Game/Maps/BiellaOpenWorldMap',
           '-game', '-vulkan', '-NoVSync', '-windowed', '-ResX=1280', '-ResY=720',
           '-unattended', '-AudioMixer', '-nosplash', '-stdout', '-FullStdOutLogOutput',
           f'-AbsLog={out / "runtime.engine.log"}', f'-BiellaEnvironmentOutput={out}',
           f'-ExecCmds={controls},Automation RunTests BiellaGames.D02.Environment; SoftQuit']
    write_json(out / 'validation.json', report)
    try:
        report['runtime'] = monitor(cmd, out, 250)
        log = (out / 'runtime.stdout.log').read_text(errors='replace')
        assert report['runtime']['returncode'] == 0 and not report['runtime']['timed_out']
        assert report['runtime']['log_finalization']['closed']
        assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log
        assert re.search(r'Result=\{Success\}.*Name=\{Environment\}', log)
        assert not runtime_has_task_error(log)
        reject_material_fallbacks(log)
        if args.disable_point_lights:
            assert re.search(r'ShowFlag.PointLights\s*=\s*"?0', log), 'Point-light isolation not applied'
        if args.buffer != 'Lit':
            assert f'r.BufferVisualizationTarget = "{args.buffer}"' in log
        report['verification'] = verify(out)
        report['identities_after'] = identities(DEFAULT_EDITOR)
        assert report['identities_before'] == report['identities_after']
        report['captures'] = [file_identity(p) for p in sorted((out / 'captures').glob('*.png'))]
        report['result'] = 'PASS'
    except (AssertionError, OSError, ValueError, KeyError) as error:
        report['error'] = repr(error)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D17-01', time=datetime.now(timezone.utc).isoformat(),
                type='material_diagnosis', status='CONTINUE', diagnostic=repr(error), evidence=str(out))) + '\n')
    write_json(out / 'validation.json', report)
    print(json.dumps({k: report.get(k) for k in ('result', 'buffer', 'error')}))
    return int(report['result'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
