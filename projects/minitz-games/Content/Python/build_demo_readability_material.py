"""Create or verify Demo 01's editable lit, parameterized presentation material.

Run with UnrealEditor-Cmd <project.uproject> -run=pythonscript
  -script=<absolute path to this file> -EnablePlugins=PythonScriptPlugin
  -unattended -nullrhi -nosound -nop4

Existing assets are verified without modification. Add
  -D01RebuildReadabilityMaterial
only to intentionally rebuild this material graph after editing this source.
Add -D01VerifyReadabilityMaterial for a read-only fresh-process check that also
fails if the saved asset is missing. Python is an editor authoring aid only;
gameplay uses the saved native material and C++ material instances.
"""

import json

import unreal


ASSET_PATH = "/Game/Materials/M_DemoReadability"
DEFAULT_COLOR = (0.18, 0.22, 0.26, 1.0)
DEFAULT_ROUGHNESS = 0.8
DEFAULT_FILL = 0.03
LIB = unreal.MaterialEditingLibrary


def require(condition, message):
    if not condition:
        raise RuntimeError("D01_040_MATERIAL FAIL: " + message)


def parameter(material, expression_class, name, value, x, y):
    node = LIB.create_material_expression(material, expression_class, x, y)
    require(node is not None, "Cannot create " + name)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", value)
    node.set_editor_property("group", "Demo Readability")
    return node


def build(material):
    # Lit opaque surfaces retain directional light, shadow, pressure flicker,
    # and depth cues. The small tint-matched fill keeps silhouettes readable
    # during shadow intervals without substituting an unlit presentation.
    material.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    LIB.delete_all_material_expressions(material)
    color = parameter(material, unreal.MaterialExpressionVectorParameter,
                      "BaseColor", unreal.LinearColor(*DEFAULT_COLOR), -600, -140)
    roughness = parameter(material, unreal.MaterialExpressionScalarParameter,
                          "Roughness", DEFAULT_ROUGHNESS, -360, 100)
    roughness.set_editor_property("slider_min", 0.0)
    roughness.set_editor_property("slider_max", 1.0)
    fill = parameter(material, unreal.MaterialExpressionScalarParameter,
                     "ReadabilityFill", DEFAULT_FILL, -600, 300)
    fill.set_editor_property("slider_min", 0.0)
    fill.set_editor_property("slider_max", 0.1)
    emissive = LIB.create_material_expression(material, unreal.MaterialExpressionMultiply, -300, 300)
    require(LIB.connect_material_property(color, "RGB", unreal.MaterialProperty.MP_BASE_COLOR),
            "BaseColor connection failed")
    require(LIB.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS),
            "Roughness connection failed")
    require(LIB.connect_material_expressions(color, "RGB", emissive, "A"),
            "Emissive color input failed")
    require(LIB.connect_material_expressions(fill, "", emissive, "B"),
            "Emissive fill input failed")
    require(LIB.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR),
            "Emissive output failed")
    errors = LIB.recompile_material(material)
    require(not errors, "Material compiler errors: " + str(errors))
    require(unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False),
            "Native material asset save failed")


def verify(material):
    require(isinstance(material, unreal.Material), "Saved asset is not a Material")
    require(material.get_editor_property("shading_model") == unreal.MaterialShadingModel.MSM_DEFAULT_LIT,
            "Material must remain lit")
    require(material.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_OPAQUE,
            "Material must remain opaque")
    vectors = sorted(str(name) for name in LIB.get_vector_parameter_names(material))
    scalars = sorted(str(name) for name in LIB.get_scalar_parameter_names(material))
    require(vectors == ["BaseColor"], "Missing runtime BaseColor vector parameter")
    require(scalars == ["ReadabilityFill", "Roughness"], "Missing surface/fill scalar parameters")
    require(abs(LIB.get_material_default_scalar_parameter_value(material, "Roughness") - DEFAULT_ROUGHNESS) < 1e-6,
            "Unexpected default roughness")
    require(abs(LIB.get_material_default_scalar_parameter_value(material, "ReadabilityFill") - DEFAULT_FILL) < 1e-6,
            "Unexpected default fill")
    color = LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
    roughness = LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_ROUGHNESS)
    emissive = LIB.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    require(isinstance(color, unreal.MaterialExpressionVectorParameter)
            and str(color.get_editor_property("parameter_name")) == "BaseColor",
            "BaseColor is not wired to the exposed parameter")
    require(isinstance(roughness, unreal.MaterialExpressionScalarParameter)
            and str(roughness.get_editor_property("parameter_name")) == "Roughness",
            "Roughness is not wired to the exposed parameter")
    require(isinstance(emissive, unreal.MaterialExpressionMultiply), "Fill must multiply BaseColor")
    inputs = LIB.get_inputs_for_material_expression(material, emissive)
    require(len(inputs) == 2 and color in inputs, "Fill is disconnected from BaseColor")
    require(any(isinstance(node, unreal.MaterialExpressionScalarParameter)
                and str(node.get_editor_property("parameter_name")) == "ReadabilityFill" for node in inputs),
            "Fill is disconnected from ReadabilityFill")
    unreal.log("D01_040_MATERIAL PASS " + json.dumps({
        "asset": material.get_path_name(), "vectors": vectors, "scalars": scalars,
        "roughness": DEFAULT_ROUGHNESS, "fill": DEFAULT_FILL,
        "shading": "DefaultLit", "blend": "Opaque", "graph_connections_verified": True,
    }, sort_keys=True))


command = unreal.SystemLibrary.get_command_line()
verify_only = "-D01VerifyReadabilityMaterial" in command
rebuild = "-D01RebuildReadabilityMaterial" in command
require(not (verify_only and rebuild), "Choose rebuild or read-only verification")
material = unreal.load_asset(ASSET_PATH)
if material is None:
    require(not verify_only, "Saved material is missing")
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_DemoReadability", "/Game/Materials", unreal.Material, unreal.MaterialFactoryNew())
    require(material is not None, "Cannot create native material asset")
    build(material)
elif rebuild:
    build(material)
verify(material)
