#!/usr/bin/env python3
"""Transfer the retained material snapshot, not Linux binaries, to a Windows build resource.

ZIP/readback and PowerShell source checks are platform-neutral preparation only.
No SDK, compile, native installer, gameplay or release-candidate pass is inferred.
"""
import argparse
from pathlib import Path
import subprocess
import zipfile

import run_d08_01_release as release


def prepare(workspace, output, archive_directory, powershell):
    release.require(not workspace.exists() and not output.exists(), 'Fresh task workspace and output required')
    workspace.mkdir(parents=True)
    output.mkdir(parents=True)
    archive_directory.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'biella.d08.source_transfer_preparation/v1', 'task_id': 'D08-01',
              'result': 'FAIL', 'scope': 'SOURCE_TRANSFER_ONLY', 'release_candidate': False,
              'observed': release.now(), 'implementation': release.identity(__file__),
              'powershell': release.identity(powershell), 'cases': []}
    try:
        project = release.PROJECT
        source_path = release.ROOT / 'source-build-manifest.json'
        source = release.read(source_path)
        rows = source['material_inputs']
        release.require(release.digest(rows) == source['material_input_digest'], 'Source material digest differs')
        actual_paths = [project / 'BiellaGames.uproject']
        for name in ('Source', 'Content', 'Config', 'Plugins'):
            actual_paths += [p for p in (project / name).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
        release.require(sorted(p.relative_to(project).as_posix() for p in actual_paths) ==
                        sorted(r['path'] for r in rows), 'Material membership changed since retained build')
        mapping = {}
        for row in rows:
            relative = release.safe_path(row['path'])
            path = project / relative
            release.require(not any(p.is_symlink() for p in (path, *path.parents)), 'Linked material input')
            actual = release.identity(path)
            release.require(actual['sha256'] == row['sha256'] and actual['bytes'] == row['bytes'],
                            f'Material input changed: {relative}')
            mapping['project/' + relative.as_posix()] = path
        mapping['source-build-manifest.json'] = source_path
        workstation = project.parents[1] / 'ops/workstation'
        for name in ('setup-unreal-win64.ps1', 'build-unreal-win64.ps1'):
            mapping['tooling/' + name] = workstation / name
        mapping['tooling/verify_d08_01_win64_source.ps1'] = project / 'tests/verify_d08_01_win64_source.ps1'
        identities = [dict(release.identity(path), path=name) for name, path in sorted(mapping.items())]
        manifest = {'schema': 'biella.d08.source_transfer/v1', 'task_id': 'D08-01',
                    'scope': 'SOURCE_TRANSFER_ONLY', 'required_engine_version': '5.8.2',
                    'material_input_digest': source['material_input_digest'], 'files': identities,
                    'retained_source_revision': source['revision'],
                    'working_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project, text=True).strip(),
                    'identity_rule': 'Exact file digests define the transferred inputs; Git revisions are provenance.',
                    'exclusions': ['No engine, SDK, built game, cooked output, editor caches or player state.',
                                   'No native Windows execution or release candidate is qualified.']}
        manifest_path = output / 'handoff-manifest.json'
        release.write(manifest_path, manifest)
        manifest_sha = release.identity(manifest_path)['sha256']
        mapping['handoff-manifest.json'] = manifest_path
        archive = archive_directory / ('BiellaGames-D08-Win64-source-' + manifest_sha[:12] + '.zip')
        release.require(not archive.exists(), 'Retain existing canonical source archive')
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            for name, path in sorted(mapping.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, path.read_bytes())
        release.require(archive.read_bytes()[:4] == b'PK\x03\x04' and zipfile.is_zipfile(archive), 'Actual ZIP format required')
        readback = workspace / 'readback'
        readback.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            release.require(bundle.namelist() == sorted(mapping), 'ZIP membership differs')
            release.require(bundle.testzip() is None, 'ZIP CRC failure')
            bundle.extractall(readback)
        for name, path in mapping.items():
            a, b = release.identity(path), release.identity(readback / name)
            release.require((a['bytes'], a['sha256']) == (b['bytes'], b['sha256']), 'ZIP extraction differs: ' + name)
        report.update(archive=release.identity(archive), manifest=release.identity(manifest_path),
                      material_input_digest=source['material_input_digest'], material_files=len(rows),
                      source_bytes=sum(r['bytes'] for r in rows), readback_directory=str(readback),
                      transfer_files=len(mapping))
        script = readback / 'tooling/verify_d08_01_win64_source.ps1'
        invocations = []

        def check(name, expected, error=None, engine='5.8.2'):
            command = [str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(script),
                       '-BundleDirectory', str(readback), '-ManifestSha256', manifest_sha,
                       '-Output', str(output / (name + '.json')), '-RequiredEngineVersion', engine]
            result = subprocess.run(command, capture_output=True, text=True)
            (output / (name + '.stdout.log')).write_text(result.stdout)
            (output / (name + '.stderr.log')).write_text(result.stderr)
            invocations.append({'case': name, 'argv': command, 'returncode': result.returncode})
            release.write(output / 'commands.json', invocations)
            value = release.read(output / (name + '.json'))
            release.require(result.returncode == expected and value['result'] == ('PASS' if expected == 0 else 'FAIL'),
                            'Unexpected source transfer verification result: ' + name)
            if error:
                release.require(error in value.get('error', ''), 'Unexpected negative rejection reason: ' + name)
            report['cases'].append({'case': name, 'result': 'PASS' if expected == 0 else 'EXPECTED_REJECTION',
                                    'receipt': release.identity(output / (name + '.json'))})

        check('clean-source-readback', 0)
        selected = next(r for r in rows if r['path'].endswith('.umap'))
        target = readback / 'project' / selected['path']
        removed = workspace / 'removed-map'
        target.rename(removed)
        try:
            check('missing-current-map', 1, 'membership differs')
        finally:
            removed.rename(target)
        check('incompatible-engine-version', 1, 'Incompatible required engine version', engine='5.8.3')
        with target.open('r+b') as stream:
            original = stream.read(1)
            stream.seek(0)
            stream.write(bytes([original[0] ^ 1]))
        try:
            check('corrupted-current-map', 1, 'bytes differ')
        finally:
            with target.open('r+b') as stream:
                stream.write(original)
        stale = readback / 'project/DerivedDataCache'
        stale.mkdir()
        try:
            check('unexpected-empty-cache-directory', 1, 'cache is present')
        finally:
            stale.rmdir()
        check('restored-exact-source', 0)
        report.update(result='PASS', bounded_content_negative=selected,
                      remote_transfer='NOT_EXECUTED_NO_COMPATIBLE_WINDOWS_RESOURCE',
                      native_win64_build_verified=False, native_windows_powershell_execution='NOT_EXECUTED',
                      limitations=['PowerShell source validation ran on Linux; this is not Windows SDK/build/runtime evidence.',
                                   'No D16 rebuild/reproducibility acceptance is inferred from source archive restoration.',
                                   'Current Development settings probe still needs its recorded native Windows path adaptation.'])
    except Exception as error:
        report['error'] = str(error)
        with release.LEDGER.open('a') as stream:
            stream.write(release.json.dumps({'task_id': 'D08-01', 'time': release.now(),
                'type': 'win64_source_transfer_preparation', 'status': 'CONTINUE',
                'diagnostics': str(error)[:2000], 'evidence': str(output)}) + '\n')
    finally:
        report['evidence'] = [release.identity(p) for p in sorted(output.iterdir())
                              if p.is_file() and p.name != 'validation.json']
        release.write(output / 'validation.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'output', 'archive-directory', 'powershell'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.workspace.absolute(), args.output.absolute(), args.archive_directory.absolute(), args.powershell.resolve())
    print(release.json.dumps({k: result.get(k) for k in ('result', 'scope', 'archive', 'material_files', 'cases', 'error')}))
    raise SystemExit(0 if result['result'] == 'PASS' else 1)
