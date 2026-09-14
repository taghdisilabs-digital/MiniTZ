#!/usr/bin/env python3
"""Independently replay input, physical motion, impacts and lifecycle evidence."""
import csv
import json
import math
from pathlib import Path
import re
import wave
import numpy as np
from PIL import Image, ImageStat
from verify_d02_01 import identity, require
from verify_d02_02 import metrics

FIELDS = 'frame,wall_seconds,wall_ms,sim_ms,phase,x,y,z,yaw,roll,pitch,speed,velocity,contacts,travel,spin,throttle,steering,brake,held,dormant,health,impacts,driver,player_health,ammo,audio,resident_bytes'.split(',')
EVENTS = ('approach','approach_capture','enter_key','accelerate','steer_right','steer_left','streamed_traversal','support_removed','support_hold','support_restored','brake','reverse','reverse_brake','collision_approach','collision_response','exit_key','walking_resumed','depart','parked','return','reenter','npc_contact_approach','npc_contact_confirmed','disabled','driver_defeated','restart_wait','restart_key','restart_clean')




def verify_npc_contact(phases, log):
    # The second NPC impact can transition phase 21 -> 18 in the same game tick.
    # Frame sampling happens after the phase change, so phase 21 may legitimately
    # end at impact count 2 while the first phase-18 sample carries count 3.
    require(phases.get(18) and phases[18][0]['impacts'] >= 3, 'Infected and rival contact missing')
    require('D02_VEHICLE_TEST event=npc_contact_confirmed' in log, 'NPC contact completion event missing')
    for team in ('1','2'):
        require(re.search(r'D01_SIGNAL DAMAGE target=\S+ amount=[\d.]+ health=0.0 tag=vehicle_impact source=\S+ source_team=0 target_team='+team,log),
                'Physical NPC damage missing for team '+team)

def verify(output):
    output = Path(output)
    result = json.loads((output/'result.json').read_text())
    require(result.get('success') is True and not result.get('error'), 'Runtime scenario failed')
    require(result.get('rhi') == 'Vulkan' and result.get('fixed_timestep') is False and result.get('benchmark') is False, 'Runtime renderer/time invalid')
    event_lines = (output/'events.log').read_text().splitlines()
    events = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in event_lines]
    require([e.get('event') for e in events] == list(EVENTS), 'Missing, duplicate or reordered lifecycle event')
    require(all(float(b['time']) >= float(a['time']) for a,b in zip(events,events[1:])), 'Event clock regressed')
    with (output/'frames.csv').open(newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == FIELDS, 'Unexpected frame schema')
        rows = []
        for raw in reader:
            require(None not in raw and None not in raw.values(), 'Malformed frame row')
            r = {k: float(v) for k,v in raw.items()}
            require(all(math.isfinite(v) for v in r.values()), 'Nonfinite frame value')
            require(r['wall_ms'] > 0 and r['sim_ms'] > 0 and r['resident_bytes'] > 0, 'Invalid measured time or memory')
            require(0 <= r['health'] <= 100 and 0 <= r['contacts'] <= 4 and 0 <= r['travel'] <= 60, 'Impossible vehicle state')
            require(r['z'] > 20 and abs(r['roll']) < 30 and abs(r['pitch']) < 30, 'Unsupported or unstable chassis')
            require(all(r[k] in (0,1) for k in ('brake','held','dormant','driver','audio')), 'Invalid state bits')
            if rows:
                prev = rows[-1]
                require(r['frame'] == prev['frame']+1, 'Missing engine frame')
                require(abs((r['wall_seconds']-prev['wall_seconds'])*1000-r['wall_ms']) < .01, 'Wall interval mismatch')
                require(r['impacts'] >= prev['impacts'] and r['health'] <= prev['health'], 'Vehicle state reset before restart')
                distance = math.dist([r[k] for k in ('x','y','z')],[prev[k] for k in ('x','y','z')])
                require(distance <= max(r['velocity'],prev['velocity'])*r['sim_ms']/1000+35, 'Vehicle transform jumped beyond physical velocity')
            rows.append(r)
    require(len(rows) > 300, 'Insufficient engine frames')
    phases = {p:[r for r in rows if r['phase']==p] for p in range(1,23)}
    require(all(phases.values()), 'Missing physical lifecycle phase')
    drive = sum([phases[p] for p in (3,4,5,6)],[])
    require(max(r['x'] for r in drive)-min(r['x'] for r in drive) >= 6400, 'Insufficient streamed physical traversal')
    require(max(r['speed'] for r in drive) > 1200 and all(r['driver']==1 for r in drive), 'Missing driver acceleration')
    require(sum(r['contacts']==4 for r in drive if not r['held'])/sum(not r['held'] for r in drive) > .9, 'Lost suspension contact during normal driving')
    require(max(r['yaw'] for r in phases[4])-min(r['yaw'] for r in phases[4]) > .5, 'Right steering did not turn chassis')
    require(min(r['steering'] for r in phases[5]) == -1 and max(r['steering'] for r in phases[4]) == 1, 'Steering input missing')
    require(abs(phases[7][-1]['speed']) < 30 and phases[7][-1]['brake']==1, 'Forward brake failed')
    require(min(r['speed'] for r in phases[8]) < -250 and abs(phases[9][-1]['speed']) < 30, 'Reverse or reverse brake failed')
    require(any(r['held']==1 and r['velocity']==0 for r in phases[6]) and phases[6][-1]['held']==0, 'Missing terrain did not hold and resume')
    require(phases[18][0]['impacts'] >= 3, 'Infected and rival contact missing')
    require(phases[11][-1]['impacts'] >= 1 and 0 < phases[11][-1]['health'] < 100, 'Collision damage missing')
    require(phases[13][-1]['driver']==0 and phases[13][-1]['audio']==0, 'Exit state not restored')
    require(all(r['player_health']==73 and r['ammo']==60 for r in rows if 3 <= r['phase'] <= 17), 'Player state changed during driving/streaming')
    parked = phases[15]
    require(all(r['dormant']==r['held']==1 for r in parked), 'Parked simulation stayed active')
    require(all(all(abs(r[k]-parked[0][k]) <= .01 for k in ('x','y','z','health')) for r in parked), 'Dormancy changed saved state')
    require(phases[17][-1]['health']==parked[-1]['health'] and phases[17][-1]['driver']==1, 'Damaged identity failed to resume')
    require(phases[18][-1]['health']==0 and phases[18][-1]['brake']==1 and abs(phases[18][-1]['speed'])<30, 'Disabled car still drives')
    require(all(r['throttle']==0 and r['audio']==0 for r in phases[20]), 'Defeat left driving or audio active')
    log = (output/'runtime.stdout.log').read_text(errors='replace')
    verify_npc_contact(phases, log)
    for line in event_lines:
        require(line in log, 'Event not present in runtime log')
    for key in ('E','W','D','A','SpaceBar','S','R'):
        require(f'D02_VEHICLE_KEY key={key} down=1' in log, 'Real input event missing: '+key)
    impacts = re.findall(r'D02_VEHICLE IMPACT other=(\S+) impulse=([\d.]+) delta_v=([\d.]+) health=([\d.]+)',log)
    require(any(float(i[1])>100000 and 0<float(i[3])<100 for i in impacts), 'No real Chaos collision impulse')
    require('reason=entry_obstructed' in log and 'reason=exit_obstructed' in log and 'reason=exit_speed_or_roll' in log, 'Safety rejection evidence missing')
    files = [identity(output/name) for name in ('result.json','frames.csv','events.log','runtime.stdout.log','runtime.engine.log')]
    for name in ('approach','driving','impact','exited','disabled'):
        path = output/'captures'/f'{name}.png'
        with Image.open(path) as im:
            im.load()
            require(im.format=='PNG' and im.size==(1280,720) and max(ImageStat.Stat(im.convert('RGB')).stddev)>5, 'Invalid runtime capture')
        files.append(identity(path))
    with wave.open(str(output/'vehicle.wav')) as wav:
        rate, channels, width, frames = wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()
        require(rate >= 44100 and channels >= 1 and width == 2 and frames/rate > 10, 'Invalid mixed vehicle audio')
        samples = np.frombuffer(wav.readframes(frames),dtype='<i2').astype(float)/32768
        rms = float(np.sqrt(np.mean(samples*samples)))
        require(rms > .001 and np.max(np.abs(samples)) < 1, 'Silent or clipped vehicle audio')
    files.append(identity(output/'vehicle.wav'))
    return dict(result='PASS',all_frames=metrics(rows),driving=metrics(drive),distance_cm=drive[-1]['x']-drive[0]['x'],
                max_speed_kmh=max(r['speed'] for r in drive)*.036,collision_health=phases[11][-1]['health'],
                audio=dict(seconds=frames/rate,rate=rate,channels=channels,rms=rms),files=files)
