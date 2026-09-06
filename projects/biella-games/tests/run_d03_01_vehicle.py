#!/usr/bin/env python3
"""Validate skeletal vehicle presentation using the existing input/Chaos lifecycle."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import re
from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import identities, monitor, reject_material_fallbacks, runtime_has_task_error
from verify_d03_01_vehicle import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--disabled', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists(), 'Preserve evidence; use a fresh output directory'
    ensure_runtime_output(out, pwd.getpwnam('unreal'))

    def inputs():
        return identities(DEFAULT_EDITOR) + [file_identity(Path(__file__))] + [
            file_identity(PROJECT / 'tests' / name) for name in ('verify_d03_01_vehicle.py', 'verify_d02_03.py')]

    report = dict(task_id='D03-01', result='FAIL', revision=source_revision(), disabled=args.disabled,
                  scope='skeletal vehicle exterior, authoritative wheel/steer/spin/contact, damage tint, fallback and lifecycle',
                  capture_status='GENERATED_DRAFT', identities_before=inputs(),
                  protected_before=file_identity(PROJECT / 'docs/PRODUCTION.md'))
    write_json(out / 'validation.json', report)
    try:
        command = ['runuser', '-u', 'unreal', '--', 'env', 'SDL_AUDIODRIVER=dummy',
                   'xvfb-run', '-a', '-s', '-screen 0 1280x720x24', str(DEFAULT_EDITOR),
                   str(PROJECT / 'BiellaGames.uproject'), '/Game/Maps/BiellaOpenWorldMap',
                   '-game', '-vulkan', '-NoVSync', '-windowed', '-ResX=1280', '-ResY=720',
                   '-unattended', '-AudioMixer', '-nosplash', '-stdout', '-FullStdOutLogOutput',
                   f'-AbsLog={out}/runtime.engine.log', f'-BiellaVehicleOutput={out}', '-BiellaVehiclePresentation',
                   '-ExecCmds=t.MaxFPS 60,r.VSync 0,r.ScreenPercentage 100,r.DynamicRes.OperationMode 0,Automation RunTests BiellaGames.D02.Vehicle; SoftQuit']
        if args.disabled:
            command.append('-BiellaVehiclePresentationDisabled')
        report['runtime'] = monitor(command, out, 250)
        report['identities_after'] = inputs()
        report['protected_after'] = file_identity(PROJECT / 'docs/PRODUCTION.md')
        assert report['identities_before'] == report['identities_after'], 'Runtime inputs changed'
        assert report['protected_before'] == report['protected_after'], 'Project production authority changed'
        log = (out / 'runtime.stdout.log').read_text(errors='replace')
        assert not report['runtime']['timed_out'] and report['runtime']['log_finalization']['closed'], 'Incomplete runtime'
        assert report['runtime']['returncode'] == 0 and '**** TEST COMPLETE. EXIT CODE: 0 ****' in log, 'Unreal failed'
        assert re.search(r'Result=\{Success\}.*Name=\{Vehicle\}', log), 'Native vehicle assertions failed'
        assert not runtime_has_task_error(log), 'Runtime error'
        reject_material_fallbacks(log)
        report['verification'] = verify(out, args.disabled)
        report['result'] = report['verification']['result']
    except (AssertionError, OSError, ValueError, KeyError) as error:
        report['error'] = str(error)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                         type='vehicle_presentation_validation', status='CONTINUE',
                                         diagnostics=str(error), evidence=str(out))) + '\n')
    write_json(out / 'validation.json', report)
    print(json.dumps({key: report[key] for key in ('task_id', 'result', 'scope')} | {'output': str(out), 'error': report.get('error')}))
    return 1 if report['result'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
