"""D03 editable industrial street buildings. Run with Blender --background --python.

Author in centimeters, bevel in physical space, then normalize each mesh to the
existing 100 cm cube envelope. Existing world actors retain their transforms.
No downloaded/generated third-party geometry or textures are used.
"""
import hashlib
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = .01
bpy.context.preferences.filepaths.save_version = 0
MATERIALS = []
for name, color, rough, metal in [
    ('Concrete', (.23, .28, .30, 1), .76, 0),
    ('PaintedFrame', (.075, .10, .105, 1), .38, 0),
    ('SealedGlazing', (.032, .052, .065, 1), .19, 0),
    ('Zinc', (.40, .43, .45, 1), .34, 1),
    ('Terracotta', (.29, .105, .058, 1), .84, 0),
]:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    MATERIALS.append(mat)

records = []
for region in range(6):
    height = 1200 + region * 100
    parts = []
    def box(name, center, size, material=0):
        # Disjoint closed parts are deliberate: no alpha cards or tiny triangles.
        bpy.ops.mesh.primitive_cube_add(size=1, location=center)
        obj = bpy.context.object
        obj.name = name
        obj.dimensions = size
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(MATERIALS[material])
        parts.append(obj)

    # Exact outer dimensions are retained by the base and roof envelope.
    box('Foundation', (0, 0, -height/2+35), (1600, 1400, 70))
    box('RecessedCore', (0, 0, -5), (1536, 1336, height-130))
    box('RoofSlab', (0, 0, height/2-110), (1600, 1400, 32))
    for y in (-684, 684):
        box('RoofParapet', (0, y, height/2-54), (1600, 32, 108))
        box('ZincCoping', (0, y, height/2-3), (1600, 32, 6), 3)
    for x in (-784, 784):
        box('RoofParapetReturn', (x, 0, height/2-54), (32, 1336, 108))
        box('ZincCopingReturn', (x, 0, height/2-3), (32, 1336, 6), 3)
    floors = 3 if region < 3 else 4
    pitch = (height-220)/floors
    for side in (-1, 1):
        # Front and rear faces carry real jamb/reveal/sill geometry.
        for floor in range(floors):
            z = -height/2 + 90 + pitch*(floor+.5)
            box('FloorBand', (0, side*682, z-pitch*.49), (1560, 28, 20), 3)
            for col in range(5):
                x = (col-2)*300
                window_h = min(205, pitch-62)
                if floor == 0 and col == 2:
                    window_h = min(255, pitch-42)
                # Glazing is sealed opaque reflective glazing, not a fake room.
                box('SealedWindow', (x, side*673, z), (222, 10, window_h), 2)
                for dx in (-118, 118):
                    box('ConcreteJamb', (x+dx, side*680, z), (18, 30, window_h+34))
                for dz in (-window_h/2-10, window_h/2+10):
                    box('WindowLintelSill', (x, side*682, z+dz), (254, 32, 20))
                for dx in (-110, 0, 110):
                    box('WindowMullion', (x+dx, side*685, z), (6, 12, window_h), 1)
                box('WindowTransom', (x, side*685, z+window_h*.18), (220, 12, 6), 1)
                box('SpandrelPanel', (x, side*680, z-window_h/2-28), (218, 22, 18), 4)
        for x in (-760, -450, -150, 150, 450, 760):
            box('FacadePier', (x, side*682, -60), (30, 32, height-200))
        box('EntranceCanopy', (0, side*670, -height/2+pitch+36), (300, 60, 14), 3)
    # End walls: panel seams, rust-red brick courses, downpipes.
    for side in (-1, 1):
        for j in range(10):
            z = -height/2+100+j*(height-240)/10
            box('EndWallCourse', (side*775, 0, z), (18, 1336, 12), 4)
        for y in (-630, -210, 210, 630):
            box('EndWallPier', (side*781, y, -55), (30, 22, height-200))
        box('Downpipe', (side*790, -620, -50), (14, 18, height-200), 3)
    for x in (-420, 420):
        box('RoofVent', (x, 0, height/2-60), (190, 240, 60), 1)
        for j in range(8):
            box('VentLouvre', (x, -105+j*30, height/2-27), (198, 12, 8), 3)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = f'SM_StreetBlock_{region:02d}'
    # Place origin at the original building center before anisotropic normalization.
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bevel = obj.modifiers.new('PhysicalEdgeBevel_1cm', 'BEVEL')
    bevel.width = 1.0
    bevel.segments = 3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    # Smooth only bevel polygons; large architectural faces retain flat normals.
    for polygon in obj.data.polygons:
        polygon.use_smooth = polygon.area < 100
    for vertex in obj.data.vertices:
        vertex.co.x /= 16
        vertex.co.y /= 14
        vertex.co.z /= height/100
    obj.data.update()
    bpy.context.view_layer.update()
    obj['D03.Status'] = 'GENERATED_DRAFT'
    obj['D03.PhysicalDimensionsCm'] = [1600, 1400, height]
    obj['D03.AuthoringSource'] = 'build_street_blocks.py'
    points = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    minimum = [min(v[i] for v in points) for i in range(3)]
    maximum = [max(v[i] for v in points) for i in range(3)]
    assert all(abs(a+50) < .002 for a in minimum), minimum
    assert all(abs(a-50) < .002 for a in maximum), maximum
    obj.data.calc_loop_triangles()
    target = ROOT / (obj.name + '.fbx')
    bpy.ops.export_scene.fbx(filepath=str(target), use_selection=True,
        object_types={'MESH'}, axis_forward='X', axis_up='Z', apply_unit_scale=True,
        bake_anim=False, add_leaf_bones=False, mesh_smooth_type='FACE')
    records.append(dict(mesh=obj.name, physical_dimensions_cm=[1600, 1400, height],
        normalized_min=minimum, normalized_max=maximum, triangles=len(obj.data.loop_triangles),
        vertices=len(obj.data.vertices), material_slots=[m.name for m in obj.data.materials],
        fbx=target.name, sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    # Arrange editable sources side by side in the Blender file (FBX origin remains zero).
    obj.location.x = region*130

bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'StreetBlocks.blend'))
(ROOT / 'street-blocks.json').write_text(json.dumps(dict(schema='biella.street_blocks/v1',
    status='GENERATED_DRAFT', source='build_street_blocks.py',
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    provenance='Project-authored parametric mesh, Blender; no third-party geometry or textures',
    blender=bpy.app.version_string, assets=records), indent=2)+'\n')
print('D03_STREET_BLOCKS COMPLETE')
