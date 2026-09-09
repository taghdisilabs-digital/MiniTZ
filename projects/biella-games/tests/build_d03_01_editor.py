#!/usr/bin/env python3
"""Incrementally build the native editor modules and preserve exact source/binary identities."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from run_d01_039 import PROJECT, file_identity, source_revision, write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--task-id',choices=('D03-01','D08-01','D17-01','D17-02'),default='D03-01')
    args=parser.parse_args()
    out=args.output.resolve()
    out.mkdir(exist_ok=False)
    def inputs():
        return [file_identity(p) for p in sorted((PROJECT/'Source').rglob('*')) if p.is_file()] + [file_identity(PROJECT/'BiellaGames.uproject'),file_identity(Path(__file__))]
    cmd=['/opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh','BiellaGamesEditor','Linux','Development',f'-Project={PROJECT}/BiellaGames.uproject','-WaitMutex']
    write_json(out/'command.json',cmd)
    report=dict(task_id=args.task_id,result='RUNNING',revision=source_revision(),inputs_before=inputs())
    write_json(out/'validation.json',report)
    with (out/'build.log').open('w') as stream:
        run=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT)
    report.update(result='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,inputs_after=inputs())
    if report['inputs_before']!=report['inputs_after']:
        report.update(result='FAIL',error='Source changed during build')
    if report['result']=='PASS':
        # UBT inherits the controller's private umask; the separate native
        # runtime account must be able to load these nonsecret project modules.
        for p in (PROJECT/'Binaries/Linux').glob('libUnrealEditor-Biella*.so'):
            os.chmod(p,p.stat().st_mode | 0o444)
        report['binaries']=[file_identity(p) for p in sorted((PROJECT/'Binaries/Linux').glob('*')) if p.is_file() and p.suffix in ('.so','.modules','.target')]
    else:
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id=args.task_id,time=datetime.now(timezone.utc).isoformat(),type='editor_build',status='CONTINUE',diagnostics=report.get('error','Native build failed'),evidence=str(out)))+'\n')
    write_json(out/'validation.json',report)
    print(json.dumps(dict(result=report['result'],returncode=run.returncode,output=str(out))))
    return 0 if report['result']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
