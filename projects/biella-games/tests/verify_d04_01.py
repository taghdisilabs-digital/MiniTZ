#!/usr/bin/env python3
"""Verify D04-01 content-registry and preserved population evidence."""

import json
import re
from pathlib import Path


def require(condition, message):
    if not condition:
        raise AssertionError(message)


EXPECTED_ACTORS = {
    "D04.Actor.InfectedStandard": {"role": "infected", "version": 1, "max_health": 70.0, "movement_speed": 210.0},
    "D04.Actor.RivalStandard": {"role": "rival", "version": 1, "max_health": 100.0, "movement_speed": 260.0},
}
EXPECTED_ENCOUNTER = "D04.Encounter.StreetPopulation"
EXPECTED_TUNING = "D04.Tuning.PopulationDevelopment"


def _actor_slot_expectation(index):
    if index % 4 == 0:
        return "D04.Actor.RivalStandard", "rival", 100.0, 260.0
    return "D04.Actor.InfectedStandard", "infected", 70.0, 210.0


def _verify_population_log(log, population_output):
    require("D04_CONTENT POPULATION_READY encounter=D04.Encounter.StreetPopulation encounter_version=1 "
            "tuning=D04.Tuning.PopulationDevelopment tuning_version=1 slots=36 variants=4 "
            "path=shared_population_admission" in log,
            "Population director did not report the structured encounter and tuning")
    require("D02_POP READY slots=36 max_active=4 budget=2" in log,
            "Preserved D02 population readiness changed")
    require("D04_CONTENT VALIDATION" not in log and "D04_CONTENT REGISTRY_REJECTED" not in log,
            "Content registry rejected definitions during population regression")
    require("D04_CONTENT POPULATION_REJECTED" not in log,
            "Population director rejected the structured encounter during regression")

    spawn_pattern = re.compile(
        r"D04_CONTENT SPAWN id=(\S+) variant=(\S+) variant_version=(\d+) "
        r"encounter=(\S+) encounter_version=(\d+) tuning=(\S+) tuning_version=(\d+) "
        r"role=(\S+) max_health=([\d.]+) movement_speed=([\d.]+) "
        r"path=(\S+) active=(\d+)")
    expected_ids = {f"D02Pop_Street03_{index:02d}" for index in range(4)}
    all_spawns = spawn_pattern.findall(log)
    spawns = [row for row in all_spawns if row[0] in expected_ids]
    require(len(spawns) == 4 and len({row[0] for row in spawns}) == 4,
            "D02 regression did not spawn four unique data-driven population actors")
    require({row[0] for row in spawns} == expected_ids,
            "Data-driven spawn identities changed the accepted D02 region")
    for row in spawns:
        slot_id, variant, version, encounter, encounter_version, tuning, tuning_version, role, health, speed, path, active = row
        index = int(slot_id.rsplit("_", 1)[1])
        expected_variant, expected_role, expected_health, expected_speed = _actor_slot_expectation(index)
        require(variant == expected_variant and role == expected_role and int(version) == 1,
                f"D04 spawn {slot_id} resolved the wrong structured actor variant")
        require(encounter == EXPECTED_ENCOUNTER and int(encounter_version) == 1,
                f"D04 spawn {slot_id} lost encounter identity/version")
        require(tuning == EXPECTED_TUNING and int(tuning_version) == 1,
                f"D04 spawn {slot_id} lost tuning identity/version")
        require(abs(float(health) - expected_health) < 0.01 and abs(float(speed) - expected_speed) < 0.01,
                f"D04 spawn {slot_id} lost effective definition values")
        require(path == "shared_population_spawn" and int(active) >= 1,
                f"D04 spawn {slot_id} did not use the reusable population spawn path")

    population_validation = json.loads((population_output / "validation.json").read_text(encoding="utf-8"))
    require(population_validation.get("result") == "PASS", "D02 population regression report is not PASS")
    return {
        "result": "PASS",
        "slots_spawned": len(spawns),
        "spawn_ids": sorted(row[0] for row in spawns),
        "variants": sorted({row[1] for row in spawns}),
        "path": "shared_population_spawn",
        "validation": str(population_output / "validation.json"),
    }


def verify(output, population_output=None, renderer="vulkan"):
    """Verify one fresh D04 runtime directory and its D02 population regression."""
    output = Path(output)
    content = json.loads((output / "content.json").read_text(encoding="utf-8"))
    require(content.get("task_id") == "D04-01" and content.get("result") == "PASS",
            "Native D04 content test did not produce a PASS report")

    actors = {row["content_id"]: row for row in content["registry"]["actor_variants"]}
    require(set(actors) == set(EXPECTED_ACTORS), "Native registry actor IDs changed")
    for content_id, expected in EXPECTED_ACTORS.items():
        actual = actors[content_id]
        require(actual["definition_version"] == expected["version"], f"{content_id} version was not preserved")
        require(actual["role"] == expected["role"], f"{content_id} role was not preserved")
        require(abs(actual["max_health"] - expected["max_health"]) < 0.01,
                f"{content_id} effective max health was not preserved")
        require(abs(actual["movement_speed"] - expected["movement_speed"]) < 0.01,
                f"{content_id} effective movement speed was not preserved")

    encounter = content["registry"]["encounter"]
    require(encounter["content_id"] == EXPECTED_ENCOUNTER and encounter["definition_version"] == 1,
            "Encounter identity/version was not preserved")
    require(encounter["tuning"]["content_id"] == EXPECTED_TUNING and encounter["tuning"]["required_definition_version"] == 1,
            "Encounter tuning reference/version was not preserved")
    require(encounter["regions"] == 3 and encounter["composition"] == 4 and encounter["slot_columns"] == 4,
            "Encounter composition/layout was not preserved")
    require(abs(encounter["slot_spacing"] - 340.0) < 0.01 and abs(encounter["row_spacing"] - 400.0) < 0.01,
            "Encounter spacing values were not preserved")

    tuning = content["registry"]["tuning"]
    require(tuning["content_id"] == EXPECTED_TUNING and tuning["definition_version"] == 1,
            "Tuning identity/version was not preserved")
    for key, value in {"max_active": 4, "spawn_budget": 2, "activation_distance": 5000.0,
                       "suspension_distance": 6500.0, "minimum_player_distance": 1000.0,
                       "admission_frame_ms": 25.0}.items():
        require(abs(tuning[key] - value) < 0.01, f"Effective tuning value changed: {key}")

    runtime = content["runtime"]
    require(runtime == {
        "content_ready": True,
        "encounter_id": EXPECTED_ENCOUNTER,
        "encounter_version": 1,
        "tuning_id": EXPECTED_TUNING,
        "tuning_version": 1,
        "slots": 36,
        "rivals": 9,
        "infected": 27,
        "path": "shared_population",
    }, "Native test did not report the exact reusable population result")

    negative = content["negative_controls"]
    for key, code in (("duplicate_definition", "duplicate_id"), ("missing_reference", "unresolved_reference"),
                      ("incompatible_reference", "incompatible_version"), ("malformed_tuning", "invalid_range"),
                      ("missing_definition_id", "missing_id")):
        require(code in negative[key], f"Negative control {key} did not report {code}")
    require(negative["missing_lookup"]["result"] == "rejected" and negative["missing_lookup"]["failure"] == "unresolved",
            "Missing runtime lookup did not fail explicitly")
    require(negative["incompatible_lookup"]["result"] == "rejected" and negative["incompatible_lookup"]["failure"] == "incompatible",
            "Incompatible runtime lookup did not fail explicitly")

    runtime_log = (output / "runtime.stdout.log").read_text(encoding="utf-8", errors="replace")
    require("**** TEST COMPLETE. EXIT CODE: 0 ****" in runtime_log,
            "D04 Unreal automation completion marker is missing")
    require(re.search(r"Result=\{Success\}.*Name=\{ContentRegistry\}", runtime_log),
            "ContentRegistry automation did not pass")
    require(not re.search(r"Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:|"
                          r"D04_CONTENT (VALIDATION|REGISTRY_REJECTED|POPULATION_REJECTED|SPAWN_REJECTED)", runtime_log),
            "D04 runtime reported a failed test, assertion or content rejection")

    slot_pattern = re.compile(
        r"D04_CONTENT SLOT id=(\S+) variant=(\S+) variant_version=(\d+) "
        r"encounter=(\S+) encounter_version=(\d+) tuning=(\S+) tuning_version=(\d+) "
        r"effective_max_health=([\d.]+) effective_movement_speed=([\d.]+) role=(\S+) path=(\S+)")
    slots = slot_pattern.findall(runtime_log)
    require(len(slots) == 36 and len({row[0] for row in slots}) == 36,
            "Structured population definition did not produce 36 stable slots")
    for row in slots:
        slot_id, variant, version, encounter_id, encounter_version, tuning_id, tuning_version, health, speed, role, path = row
        region, index_text = slot_id.rsplit("_", 1)
        index = int(index_text)
        expected_variant, expected_role, expected_health, expected_speed = _actor_slot_expectation(index)
        require(slot_id.startswith("D02Pop_") and region in {"D02Pop_Street01", "D02Pop_Street03", "D02Pop_Street05"},
                f"Unexpected stable D04 slot identity {slot_id}")
        require(variant == expected_variant and int(version) == 1 and role == expected_role,
                f"Slot {slot_id} did not use the shared variant implementation path")
        require(encounter_id == EXPECTED_ENCOUNTER and int(encounter_version) == 1 and
                tuning_id == EXPECTED_TUNING and int(tuning_version) == 1,
                f"Slot {slot_id} lost stable definition references")
        require(abs(float(health) - expected_health) < 0.01 and abs(float(speed) - expected_speed) < 0.01,
                f"Slot {slot_id} lost effective definition values")
        require(path == "shared_population_definition", f"Slot {slot_id} bypassed shared population definitions")

    population = None
    if population_output is not None:
        population_output = Path(population_output)
        population_log = (population_output / "runtime.stdout.log").read_text(encoding="utf-8", errors="replace")
        population = _verify_population_log(population_log, population_output)

    return {
        "result": "PASS",
        "capture_status": "GENERATED_DRAFT",
        "registry": {"actors": sorted(actors), "encounter": EXPECTED_ENCOUNTER, "tuning": EXPECTED_TUNING},
        "runtime": {"slots": len(slots), "rivals": sum(row[9] == "rival" for row in slots),
                    "infected": sum(row[9] == "infected" for row in slots), "path": "shared_population_definition"},
        "population": population,
        "renderer": renderer,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--population-output", type=Path)
    parser.add_argument("--renderer", choices=("vulkan", "nullrhi"), default="vulkan")
    args = parser.parse_args()
    print(json.dumps(verify(args.output, args.population_output, args.renderer), indent=2, sort_keys=True))
