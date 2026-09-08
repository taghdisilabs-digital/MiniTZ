#!/usr/bin/env python3
"""Author and independently read back new service-bay assets only."""
import argparse
import json
import pwd
from pathlib import Path
from run_d01_039 import PROJECT, DEFAULT_EDITOR, file_identity, runtime_run, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import runtime_has_task_error
from run_d08_01_release import LEDGER, now


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); out=a.output.resolve()
    ensure_runtime_output(out,pwd.getpwnam('unreal'))
    def assets():
        return {str(f.relative_to(PROJECT)):file_identity(f) for f in sorted((PROJECT/'Content').rglob('*'))
                if f.is_file() and f.suffix in ('.uasset','.umap')}
    before=assets()
    report=dict(task_id='D17-01',result='FAIL',runs=[],
        sources=[file_identity(PROJECT/p) for p in ('Content/Python/author_service_bay.py',
            'SourceAssets/Environment/service-bay.json','SourceAssets/Materials/ServiceSurface.hlsl',
            'SourceAssets/Materials/ServiceGround.hlsl')])
    try:
        for mode in ('author','readback'):
            previous=assets()
            command=['runuser','-u','unreal','--','env',f'BIELLA_D17_SERVICE_REPORT={out}/{mode}.json',
                str(DEFAULT_EDITOR.with_name('UnrealEditor-Cmd')),str(PROJECT/'BiellaGames.uproject'),
                '-run=pythonscript',f'-script={PROJECT}/Content/Python/author_service_bay.py',
                '-EnablePlugins=PythonScriptPlugin','-unattended','-nullrhi','-nosound','-nop4','-stdout','-FullStdOutLogOutput']
            if mode=='readback': command.append('-D17VerifyServiceBay')
            write_json(out/f'{mode}-command.json',command)
            run=runtime_run(command,out/f'{mode}.log',600); report['runs'].append(run)
            log=(out/f'{mode}.log').read_text(errors='replace')
            assert run['returncode']==0 and not run['timed_out'] and not runtime_has_task_error(log)
            assert 'D17_SERVICE_ASSETS COMPLETE' in log
            if mode=='readback':
                assert previous==assets(),'Readback changed assets'
                assert json.loads((out/'author.json').read_text())['meshes']==json.loads((out/'readback.json').read_text())['meshes']
        after=assets()
        assert all(after.get(k)==v for k,v in before.items() if not k.startswith('Content/Environment/ServiceBay/'))
        changed={k:v for k,v in after.items() if before.get(k)!=v}
        assert changed and all(k.startswith('Content/Environment/ServiceBay/') for k in changed)
        report.update(result='PASS',changed_assets=changed,preexisting_other_assets_unchanged=True)
    except Exception as exc:
        report['error']=str(exc)
        with LEDGER.open('a') as f: f.write(json.dumps(dict(task_id='D17-01',time=now(),type='service_asset_authoring',status='FAILED',diagnostics=str(exc),evidence=str(out)))+'\n')
    write_json(out/'validation.json',report)
    print(json.dumps(dict(result=report['result'],output=str(out),error=report.get('error'))))
    return 0 if report['result']=='PASS' else 1


if __name__=='__main__': raise SystemExit(main())
