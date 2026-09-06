"""Editable D03 cockpit steering wheel, centimeter mesh with X steering axis."""
import bpy, math
from mathutils import Vector
from pathlib import Path
p=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
parts=[]
bpy.ops.mesh.primitive_torus_add(major_radius=14,minor_radius=1.35,major_segments=48,minor_segments=10,rotation=(0,math.pi/2,0));parts.append(bpy.context.object)
for angle in (0,2*math.pi/3,4*math.pi/3):
 end=Vector((0,12*math.sin(angle),12*math.cos(angle)));bpy.ops.mesh.primitive_cube_add(size=1,location=end/2)
 o=bpy.context.object;o.dimensions=(1.3,1.8,end.length);o.rotation_euler=end.to_track_quat('Z','Y').to_euler();parts.append(o)
bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=3,depth=3,rotation=(0,math.pi/2,0));parts.append(bpy.context.object)
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();o=bpy.context.object;o.name='SM_DriverSteeringWheel'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
for f in o.data.polygons:f.use_smooth=len(f.vertices)==4
bpy.ops.wm.save_as_mainfile(filepath=str(p/'DriverSteeringWheel.blend'))
bpy.ops.export_scene.fbx(filepath=str(p/'DriverSteeringWheel.fbx'),use_selection=True,object_types={'MESH'},axis_forward='X',axis_up='Z',apply_unit_scale=True,bake_anim=False,add_leaf_bones=False)
