"""Add/read back bounded cosmetic ground in the existing world without rewriting its actors."""
import hashlib
import json
import os
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
SOURCE = PROJECT / 'SourceAssets/Architecture/ground-support.json'
SPEC = json.loads(SOURCE.read_text())
COMMAND = unreal.SystemLibrary.get_command_line()
VERIFY = '-D03VerifyGroundSupport' in COMMAND
PROBE = '-D03ProbeGroundSupport' in COMMAND
REPORT = Path(os.environ['BIELLA_D03_GROUND_REPORT'])
LIB = unreal.EditorAssetLibrary
MATERIALS = unreal.MaterialEditingLibrary
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def invariant(a):
    r = a.get_actor_rotation()
    meshes = []
    for c in a.get_components_by_class(unreal.StaticMeshComponent):
        meshes.append(dict(name=c.get_name(), mesh=c.static_mesh.get_path_name() if c.static_mesh else None,
            collision=str(c.get_collision_profile_name()), enabled=str(c.get_collision_enabled()),
            materials=[c.get_material(i).get_path_name() if c.get_material(i) else None
                       for i in range(c.get_num_materials())]))
    return dict(guid=unreal.GuidLibrary.conv_guid_to_string(a.get_editor_property('actor_guid')),
        cls=a.get_class().get_path_name(), location=vec(a.get_actor_location()),
        scale=vec(a.get_actor_scale3d()), rotation=[r.pitch,r.yaw,r.roll], tags=[str(t) for t in a.tags],
        spatial=a.get_editor_property('is_spatially_loaded'), meshes=meshes)


assert LEVEL.load_level('/Game/Maps/BiellaOpenWorldMap')
wp = unreal.WorldPartitionBlueprintLibrary
wp.load_actors([d.guid for d in wp.get_actor_descs()])
actors = {a.get_actor_label():a for a in ACTORS.get_all_level_actors()}
old = {label:invariant(a) for label,a in actors.items() if label != SPEC['label']}
ground = actors.get(SPEC['label'])
if PROBE:
    REPORT.write_text(json.dumps(dict(result='PASS', mode='probe', ground_present=ground is not None,
        existing_actors=old, source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest()),indent=2)+'\n')
    unreal.log('D03_GROUND COMPLETE probe')
else:
    master = LIB.load_asset('/Game/OpenWorld/Materials/M_ProductionSurface')
    assert isinstance(master, unreal.Material)
    material = LIB.load_asset(SPEC['material']) if LIB.does_asset_exist(SPEC['material']) else None
    if not material:
        assert not VERIFY, 'Ground material missing'
        folder,name = SPEC['material'].rsplit('/',1)
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,folder,
            unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
    parameters = dict(Roughness=SPEC['roughness'], DetailScale=SPEC['detail_scale'], ReliefCm=SPEC['relief_cm'])
    if not VERIFY:
        MATERIALS.set_material_instance_parent(material,master)
        MATERIALS.set_material_instance_vector_parameter_value(material,'BaseColor',unreal.LinearColor(*SPEC['base_color']))
        for name,value in parameters.items():
            MATERIALS.set_material_instance_scalar_parameter_value(material,name,value)
        LIB.set_metadata_tag(material,'D03.Status','GENERATED_DRAFT')
        LIB.set_metadata_tag(material,'D03.SourceSHA256',hashlib.sha256(SOURCE.read_bytes()).hexdigest())
        assert LIB.save_loaded_asset(material)
    assert material.get_editor_property('parent') == master
    for name,value in parameters.items():
        assert abs(MATERIALS.get_material_instance_scalar_parameter_value(material,name)-value)<1e-5
    color = MATERIALS.get_material_instance_vector_parameter_value(material,'BaseColor')
    assert all(abs(a-b)<1e-5 for a,b in zip((color.r,color.g,color.b,color.a),SPEC['base_color']))
    if not ground:
        assert not VERIFY, 'Ground actor missing'
        ground = ACTORS.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*SPEC['location_cm']))
        ground.set_actor_label(SPEC['label'])
    mesh = LIB.load_asset(SPEC['mesh'])
    c = ground.static_mesh_component
    if not VERIFY:
        ground.modify(); c.modify()
        ground.set_actor_location(unreal.Vector(*SPEC['location_cm']),False,False)
        ground.set_actor_rotation(unreal.Rotator(),False)
        ground.set_actor_scale3d(unreal.Vector(*[v/100 for v in SPEC['size_cm']]))
        ground.set_editor_property('is_spatially_loaded',False)
        ground.set_editor_property('enable_auto_lod_generation',False)
        ground.set_editor_property('tags',['D03GroundSupport','D03GeneratedDraft'])
        c.set_static_mesh(mesh)
        c.set_material(0,material)
        c.set_collision_profile_name('NoCollision')
        c.set_editor_property('can_ever_affect_navigation',False)
        c.set_editor_property('cast_shadow',False)
        c.set_editor_property('mobility',unreal.ComponentMobility.STATIC)
        assert LEVEL.save_current_level()
        assert unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True)
    assert vec(ground.get_actor_location()) == SPEC['location_cm']
    assert vec(ground.get_actor_scale3d()) == [v/100 for v in SPEC['size_cm']]
    assert not ground.get_editor_property('is_spatially_loaded')
    assert not ground.get_editor_property('enable_auto_lod_generation')
    assert c.static_mesh == mesh and c.get_material(0) == material
    assert c.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
    assert not c.get_editor_property('can_ever_affect_navigation') and not c.get_editor_property('cast_shadow')
    after = {label:invariant(a) for label,a in actors.items() if label != SPEC['label']}
    assert after == old, 'Existing actor invariants changed'
    desc = next(d for d in wp.get_actor_descs() if str(d.label) == SPEC['label'])
    assert '/__ExternalActors__/' in str(desc.actor_package)
    REPORT.write_text(json.dumps(dict(result='PASS', mode='readback' if VERIFY else 'author',
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(), existing_actors=after,
        ground=invariant(ground), ground_package=str(desc.actor_package), no_collision=True,
        no_navigation=True, always_loaded=True, hlod_excluded=True, status='GENERATED_DRAFT'),indent=2)+'\n')
    unreal.log('D03_GROUND COMPLETE')
