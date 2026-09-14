"""Reject corrupted copies of the native D02-04 baseline; retain originals."""
import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image
from verify_d02_04 import verify


BASELINE = Path(__file__).resolve().parents[1] / 'Build/Environment/D02-04-acceptance-30'


class EnvironmentEvidenceTests(unittest.TestCase):
    def test_native_baseline(self):
        self.assertGreater(verify(BASELINE)['frames'], 250)

    def test_corrupt_evidence_rejected(self):
        controls = (
            'missing_frames', 'nonfinite_frame', 'fixed_timestep', 'missing_damage_stage',
            'no_debris_physics', 'dormant_fall', 'no_traversal', 'unequal_hazard',
            'safe_floor_damage', 'lost_revision', 'no_resumed_damage',
            'missing_restart', 'missing_weapon_input', 'blank_capture',
        )
        for control in controls:
            with self.subTest(control=control), tempfile.TemporaryDirectory(prefix='d02-04-negative-') as temp:
                out = Path(temp)
                for name in ('frames.csv', 'events.log', 'result.json', 'runtime.stdout.log'):
                    shutil.copy2(BASELINE / name, out / name)
                shutil.copytree(BASELINE / 'captures', out / 'captures')
                self.corrupt(out, control)
                with self.assertRaises(AssertionError):
                    verify(out)

    @staticmethod
    def corrupt(out, control):
        if control == 'fixed_timestep':
            p = out / 'result.json'
            result = json.loads(p.read_text())
            result['fixed_timestep'] = True
            p.write_text(json.dumps(result))
            return
        if control in ('missing_restart', 'missing_weapon_input'):
            p = out / ('events.log' if control == 'missing_restart' else 'runtime.stdout.log')
            token = 'event=restart_clean' if control == 'missing_restart' else 'D02_ENV SHOT owner='
            p.write_text(p.read_text().replace(token, 'removed'))
            return
        if control == 'blank_capture':
            Image.new('RGB', (1280, 720)).save(out / 'captures/panel_destroyed.png')
            return
        p = out / 'frames.csv'
        with p.open() as stream:
            rows = list(csv.DictReader(stream))
        if control == 'missing_frames':
            rows = rows[:200]
        for i, row in enumerate(rows):
            phase = int(row['phase'])
            if control == 'nonfinite_frame' and i == 100:
                row['sim_ms'] = 'nan'
            elif control == 'missing_damage_stage' and row['panel_health'] == '34.000':
                row['panel_health'] = '68.000'
            elif control == 'no_debris_physics' and phase == 8:
                row['physics'] = '0'
            elif control == 'dormant_fall' and phase == 18:
                row['debris_z'] = str(-i)
            elif control == 'no_traversal' and phase == 10:
                row['player_x'] = '6300'
            elif control == 'unequal_hazard' and phase == 12:
                row['rival_health'] = '100'
            elif control == 'safe_floor_damage' and phase == 16:
                row['health'] = str(100 - i / 10)
            elif control == 'lost_revision' and phase == 19:
                row['revision'] = '-1'
            elif control == 'no_resumed_damage' and phase == 25:
                row['health'] = '100'
        with p.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


if __name__ == '__main__':
    unittest.main()
