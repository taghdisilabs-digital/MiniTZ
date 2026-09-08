"""Reopen the editable lamp and verify export geometry and ceiling contact."""
import bpy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from mathutils import Vector

root = Path(__file__).resolve().parent
spec = json.loads((root / 'hall-practical.json').read_text())
blend = root / 'HallPractical.blend'
raw = blend.read_bytes()
compressed = raw[:4] == bytes.fromhex('28b52ffd')
decoded = subprocess.run(['zstd', '-dc', str(blend)], check=True, capture_output=True).stdout if compressed else raw
assert decoded[:7] == b'BLENDER'
fbx = root / spec['fbx']
assert fbx.read_bytes()[:23] == b'Kaydara FBX Binary  \x00\x1a\x00'
assert hashlib.sha256(fbx.read_bytes()).hexdigest() == spec['sha256']
assert hashlib.sha256((root / spec['source']).read_bytes()).hexdigest() == spec['source_sha256']
bpy.ops.wm.open_mainfile(filepath=str(blend))
objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert len(objects) == spec['editable_parts']
deps = bpy.context.evaluated_depsgraph_get()
points, triangles, materials = [], 0, set()
for obj in objects:
    evaluated = obj.evaluated_get(deps)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
        points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        materials.update(m.name for m in mesh.materials if m)
        assert all(p.area > 0 for p in mesh.polygons), obj.name
    finally:
        evaluated.to_mesh_clear()
minimum = [min(v[k] for v in points) for k in range(3)]
maximum = [max(v[k] for v in points) for k in range(3)]
assert triangles == spec['triangles']
assert all(abs(a-b) < .01 for a,b in zip(minimum, spec['bounds_min']))
assert all(abs(a-b) < .01 for a,b in zip(maximum, spec['bounds_max']))
assert materials == set(spec['material_slots']), materials
world_top = maximum[2] + spec['origin_cm'][2]
assert 650 <= world_top <= 652, 'Housing must meet the retained 650 cm roof soffit'
report = dict(task_id='D17-01', result='PASS', parts_read_back=len(objects),
    triangles=triangles, bounds_min=minimum, bounds_max=maximum,
    materials=sorted(materials), roof_soffit_cm=650, world_top_cm=world_top,
    actual_blender_magic=True, blender_compression='zstd' if compressed else 'none',
    actual_binary_fbx_magic=True, evaluated_modifiers=True,
    generated_draft=True, slice_acceptance=False,
    scope='Editable geometry and expected roof contact; native saved actor placement checked separately')
report['sources'] = [dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size)
    for p in (blend, fbx, root/spec['source'], root/'hall-practical.json', Path(__file__).resolve())]
Path(os.environ['BIELLA_D17_PRACTICAL_GEOMETRY_REPORT']).write_text(json.dumps(report, indent=2)+'\n')
print('D17_HALL_PRACTICAL_GEOMETRY_VERIFIED')
