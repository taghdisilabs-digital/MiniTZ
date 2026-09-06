#!/usr/bin/env python3
"""Require authored building meshes and the actual platform-specific native proxies."""
import argparse
import csv
import json
from pathlib import Path


def verify(output, feature_level):
    output = Path(output)
    with (output / 'render-primitives.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    expected = {f'/Game/OpenWorld/Architecture/SM_StreetBlock_{i:02d}.SM_StreetBlock_{i:02d}'
                for i in range(6)}
    buildings = [row for row in rows if row['mesh'] in expected]
    # The surface fixture observes the loaded persistent world, including all six regions.
    assert {row['mesh'] for row in buildings} == expected, 'Missing authored building geometry'
    assert len({row['component'] for row in buildings}) == len(buildings), 'Duplicate components'
    assert all(row['nanite_data'] == '1' for row in buildings), 'Building lacks built Nanite data'
    if feature_level == 'sm6':
        # World Partition loads HLOD objects alongside the detailed cell actors.
        # A zero conflates absent and non-Nanite proxies in this native CSV.
        # Require a proven Nanite representation of EVERY mesh, plus every
        # detailed actor; do not demand a simultaneous proxy for duplicate HLODs.
        assert {row['mesh'] for row in buildings if row['nanite_proxy'] == '1'} == expected, 'Missing per-building Nanite proxy'
        assert all(row['nanite_proxy'] == '1' for row in buildings
                   if '.HLODInstancedStaticMeshComponent_' not in row['component']), 'Detailed building lacks Nanite proxy'
    else:
        assert all(row['nanite_proxy'] == '0' for row in buildings), 'SM5 unexpectedly has Nanite proxy'
    return dict(result='PASS', feature_level=feature_level, buildings=buildings,
                nanite_proxies=sum(row['nanite_proxy'] == '1' for row in buildings),
                zero_proxy_rows=sum(row['nanite_proxy'] == '0' for row in buildings),
                scope='Loaded mesh data and native proxies; visible appearance requires captured runtime review')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--feature-level', choices=('sm5', 'sm6'), required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output, args.feature_level), indent=2))
