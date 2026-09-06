#!/usr/bin/env python3
"""Replay evaluated vehicle bones alongside the authoritative driving telemetry."""
import csv
import math
from pathlib import Path
from verify_d02_01 import require
from verify_d02_03 import verify as verify_driving


def verify(output, disabled=False):
    output = Path(output)
    driving = verify_driving(output)
    with (output / 'frames.csv').open() as stream:
        frames = list(csv.DictReader(stream))
    with (output / 'vehicle-pose.csv').open() as stream:
        rows = [{key: float(value) for key, value in row.items()} for row in csv.DictReader(stream)]
    require(len(rows) == len(frames) > 300, 'Missing pose frames')
    require(all(all(math.isfinite(v) for v in r.values()) for r in rows), 'Nonfinite rig telemetry')
    rigid_errors = ('rigid_center_error', 'rigid_axle_error', 'rigid_spin_error', 'rigid_radius_error', 'rigid_body_error')
    for row, frame in zip(rows, frames):
        require(row['frame'] == float(frame['frame']) and row['phase'] == float(frame['phase']), 'Pose/physics lineage mismatch')
        require(row['dormant'] == float(frame['dormant']), 'Pose dormancy differs from gameplay')
        require(row['root_error'] < .01 and row['cosmetic_collision'] == 0 and row['paint_error'] < .001, 'Authority or damage presentation mismatch')
        require(not (row['body_visible'] and row['rig_visible']), 'Overlapping representations')
        require(row['rigid_visible'] == 5 * row['rig_visible'], 'Missing or stale rendered body/tires')
        require(max(row[k] for k in rigid_errors) < .1, 'Rendered rigid geometry differs from gameplay')
        if row['dormant']:
            require(row['rig_visible'] == row['body_visible'] == 0, 'Dormant representation visible')
    for a, b in zip(rows, rows[1:]):
        require(b['updates'] >= a['updates'], 'Pose update counter regressed')
        if a['dormant'] and b['dormant']:
            require(a['updates'] == b['updates'], 'Dormant rig still evaluates')
    visible = [r for r in rows if r['rig_visible']]
    if disabled:
        require(not visible and all(r['updates'] == 0 for r in rows), 'Disabled rig evaluated')
    else:
        require(len(visible) > 200, 'Skeletal presentation absent')
        require(all(max(r[k] for k in ('wheel_error', 'axle_error', 'spin_error', 'link_error')) < .1 for r in visible), 'Evaluated wheel or linkage mismatch')
        for phase in (3, 4, 5, 6, 8, 17, 18):
            require(sum(r['phase'] == phase for r in visible) > 5, 'Missing skeletal driving state')
        require(sum(r['body_visible'] and r['phase'] == 7 for r in rows) > 10, 'Live fallback switching not exercised')
    require(sum(r['body_visible'] for r in rows) > 10 and sum(r['dormant'] for r in rows) > 10, 'Missing fallback/dormancy coverage')
    return dict(result='EXPECTED_NEGATIVE_CONTROL' if disabled else 'PASS', driving=driving,
                pose_frames=len(rows), visible_frames=len(visible), fallback_frames=sum(r['body_visible'] for r in rows),
                dormant_frames=sum(r['dormant'] for r in rows),
                max_errors={k: max(r[k] for r in rows) for k in ('wheel_error', 'axle_error', 'spin_error', 'link_error', 'root_error', 'paint_error') + rigid_errors},
                measurement_scope='Actual native frames with 60fps cap, streaming, readback and captures included; not clean performance or PSO qualification')
