"""Biella-owned, individually editable pendant housing for the retained hall light.

Centimeter geometry; roof anchor reaches the existing soffit at world Z=650.
The visual asset has no collision and introduces no gameplay behavior.
"""
import bpy, bmesh, math, hashlib, json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = .01
materials = {}
for name, color, metal, rough in [
    ('Paint', (.055,.074,.08,1), 0, .48),
    ('Steel', (.31,.34,.36,1), 1, .32),
    ('Lamp', (1,.62,.28,1), 0, .3)]:
    m = bpy.data.materials.new(name); m.diffuse_color=color; m.use_nodes=True
    bsdf=m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=color
    bsdf.inputs['Metallic'].default_value=metal
    bsdf.inputs['Roughness'].default_value=rough
    if name=='Lamp':
        bsdf.inputs['Emission Color'].default_value=color
        bsdf.inputs['Emission Strength'].default_value=3
    materials[name]=m
parts=[]

def finish(obj,name,material,bevel=.2):
    obj.name=name; obj.data.materials.append(materials[material])
    if bevel:
        mod=obj.modifiers.new('Manufactured edge radius','BEVEL');mod.width=bevel;mod.segments=3
    parts.append(obj);return obj

def box(name,location,size,material='Paint',bevel=.2):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    obj=bpy.context.object;obj.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(obj,name,material,bevel)

def cylinder(name,location,radius,depth,material='Steel',vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=location)
    return finish(bpy.context.object,name,material,.15)

box('Ceiling bolted mounting plate',(0,0,129),(24,24,4))
for x in (-8,8):
    for y in (-8,8): cylinder('Roof anchor captive nut',(x,y,126.3),1.2,1.5,vertices=6)
cylinder('Threaded suspension stem',(0,0,78),1.1,100)
for z in (31,76,123): cylinder('Stem coupling',(0,0,z),2,4)
box('Sealed electrical driver',(0,0,30),(23,17,10))
# Conical reflector and deep rim enclose the diffuser; all contacts overlap.
bpy.ops.mesh.primitive_cone_add(vertices=64,radius1=26,radius2=14,depth=16,location=(0,0,17))
finish(bpy.context.object,'Spun high-bay reflector','Paint',.4)
cylinder('Reflector rolled lower rim',(0,0,8),27,4)
cylinder('Recessed opal diffuser',(0,0,5.5),23.8,1.5,'Lamp',64)
for angle in range(0,360,45):
    a=math.radians(angle)
    cylinder('Rim captive screw',(25.4*math.cos(a),25.4*math.sin(a),5.6),.6,1.2,vertices=6)
for y in (-12,0,12):
    length=2*math.sqrt(23.8**2-y*y)
    box('Diffuser safety crossbar',(0,y,4.2),(length,.7,.7),'Steel',.1)
# Visible power feed is clamped to the stem and enters the driver from above.
cylinder('Protected electrical drop',(3.8,0,80),.65,96,'Paint',24)
for z in (46,86,123): box('Cable stem clamp',(1.7,0,z),(6.6,2.8,1.5),'Steel',.15)

bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'HallPractical.blend'))
bpy.ops.object.select_all(action='DESELECT')
copies=[]
for original in parts:
    obj=original.copy();obj.data=original.data.copy();bpy.context.collection.objects.link(obj)
    obj.select_set(True);copies.append(obj)
bpy.context.view_layer.objects.active=copies[0]
bpy.ops.object.convert(target='MESH');bpy.ops.object.join();obj=bpy.context.object
obj.name='SM_HallPractical'
bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.context.view_layer.update()
bounds=[obj.matrix_world@Vector(v) for v in obj.bound_box]
minimum=[min(v[i] for v in bounds) for i in range(3)]
maximum=[max(v[i] for v in bounds) for i in range(3)]
bm=bmesh.new();bm.from_mesh(obj.data);volume=bm.calc_volume(signed=True)
assert volume>0
for v in bm.verts:v.co.y*=-1
bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
assert abs(volume-bm.calc_volume(signed=True))<volume*1e-5
bm.to_mesh(obj.data);bm.free();obj.data.calc_loop_triangles()
fbx=ROOT/'SM_HallPractical.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
    axis_forward='X',axis_up='Z',apply_unit_scale=True,bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
spec=dict(schema='biella.hall_practical/v1',task_id='D17-01',status='GENERATED_DRAFT',
    provenance='Biella-authored geometry; retained Biella ServiceBay materials',
    map='/Game/Maps/BiellaOpenWorldMap',actor_label='D17_Hall_Practical',
    origin_cm=[8000,2250,520],collision='NoCollision',mesh=obj.name,
    source=Path(__file__).name,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    fbx=fbx.name,sha256=hashlib.sha256(fbx.read_bytes()).hexdigest(),
    blender=bpy.app.version_string,editable_parts=len(parts),triangles=len(obj.data.loop_triangles),
    bounds_min=minimum,bounds_max=maximum,material_slots=[m.name for m in obj.data.materials],
    export_y_reflected=True,outward_volume_preserved=True,
    light_label='D02_Interior_Light',light_lumens=1800.0,light_color_linear=[1,.62,.28,1],
    light_attenuation_cm=2600.0,light_source_radius_cm=20.0,
    scope='Reduce the observed white interior wash and give the existing light a supported housing; preserve all existing geometry, collision and gameplay.')
(ROOT/'hall-practical.json').write_text(json.dumps(spec,indent=2)+'\n')
print('D17_HALL_PRACTICAL_MESH COMPLETE',json.dumps(spec))
