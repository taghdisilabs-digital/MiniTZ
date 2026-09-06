#!/usr/bin/env python3
"""Read back closed D03 audio evidence and preserve prior increment identities."""
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from PIL import Image
from run_d01_039 import PROJECT
from run_d02_01 import reject_material_fallbacks, runtime_has_task_error
from verify_d03_01_audio_mix import measure, qualify_mix


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_identity(entry):
    path = Path(entry['path'])
    assert digest(path) == entry['sha256'], str(path)
    if 'bytes' in entry:
        assert path.stat().st_size == entry['bytes'], str(path)


def main():
    evidence = PROJECT / 'Build/Presentation'
    native = json.loads((evidence / 'audio-runtime-03/validation.json').read_text())
    regression = json.loads((evidence / 'audio-feedback-regression-01/validation.json').read_text())
    reconciliation = json.loads((evidence / 'audio-finalization-01/authority-reconciliation.json').read_text())
    controls = json.loads((evidence / 'audio-finalization-01/validator-controls.json').read_text())
    finalized_log = json.loads((evidence / 'audio-finalization-01/regression-log-finalization.json').read_text())
    assert reconciliation['result'] == 'RECONCILED_TRANSIENT_AUTHORITY_CHANGE'
    assert native['error'] == 'Protected authority changed'
    assert native['identities_before'] == native['identities_after']
    assert native['runtime']['log_finalization']['closed']
    assert regression['result'] == 'PASS' and controls['result'] == 'PASS'
    assert len(controls['negative_controls']) == 6
    counts = {}
    for name, report in [('native', native), ('regression', regression)]:
        assert report['runtime']['returncode'] == 0 and not report['runtime']['timed_out']
        assert report['identities_before'] == report['identities_after']
        for entry in report['identities_after'] + report['protected_before']:
            check_identity(entry)
        if name == 'regression':
            assert finalized_log['result'] == 'PASS' and finalized_log['finalization']['closed']
            assert finalized_log['original'] == report['runtime']['log']
            original = finalized_log['original']
            raw = Path(original['path']).read_bytes()
            assert hashlib.sha256(raw[:original['bytes']]).hexdigest() == original['sha256']
            assert raw[original['bytes']:].decode() == finalized_log['appended_text']
            check_identity(finalized_log['final'])
        else:
            check_identity(report['runtime']['log'])
        counts[name] = len(report['identities_after'])
    for change in reconciliation['changed']:
        check_identity(change['current'])
        assert change['current'] == change['before']
    log = Path(native['runtime']['log']['path']).read_text(errors='replace')
    assert re.search(r'Test Completed\. Result=\{Success\} Name=\{AudioMix\}', log)
    assert 'D03_AUDIO_COMPLETE success=1' in log and not runtime_has_task_error(log)
    reject_material_fallbacks(log)
    assert json.loads((evidence / 'audio-runtime-03/result.json').read_text(encoding='utf-8-sig'))['success']
    mix = measure(evidence / 'audio-runtime-03')
    qualify_mix(mix)
    assert mix == native['mix']
    captures = mix['recordings'] + regression['audio'] + regression['frames']
    for entry in captures:
        check_identity(entry)
    with Image.open(evidence / 'audio-runtime-03/mixed.png') as image:
        image.load()
        assert image.size == (1280, 720)
    with (evidence / 'audio-runtime-03/release.csv').open() as stream:
        samples = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(stream)]
    assert samples and all(0.25 <= row['gain'] <= 1.001 for row in samples)
    assert all(b['gain'] >= a['gain'] for a, b in zip(samples, samples[1:]))
    assert any(row['age'] >= 0.2 and row['gain'] >= 0.99 for row in samples)
    preservation = []
    for filename in ['D03-01-file-manifest.json', 'D03-01-animation-file-manifest.json']:
        manifest_path = evidence / filename
        manifest = json.loads(manifest_path.read_text())
        for entry in manifest['files']:
            path = PROJECT / entry['path']
            raw = os.readlink(path).encode() if entry['kind'] == 'symlink' else path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == entry['sha256'], str(path)
            assert len(raw) == entry.get('size', entry.get('bytes')), str(path)
        preservation.append(dict(path=str(manifest_path), sha256=digest(manifest_path),
                                 verified_entries=len(manifest['files'])))
    result = dict(task_id='D03-01', increment='critical cue combat ducking', result='PASS', task_status='CONTINUE',
                  verified_at=datetime.now(timezone.utc).isoformat(), mix=mix, release_samples=len(samples),
                  current_input_identity_counts=counts, final_capture_identities=len(captures),
                  predecessor_manifests=preservation, protected_current=native['protected_before'],
                  native_report_admission='Only transient authority hash change invalidated runtime-03. Original FAIL retained. Same task authority reconciled; native success, clean runtime, mixer, source/build/assets and current authority rechecked here.',
                  regression_report='audio-feedback-regression-01/validation.json', negative_controls=6,
                  limitations='Software mixer, fixed game delta, SDL dummy device; no speaker, packaged-build or launch-platform qualification. No final art or full D03 acceptance.')
    target = evidence / 'D03-01-audio-final-readback.json'
    assert not target.exists(), 'Preserve earlier readback'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['result', 'release_samples', 'current_input_identity_counts', 'final_capture_identities', 'negative_controls']}))


if __name__ == '__main__':
    main()
