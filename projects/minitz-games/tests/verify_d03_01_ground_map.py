#!/usr/bin/env python3
"""Audit the bounded ground map resave; never rewrite source assets or prior receipts."""
import argparse
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
from run_d01_039 import PROJECT, file_identity, write_json


def normalized_export(path, map_name):
    lines = path.read_text().replace(map_name, 'GroundMap').splitlines()
    retained, persistent = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith('Begin Object ') and 'Name="RuntimePartitionPersistent_' in line:
            block = [line.strip()]
            i += 1
            while lines[i].strip() != 'End Object':
                block.append(lines[i].strip())
                i += 1
            # These are the only allowed regenerated object types/properties.
            if len(block) > 1:
                assert block[1:3] == ['bClientOnlyVisible=True', 'LoadingRange=0']
                assert len(block) == 4 and re.fullmatch(r'DebugColor=\(R=[0-9.]+,G=[0-9.]+,B=[0-9.]+,A=1.000000\)', block[3])
                persistent.append('definition:client-only,zero-range')
            else:
                assert 'Class=/Script/Engine.RuntimePartitionPersistent ' in line
                persistent.append('declaration:RuntimePartitionPersistent')
        else:
            retained.append(re.sub(r'RuntimePartitionPersistent_[01]', 'RuntimePartitionPersistent_GENERATED', line))
        i += 1
    assert Counter(persistent) == Counter({'definition:client-only,zero-range': 2, 'declaration:RuntimePartitionPersistent': 2})
    return '\n'.join(retained), persistent


def verify(audit, author):
    baseline = audit/'GroundBaseline.umap'
    authored = audit/'GroundAuthored.umap'
    current = PROJECT/'Content/Maps/BiellaOpenWorldMap.umap'
    receipt = json.loads((author/'validation.json').read_text())
    before = receipt['before']
    map_key = str(current.relative_to(PROJECT))
    assert file_identity(baseline)['sha256'] == before[map_key]['sha256']
    assert authored.read_bytes() == current.read_bytes(), 'Current map differs from audited copy'
    assert len(baseline.read_bytes()) == len(authored.read_bytes()) == 13330
    # Exact observed binary delta: package saved hash, generated export references,
    # DateModified metadata, and regenerated partition debug color. No broad ignore.
    allowed = [(24,44), (4965,4966), (6085,6086), (7061,7070), (10365,10381)]
    delta = [i for i,(a,b) in enumerate(zip(baseline.read_bytes(),authored.read_bytes())) if a != b]
    assert delta and all(any(lo <= i < hi for lo,hi in allowed) for i in delta), delta
    x, px = normalized_export(audit/'GroundBaseline.umap.t3d', 'GroundBaseline')
    y, py = normalized_export(audit/'GroundAuthored.umap.t3d', 'GroundAuthored')
    assert x == y and px == py, '\n'.join(difflib.unified_diff(x.splitlines(),y.splitlines()))
    after = {str(p.relative_to(PROJECT)):file_identity(p) for p in sorted((PROJECT/'Content').rglob('*'))
             if p.is_file() and p.suffix in ('.uasset','.umap')}
    assert [k for k,v in before.items() if after.get(k) != v] == [map_key]
    expected_new = ['Content/OpenWorld/Materials/MI_GroundSupport.uasset',
                    'Content/__ExternalActors__/Maps/BiellaOpenWorldMap/7/FB/1IJTPLTQE7QKVNBK0XIGE7.uasset']
    assert sorted(set(after)-set(before)) == expected_new
    probe = json.loads((author/'probe.json').read_text())
    saved = json.loads((author/'author.json').read_text())
    readback = json.loads((author/'readback.json').read_text())
    assert probe['existing_actors'] == saved['existing_actors'] == readback['existing_actors']
    assert saved['ground'] == readback['ground']
    process = json.loads((audit/'process.json').read_text())
    assert process['returncode'] == 0 and not process['timed_out']
    engine = Path('/opt/unreal/UE_5.8.2/Engine/Source/Runtime/Engine/Private/WorldPartition/RuntimeHashSet')
    refs = [engine/'WorldPartitionRuntimeHashSet.cpp', engine/'RuntimePartition.cpp']
    return dict(task_id='D03-01', result='PASS', baseline=file_identity(baseline), authored=file_identity(authored),
                current_map=file_identity(current), changed_byte_offsets=delta,
                normalized_export_sha256=hashlib.sha256(x.encode()).hexdigest(),
                preexisting_assets_unchanged_except_map=len(before)-1, new_assets=expected_new,
                existing_actor_invariants=len(probe['existing_actors']), engine_sources={str(p):file_identity(p) for p in refs},
                normalization='Only generated RuntimePartitionPersistent declarations/definitions, name references and debug colors; all retained export lines equal in order.',
                limitations='DiffAssets exports map-owned objects after PostLoad. External actors are instead checked by exact asset bytes and editor readback. Temp external-folder scan warnings are expected for copied maps. This does not qualify a cooked package.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--author',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert not args.output.exists(), 'Use fresh evidence output'
    report=verify(args.audit.resolve(),args.author.resolve())
    write_json(args.output,report)
    print(json.dumps({k:report[k] for k in ('result','preexisting_assets_unchanged_except_map','existing_actor_invariants')}))


if __name__=='__main__':main()
