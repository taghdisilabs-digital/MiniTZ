#!/usr/bin/env python3
"""Join isolated cold/warm package receipts without rewriting native evidence."""
import argparse
import json
from pathlib import Path
import re
from run_d01_039 import file_identity, write_json


def verify(root, negative):
    result = dict(task_id='D03-01', result='PASS', profiles={},
                  input=file_identity(Path(__file__).resolve()),
                  scope='Linux Development Vulkan SM5; one host; fresh user/driver caches, not flushed OS pages; no generated frames')
    archive = None
    for short, profile in [('tsr', 'ProductionTSR'), ('taa', 'NativeTAA')]:
        runs, previous = {}, None
        for phase in ['cold', 'warm', 'environment']:
            directory = root/f'package-{short}-{phase}-01'
            path = directory/'validation.json'
            report = json.loads(path.read_text())
            assert report['result'] == 'PASS' and report['profile'] == profile, f'Unqualified {directory}'
            if archive is None:
                archive = report['archive']
            assert report['archive'] == archive, 'Runs use different package archives'
            assert report['inputs_before'] == report['inputs_after'], 'Verification inputs changed'
            assert report['package_before'] == report['package_after'], 'Package changed during runtime'
            assert report['state_before'] == (previous['state_after'] if previous else []), 'Cache continuity differs'
            probe = json.loads((directory/'isolation-probe.json').read_text())
            assert probe['network_interfaces'] == ['lo'] and not any(probe['hidden_path_exists'].values()), 'Isolation not proven'
            log = (directory/'runtime.stdout.log').read_text()
            assert 'SF_VULKAN_SM5' in log, 'Actual shader platform missing'
            libraries = {name: int(count) for name, count in re.findall(
                r'Using IoDispatcher for shader code library (\w+). Total (\d+) unique shaders.', log)}
            assert libraries.get('Global', 0) > 0 and libraries.get('BiellaGames', 0) > 0, 'Packaged shader libraries missing'
            init = re.search(r'\(Engine Initialization\) Total time: ([\d.]+) seconds', log)
            assert init, 'Engine initialization timing missing'
            hitches = report['pso_hitches']
            driver_files = [entry for entry in report['state_after'] if '/xdg-cache/' in entry['path']]
            runs[phase] = dict(receipt=file_identity(path),
                frames=report['verification']['frames'],
                captures=len(report['verification']['captures']),
                native_views=report['native_views']['joined_scenario_frames'],
                shader_libraries=libraries, engine_initialization_seconds=float(init[1]),
                pso_hitches_over_20ms=len(hitches),
                pso_max_creation_ms=max((x['milliseconds'] for x in hitches), default=0),
                pso_by_kind={kind: sum(x['kind'] == kind for x in hitches) for kind in ('graphics', 'compute')},
                driver_cache_files=driver_files,
                costs=report['verification'].get('costs'),
                native_pso_observations=[line for line in report['pso_observations']
                    if 'Binary pipeline cache' in line or 'Vulkan PSO Precaching' in line])
            previous = report
        result['profiles'][profile] = runs
    rejection = json.loads(negative.read_text())
    assert rejection['result'] == 'PASS' and rejection['archive'] == archive, 'Missing shader control not proven'
    result['negative'] = file_identity(negative)
    result['archive'] = archive
    result['limitations'] = [
        'Vulkan SM5 does not execute Nanite despite requested r.Nanite=1; SM6 production qualification remains.',
        'PSO event durations may overlap across workers and are not additive frame stalls.',
        'Cold runtime PSO hitches remain; functional PASS does not accept production stutter.',
        'PipelineFileCache=0 and VulkanPSO.cache absent; observed warm acceleration uses driver cache files.',
        'Gross image delta checks and selected captures do not establish fine ghosting/disocclusion quality.',
        'Development executable, not Shipping, Windows, broad hardware, final art or complete D03 acceptance.'
    ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--negative', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve prior series receipts'
    result = verify(args.root.resolve(), args.negative.resolve())
    write_json(args.output, result)
    print(json.dumps(dict(result=result['result'], output=str(args.output))))


if __name__ == '__main__':
    main()
