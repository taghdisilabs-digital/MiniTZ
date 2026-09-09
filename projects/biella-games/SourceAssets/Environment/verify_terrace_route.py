"""Fresh Blender readback: formats, editable parts, exported identities and route clearance."""
import bpy,json,hashlib,os,subprocess
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parent
spec=json.loads((root/'terrace-route.json').read_text())
data=(root/'TerraceRoute.blend').read_bytes()
compressed=data[:4]==bytes.fromhex('28b52ffd')
decoded=subprocess.run(['zstd','-dc',str(root/'TerraceRoute.blend')],check=True,capture_output=True).stdout if compressed else data
assert decoded[:7]==b'BLENDER'
assert (root/spec['fbx']).read_bytes()[:23]==b'Kaydara FBX Binary  \x00\x1a\x00'
assert hashlib.sha256((root/spec['fbx']).read_bytes()).hexdigest()==spec['sha256']
assert hashlib.sha256((root/spec['source']).read_bytes()).hexdigest()==spec['source_sha256']
bpy.ops.wm.open_mainfile(filepath=str(root/'TerraceRoute.blend'))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
assert len(objects)==spec['editable_parts']
deps=bpy.context.evaluated_depsgraph_get(); origin=Vector(spec['origin_cm']); violations=[]
minimum=[float('inf')]*3; maximum=[-float('inf')]*3
for obj in objects:
    evaluated=obj.evaluated_get(deps); mesh=evaluated.to_mesh()
    for vertex in mesh.vertices:
        local=evaluated.matrix_world@vertex.co; p=local+origin
        for k in range(3): minimum[k]=min(minimum[k],local[k]); maximum[k]=max(maximum[k],local[k])
        floor=max(0,min(400,(p.y-1000)*.2))
        if 9860<p.x<10140 and 1000<p.y<3500 and floor+2<p.z<floor+190:
            violations.append(obj.name); break
    evaluated.to_mesh_clear()
assert not violations,sorted(set(violations))
assert max(abs(a-b) for a,b in zip(minimum,spec['bounds_min']))<.025
assert max(abs(a-b) for a,b in zip(maximum,spec['bounds_max']))<.025
report=dict(task_id='D17-02',result='PASS',parts_read_back=len(objects),
    actual_blender_magic=True,blender_compression='zstd' if compressed else 'none',actual_binary_fbx_magic=True,
    center_route_vertices_clear=True,clearance_cm=dict(x=[9860,10140],y=[1000,3500],above_floor=[2,190]),
    evaluated_modifiers=True,bounds_min=minimum,bounds_max=maximum,status='GENERATED_DRAFT',
    scope='Editable source structural readback; native import, collision and raw runtime remain required')
report['sources']=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
    for p in (root/'TerraceRoute.blend',root/spec['fbx'],root/spec['source'],root/'terrace-route.json',Path(__file__).resolve())]
Path(os.environ['BIELLA_D17_TERRACE_GEOMETRY_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
print('D17_TERRACE_GEOMETRY_VERIFIED')
