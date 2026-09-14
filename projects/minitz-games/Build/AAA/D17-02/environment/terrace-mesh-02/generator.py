"""Editable fitted steel route for the existing 4 m rise and 4 m wide ramp.

Centimeters, manufactured joints, supported deck and legible edge strips.
No downloaded assets. Original walkable ramp/deck planes remain authoritative.
"""
import bpy, bmesh, math, json, hashlib
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
ORIGIN = Vector((10000, 3000, 0))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = .01
bpy.context.preferences.filepaths.save_version = 0
parts, materials = [], {}
for name, color, metal, rough in [('Paint', (.055,.074,.08,1),0,.48),
                                 ('Steel', (.31,.34,.36,1),1,.32),
                                 ('Rubber', (.012,.015,.018,1),0,.78)]:
    m=bpy.data.materials.new(name); m.diffuse_color=color; m.use_nodes=True
    node=m.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value=color
    node.inputs['Metallic'].default_value=metal
    node.inputs['Roughness'].default_value=rough
    materials[name]=m

def box(name, at, size, mat='Paint', bevel=.25, slope=False):
    bpy.ops.mesh.primitive_cube_add(size=1, location=Vector(at)-ORIGIN)
    obj=bpy.context.object; obj.name=name; obj.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if slope: obj.rotation_euler.x=math.atan2(400,2000)
    obj.data.materials.append(materials[mat])
    if bevel:
        mod=obj.modifiers.new('Manufactured edge radius cm','BEVEL'); mod.width=bevel; mod.segments=3
    parts.append(obj); return obj

def rod(name,a,b,r=2,mat='Steel',vertices=12):
    delta=Vector(b)-Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=delta.length,
        location=(Vector(a)+Vector(b))/2-ORIGIN)
    o=bpy.context.object; o.name=name; o.rotation_mode='QUATERNION'
    o.rotation_quaternion=delta.to_track_quat('Z','Y'); o.data.materials.append(materials[mat])
    mod=o.modifiers.new('Machined lip','BEVEL'); mod.width=.12; mod.segments=2
    parts.append(o)

# The steel skins sit at most 0.7 cm above the retained continuous planes.
# Four-meter corridor is not narrowed by dressing or decorative fixtures.
for j in range(20):
    y=1050+j*100; z=(y-1000)*.2
    for x in (9900,10100):
        box('Ramp replaceable nonslip panel',(x,y,z+.05),(198,math.hypot(100,20)-1,1.2),'Paint',.15,True)
        for dx in (-88,88):
            rod('Ramp captive panel fixing',(x+dx,y,z+.65),(x+dx,y,z+.95),1.1,vertices=6)
    # Flush, bright physical strips give speed/grade and lateral-edge cues.
    for x in (9810,10190):
        box('Ramp edge wear strip',(x,y,z+.8),(8,math.hypot(100,20)-2,.3),'Steel',.08,True)
    for yoff in (-35,-15,5,25):
        box('Ramp shallow traction bar',(10000,y+yoff,z+yoff*.2+.85),(370,1.1,.3),'Steel',.06,True)
for side in (-1,1):
    x=10000+side*198
    box('Ramp edge folded web',(x,2000,180),(4,math.hypot(2000,400),36),'Paint',.3,True)
    for dz in (-17,17):
        box('Ramp edge return flange',(x,2000,180+dz),(10,math.hypot(2000,400),3),'Steel',.3,True)

for ix in range(10):
    for iy in range(5):
        x,y=9100+ix*200,3100+iy*200
        box('Terrace replaceable deck cassette',(x,y,400.05),(198,198,1.2),'Paint',.2)
        for dx in (-88,88):
            for dy in (-88,88):
                rod('Terrace captive fixing',(x+dx,y+dy,400.65),(x+dx,y+dy,401),1.1,vertices=6)
        for d in range(-80,81,20):
            box('Terrace shallow traction rib',(x+d,y,400.8),(1.1,184,.3),'Steel',.06)

# Solid original 120 cm parapets are retained and clad, including returned
# seams and coping; this does not imply passable gaps in their collision.
for axis,fixed,start,end in [('X',9025,3000,4000),('X',10975,3000,4000),('Y',3975,9000,11000)]:
    for normal in (-26,26):
        for tangent in range(start+100,end,200):
            at=(fixed+normal,tangent,460) if axis=='X' else (tangent,fixed+normal,460)
            size=(2,198,119) if axis=='X' else (198,2,119)
            box('Parapet folded protective cassette',at,size,'Paint',.4)
    at=(fixed,(start+end)/2,521) if axis=='X' else ((start+end)/2,fixed,521)
    size=(56,end-start,3) if axis=='X' else (end-start,56,3)
    box('Parapet continuous weather cap',at,size,'Steel',.6)

# Grounded columns and structural bracing remove the unsupported slab read.
# Simple native column colliders are specified separately from the skin.
columns=[]
for x in (9140,10000,10860):
    for y in (3100,3850):
        columns.append(dict(center=[x,y,150],size=[34,34,300]))
        box('Ground-bearing welded box column',(x,y,150),(30,30,300),'Paint',.6)
        box('Column base plate',(x,y,3),(52,52,6),'Steel',.4)
        box('Column head bearing plate',(x,y,296),(54,54,8),'Steel',.4)
        for dx in (-19,19):
            for dy in (-19,19): rod('Ground anchor fixing',(x+dx,y+dy,6),(x+dx,y+dy,10),2,vertices=6)
for y in (3100,3850):
    box('Deck transverse structural web',(10000,y,279),(1900,3,40),'Paint',.3)
    for z in (259,299): box('Deck structural flange',(10000,y,z),(1900,30,3),'Steel',.3)
    for x in (9570,10430):
        rod('Grounded diagonal tension brace',(x-410,y,25),(x+410,y,295),3,'Steel',16)
        rod('Grounded diagonal tension brace',(x+410,y,25),(x-410,y,295),3,'Steel',16)
for x in (9140,10000,10860):
    box('Deck longitudinal structural web',(x,3500,279),(3,1000,40),'Paint',.3)
    for z in (259,299): box('Deck longitudinal flange',(x,3500,z),(30,1000,3),'Steel',.3)

# Gap-free physical visual decking; no fake HUD route arrow or image backdrop.
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'TerraceRoute.blend'))
bpy.ops.object.select_all(action='DESELECT')
copies=[]
for original in parts:
    o=original.copy(); o.data=original.data.copy(); bpy.context.collection.objects.link(o)
    o.select_set(True); copies.append(o)
bpy.context.view_layer.objects.active=copies[0]
bpy.ops.object.convert(target='MESH'); bpy.ops.object.join(); obj=bpy.context.object
obj.name='SM_TerraceRoute'
bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
bpy.context.scene.cursor.location=(0,0,0); bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.context.view_layer.update()
bounds=[obj.matrix_world@Vector(v) for v in obj.bound_box]
minimum=[min(v[i] for v in bounds) for i in range(3)]
maximum=[max(v[i] for v in bounds) for i in range(3)]
assert -45 < minimum[2] < 1 and 522 <= maximum[2] <= 523, (minimum,maximum)
bm=bmesh.new(); bm.from_mesh(obj.data); volume=bm.calc_volume(signed=True)
for v in bm.verts:v.co.y*=-1
bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
assert abs(volume-bm.calc_volume(signed=True))<max(1,abs(volume))*1e-5
bm.to_mesh(obj.data); bm.free(); obj.data.calc_loop_triangles()
path=ROOT/'SM_TerraceRoute.fbx'
bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},
    axis_forward='X',axis_up='Z',apply_unit_scale=True,bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
spec=dict(schema='biella.terrace_route.art/v1',task_id='D17-02',status='GENERATED_DRAFT',
    provenance='Biella-authored geometry; no third-party asset inputs',map='/Game/Maps/BiellaOpenWorldMap',
    actor_label='D17_TerraceRoute',origin_cm=list(ORIGIN),collision='NoCollision',
    retained_walkable_planes=True,proposed_column_colliders=columns,
    source=Path(__file__).name,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    blender=bpy.app.version_string,editable_parts=len(parts),mesh=obj.name,fbx=path.name,
    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),triangles=len(obj.data.loop_triangles),
    bounds_min=minimum,bounds_max=maximum,export_y_reflected=True,outward_volume_preserved=True,
    material_slots=[m.name for m in obj.data.materials],
    limits=['Must be imported, collision-bound and raw-runtime qualified before route acceptance',
            'No final environment, character, HUD or whole-slice visual acceptance'])
(ROOT/'terrace-route.json').write_text(json.dumps(spec,indent=2)+'\n')
print('D17_TERRACE_ROUTE_MESH COMPLETE',json.dumps(spec))
