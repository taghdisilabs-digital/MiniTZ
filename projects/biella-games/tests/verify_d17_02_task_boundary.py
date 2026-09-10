#!/usr/bin/env python3
"""Verify D17-02 persisted bytes; integrity is not gameplay/visual acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def check(item):
    path = Path(item['path'])
    if not path.is_absolute():
        path = PROJECT / path
    assert path.stat().st_size == item['bytes'], 'Size changed: ' + str(path)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert digest == item['sha256'], 'Digest changed: ' + str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path,
                        default=PROJECT/'Build/AAA/D17-02/task-owned-files.json')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    assert manifest['task_id'] == 'D17-02'
    assert len({x['path'] for x in manifest['files']}) == len(manifest['files'])
    for item in manifest['files']:
        check(item)
    q = json.loads((PROJECT/'Build/AAA/D17-02/qualification.json').read_text())
    assert q['task_id'] == 'D17-02'
    for key in ('editable_source_and_assets', 'exact_evidence'):
        for item in q[key]:
            check(item)
    current_source = q.get('current_source_manifest',
                           'Build/AAA/D17-02/build/package-01/source-build.json')
    source = json.loads((PROJECT/current_source).read_text())
    assert source['material_input_digest'] == q['current_material_input_digest']
    for item in source['material_inputs']:
        check(item)
    package_path = q.get('runtime_package_manifest', 'Build/AAA/D17-02/build/package-01/package-manifest.json')
    package = json.loads((PROJECT/package_path).read_text())
    assert package['package_id'] == q['runtime_package']
    check(package['archive'])
    for run in q.get('current_raw_runs', []):
        directory = PROJECT / run['path']
        observed = json.loads((directory/'measurements.json').read_text())
        assert observed['route_complete'] == run['route_complete']
        assert observed['faults'] == run['faults']
        for item in observed['evidence'].values():
            check(item)
        resolved = json.loads((directory/'resolved-package.json').read_text())
        assert resolved['base_package_id'] == q['runtime_package']
        assert resolved['runtime_id'] == run['runtime_id']
        native = json.loads((directory/'native-source.json').read_text())
        assert native['material_input_digest'] == source['material_input_digest']
        if 'native_delta' in resolved:
            check(resolved['native_delta'])
    if q['unmet_criteria']:
        assert q['acceptance'] is False and q['status'] == 'IN_PROGRESS'
    print(json.dumps(dict(task_id='D17-02', result='PASS',
        scope='Exact task-owned file, current material source and resolved runtime integrity only; no visual acceptance',
        task_files=len(manifest['files']), material_inputs=len(source['material_inputs']),
        acceptance=q['acceptance'], unmet_criteria=q['unmet_criteria']), indent=2))


if __name__ == '__main__':
    main()
