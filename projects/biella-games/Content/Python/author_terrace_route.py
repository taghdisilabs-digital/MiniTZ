"""Install the fitted terrace skin and six matching column colliders.

Preserve existing ramp, floor, parapet transforms and collisions. A fresh
process verifies saved mesh/material/actor bytes without modifying the map.
"""
import hashlib, json, os
from pathlib import Path
import unreal

PROJECT=Path(__file__).resolve().parents[2]
SPEC_PATH=PROJECT/'SourceAssets/Environment/terrace-route.json'
SPEC=json.loads(SPEC_PATH.read_text())
VERIFY='-D17VerifyTerraceRoute' in unreal.SystemLibrary.get_command_line()
LIB=unreal.EditorAssetLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
MESH=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) or unreal.get_default_object(unreal.StaticMeshEditorSubsystem)
LEVEL=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem) or unreal.get_default_object(unreal.LevelEditorSubsystem)
ACTORS=unreal.get_editor_subsystem(unreal.EditorActorSubsystem) or unreal.get_default_object(unreal.EditorActorSubsystem)
WP=unreal.WorldPartitionBlueprintLibrary
ROOT='/Game/Environment/TerraceRoute'

def require(ok,message):
    if not ok: raise RuntimeError('D17_TERRACE_ROUTE FAIL: '+message)

def vector_matches(actual,expected):
    return max(abs(getattr(actual,k)-v) for k,v in zip(('x','y','z'),expected))<.025

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
require(set(slots)==set(SPEC['material_slots']),'Material slots differ')
for i,name in enumerate(slots):
    material=LIB.load_asset('/Game/Environment/ServiceBay/MI_Service'+name)
    require(material is not None,'Retained PBR material missing')
    if not VERIFY: mesh.set_material(i,material)
    require(mesh.get_material(i)==material,'Material binding differs')
if not VERIFY:
    MESH.remove_collisions(mesh)
    LIB.set_metadata_tag(mesh,'D17.SourceSHA256',SPEC['sha256'])
    LIB.set_metadata_tag(mesh,'D17.Status','GENERATED_DRAFT')
    require(LIB.save_loaded_asset(mesh,only_if_is_dirty=False),'Mesh save failed')
require(LIB.get_metadata_tag(mesh,'D17.SourceSHA256')==SPEC['sha256'],'Mesh provenance differs')
require(MESH.get_simple_collision_count(mesh)==0,'Skin acquired unintended collision')
bounds=mesh.get_bounds()
minimum=[getattr(bounds.origin,k)-getattr(bounds.box_extent,k) for k in 'xyz']
maximum=[getattr(bounds.origin,k)+getattr(bounds.box_extent,k) for k in 'xyz']
require(max(abs(a-b) for a,b in zip(minimum,SPEC['bounds_min']))<.025,'Import reflected/scaled minimum')
require(max(abs(a-b) for a,b in zip(maximum,SPEC['bounds_max']))<.025,'Import reflected/scaled maximum')
require(mesh.get_num_triangles(0)==SPEC['triangles'],'Imported triangle count differs')
require(LEVEL.load_level(SPEC['map']),'Canonical map load failed')
WP.load_actors([d.guid for d in WP.get_actor_descs()])
existing={a.get_actor_label():a for a in ACTORS.get_all_level_actors()}
preserved={}
for label in ('D02_Terrace_Ramp','D02_Terrace_Floor','D02_Terrace_BackRail','D02_Terrace_WestRail','D02_Terrace_EastRail'):
    a=existing.get(label)
    require(isinstance(a,unreal.StaticMeshActor),'Existing terrace collider missing: '+label)
    require(str(a.static_mesh_component.get_collision_profile_name())=='BlockAll','Existing collision changed')
    preserved[label]=dict(path=a.get_path_name(),transform=dict(location=[getattr(a.get_actor_location(),k) for k in 'xyz'],
                                         rotation=[getattr(a.get_actor_transform().rotation,k) for k in 'xyzw'],
                                         scale=[getattr(a.get_actor_scale3d(),k) for k in 'xyz']),
                          mesh=a.static_mesh_component.static_mesh.get_path_name(),collision='BlockAll')
edited={}

def place(label,location,scale,native_mesh,profile,hidden=False):
    a=existing.get(label)
    if a is None:
        require(not VERIFY,'Saved actor missing: '+label)
        a=ACTORS.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*location))
        a.set_actor_label(label)
    if not VERIFY:
        a.set_actor_location(unreal.Vector(*location),False,False)
        a.set_actor_scale3d(unreal.Vector(*scale))
        a.set_actor_hidden_in_game(hidden)
        a.set_editor_property('is_spatially_loaded',True)
        a.set_editor_property('enable_auto_lod_generation',False)
        a.set_editor_property('tags',[unreal.Name('D17TerraceRoute')])
        a.static_mesh_component.set_static_mesh(native_mesh)
        a.static_mesh_component.set_mobility(unreal.ComponentMobility.STATIC)
        a.static_mesh_component.set_collision_profile_name(profile)
    require(vector_matches(a.get_actor_location(),location),'Actor location differs: '+label)
    require(vector_matches(a.get_actor_scale3d(),scale),'Actor scale differs: '+label)
    require(a.static_mesh_component.static_mesh==native_mesh,'Actor mesh differs: '+label)
    require(str(a.static_mesh_component.get_collision_profile_name())==profile,'Actor collision differs: '+label)
    require(a.get_editor_property('hidden')==hidden,'Actor visibility differs: '+label)
    edited[label]=a.get_path_name()

place(SPEC['actor_label'],SPEC['origin_cm'],[1,1,1],mesh,'NoCollision')
cube=LIB.load_asset('/Engine/BasicShapes/Cube')
for i,column in enumerate(SPEC['proposed_column_colliders']):
    place('D17_TerraceColumn_%02d'%i,column['center'],[v/100 for v in column['size']],cube,'BlockAll',True)
if not VERIFY:
    require(LEVEL.save_current_level(),'Map save failed')
    require(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True),'Packages save failed')
descs={str(d.label):d for d in WP.get_actor_descs()}
report=dict(task_id='D17-02',result='PASS',status='GENERATED_DRAFT',read_only=VERIFY,
    spec_sha256=hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),mesh=mesh.get_path_name(),
    triangles=mesh.get_num_triangles(0),bounds_min=minimum,bounds_max=maximum,
    materials=slots,preserved_colliders=preserved,edited_actor_paths=edited,
    edited_actor_packages=[str(descs[label].actor_package) for label in edited],
    scope='Fitted route skin plus six column colliders; requires affected cooked runtime traversal and camera proof')
Path(os.environ['BIELLA_D17_TERRACE_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
print('D17_TERRACE_ROUTE COMPLETE')
