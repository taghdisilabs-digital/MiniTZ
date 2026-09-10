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
                                 ('Rubber', (.012,.015,.018,1),0,.78),
                                 ('Lamp', (1,.62,.28,1),0,.3),
                                 ('Growth', (.16,.007,.014,1),0,.34),
                                 ('Vein', (.42,.006,.016,1),0,.28)]:
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

# Three grounded service portals frame the ascent without narrowing the
# retained four-metre deck. All solids have explicit native box proxies.
# Five metres of overhead clearance leaves the production camera unobstructed.
fixtures, structure_colliders = [], []
for i, y in enumerate((1150, 2250, 3250)):
    floor = min(400, (y-1000)*.2)
    top = floor+500
    for side in (-1, 1):
        x = 10000+side*260
        box('Portal grounded upright', (x,y,top/2), (22,28,top), 'Paint', .8)
        box('Portal anchored shoe', (x,y,5), (62,68,10), 'Steel', .7)
        structure_colliders.append(dict(label='D17_TerracePortal_%d_%s'%(i,'W' if side<0 else 'E'),
                                       center=[x,y,top/2],size=[22,28,top]))
        for dx in (-23,23):
            for dy in (-26,26): rod('Portal foundation anchor', (x+dx,y+dy,10),(x+dx,y+dy,16),2.8,vertices=6)
        # Bolted knee plates and rain-proof cable runs share the same support.
        rod('Portal knee brace',(x,y,top-85),(x-side*90,y,top-12),4,'Steel')
        for z in (top-120,top-40):
            box('Portal bolted joint plate',(x,y-16,z),(32,4,34),'Steel',.3)
            for dx in (-10,10):rod('Portal joint fixing',(x+dx,y-19,z),(x+dx,y-21,z),2,vertices=6)
    box('Portal boxed crosshead',(10000,y,top),(542,28,22),'Paint',.8)
    box('Portal weathered coping',(10000,y,top+13),(554,40,4),'Steel',.3)
    structure_colliders.append(dict(label='D17_TerracePortalBeam_%d'%i,center=[10000,y,top],size=[542,28,22]))
    for x in (9930,10070):rod('Luminaire suspension',(x,y,top-11),(x,y,top-31),1.8)
    box('Supported sealed luminaire housing',(10000,y,top-37),(180,34,12),'Paint',.5)
    box('Warm opal luminaire lens',(10000,y,top-44),(168,26,2),'Lamp',.3)
    for x in range(9920,10081,20):rod('Luminaire protective cage',(x,y-17,top-45),(x,y+17,top-45),.6)
    fixtures.append(dict(label='D17_TerracePractical_%d'%i,position=[10000,y,top-48],
                         lumens=16000,attenuation_cm=1050,source_radius_cm=14,source_length_cm=145,
                         color_linear=[1,.62,.28,1]))
# Layered conduits and ventilated guards run outside both retained ramp edges.
# Side panels have matching solid collision; their nearest face is 2.4 m from
# the centre, leaving 40 cm between dressing and the original ramp edge.
for side in (-1,1):
    x=10000+side*258
    for j in range(10):
        y=1250+j*200; floor=min(400,(y-1000)*.2)
        box('Service guard folded cassette',(x,y,floor+115),(26,188,170),'Paint',.7)
        structure_colliders.append(dict(label='D17_TerraceGuard_%s_%02d'%('W' if side<0 else 'E',j),
                                       center=[x,y,floor+115],size=[26,188,170]))
        for zoff in (45,80,115,150,185):
            box('Guard rain louvre',(x-side*15,y,floor+zoff),(5,174,4),'Steel',.25)
        for dy in (-82,82):
            box('Guard returned seam',(x-side*15,y+dy,floor+115),(4,3,162),'Steel',.15)
    for dz,r in ((240,9),(280,5),(305,3)):
        a=(x,1150,30+dz); b=(x,3000,400+dz)
        rod('Ascending industrial utility pipe',a,b,r,'Paint',20)
        rod('Level terrace utility pipe',b,(x,3900,400+dz),r,'Paint',20)
        for y in (1200,1800,2400,2950,3500,3850):
            z=min(400,(y-1000)*.2)+dz
            rod('Pipe coupling sleeve',(x,y-5,z-1),(x,y+5,z+1),r+1.5,'Steel',20)
# A supported rear service screen gives the summit a spatial destination.
# It seats on the retained parapet, with ribbed panels and a defined coping.
for i in range(9):
    x=9200+i*200
    box('Rear service screen panel',(x,4008,720),(192,12,396),'Paint',.6)
    box('Rear screen grounded rib',(x-98,4008,460),(12,28,920),'Steel',.4)
    for z in range(560,900,42):box('Rear screen folded louvre',(x,3998,z),(176,10,7),'Steel',.3)
    structure_colliders.append(dict(label='D17_TerraceRearScreen_%02d'%i,center=[x,4008,720],size=[200,28,400]))
box('Rear screen top coping',(10000,4008,923),(1808,42,6),'Steel',.5)

# Tissue is anchored to engineered joints, with tapering branch topology and
# a separate wet red surface/emissive vascular strand; no floating spheres.
def tissue(name, points, radii, material='Growth'):
    verts,faces=[],[]; sides=10
    for i,point in enumerate(points):
        direction=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)])
        rotation=direction.to_track_quat('Z','Y')
        for j in range(sides):
            angle=j*math.tau/sides
            v=Vector(point)-ORIGIN+rotation@Vector((math.cos(angle)*radii[i],math.sin(angle)*radii[i],0))
            verts.append(v)
        if i:
            for j in range(sides):
                a=(i-1)*sides+j;b=(i-1)*sides+(j+1)%sides
                faces.append((a,b,b+sides,a+sides))
    faces += [tuple(reversed(range(sides))),tuple(range((len(points)-1)*sides,len(points)*sides))]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    mesh.materials.append(materials[material])
    for face in mesh.polygons:face.use_smooth=True
    parts.append(obj)
for side in (-1,1):
    x=10000+side*241
    for branch in range(7):
        y0=1220+branch*330
        points=[];radii=[]
        for k in range(18):
            y=y0+k*14;z=min(400,(y-1000)*.2)+45+k*9+12*math.sin(k*.47+branch)
            points.append((x+side*(5+7*math.sin(k*.42+branch)),y,z))
            radii.append(2+7*math.sin(math.pi*(k+1)/20)**2)
        tissue('Rooted vascular growth',points,radii)
        tissue('Red bioluminescent vein',[(p[0]-side*7,p[1],p[2]+2) for p in points],[1.25]*len(points),'Vein')
        for offset in (4,9,13):
            a=Vector(points[offset]);fork=[a+Vector((-side*3*k,k*7,k*4)) for k in range(7)]
            tissue('Tapered tissue branch',fork,[4*(1-k/7) for k in range(7)])
# Rear-screen tissue grows out of joints, above the parapet collision line.
for j in range(5):
    x0=9340+j*310
    points=[(x0+80*math.sin(k*.35+j),3986,510+k*20) for k in range(20)]
    tissue('Screen invading tissue root',points,[4+9*math.sin(math.pi*k/21)**2 for k in range(20)])
    tissue('Screen vascular seam',[(x,y-10,z) for x,y,z in points],[1.5]*20,'Vein')

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
assert -45 < minimum[2] < 1 and 925 <= maximum[2] <= 927, (minimum,maximum)
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
    structure_colliders=structure_colliders,practical_lights=fixtures,
    source=Path(__file__).name,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    blender=bpy.app.version_string,editable_parts=len(parts),mesh=obj.name,fbx=path.name,
    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),triangles=len(obj.data.loop_triangles),
    bounds_min=minimum,bounds_max=maximum,export_y_reflected=True,outward_volume_preserved=True,
    material_slots=[m.name for m in obj.data.materials],
    limits=['Must be imported, collision-bound and raw-runtime qualified before route acceptance',
            'No final environment, character, HUD or whole-slice visual acceptance'])
(ROOT/'terrace-route.json').write_text(json.dumps(spec,indent=2)+'\n')
print('D17_TERRACE_ROUTE_MESH COMPLETE',json.dumps(spec))
