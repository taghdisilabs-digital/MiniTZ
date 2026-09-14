"""Reopen editable hall fittings, verify export identity, support and route clearance."""
import bpy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from mathutils import Vector

root = Path(__file__).resolve().parent
spec = json.loads((root / 'hall-interior.json').read_text())
blend = root / 'HallInterior.blend'
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
boxes = {}
for obj in objects:
    evaluated = obj.evaluated_get(deps)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
        vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        points.extend(vertices)
        boxes[obj.name] = ([min(v[k] for v in vertices) for k in range(3)],
                           [max(v[k] for v in vertices) for k in range(3)])
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
# Prove every separate fitting is rooted in an original solid, directly or
# through another fitting. Axis-aligned contacts are a structural precheck;
# native playback still must establish collision/traversal and appearance.
def contact(a,b):
    return all(min(a[1][k],b[1][k])-max(a[0][k],b[0][k]) >= -.025 for k in range(3))
solids = [([-1000,-750,-100],[1000,750,0]),
          ([-1050,-750,0],[-1000,750,600]),
          ([1000,-750,0],[1050,750,600]),
          ([-1050,750,0],[1050,800,600]),
          ([-1050,-775,650],[1050,775,700])]
rooted={name for name,box in boxes.items() if any(contact(box,s) for s in solids)}
direct=len(rooted)
while True:
    new={name for name,box in boxes.items() if name not in rooted
         and any(contact(box,boxes[other]) for other in rooted)}
    if not new: break
    rooted.update(new)
assert rooted == boxes.keys(), 'Unsupported fittings: '+repr(sorted(boxes.keys()-rooted))
route=(spec['clear_route_min_cm'],spec['clear_route_max_cm'])
intersections=[name for name,box in boxes.items() if contact(box,route)]
assert not intersections, 'Fittings intrude into the retained walking route: '+repr(intersections)
floor_boxes={name:b for name,b in boxes.items() if name.startswith('Floor')}
assert floor_boxes and max(b[1][2] for b in floor_boxes.values()) <= spec['floor_detail_max_height_cm']+.001
assert min(b[0][2] for b in floor_boxes.values()) >= -.3
assert 650 <= maximum[2] <= 652
report = dict(task_id='D17-01', result='PASS', parts_read_back=len(objects),
    triangles=triangles, bounds_min=minimum, bounds_max=maximum,
    materials=sorted(materials), roof_soffit_cm=650, world_top_cm=maximum[2],
    directly_supported_parts=direct, connected_supported_parts=len(rooted),
    unsupported_parts=[], clear_route_intersections=[],
    clear_route_min_cm=route[0],clear_route_max_cm=route[1],
    floor_detail_parts=len(floor_boxes),floor_detail_max_height_cm=max(b[1][2] for b in floor_boxes.values()),
    actual_blender_magic=True, blender_compression='zstd' if compressed else 'none',
    actual_binary_fbx_magic=True, evaluated_modifiers=True,
    generated_draft=True, slice_acceptance=False,
    scope='Editable geometry, envelope contacts and clear passage; native traversal and visible quality verified separately')
report['sources'] = [dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size)
    for p in (blend, fbx, root/spec['source'], root/'hall-interior.json', Path(__file__).resolve())]
Path(os.environ['BIELLA_D17_INTERIOR_GEOMETRY_REPORT']).write_text(json.dumps(report, indent=2)+'\n')
print('D17_HALL_INTERIOR_GEOMETRY_VERIFIED')
