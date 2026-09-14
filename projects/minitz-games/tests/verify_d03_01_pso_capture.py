#!/usr/bin/env python3
"""Replay PSO experiment evidence without equating compilation logs with frame stalls."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from run_d01_039 import PROJECT, file_identity, write_json
from run_d03_01_package import members
from verify_d03_01_reconstruction import verify as verify_views
from verify_d03_01_shader_platform import verify as verify_platform
from verify_d03_01_architecture import verify as verify_architecture
from verify_d03_01_surfaces import verify as verify_surfaces
from verify_d02_04 import verify as verify_environment


RUNS = ('pso-capture-cold-01', 'pso-capture-cold-02', 'pso-capture-cold-03',
        'pso-seeded-cold-01', 'pso-seeded-cold-02', 'pso-seeded-cold-03',
        'pso-seeded-environment-01', 'pso-empty-environment-01')
EXPECTED_FAILURES = {'pso-capture-cold-01': 'One nonempty native PSO recording required',
                     'pso-seeded-cold-01': 'Seed not opened natively'}
STAMP = r'\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\]'


def stamp(value):
    return datetime.strptime(value, '%Y.%m.%d-%H.%M.%S:%f')


def measurements(log, scenario):
    initialization = re.search(STAMP + r'.*\(Engine Initialization\) Total time: ([\d.]+) seconds', log)
    started = re.search(STAMP + r'.*Test Started\. Name=\{' + scenario.title() + r'\}', log)
    assert initialization and started, 'Missing native timing boundaries'
    initialized_at, test_at = stamp(initialization[1]), stamp(started[1])
    runtime = [dict(kind=m[0], milliseconds=float(m[1])) for m in re.findall(
        r'Runtime (graphics|compute) PSO creation hitch \(([\d.]+) msec\)', log)]
    # Graphics outer timing contains the inner "key CS" timing: count only outer.
    # Compute has only key-CS timing. These include worker waits, not just driver calls.
    vulkan = []
    for m in re.finditer(STAMP + r'.*Hitchy (gfx pipeline|compute pipeline key CS) \(([\d.]+) ms\)', log):
        if float(m[3]) > 20:
            vulkan.append(dict(end_at=m[1], kind='graphics' if m[2] == 'gfx pipeline' else 'compute',
                               milliseconds=float(m[3])))

    def summary(events):
        return dict(count=len(events), by_kind=dict(Counter(x['kind'] for x in events)),
                    maximum_ms=max((x['milliseconds'] for x in events), default=0))

    return dict(engine_initialization_seconds=float(initialization[2]),
                initialization_timestamp=initialization[1], test_started_timestamp=started[1],
                runtime_creation_over_20_ms=summary(runtime),
                vulkan_creation_over_20_ms=dict(
                    entire_process=summary(vulkan),
                    ending_after_initialization=summary([x for x in vulkan if stamp(x['end_at']) >= initialized_at]),
                    ending_after_test_start=summary([x for x in vulkan if stamp(x['end_at']) >= test_at])),
                scope='Native logged creation durations can overlap and include waits. End timestamps classify observations; neither counts nor sums measure frame stalls. Startup and screenshot-free frame windows are separate.')


def normalized_command(command, run, out):
    replace = {run['state']: 'STATE', run['state']+'/home': 'STATE_HOME', str(out): 'EVIDENCE'}
    return [replace.get(x, x) for x in command]


def verify(root):
    checked, reports, commands, receipts = {}, {}, {}, {}

    def check(item):
        assert file_identity(Path(item['path'])) == item, f'Changed identity: {item["path"]}'
        checked[item['path']] = item

    def read(path):
        check(file_identity(path))
        return json.loads(path.read_text())

    stage = read(root/'package-sm6-stage-01/validation.json')
    assert stage['result'] == 'PASS'
    check(stage['archive'])
    assert members(Path(stage['archive_readback'])) == stage['readback_members']
    for item in stage['readback_members']:
        check(item)
    build = read(root/'package-sm6-build-01/result.json')
    assert build['result'] == 'PASS' and build['inputs_unchanged']
    check(build['binary'])
    assert next(x for x in stage['readback_members'] if x['path'].endswith('/Binaries/Linux/BiellaGames'))['sha256'] == build['binary']['sha256']
    build_inputs = read(root/'package-sm6-build-01/inputs-after.json')
    for item in build_inputs:
        check(item)

    for name in RUNS:
        out = root/name
        run = read(out/'validation.json')
        receipts[name] = run
        expected_error = EXPECTED_FAILURES.get(name)
        assert run['result'] == ('FAIL' if expected_error else 'PASS'), f'Unexpected result: {name}'
        if expected_error:
            assert run['error'] == expected_error
        check(run['baseline'])
        baseline = json.loads(Path(run['baseline']['path']).read_text())
        scenario = baseline['scenario']
        assert run.get('scenario', scenario) == scenario
        assert run['archive'] == stage['archive'] and run['stage'] == file_identity(root/'package-sm6-stage-01/validation.json')
        assert run['package_before'] == run['package_after'] == stage['readback_members']
        assert run['inputs_before'] == run['inputs_after']
        assert run['inputs_before'][:-1] == baseline['inputs_after']
        for item in run['inputs_before'][:-1]:
            check(item)
        snapshot = file_identity(out/'runner.py')
        check(snapshot)
        assert all(snapshot[k] == run['inputs_before'][-1][k] for k in ('sha256', 'bytes')), 'Historical runner bytes lost'
        assert run['state_before'] == [] and len(run['state_at_launch']) == (1 if 'seed' in run else 0)
        if 'seed' in run:
            check(run['seed']['source'])
            assert run['state_at_launch'] == [run['seed']['copied']]
            assert all(run['seed']['source'][k] == run['seed']['copied'][k] for k in ('sha256', 'bytes'))
            assert run['seed']['copied']['path'] == run['state']+'/user/Saved/BiellaGames_SF_VULKAN_SM6.upipelinecache'
        for item in run.get('recordings', []):
            check(item)
        probe = read(out/'isolation-probe.json')
        assert probe['network_interfaces'] == ['lo'] and not any(probe['hidden_path_exists'].values())
        assert not probe['package_writable'] and probe['state_writable']
        check(run['runtime']['log'])
        assert run['runtime']['returncode'] == 0 and not run['runtime']['timed_out']
        command = read(out/'command.json')
        assert command == run['runtime']['command'] and '-psocache' in command
        commands[name] = normalized_command(command, run, out)
        log = (out/'runtime.stdout.log').read_text()
        assert re.search(r'Result=\{Success\}.*Name=\{' + scenario.title() + r'\}', log)
        assert verify_views(out, 'ProductionTSR') == run['native_views']
        assert verify_platform(out, 'sm6', 'ProductionTSR') == run['shader_platform']
        if scenario == 'surfaces':
            assert verify_architecture(out, 'sm6') == run['architecture']
            actual = verify_surfaces(out, 4, 100)
            actual['scope'] = run['verification']['scope']
        else:
            actual = verify_environment(out)
        assert actual == run['verification'], 'Native verification changed'
        for path in sorted(out.rglob('*')):
            if path.is_file():
                check(file_identity(path))
        if name == 'pso-capture-cold-01':
            assert 'Vulkan PSO Precaching = 1, PipelineFileCache = 0' in log and not run.get('recordings')
        else:
            assert 'Vulkan PSO Precaching = 1, PipelineFileCache = 1' in log
        opened = bool(re.search(r'Opened FPipelineCacheFile:.*BiellaGames_SF_VULKAN_SM6.upipelinecache', log))
        assert opened == ('seed' in run and not expected_error), 'Seed open observation differs'
        reports[name] = dict(result=run['result'], expected_failure=expected_error, scenario=scenario,
                             frames=actual['frames'], captures=len(actual['captures']),
                             elapsed_seconds=run['runtime']['elapsed_seconds'], seed_opened=opened,
                             costs=actual.get('costs'), measurements=measurements(log, scenario))

    pairs = [('pso-capture-cold-03', 'pso-seeded-cold-02'),
             ('pso-capture-cold-03', 'pso-seeded-cold-03'),
             ('pso-empty-environment-01', 'pso-seeded-environment-01')]
    for empty, seeded in pairs:
        assert commands[empty] == commands[seeded], 'Comparison launch configurations differ'
        assert receipts[empty]['state_at_launch'] == [] and len(receipts[seeded]['state_at_launch']) == 1
    assert '-logpso' in commands['pso-seeded-cold-01'] and '-logpso' not in commands['pso-seeded-cold-02']

    preservation = read(root/'pso-recording-01/preservation.json')
    for item in preservation['copies']:
        check(item['source'])
        check(item['canonical'])
        assert all(item['source'][k] == item['canonical'][k] for k in ('bytes', 'sha256'))
    assert {x['run'] for x in preservation['copies']} == {n for n in RUNS if receipts[n].get('recordings')}
    dump = read(root/'pso-recording-dump-01/result.json')
    check(dump['recording'])
    assert dump['recording'] == dump['recording_after'] and dump['runtime']['returncode'] == 0
    final = read(root/'pso-recording-dump-01/final-log-readback.json')
    check(final['original_receipt'])
    check(final['final_log'])
    raw = Path(final['final_log']['path']).read_bytes()
    assert hashlib.sha256(raw[:dump['runtime']['log']['bytes']]).hexdigest() == dump['runtime']['log']['sha256']
    assert len(raw) - dump['runtime']['log']['bytes'] == final['append_bytes'] == 770
    entries = re.split(r'PSO hash ', raw.decode())[1:]
    assert len(entries) == 66 and 'Total PSOs logged: 66' in raw.decode()
    classifications = Counter(re.search(r'PSOPrecacheResult (\w+)', x)[1] for x in entries)
    kinds = Counter('compute' if re.search(r'\bCS:', x) else 'graphics' if 'VS:' in x else 'unknown' for x in entries)
    assert kinds == {'graphics': 63, 'compute': 3} and classifications == {'Missed': 43, 'Precached': 23}
    return dict(task_id='D03-01', result='PASS', task_status='CONTINUE',
                archive=stage['archive'], runs=reports, matched_command_pairs=pairs,
                recording=dict(entries=66, kinds=dict(kinds), classifications=dict(classifications), identity=dump['recording']),
                checked_identities=list(checked.values()),
                scope='Capture/replay experiment only. Configuration and one portable cache seed explain the comparisons; runtime counters exclude precache jobs. Cold startup smoothness, PSO coverage and production loading are not accepted.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Use a fresh evidence path'
    try:
        report = verify(PROJECT/'Build/Presentation')
    except (AssertionError, OSError, KeyError, ValueError) as error:
        report = dict(task_id='D03-01', result='FAIL', error=str(error))
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                type='pso_capture_readback', status='CONTINUE', diagnostics=str(error)))+'\n')
    write_json(args.output, report)
    print(json.dumps(dict(result=report['result'], runs=len(report.get('runs', {})),
        identities=len(report.get('checked_identities', [])), error=report.get('error'))))
    raise SystemExit(0 if report['result'] == 'PASS' else 1)
