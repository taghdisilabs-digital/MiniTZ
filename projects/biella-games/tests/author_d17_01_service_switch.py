#!/usr/bin/env python3
"""Author the switch graph, then verify its saved bytes in a fresh commandlet."""
import argparse
import json
from pathlib import Path
import pwd
from run_d01_039 import PROJECT, DEFAULT_EDITOR, file_identity, runtime_run, write_json
from run_d01_042 import ensure_runtime_output
from run_d01_043 import finalize_log
from run_d02_01 import runtime_has_task_error
from run_d08_01_release import LEDGER, now


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); out=args.output.resolve()
    assert not out.exists()
    ensure_runtime_output(out,pwd.getpwnam('unreal'))
    def assets():
        return {str(p.relative_to(PROJECT)):file_identity(p) for p in sorted((PROJECT/'Content').rglob('*'))
                if p.is_file() and p.suffix in ('.uasset','.umap')}
    before=assets()
    report=dict(task_id='D17-01',result='FAIL',runs=[],sources=[file_identity(PROJECT/p) for p in (
        'Content/Python/author_service_switch.py','SourceAssets/Materials/ServiceSwitch.hlsl')])
    try:
        for mode in ('author','readback'):
            previous=assets()
            command=['runuser','-u','unreal','--','env',f'BIELLA_D17_SWITCH_REPORT={out}/{mode}.json',
                str(DEFAULT_EDITOR.with_name('UnrealEditor-Cmd')),str(PROJECT/'BiellaGames.uproject'),
                '-run=pythonscript',f'-script={PROJECT}/Content/Python/author_service_switch.py',
                '-EnablePlugins=PythonScriptPlugin','-unattended','-nullrhi','-nosound','-nop4','-stdout','-FullStdOutLogOutput']
            if mode=='readback': command.append('-D17VerifyServiceSwitch')
            write_json(out/f'{mode}-command.json',command)
            run=runtime_run(command,out/f'{mode}.log',600)
            run['log_finalization']=finalize_log(out/f'{mode}.log')
            run['log']=file_identity(out/f'{mode}.log')
            report['runs'].append(run)
            assert run['log_finalization']['closed'],'Commandlet log still has a writer'
            log=(out/f'{mode}.log').read_text(errors='replace')
            assert run['returncode']==0 and not run['timed_out'] and not runtime_has_task_error(log)
            assert 'D17_SWITCH_ASSET COMPLETE' in log
            if mode=='readback': assert previous==assets(),'Readback changed assets'
        after=assets(); changed={k:v for k,v in after.items() if before.get(k)!=v}
        assert set(changed)=={'Content/Environment/ServiceBay/M_ServiceSwitch.uasset'},sorted(changed)
        assert all(after[k]==v for k,v in before.items() if k not in changed)
        report.update(result='PASS',changed_assets=changed,preexisting_other_assets_unchanged=True)
    except Exception as error:
        report['error']=repr(error)
        with LEDGER.open('a') as f: f.write(json.dumps(dict(task_id='D17-01',time=now(),type='switch_asset_authoring',
            status='CONTINUE',diagnostics=repr(error),evidence=str(out)))+'\n')
    write_json(out/'validation.json',report)
    print(json.dumps(dict(result=report['result'],output=str(out),error=report.get('error'))))
    return int(report['result']!='PASS')


if __name__=='__main__': raise SystemExit(main())
