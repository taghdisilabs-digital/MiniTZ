#!/usr/bin/env python3
"""Restore only the observed AFS editor-generated suffix in a D08 cook snapshot."""
import argparse
from pathlib import Path
import re
import shutil

import run_d08_01_release as release


def restore(cook_path, output):
    cook = release.read(cook_path)
    release.require(cook['task_id'] == 'D08-01' and cook['result'] == 'PASS', 'Expected successful D08 cook')
    release.require(not output.exists(), 'Fresh recovery proof required')
    snapshot = Path(cook['snapshot'])
    target = snapshot / 'Config/DefaultEngine.ini'
    canonical = release.PROJECT / 'Config/DefaultEngine.ini'
    canonical_bytes = canonical.read_bytes()
    generated = target.read_bytes()
    release.require(generated.startswith(canonical_bytes), 'Cook changed existing canonical configuration')
    suffix = generated[len(canonical_bytes):].decode()
    lines = [line for line in suffix.splitlines() if line]
    release.require(lines[0] == '[/Script/AndroidFileServerEditor.AndroidFileServerRuntimeSettings]',
                    'Unknown generated configuration section')
    expected = {'bEnablePlugin': 'True', 'bAllowNetworkConnection': 'True',
        'bIncludeInShipping': 'False', 'bAllowExternalStartInShipping': 'False',
        'bCompileAFSProject': 'False', 'bUseCompression': 'False', 'bLogFiles': 'False',
        'bReportStats': 'False', 'ConnectionType': 'USBOnly', 'bUseManualIPAddress': 'False', 'ManualIPAddress': ''}
    values = dict(line.split('=', 1) for line in lines[1:])
    token = values.pop('SecurityToken', '')
    release.require(re.fullmatch('[0-9A-F]{32}', token) is not None and values == expected
                    and len(lines) == len(expected) + 2, 'Unknown AFS configuration mutation')
    records = cook['snapshot_inputs'] + cook['snapshot_binaries'] + cook['cooked_files']
    for row in records:
        if Path(row['path']) == target:
            release.require(release.identity(canonical)['sha256'] == row['sha256'], 'Canonical input changed')
        else:
            release.require(release.identity(row['path']) == row, 'Another cook input/output changed')
    for row in cook['inputs_before']:
        release.require(release.identity(row['path']) == row, 'Canonical source changed')
    # Retain exact raw evidence privately; never print or publish the generated token.
    private = Path(cook['workspace']) / 'generated-editor-config-evidence'
    private.mkdir(mode=0o700)
    raw = private / 'DefaultEngine.generated.ini'
    shutil.copyfile(target, raw)
    raw.chmod(0o600)
    shutil.copyfile(canonical, target)
    for row in records:
        release.require(release.identity(row['path']) == row, 'Restored cook input/output readback differs')
    plugin = release.ENGINE / 'Plugins/Runtime/AndroidFileServer'
    release.write(output, {'task_id': 'D08-01', 'result': 'PASS', 'observed': release.now(),
        'cook': release.identity(cook_path), 'implementation': release.identity(__file__),
        'canonical': release.identity(canonical), 'generated_raw_private': release.identity(raw),
        'restored_snapshot': release.identity(target), 'unchanged_other_records': len(records) - 1,
        'observed_editor_side_effect': 'PostInitProperties appends its default Android File Server settings and generates a token. Existing configuration bytes were untouched. All other snapshot inputs, binaries and cooked outputs match the original receipt.',
        'source_evidence': [release.identity(plugin / name) for name in (
            'AndroidFileServer.uplugin',
            'Source/AndroidFileServerEditor/Private/AndroidFileServerRuntimeSettings.cpp',
            'Source/AndroidFileServer/Private/AndroidFileServerBPLibrary.cpp')],
        'scope': 'The AFS editor module contains no content; file-server operations are PLATFORM_ANDROID guarded. Canonical Linux settings restored exactly before UAT stage. Cook receipt and cooked bytes preserved; no shader recook or Project configuration change.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cook', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        restore(args.cook.resolve(), args.output.resolve())
        print(release.json.dumps({'result': 'PASS', 'output': str(args.output)}))
    except (ValueError, OSError, KeyError, IndexError) as error:
        with release.LEDGER.open('a') as stream:
            stream.write(release.json.dumps({'task_id': 'D08-01', 'time': release.now(),
                'type': 'cook_snapshot_config_recovery', 'status': 'CONTINUE', 'diagnostics': str(error)[:2000]}) + '\n')
        raise
