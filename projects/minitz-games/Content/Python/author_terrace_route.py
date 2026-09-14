"""Install the fitted terrace skin, practical lights and matching colliders.

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

# Local material instances preserve accepted ServiceBay materials. A separate
# editable graph supplies metre-scale rain/oxide breakup at camera distance.
MAT=unreal.MaterialEditingLibrary
SHADER=(PROJECT/'SourceAssets/Materials/TerraceSurface.hlsl').read_text()
material_packages=[]
def material_asset(name,cls,factory):
    path=ROOT+'/'+name
    value=LIB.load_asset(path) if LIB.does_asset_exist(path) else None
    if value is None:
        require(not VERIFY,'Saved material missing: '+path)
        value=TOOLS.create_asset(name,ROOT,cls,factory)
    require(isinstance(value,cls),'Material type differs')
    material_packages.append(path)
    return value
surface=material_asset('M_TerraceSurface',unreal.Material,unreal.MaterialFactoryNew())
if not VERIFY:
    MAT.delete_all_material_expressions(surface)
    surface.set_editor_property('tangent_space_normal',False)
    surface.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    def node(cls,**props):
        value=MAT.create_material_expression(surface,cls)
        for key,val in props.items():value.set_editor_property(key,val)
        return value
    def struct(cls,**props):
        val=cls()
        for key,value in props.items():val.set_editor_property(key,value)
        return val
    shader=node(unreal.MaterialExpressionCustom,code=SHADER,description='Biella terrace rain and coating wear',
        output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1,
        inputs=[struct(unreal.CustomInput,input_name=n) for n in ('Position','SurfaceNormal','BaseColor','Roughness','Metallic','Wear','Wetness')],
        additional_outputs=[struct(unreal.CustomOutput,output_name=n,output_type=t) for n,t in (
            ('OutColor',unreal.CustomMaterialOutputType.CMOT_FLOAT3),('OutMetal',unreal.CustomMaterialOutputType.CMOT_FLOAT1),
            ('OutRough',unreal.CustomMaterialOutputType.CMOT_FLOAT1),('OutNormal',unreal.CustomMaterialOutputType.CMOT_FLOAT3))])
    for n,cls,out in [('Position',unreal.MaterialExpressionWorldPosition,'XYZ'),('SurfaceNormal',unreal.MaterialExpressionVertexNormalWS,'')]:
        require(MAT.connect_material_expressions(node(cls),out,shader,n),'Graph position connection failed')
    for name,value in dict(BaseColor=(.075,.086,.09,1),Roughness=.48,Metallic=.1,Wear=.7,Wetness=.85).items():
        vector=isinstance(value,tuple)
        parameter=node(unreal.MaterialExpressionVectorParameter if vector else unreal.MaterialExpressionScalarParameter,
            parameter_name=name,default_value=unreal.LinearColor(*value) if vector else value)
        require(MAT.connect_material_expressions(parameter,'RGB' if vector else '',shader,name),'Graph parameter connection failed')
    for output,prop in [('OutColor','MP_BASE_COLOR'),('OutMetal','MP_METALLIC'),('OutRough','MP_ROUGHNESS'),('OutNormal','MP_NORMAL')]:
        require(MAT.connect_material_property(shader,output,getattr(unreal.MaterialProperty,prop)),'Graph output failed')
    MAT.layout_material_expressions(surface);MAT.recompile_material(surface)
    LIB.set_metadata_tag(surface,'D17.Status','GENERATED_DRAFT')
    require(LIB.save_loaded_asset(surface,only_if_is_dirty=False),'Material save failed')
require(not surface.get_editor_property('tangent_space_normal'),'World normal convention differs')
for prop in ('MP_BASE_COLOR','MP_METALLIC','MP_ROUGHNESS','MP_NORMAL'):
    require(MAT.get_material_property_input_node(surface,getattr(unreal.MaterialProperty,prop)).get_editor_property('code')==SHADER,'Saved shader differs')
require(MAT.get_material_property_input_node(surface,unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET) is None,'Unexpected displacement')
material_bindings={}
for name,color,rough,metal in [('Paint',(.075,.086,.09,1),.48,.1),('Steel',(.32,.34,.36,1),.3,1.)]:
    instance=material_asset('MI_Terrace'+name,unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
    params=dict(Roughness=rough,Metallic=metal,Wear=.7,Wetness=.85)
    if not VERIFY:
        MAT.set_material_instance_parent(instance,surface)
        MAT.set_material_instance_vector_parameter_value(instance,'BaseColor',unreal.LinearColor(*color))
        for key,value in params.items():MAT.set_material_instance_scalar_parameter_value(instance,key,value)
        LIB.set_metadata_tag(instance,'D17.Status','GENERATED_DRAFT')
        require(LIB.save_loaded_asset(instance,only_if_is_dirty=False),'Instance save failed')
    require(instance.get_editor_property('parent')==surface,'Material parent differs')
    actual_color=MAT.get_material_instance_vector_parameter_value(instance,'BaseColor')
    require(max(abs(getattr(actual_color,k)-v) for k,v in zip('rgba',color))<.00001,'Material color differs')
    for key,value in params.items():
        require(abs(MAT.get_material_instance_scalar_parameter_value(instance,key)-value)<.00001,'Physical parameter differs')
    material_bindings[name]=instance

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
    material=material_bindings.get(name) or LIB.load_asset('/Game/Environment/ServiceBay/MI_Service'+name)
    require(material is not None,'Retained PBR material missing')
    if not VERIFY: mesh.set_material(i,material)
    require(mesh.get_material(i)==material,'Material binding differs')
if not VERIFY:
    MESH.remove_collisions(mesh)
    # The detailed, long terrace spans many virtual shadow-map pages. Keep it
    # in Nanite's clustered path instead of the non-Nanite marking job queue.
    # Preserve all authored triangles in both Nanite input and fallback.
    nanite=MESH.get_nanite_settings(mesh)
    nanite.set_editor_property('enabled',True)
    nanite.set_editor_property('keep_percent_triangles',1.0)
    nanite.set_editor_property('fallback_target',unreal.NaniteFallbackTarget.PERCENT_TRIANGLES)
    nanite.set_editor_property('fallback_percent_triangles',1.0)
    nanite.set_editor_property('fallback_relative_error',0.0)
    MESH.set_nanite_settings(mesh,nanite,True)
    LIB.set_metadata_tag(mesh,'D17.SourceSHA256',SPEC['sha256'])
    LIB.set_metadata_tag(mesh,'D17.Status','GENERATED_DRAFT')
    require(LIB.save_loaded_asset(mesh,only_if_is_dirty=False),'Mesh save failed')
require(LIB.get_metadata_tag(mesh,'D17.SourceSHA256')==SPEC['sha256'],'Mesh provenance differs')
require(MESH.get_simple_collision_count(mesh)==0,'Skin acquired unintended collision')
nanite=MESH.get_nanite_settings(mesh)
nanite_settings={key:nanite.get_editor_property(key) for key in
    ('enabled','keep_percent_triangles','fallback_percent_triangles','fallback_relative_error')}
require(nanite_settings==dict(enabled=True,keep_percent_triangles=1.0,
    fallback_percent_triangles=1.0,fallback_relative_error=0.0),'Nanite detail settings differ')
require(nanite.get_editor_property('fallback_target')==unreal.NaniteFallbackTarget.PERCENT_TRIANGLES,
    'Fallback target differs')
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
for collider in SPEC['structure_colliders']:
    place(collider['label'],collider['center'],[v/100 for v in collider['size']],cube,'BlockAll',True)
lights=[]
for fixture in SPEC['practical_lights']:
    label=fixture['label'];a=existing.get(label)
    if a is None:
        require(not VERIFY,'Saved light missing: '+label)
        a=ACTORS.spawn_actor_from_class(unreal.PointLight,unreal.Vector(*fixture['position']))
        a.set_actor_label(label)
    require(isinstance(a,unreal.PointLight),'Light actor class differs')
    component=a.light_component
    if not VERIFY:
        a.modify();component.modify()
        a.set_actor_location(unreal.Vector(*fixture['position']),False,False)
        a.set_editor_property('is_spatially_loaded',True)
        a.set_editor_property('tags',[unreal.Name('D17TerraceRoute')])
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.set_editor_property('intensity_units',unreal.LightUnits.LUMENS)
        component.set_editor_property('use_inverse_squared_falloff',True)
        component.set_editor_property('cast_shadows',True)
        component.set_editor_property('use_temperature',False)
        component.set_editor_property('attenuation_radius',fixture['attenuation_cm'])
        component.set_editor_property('source_radius',fixture['source_radius_cm'])
        component.set_editor_property('source_length',fixture['source_length_cm'])
        component.set_intensity(fixture['lumens'])
        component.set_light_color(unreal.LinearColor(*fixture['color_linear']))
    require(vector_matches(a.get_actor_location(),fixture['position']),'Light placement differs')
    require(component.get_editor_property('intensity_units')==unreal.LightUnits.LUMENS,'Light units differ')
    require(component.get_editor_property('mobility')==unreal.ComponentMobility.MOVABLE,'Light mobility differs')
    for key,wanted in [('intensity',fixture['lumens']),('attenuation_radius',fixture['attenuation_cm']),
                       ('source_radius',fixture['source_radius_cm']),('source_length',fixture['source_length_cm']),
                       ('cast_shadows',True),('use_inverse_squared_falloff',True),('use_temperature',False)]:
        require(component.get_editor_property(key)==wanted,'Light response differs: '+key)
    color=component.get_light_color()
    require(max(abs(getattr(color,k)-v) for k,v in zip('rgba',fixture['color_linear']))<.01,'Light color differs')
    edited[label]=a.get_path_name();lights.append(fixture)
if not VERIFY:
    require(LEVEL.save_current_level(),'Map save failed')
    require(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True),'Packages save failed')
descs={str(d.label):d for d in WP.get_actor_descs()}
report=dict(task_id='D17-02',result='PASS',status='GENERATED_DRAFT',read_only=VERIFY,
    spec_sha256=hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),mesh=mesh.get_path_name(),
    triangles=mesh.get_num_triangles(0),nanite_settings=nanite_settings,bounds_min=minimum,bounds_max=maximum,
    materials=slots,material_packages=material_packages,lights=lights,
    shader_sha256=hashlib.sha256(SHADER.encode()).hexdigest(),
    preserved_colliders=preserved,edited_actor_paths=edited,
    edited_actor_packages=[str(descs[label].actor_package) for label in edited],
    scope='Supported terrace approach, surface graph, matched colliders and practical lights; affected raw runtime required')
Path(os.environ['BIELLA_D17_TERRACE_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
print('D17_TERRACE_ROUTE COMPLETE')
