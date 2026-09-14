#!/usr/bin/env python3
"""D01-43 continuous-process soak evidence gates; reuse D01-39 semantic checks."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import tempfile

from verify_d01_039 import numeric, read_capture, require, strict_object


def qualification_mode(seconds, cycles):
    return "QUALIFICATION" if seconds >= 900 and cycles >= 20 else "SMOKE_ONLY"


def warnings(content):
    return Counter(match.group(0).rstrip() for line in content.splitlines()
                   if (match := re.search(r"Log\w+: Warning:.*", line)))


def classify_log(content, baseline):
    require("**** TEST COMPLETE. EXIT CODE: 0 ****" in content, "Unreal completion missing")
    require(re.search(r"Result=\{Success\}.*Name=\{StabilitySoak\}", content), "Soak automation success missing")
    require("D01_043_TEST COMPLETE" in content, "Soak scenario completion missing")
    require(not re.search(r"Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:|"
                          r"Log\w+: Error:|VK_ERROR_DEVICE_LOST|D01_TELEMETRY_ERROR|D01_043_TEST FAIL", content),
            "Runtime error, crash, ensure, device loss or write failure")
    observed, prior = warnings(content), warnings(baseline)
    require(not (observed.keys() - prior.keys()), f"New warning signatures: {sorted(observed.keys() - prior.keys())}")
    return {"warnings": dict(observed), "baseline_warnings": dict(prior),
            "classification": "Exact previously observed signatures; warnings remain disclosed, not warning-free or leak-free."}


def verify_capture(path, seconds, cycles, reference):
    events = [json.loads(line, object_pairs_hook=strict_object) for line in Path(path).read_text().splitlines()]
    require(events, "Empty telemetry")
    session = events[0]["session"]
    for index, event in enumerate(events):
        require(event.get("schema") == "biella.demo01.telemetry/v1", "Wrong telemetry schema")
        require(event.get("session") == session and session, "Session changed")
        require(type(event.get("seq")) is int and event["seq"] == index + 1, "Broken original sequence")
        require(type(event.get("restart_count")) is int and event["restart_count"] >= 0, "Invalid restart count")
        require(isinstance(event.get("fields"), dict) and all(isinstance(k, str) and isinstance(v, str)
                for k, v in event["fields"].items()), "Malformed event fields")
        require(event.get("map") and event.get("event"), "Missing map/event")
        require(numeric(event["wall_seconds"], "wall") >= 0 and numeric(event["sim_seconds"], "sim") >= 0,
                "Invalid clocks")
        require(event["event"] not in ("scenario_failed", "soak_failed"), "Runtime scenario failed")
        if index:
            previous = events[index - 1]
            require(event["wall_seconds"] >= previous["wall_seconds"], "Wall clock regressed")
            require(previous["restart_count"] <= event["restart_count"] <= previous["restart_count"] + 1,
                    "Restart counter regressed/skipped")
            if (event["restart_count"] == previous["restart_count"] and
                previous["event"] != "restart_requested" and event["event"] != "telemetry_shutdown"):
                require(event["sim_seconds"] >= previous["sim_seconds"], "Simulation clock regressed without reload")
    require(events[0]["event"] == "telemetry_ready" and events[-1]["event"] == "telemetry_shutdown",
            "Incomplete telemetry lifecycle")
    require(sum(e["event"] == "telemetry_ready" for e in events) == 1, "Repeated telemetry lifecycle")
    soaks = [e for e in events if e["event"].startswith("soak_")]
    require(soaks and soaks[0]["event"] == "soak_begin" and soaks[-1]["event"] == "soak_complete", "Incomplete soak")
    require(sum(e["event"] == "soak_begin" for e in soaks) == 1 and
            sum(e["event"] == "soak_complete" for e in soaks) == 1, "Repeated soak markers")
    begin, end = soaks[0], soaks[-1]
    require(numeric(begin["fields"]["target_seconds"], "target_seconds") == seconds and
            int(begin["fields"]["target_cycles"]) == cycles, "Requested bounds differ")
    duration = end["wall_seconds"] - begin["wall_seconds"]
    require(duration >= seconds and numeric(end["fields"]["elapsed_wall_seconds"], "elapsed") >= seconds,
            "Insufficient continuous workload duration")
    instance = begin["fields"]["instance_id"]
    for e in soaks:
        f = e["fields"]
        require(f["instance_id"] == instance, "GameInstance changed")
        require(f["pose_finite"] == "true" and f["world_membership"] == "true" and f["assets_ready"] == "true",
                "Invalid pose/world/assets")
        require(int(f["actor_count"]) == 4, "Game actor membership changed")
        for axis in ("player_x", "player_y", "player_z"):
            numeric(f[axis], axis)
        if e["event"] in ("soak_begin", "soak_cycle_begin", "soak_cycle_end", "soak_complete"):
            require(f["clean_active_baseline"] == "true", "Clean baseline missing at cycle boundary")
        if f["phase"] == "natural":
            require(f["autonomous_ticks_enabled"] == "true", "Natural encounter AI was frozen")
        require(0 <= int(f["active_audio"]) <= 14 and 0 <= int(f["active_vfx"]) <= 24, "Feedback cap exceeded")
        require(int(f["restart_total"]) == e["restart_count"], "Reported restart mismatch")
    heartbeats = [e for e in soaks if e["event"] == "soak_heartbeat"]
    require(heartbeats, "No live heartbeats")
    progress = [begin, *heartbeats, end]
    gaps = [b["wall_seconds"] - a["wall_seconds"] for a, b in zip(progress, progress[1:])]
    require(max(gaps) <= 10, "Workload heartbeat stalled for more than 10 seconds")
    require(all(int(b["fields"]["frame_counter"]) > int(a["fields"]["frame_counter"])
                for a, b in zip(heartbeats, heartbeats[1:])), "Frame progress stalled")
    starts = [e for e in soaks if e["event"] == "soak_cycle_begin"]
    ends = [e for e in soaks if e["event"] == "soak_cycle_end"]
    count = int(end["fields"]["completed_cycles"])
    require(count >= cycles and len(starts) == len(ends) == count, "Insufficient/incomplete core cycles")
    require(sum(e["event"] == "scenario_begin" for e in events) == count and
            sum(e["event"] == "scenario_complete" for e in events) == count, "Unaccounted core scenarios")
    reference_trace, _ = read_capture(Path(reference))
    cycle_reports = []
    with tempfile.TemporaryDirectory(prefix="biella-d01-043-verify-") as directory:
        for i, (first, last) in enumerate(zip(starts, ends), 1):
            require(int(first["fields"]["cycle_index"]) == int(last["fields"]["cycle_index"]) == i,
                    "Cycle order mismatch")
            require(first["seq"] < last["seq"] and (i == 1 or ends[i - 2]["seq"] < first["seq"]),
                    "Overlapping cycle boundaries")
            original = [e for e in events[first["seq"]:last["seq"] - 1] if not e["event"].startswith("soak_")]
            # Only derived sequence is renumbered. Original timestamps, session,
            # restart counts and all semantic fields stay intact and above-checked.
            derived = [dict(e, seq=j) for j, e in enumerate(original, 1)]
            slice_path = Path(directory) / f"cycle-{i}.jsonl"
            slice_path.write_text("".join(json.dumps(e) + "\n" for e in derived))
            trace, summary = read_capture(slice_path)
            require(trace == reference_trace, f"Cycle {i} differs from qualified predecessor semantic trace")
            cycle_reports.append({"index": i, "first_seq": first["seq"], "last_seq": last["seq"],
                                  "events": summary["scenario_events"], "wall_seconds": summary["wall_seconds"]})
    natural_starts = [e for e in soaks if e["event"] == "soak_natural_begin"]
    natural_ends = [e for e in soaks if e["event"] == "soak_natural_end"]
    require(len(natural_starts) == len(natural_ends) == count - 1, "Missing autonomous dwell")
    dwell_reports = []
    for i, (a, b) in enumerate(zip(natural_starts, natural_ends)):
        require(ends[i]["seq"] < a["seq"] < b["seq"] < starts[i + 1]["seq"], "Dwell order mismatch")
        wall = b["wall_seconds"] - a["wall_seconds"]
        require(wall >= 5 and b["sim_seconds"] > a["sim_seconds"], "Autonomous dwell did not run")
        require(numeric(b["fields"]["natural_elapsed_seconds"], "natural elapsed") >= 5 and
                numeric(b["fields"]["natural_max_displacement"], "natural displacement") > 1,
                "Autonomous actors did not move")
        live = Counter(e["event"] for e in events[a["seq"]:b["seq"] - 1])
        require(live["damage"] + live["weapon_fire"] > 0, "No live autonomous combat during dwell")
        dwell_reports.append({"first_seq": a["seq"], "last_seq": b["seq"], "wall_seconds": wall,
                              "sim_seconds": b["sim_seconds"] - a["sim_seconds"], "events": dict(live)})
    return {"result": "PASS", "mode": qualification_mode(seconds, cycles), "session": session,
            "instance_id": instance, "records": len(events), "workload_wall_seconds": duration,
            "completed_cycles": count, "terminal_restarts": count * 2,
            "total_restarts": end["restart_count"] - begin["restart_count"],
            "heartbeats": len(heartbeats), "maximum_heartbeat_gap_seconds": max(gaps),
            "cycles": cycle_reports, "autonomous_dwells": dwell_reports,
            "trace_sha256": hashlib.sha256(json.dumps(reference_trace, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "derivation": "Full original capture validated first; exclude soak_* and renumber seq per cycle for unmodified D01-39 reader; compare all normalized events to retained predecessor."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=900)
    parser.add_argument("--cycles", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(verify_capture(args.capture, args.seconds, args.cycles, args.reference), indent=2))
