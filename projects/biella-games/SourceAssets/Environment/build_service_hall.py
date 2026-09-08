"""Biella-authored fitted warehouse skin in centimeters; no gameplay geometry edits.
The .blend keeps named manufactured parts and editable bevels. FBX copies
compensate Unreal's Y reflection; original building colliders remain in use.
"""
import bpy, bmesh, math, json, hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
ORIGIN=Vector((8000,2250,0))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene.unit_settings.scale_length=.01
bpy.context.preferences.filepaths.save_version=0
materials={}
for name,color,metal,rough in [('Paint',(.055,.074,.08,1),0,.48),('Steel',(.31,.34,.36,1),1,.32),('Rubber',(.012,.015,.018,1),0,.78)]:
    m=bpy.data.materials.new(name); m.diffuse_color=color; m.use_nodes=True
    bsdf=m.node_tree.nodes.get('Principled BSDF'); bsdf.inputs['Base Color'].default_value=color
    bsdf.inputs['Metallic'].default_value=metal; bsdf.inputs['Roughness'].default_value=rough
    materials[name]=m
parts=[]
def finish(obj,name,material,bevel=.25):
    obj.name=name; obj.data.materials.append(materials[material])
    if bevel:
        m=obj.modifiers.new('Fold radius cm','BEVEL'); m.width=bevel; m.segments=3
    parts.append(obj); return obj

def box(name,at,size,material='Paint',bevel=.25):
    bpy.ops.mesh.primitive_cube_add(size=1,location=Vector(at)-ORIGIN)
    o=bpy.context.object; o.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,name,material,bevel)

def rod(name,a,b,radius,material='Steel',vertices=16):
    delta=Vector(b)-Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=delta.length,
        location=(Vector(a)+Vector(b))/2-ORIGIN)
    o=bpy.context.object; o.rotation_mode='QUATERNION'; o.rotation_quaternion=delta.to_track_quat('Z','Y')
    return finish(o,name,material,.12)

# Thin skins lie on existing solid walls. Frame ribs are shallow, never
# separate invisible obstacles in the entrance, street or service apron.
# For X walls tangent=Y, for Y walls tangent=X. Exterior coordinates measured
# from author_open_world.py; centimeter offsets conceal only original faces.
walls=[('West','X',6948,1500,3000,-1),('East','X',9052,1500,3000,1),
       ('Rear','Y',3052,6950,9050,1),('DoorWest','Y',1473,7000,7800,-1),
       ('DoorEast','Y',1473,8200,9000,-1)]
def wallbox(name,axis,normal,tangent,z,depth,width,height,material='Paint',bevel=.25):
    at=(normal,tangent,z) if axis=='X' else (tangent,normal,z)
    size=(depth,width,height) if axis=='X' else (width,depth,height)
    return box(name,at,size,material,bevel)
for name,axis,face,start,end,sign in walls:
    count=round((end-start)/150); width=(end-start)/count
    for i in range(count):
        center=start+(i+.5)*width
        for z in (148,448):
            wallbox(name+' folded cassette',axis,face,center,z,2,width-2,294)
            # Folded edges and inset relief catch grazing overcast light.
            for edge in (-width/2+3,width/2-3):
                wallbox(name+' cassette return',axis,face+sign*1.5,center+edge,z,3,2.5,291)
            for seam in (-width*.32,-width*.16,0,width*.16,width*.32):
                wallbox(name+' pressed vertical rib',axis,face+sign*1.5,center+seam,z,3,1.8,284,bevel=.18)
    for tangent in [start+i*(end-start)/max(1,round((end-start)/300)) for i in range(round((end-start)/300)+1)]:
        tangent=max(start+6.5,min(end-6.5,tangent))
        wallbox(name+' structural cover plate',axis,face+sign*2,tangent,300,6,13,596,'Paint',.45)
        for z in (28,286,314,572):
            at=(face+sign*5.5,tangent,z) if axis=='X' else (tangent,face+sign*5.5,z)
            endpt=(at[0]+sign*.9,at[1],at[2]) if axis=='X' else (at[0],at[1]+sign*.9,at[2])
            rod(name+' frame fixing',at,endpt,1.2,'Steel',6)
    for z,height in ((10,18),(300,8),(588,18)):
        wallbox(name+' horizontal flashing',axis,face+sign*2.5,(start+end)/2,z,7,end-start,height,'Steel',.4)
    wallbox(name+' damp proof plinth',axis,face,(start+end)/2,3,2,end-start,5,'Rubber',.1)

# Roof edge caps cover the existing 50cm roof slab; none extends into the
# accepted 400cm entrance gap below z650. Real joints break the long skyline.
for y in (1473,3027):
    box('Roof fascia weathered plate',(8000,y,675),(2104,4,49),'Paint',.6)
    for x in range(6975,9026,150): box('Fascia seam cover',(x,y-2 if y<2250 else y+2,675),(3,3,48),'Steel')
for x in (6948,9052):
    box('Roof side fascia',(x,2250,675),(4,1554,49),'Paint',.6)
for z in (651,699):
    for y in (1471,3029): box('Roof drip edge',(8000,y,z),(2110,10,2),'Steel')
    for x in (6946,9054): box('Roof side drip edge',(x,2250,z),(10,1558,2),'Steel')

# Two fixed ventilation housings above human head height, attached to the
# west wall. Inclined blades expose deep rubber-black throats; no fan animation
# or unimplemented interaction is implied.
for y in (1910,2600):
    box('Vent sealed backplate',(6942,y,394),(8,164,156),'Rubber',.7)
    for edge in (-80,80): box('Vent side folded channel',(6930,y+edge,394),(34,6,166),'Paint',.6)
    for z in (314,474): box('Vent cap folded channel',(6930,y,z),(34,166,6),'Paint',.6)
    for z in range(325,465,14):
        blade=box('Rain-shedding ventilation louver',(6922,y,z),(27,151,3),'Steel',.45)
        blade.rotation_euler.y=math.radians(-24)
    for dy in (-72,72):
        for z in (323,465): rod('Vent captive fixing',(6912,y+dy,z),(6910,y+dy,z),1.45,'Steel',6)
# Wall-supported utilities remain above the player's standing envelope.
for z,r in ((521,4.5),(547,2.7)):
    rod('Service conduit',(6929,1510,z),(6929,2988,z),r,'Paint',24)
    for y in range(1550,3000,190):
        box('Pipe anchor',(6943,y,z),(14,11,4),'Steel')
        rod('Conduit coupling',(6929,y-2,z),(6929,y+2,z),r+1.2,'Steel',24)

# Export evaluated copies, retaining individually editable manufacturing parts.
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'ServiceHall.blend'))
bpy.ops.object.select_all(action='DESELECT')
copies=[]
for original in parts:
    obj=original.copy(); obj.data=original.data.copy(); bpy.context.collection.objects.link(obj)
    obj.select_set(True); copies.append(obj)
bpy.context.view_layer.objects.active=copies[0]
bpy.ops.object.convert(target='MESH'); bpy.ops.object.join(); obj=bpy.context.object
obj.name='SM_ServiceHallCladding'
bpy.context.scene.cursor.location=(0,0,0); bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.context.view_layer.update()
bounds=[obj.matrix_world@Vector(v) for v in obj.bound_box]
minimum=[min(v[i] for v in bounds) for i in range(3)]; maximum=[max(v[i] for v in bounds) for i in range(3)]
bm=bmesh.new(); bm.from_mesh(obj.data); volume=bm.calc_volume(signed=True)
for v in bm.verts:v.co.y*=-1
bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
assert abs(volume-bm.calc_volume(signed=True))<max(1,abs(volume))*1e-5
bm.to_mesh(obj.data); bm.free(); obj.data.calc_loop_triangles()
path=ROOT/'SM_ServiceHallCladding.fbx'
bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},
    axis_forward='X',axis_up='Z',apply_unit_scale=True,bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
spec=dict(schema='biella.service_hall.art/v1',task_id='D17-01',status='GENERATED_DRAFT',
    provenance='Biella-authored geometry, no third-party asset inputs',map='/Game/Maps/BiellaOpenWorldMap',
    actor_label='D17_ServiceHall_Cladding',origin_cm=list(ORIGIN),collision='NoCollision',
    existing_collision_preserved=True,entrance_clear_bounds_cm=[[7800,1475,0],[8200,1525,600]],
    source=Path(__file__).name,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    blender=bpy.app.version_string,editable_parts=len(parts),mesh=obj.name,fbx=path.name,
    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),triangles=len(obj.data.loop_triangles),
    bounds_min=minimum,bounds_max=maximum,export_y_reflected=True,outward_volume_preserved=True,
    material_slots=[m.name for m in obj.data.materials])
(ROOT/'service-hall.json').write_text(json.dumps(spec,indent=2)+'\n')
print('D17_SERVICE_HALL_MESH COMPLETE',json.dumps(spec))
