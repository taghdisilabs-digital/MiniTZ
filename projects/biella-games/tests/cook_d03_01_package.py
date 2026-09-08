#!/usr/bin/env python3
"""Cook an exact snapshot with an isolated filesystem DDC, empty by default.

Does not remove or reuse prior cook/cache directories. Keep failed snapshots.
An explicit validated DDC seed may be copied for an affected-scope recook.
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
    parser.add_argument('--task-id', choices=('D03-01', 'D08-01', 'D17-01'), default='D03-01')
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--game-build', type=Path, required=True)
    parser.add_argument('--editor-build', type=Path, help='Require exact source and module bytes from an editor build receipt')
    parser.add_argument('--ddc-seed', type=Path, help='Copy exact cache bytes from a successful cook validation; never reuse its cooked output')
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
    report = dict(task_id=args.task_id, result='FAIL', revision=source_revision(),
                  workspace=str(work), snapshot=str(snapshot), cache=str(cache),
                  inputs_before=before, editor=file_identity(DEFAULT_EDITOR),
                  editor_module=file_identity(PROJECT/'Binaries/Linux/libUnrealEditor-BiellaGames.so'),
                  cache_before=[], cache_graph='(Local)', capture_status='GENERATED_DRAFT')
    write_json(out/'validation.json', report)
    start = time.monotonic()
    try:
        if args.ddc_seed:
            seed_path = args.ddc_seed.resolve()
            seed = json.loads(seed_path.read_text())
            assert seed['result'] == 'PASS' and seed['editor'] == report['editor']
            seed_root = Path(seed['cache']).resolve()
            # Copy filesystem DDC records/blobs only. Zen contains cooked
            # output, authentication and mutable process/log state; each new
            # cook must build that independently. TestData is a speed probe.
            seed_rows = [row for row in seed['cache_after']
                         if Path(row['path']).relative_to(seed_root).parts[0] in ('Buckets', 'Content')]
            assert seed_rows, 'Seed has no verified filesystem cache files'
            assert seed_root != cache.resolve() and not cache.is_relative_to(seed_root)
            for row in seed_rows:
                source_cache = Path(row['path'])
                assert source_cache.resolve().is_relative_to(seed_root)
                assert file_identity(source_cache) == row, 'Seed cache bytes changed'
                target_cache = cache / source_cache.relative_to(seed_root)
                target_cache.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_cache, target_cache)
                copied = file_identity(target_cache)
                assert all(copied[k] == row[k] for k in ('sha256', 'bytes'))
            report['cache_seed'] = dict(validation=file_identity(seed_path),
                source_cache=str(seed_root), copied_files=len(seed_rows),
                copied_bytes=sum(row['bytes'] for row in seed_rows),
                copied_roots=['Buckets', 'Content'], excluded_roots=['Zen', 'TestData'],
                all_copied_digests_verified=True, cooked_outputs_reused=False)
            report['cache_before'] = [file_identity(f) for f in sorted(cache.rglob('*')) if f.is_file()]
        build = json.loads((args.game_build/'result.json').read_text())
        assert build['result'] == 'PASS', 'Native game build not qualified'
        assert build['binary'] == file_identity(PROJECT/'Binaries/Linux/BiellaGames'), 'Game binary differs from build'
        assert json.loads((args.game_build/'inputs-after.json').read_text()) == [
            file_identity(f) for f in sorted((PROJECT/'Source').rglob('*')) if f.is_file()], 'Game build source differs'
        if args.editor_build:
            editor_build = json.loads((args.editor_build/'validation.json').read_text())
            assert editor_build['result'] == 'PASS' and editor_build['returncode'] == 0
            assert editor_build['inputs_before'] == editor_build['inputs_after']
            assert [r for r in editor_build['inputs_after'] if '/Source/' in r['path']] == [
                file_identity(f) for f in sorted((PROJECT/'Source').rglob('*')) if f.is_file()], 'Editor build source differs'
            for record in editor_build['binaries']:
                assert file_identity(Path(record['path'])) == record, 'Editor build output differs'
            report['editor_build'] = file_identity(args.editor_build/'validation.json')
        for f in source:
            dest = snapshot/f.relative_to(PROJECT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            assert file_identity(f)['sha256'] == file_identity(dest)['sha256'], f'Snapshot mismatch: {f}'
        binaries = snapshot/'Binaries/Linux'
        binaries.mkdir(parents=True)
        module_manifest = json.loads((PROJECT/'Binaries/Linux/UnrealEditor.modules').read_text())
        module_names = list(module_manifest['Modules'].values())
        assert module_names and all(Path(name).name == name and name.endswith('.so') for name in module_names)
        for name in ('BiellaGames', 'BiellaGames.target', 'UnrealEditor.modules', 'BiellaGamesEditor.target', *module_names):
            shutil.copy2(PROJECT/'Binaries/Linux'/name, binaries/name)
            assert file_identity(PROJECT/'Binaries/Linux'/name)['sha256'] == file_identity(binaries/name)['sha256']
        report['editor_modules'] = [file_identity(PROJECT/'Binaries/Linux'/name) for name in module_names]
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
        for record in report.get('editor_modules', []):
            if file_identity(Path(record['path'])) != record:
                report.update(result='FAIL', error='Editor module changed during cook')
        report['elapsed_seconds'] = time.monotonic()-start
        report['cache_after'] = [file_identity(f) for f in sorted(cache.rglob('*')) if f.is_file()]
        write_json(out/'validation.json', report)
        if report['result'] != 'PASS':
            with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(task_id=args.task_id, time=datetime.now(timezone.utc).isoformat(),
                                            type='isolated_cook', status='CONTINUE',
                                            diagnostics=report.get('error'), evidence=str(out)))+'\n')
    print(json.dumps(dict(result=report['result'], output=str(out), error=report.get('error'))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
