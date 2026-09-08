"""Apply/read back D17's lighting layer in the existing streamed gameplay map.

Run after the original world authoring. Stable actor labels retain GUIDs on
resume. Only lighting packages and the cloud material are saved; gameplay and
geometry actors are inspected but never edited. Python does not run in game.
"""
import hashlib
import json
import os
from pathlib import Path
import unreal

PROJECT = Path(__file__).resolve().parents[2]
CONFIG = PROJECT / 'SourceAssets/Environment/storm-lighting.json'
SPEC = json.loads(CONFIG.read_text())
VERIFY = '-D17VerifyStorm' in unreal.SystemLibrary.get_command_line()
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
WP = unreal.WorldPartitionBlueprintLibrary
LIB = unreal.EditorAssetLibrary
MATERIALS = unreal.MaterialEditingLibrary


def require(value, message):
    if not value:
        raise RuntimeError('D17_STORM FAIL: ' + message)


def scalar(obj, key, value):
    if not VERIFY:
        obj.set_editor_property(key, value)
    actual = obj.get_editor_property(key)
    require(abs(actual - value) < 0.00001 if isinstance(value, float) else actual == value,
            key + ': saved value differs')


require(LEVEL.load_level(SPEC['map']), 'Existing canonical map missing')
WP.load_actors([desc.guid for desc in WP.get_actor_descs()])
existing = {a.get_actor_label(): a for a in ACTORS.get_all_level_actors()}
before_paths = {label: a.get_path_name() for label, a in existing.items()}
edited = []


def lighting_actor(label, cls, create=False):
    a = existing.get(label)
    if a is None:
        require(create and not VERIFY, 'Missing existing light ' + label)
        a = ACTORS.spawn_actor_from_class(cls, unreal.Vector(0, 0, 0))
        require(a is not None, 'Cannot create ' + label)
        a.set_actor_label(label)
        a.set_editor_property('is_spatially_loaded', False)
        a.set_actor_enable_collision(False)
        a.set_editor_property('tags', [unreal.Name('D17StormLighting')])
        existing[label] = a
    require(isinstance(a, cls), 'Actor class changed: ' + label)
    require(not a.get_editor_property('is_spatially_loaded'), 'Lighting must survive streaming')
    edited.append(a)
    return a


sun = lighting_actor('D02_Continuity_Sun', unreal.DirectionalLight)
sky = lighting_actor('D02_Continuity_Sky', unreal.SkyLight)
cloud = lighting_actor('D17_Storm_Clouds', unreal.VolumetricCloud, True)
fog = lighting_actor('D17_Storm_Fog', unreal.ExponentialHeightFog, True)
scalar(sun.light_component, 'intensity', SPEC['sun_lux'])
scalar(sun.light_component, 'light_source_angle', SPEC['sun_source_angle_degrees'])
scalar(sun.light_component, 'cast_cloud_shadows', True)
scalar(sun.light_component, 'cloud_shadow_strength', 0.8)
scalar(sky.light_component, 'intensity', SPEC['sky_intensity'])
scalar(sky.light_component, 'real_time_capture', True)
if not VERIFY:
    sun.light_component.set_light_color(unreal.LinearColor(*SPEC['sun_color_linear']))
sun_color = sun.light_component.get_light_color()
require(max(abs(getattr(sun_color, ch) - value) for ch, value in
            zip(('r', 'g', 'b', 'a'), SPEC['sun_color_linear'])) < 0.01, 'Sun light color mismatch')

parent = LIB.load_asset(SPEC['cloud_parent'])
require(parent is not None, 'Verified engine cloud material missing')
material = LIB.load_asset(SPEC['cloud_material']) if LIB.does_asset_exist(SPEC['cloud_material']) else None
if material is None:
    require(not VERIFY, 'Saved cloud material missing')
    directory, name = SPEC['cloud_material'].rsplit('/', 1)
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, directory, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
if not VERIFY:
    MATERIALS.set_material_instance_parent(material, parent)
require(material.get_editor_property('parent') == parent, 'Cloud parent changed')
for name, value in SPEC['cloud_scalars'].items():
    require(name in [str(n) for n in MATERIALS.get_scalar_parameter_names(parent)], 'Unknown cloud scalar')
    if not VERIFY:
        MATERIALS.set_material_instance_scalar_parameter_value(material, name, value)
    require(abs(MATERIALS.get_material_instance_scalar_parameter_value(material, name)-value) < 0.00001,
            'Saved scalar mismatch: ' + name)
for name, value in SPEC['cloud_vectors'].items():
    require(name in [str(n) for n in MATERIALS.get_vector_parameter_names(parent)], 'Unknown cloud vector')
    if not VERIFY:
        MATERIALS.set_material_instance_vector_parameter_value(material, name, unreal.LinearColor(*value))
    actual = MATERIALS.get_material_instance_vector_parameter_value(material, name)
    require(max(abs(getattr(actual, ch)-v) for ch, v in zip(('r','g','b','a'), value)) < 0.00001,
            'Saved vector mismatch: ' + name)
cc = cloud.get_component_by_class(unreal.VolumetricCloudComponent)
scalar(cc, 'material', material)
scalar(cc, 'layer_bottom_altitude', SPEC['cloud_base_km'])
scalar(cc, 'layer_height', SPEC['cloud_height_km'])
scalar(cc, 'sky_light_cloud_bottom_occlusion', 0.5)
fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
scalar(fc, 'fog_density', SPEC['fog_density'])
scalar(fc, 'fog_height_falloff', SPEC['fog_height_falloff'])
scalar(fc, 'enable_volumetric_fog', True)
scalar(fc, 'volumetric_fog_distance', SPEC['volumetric_fog_distance_cm'])
scalar(fc, 'volumetric_fog_scattering_distribution', 0.2)
scalar(fc, 'volumetric_fog_start_distance', 300.0)
if not VERIFY:
    fc.set_editor_property('fog_inscattering_luminance', unreal.LinearColor(*SPEC['fog_color_linear']))
actual = fc.get_editor_property('fog_inscattering_luminance')
require(max(abs(getattr(actual,ch)-v) for ch,v in zip(('r','g','b','a'),SPEC['fog_color_linear'])) < .00001,
        'Fog color readback mismatch')
if not VERIFY:
    require(LIB.save_loaded_asset(material), 'Cannot save cloud material')
    require(LEVEL.save_current_level(), 'Cannot save native lighting/external actors')
    require(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True), 'Cannot save lighting packages')
for label, path in before_paths.items():
    require(existing[label].get_path_name() == path, 'Preexisting actor identity changed')
descs = {str(desc.label): desc for desc in WP.get_actor_descs()}
packages = [str(descs[a.get_actor_label()].actor_package) for a in edited]
report = dict(task_id='D17-01', result='PASS', status='GENERATED_DRAFT', read_only=VERIFY,
    spec_sha256=hashlib.sha256(CONFIG.read_bytes()).hexdigest(), map=SPEC['map'],
    edited_actor_packages=packages, edited_actor_paths={a.get_actor_label(): a.get_path_name() for a in edited},
    cloud_material=material.get_path_name(), engine_parent=parent.get_path_name(),
    actor_count_before=len(before_paths), actor_count_after=len(existing),
    preexisting_actor_identities_preserved=True,
    scope='Lighting authoring/readback only; visual and gameplay acceptance require rendered runtime')
Path(os.environ['BIELLA_D17_STORM_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
print('D17_STORM COMPLETE')
