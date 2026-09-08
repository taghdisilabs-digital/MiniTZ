#!/usr/bin/env python3
"""Stage and archive the verified isolated D03 cook, preserving exact bytes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import shutil
import subprocess
import time
from run_d01_039 import file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output


def members(root):
    return [file_identity(f) for f in sorted(root.rglob('*')) if f.is_file()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-id', choices=('D03-01', 'D08-01', 'D17-01'), default='D03-01')
    parser.add_argument('--cook', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--dependencies', type=Path, required=True)
    args = parser.parse_args()
    out, archive = args.output.resolve(), args.archive.resolve()
    assert not out.exists() and not archive.exists(), 'Fresh evidence and archive required'
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(out, account)
    cook = json.loads((args.cook/'validation.json').read_text())
    assert cook['result'] == 'PASS', 'Isolated cook not qualified'
    snapshot = Path(cook['snapshot'])
    destination = Path(cook['workspace'])/f'{out.name}-archive'
    assert not destination.exists(), 'Fresh stage required'
    report = dict(task_id=args.task_id, result='FAIL', revision=source_revision(),
                  cook=file_identity(args.cook.resolve()/'validation.json'),
                  destination=str(destination), capture_status='GENERATED_DRAFT')
    write_json(out/'validation.json', report)
    start = time.monotonic()
    try:
        for item in cook['snapshot_inputs'] + cook['snapshot_binaries'] + cook['cooked_files']:
            assert file_identity(Path(item['path'])) == item, f'Cook input/output changed: {item["path"]}'
        temporary = Path(cook['workspace'])/f'{out.name}-tmp'
        assert not temporary.exists(), 'Fresh UAT temporary directory required'
        ensure_runtime_output(temporary, account)
        report['uat_temporary'] = str(temporary)
        saved_directory = temporary/'AutomationToolSaved'
        ensure_runtime_output(saved_directory, account)
        report['uat_saved_directory'] = str(saved_directory)
        zen_data = Path(cook['cache'])/'Zen'
        assert zen_data.is_dir(), 'Observed cook Zen store missing'
        stage_directory = Path(cook['workspace'])/f'{out.name}-staged'
        assert not stage_directory.exists(), 'Fresh staging directory required'
        report.update(zen_data=str(zen_data), stage_directory=str(stage_directory))
        command = ['runuser', '-u', account.pw_name, '--', 'env', f'TMPDIR={temporary}',
                   f'uebp_EngineSavedFolder={saved_directory}',
                   # FUnixPlatformMisc replaces '-' with '_' before secure_getenv.
                   f'UE_ZenSubprocessDataPath={zen_data}',
                   '/opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/RunUAT.sh', 'BuildCookRun',
                   f'-project={snapshot}/BiellaGames.uproject', '-noP4', '-platform=Linux',
                   '-clientconfig=Development', '-skipbuild', '-skipcook', '-stage', '-pak',
                   '-iostore', '-zenstore', '-nodebuginfo', f'-stagingdirectory={stage_directory}',
                   '-archive', f'-archivedirectory={destination}', '-utf8output']
        write_json(out/'command.json', command)
        with (out/'stage.log').open('xb') as stream:
            result = subprocess.run(command, cwd=snapshot, stdout=stream, stderr=subprocess.STDOUT)
        report['returncode'] = result.returncode
        assert result.returncode == 0, 'UAT stage failed; inspect stage.log'
        assert f'Found subprocess environment variable UE-ZenSubprocessDataPath={zen_data}' in (out/'stage.log').read_text(), 'Staging did not select the preserved cook Zen store'
        assert (destination/'Linux/BiellaGames.sh').is_file(), 'Missing package launcher'
        packaged_binary = destination/'Linux/BiellaGames/Binaries/Linux/BiellaGames'
        assert file_identity(packaged_binary)['sha256'] == file_identity(snapshot/'Binaries/Linux/BiellaGames')['sha256'], 'Staged game binary differs'
        dependency = json.loads((args.dependencies/'validation.json').read_text())
        assert dependency['result'] == 'PASS', 'Engine dependency repair not qualified'
        notices = destination/'Linux/ThirdPartyNotices'
        notices.mkdir()
        for item in dependency['licenses']:
            source = Path(item['path'])
            assert file_identity(source) == item, 'Dependency license differs'
            shutil.copy2(source, notices/source.name)
        report['dependencies'] = file_identity(args.dependencies.resolve()/'validation.json')
        report['members'] = members(destination)
        assert report['members'], 'Empty package'
        archive.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['tar', '--zstd', '-cf', str(archive), '-C', str(destination), 'Linux'], check=True)
        report['archive'] = file_identity(archive)
        extraction = destination.parent/'archive-readback'
        extraction.mkdir()
        subprocess.run(['tar', '--zstd', '-xf', str(archive), '-C', str(extraction)], check=True)
        report['readback_members'] = members(extraction)
        expected = [(str(Path(x['path']).relative_to(destination)), x['sha256'], x['bytes']) for x in report['members']]
        actual = [(str(Path(x['path']).relative_to(extraction)), x['sha256'], x['bytes']) for x in report['readback_members']]
        assert expected == actual, 'Archive readback differs from stage'
        report['archive_readback'] = str(extraction)
        report['result'] = 'PASS'
    except (AssertionError, OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
    finally:
        report['elapsed_seconds'] = time.monotonic()-start
        write_json(out/'validation.json', report)
        if report['result'] != 'PASS':
            with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(task_id=args.task_id, time=datetime.now(timezone.utc).isoformat(),
                                            type='package_stage', status='CONTINUE', diagnostics=report.get('error'),
                                            evidence=str(out)))+'\n')
    print(json.dumps(dict(result=report['result'], output=str(out), error=report.get('error'))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
