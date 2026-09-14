"""Author/read back D02-01's editable streamed continuation blockout.

UnrealEditor-Cmd BiellaGames.uproject -run=pythonscript -script=<this path>
  -EnablePlugins=PythonScriptPlugin -unattended -nullrhi -nosound -nop4
Add -D02VerifyOpenWorld for a fresh-process read-only asset check.

The fixture deliberately assigns no city identity or final art canon. Demo 01
maps/materials are inputs, never modified. Existing D02 actors are updated by
stable label so interrupted authoring can resume without replacing actor GUIDs.
Native World Partition owns loading; Python never runs in gameplay.
"""

import json
import math
import hashlib
import os
from pathlib import Path

import unreal


PROJECT = Path(__file__).resolve().parents[2]
MAP = "/Game/Maps/BiellaOpenWorldMap"
ROOT = "/Game/OpenWorld"
VERIFY = "-D02VerifyOpenWorld" in unreal.SystemLibrary.get_command_line()
GEOMETRY_ONLY = "-D02GeometryOnly" in unreal.SystemLibrary.get_command_line()
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
AUTHORING = unreal.BiellaWorldAuthoring
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
LIB = unreal.EditorAssetLibrary
WP = unreal.WorldPartitionBlueprintLibrary
SYSTEM = unreal.get_default_object(unreal.SystemLibrary)
MATERIALS = unreal.MaterialEditingLibrary
INSTANCE_USAGE = unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES
DEMO_MATERIAL_FILE = PROJECT / "Content/Materials/M_DemoReadability.uasset"
DEMO_MATERIAL_SHA = hashlib.sha256(DEMO_MATERIAL_FILE.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError("D02_OPEN_WORLD FAIL: " + message)


def asset(path, cls, factory):
    result = LIB.load_asset(path) if LIB.does_asset_exist(path) else None
    if result is None:
        require(not VERIFY, "Missing asset " + path)
        directory, name = path.rsplit("/", 1)
        result = ASSETS.create_asset(name, directory, cls, factory)
    require(result is not None, "Cannot create/load " + path)
    return result


def check_property(obj, name, value):
    if not VERIFY:
        obj.set_editor_property(name, value)
    actual = obj.get_editor_property(name)
    if isinstance(value, list):
        actual = list(actual)
    require(actual == value, str(obj) + ": unexpected " + name)


if LIB.does_asset_exist(MAP):
    require(LEVEL.load_level(MAP), "Cannot load continuation map")
else:
    require(not VERIFY, "Missing continuation map")
    require(LEVEL.new_level(MAP, is_partitioned_world=True), "Cannot create partitioned world")

world = EDITOR.get_editor_world()
settings = world.get_world_settings()
partition = settings.get_editor_property("world_partition")
require(partition is not None, "World Partition must be native map data")
require(AUTHORING.is_native_streaming_enabled(world), "Native distance streaming must be enabled")
check_property(settings, "force_no_precomputed_lighting", True)
mode = unreal.load_class(None, "/Script/BiellaGames.BiellaOpenWorldGameMode")
infected_class = unreal.load_class(None, "/Script/BiellaGames.BiellaStreamingInfected")
require(GEOMETRY_ONLY or (mode is not None and infected_class is not None), "Build D02 C++ runtime classes first")
if not GEOMETRY_ONLY:
    check_property(settings, "default_game_mode", mode)

# A resumed/readback process explicitly loads external actors for inspection;
# this editor operation does not pin them or alter gameplay streaming state.
descs = WP.get_actor_descs()
if descs:
    WP.load_actors([desc.guid for desc in descs])
existing = {actor.get_actor_label(): actor for actor in ACTORS.get_all_level_actors()}

hlod = asset(ROOT + "/HLOD/HLOD_Continuation", unreal.HLODLayer, unreal.HLODLayerFactory())
check_property(hlod, "layer_type", unreal.HLODLayerType.INSTANCING)
check_property(hlod, "parent_layer", None)
check_property(partition, "default_hlod_layer", hlod)
hash_class = unreal.load_class(None, "/Script/Engine.WorldPartitionRuntimeHashSet")
runtime_hash = AUTHORING.get_runtime_hash(world)
require(runtime_hash.get_class() == hash_class, "Expected UE 5.8 RuntimeHashSet")
partitions = list(runtime_hash.get_editor_property("RuntimePartitions"))
require(len(partitions) == 1, "Expected one bounded continuation grid")
main = partitions[0].get_editor_property("MainLayer")
check_property(main, "CellSize", 4000)
check_property(main, "LoadingRange", 5000)
check_property(main, "bIs2D", True)
check_property(main, "bBlockOnSlowStreaming", True)
setups = list(partitions[0].get_editor_property("HLODSetups"))
require(len(setups) > 0, "Native grid must have HLOD setup")
setup = setups[0]
check_property(setup, "HLODLayers", [hlod])
hlod_partition = setup.get_editor_property("PartitionLayer")
check_property(hlod_partition, "CellSize", 8000)
check_property(hlod_partition, "LoadingRange", 60000)
if not VERIFY:
    partitions[0].set_editor_property("HLODSetups", [setup])
    runtime_hash.set_editor_property("RuntimePartitions", partitions)

factory = unreal.DataAssetFactory()
factory.set_editor_property("data_asset_class", unreal.DataLayerAsset)
layer_asset = asset(ROOT + "/DataLayers/DL_Continuation", unreal.DataLayerAsset, factory)
check_property(layer_asset, "data_layer_type", unreal.DataLayerType.RUNTIME)
layer = AUTHORING.continuation_data_layer(world, layer_asset, VERIFY)
require(layer is not None, "Cannot create runtime data layer")
check_property(layer, "initial_runtime_state", unreal.DataLayerRuntimeState.ACTIVATED)

parent_path = ROOT + "/Materials/M_ProductionSurface"
parent_material = LIB.load_asset(parent_path) if LIB.does_asset_exist(parent_path) else None
require(parent_material is not None, "Run build_production_surfaces.py before world authoring")
if not VERIFY:
    MATERIALS.set_base_material_usage(parent_material, INSTANCE_USAGE, True)
    require(not MATERIALS.recompile_material(parent_material), "Continuation material compiler errors")
require(MATERIALS.has_material_usage(parent_material, INSTANCE_USAGE), "HLOD base material must support instancing")
cube = LIB.load_asset("/Engine/BasicShapes/Cube")
require(parent_material is not None and cube is not None, "Missing proven geometry/material inputs")
materials = {}
for name, color in {
    "Street": (0.08, 0.10, 0.12, 1),
    "Wall": (0.23, 0.28, 0.30, 1),
    "Route": (0.50, 0.47, 0.28, 1),
    "Interior": (0.24, 0.30, 0.28, 1),
}.items():
    mat = asset(ROOT + "/Materials/MI_" + name,
                unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    if not VERIFY:
        unreal.MaterialEditingLibrary.set_material_instance_parent(mat, parent_material)
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
            mat, "BaseColor", unreal.LinearColor(*color))
    require(mat.get_editor_property("parent") == parent_material, "Material parent changed")
    require(MATERIALS.has_material_usage(mat, INSTANCE_USAGE), "Material instance lacks HLOD instancing usage: " + name)
    materials[name] = mat

authored = []


def actor(label, cls, location, rotation=(0, 0, 0), spatial=True, tags=()):
    result = existing.get(label)
    if result is None:
        require(not VERIFY, "Missing actor " + label)
        result = ACTORS.spawn_actor_from_class(cls, unreal.Vector(*location), unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        require(result is not None, "Cannot spawn " + label)
        result.set_actor_label(label)
        existing[label] = result
    if not VERIFY:
        result.set_actor_location(unreal.Vector(*location), False, False)
        result.set_actor_rotation(unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]), False)
        result.set_editor_property("is_spatially_loaded", spatial)
        result.set_editor_property("tags", list(dict.fromkeys(
            [str(tag) for tag in result.get_editor_property("tags")] + ["D02Continuation", *tags])))
        if spatial:
            require(AUTHORING.add_actor_to_layer(result, layer), "Cannot assign runtime Data Layer " + label)
    require(result.get_editor_property("is_spatially_loaded") == spatial, label + ": spatial flag")
    position = result.get_actor_location()
    require(max(abs(position.x-location[0]), abs(position.y-location[1]), abs(position.z-location[2])) < .01,
            label + ": placement changed")
    authored.append(result)
    return result


def box(label, center, size, material="Wall", tags=(), rotation=(0, 0, 0), collision=True):
    result = actor(label, unreal.StaticMeshActor, center, rotation, tags=tags)
    mesh = result.static_mesh_component
    # D03 replaces only the six building visuals. Retain normalized bounds and
    # the original actor/collision contract when D02 authoring is replayed.
    native_mesh = cube
    if label.startswith("D02_Region_") and label.endswith("_Block"):
        facade_path = ROOT + "/Architecture/SM_StreetBlock_" + label.split("_")[2]
        if LIB.does_asset_exist(facade_path):
            native_mesh = LIB.load_asset(facade_path)
    if not VERIFY:
        result.set_actor_scale3d(unreal.Vector(*(value / 100.0 for value in size)))
        mesh.set_static_mesh(native_mesh)
        mesh.set_mobility(unreal.ComponentMobility.STATIC)
        if native_mesh == cube:
            mesh.set_material(0, materials[material])
        else:
            for slot in range(len(native_mesh.get_editor_property("static_materials"))):
                mesh.set_material(slot, native_mesh.get_material(slot))
        mesh.set_collision_profile_name("BlockAll" if collision else "NoCollision")
        result.set_editor_property("hlod_layer", hlod)
        result.set_editor_property("enable_auto_lod_generation", True)
    require(mesh.get_editor_property("static_mesh") == native_mesh, label + ": missing native mesh")
    scale = result.get_actor_scale3d()
    require(max(abs(scale.x-size[0]/100), abs(scale.y-size[1]/100), abs(scale.z-size[2]/100)) < .001,
            label + ": collision geometry dimensions changed")
    actual_rotation = result.get_actor_rotation()
    require(max(abs(actual_rotation.pitch-rotation[0]), abs(actual_rotation.yaw-rotation[1]),
                abs(actual_rotation.roll-rotation[2])) < .001, label + ": surface rotation changed")
    require(mesh.get_material(0) == materials[material], label + ": material changed")
    if native_mesh != cube:
        for slot in range(len(native_mesh.get_editor_property("static_materials"))):
            require(mesh.get_material(slot) == native_mesh.get_material(slot), label + ": facade material changed")
    require(str(mesh.get_collision_profile_name()) == ("BlockAll" if collision else "NoCollision"),
            label + ": collision profile changed")
    require(result.get_editor_property("hlod_layer") == hlod, label + ": missing HLOD assignment")
    return result


for region in range(6):
    x = region * 4000
    tag = "D02Region%02d" % region
    prefix = "D02_Region_%02d_" % region
    box(prefix + "Floor", (x, 0, -50), (4000, 3200, 100), "Street", (tag, "D02StreetFloor"))
    # The road remains collision-contiguous. Low edge markers preserve sight
    # lines and make unloaded near geometry distinguishable from distant HLOD.
    box(prefix + "SouthEdge", (x, -1575, 35), (4000, 50, 70), "Wall", (tag,))
    for stripe in range(4):
        box(prefix + "Stripe_%d" % stripe, (x - 1500 + stripe * 1000, -250, 1.5),
            (400, 12, 3), "Route", (tag,), collision=False)
    if region not in (2, 3):
        box(prefix + "NorthEdge", (x, 1575, 35), (4000, 50, 70), "Wall", (tag,))
    # Blockout street-side masses demonstrate retained distant silhouettes.
    box(prefix + "Block", (x, -2400, 600 + region * 50),
        (1600, 1400, 1200 + region * 100), "Wall", (tag,))

box("D02_Interior_Floor", (8000, 2250, -50), (2000, 1500, 100), "Interior", ("D02Interior",))
box("D02_Interior_Back", (8000, 3025, 300), (2100, 50, 600), tags=("D02Interior",))
box("D02_Interior_West", (6975, 2250, 300), (50, 1500, 600), tags=("D02Interior",))
box("D02_Interior_East", (9025, 2250, 300), (50, 1500, 600), tags=("D02Interior",))
box("D02_Interior_DoorWest", (7400, 1500, 300), (800, 50, 600), tags=("D02Interior",))
box("D02_Interior_DoorEast", (8600, 1500, 300), (800, 50, 600), tags=("D02Interior",))
box("D02_Interior_Roof", (8000, 2250, 675), (2100, 1550, 50), tags=("D02Interior",))

# Cube's local +Y axis rises under negative Unreal Roll. Offset the center by
# the rotated half-thickness so the top plane meets exactly z0 and z400.
angle = math.atan2(400, 2000)
box("D02_Terrace_Ramp", (10000, 2000 + 20 * math.sin(angle), 200 - 20 * math.cos(angle)),
    (400, math.hypot(2000, 400), 40), "Interior", ("D02Ramp",),
    rotation=(0, 0, -math.degrees(angle)))
box("D02_Terrace_Floor", (10000, 3500, 350), (2000, 1000, 100), "Interior", ("D02Terrace",))
box("D02_Terrace_BackRail", (10000, 3975, 460), (2000, 50, 120), tags=("D02Terrace",))
box("D02_Terrace_WestRail", (9025, 3500, 460), (50, 1000, 120), tags=("D02Terrace",))
box("D02_Terrace_EastRail", (10975, 3500, 460), (50, 1000, 120), tags=("D02Terrace",))

if not GEOMETRY_ONLY:
    infected = actor("D02_Continuity_Infected", infected_class, (1000, 600, 90), tags=("D02PersistentEntity",))
    check_property(infected, "persistent_id", unreal.Name("continuity_infected"))
actor("D02_PlayerStart", unreal.PlayerStart, (0, 0, 88), spatial=False)
sun = actor("D02_Continuity_Sun", unreal.DirectionalLight, (10000, 0, 2000), (-48, -32, 0), spatial=False)
sky = actor("D02_Continuity_Sky", unreal.SkyLight, (10000, 0, 2000), spatial=False)
atmosphere = actor("D02_Continuity_Atmosphere", unreal.load_class(None, "/Script/Engine.SkyAtmosphere"),
                   (0, 0, 0), spatial=False)
interior_light = actor("D02_Interior_Light", unreal.PointLight, (8000, 2250, 520),
                       tags=("D02Interior", "D02InteriorLight"))
if not VERIFY:
    sun.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sun.light_component.set_intensity(5.0)
    sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_property("real_time_capture", True)
    sky.light_component.set_intensity(1.0)
    interior_light.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    interior_light.light_component.set_light_color(unreal.LinearColor(1, 1, 1, 1))
check_property(sun.light_component, "atmosphere_sun_light", True)
check_property(sky.light_component, "real_time_capture", True)
check_property(sky.light_component, "intensity", 1.0)
check_property(sun.light_component, "intensity", 5.0)
check_property(interior_light.light_component, "intensity_units", unreal.LightUnits.LUMENS)
check_property(interior_light.light_component, "intensity", 12000.0)
check_property(interior_light.light_component, "attenuation_radius", 2600.0)
check_property(interior_light.light_component, "use_inverse_squared_falloff", True)
check_property(interior_light.light_component, "source_radius", 20.0)
check_property(interior_light.light_component, "cast_shadows", True)
check_property(interior_light, "enable_auto_lod_generation", False)
for light in (sun, sky, interior_light):
    require(light.light_component.get_editor_property("mobility") == unreal.ComponentMobility.MOVABLE,
            "Lighting must remain valid during native cell streaming")

if not VERIFY:
    require(LEVEL.save_current_level(), "Cannot save map/external actors")
    require(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True), "Cannot save authored native assets")

descs = WP.get_actor_descs()
by_label = {str(desc.label): desc for desc in descs}
hlod_descs = [desc for desc in descs
              if desc.native_class.get_path_name() == "/Script/Engine.WorldPartitionHLOD"]
hlod_actors = []
for desc in hlod_descs:
    # Instancing HLODs are intentionally filtered from ordinary editor loading.
    # Read their exact external packages without changing editor loading policy.
    require(unreal.load_package(str(desc.actor_package)), "Cannot read saved HLOD package")
    item = unreal.find_object(None, str(desc.actor_path))
    require(item is not None, "Cannot resolve saved HLOD actor " + str(desc.actor_path))
    hlod_actors.append(item)
hlod_geometry = []
for item in hlod_actors:
    components = item.get_components_by_class(unreal.InstancedStaticMeshComponent)
    geometry = {"actor": item.get_actor_label(),
                "instances": sum(component.get_instance_count() for component in components),
                "materials": []}
    for component in components:
        for slot in range(component.get_num_materials()):
            mat = component.get_material(slot)
            require(mat is not None and mat.get_path_name().startswith(ROOT + "/Materials/"),
                    "HLOD material slot fell back to a default material")
            require(MATERIALS.has_material_usage(mat, INSTANCE_USAGE), "HLOD slot material lacks instancing usage")
            geometry["materials"].append(mat.get_path_name())
    hlod_geometry.append(geometry)
if VERIFY:
    require(hlod_geometry and all(item["instances"] > 0 for item in hlod_geometry),
            "Run native WorldPartitionHLODsBuilder; saved HLOD instance geometry is required")
for item in authored:
    label = item.get_actor_label()
    require(label in by_label, "Missing external actor descriptor " + label)
    desc = by_label[label]
    require("/__ExternalActors__/" in str(desc.actor_package), "OFPA package missing " + label)
    if item.get_editor_property("is_spatially_loaded"):
        paths = [SYSTEM.call_method("BreakSoftObjectPath", (path,)) for path in desc.data_layer_assets]
        require(layer_asset.get_path_name() in paths,
                "Runtime Data Layer missing from saved descriptor " + label + ": " +
                str(paths) + " expected " + layer_asset.get_path_name())

require(hashlib.sha256(DEMO_MATERIAL_FILE.read_bytes()).hexdigest() == DEMO_MATERIAL_SHA,
        "Demo 01 material bytes changed during continuation authoring")
report = {
    "task": "D02-01", "result": "GEOMETRY_ONLY" if GEOMETRY_ONLY else "PASS", "map": MAP, "read_only": VERIFY,
    "world_partition": partition.get_class().get_path_name(),
    "runtime_hash": runtime_hash.get_class().get_path_name(),
    "cell_size_cm": 4000, "loading_range_cm": 5000, "bBlockOnSlowStreaming": True,
    "hlod_layer": hlod.get_path_name(), "hlod_loading_range_cm": 60000,
    "built_hlod_geometry": hlod_geometry,
    "instancing_material": parent_material.get_path_name(),
    "instancing_usage_verified": True,
    "demo_material_sha256_preserved": DEMO_MATERIAL_SHA,
    "lighting": {"native_atmosphere": atmosphere.get_actor_label(),
                 "sun_lux": 5.0, "atmosphere_sun_light": True,
                 "sky_real_time_capture": True, "sky_intensity": 1.0,
                 "interior_light": {"location_cm": [8000, 2250, 520],
                                    "lumens": 12000.0, "attenuation_radius_cm": 2600.0,
                                    "source_radius_cm": 20.0, "casts_shadows": True,
                                    "inverse_square_falloff": True, "spatial": True}},
    "data_layer": layer_asset.get_path_name(), "initial_runtime_state": "Activated",
    "actors": [{"label": item.get_actor_label(),
                "package": str(by_label[item.get_actor_label()].actor_package),
                "spatial": bool(item.get_editor_property("is_spatially_loaded"))} for item in authored],
    "street_centers_x_cm": list(range(0, 20001, 4000)),
    "street_surface_z_cm": 0, "interior_waypoint": [8000, 2300, 88],
    "ramp_surface_endpoints": [[10000, 1000, 0], [10000, 3000, 400]],
    "terrace_waypoint": [10000, 3400, 488],
    "scope": "Editable continuity blockout; no city identity, shipping scale or final visual-quality acceptance",
}
output = PROJECT / "Build/OpenWorld" / ("D02-01-map-readback.json" if VERIFY else "D02-01-map-authoring.json")
if VERIFY and os.environ.get("BIELLA_WORLD_READBACK_REPORT"):
    output = Path(os.environ["BIELLA_WORLD_READBACK_REPORT"])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
unreal.log("D02_OPEN_WORLD PASS " + json.dumps(report, sort_keys=True))
if "-ExecutePythonScript=" in unreal.SystemLibrary.get_command_line():
    unreal.SystemLibrary.quit_editor()
