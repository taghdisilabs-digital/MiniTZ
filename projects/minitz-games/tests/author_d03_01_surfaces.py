#!/usr/bin/env python3
"""Author/rebuild D03 material assets, then read back exact saved graph in a fresh process."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
from run_d01_039 import PROJECT, DEFAULT_EDITOR, file_identity, runtime_run, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import runtime_has_task_error

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rebuild',action='store_true')
    a=p.parse_args();out=a.output.resolve()
    ensure_runtime_output(out,pwd.getpwnam('unreal'))
    report={'task_id':'D03-01','result':'FAIL','runs':[], 'source':file_identity(PROJECT/'SourceAssets/Materials/ProductionSurface.hlsl')}
    def assets():
        return [file_identity(x) for x in sorted((PROJECT/'Content/OpenWorld/Materials').glob('*.uasset'))]
    try:
        for mode in ('author','readback'):
            before=assets()
            cmd=['runuser','-u','unreal','--','env',f'BIELLA_D03_SURFACE_REPORT={out}/{mode}.json',
                 str(DEFAULT_EDITOR.with_name('UnrealEditor-Cmd')),str(PROJECT/'BiellaGames.uproject'),'-run=pythonscript',
                 f'-script={PROJECT}/Content/Python/build_production_surfaces.py','-EnablePlugins=PythonScriptPlugin',
                 '-unattended','-nullrhi','-nosound','-nop4','-stdout','-FullStdOutLogOutput']
            if mode=='readback':cmd.append('-D03VerifySurfaces')
            elif a.rebuild:cmd.append('-D03RebuildSurfaces')
            run=runtime_run(cmd,out/f'{mode}.log',180);report['runs'].append(run)
            log=(out/f'{mode}.log').read_text(errors='replace')
            assert run['returncode']==0 and not run['timed_out'], f'{mode} process failed'
            assert 'D03_SURFACE COMPLETE' in log and not runtime_has_task_error(log), f'{mode} graph validation failed'
            saved=json.loads((out/f'{mode}.json').read_text())
            assert saved['result']=='PASS' and saved['source_sha256']==report['source']['sha256'], 'Wrong source readback'
            if mode=='readback':assert before==assets(), 'Readback modified saved material bytes'
        report['assets']=assets();report['result']='PASS'
    except (OSError,AssertionError,ValueError) as e:
        report['error']=str(e)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as f:
            f.write(json.dumps(dict(task_id='D03-01',time=datetime.now(timezone.utc).isoformat(),type='surface_authoring',status='CONTINUE',diagnostics=str(e),evidence=str(out)))+'\n')
    write_json(out/'validation.json',report)
    print(json.dumps({'result':report['result'],'output':str(out),'error':report.get('error')},indent=2))
    return 0 if report['result']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
