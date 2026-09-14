#!/usr/bin/env python3
"""Replay native environment evidence independently of in-engine assertions."""
import csv,json,math,statistics
from pathlib import Path
from PIL import Image,ImageStat

def require(value,message):
    if not value: raise AssertionError(message)

def verify(out):
    out=Path(out)
    result=json.loads((out/'result.json').read_text())
    require(result['success'] and result['rhi']=='Vulkan' and not result['fixed_timestep'] and not result['benchmark'],'Native variable-step Vulkan result required')
    with (out/'frames.csv').open() as stream:
        rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(stream)]
    require(len(rows)>250 and all(math.isfinite(v) for r in rows for v in r.values()),'Insufficient or nonfinite frames')
    groups={p:[r for r in rows if r['phase']==p] for p in range(1,29)}
    require(all(v for k,v in groups.items() if k!=20),'Missing lifecycle phases')
    require({0,34,68}<={r['panel_health'] for r in rows},'Missing intact/damaged/destroyed states')
    require(any(r['physics']==1 and r['panel_health']==0 for r in groups[8]),'No real debris simulation')
    require(all(r['dormant']==1 and r['physics']==0 and r['panel_health']==0 for r in groups[18]),'Dormant state not held')
    require(max(r['debris_z'] for r in groups[18])-min(r['debris_z'] for r in groups[18])<0.01,'Debris falls while unloaded')
    require(groups[10][-1]['player_x']>6580,'Movement did not traverse opened panel')
    hazard=groups[12]
    drops={key:hazard[0][key]-hazard[-1][key] for key in ('health','rival_health','infected_health')}
    require(min(drops.values())>14 and max(drops.values())-min(drops.values())<3.5,'Shared hazard is inconsistent')
    duration=sum(r['sim_ms'] for r in hazard[1:])/1000
    require(abs(drops['health']-12*duration)<3.5,'Hazard damage depends on frame cap')
    require(all(r['power']==0 for r in groups[16]) and len({r['health'] for r in groups[16]})==1,'Safe floor still hurts player')
    require(groups[19][-1]['revision']==groups[23][-1]['revision'] and groups[19][-1]['power']==1,'Streaming loses state revision')
    require(groups[25][0]['health']-groups[25][-1]['health']>5,'Hazard did not resume after return')
    log=(out/'runtime.stdout.log').read_text(errors='replace')
    events=(out/'events.log').read_text()
    for e in ('terrain_unloaded','restart_clean','shared_hazard','safe_floor','stream_return'):
        require(f'event={e}' in events,f'Missing {e}')
    require(sum('LogTemp: Display: D02_ENV SHOT owner=' in line for line in log.splitlines())==2,'Expected exactly two real weapon input events')
    captures=[]
    for name in ('switch_safe','panel_damaged','panel_destroyed','hazard_active','stream_return'):
        p=out/'captures'/f'{name}.png'
        with Image.open(p) as im:
            im.load(); require(im.format=='PNG' and im.size==(1280,720) and max(ImageStat.Stat(im.convert('RGB')).stddev)>5,'Invalid capture')
        captures.append(str(p))
    return dict(frames=len(rows),hazard_drops=drops,hazard_seconds=duration,median_frame_ms=statistics.median(r['wall_ms'] for r in rows),captures=captures,
                scope='Development Linux Vulkan causal evidence; no shipping or frame-rate qualification')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    print(json.dumps(verify(p.parse_args().output),indent=2))
