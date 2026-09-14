import bpy, json, hashlib
from pathlib import Path
out=Path(__file__).parent
source=Path(bpy.data.filepath)
meshes=[o for o in bpy.data.objects if o.type=='MESH']
groups={c.name:len(c.objects) for c in bpy.data.collections if c.name.endswith(' editable components')}
cabinet=bpy.data.objects['Control cabinet carcass']
assert len(groups)==3 and len(meshes)>50
assert len(cabinet.modifiers)>0
report=dict(result='PASS',format='Blender native editable scene',blender=bpy.app.version_string,
 source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
 mesh_objects=len(meshes),editable_groups=groups,bevel_modifiers=sum(len(o.modifiers) for o in meshes),
 cabinet_location=list(cabinet.location),cabinet_dimensions=list(cabinet.dimensions))
(out/'blender.json').write_text(json.dumps(report,indent=2)+'\n')
print('D17_EDITABLE_SERVICE_READBACK COMPLETE')
