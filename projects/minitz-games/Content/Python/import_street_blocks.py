"""Import authored street geometry, preserve six existing actors, read back saved assets."""
import hashlib
import json
import os
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
VERIFY = '-D03VerifyArchitecture' in unreal.SystemLibrary.get_command_line()
LIB = unreal.EditorAssetLibrary
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
MATERIALS = unreal.MaterialEditingLibrary
MESHES = (unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
          or unreal.get_default_object(unreal.StaticMeshEditorSubsystem))
ROOT = '/Game/OpenWorld'
SOURCE = PROJECT / 'SourceAssets/Architecture/street-blocks.json'
MANIFEST = json.loads(SOURCE.read_text())
REPORT = Path(os.environ['BIELLA_D03_ARCHITECTURE_REPORT'])


def asset(path, cls, factory):
    result = LIB.load_asset(path) if LIB.does_asset_exist(path) else None
    if result is None:
        assert not VERIFY, 'Missing saved asset: ' + path
        folder, name = path.rsplit('/', 1)
        result = ASSETS.create_asset(name, folder, cls, factory)
    assert isinstance(result, cls), path
    return result


def vector(v):
    return [float(v.x), float(v.y), float(v.z)]


def invariant(actor):
    r = actor.get_actor_rotation()
    return dict(guid=unreal.GuidLibrary.conv_guid_to_string(actor.get_editor_property('actor_guid')),
                location=vector(actor.get_actor_location()), scale=vector(actor.get_actor_scale3d()),
                rotation=[r.pitch, r.yaw, r.roll], tags=[str(t) for t in actor.tags],
                spatial=actor.get_editor_property('is_spatially_loaded'),
                hlod=actor.get_editor_property('hlod_layer').get_path_name(),
                collision=str(actor.static_mesh_component.get_collision_profile_name()))


# Opaque sealed glazing and zinc use actual roughness/metallic inputs. Concrete
# retains the proven filtered world-space surface material and HLOD usage.
finish = asset(ROOT+'/Materials/M_FacadeFinish', unreal.Material, unreal.MaterialFactoryNew())
if not VERIFY:
    MATERIALS.delete_all_material_expressions(finish)
    for cls, name, default, prop, y in [
        (unreal.MaterialExpressionVectorParameter, 'BaseColor', unreal.LinearColor(.1,.1,.1,1), unreal.MaterialProperty.MP_BASE_COLOR, 0),
        (unreal.MaterialExpressionScalarParameter, 'Roughness', .4, unreal.MaterialProperty.MP_ROUGHNESS, 150),
        (unreal.MaterialExpressionScalarParameter, 'Metallic', 0., unreal.MaterialProperty.MP_METALLIC, 300),
    ]:
        node = MATERIALS.create_material_expression(finish, cls, -300, y)
        node.set_editor_property('parameter_name', name)
        node.set_editor_property('default_value', default)
        assert MATERIALS.connect_material_property(node, '', prop)
    MATERIALS.set_base_material_usage(finish, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES, True)
    MATERIALS.set_base_material_usage(finish, unreal.MaterialUsage.MATUSAGE_NANITE, True)
    assert not MATERIALS.recompile_material(finish), 'Finish compiler errors'
    LIB.set_metadata_tag(finish, 'D03.Status', 'GENERATED_DRAFT')
    LIB.save_loaded_asset(finish)
assert MATERIALS.has_material_usage(finish, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
assert MATERIALS.has_material_usage(finish, unreal.MaterialUsage.MATUSAGE_NANITE)
materials = {'Concrete': LIB.load_asset(ROOT+'/Materials/MI_Wall')}
surface = materials['Concrete'].get_editor_property('parent')
assert surface.get_path_name() == ROOT+'/Materials/M_ProductionSurface.M_ProductionSurface'
if not VERIFY:
    MATERIALS.set_base_material_usage(surface, unreal.MaterialUsage.MATUSAGE_NANITE, True)
    assert not MATERIALS.recompile_material(surface)
    LIB.save_loaded_asset(surface)
assert MATERIALS.has_material_usage(surface, unreal.MaterialUsage.MATUSAGE_NANITE)
specs = dict(PaintedFrame=((.075,.10,.105,1),.38,0), SealedGlazing=((.032,.052,.065,1),.19,0),
             Zinc=((.40,.43,.45,1),.34,1), Terracotta=((.29,.105,.058,1),.84,0))
for name, (color, roughness, metallic) in specs.items():
    mat = asset(ROOT+'/Materials/MIC_Facade'+name, unreal.MaterialInstanceConstant,
                unreal.MaterialInstanceConstantFactoryNew())
    if not VERIFY:
        MATERIALS.set_material_instance_parent(mat, finish)
        MATERIALS.set_material_instance_vector_parameter_value(mat, 'BaseColor', unreal.LinearColor(*color))
        MATERIALS.set_material_instance_scalar_parameter_value(mat, 'Roughness', roughness)
        MATERIALS.set_material_instance_scalar_parameter_value(mat, 'Metallic', metallic)
        LIB.set_metadata_tag(mat, 'D03.Status', 'GENERATED_DRAFT')
        LIB.save_loaded_asset(mat)
    assert mat.get_editor_property('parent') == finish
    assert abs(MATERIALS.get_material_instance_scalar_parameter_value(mat, 'Roughness')-roughness) < .001
    assert abs(MATERIALS.get_material_instance_scalar_parameter_value(mat, 'Metallic')-metallic) < .001
    materials[name] = mat

meshes = []
for entry in MANIFEST['assets']:
    source = PROJECT/'SourceAssets/Architecture'/entry['fbx']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == entry['sha256']
    path = ROOT+'/Architecture/'+entry['mesh']
    existing_mesh = LIB.load_asset(path) if LIB.does_asset_exist(path) else None
    if existing_mesh is None or (not VERIFY and LIB.get_metadata_tag(existing_mesh, 'D03.SourceSHA256') != entry['sha256']):
        assert not VERIFY, 'Missing mesh: '+path
        task = unreal.AssetImportTask()
        task.filename = str(source)
        task.destination_path = ROOT+'/Architecture'
        task.destination_name = entry['mesh']
        task.automated = True
        task.replace_existing = True
        task.save = True
        options = unreal.FbxImportUI()
        options.import_mesh = True
        options.import_as_skeletal = False
        options.import_materials = False
        options.import_textures = False
        options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
        options.automated_import_should_detect_type = False
        options.static_mesh_import_data.combine_meshes = True
        options.static_mesh_import_data.auto_generate_collision = False
        task.options = options
        ASSETS.import_asset_tasks([task])
    mesh = LIB.load_asset(path)
    assert isinstance(mesh, unreal.StaticMesh), path
    slots = mesh.get_editor_property('static_materials')
    assert len(slots) == 5, 'Unexpected FBX material topology'
    names = [str(slot.get_editor_property('imported_material_slot_name')) for slot in slots]
    assert set(names) == set(materials), names
    if not VERIFY:
        for i, name in enumerate(names):
            mesh.set_material(i, materials[name])
        settings = MESHES.get_nanite_settings(mesh)
        settings.enabled = True
        settings.generate_fallback = unreal.NaniteGenerateFallback.ENABLED
        settings.fallback_target = unreal.NaniteFallbackTarget.PERCENT_TRIANGLES
        settings.fallback_percent_triangles = 1.
        settings.keep_percent_triangles = 1.
        MESHES.set_nanite_settings(mesh, settings, True)
        MESHES.remove_collisions(mesh)
        assert MESHES.add_simple_collisions(mesh, unreal.ScriptCollisionShapeType.BOX) >= 0
        LIB.set_metadata_tag(mesh, 'D03.SourceSHA256', entry['sha256'])
        LIB.set_metadata_tag(mesh, 'D03.Status', 'GENERATED_DRAFT')
        LIB.save_loaded_asset(mesh)
    bounds = mesh.get_bounds()
    assert max(abs(v-50) for v in vector(bounds.box_extent)) < .01, str(bounds)
    assert bounds.origin.length() < .01
    settings = MESHES.get_nanite_settings(mesh)
    assert settings.enabled and settings.fallback_percent_triangles == 1
    assert settings.fallback_target == unreal.NaniteFallbackTarget.PERCENT_TRIANGLES
    assert settings.generate_fallback == unreal.NaniteGenerateFallback.ENABLED
    assert MESHES.get_simple_collision_count(mesh) == 1 and MESHES.get_convex_collision_count(mesh) == 0
    body = mesh.get_editor_property('body_setup')
    boxes = body.get_editor_property('agg_geom').get_editor_property('box_elems')
    assert len(boxes) == 1
    collision_size = [float(boxes[0].get_editor_property(axis)) for axis in ('x','y','z')]
    assert all(abs(v-100)<.02 for v in collision_size), collision_size
    assert LIB.get_metadata_tag(mesh, 'D03.SourceSHA256') == entry['sha256']
    assert mesh.get_num_triangles(0) > 1000, 'Fallback geometry unexpectedly reduced'
    for i, name in enumerate(names):
        assert mesh.get_material(i) == materials[name]
    meshes.append(dict(asset=path, source_sha256=entry['sha256'], extent=vector(bounds.box_extent),
        collision_size=collision_size, fallback_triangles=mesh.get_num_triangles(0),
        nanite=True, fallback_percent=1, material_slots=names))

level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert level.load_level('/Game/Maps/BiellaOpenWorldMap')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
wp = unreal.WorldPartitionBlueprintLibrary
descs = wp.get_actor_descs()
wp.load_actors([desc.guid for desc in descs])
actors = {a.get_actor_label():a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
changes = []
for region in range(6):
    label = f'D02_Region_{region:02d}_Block'
    actor = actors[label]
    before = invariant(actor)
    mesh = LIB.load_asset(meshes[region]['asset'])
    component = actor.static_mesh_component
    previous = component.static_mesh.get_path_name()
    if not VERIFY:
        # Runtime setters do not dirty World Partition external actor packages.
        actor.modify()
        component.modify()
        component.set_static_mesh(mesh)
        for i in range(5):
            component.set_material(i, mesh.get_material(i))
    assert component.static_mesh == mesh
    assert invariant(actor) == before, 'Authoritative actor state changed: '+label
    assert before['location'] == [float(region*4000),-2400.,600.+region*50]
    assert before['scale'] == [16.,14.,12.+region]
    assert before['collision'] == 'BlockAll' and before['spatial']
    changes.append(dict(label=label, before=before, after=invariant(actor), previous_mesh=previous,
                        mesh=mesh.get_path_name()))
if not VERIFY:
    assert level.save_current_level()
    assert unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
REPORT.write_text(json.dumps(dict(result='PASS', mode='readback' if VERIFY else 'author',
    source_manifest_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(), meshes=meshes, actors=changes), indent=2)+'\n')
unreal.log('D03_ARCHITECTURE COMPLETE')
