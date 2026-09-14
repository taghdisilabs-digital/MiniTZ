#!/usr/bin/env python3
"""Verify D01-031's real SharedInteraction automation log, excluding startup AI."""
import json
import math
from pathlib import Path
import re
import sys

PHASES = [
    "collision_and_damage_guards", "input_hits_infected",
    "rival_retargets_after_infected_defeat", "rival_defeats_player",
    "defeated_player_stops", "infected_attacks_rival", "player_defeats_rival",
    "infected_retargets_after_rival_defeat", "player_defeats_infected",
    "defeated_ai_stays_stopped",
]
TEAMS = {"player": 0, "rival": 1, "infected": 2}
ATTACKS = {  # tag: role, default damage, minimum interval, resolved-hit signal
    "player_fire": ("player", 34.0, 0.25, "WEAPON_FIRE"),
    "rival_fire": ("rival", 14.0, 0.9, "RIVAL_FIRE"),
    "infected_melee": ("infected", 12.0, 0.85, "INFECTED_MELEE"),
}


def verify(path):
    content = path.read_text(encoding="utf-8", errors="replace")
    assert "D01_031_TEST FAIL" not in content, "runtime assertion failed"
    assert "**** TEST COMPLETE. EXIT CODE: 0 ****" in content, "automation did not exit successfully"
    roles, health, ammo, active = {}, {}, {}, set()
    phases, spawns, edges, last_attack, intervals = [], [], {}, {}, {}
    pending, complete, first_time, now, defeats = None, False, None, 0.0, set()
    last_state = None
    for number, line in enumerate(content.splitlines(), 1):
        match = re.search(r"D01_(031_TEST|SIGNAL) (\w+)\s*(.*)", line)
        if not match:
            continue
        domain, event, payload = match.groups()
        d = dict(re.findall(r"(\w+)=([^\s]+)", payload))
        where = f"line {number}: {event}"
        if domain == "031_TEST" and event == "STATE":
            assert pending is None, f"{where}: damage lacks resolved attack/feedback"
            if d["event"] in {"encounter_a_spawn", "encounter_b_spawn"}:
                spawns.append(d["event"])
                active = {d[role] for role in TEAMS}
                assert len(active) == 3, f"{where}: fixture identities overlap"
                for role in TEAMS:
                    actor = d[role]
                    assert actor not in roles, f"{where}: fixture reused actor identity"
                    roles[actor], health[actor] = role, 70.0 if role == "infected" else 100.0
                ammo[d["player"]] = 60
                if first_time is None:
                    first_time = float(d["time"])
            assert active == {d[role] for role in TEAMS}, f"{where}: unregistered fixture"
            now = float(d["time"])
            assert math.isfinite(now) and now >= first_time, f"{where}: invalid world time"
            for role in TEAMS:
                assert float(d[f"{role}_health"]) == health[d[role]], f"{where}: {role} health mismatch"
            assert int(d["ammo"]) == ammo[d["player"]], f"{where}: player ammo mismatch"
            last_state = d["event"]
        if first_time is None:
            continue
        if domain == "031_TEST":
            if event == "PASS":
                assert d["phase"] == last_state, f"{where}: pass has no matching state"
                phases.append(d["phase"])
            elif event == "COMPLETE":
                assert pending is None, f"{where}: unfinished damage feedback"
                assert d["input"] == "enhanced" and d["ai"] == "world_ticks", "wrong runtime mode"
                assert "Result={Success} Name={SharedInteraction} Path={BiellaGames.Demo01.SharedInteraction}" in content.split(line, 1)[1], "no subsequent automation success"
                complete = True
                break
            continue
        if event == "DAMAGE":
            source, target = d["source"], d["target"]
            if source not in roles and target not in roles:
                continue
            assert pending is None, f"{where}: preceding damage lacks attack/feedback"
            assert phases and phases[0] == PHASES[0], f"{where}: negative guard caused damage"
            assert source in active and target in active, f"{where}: inactive/unknown actor in damage"
            assert health[source] > 0 and health[target] > 0, f"{where}: defeated actor dealt/received damage"
            source_role, target_role = roles[source], roles[target]
            assert source_role != target_role, f"{where}: self/friendly damage"
            assert int(d["source_team"]) == TEAMS[source_role] and int(d["target_team"]) == TEAMS[target_role], f"{where}: team mismatch"
            role, maximum, cadence, signal = ATTACKS[d["tag"]]
            assert role == source_role, f"{where}: wrong damage tag for source"
            amount, after, time = (float(d[key]) for key in ("amount", "health", "time"))
            assert all(math.isfinite(v) for v in (amount, after, time)), f"{where}: non-finite damage state"
            assert amount > 0 and after >= 0 and time >= now, f"{where}: invalid damage state/time"
            assert amount == min(maximum, health[target]) and after == health[target] - amount, f"{where}: damage arithmetic/clamp mismatch"
            if source in last_attack:
                interval = time - last_attack[source]
                assert interval + 0.002 >= cadence, f"{where}: {role} cooldown violated ({interval:.3f})"
                intervals[role] = min(intervals.get(role, interval), interval)
            last_attack[source], health[target], now = time, after, time
            edge = f"{source_role}_to_{target_role}"
            edges[edge] = edges.get(edge, 0) + 1
            pending = (source, target, amount, signal, set())
        elif event in {"HIT_REACTION", "COMBAT_FEEDBACK", "DEFEAT"}:
            target = d.get("target", d.get("actor"))
            if target not in roles:
                continue
            assert pending and pending[1] == target, f"{where}: feedback without matching damage"
            assert event not in pending[4], f"{where}: duplicate feedback"
            pending[4].add(event)
            if event == "COMBAT_FEEDBACK":
                assert d["feedback"] == "hit_flash", f"{where}: missing hit flash"
            elif event == "DEFEAT":
                assert health[target] == 0 and target not in defeats, f"{where}: invalid defeat"
                defeats.add(target)
        elif event in {"WEAPON_FIRE", "RIVAL_FIRE", "INFECTED_MELEE"}:
            source = d.get("owner", d.get("attacker"))
            if source not in roles:
                continue
            assert pending and pending[:4] == (source, d["target"], float(d["damage"]), event), f"{where}: attack/damage mismatch"
            expected = {"HIT_REACTION", "COMBAT_FEEDBACK"}
            if health[d["target"]] == 0:
                expected.add("DEFEAT")
            assert pending[4] == expected and d["hit"] == "true", f"{where}: missing runtime feedback"
            if event == "WEAPON_FIRE":
                ammo[source] -= 1
                assert int(d["ammo"]) == ammo[source], f"{where}: attack ammo mismatch"
            pending = None
    assert complete and phases == PHASES, f"missing completion/phases: {phases}"
    assert spawns == ["encounter_a_spawn", "encounter_a_spawn", "encounter_b_spawn"], "missing isolated guards or encounters"
    assert set(edges) == {f"{a}_to_{b}" for a in TEAMS for b in TEAMS if a != b}, f"missing directed damage edges: {edges}"
    assert len(defeats) == 4, f"expected four encounter defeats, found {len(defeats)}"
    assert set(intervals) == set(TEAMS), "missing repeated attacks to verify cooldowns"
    return {"log": str(path), "result": "PASS", "phases": len(phases), "damage_events": sum(edges.values()),
            "damage_edges": edges, "defeats": len(defeats), "duration_seconds": round(now - first_time, 3),
            "minimum_cadence_seconds": {role: round(value, 3) for role, value in intervals.items()}}


if __name__ == "__main__":
    try:
        assert len(sys.argv) > 1, "usage: verify_d01_031.py LOG [LOG ...]"
        print(json.dumps({"task": "D01-031", "result": "PASS", "runs": [verify(Path(p)) for p in sys.argv[1:]]}, separators=(",", ":")))
    except (AssertionError, KeyError, ValueError, OSError) as error:
        print(json.dumps({"task": "D01-031", "result": "FAIL", "error": str(error)}, separators=(",", ":")))
        sys.exit(1)
