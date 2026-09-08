#!/usr/bin/env python3
"""Replay raw population events, gameplay damage and engine frame measurements."""
import csv
import json
import math
from pathlib import Path
import re
from PIL import Image, ImageStat
from verify_d02_01 import identity, require

FIELDS = 'frame,wall_seconds,wall_ms,sim_ms,phase,active,spawned,rivals,infected,health_sum,paths,blocked,overlap_pairs,resident_bytes'.split(',')
EVENTS = ('relocate', 'placement_rejections_pass', 'admission', 'frame_pressure',
          'frame_guard_pass', 'combat', 'combat_observed', 'depart', 'suspended',
          'return', 'continuity_tombstones_pass', 'resumed', 'navigation_obstruction',
          'dynamic_obstacle_added', 'dynamic_obstacle_removed', 'path_replanned_and_arrived', 'capture_wait')


def metrics(rows):
    values = sorted(r['wall_ms'] for r in rows)
    return dict(frames=len(rows), wall_seconds=sum(values)/1000,
                p50_ms=values[math.floor((len(values)-1)*.5)],
                p95_ms=values[math.floor((len(values)-1)*.95)],
                p99_ms=values[math.floor((len(values)-1)*.99)], max_ms=values[-1],
                peak_resident_bytes=max(r['resident_bytes'] for r in rows))


def verify(output, count, renderer='vulkan'):
    output = Path(output)
    result = json.loads((output/'result.json').read_text())
    require(result.get('success') is True and not result.get('error'), 'Runtime scenario failed')
    require(result.get('count') == count and count in (4, 8, 12), 'Wrong candidate count')
    require(result.get('initial_rivals') == count//4 and result.get('initial_infected') == count*3//4,
            'Wrong encounter composition')
    require(result.get('fixed_timestep') is False and result.get('benchmark') is False, 'Synthetic runtime time')
    require(result.get('rhi') == ('Vulkan' if renderer == 'vulkan' else 'Null'), 'Wrong runtime renderer')
    events = []
    for line in (output/'events.log').read_text().splitlines():
        require(line.startswith('D02_POP_TEST event='), 'Malformed event')
        events.append(dict(re.findall(r'(\w+)=([^\s]+)', line)))
    require([e['event'] for e in events] == list(EVENTS), 'Missing, duplicate or reordered lifecycle event')
    for previous, event in zip(events, events[1:]):
        require(float(event['time']) >= float(previous['time']), 'Event clock regressed')
    by_event = {e['event']: e for e in events}
    combat_duration = float(by_event['combat_observed']['time'])-float(by_event['combat']['time'])
    require(20 <= combat_duration < 22, 'Combat window incomplete')
    guard = by_event['frame_guard_pass']
    require(int(guard['active']) == int(guard['spawned']) == count and float(guard['measured_ms']) > 1,
            'Frame guard removed actors or admitted extra actors')
    combat = by_event['combat_observed']
    require(int(combat['moved']) >= 2 and int(combat['damaged']) >= 2 and int(combat['paths']) >= 2,
            'Missing autonomous movement, damage or Recast use')
    suspended, resumed = by_event['suspended'], by_event['resumed']
    require(all(suspended[k] == resumed[k] for k in ('id', 'health', 'x', 'y', 'z')),
            'Suspension changed identity, health or transform')
    require(float(suspended['health']) > 0 and int(resumed['active']) == 1 and int(resumed['spawned']) == count,
            'Resume duplicated or resurrected defeated population')
    nav = by_event['path_replanned_and_arrived']
    require(int(nav['final']) > int(nav['first']) >= 1 and float(nav['distance']) <= 180,
            'Navigation did not replan and arrive')

    with (output/'frames.csv').open(newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == FIELDS, 'Unexpected frame schema')
        rows = []
        for raw in reader:
            require(None not in raw and None not in raw.values(), 'Malformed frame row')
            row = {k: float(v) for k, v in raw.items()}
            require(all(math.isfinite(v) for v in row.values()), 'Nonfinite frame value')
            require(row['wall_ms'] > 0 and row['sim_ms'] > 0 and row['resident_bytes'] > 0, 'Invalid measured time or memory')
            require(0 <= row['active'] == row['rivals']+row['infected'] <= row['spawned'] <= count, 'Invalid population counts')
            require(0 <= row['health_sum'] <= (count//4*100+count*3//4*70), 'Impossible population health')
            require(row['overlap_pairs'] == 0, 'Interpenetrating population capsules')
            require(all(row[k].is_integer() for k in ('frame','phase','active','spawned','rivals','infected','paths','blocked','resident_bytes')), 'Noninteger frame counters')
            if rows:
                prior = rows[-1]
                require(row['frame'] == prior['frame']+1, 'Missing engine frame')
                require(abs((row['wall_seconds']-prior['wall_seconds'])*1000-row['wall_ms']) < .01, 'Wall interval mismatch')
                require(row['phase'] >= prior['phase'] and row['spawned'] >= prior['spawned'], 'Lifecycle or identity count regressed')
                require(row['spawned']-prior['spawned'] <= 2, 'Admission burst exceeded budget')
                require(row['paths'] >= prior['paths'] and row['blocked'] >= prior['blocked'], 'Path state lost')
                if prior['phase'] >= 3:
                    require(row['health_sum'] <= prior['health_sum'], 'Population healed or duplicated')
            rows.append(row)
    require(len(rows) > 200 and set(r['phase'] for r in rows) == set(range(1,9)), 'Incomplete frame phases')
    pressure = [r for r in rows if r['phase'] == 3]
    require(len(pressure) > 20 and all(r['active'] == r['spawned'] == count for r in pressure), 'Frame pressure changed live population')
    live = [r for r in rows if r['phase'] == 4]
    require(len(live) > 100 and live[-1]['wall_seconds']-live[0]['wall_seconds'] >= 19, 'Insufficient live combat frames')
    require(live[0]['active'] == count and live[-1]['health_sum'] < live[0]['health_sum'] and live[-1]['paths'] >= 2, 'Combat did not execute')
    require(any(r['phase'] == 5 and r['active'] == 0 for r in rows), 'No sampled suspension')
    dense = [r for r in live if r['active'] >= count*.75]
    require(len(dense) > 20, 'Insufficient concurrent actor samples')

    log = (output/'runtime.stdout.log').read_text(errors='replace')
    require('**** TEST COMPLETE. EXIT CODE: 0 ****' in log and re.search(r'Result=\{Success\}.*Name=\{Population\}',log), 'Unreal did not report success')
    require(not re.search(r'Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:|\bError:',log), 'Unreal error')
    if renderer == 'vulkan':
        require('LogVulkanRHI:' in log and 'swapchain' in log.lower(), 'No real Vulkan swapchain')
    scenario = log[log.index('D02_POP_TEST event=relocate '):]
    for line in (output/'events.log').read_text().splitlines():
        require(line in scenario, 'Event not present in runtime log')
    spawns = re.findall(r'D02_POP SPAWN id=(\S+) actor=(\S+) x=([\d.-]+) y=([\d.-]+) z=([\d.-]+) active=(\d+) frame_ms=([\d.]+)', scenario)
    require(len(spawns) == count and len({s[0] for s in spawns}) == count, 'Duplicate or missing stable spawn')
    expected_ids = {f'D02Pop_Street03_{i:02d}' for i in range(count)}
    require({s[0] for s in spawns} == expected_ids and all(s[0] == s[1] for s in spawns), 'Unexpected region or renamed identity')
    for s in spawns:
        require(11000 < float(s[2]) < 13000 and -600 <= float(s[3]) <= 600 and 88 <= float(s[4]) <= 100,
                'Spawn outside authored supported region')
        require(1 <= int(s[5]) <= count and 0 < float(s[6]) < 25, 'Admission ignored measured guard')
    live_log = scenario.split('D02_POP_TEST event=combat ',1)[1].split('D02_POP_TEST event=combat_observed ',1)[0]
    damages = re.findall(r'D01_SIGNAL DAMAGE target=(\S+) amount=([\d.]+) health=([\d.]+) tag=(\S+) source=(\S+) source_team=(\d+) target_team=(\d+)',live_log)
    natural = [d for d in damages if d[0] in expected_ids and d[4] in expected_ids and float(d[1]) > 0]
    require({(d[5],d[6]) for d in natural} >= {('1','2'),('2','1')}, 'No bidirectional autonomous rival/infected damage')
    require(len({d[0] for d in natural}) >= 2 and len({d[4] for d in natural}) >= 2, 'Combat collapsed to one actor')
    require(all(d[3] in ('infected_melee','rival_fire') for d in natural), 'Fixture damage in measured combat')
    # Explain accepts FName: packaged name-pool spelling may be "Finished".
    # Match the complete reason token, preserving the lifecycle requirement.
    require(re.search(r'\breason=finished\b', scenario, re.IGNORECASE) and ('reason=support_missing' in scenario or 'reason=distance_suspended' in scenario), 'No explained finish and suspension')
    require('reason=active_obstructed' in scenario, 'No observed live obstruction retention')
    require('reason=occupied' not in live_log, 'Crowd overlap concealed through dormancy')
    obstacle = scenario.split('D02_POP_TEST event=dynamic_obstacle_added ',1)[1].split('D02_POP_TEST event=dynamic_obstacle_removed ',1)[0]
    require(re.search(r'D02_POP PATH actor=BiellaPopulationInfected_\d+ revision=[2-9]\d*',obstacle), 'No replan while obstruction existed')

    files = [identity(output/name) for name in ('result.json','frames.csv','events.log','runtime.stdout.log','runtime.engine.log')]
    if renderer == 'vulkan':
        for name in ('dense_start','combat_result','navigation_result'):
            path = output/'captures'/f'{name}.png'
            with Image.open(path) as im:
                im.load()
                require(im.format == 'PNG' and im.size == (1280,720), 'Invalid runtime capture')
                require(max(ImageStat.Stat(im.convert('RGB')).stddev) > 5, 'Blank capture')
            files.append(identity(path))
    return dict(result='PASS', count=count, initial_rivals=count//4, initial_infected=count*3//4,
                combat_duration_seconds=combat_duration, all_frames=metrics(rows), combat_frames=metrics(live),
                at_least_75_percent_active=metrics(dense), active_end=int(live[-1]['active']),
                max_overlap_pairs=max(r['overlap_pairs'] for r in rows), natural_damage_events=len(natural),
                natural_damage_sources=sorted({d[4] for d in natural}), natural_damage_targets=sorted({d[0] for d in natural}),
                files=files, capture_status='GENERATED_DRAFT')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--count',type=int,required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output,args.count),indent=2))
