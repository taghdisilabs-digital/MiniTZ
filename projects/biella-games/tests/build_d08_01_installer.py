#!/usr/bin/env python3
"""Assemble/read back an exact Linux diagnostic Debian payload, never a Win64 RC."""
import argparse
import math
from pathlib import Path
import re
import shutil
import subprocess

import run_d08_01_release as release


def assemble(payload, manifest_path, workspace, output, archive_directory):
    manifest = release.read(manifest_path)
    release.require(manifest['platform'] == 'Linux' and manifest['configuration'] == 'Development',
                    'This recipe is for the actual Linux Development diagnostic payload only')
    release.verify_package(payload, manifest)
    release.require(not workspace.exists() and not output.exists(), 'Fresh workspace and proof required')
    workspace.mkdir(parents=True)
    output.mkdir(parents=True)
    commands = []
    report = {'schema': 'biella.d08.installer/v1', 'task_id': 'D08-01', 'result': 'FAIL',
              'scope': 'INSTALLER_ASSEMBLY_ONLY; Linux Development diagnostic, not a release candidate',
              'observed': release.now(), 'package_id': manifest['package_id'],
              'manifest': release.identity(manifest_path), 'implementation': release.identity(__file__)}

    def run(name, command):
        process = subprocess.run(command, cwd=workspace, text=True, capture_output=True)
        (output / (name + '.stdout.log')).write_text(process.stdout)
        (output / (name + '.stderr.log')).write_text(process.stderr)
        commands.append({'name': name, 'argv': command, 'returncode': process.returncode})
        release.write(output / 'commands.json', commands)
        release.require(process.returncode == 0, f'{name} failed; inspect retained stderr')
        return process.stdout

    try:
        operating_system = Path('/etc/os-release').read_text()
        release.require('ID=ubuntu\n' in operating_system and 'VERSION_ID="24.04"' in operating_system,
                        'Dependency derivation is bound to the observed Ubuntu 24.04 builder')
        report['dependency_environment'] = {'os_release': operating_system,
            'architecture': run('architecture', ['dpkg', '--print-architecture']).strip(),
            'dpkg_version': run('dpkg-version', ['dpkg-deb', '--version']).splitlines()[0]}
        release.require(report['dependency_environment']['architecture'] == 'amd64', 'Wrong target architecture')
        metadata = release.PROJECT / 'Config/DefaultGame.ini'
        project_version = re.search(r'^ProjectVersion=([\w.+~-]+)$', metadata.read_text(), re.M).group(1)
        project_name = re.search(r'^ProjectName=([^\r\n]+)$', metadata.read_text(), re.M).group(1)
        company = re.search(r'^CompanyName=([^\r\n]+)$', metadata.read_text(), re.M).group(1)
        version = project_version + '+d08.' + manifest['package_id'][:12]
        name = 'biella-games-d08-diagnostic'
        tree = workspace / 'tree'
        control = tree / 'DEBIAN'
        control.mkdir(parents=True)
        relative = Path('opt') / name / manifest['package_id']
        destination = tree / relative
        shutil.copytree(payload, destination)
        for path in (tree, *tree.rglob('*')):
            path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
        release.verify_package(destination, manifest)
        wrapper = tree / 'usr/bin' / name
        wrapper.parent.mkdir(parents=True)
        wrapper.write_text('#!/bin/sh\nset -eu\nexec "/' + relative.as_posix() + '/' + manifest['entrypoint'] + '" "$@"\n')
        wrapper.chmod(0o755)
        source_control = workspace / 'debian/control'
        source_control.parent.mkdir()
        source_control.write_text(f'Source: {name}\nSection: games\nPriority: optional\nMaintainer: {company}\n\n'
                                  f'Package: {name}\nArchitecture: amd64\nDescription: {project_name} diagnostic package\n')
        elfs = []
        for row in manifest['files']:
            path = destination / row['path']
            with path.open('rb') as stream:
                if stream.read(4) == b'\x7fELF':
                    release.require(release.executable_format(path) == 'ELF64-x86_64', 'Unexpected ELF architecture')
                    elfs.append(path)
        dependencies = run('dependencies', ['dpkg-shlibdeps', '-O', '-S' + str(tree),
            *['-l' + str(p) for p in sorted({p.parent for p in elfs})], *map(str, elfs)])
        dependency_match = re.fullmatch(r'shlibs:Depends=([^\n]+)\n?', dependencies)
        release.require(dependency_match is not None, 'Expected actual ELF-derived dependency list')
        depends = dependency_match.group(1)
        report['dependencies'] = {'depends': depends,
            'elf_inputs': [release.identity(path) for path in elfs],
            'scope': 'ELF imported-symbol dependencies derived against Ubuntu 24.04 package metadata. A working display, Vulkan GPU/driver and audio device remain runtime requirements; no cross-distribution or hardware compatibility promise.'}
        installed_size = math.ceil(sum(p.stat().st_size for p in tree.rglob('*') if p.is_file()) / 1024)
        control_text = (f'Package: {name}\nVersion: {version}\nSection: games\nPriority: optional\n'
                        f'Architecture: amd64\nMaintainer: {company}\nInstalled-Size: {installed_size}\n'
                        f'Depends: {depends}\nDescription: {project_name} D08 Linux Development diagnostic\n'
                        ' Cooked native diagnostic package assembled on Ubuntu 24.04 amd64.\n'
                        ' Requires a working Vulkan GPU and display. Not a Win64 release candidate.\n')
        (control / 'control').write_text(control_text)
        (output / 'control').write_text(control_text)
        shutil.copy2(wrapper, output / 'entrypoint.sh')
        archive_directory.mkdir(parents=True, exist_ok=True)
        archive = archive_directory / f'{name}_{version}_amd64.deb'
        release.require(not archive.exists(), 'Existing canonical installer must not be overwritten')
        run('build', ['dpkg-deb', '--root-owner-group', '--build', str(tree), str(archive)])
        with archive.open('rb') as stream:
            release.require(stream.read(8) == b'!<arch>\n', 'Not a real ar/Debian container')
        run('info', ['dpkg-deb', '--info', str(archive)])
        extracted = workspace / 'readback'
        run('extract', ['dpkg-deb', '--extract', str(archive), str(extracted)])
        readback_control = workspace / 'readback-control'
        run('control', ['dpkg-deb', '--control', str(archive), str(readback_control)])
        release.require((readback_control / 'control').read_text() == control_text, 'Control readback differs')
        release.require({p.name for p in readback_control.iterdir()} == {'control'},
                        'Unexpected maintainer scripts or control members')
        release.require(release.members(extracted) ==
                        [row for row in release.members(tree) if not row['path'].startswith('DEBIAN/')],
                        'Installer extraction bytes/membership/executable bits differ')
        readback = release.verify_package(extracted / relative, manifest)
        report.update(result='PASS', archive=release.identity(archive), metadata_source=release.identity(metadata),
                      version=version, install_path='/' + relative.as_posix(), payload_readback=readback,
                      entrypoint=release.identity(extracted / 'usr/bin' / name),
                      members=release.members(extracted), control=release.identity(output / 'control'),
                      state_preservation='No files under per-user settings/saves and no maintainer scripts. Native dpkg install/update/uninstall behavior has not been qualified.',
                      publication='Canonical local diagnostic installer retained. No remote publication/readback claimed.')
    except (OSError, ValueError, KeyError, AttributeError) as error:
        report['error'] = str(error)
        with release.LEDGER.open('a') as stream:
            stream.write(release.json.dumps({'task_id': 'D08-01', 'time': release.now(),
                'type': 'debian_installer_assembly', 'status': 'CONTINUE', 'diagnostics': str(error)[:2000],
                'evidence': str(output)}) + '\n')
    finally:
        report['evidence'] = [release.identity(p) for p in sorted(output.iterdir())
                              if p.is_file() and p.name != 'validation.json']
        release.write(output / 'validation.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('payload', 'manifest', 'workspace', 'output', 'archive-directory'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = assemble(args.payload.resolve(), args.manifest.resolve(), args.workspace.resolve(),
                      args.output.resolve(), args.archive_directory.resolve())
    print(release.json.dumps({key: result.get(key) for key in ('result', 'archive', 'error')}))
    raise SystemExit(0 if result['result'] == 'PASS' else 1)
