#!/usr/bin/env python3
"""Check startup handoff against independent display samples and native events.

The existing scene-pixel screening is fixture-specific, not a general visual
quality oracle. Keep visual review and RHI submission distinct from GPU/display
completion. This adds the missing no-exposed-black-frame boundary.
"""
import argparse
import json
from pathlib import Path
import re


def check_display(analysis):
    loading = analysis['loading_frames']
    worlds = analysis['world_frames']
    assert loading and worlds, 'Missing loading or actual scene samples'
    first_scene = min(worlds)
    assert max(loading) < first_scene, 'Loading reopened after visible scene'
    missing = sorted(set(range(min(loading), first_scene)) - set(loading))
    assert not missing, f'Exposed non-scene frames during handoff: {missing}'
    return dict(first_scene_frame=first_scene, last_loading_frame=max(loading),
                exposed_non_scene_frames=missing)


def verify(out):
    display = check_display(json.loads((out/'loading-display-analysis-v2.json').read_text()))
    log = (out/'runtime.engine.log').read_text(errors='replace')
    starts = re.findall(r'D03_HANDOFF_START version=1', log)
    ends = re.findall(r'D03_HANDOFF_END version=1 reason=(\w+) frame=(\d+) submissions=(\d+) pending=(\d+) missing_proxies=(\d+) meshes=(\d+) elapsed_s=([\d.]+)', log)
    assert len(starts) == len(ends) == 1, 'Missing or repeated native lifecycle'
    reason, frame, submissions, pending, missing, meshes, elapsed = ends[0]
    assert reason == 'ready', f'Handoff degraded: {reason}'
    assert int(submissions) >= 2 and int(pending) == int(missing) == 0 and int(meshes) > 0
    assert log.index('D03_LOADING_STOP') < log.index('D03_HANDOFF_START') < log.index('D03_HANDOFF_END') < log.index('Test Completed. Result={Success}')
    return dict(task_id='D03-01', result='PASS', display=display, native=dict(
        reason=reason, frame=int(frame), submissions=int(submissions), pending=int(pending),
        missing_proxies=int(missing), meshes=int(meshes), elapsed_s=float(elapsed)),
        scope='Startup handoff fixture; RHI submission fence is not GPU/display completion; screenshots require review')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve existing evidence'
    try:
        report = verify(args.runtime)
    except (AssertionError, OSError, ValueError, KeyError) as error:
        report = dict(task_id='D03-01', result='FAIL', error=str(error))
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    raise SystemExit(0 if report['result'] == 'PASS' else 1)
