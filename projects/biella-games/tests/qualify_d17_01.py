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
CURRENT_RUNS = ('sheath-hazard-720-01', 'sheath-hazard-1080-01')
GROWTH_RUNS = ('growth-hazard-720-01', 'growth-hazard-1080-01')
GROWTH_COMMIT = 'c24863b0c3c6b555f7871c6c6cb99579a0a0115e'
CURRENT_PROBES = ('sheath-hazard-720-02',)
COORDINATE_RUNS = ('service-720-02', 'service-1080-02', 'service-interaction-720-01', 'service-interaction-720-02')
COORDINATE_COMMIT = '5854ebea89bd581418924397bacbfc6ac7612db0'
PREVIOUS_SERVICE_RUNS = ('service-720-01', 'service-1080-01')
SERVICE_COMMIT = '0242b38e31451f24d51175fc4050172122c28a3a'
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


def check_historical_source(row, commit=HUD_COMMIT):
    """Historical gameplay proof binds its committed inputs, not newer visuals."""
    path = Path(row['path'])
    if path.is_absolute():
        path = path.relative_to(PROJECT)
    data = subprocess.check_output(['git', 'show',
        commit + ':projects/biella-games/' + path.as_posix()], cwd=PROJECT)
    assert hashlib.sha256(data).hexdigest() == row['sha256'] and len(data) == row['bytes'], row['path']


def check_input_binding(row):
    # Captures made before world-tick synchronization retain the exact old driver.
    if (Path(row['path']).name == 'd17_01_raw_input.py' and
            row['sha256'] == '73578de1303d53b6f90f8753f35ccdf92397eae0bc37f91d7213be865987811a'):
        check_historical_source(row, GROWTH_COMMIT)
    else:
        check(row)


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
    log = (directory / 'runtime.engine.log').read_text()
    assert 'TERMINAL_INPUT_STATE terminal=true' in log
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
                environment_power_transitions=sum('D02_ENV POWER ' in line for line in log.splitlines()),
                environment_panel_events=[line.split('D02_ENV PANEL ',1)[1] for line in log.splitlines() if 'D02_ENV PANEL ' in line],
                electrical_floor_damage=[dict(sim_seconds=r['sim_seconds'], **r['fields']) for r in rows if r['event']=='damage' and r['fields'].get('tag')=='electrical_floor'],
                player_defeats=[r['fields'] for r in rows if r['event'] == 'defeat' and
                               r['fields'].get('target', '').startswith('BiellaStreamingCharacter:')],
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
    previous_service_source = read(ROOT / 'build/package-02/source-build.json')
    for row in previous_service_source['material_inputs']:
        check_historical_source(row, SERVICE_COMMIT)
    previous_service_package = read(ROOT / 'build/package-02/package-manifest.json')
    previous_service_runs = [observe(name) for name in PREVIOUS_SERVICE_RUNS]
    for name in PREVIOUS_SERVICE_RUNS:
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == previous_service_package['package_id']
        assert resolved['files'] == previous_service_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k: v for k, v in resolved.items() if k != 'runtime_id'})
    coordinate_source = read(ROOT / 'build/package-03/source-build.json')
    for row in coordinate_source['material_inputs']:
        check_historical_source(row, COORDINATE_COMMIT)
    coordinate_package = read(ROOT / 'build/package-03/package-manifest.json')
    coordinate_runs = [observe(name) for name in COORDINATE_RUNS]
    for name in COORDINATE_RUNS:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values():
            check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == coordinate_package['package_id']
        assert resolved['files'] == coordinate_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k:v for k,v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    assert coordinate_runs[-1]['environment_power_transitions'] == 1
    assert any('physics=1' in line for line in coordinate_runs[-1]['environment_panel_events'])
    growth_source = read(ROOT / 'build/package-04/source-build.json')
    for row in growth_source['material_inputs']:
        check_historical_source(row, GROWTH_COMMIT)
    growth_package = read(ROOT / 'build/package-04/package-manifest.json')
    growth_runs = [observe(name) for name in GROWTH_RUNS]
    for name in GROWTH_RUNS:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values():
            check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == growth_package['package_id']
        assert resolved['files'] == growth_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k:v for k,v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    assert growth_runs[0]['environment_power_transitions'] == 1
    assert any('physics=1' in line for line in growth_runs[0]['environment_panel_events'])
    assert len(growth_runs[0]['electrical_floor_damage']) == 9
    package_root = ROOT / 'build/package-05'
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
    for path in ('build/cook-06/validation.json', 'build/stage-06/validation.json'):
        assert read(ROOT / path)['result'] == 'PASS', path
    installed = Path(installation['install']['installed'])
    assert current(installed.parents[1])[1] == package
    current_build = read(ROOT / 'build/game-02/result.json')
    assert current_build['result'] == 'PASS' and current_build['inputs_unchanged']
    assert native_source['binary']['sha256'] == current_build['binary']['sha256']
    check(current_build['binary'])
    assets = ROOT / 'environment/assets-04/validation.json'
    assert read(assets)['result'] == 'PASS'
    for mesh in read(ROOT / 'environment/assets-04/readback.json')['meshes']:
        assert mesh['authored_coordinates_verified']
    environment = ROOT / 'environment/runtime-05/validation.json'
    assert read(environment)['result'] == 'PASS'
    assert read(environment)['package_id'] == package['package_id']
    new_runs = [observe(name) for name in CURRENT_RUNS]
    new_probes = [observe(name) for name in CURRENT_PROBES]
    # Absence of an ordinary-input beat is an acceptance gap, not an integrity
    # error. Never carry the historical outcome into a newer raw run.
    ordinary_environment = new_runs[0]
    floor_damage = ordinary_environment['electrical_floor_damage']
    geometry = read(ROOT / 'environment/mesh-author-04/geometry-readback.json')
    assert geometry['result'] == 'PASS'
    assert geometry['source_blend_sha256'] == ref(PROJECT / 'SourceAssets/Environment/ServiceBay.blend')['sha256']
    column, header = geometry['records']
    assert column['bounds_min'][1] > 244
    assert header['bounds_min'][1] > 194 and header['bounds_min'][2] > 215
    # Native mechanics/map/content definitions are materially unchanged since
    # the proven package-04 consequence; changed art has fresh fixture/raw proof.
    growth_inputs = {r['path']: r for r in growth_source['material_inputs']}
    growth_delta = sorted(p for p in growth_inputs.keys() | after.keys() if growth_inputs.get(p) != after.get(p))
    expected_art_delta = ['Content/Python/author_service_bay.py'] + [
        'Content/Environment/ServiceBay/' + n + '.uasset' for n in (
        'MI_ServiceGrowth', 'MI_ServiceLamp', 'MI_ServicePaint', 'MI_ServiceRubber',
        'MI_ServiceSteel', 'MI_ServiceVein', 'M_ServiceMetal', 'SM_ServiceBayMetalwork',
        'SM_ServicePanel120', 'SM_ServicePanel240')]
    assert growth_delta == sorted(expected_art_delta), growth_delta
    synchronized = ROOT / 'raw/sheath-hazard-720-02'
    sync_result = read(synchronized / 'input-result.json')
    assert sync_result['input_time_origin'] == 'first_world_tick'
    sync_inputs = [json.loads(line) for line in (synchronized / 'input.jsonl').read_text().splitlines()]
    tick = next(r for r in sync_inputs if r['event'] == 'input_clock_started')
    assert tick['native_log_line'] in (synchronized / 'runtime.engine.log').read_text()
    assert '][  1]LogTemp: Display: D02_STREAM ENCOUNTER_RESIDENCY ' in tick['native_log_line']
    assert all(r['elapsed_seconds'] >= tick['elapsed_seconds'] for r in sync_inputs if r['event'] == 'input_sent')
    for name in CURRENT_RUNS + CURRENT_PROBES:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values():
            check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == package['package_id']
        assert resolved['files'] == package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k: v for k, v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    visual = read(ROOT / 'visual-assessment.json')
    assert visual['major_defects'] and not visual['zero_major_defects']
    assert visual['current_package_id'] == scenario['current_package']['package_id'] == package['package_id']
    check(scenario['current_package']['manifest'])
    assert scenario['current_package']['source_material_digest'] == package['source_material_digest']
    assert read(ROOT / 'environment/scope-findings.json')['current_environment_probe']['electrical_floor_damage'] == floor_damage
    for frame in visual['current_frames'] + visual['service_bay_packaged_frames']:
        assert (ROOT / frame).read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
    all_runs = runs + [route_probe] + previous_service_runs + coordinate_runs + growth_runs + new_runs + new_probes
    assert not any(run['uninterrupted_duration_satisfied'] for run in all_runs)
    report = dict(
        schema='biella.games.d17.qualification/v1', task_id='D17-01', observed=now(),
        status='INCOMPLETE', result='CONTINUE', accepted=False,
        evidence_integrity='VERIFIED', scenario=ref(ROOT / 'scenario.json'),
        owner_visual_contract=ref(PROJECT / 'docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md'),
        scope='Canonical slice candidate, HUD correction, service-bay growth/material layer and ordinary environment consequence; Linux Development diagnostics',
        implementation=dict(changed_material_inputs=changed, build=ref(ROOT / 'build/game-02/result.json'),
                            editor_build=ref(ROOT / 'build/editor-02/validation.json'),
                            editable_source=ref(PROJECT / 'Source/BiellaGames/Private/BiellaEnvironmentSite.cpp'),
                            editable_art=[ref(p) for p in sorted((PROJECT / 'SourceAssets/Environment').iterdir()) if p.is_file()] + [ref(PROJECT / 'SourceAssets/Materials/ServiceSurface.hlsl')],
                            source_manifest=ref(package_root / 'source-build.json'),
                            asset_readback=ref(assets), environment_regression=ref(environment),
                            geometry_clearance=ref(ROOT / 'environment/mesh-author-04/geometry-readback.json'),
                            visual_delta_from_previous_package=growth_delta,
                            source_material_digest=native_source['material_input_digest']),
        package=dict(package_id=package['package_id'],
                     manifest=ref(package_root / 'package-manifest.json'),
                     payload_files_digest=digest(package['files']),
                     exact_resolved_manifests=[ref(ROOT / 'raw' / n / 'resolved-package.json')
                                               for n in CURRENT_RUNS + CURRENT_PROBES],
                     cook=ref(ROOT / 'build/cook-06/validation.json'),
                     stage=ref(ROOT / 'build/stage-06/validation.json'),
                     install=ref(package_root / 'validation.json'), format='ELF64-x86_64',
                     platform='Linux', configuration='Development', renderer='Vulkan'),
        first_raw_run=runs[0], previous_raw_runs=runs[1:], current_raw_runs=new_runs, current_input_timing_probe=new_probes[0],
        current_environment_probe=dict(observation=new_runs[0],
            input_plan=ref(ROOT / 'service-hazard-input.json'),
            scope='Ordinary input on the current package; switching, panel physics and electrical-floor outcomes are extracted from native logs/telemetry above'),
        previous_growth_candidate=dict(source_commit=GROWTH_COMMIT,
            package=ref(ROOT / 'build/package-04/package-manifest.json'), raw_runs=growth_runs),
        previous_coordinate_candidate=dict(source_commit=COORDINATE_COMMIT,
            package=ref(ROOT / 'build/package-03/package-manifest.json'), raw_runs=coordinate_runs),
        previous_service_candidate=dict(source_commit=SERVICE_COMMIT,
            package=ref(ROOT / 'build/package-02/package-manifest.json'),
            raw_runs=previous_service_runs,
            coordinate_defect=ref(ROOT / 'environment/coordinate-readback-01/validation.json')),
        route_feasibility_probe=dict(observation=route_probe,
            resolved_package=ref(ROOT / 'raw/route-rival-01/resolved-package.json'),
            scope='Ordinary-input diagnostic using unchanged D08 package; no proof of new service-bay visuals'),
        hud_regressions=regressions, historical_hud_source_commit=HUD_COMMIT,
        visual_assessment=ref(ROOT / 'visual-assessment.json'),
        satisfied_partial_criteria=['Editable route/start/beat/end candidate exists and binds owner direction',
                                    'Exact baseline/native-delta package identities and first raw run retained',
                                    'HUD change builds and existing live HUD/settings behavior tests pass',
                                    'Editable service-bay metalwork/PBR assets pass fresh saved-asset readback',
                                    'New native/editor builds, isolated recook, archive readback and installed environment regression pass',
                                    'Ordinary input on package 03 toggles power and destroys a panel into simulated debris; capture/logs preserve the consequence',
                                    'Editable tapered growth follows the rail/column/header; a lobed tissue sheath covers the approach column/header faces with nonmetallic pigmentation, normal detail and embedded vascular branches',
                                    'Package-04 ordinary input proves power/panel physics/electrical-floor damage; unchanged native mechanics are reused, with fresh package-05 fixture proof and ordinary-camera observation of the changed art'],
        unmet_criteria=[
            dict(id='continuous_slice_duration_and_route', required='600–1200 seconds of representative active gameplay with route beats',
                 observed=[{'run': r['run'], 'active_seconds': r['active_simulation_seconds'],
                            'terminal': r['terminal']} for r in all_runs],
                 next_action='Identify an accepted continuous content route before changing objective behavior; no actor resets, idle padding or invented mechanics'),
            dict(id='player_rival_infected_arena_pressure', required='Player, rival, infected and arena consequence in the evolving real encounter',
                 observed='Package-04 ordinary input proves power, panel destruction/physics and electrical-floor player damage. Package-05 fixture behavior passes; its current 720p and 1080p raw runs do not reach the environmental consequence. First-world-tick synchronization is observed in an additional 720p run, which ends at 12.705 active seconds before the switch. Natural arena_pressure timing and the full evolving encounter composition remain unqualified.',
                 next_action='Reuse verified ordinary-input environment outcomes; qualify the full player+rival+infected encounter and remaining route without inventing pressure timing or rewiring the switch'),
            dict(id='zero_major_visual_defects', required='All hard visual requirements with zero major defects',
                 observed=[d['id'] for d in visual['major_defects']],
                 next_action='Replace the exposed dry service-bay approach and hazard-floor visual treatment with coherent wet worn surfaces; retain the tested hazard state and collision, then validate the affected layer in the package and ordinary camera')],
        scope_findings=ref(ROOT / 'environment/scope-findings.json'),
        proof_limits=['Short raw clips do not qualify long-form pacing or later route beats',
                      'HUD and environment automation use fixtures and are not raw-slice proof',
                      'Earlier raw runs bind the prior source/package, not the changed service-bay materials',
                      'Encoded video frame rate does not measure native game FPS; raw video has no audio',
                      'Baseline capture predates namespace-file verification; later captures verify it',
                      'D07 soak/restart cycles are not reused as continuous slice duration',
                      'Optional resource-review stdout.json is preserved empty raw output from the documented timeout; it is not JSON or a review result',
                      'No Win64 Shipping or remote publication acceptance'],
        publication=dict(local='Task-owned source/proof to be persisted by the task commit',
                         remote='Auto Feeder owns configured GitHub/Drive publication cursor; no remote success claimed'),
        index_generator=ref(Path(__file__).resolve()))
    excluded = {ROOT / 'qualification.json'}
    report['evidence_files'] = [ref(p) for p in sorted(ROOT.rglob('*')) if p.is_file() and p not in excluded]
    write(ROOT / 'qualification.json', report)
    print(json.dumps(dict(task_id='D17-01', evidence_integrity='VERIFIED', acceptance='INCOMPLETE',
                         raw_simulation_seconds=[r['active_simulation_seconds'] for r in new_runs + new_probes],
                         hud_regressions='2 PASS', major_visual_defects=len(visual['major_defects']))))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        with LEDGER.open('a') as stream:
            stream.write(json.dumps(dict(task_id='D17-01', time=now(), type='qualification_integrity',
                                         status='FAILED', diagnostics=f'{type(exc).__name__}: {exc}'[:1000])) + '\n')
        raise
