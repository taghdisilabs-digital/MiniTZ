#!/usr/bin/env python3
"""Verify a missing global shader cache fails clearly in a private package copy."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import re
import shutil
from run_d01_039 import file_identity, write_json
from run_d01_042 import ensure_runtime_output
from run_d01_048 import launch
from run_d03_01_package import members


def withhold_global_cache(package, workspace, out, account):
    """Repack only loose pak entries; preserve all IoStore containers verbatim."""
    tool = Path('/opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealPak')
    pak = package/'BiellaGames/Content/Paks/BiellaGames-Linux.pak'
    original = workspace/'original'
    ensure_runtime_output(original, account)
    saved = original/pak.name
    pak.rename(saved)

    def extract(source, destination, name):
        # UE 5.8.2 PakFileUtilities.cpp:4096 uses a literal backslash join.
        # Alias that exact spelling inside this private workspace only.
        alias = source.parent.parent/(source.parent.name+'\\'+source.name)
        alias.symlink_to(source)
        result = launch(['runuser', '-u', 'unreal', '--', str(tool), str(source),
                         '-Extract', str(destination), '-unattended'], workspace,
                        out/f'{name}.log', 120)
        assert result['returncode'] == 0 and not result['timed_out'], f'{name} failed: {result}'
        assert list(destination.rglob('*')), f'{name} extracted no files'
        return result

    extracted = workspace/'extracted'
    extraction = extract(saved, extracted, 'extract-original')
    before = members(extracted)
    target = extracted/'Engine/GlobalShaderCache-VULKAN_SM5.bin'
    assert target.is_file(), 'Exact global shader cache missing from original pak'
    withheld = original/target.name
    target.rename(withheld)
    expected = {str(Path(x['path']).relative_to(extracted)): x['sha256']
                for x in before if Path(x['path']) != target}
    response = workspace/'repack-response.txt'
    response.write_text(''.join(f'"{extracted/name}" "../../../{name}" -compress\n'
                                for name in sorted(expected)))
    rebuild = workspace/'rebuilt'
    ensure_runtime_output(rebuild, account)
    rebuilt_pak = rebuild/pak.name
    repack = launch(['runuser', '-u', 'unreal', '--', str(tool), str(rebuilt_pak),
                     f'-Create={response}', '-unattended'], workspace, out/'repack.log', 120)
    assert repack['returncode'] == 0 and not repack['timed_out'], f'Repack failed: {repack}'
    readback = workspace/'repacked-readback'
    verification = extract(rebuilt_pak, readback, 'extract-repacked')
    actual = {str(Path(x['path']).relative_to(readback)): x['sha256'] for x in members(readback)}
    assert actual == expected, 'Repacked logical files differ beyond the withheld shader cache'
    shutil.copy2(rebuilt_pak, pak)
    os.chown(pak, account.pw_uid, account.pw_gid)
    return dict(original_pak=file_identity(saved), mutated_pak=file_identity(pak),
                withheld=file_identity(withheld), logical_files_before=before,
                logical_files_after=members(readback), preserved_logical_files=len(expected),
                extraction=extraction, repack=repack, readback=verification,
                engine_source=file_identity(Path('/opt/unreal/UE_5.8.2/Engine/Source/Developer/PakFileUtilities/Private/PakFileUtilities.cpp')),
                path_alias_reason='ExtractFilesFromPak line4096 literal backslash join on Linux')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--positive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    out, workspace = args.output.resolve(), args.workspace.resolve()
    assert not out.exists() and not workspace.exists(), 'Fresh control evidence/workspace required'
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(out, account)
    ensure_runtime_output(workspace, account)
    positive = json.loads((args.positive/'validation.json').read_text())
    assert positive['result'] == 'PASS', 'Requires qualified positive package run'
    stage = json.loads(Path(positive['stage']['path']).read_text())
    extraction = Path(stage['archive_readback'])
    report = dict(task_id='D03-01', result='FAIL', control='missing_global_shader_cache',
                  positive=file_identity(args.positive.resolve()/'validation.json'),
                  input=file_identity(Path(__file__).resolve()), archive=stage['archive'],
                  canonical_before=members(extraction))
    write_json(out/'validation.json', report)
    try:
        assert report['canonical_before'] == stage['readback_members'], 'Canonical extraction changed'
        assert file_identity(Path(stage['archive']['path'])) == stage['archive'], 'Canonical archive changed'
        package = workspace/'package'
        shutil.copytree(extraction/'Linux', package)
        # copytree preserves mode0700 directories but assigns the invoking owner.
        # Preserve their original runtime accessibility in this private copy.
        for path in [package, *package.rglob('*')]:
            os.chown(path, account.pw_uid, account.pw_gid)
        report['copy_before'] = members(package)
        expected = [(str(Path(x['path']).relative_to(extraction/'Linux')), x['sha256']) for x in stage['readback_members']]
        assert [(str(Path(x['path']).relative_to(package)), x['sha256']) for x in report['copy_before']] == expected, 'Control copy differs before mutation'
        report['mutation'] = withhold_global_cache(package, workspace, out, account)
        report['copy_after'] = members(package)
        changed = [before['path'] for before, after in zip(report['copy_before'], report['copy_after'])
                   if before != after]
        assert changed == [str(package/'BiellaGames/Content/Paks/BiellaGames-Linux.pak')], 'Unexpected package mutation'
        write_json(out/'validation.json', report)
        state = workspace/'state'
        ensure_runtime_output(state, account)
        for name in ('home', 'user', 'xdg-cache', 'xdg-config'):
            ensure_runtime_output(state/name, account)
        substitutions = {str(extraction/'Linux'): str(package), positive['state']: str(state),
                         str(Path(positive['state'])/'home'): str(state/'home'),
                         str(args.positive.resolve()): str(out)}
        command = [substitutions.get(value, value) for value in json.loads((args.positive/'command.json').read_text())]
        write_json(out/'command.json', command)
        report['runtime'] = launch(command, workspace, out/'runtime.stdout.log', 90)
        log = (out/'runtime.stdout.log').read_text(errors='replace')
        report['failure_diagnostics'] = [line for line in log.splitlines() if re.search(
            r'Failed to initialize ShaderCodeLibrary|Global shader library.*missing|Failed to open.*shader|global shader cache.*missing|GlobalShaderCache.*missing', line, re.I)]
        assert not report['runtime']['timed_out'] and report['runtime']['returncode'] != 0, 'Missing cache was not rejected promptly'
        assert report['failure_diagnostics'], 'Missing cache lacks a specific shader diagnostic'
        assert '**** TEST COMPLETE. EXIT CODE: 0 ****' not in log, 'Damaged package incorrectly passed gameplay'
        probe = json.loads((out/'isolation-probe.json').read_text())
        assert not any(probe['hidden_path_exists'].values()) and not probe['package_writable'], 'Control isolation failed'
        report['result'] = 'PASS'
    except (AssertionError, OSError, ValueError, KeyError) as error:
        report['error'] = str(error)
    finally:
        report['canonical_after'] = members(extraction)
        report['archive_after'] = file_identity(Path(stage['archive']['path']))
        if report['canonical_before'] != report['canonical_after'] or report['archive_after'] != report['archive']:
            report.update(result='FAIL', error='Canonical package changed')
        write_json(out/'validation.json', report)
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                        type='package_missing_shader_negative_control',
                                        status='EXPECTED_REJECTION_VERIFIED' if report['result'] == 'PASS' else 'CONTINUE',
                                        diagnostics=report.get('error', report.get('failure_diagnostics')), evidence=str(out)))+'\n')
    print(json.dumps(dict(result=report['result'], output=str(out), error=report.get('error'))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
