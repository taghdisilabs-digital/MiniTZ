"""Biella service-bay metalwork, authored in centimeters. Blender background script.

Preserves the existing collision envelopes. Panel FBXs are normalized to the
native component's 100cm unit bounds; fixed metalwork is exported at real scale.
The .blend retains named, individually editable parts and bevel modifiers.
No downloaded mesh or texture inputs.
"""
import hashlib
import json
import math
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = .01
bpy.context.preferences.filepaths.save_version = 0
materials = {}
for name, color, roughness, metallic in [
    ('Paint', (.055, .074, .08, 1), .48, 0),
    ('Steel', (.31, .34, .36, 1), .32, 1),
    ('Rubber', (.012, .015, .018, 1), .78, 0),
    ('Lamp', (1, .62, .28, 1), .3, 0),
    ('Growth', (.055, .004, .008, 1), .34, 0),
    ('Vein', (.42, .006, .016, 1), .28, 0),
]:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    materials[name] = mat

parts = []
records = []


def finish(obj, name, material, bevel):
    obj.name = name
    obj.data.materials.append(materials[material])
    if bevel:
        modifier = obj.modifiers.new('Manufactured edge radius (cm)', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 3
    parts.append(obj)
    return obj


def box(name, at, size, material='Paint', bevel=.35):
    bpy.ops.mesh.primitive_cube_add(size=1, location=at)
    obj = bpy.context.object
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, material, bevel)


def bolt(at, axis='X', radius=1.15, depth=.8):
    rotation = (0, math.pi/2, 0) if axis == 'X' else (0, 0, 0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=radius, depth=depth,
                                      location=at, rotation=rotation)
    return finish(bpy.context.object, 'Captive hex bolt', 'Steel', .12)


def strand(name, points, radius, material='Growth'):
    """Editable tapered tissue following an explicit structural contact path."""
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 6
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    curve.use_fill_caps = True
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    for i, (point, position) in enumerate(zip(spline.bezier_points, points)):
        point.co = position
        point.radius = max(.06, (1-i/(len(points)-1))**.6)
        point.handle_left_type = point.handle_right_type = 'AUTO'
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, material, 0)


def export(name, envelope=None):
    # Export evaluated copies. The original named parts stay editable in .blend.
    copies = []
    bpy.ops.object.select_all(action='DESELECT')
    for original in parts:
        duplicate = original.copy()
        duplicate.data = original.data.copy()
        bpy.context.collection.objects.link(duplicate)
        duplicate.select_set(True)
        copies.append(duplicate)
    bpy.context.view_layer.objects.active = copies[0]
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    if envelope:
        for vertex in obj.data.vertices:
            for axis in range(3):
                vertex.co[axis] *= 100 / envelope[axis]
    obj.data.update()
    bpy.context.view_layer.update()
    bounds = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    minimum = [min(v[i] for v in bounds) for i in range(3)]
    maximum = [max(v[i] for v in bounds) for i in range(3)]
    if envelope:
        assert all(abs(v+50) < .001 for v in minimum), minimum
        assert all(abs(v-50) < .001 for v in maximum), maximum
    obj.data.calc_loop_triangles()
    path = ROOT / (name+'.fbx')
    # Authored coordinates are the native actor's coordinates. Unreal's FBX
    # import reflects Y when converting the right-handed FBX mesh. Compensate
    # on the export copy only, preserving the editable scene and outward faces.
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    volume_before = mesh.calc_volume(signed=True)
    for vertex in mesh.verts:
        vertex.co.y *= -1
    bmesh.ops.reverse_faces(mesh, faces=list(mesh.faces))
    volume_after = mesh.calc_volume(signed=True)
    assert abs(volume_before-volume_after) < max(1, abs(volume_before))*1e-5
    mesh.to_mesh(obj.data)
    mesh.free()
    obj.data.update()
    obj.data.calc_loop_triangles()
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True,
        object_types={'MESH'}, axis_forward='X', axis_up='Z', apply_unit_scale=True,
        bake_anim=False, add_leaf_bones=False, mesh_smooth_type='FACE')
    records.append(dict(mesh=name, fbx=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        triangles=len(obj.data.loop_triangles), bounds_min=minimum, bounds_max=maximum,
        export_y_reflected=True, outward_volume_preserved=True,
        normalized_envelope_cm=envelope, material_slots=[m.name for m in obj.data.materials]))
    bpy.data.objects.remove(obj, do_unlink=True)
    collection = bpy.data.collections.new(name+' editable components')
    bpy.context.scene.collection.children.link(collection)
    for original in parts:
        for old in list(original.users_collection):
            old.objects.unlink(original)
        collection.objects.link(original)
    parts.clear()


for width in (120, 240):
    # An inset folded sheet and edge channels occupy exactly the existing
    # 12 x width x 210cm body. Real ribs catch light from gameplay distance.
    box('Folded steel backing', (3, 0, 0), (6, width, 210), bevel=.3)
    for y in (-width/2+3, width/2-3):
        box('Edge channel', (0, y, 0), (12, 6, 210), 'Steel', .4)
    for z in (-101, 101):
        box('Folded end cap', (0, 0, z), (12, width, 8), 'Steel', .4)
    for y in range(-int(width/2)+18, int(width/2)-10, 24):
        box('Pressed reinforcing rib', (-2.8, y, 0), (5.6, 6, 188), bevel=.8)
    for y in (-width/2+11, width/2-11):
        for z in (-88, 88):
            bolt((-4.8, y, z))
    box('Inset service label plate', (-.8, 0, 50), (2.4, 40, 20), 'Rubber', .4)
    export('SM_ServicePanel'+str(width), [12, width, 210])

# Fixed dressing respects existing post/header/rail/cabinet collision. It does
# not add a traversable route or narrow an existing player passage.
for side in (-1, 1):
    y = side*255
    for x in (-10, 10):
        box('Column flange', (x, y, 115), (8, 28, 230), 'Steel')
    box('Column web', (0, y, 115), (12, 7, 230), 'Paint')
    for z in (3, 227):
        box('Column end plate', (0, y, z), (28, 28, 6), 'Steel')
        for dy in (-9, 9):
            bolt((-11, y+dy, z+3), 'Z', .9, .7)
    box('Low containment rail', (270, side*235, 35), (520, 14, 60), 'Paint', .6)
    box('Rail top wear strip', (270, side*235, 63), (515, 13, 4), 'Steel', .3)
    for x in (30, 250, 490):
        box('Rail fixing shoe', (x, side*235, 10), (24, 14, 10), 'Steel', .2)

box('Header spine', (0, 0, 245), (30, 550, 30), 'Paint', .8)
for y in (-230, -120, 120, 230):
    bolt((-15.4, y, 245), radius=1.5, depth=1.3)
box('Control cabinet carcass', (-170, -310, 80), (65, 65, 160), 'Paint', 1.2)
box('Recessed cabinet door', (-202.6, -310, 85), (.8, 56, 135), 'Rubber', .2)
# Existing switch at (-208,-310,115) remains fully visible and first in the
# interact trace. Door trim/vents are below it, never placed across the switch.
for z in (20, 29, 38, 47, 56):
    box('Cabinet louvre', (-203.8, -310, z), (1.6, 44, 3), 'Steel', .4)
for z in (35, 135):
    box('Hinge', (-203.5, -338, z), (2, 5, 12), 'Steel')

# A physical fascia backs the formerly floating sign; small warm lamps have
# housings, diffusers and supports. Their emission is backed by runtime lights.
box('Safety fascia', (-15.5, 0, 245), (2, 175, 25), 'Rubber', .5)
for y in (-170, 170):
    box('Lamp bracket', (-8, y, 254), (18, 10, 12), 'Steel', .4)
    box('Lamp housing', (-22, y, 247), (26, 48, 14), 'Paint', 1)
    box('Lamp diffuser', (-22, y, 239.8), (21, 40, 1.6), 'Lamp', .5)
    for dy in (-15, 0, 15):
        box('Lamp safety cage', (-22, y+dy, 238.5), (24, 1.5, 1.5), 'Steel', .3)

# Organic invasion follows the outside containment rail into the column and
# header. It is attached dressing, not a new obstacle or damage mechanic.
# The cabinet/switch side and movable panel surfaces remain clear. Named
# tapered Bezier splines survive in the editable blend; only FBX copies bake.
trunk = [(510,246,9),(415,247,16),(310,246,29),(205,246,42),
         (95,246,52),(8,271,82),(9,271,145),(8,272,210),(9,275,256)]
strand('Rail-to-column invaded tissue', trunk, 11)
strand('Header takeover', [(9,271,145),(16,273,212),(13,272,258),
                          (8,205,263),(9,130,263),(9,65,261)], 6.8)
for index, x in enumerate((430,350,270,190,110)):
    z = 12+(510-x)*.1
    strand('Anchored root fan %02d'%index,
           [(x,247,z),(x+8,253,12),(x+25,275,2.8),
            (x+43,305+index*5,1.4),(x+78,320+index*3,.8)], 5.8-index*.5)
    strand('Rail climbing branch %02d'%index,
           [(x,247,z),(x-17,248,45),(x-38,242,64),
            (x-66,230,66),(x-90,227,65)], 4.5)
    # Narrow luminous capillaries stay on the tissue's exposed outer face.
    strand('Red capillary %02d'%index,
           [(x+10,254,z+3),(x-12,254,z+10),(x-40,250,49),
            (x-63,239,68),(x-87,229,66)], .85, 'Vein')
for index, z in enumerate((80,115,150,185)):
    strand('Column attachment %02d'%index,
           [(9,274,z),(15,276,z+13),(18,262,z+29),
            (16,249,z+41),(14,243,z+51)], 3.6)
strand('Column vascular seam', [(9,280,70),(11,280,108),(10,279,153),
                               (10,279,207),(11,277,250),(9,219,266)], 1.2, 'Vein')
export('SM_ServiceBayMetalwork')

bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'ServiceBay.blend'))
(ROOT/'service-bay.json').write_text(json.dumps(dict(schema='biella.service_bay.art/v1',
    status='GENERATED_DRAFT', source=Path(__file__).name,
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    provenance='Biella-authored mesh; no third-party geometry or textures',
    blender=bpy.app.version_string, assets=records), indent=2)+'\n')
print('D17_SERVICE_BAY_MESH COMPLETE')
