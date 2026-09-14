#!/usr/bin/env python3
"""Wrap exact Win64 bytes with NSIS; fixture evidence is never game evidence.

Versioned, per-user installation leaves prior versions and UE user state alone.
This wrapper does not replace the D08 update/compatibility qualification tool.
"""
import argparse
from pathlib import Path
import struct
import subprocess

import run_d08_01_release as release


FIXTURE_SCOPE = 'INSTALLER_TEST_FIXTURE_NOT_GAME'


def quote(value, runtime=True):
    release.require('\n' not in value and '\r' not in value, 'Multiline NSIS argument')
    if runtime:
        value = value.replace('$', '$$')
    return '"' + value.replace('"', '$\\"') + '"'


def payload_identity(payload, manifest, fixture):
    if not fixture:
        release.require(manifest.get('platform') == 'Win64', 'Requires a real Win64 payload; Linux is not convertible')
        release.require('fixture_id' not in manifest and 'fixture_scope' not in manifest, 'Fixture cannot become game evidence')
        release.verify_package(payload, manifest)
        return manifest['package_id']
    release.require(manifest.get('schema') == 'biella.d08.installer_fixture/v1' and
                    manifest.get('fixture_scope') == FIXTURE_SCOPE, 'Explicit installer fixture required')
    expected = release.digest({k: v for k, v in manifest.items() if k != 'fixture_id'})
    release.require(manifest.get('fixture_id') == expected, 'Fixture identity mismatch')
    release.require(release.members(payload) == manifest['files'], 'Fixture payload differs')
    release.safe_path(manifest['entrypoint'])
    release.require(manifest['entrypoint'] in {r['path'] for r in manifest['files']}, 'Fixture entrypoint absent')
    release.require(release.executable_format(payload / manifest['entrypoint']) == 'PE32+-x86_64', 'Fixture must be an actual x64 PE')
    return expected


def assemble(payload, manifest_path, workspace, output, archive_directory, fixture=False):
    manifest = release.read(manifest_path)
    identifier = payload_identity(payload, manifest, fixture)
    # Keep comfortably below NSIS's signed 32-bit embedded data offsets. Larger
    # payloads require separately qualified external data, never truncation.
    release.require(sum(row['bytes'] for row in manifest['files']) < 1_800_000_000,
                    'Payload exceeds this embedded NSIS recipe; external-data assembly required')
    release.require(not workspace.exists() and not output.exists(), 'Fresh workspace and proof required')
    workspace.mkdir(parents=True)
    output.mkdir(parents=True)
    archive_directory.mkdir(parents=True, exist_ok=True)
    suffix = '-TEST_FIXTURE' if fixture else '-' + manifest['configuration']
    archive = archive_directory / f'BiellaGames-D08{suffix}-{identifier[:12]}-setup.exe'
    release.require(not archive.exists(), 'Do not replace an existing canonical installer')
    base = 'BiellaGames-D08-InstallerFixture' if fixture else 'BiellaGames\\Packages'
    destination = '$LOCALAPPDATA\\' + base + '\\' + identifier
    report = {'schema': 'biella.d08.nsis_assembly/v1', 'task_id': 'D08-01',
              'result': 'FAIL', 'observed': release.now(), 'release_candidate': False,
              'scope': FIXTURE_SCOPE if fixture else 'INSTALLER_ASSEMBLY_ONLY',
              'fixture_id' if fixture else 'package_id': identifier,
              'manifest': release.identity(manifest_path),
              'implementation': release.identity(__file__), 'install_directory': destination,
              'state_preservation': 'Versioned payload only; no UE settings/save writes, registry, drivers, or reboot.',
              'limitations': ['NSIS wrapper is a PE32 x86 process containing a verified PE32+ x64 payload.',
                  'No publisher signature/authentication is claimed.',
                  'No UE prerequisites are installed automatically; actual target dependencies still require qualification.',
                  'Existing version directories are rejected without writes. New versions install side by side.',
                  'Uninstaller removes exact package files; additional files and external user state are retained.',
                  'Game update compatibility and real Win64 play are separate required evidence.']}
    commands = []

    def run(name, command):
        result = subprocess.run(command, text=True, capture_output=True, cwd=workspace)
        (output / (name + '.stdout.log')).write_text(result.stdout)
        (output / (name + '.stderr.log')).write_text(result.stderr)
        commands.append({'name': name, 'argv': command, 'returncode': result.returncode})
        release.write(output / 'commands.json', commands)
        release.require(result.returncode == 0, name + ' failed; see retained logs')
        return result.stdout

    try:
        # Generate explicit file membership, not a recursive wildcard. All source
        # paths are escaped independently from runtime NSIS variables.
        lines = ['Unicode true', 'RequestExecutionLevel user', 'CRCCheck force',
                 'SetCompressor /SOLID lzma', 'Name ' + quote('Biella Games D08' + suffix),
                 'OutFile ' + quote(str(archive), runtime=False), 'ShowInstDetails show', 'ShowUninstDetails show',
                 'Page instfiles', 'UninstPage uninstConfirm', 'UninstPage instfiles',
                 'Var Mutex', 'Function .onInit',
                 '  System::Call \'kernel32::CreateMutexW(p 0, i 0, w "Local\\BiellaD08-' + identifier + '") p .r1 ?e\'',
                 '  Pop $0', '  StrCpy $Mutex $1',
                 '  StrCmp $0 183 mutex_failed', '  StrCmp $Mutex 0 mutex_failed mutex_ready',
                 'mutex_failed:', '  SetErrorLevel 2', '  Quit', 'mutex_ready:',
                 '  StrCpy $INSTDIR "' + destination + '"',
                 'FunctionEnd', 'Section "Install"',
                 '  IfFileExists "$INSTDIR" exists fresh', 'exists:',
                 '  DetailPrint "Existing version retained; uninstall it explicitly before reinstalling."',
                 '  SetErrorLevel 2', '  Quit', 'fresh:', '  SetOverwrite off']
        for row in manifest['files']:
            relative = release.safe_path(row['path'])
            directory = relative.parent.as_posix().replace('/', '\\')
            directory = '' if directory == '.' else '\\' + directory.replace('$', '$$')
            lines += ['  SetOutPath "$INSTDIR\\payload' + directory + '"',
                      '  IfErrors failed', '  File ' + quote('/oname=' + relative.name) + ' ' + quote(str(payload / relative), runtime=False),
                      '  IfErrors failed']
        lines += ['  SetOutPath "$INSTDIR"', '  File /oname=manifest.json ' + quote(str(manifest_path), runtime=False),
                  '  IfErrors failed', '  WriteUninstaller "$INSTDIR\\uninstall.exe"',
                  '  IfErrors failed', '  SetErrorLevel 0', '  Goto done', 'failed:',
                  '  DetailPrint "Installation incomplete; this version is not ready to launch."',
                  '  SetErrorLevel 1', 'done:', 'SectionEnd', 'Section "Uninstall"']
        for row in manifest['files']:
            name = row['path'].replace('/', '\\').replace('$', '$$')
            lines.append('  Delete "$INSTDIR\\payload\\' + name + '"')
        directories = {p for row in manifest['files'] for p in release.safe_path(row['path']).parents}
        for directory in sorted(directories, key=lambda p: (len(p.parts), str(p)), reverse=True):
            part = '' if str(directory) == '.' else '\\' + str(directory).replace('/', '\\').replace('$', '$$')
            lines.append('  RMDir "$INSTDIR\\payload' + part + '"')
        lines += ['  Delete "$INSTDIR\\manifest.json"', '  Delete "$INSTDIR\\uninstall.exe"',
                  '  RMDir "$INSTDIR"', '  SetErrorLevel 0', 'SectionEnd']
        recipe = output / 'installer.nsi'
        recipe.write_text('\n'.join(lines) + '\n')
        run('nsis-version', ['makensis', '-VERSION'])
        run('compile', ['makensis', '-V2', str(recipe)])
        with archive.open('rb') as stream:
            header = stream.read(64)
            release.require(header[:2] == b'MZ', 'Installer lacks DOS/PE header')
            stream.seek(struct.unpack_from('<I', header, 60)[0])
            pe = stream.read(26)
            release.require(pe[:4] == b'PE\0\0' and struct.unpack_from('<H', pe, 4)[0] == 0x14c and
                            struct.unpack_from('<H', pe, 24)[0] == 0x10b, 'Expected actual NSIS PE32-x86 wrapper')
        extracted = workspace / 'readback'
        run('extract', ['7z', 'x', '-y', '-o' + str(extracted), str(archive)])
        release.require(release.read(extracted / 'manifest.json') == manifest, 'Embedded manifest readback mismatch')
        actual = release.members(extracted / 'payload')
        byte_identity = lambda rows: [{k: row[k] for k in ('path', 'sha256', 'bytes')} for row in rows]
        release.require(byte_identity(actual) == byte_identity(manifest['files']), 'Extracted payload differs')
        report.update(result='PASS', archive=release.identity(archive), recipe=release.identity(recipe),
                      wrapper_format='PE32-x86', payload_format='PE32+-x86_64',
                      extracted_manifest=release.identity(extracted / 'manifest.json'),
                      payload_readback=byte_identity(actual),
                      native_install_launch_uninstall='NOT_EXECUTED_BY_ASSEMBLER',
                      publication='Canonical local artifact retained; remote readback requires actual transfer evidence.')
    except (OSError, ValueError, KeyError) as error:
        report['error'] = str(error)
        with release.LEDGER.open('a') as stream:
            stream.write(release.json.dumps({'task_id': 'D08-01', 'time': release.now(),
                'type': 'windows_installer_assembly', 'status': 'CONTINUE',
                'diagnostics': str(error)[:2000], 'evidence': str(output)}) + '\n')
    finally:
        report['evidence'] = [release.identity(p) for p in sorted(output.iterdir())
                              if p.is_file() and p.name != 'validation.json']
        release.write(output / 'validation.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('payload', 'manifest', 'workspace', 'output', 'archive-directory'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--fixture', action='store_true', help='Explicit tool test only; never a game package')
    args = parser.parse_args()
    result = assemble(args.payload.resolve(), args.manifest.resolve(), args.workspace.resolve(),
                      args.output.resolve(), args.archive_directory.resolve(), args.fixture)
    print(release.json.dumps({k: result.get(k) for k in ('result', 'scope', 'archive', 'error')}))
    raise SystemExit(0 if result['result'] == 'PASS' else 1)
