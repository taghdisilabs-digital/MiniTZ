#!/usr/bin/env python3
"""Reconcile D17-01's current candidate with exact raw evidence, without a pass.

This checkpoint deliberately remains incomplete while the recorded route is
shorter than the contract and the visual assessment contains major defects.
"""
from collections import Counter
import json
import hashlib
from pathlib import Path
import subprocess

from run_d08_01_release import digest, executable_format, identity, now, write, LEDGER, current


PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / 'Build/AAA/D17-01'
RUNS = ('entry-720-02', 'hud-720-01', 'hud-1080-01')
CURRENT_RUNS = ('service-720-01', 'service-1080-01')
HUD_COMMIT = '57190a294440c4dfa6deb9a9a50d23442c66fbc8'


def read(path):
    return json.loads(Path(path).read_text())


def ref(path):
    path = Path(path)
    value = identity(path)
    if path.is_absolute() and path.is_relative_to(PROJECT):
        value['path'] = path.relative_to(PROJECT).as_posix()
    return value


def check(row):
    actual = identity(PROJECT / row['path'])
    assert all(actual[k] == row[k] for k in ('sha256', 'bytes')), row['path']


def check_historical_source(row):
    """Historical gameplay proof binds its committed inputs, not newer visuals."""
    data = subprocess.check_output(['git', 'show',
        HUD_COMMIT + ':projects/biella-games/' + row['path']], cwd=PROJECT)
    assert hashlib.sha256(data).hexdigest() == row['sha256'] and len(data) == row['bytes'], row['path']


def observe(name):
    directory = ROOT / 'raw' / name
    capture = read(directory / 'input-result.json')
    assert capture['status'] == 'CAPTURED' and capture['game_returncode'] == 0
    assert not capture['world_mutation_or_automation_tests']
    inputs = [json.loads(line) for line in (directory / 'input.jsonl').read_text().splitlines()]
    actions = [r for r in inputs if r['event'] == 'input_sent']
    assert len(actions) == capture['actions_sent'] > 0
    rows = [json.loads(line) for line in (directory / 'telemetry.jsonl').read_text().splitlines()]
    assert len({r['session'] for r in rows}) == 1
    assert {r['restart_count'] for r in rows} == {0}
    assert [r['seq'] for r in rows] == sorted({r['seq'] for r in rows})
    active = next(r for r in rows if r['event'] == 'phase' and r['fields']['current'] == 'Active')
    terminal = next(r for r in rows if r['event'] == 'phase' and
                    r['fields']['current'] in ('Success', 'Failure'))
    assert active['map'] == terminal['map'] == 'BiellaOpenWorldMap'
    duration = terminal['sim_seconds'] - active['sim_seconds']
    events = dict(Counter(r['event'] for r in rows))
    observation = read(directory / 'observation.json')
    assert events == observation['telemetry_events']
    assert 'TERMINAL_INPUT_STATE terminal=true' in (directory / 'runtime.engine.log').read_text()
    video = read(directory / 'video.json')
    check(video['identity'])
    with (directory / 'raw-gameplay.mkv').open('rb') as stream:
        assert stream.read(4) == b'\x1aE\xdf\xa3', 'Not Matroska/EBML'
    stream = next(s for s in video['probe']['streams'] if s['codec_type'] == 'video')
    assert stream['codec_name'] == 'h264' and int(stream['nb_read_frames']) > 30
    assert stream['width'] == (1920 if '1080' in name else 1280)
    assert stream['height'] == (1080 if '1080' in name else 720)
    assert float(video['probe']['format']['duration']) > capture['measured_input_run_seconds']
    command = read(directory / 'game-command.json')
    assert not any('Automation' in arg or 'FixedTimeStep' in arg for arg in command)
    return dict(run=name, directory=directory.relative_to(PROJECT).as_posix(),
                session=active['session'], restart_count=0, terminal=terminal['fields']['current'],
                active_simulation_seconds=duration,
                capture_input_wall_seconds=capture['measured_input_run_seconds'],
                capture_video_seconds=float(video['probe']['format']['duration']),
                decoded_frames=int(stream['nb_read_frames']),
                resolution=[stream['width'], stream['height']], input_actions=len(actions),
                events=events, raw_video=ref(directory / 'raw-gameplay.mkv'),
                audio_captured=False, uninterrupted_duration_satisfied=600 <= duration <= 1200,
                natural_pressure_observed=bool(events.get('arena_pressure', 0)),
                namespace_file_verification=(directory / 'exposed-package-verification.json').exists())


def main():
    build = read(ROOT / 'build/game-01/result.json')
    assert build['result'] == 'PASS' and build['inputs_unchanged']
    # The old Binaries/ path is expected to change with a new build. Its exact
    # executable remains in the content-addressed native overlay archive.
    assert ref(ROOT / 'build/game-01/BiellaGames.target')['sha256'] == build['receipt']['sha256']
    source = read(ROOT / 'raw/hud-720-01/native-source.json')
    for row in source['material_inputs']:
        check_historical_source(row)
    assert digest(source['material_inputs']) == source['material_input_digest']
    previous = read(PROJECT / 'Build/Release/D08-01/source-build-manifest.json')
    before = {r['path']: r for r in previous['material_inputs']}
    after = {r['path']: r for r in source['material_inputs']}
    changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    assert changed == ['Source/BiellaGames/Private/BiellaGameplayHUD.cpp']
    scenario = read(ROOT / 'scenario.json')
    for row in scenario['editable_bindings']:
        check(row)
    assert scenario['duration_contract_seconds'] == [600, 1200]
    regressions = []
    for name in ('hud-01', 'settings-01'):
        path = ROOT / 'regression' / name / 'validation.json'
        report = read(path)
        assert report['result'] == 'PASS'
        assert report['native_delta']['sha256'] == build['binary']['sha256']
        regressions.append(ref(path))
    runtime = read(ROOT / 'raw/hud-720-01/resolved-package.json')
    for name in ('hud-720-01', 'hud-1080-01'):
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['files'] == runtime['files']
        assert resolved['runtime_id'] == digest({k: v for k, v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
        check(resolved['native_delta'])
    assert executable_format(runtime['native_delta']['path']) == 'ELF64-x86_64'
    assert runtime['native_delta']['sha256'] == build['binary']['sha256']
    runs = [observe(name) for name in RUNS]
    route_probe = observe('route-rival-01')
    probe_package = read(ROOT / 'raw/route-rival-01/resolved-package.json')
    baseline_package = read(PROJECT / 'Build/Release/D08-01/package-manifest.json')
    assert probe_package['base_package_id'] == baseline_package['package_id']
    assert probe_package['files'] == baseline_package['files'] and 'native_delta' not in probe_package
    assert probe_package['runtime_id'] == digest({k: v for k, v in probe_package.items() if k != 'runtime_id'})
    probe_exposed = read(ROOT / 'raw/route-rival-01/exposed-package-verification.json')
    assert probe_exposed['status'] == 'PASS' and probe_exposed['runtime_id'] == probe_package['runtime_id']
    package_root = ROOT / 'build/package-02'
    installation = read(package_root / 'validation.json')
    assert installation['result'] == 'PASS'
    package = read(package_root / 'package-manifest.json')
    native_source = read(package_root / 'source-build.json')
    for row in native_source['material_inputs']:
        check(row)
    assert digest(native_source['material_inputs']) == native_source['material_input_digest']
    after = {r['path']: r for r in native_source['material_inputs']}
    changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    assert package['source_material_digest'] == native_source['material_input_digest']
    check(package['archive'])
    installed = Path(installation['install']['installed'])
    assert current(installed.parents[1])[1] == package
    current_build = read(ROOT / 'build/game-02/result.json')
    assert current_build['result'] == 'PASS' and current_build['inputs_unchanged']
    assert native_source['binary']['sha256'] == current_build['binary']['sha256']
    check(current_build['binary'])
    assets = ROOT / 'environment/assets-01/validation.json'
    assert read(assets)['result'] == 'PASS'
    environment = ROOT / 'environment/runtime-02/validation.json'
    assert read(environment)['result'] == 'PASS'
    assert read(environment)['package_id'] == package['package_id']
    new_runs = [observe(name) for name in CURRENT_RUNS]
    for name in CURRENT_RUNS:
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == package['package_id']
        assert resolved['files'] == package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k: v for k, v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    visual = read(ROOT / 'visual-assessment.json')
    assert visual['major_defects'] and not visual['zero_major_defects']
    assert not any(run['uninterrupted_duration_satisfied'] for run in runs + [route_probe] + new_runs)
    report = dict(
        schema='biella.games.d17.qualification/v1', task_id='D17-01', observed=now(),
        status='INCOMPLETE', result='CONTINUE', accepted=False,
        evidence_integrity='VERIFIED', scenario=ref(ROOT / 'scenario.json'),
        owner_visual_contract=ref(PROJECT / 'docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md'),
        scope='Canonical slice candidate, HUD correction and authored service-bay layer; Linux Development diagnostics',
        implementation=dict(changed_material_inputs=changed, build=ref(ROOT / 'build/game-02/result.json'),
                            editor_build=ref(ROOT / 'build/editor-02/validation.json'),
                            editable_source=ref(PROJECT / 'Source/BiellaGames/Private/BiellaEnvironmentSite.cpp'),
                            editable_art=[ref(p) for p in sorted((PROJECT / 'SourceAssets/Environment').iterdir()) if p.is_file()],
                            source_manifest=ref(package_root / 'source-build.json'),
                            asset_readback=ref(assets), environment_regression=ref(environment),
                            source_material_digest=native_source['material_input_digest']),
        package=dict(package_id=package['package_id'],
                     manifest=ref(package_root / 'package-manifest.json'),
                     payload_files_digest=digest(package['files']),
                     exact_resolved_manifests=[ref(ROOT / 'raw' / n / 'resolved-package.json')
                                               for n in CURRENT_RUNS],
                     cook=ref(ROOT / 'build/cook-02/validation.json'),
                     stage=ref(ROOT / 'build/stage-03/validation.json'),
                     install=ref(package_root / 'validation.json'), format='ELF64-x86_64',
                     platform='Linux', configuration='Development', renderer='Vulkan'),
        first_raw_run=runs[0], previous_raw_runs=runs[1:], current_raw_runs=new_runs,
        route_feasibility_probe=dict(observation=route_probe,
            resolved_package=ref(ROOT / 'raw/route-rival-01/resolved-package.json'),
            scope='Ordinary-input diagnostic using unchanged D08 package; no proof of new service-bay visuals'),
        hud_regressions=regressions, historical_hud_source_commit=HUD_COMMIT,
        visual_assessment=ref(ROOT / 'visual-assessment.json'),
        satisfied_partial_criteria=['Editable route/start/beat/end candidate exists and binds owner direction',
                                    'Exact baseline/native-delta package identities and first raw run retained',
                                    'HUD change builds and existing live HUD/settings behavior tests pass',
                                    'Editable service-bay metalwork/PBR assets pass fresh saved-asset readback',
                                    'New native/editor builds, isolated recook, archive readback and installed environment regression pass'],
        unmet_criteria=[
            dict(id='continuous_slice_duration_and_route', required='600–1200 seconds of representative active gameplay with route beats',
                 observed=[{'run': r['run'], 'active_seconds': r['active_simulation_seconds']} for r in runs + [route_probe] + new_runs],
                 next_action='Identify an accepted continuous content route before changing objective behavior; no actor resets, idle padding or invented mechanics'),
            dict(id='player_rival_infected_arena_pressure', required='Player, rival, infected and arena consequence in the evolving real encounter',
                 observed='Raw clips contain no arena_pressure event; current native code defines/consumes pressure but has no non-test call raising it',
                 next_action='Use only an identified accepted player-reachable trigger; Contract 33 leaves timing/escalation UNKNOWN, so neither a timer nor switch-to-pressure wiring may be invented'),
            dict(id='zero_major_visual_defects', required='All hard visual requirements with zero major defects',
                 observed=[d['id'] for d in visual['major_defects']],
                 next_action='Continue the service-bay approach surface and integrated organic infection layer from the new runtime frames, preserving tested collision/gameplay')],
        scope_findings=ref(ROOT / 'environment/scope-findings.json'),
        proof_limits=['Short raw clips do not qualify long-form pacing or later route beats',
                      'HUD and environment automation use fixtures and are not raw-slice proof',
                      'Earlier raw runs bind the prior source/package, not the changed service-bay materials',
                      'Encoded video frame rate does not measure native game FPS; raw video has no audio',
                      'Baseline capture predates namespace-file verification; later captures verify it',
                      'D07 soak/restart cycles are not reused as continuous slice duration',
                      'No Win64 Shipping or remote publication acceptance'],
        publication=dict(local='Task-owned source/proof to be persisted by the task commit',
                         remote='Auto Feeder owns configured GitHub/Drive publication cursor; no remote success claimed'),
        index_generator=ref(Path(__file__).resolve()))
    excluded = {ROOT / 'qualification.json'}
    report['evidence_files'] = [ref(p) for p in sorted(ROOT.rglob('*')) if p.is_file() and p not in excluded]
    write(ROOT / 'qualification.json', report)
    print(json.dumps(dict(task_id='D17-01', evidence_integrity='VERIFIED', acceptance='INCOMPLETE',
                         raw_simulation_seconds=[r['active_simulation_seconds'] for r in new_runs],
                         hud_regressions='2 PASS', major_visual_defects=len(visual['major_defects']))))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        with LEDGER.open('a') as stream:
            stream.write(json.dumps(dict(task_id='D17-01', time=now(), type='qualification_integrity',
                                         status='FAILED', diagnostics=f'{type(exc).__name__}: {exc}'[:1000])) + '\n')
        raise
