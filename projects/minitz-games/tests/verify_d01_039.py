#!/usr/bin/env python3
"""Validate and compare D01-39 runtime JSONL timelines; no third-party packages."""

import argparse
import copy
import hashlib
import json
import math
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


CHECKPOINTS = ["active_baseline", "movement", "first_infected_defeated", "success",
               "restart_after_success", "failure", "restart_after_failure"]
BASELINE_FIELDS = ["phase", "health", "ammo", "infected_remaining", "objective_progress",
                   "target_count", "pressure", "pressure_revision"]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"JSON duplicate key: {key}")
        result[key] = value
    return result


def numeric(value, label):
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise AssertionError(f"{label} must be numeric") from error
    require(math.isfinite(result), f"{label} must be finite")
    return result


def read_capture(path):
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        require(line.strip(), f"{path}:{line_number}: empty JSONL record")
        try:
            event = json.loads(line, object_pairs_hook=strict_object)
        except ValueError as error:
            raise AssertionError(f"{path}:{line_number}: malformed JSON: {error}") from error
        label = f"{path}:{line_number}"
        require(isinstance(event, dict), f"{label}: event must be an object")
        require(event.get("schema") == "biella.demo01.telemetry/v1", f"{label}: unsupported schema")
        for field in ("session", "map", "event"):
            require(isinstance(event.get(field), str) and event[field], f"{label}: missing {field}")
        require(type(event.get("seq")) is int and event["seq"] == line_number,
                f"{label}: sequence must start at 1 and remain contiguous")
        require(type(event.get("restart_count")) is int and event["restart_count"] >= 0,
                f"{label}: invalid restart_count")
        require(isinstance(event.get("fields"), dict) and
                all(isinstance(k, str) and isinstance(v, str) for k, v in event["fields"].items()),
                f"{label}: fields must contain string values")
        for field in ("sim_seconds", "wall_seconds"):
            require(type(event.get(field)) in (int, float), f"{label}: {field} must be numeric")
            require(numeric(event[field], field) >= 0, f"{label}: {field} must be nonnegative")
        if events:
            previous = events[-1]
            require(event["session"] == previous["session"], f"{label}: session changed inside capture")
            require(previous["restart_count"] <= event["restart_count"] <= previous["restart_count"] + 1,
                    f"{label}: restart_count regressed or skipped")
            require(event["wall_seconds"] >= previous["wall_seconds"], f"{label}: wall_seconds regressed")
            # The restart request increments the GameInstance counter while the
            # old world still exists; the following new-world record resets time.
            # GameInstance shutdown can also occur after its world is destroyed.
            null_world_shutdown = (event["event"] == "telemetry_shutdown" and
                                   event["map"] == "none" and event["sim_seconds"] == 0)
            if (event["restart_count"] == previous["restart_count"] and
                    previous["event"] != "restart_requested" and not null_world_shutdown):
                require(event["sim_seconds"] >= previous["sim_seconds"], f"{label}: sim_seconds regressed without restart")
        events.append(event)
    require(events, f"{path}: empty telemetry")
    require(not any(event["event"] == "scenario_failed" for event in events), f"{path}: scenario_failed present")
    starts = [i for i, event in enumerate(events) if event["event"] == "scenario_begin"]
    ends = [i for i, event in enumerate(events) if event["event"] == "scenario_complete"]
    require(len(starts) == 1, f"{path}: expected one scenario_begin")
    require(len(ends) == 1 and ends[0] > starts[0], f"{path}: expected one final scenario_complete")
    scenario = events[starts[0]:ends[0] + 1]
    begin, complete = scenario[0]["fields"], scenario[-1]["fields"]
    require(begin.get("scenario") == complete.get("scenario") == "demo01_core_v1", f"{path}: incorrect scenario")
    require(begin.get("seed") == complete.get("seed") and begin.get("seed", "").isdigit(), f"{path}: inconsistent seed")
    require(abs(numeric(begin.get("fixed_delta"), "fixed_delta") - 1 / 60) < 0.000001,
            f"{path}: scenario must use a fixed 60 Hz step")
    require(complete.get("checkpoints") == "7", f"{path}: incomplete checkpoint count")
    checkpoints = [event for event in scenario if event["event"] == "checkpoint"]
    require([event["fields"].get("name") for event in checkpoints] == CHECKPOINTS, f"{path}: checkpoint order/integrity mismatch")
    base_restart = scenario[0]["restart_count"]
    require(scenario[-1]["restart_count"] - base_restart == 2, f"{path}: both terminal restarts are required")
    for checkpoint, expected_restart in zip(checkpoints, (0, 0, 0, 0, 1, 1, 2)):
        fields = checkpoint["fields"]
        require(all(key in fields for key in BASELINE_FIELDS), f"{path}: incomplete checkpoint baseline")
        require(fields.get("restart_relative") == str(expected_restart) and
                checkpoint["restart_count"] - base_restart == expected_restart,
                f"{path}: checkpoint restart mismatch")
        for key in BASELINE_FIELDS[1:]:
            require(numeric(fields[key], key) >= 0, f"{path}: negative checkpoint {key}")
    baseline = checkpoints[0]["fields"]
    require(baseline["phase"] == "Active" and numeric(baseline["health"], "health") == 100 and
            numeric(baseline["ammo"], "ammo") == 60 and numeric(baseline["target_count"], "target_count") == 2 and
            numeric(baseline["infected_remaining"], "infected_remaining") == 2 and
            all(numeric(baseline[key], key) == 0 for key in ("objective_progress", "pressure", "pressure_revision")),
            f"{path}: invalid clean Active baseline")
    for checkpoint in (checkpoints[4], checkpoints[6]):
        require(all(checkpoint["fields"][key] == baseline[key] for key in BASELINE_FIELDS),
                f"{path}: restart checkpoint does not match clean baseline")
    success, failure = checkpoints[3]["fields"], checkpoints[5]["fields"]
    first_defeat = checkpoints[2]["fields"]
    require(first_defeat["phase"] == "Active" and numeric(first_defeat["ammo"], "ammo") == 57 and
            numeric(first_defeat["infected_remaining"], "infected_remaining") == 1 and
            numeric(first_defeat["objective_progress"], "objective_progress") == 1,
            f"{path}: first infected checkpoint did not consume three shots and progress the objective")
    require(success["phase"] == "Success" and numeric(success["infected_remaining"], "infected_remaining") == 0 and
            numeric(success["ammo"], "ammo") == 54 and
            numeric(success["objective_progress"], "objective_progress") == numeric(success["target_count"], "target_count"),
            f"{path}: success checkpoint did not complete objective")
    require(failure["phase"] == "Failure" and numeric(failure["health"], "health") == 0,
            f"{path}: failure checkpoint did not defeat player")
    counts = Counter(event["event"] for event in scenario)
    required_events = {"weapon_fire", "damage", "defeat", "phase", "arena_pressure", "objective_activated",
                       "objective_progress", "objective_success", "restart_requested"}
    require(required_events <= counts.keys(), f"{path}: missing gameplay events: {sorted(required_events - counts.keys())}")
    require(counts["restart_requested"] == 2, f"{path}: expected two restart requests")
    require(counts["weapon_fire"] == 6, f"{path}: expected six resolved weapon_fire events")
    defeats = [event["fields"].get("target", "") for event in scenario if event["event"] == "defeat"]
    require(len(defeats) == 3 and defeats.count("player") == 1 and
            len({target for target in defeats if target.startswith("infected_")}) == 2,
            f"{path}: expected two distinct infected defeats and one player defeat")
    normalized = []
    for event in scenario:
        fields = dict(event["fields"])
        if event["event"] == "restart_requested":
            require(fields.get("restart_count", "").isdigit(), f"{path}: restart request missing count")
            fields["restart_count"] = str(int(fields["restart_count"]) - base_restart)
        normalized.append({"event": event["event"], "restart_relative": event["restart_count"] - base_restart, "fields": fields})
    return normalized, {"capture": str(path), "session": events[0]["session"], "records": len(events),
                        "scenario_events": len(scenario), "seed": int(begin["seed"]), "restart_count": 2,
                        "event_counts": dict(sorted(counts.items())),
                        "checkpoints": [event["fields"] for event in checkpoints],
                        "wall_seconds": events[-1]["wall_seconds"] - events[0]["wall_seconds"]}


def verify(paths):
    require(len(paths) >= 2, "At least two independent runtime captures are required")
    paths = [Path(path).resolve() for path in paths]
    require(len(set(paths)) == len(paths), "Capture paths must be independent")
    runs, reference = [], None
    for path in paths:
        normalized, summary = read_capture(path)
        require(summary["session"] not in {run["session"] for run in runs}, "Runtime sessions must be independent")
        if reference is None:
            reference = normalized
        else:
            for index in range(max(len(reference), len(normalized))):
                expected = reference[index] if index < len(reference) else None
                actual = normalized[index] if index < len(normalized) else None
                require(actual == expected, f"Deterministic divergence at event {index} in {path}: expected={expected}, actual={actual}")
        runs.append(summary)
    digest = hashlib.sha256(json.dumps(reference, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"task_id": "D01-39", "result": "PASS", "scenario": "demo01_core_v1", "trace_sha256": digest,
            "comparison": "ordered event + all fields + relative restart; session/sequence/map/timestamps excluded",
            "runs": runs}


def self_test():
    """Adversarial verifier fixtures are test data, never runtime evidence."""
    class VerifierTests(unittest.TestCase):
        def setUp(self):
            self.directory = tempfile.TemporaryDirectory()
            self.addCleanup(self.directory.cleanup)
            self.root = Path(self.directory.name)
            self.events = []
            self.restart = 0
            self.clock = 0
            self.add("scenario_begin", scenario="demo01_core_v1", seed="1337", fixed_delta="0.016667")
            self.checkpoint("active_baseline")
            self.checkpoint("movement")
            for ammo, health in ((59, 40), (58, 20), (57, 0)):
                self.add("weapon_fire", owner="player", target="infected_a", damage="20", ammo=str(ammo))
                self.add("damage", target="infected_a", source="player", amount="20", health=str(health), tag="weapon")
            self.add("defeat", target="infected_a", reason="weapon")
            self.add("arena_pressure", previous="Inactive", current="Rising", level="10", revision="1", reason="shot")
            self.add("objective_progress", id="Demo01ClearArena", progress="1", target="2", remaining="1", state="Active")
            self.checkpoint("first_infected_defeated", ammo="57", infected_remaining="1", objective_progress="1", pressure="10", pressure_revision="1")
            for ammo, health in ((56, 40), (55, 20), (54, 0)):
                self.add("weapon_fire", owner="player", target="infected_b", damage="20", ammo=str(ammo))
                self.add("damage", target="infected_b", source="player", amount="20", health=str(health), tag="weapon")
            self.add("defeat", target="infected_b", reason="weapon")
            self.add("objective_success", id="Demo01ClearArena", progress="2", target="2")
            self.add("phase", previous="Active", current="Success", objective="done")
            self.checkpoint("success", phase="Success", ammo="54", infected_remaining="0", objective_progress="2", pressure="10", pressure_revision="1")
            self.restart_match("Success")
            self.checkpoint("restart_after_success")
            self.add("damage", target="player", source="infected_a", amount="100", health="0", tag="melee")
            self.add("defeat", target="player", reason="melee")
            self.add("phase", previous="Active", current="Failure", objective="failed")
            self.checkpoint("failure", phase="Failure", health="0")
            self.restart_match("Failure")
            self.checkpoint("restart_after_failure")
            self.add("scenario_complete", scenario="demo01_core_v1", seed="1337", checkpoints="7")

        def add(self, event, **fields):
            self.clock += 0.02
            self.events.append({"schema": "biella.demo01.telemetry/v1", "session": "fixture-a", "seq": len(self.events) + 1,
                                "restart_count": self.restart, "sim_seconds": self.clock, "wall_seconds": len(self.events) * 0.1,
                                "map": "/Game/Maps/BiellaGameplayMap", "event": event, "fields": fields})

        def checkpoint(self, name, **changes):
            fields = dict(name=name, phase="Active", health="100", ammo="60", infected_remaining="2", objective_progress="0",
                          target_count="2", pressure="0", pressure_revision="0", restart_relative=str(self.restart))
            fields.update(changes)
            self.add("checkpoint", **fields)

        def restart_match(self, phase):
            self.restart += 1
            self.add("restart_requested", previous_phase=phase, restart_count=str(self.restart), map="BiellaGameplayMap")
            self.clock = 0
            self.add("objective_activated", id="Demo01ClearArena", version="1", target="2")

        def captures(self, mutate=None):
            other = copy.deepcopy(self.events)
            for event in other:
                event["session"] = "fixture-b"
                event["wall_seconds"] += 10
                event["sim_seconds"] += 5
                event["restart_count"] += 4
                if event["event"] == "restart_requested":
                    event["fields"]["restart_count"] = str(int(event["fields"]["restart_count"]) + 4)
            if mutate:
                mutate(other)
            paths = [self.root / "a.jsonl", self.root / "b.jsonl"]
            for path, events in zip(paths, [self.events, other]):
                path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
            return paths

        def test_independent_sessions_allow_clock_and_restart_offsets(self):
            self.assertEqual(verify(self.captures())["result"], "PASS")

        def test_missing_completion_rejected(self):
            with self.assertRaisesRegex(AssertionError, "scenario_complete"):
                verify(self.captures(lambda events: events.pop()))

        def test_changed_health_rejected(self):
            def mutate(events):
                next(e for e in events if e["event"] == "damage")["fields"]["health"] = "10"
            with self.assertRaisesRegex(AssertionError, "divergence"):
                verify(self.captures(mutate))

        def test_reordered_gameplay_events_rejected(self):
            def mutate(events):
                events[3]["event"], events[4]["event"] = events[4]["event"], events[3]["event"]
                events[3]["fields"], events[4]["fields"] = events[4]["fields"], events[3]["fields"]
            with self.assertRaisesRegex(AssertionError, "divergence"):
                verify(self.captures(mutate))

        def test_duplicate_sequence_rejected(self):
            with self.assertRaisesRegex(AssertionError, "sequence"):
                verify(self.captures(lambda events: events[4].update(seq=4)))

        def test_missing_sequence_rejected(self):
            with self.assertRaisesRegex(AssertionError, "sequence"):
                verify(self.captures(lambda events: events.pop(4)))

        def test_clock_regression_rejected(self):
            with self.assertRaisesRegex(AssertionError, "sim_seconds"):
                verify(self.captures(lambda events: events[4].update(sim_seconds=0)))

        def append_shutdown(self, events, event="telemetry_shutdown", map_name="none"):
            shutdown = copy.deepcopy(events[-1])
            shutdown.update(event=event, map=map_name, sim_seconds=0, fields={}, seq=len(events) + 1)
            events.append(shutdown)

        def test_null_world_shutdown_clock_reset_allowed(self):
            self.assertEqual(verify(self.captures(self.append_shutdown))["result"], "PASS")

        def test_ordinary_event_null_world_clock_reset_rejected(self):
            with self.assertRaisesRegex(AssertionError, "sim_seconds"):
                verify(self.captures(lambda events: self.append_shutdown(events, event="damage")))

        def test_live_world_shutdown_clock_reset_rejected(self):
            with self.assertRaisesRegex(AssertionError, "sim_seconds"):
                verify(self.captures(lambda events: self.append_shutdown(events, map_name="BiellaGameplayMap")))

        def test_wall_clock_regression_on_restart_rejected(self):
            def mutate(events):
                next(e for e in events if e["restart_count"] == 5)["wall_seconds"] = 0
            with self.assertRaisesRegex(AssertionError, "wall_seconds"):
                verify(self.captures(mutate))

        def test_nonfinite_time_rejected(self):
            with self.assertRaisesRegex(AssertionError, "finite"):
                verify(self.captures(lambda events: events[4].update(sim_seconds=float("nan"))))

        def test_restart_baseline_damage_rejected(self):
            def mutate(events):
                next(e for e in events if e["fields"].get("name") == "restart_after_success")["fields"]["health"] = "50"
            with self.assertRaisesRegex(AssertionError, "baseline"):
                verify(self.captures(mutate))

        def test_reused_session_rejected(self):
            with self.assertRaisesRegex(AssertionError, "independent"):
                verify(self.captures(lambda events: [e.update(session="fixture-a") for e in events]))

        def test_malformed_json_rejected(self):
            paths = self.captures()
            paths[1].write_text(paths[1].read_text() + "{broken\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "JSON"):
                verify(paths)

        def test_single_run_rejected(self):
            with self.assertRaisesRegex(AssertionError, "two"):
                verify(self.captures()[:1])

        def test_failure_marker_with_completion_rejected(self):
            def mutate(events):
                events[-1]["event"] = "scenario_failed"
                complete = copy.deepcopy(self.events[-1])
                complete.update(session="fixture-b", seq=len(events) + 1, restart_count=6,
                                sim_seconds=events[-1]["sim_seconds"], wall_seconds=events[-1]["wall_seconds"])
                events.append(complete)
            with self.assertRaisesRegex(AssertionError, "scenario_failed"):
                verify(self.captures(mutate))

        def test_missing_successful_shot_rejected(self):
            def mutate(events):
                next(e for e in events if e["event"] == "weapon_fire")["event"] = "weapon_blocked"
            with self.assertRaisesRegex(AssertionError, "six resolved"):
                verify(self.captures(mutate))

        def test_wrong_initial_ammunition_rejected(self):
            def mutate(events):
                next(e for e in events if e["fields"].get("name") == "active_baseline")["fields"]["ammo"] = "59"
            with self.assertRaisesRegex(AssertionError, "baseline"):
                verify(self.captures(mutate))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(VerifierTests))
    return result.wasSuccessful()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", type=Path, nargs="*")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        sys.exit(0 if self_test() else 1)
    try:
        print(json.dumps(verify(args.captures), indent=2))
    except (AssertionError, OSError, ValueError) as error:
        print(json.dumps({"task_id": "D01-39", "result": "FAIL", "error": str(error)}))
        sys.exit(1)
