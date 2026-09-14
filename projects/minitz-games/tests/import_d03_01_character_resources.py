#!/usr/bin/env python3
"""Copy the exact installed Epic resource closure without overwriting Project work.

Package-name extraction is a conservative candidate selector. Native Unreal
readback in inspect_production_animation.py validates load/dependency closure.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil

PROJECT=Path(__file__).resolve().parents[1]
SOURCE=Path('/opt/unreal/UE_5.8.2/Templates/TemplateResources/High/Characters/Content/Mannequins')
DEST=PROJECT/'Content/Characters/Mannequins'
ROOTS=['Meshes/SKM_Manny_Simple','Anims/Unarmed/BS_Idle_Walk_Run',
       'Anims/Unarmed/Jump/MM_Jump','Anims/Unarmed/Jump/MM_Fall_Loop','Anims/Unarmed/Jump/MM_Land',
       'Anims/Rifle/MM_Rifle_Fire','Anims/Rifle/HitReact/MM_HitReact_Front_Lgt_01','Anims/Rifle/MF_Rifle_Idle_ADS']
ROOTS += [str(p.relative_to(SOURCE).with_suffix('')) for c in ('Walk','Jog') for p in sorted((SOURCE/'Anims/Rifle'/c).glob('*.uasset'))]

def main():
    seen=set(); pending=ROOTS[:]; records=[]
    while pending:
        relative=pending.pop()
        if relative in seen: continue
        src=SOURCE/(relative+'.uasset'); data=src.read_bytes(); seen.add(relative)
        pending += [m.decode() for m in re.findall(rb'/Game/Characters/Mannequins/([A-Za-z0-9_/-]+)',data) if m.decode() not in seen]
    for relative in sorted(seen):
        src=SOURCE/(relative+'.uasset'); dst=DEST/(relative+'.uasset')
        if dst.exists(): assert src.read_bytes()==dst.read_bytes(), f'Preserve changed Project asset: {dst}'
        else:
            dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst); dst.chmod(0o644)
        records.append(dict(source=str(src),local=str(dst.relative_to(PROJECT)),size=dst.stat().st_size,sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
    out=PROJECT/'SourceAssets/Characters/UE58Mannequin.provenance.json'; out.parent.mkdir(parents=True,exist_ok=True)
    report=dict(task_id='D03-01',provider='Installed Epic Unreal Engine 5.8.2 TemplateResources',
                status='INTEGRATION_RESOURCE_NOT_FINAL_CHARACTER_ART',roots=ROOTS,files=records)
    serialized=json.dumps(report,indent=2)+'\n'
    if out.exists(): assert out.read_text()==serialized, 'Preserve prior provenance'
    else: out.write_text(serialized)
    print(json.dumps({'copied_or_verified':len(records),'bytes':sum(r['size'] for r in records),'provenance':str(out)}))

if __name__=='__main__': main()
