#!/usr/bin/env python3
"""Execute the actual D02 population world; retain exact identities and failed runs."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import re
from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import identities, monitor, reject_material_fallbacks


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--count', type=int, choices=(4, 8, 12), default=4)
    p.add_argument('--renderer', choices=('vulkan', 'nullrhi'), default='vulkan')
    args = p.parse_args()
    out = args.output.resolve()
    assert not out.exists(), 'Use a fresh output directory'
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(out, account)
    protected = [PROJECT.parents[1] / 'docs/project-state/03_BIELLA_CURRENT_STATE.md',
                 PROJECT.parents[1] / 'docs/project-state/04_BIELLA_ACTIVE_TASK.md', PROJECT / 'docs/PRODUCTION.md']
    def inputs():
        return identities(DEFAULT_EDITOR) + [file_identity(Path(__file__)), file_identity(PROJECT / 'tests/verify_d02_02.py')]
    report = dict(task_id='D02-02', result='FAIL', revision=source_revision(),
                  candidate_count=args.count, renderer=args.renderer, capture_status='GENERATED_DRAFT',
                  identities_before=inputs(), protected_before=[file_identity(x) for x in protected])
    try:
        cmd = ['runuser', '-u', account.pw_name, '--', 'xvfb-run', '-a', '-s', '-screen 0 1280x720x24',
               str(DEFAULT_EDITOR), str(PROJECT / 'BiellaGames.uproject'), '/Game/Maps/BiellaOpenWorldMap',
               '-game', '-' + args.renderer, '-NoVSync', '-windowed', '-ResX=1280', '-ResY=720',
               '-unattended', '-nosound', '-nosplash', '-stdout', '-FullStdOutLogOutput',
               f'-AbsLog={out / "runtime.engine.log"}', f'-BiellaPopulationOutput={out}',
               f'-BiellaPopulationCount={args.count}',
               '-ExecCmds=t.MaxFPS 0,r.VSync 0,r.ScreenPercentage 100,r.DynamicRes.OperationMode 0,Automation RunTests BiellaGames.D02.Population; SoftQuit']
        report['runtime'] = monitor(cmd, out, 300)
        log = (out / 'runtime.stdout.log').read_text(errors='replace')
        assert report['runtime']['returncode'] == 0 and not report['runtime']['timed_out'], 'Unreal process failed'
        assert report['runtime']['log_finalization']['closed'], 'Runtime log still open'
        assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log, 'Unreal completion missing'
        assert re.search(r'Result=\{Success\}.*Name=\{Population\}', log), 'Population automation failed'
        assert not re.search(r'Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:|\bError:', log), 'Runtime error'
        reject_material_fallbacks(log)
        from verify_d02_02 import verify
        report['verification'] = verify(out, args.count, args.renderer)
        report['identities_after'] = inputs()
        report['protected_after'] = [file_identity(x) for x in protected]
        assert report['identities_before'] == report['identities_after'], 'Inputs changed during run'
        assert report['protected_before'] == report['protected_after'], 'Protected authority changed'
        report['result'] = 'PASS'
    except (AssertionError, OSError, ValueError, KeyError) as e:
        report['error'] = str(e)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as f:
            f.write(json.dumps(dict(task_id='D02-02', time=datetime.now(timezone.utc).isoformat(),
                                    type='runtime_validation', status='CONTINUE', diagnostics=str(e), evidence=str(out))) + '\n')
    write_json(out / 'validation.json', report)
    print(json.dumps({k: report[k] for k in ('task_id', 'result')} | {'output': str(out), 'error': report.get('error')}, indent=2))
    return 0 if report['result'] == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
