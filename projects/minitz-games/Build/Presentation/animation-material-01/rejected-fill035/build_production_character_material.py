"""Preserve mannequin PBR detail and add bounded shadow readability.

Creates derived assets only when missing. -D03VerifyCharacterMaterial performs
read-only native graph/parameter/parent verification in a fresh process.
"""
import json
import os
from pathlib import Path
import unreal

LIB = unreal.MaterialEditingLibrary
ASSETS = unreal.EditorAssetLibrary
SOURCE = '/Game/Characters/Mannequins/Materials'
TARGET = '/Game/Characters/Presentation'
FILL = 0.035
VERIFY = '-D03VerifyCharacterMaterial' in unreal.SystemLibrary.get_command_line()

source = unreal.load_asset(SOURCE + '/M_Mannequin')
assert source and not source.get_editor_property('use_material_attributes')
path = TARGET + '/M_CharacterReadability'
if not ASSETS.does_asset_exist(path):
    assert not VERIFY, 'Missing saved character material'
    material = ASSETS.duplicate_asset(source.get_path_name().split('.')[0], path)
    assert material
    color = LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
    emission = LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    assert color and emission
    fill = LIB.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -400, 1100)
    fill.set_editor_property('parameter_name', 'CharacterReadabilityFill')
    fill.set_editor_property('default_value', FILL)
    fill.set_editor_property('slider_min', 0.0)
    fill.set_editor_property('slider_max', 0.06)
    fill.set_editor_property('group', 'Biella Presentation')
    multiply = LIB.create_material_expression(material, unreal.MaterialExpressionMultiply, -180, 1100)
    add = LIB.create_material_expression(material, unreal.MaterialExpressionAdd, 20, 1100)
    assert LIB.connect_material_expressions(color, '', multiply, 'A')
    assert LIB.connect_material_expressions(fill, '', multiply, 'B')
    assert LIB.connect_material_expressions(emission, '', add, 'A')
    assert LIB.connect_material_expressions(multiply, '', add, 'B')
    assert LIB.connect_material_property(add, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    assert not LIB.recompile_material(material)
    assert ASSETS.save_loaded_asset(material, only_if_is_dirty=False)

material = unreal.load_asset(path)
assert material.get_editor_property('shading_model') == source.get_editor_property('shading_model')
assert material.get_editor_property('blend_mode') == source.get_editor_property('blend_mode')
assert abs(LIB.get_material_default_scalar_parameter_value(material, 'CharacterReadabilityFill') - FILL) < 1e-6
color = LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
add = LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
assert isinstance(add, unreal.MaterialExpressionAdd)
inputs = LIB.get_inputs_for_material_expression(material, add)
assert len(inputs) == 2 and isinstance(inputs[0], unreal.MaterialExpressionStaticSwitchParameter)
assert isinstance(inputs[1], unreal.MaterialExpressionMultiply)
fill_inputs = LIB.get_inputs_for_material_expression(material, inputs[1])
assert fill_inputs[0] == color
assert str(fill_inputs[1].get_editor_property('parameter_name')) == 'CharacterReadabilityFill'
# Every original surface input still uses the corresponding copied expression.
for property_name in ('MP_BASE_COLOR', 'MP_METALLIC', 'MP_ROUGHNESS', 'MP_NORMAL', 'MP_AMBIENT_OCCLUSION', 'MP_OPACITY_MASK'):
    prop = getattr(unreal.MaterialProperty, property_name)
    original = LIB.get_material_property_input_node(source, prop)
    copied = LIB.get_material_property_input_node(material, prop)
    assert (original is None and copied is None) or (original and copied and original.get_name() == copied.get_name())

records = []
parent = material
for index in (1, 2):
    original = unreal.load_asset(SOURCE + f'/Manny/MI_Manny_0{index}_New')
    target = TARGET + f'/MI_Character_0{index}'
    if not ASSETS.does_asset_exist(target):
        assert not VERIFY, 'Missing saved character material instance'
        instance = ASSETS.duplicate_asset(original.get_path_name().split('.')[0], target)
        assert instance
        LIB.set_material_instance_parent(instance, parent)
        assert ASSETS.save_loaded_asset(instance, only_if_is_dirty=False)
    instance = unreal.load_asset(target)
    assert instance.get_editor_property('parent') == parent
    assert abs(LIB.get_material_instance_scalar_parameter_value(instance, 'CharacterReadabilityFill') - FILL) < 1e-6
    texture_names = LIB.get_texture_parameter_names(source)
    textures = {}
    for name in texture_names:
        original_texture = LIB.get_material_instance_texture_parameter_value(original, name)
        copied_texture = LIB.get_material_instance_texture_parameter_value(instance, name)
        assert original_texture == copied_texture, str(name)
        textures[str(name)] = copied_texture.get_path_name() if copied_texture else None
    records.append(dict(asset=target, parent=parent.get_path_name(), textures=textures))
    parent = instance

Path(os.environ['BIELLA_D03_ANIMATION_REPORT']).write_text(json.dumps(dict(
    result='PASS', mode='readback' if VERIFY else 'author', material=path,
    fill=FILL, surface_inputs_preserved=True, instances=records), indent=2) + '\n')
unreal.log('D03_CHARACTER_MATERIAL COMPLETE')
