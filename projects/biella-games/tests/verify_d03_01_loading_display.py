#!/usr/bin/env python3
"""Decode independent X11 evidence, rejecting static bars and missing world handoff."""
import argparse
import json
from pathlib import Path
import subprocess
import numpy as np


def has_scene_pixels(frame):
    # This fixture's central/lower scene excludes both top HUD panels and the
    # bottom threat banner. A HUD over a black scene must not count as a world.
    scene = frame[280:590, 300:960]
    return bool((scene.mean(axis=2) > 20).mean() > 0.6 and
                scene.std(axis=(0, 1)).mean() > 5)


def verify(out, enabled=True):
    metadata = json.loads((out/'loading-display.json').read_text())
    assert metadata['game_returncode'] == 0
    # SIGINT closes FFmpeg's container normally but reports 255.
    assert metadata['recorder_returncode'] in (0, 255), 'Recorder failed'
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                              '-of', 'json', str(out/'loading-display.mp4')]))
    stream = probe['streams'][0]
    assert (stream['width'], stream['height'], stream['r_frame_rate']) == (1280, 720, '10/1')
    process = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(out/'loading-display.mp4'),
                                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    loading, worlds, centers, title_deltas = [], [], [], []
    previous_title = None
    index = 0
    try:
        while True:
            raw = process.stdout.read(1280*720*3)
            if not raw:
                break
            assert len(raw) == 1280*720*3, 'Truncated decoded frame'
            frame = np.frombuffer(raw, np.uint8).reshape(720, 1280, 3).astype(np.float32)
            corners = frame[[100, 100, 600, 600], [100, 1180, 100, 1180]]
            is_loading = bool(np.max(np.abs(corners - [20, 29, 38])) < 16)
            if is_loading:
                loading.append(index)
                bar = frame[378:386, 444:836]
                cyan = (bar[:, :, 1] > 140) & (bar[:, :, 2] > 170) & (bar[:, :, 1]-bar[:, :, 0] > 40)
                columns = np.flatnonzero(cyan.sum(axis=0) >= 2)
                if 40 <= len(columns) <= 160:
                    centers.append(dict(frame=index, x=float(columns.mean()+444), width=len(columns)))
                title = frame[290:347, 520:760]
                if previous_title is not None:
                    title_deltas.append(float(np.abs(title-previous_title).mean()))
                previous_title = title.copy()
            elif has_scene_pixels(frame):
                worlds.append(index)
            index += 1
    finally:
        process.stdout.close()
        rc = process.wait(timeout=15)
    assert rc == 0, 'Decode failed'
    trailing_static = 0
    if centers:
        for sample in reversed(centers):
            if abs(sample['x']-centers[-1]['x']) > 2:
                break
            trailing_static += 1
    result = dict(schema='biella.loading_display/v2', frames=index, loading_frames=loading, world_frames=worlds,
                  indicator_samples=centers, max_title_delta=max(title_deltas, default=0),
                  trailing_static_loading_seconds=trailing_static/10,
                  scope='Lossy X11 10Hz fixture-specific screening; excludes HUD-only frames; scene candidates require visual review; no continuous-loading or first-frame-readiness acceptance')
    analysis = out/'loading-display-analysis-v2.json'
    assert not analysis.exists(), 'Preserve existing decoded evidence'
    analysis.write_text(json.dumps(result, indent=2)+'\n')
    if enabled:
        assert len(loading) >= 2, 'No sustained loading display'
        assert len(centers) >= 2, 'No distinct activity segment in decoded loading frames'
        result['indicator_span_pixels'] = max(c['x'] for c in centers)-min(c['x'] for c in centers)
        assert result['indicator_span_pixels'] >= 12, 'Activity segment does not visibly move'
        assert result['max_title_delta'] < 3, 'Loading title unstable'
        assert worlds and min(worlds) > min(loading), 'No visible handoff after loading'
        result['last_loading_to_first_world_seconds'] = (min(worlds)-max(loading))/10
    else:
        assert not loading, 'Disabled control still shows loading UI'
        assert worlds, 'Disabled control did not reach visible world'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--disabled', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify(args.output, not args.disabled), indent=2))
