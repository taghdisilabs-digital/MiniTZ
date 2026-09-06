#!/usr/bin/env python3
"""Preserve the exact installed Epic death clip closure and its provenance."""
from pathlib import Path
import hashlib
import json
import re
import shutil

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = Path('/opt/unreal/UE_5.8.2/Templates/TemplateResources/High/Characters/Content/Mannequins')
ROOTS = ['Anims/Death/MM_Death_Front_01']


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--physics', action='store_true')
    args = parser.parse_args()
    roots = ['Rigs/PA_Mannequin'] if args.physics else ROOTS
    pending, seen = roots[:], set()
    while pending:
        relative = pending.pop()
        if relative in seen:
            continue
        data = (SOURCE / (relative + '.uasset')).read_bytes()
        seen.add(relative)
        pending.extend(m.decode() for m in re.findall(rb'/Game/Characters/Mannequins/([A-Za-z0-9_/-]+)', data))
    records = []
    for relative in sorted(seen):
        src = SOURCE / (relative + '.uasset')
        dst = PROJECT / 'Content/Characters/Mannequins' / (relative + '.uasset')
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
                  status='INTEGRATION_RESOURCE_NOT_FINAL_CHARACTER_ART', roots=roots, files=records)
    path = PROJECT / 'SourceAssets/Characters' / ('UE58DefeatPhysics.provenance.json' if args.physics else 'UE58Defeat.provenance.json')
    data = json.dumps(report, indent=2) + '\n'
    if path.exists():
        assert path.read_text() == data, 'Preserve prior provenance'
    else:
        path.write_text(data)
        path.chmod(0o644)
    print(json.dumps(dict(copied_or_verified=len(records), provenance=str(path))))


if __name__ == '__main__':
    main()
