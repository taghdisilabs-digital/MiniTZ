#!/usr/bin/env python3
"""Repair the observed Android editor first-run append in D17's Linux cook copy.

This accepts only the exact original prefix plus the known Android settings
section. All other cook inputs/outputs must match. The modified file is retained
privately in the temporary workspace; generated authentication data is neither
printed nor added to public evidence. Canonical source is never changed.
"""
import json
import argparse
from pathlib import Path
import shutil

from run_d08_01_release import identity, now, write


PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / 'Build/AAA/D17-01/build'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cook', type=Path, default=ROOT / 'cook-02/validation.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'cook-config-recovery.json')
    args = parser.parse_args()
    cook = json.loads(args.cook.read_text())
    assert cook['result'] == 'PASS'
    snapshot = Path(cook['snapshot'])
    config = snapshot / 'Config/DefaultEngine.ini'
    source = PROJECT / 'Config/DefaultEngine.ini'
    expected = next(r for r in cook['snapshot_inputs'] if r['path'] == str(config))
    source_id = identity(source)
    assert all(source_id[k] == expected[k] for k in ('sha256', 'bytes'))
    original, modified = source.read_bytes(), config.read_bytes()
    assert modified.startswith(original)
    suffix = modified[len(original):].decode('utf-8')
    lines = [line for line in suffix.splitlines() if line]
    assert lines[0] == '[/Script/AndroidFileServerEditor.AndroidFileServerRuntimeSettings]'
    keys = [line.split('=', 1)[0] for line in lines[1:]]
    assert keys == ['bEnablePlugin', 'bAllowNetworkConnection', 'SecurityToken',
                    'bIncludeInShipping', 'bAllowExternalStartInShipping',
                    'bCompileAFSProject', 'bUseCompression', 'bLogFiles',
                    'bReportStats', 'ConnectionType', 'bUseManualIPAddress', 'ManualIPAddress']
    all_files = cook['snapshot_inputs'] + cook['snapshot_binaries'] + cook['cooked_files']
    for row in all_files:
        if row['path'] != str(config):
            assert identity(row['path']) == row, row['path']
    private_copy = Path(cook['workspace']) / 'cook-config-generated-original.ini'
    assert not private_copy.exists(), 'Recovery already applied; inspect its receipt'
    with private_copy.open('xb') as stream:
        stream.write(modified)
    private_copy.chmod(0o600)
    before = identity(config)
    shutil.copyfile(source, config)
    assert identity(config) == expected
    for row in all_files:
        assert identity(row['path']) == row, row['path']
    cause = Path('/opt/unreal/UE_5.8.2/Engine/Plugins/Runtime/AndroidFileServer/Source/AndroidFileServerEditor/Private/AndroidFileServerRuntimeSettings.cpp')
    write(args.output, dict(
        task_id='D17-01', result='PASS', observed=now(), runner=identity(__file__),
        cook=identity(args.cook), changed_input=before,
        restored_input=identity(config), canonical_source=source_id,
        private_original=identity(private_copy), appended_section=lines[0],
        appended_keys=keys, engine_cause=identity(cause),
        cause='UAndroidFileServerRuntimeSettings::PostInitProperties generates first-run config through TryUpdateDefaultConfigFile',
        scope='Linux cook temporary config restored to verified input bytes; all other snapshot inputs, binaries and cooked outputs match',
        verified_file_count=len(all_files)))
    print(json.dumps(dict(result='PASS', verified_files=len(all_files))))


if __name__ == '__main__':
    main()
