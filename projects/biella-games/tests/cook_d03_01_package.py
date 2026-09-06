#!/usr/bin/env python3
"""Cook an exact project snapshot with an initially empty, isolated filesystem DDC.

Does not remove or reuse prior cook/cache directories. Keep failed snapshots.
The native game build and current editor build must already have succeeded.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import shutil
import subprocess
import time
from run_d01_039 import PROJECT, DEFAULT_EDITOR, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output


def project_inputs():
    paths = [PROJECT/'BiellaGames.uproject']
    for directory in ('Source', 'Content', 'Config', 'Plugins'):
        paths.extend(f for f in (PROJECT/directory).rglob('*')
                     if f.is_file() and '__pycache__' not in f.parts)
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--game-build', type=Path, required=True)
    args = parser.parse_args()
    out, work = args.output.resolve(), args.workspace.resolve()
    assert not out.exists() and not work.exists(), 'Fresh output and workspace required'
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(out, account)
    ensure_runtime_output(work, account)
    snapshot, cache = work/'project', work/'cook-ddc'
    snapshot.mkdir()
    cache.mkdir()
    source = project_inputs()
    before = [file_identity(f) for f in source]
    report = dict(task_id='D03-01', result='FAIL', revision=source_revision(),
                  workspace=str(work), snapshot=str(snapshot), cache=str(cache),
                  inputs_before=before, editor=file_identity(DEFAULT_EDITOR),
                  editor_module=file_identity(PROJECT/'Binaries/Linux/libUnrealEditor-BiellaGames.so'),
                  cache_before=[], cache_graph='(Local)', capture_status='GENERATED_DRAFT')
    write_json(out/'validation.json', report)
    start = time.monotonic()
    try:
        build = json.loads((args.game_build/'result.json').read_text())
        assert build['result'] == 'PASS', 'Native game build not qualified'
        assert build['binary'] == file_identity(PROJECT/'Binaries/Linux/BiellaGames'), 'Game binary differs from build'
        assert json.loads((args.game_build/'inputs-after.json').read_text()) == [
            file_identity(f) for f in sorted((PROJECT/'Source').rglob('*')) if f.is_file()], 'Game build source differs'
        for f in source:
            dest = snapshot/f.relative_to(PROJECT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            assert file_identity(f)['sha256'] == file_identity(dest)['sha256'], f'Snapshot mismatch: {f}'
        binaries = snapshot/'Binaries/Linux'
        binaries.mkdir(parents=True)
        for name in ('BiellaGames', 'BiellaGames.target', 'libUnrealEditor-BiellaGames.so',
                     'UnrealEditor.modules', 'BiellaGamesEditor.target'):
            shutil.copy2(PROJECT/'Binaries/Linux'/name, binaries/name)
        report['snapshot_inputs'] = [file_identity(snapshot/f.relative_to(PROJECT)) for f in source]
        report['snapshot_binaries'] = [file_identity(f) for f in sorted(binaries.iterdir())]
        subprocess.run(['chown', '-R', f'{account.pw_uid}:{account.pw_gid}', str(work)], check=True)
        command = ['runuser', '-u', account.pw_name, '--', str(DEFAULT_EDITOR),
                   str(snapshot/'BiellaGames.uproject'), '-run=Cook', '-TargetPlatform=Linux',
                   '-CookAll', '-unversioned', '-unattended', '-nop4', '-nullrhi', '-nosound',
                   '-stdout', '-FullStdOutLogOutput', '-DDC=(Local)', f'-LocalDataCachePath={cache}',
                   f'-AbsLog={out}/cook.engine.log']
        write_json(out/'command.json', command)
        write_json(out/'validation.json', report)
        with (out/'cook.stdout.log').open('xb') as stream:
            result = subprocess.run(command, cwd=snapshot, stdout=stream, stderr=subprocess.STDOUT)
        report['returncode'] = result.returncode
        assert result.returncode == 0, 'Cook failed; inspect native logs'
        log = (out/'cook.stdout.log').read_text(errors='replace')
        assert str(cache) in log, 'Isolated DDC path not observed'
        assert 'success - 0 error(s)' in log.lower(), 'Cook did not report successful zero-error completion'
        report['cooked_files'] = [file_identity(f) for f in sorted((snapshot/'Saved/Cooked/Linux').rglob('*')) if f.is_file()]
        assert report['cooked_files'], 'No cooked output'
        report['result'] = 'PASS'
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
    finally:
        report['inputs_after'] = [file_identity(f) for f in project_inputs()]
        if report['inputs_before'] != report['inputs_after']:
            report.update(result='FAIL', error='Project inputs changed during cook')
        report['elapsed_seconds'] = time.monotonic()-start
        report['cache_after'] = [file_identity(f) for f in sorted(cache.rglob('*')) if f.is_file()]
        write_json(out/'validation.json', report)
        if report['result'] != 'PASS':
            with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                            type='isolated_cook', status='CONTINUE',
                                            diagnostics=report.get('error'), evidence=str(out)))+'\n')
    print(json.dumps(dict(result=report['result'], output=str(out), error=report.get('error'))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
