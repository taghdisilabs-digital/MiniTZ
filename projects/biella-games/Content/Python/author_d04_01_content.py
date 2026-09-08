"""Author and read back D04-01's versioned population content definitions.

The JSON file is the editable Project source.  This script materializes the
same stable definitions as native UDataAssets under /Game/Data/D04 and has a
read-only mode for a fresh-process compatibility check.

Author:
  UnrealEditor-Cmd BiellaGames.uproject -run=pythonscript
    -script=Content/Python/author_d04_01_content.py -EnablePlugins=PythonScriptPlugin
    -unattended -nullrhi -nosound -nop4 -BiellaContentAuthoringOutput=<report>

Readback adds -D04VerifyContent and never writes an asset.
"""

import hashlib
import json
import os
from pathlib import Path

import unreal


PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / "Content/Data/D04/D04-01-content.json"
ROOT = "/Game/Data/D04"
VERIFY = "-D04VerifyContent" in unreal.SystemLibrary.get_command_line()
LIB = unreal.EditorAssetLibrary
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()


def require(ok, message):
    if not ok:
        raise RuntimeError("D04_CONTENT AUTHORING FAIL: " + message)


def command_value(prefix):
    for token in unreal.SystemLibrary.get_command_line().split():
        if token.startswith(prefix):
            return token[len(prefix):]
    return None


report_value = (os.environ.get("BIELLA_D04_CONTENT_REPORT") or
                command_value("-BiellaContentAuthoringOutput="))
REPORT = Path(report_value) if report_value else PROJECT / "Build/Content/D04-01/authoring.json"
SOURCE_SHA = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
SPEC = json.loads(SOURCE.read_text(encoding="utf-8"))
require(SPEC.get("schema") == "biella.content/v1", "unexpected source schema")
require(SPEC.get("task_id") == "D04-01", "unexpected source task")


def asset(name, cls):
    path = ROOT + "/" + name
    result = LIB.load_asset(path) if LIB.does_asset_exist(path) else None
    if result is None:
        require(not VERIFY, "missing runtime asset " + path)
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", cls)
        result = ASSETS.create_asset(name, ROOT, cls, factory)
    require(result is not None, "cannot create/load " + path)
    require(result.get_class() == cls, path + ": incompatible asset class")
    return result


def set_and_check(obj, prop, value, label):
    if not VERIFY:
        obj.set_editor_property(prop, value)
    actual = obj.get_editor_property(prop)
    if isinstance(value, float):
        require(abs(float(actual) - value) < 0.0001, label + ": " + prop)
    else:
        require(actual == value, label + ": " + prop + " readback mismatch")
    return actual


def set_name_and_check(obj, prop, value, label):
    return set_and_check(obj, prop, unreal.Name(value), label)


def set_vector_and_check(obj, prop, values, label):
    vector = unreal.Vector(*values)
    if not VERIFY:
        obj.set_editor_property(prop, vector)
    actual = obj.get_editor_property(prop)
    require(max(abs(float(getattr(actual, axis)) - float(expected))
                 for axis, expected in zip(("x", "y", "z"), values)) < 0.0001,
            label + ": " + prop + " readback mismatch")
    return actual


def reference(spec):
    result = unreal.BiellaContentReference()
    result.set_editor_property("content_id", unreal.Name(spec["content_id"]))
    result.set_editor_property("required_definition_version", spec["required_definition_version"])
    return result


def reference_report(value):
    return {
        "content_id": str(value.get_editor_property("content_id")),
        "required_definition_version": int(value.get_editor_property("required_definition_version")),
    }


def author_actor_variants(classes, definitions):
    output = []
    for spec in definitions:
        label = spec["content_id"]
        data = asset("DA_ActorVariant_" + label.rsplit(".", 1)[-1], classes["actor"])
        set_name_and_check(data, "content_id", label, label)
        set_and_check(data, "definition_version", spec["definition_version"], label)
        role = getattr(unreal.BiellaActorVariantRole, spec["role"].upper())
        set_and_check(data, "role", role, label)
        actor_class = unreal.load_class(None, spec["actor_class"])
        require(actor_class is not None, label + ": missing actor class")
        set_and_check(data, "actor_class", actor_class, label)
        for prop, key in (
            ("max_health", "max_health"),
            ("movement_speed", "movement_speed"),
            ("max_pressure_movement_multiplier", "max_pressure_movement_multiplier"),
            ("aggro_range", "aggro_range"),
            ("attack_range", "attack_range"),
            ("attack_damage", "attack_damage"),
            ("attack_cooldown", "attack_cooldown"),
            ("weapon_range", "weapon_range"),
            ("weapon_damage", "weapon_damage"),
            ("weapon_cooldown", "weapon_cooldown"),
            ("preferred_distance", "preferred_distance"),
        ):
            if key in spec:
                set_and_check(data, prop, float(spec[key]), label)
        if not VERIFY:
            LIB.set_metadata_tag(data, "D04.SourceSHA256", SOURCE_SHA)
            LIB.set_metadata_tag(data, "D04.Status", "GENERATED_DRAFT")
            require(LIB.save_loaded_asset(data), label + ": asset save failed")
        output.append({
            "content_id": str(data.get_editor_property("content_id")),
            "definition_version": int(data.get_editor_property("definition_version")),
            "role": spec["role"],
            "actor_class": str(data.get_editor_property("actor_class")),
            "effective": {
                prop: float(data.get_editor_property(prop))
                for prop in ("max_health", "movement_speed", "max_pressure_movement_multiplier",
                             "aggro_range", "attack_range", "attack_damage", "attack_cooldown",
                             "weapon_range", "weapon_damage", "weapon_cooldown", "preferred_distance")
            },
            "asset": "/Game/Data/D04/" + data.get_name(),
        })
    return output


def author_tuning(classes, spec):
    label = spec["content_id"]
    data = asset("DA_Tuning_" + label.rsplit(".", 1)[-1], classes["tuning"])
    set_name_and_check(data, "content_id", label, label)
    set_and_check(data, "definition_version", spec["definition_version"], label)
    for prop, key in (("max_active", "max_active"), ("spawn_budget", "spawn_budget"),
                      ("activation_distance", "activation_distance"),
                      ("suspension_distance", "suspension_distance"),
                      ("minimum_player_distance", "minimum_player_distance"),
                      ("admission_frame_ms", "admission_frame_ms")):
        value = float(spec[key]) if isinstance(spec[key], float) else spec[key]
        set_and_check(data, prop, value, label)
    if not VERIFY:
        LIB.set_metadata_tag(data, "D04.SourceSHA256", SOURCE_SHA)
        LIB.set_metadata_tag(data, "D04.Status", "GENERATED_DRAFT")
        require(LIB.save_loaded_asset(data), label + ": asset save failed")
    return {
        "content_id": str(data.get_editor_property("content_id")),
        "definition_version": int(data.get_editor_property("definition_version")),
        "effective": {prop: data.get_editor_property(prop) for prop in (
            "max_active", "spawn_budget", "activation_distance", "suspension_distance",
            "minimum_player_distance", "admission_frame_ms")},
        "asset": "/Game/Data/D04/" + data.get_name(),
    }


def author_encounter(classes, spec):
    label = spec["content_id"]
    data = asset("DA_Encounter_" + label.rsplit(".", 1)[-1], classes["encounter"])
    set_name_and_check(data, "content_id", label, label)
    set_and_check(data, "definition_version", spec["definition_version"], label)
    tuning_reference = reference(spec["tuning"])
    if not VERIFY:
        data.set_editor_property("tuning", tuning_reference)
    require(reference_report(data.get_editor_property("tuning")) == spec["tuning"],
            label + ": tuning reference readback")

    regions = []
    for region_spec in spec["regions"]:
        region = unreal.BiellaEncounterRegionDefinition()
        region.set_editor_property("region_id", unreal.Name(region_spec["region_id"]))
        region.set_editor_property("center", unreal.Vector(*region_spec["center"]))
        region.set_editor_property("slot_count", region_spec["slot_count"])
        regions.append(region)
    if not VERIFY:
        data.set_editor_property("regions", regions)
    actual_regions = list(data.get_editor_property("regions"))
    require(len(actual_regions) == len(regions), label + ": region count")
    region_report = []
    for actual, expected in zip(actual_regions, spec["regions"]):
        require(str(actual.get_editor_property("region_id")) == expected["region_id"], label + ": region id")
        center = actual.get_editor_property("center")
        require(max(abs(float(getattr(center, axis)) - float(value))
                   for axis, value in zip(("x", "y", "z"), expected["center"])) < 0.0001,
                label + ": region center")
        require(int(actual.get_editor_property("slot_count")) == expected["slot_count"], label + ": region slots")
        region_report.append({
            "region_id": str(actual.get_editor_property("region_id")),
            "center": [float(center.x), float(center.y), float(center.z)],
            "slot_count": int(actual.get_editor_property("slot_count")),
        })

    set_and_check(data, "slot_columns", spec["slot_columns"], label)
    set_and_check(data, "slot_spacing", float(spec["slot_spacing"]), label)
    set_and_check(data, "row_spacing", float(spec["row_spacing"]), label)

    composition = []
    for member_spec in spec["composition"]:
        member = unreal.BiellaEncounterMemberDefinition()
        member.set_editor_property("actor_variant", reference(member_spec["actor_variant"]))
        composition.append(member)
    if not VERIFY:
        data.set_editor_property("composition", composition)
    actual_composition = list(data.get_editor_property("composition"))
    require(len(actual_composition) == len(composition), label + ": composition count")
    composition_report = [reference_report(member.get_editor_property("actor_variant"))
                          for member in actual_composition]
    require(composition_report == [member["actor_variant"] for member in spec["composition"]],
            label + ": composition readback")

    if not VERIFY:
        LIB.set_metadata_tag(data, "D04.SourceSHA256", SOURCE_SHA)
        LIB.set_metadata_tag(data, "D04.Status", "GENERATED_DRAFT")
        require(LIB.save_loaded_asset(data), label + ": asset save failed")
    return {
        "content_id": str(data.get_editor_property("content_id")),
        "definition_version": int(data.get_editor_property("definition_version")),
        "tuning": reference_report(data.get_editor_property("tuning")),
        "regions": region_report,
        "slot_columns": int(data.get_editor_property("slot_columns")),
        "slot_spacing": float(data.get_editor_property("slot_spacing")),
        "row_spacing": float(data.get_editor_property("row_spacing")),
        "composition": composition_report,
        "asset": "/Game/Data/D04/" + data.get_name(),
    }


def main():
    classes = {
        "actor": unreal.load_class(None, "/Script/BiellaGames.BiellaActorVariantData"),
        "encounter": unreal.load_class(None, "/Script/BiellaGames.BiellaEncounterData"),
        "tuning": unreal.load_class(None, "/Script/BiellaGames.BiellaTuningData"),
    }
    require(all(classes.values()), "D04 native data classes are unavailable")
    definitions = SPEC["definitions"]
    report = {
        "task_id": "D04-01",
        "result": "FAIL",
        "mode": "verify" if VERIFY else "author",
        "source": str(SOURCE),
        "source_sha256": SOURCE_SHA,
        "actor_variants": author_actor_variants(classes, definitions["actor_variants"]),
        "tunings": [author_tuning(classes, definitions["tunings"][0])],
        "encounters": [author_encounter(classes, definitions["encounters"][0])],
    }
    report["result"] = "PASS"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unreal.log("D04_CONTENT AUTHORING COMPLETE mode=" + report["mode"] + " report=" + str(REPORT))


try:
    main()
except Exception as error:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"task_id": "D04-01", "result": "FAIL", "mode": "verify" if VERIFY else "author",
                                  "error": str(error), "source": str(SOURCE), "source_sha256": SOURCE_SHA},
                                 indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raise
