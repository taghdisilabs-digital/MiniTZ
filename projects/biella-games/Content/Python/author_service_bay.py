"""D17 service-bay assets: new material graph + mesh import; fresh readback.

No level, original material, collision actor or gameplay data is edited here.
The runtime uses these assets on the existing service-bay components.
"""
import hashlib
import json
import os
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
ROOT = '/Game/Environment/ServiceBay'
SPEC_PATH = PROJECT/'SourceAssets/Environment/service-bay.json'
SPEC = json.loads(SPEC_PATH.read_text())
SHADER = (PROJECT/'SourceAssets/Materials/ServiceSurface.hlsl').read_text()
GROUND_SHADER = (PROJECT/'SourceAssets/Materials/ServiceGround.hlsl').read_text()
VERIFY = '-D17VerifyServiceBay' in unreal.SystemLibrary.get_command_line()
LIB = unreal.EditorAssetLibrary
MAT = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
MESH = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) or unreal.get_default_object(unreal.StaticMeshEditorSubsystem)


def node(material, cls, **props):
    value = MAT.create_material_expression(material, cls)
    assert value
    for key, prop in props.items():
        value.set_editor_property(key, prop)
    return value


def link(a, out, b, pin):
    assert MAT.connect_material_expressions(a, out, b, pin)


def structure(cls, **props):
    value = cls()
    for key, prop in props.items():
        value.set_editor_property(key, prop)
    return value


def asset(name, cls, factory):
    path = ROOT+'/'+name
    value = LIB.load_asset(path) if LIB.does_asset_exist(path) else None
    if value is None:
        assert not VERIFY, path
        value = TOOLS.create_asset(name, ROOT, cls, factory)
    assert isinstance(value, cls), path
    return value


material = asset('M_ServiceMetal', unreal.Material, unreal.MaterialFactoryNew())
if not VERIFY:
    MAT.delete_all_material_expressions(material)
    material.set_editor_property('tangent_space_normal', False)
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    MAT.set_base_material_usage(material, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES, True)
    params = {}
    for name, value in dict(BaseColor=(.055,.074,.08,1), Roughness=.48, Metallic=0.,
                            DetailScale=1., ReliefCm=.012, Wear=.35, Wetness=.3,
                            Emission=0., Organic=0.).items():
        vector = isinstance(value, tuple)
        params[name] = node(material, unreal.MaterialExpressionVectorParameter if vector else unreal.MaterialExpressionScalarParameter,
            parameter_name=name, default_value=unreal.LinearColor(*value) if vector else value,
            group='Biella Service Metal')
    pos = node(material, unreal.MaterialExpressionWorldPosition)
    normal = node(material, unreal.MaterialExpressionVertexNormalWS)
    grain = node(material, unreal.MaterialExpressionCustom, code=SHADER,
        description='Biella filtered centimeter-scale metal wear',
        output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1,
        inputs=[structure(unreal.CustomInput, input_name=n) for n in ('Position','SurfaceNormal','DetailScale','ReliefCm','Organic')],
        additional_outputs=[structure(unreal.CustomOutput, output_name='ReliefNormal',output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)])
    for a, output, key in ((pos,'XYZ','Position'),(normal,'','SurfaceNormal'),
                          (params['DetailScale'],'','DetailScale'),(params['ReliefCm'],'','ReliefCm'),
                          (params['Organic'],'','Organic')):
        link(a, output, grain, key)
    # Shallow oxidation and accumulated dirt modulate distinct material inputs.
    # Metallic is reduced in oxidized regions; moisture affects roughness/color,
    # never displacement, opacity, or gameplay collision.
    code = '''float dirt = smoothstep(0.42, 0.67, Grain) * saturate(Wear);
float wet = saturate(Wetness) * smoothstep(0.35, 0.60, Grain);
OutColor = lerp(BaseColor, float3(0.12,0.042,0.018), dirt) * lerp(1.0,0.72,wet);
OutMetal = saturate(Metallic) * (1.0-dirt);
OutRough = clamp(lerp(Roughness + dirt * 0.22, 0.17, wet), 0.12, 0.94);
float tissueWet = saturate(Wetness) * smoothstep(0.3,0.65,Grain);
float3 tissueColor = BaseColor * lerp(0.32,1.65,Grain);
OutColor = lerp(OutColor,tissueColor,saturate(Organic));
OutMetal *= 1.0-saturate(Organic);
OutRough = lerp(OutRough,clamp(Roughness + 0.1*(1.0-Grain)-0.16*tissueWet,0.18,0.65),saturate(Organic));
return 0.0;'''
    surface = node(material, unreal.MaterialExpressionCustom, code=code,
        description='Oxide and dampness affect physical response independently',
        output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1,
        inputs=[structure(unreal.CustomInput,input_name=n) for n in ('Grain','BaseColor','Roughness','Metallic','Wear','Wetness','Organic')],
        additional_outputs=[structure(unreal.CustomOutput,output_name=n,output_type=t) for n,t in (
            ('OutColor',unreal.CustomMaterialOutputType.CMOT_FLOAT3),
            ('OutMetal',unreal.CustomMaterialOutputType.CMOT_FLOAT1),
            ('OutRough',unreal.CustomMaterialOutputType.CMOT_FLOAT1))])
    link(grain,'',surface,'Grain')
    for key in ('BaseColor','Roughness','Metallic','Wear','Wetness','Organic'):
        link(params[key], 'RGB' if key=='BaseColor' else '', surface, key)
    emission = node(material,unreal.MaterialExpressionMultiply)
    link(params['BaseColor'],'RGB',emission,'A'); link(params['Emission'],'',emission,'B')
    for a,out,prop in ((surface,'OutColor','MP_BASE_COLOR'),(surface,'OutMetal','MP_METALLIC'),
                        (surface,'OutRough','MP_ROUGHNESS'),(grain,'ReliefNormal','MP_NORMAL'),(emission,'','MP_EMISSIVE_COLOR')):
        assert MAT.connect_material_property(a,out,getattr(unreal.MaterialProperty,prop))
    MAT.layout_material_expressions(material)
    assert not MAT.recompile_material(material)
    LIB.set_metadata_tag(material,'D17.Status','GENERATED_DRAFT')
    assert LIB.save_loaded_asset(material,only_if_is_dirty=False)

assert not material.get_editor_property('tangent_space_normal')
assert material.get_editor_property('shading_model') == unreal.MaterialShadingModel.MSM_DEFAULT_LIT
grain = MAT.get_material_property_input_node(material,unreal.MaterialProperty.MP_NORMAL)
assert grain.get_editor_property('code') == SHADER
for key in ('MP_BASE_COLOR','MP_ROUGHNESS','MP_METALLIC'):
    assert isinstance(MAT.get_material_property_input_node(material,getattr(unreal.MaterialProperty,key)),unreal.MaterialExpressionCustom)
assert MAT.get_material_property_input_node(material,unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET) is None

materials = {}
for name,color,rough,metal,wear,wet,emission in [
    ('Paint',(.055,.074,.08,1),.48,0,.3,.25,0),
    ('Steel',(.31,.34,.36,1),.32,1,.22,.22,0),
    ('Rubber',(.012,.015,.018,1),.78,0,0,0,0),
    ('Lamp',(1,.62,.28,1),.3,0,0,0,3),
    ('Growth',(.16,.007,.014,1),.34,0,0,.7,0),
    ('Vein',(.42,.006,.016,1),.28,0,0,.4,1.8),
]:
    instance=asset('MI_Service'+name,unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
    organic = name in ('Growth','Vein')
    parameters=dict(Roughness=rough,Metallic=metal,Wear=wear,Wetness=wet,Emission=emission,
                    Organic=float(organic),ReliefCm=.065 if name=='Growth' else .012)
    if not VERIFY:
        MAT.set_material_instance_parent(instance,material)
        MAT.set_material_instance_vector_parameter_value(instance,'BaseColor',unreal.LinearColor(*color))
        for key,value in parameters.items():
            MAT.set_material_instance_scalar_parameter_value(instance,key,value)
        LIB.set_metadata_tag(instance,'D17.Status','GENERATED_DRAFT')
        assert LIB.save_loaded_asset(instance,only_if_is_dirty=False)
    assert instance.get_editor_property('parent') == material
    for key,value in parameters.items():
        assert abs(MAT.get_material_instance_scalar_parameter_value(instance,key)-value)<1e-5
    materials[name]=instance

# A separate ground graph prevents native switch color from tinting the floor.
ground=asset('M_ServiceGround',unreal.Material,unreal.MaterialFactoryNew())
if not VERIFY:
    MAT.delete_all_material_expressions(ground)
    ground.set_editor_property('tangent_space_normal',False)
    ground.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    position=node(ground,unreal.MaterialExpressionWorldPosition)
    normal=node(ground,unreal.MaterialExpressionVertexNormalWS)
    origin=node(ground,unreal.MaterialExpressionVectorParameter,parameter_name='SiteOrigin',
                default_value=unreal.LinearColor(6500,700,0,1))
    powered=node(ground,unreal.MaterialExpressionScalarParameter,parameter_name='Powered',default_value=0.)
    shader=node(ground,unreal.MaterialExpressionCustom,code=GROUND_SHADER,
        description='Weathered slabs and wet service plates; native powered perimeter',
        output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1,
        inputs=[structure(unreal.CustomInput,input_name=n) for n in ('Position','SurfaceNormal','SiteOrigin','Powered')],
        additional_outputs=[structure(unreal.CustomOutput,output_name=n,output_type=t) for n,t in (
            ('OutColor',unreal.CustomMaterialOutputType.CMOT_FLOAT3),
            ('OutMetal',unreal.CustomMaterialOutputType.CMOT_FLOAT1),
            ('OutRough',unreal.CustomMaterialOutputType.CMOT_FLOAT1),
            ('OutNormal',unreal.CustomMaterialOutputType.CMOT_FLOAT3),
            ('OutEmission',unreal.CustomMaterialOutputType.CMOT_FLOAT3))])
    for a,out,key in ((position,'XYZ','Position'),(normal,'','SurfaceNormal'),
                      (origin,'RGB','SiteOrigin'),(powered,'','Powered')):
        link(a,out,shader,key)
    for out,prop in (('OutColor','MP_BASE_COLOR'),('OutMetal','MP_METALLIC'),
                     ('OutRough','MP_ROUGHNESS'),('OutNormal','MP_NORMAL'),('OutEmission','MP_EMISSIVE_COLOR')):
        assert MAT.connect_material_property(shader,out,getattr(unreal.MaterialProperty,prop))
    MAT.layout_material_expressions(ground)
    MAT.recompile_material(ground)
    LIB.set_metadata_tag(ground,'D17.Status','GENERATED_DRAFT')
    assert LIB.save_loaded_asset(ground,only_if_is_dirty=False)
assert not ground.get_editor_property('tangent_space_normal')
for prop in ('MP_BASE_COLOR','MP_ROUGHNESS','MP_METALLIC','MP_NORMAL','MP_EMISSIVE_COLOR'):
    assert MAT.get_material_property_input_node(ground,getattr(unreal.MaterialProperty,prop)).get_editor_property('code')==GROUND_SHADER
assert MAT.get_material_property_input_node(ground,unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET) is None
materials['Ground']=ground

records=[]
for entry in SPEC['assets']:
    source=SPEC_PATH.parent/entry['fbx']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==entry['sha256']
    path=ROOT+'/'+entry['mesh']
    mesh=LIB.load_asset(path) if LIB.does_asset_exist(path) else None
    if mesh is None or (not VERIFY and LIB.get_metadata_tag(mesh,'D17.SourceSHA256') != entry['sha256']):
        assert not VERIFY, path
        task=unreal.AssetImportTask()
        task.filename=str(source); task.destination_path=ROOT; task.destination_name=entry['mesh']
        task.automated=True; task.replace_existing=True; task.save=True
        options=unreal.FbxImportUI()
        options.import_mesh=True; options.import_as_skeletal=False
        options.import_materials=False; options.import_textures=False
        options.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH
        options.automated_import_should_detect_type=False
        options.static_mesh_import_data.combine_meshes=True
        options.static_mesh_import_data.auto_generate_collision=False
        task.options=options
        TOOLS.import_asset_tasks([task])
        mesh=LIB.load_asset(path)
    assert isinstance(mesh,unreal.StaticMesh)
    slots=mesh.get_editor_property('static_materials')
    names=[str(s.get_editor_property('imported_material_slot_name')) for s in slots]
    if not VERIFY:
        for i,name in enumerate(names):
            mesh.set_material(i,materials[name])
        MESH.remove_collisions(mesh)
        if entry['normalized_envelope_cm']:
            assert MESH.add_simple_collisions(mesh,unreal.ScriptCollisionShapeType.BOX)>=0
        LIB.set_metadata_tag(mesh,'D17.SourceSHA256',entry['sha256'])
        LIB.set_metadata_tag(mesh,'D17.Status','GENERATED_DRAFT')
        assert LIB.save_loaded_asset(mesh,only_if_is_dirty=False)
    assert LIB.get_metadata_tag(mesh,'D17.SourceSHA256') == entry['sha256']
    for i,name in enumerate(names):
        assert mesh.get_material(i)==materials[name]
    bounds=mesh.get_bounds()
    extent=[bounds.box_extent.x,bounds.box_extent.y,bounds.box_extent.z]
    origin=[bounds.origin.x,bounds.origin.y,bounds.origin.z]
    observed_min=[o-e for o,e in zip(origin,extent)]
    observed_max=[o+e for o,e in zip(origin,extent)]
    # Extents alone cannot catch reflection of an asymmetric cabinet. Require
    # the saved imported mesh to occupy the authored native coordinates.
    assert all(abs(a-b)<.02 for a,b in zip(observed_min,entry['bounds_min'])), (path,observed_min)
    assert all(abs(a-b)<.02 for a,b in zip(observed_max,entry['bounds_max'])), (path,observed_max)
    if entry['normalized_envelope_cm']:
        assert max(abs(v-50) for v in extent)<.02,extent
        assert bounds.origin.length()<.02
        boxes=mesh.get_editor_property('body_setup').get_editor_property('agg_geom').get_editor_property('box_elems')
        assert len(boxes)==1
        assert all(abs(boxes[0].get_editor_property(a)-100)<.04 for a in ('x','y','z'))
        assert MESH.get_simple_collision_count(mesh)==1
    else:
        assert MESH.get_simple_collision_count(mesh)==0
    records.append(dict(asset=path,source_sha256=entry['sha256'],bounds_extent=extent,bounds_origin=origin,
        bounds_min=observed_min,bounds_max=observed_max,authored_coordinates_verified=True,
        collision_boxes=MESH.get_simple_collision_count(mesh),triangles=mesh.get_num_triangles(0),materials=names))

report=dict(task_id='D17-01',result='PASS',mode='readback' if VERIFY else 'author',
    source_sha256=hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),meshes=records,
    master=material.get_path_name(),ground_master=ground.get_path_name(),
    ground_shader_sha256=hashlib.sha256(GROUND_SHADER.encode()).hexdigest(),status='GENERATED_DRAFT',
    collision='Panel boxes retain unit bounds; fixed dressing has no collision')
Path(os.environ['BIELLA_D17_SERVICE_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
unreal.log('D17_SERVICE_ASSETS COMPLETE')
