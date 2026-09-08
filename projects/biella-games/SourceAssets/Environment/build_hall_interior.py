"""Biella-owned fitted hall structure and service floor, in editable centimeters.

Shallow wall fittings, roof-supported utilities and flush maintenance plates
retain the original solid envelopes, entrance and walking route.
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
    ('Rubber', (.012,.015,.018,1), 0, .78)]:
    m = bpy.data.materials.new(name); m.diffuse_color=color; m.use_nodes=True
    bsdf=m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=color
    bsdf.inputs['Metallic'].default_value=metal
    bsdf.inputs['Roughness'].default_value=rough
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

# Local origin is the center of the retained floor: world (8000,2250,0).
# Original solids: floor Z<=0, side faces X=+-1000, back Y=750, soffit Z=650.
# All fittings connect to these solids; no new collision or gameplay changes.
def rod(name,start,end,radius,material='Steel'):
    delta=Vector(end)-Vector(start)
    obj=cylinder(name,(Vector(start)+Vector(end))*.5,radius,delta.length,material,24)
    obj.rotation_mode='QUATERNION';obj.rotation_quaternion=delta.to_track_quat('Z','Y')
    return obj

for x in (-994,994):
    for y in (-520,0,520):
        box('Side wall bearing rib',(x,y,325),(16,24,652))
        box('Side rib footing',(x,y,2),(25,44,4))
        for yy in (-15,15): cylinder('Side foot anchor',(x,y+yy,4.5),1.6,2,vertices=6)
    box('Side perimeter beam web',(x,0,624),(5,1504,48))
    for z in (600,648): box('Side perimeter beam flange',(x,0,z),(24,1504,6))
for x in (-960,-480,0,480,960):
    box('Back wall bearing rib',(x,744,325),(24,16,652))
    box('Back rib footing',(x,744,2),(44,25,4))
    for xx in (-15,15): cylinder('Back foot anchor',(x+xx,744,4.5),1.6,2,vertices=6)
# The wide section connects the side wall ribs and overlaps the roof soffit.
for y in (-520,520,744):
    box('Roof beam web',(0,y,624),(2004,5,48))
    for z in (600,648): box('Roof beam flange',(0,y,z),(2004,24,6))
    for x in (-980,980):
        box('Roof beam connection plate',(x,y,624),(5,40,54),'Steel')
        for z in (609,639):
            rod('Beam connection stud',(x-4,y,z),(x+4,y,z),1.7)

# A replaceable lower wall lining meets the wall and is split by bearing ribs.
for x in (-720,-240,240,720):
    box('Back lining cassette',(x,747,235),(441,8,286))
    for xx in (-210,210):
        box('Lining edge seam',(x+xx,741.8,235),(3,3,280),'Steel',.12)
    for z in (99,371): box('Lining folded edge',(x,741, z),(441,4,5),'Steel',.2)
    for xx in (-160,0,160):
        box('Lining pressed reinforcing rib',(x+xx,741,235),(6,4,255),bevel=.3)
# Side liners stop well short of the doorway; avoid new protruding obstacles.
for x in (-998,998):
    for y in (-270,270):
        box('Side lining cassette',(x,y,210),(8,475,236))
        for z in (96,324): box('Side lining folded edge',(x-(5 if x>0 else -5),y,z),(4,475,5),'Steel')

# Ladder cable trays and clipped conductors are mechanically suspended.
for x in (-620,620):
    for xx in (-24,24): box('Tray side rail',(x+xx,0,575),(3,1340,10),'Steel')
    for y in range(-660,661,30): box('Tray cross rung',(x,y,571),(48,3,3),'Steel',.1)
    for xx in (-13,0,13): rod('Retained insulated cable',(x+xx,-670,574),(x+xx,670,574),1.8,'Rubber')
    for y in (-520,0,520):
        box('Tray support saddle',(x,y,568),(62,5,4),'Steel')
        for xx in (-29,29):
            rod('Tray suspension stud',(x+xx,y,569),(x+xx,y,650),.9)
            box('Ceiling hanger anchor',(x+xx,y,649),(8,8,4),'Steel')
            for z in (565.5,571): cylinder('Tray support captive nut',(x+xx,y,z),1.7,2,vertices=6)
    # End stops touch the rails and keep the cut cable ends contained.
    for y in (-670,670): box('Tray end restraint',(x,y,575),(51,3,10),'Steel')

# Back-wall service bus, enclosed at both ends and visibly bracketed.
for x in (-888,888):
    box('Wall junction enclosure',(x,737,470),(36,30,60))
    box('Enclosure removable face',(x,720,470),(30,5,52),'Steel')
rod('Back service conduit',(-888,725,470),(888,725,470),3.5)
for x in range(-800,801,200):
    box('Conduit wall bracket',(x,739,469),(7,25,5),'Steel')
    box('Conduit retaining strap',(x,725,470),(9,10,10),'Steel')

# Flush access plates have an inset dark gasket and visible captive fixings.
# Their highest point is 0.5 cm; the central four-meter passage is untouched.
for x in (-500,500):
    for y in (-520,-260,0,260,520):
        box('Floor access gasket',(x,y,0),(206,226,.5),'Rubber',.05)
        box('Floor maintenance plate',(x,y,.1),(198,218,.6),'Steel',.09)
        for xx in (-88,88):
            for yy in (-98,98): cylinder('Floor captive countersunk screw',(x+xx,y+yy,.3),1.5,.4,'Steel',6)
        # Two flush handles read as recessed dark steel without raised obstacles.
        for yy in (-76,76): box('Floor plate recessed pull',(x,y+yy,.41),(25,4,.06),'Rubber',.02)

bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'HallInterior.blend'))
bpy.ops.object.select_all(action='DESELECT')
copies=[]
for original in parts:
    obj=original.copy();obj.data=original.data.copy();bpy.context.collection.objects.link(obj)
    obj.select_set(True);copies.append(obj)
bpy.context.view_layer.objects.active=copies[0]
bpy.ops.object.convert(target='MESH');bpy.ops.object.join();obj=bpy.context.object
obj.name='SM_HallInterior'
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
fbx=ROOT/'SM_HallInterior.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
    axis_forward='X',axis_up='Z',apply_unit_scale=True,bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
spec=dict(schema='biella.hall_interior/v1',task_id='D17-01',status='GENERATED_DRAFT',
    provenance='Biella-authored geometry; retained Biella ServiceBay materials',
    map='/Game/Maps/BiellaOpenWorldMap',actor_label='D17_Hall_Interior',
    origin_cm=[8000,2250,0],collision='NoCollision',mesh=obj.name,
    source=Path(__file__).name,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    fbx=fbx.name,sha256=hashlib.sha256(fbx.read_bytes()).hexdigest(),
    blender=bpy.app.version_string,editable_parts=len(parts),triangles=len(obj.data.loop_triangles),
    bounds_min=minimum,bounds_max=maximum,material_slots=[m.name for m in obj.data.materials],
    export_y_reflected=True,outward_volume_preserved=True,
    retained_envelopes=dict(floor_top_cm=0,west_face_cm=-1000,east_face_cm=1000,back_face_cm=750,roof_soffit_cm=650),
    clear_route_min_cm=[-199,-850,.6],clear_route_max_cm=[199,680,220],
    floor_detail_max_height_cm=.5,
    scope='Fitted hall ribs, roof beams, supported cable trays and flush floor access plates; no changes to retained collision, light, materials or gameplay.')
(ROOT/'hall-interior.json').write_text(json.dumps(spec,indent=2)+'\n')
print('D17_HALL_INTERIOR_MESH COMPLETE',json.dumps(spec))
