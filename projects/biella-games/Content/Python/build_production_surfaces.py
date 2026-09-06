"""D03 native PBR surface authoring/readback; geometry and Demo assets untouched.

UnrealEditor-Cmd BiellaGames.uproject -run=pythonscript -script=<this file>
 -EnablePlugins=PythonScriptPlugin -unattended -nullrhi -nosound -nop4
Default creates missing master and updates the four existing instances.
Use -D03VerifySurfaces for read-only verification, -D03RebuildSurfaces to
intentionally rebuild a master whose source has changed. All outputs are drafts.
"""
import hashlib
import json
import os
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
SOURCE = PROJECT / 'SourceAssets/Materials/ProductionSurface.hlsl'
SHADER = SOURCE.read_text()
SHA = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
ROOT = '/Game/OpenWorld/Materials'
MASTER = ROOT + '/M_ProductionSurface'
VERIFY = '-D03VerifySurfaces' in unreal.SystemLibrary.get_command_line()
REBUILD = '-D03RebuildSurfaces' in unreal.SystemLibrary.get_command_line()
LIB = unreal.MaterialEditingLibrary
ASSETS = unreal.EditorAssetLibrary
SPECS = {'Street': ((0.08, 0.10, 0.12, 1), .88, 1.4, .12),
         'Wall': ((.23, .28, .30, 1), .76, 1.0, .09),
         'Route': ((.50, .47, .28, 1), .67, .65, .035),
         'Interior': ((.24, .30, .28, 1), .82, .8, .06)}

def require(value, why):
    if not value:
        raise RuntimeError('D03_SURFACE FAIL: ' + why)

def node(mat, cls, **props):
    result = LIB.create_material_expression(mat, cls)
    require(result is not None, 'create ' + str(cls))
    for name, value in props.items():
        result.set_editor_property(name, value)
    return result

def link(a, output, b, slot):
    require(LIB.connect_material_expressions(a, output, b, slot), 'connect ' + slot)

def parameter(mat, name, value):
    vector = isinstance(value, tuple)
    return node(mat, unreal.MaterialExpressionVectorParameter if vector else unreal.MaterialExpressionScalarParameter,
                parameter_name=name, default_value=unreal.LinearColor(*value) if vector else value,
                group='Production Surface')

def structure(cls, **props):
    value = cls()
    for key, item in props.items():
        value.set_editor_property(key, item)
    return value

def build(mat):
    LIB.delete_all_material_expressions(mat)
    mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property('tangent_space_normal', False)
    LIB.set_base_material_usage(mat, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES, True)
    LIB.set_base_material_usage(mat, unreal.MaterialUsage.MATUSAGE_NANITE, True)
    color = parameter(mat, 'BaseColor', (.23, .28, .30, 1))
    rough = parameter(mat, 'Roughness', .76)
    scale = parameter(mat, 'DetailScale', 1.0)
    relief = parameter(mat, 'ReliefCm', .09)
    pos = node(mat, unreal.MaterialExpressionWorldPosition)
    normal = node(mat, unreal.MaterialExpressionVertexNormalWS)
    custom = node(mat, unreal.MaterialExpressionCustom, code=SHADER,
                  description='D03 filtered world-scale surface relief',
                  output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1,
                  inputs=[structure(unreal.CustomInput, input_name=x) for x in ('Position', 'SurfaceNormal', 'DetailScale', 'ReliefCm')],
                  additional_outputs=[structure(unreal.CustomOutput, output_name='ReliefNormal', output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3)])
    for a, output, name in ((pos, 'XYZ', 'Position'), (normal, '', 'SurfaceNormal'), (scale, '', 'DetailScale'), (relief, '', 'ReliefCm')):
        link(a, output, custom, name)
    tint = node(mat, unreal.MaterialExpressionLinearInterpolate, const_a=.86, const_b=1.08)
    link(custom, '', tint, 'Alpha')
    base = node(mat, unreal.MaterialExpressionMultiply)
    link(color, 'RGB', base, 'A'); link(tint, '', base, 'B')
    centered = node(mat, unreal.MaterialExpressionSubtract, const_b=.5)
    link(custom, '', centered, 'A')
    variation = node(mat, unreal.MaterialExpressionMultiply, const_b=.12)
    link(centered, '', variation, 'A')
    varied = node(mat, unreal.MaterialExpressionAdd)
    link(rough, '', varied, 'A'); link(variation, '', varied, 'B')
    clamp = node(mat, unreal.MaterialExpressionClamp, min_default=.4, max_default=.98)
    link(varied, '', clamp, '')
    for a, output, prop in ((base, '', unreal.MaterialProperty.MP_BASE_COLOR),
                            (clamp, '', unreal.MaterialProperty.MP_ROUGHNESS),
                            (custom, 'ReliefNormal', unreal.MaterialProperty.MP_NORMAL)):
        require(LIB.connect_material_property(a, output, prop), 'material output ' + str(prop))
    # Dielectric surfaces: zero metallic/emission, engine dielectric specular.
    LIB.layout_material_expressions(mat)
    require(not LIB.recompile_material(mat), 'material compile')
    ASSETS.set_metadata_tag(mat, 'D03.SourceSHA256', SHA)
    ASSETS.set_metadata_tag(mat, 'D03.Status', 'GENERATED_DRAFT')
    require(ASSETS.save_loaded_asset(mat, only_if_is_dirty=False), 'master save')

def run():
    mat = ASSETS.load_asset(MASTER) if ASSETS.does_asset_exist(MASTER) else None
    if mat is None:
        require(not VERIFY, 'missing master')
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            'M_ProductionSurface', ROOT, unreal.Material, unreal.MaterialFactoryNew())
        build(mat)
    elif REBUILD and not VERIFY:
        build(mat)
    require(isinstance(mat, unreal.Material), 'master class')
    require(ASSETS.get_metadata_tag(mat, 'D03.SourceSHA256') == SHA, 'source digest; rebuild explicitly')
    require(mat.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_OPAQUE, 'opaque')
    require(mat.get_editor_property('shading_model') == unreal.MaterialShadingModel.MSM_DEFAULT_LIT, 'lit')
    require(not mat.get_editor_property('tangent_space_normal'), 'world-space normal')
    require(LIB.has_material_usage(mat, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES), 'HLOD instancing')
    require(LIB.has_material_usage(mat, unreal.MaterialUsage.MATUSAGE_NANITE), 'Authored facade Nanite usage')
    normal = LIB.get_material_property_input_node(mat, unreal.MaterialProperty.MP_NORMAL)
    require(isinstance(normal, unreal.MaterialExpressionCustom), 'saved normal custom node')
    require(normal.get_editor_property('code') == SHADER, 'saved shader bytes')
    require(LIB.get_material_property_input_node_output_name(mat, unreal.MaterialProperty.MP_NORMAL) == 'ReliefNormal', 'saved normal output')
    for prop in (unreal.MaterialProperty.MP_EMISSIVE_COLOR, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET):
        require(LIB.get_material_property_input_node(mat, prop) is None, 'no artificial emission or displacement')
    graph = {}
    for label, prop in [('base_color', unreal.MaterialProperty.MP_BASE_COLOR), ('roughness', unreal.MaterialProperty.MP_ROUGHNESS), ('normal', unreal.MaterialProperty.MP_NORMAL)]:
        root = LIB.get_material_property_input_node(mat, prop)
        require(root is not None, 'saved ' + label + ' output')
        stack, seen = [root], set()
        while stack:
            item = stack.pop()
            if item in seen:
                continue
            seen.add(item)
            stack.extend(x for x in LIB.get_inputs_for_material_expression(mat, item) if x is not None)
        require(normal in seen, 'filtered surface drives ' + label)
        graph[label] = sorted(str(x.get_class().get_name()) for x in seen)
    records = []
    for name, (color, roughness, scale, relief) in SPECS.items():
        instance = ASSETS.load_asset(ROOT + '/MI_' + name)
        require(isinstance(instance, unreal.MaterialInstanceConstant), 'existing instance ' + name)
        if not VERIFY:
            LIB.set_material_instance_parent(instance, mat)
            LIB.set_material_instance_vector_parameter_value(instance, 'BaseColor', unreal.LinearColor(*color))
            for key, value in [('Roughness', roughness), ('DetailScale', scale), ('ReliefCm', relief)]:
                LIB.set_material_instance_scalar_parameter_value(instance, key, value)
            ASSETS.set_metadata_tag(instance, 'D03.Status', 'GENERATED_DRAFT')
            require(ASSETS.save_loaded_asset(instance, only_if_is_dirty=False), 'instance save')
        require(instance.get_editor_property('parent') == mat, 'instance parent')
        for key, expected in [('Roughness', roughness), ('DetailScale', scale), ('ReliefCm', relief)]:
            require(abs(LIB.get_material_instance_scalar_parameter_value(instance, key) - expected) < 1e-5, name + ':' + key)
        actual = LIB.get_material_instance_vector_parameter_value(instance, 'BaseColor')
        require(all(abs(a-b) < 1e-5 for a,b in zip((actual.r, actual.g, actual.b, actual.a), color)), name + ':color')
        records.append(dict(asset=instance.get_path_name(), roughness=roughness, detail_scale=scale, relief_cm=relief))
    report = dict(result='PASS', mode='readback' if VERIFY else 'author', source_sha256=SHA,
                  master=mat.get_path_name(), instances=records, saved_graph=graph, candidate_status='GENERATED_DRAFT')
    path = Path(os.environ.get('BIELLA_D03_SURFACE_REPORT', str(PROJECT / 'Build/Presentation' / ('D03-01-surface-readback.json' if VERIFY else 'D03-01-surface-author.json'))))
    path.write_text(json.dumps(report, indent=2)+'\n')
    unreal.log('D03_SURFACE COMPLETE ' + json.dumps(report))

if __name__ == '__main__':
    run()
