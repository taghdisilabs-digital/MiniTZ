"""Fresh Blender-file readback; invoke Blender StreetBlocks.blend --background --python this.py."""
import hashlib
import json
import os
from pathlib import Path
import bpy

project = Path(__file__).resolve().parents[1]
manifest = json.loads((project/'SourceAssets/Architecture/street-blocks.json').read_text())
rows = []
assert len([o for o in bpy.data.objects if o.type == 'MESH']) == 6
for entry in manifest['assets']:
    obj = bpy.data.objects[entry['mesh']]
    mesh = obj.data
    assert obj.type == 'MESH' and len(mesh.vertices) == entry['vertices']
    mesh.calc_loop_triangles()
    assert len(mesh.loop_triangles) == entry['triangles']
    minimum = [min(v.co[i] for v in mesh.vertices) for i in range(3)]
    maximum = [max(v.co[i] for v in mesh.vertices) for i in range(3)]
    assert all(abs(v+50)<.002 for v in minimum) and all(abs(v-50)<.002 for v in maximum)
    assert all(len(p.vertices) >= 3 and p.area > 0 for p in mesh.polygons)
    assert [m.name for m in mesh.materials] == entry['material_slots']
    assert set(p.material_index for p in mesh.polygons) == set(range(5))
    assert obj['D03.Status'] == 'GENERATED_DRAFT'
    fbx = project/'SourceAssets/Architecture'/entry['fbx']
    assert hashlib.sha256(fbx.read_bytes()).hexdigest() == entry['sha256']
    rows.append(dict(mesh=obj.name, triangles=len(mesh.loop_triangles), vertices=len(mesh.vertices),
                     min=minimum, max=maximum, material_slots=entry['material_slots']))
Path(os.environ['BIELLA_D03_BLENDER_REPORT']).write_text(json.dumps(dict(
    result='PASS', blender=bpy.app.version_string, assets=rows), indent=2)+'\n')
print('D03_BLENDER_READBACK COMPLETE')
