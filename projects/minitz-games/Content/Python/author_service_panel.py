"""Author/read back only the service-panel material; preserve existing assets."""
import hashlib
import json
import os
from pathlib import Path
import unreal

PROJECT=Path(unreal.Paths.project_dir()).resolve()
SHADER=(PROJECT/'SourceAssets/Materials/ServicePanel.hlsl').read_text()
PATH='/Game/Environment/ServiceBay/M_ServicePanel'
VERIFY='-D17VerifyServicePanel' in unreal.SystemLibrary.get_command_line()
LIB=unreal.EditorAssetLibrary
MAT=unreal.MaterialEditingLibrary

def node(cls,**props):
    result=MAT.create_material_expression(material,cls)
    for key,value in props.items(): result.set_editor_property(key,value)
    return result

def item(cls,**props):
    result=cls()
    for key,value in props.items(): result.set_editor_property(key,value)
    return result

material=LIB.load_asset(PATH) if LIB.does_asset_exist(PATH) else None
if material is None:
    assert not VERIFY
    material=unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        'M_ServicePanel','/Game/Environment/ServiceBay',unreal.Material,unreal.MaterialFactoryNew())
assert isinstance(material,unreal.Material)
if not VERIFY:
    MAT.delete_all_material_expressions(material)
    material.set_editor_property('tangent_space_normal',False)
    material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property('blend_mode',unreal.BlendMode.BLEND_OPAQUE)
    position=node(unreal.MaterialExpressionWorldPosition)
    local=node(unreal.MaterialExpressionTransformPosition,
        transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
        transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    # The transform's first input has no public pin name in this engine build.
    assert MAT.connect_material_expressions(position,'XYZ',local,'')
    normal=node(unreal.MaterialExpressionVertexNormalWS)
    parameters=[]
    for name,default in (('PanelSize',(12,120,210)),('ImpactA',(0,0,0)),('ImpactB',(0,0,0))):
        parameters.append((node(unreal.MaterialExpressionVectorParameter,parameter_name=name,
            default_value=unreal.LinearColor(*default,1)), 'RGB', name))
    parameters.append((node(unreal.MaterialExpressionScalarParameter,parameter_name='DamageAmount',default_value=0), '', 'DamageAmount'))
    shader=node(unreal.MaterialExpressionCustom,code=SHADER,
        description='Biella coated steel; actual first/latest impacts remain on native debris',
        output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1,
        inputs=[item(unreal.CustomInput,input_name=n) for n in ('Position','LocalPosition','SurfaceNormal','PanelSize','ImpactA','ImpactB','DamageAmount')],
        additional_outputs=[item(unreal.CustomOutput,output_name=n,output_type=t) for n,t in (
            ('OutColor',unreal.CustomMaterialOutputType.CMOT_FLOAT3),
            ('OutMetal',unreal.CustomMaterialOutputType.CMOT_FLOAT1),
            ('OutRough',unreal.CustomMaterialOutputType.CMOT_FLOAT1),
            ('OutNormal',unreal.CustomMaterialOutputType.CMOT_FLOAT3))])
    for source,output,pin in [(position,'XYZ','Position'),(local,'','LocalPosition'),
                              (normal,'','SurfaceNormal')]+parameters:
        assert MAT.connect_material_expressions(source,output,shader,pin)
    for output,prop in (('OutColor','MP_BASE_COLOR'),('OutMetal','MP_METALLIC'),
                        ('OutRough','MP_ROUGHNESS'),('OutNormal','MP_NORMAL')):
        assert MAT.connect_material_property(shader,output,getattr(unreal.MaterialProperty,prop))
    MAT.layout_material_expressions(material)
    MAT.recompile_material(material)
    LIB.set_metadata_tag(material,'D17.Status','GENERATED_DRAFT')
    LIB.set_metadata_tag(material,'D17.ShaderSHA256',hashlib.sha256(SHADER.encode()).hexdigest())
    assert LIB.save_loaded_asset(material,only_if_is_dirty=False)

assert not material.get_editor_property('tangent_space_normal')
assert material.get_editor_property('shading_model')==unreal.MaterialShadingModel.MSM_DEFAULT_LIT
assert material.get_editor_property('blend_mode')==unreal.BlendMode.BLEND_OPAQUE
for prop in ('MP_BASE_COLOR','MP_METALLIC','MP_ROUGHNESS','MP_NORMAL'):
    assert MAT.get_material_property_input_node(material,getattr(unreal.MaterialProperty,prop)).get_editor_property('code')==SHADER
assert MAT.get_material_property_input_node(material,unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET) is None
assert LIB.get_metadata_tag(material,'D17.ShaderSHA256')==hashlib.sha256(SHADER.encode()).hexdigest()
report=dict(task_id='D17-01',result='PASS',mode='readback' if VERIFY else 'author',asset=material.get_path_name(),
    shader_sha256=hashlib.sha256(SHADER.encode()).hexdigest(),status='GENERATED_DRAFT',
    damage_parameters=['ImpactA','ImpactB','DamageAmount'],state_scope='First and latest real point-hit positions; existing health only',
    geometry_scope='Original folded panel meshes, transforms and collision; no WPO; closed impact relief')
Path(os.environ['BIELLA_D17_PANEL_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
unreal.log('D17_PANEL_ASSET COMPLETE')
