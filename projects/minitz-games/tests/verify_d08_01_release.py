#!/usr/bin/env python3
"""Read back D08's real Linux diagnostic lineage; never infer Win64 RC status."""
import argparse
import os
import re
from pathlib import Path

import run_d08_01_release as release
from verify_d01_039 import verify as verify_gameplay


def receipt(path):
    value = release.read(path)
    release.require(value['result'] == 'PASS', f'Evidence did not pass: {path}')
    return value


def resource_summary(path, native_pids):
    rows = [release.json.loads(line) for line in path.open() if line.strip()]
    native = [(row['elapsed_seconds'], process) for row in rows for process in row['unreal']
              if process['pid'] in native_pids]
    release.require(native, 'No resource samples for the actual packaged game')
    first_time, first = native[0]
    last_time, last = native[-1]
    vram = []
    for row in rows:
        for gpu in row['gpus']:
            for process in gpu.get('processes', []):
                if process.get('pid') in native_pids:
                    match = re.fullmatch(r'([\d.]+) MiB', str(process.get('used_memory', '')))
                    if match:
                        vram.append(float(match.group(1)))
    return {'samples': len(rows), 'native_samples': len(native),
            'peak_rss_mib': max(process['rss_peak_kib'] for _, process in native) / 1024,
            'peak_swap_mib': max(process['swap_kib'] for _, process in native) / 1024,
            'average_cpu_core_equivalents': ((last['cpu_ticks'] - first['cpu_ticks']) /
                os.sysconf('SC_CLK_TCK') / (last_time - first_time)) if last_time > first_time else None,
            'native_reported_vram_peak_mib': max(vram) if vram else None,
            'scope': 'Sampled native process on a shared host; GPU memory is driver-reported, not an allocation lifetime audit. No approved performance budget inferred.'}


def verify(installation, runs):
    root = release.ROOT
    package = release.read(root / 'package-manifest.json')
    old = release.read(root / 'old-package-manifest.json')
    release.require(package['platform'] == 'Linux' and package['configuration'] == 'Development',
                    'This verifier qualifies Linux Development diagnostic evidence only')
    directory, installed = release.current(installation)
    release.require(installed == package and old['package_id'] != package['package_id'],
                    'Expected exact distinct old and current packages')
    release.verify_package(installation / 'versions' / old['package_id'] / 'payload', old)
    for manifest in (old, package):
        release.require(release.identity(manifest['archive']['path']) == manifest['archive'], 'Archive changed')
    update = receipt(root / 'install-update.json')
    release.require(update['from_package'] == old['package_id'] and
                    update['to_package'] == package['package_id'], 'Update lineage differs')
    debian_path = root / 'debian-02/validation.json'
    debian = receipt(debian_path)
    release.require(debian['package_id'] == package['package_id'] and
                    debian['manifest'] == release.identity(root / 'package-manifest.json') and
                    release.identity(debian['archive']['path']) == debian['archive'],
                    'Debian installer differs from this exact diagnostic package')
    for row in debian['evidence']:
        release.require(release.identity(row['path']) == row, 'Debian assembly evidence changed')
    negative = receipt(root / 'negative-real-package.json')
    release.require(negative['base_package_id'] == old['package_id'] and
                    negative['current_before'] == negative['current_after'] and len(negative['cases']) == 2,
                    'Real incomplete/incompatible update did not preserve the old version')
    tool_tests_path = root / 'tool-tests/final-03/validation.json'
    tool_tests = receipt(tool_tests_path)
    for row in tool_tests['inputs']:
        release.require(release.identity(row['path'])['sha256'] == row['sha256'],
                        'Installer changed after fault-injection tests')
    source = release.read(root / 'source-build-manifest.json')
    for key in ('build', 'engine', 'binary', 'receipt'):
        release.require(release.identity(source[key]['path']) == source[key], f'Source/build {key} changed')
    d07 = release.read(root / 'd07-reuse.json')
    for key in ('predecessor_manifest', 'predecessor_summary'):
        release.require(release.identity(d07[key]['path']) == d07[key], 'Retained D07 proof changed')
    release.require(release.identity(root / 'source-build-manifest.json') == package['source_manifest'],
                    'Package source manifest changed')
    for row in source['material_inputs']:
        actual = release.identity(release.PROJECT / row['path'])
        release.require(actual['sha256'] == row['sha256'] and actual['bytes'] == row['bytes'],
                        f'Current material source changed: {row["path"]}')
    stage = receipt(package['stage_receipt']['path'])
    release.require(release.identity(package['stage_receipt']['path']) == package['stage_receipt'],
                    'Stage receipt changed')
    cook = receipt(stage['cook']['path'])
    release.require(release.identity(stage['cook']['path']) == stage['cook'], 'Cook receipt changed')
    cook_recovery = receipt(root / 'cook-config-recovery.json')
    original_cook_identity = cook.get('original_cook', stage['cook'])
    release.require(cook_recovery['cook'] == original_cook_identity, 'Cook recovery belongs to another cook')
    if 'original_cook' in cook:
        original_cook = receipt(original_cook_identity['path'])
        release.require(release.identity(original_cook_identity['path']) == original_cook_identity,
                        'Original cook receipt changed')
        release.require(cook['scope'] == 'CONTENT_REUSE_WITH_REBUILT_AUTOMATION_PROBE_ONLY' and
                        cook['recook_performed'] is False and len(cook['changed_source']) == 1,
                        'Unexpected cook reuse scope')
        release.require(cook['native_build'] == source['build'], 'Reused content has another native build')
        for row in original_cook['snapshot_inputs'] + original_cook['snapshot_binaries'] + original_cook['cooked_files']:
            release.require(release.identity(row['path']) == row, 'Original cook evidence changed')
        release.require([(r['sha256'], r['bytes']) for r in cook['cooked_files']] ==
                        [(r['sha256'], r['bytes']) for r in original_cook['cooked_files']],
                        'Reused cooked output differs')
    for row in cook['snapshot_inputs'] + cook['snapshot_binaries'] + cook['cooked_files']:
        release.require(release.identity(row['path']) == row, 'Staged input or cooked output changed')
    release.require(release.identity(cook_recovery['restored_snapshot']['path']) ==
                    cook_recovery['restored_snapshot'], 'Recovered canonical stage configuration changed')
    release.require(source['material_inputs'] == [dict(row, path=str(Path(row['path']).relative_to(release.PROJECT)))
                    for row in cook['inputs_before']], 'Cook/source identity differs')
    grouped = {}
    for path in runs:
        report = release.read(path / 'validation.json')
        revalidate_population = (report['result'] == 'FAIL' and report['scenario'] == 'population'
                                and report.get('error') == 'No explained finish and suspension')
        release.require(report['result'] == 'PASS' or revalidate_population,
                        f'Evidence did not pass: {path}')
        release.require(report['package_id'] == package['package_id'], 'Run belongs to another package')
        runtime = report['runtime']
        release.require(runtime['returncode'] == 0 and not runtime['watchdog_failure'] and
                        not runtime['survivors'] and runtime['log_finalization']['closed'] and
                        runtime['unreal_process_identities'], 'Native process lifecycle did not pass')
        for row in report['evidence']:
            release.require(release.identity(row['path']) == row, f'Runtime raw evidence changed: {row["path"]}')
        if revalidate_population:
            from verify_d02_02 import verify as verify_population
            from run_d02_01 import runtime_has_task_error, reject_material_fallbacks
            log = (path / 'runtime.stdout.log').read_text(errors='replace')
            release.require('**** TEST COMPLETE. EXIT CODE: 0 ****' in log and
                            re.search(r'Result=\{Success\}.*Name=\{Population\}', log) and
                            not runtime_has_task_error(log), 'Population native completion failed')
            reject_material_fallbacks(log)
            report['verification'] = verify_population(path, 4)
            report['diagnostics'] = [line[:1500] for line in log.splitlines()
                                     if re.search(r'\b(Warning|Error):', line)]
            revalidation_path = root / 'population-revalidation.json'
            release.write(revalidation_path, {
                'task_id': 'D08-01', 'result': 'PASS', 'observed': release.now(),
                'package_id': package['package_id'],
                'original_failure': release.identity(path / 'validation.json'),
                'verifier': release.identity(release.PROJECT / 'tests/verify_d02_02.py'),
                'verification': report['verification'],
                'scope': 'Exact retained native evidence revalidated after allowing FName reason token capitalization. Original failed receipt and raw bytes are preserved; no gameplay replay or acceptance relaxation.'})
            report['revalidation'] = release.identity(revalidation_path)
        grouped.setdefault(report['scenario'], []).append((path, report))
    release.require(set(grouped) == set(release.SCENARIOS), 'A current package scenario is missing')
    release.require(len(grouped['core']) == 2, 'Two independent gameplay processes required')
    gameplay = verify_gameplay([path / 'telemetry.jsonl' for path, _ in grouped['core']])
    settings = {report['verification']['phase']: report for _, report in grouped['settings']}
    release.require(set(settings) == {'legacy', 'write', 'read'} and len(grouped['settings']) == 3,
                    'Settings legacy/write/read processes missing')
    settings_pids = [settings[phase]['verification']['process_id'] for phase in ('legacy', 'write', 'read')]
    release.require(len(set(settings_pids)) == 3, 'Settings reconstruction reused one process')
    legacy = release.identity(root / 'legacy-GameUserSettings.ini')
    release.require(any(row['sha256'] == legacy['sha256'] for row in settings['legacy']['settings_before']),
                    'New package did not receive the retained old runtime settings')
    release.require(settings['write']['settings_after'] == settings['read']['settings_before'],
                    'Settings bytes changed between write teardown and read startup')
    release.require(len({settings[phase]['state'] for phase in settings}) == 1,
                    'Settings runs did not share the same per-user state')
    for phase in settings:
        release.require(settings[phase]['verification']['result'] == 'PASS', 'Native settings probe failed')
    old_run = receipt(root / 'runtime/old-environment-02/validation.json')
    release.require(old_run['package_id'] == old['package_id'] and not old_run['runtime']['survivors'],
                    'Retained build native baseline missing')
    observations = []
    for scenario, values in grouped.items():
        for path, report in values:
            log = (path / 'runtime.stdout.log').read_text(errors='replace')
            observations.append({'scenario': scenario, 'run': release.identity(path / 'validation.json'),
                'revalidation': report.get('revalidation'),
                'elapsed_seconds': report['runtime']['elapsed_seconds'],
                'native_processes': report['runtime']['unreal_process_identities'],
                'diagnostics': report['diagnostics'],
                'startup_seconds': re.findall(r'Engine is initialized\. Leaving FEngineLoop::Init\(\) took ([\d.]+)', log),
                'verification': report['verification'],
                'resources': release.identity(path / 'resources.jsonl'),
                'resource_summary': resource_summary(path / 'resources.jsonl',
                    {p['pid'] for p in report['runtime']['unreal_process_identities']})})
    result = {
        'schema': 'biella.d08.qualification/v1', 'task_id': 'D08-01', 'observed': release.now(),
        'status': 'CONTINUE', 'release_candidate': False,
        'linux_diagnostic_lineage': 'PASS',
        'scope': 'Exact Linux Development cooked package, outside-editor native gameplay and transactional update. Win64 Shipping remains unqualified.',
        'old_package_id': old['package_id'], 'package_id': package['package_id'],
        'package_manifest': release.identity(root / 'package-manifest.json'), 'archive': package['archive'],
        'debian_installer': {'validation': release.identity(debian_path), 'archive': debian['archive'],
                            'scope': debian['scope']},
        'source_manifest': release.identity(root / 'source-build-manifest.json'),
        'build': source['build'], 'cook': stage['cook'], 'stage': package['stage_receipt'],
        'cook_config_recovery': release.identity(root / 'cook-config-recovery.json'),
        'update': release.identity(root / 'install-update.json'),
        'negative_controls': release.identity(root / 'negative-real-package.json'),
        'installer_fault_tests': release.identity(tool_tests_path),
        'legacy_settings': release.identity(root / 'legacy-settings-lineage.json'),
        'settings_native_pids': settings_pids, 'gameplay_comparison': gameplay,
        'runs': observations,
        'd07_reuse': release.identity(root / 'd07-reuse.json'),
        'limitations': [
            'Linux Vulkan on one shared L40S host, 1280x720 Xvfb; Development diagnostic automation is compiled out of Shipping.',
            'D07 measurements retain their original editor binary and all recorded risks. They are not package-specific Win64 performance acceptance.',
            'Approved quantitative hardware/frame-time/input-latency budgets remain UNKNOWN; raw hitches and warnings are retained, not converted into a budget pass.',
            'Audio evidence decodes actual runtime mixer captures through a dummy output device; physical speaker/device fidelity remains unmeasured.',
            'No world SaveGame system is implemented. This lineage exercises the actual supported GameUserSettings file and new custom preferences.',
            'The retained D03 file contains runtime-created default resolution/window settings. Arbitrary old customized settings or future schema migrations are not established.',
            'Installer hashes detect byte mismatch; they do not provide publisher authentication or a store/launcher/signing protocol.',
            'Debian assembly/extraction matches the same Linux diagnostic payload. Dependencies derive from Ubuntu 24.04 ELF metadata; native dpkg install/update/uninstall and other Linux distributions are unqualified.',
            'Generated runtime captures remain evidence, not newly accepted art content.'
        ],
        'unmet_criteria': [
            {'criterion': 'Accepted Win64 Shipping distributable and exact Windows old-build/update/native-play qualification',
             'classification': 'REQUIRES_OTHER_RESOURCE',
             'evidence': release.identity(root / 'resources/routing.json'),
             'smallest_next_action': 'Route to an actually verified Windows UE 5.8.2 build/play Resource with adequate storage and DX12 SM6 GPU, then execute the retained Win64 UBT/UAT package recipe and native qualification on its exact package bytes.'}
        ],
        'publication': 'Exact canonical local archive retained. Auto Feeder owns GitHub/Drive continuity publication from the task commit. No Win64 package, remote delivery or remote readback is claimed.',
        'verification_implementation': [release.identity(__file__), release.identity(release.__file__),
            *[release.identity(release.PROJECT / 'tests' / name) for name in (
                'build_d03_01_game.py', 'build_d03_01_editor.py', 'cook_d03_01_package.py',
                'stage_d03_01_package.py', 'run_d01_044.py', 'verify_d01_039.py', 'run_d01_042.py',
                'run_d02_01.py', 'verify_d02_02.py', 'verify_d02_04.py', 'verify_d04_01.py',
                'run_d06_01_cinematic.py', 'verify_d01_048.py', 'restore_d08_01_cook_config.py',
                'restage_d08_01_probe.py', 'build_d08_01_installer.py')]]
    }
    release.write(root / 'qualification.json', result)
    lines = ['# D08-01 delivery qualification', '',
             '**CONTINUE — Win64 Shipping release candidate remains unqualified.**', '',
             f'Linux Development diagnostic lineage passed for package `{package["package_id"]}`.',
             f'The exact archive is `{package["archive"]["path"]}` (SHA-256 `{package["archive"]["sha256"]}`).', '',
             'An isolated cook and UAT archive readback bind editable source/config/content and the native binary. The installer preserved the exact old version, rejected missing content and incompatible metadata, and activated the verified current version atomically.', '',
             'Outside-editor package processes exercised core gameplay twice, population/pressure, world interactions, cooked content/version rejection, audio/VFX, UI/settings and watched/skipped cinematic handoff. Three separate native processes exercised legacy settings, preference write and preference reconstruction after teardown.', '',
             'Each run retains commands, final logs, native PID/resource samples and feature-derived raw evidence. See qualification.json for exact hashes, diagnostics and limits. D07 evidence is preserved with its original scope.', '',
             f'The Debian diagnostic installer `{debian["archive"]["path"]}` passed container/control and complete payload extraction readback (SHA-256 `{debian["archive"]["sha256"]}`). This is installer assembly evidence, not native dpkg lifecycle or Windows qualification.', '',
             '## Remaining criterion', '', result['unmet_criteria'][0]['criterion'] + '.', '',
             result['unmet_criteria'][0]['smallest_next_action'], '',
             '## Known limits', '', *('- ' + item for item in result['limitations']), '',
             result['publication'], '']
    (root / 'qualification.md').write_text('\n'.join(lines))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-root', type=Path, required=True)
    parser.add_argument('--runs', type=Path, nargs='+', required=True)
    args = parser.parse_args()
    try:
        report = verify(args.install_root.resolve(), [path.resolve() for path in args.runs])
        print(release.json.dumps({key: report[key] for key in ('task_id', 'status', 'linux_diagnostic_lineage', 'package_id')}))
    except (OSError, ValueError, KeyError, AssertionError, RuntimeError) as error:
        with release.LEDGER.open('a') as stream:
            stream.write(release.json.dumps({'task_id': 'D08-01', 'time': release.now(),
                'type': 'release_qualification_readback', 'status': 'CONTINUE', 'diagnostics': str(error)[:2000]}) + '\n')
        raise
