#!/usr/bin/env python3
"""Verify observed Vulkan feature support, independently of requested CVars."""
import argparse
import csv
import json
from pathlib import Path

from verify_d03_01_reconstruction import read_rows, verify as verify_views


def verify(out, feature_level, profile):
    out = Path(out)
    assert feature_level in ('sm5', 'sm6'), 'Unknown feature level'
    reconstruction = verify_views(out, profile)
    frames = {row['frame'] for row in read_rows(out/'frames.csv')}
    views = [row for row in read_rows(out/'native-views.csv')
             if row['frame'] in frames and row['view'] == 0]
    sm6 = int(feature_level == 'sm6')
    expected = dict(feature_sm6=sm6, nanite_supported=sm6, nanite_enabled=sm6,
                    vsm_enabled=sm6, lumen_supported=1)
    for key, value in expected.items():
        assert all(key in row for row in views), f'Missing runtime capability observation: {key}'
        assert all(row[key] == value for row in views), f'Runtime capability mismatch: {key}={value}'
    log = (out/'runtime.stdout.log').read_text(errors='replace')
    assert f'shader_platform=SF_VULKAN_{feature_level.upper()}' in log, 'Native shader platform diagnostic missing'
    result = dict(result='PASS', feature_level=feature_level, expected=expected,
                  reconstruction=reconstruction,
                  scope='Native game-view feature level and renderer eligibility; primitive proxy counts do not establish visible-pixel coverage')
    primitives_path = out/'render-primitives.csv'
    if primitives_path.exists():
        with primitives_path.open() as stream:
            primitives = list(csv.DictReader(stream))
        assert primitives, 'Missing loaded static mesh observations'
        assert len({row['component'] for row in primitives}) == len(primitives), 'Duplicate primitive observations'
        for row in primitives:
            assert row['nanite_data'] in ('0', '1') and row['nanite_proxy'] in ('0', '1'), 'Invalid primitive observation'
            if row['nanite_proxy'] == '1':
                assert row['nanite_data'] == '1' and sm6, 'Nanite proxy lacks supported platform or mesh data'
        result['primitives'] = dict(loaded_components=len(primitives),
                                    nanite_data=sum(int(row['nanite_data']) for row in primitives),
                                    nanite_proxies=sum(int(row['nanite_proxy']) for row in primitives),
                                    mesh_assets=sorted({row['mesh'] for row in primitives}))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--feature-level', choices=('sm5', 'sm6'), required=True)
    parser.add_argument('--profile', choices=('ProductionTSR', 'NativeTAA'), required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output, args.feature_level, args.profile), indent=2))
