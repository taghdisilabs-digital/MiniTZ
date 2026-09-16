#!/usr/bin/env python3
"""Measure native D17 route observations; never infer final visual acceptance.

X11 waypoint intent is checked against native positions. Telemetry and decoded
video remain complementary evidence: collision queries cannot assess art quality.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess

from run_d08_01_release import identity, write


PROJECT = Path(__file__).resolve().parents[1]


def resolve_snapshot_path(value):
    """Resolve preserved receipts after the project moved from its predecessor root."""
    path = Path(value)
    if path.exists():
        return path
    marker = '/projects/biella-games/'
    text = path.as_posix()
    if marker in text:
        candidate = PROJECT / text.split(marker, 1)[1]
        if candidate.exists():
            return candidate
    return path


def snapshot_matches(snapshot, expected_sha256):
    if not snapshot:
        return False
    path = resolve_snapshot_path(snapshot['path'])
    try:
        actual = identity(path)
    except FileNotFoundError:
        return False
    return (actual['sha256'] == snapshot['sha256'] == expected_sha256
            and actual['bytes'] == snapshot['bytes'])


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure(directory):
    telemetry = rows(directory / 'telemetry.jsonl')
    inputs = rows(directory / 'input.jsonl')
    receipt = read(directory / 'inputs.json')
    faults = []
    for key, item in receipt.items():
        snapshot = item.get('snapshot')
        if not snapshot_matches(snapshot, item['sha256']):
            faults.append('Missing or mismatched exact input snapshot: '+key)
    plan = read(resolve_snapshot_path(receipt['plan']['snapshot']['path']))
    observed = [r for r in telemetry if r['event'] == 'traversal_frame']
    by_frame = {r['fields']['frame']: r for r in observed}
    active = [r for r in observed if r['fields']['phase'] == 'Active' and r['fields']['ready'] == 'true']
    if not active:
        raise ValueError('No ready native gameplay frames')
    interrupted = [r for r in observed if r['seq'] >= active[0]['seq']
                   and r['fields']['phase']=='Active' and r['fields']['ready']!='true']
    if interrupted:
        faults.append('Traversal became unavailable after initial readiness')
    if int(active[-1]['fields']['holds']) != int(active[0]['fields']['holds']):
        faults.append('New floor safety hold during the route')
    if len({r['session'] for r in telemetry}) != 1 or any(r['restart_count'] != 0 for r in telemetry):
        faults.append('Native session/restart discontinuity')
    if any(b['seq'] != a['seq']+1 for a,b in zip(telemetry,telemetry[1:])):
        faults.append('Native telemetry sequence gap')
    if any(r['map'] != 'BiellaOpenWorldMap' for r in active):
        faults.append('Wrong native map')
    reached = [r for r in inputs if r['event'] == 'route_stage_reached']
    stages = []
    for event in reached:
        index, f = event['stage'], event['observed']
        native = by_frame.get(f['frame'])
        matches = bool(native and native['fields'] == f and f['phase'] == 'Active')
        if not matches:
            faults.append('Stage does not match a live native frame: '+str(index))
        stage = plan['stages'][index]
        if stage != event['intended']:
            faults.append('Stage intent differs from captured input source: '+str(index))
        error = None
        if stage['kind'] == 'walk':
            error = math.dist([float(f['x']),float(f['y'])], stage['at'])
            if error >= stage.get('radius',70):
                faults.append('Native waypoint outside its intended radius: '+str(index))
            # Same canonical walkable planes as the predecessor: 4 m terrace
            # rise and ground-level street. XY success cannot hide a fall.
            expected_height = ([480,505] if stage['at']==[10000,3400] else
                               [80,110] if stage['at']==[10000,1000] else None)
            if expected_height and not expected_height[0] <= float(f['z']) <= expected_height[1]:
                faults.append('Canonical route plane height mismatch: '+str(index))
        stages.append(dict(index=index, beat=stage['beat'], kind=stage['kind'],
                           video_seconds=event['elapsed_seconds'],
                           sim_seconds=native['sim_seconds'] if native else None,
                           native_frame=f['frame'], position=[float(f[k]) for k in 'xyz'],
                           health=float(f['health']), position_error_cm=error,
                           native_match=matches))
    complete = [r['stage'] for r in reached] == list(range(len(plan['stages'])))
    if not complete:
        faults.append(f'Route incomplete: {len(reached)}/{len(plan["stages"])} stages')
    result = read(directory / 'input-result.json')
    if result.get('reason') != 'route_inputs_finished' or result.get('world_mutation_or_automation_tests') is not False:
        faults.append('Raw run did not finish the route using ordinary inputs')
    if any(float(r['fields']['arm']) != 520 or float(r['fields']['fov']) != 90 for r in active):
        faults.append('Production camera arm or FOV changed')
    if any(float(r['observed']['health']) <= 0 for r in reached):
        faults.append('Route stage reached with defeated player')
    native_faults = {}
    conditions = {
        'camera_overlap': lambda f:f['camera_overlap']=='true',
        'near_plane_geometry_hits': lambda f:int(f['near_hits'])>0,
        'pawn_static_overlap': lambda f:f['pawn_static_overlap']=='true',
        'body_occlusion': lambda f:f['body_occluded']=='true',
        'player_center_outside_frame': lambda f:f['projected']!='true' or not
            (0<float(f['center_u'])<1 and 0<float(f['center_v'])<1),
        'head_outside_frame': lambda f:not 0<float(f['head_v'])<1,
        'feet_outside_frame': lambda f:not 0<float(f['feet_v'])<1,
        'nonplayer_view': lambda f:f['view_target_player']!='true',
    }
    for name, predicate in conditions.items():
        hits = [r for r in active if predicate(r['fields'])]
        span = longest = 0.0
        for r in active:
            span = span + float(r['fields']['delta_ms'])/1000 if predicate(r['fields']) else 0
            longest = max(longest,span)
        native_faults[name] = dict(frames=len(hits), longest_seconds=longest,
            first_native_frames=[r['fields']['frame'] for r in hits[:5]],
            blockers=sorted({r['fields'][key] for r in hits for key in ('near_blocker','body_blocker')
                             if r['fields'][key] not in ('','None')}))
        # Head/feet crop can be the normal close shoulder view. Preserve it for
        # visual inspection rather than silently accepting or mislabeling it.
        if hits and name not in ('head_outside_frame','feet_outside_frame'):
            faults.append('Native camera/collision issue: '+name)
    travel = sum(math.dist([float(a['fields'][k]) for k in 'xyz'],
                           [float(b['fields'][k]) for k in 'xyz']) for a,b in zip(active,active[1:]))
    steps = [(math.dist([float(a['fields'][k]) for k in 'xyz'],[float(b['fields'][k]) for k in 'xyz']),
              b['sim_seconds']-a['sim_seconds']) for a,b in zip(active,active[1:])]
    jumps = [(distance,dt) for distance,dt in steps if distance > 650*dt+15]
    if jumps:
        faults.append('Unexplained native position discontinuity')
    deltas = sorted(float(r['fields']['delta_ms']) for r in active)
    quantile = lambda p:deltas[min(len(deltas)-1,int((len(deltas)-1)*p))]
    decode = subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',
                             str(directory/'raw-gameplay.mkv'),'-f','null','-'],
                            text=True,capture_output=True)
    if decode.returncode != 0 or decode.stderr.strip():
        faults.append('Raw video decode error')
    video = read(directory/'video.json')
    actual_video = identity(directory/'raw-gameplay.mkv')
    recorded_video = video['identity']
    if (actual_video['sha256'] != recorded_video['sha256']
            or actual_video['bytes'] != recorded_video['bytes']):
        faults.append('Raw video identity mismatch')
    return dict(schema='biella.d17.traversal_measurement/v1', task_id='D17-02',
        measurement_source=identity(Path(__file__)),
        status='MEASUREMENTS_CLEAR_REQUIRES_VISUAL_QUALIFICATION' if not faults else 'UNMET_CRITERIA',
        limits=['Instrument-assisted X11 route; not external-player usability evidence',
                'Read-only native collision probes do not prove visual quality',
                'No AAA, whole-slice duration, shipping or platform qualification inferred'],
        evidence={name:identity(directory/name) for name in
                  ('telemetry.jsonl','runtime.engine.log','input.jsonl','inputs.json','input-result.json',
                   'resolved-package.json','native-source.json','raw-gameplay.mkv')},
        stages=stages, required_stages=len(plan['stages']), route_complete=complete,
        ready_active_frames=len(active), active_sim_seconds=active[-1]['sim_seconds']-active[0]['sim_seconds'],
        active_unready_after_start=len(interrupted),
        path_length_cm=travel, unexplained_position_steps=jumps,
        z_min_max=[min(float(r['fields']['z']) for r in active),max(float(r['fields']['z']) for r in active)],
        production_camera=dict(arm_values=sorted({float(r['fields']['arm']) for r in active}),
                               fov_values=sorted({float(r['fields']['fov']) for r in active}),
                               min_arm_distance_cm=min(float(r['fields']['arm_distance']) for r in active)),
        floor_hold_count_at_first_ready=int(active[0]['fields']['holds']),
        floor_hold_count_at_last_ready=int(active[-1]['fields']['holds']),
        frame_ms=dict(p50=quantile(.5),p95=quantile(.95),p99=quantile(.99),maximum=max(deltas)),
        camera_collision_observations=native_faults, faults=faults,
        video_decode=dict(returncode=decode.returncode,diagnostics=decode.stderr[:1000]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture',type=Path)
    args=parser.parse_args()
    result=measure(args.capture.resolve())
    write(args.capture/'measurements.json',result)
    print(json.dumps({k:result[k] for k in ('status','route_complete','ready_active_frames','faults')}))


if __name__=='__main__':
    main()
