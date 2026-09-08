#!/usr/bin/env python3
"""Real NSIS assembly and negative controls, explicitly NOT a Win64 game build."""
import argparse
from pathlib import Path
import subprocess
import sys

import build_d08_01_windows_installer as installer
import run_d08_01_release as release


SOURCE = r'''// D08 installer-tool fixture only. No Unreal or game code.
typedef unsigned long DWORD;
__declspec(dllimport) void* __stdcall GetStdHandle(DWORD);
__declspec(dllimport) int __stdcall WriteFile(void*, const void*, DWORD, DWORD*, void*);
__declspec(dllimport) __declspec(noreturn) void __stdcall ExitProcess(unsigned);
void mainCRTStartup(void) {
    static const char message[] = "BIELLA_D08_INSTALLER_TEST_FIXTURE_NOT_GAME\r\n";
    DWORD written = 0;
    int ok = WriteFile(GetStdHandle((DWORD)-11), message, sizeof(message)-1, &written, (void*)0);
    ExitProcess(ok && written == sizeof(message)-1 ? 0 : 1);
}
'''


def qualify(output, workspace, archive_directory):
    release.require(not output.exists() and not workspace.exists(), 'Fresh fixture output and workspace required')
    output.mkdir(parents=True)
    workspace.mkdir(parents=True)
    fixture_source = output / 'fixture.c'
    fixture_source.write_text(SOURCE)
    definition = output / 'kernel32.def'
    definition.write_text('LIBRARY KERNEL32.dll\nEXPORTS\nGetStdHandle\nWriteFile\nExitProcess\n')
    commands = [
        ['clang', '--version'], ['lld-link', '--version'],
        ['llvm-dlltool', '-m', 'i386:x86-64', '-d', str(definition), '-l', str(workspace / 'kernel32.lib')],
        ['clang', '-target', 'x86_64-pc-windows-msvc', '-ffreestanding', '-fno-stack-protector', '-c',
         str(fixture_source), '-o', str(workspace / 'fixture.obj')],
        ['lld-link', '/entry:mainCRTStartup', '/subsystem:console', '/nodefaultlib', '/machine:x64',
         '/out:' + str(output / 'fixture.exe'), str(workspace / 'fixture.obj'), str(workspace / 'kernel32.lib')]]
    invocations = []
    report = {'schema': 'biella.d08.nsis_fixture_test/v1', 'task_id': 'D08-01',
              'scope': installer.FIXTURE_SCOPE, 'observed': release.now(), 'result': 'FAIL',
              'release_candidate': False, 'game_build': False, 'native_execution': 'NOT_RUN',
              'implementation': release.identity(__file__), 'cases': []}
    try:
        for index, command in enumerate(commands):
            process = subprocess.run(command, text=True, capture_output=True)
            (output / f'compiler-{index}.stdout.log').write_text(process.stdout)
            (output / f'compiler-{index}.stderr.log').write_text(process.stderr)
            invocations.append({'argv': command, 'returncode': process.returncode})
            release.write(output / 'compiler-invocations.json', invocations)
            release.require(process.returncode == 0, 'Fixture compiler failed; inspect retained logs')
        release.require(release.executable_format(output / 'fixture.exe') == 'PE32+-x86_64', 'Fixture format mismatch')
        report['fixture_binary'] = release.identity(output / 'fixture.exe')
        fixtures = []
        for version in ('a', 'b'):
            payload = output / ('fixture-' + version) / 'payload'
            payload.mkdir(parents=True)
            (payload / 'fixture.exe').write_bytes((output / 'fixture.exe').read_bytes())
            (payload / 'nested $ test').mkdir()
            (payload / 'nested $ test' / 'résumé $.txt').write_text(installer.FIXTURE_SCOPE + '\nversion=' + version + '\n')
            manifest = {'schema': 'biella.d08.installer_fixture/v1', 'fixture_scope': installer.FIXTURE_SCOPE,
                        'version': version, 'entrypoint': 'fixture.exe', 'files': release.members(payload)}
            manifest['fixture_id'] = release.digest(manifest)
            path = payload.parent / 'manifest.json'
            release.write(path, manifest)
            result = installer.assemble(payload, path, workspace / ('assembly-' + version),
                                        output / ('assembly-' + version), archive_directory, fixture=True)
            release.require(result['result'] == 'PASS', 'Fixture NSIS assembly/readback failed')
            fixtures.append({'version': version, 'manifest': release.identity(path), 'fixture_id': manifest['fixture_id'],
                             'archive': result['archive'], 'install_directory': result['install_directory']})
        report['fixtures'] = fixtures
        report['cases'].append({'case': 'actual_x64_fixture_and_two_nsis_PE32_installers_extract_exact_unicode_dollar_paths', 'result': 'PASS'})
        fixture_manifest = release.read(output / 'fixture-a/manifest.json')
        payload = output / 'fixture-a/payload'

        def rejects(name, action):
            try:
                action()
            except ValueError as error:
                report['cases'].append({'case': name, 'result': 'EXPECTED_REJECTION', 'reason': str(error)})
                return
            raise ValueError('Negative control was accepted: ' + name)

        rejects('fixture_without_explicit_opt_in', lambda: installer.payload_identity(payload, fixture_manifest, False))
        linux_manifest = release.read(release.ROOT / 'package-manifest.json')
        rejects('actual_linux_manifest_cannot_be_wrapped_as_windows', lambda: installer.payload_identity(payload, linux_manifest, False))
        altered = dict(fixture_manifest, fixture_id='0' * 64)
        rejects('incorrect_fixture_identity', lambda: installer.payload_identity(payload, altered, True))
        file = payload / 'fixture.exe'
        original = file.read_bytes()
        try:
            file.write_bytes(original[:-1])
            rejects('truncated_payload', lambda: installer.payload_identity(payload, fixture_manifest, True))
        finally:
            file.write_bytes(original)
        release.require(installer.payload_identity(payload, fixture_manifest, True) == fixture_manifest['fixture_id'],
                        'Exact fixture bytes were not restored')
        report['result'] = 'PASS'
    except (OSError, ValueError, KeyError) as error:
        report['error'] = str(error)
        with release.LEDGER.open('a') as stream:
            stream.write(release.json.dumps({'task_id': 'D08-01', 'time': release.now(),
                'type': 'nsis_fixture_validation', 'status': 'CONTINUE', 'diagnostics': str(error),
                'evidence': str(output)}) + '\n')
    finally:
        report['evidence'] = [release.identity(p) for p in sorted(output.rglob('*'))
                              if p.is_file() and p != output / 'validation.json']
        release.write(output / 'validation.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output', 'workspace', 'archive-directory'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = qualify(args.output.resolve(), args.workspace.resolve(), args.archive_directory.resolve())
    print(release.json.dumps({k: report.get(k) for k in ('result', 'scope', 'cases', 'error')}))
    sys.exit(0 if report['result'] == 'PASS' else 1)
