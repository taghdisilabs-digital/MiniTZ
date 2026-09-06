#!/usr/bin/env python3
"""Replay actual seated bone contacts alongside native input and Chaos evidence."""
import csv
import math
from pathlib import Path
from PIL import Image
from verify_d02_01 import require
from verify_d03_01_vehicle import verify as verify_vehicle


def verify(output, disabled=False):
    output = Path(output)
    vehicle = verify_vehicle(output)
    with (output / 'driver-pose.csv').open() as stream:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(stream)]
    with (output / 'frames.csv').open() as stream:
        frames = list(csv.DictReader(stream))
    require(len(rows) == len(frames) > 300, 'Missing driver frames')
    require(all(all(math.isfinite(v) for v in r.values()) for r in rows), 'Nonfinite driver telemetry')
    for r, f in zip(rows, frames):
        require(r['frame'] == float(f['frame']) and r['phase'] == float(f['phase']), 'Driver/physics lineage mismatch')
        require(r['mounted'] == float(f['driver']) and r['alive'] == (float(f['player_health']) > 0), 'Driver gameplay mismatch')
        if not r['stable']:
            continue
        require(r['wheel_collision'] == 0, 'Cosmetic cockpit affects collision/navigation')
        require(r['wheel_visible'] == r['wheel_expected'], 'Cockpit visibility does not follow vehicle fallback/dormancy')
        if r['mounted']:
            require(r['seated'] == r['visible'] == r['enabled'], 'Driver representation state mismatch')
            require(r['blockout'] == (r['alive'] and not r['enabled']), 'Fallback mismatch')
            require(r['root_error'] < .001 and r['action_weight'] == 0, 'Seat changes gameplay root or retains on-foot actions')
        else:
            require(r['seated'] == 0, 'Seat pose leaked after exit')
    seated = [r for r in rows if r['stable'] and r['seated']]
    errors = ('pelvis_error', 'feet_error', 'hands_error', 'length_error', 'grip_error')
    require(all(max(r[k] for k in errors) < .5 and r['length_error'] < .05 for r in seated), 'Seat or moving wheel contact failed')
    require(all(r['grip_error'] < .001 for r in seated), 'Fingers do not straddle the moving steering rim')
    if disabled:
        require(not seated, 'Disabled driver pose evaluated')
    else:
        require(len(seated) > 200, 'Missing seated animation')
        for phase in (3, 4, 5, 6, 8, 17, 18):
            require(sum(r['phase'] == phase for r in seated) > 5, 'Missing seated driving state')
        require(any(r['steering'] > .9 for r in seated) and any(r['steering'] < -.9 for r in seated), 'Hands never followed both steering directions')
    fallback = [r for r in rows if r['stable'] and r['mounted'] and r['blockout']]
    require(len(fallback) > 10, 'Missing driver fallback')
    require(sum(r['stable'] and r['phase'] == 13 and not r['mounted'] for r in rows) > 10, 'Missing dismount')
    require(sum(r['stable'] and r['mounted'] and not r['alive'] and not r['visible'] for r in rows) > 10, 'Missing seated defeat')
    for name in ('cockpit', 'cockpit_front'):
        with Image.open(output / 'captures' / (name + '.png')) as im:
            im.load()
            require(im.size == (1280, 720), 'Missing native cockpit capture')
    return dict(result='EXPECTED_NEGATIVE_CONTROL' if disabled else 'PASS', vehicle=vehicle,
                driver_frames=len(rows), seated_frames=len(seated), fallback_frames=len(fallback),
                max_errors={k: max((r[k] for r in seated), default=0) for k in errors})
