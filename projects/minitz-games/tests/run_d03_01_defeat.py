#!/usr/bin/env python3
"""Native cosmetic defeat pose, authoritative gameplay and bounded lifecycle evidence."""
import argparse
import csv
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
    parser.add_argument('--disabled', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists(), 'Preserve evidence; use a fresh output directory'
    ensure_runtime_output(out, pwd.getpwnam('unreal'))

    def inputs():
        return identities(DEFAULT_EDITOR) + [file_identity(Path(__file__))]

    report = dict(task_id='D03-01', result='FAIL', revision=source_revision(),
                  scope='cosmetic defeat animation and immediate authoritative defeat', capture_status='GENERATED_DRAFT',
                  fixture='Canonical map; population frozen; real lethal shot/damage APIs, evaluated skeleton, lifetime, dormancy and EndPlay; captures run separately from measurements',
                  identities_before=inputs(), protected_before=file_identity(PROJECT / 'docs/PRODUCTION.md'))
    try:
        command = ['runuser', '-u', 'unreal', '--', 'env', 'SDL_AUDIODRIVER=dummy',
                   'xvfb-run', '-a', '-s', '-screen 0 1280x720x24', str(DEFAULT_EDITOR),
                   str(PROJECT / 'BiellaGames.uproject'), '/Game/Maps/BiellaGameplayMap',
                   '-game', '-vulkan', '-NoVSync', '-windowed', '-ResX=1280', '-ResY=720',
                   '-unattended', '-AudioMixer', '-nosplash', '-stdout', '-FullStdOutLogOutput',
                   f'-AbsLog={out}/runtime.engine.log', f'-BiellaDefeatOutput={out}',
                   '-ExecCmds=t.MaxFPS 0,r.VSync 0,r.MotionBlurQuality 0,r.DynamicRes.OperationMode 0,Automation RunTests BiellaGames.D03.DefeatPresentation; SoftQuit']
        if args.disabled:
            command.append('-BiellaDefeatDisabled')
        report['runtime'] = monitor(command, out, 210)
        log = (out / 'runtime.stdout.log').read_text(errors='replace')
        result = json.loads((out / 'result.json').read_text(encoding='utf-8-sig'))
        assert not report['runtime']['timed_out'] and report['runtime']['log_finalization']['closed'], 'Incomplete runtime'
        report['identities_after'] = inputs()
        report['protected_after'] = file_identity(PROJECT / 'docs/PRODUCTION.md')
        assert report['identities_before'] == report['identities_after'], 'Runtime inputs changed'
        assert report['protected_before'] == report['protected_after'], 'Project production authority changed'
        assert report['runtime']['returncode'] == 0 and '**** TEST COMPLETE. EXIT CODE: 0 ****' in log, 'Unreal failed'
        assert re.search(r'Result=\{Success\}.*Name=\{DefeatPresentation\}', log) and result['success'], 'Native defeat assertions failed'
        assert not runtime_has_task_error(log), 'Runtime error'
        reject_material_fallbacks(log)
        with (out / 'poses.csv').open(encoding='utf-8-sig') as stream:
            poses = list(csv.DictReader(stream))
        labels = ['live', 'falling', 'settled']
        assert {4, 5, 6} <= {int(row['phase']) for row in poses}, 'Missing death/hold/cleanup windows'
        assert all(float(row['root_drift']) < .1 for row in poses), 'Cosmetic moved gameplay root'
        if args.disabled:
            assert all(int(row['cosmetic']) == 0 for row in poses), 'Disabled control created cosmetic'
            outcome = 'EXPECTED_NEGATIVE_CONTROL'
        else:
            assert result['falling_frames'] >= 8 and result['head_drop'] > 60 and result['pelvis_drop'] > 30, 'Death motion absent'
            assert result['initial_pose_error'] < .1 and result['root_drift'] < .1, 'Death continuity/authority failed'
            assert any(int(row['cosmetic']) == 0 and float(row['age']) > 3.1 for row in poses), 'Bounded lifetime not observed'
            outcome = 'PASS'
        from PIL import Image
        for label in labels:
            with Image.open(out / 'captures' / f'{label}.png') as im:
                assert im.size == (1280, 720) and max(hi-lo for lo, hi in im.convert('RGB').getextrema()) > 100, 'Invalid native capture'
        report.update(result=outcome, pose_frames=len(poses),
                      captures=[file_identity(out / 'captures' / f'{label}.png') for label in labels],
                      measurements=[file_identity(out / name) for name in ('poses.csv', 'result.json')])
    except (AssertionError, OSError, ValueError, KeyError) as error:
        report['result'] = 'FAIL'
        report['error'] = str(error)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                         type='defeat_presentation_validation', status='CONTINUE',
                                         diagnostics=str(error), evidence=str(out))) + '\n')
    write_json(out / 'validation.json', report)
    print(json.dumps({key: report[key] for key in ('task_id', 'result', 'scope')} | {'output': str(out), 'error': report.get('error')}))
    return 1 if report['result'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
