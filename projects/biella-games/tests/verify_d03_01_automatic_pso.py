#!/usr/bin/env python3
"""Check both startup PSO counters and the demonstrated long indicator freeze.

10 Hz lossy display samples can reject a one-second frozen indicator, but cannot
qualify uninterrupted animation or native frame times between samples.
"""
import argparse
import csv
import json
from pathlib import Path
import re

from run_d01_039 import file_identity, write_json
from verify_d03_01_handoff import verify as verify_handoff


def observe(out):
    display = json.loads((out/'loading-display-analysis-v2.json').read_text())
    longest, run = [], []
    for sample in display['indicator_samples']:
        if run and sample['frame'] != run[-1]['frame']+1:
            run = []
        run.append(sample)
        while max(s['x'] for s in run)-min(s['x'] for s in run) > 2:
            run.pop(0)
        if len(run) > len(longest):
            longest = run.copy()
    log = (out/'runtime.engine.log').read_text(errors='replace')
    patterns = dict(
        start=r'D03_AUTOMATIC_PSO_START version=1 wait=(\d+) file_cache=(\d+) automatic=(\d+) enabled=(-?\d+) min_priority=(-?\d+) task_threshold=(-?\d+)',
        stop=r'D03_AUTOMATIC_PSO_STOP version=1 wait=(\d+) file_cache=(\d+) automatic=(\d+)',
        handoff=r'D03_AUTOMATIC_PSO_HANDOFF version=1 wait=(\d+) file_cache=(\d+) automatic=(\d+)')
    native = {key: [list(map(int, m)) for m in re.findall(pattern, log)] for key, pattern in patterns.items()}
    samples = []
    if (out/'loading-pso-samples.csv').is_file():
        with (out/'loading-pso-samples.csv').open() as stream:
            samples = list(csv.DictReader(stream))
    return dict(native=native, sampled_max_automatic=max((int(s['automatic']) for s in samples), default=0),
                sampled_max_file_cache=max((int(s['file_cache']) for s in samples), default=0),
                pipeline_sample_count=len(samples),
                longest_static_seconds=(longest[-1]['frame']-longest[0]['frame'])/10 if longest else 0,
                longest_static_frames=[s['frame'] for s in longest],
                unmeasured_loading_frames=sorted(set(display['loading_frames'])-
                    {s['frame'] for s in display['indicator_samples']}),
                first_scene_frame=min(display['world_frames']),
                evidence=[file_identity(out/name) for name in (
                    'runtime.engine.log', 'loading-display.mp4', 'loading-display-analysis-v2.json')])


def verify(out, require_observed_work=False):
    report = dict(task_id='D03-01', result='FAIL', observations=observe(out),
                  scope='Both configured PSO counters and rejection of >=1s static indicator at 10Hz; not continuous-motion or native frame-time acceptance')
    try:
        observed = report['observations']
        native = observed['native']
        assert all(len(native[k]) == 1 for k in native), 'Missing or repeated separate-counter telemetry'
        start, stop, handoff = (native[k][0] for k in ('start', 'stop', 'handoff'))
        assert start[0] == 1 and stop == handoff == [1, 0, 0], 'Automatic wait bypassed or outstanding PSOs at release'
        assert start[3:] == [1, 0, 0], 'Automatic precaching disabled or priority-filtered'
        assert observed['pipeline_sample_count'] >= 3, 'Missing pipeline observations'
        if require_observed_work:
            assert max(start[2], observed['sampled_max_automatic']) > 0, 'No automatic work observed in cold fixture'
        report['handoff'] = verify_handoff(out)
        assert not observed['unmeasured_loading_frames'], 'Activity segment missing from loading samples'
        assert observed['longest_static_seconds'] < 1.0, 'Indicator static for at least one second'
        report['result'] = 'PASS'
    except AssertionError as error:
        report['error'] = str(error)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-observed-work', action='store_true')
    args = parser.parse_args()
    assert not args.output.exists(), 'Preserve evidence'
    result = verify(args.runtime, args.require_observed_work)
    write_json(args.output, result)
    print(json.dumps(result))
    raise SystemExit(0 if result['result'] == 'PASS' else 1)
