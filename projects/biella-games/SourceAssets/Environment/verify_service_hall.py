"""Read the editable cladding scene and check the original doorway stays open."""
import bpy,json,hashlib,os,subprocess
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parent
spec=json.loads((root/'service-hall.json').read_text())
blend_bytes=(root/'ServiceHall.blend').read_bytes()
compressed=blend_bytes[:4]==bytes.fromhex('28b52ffd')
decoded=subprocess.run(['zstd','-dc',str(root/'ServiceHall.blend')],check=True,capture_output=True).stdout if compressed else blend_bytes
assert decoded[:7]==b'BLENDER'
assert (root/spec['fbx']).read_bytes()[:23]==b'Kaydara FBX Binary  \x00\x1a\x00'
assert hashlib.sha256((root/spec['fbx']).read_bytes()).hexdigest()==spec['sha256']
bpy.ops.wm.open_mainfile(filepath=str(root/'ServiceHall.blend'))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
assert len(objects)==spec['editable_parts']
deps=bpy.context.evaluated_depsgraph_get()
origin=Vector(spec['origin_cm']); violations=[]
# Expand the swept doorway volume fore/aft; use one millimeter tolerance at
# wall boundaries. Check evaluated objects, including all bevel modifiers.
lo=(7800.1,1400,0); hi=(8199.9,1600,599.9)
for obj in objects:
    evaluated=obj.evaluated_get(deps)
    points=[evaluated.matrix_world@Vector(v)+origin for v in evaluated.bound_box]
    minimum=[min(v[k] for v in points) for k in range(3)]
    maximum=[max(v[k] for v in points) for k in range(3)]
    if all(min(maximum[k],hi[k])-max(minimum[k],lo[k])>.001 for k in range(3)):
        violations.append(obj.name)
assert not violations,violations
report=dict(task_id='D17-01',result='PASS',parts_read_back=len(objects),
    actual_blender_magic=True,blender_compression='zstd' if compressed else 'none',actual_binary_fbx_magic=True,entrance_volume_clear_cm=[lo,hi],
    evaluated_modifiers=True,generated_draft=True,scope='Editable mesh structural readback; runtime required')
report['sources']=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
    for p in (root/'ServiceHall.blend',root/spec['fbx'],root/spec['source'],root/'service-hall.json',Path(__file__).resolve())]
Path(os.environ['BIELLA_D17_HALL_GEOMETRY_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
print('D17_HALL_GEOMETRY_VERIFIED')
