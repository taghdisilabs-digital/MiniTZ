"""Read native observations and deliver only X11 inputs. Never write game state.

This is instrument-assisted automation, not external-player/usability evidence.
Waypoint intent is logged separately from actual positions and camera measures.
"""
import json
import math
import subprocess
import time


def angle(value):
    return (value + 180) % 360 - 180


class RouteInput:
    def __init__(self, plan, telemetry, event):
        self.plan, self.path, self.event = plan, telemetry, event
        self.offset, self.pending, self.index = 0, '', 0
        self.frame, self.actors, self.dead = None, {}, set()
        self.keys = set()
        self.stage_start = time.monotonic()
        self.announced = False
        self.last_shot = -1.0
        self.actions_sent = 0
        self.remaining_infected = None

    def send(self, *args):
        subprocess.run(['xdotool', *map(str, args)], check=True)
        self.actions_sent += 1
        self.event('input_sent', input=list(args), stage=self.index,
                   intended_beat=self.plan['stages'][self.index]['beat'])

    def key(self, key, down):
        if (key in self.keys) != down:
            self.send('keydown' if down else 'keyup', key)
            (self.keys.add if down else self.keys.discard)(key)

    def trigger(self, down):
        if ('fire' in self.keys) != down:
            self.send('mousedown' if down else 'mouseup', '1')
            (self.keys.add if down else self.keys.discard)('fire')

    def release(self):
        for key in list(self.keys):
            self.trigger(False) if key == 'fire' else self.key(key, False)

    def look(self, yaw, pitch):
        f = self.frame
        dyaw = angle(yaw - float(f['camera_yaw']))
        dpitch = pitch - float(f['camera_pitch'])
        # DefaultInput mouse axes multiply the user setting by 0.07.
        dx = round(max(-500, min(500, dyaw / (.8 * .07))))
        dy = round(max(-350, min(350, -dpitch / (.6 * .07))))
        if dx or dy:
            self.send('mousemove_relative', '--', dx, dy)
        return abs(dyaw) < 1.7 and abs(dpitch) < 1.3

    def aim(self, at):
        f = self.frame
        x, y, z = (at[i] - float(f['camera_'+axis]) for i, axis in enumerate('xyz'))
        return self.look(math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y))))

    def shoot(self, aligned, now, preserve_route=True):
        # Traversal intent includes returning before finishing the encounter.
        # With the native nearest-enemy weapon selection, an unseen late click
        # can kill the final infected after a rival dies. Choose to withhold
        # that click using the same live objective state as the HUD. Damage,
        # objectives and AI remain untouched; environmental shots are explicit.
        if preserve_route and self.remaining_infected == 1:
            live = [a for a in self.actors.values() if a['id'] not in self.dead]
            distance = lambda a: sum((float(a[axis])-float(self.frame[axis]))**2 for axis in 'xyz')
            nearest = min(live, key=distance) if live else None
            if nearest and 'Infected' in nearest['class']:
                aligned = False
        # Fire is a Started action with a native 0.25 s cooldown.
        if 'fire' in self.keys:
            self.trigger(False)
        elif aligned and now-self.last_shot > .30:
            self.trigger(True)
            self.last_shot = now

    def tick(self):
        if not self.path.exists():
            return False
        with self.path.open() as stream:
            stream.seek(self.offset)
            content = self.pending + stream.read()
            self.offset = stream.tell()
        lines = content.split('\n')
        self.pending = lines.pop()
        for line in lines:
            row = json.loads(line)
            if row['event'] == 'traversal_frame':
                self.frame = row['fields']
            elif row['event'] == 'traversal_actor':
                self.actors[row['fields']['id']] = row['fields']
            elif row['event'] == 'defeat':
                self.dead.add(row['fields']['target'])
            elif row['event'] == 'objective_progress':
                self.remaining_infected = int(row['fields']['remaining'])
        if not self.frame or self.frame['phase'] != 'Active':
            return False
        s = self.plan['stages'][self.index]
        now = time.monotonic()
        if not self.announced:
            self.event('route_stage_started', stage=self.index, intended=s, observed=self.frame)
            self.announced, self.stage_start = True, now
            self.stage_ammo = int(self.frame['ammo'])
            self.patrol_index = 0
            self.rival_target = s.get('target')
            if self.rival_target == 'nearest_admitted':
                self.rival_target = None
        if now - self.stage_start > s.get('timeout', 45):
            self.release()
            raise RuntimeError('Route stage timed out: ' + s['beat'])
        done = False
        if s['kind'] == 'rival':
            if s.get('target') == 'nearest_admitted' and self.rival_target is None:
                distance_to = lambda a: math.hypot(float(a['x'])-float(self.frame['x']),
                                                  float(a['y'])-float(self.frame['y']))
                radius = s.get('admission_radius_cm', 4000)
                admitted = [a for a in self.actors.values() if a['class']=='BiellaRival'
                            and a['id'] not in self.dead and distance_to(a)<radius]
                if admitted:
                    self.rival_target = min(admitted,key=distance_to)['id']
                    self.event('route_rival_selected',stage=self.index,target=self.rival_target,
                               selection='closest live observed rival',radius_cm=radius)
            actors = [a for a in self.actors.values() if a['id'] == self.rival_target]
            done = (not actors and s.get('skip_if_not_admitted', False) and
                    now-self.stage_start >= s.get('admission_wait_seconds', 0))
            if not actors and not done and s.get('admission_patrol'):
                # Waiting for native population admission must remain live
                # play: move within the street instead of standing in melee.
                patrol = s['admission_patrol']
                at = patrol[self.patrol_index % len(patrol)]
                x, y = (at[i]-float(self.frame[axis]) for i, axis in enumerate('xy'))
                if math.hypot(x, y) < 70:
                    self.patrol_index += 1
                yaw = math.degrees(math.atan2(y, x))
                self.look(yaw, -18)
                self.key('w', abs(angle(yaw-float(self.frame['yaw']))) < 20)
                live = [a for a in self.actors.values() if a['id'] not in self.dead]
                nearest_distance = min((math.hypot(float(a['x'])-float(self.frame['x']),
                                                  float(a['y'])-float(self.frame['y']))
                                        for a in live), default=10000)
                self.shoot(nearest_distance < 400, now)
            if actors:
                a = actors[0]
                done = a['id'] in self.dead
                if not done:
                    x, y = float(a['x'])-float(self.frame['x']), float(a['y'])-float(self.frame['y'])
                    aligned = self.aim([float(a['x']), float(a['y']), float(a['z'])+25])
                    live = [v for v in self.actors.values() if v['id'] not in self.dead]
                    distance_to = lambda v: math.hypot(float(v['x'])-float(self.frame['x']),
                                                        float(v['y'])-float(self.frame['y']))
                    nearest = min(live, key=distance_to) if live else None
                    nearest_distance = distance_to(nearest) if nearest else 10000
                    if (self.remaining_infected == 1 and nearest and
                            'Infected' in nearest['class'] and s.get('skip_if_not_admitted')):
                        # Keep moving when the optional rival engagement would
                        # require finishing the encounter. Waiting beside that
                        # infected would turn this route into a melee death.
                        self.event('route_rival_deferred', stage=self.index,
                                   reason='final infected is native nearest shot target; continue traversal')
                        done = True
                    if not done:
                        # Backpedal within the observed street corridor; do not
                        # leave it to chase an enemy and trigger an off-route nav hold.
                        yaw_radians = math.radians(float(self.frame['yaw']))
                        retreat_y = float(self.frame['y']) - math.sin(yaw_radians)*180
                        can_retreat = abs(retreat_y) < 1100
                        self.key('s', nearest_distance < 320 and can_retreat)
                        self.key('w', nearest_distance >= 320 and math.hypot(x, y) > 550 and
                                 abs(angle(math.degrees(math.atan2(y,x))-float(self.frame['yaw']))) < 20)
                        self.shoot(math.hypot(x,y) < 650 or nearest_distance < 400, now)
        elif s['kind'] == 'walk':
            x, y = (s['at'][i] - float(self.frame[axis]) for i, axis in enumerate('xy'))
            distance = math.hypot(x, y)
            done = distance < s.get('radius', 70)
            if not done:
                yaw = math.degrees(math.atan2(y, x))
                self.look(yaw, s.get('pitch', -18))
                self.key('w', abs(angle(yaw-float(self.frame['yaw']))) < 20)
            if s.get('defend_against_nearest_rival') or s.get('clear_immediate_enemy'):
                live = [a for a in self.actors.values() if a['id'] not in self.dead]
                distance_to = lambda a: math.hypot(float(a['x'])-float(self.frame['x']),
                                                  float(a['y'])-float(self.frame['y']))
                nearest = min(live, key=distance_to) if live else None
                self.shoot(bool(nearest and (
                    (s.get('defend_against_nearest_rival') and nearest['class'] == 'BiellaRival'
                     and distance_to(nearest) < 1500) or
                    (s.get('clear_immediate_enemy') and distance_to(nearest) < 400))), now)
        elif s['kind'] == 'look':
            aligned = self.look(s['yaw'], s.get('pitch', -18))
            done = aligned and now-self.stage_start > s.get('seconds', 1.5)
        elif s['kind'] == 'fire':
            aligned = self.aim(s['at'])
            self.shoot(aligned, now, preserve_route=False)
            done = self.stage_ammo-int(self.frame['ammo']) >= s['shots']
        elif s['kind'] == 'interact':
            self.look(s['yaw'], -18)
            self.key('e', now-self.stage_start > .5)
            done = now-self.stage_start > 1
        else:
            raise ValueError('Unknown input stage: '+str(s))
        if done:
            self.release()
            self.event('route_stage_reached', stage=self.index, intended=s, observed=self.frame)
            self.index += 1
            self.announced = False
            return self.index == len(self.plan['stages'])
        return False
