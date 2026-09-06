#!/usr/bin/env python3
"""Build a byte-verified startup candidate from unchanged qualified cooked content.

This is explicitly a native-binary/descriptor patch candidate, not a fresh cook.
All other archive members and current Content/Config inputs must match the cook.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
from run_d01_039 import PROJECT, file_identity, write_json
from run_d03_01_package import members


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--archive', type=Path, required=True)
    a = p.parse_args()
    out, workspace = a.output.resolve(), a.workspace.resolve()
    out.mkdir(parents=True, exist_ok=False)
    workspace.mkdir(parents=True, exist_ok=False)
    report = dict(task_id='D03-01', result='FAIL', capture_status='GENERATED_DRAFT',
                  scope='Native executable and descriptor patch over byte-identical qualified cooked content; not a fresh cook')
    try:
        base = json.loads((PROJECT/'Build/Presentation/package-sm6-stage-01/validation.json').read_text())
        cook = json.loads((PROJECT/'Build/Presentation/package-sm6-cook-01/validation.json').read_text())
        build = json.loads((a.build/'result.json').read_text())
        assert base['result'] == cook['result'] == build['result'] == 'PASS'
        report['build'] = file_identity(a.build.resolve()/'result.json')
        assert file_identity(Path(build['binary']['path'])) == build['binary']
        for entry in json.loads((a.build/'inputs-after.json').read_text()):
            assert file_identity(Path(entry['path'])) == entry, entry['path']
        report['descriptor'] = file_identity(PROJECT/'BiellaGames.uproject')
        report['reused_cook_inputs'] = [x for x in cook['inputs_before'] if Path(x['path']).relative_to(PROJECT).parts[0] in ('Content', 'Config')]
        assert report['reused_cook_inputs']
        for entry in report['reused_cook_inputs']:
            assert file_identity(Path(entry['path'])) == entry, entry['path']
        expected_paths = {x['path'] for x in report['reused_cook_inputs']}
        # The cook snapshots all Content/Config files; new assets/config cannot hide here.
        current_paths = {str(f) for root in ('Content', 'Config') for f in (PROJECT/root).rglob('*')
                         if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc'}
        assert current_paths == expected_paths, 'Cook input set changed'
        extraction = Path(base['archive_readback'])
        assert members(extraction) == base['readback_members']
        assert file_identity(Path(base['archive']['path'])) == base['archive']
        report['base_archive'] = base['archive']
        candidate = workspace/'candidate'
        shutil.copytree(extraction, candidate, symlinks=True)
        binary_rel = Path('Linux/BiellaGames/Binaries/Linux/BiellaGames')
        shutil.copy2(build['binary']['path'], candidate/binary_rel)
        patch = workspace/'patch'
        patch.mkdir(mode=0o777)
        patch.chmod(0o777)
        # A standalone .pak is rejected by this IoStore runtime without its own
        # .utoc. Repack only the existing non-UObject pak, preserving its paired
        # .utoc/.ucas and verifying every extracted member before/after.
        pak_rel = Path('Linux/BiellaGames/Content/Paks/BiellaGames-Linux.pak')
        native = '/opt/unreal/UE_5.8.2/Engine/Binaries/Linux/UnrealPak'
        prefix = ['bwrap', '--ro-bind', '/', '/', '--dev-bind', '/dev', '/dev', '--tmpfs', '/tmp',
                  '--bind', str(patch), '/tmp/patch',
                  '--ro-bind', str(extraction/pak_rel), '/tmp/patch/base.pak',
                  '--ro-bind', str(extraction/pak_rel), '/tmp/patch\\base.pak']

        def pak_tool(label, args, aliases=()):
            command = prefix + list(aliases) + ['--', 'runuser', '-u', 'unreal', '--', native] + args
            write_json(out/f'{label}-command.json', command)
            with (out/f'{label}.log').open('xb') as stream:
                result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
            assert result.returncode == 0, f'{label} native process failed'
            log = (out/f'{label}.log').read_text(errors='replace')
            assert ': Error:' not in log, f'{label} native tool error'
            return log

        pak_tool('base-extract', ['/tmp/patch/base.pak', '-Extract', '/tmp/patch/base'])
        source = patch/'base'
        assert (source/'BiellaGames/BiellaGames.uproject').is_file(), 'Base mount layout differs'
        before = {str(f.relative_to(source)): file_identity(f) for f in source.rglob('*') if f.is_file()}
        report['base_pak_members'] = before
        modified = patch/'modified'
        shutil.copytree(source, modified)
        shutil.copy2(PROJECT/'BiellaGames.uproject', modified/'BiellaGames/BiellaGames.uproject')
        for f in modified.rglob('*'):
            f.chmod(0o755 if f.is_dir() else 0o644)
        modified.chmod(0o755)
        response = patch/'response.txt'
        response.write_text(''.join(f'"/tmp/patch/modified/{name}" "../../../{name}"\n' for name in sorted(before)))
        response.chmod(0o644)
        log = pak_tool('pak-create', ['/tmp/patch/BiellaGames-Linux.pak', '-Create=/tmp/patch/response.txt'])
        assert f'Added {len(before)} entries' in log, 'Rebuilt pak input count differs'
        pak_tool('pak-readback', ['/tmp/patch/BiellaGames-Linux.pak', '-Extract', '/tmp/patch/readback'],
                 ['--ro-bind', str(patch/'BiellaGames-Linux.pak'), '/tmp/patch\\BiellaGames-Linux.pak'])
        read = patch/'readback'
        after = {str(f.relative_to(read)): file_identity(f) for f in read.rglob('*') if f.is_file()}
        assert before.keys() == after.keys(), 'Rebuilt pak member set differs'
        changed = [name for name in before if (before[name]['sha256'], before[name]['bytes']) !=
                   (after[name]['sha256'], after[name]['bytes'])]
        assert changed == ['BiellaGames/BiellaGames.uproject'], changed
        assert (read/'BiellaGames/BiellaGames.uproject').read_bytes() == (PROJECT/'BiellaGames.uproject').read_bytes()
        report.update(pak_readback_members=after, changed_pak_members=changed)
        shutil.copy2(patch/'BiellaGames-Linux.pak', candidate/pak_rel)
        report['repacked_pak'] = file_identity(candidate/pak_rel)
        report['changed_members'] = []
        for entry in base['readback_members']:
            relative = Path(entry['path']).relative_to(extraction)
            current = file_identity(candidate/relative)
            if current['sha256'] != entry['sha256'] or current['bytes'] != entry['bytes']:
                report['changed_members'].append(str(relative))
        assert report['changed_members'] == [str(binary_rel), str(pak_rel)]
        assert len(members(candidate)) == len(base['readback_members'])
        archive = a.archive.resolve()
        archive.parent.mkdir(parents=True, exist_ok=True)
        assert not archive.exists()
        subprocess.run(['tar', '--zstd', '-cf', str(archive), '-C', str(candidate), 'Linux'], check=True)
        readback = workspace/'archive-readback'
        readback.mkdir()
        subprocess.run(['tar', '--zstd', '-xf', str(archive), '-C', str(readback)], check=True)
        account = pwd.getpwnam('unreal')
        # Preserve archive modes, which include 0700 paths, for the runtime user.
        for path in [readback, *readback.rglob('*')]:
            os.chown(path, account.pw_uid, account.pw_gid, follow_symlinks=False)
        normalized = lambda root: {str(Path(x['path']).relative_to(root)): (x['sha256'], x['bytes']) for x in members(root)}
        assert normalized(candidate) == normalized(readback), 'Archive readback mismatch'
        assert members(extraction) == base['readback_members'], 'Baseline changed'
        assert file_identity(PROJECT/'BiellaGames.uproject') == report['descriptor']
        report.update(result='PASS', archive=file_identity(archive), archive_readback=str(readback),
                      readback_members=members(readback), destination=str(candidate))
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
    write_json(out/'validation.json', report)
    if report['result'] != 'PASS':
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                        type='loading_candidate_stage', status='CONTINUE', diagnostics=report['error'], evidence=str(out)))+'\n')
    print(json.dumps(dict(result=report['result'], error=report.get('error'), output=str(out))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
