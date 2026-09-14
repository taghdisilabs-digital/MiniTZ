#!/usr/bin/env python3
"""Read back the package qualification's source, binary, archive and runtime lineage."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from PIL import Image
from run_d01_039 import PROJECT, file_identity, write_json
from run_d03_01_package import members
from verify_d03_01_package_series import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve prior readbacks'
    root = PROJECT/'Build/Presentation'
    checked = {}
    report = dict(task_id='D03-01', result='FAIL', input=file_identity(Path(__file__).resolve()))

    def check(item):
        assert file_identity(Path(item['path'])) == item, f'Identity changed: {item["path"]}'
        checked[item['path']] = item

    def read(relative):
        path = root/relative
        check(file_identity(path))
        return json.loads(path.read_text())

    try:
        build = read('package-build-03/result.json')
        assert build['result'] == 'PASS' and build['inputs_unchanged'], 'Build not qualified'
        sources = read('package-build-03/inputs-after.json')
        assert sources == read('package-build-03/inputs-before.json'), 'Build inputs changed'
        for item in sources + [build['binary'], build['marker_after']]:
            check(item)
        cook = read('package-cook-01/validation.json')
        assert cook['result'] == 'PASS' and cook['cache_before'] == [], 'Isolated cook not qualified'
        assert cook['inputs_before'] == cook['inputs_after'], 'Cook changed canonical inputs'
        for key in ('inputs_after', 'snapshot_inputs', 'snapshot_binaries', 'cooked_files'):
            for item in cook[key]:
                check(item)
        check(cook['editor'])
        check(cook['editor_module'])
        dependency = read('package-toolchain-02/validation.json')
        assert dependency['result'] == 'PASS', 'Engine repair not qualified'
        assert dependency['mimalloc_existing_before'] == dependency['mimalloc_existing_after'], 'Existing engine headers changed'
        for item in dependency['added_files'] + dependency['mimalloc_existing_after'] + dependency['licenses'] + [dependency['rules_after']]:
            check(item)
        stage_path = root/'package-stage-07/validation.json'
        stage = read('package-stage-07/validation.json')
        assert stage['result'] == 'PASS', 'Stage not qualified'
        check(stage['cook'])
        check(stage['dependencies'])
        check(stage['archive'])
        assert members(Path(stage['archive_readback'])) == stage['readback_members'], 'Archive readback changed'
        for item in stage['members'] + stage['readback_members']:
            check(item)
        packaged_binary = next(x for x in stage['readback_members'] if x['path'].endswith('/Binaries/Linux/BiellaGames'))
        assert packaged_binary['sha256'] == build['binary']['sha256'], 'Native binary lineage differs'
        series = read('package-series-01.json')
        negative_path = root/'package-missing-shader-04/validation.json'
        assert verify(root, negative_path) == series, 'Series no longer reproduces'
        captures = []
        for runs in series['profiles'].values():
            for summary in runs.values():
                check(summary['receipt'])
                path = Path(summary['receipt']['path'])
                run = json.loads(path.read_text())
                assert run['stage'] == file_identity(stage_path), 'Runtime stage lineage differs'
                check(run['runtime']['log'])
                for item in run['inputs_after']:
                    check(item)
                for item in run['verification']['captures']:
                    image_path = path.parent/'captures'/f'{item["name"]}.png' if isinstance(item, dict) else Path(item)
                    identity = file_identity(image_path)
                    if isinstance(item, dict):
                        assert identity['sha256'] == item['sha256'] and identity['bytes'] == item['bytes'], 'Capture changed'
                    with Image.open(image_path) as image:
                        image.load()
                        assert image.size == (1280, 720), 'Unexpected native capture dimensions'
                    captures.append(identity)
        negative = read('package-missing-shader-04/validation.json')
        check(negative['input'])
        check(negative['positive'])
        check(negative['runtime']['log'])
        assert negative['canonical_before'] == negative['canonical_after'] == stage['readback_members'], 'Negative changed original package'
        assert negative['archive'] == negative['archive_after'] == stage['archive'], 'Negative archive lineage differs'
        mutation = negative['mutation']
        for item in [mutation['original_pak'], mutation['mutated_pak'], mutation['withheld'], mutation['engine_source']] + mutation['logical_files_after']:
            check(item)
        original = {Path(x['path']).relative_to(Path(mutation['withheld']['path']).parent.parent/'extracted').as_posix(): x
                    for x in mutation['logical_files_before']}
        assert original.pop('Engine/GlobalShaderCache-VULKAN_SM5.bin')['sha256'] == mutation['withheld']['sha256'], 'Wrong shader cache withheld'
        actual = {Path(x['path']).relative_to(Path(mutation['withheld']['path']).parent.parent/'repacked-readback').as_posix(): x['sha256']
                  for x in mutation['logical_files_after']}
        assert {name: item['sha256'] for name, item in original.items()} == actual, 'Other logical pak bytes changed'
        report.update(result='PASS', build_source_files=len(sources), canonical_cook_inputs=len(cook['inputs_after']),
                      native_binary=packaged_binary, archive=stage['archive'], archive_members=len(stage['readback_members']),
                      positive_frames=sum(s['frames'] for r in series['profiles'].values() for s in r.values()),
                      captures=captures, negative_preserved_logical_files=len(actual),
                      scope=series['scope'], limitations=series['limitations'])
    except (AssertionError, OSError, ValueError, KeyError) as error:
        report['error'] = str(error)
    report['identities'] = sorted(checked.values(), key=lambda x: x['path'])
    write_json(args.output, report)
    if report['result'] != 'PASS':
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                        type='package_lineage_readback', status='CONTINUE', diagnostics=report.get('error'),
                                        evidence=str(args.output)))+'\n')
    print(json.dumps(dict(result=report['result'], output=str(args.output), identities=len(checked), error=report.get('error'))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
