#!/usr/bin/env python3
"""Independent frame/capture validation; measurements are not artistic acceptance."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import numpy as np
from PIL import Image, ImageStat

def require(value, why):
    if not value:
        raise AssertionError(why)

def verify(out, aa, percentage):
    out = Path(out)
    result = json.loads((out/'result.json').read_text())
    require(result['success'] and result['rhi']=='Vulkan' and not result['fixed_timestep'] and not result['benchmark'], 'Native variable-step Vulkan result required')
    require(result['surface_count']>=3 and result['walk_cm']>200, 'Playable world surface coverage or movement missing')
    with (out/'frames.csv').open() as f:
        rows = [{k:float(v) for k,v in row.items()} for row in csv.DictReader(f)]
    require(len(rows)>250 and all(math.isfinite(v) for r in rows for v in r.values()), 'Insufficient or nonfinite native frames')
    require(all(b['frame']>a['frame'] for a,b in zip(rows, rows[1:])), 'Nonmonotonic native frame identity')
    require(all(r['aa']==aa and r['screen_percentage']==percentage for r in rows), 'Requested quality path not active')
    require(all(r[k]==0 for r in rows for k in ('motion_blur_quality','dynamic_res','vsync','frame_cap')), 'Blur, dynamic resolution or pacing obscures the comparison')
    costs = {}
    for phase, name in ((2,'stationary'),(4,'camera_pan')):
        group = [r for r in rows if r['phase']==phase]
        # Drop the first 0.5s after each change. These phases never request a capture.
        elapsed = 0; samples = []
        for r in group:
            elapsed += r['sim_ms']
            if elapsed>500: samples.append(r)
        require(len(samples)>=30 and all(r['shot_requested']==0 for r in group), 'Performance window contaminated by capture or too short')
        require(all(r['wall_ms']>0 and r['gpu_ms']>0 for r in samples), 'Missing native wall/GPU timings')
        costs[name] = {'frames':len(samples), 'wall_p50_ms':statistics.median(r['wall_ms'] for r in samples),
                       'wall_p95_ms':float(np.percentile([r['wall_ms'] for r in samples],95)),
                       'gpu_p50_ms':statistics.median(r['gpu_ms'] for r in samples)}
    walk = [r for r in rows if r['phase']==7]
    require(walk[-1]['x']-walk[0]['x']>200 and all(r['ready']==1 for r in walk), 'Real traversal did not advance over resident ground')
    with (out/'captures.csv').open() as f: capture_rows = list(csv.DictReader(f))
    expected = [f'static_{i:03}' for i in range(10)]+[f'pan_{i:03}' for i in range(32)]+['walk_end']
    require([r['name'] for r in capture_rows]==expected, 'Capture sequence incomplete or duplicated')
    captures = []; stills = []; pans = []
    for r in capture_rows:
        path = out/'captures'/f"{r['name']}.png"
        with Image.open(path) as im:
            im.load()
            require(im.format=='PNG' and im.size==(1280,720) and max(ImageStat.Stat(im.convert('RGB')).stddev)>5, 'Invalid capture')
            # Exclude screen-edge UI; retain the actual world and player.
            pixels = np.asarray(im.convert('RGB').crop((160,100,1120,580)),dtype=np.float32)
            if r['name'].startswith('static'): stills.append(pixels)
            if r['name'].startswith('pan'): pans.append(pixels)
        captures.append({'name':r['name'], 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes':path.stat().st_size})
    static_delta = [float(np.mean(np.abs(a-b))) for a,b in zip(stills,stills[1:])]
    pan_delta = [float(np.mean(np.abs(a-b))) for a,b in zip(pans,pans[1:])]
    require(max(static_delta)<10, 'Large stationary temporal instability in world crop')
    require(statistics.median(pan_delta)>0.5, 'Motion captures are frozen')
    pan_yaw = [float(r['yaw']) for r in capture_rows if r['name'].startswith('pan')]
    require(pan_yaw[-1]-pan_yaw[0]>35 and all(b>=a for a,b in zip(pan_yaw,pan_yaw[1:])), 'Camera trajectory missing')
    return {'frames':len(rows), 'costs':costs, 'static_mean_abs_delta_255':static_delta,
            'pan_mean_abs_delta_255':pan_delta, 'captures':captures,
            'scope':'Development Vulkan at 1280x720, uncapped, existing DDC. Pixel deltas screen for gross instability; visual review still required. GPU timings are engine whole-frame measurements.'}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--aa',type=int,default=4);p.add_argument('--percentage',type=int,default=100)
    a=p.parse_args();print(json.dumps(verify(a.output,a.aa,a.percentage),indent=2))
