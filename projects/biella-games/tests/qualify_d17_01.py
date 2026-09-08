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
import re

from run_d08_01_release import digest, executable_format, identity, now, write, LEDGER, current


PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / 'Build/AAA/D17-01'
RUNS = ('entry-720-02', 'hud-720-01', 'hud-1080-01')
CURRENT_RUNS = ('hall-720-01', 'hall-1080-01')
STORM_RUNS = ('storm-720-01', 'storm-1080-01')
STORM_COMMIT = 'bf7c10031690ff43d045287b9f6a0433df0b57a1'
FLOOR_EDGE_RUNS = ('floor-edge-720-01', 'floor-edge-1080-01')
FLOOR_EDGE_COMMIT = 'cbca5c7cd692fa77e0a66a7e1ebcf9983287e956'
PANEL_RUNS = ('panel-impact-720-01', 'panel-impact-1080-01')
PANEL_COMMIT = '1fbc5e9c00447b4997af87a6fdde0f1628deb712'
SWITCH_RUNS = ('switch-face-720-01', 'switch-face-1080-01')
SWITCH_COMMIT = '8236b5b4bbbdafb8499babb4f95b9dd80dfc32b0'
INTEGER_RUNS = ('integer-floor-720-01', 'integer-floor-1080-01')
INTEGER_COMMIT = 'ef771a62b993fc4fa1718ff9ae21f447c7cabe45'
SMOOTH_RUNS = ('smooth-floor-720-01', 'smooth-floor-1080-01')
SMOOTH_COMMIT = 'fdad60240ebd296e95a593789cc0fb8ed7716124'
GROUND_RUNS = ('wet-floor-720-01', 'wet-floor-1080-01')
GROUND_COMMIT = '51811365a77cde9f45a8733a663a649c57766df9'
SHEATH_RUNS = ('sheath-hazard-720-01', 'sheath-hazard-1080-01', 'sheath-hazard-720-02')
SHEATH_COMMIT = '02174657d6e83409c441a928c5b1a029024cec8b'
GROWTH_RUNS = ('growth-hazard-720-01', 'growth-hazard-1080-01')
GROWTH_COMMIT = 'c24863b0c3c6b555f7871c6c6cb99579a0a0115e'
CURRENT_PROBES = ()
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


def check_pre_hall(row):
    """The only preexisting runtime asset changed by hall cladding is the map."""
    path = Path(row['path'])
    if path.is_absolute() and path.is_relative_to(PROJECT):
        path = path.relative_to(PROJECT)
    if path.as_posix() == 'Content/Maps/BiellaOpenWorldMap.umap':
        check_historical_source(row, STORM_COMMIT)
    else:
        check(row)


def check_pre_storm(row):
    """Earlier visual fixtures retain the exact committed pre-storm lighting."""
    path = Path(row['path'])
    if path.is_absolute() and path.is_relative_to(PROJECT):
        path = path.relative_to(PROJECT)
    changed = read(ROOT / 'environment/storm-assets-01/validation.json')['changed_inputs']
    if path.as_posix() in changed:
        check_historical_source(row, FLOOR_EDGE_COMMIT)
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
    sheath_source = read(ROOT / 'build/package-05/source-build.json')
    for row in sheath_source['material_inputs']:
        check_historical_source(row, SHEATH_COMMIT)
    sheath_package = read(ROOT / 'build/package-05/package-manifest.json')
    sheath_runs = [observe(name) for name in SHEATH_RUNS]
    for name in SHEATH_RUNS:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values():
            check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == sheath_package['package_id']
        assert resolved['files'] == sheath_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k:v for k,v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    ground_source = read(ROOT / 'build/package-06/source-build.json')
    for row in ground_source['material_inputs']:
        check_historical_source(row, GROUND_COMMIT)
    ground_package = read(ROOT / 'build/package-06/package-manifest.json')
    ground_runs = [observe(name) for name in GROUND_RUNS]
    for name in GROUND_RUNS:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values():
            check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == ground_package['package_id']
        assert resolved['files'] == ground_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k:v for k,v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    smooth_source = read(ROOT / 'build/package-07/source-build.json')
    for row in smooth_source['material_inputs']:
        check_historical_source(row, SMOOTH_COMMIT)
    smooth_package = read(ROOT / 'build/package-07/package-manifest.json')
    smooth_runs = [observe(name) for name in SMOOTH_RUNS]
    for name in SMOOTH_RUNS:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values():
            check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == smooth_package['package_id']
        assert resolved['files'] == smooth_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k:v for k,v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    integer_source = read(ROOT / 'build/package-08/source-build.json')
    for row in integer_source['material_inputs']:
        check_historical_source(row, INTEGER_COMMIT)
    integer_package = read(ROOT / 'build/package-08/package-manifest.json')
    integer_runs = [observe(name) for name in INTEGER_RUNS]
    for name in INTEGER_RUNS:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values():
            check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == integer_package['package_id']
        assert resolved['files'] == integer_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k:v for k,v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    switch_source = read(ROOT / 'build/package-09/source-build.json')
    for row in switch_source['material_inputs']:
        check_historical_source(row, SWITCH_COMMIT)
    switch_package = read(ROOT / 'build/package-09/package-manifest.json')
    switch_runs = [observe(name) for name in SWITCH_RUNS]
    for name in SWITCH_RUNS:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values():
            check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == switch_package['package_id']
        assert resolved['files'] == switch_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k:v for k,v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    panel_source = read(ROOT / 'build/package-10/source-build.json')
    for row in panel_source['material_inputs']: check_historical_source(row, PANEL_COMMIT)
    panel_package = read(ROOT / 'build/package-10/package-manifest.json')
    panel_runs = [observe(name) for name in PANEL_RUNS]
    for name in PANEL_RUNS:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values(): check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == panel_package['package_id']
        assert resolved['files'] == panel_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k:v for k,v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    panel_environment = read(ROOT / 'environment/runtime-10/validation.json')
    assert panel_environment['result'] == 'PASS' and panel_environment['package_id'] == panel_package['package_id']
    floor_edge_source = read(ROOT / 'build/package-11/source-build.json')
    for row in floor_edge_source['material_inputs']: check_historical_source(row, FLOOR_EDGE_COMMIT)
    floor_edge_package = read(ROOT / 'build/package-11/package-manifest.json')
    floor_edge_runs = [observe(name) for name in FLOOR_EDGE_RUNS]
    for name in FLOOR_EDGE_RUNS:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values(): check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == floor_edge_package['package_id']
        assert resolved['files'] == floor_edge_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k:v for k,v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    storm_source = read(ROOT / 'build/package-12/source-build.json')
    for row in storm_source['material_inputs']: check_historical_source(row, STORM_COMMIT)
    storm_source_inputs = {r['path']: r for r in storm_source['material_inputs']}
    storm_package = read(ROOT / 'build/package-12/package-manifest.json')
    storm_runs = [observe(name) for name in STORM_RUNS]
    for name in STORM_RUNS:
        for row in read(ROOT / 'raw' / name / 'inputs.json').values(): check_input_binding(row)
        resolved = read(ROOT / 'raw' / name / 'resolved-package.json')
        assert resolved['base_package_id'] == storm_package['package_id']
        assert resolved['files'] == storm_package['files'] and 'native_delta' not in resolved
        assert resolved['runtime_id'] == digest({k:v for k,v in resolved.items() if k != 'runtime_id'})
        exposed = read(ROOT / 'raw' / name / 'exposed-package-verification.json')
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
    package_root = ROOT / 'build/package-13'
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
    for path in ('build/cook-14/validation.json', 'build/stage-16/validation.json'):
        assert read(ROOT / path)['result'] == 'PASS', path
    installed = Path(installation['install']['installed'])
    assert current(installed.parents[1])[1] == package
    current_build = read(ROOT / 'build/game-05/result.json')
    assert current_build['result'] == 'PASS' and current_build['inputs_unchanged']
    assert native_source['binary']['sha256'] == current_build['binary']['sha256']
    check(current_build['binary'])
    assets = ROOT / 'environment/assets-08/validation.json'
    assert read(assets)['result'] == 'PASS'
    assert read(assets)['ground_only']
    assert set(read(assets)['changed_assets']) == {'Content/Environment/ServiceBay/M_ServiceGround.uasset'}
    for row in read(assets)['sources']: check(row)
    assert read(ROOT / 'environment/assets-08/readback.json')['ground_shader_sha256'] == ref(PROJECT/'SourceAssets/Materials/ServiceGround.hlsl')['sha256']
    for mesh in read(ROOT / 'environment/assets-08/readback.json')['meshes']:
        assert mesh['authored_coordinates_verified']
    switch_assets = ROOT / 'environment/switch-assets-03/validation.json'
    switch_report = read(switch_assets)
    assert switch_report['result'] == 'PASS' and switch_report['preexisting_other_assets_unchanged']
    assert set(switch_report['changed_assets']) == {'Content/Environment/ServiceBay/M_ServiceSwitch.uasset'}
    for row in switch_report['sources'] + list(switch_report['changed_assets'].values()): check(row)
    switch_readback = read(switch_assets.parent / 'readback.json')
    assert switch_readback['shader_sha256'] == ref(PROJECT/'SourceAssets/Materials/ServiceSwitch.hlsl')['sha256']
    assert switch_readback['power_parameters'] == ['BaseColor', 'Emission']
    assert switch_readback['mode'] == 'readback' and switch_readback['result'] == 'PASS'
    final_logs = read(switch_assets.parent / 'log-finalization.json')
    assert final_logs['result'] == 'PASS'
    check(final_logs['author_validation'])
    for row in final_logs['logs']:
        assert row['finalization']['closed']
        check(row['final_identity'])
    switch_visual = read(ROOT / 'environment/switch-material-validation.json')
    assert switch_visual['result'] == 'PASS_AFFECTED_LAYER' and not switch_visual['slice_acceptance']
    for row in (switch_visual['sources'] + switch_visual['inspected_frames'] +
                switch_visual['ordinary_input_inspected_frames']):
        if Path(row['path']).name == 'BiellaEnvironmentSite.cpp': check_historical_source(row, SWITCH_COMMIT)
        else: check(row)
    check(switch_visual['editor_validation'])
    diagnostic = read(PROJECT / switch_visual['editor_validation']['path'])
    assert diagnostic['result'] == 'PASS' and diagnostic['buffer'] == 'Lit'
    assert diagnostic['identities_before'] == diagnostic['identities_after']
    switch_editor = ROOT / 'build/editor-04/validation.json'
    check_historical_source(ref(switch_editor), SWITCH_COMMIT)
    switch_binaries = {r['path']:r for r in read(switch_editor)['binaries']}
    for row in diagnostic['identities_after']:
        if row['path'] in switch_binaries: assert row == switch_binaries[row['path']]
        elif Path(row['path']).name in ('BiellaEnvironmentSite.cpp', 'M_ServiceGround.uasset'): check_historical_source(row, SWITCH_COMMIT)
        else: check_pre_storm(row)
    environment = ROOT / 'environment/runtime-13/validation.json'
    assert read(environment)['result'] == 'PASS'
    assert read(environment)['package_id'] == package['package_id']
    new_runs = [observe(name) for name in CURRENT_RUNS]
    new_probes = [observe(name) for name in CURRENT_PROBES]
    assert len(switch_visual['ordinary_input_runs']) == len(switch_runs)
    for bound, observed in zip(switch_visual['ordinary_input_runs'], switch_runs):
        assert bound['run'] == observed['run']
        assert bound['active_simulation_seconds'] == observed['active_simulation_seconds']
        assert bound['terminal'] == observed['terminal']
        assert bound['power_transitions'] == observed['environment_power_transitions']
        assert bound['panel_events'] == observed['environment_panel_events']
        assert bound['electrical_floor_damage'] == observed['electrical_floor_damage']
        assert bound['raw_video'] == observed['raw_video']
        for key in ('raw_video', 'telemetry', 'runtime_log'): check(bound[key])
    panel_assets = ROOT / 'environment/panel-assets-01/validation.json'
    panel_report = read(panel_assets)
    assert panel_report['result'] == 'PASS' and panel_report['preexisting_other_assets_unchanged']
    assert set(panel_report['changed_assets']) == {'Content/Environment/ServiceBay/M_ServicePanel.uasset'}
    for row in panel_report['sources'] + list(panel_report['changed_assets'].values()): check(row)
    for run in panel_report['runs']:
        assert run['returncode'] == 0 and not run['timed_out'] and run['log_finalization']['closed']
        check(run['log'])
    panel_readback = read(panel_assets.parent / 'readback.json')
    assert panel_readback['shader_sha256'] == ref(PROJECT/'SourceAssets/Materials/ServicePanel.hlsl')['sha256']
    assert panel_readback['damage_parameters'] == ['ImpactA', 'ImpactB', 'DamageAmount']
    assert panel_readback['mode'] == 'readback' and panel_readback['result'] == 'PASS'
    panel_visual = read(ROOT / 'environment/panel-material-validation.json')
    assert panel_visual['result'] == 'PASS_AFFECTED_LAYER' and not panel_visual['slice_acceptance']
    assert panel_visual['package_id'] == panel_package['package_id']
    for row in panel_visual['sources'] + panel_visual['inspected_frames'] + panel_visual['ordinary_input_inspected_frames']:
        check(row)
    for key in ('editor_validation', 'package_validation', 'asset_validation', 'saved_readback', 'mechanics_preservation'):
        check(panel_visual[key])
    diagnostic = read(PROJECT / panel_visual['editor_validation']['path'])
    assert diagnostic['result'] == 'PASS' and diagnostic['buffer'] == 'Lit'
    assert diagnostic['identities_before'] == diagnostic['identities_after']
    for row in diagnostic['identities_after']:
        if Path(row['path']).name == 'M_ServiceGround.uasset': check_historical_source(row, PANEL_COMMIT)
        else: check_pre_storm(row)
    assert len(panel_visual['ordinary_input_runs']) == len(panel_runs)
    for bound, observed in zip(panel_visual['ordinary_input_runs'], panel_runs):
        assert bound['run'] == observed['run']
        assert bound['active_simulation_seconds'] == observed['active_simulation_seconds']
        assert bound['terminal'] == observed['terminal']
        assert bound['power_transitions'] == observed['environment_power_transitions']
        assert bound['panel_events'] == observed['environment_panel_events']
        assert bound['electrical_floor_damage'] == observed['electrical_floor_damage']
        assert bound['raw_video'] == observed['raw_video']
        for key in ('raw_video', 'telemetry', 'runtime_log'): check(bound[key])
    edge_visual = read(ROOT / 'environment/floor-edge-material-validation.json')
    assert edge_visual['result'] == 'PASS_AFFECTED_LAYER' and not edge_visual['slice_acceptance']
    assert edge_visual['previous_commit'] == PANEL_COMMIT and edge_visual['package_id'] == floor_edge_package['package_id']
    for row in edge_visual['sources'] + edge_visual['inspected_frames'] + edge_visual['ordinary_input_inspected_frames']: check(row)
    for key in ('asset_validation', 'saved_readback', 'editor_validation', 'package_validation'): check(edge_visual[key])
    for row in edge_visual['preserved_native_geometry']: check(row)
    diagnostic = read(PROJECT / edge_visual['editor_validation']['path'])
    assert diagnostic['result'] == 'PASS' and diagnostic['buffer'] == 'Lit'
    assert diagnostic['identities_before'] == diagnostic['identities_after']
    for row in diagnostic['identities_after']: check_pre_storm(row)
    assert edge_visual['ordinary_input_runs'] == floor_edge_runs
    storm_assets = ROOT / 'environment/storm-assets-01/validation.json'
    storm_authoring = read(storm_assets)
    assert storm_authoring['result'] == 'PASS' and storm_authoring['fresh_process_readback_verified']
    assert storm_authoring['all_other_source_geometry_materials_config_unchanged']
    assert not storm_authoring['slice_acceptance']
    storm_inputs = storm_authoring['inputs_before'] | storm_authoring['changed_inputs']
    for row in (list(storm_inputs.values()) +
                [storm_authoring['author'], storm_authoring['spec']]): check_pre_hall(row)
    for run in storm_authoring['runs']:
        assert run['returncode'] == 0 and not run['timed_out'] and run['log_finalization']['closed']
        check(run['log'])
    storm_readback = read(storm_assets.parent / 'readback.json')
    assert storm_readback['result'] == 'PASS' and storm_readback['read_only']
    assert storm_readback['spec_sha256'] == storm_authoring['spec']['sha256']
    storm_visual = read(ROOT / 'environment/storm-lighting-validation.json')
    assert storm_visual['result'] == 'PASS_AFFECTED_LAYER' and not storm_visual['slice_acceptance']
    assert storm_visual['package_id'] == storm_package['package_id']
    for row in storm_visual['sources'] + storm_visual['inspected_frames']: check_pre_hall(row)
    for key in ('asset_validation', 'saved_readback', 'editor_validation', 'package_validation'): check(storm_visual[key])
    diagnostic = read(PROJECT / storm_visual['editor_validation']['path'])
    assert diagnostic['result'] == 'PASS' and diagnostic['buffer'] == 'Lit'
    assert diagnostic['identities_before'] == diagnostic['identities_after']
    for row in diagnostic['identities_after']: check_pre_hall(row)
    assert storm_visual['ordinary_input_runs'] == storm_runs
    hall_assets = ROOT / 'environment/hall-assets-03/validation.json'
    hall_authoring = read(hall_assets)
    assert hall_authoring['result'] == 'PASS' and hall_authoring['fresh_process_readback_verified']
    assert hall_authoring['all_other_source_geometry_materials_config_unchanged']
    assert not hall_authoring['slice_acceptance']
    for row in (list((hall_authoring['inputs_before'] | hall_authoring['changed_inputs']).values()) +
                [hall_authoring['author'], hall_authoring['spec']]): check(row)
    for run in hall_authoring['runs']:
        assert run['returncode'] == 0 and not run['timed_out'] and run['log_finalization']['closed']
        check(run['log'])
    hall_readback = read(hall_assets.parent / 'readback.json')
    assert hall_readback['result'] == 'PASS' and hall_readback['read_only']
    assert hall_readback['spec_sha256'] == hall_authoring['spec']['sha256']
    assert len(hall_readback['supports']) == 6 and hall_readback['collision_boxes'] == 0
    hall_visual = read(ROOT / 'environment/hall-cladding-validation.json')
    assert hall_visual['result'] == 'PASS_AFFECTED_LAYER' and not hall_visual['slice_acceptance']
    assert hall_visual['package_id'] == package['package_id']
    for row in hall_visual['sources'] + hall_visual['inspected_frames']: check(row)
    for key in ('asset_validation', 'saved_readback', 'geometry_validation', 'editor_validation', 'package_validation', 'frame_review'):
        check(hall_visual[key])
    frame_review = read(PROJECT / hall_visual['frame_review']['path'])
    assert frame_review['reviewed'] and frame_review['package_id'] == package['package_id']
    for name in CURRENT_RUNS:
        extraction = read(ROOT / 'raw' / name / 'frame-extraction.json')
        check(extraction['source_video'])
        assert extraction['source_video'] == ref(ROOT / 'raw' / name / 'raw-gameplay.mkv')
        for frame in extraction['frames']:
            assert frame['returncode'] == 0 and 0 <= frame['timestamp_seconds'] < extraction['duration_seconds']
            check(frame['frame'])
    hall_geometry = read(PROJECT / hall_visual['geometry_validation']['path'])
    assert hall_geometry['result'] == 'PASS' and hall_geometry['parts_read_back'] == 976
    assert hall_geometry['actual_blender_magic'] and hall_geometry['actual_binary_fbx_magic']
    for row in hall_geometry['sources']: check(row)
    diagnostic = read(PROJECT / hall_visual['editor_validation']['path'])
    assert diagnostic['result'] == 'PASS' and diagnostic['buffer'] == 'Lit'
    assert diagnostic['identities_before'] == diagnostic['identities_after']
    for row in diagnostic['identities_after']: check(row)
    assert hall_visual['ordinary_input_runs'] == new_runs
    # Absence of an ordinary-input beat is an acceptance gap, not an integrity
    # error. Never carry the historical outcome into a newer raw run.
    ordinary_environment = new_runs[0]
    floor_damage = ordinary_environment['electrical_floor_damage']
    geometry = read(ROOT / 'environment/mesh-author-05/geometry-readback.json')
    assert geometry['result'] == 'PASS'
    assert geometry['source_blend_sha256'] == ref(PROJECT / 'SourceAssets/Environment/ServiceBay.blend')['sha256']
    column, header = geometry['records']
    assert column['bounds_min'][1] > 244
    assert header['bounds_min'][1] > 194 and header['bounds_min'][2] > 215
    # The new native changes bind visual ground assets and the existing power
    # state. Exact function readback proves gameplay methods remained identical.
    preserved = read(ROOT / 'environment/ground-mechanics-preservation.json')
    assert preserved['result'] == 'PASS' and len(preserved['unchanged_native_functions']) == 11
    prior_native = subprocess.check_output(['git','show',INTEGER_COMMIT+':projects/biella-games/Source/BiellaGames/Private/BiellaEnvironmentSite.cpp'],cwd=PROJECT)
    assert preserved['source_sha256'] == hashlib.sha256(prior_native).hexdigest()
    original = subprocess.check_output(['git','show',SHEATH_COMMIT+':projects/biella-games/Source/BiellaGames/Private/BiellaEnvironmentSite.cpp'],cwd=PROJECT).decode()
    edited = (PROJECT/'Source/BiellaGames/Private/BiellaEnvironmentSite.cpp').read_text()
    def methods(text):
        matches=list(re.finditer(r'(?m)^(?:bool|float|void|FVector|FString) ABiellaEnvironmentSite::(\w+)\(',text))
        return {m[1]:text[m.start():matches[i+1].start() if i+1<len(matches) else len(text)] for i,m in enumerate(matches)}
    original_methods, edited_methods = methods(original), methods(edited)
    integer_methods = methods(prior_native.decode())
    for name, expected in preserved['unchanged_native_functions'].items():
        assert original_methods[name] == integer_methods[name]
        assert hashlib.sha256(integer_methods[name].encode()).hexdigest() == expected
    switch_preserved = read(ROOT / 'environment/switch-mechanics-preservation.json')
    assert switch_preserved['result'] == 'PASS' and switch_preserved['previous_commit'] == INTEGER_COMMIT
    check_historical_source(switch_preserved['source_before'], INTEGER_COMMIT)
    check_historical_source(switch_preserved['source_after'], SWITCH_COMMIT)
    switch_native = subprocess.check_output(['git','show',SWITCH_COMMIT+':projects/biella-games/Source/BiellaGames/Private/BiellaEnvironmentSite.cpp'],cwd=PROJECT).decode()
    switch_methods = methods(switch_native)
    prior_methods = methods(prior_native.decode())
    assert len(switch_preserved['unchanged_native_functions']) == 12
    for name, expected in switch_preserved['unchanged_native_functions'].items():
        assert prior_methods[name] == switch_methods[name]
        assert hashlib.sha256(switch_methods[name].encode()).hexdigest() == expected
    assert switch_preserved['switch_component_declaration'] in edited
    assert switch_preserved['switch_component_declaration'] in prior_native.decode()
    panel_preserved = read(ROOT / 'environment/panel-mechanics-preservation.json')
    assert panel_preserved['result'] == 'PASS' and panel_preserved['previous_commit'] == SWITCH_COMMIT
    check_historical_source(panel_preserved['source_before'], SWITCH_COMMIT)
    check(panel_preserved['source_after'])
    assert len(panel_preserved['unchanged_native_functions']) == 11
    for name, expected in panel_preserved['unchanged_native_functions'].items():
        assert switch_methods[name] == edited_methods[name]
        assert hashlib.sha256(edited_methods[name].encode()).hexdigest() == expected
    def damage_gameplay(text):
        # Strip the exact visual-only bindings; preserve every gameplay byte.
        text = re.sub(r'        const bool FirstImpact=PanelHealth\[I\]==68;\n', '', text)
        text = re.sub(r'        // Presentation records.*?PanelMaterials\[I\]->SetScalarParameterValue\(TEXT\("DamageAmount"\),1-PanelHealth\[I\]/68.0f\);\n', '', text, flags=re.S)
        return re.sub(r'        PanelMaterials\[I\]->SetVectorParameterValue\(TEXT\("BaseColor"\).*?;\n', '', text)
    old_damage, new_damage = damage_gameplay(switch_methods['TakeDamage']), damage_gameplay(edited_methods['TakeDamage'])
    assert old_damage == new_damage
    assert hashlib.sha256(new_damage.encode()).hexdigest() == panel_preserved['damage_gameplay_sha256']
    assert len(geometry['ground_parts']) == 200
    assert all(r['bounds_max'][2] <= 2.01 and r['bounds_min'][2] >= -2.01 for r in geometry['ground_parts'])
    prior_inputs = {r['path']: r for r in sheath_source['material_inputs']}
    floor_edge_inputs = {r['path']:r for r in floor_edge_source['material_inputs']}
    growth_delta = sorted(p for p in prior_inputs.keys() | floor_edge_inputs.keys() if prior_inputs.get(p) != floor_edge_inputs.get(p))
    allowed = {'Source/BiellaGames/Private/BiellaEnvironmentSite.cpp',
               'Source/BiellaGames/Public/BiellaEnvironmentSite.h', 'Content/Python/author_service_bay.py',
               'Content/Python/author_service_switch.py', 'Content/Python/author_service_panel.py'}
    assert growth_delta and all(p in allowed or p.startswith('Content/Environment/ServiceBay/') for p in growth_delta), growth_delta
    assert 'Content/Environment/ServiceBay/M_ServiceGround.uasset' in growth_delta
    assert 'Content/Environment/ServiceBay/SM_ServiceGround.uasset' in growth_delta
    ground_inputs = {r['path']:r for r in ground_source['material_inputs']}
    integer_inputs = {r['path']:r for r in integer_source['material_inputs']}
    wetness_delta = sorted(p for p in ground_inputs.keys() | integer_inputs.keys() if ground_inputs.get(p) != integer_inputs.get(p))
    assert wetness_delta == ['Content/Environment/ServiceBay/M_ServiceGround.uasset', 'Content/Python/author_service_bay.py'], wetness_delta
    smooth_inputs = {r['path']:r for r in smooth_source['material_inputs']}
    hash_delta = sorted(p for p in smooth_inputs.keys() | integer_inputs.keys() if smooth_inputs.get(p) != integer_inputs.get(p))
    switch_inputs = {r['path']:r for r in switch_source['material_inputs']}
    switch_delta = sorted(p for p in integer_inputs.keys() | switch_inputs.keys() if integer_inputs.get(p) != switch_inputs.get(p))
    panel_inputs = {r['path']:r for r in panel_source['material_inputs']}
    panel_delta = sorted(p for p in switch_inputs.keys() | panel_inputs.keys() if switch_inputs.get(p) != panel_inputs.get(p))
    edge_delta = sorted(p for p in panel_inputs.keys() | floor_edge_inputs.keys() if panel_inputs.get(p) != floor_edge_inputs.get(p))
    assert edge_delta == ['Content/Environment/ServiceBay/M_ServiceGround.uasset'], edge_delta
    assert edge_visual['material_input_delta'] == edge_delta
    storm_delta = sorted(p for p in floor_edge_inputs.keys() | storm_source_inputs.keys() if floor_edge_inputs.get(p) != storm_source_inputs.get(p))
    assert set(storm_delta) == set(storm_authoring['changed_inputs']) | {'Content/Python/author_storm_lighting.py'}, storm_delta
    assert storm_visual['material_input_delta'] == storm_delta
    hall_delta = sorted(p for p in storm_source_inputs.keys() | after.keys() if storm_source_inputs.get(p) != after.get(p))
    assert set(hall_delta) == set(hall_authoring['allowed_packages']) | {'Content/Python/author_service_hall.py'}, hall_delta
    assert hall_visual['material_input_delta'] == hall_delta
    assert panel_delta == ['Content/Environment/ServiceBay/M_ServicePanel.uasset', 'Content/Python/author_service_panel.py', 'Source/BiellaGames/Private/BiellaEnvironmentSite.cpp'], panel_delta
    assert switch_delta == ['Content/Environment/ServiceBay/M_ServiceSwitch.uasset', 'Content/Python/author_service_switch.py', 'Source/BiellaGames/Private/BiellaEnvironmentSite.cpp'], switch_delta
    assert hash_delta == ['Content/Environment/ServiceBay/M_ServiceGround.uasset'], hash_delta
    diagnosis = read(ROOT / 'environment/floor-diagnosis.json')
    assert diagnosis['baseline_source_commit'] == SMOOTH_COMMIT
    assert diagnosis['baseline_package_id'] == smooth_package['package_id']
    for key in ('before_source', 'before_asset'):
        check_historical_source(diagnosis[key], SMOOTH_COMMIT)
    for key in ('after_source', 'after_asset', 'asset_readback'):
        check_historical_source(diagnosis[key], INTEGER_COMMIT)
    assert diagnosis['runtime_material_input_delta'] == hash_delta
    assert {(o['phase'],o['buffer']) for o in diagnosis['observations']} == {
        ('before','WorldNormal'), ('before','Roughness'), ('before','BaseColor'),
        ('after','Roughness'), ('after','Lit')}
    # Old editor binaries were rebuilt in place. Bind their exact identities to
    # the preserved committed build report; never compare them with the new build.
    old_editor_report = ROOT / 'build/editor-03/validation.json'
    check_historical_source(ref(old_editor_report), INTEGER_COMMIT)
    old_editor_binaries = {r['path']:r for r in read(old_editor_report)['binaries']}
    for observation in diagnosis['observations']:
        check(observation['validation']); check(observation['inspected_frame'])
        diagnostic = read(PROJECT / observation['validation']['path'])
        assert diagnostic['result'] == 'PASS' and diagnostic['buffer'] == observation['buffer']
        assert diagnostic['identities_before'] == diagnostic['identities_after']
        assert diagnostic['scope'] == 'EDITOR_FIXTURE_MATERIAL_DIAGNOSIS_NOT_SLICE_ACCEPTANCE'
        for row in diagnostic['identities_before']:
            if Path(row['path']).name == 'M_ServiceGround.uasset':
                assert row['sha256'] == diagnosis['before_asset' if observation['phase']=='before' else 'after_asset']['sha256']
            elif row['path'] in old_editor_binaries:
                assert row == old_editor_binaries[row['path']]
            elif Path(row['path']).name == 'BiellaEnvironmentSite.cpp':
                check_historical_source(row, INTEGER_COMMIT)
            else:
                check_pre_storm(row)
    failed_diagnostic = diagnosis['failed_diagnostic']
    check(failed_diagnostic['validation'])
    assert failed_diagnostic['excluded_from_channel_evidence']
    assert read(PROJECT / failed_diagnostic['validation']['path'])['result'] == 'FAIL'
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
    all_runs = runs + [route_probe] + previous_service_runs + coordinate_runs + growth_runs + sheath_runs + ground_runs + smooth_runs + integer_runs + switch_runs + panel_runs + floor_edge_runs + storm_runs + new_runs + new_probes
    assert not any(run['uninterrupted_duration_satisfied'] for run in all_runs)
    report = dict(
        schema='biella.games.d17.qualification/v1', task_id='D17-01', observed=now(),
        status='INCOMPLETE', result='CONTINUE', accepted=False,
        evidence_integrity='VERIFIED', scenario=ref(ROOT / 'scenario.json'),
        owner_visual_contract=ref(PROJECT / 'docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md'),
        scope='Canonical slice candidate, HUD correction, editable service-bay materials, native cloud/fog lighting and fitted warehouse cladding; current Linux Development raw diagnostics and separately bound historical environment consequence',
        implementation=dict(changed_material_inputs=changed, build=ref(ROOT / 'build/game-05/result.json'),
                            editor_build=ref(ROOT / 'build/editor-05/validation.json'),
                            editable_source=ref(PROJECT / 'Source/BiellaGames/Private/BiellaEnvironmentSite.cpp'),
                            editable_art=[ref(p) for p in sorted((PROJECT / 'SourceAssets/Environment').iterdir()) if p.is_file()] + [ref(PROJECT / 'SourceAssets/Materials/ServiceSurface.hlsl'), ref(PROJECT / 'SourceAssets/Materials/ServiceGround.hlsl'), ref(PROJECT / 'SourceAssets/Materials/ServiceSwitch.hlsl'), ref(PROJECT / 'SourceAssets/Materials/ServicePanel.hlsl')],
                            source_manifest=ref(package_root / 'source-build.json'),
                            asset_readback=ref(assets), switch_asset_readback=ref(switch_assets),
                            switch_mechanics_preservation=ref(ROOT / 'environment/switch-mechanics-preservation.json'),
                            switch_material_validation=ref(ROOT / 'environment/switch-material-validation.json'),
                            panel_asset_readback=ref(panel_assets),
                            panel_mechanics_preservation=ref(ROOT / 'environment/panel-mechanics-preservation.json'),
                            panel_material_validation=ref(ROOT / 'environment/panel-material-validation.json'),
                            environment_regression=ref(environment),
                            geometry_clearance=ref(ROOT / 'environment/mesh-author-05/geometry-readback.json'),
                            visual_delta_from_sheath_package=growth_delta,
                            visual_delta_from_ground_package=wetness_delta,
                            floor_hash_delta=hash_delta, switch_material_delta=switch_delta, panel_material_delta=panel_delta, floor_edge_material_delta=edge_delta, visual_delta_from_previous_package=hall_delta,
                            hall_asset_readback=ref(hall_assets),
                            hall_cladding_validation=ref(ROOT / 'environment/hall-cladding-validation.json'),
                            storm_asset_readback=ref(storm_assets),
                            storm_lighting_validation=ref(ROOT / 'environment/storm-lighting-validation.json'),
                            floor_edge_material_validation=ref(ROOT / 'environment/floor-edge-material-validation.json'),
                            floor_material_diagnosis=ref(ROOT / 'environment/floor-diagnosis.json'),
                            source_material_digest=native_source['material_input_digest']),
        package=dict(package_id=package['package_id'],
                     manifest=ref(package_root / 'package-manifest.json'),
                     payload_files_digest=digest(package['files']),
                     exact_resolved_manifests=[ref(ROOT / 'raw' / n / 'resolved-package.json')
                                               for n in CURRENT_RUNS + CURRENT_PROBES],
                     cook=ref(ROOT / 'build/cook-14/validation.json'),
                     stage=ref(ROOT / 'build/stage-16/validation.json'),
                     install=ref(package_root / 'validation.json'), format='ELF64-x86_64',
                     platform='Linux', configuration='Development', renderer='Vulkan'),
        first_raw_run=runs[0], previous_raw_runs=runs[1:], current_raw_runs=new_runs, previous_input_timing_probe=sheath_runs[-1],
        current_environment_probe=dict(observation=new_runs[0],
            input_plan=ref(ROOT / 'service-hazard-input.json'),
            scope='Ordinary input on the current package; switching, panel physics and electrical-floor outcomes are extracted from native logs/telemetry above'),
        previous_storm_candidate=dict(source_commit=STORM_COMMIT,
            package=ref(ROOT / 'build/package-12/package-manifest.json'), raw_runs=storm_runs),
        previous_floor_edge_candidate=dict(source_commit=FLOOR_EDGE_COMMIT,
            package=ref(ROOT / 'build/package-11/package-manifest.json'), raw_runs=floor_edge_runs),
        previous_panel_candidate=dict(source_commit=PANEL_COMMIT,
            package=ref(ROOT / 'build/package-10/package-manifest.json'), raw_runs=panel_runs),
        previous_switch_candidate=dict(source_commit=SWITCH_COMMIT,
            package=ref(ROOT / 'build/package-09/package-manifest.json'), raw_runs=switch_runs),
        previous_integer_candidate=dict(source_commit=INTEGER_COMMIT,
            package=ref(ROOT / 'build/package-08/package-manifest.json'), raw_runs=integer_runs),
        previous_smooth_candidate=dict(source_commit=SMOOTH_COMMIT,
            package=ref(ROOT / 'build/package-07/package-manifest.json'), raw_runs=smooth_runs),
        previous_ground_candidate=dict(source_commit=GROUND_COMMIT,
            package=ref(ROOT / 'build/package-06/package-manifest.json'), raw_runs=ground_runs),
        previous_sheath_candidate=dict(source_commit=SHEATH_COMMIT,
            package=ref(ROOT / 'build/package-05/package-manifest.json'), raw_runs=sheath_runs),
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
                                    'Package-04 ordinary input proves power/panel physics/electrical-floor damage; package-08 separately validates the integer ground-noise hash through exact material readback, controlled G-buffer diagnostics, a fresh cook/package and the installed environment fixture while reusing unchanged geometry and native builds',
                                    'Package-09 binds a saved weathered service-switch material to the existing native BaseColor/Emission parameters; all twelve gameplay/presentation methods and the Switch component remain identical, with fresh native builds and packaged environment regression',
                                    'Package-10 replaces whole-panel tint with local first/latest point-hit coating/normal response; gameplay damage bytes and eleven other methods are preserved, with saved graph readback and fresh native/installed regression',
                                    'Package-11 confines apron moisture with a variable drying edge; geometry/native source are byte-identical, the saved material has fresh readback, and the rebuilt package passes installed environment regression',
                                    'Package-12 binds saved native cloud/fog actors and cooler sun/sky lighting; all geometry and native source are preserved, with fresh asset readback, cooked shaders, installed environment behavior and normal-camera raw captures',
                                    'Package-13 adds 976 editable fitted warehouse cladding parts, verified doorway clearance and preserved original colliders, with native saved readback, installed environment regression and raw gameplay captures'],
        unmet_criteria=[
            dict(id='continuous_slice_duration_and_route', required='600–1200 seconds of representative active gameplay with route beats',
                 observed=[{'run': r['run'], 'active_seconds': r['active_simulation_seconds'],
                            'terminal': r['terminal']} for r in all_runs],
                 next_action='Identify an accepted continuous content route before changing objective behavior; no actor resets, idle padding or invented mechanics'),
            dict(id='player_rival_infected_arena_pressure', required='Player, rival, infected and arena consequence in the evolving real encounter',
                 observed=dict(current_raw_environment=ordinary_environment, historical_ordinary_consequence=growth_runs[0], limit='Natural arena_pressure timing and the full evolving encounter composition remain unqualified; no outcome is inherited between packages.'),
                 next_action='Reuse verified ordinary-input environment outcomes; qualify the full player+rival+infected encounter and remaining route without inventing pressure timing or rewiring the switch'),
            dict(id='zero_major_visual_defects', required='All hard visual requirements with zero major defects',
                 observed=[d['id'] for d in visual['major_defects']],
                 next_action=visual['next_action'])],
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
