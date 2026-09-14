"""Correct Demo 01's authored lighting for its real-time runtime arena.

UnrealEditor-Cmd <project.uproject> -run=pythonscript -script=<this file>
  -EnablePlugins=PythonScriptPlugin -unattended -nullrhi -nosound -nop4

Add -D01VerifyReadabilityLighting for a fresh-process read-only check.
The baseline at Build/Demo01/D01-040-lighting-baseline.log records actor names,
transforms, component geometry/collision, and original map file identities
before editing. Existing baseline evidence is preserved on repeat runs.
The only authored changes are movable daylight/skylight, captured-scene sky
lighting, and disabling precomputed lighting in these runtime-generated maps.
The runtime recaptures the sky after arena construction. Continuous capture
requires an atmosphere or sky dome, which these maps do not contain.
"""

import hashlib
import json
from pathlib import Path

import unreal


PROJECT = Path(__file__).resolve().parents[2]
BASELINE = PROJECT / "Build/Demo01/D01-040-lighting-baseline.log"
MAPS = ("/Game/Maps/BiellaGameplayMap", "/Game/Maps/BiellaGameplayMap_Recovered")
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
VERIFY_ONLY = "-D01VerifyReadabilityLighting" in unreal.SystemLibrary.get_command_line()


def require(condition, message):
    if not condition:
        raise RuntimeError("D01_040_LIGHTING FAIL: " + message)


def values(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def rotation(rotator):
    return [float(rotator.pitch), float(rotator.yaw), float(rotator.roll)]


def snapshot(actors):
    result = []
    for actor in actors:
        entry = {"name": actor.get_name(), "label": actor.get_actor_label(),
                 "class": actor.get_class().get_path_name(),
                 "location": values(actor.get_actor_location()),
                 "rotation": rotation(actor.get_actor_rotation()),
                 "scale": values(actor.get_actor_scale3d()), "components": []}
        for component in actor.get_components_by_class(unreal.SceneComponent):
            detail = {"name": component.get_name(), "class": component.get_class().get_path_name(),
                      "location": values(component.get_editor_property("relative_location")),
                      "rotation": rotation(component.get_editor_property("relative_rotation")),
                      "scale": values(component.get_editor_property("relative_scale3d"))}
            if isinstance(component, unreal.PrimitiveComponent):
                detail["collision_profile"] = str(component.get_collision_profile_name())
                detail["collision_enabled"] = str(component.get_collision_enabled())
            if isinstance(component, unreal.StaticMeshComponent):
                mesh = component.get_editor_property("static_mesh")
                detail["static_mesh"] = mesh.get_path_name() if mesh else None
                detail["materials"] = [component.get_material(i).get_path_name()
                                       if component.get_material(i) else None
                                       for i in range(component.get_num_materials())]
            entry["components"].append(detail)
        entry["components"].sort(key=lambda item: item["name"])
        result.append(entry)
    return sorted(result, key=lambda item: item["name"])


baseline = json.loads(BASELINE.read_text()) if BASELINE.exists() and BASELINE.stat().st_size else {}
require(not VERIFY_ONLY or baseline, "Read-only verification requires initial baseline evidence")
for asset_path in MAPS:
    require(LEVEL.load_level(asset_path), "Cannot load " + asset_path)
    world = EDITOR.get_editor_world()
    world_settings = world.get_world_settings()
    actors = ACTORS.get_all_level_actors()
    before = snapshot(actors)
    if asset_path not in baseline:
        require(not VERIFY_ONLY, "Baseline is missing " + asset_path)
        map_file = PROJECT / "Content" / (asset_path.removeprefix("/Game/") + ".umap")
        baseline[asset_path] = {"actors": before, "original_sha256": hashlib.sha256(map_file.read_bytes()).hexdigest()}
        BASELINE.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    require(before == baseline[asset_path]["actors"], "Actor/geometry/collision baseline changed: " + asset_path)
    suns = [actor for actor in actors if isinstance(actor, unreal.DirectionalLight)]
    skies = [actor for actor in actors if isinstance(actor, unreal.SkyLight)]
    require(len(suns) == 1 and len(skies) == 1, "Expected one authored sun and sky: " + asset_path)
    sun = suns[0].get_component_by_class(unreal.DirectionalLightComponent)
    sky = skies[0].get_component_by_class(unreal.SkyLightComponent)
    if not VERIFY_ONLY:
        world_settings.set_editor_property("force_no_precomputed_lighting", True)
        sun.set_mobility(unreal.ComponentMobility.MOVABLE)
        sky.set_mobility(unreal.ComponentMobility.MOVABLE)
        sky.set_editor_property("real_time_capture", False)
        require(LEVEL.save_current_level(), "Cannot save " + asset_path)
    require(world_settings.get_editor_property("force_no_precomputed_lighting"), "Precomputed lighting still enabled")
    require(sun.get_editor_property("mobility") == unreal.ComponentMobility.MOVABLE, "Sun must be movable")
    require(sky.get_editor_property("mobility") == unreal.ComponentMobility.MOVABLE, "Sky must be movable")
    require(not sky.get_editor_property("real_time_capture"), "Sky requires explicit scene recapture")
    require(snapshot(ACTORS.get_all_level_actors()) == baseline[asset_path]["actors"],
            "Actor/geometry/collision changed while configuring lighting")
    unreal.log("D01_040_LIGHTING PASS " + json.dumps({
        "map": asset_path, "actor_count": len(actors), "actor_geometry_collision_preserved": True,
        "sun": suns[0].get_name(), "sky": skies[0].get_name(), "mobility": "Movable",
        "real_time_sky_capture": False, "force_no_precomputed_lighting": True,
        "read_only": VERIFY_ONLY,
    }, sort_keys=True))
