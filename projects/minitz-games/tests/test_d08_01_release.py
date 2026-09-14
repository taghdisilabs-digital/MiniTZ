#!/usr/bin/env python3
"""Fault-injected installer tests. Tiny fixtures are never gameplay evidence."""
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch

import run_d08_01_release as release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.installation = self.root / 'installed'
        self.state = self.root / 'user' / 'GameUserSettings.ini'
        self.state.parent.mkdir()
        self.state.write_bytes(b'LookSensitivityX=1.37\n')
        self.old, self.a = self.fixture('old', b'old cooked content')
        self.new, self.b = self.fixture('new', b'new cooked content')
        release.install(self.old, self.a, self.installation)

    def fixture(self, name, data):
        payload = self.root / name
        payload.mkdir()
        header = bytearray(64)
        header[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', header, 18, 62)
        (payload / 'game').write_bytes(header)
        (payload / 'game').chmod(0o755)
        (payload / 'launch.sh').write_text('#!/bin/sh\nexec ./game\n')
        (payload / 'launch.sh').chmod(0o755)
        (payload / 'content.pak').write_bytes(data)
        manifest = release.seal({'schema': 'biella.d08.package/v1', 'project': 'TEST_FIXTURE',
                                'platform': 'Linux', 'configuration': 'Development', 'engine_version': '5.8.2',
                                'entrypoint': 'launch.sh', 'binary': 'game', 'binary_format': 'ELF64-x86_64',
                                'files': release.members(payload)})
        return payload, manifest

    def assert_old_intact(self):
        _, manifest = release.current(self.installation)
        self.assertEqual(manifest, self.a)
        release.verify_package(self.old, self.a)
        self.assertEqual(self.state.read_bytes(), b'LookSensitivityX=1.37\n')

    def test_exact_update_preserves_old_and_external_state(self):
        result = release.install(self.new, self.b, self.installation, self.a['package_id'])
        self.assertEqual(result['to_package'], self.b['package_id'])
        self.assertEqual(release.current(self.installation)[1], self.b)
        release.verify_package(self.installation / 'versions' / self.a['package_id'] / 'payload', self.a)
        self.assertEqual(self.state.read_bytes(), b'LookSensitivityX=1.37\n')

    def test_incomplete_update_preserves_active_version(self):
        (self.new / 'content.pak').unlink()
        with self.assertRaisesRegex(ValueError, 'differ'):
            release.install(self.new, self.b, self.installation, self.a['package_id'])
        self.assert_old_intact()

    def test_mixed_content_preserves_active_version(self):
        shutil.copyfile(self.old / 'content.pak', self.new / 'content.pak')
        with self.assertRaisesRegex(ValueError, 'differ'):
            release.install(self.new, self.b, self.installation, self.a['package_id'])
        self.assert_old_intact()

    def test_incompatible_engine_and_platform_rejected(self):
        for key, value in [('engine_version', '99'), ('platform', 'Win64'), ('configuration', 'Shipping')]:
            manifest = release.seal(dict(self.b, **{key: value}))
            with self.assertRaisesRegex(ValueError, 'Incompatible'):
                release.install(self.new, manifest, self.installation, self.a['package_id'])
            self.assert_old_intact()

    def test_wrong_update_base_rejected(self):
        with self.assertRaisesRegex(ValueError, 'base'):
            release.install(self.new, self.b, self.installation, 'f' * 64)
        self.assert_old_intact()

    def test_postcopy_corruption_rejected(self):
        original = shutil.copytree
        def corrupt(src, dest, **kwargs):
            result = original(src, dest, **kwargs)
            (Path(dest) / 'content.pak').write_bytes(b'partial transfer')
            return result
        with patch.object(release.shutil, 'copytree', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'differ'):
                release.install(self.new, self.b, self.installation, self.a['package_id'])
        self.assert_old_intact()

    def test_interrupted_copy_can_retry(self):
        with patch.object(release.shutil, 'copytree', side_effect=OSError('interrupted copy')):
            with self.assertRaisesRegex(OSError, 'interrupted copy'):
                release.install(self.new, self.b, self.installation, self.a['package_id'])
        self.assert_old_intact()
        release.install(self.new, self.b, self.installation, self.a['package_id'])
        self.assertEqual(release.current(self.installation)[1], self.b)

    def test_interrupted_pointer_commit_recovers_verified_version(self):
        original = release.write
        def fail_pointer(path, value):
            if Path(path).name == 'CURRENT.json':
                raise OSError('interrupted pointer commit')
            return original(path, value)
        with patch.object(release, 'write', side_effect=fail_pointer):
            with self.assertRaisesRegex(OSError, 'pointer'):
                release.install(self.new, self.b, self.installation, self.a['package_id'])
        self.assert_old_intact()
        result = release.install(self.new, self.b, self.installation, self.a['package_id'])
        self.assertTrue(result['recovered_verified_version'])
        self.assertEqual(release.current(self.installation)[1], self.b)

    def test_extra_file_and_symlink_rejected(self):
        extra = self.new / 'unexpected'
        extra.write_text('unmanifested')
        with self.assertRaisesRegex(ValueError, 'differ'):
            release.verify_package(self.new, self.b)
        extra.unlink()
        extra.symlink_to(self.state)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            release.verify_package(self.new, self.b)

    def test_renamed_elf_is_not_windows_binary(self):
        manifest = release.seal(dict(self.b, platform='Win64', binary_format='PE32+-x86_64'))
        with self.assertRaisesRegex(ValueError, 'format'):
            release.verify_package(self.new, manifest)

    def test_manifest_tamper_traversal_and_case_collision_rejected(self):
        manifest = copy.deepcopy(self.b)
        manifest['files'][0]['bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'digest'):
            release.validate_manifest(manifest)
        for bad in ('../escape', '/absolute', 'C:/escape', 'dir\\escape', 'CON.txt', 'trailing.', 'dir//file'):
            with self.assertRaises(ValueError):
                release.safe_path(bad)
        manifest = copy.deepcopy(self.b)
        manifest['files'].append(dict(manifest['files'][0], path=manifest['files'][0]['path'].upper()))
        with self.assertRaisesRegex(ValueError, 'colliding'):
            release.validate_manifest(release.seal(manifest))

    def test_manifest_rejects_extraction_changed_after_stage(self):
        # Explicitly synthetic stage fixture: this tests receipt binding only.
        payload = self.root / 'readback/Linux'
        shutil.copytree(self.new, payload)
        archive = self.root / 'fixture.archive'
        archive.write_bytes(b'SYNTHETIC_TEST_ARCHIVE_NOT_GAMEPLAY_EVIDENCE')
        cook = self.root / 'fixture-cook.json'
        release.write(cook, {'result': 'PASS', 'inputs_before': []})
        stage = self.root / 'fixture-stage.json'
        release.write(stage, {'result': 'PASS', 'archive': release.identity(archive),
            'cook': release.identity(cook), 'archive_readback': str(payload.parent),
            'readback_members': [release.identity(path) for path in sorted(payload.iterdir())]})
        source = self.root / 'fixture-source.json'
        release.write(source, {'material_inputs': []})
        (payload / 'content.pak').write_bytes(b'changed since archive readback')
        with self.assertRaisesRegex(ValueError, 'extraction changed'):
            release.package_manifest(stage, source, self.root / 'must-not-exist.json')
        self.assertFalse((self.root / 'must-not-exist.json').exists())

    def test_parallel_installer_cannot_switch_pointer(self):
        with release.install_lock(self.installation):
            with self.assertRaises(OSError):
                release.install(self.new, self.b, self.installation, self.a['package_id'])
        self.assert_old_intact()


if __name__ == '__main__':
    unittest.main()
