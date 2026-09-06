#!/usr/bin/env python3
"""Import six street meshes into the existing world and verify fresh saved readback."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
from run_d01_039 import PROJECT, DEFAULT_EDITOR, file_identity, runtime_run, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import runtime_has_task_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    ensure_runtime_output(out, pwd.getpwnam('unreal'))
    def identities():
        return [file_identity(p) for p in sorted((PROJECT/'Content').rglob('*'))
                if p.is_file() and p.suffix in ('.uasset', '.umap')]
    report = dict(task_id='D03-01', result='FAIL', runs=[], before=identities(),
        sources=[file_identity(p) for p in sorted((PROJECT/'SourceAssets/Architecture').glob('*')) if p.is_file()])
    try:
        for mode in ('author', 'readback'):
            before = identities()
            cmd = ['runuser','-u','unreal','--','env',f'BIELLA_D03_ARCHITECTURE_REPORT={out}/{mode}.json',
                str(DEFAULT_EDITOR.with_name('UnrealEditor-Cmd')),str(PROJECT/'BiellaGames.uproject'),
                '-run=pythonscript',f'-script={PROJECT}/Content/Python/import_street_blocks.py',
                '-EnablePlugins=PythonScriptPlugin','-unattended','-nullrhi','-nosound','-nop4','-stdout','-FullStdOutLogOutput']
            if mode == 'readback':
                cmd.append('-D03VerifyArchitecture')
            run = runtime_run(cmd, out/f'{mode}.log', 900)
            report['runs'].append(run)
            log = (out/f'{mode}.log').read_text(errors='replace')
            assert run['returncode'] == 0 and not run['timed_out'], mode+' process failed'
            assert 'D03_ARCHITECTURE COMPLETE' in log and not runtime_has_task_error(log), mode+' validation failed'
            saved = json.loads((out/f'{mode}.json').read_text())
            assert saved['result'] == 'PASS'
            if mode == 'readback':
                assert identities() == before, 'Readback modified saved assets'
                author = json.loads((out/'author.json').read_text())
                assert author['meshes'] == saved['meshes'], 'Saved mesh mismatch'
                assert [x['after'] for x in author['actors']] == [x['after'] for x in saved['actors']], 'Saved actor mismatch'
        report['result'] = 'PASS'
    except (OSError, ValueError, AssertionError) as exc:
        report['error'] = str(exc)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01',time=datetime.now(timezone.utc).isoformat(),
                type='architecture_authoring',status='CONTINUE',diagnostics=str(exc),evidence=str(out)))+'\n')
    report['after'] = identities()
    write_json(out/'validation.json', report)
    print(json.dumps(dict(result=report['result'], error=report.get('error'), output=str(out))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
