#!/usr/bin/env python3
"""Reject corrupted traversal proof using the retained full-route native run.

Only ffmpeg decoding is stubbed here: that exact video's full decode already
has its own runtime receipt. Source snapshots and file identities remain real.
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import measure_d17_02_route as subject

CAPTURE = Path(__file__).resolve().parents[1] / 'Build/AAA/D17-02/raw/framing-720-05'


class TraversalProofRejection(unittest.TestCase):
    def measure(self, mutate=None):
        native = subject.rows(CAPTURE / 'telemetry.jsonl')
        inputs = subject.rows(CAPTURE / 'input.jsonl')
        if mutate:
            mutate(native, inputs)
        def rows(path):
            return native if path.name == 'telemetry.jsonl' else inputs
        with patch.object(subject, 'rows', side_effect=rows), patch.object(
                subject.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stderr='')):
            return subject.measure(CAPTURE)

    def test_intact_captured_route(self):
        self.assertEqual(self.measure()['faults'], [])

    def test_forged_waypoint_observation(self):
        def mutate(native, inputs):
            event = next(r for r in inputs if r['event'] == 'route_stage_reached')
            event['observed']['x'] = '99999'
        self.assertTrue(any('match a live native frame' in f for f in self.measure(mutate)['faults']))

    def test_missing_return_stage(self):
        def mutate(native, inputs):
            last = [r for r in inputs if r['event'] == 'route_stage_reached'][-1]
            inputs.remove(last)
        self.assertFalse(self.measure(mutate)['route_complete'])

    def test_native_sequence_gap(self):
        self.assertIn('Native telemetry sequence gap', self.measure(lambda n, i: n.pop(100))['faults'])

    def test_geometry_overlap_is_rejected(self):
        def mutate(native, inputs):
            frame = next(r for r in native if r['event'] == 'traversal_frame'
                         and r['fields']['phase'] == 'Active' and r['fields']['ready'] == 'true')
            frame['fields']['near_hits'] = '1'
        self.assertIn('Native camera/collision issue: near_plane_geometry_hits', self.measure(mutate)['faults'])

    def test_wrong_terrace_height_even_with_matching_native_frame(self):
        def mutate(native, inputs):
            event = next(r for r in inputs if r['event'] == 'route_stage_reached'
                         and r['intended'].get('at') == [10000, 3400])
            event['observed']['z'] = '90.0000'
            frame = next(r for r in native if r['event'] == 'traversal_frame'
                         and r['fields']['frame'] == event['observed']['frame'])
            frame['fields'] = copy.deepcopy(event['observed'])
        self.assertTrue(any('route plane height mismatch' in f for f in self.measure(mutate)['faults']))

    def test_nonproduction_camera_is_rejected(self):
        def mutate(native, inputs):
            for r in native:
                if r['event'] == 'traversal_frame':
                    r['fields']['arm'] = '900.0000'
        self.assertIn('Production camera arm or FOV changed', self.measure(mutate)['faults'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
