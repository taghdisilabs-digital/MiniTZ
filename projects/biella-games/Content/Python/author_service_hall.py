"""Import fitted hall cladding into the existing map without editing any collider.
Native saved StaticMeshActor; fresh-process verify is read only. Run after the
original world authoring, as for the retained storm layer.
"""
import hashlib,json,os
from pathlib import Path
import unreal
PROJECT=Path(__file__).resolve().parents[2]
SPEC_PATH=PROJECT/'SourceAssets/Environment/service-hall.json'
SPEC=json.loads(SPEC_PATH.read_text())
VERIFY='-D17VerifyHall' in unreal.SystemLibrary.get_command_line()
LIB=unreal.EditorAssetLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
MESH=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) or unreal.get_default_object(unreal.StaticMeshEditorSubsystem)
LEVEL=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
WP=unreal.WorldPartitionBlueprintLibrary
ROOT='/Game/Environment/ServiceHall'
def require(ok,message):
    if not ok: raise RuntimeError('D17_HALL FAIL: '+message)
source=SPEC_PATH.parent/SPEC['fbx']
require(hashlib.sha256(source.read_bytes()).hexdigest()==SPEC['sha256'],'FBX differs')
require(hashlib.sha256((SPEC_PATH.parent/SPEC['source']).read_bytes()).hexdigest()==SPEC['source_sha256'],'Author source differs')
path=ROOT+'/'+SPEC['mesh']
mesh=LIB.load_asset(path) if LIB.does_asset_exist(path) else None
if mesh is None or (not VERIFY and LIB.get_metadata_tag(mesh,'D17.SourceSHA256')!=SPEC['sha256']):
    require(not VERIFY,'Saved mesh missing')
    task=unreal.AssetImportTask(); task.filename=str(source); task.destination_path=ROOT
    task.destination_name=SPEC['mesh']; task.automated=True; task.replace_existing=True; task.save=True
    options=unreal.FbxImportUI(); options.import_mesh=True; options.import_as_skeletal=False
    options.import_materials=False; options.import_textures=False
    options.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
    options.automated_import_should_detect_type=False
    options.static_mesh_import_data.combine_meshes=True
    options.static_mesh_import_data.auto_generate_collision=False
    task.options=options; TOOLS.import_asset_tasks([task]); mesh=LIB.load_asset(path)
require(isinstance(mesh,unreal.StaticMesh),'Mesh import failed')
slots=[str(m.get_editor_property('imported_material_slot_name')) for m in mesh.get_editor_property('static_materials')]
require(set(slots)==set(SPEC['material_slots']),'Material slot mismatch')
for i,name in enumerate(slots):
    material=LIB.load_asset('/Game/Environment/ServiceBay/MI_Service'+name)
    require(material is not None,'Retained physical material missing')
    if not VERIFY: mesh.set_material(i,material)
    require(mesh.get_material(i)==material,'Material readback differs')
if not VERIFY:
    MESH.remove_collisions(mesh)
    LIB.set_metadata_tag(mesh,'D17.SourceSHA256',SPEC['sha256'])
    LIB.set_metadata_tag(mesh,'D17.Status','GENERATED_DRAFT')
    require(LIB.save_loaded_asset(mesh,only_if_is_dirty=False),'Mesh save failed')
require(LIB.get_metadata_tag(mesh,'D17.SourceSHA256')==SPEC['sha256'],'Mesh provenance differs')
require(MESH.get_simple_collision_count(mesh)==0,'Visual skin must not replace building collision')
bounds=mesh.get_bounds()
actual_min=[getattr(bounds.origin,k)-getattr(bounds.box_extent,k) for k in ('x','y','z')]
actual_max=[getattr(bounds.origin,k)+getattr(bounds.box_extent,k) for k in ('x','y','z')]
require(max(abs(a-b) for a,b in zip(actual_min,SPEC['bounds_min']))<.025,'Imported minimum reflected/scaled')
require(max(abs(a-b) for a,b in zip(actual_max,SPEC['bounds_max']))<.025,'Imported maximum reflected/scaled')
require(mesh.get_num_triangles(0)==SPEC['triangles'],'Triangle readback differs')
require(LEVEL.load_level(SPEC['map']),'Canonical map missing')
WP.load_actors([d.guid for d in WP.get_actor_descs()])
existing={a.get_actor_label():a for a in ACTORS.get_all_level_actors()}
before={label:a.get_path_name() for label,a in existing.items()}
# Explicitly bind the supporting solid envelopes and clear four-meter entrance.
expected={'D02_Interior_West':([6975,2250,300],[.5,15,6]),
'D02_Interior_East':([9025,2250,300],[.5,15,6]),
'D02_Interior_Back':([8000,3025,300],[21,.5,6]),
'D02_Interior_DoorWest':([7400,1500,300],[8,.5,6]),
'D02_Interior_DoorEast':([8600,1500,300],[8,.5,6]),
'D02_Interior_Roof':([8000,2250,675],[21,15.5,.5])}
supports={}
surface=LIB.load_asset('/Game/Environment/ServiceBay/MI_ServicePaint')
require(surface is not None,'Retained weathered coating missing')
for label,(location,scale) in expected.items():
    a=existing.get(label); require(isinstance(a,unreal.StaticMeshActor),'Supporting building missing')
    component=a.static_mesh_component
    require(str(component.get_collision_profile_name())=='BlockAll','Building collider changed')
    for actual,values in ((a.get_actor_location(),location),(a.get_actor_scale3d(),scale)):
        require(max(abs(getattr(actual,k)-v) for k,v in zip(('x','y','z'),values))<.001,'Building envelope changed')
    require(component.get_editor_property('static_mesh').get_path_name()=='/Engine/BasicShapes/Cube.Cube','Original collider mesh changed')
    # The envelope is also visible at the entrance reveals and soffit. Coat its
    # existing faces rather than adding thickness inside the four-meter opening.
    # The retained world-space PBR material matches the fitted outer cassettes.
    if not VERIFY:
        a.modify(); component.modify()
        component.set_editor_property('override_materials',[surface])
    require(component.get_material(0)==surface,'Entrance/interior surface binding differs')
    supports[label]=dict(path=a.get_path_name(),location_cm=location,scale=scale,collision='BlockAll',
                        material=component.get_material(0).get_path_name())
a=existing.get(SPEC['actor_label'])
if a is None:
    require(not VERIFY,'Saved visual actor missing')
    a=ACTORS.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*SPEC['origin_cm']))
    require(a is not None,'Cannot spawn visual actor'); a.set_actor_label(SPEC['actor_label'])
if not VERIFY:
    a.set_actor_location(unreal.Vector(*SPEC['origin_cm']),False,False)
    a.set_actor_scale3d(unreal.Vector(1,1,1))
    a.set_editor_property('is_spatially_loaded',True)
    a.set_editor_property('enable_auto_lod_generation',False)
    a.set_editor_property('tags',[unreal.Name('D17HallVisual')])
    a.static_mesh_component.set_static_mesh(mesh)
    a.static_mesh_component.set_mobility(unreal.ComponentMobility.STATIC)
    a.static_mesh_component.set_collision_profile_name('NoCollision')
    require(LEVEL.save_current_level(),'Map save failed')
    require(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True),'Package save failed')
require(a.static_mesh_component.get_editor_property('static_mesh')==mesh,'Saved mesh binding differs')
require(str(a.static_mesh_component.get_collision_profile_name())=='NoCollision','Visual actor gained collision')
require(max(abs(getattr(a.get_actor_location(),k)-v) for k,v in zip(('x','y','z'),SPEC['origin_cm']))<.001,'Saved placement differs')
for label,path_before in before.items(): require(existing[label].get_path_name()==path_before,'Preexisting actor identity changed')
descs={str(d.label):d for d in WP.get_actor_descs()}
report=dict(task_id='D17-01',result='PASS',status='GENERATED_DRAFT',read_only=VERIFY,
    spec_sha256=hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),map=SPEC['map'],
    mesh=mesh.get_path_name(),triangles=mesh.get_num_triangles(0),bounds_min=actual_min,bounds_max=actual_max,
    materials=slots,collision_boxes=0,supports=supports,preexisting_actor_identities_preserved=True,
    edited_actor_paths={**{label:existing[label].get_path_name() for label in expected},
                       SPEC['actor_label']:a.get_path_name()},
    edited_actor_packages=[str(descs[label].actor_package) for label in [SPEC['actor_label'],*expected]],
    surface_scope='Existing entrance reveals, inner wall faces and roof soffit; no geometry or collision changes',
    scope='Fitted visual skin and matching weathered envelope coating; preserved original collision and entrance; no gameplay acceptance')
Path(os.environ['BIELLA_D17_HALL_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
print('D17_HALL COMPLETE')
