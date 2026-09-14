#!/usr/bin/env python3
"""Rebuild affected native HLODs and read back the saved existing world."""
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
    report = dict(task_id='D03-01', result='FAIL', before=identities(), runs=[],
                  scripts=[file_identity(Path(__file__)), file_identity(PROJECT/'Content/Python/author_open_world.py'),
                           file_identity(PROJECT/'Content/Python/build_production_surfaces.py')])
    editor = str(DEFAULT_EDITOR.with_name('UnrealEditor-Cmd'))
    project = str(PROJECT/'BiellaGames.uproject')
    try:
        commands = [
            ('hlod', ['runuser','-u','unreal','--',editor,project,'/Game/Maps/BiellaOpenWorldMap',
                '-run=WorldPartitionBuilderCommandlet','-Builder=WorldPartitionHLODsBuilder',
                '-SetupHLODs','-BuildHLODs','-AllowCommandletRendering', '-nullrhi',
                '-unattended','-nosound','-nop4','-stdout','-FullStdOutLogOutput',f'-AbsLog={out}/hlod.engine.log']),
            ('readback', ['runuser','-u','unreal','--','env', f'BIELLA_WORLD_READBACK_REPORT={out}/world.json',
                editor, project, '-run=pythonscript',f'-script={PROJECT}/Content/Python/author_open_world.py',
                '-D02VerifyOpenWorld','-EnablePlugins=PythonScriptPlugin','-nullrhi',
                '-unattended','-nosound','-nop4','-stdout','-FullStdOutLogOutput']),
            ('surfaces', ['runuser','-u','unreal','--','env', f'BIELLA_D03_SURFACE_REPORT={out}/surfaces.json',
                editor, project, '-run=pythonscript',f'-script={PROJECT}/Content/Python/build_production_surfaces.py',
                '-D03VerifySurfaces','-EnablePlugins=PythonScriptPlugin','-nullrhi',
                '-unattended','-nosound','-nop4','-stdout','-FullStdOutLogOutput'])]
        for mode, cmd in commands:
            before = identities()
            run = runtime_run(cmd, out/f'{mode}.log', 900)
            report['runs'].append(run)
            log = (out/f'{mode}.log').read_text(errors='replace')
            assert run['returncode'] == 0 and not run['timed_out'], mode+' process failed'
            assert not runtime_has_task_error(log), mode+' logged an error'
            if mode == 'readback':
                assert 'D02_OPEN_WORLD PASS' in log
                assert identities() == before, 'Readback changed saved content'
                saved = json.loads((out/'world.json').read_text())
                assert saved['result'] == 'PASS' and saved['read_only']
                assert any('/MIC_Facade' in mat for item in saved['built_hlod_geometry'] for mat in item['materials']), 'HLODs lack facade materials'
            if mode == 'surfaces':
                assert 'D03_SURFACE COMPLETE' in log
                assert identities() == before, 'Surface readback changed saved content'
                saved = json.loads((out/'surfaces.json').read_text())
                assert saved['result'] == 'PASS' and saved['mode'] == 'readback'
        report['result'] = 'PASS'
    except (OSError, ValueError, AssertionError) as exc:
        report['error'] = str(exc)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                type='architecture_hlod',status='CONTINUE',diagnostics=str(exc),evidence=str(out)))+'\n')
    report['after'] = identities()
    write_json(out/'validation.json',report)
    print(json.dumps(dict(result=report['result'],error=report.get('error'),output=str(out))))
    return 0 if report['result']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
