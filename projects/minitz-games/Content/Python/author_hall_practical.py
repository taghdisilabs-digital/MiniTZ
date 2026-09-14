"""Author the retained hall light and its supported visual housing.

Only the existing light and one collision-free mesh actor are edited; the
fresh-process verification branch never saves or changes source.
"""
import hashlib,json,os
from pathlib import Path
import unreal
PROJECT=Path(__file__).resolve().parents[2]
SPEC_PATH=PROJECT/'SourceAssets/Environment/hall-practical.json'
SPEC=json.loads(SPEC_PATH.read_text())
VERIFY='-D17VerifyHallPractical' in unreal.SystemLibrary.get_command_line()
LIB=unreal.EditorAssetLibrary
TOOLS=unreal.AssetToolsHelpers.get_asset_tools()
MESH=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) or unreal.get_default_object(unreal.StaticMeshEditorSubsystem)
LEVEL=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
WP=unreal.WorldPartitionBlueprintLibrary
ROOT='/Game/Environment/ServiceHall'
def require(ok,message):
    if not ok: raise RuntimeError('D17_HALL_PRACTICAL FAIL: '+message)
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
light=existing.get(SPEC['light_label'])
require(isinstance(light,unreal.PointLight),'Retained interior light missing')
require(max(abs(getattr(light.get_actor_location(),k)-v) for k,v in zip(('x','y','z'),SPEC['origin_cm']))<.001,'Retained light moved')
component=light.light_component
require(component.get_editor_property('intensity_units')==unreal.LightUnits.LUMENS,'Light units changed')
require(component.get_editor_property('mobility')==unreal.ComponentMobility.MOVABLE,'Retained mobility changed')
if not VERIFY:
    light.modify();component.modify()
    component.set_intensity(SPEC['light_lumens'])
    component.set_light_color(unreal.LinearColor(*SPEC['light_color_linear']))
    component.set_editor_property('use_temperature',False)
require(abs(component.get_editor_property('intensity')-SPEC['light_lumens'])<.001,'Saved intensity differs')
color=component.get_light_color()
require(max(abs(getattr(color,k)-v) for k,v in zip(('r','g','b','a'),SPEC['light_color_linear']))<.01,'Saved light color differs')
for name,wanted in [('attenuation_radius',SPEC['light_attenuation_cm']),('source_radius',SPEC['light_source_radius_cm']),
                    ('cast_shadows',True),('use_inverse_squared_falloff',True),('use_temperature',False)]:
    require(component.get_editor_property(name)==wanted,'Retained light response differs: '+name)
# Housing is seated in the existing roof soffit; no support collider is edited.
roof=existing.get('D02_Interior_Roof')
require(isinstance(roof,unreal.StaticMeshActor),'Retained roof missing')
require(str(roof.static_mesh_component.get_collision_profile_name())=='BlockAll','Roof collision differs')
require(abs(roof.get_actor_location().z-675)<.001 and abs(roof.get_actor_scale3d().z-.5)<.001,'Roof support height changed')
a=existing.get(SPEC['actor_label'])
if a is None:
    require(not VERIFY,'Saved practical housing missing')
    a=ACTORS.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*SPEC['origin_cm']))
    require(a is not None,'Cannot create housing');a.set_actor_label(SPEC['actor_label'])
if not VERIFY:
    a.modify();a.static_mesh_component.modify()
    a.set_actor_location(unreal.Vector(*SPEC['origin_cm']),False,False)
    a.set_actor_scale3d(unreal.Vector(1,1,1))
    a.set_editor_property('is_spatially_loaded',True)
    a.set_editor_property('enable_auto_lod_generation',False)
    a.set_editor_property('tags',[unreal.Name('D17HallPractical')])
    a.static_mesh_component.set_static_mesh(mesh)
    a.static_mesh_component.set_mobility(unreal.ComponentMobility.STATIC)
    a.static_mesh_component.set_collision_profile_name('NoCollision')
    require(LEVEL.save_current_level(),'Map save failed')
    require(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True),'External actor save failed')
require(a.static_mesh_component.get_editor_property('static_mesh')==mesh,'Saved housing mesh differs')
require(str(a.static_mesh_component.get_collision_profile_name())=='NoCollision','Housing gained collision')
require(max(abs(getattr(a.get_actor_location(),k)-v) for k,v in zip(('x','y','z'),SPEC['origin_cm']))<.001,'Housing placement differs')
for label,path_before in before.items():require(existing[label].get_path_name()==path_before,'Preexisting actor identity changed')
descs={str(d.label):d for d in WP.get_actor_descs()}
report=dict(task_id='D17-01',result='PASS',status='GENERATED_DRAFT',read_only=VERIFY,
    spec_sha256=hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),map=SPEC['map'],
    mesh=mesh.get_path_name(),triangles=mesh.get_num_triangles(0),bounds_min=actual_min,bounds_max=actual_max,
    materials=slots,collision_boxes=0,preexisting_actor_identities_preserved=True,
    edited_actor_paths={SPEC['actor_label']:a.get_path_name(),SPEC['light_label']:light.get_path_name()},
    edited_actor_packages=[str(descs[label].actor_package) for label in (SPEC['actor_label'],SPEC['light_label'])],
    light=dict(lumens=component.get_editor_property('intensity'),color_linear=[getattr(color,k) for k in ('r','g','b','a')],
               position_cm=SPEC['origin_cm'],source_radius_cm=component.get_editor_property('source_radius'),
               attenuation_cm=component.get_editor_property('attenuation_radius')),
    support=dict(roof_path=roof.get_path_name(),soffit_z_cm=650,housing_top_z_cm=SPEC['origin_cm'][2]+actual_max[2]),
    scope='Supported warm hall practical; no gameplay or whole-slice visual acceptance')
Path(os.environ['BIELLA_D17_HALL_PRACTICAL_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
print('D17_HALL_PRACTICAL COMPLETE')
