#!/usr/bin/env python3
"""Native Windows installer fault tests; PE fixtures are not Unreal packages."""
import argparse
import io
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import unittest

import run_d08_01_release as release
from test_d08_01_release import ReleaseTests


class WindowsReleaseTests(ReleaseTests):
    fixture_executable = None

    def fixture(self, name, data):
        payload = self.root / name
        payload.mkdir()
        (payload / 'fixture.exe').write_bytes(self.fixture_executable.read_bytes())
        (payload / 'content.pak').write_bytes(b'SYNTHETIC_NOT_COOKED_UNREAL_CONTENT\n' + data)
        manifest = release.seal({
            'schema': 'biella.d08.package/v1', 'project': 'TEST_FIXTURE',
            'platform': 'Win64', 'configuration': 'Development', 'engine_version': '5.8.2',
            'entrypoint': 'fixture.exe', 'binary': 'fixture.exe',
            'binary_format': 'PE32+-x86_64', 'files': release.members(payload)})
        return payload, manifest

    def test_incompatible_engine_and_platform_rejected(self):
        for key, value in [('engine_version', '99'), ('platform', 'Linux'),
                           ('configuration', 'Shipping')]:
            manifest = release.seal(dict(self.b, **{key: value}))
            with self.assertRaisesRegex(ValueError, 'Incompatible'):
                release.install(self.new, manifest, self.installation, self.a['package_id'])
            self.assert_old_intact()

    def test_renamed_elf_is_not_windows_binary(self):
        header = bytearray(64)
        header[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', header, 18, 62)
        (self.new / 'fixture.exe').write_bytes(header)
        manifest = release.seal(dict(self.b, files=release.members(self.new)))
        with self.assertRaisesRegex(ValueError, 'format'):
            release.verify_package(self.new, manifest)
        self.assert_old_intact()

    def test_native_fixture_launch_before_and_after_update(self):
        observed = []
        for payload, manifest, expected_base in ((self.old, self.a, None),
                                                (self.new, self.b, self.a['package_id'])):
            if expected_base is not None:
                release.install(payload, manifest, self.installation, expected_base)
            directory, current = release.current(self.installation)
            self.assertEqual(current, manifest)
            result = subprocess.run([str(directory / 'payload' / 'fixture.exe')],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), 'BIELLA_D08_INSTALLER_TEST_FIXTURE_NOT_GAME')
            observed.append(current['package_id'])
        self.assertNotEqual(*observed)
        release.verify_package(self.installation / 'versions' / self.a['package_id'] / 'payload', self.a)
        self.assertEqual(self.state.read_bytes(), b'LookSensitivityX=1.37\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-executable', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Native Windows required; no emulated Windows result')
    if args.output.exists():
        parser.error('Preserve existing evidence; use a fresh output')
    fixture = release.identity(args.fixture_executable)
    release.require(fixture['sha256'] == args.expected_sha256, 'Fixture identity differs')
    release.require(release.executable_format(args.fixture_executable) == 'PE32+-x86_64',
                    'Actual x64 PE fixture required')
    WindowsReleaseTests.fixture_executable = args.fixture_executable
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WindowsReleaseTests)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = {
        'schema': 'biella.d08.windows_update_fixture_validation/v1', 'task_id': 'D08-01',
        'scope': 'NATIVE_WINDOWS_INSTALLER_FIXTURE_NOT_GAME', 'observed_utc': release.now(),
        'result': 'PASS' if result.wasSuccessful() and not result.skipped else 'FAIL',
        'release_candidate': False, 'game_runtime_verified': False, 'ue_save_migration_verified': False,
        'machine': platform.node(), 'platform': platform.platform(), 'python': sys.version,
        'executable': release.identity(sys.executable), 'invocation': sys.argv,
        'implementation': [release.identity(p) for p in
                           [__file__, release.__file__, Path(__file__).with_name('test_d08_01_release.py')]],
        'fixture': fixture, 'tests_run': result.testsRun, 'skipped': result.skipped,
        'failures': [(test.id(), text) for test, text in result.failures],
        'errors': [(test.id(), text) for test, text in result.errors], 'test_output': stream.getvalue(),
        'limitations': ['content.pak contains explicit synthetic bytes, not cooked Unreal assets.',
                        'Fixture launch and retained sentinel are not gameplay or UE settings/save reconstruction.']}
    release.write(args.output, report)
    print(json.dumps({'result': report['result'], 'tests_run': result.testsRun,
                      'scope': report['scope'], 'output': release.identity(args.output)}))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
