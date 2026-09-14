import bpy, hashlib, json
from pathlib import Path
from mathutils import Vector
out=Path(__file__).resolve().parent
root=out.parents[4]
blend=root/'SourceAssets/Environment/ServiceBay.blend'
assert Path(bpy.data.filepath).resolve()==blend
records=[]
for name in ('Approach column tissue sheath','Header end tissue mat'):
    obj=bpy.data.objects[name]
    assert obj.type=='MESH' and obj.modifiers[0].type=='SUBSURF'
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    positions=[evaluated.matrix_world @ v.co for v in mesh.vertices]
    low=[min(v[i] for v in positions) for i in range(3)]
    high=[max(v[i] for v in positions) for i in range(3)]
    if 'column' in name:
        assert low[1]>244 and low[2]>=0, (name,low)
        assert low[0]<-25 and high[2]>240, (name,low,high)
    else:
        assert low[1]>194 and low[2]>215, (name,low)
    assert obj.data.materials[0].name=='Growth'
    records.append(dict(name=name,vertices=len(mesh.vertices),bounds_min=low,bounds_max=high,
        outside_moving_panel_envelope=True,clear_of_lamp_and_switch=True))
    evaluated.to_mesh_clear()
report=dict(task_id='D17-01',result='PASS',source_blend_sha256=hashlib.sha256(blend.read_bytes()).hexdigest(),
    records=records,scope='Read-only evaluated geometry in saved editable blend; fresh Unreal bounds/collision readback is separate')
(out/'geometry-readback.json').write_text(json.dumps(report,indent=2)+'\n')
print('D17_SERVICE_GEOMETRY_READBACK PASS')
