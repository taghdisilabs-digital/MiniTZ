#!/usr/bin/env python3
"""Probe, author and read back ground; require byte preservation of existing assets."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
from run_d01_039 import PROJECT, DEFAULT_EDITOR, file_identity, runtime_run, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import runtime_has_task_error


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    mode_group=parser.add_mutually_exclusive_group()
    mode_group.add_argument('--probe-only',action='store_true')
    mode_group.add_argument('--readback-only',action='store_true')
    args=parser.parse_args()
    out=args.output.resolve()
    assert not out.exists(), 'Use fresh evidence output'
    ensure_runtime_output(out,pwd.getpwnam('unreal'))
    for path in (PROJECT/'Content/Python/author_ground_support.py',PROJECT/'SourceAssets/Architecture/ground-support.json'):
        os.chmod(path,path.stat().st_mode | 0o444)
    def identities():
        return {str(p.relative_to(PROJECT)):file_identity(p) for p in sorted((PROJECT/'Content').rglob('*'))
                if p.is_file() and p.suffix in ('.uasset','.umap')}
    report=dict(task_id='D03-01',result='FAIL',before=identities(),runs=[])
    try:
        for mode in (('probe',) if args.probe_only else ('readback',) if args.readback_only else ('probe','author','readback')):
            before=identities()
            cmd=['runuser','-u','unreal','--','env',f'BIELLA_D03_GROUND_REPORT={out}/{mode}.json',
                 str(DEFAULT_EDITOR.with_name('UnrealEditor-Cmd')),str(PROJECT/'BiellaGames.uproject'),
                 '-run=pythonscript',f'-script={PROJECT}/Content/Python/author_ground_support.py',
                 '-EnablePlugins=PythonScriptPlugin','-unattended','-nullrhi','-nosound','-nop4','-stdout','-FullStdOutLogOutput']
            if mode!='author':cmd.append('-D03ProbeGroundSupport' if mode=='probe' else '-D03VerifyGroundSupport')
            write_json(out/f'{mode}-command.json',cmd)
            run=runtime_run(cmd,out/f'{mode}.log',300);report['runs'].append(run)
            log=(out/f'{mode}.log').read_text(errors='replace')
            assert run['returncode']==0 and not run['timed_out'],mode+' process failed'
            assert 'D03_GROUND COMPLETE' in log and not runtime_has_task_error(log),mode+' failed'
            saved=json.loads((out/f'{mode}.json').read_text())
            if mode!='author':assert identities()==before,'Read-only run changed asset bytes'
            if mode=='readback' and not args.readback_only:
                authored=json.loads((out/'author.json').read_text())
                assert authored['ground']==saved['ground'],'Ground save/readback mismatch'
                assert json.loads((out/'probe.json').read_text())['existing_actors']==saved['existing_actors'],'Existing actors changed'
        after=identities()
        changed=[k for k,v in report['before'].items() if after.get(k)!=v]
        # New OFPA actor and material are permitted; preexisting map and all
        # external actor/asset bytes must remain identical.
        assert not changed, 'Preexisting assets changed: '+str(changed)
        report.update(result='PASS',after=after,new_assets=[k for k in after if k not in report['before']])
    except (OSError,ValueError,AssertionError) as e:
        report['error']=str(e)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as f:
            f.write(json.dumps(dict(task_id='D03-01',time=datetime.now(timezone.utc).isoformat(),type='ground_authoring',status='CONTINUE',diagnostics=str(e),evidence=str(out)))+'\n')
    write_json(out/'validation.json',report)
    print(json.dumps(dict(result=report['result'],error=report.get('error'),output=str(out))))
    return 0 if report['result']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
