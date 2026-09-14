#!/usr/bin/env python3
"""Preserve and remove only UE's observed Android editor-default append in a Linux cook snapshot."""
import argparse
import configparser
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
from run_d01_039 import PROJECT, file_identity, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cook', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists(), 'Fresh evidence required'
    out.mkdir(parents=True)
    report = dict(task_id='D03-01', result='FAIL')
    try:
        cook = json.loads((args.cook/'validation.json').read_text())
        assert cook['result'] == 'PASS', 'Cook must have passed'
        snapshot = Path(cook['snapshot'])
        target = snapshot/'Config/DefaultEngine.ini'
        canonical = PROJECT/'Config/DefaultEngine.ini'
        expected = next(x for x in cook['snapshot_inputs'] if x['path'] == str(target))
        original, generated = canonical.read_bytes(), target.read_bytes()
        assert file_identity(canonical)['sha256'] == expected['sha256'], 'Canonical input changed'
        assert generated.startswith(original), 'Unexpected edit beyond appended defaults'
        appended = generated[len(original):].decode('utf-8')
        settings = configparser.ConfigParser()
        settings.read_string(appended)
        section = '/Script/AndroidFileServerEditor.AndroidFileServerRuntimeSettings'
        assert settings.sections() == [section], 'Unexpected appended section'
        values = dict(settings[section])
        token = values.pop('securitytoken', '')
        assert re.fullmatch('[A-F0-9]{32}', token), 'Unexpected generated default format'
        assert values == dict(benableplugin='True', ballownetworkconnection='True',
                             bincludeinshipping='False', ballowexternalstartinshipping='False',
                             bcompileafsproject='False', busecompression='False', blogfiles='False',
                             breportstats='False', connectiontype='USBOnly', busemanualipaddress='False',
                             manualipaddress=''), 'Unexpected generated Android defaults'
        # The raw generated token stays only in a private local recovery copy.
        backup = snapshot.parent/'cook-side-effects/DefaultEngine.ini'
        backup.parent.mkdir(mode=0o700)
        shutil.copy2(target, backup)
        backup.chmod(0o600)
        report.update(cook=file_identity(args.cook.resolve()/'validation.json'),
                      before=file_identity(target), private_backup=file_identity(backup),
                      engine_source=file_identity(Path('/opt/unreal/UE_5.8.2/Engine/Plugins/Runtime/AndroidFileServer/Source/AndroidFileServerEditor/Private/AndroidFileServerRuntimeSettings.cpp')),
                      reason='PostInitProperties appends Android editor defaults; Linux content and canonical project unchanged',
                      appended_section=section, generated_token_value_recorded=False)
        target.write_bytes(original)
        report['after'] = file_identity(target)
        assert report['after'] == expected, 'Canonical byte restoration failed'
        for item in cook['snapshot_inputs'] + cook['snapshot_binaries'] + cook['cooked_files']:
            assert file_identity(Path(item['path'])) == item, 'Other cook input/output changed'
        report['result'] = 'PASS'
    except (AssertionError, OSError, ValueError, KeyError, configparser.Error) as error:
        report['error'] = str(error)
    write_json(out/'validation.json', report)
    with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                    type='cook_snapshot_config_mutation', status='RECOVERED' if report['result']=='PASS' else 'CONTINUE',
                                    diagnostics=report.get('error', report.get('reason')), evidence=str(out)))+'\n')
    print(json.dumps(dict(result=report['result'], output=str(out), error=report.get('error'))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
