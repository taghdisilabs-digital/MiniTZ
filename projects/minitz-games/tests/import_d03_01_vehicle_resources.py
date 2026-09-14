#!/usr/bin/env python3
"""Preserve the exact installed Epic vehicle rig closure and its provenance."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = Path('/opt/unreal/UE_5.8.2/Templates/TemplateResources/Standard/Vehicles/Content')
ROOTS = ['OffroadCar/SKM_Offroad']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rigid-parts', action='store_true')
    args = parser.parse_args()
    roots = ['OffroadCar/SM_Offroad_Body', 'OffroadCar/SM_Offroad_Tire'] if args.rigid_parts else ROOTS
    pending, seen = roots[:], set()
    while pending:
        relative = pending.pop()
        if relative in seen:
            continue
        data = (SOURCE / (relative + '.uasset')).read_bytes()
        seen.add(relative)
        pending.extend(m.decode() for m in re.findall(rb'/Game/Vehicles/([A-Za-z0-9_/-]+)', data))
    records = []
    for relative in sorted(seen):
        src = SOURCE / (relative + '.uasset')
        dst = PROJECT / 'Content/Vehicles' / (relative + '.uasset')
        if dst.exists():
            assert src.read_bytes() == dst.read_bytes(), f'Preserve changed Project asset: {dst}'
        else:
            missing = []
            parent = dst.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            dst.parent.mkdir(parents=True, exist_ok=True)
            for parent in missing:
                parent.chmod(0o755)
            shutil.copyfile(src, dst)
            dst.chmod(0o644)
        records.append(dict(source=str(src), local=str(dst.relative_to(PROJECT)),
                            bytes=dst.stat().st_size, sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
    report = dict(task_id='D03-01', provider='Installed Epic Unreal Engine 5.8.2 TemplateResources',
                  status='INTEGRATION_RESOURCE_NOT_FINAL_VEHICLE_ART', roots=roots, files=records)
    path = PROJECT / 'SourceAssets/Vehicles' / ('UE58OffroadParts.provenance.json' if args.rigid_parts else 'UE58Offroad.provenance.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o755)
    data = json.dumps(report, indent=2) + '\n'
    if path.exists():
        assert path.read_text() == data, 'Preserve prior provenance'
    else:
        path.write_text(data)
        path.chmod(0o644)
    print(json.dumps(dict(copied_or_verified=len(records), provenance=str(path))))


if __name__ == '__main__':
    main()
