#!/usr/bin/env python3
"""Native D03 surface evidence. Each launch retains exact inputs and raw frames."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import re
from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import identities, monitor, reject_material_fallbacks, runtime_has_task_error

PROFILES = {'tsr100': (4, 100), 'taa100': (2, 100), 'tsr67': (4, 67)}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--profile', choices=PROFILES, default='tsr100')
    args = p.parse_args()
    out = args.output.resolve()
    assert not out.exists(), 'Use a fresh output directory'
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(out, account)
    protected = [PROJECT.parents[1] / 'docs/project-state/03_BIELLA_CURRENT_STATE.md',
                 PROJECT.parents[1] / 'docs/project-state/04_BIELLA_ACTIVE_TASK.md', PROJECT / 'docs/PRODUCTION.md']
    def inputs():
        return identities(DEFAULT_EDITOR) + [file_identity(x) for x in (
            Path(__file__), PROJECT/'tests/verify_d03_01_surfaces.py', PROJECT/'SourceAssets/Materials/ProductionSurface.hlsl')]
    aa, percentage = PROFILES[args.profile]
    report = dict(task_id='D03-01', scope='surface rendering only', result='FAIL', revision=source_revision(),
                  profile=args.profile, aa=aa, screen_percentage=percentage, capture_status='GENERATED_DRAFT',
                  cache_scope='Existing development DDC; neither cold cache nor packaged shipping proof',
                  fixture='Population AI frozen; real open-world geometry, streaming, rendering and W movement',
                  identities_before=inputs(), protected_before=[file_identity(x) for x in protected])
    write_json(out / 'validation.json', report)
    try:
        cmd = ['runuser', '-u', account.pw_name, '--', 'env', 'SDL_AUDIODRIVER=dummy', 'xvfb-run', '-a', '-s', '-screen 0 1280x720x24',
               str(DEFAULT_EDITOR), str(PROJECT / 'BiellaGames.uproject'), '/Game/Maps/BiellaOpenWorldMap',
               '-game', '-vulkan', '-NoVSync', '-windowed', '-ResX=1280', '-ResY=720',
               '-unattended', '-AudioMixer', '-nosplash', '-stdout', '-FullStdOutLogOutput',
               f'-AbsLog={out / "runtime.engine.log"}', f'-BiellaPresentationOutput={out}',
               f'-ExecCmds=t.MaxFPS 0,r.VSync 0,r.MotionBlurQuality 0,r.AntiAliasingMethod {aa},r.ScreenPercentage {percentage},r.DynamicRes.OperationMode 0,Automation RunTests BiellaGames.D03.Surfaces; SoftQuit']
        report['runtime'] = monitor(cmd, out, 240)
        log = (out / 'runtime.stdout.log').read_text(errors='replace')
        assert report['runtime']['returncode'] == 0 and not report['runtime']['timed_out'], 'Unreal process failed'
        assert report['runtime']['log_finalization']['closed'], 'Runtime log still open'
        assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log, 'Unreal completion missing'
        assert re.search(r'Result=\{Success\}.*Name=\{Surfaces\}', log), 'Surface automation failed'
        assert not runtime_has_task_error(log), 'Runtime error'
        reject_material_fallbacks(log)
        from verify_d03_01_surfaces import verify
        report['verification'] = verify(out, aa, percentage)
        report['identities_after'] = inputs()
        report['protected_after'] = [file_identity(x) for x in protected]
        assert report['identities_before'] == report['identities_after'], 'Inputs changed during run'
        assert report['protected_before'] == report['protected_after'], 'Protected authority changed'
        report['result'] = 'PASS'
    except (AssertionError, OSError, ValueError, KeyError) as e:
        report['error'] = str(e)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as f:
            f.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                    type='runtime_validation', status='CONTINUE', diagnostics=str(e), evidence=str(out))) + '\n')
    write_json(out / 'validation.json', report)
    print(json.dumps({'task_id': 'D03-01', 'result': report['result'], 'output': str(out), 'error': report.get('error')}, indent=2))
    return 0 if report['result'] == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
