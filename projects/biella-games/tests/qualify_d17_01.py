#!/usr/bin/env python3
"""Reconcile D17-01's current candidate with exact raw evidence, without a pass.

This checkpoint deliberately remains incomplete while the recorded route is
shorter than the contract and the visual assessment contains major defects.
"""
from collections import Counter
import json
from pathlib import Path

from run_d08_01_release import digest, executable_format, identity, now, write, LEDGER


PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / 'Build/AAA/D17-01'
RUNS = ('entry-720-02', 'hud-720-01', 'hud-1080-01')


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
    check(build['binary'])
    assert ref(ROOT / 'build/game-01/BiellaGames.target')['sha256'] == build['receipt']['sha256']
    source = read(ROOT / 'raw/hud-720-01/native-source.json')
    for row in source['material_inputs']:
        check(row)
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
    runs = [observe(name) for name in RUNS]
    visual = read(ROOT / 'visual-assessment.json')
    assert visual['major_defects'] and not visual['zero_major_defects']
    assert not any(run['uninterrupted_duration_satisfied'] for run in runs)
    report = dict(
        schema='biella.games.d17.qualification/v1', task_id='D17-01', observed=now(),
        status='INCOMPLETE', result='CONTINUE', accepted=False,
        evidence_integrity='VERIFIED', scenario=ref(ROOT / 'scenario.json'),
        owner_visual_contract=ref(PROJECT / 'docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md'),
        scope='Canonical slice selection candidate and partial native HUD correction; Linux Development diagnostics',
        implementation=dict(changed_material_inputs=changed, build=ref(ROOT / 'build/game-01/result.json'),
                            native_receipt=ref(ROOT / 'build/game-01/BiellaGames.target'),
                            editable_source=ref(PROJECT / changed[0]),
                            source_manifest=ref(ROOT / 'raw/hud-720-01/native-source.json'),
                            source_material_digest=source['material_input_digest'],
                            native_delta=runtime['native_delta']),
        package=dict(base_package_id=runtime['base_package_id'],
                     base_manifest=ref(PROJECT / 'Build/Release/D08-01/package-manifest.json'),
                     payload_files_digest=digest(runtime['files']),
                     exact_resolved_manifests=[ref(ROOT / 'raw' / n / 'resolved-package.json')
                                               for n in ('hud-720-01', 'hud-1080-01')],
                     cook_reuse=runtime['cook_reuse'], format='ELF64-x86_64',
                     platform='Linux', configuration='Development', renderer='Vulkan'),
        first_raw_run=runs[0], current_raw_runs=runs[1:], hud_regressions=regressions,
        visual_assessment=ref(ROOT / 'visual-assessment.json'),
        satisfied_partial_criteria=['Editable route/start/beat/end candidate exists and binds owner direction',
                                    'Exact baseline/native-delta package identities and first raw run retained',
                                    'HUD change builds and existing live HUD/settings behavior tests pass'],
        unmet_criteria=[
            dict(id='continuous_slice_duration_and_route', required='600–1200 seconds of representative active gameplay with route beats',
                 observed='Every raw attempt reaches native Success before 35 simulation seconds; later beats are unproven',
                 next_action='Resolve early terminal behavior for the selected existing content route without actor resets, idle padding or invented mechanics; then run normal inputs continuously'),
            dict(id='player_rival_infected_arena_pressure', required='Player, rival, infected and arena consequence in the evolving real encounter',
                 observed='Raw clips contain no arena_pressure event; current native code defines/consumes pressure but has no non-test call raising it',
                 next_action='Trace the selected map/content pressure entry and bind a supported player-reachable trigger; fixture SetArenaPressure calls cannot substitute for the run'),
            dict(id='zero_major_visual_defects', required='All hard visual requirements with zero major defects',
                 observed=[d['id'] for d in visual['major_defects']],
                 next_action='Author the existing service-bay approach industrial materials, lighting and infection layer while preserving collision/gameplay; validate affected build and recapture')],
        proof_limits=['Short raw clips do not qualify long-form pacing or later route beats',
                      'HUD automation uses fixtures and is not raw-slice proof',
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
                         raw_simulation_seconds=[r['active_simulation_seconds'] for r in runs],
                         hud_regressions='2 PASS', major_visual_defects=len(visual['major_defects']))))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        with LEDGER.open('a') as stream:
            stream.write(json.dumps(dict(task_id='D17-01', time=now(), type='qualification_integrity',
                                         status='FAILED', diagnostics=f'{type(exc).__name__}: {exc}'[:1000])) + '\n')
        raise
