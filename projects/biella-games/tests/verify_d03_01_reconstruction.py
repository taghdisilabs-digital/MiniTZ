#!/usr/bin/env python3
"""Replay native view observations joined to authoritative scenario frames."""
import csv
import math
from pathlib import Path


def read_rows(path):
    with Path(path).open() as stream:
        return [{key: float(value) for key, value in row.items()} for row in csv.DictReader(stream)]


def verify_rows(views, frames, profile):
    def require(value, message):
        if not value:
            raise AssertionError(message)
    expected_aa = 4 if profile == 'ProductionTSR' else 2
    require(profile in ('ProductionTSR', 'NativeTAA'), 'Unknown expected profile')
    require(len(views) > 250 and len(frames) > 250, 'Missing native view or scenario frames')
    require(all(math.isfinite(value) for row in views for value in row.values()), 'Nonfinite native view state')
    require(all(b['frame'] >= a['frame'] for a, b in zip(views, views[1:])), 'Unordered native views')
    # Loading can render multiple view families inside one GFrameCounter.
    # Retain and validate every matching primary view instead of overwriting it.
    by_frame = {}
    for row in views:
        if row['view'] == 0:
            by_frame.setdefault(row['frame'], []).append(row)
    require(len({row['frame'] for row in frames}) == len(frames), 'Duplicate scenario frames')
    missing = [row['frame'] for row in frames if row['frame'] not in by_frame]
    require(not missing, f'Scenario frames without native view: {missing[:5]}')
    joined = [view for row in frames for view in by_frame[row['frame']]]
    expected = dict(aa=expected_aa, requested_aa=expected_aa, screen_percentage=100,
                    temporal_upsampling=1 if profile == 'ProductionTSR' else 0,
                    dynamic_res=0, gi=1, reflections=1, vsm=1, nanite=1,
                    ray_tracing=0, external_upscaler=0, width=1280, height=720)
    if profile == 'ProductionTSR':
        expected['tsr_supported'] = 1
    for key, value in expected.items():
        require(all(row[key] == value for row in joined), f'Native view invariant failed: {key}={value}')
    return dict(observed_views=len(views), joined_scenario_frames=len(frames), joined_views=len(joined), missing_frames=missing,
                multiple_view_frames=sum(len(by_frame[row['frame']]) > 1 for row in frames),
                first_frame=joined[0]['frame'], last_frame=joined[-1]['frame'], expected=expected,
                scope='Constructed game-thread views plus requested renderer cvars; no generated frames or hardware compatibility claim')


def verify(out, profile):
    out = Path(out)
    return verify_rows(read_rows(out/'native-views.csv'), read_rows(out/'frames.csv'), profile)
