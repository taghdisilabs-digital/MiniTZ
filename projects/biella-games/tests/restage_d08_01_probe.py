#!/usr/bin/env python3
"""Reuse an exact cook after the bounded D08 settings-probe filename fix.

No content is recooked and no original source, binary or cook evidence is
overwritten. The replacement game executable must have a passing native build.
The only permitted source difference is the non-reflected automation probe.
"""
import argparse
from pathlib import Path
import pwd
import shutil
import subprocess

import run_d08_01_release as release
from run_d01_042 import ensure_runtime_output


PROBE = Path('Source/BiellaGames/Private/Tests/BiellaReleaseSettingsTest.cpp')
OLD = '    const FString SettingsPath = FPaths::ConvertRelativePathToFull(GGameUserSettingsIni);'
NEW = '''    // UE 5.8 uses a known-config key ("GameUserSettings"), not a filename,
    // in GGameUserSettingsIni. Resolve its generated destination explicitly.
    const FString SettingsPath = FPaths::ConvertRelativePathToFull(
        FConfigCacheIni::GetDestIniFilename(*GGameUserSettingsIni, nullptr, *FPaths::GeneratedConfigDir()));'''


def prepare(cook_path, build_path, work, output):
    cook = release.read(cook_path)
    build = release.read(build_path)
    release.require(cook['result'] == build['result'] == 'PASS', 'Cook and native build must pass')
    release.require(not work.exists() and not output.exists(), 'Fresh evidence and workspace required')
    original = Path(cook['snapshot'])
    changed = []
    for record in cook['snapshot_inputs'] + cook['snapshot_binaries'] + cook['cooked_files']:
        release.require(release.identity(record['path']) == record, 'Original cook bytes changed')
    for record in cook['inputs_before']:
        if release.identity(record['path']) != record:
            changed.append(Path(record['path']).relative_to(release.PROJECT))
    release.require(changed == [PROBE], 'Only the D08 automation probe may differ from the cook')
    before = (original / PROBE).read_text()
    after = (release.PROJECT / PROBE).read_text()
    release.require(before.count(OLD) == 1 and before.replace(OLD, NEW) == after,
                    'Source change differs from the reviewed known-config filename fix')
    source = release.read(build_path.parent / 'inputs-after.json')
    actual = [release.identity(p) for p in sorted((release.PROJECT / 'Source').rglob('*')) if p.is_file()]
    release.require(source == actual, 'Game build source differs from current source')
    for key in ('binary', 'receipt'):
        release.require(release.identity(build[key]['path']) == build[key], 'Game build output changed')
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(work, account)
    ensure_runtime_output(output, account)
    snapshot = work / 'project'
    shutil.copytree(original, snapshot)
    shutil.copy2(release.PROJECT / PROBE, snapshot / PROBE)
    for key in ('binary', 'receipt'):
        path = Path(build[key]['path'])
        shutil.copy2(path, snapshot / path.relative_to(release.PROJECT))
    subprocess.run(['chown', '-R', f'{account.pw_uid}:{account.pw_gid}', str(work)], check=True)
    remap = lambda row: release.identity(snapshot / Path(row['path']).relative_to(original))
    inputs = [release.identity(row['path']) for row in cook['inputs_before']]
    binaries = [remap(row) for row in cook['snapshot_binaries']]
    cooked = [remap(row) for row in cook['cooked_files']]
    release.require([(r['sha256'], r['bytes']) for r in cooked] ==
                    [(r['sha256'], r['bytes']) for r in cook['cooked_files']], 'Cooked content copy differs')
    report = dict(task_id='D08-01', result='PASS', observed=release.now(),
        scope='CONTENT_REUSE_WITH_REBUILT_AUTOMATION_PROBE_ONLY', recook_performed=False,
        original_cook=release.identity(cook_path), native_build=release.identity(build_path),
        reason='Known-config key was incorrectly treated as an on-disk filename in D08 automation only. No reflected type, gameplay, content, configuration, plugin or shader input changed.',
        changed_source=[dict(path=str(PROBE), before=release.identity(original / PROBE),
                             after=release.identity(release.PROJECT / PROBE))],
        workspace=str(work), snapshot=str(snapshot), cache=cook['cache'],
        inputs_before=inputs, inputs_after=inputs,
        snapshot_inputs=[remap(row) for row in cook['snapshot_inputs']],
        snapshot_binaries=binaries, cooked_files=cooked,
        implementation=release.identity(__file__))
    release.write(output / 'validation.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('cook', 'build', 'workspace', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.cook.resolve(), args.build.resolve(), args.workspace.resolve(), args.output.resolve())
        print(release.json.dumps({'result': result['result'], 'scope': result['scope']}))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        with release.LEDGER.open('a') as stream:
            stream.write(release.json.dumps(dict(task_id='D08-01', time=release.now(),
                type='restage_probe', status='CONTINUE', diagnostics=str(error)[:2000])) + '\n')
        raise
